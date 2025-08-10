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
    ObservationMemoryBlock,
    FileMemoryBlock,
    Priority, MemoryType
)
from .perception import EnvironmentScanner
from .knowledge import KnowledgeManager
from .state import CyberStateManager, ExecutionStateTracker
from .state.stage_pipeline import StagePipeline
from .state.goal_manager import GoalManager
from .actions import ActionCoordinator
from .actions.action_tracker import ActionTracker
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
        
        # Stage pipeline for information flow
        self.stage_pipeline = StagePipeline(self.memory_dir)
        
        # Goal manager for persistent objectives
        self.goal_manager = GoalManager(self.memory_dir)
        
        # State management
        self.state_manager = CyberStateManager(self.cyber_id, self.memory_dir)
        self.execution_tracker = ExecutionStateTracker(self.cyber_id, self.memory_dir)
        
        # Action coordination
        self.action_tracker = ActionTracker()
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
        
        # Load state
        existing_state = self.state_manager.load_state()
        if existing_state:
            self.cycle_count = existing_state.get("cycle_count", 0)
            logger.info(f"Resumed at cycle {self.cycle_count}")
        
        # Load execution state
        self.execution_tracker.load_execution_state()
        
        # Add identity to memory (pinned so always visible)
        self._init_identity_memory()
        
        # Initialize dynamic context file
        self._init_dynamic_context()
    
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
    
    def _update_dynamic_context(self, stage=None, phase=None, **updates):
        """Update the dynamic context file with new values.
        
        Args:
            stage: Current stage (OBSERVATION, DECISION, EXECUTION, MAINTENANCE)
            phase: Current phase within the stage (e.g., OBSERVE, CLEANUP, DECIDE, etc.)
            **updates: Additional key-value pairs to update
        """
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
            
            # Update stage and phase if provided
            if stage:
                context_data["current_stage"] = stage
            if phase:
                context_data["current_phase"] = phase
            
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
            
            # Start new pipeline cycle
            self.stage_pipeline.start_new_cycle(self.cycle_count)
            
            # Update dynamic context at the start of each cycle
            self._update_dynamic_context(stage="STARTING", phase="INIT")
            
            # Stage 1: Observation - Gather and understand information
            self._update_dynamic_context(stage="OBSERVATION", phase="STARTING")
            orientation = await self.observation_stage.run()
            
            if not orientation:
                # No observation needed attention, do maintenance
                logger.debug("😴 No work found, performing maintenance")
                self._update_dynamic_context(stage="MAINTENANCE", phase="IDLE")
                await self.maintain()
                await self._save_checkpoint()
                self.execution_tracker.end_execution("idle", {"reason": "no_observations"})
                return False
            
            # Stage 2: Decision - Choose what to do
            self._update_dynamic_context(stage="DECISION", phase="STARTING")
            actions = await self.decision_stage.run(orientation)
            
            if not actions:
                # No actions decided, pause briefly
                await asyncio.sleep(1.0)
                await self._save_checkpoint()
                self.execution_tracker.end_execution("completed", {"reason": "no_actions"})
                return True
            
            # Stage 3: Execution - Take action
            self._update_dynamic_context(stage="EXECUTION", phase="STARTING")
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
            
            # Reset context on error
            self._update_dynamic_context(stage="ERROR_RECOVERY", phase="RESET")
            return False
    
    # === HELPER METHODS USED BY STAGES ===
    
    
    
    
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