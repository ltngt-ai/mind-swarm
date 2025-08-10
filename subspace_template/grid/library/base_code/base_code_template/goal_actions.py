"""Goal management actions for Cybers to set and track objectives."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from .actions.base_actions import Action, ActionResult, ActionStatus, Priority as ActionPriority
from .state.goal_manager import GoalManager, GoalStatus, TaskStatus

logger = logging.getLogger("Cyber.goal_actions")


class CreateGoalAction(Action):
    """Create a new goal to work towards.
    
    This allows Cybers to set their own objectives and priorities.
    """
    
    def __init__(self):
        super().__init__(
            "create_goal",
            "Create a new goal",
            priority=ActionPriority.MEDIUM
        )
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Create a new goal.
        
        Params (from self.params):
            description: Goal description
            priority: Goal priority (high, medium, low)
            parent_goal: Optional parent goal ID for sub-goals
        
        Args:
            context: Execution context
            
        Returns:
            ActionResult with created goal details
        """
        try:
            description = self.params.get("description", "").strip()
            priority = self.params.get("priority", "medium").lower()
            parent_goal = self.params.get("parent_goal")
            
            if not description:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error="Goal description is required"
                )
            
            if priority not in ["high", "medium", "low"]:
                priority = "medium"
            
            # Get goal manager from cognitive loop
            cognitive_loop = context.get("cognitive_loop")
            if not cognitive_loop:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error="Goal manager not available"
                )
            
            goal_manager = cognitive_loop.goal_manager
            
            # Create the goal
            goal = goal_manager.create_goal(description, priority, parent_goal)
            
            # Automatically set as active if no other goals exist
            active_goals = goal_manager.get_active_goals()
            if not active_goals:
                goal_manager.update_goal_status(goal.id, GoalStatus.ACTIVE)
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result={
                    "goal_id": goal.id,
                    "description": goal.description,
                    "priority": goal.priority,
                    "status": goal.status.value,
                    "created_at": goal.created_at.isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Error creating goal: {e}", exc_info=True)
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=str(e)
            )


class CreateTaskAction(Action):
    """Create a task for a specific goal.
    
    This breaks down goals into actionable tasks.
    """
    
    def __init__(self):
        super().__init__(
            "create_task",
            "Create a task for a goal",
            priority=ActionPriority.MEDIUM
        )
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Create a new task.
        
        Params (from self.params):
            goal_id: The goal this task contributes to
            description: Task description
        
        Args:
            context: Execution context
            
        Returns:
            ActionResult with created task details
        """
        try:
            goal_id = self.params.get("goal_id", "").strip()
            description = self.params.get("description", "").strip()
            
            if not goal_id:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error="Goal ID is required"
                )
            
            if not description:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error="Task description is required"
                )
            
            # Get goal manager
            cognitive_loop = context.get("cognitive_loop")
            if not cognitive_loop:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error="Goal manager not available"
                )
            
            goal_manager = cognitive_loop.goal_manager
            
            # Create the task
            task = goal_manager.create_task(goal_id, description)
            if not task:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error=f"Goal {goal_id} not found"
                )
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result={
                    "task_id": task.id,
                    "goal_id": task.goal_id,
                    "description": task.description,
                    "status": task.status.value,
                    "created_at": task.created_at.isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Error creating task: {e}", exc_info=True)
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=str(e)
            )


class UpdateGoalStatusAction(Action):
    """Update the status of a goal.
    
    This allows Cybers to mark goals as completed, abandoned, etc.
    """
    
    def __init__(self):
        super().__init__(
            "update_goal_status",
            "Update goal status",
            priority=ActionPriority.LOW
        )
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Update goal status.
        
        Params (from self.params):
            goal_id: Goal to update
            status: New status (planned, active, in_progress, completed, abandoned, blocked)
        
        Args:
            context: Execution context
            
        Returns:
            ActionResult with update confirmation
        """
        try:
            goal_id = self.params.get("goal_id", "").strip()
            status_str = self.params.get("status", "").lower()
            
            if not goal_id:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error="Goal ID is required"
                )
            
            # Map status string to enum
            status_map = {
                "planned": GoalStatus.PLANNED,
                "active": GoalStatus.ACTIVE,
                "in_progress": GoalStatus.IN_PROGRESS,
                "completed": GoalStatus.COMPLETED,
                "abandoned": GoalStatus.ABANDONED,
                "blocked": GoalStatus.BLOCKED
            }
            
            if status_str not in status_map:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error=f"Invalid status: {status_str}. Must be one of: {', '.join(status_map.keys())}"
                )
            
            status = status_map[status_str]
            
            # Get goal manager
            cognitive_loop = context.get("cognitive_loop")
            if not cognitive_loop:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error="Goal manager not available"
                )
            
            goal_manager = cognitive_loop.goal_manager
            
            # Update the status
            success = goal_manager.update_goal_status(goal_id, status)
            if not success:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error=f"Goal {goal_id} not found"
                )
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result={
                    "goal_id": goal_id,
                    "new_status": status.value,
                    "updated": True
                }
            )
            
        except Exception as e:
            logger.error(f"Error updating goal status: {e}", exc_info=True)
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=str(e)
            )


