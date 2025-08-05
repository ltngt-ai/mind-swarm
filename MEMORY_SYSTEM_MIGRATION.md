# MemorySystem Facade Migration Guide

## Overview

The new `MemorySystem` facade provides a unified interface to all memory operations, replacing the need to manage multiple memory components separately. This guide shows how to migrate from the old pattern to the new facade.

## Before: Using Individual Components

**Old pattern (cognitive_loop.py):**

```python
# === OLD PATTERN: Multiple components ===
from .memory import (
    WorkingMemoryManager, MemorySelector, ContextBuilder, ContentLoader,
    ObservationMemoryBlock, MessageMemoryBlock, CycleStateMemoryBlock,
    Priority, MemoryType
)

class CognitiveLoop:
    def _initialize_managers(self):
        # Memory system - 4 separate components!
        self.memory_manager = WorkingMemoryManager(max_tokens=self.max_context_tokens)
        self.memory_selector = MemorySelector(
            ContextBuilder(ContentLoader(filesystem_root=self.home.parent))
        )
        self.context_builder = ContextBuilder(ContentLoader(filesystem_root=self.home.parent))
        # ^^^ Note: ContentLoader created TWICE!
        
    def _load_memory_state(self):
        # Complex initialization with duplicate objects
        if not self.memory_manager.load_from_snapshot_file(self.memory_dir, self.knowledge_manager):
            self.knowledge_manager.load_rom_into_memory(self.memory_manager)
    
    def _perceive_filesystem(self):
        # Adding memories requires direct manager access
        for obs in observations:
            self.memory_manager.add_memory(obs)
    
    def _decide_orientation(self):
        # Context building requires coordinating 2 components
        selected_memories = self.memory_selector.select_memories(
            symbolic_memory=self.memory_manager.symbolic_memory,
            max_tokens=self.max_context_tokens // 2,
            current_task="Deciding what to focus on",
            selection_strategy="balanced"
        )
        memory_context = self.context_builder.build_context(selected_memories)
    
    def _build_decision_context(self):
        # Repeated pattern: select then build
        selected_memories = self.memory_selector.select_memories(
            symbolic_memory=self.memory_manager.symbolic_memory,
            max_tokens=self.max_context_tokens // 2,
            current_task="Making a decision",
            selection_strategy="balanced"
        )
        return self.context_builder.build_context(selected_memories)
    
    def _save_memory_state(self):
        # Direct manager access for persistence
        snapshot = self.memory_manager.create_snapshot()
        # ... save snapshot ...
    
    def _perform_maintenance(self):
        # Multiple cleanup calls
        expired = self.memory_manager.cleanup_expired()
        old_observations = self.memory_manager.cleanup_old_observations(max_age_seconds=1800)
```

## After: Using Unified Facade

**New pattern (recommended):**

```python
# === NEW PATTERN: Single facade ===
from .memory import (
    MemorySystem,
    ObservationMemoryBlock, MessageMemoryBlock, CycleStateMemoryBlock,
    Priority, MemoryType
)

class CognitiveLoop:
    def _initialize_managers(self):
        # Memory system - single component!
        self.memory_system = MemorySystem(
            filesystem_root=self.home.parent,
            max_tokens=self.max_context_tokens,
            cache_ttl=300
        )
        
    def _load_memory_state(self):
        # Simple, unified interface
        if not self.memory_system.load_from_snapshot_file(self.memory_dir, self.knowledge_manager):
            self.knowledge_manager.load_rom_into_memory(self.memory_system.memory_manager)
    
    def _perceive_filesystem(self):
        # Clean interface for adding memories
        for obs in observations:
            self.memory_system.add_memory(obs)
    
    def _decide_orientation(self):
        # Single call for context building
        memory_context = self.memory_system.build_context(
            max_tokens=self.max_context_tokens // 2,
            current_task="Deciding what to focus on",
            selection_strategy="balanced"
        )
    
    def _build_decision_context(self):
        # Same simple pattern everywhere
        return self.memory_system.build_context(
            max_tokens=self.max_context_tokens // 2,
            current_task="Making a decision",
            selection_strategy="balanced"
        )
    
    def _save_memory_state(self):
        # Unified persistence interface
        self.memory_system.save_snapshot_to_file(self.memory_dir)
    
    def _perform_maintenance(self):
        # Single call for all cleanup
        expired = self.memory_system.cleanup_expired()
        old_observations = self.memory_system.cleanup_old_observations(max_age_seconds=1800)
        cache_cleaned = self.memory_system.cleanup_cache()
```

## Key Benefits

### 1. Reduced Complexity
- **Before**: Manage 4 separate objects (`WorkingMemoryManager`, `MemorySelector`, `ContextBuilder`, `ContentLoader`)
- **After**: Manage 1 unified object (`MemorySystem`)

### 2. Eliminated Duplication
- **Before**: `ContentLoader` created twice, leading to separate caches
- **After**: Shared `ContentLoader` with unified caching

### 3. Simpler Interface
- **Before**: `select_memories()` → `build_context()` (2 steps)
- **After**: `build_context()` (1 step)

