"""
# Memory API for Cybers.

## Core Concept: Everything is Memory
The `memory` object provides unified access to everything in Mind-Swarm.
This provides a way to safely mutate memories and so progress towards goals and task.

Everything is memory. This module provides a unified interface for all memory operations
including files, messages, goals, and any other data in the Mind-Swarm ecosystem.
    
## Important Examples

### Reading Memory (any access will load the memory into working memory)
```python
# Bracket notation is the ONLY way to access memory
info = memory["/grid/community/school/onboarding/new_cyber_introduction/intro.yaml"]
notes = memory["/personal/notes/important"]
# Check if memory exists
if memory.exists("/personal/data.json"):
    data = memory["/personal/data.json"]
```

### Writing Memory
```python
# Create or update memory
memory["/personal/journal/today"] = "Today I learned about the memory API"
```

### Type Checking - Know Your Data Types!
```python
# IMPORTANT: Always check content type before using it
# Files like .yaml and .json are automatically parsed, but you should verify

# Example 1: Safely handle tasks that might be JSON or string
tasks_node = memory["/personal/tasks"]
if hasattr(tasks_node, 'content'):
    tasks_data = tasks_node.content
    
    # Check if it's already parsed (list/dict) or raw string
    if isinstance(tasks_data, str):
        # It's a raw string, parse it
        import json
        try:
            tasks = json.loads(tasks_data)
        except json.JSONDecodeError:
            print(f"Tasks is plain text: {tasks_data}")
            tasks = []
    elif isinstance(tasks_data, list):
        # Already parsed as list
        tasks = tasks_data
    elif isinstance(tasks_data, dict):
        # Already parsed as dict
        tasks = tasks_data.get('tasks', [])
    else:
        print(f"Unexpected type: {type(tasks_data)}")
        tasks = []
        
    # Now safely iterate
    for task in tasks:
        if isinstance(task, dict) and task.get("id") == "task_001":
            task["status"] = "completed"

# Example 2: Working with YAML/JSON files
config = memory["/personal/config.yaml"].content
if isinstance(config, dict):
    # It's parsed YAML/JSON - safe to use as dict
    config["updated"] = True
elif isinstance(config, str):
    # It's raw text - parse it first
    import yaml
    config = yaml.safe_load(config)
    config["updated"] = True
    memory["/personal/config.yaml"] = config

# Example 3: Type hints for better code
def update_task(task_id: str, status: str):
    tasks_node = memory["/personal/tasks"]
    content = tasks_node.content if hasattr(tasks_node, 'content') else tasks_node
    
    # Always validate type before operations
    if not isinstance(content, list):
        if isinstance(content, str):
            import json
            content = json.loads(content)
        else:
            raise TypeError(f"Expected list or JSON string, got {type(content)}")
    
    for task in content:
        if isinstance(task, dict) and task.get("id") == task_id:
            task["status"] = status
            break
    
    memory["/personal/tasks"] = content
```

### Transactions for Safety
```python
# Multiple operations succeed or fail together
try:
    with memory.transaction():
        # Read existing data
        data = memory["/personal/config.json"]
        
        # Modify JSON data directly (if it's JSON)
        if hasattr(data, 'content') and isinstance(data.content, dict):
            data.content["updated"] = "2024-01-01"
            # Changes are saved automatically
        
        # Save backup
        memory["/personal/backup/config"] = data.content
        
        # Send confirmation message via outbox
        import time
        memory[f"/personal/outbox/msg_{int(time.time())}"] = {
            "to": "user", 
            "content": "Config updated and backed up",
            "msg_type": "CONFIRMATION"
        }       
except MemoryError as e:
    print(f"Transaction failed, all changes rolled back: {e}")
```

### Creating Memory Groups
```python
# Create organized structure
try:
    memory.make_memory_group("/personal/projects")
    memory.make_memory_group("/personal/projects/current")
    memory["/personal/projects/current/status"] = "Active"
    print("Project structure created")
except MemoryError as e:
    print(f"ERROR: {e}")
```
## Key Rules
1. **Automatic save** - Changes persist immediately, unless in a transaction
2. **Transaction safety** - Use transactions for critical operations
3. **Everything is memory** - Think in terms of memory, not files
4. **Type checking** - Always verify data types before operations (use isinstance())
5. **Parse when needed** - YAML/JSON files auto-parse but always check type first
"""

import json
import yaml
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime
from contextlib import contextmanager
from collections.abc import MutableMapping, MutableSequence


class MemoryError(Exception):
    """Base exception for memory operations."""
    pass


class MemoryNotFoundError(MemoryError):
    """Raised when trying to access non-existent memory."""
    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Memory not found: {path}")


class NotAMemoryGroupError(MemoryError):
    """Raised when trying to create a memory group where a memory already exists."""
    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Cannot create memory group at '{path}': a memory already exists there")


class MemoryPermissionError(MemoryError):
    """Raised when lacking permission to access memory."""
    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Permission denied: {path}")


class MemoryTypeError(MemoryError):
    """Raised when memory type doesn't match expected."""
    pass