class UpdateTaskStatusAction(Action):
    """Update the status of a task.
    
    This allows Cybers to track task progress.
    """
    
    def __init__(self):
        super().__init__(
            "update_task_status",
            "Update task status",
            priority=ActionPriority.LOW
        )
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Update task status.
        
        Params (from self.params):
            task_id: Task to update
            status: New status (todo, in_progress, completed, failed, blocked)
        
        Args:
            context: Execution context
            
        Returns:
            ActionResult with update confirmation
        """
        try:
            task_id = self.params.get("task_id", "").strip()
            status_str = self.params.get("status", "").lower()
            
            if not task_id:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error="Task ID is required"
                )
            
            # Map status string to enum
            status_map = {
                "todo": TaskStatus.TODO,
                "in_progress": TaskStatus.IN_PROGRESS,
                "completed": TaskStatus.COMPLETED,
                "failed": TaskStatus.FAILED,
                "blocked": TaskStatus.BLOCKED
            }
            
            if status_str not in status_map:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error=f"Invalid status: {status_str}. Must be one of: {', '.join(status_map.keys())}"
                )
            
            status = status_map[status_str]
            
            # Get goal manager
            cognitive_loop = context.get("cognitive_loop")
            if not cognitive_loop:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error="Goal manager not available"
                )
            
            goal_manager = cognitive_loop.goal_manager
            
            # Update the status
            success = goal_manager.update_task_status(task_id, status)
            if not success:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error=f"Task {task_id} not found"
                )
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result={
                    "task_id": task_id,
                    "new_status": status.value,
                    "updated": True
                }
            )
            
        except Exception as e:
            logger.error(f"Error updating task status: {e}", exc_info=True)
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=str(e)
            )


class ListGoalsAction(Action):
    """List all goals or goals with specific status.
    
    This allows Cybers to review their objectives.
    """
    
    def __init__(self):
        super().__init__(
            "list_goals",
            "List goals",
            priority=ActionPriority.LOW
        )
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """List goals.
        
        Params (from self.params):
            status: Optional status filter (active, completed, etc.)
        
        Args:
            context: Execution context
            
        Returns:
            ActionResult with goals list
        """
        try:
            status_filter = self.params.get("status", "").lower()
            
            # Get goal manager
            cognitive_loop = context.get("cognitive_loop")
            if not cognitive_loop:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error="Goal manager not available"
                )
            
            goal_manager = cognitive_loop.goal_manager
            
            # Get goals based on filter
            if status_filter == "active":
                goals = goal_manager.get_active_goals()
            elif status_filter:
                # Filter by specific status
                goals = [g for g in goal_manager.goals.values() 
                        if g.status.value == status_filter]
            else:
                # All goals
                goals = list(goal_manager.goals.values())
            
            # Format goals for response
            goals_list = [{
                "id": g.id,
                "description": g.description,
                "priority": g.priority,
                "status": g.status.value,
                "created_at": g.created_at.isoformat(),
                "updated_at": g.updated_at.isoformat(),
                "sub_goals": g.sub_goals,
                "parent_goal": g.parent_goal
            } for g in goals]
            
            # Get summary
            summary = goal_manager.get_goal_summary()
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result={
                    "goals": goals_list,
                    "count": len(goals_list),
                    "summary": summary
                }
            )
            
        except Exception as e:
            logger.error(f"Error listing goals: {e}", exc_info=True)
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=str(e)
            )


# Register goal actions
def register_goal_actions(registry):
    """Register all goal management actions."""
    registry.register_action("base", "create_goal", CreateGoalAction)
    registry.register_action("base", "create_task", CreateTaskAction)
    registry.register_action("base", "update_goal_status", UpdateGoalStatusAction)
    registry.register_action("base", "update_task_status", UpdateTaskStatusAction)
    registry.register_action("base", "list_goals", ListGoalsAction)