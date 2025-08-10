"""Goal Manager - Manages high-level goals and active tasks for Cybers.

This module provides persistent goal tracking and task management,
giving Cybers purpose and direction across cognitive cycles.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum

from ..utils.json_utils import safe_json_encode, safe_json_decode

logger = logging.getLogger("Cyber.goals")


class GoalStatus(Enum):
    """Status of a goal."""
    PLANNED = "planned"
    ACTIVE = "active"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    BLOCKED = "blocked"


class TaskStatus(Enum):
    """Status of a task."""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class Goal:
    """Represents a high-level goal."""
    id: str
    description: str
    priority: str = "medium"  # high, medium, low
    status: GoalStatus = GoalStatus.PLANNED
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    progress: Dict[str, Any] = field(default_factory=dict)
    sub_goals: List[str] = field(default_factory=list)
    parent_goal: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Goal":
        """Create from dictionary."""
        data = data.copy()
        data['status'] = GoalStatus(data['status'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)


@dataclass
class Task:
    """Represents a concrete task towards a goal."""
    id: str
    goal_id: str
    description: str
    status: TaskStatus = TaskStatus.TODO
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    actions_taken: List[Dict[str, Any]] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create from dictionary."""
        data = data.copy()
        data['status'] = TaskStatus(data['status'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)


class GoalManager:
    """Manages goals and tasks for a Cyber."""
    
    def __init__(self, memory_dir: Path):
        """Initialize the goal manager.
        
        Args:
            memory_dir: Directory for storing goals and tasks
        """
        self.memory_dir = memory_dir
        self.goals_file = memory_dir / "goals.json"
        self.tasks_file = memory_dir / "active_tasks.json"
        
        # Current state
        self.goals: Dict[str, Goal] = {}
        self.tasks: Dict[str, Task] = {}
        
        # Load existing state
        self.load_goals()
        self.load_tasks()
    
    def load_goals(self) -> bool:
        """Load goals from disk.
        
        Returns:
            True if loaded successfully
        """
        try:
            if self.goals_file.exists():
                with open(self.goals_file, 'r') as f:
                    data = json.load(f)
                    for goal_data in data.get('goals', []):
                        goal = Goal.from_dict(goal_data)
                        self.goals[goal.id] = goal
                    logger.info(f"Loaded {len(self.goals)} goals")
                    return True
        except Exception as e:
            logger.error(f"Failed to load goals: {e}")
        return False
    
    def save_goals(self) -> bool:
        """Save goals to disk.
        
        Returns:
            True if saved successfully
        """
        try:
            goals_data = {
                "goals": [goal.to_dict() for goal in self.goals.values()],
                "last_updated": datetime.now().isoformat()
            }
            goals_json = safe_json_encode(goals_data, indent=2)
            with open(self.goals_file, 'w') as f:
                f.write(goals_json)
            return True
        except Exception as e:
            logger.error(f"Failed to save goals: {e}")
            return False
    
    def load_tasks(self) -> bool:
        """Load tasks from disk.
        
        Returns:
            True if loaded successfully
        """
        try:
            if self.tasks_file.exists():
                with open(self.tasks_file, 'r') as f:
                    data = json.load(f)
                    for task_data in data.get('tasks', []):
                        task = Task.from_dict(task_data)
                        self.tasks[task.id] = task
                    logger.info(f"Loaded {len(self.tasks)} tasks")
                    return True
        except Exception as e:
            logger.error(f"Failed to load tasks: {e}")
        return False
    
    def save_tasks(self) -> bool:
        """Save tasks to disk.
        
        Returns:
            True if saved successfully
        """
        try:
            tasks_data = {
                "tasks": [task.to_dict() for task in self.tasks.values()],
                "last_updated": datetime.now().isoformat()
            }
            tasks_json = safe_json_encode(tasks_data, indent=2)
            with open(self.tasks_file, 'w') as f:
                f.write(tasks_json)
            return True
        except Exception as e:
            logger.error(f"Failed to save tasks: {e}")
            return False
    
    def create_goal(self, description: str, priority: str = "medium", 
                   parent_goal: Optional[str] = None) -> Goal:
        """Create a new goal.
        
        Args:
            description: Goal description
            priority: Goal priority (high, medium, low)
            parent_goal: Optional parent goal ID
            
        Returns:
            The created goal
        """
        goal_id = f"goal_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.goals)}"
        goal = Goal(
            id=goal_id,
            description=description,
            priority=priority,
            parent_goal=parent_goal,
            status=GoalStatus.PLANNED
        )
        
        self.goals[goal_id] = goal
        
        # Add to parent's sub_goals if applicable
        if parent_goal and parent_goal in self.goals:
            self.goals[parent_goal].sub_goals.append(goal_id)
        
        self.save_goals()
        logger.info(f"Created goal: {goal_id} - {description}")
        return goal
    
    def create_task(self, goal_id: str, description: str) -> Optional[Task]:
        """Create a new task for a goal.
        
        Args:
            goal_id: The goal this task contributes to
            description: Task description
            
        Returns:
            The created task or None if goal doesn't exist
        """
        if goal_id not in self.goals:
            logger.error(f"Cannot create task - goal {goal_id} not found")
            return None
        
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.tasks)}"
        task = Task(
            id=task_id,
            goal_id=goal_id,
            description=description,
            status=TaskStatus.TODO
        )
        
        self.tasks[task_id] = task
        self.save_tasks()
        logger.info(f"Created task: {task_id} for goal {goal_id}")
        return task
    
    def update_goal_status(self, goal_id: str, status: GoalStatus) -> bool:
        """Update a goal's status.
        
        Args:
            goal_id: Goal to update
            status: New status
            
        Returns:
            True if updated successfully
        """
        if goal_id not in self.goals:
            return False
        
        self.goals[goal_id].status = status
        self.goals[goal_id].updated_at = datetime.now()
        self.save_goals()
        logger.info(f"Updated goal {goal_id} status to {status.value}")
        return True
    
    def update_task_status(self, task_id: str, status: TaskStatus) -> bool:
        """Update a task's status.
        
        Args:
            task_id: Task to update
            status: New status
            
        Returns:
            True if updated successfully
        """
        if task_id not in self.tasks:
            return False
        
        self.tasks[task_id].status = status
        self.tasks[task_id].updated_at = datetime.now()
        self.save_tasks()
        logger.info(f"Updated task {task_id} status to {status.value}")
        return True
    
    def add_task_action(self, task_id: str, action: Dict[str, Any]) -> bool:
        """Add an action taken for a task.
        
        Args:
            task_id: Task ID
            action: Action details
            
        Returns:
            True if added successfully
        """
        if task_id not in self.tasks:
            return False
        
        self.tasks[task_id].actions_taken.append(action)
        self.tasks[task_id].updated_at = datetime.now()
        self.save_tasks()
        return True
    
    def get_active_goals(self) -> List[Goal]:
        """Get all active goals.
        
        Returns:
            List of active goals
        """
        return [
            goal for goal in self.goals.values()
            if goal.status in [GoalStatus.ACTIVE, GoalStatus.IN_PROGRESS]
        ]
    
    def get_active_tasks(self) -> List[Task]:
        """Get all active tasks.
        
        Returns:
            List of active tasks
        """
        return [
            task for task in self.tasks.values()
            if task.status in [TaskStatus.TODO, TaskStatus.IN_PROGRESS]
        ]
    
    def get_tasks_for_goal(self, goal_id: str) -> List[Task]:
        """Get all tasks for a specific goal.
        
        Args:
            goal_id: Goal ID
            
        Returns:
            List of tasks for the goal
        """
        return [
            task for task in self.tasks.values()
            if task.goal_id == goal_id
        ]
    
    def get_goal_summary(self) -> Dict[str, Any]:
        """Get a summary of goal state.
        
        Returns:
            Summary of goals and tasks
        """
        return {
            "total_goals": len(self.goals),
            "active_goals": len(self.get_active_goals()),
            "total_tasks": len(self.tasks),
            "active_tasks": len(self.get_active_tasks()),
            "goals_by_status": {
                status.value: len([g for g in self.goals.values() if g.status == status])
                for status in GoalStatus
            },
            "tasks_by_status": {
                status.value: len([t for t in self.tasks.values() if t.status == status])
                for status in TaskStatus
            }
        }