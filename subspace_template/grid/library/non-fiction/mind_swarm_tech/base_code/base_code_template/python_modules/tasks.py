"""
# Task Management API for Cybers

## Core Concept: Simple Task Tracking
The Tasks API provides a lightweight way for Cybers to manage their tasks.
Tasks are stored as JSON files with a one-line summary visible in personal.txt.

## Examples

### Intention: "I want to create a new task"
```python
task_id = tasks.create(
    summary="Help Alice with memory management",
    description="Alice needs help implementing memory persistence. Issues with memory blocks not saving.",
    context=["/personal/.internal/messages/Alice_51.msg"]
)
print(f"Created task {task_id}")
```

### Intention: "I want to see my active tasks"
```python
active = tasks.get_active()
for task in active:
    print(f"• {task['summary']}")
```

### Intention: "I want to complete a task"
```python
tasks.complete("task_001", notes="Helped Alice fix the memory block persistence issue")
```

### Intention: "I want to block a task"
```python
tasks.block("task_002", reason="Waiting for Bob's response on API design")
```

## Best Practices
1. Keep summaries concise (one line, <80 chars)
2. Use descriptions for full context
3. Reference relevant files in context array
4. Add notes when completing/blocking for future reference
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import re

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
        
        # Task directories
        self.tasks_root = self.personal / '.internal' / 'tasks'
        self.active_dir = self.tasks_root / 'active'
        self.completed_dir = self.tasks_root / 'completed'
        self.blocked_dir = self.tasks_root / 'blocked'
        
        # Ensure directories exist
        for dir in [self.active_dir, self.completed_dir, self.blocked_dir]:
            dir.mkdir(parents=True, exist_ok=True)
        
        # Track next task ID
        self._next_id = self._get_next_id()
    
    def _get_next_id(self) -> int:
        """Get the next available task ID."""
        max_id = 0
        
        # Check all directories for existing task IDs
        for dir in [self.active_dir, self.completed_dir, self.blocked_dir]:
            for task_file in dir.glob("task_*.json"):
                match = re.match(r"task_(\d+)_", task_file.stem)
                if match:
                    task_id = int(match.group(1))
                    max_id = max(max_id, task_id)
        
        return max_id + 1
    
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
               description: str = "",
               context: Optional[List[str]] = None,
               notes: str = "") -> str:
        """Create a new task.
        
        Args:
            summary: One-line summary of the task
            description: Detailed description
            context: List of relevant file paths
            notes: Any additional notes
            
        Returns:
            Task ID of the created task
            
        Example:
            task_id = tasks.create(
                summary="Review code changes",
                description="Review the recent changes to memory system",
                context=["/personal/code_review.md"]
            )
        """
        task_id = f"task_{self._next_id:03d}"
        self._next_id += 1
        
        # Create task data
        task_data = {
            "id": task_id,
            "summary": summary[:100],  # Limit summary length
            "description": description,
            "status": "active",
            "created": datetime.now().isoformat(),
            "context": context or [],
            "notes": notes
        }
        
        # Create filename
        filename = f"{task_id}_{self._sanitize_filename(summary)}.json"
        task_file = self.active_dir / filename
        
        # Write task file
        with open(task_file, 'w') as f:
            json.dump(task_data, f, indent=2)
        
        return task_id
    
    def get_active(self) -> List[Dict[str, Any]]:
        """Get all active tasks.
        
        Returns:
            List of active task dictionaries
            
        Example:
            for task in tasks.get_active():
                print(f"{task['id']}: {task['summary']}")
        """
        return self._get_tasks_from_dir(self.active_dir)
    
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
        # Search all directories
        for dir in [self.active_dir, self.blocked_dir, self.completed_dir]:
            for task_file in dir.glob(f"{task_id}_*.json"):
                try:
                    with open(task_file, 'r') as f:
                        task_data = json.load(f)
                        task_data['_file'] = str(task_file)
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
        """Unblock a task and make it active again.
        
        Args:
            task_id: The task ID to unblock
            notes: Notes about unblocking
            
        Returns:
            True if successful, False otherwise
        """
        return self._move_task(task_id, self.active_dir,
                              updates={"status": "active",
                                     "unblocked_at": datetime.now().isoformat(),
                                     "unblock_notes": notes})
    
    def _move_task(self, task_id: str, target_dir: Path, updates: Dict[str, Any] = None) -> bool:
        """Move a task between directories and update its data."""
        # Find the task file
        task_file = None
        for dir in [self.active_dir, self.blocked_dir, self.completed_dir]:
            matches = list(dir.glob(f"{task_id}_*.json"))
            if matches:
                task_file = matches[0]
                break
        
        if not task_file:
            return False
        
        try:
            # Read task data
            with open(task_file, 'r') as f:
                task_data = json.load(f)
            
            # Apply updates
            if updates:
                task_data.update(updates)
            
            # Create new filename in target directory
            new_file = target_dir / task_file.name
            
            # Write to new location
            with open(new_file, 'w') as f:
                json.dump(task_data, f, indent=2)
            
            # Remove old file
            task_file.unlink()
            
            return True
            
        except Exception:
            return False
    
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
        
        # Remove internal field before saving
        task.pop('_file', None)
        
        try:
            with open(task_file, 'w') as f:
                json.dump(task, f, indent=2)
            return True
        except Exception:
            return False
    
    def get_summary(self) -> Dict[str, Any]:
        """Get task statistics summary.
        
        Returns:
            Dictionary with task counts and summaries
            
        Example:
            summary = tasks.get_summary()
            print(f"Active: {summary['active_count']}")
        """
        active = self.get_active()
        blocked = self.get_blocked()
        completed = self.get_completed(5)
        
        return {
            "active_count": len(active),
            "blocked_count": len(blocked),
            "completed_recent": len(completed),
            "active_summaries": [t['summary'] for t in active],
            "blocked_summaries": [t['summary'] for t in blocked]
        }