"""Streamlined Cognitive Loop - Three-stage architecture.

This refactored version uses a three-stage cognitive architecture:
1. Observation Stage (Perceive, Observe, Orient)
2. Decision Stage (Decide)  
3. Execution Stage (Instruct, Act)
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# Import supporting modules
from .memory import (
    MemorySystem,
    ObservationMemoryBlock, CycleStateMemoryBlock,
    FileMemoryBlock,
    Priority, MemoryType
)
from .perception import EnvironmentScanner
from .knowledge import KnowledgeManager
from .state import CyberStateManager, ExecutionStateTracker
from .actions import ActionCoordinator
from .utils import CognitiveUtils, FileManager
from .brain import BrainInterface
from .stages import ObservationStage, DecisionStage, ExecutionStage

logger = logging.getLogger("Cyber.cognitive")


class CognitiveLoop:
    """
    Streamlined cognitive processing engine using three-stage architecture.
    
    The cognitive loop is organized into three fundamental stages:
    1. Observation - Gather and understand information
    2. Decision - Choose what to do
    3. Execution - Take action
    """
    
    def __init__(self, cyber_id: str, personal: Path, 
                 max_context_tokens: int = 50000,
                 cyber_type: str = 'general'):
        """Initialize the cognitive loop with all supporting managers.
        
        Args:
            cyber_id: The Cyber's identifier
            personal: Path to Cyber's personal directory
            max_context_tokens: Maximum tokens for LLM context
            cyber_type: Type of Cyber (general, io_cyber, etc.)
        """
        self.cyber_id = cyber_id
        self.personal = Path(personal)
        self.max_context_tokens = max_context_tokens
        self.cyber_type = cyber_type
        
        # Core file interfaces - define these first
        self.brain_file = self.personal / "brain"
        self.inbox_dir = self.personal / "comms" / "inbox"
        self.outbox_dir = self.personal / "comms" / "outbox"
        self.memory_dir = self.personal / "memory"
        
        # Initialize all managers
        self._initialize_managers()
        
        # Ensure directories exist
        self.file_manager.ensure_directory(self.inbox_dir)
        self.file_manager.ensure_directory(self.outbox_dir)
        self.file_manager.ensure_directory(self.memory_dir)
        
        # Initialize state
        self.cycle_count = 0
        self.last_activity = datetime.now()
        
        # Initialize systems
        self._initialize_systems()
        
        # Initialize cognitive stages
        self.observation_stage = ObservationStage(self)
        self.decision_stage = DecisionStage(self)
        self.execution_stage = ExecutionStage(self)
    
    def _initialize_managers(self):
        """Initialize all supporting managers."""
        # Unified memory system
        self.memory_system = MemorySystem(
            filesystem_root=self.personal.parent,
            max_tokens=self.max_context_tokens
        )
        
        # Knowledge system
        self.knowledge_manager = KnowledgeManager(cyber_type=self.cyber_type)
        
        # State management
        self.state_manager = CyberStateManager(self.cyber_id, self.memory_dir)
        self.execution_tracker = ExecutionStateTracker(self.cyber_id, self.memory_dir)
        
        # Action coordination
        self.action_coordinator = ActionCoordinator(cyber_type=self.cyber_type)
        
        # Perception system
        grid_path = self.personal.parent.parent / "grid"
        self.environment_scanner = EnvironmentScanner(
            personal_path=self.personal,
            grid_path=grid_path
        )
        
        # Utilities
        self.cognitive_utils = CognitiveUtils()
        self.file_manager = FileManager()
        
        # Brain interface
        self.brain_interface = BrainInterface(self.brain_file, self.cyber_id)
    
    def _initialize_systems(self):
        """Initialize all systems and load initial data."""
        # Initialize managers
        self.state_manager.initialize()
        self.knowledge_manager.initialize()
        
        # Try to restore memory from snapshot first
        if not self.memory_system.load_from_snapshot_file(self.memory_dir, self.knowledge_manager):
            # No snapshot - load ROM and init fresh
            self.knowledge_manager.load_rom_into_memory(self.memory_system)
            self._init_cycle_state()
        
        # Load state
        existing_state = self.state_manager.load_state()
        if existing_state:
            self.cycle_count = existing_state.get("cycle_count", 0)
            logger.info(f"Resumed at cycle {self.cycle_count}")
        
        # Load execution state
        self.execution_tracker.load_execution_state()
        
        # Add identity to memory (pinned so always visible)
        self._init_identity_memory()
        
        # Ensure processed_observations.json exists and is in memory
        self._init_processed_observations()
        
        # Initialize dynamic context file
        self._init_dynamic_context()
    
    def _init_processed_observations(self):
        """Ensure processed_observations.json exists and is in memory."""
        processed_file = self.memory_dir / "processed_observations.json"
        
        # Create file if it doesn't exist
        if not processed_file.exists():
            with open(processed_file, 'w') as f:
                json.dump([], f, indent=2)
            logger.info("Created empty processed_observations.json")
        
        # Invalidate any cached version to ensure fresh content
        self.memory_system.content_loader.invalidate_file(str(processed_file))
        
        # Add to memory as pinned so Cyber always sees it
        processed_memory = FileMemoryBlock(
            location=str(processed_file),
            priority=Priority.LOW,
            confidence=1.0,
            pinned=True,  # Always in working memory
            metadata={"file_type": "processed_observations_log"}
        )
        self.memory_system.add_memory(processed_memory)
        logger.info("Added processed_observations.json to pinned memory")
    
    def _init_identity_memory(self):
        """Add Cyber identity file to working memory as pinned."""
        identity_file = self.personal / "identity.json"
        if identity_file.exists():
            identity_memory = FileMemoryBlock(
                location=str(identity_file),
                priority=Priority.LOW,  # Low priority since it's pinned
                confidence=1.0,
                pinned=True,  # Always in working memory
                metadata={"file_type": "identity", "description": "My identity and configuration"}
            )
            self.memory_system.add_memory(identity_memory)
            logger.info(f"Added identity.json to pinned memory")
        else:
            logger.warning(f"No identity.json file found at {identity_file}")
    
    def _init_dynamic_context(self):
        """Initialize and maintain dynamic context file with runtime state."""
        context_file = self.memory_dir / "dynamic_context.json"
        
        # Create or update the dynamic context
        context_data = {
            "current_time": datetime.now().isoformat(),
            "current_location": "/personal",  # Default starting location
            "cycle_count": self.cycle_count,
            "cyber_id": self.cyber_id,
            "cyber_type": self.cyber_type,
            "last_activity": datetime.now().isoformat(),
            "uptime_seconds": 0,
            "working_memory_tokens": self.max_context_tokens
        }
        
        # Write context file
        with open(context_file, 'w') as f:
            json.dump(context_data, f, indent=2)
        
        # Invalidate any cached version
        self.memory_system.content_loader.invalidate_file(str(context_file))
        
        # Add to memory as pinned so Cyber always sees current context
        context_memory = FileMemoryBlock(
            location=str(context_file),
            priority=Priority.LOW,
            confidence=1.0,
            pinned=True,  # Always in working memory
            metadata={"file_type": "dynamic_context", "description": "Current runtime context"}
        )
        self.memory_system.add_memory(context_memory)
        logger.info("Initialized dynamic_context.json")
        
        # Store reference for updates
        self.dynamic_context_file = context_file
        self.start_time = datetime.now()
    
    def _update_dynamic_context(self, **updates):
        """Update the dynamic context file with new values."""
        if not hasattr(self, 'dynamic_context_file'):
            return
            
        try:
            # Read current context
            with open(self.dynamic_context_file, 'r') as f:
                context_data = json.load(f)
            
            # Update time and uptime always
            now = datetime.now()
            context_data["current_time"] = now.isoformat()
            if hasattr(self, 'start_time'):
                uptime = (now - self.start_time).total_seconds()
                context_data["uptime_seconds"] = int(uptime)
            
            # Update cycle count
            context_data["cycle_count"] = self.cycle_count
            
            # Apply any specific updates
            for key, value in updates.items():
                context_data[key] = value
            
            # Write back
            with open(self.dynamic_context_file, 'w') as f:
                json.dump(context_data, f, indent=2)
            
            # Invalidate cache so the new content is loaded
            self.memory_system.content_loader.invalidate_file(str(self.dynamic_context_file))
                
        except Exception as e:
            logger.error(f"Failed to update dynamic context: {e}")
    
    def _init_cycle_state(self):
        """Initialize a new cycle state."""
        cycle_state = CycleStateMemoryBlock(
            cycle_state="perceive",
            cycle_count=0
        )
        self.memory_system.add_memory(cycle_state)
        self.state_manager.update_state({
            "cycle_state": "perceive",
            "cycle_count": 0
        })
        logger.info("Initialized new cycle state")
    
    async def run_cycle(self) -> bool:
        """Run one complete cognitive cycle using three-stage architecture.
        
        The cycle is organized into three fundamental stages:
        1. Observation (Perceive → Observe → Orient)
        2. Decision (Decide)
        3. Execution (Instruct → Act)
        
        Returns:
            True if something was processed, False if idle
        """
        # Start execution tracking
        self.execution_tracker.start_execution("cognitive_cycle", {
            "cycle_count": self.cycle_count,
            "cyber_type": self.cyber_type
        })
        
        try:
            logger.debug(f"Starting cycle {self.cycle_count}")
            
            # Increment cycle count
            self.cycle_count = self.state_manager.increment_cycle_count()
            
            # Update dynamic context at the start of each cycle
            self._update_dynamic_context()
            
            # Stage 1: Observation - Gather and understand information
            orientation = await self.observation_stage.run()
            
            if not orientation:
                # No observation needed attention, do maintenance
                logger.debug("😴 No work found, performing maintenance")
                await self.maintain()
                await self._save_checkpoint()
                self.execution_tracker.end_execution("idle", {"reason": "no_observations"})
                return False
            
            # Stage 2: Decision - Choose what to do
            actions = await self.decision_stage.run(orientation)
            
            if not actions:
                # No actions decided, pause briefly
                await asyncio.sleep(1.0)
                await self._save_checkpoint()
                self.execution_tracker.end_execution("completed", {"reason": "no_actions"})
                return True
            
            # Stage 3: Execution - Take action
            results = await self.execution_stage.run(actions)
            
            # Save checkpoint after completing all stages
            await self._save_checkpoint()
            
            # End execution tracking
            self.execution_tracker.end_execution("completed", {
                "stages_completed": ["observation", "decision", "execution"],
                "actions_executed": len(results)
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Error in cognitive cycle: {e}", exc_info=True)
            self.execution_tracker.end_execution("failed", {"error": str(e)})
            
            # Reset state on error
            self.state_manager.set_cycle_state("perceive")
            return False
    
    # === HELPER METHODS USED BY STAGES ===
    
    def _get_cycle_state(self) -> Optional[CycleStateMemoryBlock]:
        """Get the current cycle state from memory."""
        cycle_states = self.memory_system.get_memories_by_type(MemoryType.CYCLE_STATE)
        if cycle_states and isinstance(cycle_states[0], CycleStateMemoryBlock):
            return cycle_states[0]
        return None
    
    def _update_cycle_state(self, **kwargs):
        """Update the cycle state in memory."""
        cycle_state = self._get_cycle_state()
        if not cycle_state:
            # Create new cycle state if missing
            cycle_state = CycleStateMemoryBlock(
                cycle_state=kwargs.get('cycle_state', 'perceive'),
                cycle_count=kwargs.get('cycle_count', 0)
            )
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(cycle_state, key):
                setattr(cycle_state, key, value)
        
        # Update timestamp
        cycle_state.timestamp = datetime.now()
        
        # Add/update in memory
        self.memory_system.add_memory(cycle_state)
    
    def _record_processed_observation(self, memory_id: str, observation: Dict[str, Any]):
        """Record that an observation has been processed."""
        try:
            # Create a processed observations file in memory
            processed_file = self.memory_dir / "processed_observations.json"
            
            # Load existing records
            if processed_file.exists():
                try:
                    with open(processed_file, 'r') as f:
                        content = f.read().strip()
                        if content:
                            processed = json.loads(content)
                        else:
                            # File exists but is empty
                            processed = []
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Invalid JSON in processed_observations.json, starting fresh: {e}")
                    processed = []
            else:
                processed = []
            
            # Add new record - simplified without redundant information
            record = {
                "memory_id": memory_id,
                "processed_at": datetime.now().isoformat()
            }
            processed.append(record)
            
            # Extract type from observation for logging only
            obs_type = observation.get("observation_type", observation.get("type", "unknown"))
            logger.info(f"Recorded processed observation: {memory_id} ({obs_type})")
            
            # Keep only last 100 records to avoid unbounded growth
            if len(processed) > 100:
                processed = processed[-100:]
            
            # Write back
            with open(processed_file, 'w') as f:
                json.dump(processed, f, indent=2)
            
            logger.info(f"Wrote {len(processed)} records to processed_observations.json")
            
            # Invalidate the cache for this file so the new content is loaded
            self.memory_system.content_loader.invalidate_file(str(processed_file))
            
            # Update the FileMemoryBlock for this file so the Cyber always sees it
            # The memory manager will replace the existing one with the same ID
            processed_memory = FileMemoryBlock(
                location=str(processed_file),
                priority=Priority.LOW,
                confidence=1.0,
                pinned=True,  # Always in working memory
                metadata={"file_type": "processed_observations_log"}
            )
            self.memory_system.add_memory(processed_memory)
            
        except Exception as e:
            logger.error(f"Failed to record processed observation: {e}")
    
    def _remove_obsolete_from_processed(self, obsolete_ids: List[str]):
        """Remove obsolete observations from the processed_observations.json file."""
        try:
            processed_file = self.memory_dir / "processed_observations.json"
            
            if not processed_file.exists():
                return
            
            # Load existing records
            try:
                with open(processed_file, 'r') as f:
                    content = f.read().strip()
                    if content:
                        processed = json.loads(content)
                    else:
                        processed = []
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Invalid JSON in processed_observations.json: {e}")
                return
            
            # Filter out obsolete observations
            original_count = len(processed)
            processed = [
                record for record in processed 
                if record.get("memory_id") not in obsolete_ids
            ]
            
            removed_count = original_count - len(processed)
            if removed_count > 0:
                logger.info(f"Removed {removed_count} obsolete observations from processed_observations.json")
                
                # Write back the filtered list
                with open(processed_file, 'w') as f:
                    json.dump(processed, f, indent=2)
                
                # Invalidate the cache for this file so the new content is loaded
                self.memory_system.content_loader.invalidate_file(str(processed_file))
                
                # Update the FileMemoryBlock for this file
                processed_memory = FileMemoryBlock(
                    location=str(processed_file),
                    priority=Priority.LOW,
                    confidence=1.0,
                    pinned=True,  # Always in working memory
                    metadata={"file_type": "processed_observations_log"}
                )
                self.memory_system.add_memory(processed_memory)
            
        except Exception as e:
            logger.error(f"Failed to remove obsolete observations from processed file: {e}")
    
    # === SUPPORTING METHODS ===
    
    async def maintain(self):
        """Perform maintenance tasks when idle."""
        # Cleanup old memories
        expired = self.memory_system.cleanup_expired()
        old_observations = self.memory_system.cleanup_old_observations(max_age_seconds=1800)
        
        if expired or old_observations:
            logger.info(f"🧹 Cleaned up {expired} expired, {old_observations} old memories")
            
        # Save state periodically
        if self.cycle_count % 100 == 0:
            logger.info(f"💾 Saving checkpoint at cycle {self.cycle_count}")
            await self._save_checkpoint()
            self.execution_tracker.save_execution_state()
        elif self.cycle_count % 10 == 0:
            logger.debug(f"Idle maintenance at cycle {self.cycle_count}")
    
    async def _save_checkpoint(self):
        """Save current state and memory."""
        # Save memory snapshot
        await self.save_memory()
        
        # Save state
        self.state_manager.save_state()
    
    async def save_memory(self):
        """Save memory snapshot to disk."""
        try:
            self.memory_system.save_snapshot_to_file(self.memory_dir)
        except Exception as e:
            logger.error(f"Error saving memory: {e}")