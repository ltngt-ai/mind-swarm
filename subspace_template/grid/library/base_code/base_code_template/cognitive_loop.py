"""Streamlined Cognitive Loop - Three-stage architecture.

This refactored version uses a three-stage cognitive architecture:
1. Observation Stage (Perceive, Observe, Orient)
2. Decision Stage (Decide)  
3. Execution Stage (Instruct, Act)
"""

import asyncio
import json
import logging
import mmap
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
# Removed StagePipeline - using double-buffered FileMemoryBlocks instead
from .state.goal_manager import GoalManager
from .actions import ActionCoordinator
from .actions.action_tracker import ActionTracker
from .utils import CognitiveUtils, FileManager
from .brain import BrainInterface
from .stages import ObservationStage, DecisionStage, ExecutionStage, ReflectStage

logger = logging.getLogger("Cyber.cognitive")


class CognitiveLoop:
    """
    Streamlined cognitive processing engine using three-stage architecture.
    
    The cognitive loop is organized into three fundamental stages:
    1. Observation - Gather and understand information
    2. Decision - Choose what to do
    3. Execution - Take action
    4. Reflection - Reflect on what has happened
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
        
        # Initialize state early so it's available for managers
        self.cycle_count = 0
        self.last_activity = datetime.now()
        
        # Initialize all managers
        self._initialize_managers()
        
        # Ensure directories exist
        self.file_manager.ensure_directory(self.inbox_dir)
        self.file_manager.ensure_directory(self.outbox_dir)
        self.file_manager.ensure_directory(self.memory_dir)
        
        # Initialize systems
        self._initialize_systems()
        
        # Initialize cognitive stages (4 stages now)
        self.observation_stage = ObservationStage(self)
        self.decision_stage = DecisionStage(self)
        self.execution_stage = ExecutionStage(self)
        self.reflect_stage = ReflectStage(self)
    
    def _initialize_pipeline_buffers(self):
        """Initialize pipeline memory blocks for each stage with clear current/previous naming."""
        import json
        
        # Create pipeline directory
        pipeline_dir = self.memory_dir / "pipeline"
        pipeline_dir.mkdir(parents=True, exist_ok=True)
        
        # Each stage gets current and previous buffers with clear names
        stages = ["observation", "decision", "execution", "reflect"]
        
        # Initialize buffers with clear naming
        self.pipeline_buffers = {}
        for stage in stages:
            self.pipeline_buffers[stage] = {}
            
            # Create current and previous buffer files for each stage
            for buffer_type in ["current", "previous"]:
                buffer_file = pipeline_dir / f"{buffer_type}_{stage}_pipe_stage.json"
                # Initialize with empty JSON if doesn't exist
                if not buffer_file.exists():
                    with open(buffer_file, 'w') as f:
                        json.dump({}, f)
                
                # Create FileMemoryBlock for this buffer
                # Use path relative to filesystem_root (self.personal.parent)
                buffer_memory = FileMemoryBlock(
                    location=str(buffer_file.relative_to(self.personal.parent)),
                    priority=Priority.HIGH,
                    pinned=True,  # Pipeline buffers should never be removed
                    metadata={
                        "stage": stage, 
                        "buffer_type": buffer_type, 
                        "file_type": "pipeline_buffer",
                        "description": f"{buffer_type.capitalize()} {stage} pipeline stage results"
                    },
                    cycle_count=self.cycle_count,  # When this memory was added
                    no_cache=True  # Pipeline buffers change frequently, don't cache
                )
                
                # Add to memory system
                self.memory_system.add_memory(buffer_memory)
                
                # Store reference
                self.pipeline_buffers[stage][buffer_type] = buffer_memory
    
    def _swap_pipeline_buffers(self):
        """Move current pipeline data to previous and clear current for new cycle."""
        import json
        import shutil
        
        # For each stage, move current to previous and clear current
        for stage in self.pipeline_buffers:
            current_buffer = self.pipeline_buffers[stage]["current"]
            previous_buffer = self.pipeline_buffers[stage]["previous"]
            
            # Get absolute paths
            current_file = self.personal.parent / current_buffer.location
            previous_file = self.personal.parent / previous_buffer.location
            
            # Copy current to previous (preserving any data written in last cycle)
            if current_file.exists():
                shutil.copy2(current_file, previous_file)
            
            # Clear current for new cycle
            with open(current_file, 'w') as f:
                json.dump({}, f)
            
            # Update the memory blocks' cycle_count
            # Previous gets the last cycle's count
            self.memory_system.remove_memory(previous_buffer.id)
            updated_previous = FileMemoryBlock(
                location=previous_buffer.location,
                priority=Priority.HIGH,
                pinned=True,
                metadata={
                    "stage": stage,
                    "buffer_type": "previous",
                    "file_type": "pipeline_buffer",
                    "description": f"Previous {stage} pipeline stage results"
                },
                cycle_count=max(0, self.cycle_count - 1),  # Previous cycle
                no_cache=True  # Don't cache pipeline buffers
            )
            self.memory_system.add_memory(updated_previous)
            self.pipeline_buffers[stage]["previous"] = updated_previous
            
            # Current gets this cycle's count
            self.memory_system.remove_memory(current_buffer.id)
            updated_current = FileMemoryBlock(
                location=current_buffer.location,
                priority=Priority.HIGH,
                pinned=True,
                metadata={
                    "stage": stage,
                    "buffer_type": "current", 
                    "file_type": "pipeline_buffer",
                    "description": f"Current {stage} pipeline stage results"
                },
                cycle_count=self.cycle_count,  # Current cycle
                no_cache=True  # Don't cache pipeline buffers
            )
            self.memory_system.add_memory(updated_current)
            self.pipeline_buffers[stage]["current"] = updated_current
        
        # No need to invalidate cache - pipeline buffers have no_cache=True
    
    def get_current_pipeline(self, stage: str) -> FileMemoryBlock:
        """Get the current buffer for a stage."""
        return self.pipeline_buffers[stage]["current"]
    
    def get_previous_pipeline(self, stage: str) -> FileMemoryBlock:
        """Get the previous buffer for a stage."""
        return self.pipeline_buffers[stage]["previous"]
    
    
    def _initialize_managers(self):
        """Initialize all supporting managers."""
        # Unified memory system
        self.memory_system = MemorySystem(
            filesystem_root=self.personal.parent,
            max_tokens=self.max_context_tokens
        )
        
        # Knowledge system
        self.knowledge_manager = KnowledgeManager(cyber_type=self.cyber_type)
        
        # Double-buffered pipeline using FileMemoryBlocks
        # Each stage has two buffers (0 and 1) that swap between current and previous
        self._initialize_pipeline_buffers()
        
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
        
        # Add goals and tasks files to memory if they exist
        self._add_goals_and_tasks_files()
    
    def _init_identity_memory(self):
        """Add Cyber identity file to working memory as pinned."""
        identity_file = self.personal / ".internal" / "identity.json"
        if identity_file.exists():
            identity_memory = FileMemoryBlock(
                location=str(identity_file.relative_to(self.personal.parent)),
                priority=Priority.LOW,  # Low priority since it's pinned
                confidence=1.0,
                pinned=True,  # Always in working memory
                metadata={"file_type": "identity", "description": "My identity and configuration"},
                cycle_count=self.cycle_count  # When this memory was added
            )
            self.memory_system.add_memory(identity_memory)
            logger.info(f"Added identity.json to pinned memory")
        else:
            logger.warning(f"No identity.json file found at {identity_file}")
    
    def _init_dynamic_context(self):
        """Initialize memory mapping for existing dynamic context file."""
        self.dynamic_context_file = self.memory_dir / "dynamic_context.json"
        
        # File should already exist - if not, create minimal one
        if not self.dynamic_context_file.exists():
            # Only happens on very first run of a new Cyber
            context_data = {
                "cycle_count": self.cycle_count,
                "current_stage": "STARTING",
                "current_phase": "INIT"
            }
            json_str = json.dumps(context_data, indent=2)
            json_bytes = json_str.encode('utf-8') + b'\0'
            padded_content = json_bytes.ljust(4096, b'\0')
            with open(self.dynamic_context_file, 'wb') as f:
                f.write(padded_content)
            logger.info(f"Created initial dynamic_context.json for new Cyber")
        else:
            # File exists - just verify it's the right size for memory mapping
            file_size = self.dynamic_context_file.stat().st_size
            if file_size < 4096:
                # Pad existing file to 4KB if needed
                with open(self.dynamic_context_file, 'rb') as f:
                    content = f.read()
                # Find null terminator or end of JSON
                null_pos = content.find(b'\0')
                if null_pos == -1:
                    # No null terminator, add one
                    padded_content = content.rstrip() + b'\0'
                    padded_content = padded_content.ljust(4096, b'\0')
                else:
                    # Already has null, just pad with more nulls
                    padded_content = content.ljust(4096, b'\0')
                with open(self.dynamic_context_file, 'wb') as f:
                    f.write(padded_content)
                logger.debug(f"Padded existing dynamic_context.json to 4KB")
        
        # Open existing file for memory mapping
        self.dynamic_context_fd = open(self.dynamic_context_file, 'r+b')
        self.dynamic_context_mmap = mmap.mmap(self.dynamic_context_fd.fileno(), 4096)
        
        # Add to memory as pinned so Cyber always sees current context
        self.dynamic_context_location = str(self.dynamic_context_file.relative_to(self.personal.parent))
        context_memory = FileMemoryBlock(
            location=self.dynamic_context_location,
            priority=Priority.LOW,
            confidence=1.0,
            pinned=True,  # Always in working memory
            metadata={"file_type": "dynamic_context", "description": "Current runtime context"},
            cycle_count=self.cycle_count,  # Will always match file content now
            no_cache=True  # Memory-mapped file, don't cache
        )
        self.memory_system.add_memory(context_memory)
        self.dynamic_context_memory_id = context_memory.id
        logger.info("Initialized dynamic_context.json with memory mapping")
    
    def _update_dynamic_context(self, stage=None, phase=None, **updates):
        """Update the dynamic context file with new values using memory mapping.
        
        Args:
            stage: Current stage (OBSERVATION, DECISION, EXECUTION, MAINTENANCE)
            phase: Current phase within the stage (e.g., OBSERVE, CLEANUP, DECIDE, etc.)
            **updates: Additional key-value pairs to update
        """
        if not hasattr(self, 'dynamic_context_mmap'):
            return
            
        try:
            # Read current data from memory-mapped file
            self.dynamic_context_mmap.seek(0)
            content_bytes = self.dynamic_context_mmap.read(4096)
            
            # Find null terminator to get actual JSON content
            null_pos = content_bytes.find(b'\0')
            if null_pos != -1:
                json_content = content_bytes[:null_pos].decode('utf-8')
            else:
                # No null terminator, try to parse what we have
                json_content = content_bytes.decode('utf-8').rstrip()
            
            # Parse JSON
            try:
                context_data = json.loads(json_content)
            except json.JSONDecodeError:
                # If corrupted, reset to defaults
                context_data = {
                    "cycle_count": self.cycle_count,
                    "current_stage": "ERROR_RECOVERY",
                    "current_phase": "RESET"
                }
            
            # Update cycle count - this is the key change
            context_data["cycle_count"] = self.cycle_count
            
            # Update stage and phase if provided
            if stage:
                context_data["current_stage"] = stage
            if phase:
                context_data["current_phase"] = phase
            
            # Apply any specific updates
            for key, value in updates.items():
                context_data[key] = value
            
            # Write back to memory-mapped file
            json_str = json.dumps(context_data, indent=2)
            if len(json_str) > 4095:  # Leave room for null terminator
                logger.warning("Dynamic context exceeds 4KB, truncating")
                json_str = json_str[:4095]
            
            # Add null terminator and pad the rest with nulls
            json_bytes = json_str.encode('utf-8') + b'\0'
            padded_content = json_bytes.ljust(4096, b'\0')
            
            # Write to memory map
            self.dynamic_context_mmap.seek(0)
            self.dynamic_context_mmap.write(padded_content)
            self.dynamic_context_mmap.flush()  # Force write to disk
            
            # Touch the memory block so it knows the file was updated
            if hasattr(self, 'dynamic_context_memory_id'):
                self.memory_system.touch_memory(self.dynamic_context_memory_id, self.cycle_count)
            
        except Exception as e:
            logger.error(f"Failed to update dynamic context: {e}")
    
    def _ensure_goals_and_tasks_in_memory(self):
        """Ensure goals and tasks files are in memory if they exist and have content.
        
        This is called each cycle to handle files created after initialization.
        """
        # Check goals.json
        goals_file = self.memory_dir / "goals.json"
        goals_memory_id = f"memory:{goals_file.relative_to(self.personal.parent)}"
        
        # Check if it exists, has content, and isn't already in memory
        if goals_file.exists() and goals_file.stat().st_size > 50:  # More than just empty JSON
            # Check if already in memory
            already_in_memory = any(
                m.id == goals_memory_id 
                for m in self.memory_system.symbolic_memory
            )
            if not already_in_memory:
                goals_memory = FileMemoryBlock(
                    location=str(goals_file.relative_to(self.personal.parent)),
                    priority=Priority.HIGH,
                    confidence=1.0,
                    pinned=True,
                    metadata={
                        "file_type": "goals",
                        "description": "My goals and objectives. Goals are high-level, long-term objectives that define WHY I do things."
                    },
                    cycle_count=self.cycle_count
                )
                self.memory_system.add_memory(goals_memory)
                logger.info(f"Added goals.json to pinned memory at cycle {self.cycle_count}")
        
        # Check active_tasks.json
        tasks_file = self.memory_dir / "active_tasks.json"
        tasks_memory_id = f"memory:{tasks_file.relative_to(self.personal.parent)}"
        
        # Check if it exists, has content, and isn't already in memory
        if tasks_file.exists() and tasks_file.stat().st_size > 50:  # More than just empty JSON
            # Check if already in memory
            already_in_memory = any(
                m.id == tasks_memory_id 
                for m in self.memory_system.symbolic_memory
            )
            if not already_in_memory:
                tasks_memory = FileMemoryBlock(
                    location=str(tasks_file.relative_to(self.personal.parent)),
                    priority=Priority.HIGH,
                    confidence=1.0,
                    pinned=True,
                    metadata={
                        "file_type": "tasks",
                        "description": "My active tasks. Tasks are specific, actionable items that define WHAT to do and can be completed in a few cycles."
                    },
                    cycle_count=self.cycle_count
                )
                self.memory_system.add_memory(tasks_memory)
                logger.info(f"Added active_tasks.json to pinned memory at cycle {self.cycle_count}")
    
    def _add_goals_and_tasks_files(self):
        """Add goals and tasks JSON files to memory as pinned FileMemoryBlocks.
        
        This makes the goal and task data visible to the Cyber without complexity.
        Just calls the ensure method for initial setup.
        """
        self._ensure_goals_and_tasks_in_memory()
    
    
    async def run_cycle(self) -> bool:
        """Run one complete cognitive cycle using four-stage architecture.

        The cycle is organized into four fundamental stages:
        1. Observation (Perceive → Observe → Orient)
        2. Decision (Decide)
        3. Execution (Instruct → Act)
        4. Reflection (Review → Learn)

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
            
            # Swap pipeline buffers at start of new cycle
            if self.cycle_count > 0:  # Don't swap on first cycle
                self._swap_pipeline_buffers()
            
            # Update dynamic context at the start of each cycle
            self._update_dynamic_context(stage="STARTING", phase="INIT")
            
            # Check if goals/tasks files need to be added to memory
            # (they might have been created after initialization)
            self._ensure_goals_and_tasks_in_memory()
            
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
            actions = await self.decision_stage.run()
            
            if not actions:
                # No actions decided, pause briefly
                await asyncio.sleep(1.0)
                await self._save_checkpoint()
                self.execution_tracker.end_execution("completed", {"reason": "no_actions"})
                return True
            
            # Stage 3: Execution - Take action
            self._update_dynamic_context(stage="EXECUTION", phase="STARTING")
            results = await self.execution_stage.run()
            
            # Stage 4: Reflect - Review what just happened
            self._update_dynamic_context(stage="REFLECT", phase="STARTING")
            await self.reflect_stage.run()
            
            # Save checkpoint after completing all stages
            await self._save_checkpoint()
            
            # End execution tracking
            self.execution_tracker.end_execution("completed", {
                "stages_completed": ["observation", "decision", "execution", "reflect"],
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
    
    def cleanup(self):
        """Clean up resources including memory-mapped files."""
        try:
            if hasattr(self, 'dynamic_context_mmap'):
                self.dynamic_context_mmap.close()
            if hasattr(self, 'dynamic_context_fd'):
                self.dynamic_context_fd.close()
            logger.info("Cleaned up memory-mapped resources")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")