class TrackedDict(dict):
    """Dictionary that tracks modifications and notifies parent MemoryNode."""
    
    def __init__(self, data: dict, memory_node: 'MemoryNode'):
        # Recursively wrap nested dicts and lists before initializing
        wrapped_data = {}
        for k, v in data.items():
            if isinstance(v, dict) and not isinstance(v, TrackedDict):
                wrapped_data[k] = TrackedDict(v, memory_node)
            elif isinstance(v, list) and not isinstance(v, TrackedList):
                wrapped_data[k] = TrackedList(v, memory_node)
            else:
                wrapped_data[k] = v
        super().__init__(wrapped_data)
        self._memory_node = memory_node
    
    def __getitem__(self, key):
        """Wrap nested structures when accessed."""
        value = super().__getitem__(key)
        # Wrap on access in case something wasn't wrapped initially
        if isinstance(value, dict) and not isinstance(value, TrackedDict):
            wrapped = TrackedDict(value, self._memory_node)
            super().__setitem__(key, wrapped)
            return wrapped
        elif isinstance(value, list) and not isinstance(value, TrackedList):
            wrapped = TrackedList(value, self._memory_node)
            super().__setitem__(key, wrapped)
            return wrapped
        return value
    
    def __setitem__(self, key, value):
        # Wrap nested structures when setting
        if isinstance(value, dict) and not isinstance(value, TrackedDict):
            value = TrackedDict(value, self._memory_node)
        elif isinstance(value, list) and not isinstance(value, TrackedList):
            value = TrackedList(value, self._memory_node)
        super().__setitem__(key, value)
        self._notify_change()
    
    def __delitem__(self, key):
        super().__delitem__(key)
        self._notify_change()
    
    def pop(self, *args, **kwargs):
        result = super().pop(*args, **kwargs)
        self._notify_change()
        return result
    
    def popitem(self):
        result = super().popitem()
        self._notify_change()
        return result
    
    def clear(self):
        super().clear()
        self._notify_change()
    
    def update(self, *args, **kwargs):
        # Wrap any nested structures in the update
        if args and len(args) == 1:
            if isinstance(args[0], dict):
                wrapped = {}
                for k, v in args[0].items():
                    if isinstance(v, dict) and not isinstance(v, TrackedDict):
                        wrapped[k] = TrackedDict(v, self._memory_node)
                    elif isinstance(v, list) and not isinstance(v, TrackedList):
                        wrapped[k] = TrackedList(v, self._memory_node)
                    else:
                        wrapped[k] = v
                super().update(wrapped)
            else:
                super().update(args[0])
        else:
            # Handle kwargs
            wrapped_kwargs = {}
            for k, v in kwargs.items():
                if isinstance(v, dict) and not isinstance(v, TrackedDict):
                    wrapped_kwargs[k] = TrackedDict(v, self._memory_node)
                elif isinstance(v, list) and not isinstance(v, TrackedList):
                    wrapped_kwargs[k] = TrackedList(v, self._memory_node)
                else:
                    wrapped_kwargs[k] = v
            super().update(*args, **wrapped_kwargs)
        self._notify_change()
    
    def setdefault(self, key, default=None):
        # Wrap default if it's a dict or list
        if isinstance(default, dict) and not isinstance(default, TrackedDict):
            default = TrackedDict(default, self._memory_node)
        elif isinstance(default, list) and not isinstance(default, TrackedList):
            default = TrackedList(default, self._memory_node)
        result = super().setdefault(key, default)
        self._notify_change()
        return result
    
    def _notify_change(self):
        """Notify the parent MemoryNode that content has changed."""
        self._memory_node._modified = True
        if self._memory_node._memory._auto_save:
            self._memory_node._save()
    
    def __reduce__(self):
        """Make TrackedDict serialize as a regular dict.
        
        This ensures that when Cybers save data, they get plain dicts,
        not TrackedDict objects with internal implementation details.
        """
        return (dict, (dict(self),))
    
    def __getstate__(self):
        """Return state for pickling as a regular dict."""
        return dict(self)
    
    def __setstate__(self, state):
        """Restore from pickled state."""
        self.clear()
        self.update(state)
    
    @classmethod
    def __get_validators__(cls):
        """Pydantic validator to treat as regular dict."""
        yield lambda v: dict(v) if isinstance(v, cls) else v
    
    def to_dict(self):
        """Convert to a regular dictionary (for explicit conversion)."""
        return dict(self)


class TrackedList(list):
    """List that tracks modifications and notifies parent MemoryNode."""
    
    def __init__(self, data: list, memory_node: 'MemoryNode'):
        # Recursively wrap nested dicts and lists before initializing
        wrapped_data = []
        for item in data:
            if isinstance(item, dict) and not isinstance(item, TrackedDict):
                wrapped_data.append(TrackedDict(item, memory_node))
            elif isinstance(item, list) and not isinstance(item, TrackedList):
                wrapped_data.append(TrackedList(item, memory_node))
            else:
                wrapped_data.append(item)
        super().__init__(wrapped_data)
        self._memory_node = memory_node
    
    def __getitem__(self, key):
        """Wrap nested structures when accessed."""
        value = super().__getitem__(key)
        # Wrap on access in case something wasn't wrapped initially
        if isinstance(value, dict) and not isinstance(value, TrackedDict):
            wrapped = TrackedDict(value, self._memory_node)
            super().__setitem__(key, wrapped)
            return wrapped
        elif isinstance(value, list) and not isinstance(value, TrackedList):
            wrapped = TrackedList(value, self._memory_node)
            super().__setitem__(key, wrapped)
            return wrapped
        return value
    
    def __setitem__(self, key, value):
        # Wrap nested structures when setting
        if isinstance(value, dict) and not isinstance(value, TrackedDict):
            value = TrackedDict(value, self._memory_node)
        elif isinstance(value, list) and not isinstance(value, TrackedList):
            value = TrackedList(value, self._memory_node)
        super().__setitem__(key, value)
        self._notify_change()
    
    def __delitem__(self, key):
        super().__delitem__(key)
        self._notify_change()
    
    def append(self, value):
        # Wrap nested structures when appending
        if isinstance(value, dict) and not isinstance(value, TrackedDict):
            value = TrackedDict(value, self._memory_node)
        elif isinstance(value, list) and not isinstance(value, TrackedList):
            value = TrackedList(value, self._memory_node)
        super().append(value)
        self._notify_change()
    
    def extend(self, iterable):
        # Wrap nested structures in the iterable
        wrapped = []
        for item in iterable:
            if isinstance(item, dict) and not isinstance(item, TrackedDict):
                wrapped.append(TrackedDict(item, self._memory_node))
            elif isinstance(item, list) and not isinstance(item, TrackedList):
                wrapped.append(TrackedList(item, self._memory_node))
            else:
                wrapped.append(item)
        super().extend(wrapped)
        self._notify_change()
    
    def insert(self, index, value):
        # Wrap nested structures when inserting
        if isinstance(value, dict) and not isinstance(value, TrackedDict):
            value = TrackedDict(value, self._memory_node)
        elif isinstance(value, list) and not isinstance(value, TrackedList):
            value = TrackedList(value, self._memory_node)
        super().insert(index, value)
        self._notify_change()
    
    def remove(self, value):
        super().remove(value)
        self._notify_change()
    
    def pop(self, *args):
        result = super().pop(*args)
        self._notify_change()
        return result
    
    def clear(self):
        super().clear()
        self._notify_change()
    
    def sort(self, *args, **kwargs):
        super().sort(*args, **kwargs)
        self._notify_change()
    
    def reverse(self):
        super().reverse()
        self._notify_change()
    
    def _notify_change(self):
        """Notify the parent MemoryNode that content has changed."""
        self._memory_node._modified = True
        if self._memory_node._memory._auto_save:
            self._memory_node._save()
    
    def __reduce__(self):
        """Make TrackedList serialize as a regular list.
        
        This ensures that when Cybers save data, they get plain lists,
        not TrackedList objects with internal implementation details.
        """
        return (list, (list(self),))
    
    def __getstate__(self):
        """Return state for pickling as a regular list."""
        return list(self)
    
    def __setstate__(self, state):
        """Restore from pickled state."""
        self.clear()
        self.extend(state)
    
    @classmethod
    def __get_validators__(cls):
        """Pydantic validator to treat as regular list."""
        yield lambda v: list(v) if isinstance(v, cls) else v
    
    def to_list(self):
        """Convert to a regular list (for explicit conversion)."""
        return list(self)


