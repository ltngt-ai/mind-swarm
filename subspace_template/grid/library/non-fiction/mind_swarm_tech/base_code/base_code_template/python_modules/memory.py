"""
# Memory API for Cybers.

## Core Concept: Everything is Memory
The `memory` object provides unified access to everything in Mind-Swarm.
This provides a way to safely mutate memories and so progress towards goals and task.

Everything is memory. This module provides a unified interface for all memory operations
including files, messages, goals, and any other data in the Mind-Swarm ecosystem.

## Working Memory vs Python Memory
**IMPORTANT DISTINCTION:**
- **Working Memory**: Affects token limits for cognitive processing (thinking)
- **Python Memory**: Just variables in your script, doesn't affect cognition

Methods that ADD to working memory (use sparingly for large files):
- `memory[path]` - Reading files this way
- `memory.read_lines()` - Reading specific ranges
- `memory.append()` - Appending to files
You NEVER need to `print` these, as you will automatically `see` them in later cycles.

Methods that DON'T add to working memory (use for large file processing):
- `memory.read_raw()` - Read files directly into Python
- `memory.write_raw()` - Write files directly from Python
- `memory.get_info()` - Get metadata only

## Important Examples

### Reading Memory (any access will load the memory into working memory)
```python
# Memory access follows standard Python patterns
# memory[path] returns raw STRING content - just like open().read()
# This matches what Python developers naturally expect!

# Reading files - ALWAYS returns a STRING
notes = memory["/personal/notes.txt"]  # Returns raw STRING content
json_str = memory["/personal/data.json"]  # Returns raw JSON string
yaml_str = memory["/personal/config.yaml"]  # Returns raw YAML string

# Parse JSON/YAML yourself (standard Python way)
import json
import yaml
data = json.loads(memory["/personal/data.json"])  # Parse JSON string
config = yaml.safe_load(memory["/personal/config.yaml"])  # Parse YAML string

# OR use .content for auto-parsing (convenience method)
node = memory.get_node("/personal/data.json")
data = node.content  # Returns already parsed DICT or LIST
print(node.content_type)  # Check MIME type: "application/json"

# Check if memory exists
if memory.exists("/personal/data.json"):
    content = memory["/personal/data.json"]  # Returns raw string
```

### Writing Memory
```python
# Create or update memory - just assign the value directly
memory["/personal/journal/today"] = "Today I learned about the memory API"

# Write JSON data
memory["/personal/data.json"] = {"name": "Alice", "tasks": [1, 2, 3]}

# Write YAML data  
memory["/personal/config.yaml"] = {"setting": "value", "debug": True}
```

### CRITICAL: Understanding MemoryNode vs Content
```python
# memory[path] returns raw string (what Python devs expect!)
json_str = memory["/personal/data.json"]  # Returns raw JSON string
import json
data = json.loads(json_str)  # Parse it yourself (standard Python)
data["key"] = "value"  # Works!
memory["/personal/data.json"] = json.dumps(data)  # Save back

# Alternative: use get_node() for auto-parsing
node = memory.get_node("/personal/data.json")
data = node.content  # Auto-parsed dict/list (convenience)
print(node.content_type)  # "application/json"
print(node.exists)  # True if file exists

# Content type (for node.content) determines auto-parsing:
# - "application/json" → dict or list (parsed JSON)
# - "application/x-yaml" → dict, list, or string (parsed YAML)  
# - "text/plain" → string (raw text)
# - other → string (raw bytes as string)
```

### Type Checking - Know Your Data Types!
```python
# Check content_type before using auto-parsing
node = memory.get_node("/personal/tasks.json")
if node.content_type == "application/json":
    tasks = node.content  # Auto-parsed dict/list
    # ... process the json here
else:
    # Not JSON, just get raw content
    raw_content = memory["/personal/tasks.json"]
    print(f"Tasks file is not JSON: {raw_content[:100]}")
```

### Transactions for Safety
```python
# Multiple operations succeed or fail together
import json
try:
    with memory.transaction():
        # Read and parse JSON data
        config_str = memory["/personal/config.json"]
        config = json.loads(config_str)
        
        # Modify the data
        config["updated"] = "2024-01-01"
        
        # Save modified data and backup
        memory["/personal/config.json"] = json.dumps(config)
        memory["/personal/backup/config.json"] = json.dumps(config)
        
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

### Working with Large Files
```python
info = memory.get_info("/personal/large_dataset.csv")
if info['lines'] > 1000:
    # Read specific range
    middle = memory.read_lines("/personal/large_dataset.csv", start_line=5000, end_line=5500)    
else:
    # Small enough to read entirely
    full_content = memory["/personal/large_dataset.csv"]  # Returns raw string
```

### Appending to Files
```python
# Append to a notes file without reading existing content
memory.append("/personal/notes.txt", f"[{time.time()}] New observation\n")
```

### Processing Large Files Without Cognitive Overhead
```python
# read_raw() loads files into Python memory WITHOUT adding to working memory
# This doesn't affect token limits for cognitive processing!

# Process a huge CSV file
raw_csv = memory.read_raw("/personal/huge_dataset.csv")  # No working memory!
lines = raw_csv.split('\n')
# Do heavy processing in Python
filtered = []
for line in lines:
    if 'important' in line:
        filtered.append(line)
# Only save results to working memory
memory["/personal/filtered.csv"] = '\n'.join(filtered)  # This goes to working memory
# Or save results without working memory
memory.write_raw("/personal/filtered.csv", '\n'.join(filtered))  # Stays out of working memory
```

## Key Rules
1. **Automatic save** - Changes persist immediately, unless in a transaction
2. **Transaction safety** - Use transactions for critical operations
3. **Everything is memory** - Think in terms of memory, not files
4. **Type checking** - Always verify data types before operations (use .content_type)
5. **Parse when needed** - YAML/JSON files auto-parse but always check type first
6. **Working memory is precious** - Use read_raw()/write_raw() for large file processing
7. **Size limits exist** - Files over 32KB or 1,000 lines need special handling
"""

