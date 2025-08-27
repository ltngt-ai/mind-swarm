"""
Unified State Manager for Cyber - consolidates all state management into a single system.

This module replaces the fragmented state storage (cyber_state.json, status.json, 
biofeedback_state.json, dynamic_context.json) with a single, well-organized state file.
"""

import json
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

from ..utils.json_utils import DateTimeEncoder, safe_json_encode, safe_json_decode
from ..utils.file_utils import FileManager

logger = logging.getLogger("Cyber.unified_state")


class StateSection(Enum):
    """Sections in the unified state."""
    IDENTITY = "identity"
    COGNITIVE = "cognitive"
    BIOFEEDBACK = "biofeedback"
    TASK = "task"
    LOCATION = "location"
    MEMORY = "memory"
    PERFORMANCE = "performance"


class UnifiedStateManager:
    """Manages all Cyber state in a single, unified system."""
    
    def __init__(self, cyber_id: str, memory_dir: Path):
        """Initialize unified state manager.
        
        Args:
            cyber_id: Cyber identifier
            memory_dir: Directory for state persistence
        """
        self.cyber_id = cyber_id
        self.memory_dir = memory_dir
        self.file_manager = FileManager()
        
        # Single state file
        self.state_file = memory_dir / "unified_state.json"
        
        # Initialize state structure
        self.state = self._create_default_state()
        
        # Configuration for biofeedback
        self.config = {
            'boredom_increment': 5,
            'tiredness_increment': 2,
            'tiredness_decay': 20,
            'duty_decay_cycles': 20,
            'duty_decay_amount': 5,
            'duty_completion_bonus': 20,
            'restlessness_increment_cycles': 10,
            'restlessness_increment': 10,
            'restlessness_move_decay': 10,
        }
        
    def _create_default_state(self) -> Dict[str, Any]:
        """Create default state structure.
        
        Returns:
            Default state dictionary with all sections
        """
        return {
            # Identity section
            StateSection.IDENTITY.value: {
                "cyber_id": self.cyber_id,
                "name": self.cyber_id,  # Will be updated from identity file
                "created_at": datetime.now().isoformat(),
                "version": "2.0.0"  # State format version
            },
            
            # Cognitive section (replaces cognitive_loop state)
            StateSection.COGNITIVE.value: {
                "cycle_count": 0,
                "current_stage": "INIT",
                "current_phase": "STARTING",
                "last_activity": datetime.now().isoformat(),
                "status": "active",  # active, thinking, waiting, error
                "thinking_depth": 0,  # How many cognitive cycles deep
            },
            
            # Biofeedback section (replaces biofeedback_state.json)
            StateSection.BIOFEEDBACK.value: {
                "boredom": 0,
                "tiredness": 0,
                "duty": 100,
                "restlessness": 0,
                "last_update_cycle": 0,
                "cycles_on_current_task": 0,
                "cycles_since_maintenance": 0,
                "cycles_since_move": 0,
                "last_duty_decrement_cycle": 0,
                "credited_community_tasks": [],
                "credited_maintenance_tasks": [],
            },
            
            # Task section (current task tracking)
            StateSection.TASK.value: {
                "current_task_id": None,
                "current_task_type": None,  # hobby, maintenance, community
                "current_task_summary": None,
                "task_started_cycle": None,
                "task_progress": {},  # Task-specific progress tracking
                "completed_tasks_count": {
                    "community": 0,
                    "maintenance": 0,
                    "hobby": 0
                }
            },
            
            # Location section
            StateSection.LOCATION.value: {
                "current_location": "/grid/library/knowledge",
                "previous_location": None,
                "location_changed_cycle": 0,
                "visited_locations": [],  # History of visited locations
            },
            
            # Memory section (memory system state)
            StateSection.MEMORY.value: {
                "total_memories": 0,
                "working_memory_count": 0,
                "last_cleanup_cycle": 0,
                "memory_usage_bytes": 0,
                "cache_hits": 0,
                "cache_misses": 0,
            },
            
            # Performance section
            StateSection.PERFORMANCE.value: {
                "average_cycle_duration_ms": 0,
                "total_actions_executed": 0,
                "successful_actions": 0,
                "failed_actions": 0,
                "brain_requests": 0,
                "brain_tokens_used": 0,
            },
            
            
            # Metadata
            "_metadata": {
                "last_saved": datetime.now().isoformat(),
                "save_count": 0,
                "format_version": "2.0.0"
            }
        }
    
    def initialize(self) -> bool:
        """Initialize state management system.
        
        Returns:
            True if initialized successfully
        """
        try:
            # Ensure memory directory exists
            self.file_manager.ensure_directory(self.memory_dir)
            
            # Load existing state or create new
            if self.state_file.exists():
                self.load_state()
            else:
                # Save initial state
                self.save_state()
            
            logger.info(f"Unified state manager initialized for Cyber {self.cyber_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize unified state manager: {e}")
            return False
    
    
    def save_state(self) -> bool:
        """Save unified state to disk atomically.
        
        Returns:
            True if saved successfully
        """
        try:
            # Update metadata
            self.state["_metadata"]["last_saved"] = datetime.now().isoformat()
            self.state["_metadata"]["save_count"] = self.state["_metadata"].get("save_count", 0) + 1
            
            # Atomic write
            state_json = safe_json_encode(self.state, indent=2)
            success = self.file_manager.save_file(self.state_file, state_json, atomic=True)
            
            if success:
                logger.debug(f"Saved unified state for Cyber {self.cyber_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to save unified state: {e}")
            return False
    
    def load_state(self) -> Optional[Dict[str, Any]]:
        """Load unified state from disk.
        
        Returns:
            Loaded state dict or None if failed
        """
        try:
            state_json = self.file_manager.load_file(self.state_file)
            if not state_json:
                logger.warning("No unified state file found")
                return None
            
            state_data = safe_json_decode(state_json)
            if not state_data:
                logger.error("Failed to parse unified state file")
                return None
            
            # Start with default state to ensure correct structure
            default_state = self._create_default_state()
            
            # Only copy over valid sections from loaded state
            for section in StateSection:
                if section.value in state_data:
                    # Merge loaded values into default structure
                    for key in default_state[section.value].keys():
                        if key in state_data[section.value]:
                            default_state[section.value][key] = state_data[section.value][key]
            
            # Copy metadata if it exists
            if "_metadata" in state_data:
                default_state["_metadata"] = state_data["_metadata"]
            
            # Remove any invalid sections (like 'activity')
            valid_sections = {s.value for s in StateSection} | {"_metadata"}
            clean_state = {k: v for k, v in default_state.items() if k in valid_sections or k == "_metadata"}
            
            self.state = clean_state
            
            cycle = self.get_value(StateSection.COGNITIVE, "cycle_count", 0)
            logger.info(f"Loaded unified state for Cyber {self.cyber_id}: cycle {cycle}")
            
            return state_data
            
        except Exception as e:
            logger.error(f"Failed to load unified state: {e}")
            return None
    
    def get_section(self, section: StateSection) -> Dict[str, Any]:
        """Get entire section of state.
        
        Args:
            section: Section to retrieve
            
        Returns:
            Section dictionary
        """
        return self.state.get(section.value, {}).copy()
    
    def get_value(self, section: StateSection, key: str, default: Any = None) -> Any:
        """Get specific value from a section.
        
        Args:
            section: State section
            key: Key within section
            default: Default value if not found
            
        Returns:
            Value or default
        """
        return self.state.get(section.value, {}).get(key, default)
    
    def set_value(self, section: StateSection, key: str, value: Any, save: bool = True) -> bool:
        """Set specific value in a section.
        
        Args:
            section: State section
            key: Key within section
            value: Value to set
            save: Whether to save immediately
            
        Returns:
            True if set successfully
        """
        try:
            if section.value not in self.state:
                self.state[section.value] = {}
            
            self.state[section.value][key] = value
            
            if save:
                return self.save_state()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to set state value: {e}")
            return False
    
    def update_section(self, section: StateSection, updates: Dict[str, Any], save: bool = True) -> bool:
        """Update multiple values in a section.
        
        Args:
            section: State section
            updates: Dictionary of updates
            save: Whether to save immediately
            
        Returns:
            True if updated successfully
        """
        try:
            if section.value not in self.state:
                self.state[section.value] = {}
            
            self.state[section.value].update(updates)
            
            if save:
                return self.save_state()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update state section: {e}")
            return False
    
    def increment_cycle_count(self) -> int:
        """Increment and return the cycle count.
        
        Returns:
            New cycle count
        """
        new_count = self.get_value(StateSection.COGNITIVE, "cycle_count", 0) + 1
        self.set_value(StateSection.COGNITIVE, "cycle_count", new_count)
        return new_count
    
    
    def increment_counter(self, section: StateSection, key: str, amount: int = 1) -> int:
        """Increment a counter in the state.
        
        Args:
            section: State section
            key: Counter key
            amount: Amount to increment
            
        Returns:
            New counter value
        """
        current = self.get_value(section, key, 0)
        new_value = current + amount
        self.set_value(section, key, new_value)
        return new_value
    
    
    def update_biofeedback(self, current_task: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
        """Update biofeedback metrics based on current state.
        
        Args:
            current_task: Current task information
            
        Returns:
            Updated biofeedback metrics
        """
        bio = self.state[StateSection.BIOFEEDBACK.value]
        task = self.state[StateSection.TASK.value]
        location = self.state[StateSection.LOCATION.value]
        cognitive = self.state[StateSection.COGNITIVE.value]
        
        current_cycle = cognitive["cycle_count"]
        
        # Skip if same cycle
        if current_cycle <= bio["last_update_cycle"]:
            return self.get_biofeedback_stats()
        
        # Update boredom based on task continuity
        if current_task:
            if current_task['id'] == task["current_task_id"]:
                # Same task
                bio["cycles_on_current_task"] += 1
                if current_task.get('task_type') != 'hobby':
                    # Increase boredom for non-hobby tasks
                    bio["boredom"] = min(100, bio["boredom"] + self.config['boredom_increment'])
            else:
                # Task changed - reset boredom
                task["current_task_id"] = current_task['id']
                task["current_task_type"] = current_task.get('task_type')
                task["current_task_summary"] = current_task.get('summary')
                task["task_started_cycle"] = current_cycle
                bio["cycles_on_current_task"] = 1
                bio["boredom"] = max(0, bio["boredom"] - 20)
        
        # Update tiredness based on maintenance activity
        if current_task and current_task.get('task_type') == 'maintenance':
            bio["tiredness"] = max(0, bio["tiredness"] - self.config['tiredness_decay'])
            bio["cycles_since_maintenance"] = 0
        else:
            bio["cycles_since_maintenance"] += 1
            bio["tiredness"] = min(100, bio["tiredness"] + self.config['tiredness_increment'])
        
        # Update duty decay
        cycles_since_decrement = current_cycle - bio["last_duty_decrement_cycle"]
        if cycles_since_decrement >= self.config['duty_decay_cycles']:
            decrements = cycles_since_decrement // self.config['duty_decay_cycles']
            bio["duty"] = max(0, bio["duty"] - (self.config['duty_decay_amount'] * decrements))
            bio["last_duty_decrement_cycle"] = current_cycle
        
        # Update restlessness based on location
        if location["current_location"] != location.get("previous_location"):
            bio["restlessness"] = max(0, bio["restlessness"] - self.config['restlessness_move_decay'])
            bio["cycles_since_move"] = 0
        else:
            bio["cycles_since_move"] += 1
            if bio["cycles_since_move"] >= self.config['restlessness_increment_cycles']:
                bio["restlessness"] = min(100, bio["restlessness"] + self.config['restlessness_increment'])
                bio["cycles_since_move"] = 0
        
        bio["last_update_cycle"] = current_cycle
        self.save_state()
        
        return self.get_biofeedback_stats()
    
    def get_biofeedback_stats(self) -> Dict[str, int]:
        """Get current biofeedback statistics.
        
        Returns:
            Dictionary with biofeedback percentages
        """
        bio = self.state[StateSection.BIOFEEDBACK.value]
        return {
            'boredom': min(100, max(0, bio['boredom'])),
            'tiredness': min(100, max(0, bio['tiredness'])),
            'duty': min(100, max(0, bio['duty'])),
            'restlessness': min(100, max(0, bio['restlessness']))
        }
    
    def credit_task_completion(self, task_id: str, task_type: str) -> bool:
        """Credit completion of a task to biofeedback.
        
        Args:
            task_id: ID of completed task
            task_type: Type of task (community, maintenance, hobby)
            
        Returns:
            True if credited successfully
        """
        try:
            bio = self.state[StateSection.BIOFEEDBACK.value]
            task_section = self.state[StateSection.TASK.value]
            
            if task_type == "community":
                if task_id not in bio["credited_community_tasks"]:
                    bio["duty"] = min(100, bio["duty"] + self.config['duty_completion_bonus'])
                    bio["credited_community_tasks"].append(task_id)
                    
                    # Keep only last 10
                    if len(bio["credited_community_tasks"]) > 10:
                        bio["credited_community_tasks"] = bio["credited_community_tasks"][-10:]
                    
                    task_section["completed_tasks_count"]["community"] += 1
                    logger.info(f"Credited community task {task_id}, duty increased")
                    
            elif task_type == "maintenance":
                if task_id not in bio["credited_maintenance_tasks"]:
                    bio["tiredness"] = max(0, bio["tiredness"] - 15)
                    bio["credited_maintenance_tasks"].append(task_id)
                    
                    # Keep only last 10
                    if len(bio["credited_maintenance_tasks"]) > 10:
                        bio["credited_maintenance_tasks"] = bio["credited_maintenance_tasks"][-10:]
                    
                    task_section["completed_tasks_count"]["maintenance"] += 1
                    logger.info(f"Credited maintenance task {task_id}, tiredness reduced")
                    
            elif task_type == "hobby":
                task_section["completed_tasks_count"]["hobby"] += 1
            
            self.save_state()
            return True
            
        except Exception as e:
            logger.error(f"Failed to credit task completion: {e}")
            return False
    
    def update_location(self, new_location: str) -> bool:
        """Update current location.
        
        Args:
            new_location: New location path
            
        Returns:
            True if updated successfully
        """
        try:
            location = self.state[StateSection.LOCATION.value]
            
            if new_location != location["current_location"]:
                location["previous_location"] = location["current_location"]
                location["current_location"] = new_location
                location["location_changed_cycle"] = self.get_value(StateSection.COGNITIVE, "cycle_count", 0)
                
                # Add to visited locations
                if new_location not in location["visited_locations"]:
                    location["visited_locations"].append(new_location)
                    
                    # Keep only last 50 visited locations
                    if len(location["visited_locations"]) > 50:
                        location["visited_locations"] = location["visited_locations"][-50:]
                
                self.save_state()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update location: {e}")
            return False
    
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
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            checkpoint_file = checkpoint_dir / f"{checkpoint_name}_{timestamp}.json"
            
            checkpoint_data = {
                "checkpoint_name": checkpoint_name,
                "created_at": datetime.now().isoformat(),
                "state": self.state.copy(),
            }
            
            checkpoint_json = safe_json_encode(checkpoint_data, indent=2)
            return self.file_manager.save_file(checkpoint_file, checkpoint_json)
            
        except Exception as e:
            logger.error(f"Failed to create checkpoint: {e}")
            return False
    
    def export_for_display(self) -> Dict[str, Any]:
        """Export state in format suitable for display/monitoring.
        
        Returns:
            Display-friendly state dictionary
        """
        cognitive = self.get_section(StateSection.COGNITIVE)
        task = self.get_section(StateSection.TASK)
        bio = self.get_biofeedback_stats()
        
        return {
            'cycle': cognitive.get('cycle_count', 0),
            'timestamp': datetime.now().isoformat(),
            'name': self.get_value(StateSection.IDENTITY, 'name'),
            'status': cognitive.get('status', 'unknown'),
            'stage': cognitive.get('current_stage'),
            'phase': cognitive.get('current_phase'),
            'biofeedback': bio,
            'current_task': {
                'id': task.get('current_task_id'),
                'type': task.get('current_task_type'),
                'summary': task.get('current_task_summary')
            },
            'location': self.get_value(StateSection.LOCATION, 'current_location'),
            'performance': {
                'total_actions': self.get_value(StateSection.PERFORMANCE, 'total_actions_executed', 0),
                'success_rate': self._calculate_success_rate()
            }
        }
    
    def _calculate_success_rate(self) -> float:
        """Calculate action success rate.
        
        Returns:
            Success rate as percentage
        """
        total = self.get_value(StateSection.PERFORMANCE, 'total_actions_executed', 0)
        successful = self.get_value(StateSection.PERFORMANCE, 'successful_actions', 0)
        
        if total == 0:
            return 100.0
        
        return round((successful / total) * 100, 1)
    
    def generate_status_display(self) -> str:
        """Generate human-readable status display.
        
        Returns:
            Formatted status text
        """
        # This would be called by StatusManager to generate status.txt
        # Implementation would be similar to current StatusManager.get_formatted_status()
        # but pulling all data from unified state
        pass  # Implement if needed