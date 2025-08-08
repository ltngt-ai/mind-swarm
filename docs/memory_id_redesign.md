# Memory ID System Redesign

## Current Issues

1. **Inconsistent ID Formats**: 
   - Observation IDs like `observation:personal:memory_focused/grid:file:community:cyber_directory.json:d74ce1`
   - Double prefixing: `personal:file:personal:personal:file:personal:cyber_directory_changes.json`
   - Mixed separators: colons vs slashes

2. **Path vs ID Confusion**:
   - Some code expects filesystem paths
   - Other code expects memory IDs
   - No clear conversion between the two

3. **Nested IDs**:
   - Observations about memories include the full memory ID in their path
   - This creates confusing nested structures

## Proposed Solution

### Memory ID Format

**Standard Format**: `<namespace>:<type>:<path>`

Where:
- `namespace`: Either `personal` or `grid` 
- `type`: The memory type (file, observation, knowledge, etc.)
- `path`: The semantic path using forward slashes

**Examples**:
- `personal:file:memory/journal.md`
- `grid:file:community/cyber_directory.json`
- `personal:observation:new_message/msg_123`
- `grid:knowledge:rom/actions/action_system`

### Key Changes

1. **No Double Prefixing**: Never add namespace prefix if already present
2. **Consistent Separators**: Use colons for ID components, slashes for paths
3. **Clear Conversion**: Explicit methods to convert between IDs and filesystem paths

### Conversion Rules

#### Memory ID → Filesystem Path
```
personal:file:memory/journal.md → /personal/memory/journal.md
grid:file:community/discussion.txt → /grid/community/discussion.txt
```

#### Filesystem Path → Memory ID
```
/personal/inbox/msg.txt → personal:file:inbox/msg.txt
/grid/library/knowledge.yaml → grid:file:library/knowledge.yaml
```

### Observations About Memories

When creating observations about memory operations:
- Store the referenced memory ID in metadata
- Use a simple semantic path for the observation itself

Example:
```python
# Instead of path=memory_id
obs = ObservationMemoryBlock(
    observation_type="memory_focused",
    path="focused/cyber_directory",  # Simple semantic path
    metadata={
        "memory_id": memory_id,  # Store actual memory ID here
        "focus_type": focus_type
    }
)
```

## Implementation Plan

1. Update `UnifiedMemoryID` class:
   - Fix ID pattern regex
   - Add proper path conversion methods
   - Prevent double prefixing

2. Fix `memory_actions.py`:
   - Don't pass memory IDs as paths to observations
   - Store memory IDs in metadata instead

3. Update `memory_blocks.py`:
   - Ensure consistent ID generation
   - Fix path handling in observations

4. Add validation:
   - Check for double prefixes
   - Validate ID format consistency