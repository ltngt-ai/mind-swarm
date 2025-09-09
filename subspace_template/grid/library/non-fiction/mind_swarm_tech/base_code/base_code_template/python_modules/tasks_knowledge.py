"""
# Tasks Knowledge API for Cybers

## Core Concept: Semantic Task Management
The Tasks Knowledge API provides semantic storage and retrieval for tasks,
replacing file-based task storage with a knowledge database approach.

Tasks are stored with rich metadata enabling semantic search, task relationships,
and cross-cyber collaboration on community tasks.

## Examples

### Intention: "Create a new task in knowledge"
```python
task_id = tasks_knowledge.create_task(
    summary="Optimize memory compression algorithm",
    description="Current compression is slow, need to improve performance",
    task_type="maintenance",
    todo_list=[
        {"title": "Profile current implementation", "status": "NOT-STARTED"},
        {"title": "Research better algorithms", "status": "NOT-STARTED"}
    ]
)
print(f"Created task: {task_id}")
```

### Intention: "Search for related tasks"
```python
similar_tasks = tasks_knowledge.search_tasks(
    query="memory optimization compression",
    task_type="maintenance"
)
for task in similar_tasks:
    print(f"{task['task_id']}: {task['summary']}")
```

### Intention: "Get all community tasks"
```python
community_tasks = tasks_knowledge.get_community_tasks()
for task in community_tasks:
    if not task.get('claimed_by'):
        print(f"Available: {task['summary']}")
```

### Intention: "Update task progress"
```python
tasks_knowledge.update_task_progress(
    task_id="MT-001",
    todo_index=0,
    status="DONE",
    notes="Profiling complete, found bottleneck in hash function"
)
```

## Best Practices
1. Use semantic descriptions for better task discovery
2. Include context references for task history
3. Tag tasks appropriately for cross-cyber collaboration
4. Update progress regularly for transparency
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger("Cyber.tasks_knowledge")


class TasksKnowledgeError(Exception):
    """Base exception for task knowledge errors."""
    pass


class TasksKnowledge:
    """Manages task storage and retrieval using the knowledge database."""
    
    TASK_TYPES = ["maintenance", "hobby", "community"]
    TODO_STATUSES = ["NOT-STARTED", "IN-PROGRESS", "DONE", "BLOCKED"]
    
    def __init__(self, context_or_knowledge):
        """Initialize the Tasks Knowledge API.
        
        Args:
            context_or_knowledge: Either execution context dict or Knowledge API instance
        """
        if isinstance(context_or_knowledge, dict):
            # Initialize from context
            self.context = context_or_knowledge
            self.cyber_id = context_or_knowledge.get('cyber_id', 'unknown')
            
            # Get Knowledge API from context
            from .knowledge import Knowledge
            memory_api = context_or_knowledge.get('memory_api')
            if not memory_api:
                raise TasksKnowledgeError("Memory API required in context")
            self.knowledge = Knowledge(memory_api)
        else:
            # Direct Knowledge API instance
            self.knowledge = context_or_knowledge
            self.cyber_id = 'unknown'
    
    def create_task(self,
                   summary: str,
                   description: str = "",
                   task_type: str = "maintenance",
                   todo_list: List[Dict[str, Any]] = None,
                   context: List[str] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a new task in the knowledge database.
        
        Args:
            summary: Brief task summary (one line)
            description: Detailed task description
            task_type: Type of task (maintenance, hobby, community)
            todo_list: List of todo items with title and status
            context: List of related file paths or references
            metadata: Additional metadata
            
        Returns:
            Task ID of created task
            
        Example:
            task_id = tasks_knowledge.create_task(
                summary="Fix memory leak in scanner",
                description="Scanner is not releasing old observations",
                task_type="maintenance",
                todo_list=[
                    {"title": "Identify leak source", "status": "NOT-STARTED"},
                    {"title": "Implement fix", "status": "NOT-STARTED"}
                ]
            )
        """
        if task_type not in self.TASK_TYPES:
            raise TasksKnowledgeError(f"Invalid task type: {task_type}")
        
        # Generate task ID based on type
        type_prefix = task_type[0].upper() + "T"  # MT, HT, or CT
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        task_id = f"{type_prefix}-{timestamp}-{uuid.uuid4().hex[:6]}"
        
        # Create semantic content
        semantic_content = f"""
Task: {summary}
Type: {task_type.capitalize()}
Status: ACTIVE
Created: {datetime.now().isoformat()}

Description:
{description}

Todo List:
"""
        if todo_list:
            for i, todo in enumerate(todo_list):
                status = todo.get('status', 'NOT-STARTED')
                semantic_content += f"{i+1}. [{status}] {todo.get('title', 'Untitled')}\n"
        
        if context:
            semantic_content += f"\nContext References:\n"
            for ref in context:
                semantic_content += f"- {ref}\n"
        
        # Prepare metadata
        task_metadata = {
            "task_id": task_id,
            "task_type": task_type,
            "summary": summary,
            "description": description,
            "status": "ACTIVE",
            "created_by": self.cyber_id,
            "created_at": datetime.now().isoformat(),
            "todo_list": todo_list or [],
            "context": context or [],
            "completed_at": None,
            "blocked_reason": None,
            "notes": []
        }
        
        if metadata:
            task_metadata.update(metadata)
        
        # Store in knowledge with hierarchical ID
        knowledge_id = f"tasks/{self.cyber_id}/{task_id}"
        
        # Community tasks are shared, others are personal
        personal = (task_type != "community")
        
        stored_id = self.knowledge.store(
            content=semantic_content,
            knowledge_id=knowledge_id,
            tags=["task", task_type, f"cyber_{self.cyber_id}", "active"],
            personal=personal,
            metadata=task_metadata
        )
        
        logger.info(f"Created task {task_id} as knowledge {stored_id}")
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific task by ID.
        
        Args:
            task_id: The task ID to retrieve
            
        Returns:
            Task data or None if not found
            
        Example:
            task = tasks_knowledge.get_task("MT-001")
            if task:
                print(f"Task: {task['summary']}")
                for todo in task['todo_list']:
                    print(f"  - [{todo['status']}] {todo['title']}")
        """
        # Try direct lookup first
        knowledge_id = f"tasks/{self.cyber_id}/{task_id}"
        result = self.knowledge.get(knowledge_id)
        
        if not result:
            # Try searching for it (might be community task)
            results = self.search_tasks(query=task_id, limit=1)
            if results:
                return results[0]
            return None
        
        # Extract task data from knowledge
        metadata = result.get('metadata', {})
        return {
            'task_id': metadata.get('task_id', task_id),
            'task_type': metadata.get('task_type'),
            'summary': metadata.get('summary'),
            'description': metadata.get('description'),
            'status': metadata.get('status'),
            'created_by': metadata.get('created_by'),
            'created_at': metadata.get('created_at'),
            'todo_list': metadata.get('todo_list', []),
            'context': metadata.get('context', []),
            'notes': metadata.get('notes', [])
        }
    
    def search_tasks(self,
                    query: str = "",
                    task_type: Optional[str] = None,
                    status: Optional[str] = None,
                    limit: int = 10) -> List[Dict[str, Any]]:
        """Search for tasks using semantic search.
        
        Args:
            query: Search query (semantic search)
            task_type: Filter by task type
            status: Filter by status (ACTIVE, COMPLETED, BLOCKED)
            limit: Maximum number of results
            
        Returns:
            List of matching tasks
            
        Example:
            maintenance_tasks = tasks_knowledge.search_tasks(
                query="memory",
                task_type="maintenance",
                status="ACTIVE"
            )
        """
        # Build search tags
        tags = ["task"]
        if task_type:
            tags.append(task_type)
        if status:
            tags.append(status.lower())
        
        # Search in knowledge
        results = self.knowledge.search(
            query=query,
            tags=tags,
            limit=limit
        )
        
        # Extract task data
        tasks = []
        for result in results:
            metadata = result.get('metadata', {})
            tasks.append({
                'task_id': metadata.get('task_id'),
                'task_type': metadata.get('task_type'),
                'summary': metadata.get('summary'),
                'description': metadata.get('description'),
                'status': metadata.get('status'),
                'created_by': metadata.get('created_by'),
                'created_at': metadata.get('created_at'),
                'todo_list': metadata.get('todo_list', []),
                'score': result.get('score', 0)
            })
        
        return tasks
    
    def get_current_task(self) -> Optional[Dict[str, Any]]:
        """Get the current active task for this cyber.
        
        Returns:
            Current task data or None if no current task
            
        Example:
            current = tasks_knowledge.get_current_task()
            if current:
                print(f"Working on: {current['summary']}")
        """
        # Search for tasks created by this cyber with CURRENT tag
        results = self.knowledge.search(
            query="",
            tags=["task", f"cyber_{self.cyber_id}", "current"],
            limit=1
        )
        
        if results:
            metadata = results[0].get('metadata', {})
            return {
                'task_id': metadata.get('task_id'),
                'task_type': metadata.get('task_type'),
                'summary': metadata.get('summary'),
                'description': metadata.get('description'),
                'todo_list': metadata.get('todo_list', []),
                'context': metadata.get('context', [])
            }
        
        return None
    
    def set_current_task(self, task_id: str) -> bool:
        """Set a task as the current active task.
        
        Args:
            task_id: Task ID to set as current
            
        Returns:
            True if successfully set
            
        Example:
            if tasks_knowledge.set_current_task("MT-001"):
                print("Task set as current")
        """
        # First, remove "current" tag from any existing current task
        current = self.get_current_task()
        if current and current['task_id'] != task_id:
            self._update_task_tags(current['task_id'], remove_tags=["current"])
        
        # Add "current" tag to the new task
        return self._update_task_tags(task_id, add_tags=["current"])
    
    def update_task_progress(self,
                            task_id: str,
                            todo_index: int = None,
                            status: str = None,
                            notes: str = None) -> bool:
        """Update progress on a task.
        
        Args:
            task_id: Task ID to update
            todo_index: Index of todo item to update (optional)
            status: New status for todo item
            notes: Additional notes to add
            
        Returns:
            True if successfully updated
            
        Example:
            tasks_knowledge.update_task_progress(
                task_id="MT-001",
                todo_index=0,
                status="DONE",
                notes="Fixed the memory leak"
            )
        """
        task = self.get_task(task_id)
        if not task:
            return False
        
        knowledge_id = f"tasks/{self.cyber_id}/{task_id}"
        
        # Update todo item if specified
        if todo_index is not None and status:
            if 0 <= todo_index < len(task['todo_list']):
                task['todo_list'][todo_index]['status'] = status
                task['todo_list'][todo_index]['updated_at'] = datetime.now().isoformat()
        
        # Add notes if provided
        if notes:
            task_notes = task.get('notes', [])
            task_notes.append({
                'timestamp': datetime.now().isoformat(),
                'note': notes
            })
            task['notes'] = task_notes
        
        # Rebuild semantic content
        semantic_content = f"""
