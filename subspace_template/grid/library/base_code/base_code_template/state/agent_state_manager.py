"""Agent state management and persistence.

This module handles saving, loading, and tracking agent state
throughout the cognitive loop lifecycle.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

from ..utils.json_utils import DateTimeEncoder, safe_json_encode, safe_json_decode
from ..utils.file_utils import FileManager
from ..utils.cognitive_utils import CognitiveUtils

logger = logging.getLogger("agent.state")


class AgentStateManager:
    """Manages agent state persistence and transitions."""
    
    def __init__(self, agent_id: str, memory_dir: Path):
        """Initialize state manager.
        
        Args:
            agent_id: Agent identifier
            memory_dir: Directory for state persistence
        """
        self.agent_id = agent_id
        self.memory_dir = memory_dir
        self.file_manager = FileManager()
        self.cognitive_utils = CognitiveUtils()
        
        # State storage
        self.current_state = {
            "agent_id": agent_id,
            "cycle_count": 0,
            "cycle_state": "perceive",
            "last_activity": datetime.now(),
            "status": "active",
            "metadata": {}
        }
        
        # State history
        self.state_history = []
        self.max_history = 100
        
        # File paths
        self.state_file = memory_dir / "agent_state.json"
        self.history_file = memory_dir / "state_history.json"
        
    def initialize(self) -> bool:
        """Initialize state management system.
        
        Returns:
            True if initialized successfully
        """
        try:
            # Ensure memory directory exists
            self.file_manager.ensure_directory(self.memory_dir)
            
            # Try to load existing state
            if self.state_file.exists():
                self.load_state()
            else:
                # Save initial state
                self.save_state()
                
            logger.info(f"State manager initialized for agent {self.agent_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize state manager: {e}")
            return False
            
    def save_state(self, state_data: Optional[Dict[str, Any]] = None) -> bool:
        """Save current agent state.
        
        Args:
            state_data: Optional state data to save (uses current_state if None)
            
        Returns:
            True if saved successfully
        """
        try:
            # Use provided state or current state
            state_to_save = state_data or self.current_state
            
            # Update timestamp
            state_to_save["last_saved"] = datetime.now()
            
            # Save state file
            state_json = safe_json_encode(state_to_save, indent=2)
            success = self.file_manager.save_file(self.state_file, state_json, atomic=True)
            
            if success:
                # Add to history
                self._add_to_history(state_to_save)
                logger.debug(f"Saved state for agent {self.agent_id}")
                
            return success
            
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            return False
            
    def load_state(self) -> Optional[Dict[str, Any]]:
        """Load agent state from disk.
        
        Returns:
            Loaded state dict or None if failed
        """
        try:
            # Load state file
            state_json = self.file_manager.load_file(self.state_file)
            if not state_json:
                logger.warning("No state file found")
                return None
                
            # Parse state
            state_data = safe_json_decode(state_json)
            if not state_data:
                logger.error("Failed to parse state file")
                return None
                
            # Convert string timestamps back to datetime
            for field in ["last_activity", "last_saved"]:
                if field in state_data and isinstance(state_data[field], str):
                    try:
                        state_data[field] = datetime.fromisoformat(state_data[field])
                    except:
                        pass
                        
            # Update current state
            self.current_state = state_data
            logger.info(f"Loaded state for agent {self.agent_id}: cycle {state_data.get('cycle_count', 0)}")
            
            # Load history if available
            self._load_history()
            
            return state_data
            
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            return None
            
    def update_state(self, updates: Dict[str, Any], save: bool = True) -> bool:
        """Update agent state with new values.
        
        Args:
            updates: Dictionary of state updates
            save: Whether to save immediately
            
        Returns:
            True if updated successfully
        """
        try:
            # Track what changed
            changes = {}
            for key, value in updates.items():
                if key in self.current_state and self.current_state[key] != value:
                    changes[key] = {
                        "old": self.current_state[key],
                        "new": value
                    }
                    
            # Apply updates
            self.current_state.update(updates)
            self.current_state["last_updated"] = datetime.now()
            
            # Track state change if significant
            if changes:
                self._track_state_change(changes)
                
            # Save if requested
            if save:
                return self.save_state()
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to update state: {e}")
            return False
            
    def get_current_state(self) -> Dict[str, Any]:
        """Get current agent state.
        
        Returns:
            Current state dictionary
        """
        return self.current_state.copy()
        
    def get_state_value(self, key: str, default: Any = None) -> Any:
        """Get specific state value.
        
        Args:
            key: State key to retrieve
            default: Default value if key not found
            
        Returns:
            State value or default
        """
        return self.current_state.get(key, default)
        
    def set_cycle_state(self, new_state: str, **kwargs) -> bool:
        """Set the cognitive cycle state.
        
        Args:
            new_state: New cycle state (perceive, observe, etc.)
            **kwargs: Additional state updates
            
        Returns:
            True if updated successfully
        """
        updates = {
            "cycle_state": new_state,
            "cycle_state_changed": datetime.now()
        }
        updates.update(kwargs)
        
        return self.update_state(updates)
        
    def increment_cycle_count(self) -> int:
        """Increment and return the cycle count.
        
        Returns:
            New cycle count
        """
        new_count = self.current_state.get("cycle_count", 0) + 1
        self.update_state({"cycle_count": new_count})
        return new_count
        
    def _track_state_change(self, changes: Dict[str, Any]):
        """Track state changes for history.
        
        Args:
            changes: Dictionary of changes
        """
        change_record = {
            "timestamp": datetime.now(),
            "changes": changes,
            "cycle_count": self.current_state.get("cycle_count", 0),
            "cycle_state": self.current_state.get("cycle_state", "unknown")
        }
        
        # Log significant changes
        for key, change in changes.items():
            if key in ["cycle_state", "status"]:
                logger.info(f"State change: {key} {change['old']} -> {change['new']}")
                
    def _add_to_history(self, state_snapshot: Dict[str, Any]):
        """Add state snapshot to history.
        
        Args:
            state_snapshot: State snapshot to add
        """
        # Create history entry
        history_entry = {
            "timestamp": datetime.now(),
            "snapshot": state_snapshot.copy()
        }
        
        # Add to history
        self.state_history.append(history_entry)
        
        # Trim history if needed
        if len(self.state_history) > self.max_history:
            self.state_history = self.state_history[-self.max_history:]
            
        # Save history periodically
        if len(self.state_history) % 10 == 0:
            self._save_history()
            
    def _save_history(self):
        """Save state history to disk."""
        try:
            history_json = safe_json_encode(self.state_history, indent=2)
            self.file_manager.save_file(self.history_file, history_json)
        except Exception as e:
            logger.error(f"Failed to save state history: {e}")
            
    def _load_history(self):
        """Load state history from disk."""
        try:
            history_json = self.file_manager.load_file(self.history_file)
            if history_json:
                self.state_history = safe_json_decode(history_json) or []
                logger.debug(f"Loaded {len(self.state_history)} history entries")
        except Exception as e:
            logger.error(f"Failed to load state history: {e}")
            
    def get_state_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent state history.
        
        Args:
            limit: Maximum entries to return
            
        Returns:
            List of history entries
        """
        return self.state_history[-limit:] if self.state_history else []
        
    def validate_state(self, state_data: Optional[Dict[str, Any]] = None) -> bool:
        """Validate state data structure.
        
        Args:
            state_data: State data to validate (uses current_state if None)
            
        Returns:
            True if valid
        """
        state_to_validate = state_data or self.current_state
        
        # Required fields
        required_fields = ["agent_id", "cycle_count", "cycle_state", "status"]
        
        is_valid, error = self.cognitive_utils.validate_cognitive_structure(
            state_to_validate, 
            required_fields
        )
        
        if not is_valid:
            logger.error(f"Invalid state: {error}")
            
        return is_valid
        
    def create_checkpoint(self, checkpoint_name: str) -> bool:
        """Create a named checkpoint of current state.
        
        Args:
            checkpoint_name: Name for the checkpoint
            
        Returns:
            True if checkpoint created successfully
        """
        try:
            checkpoint_dir = self.memory_dir / "checkpoints"
            self.file_manager.ensure_directory(checkpoint_dir)
            
            checkpoint_file = checkpoint_dir / f"{checkpoint_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            checkpoint_data = {
                "checkpoint_name": checkpoint_name,
                "created_at": datetime.now(),
                "state": self.current_state.copy(),
                "metadata": {
                    "cycle_count": self.current_state.get("cycle_count", 0),
                    "status": self.current_state.get("status", "unknown")
                }
            }
            
            checkpoint_json = safe_json_encode(checkpoint_data, indent=2)
            return self.file_manager.save_file(checkpoint_file, checkpoint_json)
            
        except Exception as e:
            logger.error(f"Failed to create checkpoint: {e}")
            return False
            
    def restore_checkpoint(self, checkpoint_name: str) -> bool:
        """Restore state from a checkpoint.
        
        Args:
            checkpoint_name: Name of checkpoint to restore
            
        Returns:
            True if restored successfully
        """
        try:
            checkpoint_dir = self.memory_dir / "checkpoints"
            
            # Find matching checkpoint (most recent)
            checkpoints = self.file_manager.list_directory(checkpoint_dir, f"{checkpoint_name}_*.json")
            
            if not checkpoints:
                logger.error(f"No checkpoint found with name: {checkpoint_name}")
                return False
                
            # Use most recent
            checkpoint_file = sorted(checkpoints)[-1]
            
            checkpoint_json = self.file_manager.load_file(checkpoint_file)
            if not checkpoint_json:
                return False
                
            checkpoint_data = safe_json_decode(checkpoint_json)
            if checkpoint_data and "state" in checkpoint_data:
                self.current_state = checkpoint_data["state"]
                self.save_state()
                logger.info(f"Restored checkpoint: {checkpoint_name}")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Failed to restore checkpoint: {e}")
            return False