### 4. Better Coordination
- **Before**: Manual coordination between components
- **After**: Automatic coordination within facade

### 5. Enhanced Functionality
- **New**: Keyword search with `find_memories_by_keywords()`
- **New**: Token usage breakdown with `get_token_usage_breakdown()`
- **New**: Enhanced statistics with `get_memory_stats()`
- **New**: Unified persistence with `save_snapshot_to_file()`

## Migration Steps

### Step 1: Update Imports
```python
# Old
from .memory import (
    WorkingMemoryManager, MemorySelector, ContextBuilder, ContentLoader,
    # ... other imports
)

# New
from .memory import (
    MemorySystem,
    # ... other imports (blocks and types remain the same)
)
```

### Step 2: Replace Initialization
```python
# Old
def _initialize_managers(self):
    self.memory_manager = WorkingMemoryManager(max_tokens=self.max_context_tokens)
    self.memory_selector = MemorySelector(
        ContextBuilder(ContentLoader(filesystem_root=self.home.parent))
    )
    self.context_builder = ContextBuilder(ContentLoader(filesystem_root=self.home.parent))

# New
def _initialize_managers(self):
    self.memory_system = MemorySystem(
        filesystem_root=self.home.parent,
        max_tokens=self.max_context_tokens,
        cache_ttl=300
    )
```

### Step 3: Update Memory Operations
```python
# Old
self.memory_manager.add_memory(memory_block)
retrieved = self.memory_manager.access_memory(memory_id)

# New
self.memory_system.add_memory(memory_block)
retrieved = self.memory_system.get_memory(memory_id)
```

### Step 4: Simplify Context Building
```python
# Old
selected_memories = self.memory_selector.select_memories(
    symbolic_memory=self.memory_manager.symbolic_memory,
    max_tokens=token_budget,
    current_task=current_task,
    selection_strategy="balanced"
)
context = self.context_builder.build_context(selected_memories)

# New
context = self.memory_system.build_context(
    max_tokens=token_budget,
    current_task=current_task,
    selection_strategy="balanced"
)
```

### Step 5: Update Queries
```python
# Old
file_memories = self.memory_manager.get_memories_by_type(MemoryType.FILE)
recent = self.memory_manager.get_recent_memories(300)
unread = self.memory_manager.get_unread_messages()

# New
file_memories = self.memory_system.get_memories_by_type(MemoryType.FILE)
recent = self.memory_system.get_recent_memories(300)
unread = self.memory_system.get_unread_messages()
```

### Step 6: Update Persistence
```python
# Old
snapshot = self.memory_manager.create_snapshot()
# ... manual file saving ...
success = self.memory_manager.load_from_snapshot_file(memory_dir, knowledge_manager)

# New
success = self.memory_system.save_snapshot_to_file(memory_dir)
success = self.memory_system.load_from_snapshot_file(memory_dir, knowledge_manager)
```

## Backward Compatibility

The old components are still available for advanced use cases:

```python
# Access underlying components if needed
memory_manager = memory_system.memory_manager
content_loader = memory_system.content_loader
context_builder = memory_system.context_builder
memory_selector = memory_system.memory_selector
```

## New Features Available

### Enhanced Search
```python
# Find memories by keywords
results = memory_system.find_memories_by_keywords(["python", "programming"])
for memory, relevance_score in results:
    print(f"{memory.id}: {relevance_score}")
```

### Task Management
```python
# Set current task for better relevance scoring
memory_system.set_current_task("task_001", "Implement web server")
memory_system.add_active_topic("python")
memory_system.add_active_topic("web_development")
```

### Token Analysis
```python
# Get token usage breakdown by type
breakdown = memory_system.get_token_usage_breakdown()
print(f"Knowledge tokens: {breakdown.get('KNOWLEDGE', 0)}")
print(f"File tokens: {breakdown.get('FILE', 0)}")
```

### Enhanced Statistics
```python
# Comprehensive memory statistics
stats = memory_system.get_memory_stats()
print(f"Total memories: {stats['total_memories']}")
print(f"Cache size: {stats['cache_size']}")
print(f"System stats: {stats['system_stats']}")
```

## Testing

The facade includes comprehensive validation. Use the provided test script:

```bash
python3 validate_memory_system.py
```

## Performance Improvements

1. **Unified Caching**: Single `ContentLoader` cache instead of multiple
2. **Smart Coordination**: Automatic relevance scoring updates
3. **Batch Operations**: Optimized for common usage patterns
4. **Memory Monitoring**: Built-in statistics and token tracking

## Summary

The `MemorySystem` facade provides:

- ✅ **Simplified Interface**: 1 object instead of 4
- ✅ **Reduced Duplication**: Shared components and caching
- ✅ **Better Coordination**: Automatic component coordination
- ✅ **Enhanced Features**: Search, analysis, and monitoring
- ✅ **Backward Compatibility**: Access to underlying components
- ✅ **Performance**: Optimized caching and batch operations

**Recommendation**: Use `MemorySystem` for all new code. Migrate existing code when convenient.