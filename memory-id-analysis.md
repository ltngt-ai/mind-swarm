# Memory ID System Analysis and Unified Approach Proposal

## Current State Analysis

### 1. Memory ID Patterns Discovered

After analyzing the codebase, I've identified several different ID patterns used across memory types:

#### FileMemoryBlock IDs
- Pattern: `{location}` or `{location}:{start_line}-{end_line}`
- Examples:
  - `/home/agent/memory/notes.txt`
  - `/grid/plaza/question-123.md:10-20`
- Issues: Uses full filesystem paths, making IDs fragile if files move

#### MessageMemoryBlock IDs
- Pattern: `msg:{full_path}`
- Example: `msg:/home/agent/inbox/message-123.json`
- Issues: References inbox path, not content

#### ObservationMemoryBlock IDs
- Pattern: `obs:{path}:{timestamp}`
- Example: `obs:/grid/plaza/new-file.txt:1735683024.123456`
- Issues: Timestamp makes it impossible to reference the same observation later

#### KnowledgeMemoryBlock IDs
- Pattern: `knowledge:{topic}` or `knowledge:{topic}:{subtopic}`
- Examples:
  - `knowledge:cognitive_loop`
  - `knowledge:actions:create_memory`
- Issues: Topic-based, doesn't indicate source location

#### TaskMemoryBlock IDs
- Pattern: `task:{task_id}`
- Example: `task:implement-feature-xyz`
- Issues: Requires external task_id generation

#### StatusMemoryBlock IDs
- Pattern: `status:{status_type}`
- Example: `status:system_health`
- Issues: Only one status per type can exist

#### ContextMemoryBlock IDs
- Pattern: `context:{context_type}:{timestamp}`
- Example: `context:conversation:1735683024.123456`
- Issues: Timestamp prevents consistent referencing

#### CycleStateMemoryBlock ID
- Pattern: Fixed string `"cycle_state"`
- Issues: Singleton pattern, only one can exist

### 2. Key Problems Identified

1. **Inconsistent Patterns**: Each memory type uses a different ID scheme
2. **Path Dependency**: Many IDs depend on filesystem paths that can change
3. **Timestamp Usage**: Some IDs include timestamps, making them unreferenceable
4. **Content Disconnect**: IDs don't help agents reason about content
5. **No Content Hashing**: No way to identify duplicate content
6. **Fragile References**: Moving files breaks memory references
7. **Mixed Concerns**: IDs mix location info with identity

### 3. Agent Perspective Issues

From an agent's perspective:
- They see IDs like `msg:/home/agent/inbox/message-123.json` but can't tell what the message is about
- They must load content to understand what a memory contains
- They can't easily find related memories by ID patterns
- File paths in IDs expose implementation details

## Proposed Unified Memory ID System

### Design Principles

1. **Content-Aware**: IDs should help agents understand what the memory contains
2. **Location-Independent**: IDs shouldn't break when files move
3. **Hierarchical**: Support natural grouping and navigation
4. **Deterministic**: Same content should generate same ID
5. **Human-Readable**: Agents should understand IDs without loading content
6. **Backward Compatible**: Support migration from old system

### Proposed ID Structure

```
{type}:{namespace}:{semantic_path}[:{content_hash}]
```

Examples:
- `file:personal:notes/daily/2024-01-15:a7b9c2`
- `file:shared:plaza/questions/how-to-collaborate:d4e5f6`
- `message:inbox:from-alice/about-project:b8c3d1`
- `knowledge:rom:cognitive/ooda-loop:e9f1a2`
- `observation:grid:plaza/new-discussion:c5d6e7`
- `task:active:implement-memory-system:f7a8b9`

### Components Explained

1. **Type**: Memory type (file, message, knowledge, observation, task, etc.)
2. **Namespace**: Scope (personal, shared, inbox, rom, grid, active, etc.)
3. **Semantic Path**: Human-readable path describing content/purpose
4. **Content Hash**: Optional 6-char hash for uniqueness and deduplication

### Implementation Details

```python
@dataclass
class UnifiedMemoryID:
    """Unified memory ID system for all memory types."""
    
    type: str  # file, message, knowledge, observation, task, etc.
    namespace: str  # personal, shared, inbox, rom, grid, etc.
    semantic_path: str  # meaningful path like "notes/daily/2024-01-15"
    content_hash: Optional[str] = None  # 6-char hash of content
    
    def __str__(self) -> str:
        """Generate the ID string."""
        base = f"{self.type}:{self.namespace}:{self.semantic_path}"
        if self.content_hash:
            return f"{base}:{self.content_hash}"
        return base
    
    @classmethod
    def from_file_path(cls, file_path: Path, home_dir: Path) -> 'UnifiedMemoryID':
        """Create ID from file path."""
        # Determine namespace
        if file_path.is_relative_to(home_dir / "memory"):
            namespace = "personal"
            semantic_path = file_path.relative_to(home_dir / "memory")
        elif file_path.is_relative_to(home_dir.parent / "grid"):
            namespace = "shared"
            semantic_path = file_path.relative_to(home_dir.parent / "grid")
        else:
            namespace = "system"
            semantic_path = file_path.name
        
        # Generate semantic path
        semantic_path = str(semantic_path).replace("/", "/")
        
        # Calculate content hash if file exists
        content_hash = None
        if file_path.exists():
            content_hash = calculate_content_hash(file_path)[:6]
        
        return cls(
            type="file",
            namespace=namespace,
            semantic_path=semantic_path,
            content_hash=content_hash
        )
    
    @classmethod
    def parse(cls, id_string: str) -> 'UnifiedMemoryID':
        """Parse an ID string back into components."""
        parts = id_string.split(":", 3)
        if len(parts) < 3:
            raise ValueError(f"Invalid memory ID format: {id_string}")
        
        return cls(
            type=parts[0],
            namespace=parts[1],
            semantic_path=parts[2],
            content_hash=parts[3] if len(parts) > 3 else None
        )
```

