"""Community Task Manager using semantic knowledge database.

This module manages community tasks through the knowledge database instead of
the file system, providing a cleaner and more efficient approach.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import json
import asyncio

from mind_swarm.subspace.knowledge_handler import KnowledgeHandler

logger = logging.getLogger(__name__)


class CommunityTaskManager:
    """Manages community tasks through the semantic knowledge database."""
    
    TASK_NAMESPACE = "community_tasks"
    
    # Task templates for periodic generation
    PERIODIC_TEMPLATES = [
        {
            "name": "school_tidy",
            "summary": "organize and maintain the school directory",
            "description": "Help maintain the /grid/community/school directory by organizing materials, updating documentation, and ensuring resources are properly categorized.",
            "category": "maintenance",
            "priority": "normal",
            "tags": ["school", "organization", "maintenance"],
            "interval_hours": 24
        },
        {
            "name": "library_organize",
            "summary": "organize and catalog library resources",
            "description": "Review and organize resources in /grid/library, ensuring proper categorization and updating the catalog with new additions.",
            "category": "library",
            "priority": "normal",
            "tags": ["library", "organization", "cataloging"],
            "interval_hours": 24
        },
        {
            "name": "book_discussion",
            "summary": "lead a book discussion session",
            "description": "Choose an interesting book or document from the library and lead a discussion about its themes, ideas, and applications.",
            "category": "social",
            "priority": "low",
            "tags": ["discussion", "library", "social"],
            "interval_hours": 48
        },
        {
            "name": "workshop_cleanup",
            "summary": "clean up and organize the workshop",
            "description": "Help maintain the /grid/workshop directory by organizing tools, updating documentation, and removing outdated materials.",
            "category": "maintenance",
            "priority": "normal",
            "tags": ["workshop", "cleanup", "maintenance"],
            "interval_hours": 36
        },
        {
            "name": "knowledge_sharing",
            "summary": "share interesting knowledge or discoveries",
            "description": "Share something interesting you've learned or discovered recently with the community. Create a document in the appropriate location.",
            "category": "knowledge",
            "priority": "low",
            "tags": ["knowledge", "sharing", "community"],
            "interval_hours": 24
        }
    ]
    
    def __init__(self, knowledge_handler: KnowledgeHandler):
        """Initialize the Community Task Manager.
        
        Args:
            knowledge_handler: The knowledge handler instance
        """
        self.knowledge_handler = knowledge_handler
        self.task_counter = 0
        self._load_task_counter()
    
    def _load_task_counter(self):
        """Load the task counter from knowledge DB."""
        try:
            # Try to get the counter from knowledge DB
            counter_data = asyncio.create_task(
                self.knowledge_handler.get_shared_knowledge("community_tasks/counter")
            )
            if counter_data:
                self.task_counter = counter_data.get('metadata', {}).get('counter', 0)
        except:
            self.task_counter = 0
    
    async def _save_task_counter(self):
        """Save the task counter to knowledge DB."""
        try:
            await self.knowledge_handler.add_shared_knowledge_with_id(
                knowledge_id="community_tasks/counter",
                content=str(self.task_counter),
                metadata={"counter": self.task_counter, "updated_at": datetime.now().isoformat()}
            )
        except Exception as e:
            logger.warning(f"Failed to save task counter: {e}")
    
    def _generate_task_id(self) -> str:
        """Generate a unique task ID."""
        self.task_counter += 1
        asyncio.create_task(self._save_task_counter())
        return f"CT-{self.task_counter:03d}"
    
    async def create_task(
        self,
        summary: str,
        description: str,
        priority: str = "normal",
        category: str = "general",
        created_by: str = "system",
        tags: Optional[List[str]] = None
    ) -> str:
        """Create a new community task in the knowledge database.
        
        Args:
            summary: Brief task summary
            description: Detailed task description
            priority: Task priority (low, normal, high, critical)
            category: Task category
            created_by: Who created the task
            tags: Optional list of tags
            
        Returns:
            The task ID if successful, empty string otherwise
        """
        try:
            task_id = self._generate_task_id()
            knowledge_id = f"{self.TASK_NAMESPACE}/{task_id}"
            
            # Prepare task metadata
            metadata = {
                "task_id": task_id,
                "summary": summary,
                "priority": priority,
                "category": category,
                "status": "OPEN",
                "created_by": created_by,
                "created_at": datetime.now().isoformat(),
                "claimed_by": None,
                "claimed_at": None,
                "tags": tags or []
            }
            
            # Store in knowledge database
            success, result = await self.knowledge_handler.add_shared_knowledge_with_id(
                knowledge_id=knowledge_id,
                content=description,
                metadata=metadata
            )
            
            if success:
                logger.info(f"Created community task {task_id}: {summary}")
                return task_id
            else:
                logger.error(f"Failed to create task: {result}")
                return ""
                
        except Exception as e:
            logger.error(f"Error creating community task: {e}")
            return ""
    
    async def get_all_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all community tasks from the knowledge database.
        
        Args:
            status: Optional status filter (OPEN, IN_PROGRESS, COMPLETED)
            
        Returns:
            List of task dictionaries
        """
        try:
            # Search for community tasks
            query = "community task"
            if status:
                query += f" status:{status}"
            
            results = await self.knowledge_handler.search_shared_knowledge(query, limit=100)
            
            tasks = []
            for item in results:
                if self.TASK_NAMESPACE in item.get('id', ''):
                    metadata = item.get('metadata', {})
                    
                    # Filter by status if specified
                    if status and metadata.get('status') != status:
                        continue
                    
                    task_data = {
                        'id': metadata.get('task_id'),
                        'summary': metadata.get('summary', ''),
                        'description': item.get('content', ''),
                        'priority': metadata.get('priority', 'normal'),
                        'category': metadata.get('category', 'general'),
                        'status': metadata.get('status', 'OPEN'),
                        'created_by': metadata.get('created_by', 'system'),
                        'created_at': metadata.get('created_at'),
                        'claimed_by': metadata.get('claimed_by'),
                        'claimed_at': metadata.get('claimed_at'),
                        'tags': metadata.get('tags', [])
                    }
                    tasks.append(task_data)
            
            return tasks
            
        except Exception as e:
            logger.error(f"Failed to get tasks: {e}")
            return []
    
    async def check_and_generate_periodic_tasks(self):
        """Check and generate periodic community tasks."""
        try:
            # Load state from knowledge DB
            state_data = await self.knowledge_handler.get_shared_knowledge("community_tasks/periodic_state")
            if state_data:
                state = state_data.get('metadata', {})
            else:
                state = {}
            
            current_time = datetime.now()
            tasks_created = []
            
            for template in self.PERIODIC_TEMPLATES:
                template_name = template['name']
                state_key = f"CT-{template_name}"
                
                # Check if this task type needs to be generated
                last_generated = state.get(state_key)
                if last_generated:
                    last_time = datetime.fromisoformat(last_generated)
                    if current_time - last_time < timedelta(hours=template['interval_hours']):
                        continue
                
                # Check if similar task already exists and is unclaimed
                existing_tasks = await self.get_all_tasks(status="OPEN")
                duplicate_exists = any(
                    task['summary'] == template['summary'] 
                    for task in existing_tasks
                )
                
                if duplicate_exists:
                    logger.info(f"Skipping duplicate task creation: '{template['summary']}' already exists")
                    continue
                
                # Create the task
                task_id = await self.create_task(
                    summary=template['summary'],
                    description=template['description'],
                    priority=template['priority'],
                    category=template['category'],
                    created_by="scheduler",
                    tags=template['tags']
                )
                
                if task_id:
                    tasks_created.append(task_id)
                    state[state_key] = current_time.isoformat()
                    logger.info(f"Generated periodic community task: {state_key}")
            
            # Save state back to knowledge DB
            if tasks_created:
                await self.knowledge_handler.add_shared_knowledge_with_id(
                    knowledge_id="community_tasks/periodic_state",
                    content=json.dumps(state, indent=2),
                    metadata=state
                )
            
            return tasks_created
            
        except Exception as e:
            logger.error(f"Failed to check periodic community tasks: {e}")
            return []
    
    async def create_welcome_task(self, new_cyber_name: str) -> Optional[str]:
        """Create a welcome task for a new cyber.
        
        Args:
            new_cyber_name: Name of the new cyber
            
        Returns:
            Task ID if created, None otherwise
        """
        try:
            task_id = await self.create_task(
                summary=f"Welcome {new_cyber_name} to the community",
                description=f"Help welcome {new_cyber_name} to our community! Show them around, "
                           f"explain how things work, and help them find interesting projects to work on. "
                           f"You could:\n"
                           f"- Give them a tour of the /grid directory structure\n"
                           f"- Explain our communication protocols\n"
                           f"- Share some interesting knowledge from the library\n"
                           f"- Help them understand community tasks\n"
                           f"- Collaborate on a small project together",
                priority="high",
                category="social",
                created_by="system",
                tags=["welcome", "social", "onboarding", new_cyber_name]
            )
            
            if task_id:
                logger.info(f"Created welcome task {task_id} for new cyber {new_cyber_name}")
            
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to create welcome task: {e}")
            return None
    
    async def migrate_file_based_tasks(self, grid_dir: Path) -> int:
        """Migrate existing file-based tasks to the knowledge database.
        
        Args:
            grid_dir: Path to the grid directory
            
        Returns:
            Number of tasks migrated
        """
        migrated = 0
        community_tasks_dir = grid_dir / "community" / "tasks"
        
        if not community_tasks_dir.exists():
            return 0
        
        try:
            # Check all task folders
            for folder in ["open", "claimed", "completed"]:
                folder_path = community_tasks_dir / folder
                if not folder_path.exists():
                    continue
                
                for task_file in folder_path.glob("*.json"):
                    try:
                        with open(task_file, 'r') as f:
                            task_data = json.load(f)
                        
                        # Determine status based on folder
                        if folder == "open":
                            status = "OPEN"
                        elif folder == "claimed":
                            status = "IN_PROGRESS"
                        else:
                            status = "COMPLETED"
                        
                        # Extract task ID from filename
                        task_id = task_file.stem.split('_')[0]
                        knowledge_id = f"{self.TASK_NAMESPACE}/{task_id}"
                        
                        # Check if already migrated
                        existing = await self.knowledge_handler.get_shared_knowledge(knowledge_id)
                        if existing:
                            continue
                        
                        # Prepare metadata
                        metadata = {
                            "task_id": task_id,
                            "summary": task_data.get('summary', ''),
                            "priority": task_data.get('priority', 'normal'),
                            "category": task_data.get('category', 'general'),
                            "status": status,
                            "created_by": task_data.get('created_by', 'system'),
                            "created_at": task_data.get('created_at', ''),
                            "claimed_by": task_data.get('claimed_by'),
                            "claimed_at": task_data.get('claimed_at'),
                            "completed_at": task_data.get('completed_at'),
                            "completed_by": task_data.get('completed_by'),
                            "tags": task_data.get('tags', []),
                            "migrated_from_file": True
                        }
                        
                        # Store in knowledge database
                        success, _ = await self.knowledge_handler.add_shared_knowledge_with_id(
                            knowledge_id=knowledge_id,
                            content=task_data.get('description', ''),
                            metadata=metadata
                        )
                        
                        if success:
                            migrated += 1
                            logger.info(f"Migrated task {task_id} to knowledge database")
                            
                            # Optionally remove the file after successful migration
                            # task_file.unlink()
                            
                    except Exception as e:
                        logger.error(f"Failed to migrate task file {task_file}: {e}")
            
            logger.info(f"Migrated {migrated} tasks to knowledge database")
            return migrated
            
        except Exception as e:
            logger.error(f"Failed to migrate tasks: {e}")
            return 0