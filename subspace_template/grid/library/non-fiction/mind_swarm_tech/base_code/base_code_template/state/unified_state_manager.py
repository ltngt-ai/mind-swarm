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
            'duty_decay_cycles': 20,  # Duty decays over time
            'duty_decay_amount': 5,   # Amount duty decreases
            'duty_completion_bonus': 20,  # Amount duty increases when CT completed
            'duty_working_increment': 2,  # Amount duty increases per cycle working on CT
            'restlessness_increment_cycles': 10,
            'restlessness_increment': 10,
            'restlessness_move_decay': 30,  # Increased from 10 to make moves more effective
            # Memory pressure configuration
            'memory_usage_factor': 0.7,  # Use 70% of available context as target
            'expected_working_memories': 50,  # Expected healthy working memory count
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
                "duty": 100,  # Starts at 100, decays over time
                "restlessness": 0,
                "memory_pressure": 0,  # Memory usage as percentage (0-100)
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
    
    
    def update_biofeedback(self, 
                          current_task: Optional[Dict[str, Any]] = None,
                          memory_stats: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
        """Update biofeedback metrics based on current state.
        
        Args:
            current_task: Current task information
            memory_stats: Memory system statistics (from memory_system.get_memory_stats())
            
        Returns:
            Updated biofeedback metrics
        """
        bio = self.state[StateSection.BIOFEEDBACK.value]
        task = self.state[StateSection.TASK.value]
        location = self.state[StateSection.LOCATION.value]
        cognitive = self.state[StateSection.COGNITIVE.value]
        
        current_cycle = cognitive["cycle_count"]
        
        # Debug logging for task tracking
        if current_task:
            # Ensure task type is set, derive from ID if needed
            if not current_task.get('task_type') and current_task.get('id'):
                current_task['task_type'] = self._get_task_type_from_id(current_task['id'])
            logger.debug(f"Biofeedback update - task: {current_task.get('id')}, type: {current_task.get('task_type')}")
        
        # Skip if same cycle
        if current_cycle <= bio["last_update_cycle"]:
            return self.get_biofeedback_stats()
        
        # Check if task has changed (including task completion where current_task becomes None)
        current_task_id = current_task['id'] if current_task else None
        prev_task_id = task["current_task_id"]
        prev_task_type = task["current_task_type"]
        
        # Update boredom based on task continuity
        if current_task_id == prev_task_id and current_task_id is not None:
            # Same task (and not None)
            bio["cycles_on_current_task"] += 1
            # Determine task type from ID
            task_type = self._get_task_type_from_id(current_task['id'])
            
            if task_type == 'community':
                # Increase duty while working on community tasks
                bio["duty"] = min(100, bio["duty"] + self.config['duty_working_increment'])
                # Community tasks don't increase boredom as much
                bio["boredom"] = min(100, bio["boredom"] + self.config['boredom_increment'] // 2)
            elif task_type == 'hobby':
                # Decrease boredom for hobby tasks
                bio["boredom"] = max(0, bio["boredom"] - self.config['boredom_increment'])
            else:
                # Increase boredom for other tasks (maintenance, etc)
                bio["boredom"] = min(100, bio["boredom"] + self.config['boredom_increment'])
        else:
            # Task changed - check if previous task was completed
            logger.info(f"Task changed from {prev_task_id} ({prev_task_type}) to {current_task_id} ({self._get_task_type_from_id(current_task_id) if current_task_id else 'none'})")
            
            # Check if the previous task was actually completed
            # Look for it in the completed directory
            if prev_task_id and prev_task_type:
                # Community tasks are in grid, personal tasks are in personal
                if prev_task_type == 'community':
                    completed_path = Path("/grid/community/tasks/completed")
                elif prev_task_type == 'maintenance':
                    completed_path = Path("/personal/.internal/tasks/completed")  # Fixed path
                else:  # hobby
                    completed_path = Path("/personal/.internal/tasks/completed")  # Fixed path
                
                logger.info(f"Checking for completed task in {completed_path}")
                if completed_path.exists():
                    # Check if the task file exists in completed directory
                    found = False
                    for completed_file in completed_path.glob(f"{prev_task_id}_*.json"):
                        # Task was completed, credit it
                        logger.info(f"Task {prev_task_id} found in completed directory at {completed_file}, crediting completion")
                        self.credit_task_completion(prev_task_id, prev_task_type)
                        found = True
                        break
                    if not found:
                        logger.info(f"Task {prev_task_id} not found in completed directory")
                else:
                    logger.warning(f"Completed directory does not exist: {completed_path}")
            
            # Update to new task
            if current_task:
                task["current_task_id"] = current_task['id']
                # Derive task type from ID
                task["current_task_type"] = self._get_task_type_from_id(current_task['id'])
                task["current_task_summary"] = current_task.get('summary')
                task["task_started_cycle"] = current_cycle
                bio["cycles_on_current_task"] = 1
                bio["boredom"] = max(0, bio["boredom"] - 20)
            else:
                # No current task
                task["current_task_id"] = None
                task["current_task_type"] = None
                task["current_task_summary"] = None
                task["task_started_cycle"] = None
                bio["cycles_on_current_task"] = 0
        
        # Update tiredness using hybrid calculation (time + memory pressure)
        if current_task and self._get_task_type_from_id(current_task['id']) == 'maintenance':
            # Gradually reduce tiredness while doing maintenance (not just on completion)
            reduction = self.config.get('tiredness_decay', 20)
            logger.info(f"Maintenance task in progress: {current_task.get('id')} - reducing tiredness by {reduction}")
            bio["tiredness"] = max(0, bio["tiredness"] - reduction)
            bio["cycles_since_maintenance"] = 0
            
            # Still update memory_pressure even during maintenance - use same token-based calculation
            if memory_stats:
                # Use actual working memory tokens from execution stage (most accurate measure)
                working_memory_tokens = memory_stats.get('last_working_memory_tokens', 0)
                max_tokens = memory_stats.get('max_tokens', 65536)  # Default to 65k standard context
                
                # Working memory is limited to half of max_context_tokens (32K out of 64K)
                working_memory_limit = max_tokens // 2
                
                # If we haven't run execution yet, fall back to memory count estimate
                if working_memory_tokens == 0:
                    # Rough estimate: assume 100 tokens per memory block
                    total_memories = memory_stats.get('total_memories', 0)
                    working_memory_tokens = total_memories * 100
                
                # Show actual percentage of working memory limit (32K) - same as non-maintenance
                if working_memory_limit > 0:
                    # Direct percentage without artificial caps or scaling
                    bio["memory_pressure"] = min(100, (working_memory_tokens / working_memory_limit) * 100)
                    logger.debug(f"Maintenance memory pressure: {working_memory_tokens}/{working_memory_limit} = {bio['memory_pressure']}%")
                else:
                    bio["memory_pressure"] = 0
        else:
            bio["cycles_since_maintenance"] += 1
            
            # Calculate hybrid tiredness
            # Time component (0-50% of tiredness)
            maintenance_interval = 100  # Expected cycles between maintenance
            time_factor = min(bio["cycles_since_maintenance"] / maintenance_interval, 1.0) * 50
            
            # Memory pressure component (0-50% of tiredness) 
            memory_pressure_factor = 0
            if memory_stats:
                # Use actual working memory tokens from execution stage (most accurate measure)
                working_memory_tokens = memory_stats.get('last_working_memory_tokens', 0)
                max_tokens = memory_stats.get('max_tokens', 65536)  # Default to 65k standard context
                
                # Working memory is limited to half of max_context_tokens (32K out of 64K)
                # This is enforced in execution_stage.py and other stages
                working_memory_limit = max_tokens // 2
                
                # If we haven't run execution yet, fall back to memory count estimate
                if working_memory_tokens == 0:
                    # Rough estimate: assume 100 tokens per memory block
                    total_memories = memory_stats.get('total_memories', 0)
                    working_memory_tokens = total_memories * 100
                
                # Use a comfortable threshold (e.g., 70% of working memory limit, not full context)
                comfortable_threshold = working_memory_limit * 0.7
                
                # Calculate pressure as ratio of current to comfortable threshold
                memory_pressure_factor = min(working_memory_tokens / comfortable_threshold, 1.0) * 50
                
                # Also update memory_pressure as a standalone biofeedback metric (0-100)
                # Show actual percentage of working memory limit (32K)
                if working_memory_limit > 0:
                    # Direct percentage without artificial caps or scaling
                    bio["memory_pressure"] = min(100, (working_memory_tokens / working_memory_limit) * 100)
                else:
                    bio["memory_pressure"] = 0
            else:
                # No memory stats at all - default to 0% pressure
                bio["memory_pressure"] = 0
            
            # Combine factors for total tiredness
            bio["tiredness"] = min(100, time_factor + memory_pressure_factor)
        
        # Update duty decay (duty decreases over time)
        cycles_since_decrement = current_cycle - bio["last_duty_decrement_cycle"]
        if cycles_since_decrement >= self.config['duty_decay_cycles']:
            decrements = cycles_since_decrement // self.config['duty_decay_cycles']
            bio["duty"] = max(0, bio["duty"] - (self.config['duty_decay_amount'] * decrements))
            bio["last_duty_decrement_cycle"] = current_cycle
        
        # Update restlessness based on location
        location_changed_cycle = location.get("location_changed_cycle", 0)
        actual_cycles_since_move = current_cycle - location_changed_cycle
        bio["cycles_since_move"] = actual_cycles_since_move
        
        # Check if we moved very recently (within last 2 cycles) and haven't already reduced restlessness
        last_restlessness_reduction = bio.get("last_restlessness_reduction_cycle", 0)
        if actual_cycles_since_move <= 1 and location_changed_cycle > last_restlessness_reduction:
            # We just moved, reduce restlessness
            bio["restlessness"] = max(0, bio["restlessness"] - self.config['restlessness_move_decay'])
            bio["last_restlessness_reduction_cycle"] = location_changed_cycle
        elif actual_cycles_since_move > 0 and actual_cycles_since_move % self.config['restlessness_increment_cycles'] == 0:
            # Only increment restlessness every N cycles, not continuously
            bio["restlessness"] = min(100, bio["restlessness"] + self.config['restlessness_increment'])
        
        bio["last_update_cycle"] = current_cycle
        
        # Check if we need to create MT-001 for memory pressure
        self._check_and_create_memory_task(bio["memory_pressure"])
        
        self.save_state()
        
        return self.get_biofeedback_stats()
    
    def _check_and_create_memory_task(self, memory_pressure: float) -> None:
        """Check if we need to create MT-001 maintenance task for memory pressure.
        
        Args:
            memory_pressure: Current memory pressure percentage
        """
        # Only create task if memory pressure > 60%
        if memory_pressure <= 60:
            return
            
        # Check if MT-001 already exists in backlog or as current task
        task_id = "MT-001"
        
        # Check current task
        current_task_id = self.state[StateSection.TASK.value].get("current_task_id")
        if current_task_id == task_id:
            return  # Already working on it
            
        # Check if task already exists in maintenance directory
        maintenance_dir = Path("/personal/.internal/tasks/maintenance")
        if maintenance_dir.exists():
            for task_file in maintenance_dir.glob(f"{task_id}_*.json"):
                logger.debug(f"MT-001 already exists in backlog at {task_file}")
                return  # Already in backlog
        
        # Check blocked directory too
        blocked_dir = Path("/personal/.internal/tasks/blocked")
        if blocked_dir.exists():
            for task_file in blocked_dir.glob(f"{task_id}_*.json"):
                logger.debug(f"MT-001 is blocked at {task_file}")
                return  # Already exists but blocked
                
        # Create MT-001 task
        logger.info(f"Memory pressure at {memory_pressure:.1f}% - creating MT-001 maintenance task")
        
        task_data = {
            "id": task_id,
            "summary": "Working memory eviction - clean up old memories",
            "description": "Memory pressure is above 60%. Review and evict old memories from working memory to reduce token usage and improve performance.",
            "task_type": "maintenance",
            "created_at": datetime.now().isoformat(),
            "created_by": "system",
            "status": "pending",
            "priority": "HIGH",
            "todo": [
                {"title": "Review current memory blocks", "status": "NOT-STARTED"},
                {"title": "Identify stale or redundant memories", "status": "NOT-STARTED"},
                {"title": "Remove low-priority expired memories", "status": "NOT-STARTED"},
                {"title": "Consolidate related memories if possible", "status": "NOT-STARTED"},
                {"title": "Verify memory pressure reduced below 60%", "status": "NOT-STARTED"}
            ],
            "context": [
                f"Memory pressure: {memory_pressure:.1f}%",
                "Target: Reduce below 60%"
            ]
        }
        
        # Write task file
        maintenance_dir.mkdir(parents=True, exist_ok=True)
        task_file = maintenance_dir / f"{task_id}_working_memory_eviction.json"
        
        try:
            with open(task_file, 'w') as f:
                import json
                json.dump(task_data, f, indent=2)
            logger.info(f"Created maintenance task {task_id} at {task_file}")
        except Exception as e:
            logger.error(f"Failed to create MT-001 task: {e}")
    
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
            'restlessness': min(100, max(0, bio['restlessness'])),
            'memory_pressure': min(100, max(0, bio.get('memory_pressure', 0)))
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
                    bio["cycles_since_maintenance"] = 0  # Reset timer so tiredness decay takes effect
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
    
    def _get_task_type_from_id(self, task_id: str) -> str:
        """Determine task type from task ID prefix.
        
        Args:
            task_id: Task identifier (e.g., MT-001, HT-002, CT-003)
            
        Returns:
            Task type (maintenance, hobby, community, general)
        """
        if not task_id:
            return "general"
            
        prefix = task_id.split('-')[0].upper() if '-' in task_id else task_id[:2].upper()
        
        type_map = {
            'MT': 'maintenance',
            'HT': 'hobby',
            'CT': 'community',
            'ST': 'system',
            'RT': 'routine',
        }
        
        return type_map.get(prefix, 'general')
    
    def set_current_task(self, task_id: str, summary: str = None) -> None:
        """Set the current task information.
        
        Args:
            task_id: Task identifier (type determined from prefix)
            summary: Task summary/description
        """
        task = self.state[StateSection.TASK.value]
        task["current_task_id"] = task_id
        
        # Automatically determine task type from ID
        task_type = self._get_task_type_from_id(task_id)
        task["current_task_type"] = task_type
        
        if summary:
            task["current_task_summary"] = summary
        task["task_started_cycle"] = self.state[StateSection.COGNITIVE.value]["cycle_count"]
        
        logger.info(f"Set current task: {task_id} (type={task_type})")
        self.save_state()
    
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