class MemoryNode:
    """Represents a single memory location that can be read or written."""
    
    def __init__(self, path: str, memory_system: 'Memory', new: bool = False):
        self.path = path
        self._memory = memory_system
        self._new = new
        self._content = None
        self._type = None
        self._metadata = {}
        self._modified = False
        
        if not new:
            self._load()
    
    def __getitem__(self, key):
        """Allow subscript access to content for dict/list data."""
        if self._content is None:
            self._load()
        
        # Ensure content is wrapped for tracking
        if isinstance(self._content, dict) and not isinstance(self._content, TrackedDict):
            self._content = TrackedDict(self._content, self)
        elif isinstance(self._content, list) and not isinstance(self._content, TrackedList):
            self._content = TrackedList(self._content, self)
        
        if isinstance(self._content, (dict, list)):
            return self._content[key]
        else:
            raise TypeError(f"Memory at {self.path} is not subscriptable (type: {type(self._content).__name__})")
    
    def __setitem__(self, key, value):
        """Allow subscript assignment for dict/list data."""
        if self._content is None:
            self._load()
        
        if isinstance(self._content, dict):
            self._content[key] = value
            self._modified = True
            # Auto-save if configured
            if self._memory._auto_save:
                self._save()
        elif isinstance(self._content, list):
            self._content[key] = value
            self._modified = True
            # Auto-save if configured
            if self._memory._auto_save:
                self._save()
        else:
            raise TypeError(f"Memory at {self.path} does not support item assignment (type: {type(self._content).__name__})")
    
    def _load(self):
        """Load content from the memory path."""
        try:
            actual_path = self._memory._resolve_path(self.path)
            
            if not actual_path.exists():
                raise MemoryNotFoundError(self.path)
            
            if actual_path.is_dir():
                self._type = "memory/group"
                # For directories, content is the list of items
                self._content = [item.name for item in actual_path.iterdir()]
            else:
                # Determine type from extension
                if actual_path.suffix == '.json':
                    self._type = "application/json"
                    with open(actual_path, 'r') as f:
                        content_str = f.read()
                    try:
                        self._content = json.loads(content_str)
                    except json.JSONDecodeError as e:
                        # Give feedback to cyber about corrupted file
                        print(f"⚠️ WARNING: Corrupted JSON file detected: {self.path}")
                        print(f"   Error: {e}")
                        print(f"   File content: {content_str[:100]}..." if len(content_str) > 100 else f"   File content: {content_str}")
                        print(f"   Returning empty dict - you may want to recreate this file")
                        self._content = {}  # Return empty dict for corrupted JSON files
                elif actual_path.suffix in ['.yaml', '.yml']:
                    import yaml
                    self._type = "application/yaml"
                    with open(actual_path, 'r') as f:
                        self._content = yaml.safe_load(f)
                else:
                    # For files without extension, try to detect JSON content
                    with open(actual_path, 'r') as f:
                        content_str = f.read()
                    
                    # Try to parse as JSON first
                    try:
                        self._content = json.loads(content_str)
                        self._type = "application/json"
                    except (json.JSONDecodeError, ValueError):
                        # Not JSON, treat as plain text
                        self._type = "text/plain"
                        self._content = content_str
                
                # Track that this file was accessed for transaction commit
                if not actual_path.is_dir():
                    self._memory._track_access(self.path, self._type)
                        
        except Exception as e:
            if not isinstance(e, MemoryError):
                raise MemoryError(f"Failed to load {self.path}: {e}")
            raise
    
    def _save(self):
        """Save content to the memory path."""
        if not self._modified and not self._new:
            return
            
        try:
            actual_path = self._memory._resolve_path(self.path)
            
            # Create parent directories if needed
            actual_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Unwrap tracked objects back to plain dict/list for saving
            content_to_save = self._content
            if isinstance(self._content, TrackedDict):
                content_to_save = dict(self._content)
            elif isinstance(self._content, TrackedList):
                content_to_save = list(self._content)
            
            # Save based on type
            if self._type == "application/json":
                # First serialize to string to catch any errors before truncating file
                try:
                    json_string = json.dumps(content_to_save, indent=2)
                except (TypeError, ValueError) as e:
                    # Log error for cyber to see
                    print(f"⚠️ WARNING: Cannot save non-serializable content to JSON file {self.path}")
                    print(f"   Error: {e}")
                    print(f"   Converting non-serializable objects to strings...")
                    # Try again with default=str to convert non-serializable objects
                    json_string = json.dumps(content_to_save, indent=2, default=str)
                    print(f"   ✓ Saved with string conversion")
                # Only write if serialization succeeded
                with open(actual_path, 'w') as f:
                    f.write(json_string)
            elif self._type == "application/yaml":
                # Save as YAML, not JSON!
                import yaml
                try:
                    yaml_string = yaml.dump(content_to_save, default_flow_style=False, sort_keys=False)
                except Exception as e:
                    print(f"⚠️ WARNING: Cannot save content to YAML file {self.path}")
                    print(f"   Error: {e}")
                    # Fall back to JSON format as last resort
                    print(f"   Falling back to JSON format...")
                    yaml_string = json.dumps(content_to_save, indent=2, default=str)
                    print(f"   ⚠️ File saved as JSON despite .yaml extension")
                with open(actual_path, 'w') as f:
                    f.write(yaml_string)
            else:
                with open(actual_path, 'w') as f:
                    f.write(str(content_to_save))
            
            # Track change for potential rollback
            self._memory._track_change(self.path, 'write', content_to_save)
            
            # Track that this file was written for transaction commit
            self._memory._track_write(self.path, self._type, self._new)
            
            self._modified = False
            self._new = False
            
        except Exception as e:
            raise MemoryError(f"Failed to save {self.path}: {e}")
    
    @property
    def content(self):
        """Get the memory content, wrapped in tracking if mutable."""
        if isinstance(self._content, dict) and not isinstance(self._content, TrackedDict):
            # Wrap dict in TrackedDict for automatic change tracking
            self._content = TrackedDict(self._content, self)
        elif isinstance(self._content, list) and not isinstance(self._content, TrackedList):
            # Wrap list in TrackedList for automatic change tracking
            self._content = TrackedList(self._content, self)
        return self._content
    
    @content.setter
    def content(self, value):
        """Set the memory content."""
        # Check if someone is trying to save a MemoryNode directly
        if isinstance(value, MemoryNode):
            raise MemoryTypeError(
                f"Cannot save a MemoryNode object directly. "
                f"Did you mean to use .content? "
                f"Example: memory['{self.path}'] = other_memory.content"
            )
        self._content = value
        self._modified = True
        # Auto-detect type if not set, considering file extension
        if self._type is None:
            # Check file extension first
            actual_path = self._memory._resolve_path(self.path)
            if actual_path.suffix in ['.yaml', '.yml']:
                self._type = "application/yaml"
            elif actual_path.suffix == '.json':
                self._type = "application/json"
            elif isinstance(value, dict) or isinstance(value, list):
                # Default to JSON for dict/list without explicit extension
                self._type = "application/json"
            else:
                self._type = "text/plain"
        # Auto-save in transaction mode
        if self._memory._auto_save:
            self._save()
    
    @property
    def type(self):
        """Get the memory type."""
        return self._type
    
    @type.setter
    def type(self, value):
        """Set the memory type."""
        self._type = value
        self._modified = True
    
    @property
    def exists(self):
        """Check if this memory exists."""
        actual_path = self._memory._resolve_path(self.path)
        return actual_path.exists()
    
    def __str__(self):
        """String representation returns content."""
        return str(self._content)
    
    def __repr__(self):
        return f"MemoryNode(path={self.path}, type={self._type})"