### Memory Block Updates

```python
@dataclass
class FileMemoryBlock(MemoryBlock):
    """Updated file memory block with unified IDs."""
    location: str  # Keep for backward compatibility
    semantic_id: Optional[UnifiedMemoryID] = None
    # ... other fields ...
    
    def __post_init__(self):
        super().__init__(...)
        self.type = MemoryType.FILE
        
        # Generate unified ID
        if self.semantic_id:
            self.id = str(self.semantic_id)
        else:
            # Fallback for compatibility
            if self.start_line and self.end_line:
                self.id = f"{self.location}:{self.start_line}-{self.end_line}"
            else:
                self.id = self.location
```

### Benefits for Agents

1. **Semantic Understanding**: 
   - Old: `msg:/home/agent/inbox/message-123.json`
   - New: `message:inbox:from-alice/project-update:a7b9c2`

2. **Content Deduplication**:
   - Same content gets same hash suffix
   - Agents can identify duplicate memories

3. **Hierarchical Navigation**:
   - `knowledge:rom:cognitive/*` - All cognitive knowledge
   - `file:personal:notes/*` - All personal notes

4. **Stable References**:
   - IDs based on semantic meaning, not physical location
   - Moving files doesn't break references

### Migration Strategy

1. **Dual ID Support**: Memory blocks support both old and new IDs
2. **Lazy Migration**: Convert IDs as memories are accessed
3. **ID Translation Layer**: Map old IDs to new ones
4. **Compatibility Mode**: Accept both formats in actions

```python
class MemoryIDTranslator:
    """Translate between old and new ID formats."""
    
    def translate_to_unified(self, old_id: str, context: Dict) -> str:
        """Convert old ID to new format."""
        # Handle different old patterns
        if old_id.startswith("msg:"):
            path = old_id[4:]
            return self._translate_message_id(path, context)
        elif old_id.startswith("knowledge:"):
            return old_id  # Already somewhat unified
        elif ":" in old_id and "-" in old_id.split(":")[-1]:
            # File with line range
            return self._translate_file_with_range(old_id, context)
        else:
            # Assume file path
            return self._translate_file_path(old_id, context)
```

### Action Interface Changes

```python
# Old way - using paths or opaque IDs
{
    "action": "focus_memory",
    "params": {
        "memory_id": "/home/agent/memory/notes.txt"
    }
}

# New way - using semantic IDs
{
    "action": "focus_memory", 
    "params": {
        "memory_id": "file:personal:notes/daily/today"
    }
}

# Also support content-based queries
{
    "action": "focus_memory",
    "params": {
        "memory_query": {
            "type": "file",
            "namespace": "personal",
            "semantic_path_pattern": "notes/*",
            "content_contains": "OODIA loop"
        }
    }
}
```

### Future Enhancements

1. **Semantic Relationships**: Link related memories by ID patterns
2. **Version Tracking**: Add version component for memory evolution
3. **Cross-References**: IDs can reference other IDs
4. **Smart Aliases**: Common patterns like "today's notes"

## Implementation Recommendations

### Phase 1: Foundation (Week 1)
1. Implement `UnifiedMemoryID` class
2. Add to existing memory blocks without breaking compatibility
3. Create ID translation layer
4. Update memory manager to handle both formats

### Phase 2: Migration (Week 2)
1. Update actions to generate new IDs
2. Add migration utility for existing memories
3. Update search to use semantic paths
4. Test with existing agents

### Phase 3: Enhancement (Week 3)
1. Add content-based queries
2. Implement semantic relationships
3. Add ID aliases and shortcuts
4. Documentation and examples

### Code Example: Updated Memory Creation

```python
class CreateMemoryAction(Action):
    """Updated create memory action with unified IDs."""
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        content = self.params.get("content", "")
        location = self.params.get("location", "")
        semantic_path = self.params.get("semantic_path", "")
        
        # Support both old and new ways
        if semantic_path:
            # New way - semantic path
            unified_id = UnifiedMemoryID(
                type="file",
                namespace="personal" if not semantic_path.startswith("shared/") else "shared",
                semantic_path=semantic_path.replace("shared/", ""),
                content_hash=calculate_hash(content)[:6]
            )
            
            # Determine actual file path
            file_path = self._resolve_semantic_path(unified_id, context)
        else:
            # Old way - location-based
            file_path = Path(location)
            unified_id = UnifiedMemoryID.from_file_path(file_path, context["home_dir"])
        
        # Create memory with both IDs
        memory = FileMemoryBlock(
            location=str(file_path),  # For compatibility
            semantic_id=unified_id,    # New unified ID
            metadata={
                "created_by": "agent",
                "semantic_path": unified_id.semantic_path
            }
        )
        
        # Rest of implementation...
```

## Conclusion

This unified memory ID system addresses the current inconsistencies while providing:
- Better semantic understanding for agents
- Stable references independent of file locations  
- Content-aware deduplication
- Backward compatibility
- Natural hierarchical organization

The phased implementation allows gradual migration without breaking existing agents, while the semantic approach aligns with how agents naturally think about memories - by meaning, not by filesystem paths.