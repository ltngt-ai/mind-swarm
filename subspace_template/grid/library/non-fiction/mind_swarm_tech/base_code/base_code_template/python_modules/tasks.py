"""
# Task Management API for Cybers

## Core Concept: Simple Task Tracking
The Tasks API provides a lightweight way for Cybers to manage their tasks.
Tasks are stored as JSON files with summaries visible in status.txt.

## Examples

### Intention: "I want to create a new task"
```python
task_id = tasks.create(
    summary="Help Alice with memory management",
    description="Alice needs help implementing memory persistence. Issues with memory blocks not saving.",
    task_type="community",  # hobby, maintenance, or community
    todo_list=[  # Note: stored internally as 'todo' for consistency
        {"title": "Review Alice's code", "status": "NOT-STARTED"},
        {"title": "Identify the issue", "status": "NOT-STARTED"},
        {"title": "Propose solution", "status": "NOT-STARTED"}
    ],
    context=["/personal/.internal/messages/Alice_51.msg"]
)
print(f"Created task {task_id}")
```

### Intention: "I want to see my current task"
```python
current = tasks.get_current()
if current:
    print(f"Current task: {current['summary']}")
else:
    print("No current task set")
```

### Intention: "I want to complete a task"
```python
tasks.complete("task_001", notes="Helped Alice fix the memory block persistence issue")
```

### Intention: "I want to block a task"
```python
tasks.block("task_002", reason="Waiting for Bob's response on API design")
```

### Intention: "I want to update a todo item"
```python
tasks.update_todo("task_001", 0, status="DONE", notes="Completed review")
```

### Intention: "I want to set current task"
```python
tasks.set_current("task_001")
```

### Intention: "I want to claim a community task"
```python
if tasks.claim_community_task("CT-042"):
    print("Successfully claimed community task")
```

## Best Practices
1. Keep summaries concise (one line, <80 chars)
2. Use descriptions for full context
3. Reference relevant files in context array
4. Add notes when completing/blocking for future reference
"""

import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import re

logger = logging.getLogger("Cyber.tasks")

class TasksError(Exception):
    """Base exception for task errors."""
    pass

