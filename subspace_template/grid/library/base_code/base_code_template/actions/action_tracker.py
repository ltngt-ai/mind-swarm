"""Action tracking system to replace cycle_state current_actions functionality."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

@dataclass
class ActionTracker:
    """Tracks current actions being executed, replacing cycle_state functionality."""
    
    current_actions: List[Dict[str, Any]] = field(default_factory=list)
    
    def set_actions(self, actions: List[Dict[str, Any]]) -> None:
        """Set the current actions list."""
        self.current_actions = actions.copy() if actions else []
        logger.debug(f"Set {len(self.current_actions)} actions in tracker")
    
    def add_action(self, action: Dict[str, Any]) -> None:
        """Add an action to the current list."""
        self.current_actions.append(action)
        logger.debug(f"Added action: {action.get('name', 'unknown')}")
    
    def clear_actions(self) -> None:
        """Clear all current actions."""
        self.current_actions.clear()
        logger.debug("Cleared all actions from tracker")
    
    def get_actions(self) -> List[Dict[str, Any]]:
        """Get copy of current actions."""
        return self.current_actions.copy()
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {"current_actions": self.current_actions}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionTracker":
        """Deserialize from dictionary."""
        return cls(current_actions=data.get("current_actions", []))