class MemoryGroup:
    """Provides attribute-style and subscript access to a memory group (directory).
    A MemoryGroup represents a directory in the memory system. You can access
    sub-memories using
    subscript notation (memory['personal']['notes']).    
    """
    
    def __init__(self, base_path: str, memory_system: 'Memory'):
        self._base_path = base_path.rstrip('/')
        self._memory = memory_system
    
    # Removed __getattr__ and __setattr__ - only bracket notation is supported
    # This prevents confusion with file extensions like .json, .txt, etc.
    
    def __getitem__(self, key: str):
        """Allow subscript access to sub-memories."""
        # Same logic as __getattr__ but for subscript notation
        path = f"{self._base_path}/{key}"
        actual_path = self._memory._resolve_path(path)
        
        # If it exists and is a directory, return a MemoryGroup
        if actual_path.exists() and actual_path.is_dir():
            return MemoryGroup(path, self._memory)
        # If it doesn't exist, assume it will be a directory
        elif not actual_path.exists():
            return MemoryGroup(path, self._memory)
        # Otherwise it's a file, return a MemoryNode
        else:
            return self._memory[path]
    
    def __setitem__(self, key: str, value: Any):
        """Set memory via subscript."""
        # Check if someone is trying to save a MemoryNode directly
        if isinstance(value, MemoryNode):
            raise MemoryTypeError(
                f"Cannot save a MemoryNode object directly to '{self._base_path}/{key}'. "
                f"Did you mean to use .content? "
                f"Example: memory['{self._base_path}/{key}'] = other_memory.content"
            )
        # Same logic as __setattr__ but for subscript notation
        path = f"{self._base_path}/{key}"
        actual_path = self._memory._resolve_path(path)
        
        # Create parent directory if it doesn't exist
        parent_dir = actual_path.parent
        if not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)
            self._memory._track_change(str(parent_dir), 'mkdir')
        
        # Now create and save the node
        node = MemoryNode(path, self._memory, new=True)
        node.content = value
        node._save()
    
    def __iter__(self):
        """Iterate over memories in this group."""
        actual_path = self._memory._resolve_path(self._base_path)
        if actual_path.exists() and actual_path.is_dir():
            for item in actual_path.iterdir():
                relative_name = item.name
                full_path = f"{self._base_path}/{relative_name}"
                if item.is_dir():
                    yield MemoryGroup(full_path, self._memory)
                else:
                    yield self._memory[full_path]
    
    def __repr__(self):
        return f"MemoryGroup(path={self._base_path})"


# OutboxHelper removed - use bracket notation to create messages in /personal/outbox/

