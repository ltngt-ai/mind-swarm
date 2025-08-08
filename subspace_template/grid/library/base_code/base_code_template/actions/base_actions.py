"""Base action classes and registry for the cognitive system."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime

from ..memory import MemoryBlock, Priority

logger = logging.getLogger("Cyber.actions")


class ActionStatus(Enum):
    """Status of an action execution."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ActionResult:
    """Result of executing an action."""
    action_name: str
    status: ActionStatus
    result: Any = None
    error: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class Action(ABC):
    """Base class for all actions."""
    
    def __init__(self, name: str, description: str, priority: Priority = Priority.MEDIUM):
        """Initialize action.
        
        Args:
            name: Action identifier
            description: Human-readable description
            priority: Execution priority
        """
        self.name = name
        self.description = description
        self.priority = priority
        self.params: Dict[str, Any] = {}
    
    def with_params(self, **params) -> 'Action':
        """Set parameters for this action.
        
        Returns:
            Self for chaining
        """
        self.params.update(params)
        return self
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Execute the action.
        
        Args:
            context: Execution context including Cyber state, memory, etc.
            
        Returns:
            ActionResult with outcome
        """
        pass
    
    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}', params={self.params})"


# Base Actions available to all Cybers

class SendMessageAction(Action):
    """Send a message to another Cyber."""
    
    def __init__(self):
        super().__init__("send_message", "Send message to another Cyber")
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Write message to outbox."""
        to_agent = self.params.get("to")
        message_type = self.params.get("type", "RESPONSE")
        content = self.params.get("content", "")
        
        if not to_agent:
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error="No recipient specified"
            )
        
        # Process template references in content
        if "@last" in content and "last_action_result" in context:
            last_result = context["last_action_result"]
            
            # Simple @last replacement
            if isinstance(last_result, str) or isinstance(last_result, (int, float)):
                content = content.replace("@last", str(last_result))
            elif isinstance(last_result, dict):
                # For dict results, use string representation for bare @last
                content = content.replace("@last", str(last_result))
                
                # Handle nested access like @last.output or @last.variables.result
                import re
                # Find all @last.path.to.value patterns
                pattern = r'@last\.([a-zA-Z0-9_.]+)'
                matches = re.findall(pattern, content)
                
                for path in matches:
                    # Navigate the path
                    value = last_result
                    for part in path.split('.'):
                        if isinstance(value, dict) and part in value:
                            value = value[part]
                        else:
                            value = f"<undefined:{path}>"
                            break
                    
                    # Replace the pattern with the value
                    content = content.replace(f"@last.{path}", str(value))
        
        try:
            # Get outbox from context
            outbox_dir = context.get("outbox_dir")
            cyber_id = context.get("cyber_id")
            
            if not outbox_dir:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error="No outbox directory in context"
                )
            
            # Create message
            message = {
                "from": cyber_id,
                "to": to_agent,
                "type": message_type,
                "content": content,
                "timestamp": datetime.now().isoformat()
            }
            
            # Write to outbox
            import json
            from pathlib import Path
            msg_id = f"{cyber_id}_{int(datetime.now().timestamp() * 1000)}"
            msg_file = Path(outbox_dir) / f"{msg_id}.msg"
            msg_file.write_text(json.dumps(message, indent=2))
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result={"message_id": msg_id, "to": to_agent}
            )
        except Exception as e:
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=str(e)
            )

class WaitAction(Action):
    """Wait for a condition or timeout."""
    
    def __init__(self):
        super().__init__("wait", "Wait for condition or timeout")
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Wait for specified duration or condition."""
        duration = self.params.get("duration", 1.0)
        condition = self.params.get("condition")
        
        try:
            import asyncio
            
            # Convert duration to float if it's a string
            if isinstance(duration, str):
                try:
                    duration = float(duration)
                except ValueError:
                    return ActionResult(
                        self.name,
                        ActionStatus.FAILED,
                        error=f"Invalid duration: {duration} - must be a number"
                    )
            
            if condition:
                # Check condition (simplified)
                # Real implementation would check memory, files, etc.
                await asyncio.sleep(0.1)  # Quick check
            else:
                # Simple timeout
                await asyncio.sleep(duration)
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result={"waited": duration}
            )
        except Exception as e:
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=str(e)
            )


# Action Registry

class ActionRegistry:
    """Registry of available actions for different Cyber types."""
    
    def __init__(self):
        self._actions: Dict[str, Dict[str, type[Action]]] = {
            # Base actions available to all Cybers
            "base": {
                "send_message": SendMessageAction,
                "wait": WaitAction,
            }
        }
    
    def register_action(self, cyber_type: str, action_name: str, action_class: type[Action]):
        """Register an action for a specific Cyber type."""
        if cyber_type not in self._actions:
            self._actions[cyber_type] = {}
        self._actions[cyber_type][action_name] = action_class
    
    def get_available_actions(self, cyber_type: str) -> Dict[str, type[Action]]:
        """Get all available actions for an Cyber type."""
        # Start with base actions
        actions = self._actions["base"].copy()
        
        # Add type-specific actions
        if cyber_type in self._actions:
            actions.update(self._actions[cyber_type])
        
        return actions
    
    def create_action(self, cyber_type: str, action_name: str) -> Optional[Action]:
        """Create an action instance."""
        actions = self.get_available_actions(cyber_type)
        action_class = actions.get(action_name)
        
        if action_class:
            return action_class()
        return None

    def get_actions_for_agent(self, cyber_type: str) -> List[str]:
        """Get list of action names for an Cyber type."""
        return list(self.get_available_actions(cyber_type).keys())


# Global action registry
action_registry = ActionRegistry()