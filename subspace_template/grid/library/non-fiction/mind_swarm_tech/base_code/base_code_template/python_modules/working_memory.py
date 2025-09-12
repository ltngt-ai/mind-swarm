"""
# Working Memory API for Cybers

## Core Concept
Working memory is what your cognitive loop sees and processes. It's separate from the filesystem.
You have complete control over what enters and leaves your working memory.

## Key Principle
- **Filesystem**: Use standard Python (`open()`, `os`, `pathlib`) for all file operations
- **Working Memory**: Explicitly manage what your cognitive loop will see

## IMPORTANT: No Import Needed!
The `working_memory` module is pre-loaded in your execution environment.
Just use it directly WITHOUT importing:

```python
# ✅ CORRECT - Just use it directly
working_memory.add("data", my_data)

# ❌ WRONG - Don't try to import it
import working_memory  # This will fail!
```

## Examples

### Basic Usage
```python
# NO IMPORT NEEDED - working_memory is already available

# Add Python objects to working memory
data = {"task": "analyze", "priority": "high"}
working_memory.add("current_task", data)

# Load file content into working memory
working_memory.add_file("/personal/notes.txt", name="my_notes")

# Check what's loaded
items = working_memory.list()
print(f"Working memory contains: {items}")

# Check token usage
tokens = working_memory.get_tokens()
print(f"Using approximately {tokens} tokens")

# Remove specific item
working_memory.remove("current_task")

# Clear everything
working_memory.clear()
```

### Working with Files
```python
import json
import working_memory

# Read and process files with standard Python
with open("/personal/data.json") as f:
    data = json.load(f)

# Do your processing
results = analyze_data(data)

# Save results normally
with open("/personal/results.json", "w") as f:
    json.dump(results, f)

# Only add to working memory what you want to remember
working_memory.add("analysis_results", results)
```

### Managing Context Size
```python
# Check before adding large content
if working_memory.get_tokens() < 40000:
    working_memory.add_file("/personal/large_doc.txt")
else:
    # Remove something first
    working_memory.remove("old_data")
    working_memory.add_file("/personal/large_doc.txt")
```
"""

import json
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("Cyber.working_memory")


class WorkingMemoryError(Exception):
    """Base exception for working memory errors."""
    pass