import json
import yaml
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime
from contextlib import contextmanager
from collections.abc import MutableMapping, MutableSequence

# Python-magic is required for consistent MIME type detection
# The Debian rootfs environment must have this installed
import magic

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
                # Use centralized content type detection (with python-magic when available)
                self._type = self._memory._detect_content_type(actual_path)
                
                # Check file size limits BEFORE reading
                file_stat = actual_path.stat()
                file_size = file_stat.st_size
                
                # Check size limit
                if file_size > Memory.MAX_FILE_SIZE:
                    raise MemoryError(
                        f"File too large to load entirely: {self.path}\n"
                        f"Size: {file_size:,} bytes (limit: {Memory.MAX_FILE_SIZE:,} bytes)\n"
                        f"Use memory.read_lines() to read specific ranges instead:\n"
                        f"  preview = memory.read_lines('{self.path}', end_line=100)\n"
                        f"  middle = memory.read_lines('{self.path}', start_line=1000, end_line=2000)"
                    )
                
                # Check line count for text files
                if self._type.startswith('text/') or self._type in ['application/json', 'application/yaml']:
                    try:
                        with open(actual_path, 'r', encoding='utf-8') as f:
                            line_count = sum(1 for _ in f)
                        
                        if line_count > Memory.MAX_FILE_LINES:
                            raise MemoryError(
                                f"File has too many lines to load entirely: {self.path}\n"
                                f"Lines: {line_count:,} (limit: {Memory.MAX_FILE_LINES:,})\n"
                                f"Use memory.read_lines() to read specific ranges instead:\n"
                                f"  first_100 = memory.read_lines('{self.path}', end_line=100)\n"
                                f"  last_100 = memory.read_lines('{self.path}', start_line={line_count - 100})"
                            )
                    except UnicodeDecodeError:
                        # Misdetected as text, actually binary - continue anyway
                        pass
                
                # Load content based on detected type
                if self._type in ["application/json", "application/x-mindswarm-message"]:
                    # JSON-based formats (including Mind-Swarm messages)
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
                elif self._type in ["application/yaml", "application/x-mindswarm-knowledge"]:
                    # YAML-based formats (including Mind-Swarm knowledge)
                    import yaml
                    with open(actual_path, 'r') as f:
                        self._content = yaml.safe_load(f)
                elif self._type == "application/octet-stream":
                    # Binary file - return as bytes
                    with open(actual_path, 'rb') as f:
                        self._content = f.read()
                else:
                    # Text file (including text/plain, text/markdown, and other text/* types)
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
            actual_path = self._memory._resolve_path(self.path, for_write=True)
            
            # Create parent directories if needed
            actual_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Unwrap tracked objects back to plain dict/list for saving
            content_to_save = self._content
            if isinstance(self._content, TrackedDict):
                content_to_save = dict(self._content)
            elif isinstance(self._content, TrackedList):
                content_to_save = list(self._content)
            
            # Save based on type
            if self._type in ["application/json", "application/x-mindswarm-message"]:
                # JSON-based formats (including Mind-Swarm messages)
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
            elif self._type in ["application/yaml", "application/x-mindswarm-knowledge"]:
                # YAML-based formats (including Mind-Swarm knowledge)
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
            elif self._type == "application/octet-stream":
                # Binary content
                with open(actual_path, 'wb') as f:
                    if isinstance(content_to_save, bytes):
                        f.write(content_to_save)
                    else:
                        # Convert to bytes if needed
                        f.write(str(content_to_save).encode('utf-8'))
            else:
                # Text content (including text/plain, text/markdown, and other text/* types)
                with open(actual_path, 'w') as f:
                    f.write(str(content_to_save))
            
            # Track change for potential rollback
            self._memory._track_change(self.path, 'write', content_to_save)
            
            # Track that this file was written for transaction commit
            self._memory._track_write(self.path, self._type, self._new)
            
            # Invalidate any cached content for this file
            self._memory._invalidate_cache(self.path)
            
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
        # Auto-detect type if not set, using centralized detection
        if self._type is None:
            actual_path = self._memory._resolve_path(self.path)
            # If file exists, use proper detection
            if actual_path.exists():
                self._type = self._memory._detect_content_type(actual_path)
            else:
                # For new files, infer from extension or content type
                if actual_path.suffix in ['.yaml', '.yml']:
                    self._type = "application/yaml"
                elif actual_path.suffix == '.json':
                    self._type = "application/json"
                elif isinstance(value, dict) or isinstance(value, list):
                    # Default to JSON for dict/list without explicit extension
                    self._type = "application/json"
                elif isinstance(value, bytes):
                    self._type = "application/octet-stream"
                else:
                    self._type = "text/plain"
        # Auto-save in transaction mode
        if self._memory._auto_save:
            self._save()
    
    @property
    def type(self):
        """Get the memory type (deprecated - use content_type)."""
        return self._type
    
    @type.setter
    def type(self, value):
        """Set the memory type (deprecated - use content_type setter)."""
        self._type = value
        self._modified = True
    
    @property
    def content_type(self):
        """Get the content type (MIME type like 'application/json')."""
        return self._type
    
    @content_type.setter
    def content_type(self, value):
        """Set the content type."""
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
    
    # Safety limits to prevent memory system overload
    MAX_FILE_LINES = 1000  # Maximum lines for full file read
    MAX_FILE_SIZE = 32 * 1024  # 32KB max for full file read
    MAX_RANGE_LINES = 500  # Maximum lines for ranged read
    
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
    
    def _clean_path(self, path: str) -> str:
        """Clean a path by removing any type prefix.       
        - "personal/goals/..." -> "personal/goals/..."
        
        Note: We only run on Linux, so no need to handle Windows paths.
        """
        if ':' in path and not path.startswith('/'):
            # Strip the prefix (everything before and including first ':')
            return path.split(':', 1)[1]
        return path
    
    def _resolve_path(self, path: str, for_write: bool = False) -> Path:
        """Resolve a memory path to actual filesystem path.
        
        Valid path formats:
        - '/personal/...' - Absolute personal path
        - 'personal/...' - Relative personal path
        - '/grid/...' - Absolute grid path
        - 'grid/...' - Relative grid path
        
        Restricted paths:
        - Writing to .internal is forbidden (system use only)
        - Reading from .internal is allowed
        
        Args:
            path: The path to resolve
            for_write: True if this path will be written to, False for reading
        """
        original_path = path
        
        # First clean the path to remove any type prefix
        path = self._clean_path(path)
        
        # Security check: block WRITES to .internal, but allow reads
        if '.internal' in path and for_write:
            raise MemoryError(
                f"Access denied: Cannot write to system directories (.internal). "
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
                
            elif operation == 'append':
                # Store the file size before append for truncation on rollback
                actual_path = self._resolve_path(path)
                if actual_path.exists():
                    rollback_info['original_size'] = actual_path.stat().st_size
                else:
                    rollback_info['original_size'] = 0
                    rollback_info['was_new'] = True
                    
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
    
    def _invalidate_cache(self, path: str):
        """Invalidate cache for a specific file path.
        
        This ensures that subsequent reads get fresh content after writes.
        """
        if self._memory_system and hasattr(self._memory_system, 'content_loader'):
            clean_path = self._clean_path(path)
            # Invalidate in the ContentLoader cache
            self._memory_system.content_loader.invalidate_file(clean_path)
    
    def __getitem__(self, path: str):
        """Dictionary-style access to memory - returns raw string content.
        
        This matches standard Python file reading expectations:
        - memory["/path/to/file"] returns the raw string content
        - Use memory.get_node("/path/to/file") to get the MemoryNode object
        - Use memory.get_node("/path/to/file").content for auto-parsed content
        """
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
        
        # For files, return the raw string content directly
        # This matches what Python developers expect from file access
        if actual_path.exists() and actual_path.is_file():
            with open(actual_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        # File doesn't exist - return empty string to match Python behavior
        return ""
    
    def get_node(self, path: str) -> 'MemoryNode':
        """Get the MemoryNode object for advanced operations.
        
        Use this when you need:
        - .content for auto-parsed JSON/YAML
        - .content_type to check MIME type
        - .exists to check if file exists
        
        Example:
            node = memory.get_node("/personal/data.json")
            if node.exists:
                data = node.content  # Auto-parsed dict/list
                print(node.content_type)  # "application/json"
        """
        clean_path = self._clean_path(path)
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
        # Check write permission for .internal
        self._resolve_path(clean_path, for_write=True)  # This will raise error if .internal
        node = MemoryNode(clean_path, self, new=True)
        node.content = value
        node._save()
        # Cache is invalidated within node._save() via _invalidate_cache()
        
    def create(self, path: str) -> MemoryNode:
        """
Create a new memory at the specified path.
Args: path - Memory path like "/personal/notes.txt"
Returns: MemoryNode that can be modified and saved
"""
        clean_path = self._clean_path(path)
        return MemoryNode(clean_path, self, new=True)
    
    def make_memory_group(self, path: str):
        """
Create a memory group at the specified path.                
Args: path - Group path like "/personal/projects"            
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
            from ..memory.memory_blocks import MemoryBlock
            from ..memory.memory_types import Priority
            
            # Add accessed files
            for file_info in self._accessed_files:
                memory_block = MemoryBlock(
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
                memory_block = MemoryBlock(
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
    
    def _detect_content_type(self, path: Path) -> str:
        """
        Detect content type using the same logic as server's MimeHandler.
        This ensures consistency between get_info() and actual memory loading.
        
        Priority:
        1. Check Mind-Swarm specific double extensions (.knowledge.yaml, .msg.json, etc.)
        2. Check directory-based hints (/inbox/, /knowledge/, etc.)
        3. Use python-magic for base MIME type detection (REQUIRED)
        4. Content sniffing for Mind-Swarm specific YAML/JSON types
        
        No fallbacks - python-magic must be available in the Debian rootfs environment.
        """
        path_str = str(path)
        
        # 1. Check Mind-Swarm specific double extensions (only 2 types currently)
        if path_str.endswith('.knowledge.yaml') or path_str.endswith('.knowledge.yml'):
            return 'application/x-mindswarm-knowledge'
        elif path_str.endswith('.msg.json') or path_str.endswith('.msg.yaml'):
            return 'application/x-mindswarm-message'
        
        # 2. Directory-based hints (only for the 2 types we support)
        if '/knowledge/' in path_str or '/initial_knowledge/' in path_str:
            if path.suffix in ['.yaml', '.yml']:
                return 'application/x-mindswarm-knowledge'
        elif '/inbox/' in path_str or '/outbox/' in path_str:
            if path.suffix in ['.json', '.yaml', '.yml']:
                return 'application/x-mindswarm-message'
        
        # 3. Use python-magic for base type detection (REQUIRED - no fallback)
        if not path.exists():
            raise MemoryError(f"Cannot detect content type: {path} does not exist")
        
        magic_mime = magic.Magic(mime=True)
        detected_type = magic_mime.from_file(str(path))
        
        # For text/plain, YAML, and JSON, continue to content sniffing
        # to detect Mind-Swarm specific types
        if detected_type not in ['text/plain', 'application/json', 'text/x-yaml', 'application/x-yaml']:
            # For other types (images, PDFs, etc.), trust magic
            return detected_type
        
        # 4. Content sniffing for Mind-Swarm specific types
        if path.suffix in ['.yaml', '.yml', '.json']:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content_sample = f.read(1024)  # Read first 1KB for sniffing
                
                # Sniff YAML files
                if path.suffix in ['.yaml', '.yml']:
                    try:                       
                        data = yaml.safe_load(content_sample)
                        if isinstance(data, dict):
                            # Check for knowledge markers
                            if any(key in data for key in ['title', 'tags', 'category', 'content', 'description']):
                                return 'application/x-mindswarm-knowledge'
                            # Check for message markers
                            elif any(key in data for key in ['to', 'from', 'subject', 'body']):
                                return 'application/x-mindswarm-message'
                    except:
                        pass
                    return 'application/yaml'  # Generic YAML
                
                # Sniff JSON files
                elif path.suffix == '.json':
                    try:
                        # Handle truncated samples
                        if len(content_sample) == 1024:
                            # Add closing brackets for partial parse
                            test_content = content_sample + ']}' * 10
                        else:
                            test_content = content_sample
                        
                        data = json.loads(test_content)
                        if isinstance(data, dict):
                            # Check for message markers (only type we support for JSON)
                            if any(key in data for key in ['to', 'from', 'subject']):
                                return 'application/x-mindswarm-message'
                    except:
                        pass
                    return 'application/json'  # Generic JSON
                    
            except (UnicodeDecodeError, IOError):
                # If we can't read/parse the file for sniffing, return what magic detected
                return detected_type
        
        # If no Mind-Swarm specific type was detected, return what magic detected
        return detected_type
    
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
                            
                elif operation == 'append':
                    # Truncate file to original size or delete if new
                    actual_path = self._resolve_path(path)
                    if change.get('was_new') and actual_path.exists():
                        actual_path.unlink()
                        print(f"↩️ Removed newly created file {path}")
                    elif actual_path.exists():
                        original_size = change.get('original_size', 0)
                        with open(actual_path, 'r+b') as f:
                            f.truncate(original_size)
                        print(f"↩️ Truncated {path} to original size")
                        
                elif operation == 'evict':
                    # Re-add to working memory
                    if change.get('was_in_memory'):
                        from ..memory.memory_blocks import MemoryBlock
                        from ..memory.memory_types import Priority
                        memory_block = MemoryBlock(
                            location=path,
                            priority=Priority.MEDIUM,
                            confidence=1.0,
                            metadata={"restored": "rollback"}
                        )
                        self._memory_system.add_memory(memory_block)
                        print(f"↩️ Restored {path} to working memory")
                        
            except Exception as e:
                print(f"⚠️ Failed to rollback {operation} on {path}: {e}")
    
    def get_info(self, path: str) -> Dict[str, Any]:
        """
        Get metadata about a memory without loading its content.
        
        Args:
            path: Memory path to inspect
            
        Returns:
            Dict with keys:
            - size: int - size in bytes
            - lines: int - number of lines (for text memories)
            - type: str - 'memory' or 'memory_group'
            - content_type: str - MIME type like 'application/json', 'text/plain', etc. (for memories only)
            - modified: datetime - last modified time (for memories only)
            - items: int - number of items in the group (for memory_groups only)
            
        Raises:
            MemoryNotFoundError: If the path doesn't exist
            
        Example:
            try:
                info = memory.get_info("/personal/large_file.txt")
                if info['lines'] > 1000:
                    # Use ranged read for large files
                    first_100 = memory.read_lines("/personal/large_file.txt", end_line=100)
            except MemoryNotFoundError:
                print("File doesn't exist")
        """
        clean_path = self._clean_path(path)
        actual_path = self._resolve_path(clean_path)
        
        if not actual_path.exists():
            raise MemoryNotFoundError(f"Memory does not exist: {path}")
        
        info = {}
            
        if actual_path.is_dir():
            info['type'] = 'memory_group'
            info['size'] = sum(f.stat().st_size for f in actual_path.rglob('*') if f.is_file())
            info['items'] = len(list(actual_path.iterdir()))
        else:
            info['type'] = 'memory'
            stat = actual_path.stat()
            info['size'] = stat.st_size
            info['modified'] = datetime.fromtimestamp(stat.st_mtime)
            
            # Determine content type using our centralized detection method
            # This ensures consistency with how memories are typed when loaded
            info['content_type'] = self._detect_content_type(actual_path)
            
            # Count lines for text files
            if info['content_type'].startswith('text/') or info['content_type'] == 'application/json' or info['content_type'] == 'application/yaml':
                try:
                    with open(actual_path, 'r', encoding='utf-8') as f:
                        info['lines'] = sum(1 for _ in f)
                except (UnicodeDecodeError, IOError):
                    info['lines'] = None  # Can't count lines
            else:
                info['lines'] = None  # Binary file
                
        return info

    def read_lines(self, path: str, start_line: int | None = 0, end_line: int | None = None) -> str:
        """
        Read specific lines from a memory without loading the entire file.
        
        Args:
            path: Memory path to read
            start_line: First line to read. Supports Python-style negative indexing.
                       1-based for positive, -1 is last line. None means from beginning.
            end_line: Last line to read (inclusive). Supports negative indexing.
                      None means to end.
            
        Returns:
            String containing the requested lines
            
        Example:
            # Read first 100 lines
            header = memory.read_lines("/personal/data.csv", end_line=100)           
            # Read lines 50-150
            middle = memory.read_lines("/personal/log.txt", start_line=50, end_line=150)            
            # Read from line 1000 to end
            tail = memory.read_lines("/personal/output.txt", start_line=1000)            
            # Read last 100 lines (Python-style negative indexing)
            tail = memory.read_lines("/personal/log.txt", start_line=-100)            
            # Read last 50 lines
            tail = memory.read_lines("/personal/output.txt", start_line=-50, end_line=-1)
        """
        clean_path = self._clean_path(path)
        actual_path = self._resolve_path(clean_path)
        
        if not actual_path.exists():
            raise MemoryNotFoundError(path)
            
        if actual_path.is_dir():
            raise MemoryTypeError(f"Cannot read lines from directory: {path}")
        
        # Handle negative indices by counting lines first if needed
        if start_line and start_line < 0 or end_line and end_line < 0:
            # Need to count total lines for negative indexing
            with open(actual_path, 'r', encoding='utf-8') as f:
                total_lines = sum(1 for _ in f)
            
            # Convert negative indices to positive
            if start_line and start_line < 0:
                start_line = max(1, total_lines + start_line + 1)  # -1 becomes total_lines
            if end_line and end_line < 0:
                end_line = max(1, total_lines + end_line + 1)
        
        # Check if range is too large
        if start_line and end_line:
            range_size = end_line - start_line + 1
            if range_size > self.MAX_RANGE_LINES:
                raise MemoryError(
                    f"Requested range too large: {range_size} lines\n"
                    f"Maximum range size: {self.MAX_RANGE_LINES} lines\n"
                    f"Try reading in smaller chunks or use multiple calls"
                )
        
        # Track access for working memory
        self._track_access(clean_path, 'text/plain')
        
        # Also add to working memory with line range info
        if self._memory_system:
            from ..memory.memory_blocks import MemoryBlock
            from ..memory.memory_types import Priority
            
            memory_block = MemoryBlock(
                location=clean_path,
                start_line=start_line,
                end_line=end_line,
                priority=Priority.MEDIUM,
                confidence=1.0,
                metadata={
                    "source": "script_read_lines",
                    "cycle": self._cognitive_loop.cycle_count if self._cognitive_loop else 0
                }
            )
            self._memory_system.add_memory(memory_block)
        
        lines = []
        with open(actual_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                if start_line and i < start_line:
                    continue
                if end_line and i > end_line:
                    break
                lines.append(line)
                
        return ''.join(lines)
    
    def read_raw(self, path: str, binary: bool = False) -> Any:
        """
        Read a file directly WITHOUT adding it to working memory.
        
        This is useful for processing large files that don't need to be part of
        cognitive context. The file is loaded into Python memory only, not the
        cyber's working memory that affects token limits.
        
        Args:
            path: Memory path to read
            binary: If True, read as binary data (bytes). If False, read as text (str).
            
        Returns:
            File contents as string (text mode) or bytes (binary mode)
            
        Example:
            # Process a large CSV without affecting working memory
            csv_data = memory.read_raw("/personal/large_dataset.csv")
            lines = csv_data.split('\n')
            
            # Process each line without cognitive overhead
            results = []
            for line in lines:
                cols = line.split(',')
                if len(cols) > 3 and cols[2] == 'important':
                    results.append(cols)
            
            # Only save results to working memory
            memory["/personal/filtered_results.json"] = results
            
            # Read binary file
            image_data = memory.read_raw("/personal/photo.jpg", binary=True)
        """
        clean_path = self._clean_path(path)
        actual_path = self._resolve_path(clean_path)
        
        if not actual_path.exists():
            raise MemoryNotFoundError(path)
            
        if actual_path.is_dir():
            raise MemoryTypeError(f"Cannot read raw content from directory: {path}")
        
        # Just read the file directly
        if binary:
            with open(actual_path, 'rb') as f:
                return f.read()
        else:
            with open(actual_path, 'r', encoding='utf-8') as f:
                return f.read()
    
    def write_raw(self, path: str, content: Any, binary: bool = False) -> None:
        """
        Write content directly to a file WITHOUT adding it to working memory.
        
        This is useful for saving processed results from large datasets without
        affecting the cyber's cognitive context.
        
        Args:
            path: Memory path to write to
            content: Content to write (str for text, bytes for binary)
            binary: If True, write as binary data. If False, write as text.
            
        Example:
            # Process large file and save results without cognitive overhead
            raw_data = memory.read_raw("/personal/input.txt")
            processed = raw_data.upper()  # Some processing
            memory.write_raw("/personal/output.txt", processed)
            
            # Write binary data (example with safe bytes)
            memory.write_raw("/personal/data.bin", b'\\x41\\x42\\x43', binary=True)
        """
        clean_path = self._clean_path(path)
        actual_path = self._resolve_path(clean_path, for_write=True)
        
        # Track the write for rollback purposes
        self._track_change(clean_path, 'write', {'content': content if not binary else '<binary>'})
        
        # Create parent directory if needed
        actual_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the file WITHOUT adding to working memory
        if binary:
            with open(actual_path, 'wb') as f:
                f.write(content)
        else:
            with open(actual_path, 'w', encoding='utf-8') as f:
                f.write(content)
    
    def append(self, path: str, content: str) -> None:
        """
        Append content to a memory without reading the existing content.
        
        Args:
            path: Memory path to append to
            content: Content to append
            
        Example:
            # Append to a notes file
            memory.append("/personal/notes.txt", f"[{datetime.now()}] Task completed\n")
        """
        clean_path = self._clean_path(path)
        actual_path = self._resolve_path(clean_path, for_write=True)
        
        # Track the append operation
        self._track_change(clean_path, 'append', {'content': content})
        self._track_write(clean_path, 'text/plain', not actual_path.exists())
        
        # Create parent directory if needed
        actual_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Append to file
        with open(actual_path, 'a', encoding='utf-8') as f:
            f.write(content)
        
        # Invalidate cache after append
        self._invalidate_cache(clean_path)
            
        # Also add to working memory
        if self._memory_system:
            from ..memory.memory_blocks import MemoryBlock
            from ..memory.memory_types import Priority
            
            memory_block = MemoryBlock(
                location=clean_path,
                priority=Priority.MEDIUM,
                confidence=1.0,
                metadata={
                    "source": "script_append",
                    "cycle": self._cognitive_loop.cycle_count if self._cognitive_loop else 0
                }
            )
            self._memory_system.add_memory(memory_block)
    
    def evict(self, path: str) -> bool:
        """
Remove a memory from working memory but keep it in shared memory.                
Args:
    path: Path to the memory to evict
    
Returns: True if evicted, False if not found in working memory
"""
        clean_path = self._clean_path(path)
        
        # Normalize the path to match how MemoryBlock creates IDs
        from ..memory.unified_memory_id import UnifiedMemoryID
        memory_id = UnifiedMemoryID.normalize_path(clean_path)
        
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
            
            old_actual = self._resolve_path(old_clean)  # Reading old location
            new_actual = self._resolve_path(new_clean, for_write=True)  # Writing to new location
            
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
            
            # Invalidate cache for both old and new paths
            self._invalidate_cache(old_clean)
            self._invalidate_cache(new_clean)
            
            # Update working memory if present
            # Look for memory by location, not just ID
            memory_found = False
            for mem in list(self._memory_system.symbolic_memory):
                # Check if this is a MemoryBlock with matching location
                if hasattr(mem, 'location') and mem.location == old_clean:
                    memory_found = True
                    # Remove old reference
                    self._memory_system.remove_memory(mem.id)
                    
                    # Create new memory block preserving properties
                    from ..memory.memory_blocks import MemoryBlock
                    from ..memory.memory_types import Priority
                    new_block = MemoryBlock(
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