Task: {task['summary']}
Type: {task['task_type'].capitalize()}
Status: {task['status']}
Created: {task['created_at']}

Description:
{task['description']}

Todo List:
"""
        for i, todo in enumerate(task['todo_list']):
            semantic_content += f"{i+1}. [{todo.get('status', 'NOT-STARTED')}] {todo.get('title', 'Untitled')}\n"
        
        if task.get('notes'):
            semantic_content += "\nNotes:\n"
            for note in task['notes']:
                semantic_content += f"- {note['timestamp']}: {note['note']}\n"
        
        # Update in knowledge
        return self.knowledge.update(
            knowledge_id=knowledge_id,
            content=semantic_content,
            metadata=task
        )
    
    def complete_task(self, task_id: str, notes: str = "") -> bool:
        """Mark a task as completed.
        
        Args:
            task_id: Task ID to complete
            notes: Completion notes
            
        Returns:
            True if successfully completed
            
        Example:
            tasks_knowledge.complete_task(
                "MT-001",
                notes="Memory leak fixed, performance improved by 30%"
            )
        """
        task = self.get_task(task_id)
        if not task:
            return False
        
        task['status'] = "COMPLETED"
        task['completed_at'] = datetime.now().isoformat()
        
        if notes:
            task_notes = task.get('notes', [])
            task_notes.append({
                'timestamp': datetime.now().isoformat(),
                'note': f"COMPLETED: {notes}"
            })
            task['notes'] = task_notes
        
        # Update tags
        self._update_task_tags(task_id, 
                              remove_tags=["active", "current", "blocked"],
                              add_tags=["completed"])
        
        # Update task data
        knowledge_id = f"tasks/{self.cyber_id}/{task_id}"
        return self.knowledge.update(
            knowledge_id=knowledge_id,
            content=self._build_task_content(task),
            metadata=task
        )
    
    def get_community_tasks(self, include_claimed: bool = False) -> List[Dict[str, Any]]:
        """Get all community tasks.
        
        Args:
            include_claimed: Include tasks already claimed by others
            
        Returns:
            List of community tasks
            
        Example:
            available_tasks = tasks_knowledge.get_community_tasks()
            for task in available_tasks:
                if not task.get('claimed_by'):
                    print(f"Available: {task['summary']}")
        """
        # Search for community tasks
        tasks = self.search_tasks(task_type="community", status="ACTIVE", limit=50)
        
        if not include_claimed:
            # Filter out claimed tasks
            tasks = [t for t in tasks if not t.get('claimed_by')]
        
        return tasks
    
    def claim_community_task(self, task_id: str) -> bool:
        """Claim a community task.
        
        Args:
            task_id: Community task ID to claim
            
        Returns:
            True if successfully claimed
            
        Example:
            if tasks_knowledge.claim_community_task("CT-001"):
                print("Task claimed successfully")
        """
        task = self.get_task(task_id)
        if not task or task['task_type'] != 'community':
            return False
        
        if task.get('claimed_by'):
            logger.warning(f"Task {task_id} already claimed by {task['claimed_by']}")
            return False
        
        task['claimed_by'] = self.cyber_id
        task['claimed_at'] = datetime.now().isoformat()
        
        # Update in knowledge
        knowledge_id = f"tasks/community/{task_id}"
        return self.knowledge.update(
            knowledge_id=knowledge_id,
            content=self._build_task_content(task),
            metadata=task
        )
    
    def _update_task_tags(self, 
                         task_id: str,
                         add_tags: List[str] = None,
                         remove_tags: List[str] = None) -> bool:
        """Update tags for a task.
        
        Args:
            task_id: Task ID to update
            add_tags: Tags to add
            remove_tags: Tags to remove
            
        Returns:
            True if successfully updated
        """
        knowledge_id = f"tasks/{self.cyber_id}/{task_id}"
        result = self.knowledge.get(knowledge_id)
        
        if not result:
            return False
        
        current_tags = result.get('tags', [])
        
        # Remove tags
        if remove_tags:
            current_tags = [t for t in current_tags if t not in remove_tags]
        
        # Add tags
        if add_tags:
            for tag in add_tags:
                if tag not in current_tags:
                    current_tags.append(tag)
        
        # Update with new tags
        return self.knowledge.update(
            knowledge_id=knowledge_id,
            content=result.get('content', ''),
            metadata=result.get('metadata', {}),
            tags=current_tags
        )
    
    def _build_task_content(self, task: Dict[str, Any]) -> str:
        """Build semantic content for a task.
        
        Args:
            task: Task data dictionary
            
        Returns:
            Formatted semantic content string
        """
        content = f"""
Task: {task['summary']}
Type: {task.get('task_type', 'unknown').capitalize()}
Status: {task.get('status', 'ACTIVE')}
Created: {task.get('created_at', 'unknown')}
"""
        
        if task.get('claimed_by'):
            content += f"Claimed by: {task['claimed_by']}\n"
        
        if task.get('description'):
            content += f"\nDescription:\n{task['description']}\n"
        
        if task.get('todo_list'):
            content += "\nTodo List:\n"
            for i, todo in enumerate(task['todo_list']):
                status = todo.get('status', 'NOT-STARTED')
                content += f"{i+1}. [{status}] {todo.get('title', 'Untitled')}\n"
        
        if task.get('notes'):
            content += "\nNotes:\n"
            for note in task['notes']:
                content += f"- {note.get('timestamp', '')}: {note.get('note', '')}\n"
        
        return content