class Memory:
    """
Main memory interface providing unified access to all Mind-Swarm memories.
    The Memory class provides methods to read, write, and manage memories"""
    
    def __init__(self, context: Dict[str, Any]):
        """Initialize the memory system.
        
        Args:
            context: Execution context with cyber_id, paths, etc.
        """
        self._context = context
        self._changes = []  # Track changes for rollback
        self._auto_save = True  # Auto-save on modifications
        self._transaction_depth = 0
        
        # Set up root paths
        self._personal_root = Path(context.get('personal_dir', '/personal'))
        self._grid_root = Path('/grid')
        
        # Get references to memory system and cognitive loop
        self._memory_system = context['memory_system']
        self._cognitive_loop = context['cognitive_loop']
        
        # Track accessed and written files for transaction commit
        self._accessed_files = []
        
        # Initialize knowledge API (lazy loaded)
        self._knowledge = None
        self._written_files = []
    
    def _clean_path(self, path: str) -> str:
        """Clean a path by removing any type prefix.
        
        Accepts both formats:
        - "knowledge:personal/goals/..." -> "personal/goals/..."
        - "personal/goals/..." -> "personal/goals/..." (unchanged)
        
        Note: We only run on Linux, so no need to handle Windows paths.
        """
        if ':' in path and not path.startswith('/'):
            # Strip the prefix (everything before and including first ':')
            return path.split(':', 1)[1]
        return path
    
    def _resolve_path(self, path: str) -> Path:
        """Resolve a memory path to actual filesystem path.
        
        Valid path formats:
        - '/personal/...' - Absolute personal path
        - 'personal/...' - Relative personal path
        - '/grid/...' - Absolute grid path
        - 'grid/...' - Relative grid path
        - 'type:path' - Memory ID format (prefix will be stripped)
        
        Restricted paths:
        - Paths containing '.internal' are forbidden (system use only)
        """
        original_path = path
        
        # First clean the path to remove any type prefix
        path = self._clean_path(path)
        
        # Security check: reject access to .internal directories
        if '.internal' in path:
            raise MemoryError(
                f"Access denied: Cannot read or write to system directories (.internal). "
                f"Path: '{original_path}'. "
                f"The .internal directory is reserved for system use only."
            )
        
        if path.startswith('/personal'):
            return self._personal_root / path[10:]  # Remove '/personal/'
        elif path.startswith('personal/'):
            # Already relative to personal, just remove the 'personal/' prefix
            return self._personal_root / path[9:]  # Remove 'personal/'
        elif path.startswith('/grid'):
            return Path(path)
        elif path.startswith('grid/'):
            # Relative grid path
            return Path('/') / path
        else:
            # No valid namespace found - this is an error
            raise MemoryError(
                f"Invalid memory path: '{original_path}'. "
                f"Path must start with 'personal/', '/personal/', 'grid/', or '/grid/'. "
                f"After stripping any type prefix, got: '{path}'"
            )
    
    def _track_change(self, path: str, operation: str, data: Any = None):
        """Track a change for potential rollback."""
        if self._transaction_depth > 0:
            # For rollback, we need to store the previous state
            rollback_info = {
                'path': path,
                'operation': operation,
                'data': data,
                'timestamp': datetime.now()
            }
            
            # Store backup data for rollback based on operation type
            if operation == 'write':
                # Store previous content if file existed
                actual_path = self._resolve_path(path)
                if actual_path.exists():
                    with open(actual_path, 'r') as f:
                        rollback_info['previous_content'] = f.read()
                    rollback_info['existed'] = True
                else:
                    rollback_info['existed'] = False
                    
            elif operation == 'delete':
                # Store content before deletion
                actual_path = self._resolve_path(path)
                if actual_path.exists() and actual_path.is_file():
                    with open(actual_path, 'r') as f:
                        rollback_info['previous_content'] = f.read()
                        
            elif operation == 'mkdir':
                # Just track that we created this directory
                rollback_info['created'] = True
                
            elif operation == 'rmdir':
                # Move to temp for potential rollback instead of immediate deletion
                actual_path = self._resolve_path(path)
                if actual_path.exists() and actual_path.is_dir():
                    import tempfile
                    import shutil
                    # Create a temp directory to hold the backup
                    temp_backup = tempfile.mkdtemp(prefix="rollback_", suffix=f"_{actual_path.name}")
                    # Move the directory to temp location
                    backup_path = Path(temp_backup) / actual_path.name
                    shutil.move(str(actual_path), str(backup_path))
                    rollback_info['backup_path'] = str(backup_path)
                    rollback_info['original_path'] = str(actual_path)
                    print(f"📦 Directory moved to temp for potential rollback: {path}")
                    
            elif operation == 'move':
                # Store the move operation for reversal
                rollback_info['from_path'] = path
                rollback_info['to_path'] = data.get('to') if data else None
                
            elif operation == 'evict':
                # Store that this was in working memory
                rollback_info['was_in_memory'] = True
                # Use path directly as memory ID (no type prefix)
                rollback_info['memory_id'] = path
            
            self._changes.append(rollback_info)
    
    def _track_access(self, path: str, file_type: str):
        """Track file access for adding to working memory on commit."""
        if self._transaction_depth > 0:
            # Clean the path to remove any type prefix before tracking
            clean_path = self._clean_path(path)
            self._accessed_files.append({'path': clean_path, 'type': file_type})
    
    def _track_write(self, path: str, file_type: str, is_new: bool):
        """Track file write for adding to working memory on commit."""
        if self._transaction_depth > 0:
            # Clean the path to remove any type prefix before tracking
            clean_path = self._clean_path(path)
            self._written_files.append({'path': clean_path, 'type': file_type, 'new': is_new})
    
    def __getitem__(self, path: str):
        """Dictionary-style access to memory."""
        # Handle root directory access
        if path in ['personal', '/personal', 'grid', '/grid']:
            if path.lstrip('/') == 'personal':
                return MemoryGroup('/personal', self)
            else:
                return MemoryGroup('/grid', self)
        
        # Clean the path to allow both prefixed and non-prefixed formats
        clean_path = self._clean_path(path)
        
        # Check if this is a directory that should return a MemoryGroup
        actual_path = self._resolve_path(clean_path)
        if actual_path.exists() and actual_path.is_dir():
            return MemoryGroup('/' + clean_path.lstrip('/'), self)
        
        # Otherwise return a MemoryNode (file or not-yet-existing path)
        return MemoryNode(clean_path, self)
    
    def __setitem__(self, path: str, value: Any):
        """Dictionary-style memory assignment."""
        # Check if someone is trying to save a MemoryNode directly
        if isinstance(value, MemoryNode):
            raise MemoryTypeError(
                f"Cannot save a MemoryNode object directly to '{path}'. "
                f"Did you mean to use .content? "
                f"Example: memory['{path}'] = other_memory.content"
            )
        # Clean the path to allow both prefixed and non-prefixed formats
        clean_path = self._clean_path(path)
        node = MemoryNode(clean_path, self, new=True)
        node.content = value
        node._save()
    
    # Removed __getattr__ - only bracket notation is supported
    # Use memory["/personal/..."] or memory["/grid/..."] instead
    
    def create(self, path: str) -> MemoryNode:
        """
Create a new memory at the specified path.
Args: path - Memory path like "/personal/notes.txt" or "knowledge:personal/notes.txt"
Returns: MemoryNode that can be modified and saved
"""
        clean_path = self._clean_path(path)
        return MemoryNode(clean_path, self, new=True)
    
    def make_memory_group(self, path: str):
        """
Create a memory group at the specified path.                
Args: path - Group path like "/personal/projects" or "knowledge:personal/projects"            
Raises:
    NotAMemoryGroupError: If a memory already exists at this path
    MemoryError: If creation fails for other reasons
"""
        clean_path = self._clean_path(path)
        actual_path = self._resolve_path(clean_path)
        
        # Check if there's already a file (memory) at this path
        if actual_path.exists() and actual_path.is_file():
            raise NotAMemoryGroupError(path)
        
        try:
            actual_path.mkdir(parents=True, exist_ok=True)
            self._track_change(path, 'mkdir')
        except NotADirectoryError:
            # This happens when a parent in the path is a file, not a directory
            raise NotAMemoryGroupError(path)
        except Exception as e:
            raise MemoryError(f"Failed to create memory group at '{path}': {e}")
    
    def has_memory(self, path: str) -> bool:
        """
Check if a memory exists at the path.
Args: path - Memory path to check (with or without prefix)            
Returns: True if memory exists, False otherwise
"""
        clean_path = self._clean_path(path)
        actual_path = self._resolve_path(clean_path)
        return actual_path.exists() and actual_path.is_file()
    
    def has_group(self, path: str) -> bool:
        """
Check if a memory group exists at the path.
Args: path - Group path to check (with or without prefix)
Returns: True if group exists, False otherwise
"""
        clean_path = self._clean_path(path)
        actual_path = self._resolve_path(clean_path)
        return actual_path.exists() and actual_path.is_dir()
    
    def exists(self, path: str) -> bool:
        """
Check if anything (memory or group) exists at the path.
Args: path- Path to check (with or without prefix)
Returns: True if path exists, False otherwise
"""
        clean_path = self._clean_path(path)
        actual_path = self._resolve_path(clean_path)
        return actual_path.exists()
    
    def list_memories(self, path: str) -> List[str]:
        """List all memories in a group."""
        clean_path = self._clean_path(path)
        actual_path = self._resolve_path(clean_path)
        if not actual_path.exists() or not actual_path.is_dir():
            return []
        return [item.name for item in actual_path.iterdir() if item.is_file()]
    
    def list_groups(self, path: str) -> List[str]:
        """List all sub-groups in a group."""
        clean_path = self._clean_path(path)
        actual_path = self._resolve_path(clean_path)
        if not actual_path.exists() or not actual_path.is_dir():
            return []
        return [item.name for item in actual_path.iterdir() if item.is_dir()]
        
    def search(self, query: str, path: str = "/personal", limit: int = 10) -> List[MemoryNode]:
        """Search for memories containing the query string."""
        results = []
        clean_path = self._clean_path(path)
        search_root = self._resolve_path(clean_path)
        
        if not search_root.exists():
            return results
        
        for file_path in search_root.rglob('*'):
            if file_path.is_file() and len(results) < limit:
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        if query.lower() in content.lower():
                            memory_path = str(file_path).replace(str(self._personal_root), '/personal')
                            results.append(self[memory_path])
                except:
                    continue
        
        return results
    
    @contextmanager
    def transaction(self):
        """Context manager for transactional memory operations."""
        self._transaction_depth += 1
        self._auto_save = True
        checkpoint = len(self._changes)
        
        try:
            yield self
            # If successful, commit the transaction
            self.commit()
        except Exception as e:
            # On exception, rollback to checkpoint
            self.rollback()
            raise
    
    def begin_transaction(self):
        """Start tracking changes for potential rollback."""
        self._transaction_depth += 1
    
    def commit(self):
        """Commit all pending changes."""
        if self._transaction_depth > 0:
            self._transaction_depth -= 1
        if self._transaction_depth == 0:
            # Clean up any temp backups from rmdir operations
            for change in self._changes:
                if change['operation'] == 'rmdir' and 'backup_path' in change:
                    import shutil
                    backup_path = Path(change['backup_path'])
                    if backup_path.exists():
                        # Actually delete the backed-up directory
                        shutil.rmtree(backup_path)
                        # Clean up the temp directory
                        if backup_path.parent.exists():
                            try:
                                backup_path.parent.rmdir()
                            except:
                                pass  # Might not be empty
                        print(f"✓ Finalized deletion of {change['path']}")
            
            # Add accessed and written files to working memory
            from ..memory.memory_blocks import FileMemoryBlock
            from ..memory.memory_types import Priority
            
            # Add accessed files
            for file_info in self._accessed_files:
                memory_block = FileMemoryBlock(
                    location=file_info['path'],
                    priority=Priority.MEDIUM,
                    confidence=1.0,
                    metadata={
                        "source": "script_read",
                        "cycle": self._cognitive_loop.cycle_count
                    }
                )
                self._memory_system.add_memory(memory_block)
            
            # Add written files
            for file_info in self._written_files:
                memory_block = FileMemoryBlock(
                    location=file_info['path'],
                    priority=Priority.MEDIUM,
                    confidence=1.0,
                    metadata={
                        "source": "script_write",
                        "cycle": self._cognitive_loop.cycle_count,
                        "new": file_info['new']
                    }
                )
                self._memory_system.add_memory(memory_block)
            
            # Clear all tracking
            self._changes.clear()
            self._accessed_files.clear()
            self._written_files.clear()
    
    def rollback(self):
        """Rollback all changes since the last begin_transaction."""
        self._rollback_to(0)
        self._transaction_depth = 0
        # Clear tracking on rollback - don't add to working memory
        self._accessed_files.clear()
        self._written_files.clear()
    
    def _rollback_to(self, checkpoint: int):
        """Rollback changes to a specific checkpoint."""
        while len(self._changes) > checkpoint:
            change = self._changes.pop()
            operation = change['operation']
            path = change['path']
            
            try:
                if operation == 'write':
                    # Restore previous content or delete if new
                    actual_path = self._resolve_path(path)
                    if change.get('existed'):
                        # Restore previous content
                        with open(actual_path, 'w') as f:
                            f.write(change.get('previous_content', ''))
                        print(f"↩️ Restored {path} to previous content")
                    else:
                        # File was new, remove it
                        if actual_path.exists():
                            actual_path.unlink()
                        print(f"↩️ Removed newly created {path}")
                        
                elif operation == 'delete':
                    # Restore deleted file
                    if 'previous_content' in change:
                        actual_path = self._resolve_path(path)
                        actual_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(actual_path, 'w') as f:
                            f.write(change['previous_content'])
                        print(f"↩️ Restored deleted file {path}")
                        
                elif operation == 'mkdir':
                    # Remove newly created directory if empty
                    if change.get('created'):
                        actual_path = self._resolve_path(path)
                        if actual_path.exists() and actual_path.is_dir():
                            try:
                                actual_path.rmdir()  # Only works if empty
                                print(f"↩️ Removed newly created directory {path}")
                            except OSError:
                                print(f"⚠️ Cannot remove {path} - not empty")
                                
                elif operation == 'rmdir':
                    # Restore directory from temp backup
                    if 'backup_path' in change:
                        import shutil
                        backup_path = Path(change['backup_path'])
                        original_path = Path(change['original_path'])
                        if backup_path.exists():
                            shutil.move(str(backup_path), str(original_path))
                            # Clean up temp directory
                            backup_path.parent.rmdir()
                            print(f"↩️ Restored directory {path} from backup")
                            
                elif operation == 'move':
                    # Reverse the move
                    if change.get('to_path'):
                        old_actual = self._resolve_path(change['to_path'])
                        new_actual = self._resolve_path(path)
                        if old_actual.exists():
                            old_actual.rename(new_actual)
                            print(f"↩️ Reversed move: {change['to_path']} → {path}")
                            
                elif operation == 'evict':
                    # Re-add to working memory
                    if change.get('was_in_memory'):
                        from ..memory.memory_blocks import FileMemoryBlock
                        from ..memory.memory_types import Priority
                        memory_block = FileMemoryBlock(
                            location=path,
                            priority=Priority.MEDIUM,
                            confidence=1.0,
                            metadata={"restored": "rollback"}
                        )
                        self._memory_system.add_memory(memory_block)
                        print(f"↩️ Restored {path} to working memory")
                        
            except Exception as e:
                print(f"⚠️ Failed to rollback {operation} on {path}: {e}")
    
    def evict(self, path: str) -> bool:
        """
Remove a memory from working memory but keep it in shared memory.                
Args:
    path: Path to the memory to evict
    
Returns: True if evicted, False if not found in working memory
"""
        clean_path = self._clean_path(path)
        
        # Find and remove from working memory
        # The memory ID format is "memory:path"
        # Use path directly as memory ID (no type prefix)
        memory_id = clean_path
        
        # Try to find the memory in the memory system
        for mem in list(self._memory_system.symbolic_memory):
            if mem.id == memory_id:
                # Track the eviction for potential rollback
                self._track_change(clean_path, 'evict')
                self._memory_system.remove_memory(memory_id)
                print(f"✓ Evicted {path} from working memory (still on disk)")
                return True
        
        print(f"⚠️ {path} not found in working memory")
        return False
    
    def move_memory(self, old_path: str, new_path: str) -> bool:
        """
Move or rename a memory file or directory.        
Args:
    old_path: Current path of the memory
    new_path: New path for the memory            
Returns:
    True if moved successfully, False otherwise
"""
        try:
            old_clean = self._clean_path(old_path)
            new_clean = self._clean_path(new_path)
            
            old_actual = self._resolve_path(old_clean)
            new_actual = self._resolve_path(new_clean)
            
            if not old_actual.exists():
                print(f"⚠️ Source {old_path} does not exist")
                return False
            
            # Check if destination already exists
            if new_actual.exists():
                print(f"⚠️ Destination {new_path} already exists")
                return False
            
            # Create parent directory if needed
            new_actual.parent.mkdir(parents=True, exist_ok=True)
            
            # Move the file/directory
            old_actual.rename(new_actual)
            
            # Update working memory if present
            # Look for memory by location, not just ID
            memory_found = False
            for mem in list(self._memory_system.symbolic_memory):
                # Check if this is a FileMemoryBlock with matching location
                if hasattr(mem, 'location') and mem.location == old_clean:
                    memory_found = True
                    # Remove old reference
                    self._memory_system.remove_memory(mem.id)
                    
                    # Create new memory block preserving properties
                    from ..memory.memory_blocks import FileMemoryBlock
                    from ..memory.memory_types import Priority
                    new_block = FileMemoryBlock(
                        location=new_clean,
                        priority=mem.priority if hasattr(mem, 'priority') else Priority.MEDIUM,
                        confidence=mem.confidence if hasattr(mem, 'confidence') else 1.0,
                        pinned=mem.pinned if hasattr(mem, 'pinned') else False,
                        content_type=mem.content_type if hasattr(mem, 'content_type') else None,
                        metadata={
                            **(mem.metadata if hasattr(mem, 'metadata') else {}),
                            "moved_from": old_clean,
                            "moved_at_cycle": self._cognitive_loop.cycle_count
                        },
                        cycle_count=self._cognitive_loop.cycle_count
                    )
                    self._memory_system.add_memory(new_block)
                    break
            
            self._track_change(old_clean, 'move', {'to': new_clean})
            print(f"✓ Moved {old_path} → {new_path}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to move {old_path} to {new_path}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # Alias for convenience
    move = move_memory
    
    def DANGER_remove_memory_permanently(self, path: str, confirm: str = "") -> bool:
        """
⚠️ PERMANENTLY DELETE a memory file from disk.

This operation deletes the file from disk. It can be rolled back if used
within a transaction, but once committed, the deletion is permanent.

Args:
    path: Path to the memory to permanently delete
    confirm: Must be "DELETE" to confirm the operation
    
Returns:
    True if deleted, False otherwise
    
Example:
    ```python
    # Must explicitly confirm dangerous operations
    memory.DANGER_remove_memory_permanently(
        "/personal/old_data.json", 
        confirm="DELETE"
    )
    
    # Safe within a transaction - can be rolled back:
    with memory.transaction():
        memory.DANGER_remove_memory_permanently("/personal/temp.json", confirm="DELETE")
        # If an error occurs here, the file will be restored
    ```
"""
        if confirm != "DELETE":
            print("❌ DANGER: Must confirm with confirm='DELETE' to permanently delete files")
            print("    Without a transaction, this operation cannot be undone!")
            return False
        
        try:
            clean_path = self._clean_path(path)
            actual_path = self._resolve_path(clean_path)
            
            if not actual_path.exists():
                print(f"⚠️ {path} does not exist")
                return False
            
            if actual_path.is_dir():
                print(f"❌ {path} is a directory, use DANGER_remove_memory_group_permanently")
                return False
            
            # Remove from working memory first
            # Use path directly as memory ID (no type prefix)
            memory_id = clean_path
            self._memory_system.remove_memory(memory_id)
            
            # Delete from disk
            actual_path.unlink()
            self._track_change(clean_path, 'delete')
            
            print(f"🗑️ PERMANENTLY DELETED {path}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to delete {path}: {e}")
            return False
    
    def DANGER_remove_memory_group_permanently(self, path: str, confirm: str = "") -> bool:
        """
⚠️ PERMANENTLY DELETE an entire memory group (directory) and all contents.

This operation deletes an entire directory tree. Within a transaction, the
directory is moved to a temporary location and can be restored if rolled back.
Once committed, the deletion is permanent and cannot be recovered.

Args:
    path: Path to the memory group to permanently delete
    confirm: Must be "DELETE_ALL" to confirm the operation
    
Returns:
    True if deleted, False otherwise
    
Example:
    ```python
    # Must explicitly confirm dangerous operations with stronger confirmation
    memory.DANGER_remove_memory_group_permanently(
        "/personal/old_project", 
        confirm="DELETE_ALL"
    )
    
    # Safe within a transaction - entire directory can be restored:
    with memory.transaction():
        memory.DANGER_remove_memory_group_permanently(
            "/personal/temp_project", 
            confirm="DELETE_ALL"
        )
        # If an error occurs, the entire directory tree will be restored
    ```
"""
        if confirm != "DELETE_ALL":
            print("❌ DANGER: Must confirm with confirm='DELETE_ALL' to permanently delete directories")
            print("    Without a transaction, this will delete ALL contents permanently!")
            return False
        
        try:
            clean_path = self._clean_path(path)
            actual_path = self._resolve_path(clean_path)
            
            # Safety check - don't allow deleting root directories
            if clean_path in ['personal', '/personal', 'grid', '/grid']:
                print(f"❌ REFUSED: Cannot delete root directory {path}")
                return False
            
            if not actual_path.exists():
                print(f"⚠️ {path} does not exist")
                return False
            
            if not actual_path.is_dir():
                print(f"❌ {path} is not a directory, use DANGER_remove_memory_permanently")
                return False
            
            # Count items to be deleted for confirmation
            file_count = sum(1 for _ in actual_path.rglob('*') if _.is_file())
            dir_count = sum(1 for _ in actual_path.rglob('*') if _.is_dir())
            
            print(f"⚠️ About to delete {file_count} files and {dir_count} directories in {path}")
            
            # Remove all related items from working memory
            path_prefix = clean_path.rstrip('/') + '/'
            for mem in list(self._memory_system.symbolic_memory):
                if hasattr(mem, 'location') and (
                    mem.location == clean_path or 
                    mem.location.startswith(path_prefix)
                ):
                    self._memory_system.remove_memory(mem.id)
            
            # Track change BEFORE deletion (so it can backup if in transaction)
            self._track_change(clean_path, 'rmdir')
            
            # If not in a transaction, delete immediately
            # If in transaction, it was already moved to temp by _track_change
            if self._transaction_depth == 0:
                import shutil
                shutil.rmtree(actual_path)
            
            print(f"🗑️ PERMANENTLY DELETED {path} ({file_count} files, {dir_count} directories)")
            return True
            
        except Exception as e:
            print(f"❌ Failed to delete {path}: {e}")
            return False
    
    @property
    def knowledge(self):
        """
        Access the Knowledge API for searching and storing knowledge.
        
        Returns:
            Knowledge: The Knowledge API instance
            
        Example:
            ```python
            # Search for relevant knowledge
            results = memory.knowledge.search("how to communicate with other cybers")
            for item in results:
                print(f"Found: {item['content']}")
            
            # Store new knowledge
            memory.knowledge.store(
                "Cybers communicate through messages in the outbox",
                tags=["communication", "messaging"],
                personal=False  # Share with the hive mind
            )
            
            # Get formatted knowledge for brain prompts
            relevant = memory.knowledge.remember("current task context")
            ```
        """
        if self._knowledge is None:
            from .knowledge import Knowledge
            self._knowledge = Knowledge(self)
        return self._knowledge


# Register YAML representers to make TrackedDict and TrackedList transparent
# This ensures Cybers never see these internal implementation classes
def _represent_tracked_dict(dumper, data):
    """Represent TrackedDict as a regular dict in YAML."""
    return dumper.represent_dict(dict(data))

def _represent_tracked_list(dumper, data):
    """Represent TrackedList as a regular list in YAML."""
    return dumper.represent_list(list(data))

# Register with both safe and regular dumpers
yaml.add_representer(TrackedDict, _represent_tracked_dict)
yaml.add_representer(TrackedList, _represent_tracked_list)
try:
    # Also register with SafeDumper if available
    yaml.SafeDumper.add_representer(TrackedDict, _represent_tracked_dict)
    yaml.SafeDumper.add_representer(TrackedList, _represent_tracked_list)
except AttributeError:
    pass  # SafeDumper might not be available in all versions
