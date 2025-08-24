# CLAUDE.md - Python Modules Development Guide

This guide explains how to add new Python modules that cybers can use in their execution scripts.

## Overview

Python modules in this directory provide APIs that cybers can use during the EXECUTION stage. These modules are made available in the namespace when cybers run Python scripts.

## Steps to Add a New Module

### 1. Create the Module File

Create a new Python file in this directory (e.g., `myapi.py`):

```python
"""
# MyAPI for Cybers

## Core Concept
Brief description of what this API does and why cybers need it.

## Examples

### Basic Usage
```python
result = myapi.do_something("parameter")
print(result)
```
"""

class MyAPIError(Exception):
    """Base exception for MyAPI errors."""
    pass

class MyAPI:
    """Main API class for cyber usage."""
    
    def __init__(self, context_or_dependency):
        """Initialize the API.
        
        Args:
            context_or_dependency: Either the execution context dict or another API instance
        """
        # If your API needs the context (access to cognitive_loop, memory_system, etc.)
        if isinstance(context_or_dependency, dict):
            self.context = context_or_dependency
            self.cognitive_loop = context_or_dependency.get('cognitive_loop')
            self.memory_system = context_or_dependency.get('memory_system')
        # If your API depends on another API (like Knowledge depends on Memory)
        else:
            self.dependency = context_or_dependency
    
    def do_something(self, param):
        """Public method cybers can call."""
        # Implementation here
        return f"Did something with {param}"
```

### 2. Update __init__.py

Add your module to the exports in `__init__.py`:

```python
from .memory import Memory, MemoryError
from .location import Location, LocationError
from .events import Events, EventsError
from .knowledge import Knowledge
from .awareness import Awareness
from .myapi import MyAPI, MyAPIError  # Add your module here

__all__ = [
    'Memory', 'MemoryError',
    'Location', 'LocationError', 
    'Events', 'EventsError',
    'Knowledge',
    'Awareness',
    'MyAPI', 'MyAPIError'  # Add to exports
]
```

### 3. Add to Execution Stage (TWO PLACES REQUIRED!)

Update `/stages/execution_stage.py` in **TWO CRITICAL PLACES**:

#### 3a. Initialize in _setup_execution_environment()
Add your API initialization in the `_setup_execution_environment()` method:

```python
def _setup_execution_environment(self):
    # ... existing code ...
    
    # Add your API alongside the others (around line 317)
    from ..python_modules.myapi import MyAPI
    self.myapi = MyAPI(context)  # or MyAPI(self.memory_api) if it depends on Memory
```

#### 3b. Add Documentation Extraction in __init__()
Add documentation extraction in the `__init__()` method:

```python
def __init__(self, cognitive_loop):
    # ... existing code ...
    
    # Generate API documentation as knowledge for all modules (around line 69)
    self._extract_and_save_module_docs(self.myapi, "myapi_docs")
```

#### 3c. Add to _run_script() namespace
Finally, make it available in the script namespace in `_run_script()`:

```python
async def _run_script(self, script: str, attempt: int) -> Dict[str, Any]:
    # ... existing code ...
    
    # After the other API imports and initializations (around line 650)
    from ..python_modules.myapi import MyAPI, MyAPIError
    
    myapi_instance = MyAPI(context)
    namespace['myapi'] = myapi_instance
    if MyAPIError:
        namespace['MyAPIError'] = MyAPIError
```

**IMPORTANT**: All THREE steps are required:
1. Initialize in `_setup_execution_environment()` - creates the instance
2. Extract docs in `__init__()` - makes documentation available to cybers
3. Add to namespace in `_run_script()` - makes API usable in scripts

Without step 2, cybers won't know the API exists!

### 4. Document the API

Create comprehensive documentation in your module's docstring:

```python
"""
# MyAPI Documentation

## Purpose
Explain what problem this API solves for cybers.

## Core Concepts
- Concept 1: Explanation
- Concept 2: Explanation

## API Methods

### do_something(param)
Description of what this method does.

**Parameters:**
- `param` (str): Description of parameter

**Returns:**
- Description of return value

**Example:**
```python
result = myapi.do_something("test")
print(result)  # Output: Did something with test
```

### another_method(arg1, arg2)
...

## Error Handling

The API raises `MyAPIError` when:
- Condition 1
- Condition 2

**Example:**
```python
try:
    myapi.do_something("invalid")
except MyAPIError as e:
    print(f"Error: {e}")
```

## Best Practices

1. Always check for None returns
2. Handle exceptions appropriately
3. Don't make blocking calls that could hang

## Implementation Notes

For developers maintaining this API:
- Note about internal workings
- Gotchas to watch out for
- Performance considerations
"""
```

### 5. Test the Module

Create a test cyber script to verify your module works:

```python
# Test script for cybers to run
print("Testing MyAPI...")

# Test basic functionality
result = myapi.do_something("test")
print(f"Result: {result}")

# Test error handling
try:
    myapi.do_something(None)
except MyAPIError as e:
    print(f"Caught expected error: {e}")

print("MyAPI test complete!")
```

