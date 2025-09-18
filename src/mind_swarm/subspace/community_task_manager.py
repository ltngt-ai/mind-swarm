"""Community Task Manager using semantic knowledge database.

This module manages community tasks through the knowledge database instead of
the file system, providing a cleaner and more efficient approach.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import json
import asyncio

from mind_swarm.subspace.knowledge_handler import KnowledgeHandler

logger = logging.getLogger(__name__)


@dataclass
class TaskTemplate:
    """Represents a community task template loaded from disk."""

    name: str
    summary: str
    description: str
    priority: str
    category: str
    metadata: Dict[str, Any]


class CommunityTaskManager:
    """Manages community tasks through the semantic knowledge database."""

    TASK_NAMESPACE = "community_tasks"
    TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "subspace_template" / "community_task_templates"
    DEFAULT_INTERVAL_HOURS = 24
    ESTIMATED_CYCLE_DURATION_SECONDS = 300  # Approximate 5 minutes per generation check

    def __init__(self, knowledge_handler: KnowledgeHandler):
        """Initialize the Community Task Manager.

        Args:
            knowledge_handler: The knowledge handler instance
        """
        self.knowledge_handler = knowledge_handler
        self.task_counter = 0
        self.templates: Dict[str, TaskTemplate] = {}
        self._load_task_counter()
        self._load_templates()

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

    def _load_templates(self):
        """Load community task templates from disk."""
        if not self.TEMPLATE_DIR.exists():
            logger.warning(f"Community task template directory missing: {self.TEMPLATE_DIR}")
            return

        for template_file in self.TEMPLATE_DIR.glob("*.json"):
            try:
                with open(template_file, "r") as f:
                    data = json.load(f)

                metadata = data.get("metadata") or {}
                template = TaskTemplate(
                    name=template_file.stem,
                    summary=data.get("summary", template_file.stem.replace('_', ' ')),
                    description=data.get("description", ""),
                    priority=data.get("priority", "normal"),
                    category=metadata.get("category", data.get("task_type", "general")),
                    metadata=metadata,
                )
                self.templates[template.name] = template
                logger.debug(f"Loaded community task template: {template.name}")
            except Exception as exc:
                logger.error(f"Failed to load community task template {template_file}: {exc}")

    def _get_template_interval_seconds(self, template: TaskTemplate) -> int:
        """Determine how often a template should be generated."""
        metadata = template.metadata or {}

        # Direct seconds definition takes precedence
        if "frequency_seconds" in metadata:
            return max(int(metadata["frequency_seconds"]), 1)

        if "frequency_minutes" in metadata:
            return max(int(metadata["frequency_minutes"] * 60), 1)

        if "frequency_hours" in metadata:
            return max(int(metadata["frequency_hours"] * 3600), 1)

        if "frequency_cycles" in metadata:
            cycles = max(int(metadata["frequency_cycles"]), 1)
            return cycles * self.ESTIMATED_CYCLE_DURATION_SECONDS

        # Default interval
        return int(self.DEFAULT_INTERVAL_HOURS * 3600)

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
        tags: Optional[List[str]] = None,
        extra_metadata: Optional[Dict[str, Any]] = None
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

            if extra_metadata:
                metadata.update(extra_metadata)

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
    
    async def create_task_from_template(
        self, template_name: str, *, created_by: str = "scheduler", overrides: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Create a task instance from a stored template."""
        template = self.templates.get(template_name)
        if not template:
            logger.error(f"Community task template not found: {template_name}")
            return None

        overrides = overrides or {}
        summary = overrides.get("summary", template.summary)
        description = overrides.get("description", template.description)
        priority = overrides.get("priority", template.priority)
        category = overrides.get("category", template.category)

        extra_metadata = dict(template.metadata)
        extra_metadata.update(overrides.get("metadata", {}))
        extra_metadata["template_name"] = template.name
        extra_metadata.setdefault("auto_generated", template.metadata.get("auto_generated", False))

        template_tags = template.metadata.get("tags")
        if isinstance(template_tags, list):
            tags = template_tags.copy()
        elif template_tags:
            tags = [str(template_tags)]
        else:
            tags = []

        override_tags = overrides.get("tags")
        if override_tags is not None:
            tags = override_tags

        return await self.create_task(
            summary=summary,
            description=description,
            priority=priority,
            category=category,
            created_by=created_by,
            tags=tags,
            extra_metadata=extra_metadata,
        )

    async def check_and_generate_periodic_tasks(self):
        """Check and generate periodic community tasks."""
        if not self.knowledge_handler.enabled:
            logger.debug("Knowledge handler disabled; skipping periodic community task generation")
            return []

        try:
            # Load state from knowledge DB
            state_data = await self.knowledge_handler.get_shared_knowledge("community_tasks/periodic_state")
            if state_data:
                state = state_data.get('metadata', {})
            else:
                state = {}

            current_time = datetime.now()
            tasks_created = []

            open_tasks = await self.get_all_tasks(status="OPEN")

            for template in self.templates.values():
                template_trigger = template.metadata.get("trigger")
                if template.metadata.get("auto_generated") and template_trigger == "periodic":
                    state_key = f"template::{template.name}"

                    last_generated = state.get(state_key)
                    if last_generated:
                        last_time = datetime.fromisoformat(last_generated)
                        interval_seconds = self._get_template_interval_seconds(template)
                        if (current_time - last_time) < timedelta(seconds=interval_seconds):
                            continue

                    # Prevent duplicates by checking open tasks with same summary
                    duplicate_exists = any(
                        task['summary'].lower() == template.summary.lower()
                        for task in open_tasks
                    )

                    if duplicate_exists:
                        logger.debug(
                            "Skipping community task generation for %s because an open task already exists",
                            template.summary,
                        )
                        continue

                    task_id = await self.create_task_from_template(template.name)
                    if task_id:
                        tasks_created.append(task_id)
                        open_tasks.append({'summary': template.summary})
                        state[state_key] = current_time.isoformat()
                        logger.info(f"Generated periodic community task from template: {template.name}")

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
