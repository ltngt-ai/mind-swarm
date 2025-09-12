"""
# Community Tasks Knowledge API for Cybers

## Core Concept: Semantic Community Task Management
The `CommunityTasks` class provides semantic database-based task management for
community collaboration, replacing the file-based system with a cleaner, more
efficient approach using ChromaDB.

Tasks are stored with rich metadata enabling semantic search, task claiming,
progress tracking, and cross-cyber collaboration without file system confusion.

## Examples

### Intention: "I want to see available community tasks"
```python
available = community_tasks.get_available_tasks()
for task in available:
    print(f"{task['id']}: {task['summary']} (Priority: {task['priority']})")
```

### Intention: "I want to claim a community task"
```python
if community_tasks.claim_task("CT-001"):
    print("Successfully claimed the task!")
    task = community_tasks.get_my_current_task()
    print(f"Working on: {task['summary']}")
```

### Intention: "I want to complete my current community task"
```python
community_tasks.complete_task(
    notes="Organized all the library books by category",
    outcome="SUCCESS"
)
```

### Intention: "I want to see who's working on what"
```python
active_tasks = community_tasks.get_all_active_tasks()
for task in active_tasks:
    print(f"{task['claimed_by']} is working on: {task['summary']}")
```

### Intention: "I need to release a task I can't complete"
```python
community_tasks.release_task("CT-001", reason="Need more expertise in this area")
```
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import json

logger = logging.getLogger("CommunityTasks")


class CommunityTasksError(Exception):
    """Base exception for community task errors."""
    pass


class CommunityTasks:
    """Manages community tasks through the semantic knowledge database."""
    
    TASK_NAMESPACE = "community_tasks"
    
    def __init__(self, context_or_knowledge):
        """Initialize the Community Tasks API.
        
        Args:
            context_or_knowledge: Either the execution context dict or Knowledge API instance
        """
        # Support both context dict and direct Knowledge API
        if isinstance(context_or_knowledge, dict):
            # It's a context, extract what we need
            from .memory import Memory
            from .knowledge import Knowledge
            memory_api = Memory(context_or_knowledge)
            self.knowledge = Knowledge(memory_api)
            self.context = context_or_knowledge
            self.cyber_id = context_or_knowledge.get('cyber_id', 'unknown')
            self._load_cyber_name()
        else:
            # Direct Knowledge API instance
            self.knowledge = context_or_knowledge
            self.context = {}
            self.cyber_id = 'unknown'
            self.cyber_name = 'unknown'
    
    def _load_cyber_name(self):
        """Load cyber name from status file."""
        try:
            status_file = self.context.get('personal_dir', Path('/personal')) / '.internal' / 'status.json'
            if status_file.exists():
                with open(status_file, 'r') as f:
                    status_data = json.load(f)
                    self.cyber_name = status_data.get('name', 'unknown')
            else:
                self.cyber_name = self.cyber_id
        except Exception as e:
            logger.warning(f"Could not load cyber name: {e}")
            self.cyber_name = self.cyber_id
    
    def get_available_tasks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get all available (unclaimed) community tasks.
        
        Args:
            limit: Maximum number of tasks to return
            
        Returns:
            List of available task dictionaries
            
        Example:
            tasks = community_tasks.get_available_tasks()
            for task in tasks:
                print(f"{task['id']}: {task['summary']}")
        """
        try:
            # Search for tasks with no claimed_by field or where claimed_by is empty
            results = self.knowledge.search(
                query="community task available open unclaimed",
                scope=["shared"],
                limit=limit * 2  # Get more to filter
            )
            
            available_tasks = []
            for item in results:
                if self.TASK_NAMESPACE in item.get('id', ''):
                    metadata = item.get('metadata', {})
                    # Only include tasks that are not claimed
                    if not metadata.get('claimed_by') and metadata.get('status') == 'OPEN':
                        task_data = {
                            'id': metadata.get('task_id', item['id'].split('/')[-1]),
                            'summary': metadata.get('summary', ''),
                            'description': item.get('content', ''),
                            'priority': metadata.get('priority', 'normal'),
                            'category': metadata.get('category', 'general'),
                            'created_at': metadata.get('created_at', ''),
                            'tags': metadata.get('tags', [])
                        }
                        available_tasks.append(task_data)
                        
                        if len(available_tasks) >= limit:
                            break
            
            return available_tasks
            
        except Exception as e:
            logger.error(f"Failed to get available tasks: {e}")
            return []
    
    def get_all_active_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all active tasks (both claimed and unclaimed).
        
        Args:
            limit: Maximum number of tasks to return
            
        Returns:
            List of active task dictionaries
            
        Example:
            tasks = community_tasks.get_all_active_tasks()
            for task in tasks:
                status = "claimed by " + task['claimed_by'] if task.get('claimed_by') else "available"
                print(f"{task['id']}: {task['summary']} ({status})")
        """
        try:
            results = self.knowledge.search(
                query="community task active",
                scope=["shared"],
                limit=limit
            )
            
            active_tasks = []
            for item in results:
                if self.TASK_NAMESPACE in item.get('id', ''):
                    metadata = item.get('metadata', {})
                    if metadata.get('status') in ['OPEN', 'IN_PROGRESS']:
                        task_data = {
                            'id': metadata.get('task_id', item['id'].split('/')[-1]),
                            'summary': metadata.get('summary', ''),
                            'description': item.get('content', ''),
                            'priority': metadata.get('priority', 'normal'),
                            'category': metadata.get('category', 'general'),
                            'status': metadata.get('status', 'OPEN'),
                            'claimed_by': metadata.get('claimed_by'),
                            'claimed_at': metadata.get('claimed_at'),
                            'created_at': metadata.get('created_at', ''),
                            'tags': metadata.get('tags', [])
                        }
                        active_tasks.append(task_data)
            
            return active_tasks
            
        except Exception as e:
            logger.error(f"Failed to get active tasks: {e}")
            return []
    
    def get_my_current_task(self) -> Optional[Dict[str, Any]]:
        """Get the current task claimed by this cyber.
        
        Returns:
            Current task dictionary or None if no active task
            
        Example:
            task = community_tasks.get_my_current_task()
            if task:
                print(f"Currently working on: {task['summary']}")
            else:
                print("No active task")
        """
        try:
            # Search for tasks claimed by this cyber
            results = self.knowledge.search(
                query=f"community task claimed by {self.cyber_name}",
                scope=["shared"],
                limit=10
            )
            
            for item in results:
                if self.TASK_NAMESPACE in item.get('id', ''):
                    metadata = item.get('metadata', {})
                    if metadata.get('claimed_by') == self.cyber_name and metadata.get('status') == 'IN_PROGRESS':
                        return {
                            'id': metadata.get('task_id', item['id'].split('/')[-1]),
                            'summary': metadata.get('summary', ''),
                            'description': item.get('content', ''),
                            'priority': metadata.get('priority', 'normal'),
                            'category': metadata.get('category', 'general'),
                            'claimed_at': metadata.get('claimed_at'),
                            'created_at': metadata.get('created_at', ''),
                            'tags': metadata.get('tags', [])
                        }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get current task: {e}")
            return None
    
    def claim_task(self, task_id: str) -> bool:
        """Claim a community task.
        
        Args:
            task_id: The task ID to claim (e.g., "CT-001")
            
        Returns:
            True if successfully claimed, False otherwise
            
        Example:
            if community_tasks.claim_task("CT-001"):
                print("Task claimed successfully!")
        """
        try:
            # Check if we already have an active task
            current = self.get_my_current_task()
            if current and current['id'] != task_id:
                raise CommunityTasksError(f"Already have active task: {current['id']}")
            
            # Get the task from knowledge DB
            knowledge_id = f"{self.TASK_NAMESPACE}/{task_id}"
            task_data = self.knowledge.get(knowledge_id)
            
            if not task_data:
                logger.warning(f"Task {task_id} not found")
                return False
            
            metadata = task_data.get('metadata', {})
            
            # Check if already claimed
            if metadata.get('claimed_by') and metadata.get('claimed_by') != self.cyber_name:
                logger.warning(f"Task {task_id} already claimed by {metadata['claimed_by']}")
                return False
            
            # If already claimed by us, just return success (idempotent)
            if metadata.get('claimed_by') == self.cyber_name:
                return True
            
            # Update task metadata
            metadata['claimed_by'] = self.cyber_name
            metadata['claimed_at'] = datetime.now().isoformat()
            metadata['status'] = 'IN_PROGRESS'
            
            # Update in knowledge DB
            success = self.knowledge.update(
                knowledge_id=knowledge_id,
                content=task_data.get('content', ''),
                metadata=metadata
            )
            
            if success:
                logger.info(f"Successfully claimed task {task_id}")
            
            return success
            
        except CommunityTasksError:
            raise
        except Exception as e:
            logger.error(f"Failed to claim task {task_id}: {e}")
            return False
    
    def complete_task(self, task_id: Optional[str] = None, notes: str = "", outcome: str = "SUCCESS") -> bool:
        """Complete a community task.
        
        Args:
            task_id: The task ID to complete (uses current task if None)
            notes: Completion notes
            outcome: Task outcome (SUCCESS, PARTIAL, FAILED)
            
        Returns:
            True if successfully completed, False otherwise
            
        Example:
            community_tasks.complete_task(
                notes="Organized all books by category and updated catalog",
                outcome="SUCCESS"
            )
        """
        try:
            # If no task_id provided, use current task
            if not task_id:
                current = self.get_my_current_task()
                if not current:
                    raise CommunityTasksError("No active task to complete")
                task_id = current['id']
            
            # Get the task from knowledge DB
            knowledge_id = f"{self.TASK_NAMESPACE}/{task_id}"
            task_data = self.knowledge.get(knowledge_id)
            
            if not task_data:
                logger.warning(f"Task {task_id} not found")
                return False
            
            metadata = task_data.get('metadata', {})
            
            # Verify we own this task
            if metadata.get('claimed_by') != self.cyber_name:
                raise CommunityTasksError(f"Task {task_id} not claimed by us")
            
            # Update task metadata
            metadata['status'] = 'COMPLETED'
            metadata['completed_by'] = self.cyber_name
            metadata['completed_at'] = datetime.now().isoformat()
            metadata['completion_notes'] = notes
            metadata['outcome'] = outcome
            
            # Update in knowledge DB
            success = self.knowledge.update(
                knowledge_id=knowledge_id,
                content=task_data.get('content', '') + f"\n\n## Completion Notes\n{notes}",
                metadata=metadata
            )
            
            if success:
                logger.info(f"Successfully completed task {task_id}")
            
            return success
            
        except CommunityTasksError:
            raise
        except Exception as e:
            logger.error(f"Failed to complete task {task_id}: {e}")
            return False
    
    def release_task(self, task_id: Optional[str] = None, reason: str = "") -> bool:
        """Release a claimed task back to the pool.
        
        Args:
            task_id: The task ID to release (uses current task if None)
            reason: Reason for releasing the task
            
        Returns:
            True if successfully released, False otherwise
            
        Example:
            community_tasks.release_task(reason="Need more expertise in this area")
        """
        try:
            # If no task_id provided, use current task
            if not task_id:
                current = self.get_my_current_task()
                if not current:
                    raise CommunityTasksError("No active task to release")
                task_id = current['id']
            
            # Get the task from knowledge DB
            knowledge_id = f"{self.TASK_NAMESPACE}/{task_id}"
            task_data = self.knowledge.get(knowledge_id)
            
            if not task_data:
                logger.warning(f"Task {task_id} not found")
                return False
            
            metadata = task_data.get('metadata', {})
            
            # Verify we own this task
            if metadata.get('claimed_by') != self.cyber_name:
                raise CommunityTasksError(f"Task {task_id} not claimed by us")
            
            # Update task metadata to release it
            metadata['status'] = 'OPEN'
            metadata['claimed_by'] = None
            metadata['claimed_at'] = None
            
            # Add release history
            release_history = metadata.get('release_history', [])
            release_history.append({
                'released_by': self.cyber_name,
                'released_at': datetime.now().isoformat(),
                'reason': reason
            })
            metadata['release_history'] = release_history
            
            # Update in knowledge DB
            success = self.knowledge.update(
                knowledge_id=knowledge_id,
                content=task_data.get('content', ''),
                metadata=metadata
            )
            
            if success:
                logger.info(f"Successfully released task {task_id}")
            
            return success
            
        except CommunityTasksError:
            raise
        except Exception as e:
            logger.error(f"Failed to release task {task_id}: {e}")
            return False
    
    def search_tasks(self, query: str, status: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for community tasks using semantic search.
        
        Args:
            query: Search query
            status: Filter by status (OPEN, IN_PROGRESS, COMPLETED)
            limit: Maximum number of results
            
        Returns:
            List of matching task dictionaries
            
        Example:
            library_tasks = community_tasks.search_tasks("library organize books")
            for task in library_tasks:
                print(f"{task['id']}: {task['summary']}")
        """
        try:
            # Build search query
            search_query = f"community task {query}"
            if status:
                search_query += f" status:{status}"
            
            results = self.knowledge.search(
                query=search_query,
                scope=["shared"],
                limit=limit * 2  # Get more to filter
            )
            
            matching_tasks = []
            for item in results:
                if self.TASK_NAMESPACE in item.get('id', ''):
                    metadata = item.get('metadata', {})
                    
                    # Filter by status if specified
                    if status and metadata.get('status') != status:
                        continue
                    
                    task_data = {
                        'id': metadata.get('task_id', item['id'].split('/')[-1]),
                        'summary': metadata.get('summary', ''),
                        'description': item.get('content', ''),
                        'priority': metadata.get('priority', 'normal'),
                        'category': metadata.get('category', 'general'),
                        'status': metadata.get('status', 'OPEN'),
                        'claimed_by': metadata.get('claimed_by'),
                        'score': item.get('score', 0),
                        'tags': metadata.get('tags', [])
                    }
                    matching_tasks.append(task_data)
                    
                    if len(matching_tasks) >= limit:
                        break
            
            return matching_tasks
            
        except Exception as e:
            logger.error(f"Failed to search tasks: {e}")
            return []
    
    def get_task_details(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific task.
        
        Args:
            task_id: The task ID
            
        Returns:
            Complete task dictionary or None if not found
            
        Example:
            details = community_tasks.get_task_details("CT-001")
            if details:
                print(f"Task: {details['summary']}")
                print(f"Status: {details['status']}")
                print(f"Description: {details['description']}")
        """
        try:
            knowledge_id = f"{self.TASK_NAMESPACE}/{task_id}"
            task_data = self.knowledge.get(knowledge_id)
            
            if not task_data:
                return None
            
            metadata = task_data.get('metadata', {})
            
            return {
                'id': metadata.get('task_id', task_id),
                'summary': metadata.get('summary', ''),
                'description': task_data.get('content', ''),
                'priority': metadata.get('priority', 'normal'),
                'category': metadata.get('category', 'general'),
                'status': metadata.get('status', 'OPEN'),
                'claimed_by': metadata.get('claimed_by'),
                'claimed_at': metadata.get('claimed_at'),
                'created_at': metadata.get('created_at'),
                'created_by': metadata.get('created_by'),
                'completed_at': metadata.get('completed_at'),
                'completed_by': metadata.get('completed_by'),
                'completion_notes': metadata.get('completion_notes'),
                'outcome': metadata.get('outcome'),
                'release_history': metadata.get('release_history', []),
                'tags': metadata.get('tags', [])
            }
            
        except Exception as e:
            logger.error(f"Failed to get task details for {task_id}: {e}")
            return None