## Design Guidelines

### 1. Context vs Dependencies

**Use Context** when your API needs:
- Access to cognitive_loop
- Access to memory_system
- Access to brain_interface
- File paths (personal_dir, outbox_dir, etc.)
- Cyber identity information

**Use Another API** when:
- Your API builds on top of another (like Knowledge uses Memory)
- You need to maintain consistency with another API's state

### 2. Error Handling

Always define custom exception classes:

```python
class MyAPIError(Exception):
    """Base exception for all MyAPI errors."""
    pass

class MyAPINotFoundError(MyAPIError):
    """Raised when requested item is not found."""
    pass

class MyAPIPermissionError(MyAPIError):
    """Raised when operation is not permitted."""
    pass
```

### 3. State Management

- APIs should be stateless where possible
- If state is needed, ensure it's transaction-safe
- Consider using Memory API for persistent state

### 4. Security Considerations

- Never expose direct file system access
- Validate all inputs
- Respect cyber sandbox boundaries
- Don't allow access outside /personal and /grid

### 5. Performance

- Avoid blocking operations
- Cache expensive computations appropriately
- Use async/await for I/O operations if needed
- Be mindful of memory usage

## Common Patterns

### Pattern 1: Wrapper Around System Functionality

```python
class SystemWrapper:
    def __init__(self, context):
        self.context = context
        self.personal = context['personal_dir']
    
    def safe_operation(self, param):
        # Validate and sanitize
        if not self._is_valid(param):
            raise SystemWrapperError("Invalid parameter")
        
        # Perform operation with proper error handling
        try:
            result = self._do_operation(param)
            return result
        except Exception as e:
            raise SystemWrapperError(f"Operation failed: {e}")
```

### Pattern 2: High-Level Abstraction

```python
class HighLevelAPI:
    def __init__(self, memory_api):
        self.memory = memory_api
    
    def complex_operation(self, goal):
        # Use lower-level APIs to achieve high-level goal
        data = self.memory["/personal/data.json"]
        processed = self._process(data, goal)
        self.memory["/personal/result.json"] = processed
        return "Operation complete"
```

### Pattern 3: Event-Driven API

```python
class EventAPI:
    def __init__(self, context):
        self.context = context
        self.handlers = {}
    
    def on(self, event_type, handler):
        """Register event handler."""
        self.handlers[event_type] = handler
    
    def emit(self, event_type, data):
        """Trigger event."""
        if event_type in self.handlers:
            return self.handlers[event_type](data)
```

## Checklist for New Modules

- [ ] Created module file in python_modules/
- [ ] Added comprehensive docstring with examples
- [ ] Defined error classes (if needed)
- [ ] Implemented __init__ method correctly
- [ ] Added to __init__.py exports
- [ ] Updated execution_stage.py to include in namespace
- [ ] Tested with actual cyber execution
- [ ] Documented all public methods
- [ ] Added error handling examples
- [ ] Considered security implications
- [ ] Optimized for performance
- [ ] Added to this guide's module list below

## Existing Modules

### memory.py
- **Purpose**: File system abstraction for reading/writing memories
- **Dependencies**: Context
- **Key Methods**: `__getitem__`, `__setitem__`, `exists()`, `delete()`

### location.py
- **Purpose**: Manage cyber's current location in the grid
- **Dependencies**: Context
- **Key Methods**: `move()`, `look()`, `get_location()`

### events.py
- **Purpose**: Event system for cyber communication
- **Dependencies**: Context
- **Key Methods**: `emit()`, `on()`, `recent()`

### knowledge.py
- **Purpose**: Semantic knowledge storage and search
- **Dependencies**: Memory API
- **Key Methods**: `search()`, `remember()`, `store()`, `forget()`

### awareness.py
- **Purpose**: Awareness of other cybers and environment
- **Dependencies**: Context
- **Key Methods**: `get_nearby_cybers()`, `who_is()`

### tasks.py
- **Purpose**: Simple task management system
- **Dependencies**: Context
- **Key Methods**: `create()`, `get_current()`, `get_all()`, `complete()`, `block()`, `update()`

## Troubleshooting

### Module Not Available in Cyber Script
- Check execution_stage.py has the import and namespace assignment
- Verify module is in __init__.py exports
- Ensure no import errors in the module itself

### Import Errors
- All imports must be relative (use `.` prefix)
- Check circular dependencies
- Verify all dependencies are available

### API Not Working as Expected
- Add logging to help debug
- Check if context is being passed correctly
- Verify cyber has necessary permissions
- Test in isolation first

### Performance Issues
- Profile the code to find bottlenecks
- Consider caching frequently accessed data
- Avoid repeated file I/O operations
- Use Memory API's caching when appropriate

## Getting Help

When adding a new module:
1. Follow this guide step-by-step
2. Look at existing modules for examples
3. Test thoroughly with actual cybers
4. Document edge cases and limitations
5. Consider backward compatibility

Remember: These APIs are the primary way cybers interact with their world during execution. Make them intuitive, safe, and powerful!