class WorkingMemory:
    """Manages what content is visible to the cognitive loop.
    
    This is NOT about filesystem access - use standard Python for that.
    This is about controlling what your cognitive processing sees.
    """
    
    def __init__(self, context: Dict[str, Any]):
        """Initialize working memory manager.
        
        Args:
            context: Execution context containing memory_system reference
        """
        self.context = context
        self.memory_system = context.get('memory_system')
        self.cognitive_loop = context.get('cognitive_loop')
        
        # Track what's been explicitly added
        self._items: Dict[str, Any] = {}
        self._file_items: Dict[str, str] = {}  # name -> filepath mapping
        
        if not self.memory_system:
            raise WorkingMemoryError("Memory system not available in context")
    
    def add(self, name: str, content: Any) -> None:
        """Add a Python object to working memory.
        
        Args:
            name: Identifier for this content
            content: Any Python object (dict, list, string, etc.)
            
        Example:
            working_memory.add("current_plan", {"step": 1, "action": "analyze"})
        """
        if not name:
            raise WorkingMemoryError("Name cannot be empty")
            
        # Store in our tracking
        self._items[name] = content
        
        # Create a memory block for the cognitive system
        from ..memory.memory_blocks import MemoryBlock
        from ..memory.memory_types import Priority, ContentType
        
        # Convert content to string for storage
        # Use type() instead of isinstance() to avoid issues with restricted namespace
        content_type_name = type(content).__name__
        if content_type_name in ('dict', 'list'):
            content_str = json.dumps(content, indent=2)
            content_type = ContentType.APPLICATION_JSON
        else:
            content_str = str(content)
            content_type = ContentType.TEXT_PLAIN
        
        # Create virtual memory block with content in metadata
        # This works with the semantic database approach
        temp_path = f"/personal/.internal/memory/working/{name}.tmp"
        
        # Add to memory system with content in metadata
        memory_block = MemoryBlock(
            location=temp_path,
            confidence=1.0,
            priority=Priority.HIGH,
            metadata={
                "source": "working_memory",
                "name": name,
                "content": content_str,  # Content stored in metadata for semantic DB
                "added_at": datetime.now().isoformat(),
                "virtual": True  # Mark as virtual (not file-backed)
            },
            content_type=content_type,
            pinned=True  # Pin working memory items so they persist across cycles
        )
        
        self.memory_system.add_memory(memory_block)
        logger.info(f"Added '{name}' to working memory")
    
    def add_file(self, filepath: str, name: Optional[str] = None) -> None:
        """Load a file's content into working memory.
        
        Args:
            filepath: Path to file to load
            name: Optional name for the content (defaults to filename)
            
        Example:
            working_memory.add_file("/personal/notes.txt")
            working_memory.add_file("/personal/data.json", name="current_data")
        """
        path = Path(filepath)
        
        # Resolve path relative to cyber's view
        if not path.is_absolute():
            if filepath.startswith("personal/"):
                path = Path("/") / filepath
            elif filepath.startswith("grid/"):
                path = Path("/") / filepath
            else:
                path = Path("/personal") / filepath
        
        # Default name is the filename
        if name is None:
            name = path.name
            
        # Track this file
        self._file_items[name] = str(path)
        
        # Add to memory system
        from ..memory.memory_blocks import MemoryBlock
        from ..memory.memory_types import Priority, ContentType
        
        memory_block = MemoryBlock(
            location=str(path),
            confidence=1.0,
            priority=Priority.HIGH,
            metadata={
                "source": "working_memory_file",
                "name": name,
                "added_at": datetime.now().isoformat()
            },
            content_type=ContentType.from_file_extension(str(path)),
            pinned=False  # Let memory selector manage based on priority
        )
        
        self.memory_system.add_memory(memory_block)
        logger.info(f"Added file '{filepath}' to working memory as '{name}'")
    
    def remove(self, name: str) -> bool:
        """Remove an item from working memory.
        
        Args:
            name: Name of item to remove
            
        Returns:
            True if removed, False if not found
            
        Example:
            working_memory.remove("old_data")
        """
        removed = False
        
        # Remove from our tracking
        if name in self._items:
            del self._items[name]
            removed = True
            
        if name in self._file_items:
            del self._file_items[name]
            removed = True
        
        # Remove from memory system
        # Find memories with this name in metadata
        memories_to_remove = []
        for memory_id, memory in self.memory_system._memory_manager._memories.items():
            if (hasattr(memory, 'metadata') and 
                memory.metadata and 
                memory.metadata.get('name') == name):
                memories_to_remove.append(memory_id)
        
        for memory_id in memories_to_remove:
            self.memory_system.remove_memory(memory_id)
            removed = True
        
        if removed:
            logger.info(f"Removed '{name}' from working memory")
        else:
            logger.warning(f"Item '{name}' not found in working memory")
            
        return removed
    
    def clear(self) -> None:
        """Clear all items from working memory.
        
        Example:
            working_memory.clear()
        """
        # Get all names
        all_names = list(self._items.keys()) + list(self._file_items.keys())
        
        # Remove each one
        for name in all_names:
            self.remove(name)
            
        logger.info("Cleared all working memory")
    
    def list(self) -> List[str]:
        """List all items currently in working memory.
        
        Returns:
            List of item names
            
        Example:
            items = working_memory.list()
            print(f"Working memory: {items}")
        """
        all_items = list(self._items.keys()) + list(self._file_items.keys())
        return sorted(set(all_items))
    
    def get_tokens(self) -> int:
        """Get approximate token count of working memory.
        
        Returns:
            Estimated number of tokens
            
        Example:
            if working_memory.get_tokens() > 50000:
                print("Working memory is getting full!")
        """
        # Get from memory system's tracking
        if hasattr(self.memory_system, '_last_working_memory_tokens'):
            return self.memory_system._last_working_memory_tokens
        
        # Rough estimate if not available
        total_chars = 0
        
        # Count characters in added items
        for content in self._items.values():
            # Use type() instead of isinstance() to avoid issues with restricted namespace
            content_type_name = type(content).__name__
            if content_type_name in ('dict', 'list'):
                total_chars += len(json.dumps(content))
            else:
                total_chars += len(str(content))
        
        # Rough token estimate (1 token ≈ 4 characters)
        return total_chars // 4
    
    def get(self, name: str) -> Optional[Any]:
        """Get an item from working memory by name.
        
        Args:
            name: Name of item to retrieve
            
        Returns:
            The content if found, None otherwise
            
        Example:
            data = working_memory.get("current_task")
            if data:
                print(f"Task: {data}")
        """
        return self._items.get(name)
    
    def contains(self, name: str) -> bool:
        """Check if an item exists in working memory.
        
        Args:
            name: Name to check
            
        Returns:
            True if exists, False otherwise
            
        Example:
            if working_memory.contains("analysis_results"):
                print("Results are ready")
        """
        return name in self._items or name in self._file_items


# Module-level instance that will be initialized by execution stage
_instance: Optional[WorkingMemory] = None


def _get_instance() -> WorkingMemory:
    """Get the working memory instance."""
    if _instance is None:
        raise WorkingMemoryError("Working memory not initialized. This should be set up by execution stage.")
    return _instance


# Public API functions that delegate to instance
def add(name: str, content: Any) -> None:
    """Add a Python object to working memory."""
    return _get_instance().add(name, content)


def add_file(filepath: str, name: Optional[str] = None) -> None:
    """Load a file's content into working memory."""
    return _get_instance().add_file(filepath, name)


def remove(name: str) -> bool:
    """Remove an item from working memory."""
    return _get_instance().remove(name)


def clear() -> None:
    """Clear all items from working memory."""
    return _get_instance().clear()


def list() -> List[str]:
    """List all items currently in working memory."""
    return _get_instance().list()


def get_tokens() -> int:
    """Get approximate token count of working memory."""
    return _get_instance().get_tokens()


def get(name: str) -> Optional[Any]:
    """Get an item from working memory by name."""
    return _get_instance().get(name)


def contains(name: str) -> bool:
    """Check if an item exists in working memory."""
    return _get_instance().contains(name)