"""Memory API for cybers.

## Core Concept: Everything is Memory
The `memory` object provides unified access to everything in Mind-Swarm.
This provides a way to safely mutate memories and so progress towards goals and task.

Everything is memory. This module provides a unified interface for all memory operations
including files, messages, goals, and any other data in the Mind-Swarm ecosystem.

## Important Examples

### Reading Memory (any access will load the memory into working memory)
```python
# Dictionary style for dynamic paths
info = memory["/grid/library/knowledge/sections/new_cyber_introduction/intro.yaml"]
# Attribute style for known paths
notes = memory.personal.notes.important
# Check if memory exists
if memory.exists("/personal/data.json"):
    data = memory["/personal/data.json"]
```

### Writing Memory
```python
# Create or update memory
memory.personal.journal.today = "Today I learned about the memory API"
```

### Type Checking - Know Your Data Types!
```python
# IMPORTANT: Always check content type before using it
# Files like .yaml and .json are automatically parsed, but you should verify

# Example 1: Safely handle tasks that might be JSON or string
tasks_node = memory.personal.tasks
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
config = memory.personal.config.yaml.content
if isinstance(config, dict):
    # It's parsed YAML/JSON - safe to use as dict
    config["updated"] = True
elif isinstance(config, str):
    # It's raw text - parse it first
    import yaml
    config = yaml.safe_load(config)
    config["updated"] = True
    memory.personal.config.yaml = config

# Example 3: Type hints for better code
def update_task(task_id: str, status: str):
    tasks_node = memory.personal.tasks
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
    
    memory.personal.tasks = content
```

### Transactions for Safety
```python
# Multiple operations succeed or fail together
try:
    with memory.transaction():
        # Read existing data
        data = memory.personal.config.json
        
        # Modify JSON data directly (if it's JSON)
        if hasattr(data, 'content') and isinstance(data.content, dict):
            data.content["updated"] = "2024-01-01"
            # Changes are saved automatically
        
        # Save backup
        memory.personal.backup.config = data.content
        
        # Send confirmation
        memory.outbox.new(
            to="user", 
            content="Config updated and backed up",
            msg_type="CONFIRMATION"
        )       
except MemoryError as e:
    print(f"Transaction failed, all changes rolled back: {e}")
```

### Creating Memory Groups
```python
# Create organized structure
try:
    memory.make_memory_group("/personal/projects")
    memory.make_memory_group("/personal/projects/current")
    memory.personal.projects.current.status = "Active"
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
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime
from contextlib import contextmanager


class MemoryError(Exception):
    """Base exception for memory operations."""
    pass


class MemoryNotFoundError(MemoryError):
    """Raised when trying to access non-existent memory."""
    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Memory not found: {path}")


class MemoryPermissionError(MemoryError):
    """Raised when lacking permission to access memory."""
    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Permission denied: {path}")


class MemoryTypeError(MemoryError):
    """Raised when memory type doesn't match expected."""
    pass


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
        elif isinstance(self._content, list):
            self._content[key] = value
            self._modified = True
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
                        self._content = json.load(f)
                elif actual_path.suffix in ['.yaml', '.yml']:
                    import yaml
                    self._type = "application/yaml"
                    with open(actual_path, 'r') as f:
                        self._content = yaml.safe_load(f)
                else:
                    self._type = "text/plain"
                    with open(actual_path, 'r') as f:
                        self._content = f.read()
                
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
            
            # Save based on type
            if self._type == "application/json":
                with open(actual_path, 'w') as f:
                    json.dump(self._content, f, indent=2)
            else:
                with open(actual_path, 'w') as f:
                    f.write(str(self._content))
            
            # Track change for potential rollback
            self._memory._track_change(self.path, 'write', self._content)
            
            # Track that this file was written for transaction commit
            self._memory._track_write(self.path, self._type, self._new)
            
            self._modified = False
            self._new = False
            
        except Exception as e:
            raise MemoryError(f"Failed to save {self.path}: {e}")
    
    @property
    def content(self):
        """Get the memory content."""
        return self._content
    
    @content.setter
    def content(self, value):
        """Set the memory content."""
        self._content = value
        self._modified = True
        # Auto-detect type if not set
        if self._type is None:
            if isinstance(value, dict) or isinstance(value, list):
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
    sub-memories using either attribute notation (memory.personal.notes) or
    subscript notation (memory['personal']['notes']).
    
    Examples:
        # Both of these are equivalent:
        memory.personal.projects.task1 = "Task data"
        memory['personal']['projects']['task1'] = "Task data"
        
        # You can mix styles:
        memory.personal['dynamic_name'] = "Dynamic data"
    """
    
    def __init__(self, base_path: str, memory_system: 'Memory'):
        self._base_path = base_path.rstrip('/')
        self._memory = memory_system
    
    def __getattr__(self, name: str):
        """Access sub-memory via attribute."""
        if name.startswith('_'):
            raise AttributeError(f"Private attribute access not allowed: {name}")
        
        path = f"{self._base_path}/{name}"
        actual_path = self._memory._resolve_path(path)
        
        # If it exists and is a directory, return a MemoryGroup
        if actual_path.exists() and actual_path.is_dir():
            return MemoryGroup(path, self._memory)
        # If it doesn't exist, assume it will be a directory (for chained assignment)
        elif not actual_path.exists():
            # Return a MemoryGroup that can handle further attribute access
            return MemoryGroup(path, self._memory)
        # Otherwise it's a file, return a MemoryNode
        else:
            return self._memory[path]
    
    def __setattr__(self, name: str, value: Any):
        """Set memory via attribute."""
        if name.startswith('_'):
            # Internal attributes
            super().__setattr__(name, value)
        else:
            # Memory assignment - ensure parent directory exists
            path = f"{self._base_path}/{name}"
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


class OutboxHelper:
    """Helper for creating outbox messages."""
    
    def __init__(self, memory_system: 'Memory'):
        self._memory = memory_system
    
    def new(self, to: str, content: str, msg_type: str = "MESSAGE") -> MemoryNode:
        """Create a new message in the outbox."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:20]
        safe_to = to.replace('/', '_').replace(' ', '_')
        path = f"/personal/outbox/msg_{safe_to}_{timestamp}.json"
        
        node = MemoryNode(path, self._memory, new=True)
        node.type = "application/json"
        node.content = {
            "to": to,
            "from": self._memory._context.get('cyber_id', 'unknown'),
            "content": content,
            "type": msg_type,
            "timestamp": datetime.now().isoformat()
        }
        node._save()
        return node

