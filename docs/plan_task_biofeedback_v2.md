# Plan v2: Biofeedback + Task Rework (Mind-Swarm Aligned)

Based on the Mind-Swarm architecture review, this updated plan simplifies the original approach by leveraging existing patterns and removing unnecessary complexity.

## Key Simplifications from v1

1. **No locks needed** - Cybers run as separate processes with atomic file operations
2. **No backward compatibility** - Clean implementation in subspace_template
3. **Leverage existing patterns** - Use MemoryBlock system and python_modules pattern
4. **Simpler file structure** - Follow existing conventions in .internal/

## Phase 1: Status Module and Biofeedback

### 1. New Status Python Module
Create `subspace_template/grid/library/non-fiction/mind_swarm_tech/base_code/base_code_template/python_modules/status.py`:

```python
"""
# Status and Biofeedback API for Cybers

## Core Concept
Provides consolidated status view with biofeedback metrics to help Cybers maintain balanced activity.

## Examples
```python
# Get current biofeedback
stats = status.get_biofeedback()
print(f"Boredom: {stats['boredom']}%, Tiredness: {stats['tiredness']}%")

# Update status display
status.render()
```
"""

class Status:
    def __init__(self, context):
        self.context = context
        self.personal = Path(context['personal_dir'])
        self.cognitive_loop = context.get('cognitive_loop')
        self.memory_system = context.get('memory_system')
        
        # Biofeedback state file
        self.state_file = self.personal / '.internal' / 'memory' / 'status' / 'biofeedback_state.json'
        self.status_file = self.personal / '.internal' / 'memory' / 'status' / 'status.txt'
        self.status_json = self.personal / '.internal' / 'memory' / 'status' / 'status.json'
        
    def get_biofeedback(self) -> Dict[str, int]:
        """Calculate current biofeedback stats (0-100)."""
        # Load persisted state
        # Calculate:
        # - Tiredness: cycles since last Maintenance task
        # - Boredom: consecutive cycles on same non-Hobby task  
        # - Duty: Community tasks in rolling window
        
    def render(self):
        """Generate consolidated status files."""
        # Create status.txt and status.json with:
        # - Identity, biofeedback bars, cycle info
        # - Location tree, current task, todo list
        # - Recent activity log entries
```

### 2. Integration Points

#### In cognitive_loop.py
After dynamic context update (around line 200):
```python
# Update status display each cycle
from .python_modules.status import Status
status = Status(context)
status.render()
```

#### In environment_scanner.py
Add pinned status file scanning:
```python
def _scan_status_file(self) -> List[MemoryBlock]:
    """Scan the consolidated status file."""
    status_path = self.personal_path / '.internal' / 'memory' / 'status' / 'status.txt'
    if status_path.exists():
        return [MemoryBlock(
            source_path=str(status_path),
            priority=Priority.HIGH,
            pinned=True,
            tags=["status", "biofeedback", "self"]
        )]
```

### 3. Biofeedback Thresholds
- 60% warning: Advisory message in status
- 80% alert: Stronger suggestion to switch task type
- Simple decay rates configurable in biofeedback_state.json

## Phase 2: Enhanced Task System

### 1. Extend Existing tasks.py Module

Update the existing `python_modules/tasks.py`:

```python
def create(self, summary: str, description: str = "", 
           task_type: str = "general",  # New: "hobby", "maintenance", "community"
           todo_list: List[Dict] = None,  # New: [{title, status, notes}]
           context: List[str] = None) -> str:
    """Create a new task with type and todo list."""
    
    task_data = {
        'id': task_id,
        'summary': summary,
        'description': description,
        'task_type': task_type,
        'todo': todo_list or [],
        'current': False,
        'created': datetime.now().isoformat(),
        'updated': datetime.now().isoformat()
    }

def update_todo(self, task_id: str, index: int, 
                status: str = None, notes: str = None):
    """Update a todo item status."""
    # Status: "NOT-STARTED", "IN-PROGRESS", "DONE", "BLOCKED"

def claim_community_task(self, task_id: str) -> bool:
    """Claim a community task from the pool."""
    # Move from /grid/community/tasks/ to personal/active/
    # Set claimed_by and claimed_at fields
    
def set_current(self, task_id: str):
    """Set task as current (shown in status)."""
    # Update current flag in task data
    # Write to current_task.txt for quick access
```

### 2. Task Storage Structure

Use existing patterns, no new directories needed:
```
/personal/.internal/tasks/
├── active/          # Current tasks (existing)
├── completed/       # Completed tasks (existing)  
├── blocked/         # Blocked tasks (existing)
├── hobby/          # New: Personal hobby backlog
├── maintenance/    # New: Maintenance task backlog
└── current_task.txt # New: Quick pointer to current task ID

/grid/community/tasks/  # New: Shared task pool
├── CT-001.json
├── CT-002.json
└── ...
```

### 3. Task Lifecycle Rules

Implement in tasks.py methods:
- Max 1 active community task per Cyber
- Max 3 hobby tasks in backlog  
- Maintenance tasks reset when all complete
- Community completion creates review task (prevent self-review)

## Phase 3: Memory Integration

### 1. Status as Primary Memory

In `memory_selector.py`, prioritize status memory:
```python
def _select_by_priority(self, memories: List[MemoryBlock]) -> List[MemoryBlock]:
    # Always include pinned status.txt first
    status_memories = [m for m in memories if 'status' in m.tags and m.pinned]
    # Then other HIGH priority...
```

### 2. Task Context in Pipeline

Tasks module already creates memory blocks. Enhance to include:
- Current task in decision stage context
- Todo progress in execution planning
- Task completion in reflection stage

## Phase 4: Testing and Rollout

### 1. Test Utilities
Create `scripts/test_status_tasks.py`:
```python
# Test script to verify status generation
# Test biofeedback calculations
# Test task lifecycle operations
# Test community task claiming
```

### 2. Migration Path
1. Deploy new python_modules/status.py
2. Update execution_stage.py to include status module
3. Enhance existing tasks.py with new features
4. Create /grid/community/tasks/ directory
5. Test with single Cyber first
6. Roll out to all Cybers

## Implementation Benefits

This approach:
- Uses existing MemoryBlock system (no new memory types)
- Follows python_modules pattern (easy integration)
- Leverages atomic file operations (no locks needed)
- Maintains cyber perspective (clean /personal view)
- Minimal changes to core systems

## Acceptance Criteria

1. ✅ Status module generates consolidated status.txt every cycle
2. ✅ Biofeedback responds to task activity patterns
3. ✅ Tasks support type categorization and todo lists
4. ✅ Community task claiming is atomic (first Cyber wins)
5. ✅ Current task appears prominently in status display
6. ✅ Cybers can discover and use new APIs naturally

## Next Steps

1. Implement status.py module
2. Update execution_stage.py to register it
3. Enhance tasks.py with new features
4. Test with development Cyber
5. Document in knowledge files for Cyber discovery