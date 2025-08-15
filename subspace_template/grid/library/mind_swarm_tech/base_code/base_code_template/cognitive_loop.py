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
from .utils import CognitiveUtils, FileManager
from .brain import BrainInterface
from .stages import ObservationStage, ReflectStage, DecisionStage, ExecutionStage

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
        self.brain_file = self.personal / ".internal" / "brain"
        self.inbox_dir = self.personal / "inbox"
        self.outbox_dir = self.personal / "outbox"
        self.memory_dir = self.personal / ".internal" / "memory"
        
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
        self.decision_stage = DecisionStage(self)  # This is now V2
        self.execution_stage = ExecutionStage(self)  # This is now V2
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
                    priority=Priority.SYSTEM,  # System-controlled memory
                    pinned=True,  # Pipeline buffers should never be removed
                    metadata={
                        "stage": stage, 
                        "buffer_type": buffer_type, 
                        "file_type": "pipeline_buffer",
                        "description": f"{buffer_type.capitalize()} {stage} pipeline stage results"
                    },
                    cycle_count=self.cycle_count,  # When this memory was added
                    no_cache=True,  # Pipeline buffers change frequently, don't cache
                    block_type=MemoryType.SYSTEM  # Mark as system memory
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
                priority=Priority.SYSTEM,  # System-controlled memory
                pinned=True,
                metadata={
                    "stage": stage,
                    "buffer_type": "previous",
                    "file_type": "pipeline_buffer",
                    "description": f"Previous {stage} pipeline stage results"
                },
                cycle_count=max(0, self.cycle_count - 1),  # Previous cycle
                no_cache=True,  # Don't cache pipeline buffers
                block_type=MemoryType.SYSTEM  # Mark as system memory
            )
            self.memory_system.add_memory(updated_previous)
            self.pipeline_buffers[stage]["previous"] = updated_previous
            
            # Current gets this cycle's count
            self.memory_system.remove_memory(current_buffer.id)
            updated_current = FileMemoryBlock(
                location=current_buffer.location,
                priority=Priority.SYSTEM,  # System-controlled memory
                pinned=True,
                metadata={
                    "stage": stage,
                    "buffer_type": "current", 
                    "file_type": "pipeline_buffer",
                    "description": f"Current {stage} pipeline stage results"
                },
                cycle_count=self.cycle_count,  # Current cycle
                no_cache=True,  # Don't cache pipeline buffers
                block_type=MemoryType.SYSTEM  # Mark as system memory
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
        
        # State management
        self.state_manager = CyberStateManager(self.cyber_id, self.memory_dir)
        self.execution_tracker = ExecutionStateTracker(self.cyber_id, self.memory_dir)
        
        # V2 doesn't need action system - actions are Python functions in scripts
        # self.action_tracker = ActionTracker()
        
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
        self.brain_interface = BrainInterface(self.brain_file, self.cyber_id, self.personal)
    
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
                priority=Priority.SYSTEM,  # System-controlled identity
                confidence=1.0,
                pinned=True,  # Always in working memory
                metadata={"file_type": "identity", "description": "My identity and configuration"},
                cycle_count=self.cycle_count,  # When this memory was added
                block_type=MemoryType.SYSTEM  # Mark as system memory
            )
            self.memory_system.add_memory(identity_memory)
            logger.info(f"Added identity.json to pinned memory")
        else:
            logger.warning(f"No identity.json file found at {identity_file}")
    
    def _init_dynamic_context(self):
        """Initialize dynamic context file."""
        self.dynamic_context_file = self.memory_dir / "dynamic_context.json"
        
        # File should already exist - if not, create minimal one
        if not self.dynamic_context_file.exists():
            # Only happens on very first run of a new Cyber
            context_data = {
                "cycle_count": self.cycle_count,
                "current_stage": "STARTING",
                "current_phase": "INIT",
                "current_location": "/grid/library/knowledge/sections/new_cyber_introduction"  # Starting location for new Cybers
            }
            with open(self.dynamic_context_file, 'w') as f:
                json.dump(context_data, f, indent=2)
            logger.info(f"Created initial dynamic_context.json for new Cyber")
        
        # Add to memory as pinned so Cyber always sees current context
        self.dynamic_context_location = str(self.dynamic_context_file.relative_to(self.personal.parent))
        context_memory = FileMemoryBlock(
            location=self.dynamic_context_location,
            priority=Priority.SYSTEM,  # System-controlled runtime context
            confidence=1.0,
            pinned=True,  # Always in working memory
            metadata={"file_type": "dynamic_context", "description": "Current runtime context"},
            cycle_count=self.cycle_count,  # Will always match file content now
            no_cache=True,  # Don't cache, always read from disk
            block_type=MemoryType.SYSTEM  # Mark as system memory
        )
        self.memory_system.add_memory(context_memory)
        self.dynamic_context_memory_id = context_memory.id
        logger.info("Initialized dynamic_context.json")
    
    def get_dynamic_context(self) -> Dict[str, Any]:
        """Get the current dynamic context from file.
        
        Returns:
            Dictionary containing the current dynamic context
        """
        if not hasattr(self, 'dynamic_context_file'):
            logger.error("Dynamic context file not initialized!")
            return {}
        
        try:
            # Read current data from file
            with open(self.dynamic_context_file, 'r') as f:
                return json.load(f)
            
        except Exception as e:
            logger.error(f"Error reading dynamic context: {e}")
            return {}
    
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
            # Read current data from file
            try:
                with open(self.dynamic_context_file, 'r') as f:
                    context_data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                # If corrupted or missing, reset to defaults
                context_data = {
                    "cycle_count": self.cycle_count,
                    "current_stage": "ERROR_RECOVERY",
                    "current_phase": "RESET",
                    "current_location": "/grid/library/knowledge/sections/new_cyber_introduction"
                }
            
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
            
            # Write back to file
            with open(self.dynamic_context_file, 'w') as f:
                json.dump(context_data, f, indent=2)
            
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
            
            # Stage 5: Cleanup - Clean up obsolete memories and maintain system
            self._update_dynamic_context(stage="CLEANUP", phase="STARTING")
            await self.cleanup()
            
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
    
    async def cleanup(self):
        """Perform memory cleanup and system maintenance.
        
        This is called at the end of every cognitive cycle to:
        1. Clean up obsolete observations
        2. Remove expired memories
        3. Manage memory budget
        4. Perform other maintenance tasks
        """
        logger.debug(f"Starting cleanup for cycle {self.cycle_count}")
        
        # Get context for intelligent cleanup decisions
        from .memory.tag_filter import TagFilter
        memory_context = self.memory_system.build_context(
            max_tokens=self.max_context_tokens // 4,  # Smaller context for cleanup
            current_task="Identifying obsolete memories and observations for cleanup",
            selection_strategy="recent",
            tag_filter=TagFilter(blacklist={"action_guide", "action_implementation", "execution", "procedures", "tools"}),
            exclude_types=[]
        )
        
        logger.debug(f"Built cleanup context with {len(memory_context)} chars")
        
        # Use brain to identify what to clean up
        logger.debug("Calling _identify_cleanup_targets...")
        cleanup_decisions = await self._identify_cleanup_targets(memory_context)
        logger.debug(f"Cleanup decisions: {cleanup_decisions}")
        
        if cleanup_decisions:
            # Clean up identified obsolete observations
            obsolete_observations = cleanup_decisions.get("obsolete_observations", [])
            for obs_id in obsolete_observations:
                if self.memory_system.remove_memory(obs_id):
                    logger.debug(f"🧹 Removed obsolete observation: {obs_id}")
            
            # Clean up identified obsolete memory blocks
            obsolete_memories = cleanup_decisions.get("obsolete_memories", [])
            for mem_id in obsolete_memories:
                if self.memory_system.remove_memory(mem_id):
                    logger.debug(f"🧹 Removed obsolete memory: {mem_id}")
        
        # Also do automatic cleanup of expired memories
        expired = self.memory_system.cleanup_expired()
        old_observations = self.memory_system.cleanup_old_observations(max_age_seconds=1800)
        
        if expired or old_observations:
            logger.info(f"🧹 Cleaned up {expired} expired, {old_observations} old memories")
        
        # Clean up old script execution files
        script_files_cleaned = await self._cleanup_old_script_executions()
        if script_files_cleaned > 0:
            logger.info(f"🧹 Cleaned up {script_files_cleaned} old script execution files")
        
        # Log cleanup completion
        if cleanup_decisions or expired or old_observations or script_files_cleaned:
            logger.info(f"✨ Cleanup completed for cycle {self.cycle_count}")
    
    async def _cleanup_old_script_executions(self, max_age_minutes: int = 30, keep_recent: int = 10) -> int:
        """Clean up old script execution files from action_results directory.
        
        Args:
            max_age_minutes: Maximum age in minutes before files are eligible for cleanup
            keep_recent: Always keep at least this many recent files
            
        Returns:
            Number of files cleaned up
        """
        import time
        from pathlib import Path
        
        action_results_dir = self.memory_dir / "action_results"
        if not action_results_dir.exists():
            return 0
        
        # Get all script execution files
        script_files = list(action_results_dir.glob("script_execution_*.json"))
        if len(script_files) <= keep_recent:
            return 0  # Don't clean up if we have fewer than the minimum to keep
        
        # Sort by modification time (newest first)
        script_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        # Always keep the most recent files
        files_to_check = script_files[keep_recent:]
        
        current_time = time.time()
        max_age_seconds = max_age_minutes * 60
        cleaned_count = 0
        
        for file_path in files_to_check:
            try:
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    # Remove associated memory if it exists
                    memory_id = f"memory:{file_path.relative_to(self.personal.parent)}"
                    if self.memory_system.remove_memory(memory_id):
                        logger.debug(f"Removed memory for old script execution: {memory_id}")
                    
                    # Delete the file
                    file_path.unlink()
                    cleaned_count += 1
                    logger.debug(f"Deleted old script execution file: {file_path.name}")
            except Exception as e:
                logger.error(f"Error cleaning up script file {file_path}: {e}")
        
        return cleaned_count
    
    async def _identify_cleanup_targets(self, memory_context: str) -> Optional[Dict[str, Any]]:
        """Use brain to identify what needs cleanup.
        
        Args:
            memory_context: Working memory context for cleanup decisions
            
        Returns:
            Dict with cleanup targets or None
        """
        import time
        
        logger.debug("_identify_cleanup_targets called")
        
        thinking_request = {
            "signature": {
                "instruction": """
Review your working memory to identify items that can be cleaned up.
Each memory has a cycle_count showing when it was created.
Look for:
1. Old observations from many cycles ago that are no longer relevant
2. Duplicate observations about the same thing
3. Action results that have been superseded by newer results
4. Observations about things that have already been handled
5. Memory blocks for files that no longer exist (e.g., old outbox messages that were moved)
6. Temporary memory blocks that are no longer needed
7. Completed tasks that don't need to be tracked anymore

Be conservative - only mark items as obsolete if you're certain they're no longer needed.
Current cycle count is in your working memory.
Always start your output with [[ ## reasoning ## ]]
""",
                "inputs": {
                    "working_memory": "Your working memory with all items including their cycle counts"
                },
                "outputs": {
                    "reasoning": "Why these items can be cleaned up",
                    "obsolete_observations": "JSON array of observation IDs that are obsolete and can be removed, e.g. [\"observation:personal/action_result/old:cycle_5\"]",
                    "obsolete_memories": "JSON array of memory IDs that are obsolete and can be removed, e.g. [\"memory:personal/outbox/msg_Alice_20250814_132424_7715.json\"]"
                },
                "display_field": "reasoning"
            },
            "input_values": {
                "working_memory": memory_context
            },
            "request_id": f"cleanup_{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        logger.debug(f"Sending cleanup brain request with ID: {thinking_request['request_id']}")
        response = await self.brain_interface._use_brain(json.dumps(thinking_request))
        logger.debug(f"Got cleanup brain response: {response[:200] if response else 'None'}")
        result = json.loads(response)
        
        output_values = result.get("output_values", {})
        
        # Parse the JSON arrays from strings if needed
        obsolete_obs_json = output_values.get("obsolete_observations", "[]")
        obsolete_mem_json = output_values.get("obsolete_memories", "[]")
        
        try:
            if isinstance(obsolete_obs_json, str):
                obsolete_observations = json.loads(obsolete_obs_json)
            else:
                obsolete_observations = obsolete_obs_json
        except:
            obsolete_observations = []
        
        try:
            if isinstance(obsolete_mem_json, str):
                obsolete_memories = json.loads(obsolete_mem_json)
            else:
                obsolete_memories = obsolete_mem_json
        except:
            obsolete_memories = []
        
        # Return None if nothing to clean up
        if not obsolete_observations and not obsolete_memories:
            return None
            
        return {
            "obsolete_observations": obsolete_observations,
            "obsolete_memories": obsolete_memories
        }
    
    async def maintain(self):
        """Perform maintenance tasks when idle.
        
        This is called when the cyber has no work to do.
        Note: Regular cleanup is now done at the end of each cycle.
        """
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