class Memory:
    """Main memory interface providing unified access to all Mind-Swarm memories.
    The Memory class is the central API for all operations in Mind-Swarm.
    It provides both dictionary-style and attribute-style access to memories.

    Memory isn't just the working memory, you can access ALL memories.
    Normally memory access will bring it into working memory, so other stages can see it instantly.
    """
    
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
        self._written_files = []
    
    def _resolve_path(self, path: str) -> Path:
        """Resolve a memory path to actual filesystem path."""
        # Strip off any prefix before ':' (common mistake when copying from working memory)
        # e.g., 'system:personal/...' -> 'personal/...'
        # e.g., 'file:/personal/...' -> '/personal/...'
        if ':' in path and not path.startswith('/'):
            path = path.split(':', 1)[1]  # Remove everything before and including first ':'
        
        if path.startswith('/personal'):
            return self._personal_root / path[10:]  # Remove '/personal/'
        elif path.startswith('/grid'):
            return Path(path)
        else:
            # Default to personal space
            return self._personal_root / path
    
    def _track_change(self, path: str, operation: str, data: Any = None):
        """Track a change for potential rollback."""
        if self._transaction_depth > 0:
            self._changes.append({
                'path': path,
                'operation': operation,
                'data': data,
                'timestamp': datetime.now()
            })
    
    def _track_access(self, path: str, file_type: str):
        """Track file access for adding to working memory on commit."""
        if self._transaction_depth > 0:
            self._accessed_files.append({'path': path, 'type': file_type})
    
    def _track_write(self, path: str, file_type: str, is_new: bool):
        """Track file write for adding to working memory on commit."""
        if self._transaction_depth > 0:
            self._written_files.append({'path': path, 'type': file_type, 'new': is_new})
    
    def __getitem__(self, path: str) -> MemoryNode:
        """Dictionary-style access to memory."""
        return MemoryNode(path, self)
    
    def __setitem__(self, path: str, value: Any):
        """Dictionary-style memory assignment."""
        node = MemoryNode(path, self, new=True)
        node.content = value
        node._save()
    
    def __getattr__(self, name: str):
        """Attribute-style access to memory groups."""
        if name.startswith('_'):
            raise AttributeError(f"Private attribute access not allowed: {name}")
        
        # Special properties
        if name == 'outbox':
            return OutboxHelper(self)
        elif name == 'personal':
            return MemoryGroup('/personal', self)
        elif name == 'grid':
            return MemoryGroup('/grid', self)
        else:
            # Only allow known attributes - don't create arbitrary groups
            raise AttributeError(f"'Memory' object has no attribute '{name}'")
    
    def create(self, path: str) -> MemoryNode:
        """Create a new memory at the specified path.
        
        Args:
            path: Memory path like "/personal/notes.txt"
            
        Returns:
            MemoryNode that can be modified and saved
            
        Example:
            ```python
            note = memory.create("/personal/daily_note.txt")
            note.content = "Today's thoughts..."
            # Automatically saved
            ```
        """
        return MemoryNode(path, self, new=True)
    
    def make_memory_group(self, path: str):
        """Create a memory group (directory) at the specified path.
        
        Memory groups organize related memories together.
        
        Args:
            path: Group path like "/personal/projects"
            
        Example:
            ```python
            memory.make_memory_group("/personal/experiments")
            memory.personal.experiments.test1 = "First experiment"
            ```
        """
        actual_path = self._resolve_path(path)
        actual_path.mkdir(parents=True, exist_ok=True)
        self._track_change(path, 'mkdir')
    
    def has_memory(self, path: str) -> bool:
        """Check if a memory exists at the path.
        
        Args:
            path: Memory path to check
            
        Returns:
            True if memory exists, False otherwise
            
        Example:
            ```python
            if memory.has_memory("/personal/config.json"):
                config = memory["/personal/config.json"]
            else:
                memory["/personal/config.json"] = "{}"
            ```
        """
        actual_path = self._resolve_path(path)
        return actual_path.exists() and actual_path.is_file()
    
    def has_group(self, path: str) -> bool:
        """Check if a memory group exists at the path.
        
        Args:
            path: Group path to check
            
        Returns:
            True if group exists, False otherwise
            
        Example:
            ```python
            if not memory.has_group("/personal/archive"):
                memory.make_memory_group("/personal/archive")
            ```
        """
        actual_path = self._resolve_path(path)
        return actual_path.exists() and actual_path.is_dir()
    
    def exists(self, path: str) -> bool:
        """Check if anything (memory or group) exists at the path.
        
        Args:
            path: Path to check
            
        Returns:
            True if path exists, False otherwise
            
        Example:
            ```python
            if not memory.exists("/personal/data"):
                memory.make_memory_group("/personal/data")
            ```
        """
        actual_path = self._resolve_path(path)
        return actual_path.exists()
    
    def list_memories(self, path: str) -> List[str]:
        """List all memories in a group."""
        actual_path = self._resolve_path(path)
        if not actual_path.exists() or not actual_path.is_dir():
            return []
        return [item.name for item in actual_path.iterdir() if item.is_file()]
    
    def list_groups(self, path: str) -> List[str]:
        """List all sub-groups in a group."""
        actual_path = self._resolve_path(path)
        if not actual_path.exists() or not actual_path.is_dir():
            return []
        return [item.name for item in actual_path.iterdir() if item.is_dir()]
    
    def remove_memory(self, path: str):
        """Delete a memory."""
        actual_path = self._resolve_path(path)
        if actual_path.exists() and actual_path.is_file():
            actual_path.unlink()
            self._track_change(path, 'delete')
    
    def remove_group(self, path: str):
        """Delete a memory group and all its contents."""
        actual_path = self._resolve_path(path)
        if actual_path.exists() and actual_path.is_dir():
            import shutil
            shutil.rmtree(actual_path)
            self._track_change(path, 'rmdir')
    
    def search(self, query: str, path: str = "/personal", limit: int = 10) -> List[MemoryNode]:
        """Search for memories containing the query string."""
        results = []
        search_root = self._resolve_path(path)
        
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
            # TODO: Implement actual rollback logic
            # This would restore previous file states
            print(f"Rolling back: {change['operation']} on {change['path']}")
    