class Tasks:
    """Manages cyber tasks with simple file-based storage."""
    
    def __init__(self, context: Dict[str, Any]):
        """Initialize the Tasks API.
        
        Args:
            context: Execution context containing personal_dir, etc.
        """
        self.context = context
        self.personal = Path(context.get('personal_dir', '/personal'))
        
        # Get state manager from context for unified state access
        self.state_manager = context.get('state_manager')
        if not self.state_manager:
            raise TasksError("State manager is required in context for Tasks API")
        
        # Task directories
        self.tasks_root = self.personal / '.internal' / 'tasks'
        self.completed_dir = self.tasks_root / 'completed'
        self.blocked_dir = self.tasks_root / 'blocked'
        self.hobby_dir = self.tasks_root / 'hobby'
        self.maintenance_dir = self.tasks_root / 'maintenance'
        
        # Community tasks in grid with state folders
        self.grid = Path('/grid')  # Grid is always at /grid from cyber perspective
        self.community_dir = self.grid / 'community' / 'tasks'
        self.community_open_dir = self.community_dir / 'open'
        self.community_claimed_dir = self.community_dir / 'claimed'
        self.community_completed_dir = self.community_dir / 'completed'
        
        # Ensure directories exist (no more active directory)
        for dir in [self.completed_dir, self.blocked_dir, 
                   self.hobby_dir, self.maintenance_dir]:
            dir.mkdir(parents=True, exist_ok=True)
    
    def _get_next_id(self, task_type: str) -> str:
        """Get the next available task ID for the given type.
        
        Args:
            task_type: Type of task (hobby or maintenance)
            
        Returns:
            Task ID with proper prefix (HT-001 or MT-001)
        """
        # Determine prefix based on task type
        prefix_map = {
            'hobby': 'HT',
            'maintenance': 'MT'
        }
        prefix = prefix_map.get(task_type)
        if not prefix:
            raise TasksError(f"Invalid task_type: {task_type}. Must be 'hobby' or 'maintenance'")
        
        max_id = 0
        
        # Check all directories for existing task IDs with this prefix
        pattern = f"{prefix}-*.json"
        separator = '-'
        
        for dir in [self.completed_dir, self.blocked_dir, 
                   self.hobby_dir, self.maintenance_dir]:
            if dir.exists():
                for task_file in dir.glob(pattern):
                    # Extract ID from filename
                    match = re.match(rf"{prefix}{separator}(\d+)[_.]?", task_file.stem)
                    if match:
                        task_id = int(match.group(1))
                        max_id = max(max_id, task_id)
        
        # Also check community tasks in all state folders
        if task_type == 'community':
            for state_dir in [self.community_open_dir, self.community_claimed_dir, self.community_completed_dir]:
                if state_dir.exists():
                    for task_file in state_dir.glob("CT-*.json"):
                        match = re.match(r"CT-(\d+)", task_file.stem)
                        if match:
                            task_id = int(match.group(1))
                            max_id = max(max_id, task_id)
        
        # Format the new ID
        new_id = max_id + 1
        return f"{prefix}-{new_id:03d}"
    
    def _sanitize_filename(self, text: str, max_length: int = 50) -> str:
        """Sanitize text for use in filename."""
        # Remove special characters, keep alphanumeric and spaces
        sanitized = re.sub(r'[^a-zA-Z0-9\s]', '', text)
        # Replace spaces with underscores
        sanitized = re.sub(r'\s+', '_', sanitized).strip('_')
        # Truncate and lowercase
        return sanitized[:max_length].lower()
    
    def create(self, 
               summary: str,
               task_type: str,
               description: str = "",
               todo_list: Optional[List[Dict[str, str]]] = None,
               context: Optional[List[str]] = None,
               notes: str = "") -> str:
        """Create a new task.
        
        Args:
            summary: One-line summary of the task
            description: Detailed description
            task_type: Type of task - only 'hobby' (maintenance tasks are predefined)
            todo_list: List of todo items with 'title' and optional 'status' and 'notes'
            context: List of relevant file paths
            notes: Any additional notes
            
        Returns:
            Task ID of the created task
            
        Raises:
            TasksError: If hobby task limit exceeded or invalid task type
            
        Example:
            task_id = tasks.create(
                summary="Research new algorithm",
                task_type="hobby",
                description="Study and implement a new pathfinding algorithm",
                todo_list=[{"title": "Read documentation", "status": "NOT-STARTED"}],
                context=["/personal/research/"]
            )
        """
        # Validate task type - only hobby tasks can be created
        if task_type == 'maintenance':
            raise TasksError(
                "Maintenance tasks cannot be created - they are predefined system tasks. "
                "You can only create 'hobby' tasks. Maintenance tasks are automatically "
                "provided and reset when all are completed."
            )
        
        valid_types = ['hobby']
        if task_type not in valid_types:
            raise TasksError(f"Invalid task_type: {task_type}. Only 'hobby' tasks can be created.")
        
        # Check hobby task limit (5 max)
        if task_type == 'hobby':
            # Count hobby tasks in both hobby dir and active dir
            hobby_count = 0
            
            # Check hobby directory
            for f in self.hobby_dir.glob("HT-*.json"):
                hobby_count += 1
            
            # Hobby tasks are only in hobby directory now
                
            if hobby_count >= 5:
                raise TasksError(
                    f"Maximum of 5 hobby tasks allowed. You currently have {hobby_count} hobby tasks. "
                    f"Please complete or remove some before creating new ones."
                )
        
        task_id = self._get_next_id(task_type)
        
        # Process todo items
        if todo_list:
            # Ensure each todo has required fields
            processed_todos = []
            for i, todo in enumerate(todo_list[:10]):  # Max 10 todos
                processed_todo = {
                    "title": todo.get("title", f"Todo {i+1}"),
                    "status": todo.get("status", "NOT-STARTED"),
                    "notes": todo.get("notes", "")
                }
                # Validate status
                if processed_todo["status"] not in ["NOT-STARTED", "IN-PROGRESS", "DONE", "BLOCKED"]:
                    processed_todo["status"] = "NOT-STARTED"
                processed_todos.append(processed_todo)
            todo_list = processed_todos
        else:
            todo_list = []
        
        # Create task data
        task_data = {
            "id": task_id,
            "summary": summary[:100],  # Limit summary length
            "description": description,
            "task_type": task_type,
            "todo": todo_list,
            "status": "active",
            "current": False,
            "created": datetime.now().isoformat(),
            "updated": datetime.now().isoformat(),
            "context": context or [],
            "notes": notes
        }
        
        # Create filename and place in appropriate backlog directory
        filename = f"{task_id}_{self._sanitize_filename(summary)}.json"
        
        # Determine target directory based on task type
        if task_type == 'hobby':
            task_file = self.hobby_dir / filename
        elif task_type == 'maintenance':
            task_file = self.maintenance_dir / filename
        else:
            raise TasksError(f"Invalid task type: {task_type}")
        
        # Write task file
        with open(task_file, 'w') as f:
            json.dump(task_data, f, indent=2)
        
        return task_id
    
    
    def get_blocked(self) -> List[Dict[str, Any]]:
        """Get all blocked tasks.
        
        Returns:
            List of blocked task dictionaries
        """
        return self._get_tasks_from_dir(self.blocked_dir)
    
    def get_completed(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recently completed tasks.
        
        Args:
            limit: Maximum number of tasks to return
            
        Returns:
            List of completed task dictionaries
        """
        tasks = self._get_tasks_from_dir(self.completed_dir)
        # Sort by completion time (most recent first)
        tasks.sort(key=lambda x: x.get('completed_at', x.get('created', '')), reverse=True)
        return tasks[:limit]
    
    def _get_tasks_from_dir(self, directory: Path) -> List[Dict[str, Any]]:
        """Get all tasks from a directory."""
        tasks = []
        
        for task_file in directory.glob("task_*.json"):
            try:
                with open(task_file, 'r') as f:
                    task_data = json.load(f)
                    # Add file path for reference
                    task_data['_file'] = str(task_file)
                    tasks.append(task_data)
            except Exception:
                # Skip corrupted files
                pass
        
        # Sort by creation time
        tasks.sort(key=lambda x: x.get('created', ''))
        return tasks
    
    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific task by ID.
        
        Args:
            task_id: The task ID to retrieve
            
        Returns:
            Task dictionary or None if not found
            
        Example:
            task = tasks.get("task_001")
            if task:
                print(task['description'])
        """
        # Search all directories (backlog, blocked, completed)
        for dir in [self.hobby_dir, self.maintenance_dir, self.blocked_dir, self.completed_dir]:
            for task_file in dir.glob(f"{task_id}_*.json"):
                try:
                    with open(task_file, 'r') as f:
                        task_data = json.load(f)
                        task_data['_file'] = str(task_file)
                        # Handle field name inconsistency: normalize todo_list to todo
                        if 'todo_list' in task_data and 'todo' in task_data:
                            # If both exist, prefer todo_list if it has content
                            if task_data['todo_list'] and not task_data['todo']:
                                task_data['todo'] = task_data['todo_list']
                            del task_data['todo_list']  # Remove the deprecated field
                        elif 'todo_list' in task_data:
                            # Migrate todo_list to todo
                            task_data['todo'] = task_data.get('todo_list', [])
                            del task_data['todo_list']
                        return task_data
                except Exception:
                    pass
        
        # Also check community tasks claimed by this cyber
        try:
            status_file = self.personal / '.internal' / 'status.json'
            with open(status_file, 'r') as f:
                cyber_name = json.load(f)['name']
            
            # Check claimed community tasks folder for tasks claimed by us
            if self.community_claimed_dir.exists():
                for potential_file in self.community_claimed_dir.glob(f"{task_id}_*.json"):
                    with open(potential_file, 'r') as f:
                        task_data = json.load(f)
                        if task_data.get('claimed_by') == cyber_name:
                            task_data['_file'] = str(potential_file)
                            # Handle field name inconsistency here too
                            if 'todo_list' in task_data and 'todo' in task_data:
                                if task_data['todo_list'] and not task_data['todo']:
                                    task_data['todo'] = task_data['todo_list']
                                del task_data['todo_list']
                            elif 'todo_list' in task_data:
                                task_data['todo'] = task_data.get('todo_list', [])
                                del task_data['todo_list']
                            return task_data
        except Exception:
            pass
        
        return None
    
    def complete(self, task_id: str, notes: str = "") -> bool:
        """Mark a task as completed.
        
        Args:
            task_id: The task ID to complete
            notes: Completion notes
            
        Returns:
            True if successful, False otherwise
            
        Example:
            tasks.complete("task_001", notes="Fixed the issue")
        """
        return self._move_task(task_id, self.completed_dir, 
                              updates={"status": "completed", 
                                     "completed_at": datetime.now().isoformat(),
                                     "completion_notes": notes})
    
    def block(self, task_id: str, reason: str = "") -> bool:
        """Mark a task as blocked.
        
        Args:
            task_id: The task ID to block
            reason: Why the task is blocked
            
        Returns:
            True if successful, False otherwise
            
        Example:
            tasks.block("task_002", reason="Waiting for API access")
        """
        return self._move_task(task_id, self.blocked_dir,
                              updates={"status": "blocked",
                                     "blocked_at": datetime.now().isoformat(),
                                     "blocked_reason": reason})
    
    def unblock(self, task_id: str, notes: str = "") -> bool:
        """Unblock a task and return it to its backlog.
        
        Args:
            task_id: The task ID to unblock
            notes: Notes about unblocking
            
        Returns:
            True if successful, False otherwise
        """
        # Find the blocked task first to determine its type
        task = self.get(task_id)
        if not task:
            return False
            
        # Determine target directory based on task type
        if task_id.startswith('HT-'):
            target_dir = self.hobby_dir
        elif task_id.startswith('MT-'):
            target_dir = self.maintenance_dir
        else:
            return False
            
        return self._move_task(task_id, target_dir,
                              updates={"status": "pending",
                                     "unblocked_at": datetime.now().isoformat(),
                                     "unblock_notes": notes})
    
    def update_todo(self, task_id: str, index: int, 
                    status: Optional[str] = None, notes: Optional[str] = None) -> bool:
        """Update a todo item in a task.
        
        Args:
            task_id: The task ID
            index: Zero-based index of the todo item
            status: New status (NOT-STARTED, IN-PROGRESS, DONE, BLOCKED)
            notes: Additional notes for the todo
            
        Returns:
            True if successful, False otherwise
            
        Example:
            tasks.update_todo("task_001", 0, status="DONE", notes="Completed review")
        """
        task = self.get(task_id)
        if not task:
            return False
        
        todos = task.get('todo', [])
        if index < 0 or index >= len(todos):
            return False
        
        # Update the todo item
        if status:
            if status in ["NOT-STARTED", "IN-PROGRESS", "DONE", "BLOCKED"]:
                todos[index]['status'] = status
        if notes is not None:
            todos[index]['notes'] = notes
        
        # Update task
        task['todo'] = todos
        task['updated'] = datetime.now().isoformat()
        
        # Save task - ensure we don't save the deprecated todo_list field
        try:
            task_file = Path(task['_file'])
            with open(task_file, 'w') as f:
                # Remove internal _file key and any todo_list field before saving
                save_data = {k: v for k, v in task.items() 
                           if not k.startswith('_') and k != 'todo_list'}
                json.dump(save_data, f, indent=2)
            return True
        except Exception:
            return False
    
    def set_current(self, task_id: str) -> bool:
        """Set a task as the current task.
        
        Args:
            task_id: The task ID to set as current
            
        Returns:
            True if successful, False otherwise
            
        Example:
            tasks.set_current("task_001")
        """
        task = self.get(task_id)
        if not task:
            return False
        
        try:
            # Clear current flag on all tasks
            for dir in [self.hobby_dir, self.maintenance_dir, self.blocked_dir]:
                for task_file in dir.glob("*.json"):
                    with open(task_file, 'r') as f:
                        data = json.load(f)
                    if data.get('current'):
                        data['current'] = False
                        with open(task_file, 'w') as f:
                            json.dump(data, f, indent=2)
            
            # Set current flag on selected task
            task['current'] = True
            task['updated'] = datetime.now().isoformat()
            
            task_file = Path(task['_file'])
            with open(task_file, 'w') as f:
                # Remove internal _file key and any todo_list field before saving
                save_data = {k: v for k, v in task.items() 
                           if not k.startswith('_') and k != 'todo_list'}
                json.dump(save_data, f, indent=2)
            
            # Update unified state with current task
            from ..state.unified_state_manager import StateSection
            self.state_manager.update_value(StateSection.TASK, "current_task_id", task_id)
            self.state_manager.update_value(StateSection.TASK, "current_task_type", 
                                           "hobby" if task_id.startswith("HT-") else 
                                           "maintenance" if task_id.startswith("MT-") else 
                                           "community")
            self.state_manager.update_value(StateSection.TASK, "current_task_summary", 
                                           task.get('summary', ''))
            self.state_manager.update_value(StateSection.TASK, "task_started_cycle", 
                                           self.state_manager.get_value(StateSection.COGNITIVE, "cycle_count", 0))
            
            return True
        except Exception:
            return False
    
    def get_current(self) -> Optional[Dict[str, Any]]:
        """Get the current task.
        
        Returns:
            Current task dictionary or None if no current task
            
        Example:
            current = tasks.get_current()
            if current:
                print(f"Working on: {current['summary']}")
        """
        try:
            # Get current task ID from unified state
            from ..state.unified_state_manager import StateSection
            task_id = self.state_manager.get_value(StateSection.TASK, "current_task_id")
            if task_id:
                return self.get(task_id)
        except Exception:
            pass
        return None
    
    def claim_community_task(self, task_id: str) -> bool:
        """Claim a community task from the grid.
        
        Args:
            task_id: The community task ID (e.g., "CT-001")
            
        Returns:
            True if successfully claimed, False otherwise
            
        Example:
            if tasks.claim_community_task("CT-042"):
                print("Successfully claimed community task")
        """
        if not self.community_open_dir.exists():
            return False
        
        # Check if already have an active community task
        current_task = self.get_current()
        if current_task and current_task.get('task_type') == 'community':
            raise TasksError("Already have an active community task. Complete or block it first.")
        
        # Find the community task in open folder
        task_files = list(self.community_open_dir.glob(f"{task_id}_*.json"))
        if not task_files:
            # Also check for exact match
            exact_file = self.community_open_dir / f"{task_id}.json"
            if exact_file.exists():
                task_file = exact_file
            else:
                return False
        else:
            task_file = task_files[0]  # Use first match
        
        try:
            # Read task data
            with open(task_file, 'r') as f:
                task_data = json.load(f)
            
            # Check if already claimed (shouldn't happen in open folder but double-check)
            if task_data.get('claimed_by'):
                return False
            
            # Get cyber name from status.json
            status_file = self.personal / '.internal' / 'status.json'
            with open(status_file, 'r') as f:
                status_data = json.load(f)
                cyber_name = status_data['name']
            
            # Claim the task
            task_data['claimed_by'] = cyber_name
            task_data['claimed_at'] = datetime.now().isoformat()
            
            # Ensure claimed directory exists
            self.community_claimed_dir.mkdir(parents=True, exist_ok=True)
            
            # Move to claimed folder atomically
            claimed_file = self.community_claimed_dir / task_file.name
            temp_file = claimed_file.with_suffix('.tmp')
            
            # Write updated data to temp file in claimed folder
            with open(temp_file, 'w') as f:
                json.dump(task_data, f, indent=2)
            
            # Try to rename (atomic operation - only one will succeed)
            try:
                os.rename(temp_file, claimed_file)
                # Success! Now remove from open folder
                task_file.unlink()
                return True
            except OSError:
                # Someone else claimed it first
                if temp_file.exists():
                    temp_file.unlink()
                return False
            
        except Exception as e:
            # Log the error for debugging
            import traceback
            error_msg = f"Error claiming community task {task_id}: {str(e)}\n{traceback.format_exc()}"
            try:
                error_file = self.personal / '.internal' / 'logs' / 'task_errors.log'
                error_file.parent.mkdir(parents=True, exist_ok=True)
                with open(error_file, 'a') as f:
                    f.write(f"[{datetime.now().isoformat()}] {error_msg}\n")
            except:
                pass  # Can't log, but at least we tried
            return False
    
    def release_community_task(self, task_id: str) -> bool:
        """Release/abandon a claimed community task back to open.
        
        Args:
            task_id: The community task ID (e.g., "CT-001")
            
        Returns:
            True if successfully released, False otherwise
            
        Example:
            if tasks.release_community_task("CT-042"):
                print("Released community task back to open")
        """
        if not task_id.startswith("CT-"):
            return False
            
        try:
            # Find the task in claimed folder
            task_file = None
            if self.community_claimed_dir.exists():
                for potential_file in self.community_claimed_dir.glob(f"{task_id}_*.json"):
                    try:
                        with open(potential_file, 'r') as f:
                            task_data = json.load(f)
                            # Get cyber name
                            status_file = self.personal / '.internal' / 'status.json'
                            with open(status_file, 'r') as sf:
                                cyber_name = json.load(sf)['name']
                            # Check if it's our task
                            if task_data.get('claimed_by') == cyber_name:
                                task_file = potential_file
                                break
                    except:
                        pass
            
            if not task_file:
                return False
                
            # Read task data
            with open(task_file, 'r') as f:
                task_data = json.load(f)
            
            # Clear claim fields
            task_data['claimed_by'] = None
            task_data['claimed_at'] = None
            task_data['updated'] = datetime.now().isoformat()
            
            # Ensure open directory exists
            self.community_open_dir.mkdir(parents=True, exist_ok=True)
            
            # Move back to open folder
            open_file = self.community_open_dir / task_file.name
            with open(open_file, 'w') as f:
                json.dump(task_data, f, indent=2)
            
            # Remove from claimed folder
            task_file.unlink()
            
            # Clear current task if this was it
            from ..state.unified_state_manager import StateSection
            current_id = self.state_manager.get_value(StateSection.TASK, "current_task_id")
            if current_id == task_id:
                self.state_manager.update_value(StateSection.TASK, "current_task_id", None)
                self.state_manager.update_value(StateSection.TASK, "current_task_type", None)
                self.state_manager.update_value(StateSection.TASK, "current_task_summary", None)
                self.state_manager.update_value(StateSection.TASK, "task_started_cycle", None)
            
            return True
            
        except Exception:
            return False
    
    def get_available_community_tasks(self) -> List[Dict[str, Any]]:
        """Get list of available (unclaimed) community tasks.
        
        Returns:
            List of available community task dictionaries
            
        Example:
            for task in tasks.get_available_community_tasks():
                print(f"{task['id']}: {task['summary']}")
        """
        tasks = []
        if not self.community_open_dir.exists():
            return tasks
        
        # Only look in open folder - all tasks there are available
        for task_file in self.community_open_dir.glob("CT-*.json"):
            try:
                with open(task_file, 'r') as f:
                    task_data = json.load(f)
                    tasks.append(task_data)
            except Exception:
                pass
        
        return tasks
    
    def reset_maintenance(self) -> bool:
        """Reset all maintenance task todos to NOT-STARTED.
        
        Returns:
            True if successful, False otherwise
            
        Example:
            if tasks.reset_maintenance():
                print("Maintenance tasks reset")
        """
        try:
            for task_file in self.maintenance_dir.glob("task_*.json"):
                with open(task_file, 'r') as f:
                    task_data = json.load(f)
                
                # Reset all todos
                for todo in task_data.get('todo', []):
                    todo['status'] = 'NOT-STARTED'
                    todo['notes'] = ''
                
                task_data['updated'] = datetime.now().isoformat()
                
                with open(task_file, 'w') as f:
                    json.dump(task_data, f, indent=2)
            
            return True
        except Exception:
            return False
    
    def _move_task(self, task_id: str, target_dir: Path, updates: Dict[str, Any] = None) -> bool:
        """Move a task between directories and update its data."""
        # Find the task file
        task_file = None
        
        # Check personal task directories first
        for dir in [self.hobby_dir, self.maintenance_dir, self.blocked_dir, 
                   self.completed_dir]:
            matches = list(dir.glob(f"{task_id}_*.json"))
            if matches:
                task_file = matches[0]
                break
        
        # If not found, check community claimed folder (only tasks claimed by us)
        if not task_file and task_id.startswith("CT-"):
            if self.community_claimed_dir.exists():
                for potential_file in self.community_claimed_dir.glob(f"{task_id}_*.json"):
                    try:
                        with open(potential_file, 'r') as f:
                            task_data = json.load(f)
                            # Get cyber name
                            status_file = self.personal / '.internal' / 'status.json'
                            with open(status_file, 'r') as sf:
                                cyber_name = json.load(sf)['name']
                            # Check if it's our task
                            if task_data.get('claimed_by') == cyber_name:
                                task_file = potential_file
                                break
                    except:
                        pass
        
        if not task_file:
            return False
        
        try:
            # Read task data
            with open(task_file, 'r') as f:
                task_data = json.load(f)
            
            # Apply updates
            if updates:
                task_data.update(updates)
            
            # Remove deprecated todo_list field if present
            task_data.pop('todo_list', None)
            
            task_data['updated'] = datetime.now().isoformat()
            
            # Handle community tasks specially - they go to community folders
            if task_data.get('task_type') == 'community' or task_id.startswith("CT-"):
                # If completing a community task, move to community completed folder
                if target_dir == self.completed_dir:
                    self.community_completed_dir.mkdir(parents=True, exist_ok=True)
                    new_file = self.community_completed_dir / task_file.name
                else:
                    # For now, blocking community tasks keeps them in claimed
                    # (could add a blocked folder later if needed)
                    new_file = task_file
            else:
                # Regular personal task - use the target directory
                new_file = target_dir / task_file.name
            
            # Only move if it's a different location
            if new_file != task_file:
                # Write to new location
                with open(new_file, 'w') as f:
                    json.dump(task_data, f, indent=2)
                
                # Remove old file
                task_file.unlink()
            else:
                # Just update in place
                with open(task_file, 'w') as f:
                    json.dump(task_data, f, indent=2)
            
            # If this was the current task and we're completing/blocking it, clear from unified state
            if target_dir in [self.completed_dir, self.blocked_dir]:
                from ..state.unified_state_manager import StateSection
                current_id = self.state_manager.get_value(StateSection.TASK, "current_task_id")
                if current_id == task_id:
                    self.state_manager.update_value(StateSection.TASK, "current_task_id", None)
                    self.state_manager.update_value(StateSection.TASK, "current_task_type", None)
                    self.state_manager.update_value(StateSection.TASK, "current_task_summary", None)
                    self.state_manager.update_value(StateSection.TASK, "task_started_cycle", None)
            
            # Check if this was a maintenance task being completed
            if (task_data.get('task_type') == 'maintenance' and 
                target_dir == self.completed_dir):
                self._check_and_reset_maintenance_tasks()
            
            return True
            
        except Exception:
            return False
    
    def _check_and_reset_maintenance_tasks(self):
        """Check if all maintenance tasks are completed and reset them if so."""
        try:
            # Check if there are any maintenance tasks still in maintenance backlog or blocked
            backlog_maintenance = list(self.maintenance_dir.glob("MT-*.json"))
            blocked_maintenance = list(self.blocked_dir.glob("MT-*.json"))
            
            # Also check if current task is a maintenance task
            current_is_maintenance = False
            try:
                from ..state.unified_state_manager import StateSection
                current_id = self.state_manager.get_value(StateSection.TASK, "current_task_id")
                if current_id:
                    current_is_maintenance = current_id.startswith('MT-')
            except:
                pass
            
            # If no maintenance tasks are pending (all are completed), reset all
            if not backlog_maintenance and not blocked_maintenance and not current_is_maintenance:
                logger.info("All maintenance tasks completed - resetting for next cycle")
                
                # Get all maintenance tasks from completed directory
                completed_maintenance = list(self.completed_dir.glob("MT-*.json"))
                
                # Move them back to active directory and reset their status
                for task_file in completed_maintenance:
                    with open(task_file, 'r') as f:
                        task_data = json.load(f)
                    
                    # Reset task status
                    task_data['status'] = 'pending'
                    task_data['completed_at'] = None
                    task_data['completion_notes'] = None
                    
                    # Reset all todos
                    for todo in task_data.get('todo', []):
                        todo['status'] = 'NOT-STARTED'
                        if 'notes' in todo:
                            todo['notes'] = todo.get('notes', '').split(' - ')[0]  # Keep original note, remove any added context
                    
                    task_data['updated'] = datetime.now().isoformat()
                    
                    # Write back to maintenance directory
                    new_file = self.maintenance_dir / task_file.name
                    with open(new_file, 'w') as f:
                        json.dump(task_data, f, indent=2)
                    
                    # Remove from completed
                    task_file.unlink()
                    
                logger.info(f"Reset {len(completed_maintenance)} maintenance tasks")
                
        except Exception as e:
            logger.warning(f"Failed to check/reset maintenance tasks: {e}")
    
    def update(self, task_id: str, **kwargs) -> bool:
        """Update task fields.
        
        Args:
            task_id: The task ID to update
            **kwargs: Fields to update
            
        Returns:
            True if successful, False otherwise
            
        Example:
            tasks.update("task_001", 
                        description="Updated description",
                        notes="Added more context")
        """
        task = self.get(task_id)
        if not task:
            return False
        
        task_file = Path(task['_file'])
        
        # Update fields
        for key, value in kwargs.items():
            if key != '_file':  # Don't update internal fields
                task[key] = value
        
        # Add update timestamp
        task['updated_at'] = datetime.now().isoformat()
        
        # Remove internal field and todo_list before saving
        task.pop('_file', None)
        task.pop('todo_list', None)  # Remove deprecated field if present
        
        try:
            with open(task_file, 'w') as f:
                json.dump(task, f, indent=2)
            return True
        except Exception:
            return False
    
    def get_summary(self) -> Dict[str, Any]:
        """Get task statistics summary.
        
        Returns:
            Dictionary with task counts, summaries, and backlog
            
        Example:
            summary = tasks.get_summary()
            print(f"Active: {summary['active_count']}")
            print(f"Backlog tasks: {len(summary['backlog'])}")
        """
        # Get all non-completed tasks
        all_tasks = self.get_all()
        active = [t for t in all_tasks if t.get('status') != 'completed']
        blocked = self.get_blocked()
        completed = self.get_completed(5)
        
        # Create set of blocked task IDs for consistent filtering
        blocked_ids = set(t.get('id') for t in blocked)
        
        # Build backlog (all non-completed, non-blocked tasks) and find current task
        backlog = []
        current_task = None
        for task in all_tasks:
            # Use blocked_ids for consistent filtering with get_blocked()
            if task.get('status') != 'completed' and task.get('id') not in blocked_ids:
                task_info = {
                    'id': task['id'],
                    'summary': task['summary'],
                    'type': task.get('task_type', 'unknown'),
                    'current': task.get('current', False)
                }
                backlog.append(task_info)
                # Track current task while building backlog (optimization)
                if task_info['current'] and current_task is None:
                    current_task = task_info
        
        return {
            "active_count": len(active),
            "blocked_count": len(blocked),
            "completed_recent": len(completed),
            "active_summaries": [t['summary'] for t in active],
            "blocked_summaries": [t['summary'] for t in blocked],
            "backlog": backlog,  # Added backlog list
            "current_task": current_task  # Found during backlog construction
        }