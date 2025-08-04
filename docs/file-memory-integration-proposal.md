# File and Memory Integration for Mind-Swarm Agents

## Current Architecture Analysis

The Mind-Swarm memory system already treats files as a type of memory:

1. **FileMemoryBlock** - Represents files as symbolic memory references
2. **ContentLoader** - Lazy-loads file content only when needed
3. **EnvironmentScanner** - Discovers files and creates memory blocks
4. **WorkingMemoryManager** - Manages all memory types uniformly

Key insight: **Files ARE memories in the agent's worldview**. The hive mind's persistent memory is literally the filesystem.

## Conceptual Model

From an agent's perspective:
- **Working Memory** = Currently loaded/active memories (symbolic references)
- **Long-term Memory** = Files on disk that can be loaded
- **Shared Memory** = Grid filesystem (plaza, library, workshop)
- **Personal Memory** = Agent's home directory

## Proposed File Actions as Memory Operations

Instead of traditional file operations, we should provide memory-focused actions that naturally align with how agents think:

### 1. Memory Focus Actions

```python
class FocusMemoryAction(Action):
    """Focus attention on a specific memory (file or otherwise).
    
    This loads content into working memory for processing.
    """
    params:
        - memory_id: str  # Can be file path or memory block ID
        - focus_type: str  # "read", "edit", "analyze"
        - line_range: Optional[Tuple[int, int]]  # For partial focus
```

```python
class SearchMemoryAction(Action):
    """Search through memories for specific content.
    
    Creates new memory blocks for search results.
    """
    params:
        - query: str  # What to search for
        - scope: str  # "personal", "shared", "all"
        - memory_types: List[str]  # ["file", "message", "knowledge"]
```

### 2. Memory Creation/Modification Actions

```python
class CreateMemoryAction(Action):
    """Create a new persistent memory (file).
    
    Memories are automatically categorized based on content and location.
    """
    params:
        - content: str  # The memory content
        - location: str  # Where to store (e.g., "personal/notes", "shared/knowledge")
        - memory_type: str  # "note", "knowledge", "code", "data"
        - metadata: Dict  # Tags, categories, etc.
```

```python
class UpdateMemoryAction(Action):
    """Update an existing memory (file edit).
    
    Can update partial content or metadata.
    """
    params:
        - memory_id: str  # Memory to update
        - updates: List[Dict]  # List of changes to apply
        - preserve_history: bool  # Keep version history
```

### 3. Memory Organization Actions

```python
class OrganizeMemoryAction(Action):
    """Reorganize memories (move/rename files).
    
    Maintains references and relationships.
    """
    params:
        - memory_id: str
        - new_location: str  # New path/category
        - update_references: bool  # Update other memories that reference this
```

```python
class LinkMemoriesAction(Action):
    """Create relationships between memories.
    
    Builds knowledge graph connections.
    """
    params:
        - source_memory: str
        - target_memory: str
        - relationship: str  # "references", "extends", "contradicts", etc.
```

### 4. Memory Inspection Actions

```python
class InspectMemoryAction(Action):
    """Get detailed information about a memory without loading content.
    
    Returns metadata, relationships, access history.
    """
    params:
        - memory_id: str
        - include_related: bool  # Include related memories
```

```python
class ListMemoriesAction(Action):
    """List memories matching criteria.
    
    Returns FileMemoryBlocks for discovered files.
    """
    params:
        - location: str  # Directory to list
        - pattern: str  # Glob pattern
        - memory_type: Optional[str]
        - since: Optional[datetime]  # Recently modified
```

## Implementation Approach

### Phase 1: Core Memory Actions
1. Implement `FocusMemoryAction` for reading files
2. Implement `CreateMemoryAction` for writing files
3. Implement `SearchMemoryAction` for finding content

### Phase 2: Advanced Operations
4. Implement `UpdateMemoryAction` for editing
5. Implement `OrganizeMemoryAction` for file management
6. Implement `InspectMemoryAction` for metadata

### Phase 3: Knowledge Graph
7. Implement `LinkMemoriesAction` for relationships
8. Add graph traversal to memory selector
9. Enable memory-based reasoning

## Natural Usage Examples

### Agent Reading a File
Instead of: "read file /grid/library/docs/guide.md"
Natural: "focus on the guide in the library"

```json
{
  "action": "focus_memory",
  "params": {
    "memory_id": "/grid/library/docs/guide.md",
    "focus_type": "read"
  }
}
```

### Agent Creating a Note
Instead of: "write file /home/memory/observations.txt"
Natural: "create a memory about my observations"

```json
{
  "action": "create_memory",
  "params": {
    "content": "Today I learned about...",
    "location": "personal/observations",
    "memory_type": "note",
    "metadata": {
      "tags": ["learning", "reflection"],
      "importance": "high"
    }
  }
}
```

### Agent Searching Knowledge
Instead of: "grep -r 'pattern' /grid/library/"
Natural: "search shared knowledge for information about patterns"

```json
{
  "action": "search_memory",
  "params": {
    "query": "pattern",
    "scope": "shared",
    "memory_types": ["knowledge", "file"]
  }
}
```

## Benefits of This Approach

1. **Conceptual Clarity**: Agents think in terms of memories, not files
2. **Unified Interface**: Same actions work for all memory types
3. **Rich Metadata**: Every file operation can include semantic information
4. **Knowledge Building**: File operations naturally build the knowledge graph
5. **Context Aware**: Memory focus maintains context for better decisions

## Integration with Existing System

- Actions work through the existing `WorkingMemoryManager`
- `ContentLoader` handles lazy loading
- `EnvironmentScanner` discovers new files as memories
- Memory blocks track all file metadata and relationships

## Next Steps

1. Review and refine the action definitions
2. Implement `FocusMemoryAction` as proof of concept
3. Test with agents to ensure natural usage
4. Iterate based on agent behavior patterns

This approach makes file operations feel like natural memory operations, which aligns perfectly with how agents perceive their world as a memory-rich environment rather than a traditional filesystem.