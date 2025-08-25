# Community Tasks Folder Organization

## Overview

Community tasks are now organized into state-based folders to improve visibility and prevent cybers from seeing all tasks regardless of state. This change ensures cybers only perceive tasks relevant to their current context.

## Folder Structure

```
/grid/community/tasks/
├── open/        # Available tasks that can be claimed
├── claimed/     # Tasks currently being worked on
├── completed/   # Finished tasks for reference
└── .description.txt
```

## Changes Implemented

### 1. Folder Creation
- Created three subdirectories: `open/`, `claimed/`, `completed/`
- Tasks move between folders based on their lifecycle state

### 2. Task Lifecycle

| State | Folder | Description |
|-------|--------|-------------|
| Created | `open/` | New tasks available for claiming |
| Claimed | `claimed/` | Task assigned to a specific cyber |
| Completed | `completed/` | Finished tasks kept for reference |
| Abandoned | `open/` | Released tasks return to open |

### 3. API Updates

#### claim_community_task()
- Now searches only in `open/` folder
- Moves task to `claimed/` folder upon successful claim
- Updates claimed_by and claimed_at fields

#### complete()
- For community tasks, moves from `claimed/` to `completed/`
- Updates completion timestamp and notes

#### release_community_task() [NEW]
- Releases a claimed task back to `open/`
- Clears claim fields
- Allows cyber to abandon a task they can't complete

#### get_available_community_tasks()
- Only searches `open/` folder
- Returns truly available tasks (not claimed ones)

### 4. Memory Visibility

**Before**: All tasks appeared in memory regardless of state
```
/grid/community/tasks/CT-001.json (open)
/grid/community/tasks/CT-002.json (claimed)
/grid/community/tasks/CT-003.json (completed)
```

**After**: Tasks organized by state
```
/grid/community/tasks/open/CT-001.json
/grid/community/tasks/claimed/CT-002.json
/grid/community/tasks/completed/CT-003.json
```

## Benefits

1. **Cleaner Perception**: Cybers only see relevant tasks in each folder
2. **State Clarity**: Folder location immediately indicates task state
3. **Reduced Confusion**: No need to check claimed_by field to understand availability
4. **Better Organization**: Historical completed tasks don't clutter active view

## Usage Examples

### Claiming a Task
```python
# Only searches open/ folder
if tasks.claim_community_task("CT-001"):
    print("Task claimed and moved to claimed/ folder")
```

### Completing a Task
```python
# Moves from claimed/ to completed/
tasks.complete("CT-001", notes="Implemented successfully")
```

### Releasing a Task
```python
# Moves back from claimed/ to open/
if tasks.release_community_task("CT-001"):
    print("Task released back to open pool")
```

### Viewing Available Tasks
```python
# Only shows tasks in open/ folder
available = tasks.get_available_community_tasks()
for task in available:
    print(f"{task['id']}: {task['summary']}")
```

## Migration

Existing tasks are automatically moved to the appropriate folder:
- Unclaimed tasks → `open/`
- Claimed tasks → `claimed/`  
- Completed tasks → `completed/`

## Future Improvements

1. **Blocked Folder**: Add `blocked/` for tasks with dependencies
2. **Archive System**: Periodically archive old completed tasks
3. **Priority Sorting**: Order tasks within folders by priority
4. **Stale Task Detection**: Auto-release long-claimed inactive tasks