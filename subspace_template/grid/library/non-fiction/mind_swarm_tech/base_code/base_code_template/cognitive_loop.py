"""Cognitive Loop - Five-stage architecture.

This refactored version uses a five-stage cognitive architecture:
1. Observation Stage)
2. Decision Stage
3. Execution Stage
4. Reflection Stage
5. Cleanup Stage
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

# Import supporting modules
from .memory import (
    MemorySystem,
    Priority, ContentType
)
from .memory.memory_blocks import MemoryBlock
from .perception import EnvironmentScanner
from .knowledge.simplified_knowledge import SimplifiedKnowledgeManager
from .state import UnifiedStateManager, StateSection, ExecutionStateTracker
from .utils import CognitiveUtils, FileManager
from .brain import BrainInterface
from .stages import ObservationStage, ReflectStage, DecisionStage, ExecutionStage
from .cycle_recorder_client import get_cycle_recorder

logger = logging.getLogger("Cyber.cognitive")


class CognitiveLoop:
    """
    Streamlined cognitive processing engine using five-stage architecture.

    The cognitive loop is organized into five fundamental stages:
    1. Observation - Gather and understand information
    2. Decision - Choose what to do
    3. Execution - Take action
    4. Reflection - Reflect on what has happened
    5. Cleanup - See what memories aren't needed to conserve working memory space
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
        self.outbox_dir = self.personal / ".internal" / "outbox"
        self.memory_dir = self.personal / ".internal" / "memory"
        
        # Initialize state early so it's available for managers
        self.cycle_count = 0
        self.last_activity = datetime.now()
        
        # Initialize all managers
        self._initialize_managers()
        
        # Ensure directories exist
        self.file_manager.ensure_directory(self.inbox_dir)
        self.file_manager.ensure_directory(self.memory_dir)
        
        # Initialize systems
        self._initialize_systems()
        
        # Initialize cognitive stages (4 stages now)
        self.observation_stage = ObservationStage(self)
        self.decision_stage = DecisionStage(self)
        self.execution_stage = ExecutionStage(self)
        self.reflect_stage = ReflectStage(self)
        
        # Initialize cycle recorder
        self.cycle_recorder = get_cycle_recorder(cyber_id, personal)
    
    @property
    def cycle(self):
        """Get current cycle count (for compatibility with status module)."""
        return self.cycle_count
    
    def _initialize_pipeline_buffers(self):
        """Initialize pipeline memory blocks for each stage."""
        import json
        
        # Create pipeline directory
        pipeline_dir = self.memory_dir / "pipeline"
        pipeline_dir.mkdir(parents=True, exist_ok=True)
        
        # Each stage gets a single current buffer (except reflect which uses reflection_on_last_cycle)
        stages = ["observation", "decision", "execution"]
        
        # Initialize buffers
        self.pipeline_buffers = {}
        for stage in stages:
            # Create current buffer file for each stage
            buffer_file = pipeline_dir / f"{stage}_pipe_stage.json"
            # Initialize with empty JSON if doesn't exist
            if not buffer_file.exists():
                with open(buffer_file, 'w') as f:
                    json.dump({}, f)
            
            # Create MemoryBlock for this buffer
            # Use sandbox path directly
            buffer_memory = MemoryBlock(
                location=f"personal/.internal/memory/pipeline/{stage}_pipe_stage.json",
                priority=Priority.SYSTEM,  # System-controlled memory
                pinned=True,  # Pipeline buffers should never be removed
                metadata={
                    "stage": stage, 
                    "file_type": "pipeline_buffer",
                    "description": f"Current {stage} pipeline stage results"
                },
                cycle_count=self.cycle_count,  # When this memory was added
                no_cache=True,  # Pipeline buffers change frequently, don't cache
                content_type=ContentType.APPLICATION_JSON  # System JSON file
            )
            
            # Add to memory system
            self.memory_system.add_memory(buffer_memory)
            
            # Store reference
            self.pipeline_buffers[stage] = buffer_memory
    
    def _clear_pipeline_buffers(self):
        """Clear pipeline buffers for new cycle."""
        import json
        
        # Clear each stage's buffer for the new cycle
        for stage, buffer_memory in self.pipeline_buffers.items():
            # Get absolute path
            buffer_file = self.personal.parent / buffer_memory.location
            
            # Clear buffer for new cycle
            with open(buffer_file, 'w') as f:
                json.dump({}, f)
            
            # Update the memory block's cycle_count
            self.memory_system.remove_memory(buffer_memory.id)
            updated_buffer = MemoryBlock(
                location=buffer_memory.location,
                priority=Priority.SYSTEM,  # System-controlled memory
                pinned=True,
                metadata={
                    "stage": stage,
                    "file_type": "pipeline_buffer",
                    "description": f"Current {stage} pipeline stage results"
                },
                cycle_count=self.cycle_count,  # Current cycle
                no_cache=True,  # Don't cache pipeline buffers
                content_type=ContentType.APPLICATION_JSON  # System JSON file
            )
            self.memory_system.add_memory(updated_buffer)
            self.pipeline_buffers[stage] = updated_buffer
    
    def get_current_pipeline(self, stage: str) -> MemoryBlock:
        """Get the current buffer for a stage."""
        return self.pipeline_buffers[stage]
    
    
    def _initialize_managers(self):
        """Initialize all supporting managers."""
        # Unified memory system
        self.memory_system = MemorySystem(
            filesystem_root=self.personal.parent,
            max_tokens=self.max_context_tokens
        )
        
        # Knowledge system
        self.knowledge_manager = SimplifiedKnowledgeManager()
        
        # Pipeline using MemoryBlocks
        # Each stage has a single buffer that gets cleared each cycle
        self._initialize_pipeline_buffers()
        
        # State management - using new unified state manager
        self.state_manager = UnifiedStateManager(self.cyber_id, self.memory_dir)
        self.execution_tracker = ExecutionStateTracker(self.cyber_id, self.memory_dir)
                
        # Perception system
        grid_path = self.personal.parent.parent / "grid"
        self.environment_scanner = EnvironmentScanner(
            personal_path=self.personal,
            grid_path=grid_path,
            memory_system=self.memory_system
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
        
        # Try to restore memory from snapshot FIRST
        self.memory_system.load_from_snapshot_file(self.memory_dir, None)
        
        # Always load boot ROM as a pinned memory (will replace if exists)
        # The boot ROM is fundamental identity that should always be present
        boot_rom = self.knowledge_manager.get_boot_rom()
        if boot_rom:
            # Create a pinned memory for the boot ROM
            # Include all metadata fields for knowledge validation
            metadata = boot_rom.copy()  # Include all fields from boot ROM
            boot_memory = MemoryBlock(
                location="/personal/.internal/boot_rom.yaml",
                confidence=1.0,
                priority=Priority.FOUNDATIONAL,
                metadata=metadata,
                pinned=True,
                cycle_count=0,
                content_type=ContentType.MINDSWARM_KNOWLEDGE
            )
            # Remove old boot ROM if exists (by ID)
            boot_rom_id = boot_memory.id
            self.memory_system.remove_memory(boot_rom_id)  # Safe to call even if doesn't exist
            # Add the fresh boot ROM
            self.memory_system.add_memory(boot_memory)
            logger.info("Loaded boot ROM into working memory")
        
        # Load state
        existing_state = self.state_manager.load_state()
        if existing_state:
            self.cycle_count = existing_state.get("cycle_count", 0)
            logger.info(f"Resumed at cycle {self.cycle_count}")
        
        # Load execution state
        self.execution_tracker.load_execution_state()
                
        # Initialize dynamic context file
        self._init_dynamic_context()
        
        # Add location files to memory
        self._init_location_memory()
        
        # Add reflection file if it exists from a previous run
        self._ensure_reflection_in_memory()
    
    def _init_identity_memory(self):
        """Add Cyber identity file to working memory as pinned."""
        # REMOVED: identity.json content is now included in status.txt to save token space
        # The identity information (name, type, capabilities) is shown at the top of status.txt
        identity_file = self.personal / ".internal" / "identity.json"
        if not identity_file.exists():
            logger.warning(f"No identity.json file found at {identity_file}")
        # No longer adding identity.json as a separate memory block
    
    def _init_dynamic_context(self):
        """Initialize dynamic context in unified state."""
        # Dynamic context is now managed through UnifiedStateManager
        # Set initial values if this is a new Cyber
        if self.state_manager.get_value(StateSection.COGNITIVE, "cycle_count") == 0:
            # First run of a new Cyber
            self.state_manager.set_value(StateSection.COGNITIVE, "current_stage", "STARTING", save=False)
            self.state_manager.set_value(StateSection.COGNITIVE, "current_phase", "INIT", save=False)
            self.state_manager.update_location("/grid/community/school/onboarding/new_cyber_introduction")
            logger.info(f"Initialized dynamic context for new Cyber")
        
        logger.info("Dynamic context managed through unified state")
    
    def _init_location_memory(self):
        """Add location tracking files to memory."""
        self._ensure_location_files_in_memory()
    
    
    def _ensure_location_files_in_memory(self):
        """Ensure location files are in memory, creating them if needed."""
        # Create/update current_location.txt
        current_location_file = self.memory_dir / "current_location.txt"
        current_location_id = "memory:personal/.internal/memory/current_location.txt"
        
        # Create the file if it doesn't exist
        if not current_location_file.exists():
            # Get current location from unified state or use default
            current_loc = self.state_manager.get_value(StateSection.LOCATION, "current_location", "/personal")
            
            # Create basic location file content
            current_location_file.write_text(f"| {current_loc} (📁=memory group, 📄=memory)\n")
            logger.info(f"Created current_location.txt with location: {current_loc}")
        
        if current_location_file.exists():
            # Check if already in memory
            existing_memory = self.memory_system.get_memory(current_location_id)
            if existing_memory:
                # Update the cycle count to keep it fresh
                self.memory_system.touch_memory(current_location_id, self.cycle_count)
            else:
                current_location_memory = MemoryBlock(
                    location="personal/.internal/memory/current_location.txt",
                    priority=Priority.SYSTEM,  # System-controlled location tracking
                    confidence=1.0,
                    pinned=True,  # Always visible
                    metadata={"file_type": "location", "description": "My current location in the grid"},
                    cycle_count=self.cycle_count,
                    no_cache=True,  # Always read fresh
                    content_type=ContentType.TEXT_PLAIN  # Plain text location file
                )
                self.memory_system.add_memory(current_location_memory)
                logger.info(f"Added current_location.txt to pinned memory with id: {current_location_memory.id}")
            
    def get_dynamic_context(self) -> Dict[str, Any]:
        """Get the current dynamic context from unified state.
        
        Returns:
            Dictionary containing the current dynamic context
        """
        try:
            return {
                "cycle_count": self.state_manager.get_value(StateSection.COGNITIVE, "cycle_count", 0),
                "current_stage": self.state_manager.get_value(StateSection.COGNITIVE, "current_stage", "INIT"),
                "current_phase": self.state_manager.get_value(StateSection.COGNITIVE, "current_phase", "STARTING"),
                "current_location": self.state_manager.get_value(StateSection.LOCATION, "current_location", "/personal"),
                "previous_location": self.state_manager.get_value(StateSection.LOCATION, "previous_location", None)
            }
        except Exception as e:
            logger.error(f"Error reading dynamic context from state: {e}")
            return {}
    
    def _update_dynamic_context(self, stage=None, phase=None, **updates):
        """Update the dynamic context with new values.
        
        Uses UnifiedStateManager for all state management.
        
        Args:
            stage: Current stage (OBSERVATION, DECISION, EXECUTION, MAINTENANCE)
            phase: Current phase within the stage (e.g., OBSERVE, DECIDE, etc.)
            **updates: Additional key-value pairs to update
        """
        try:
            # Update unified state
            if stage:
                self.state_manager.set_value(StateSection.COGNITIVE, "current_stage", stage, save=False)
            if phase:
                self.state_manager.set_value(StateSection.COGNITIVE, "current_phase", phase, save=False)
            
            # Update cycle count in state
            self.state_manager.set_value(StateSection.COGNITIVE, "cycle_count", self.cycle_count, save=False)
            
            # Handle location updates
            if "current_location" in updates:
                self.state_manager.update_location(updates["current_location"])
            
            # Save state
            self.state_manager.save_state()
            
        except Exception as e:
            logger.error(f"Failed to update dynamic context: {e}")
    
    def _ensure_reflection_in_memory(self):
        """Ensure reflection_on_last_cycle file is in memory if it exists."""
        reflection_file = self.memory_dir / "reflection_on_last_cycle.json"
        # Use path directly as memory ID (no type prefix)
        reflection_memory_id = "personal/.internal/memory/reflection_on_last_cycle.json"
        
        # Check if it exists and has content
        if reflection_file.exists() and reflection_file.stat().st_size > 50:  # More than just empty JSON
            # Check if already in memory
            already_in_memory = any(
                m.id == reflection_memory_id 
                for m in self.memory_system.symbolic_memory
            )
            if not already_in_memory:
                reflection_memory = MemoryBlock(
                    location="personal/.internal/memory/reflection_on_last_cycle.json",
                    priority=Priority.MEDIUM,  # Medium priority, not as critical as goals
                    confidence=1.0,
                    pinned=False,  # Not pinned, can be cleaned up if needed
                    metadata={
                        "file_type": "reflection",
                        "description": "Reflection on the last execution cycle"
                    },
                    cycle_count=self.cycle_count,
                    no_cache=True,  # Always read fresh
                )
                self.memory_system.add_memory(reflection_memory)
                logger.info(f"Added reflection_on_last_cycle.json to memory at cycle {self.cycle_count}")
    
    
    
    async def run_cycle(self):
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
            
            # Set cycle in recorder
            self.cycle_recorder.set_cycle(self.cycle_count)
            
            # Clear pipeline buffers at start of new cycle
            if self.cycle_count > 0:  # Don't clear on first cycle
                self._clear_pipeline_buffers()
            
            # personal.txt update removed - status.txt handles this now
            
            # Update dynamic context at the start of each cycle
            self._update_dynamic_context(stage="STARTING", phase="INIT")
            
            # Update status display
            try:
                from .status import StatusManager
                status = StatusManager(self)
                status.render()
                logger.debug("Status display updated")
            except Exception as e:
                logger.debug(f"Status rendering failed: {e}")
            
            # Check if location and reflection files need to be added to memory
            # (they might have been created or updated after initialization)
            self._ensure_location_files_in_memory()
            self._ensure_reflection_in_memory()
            
            await self.observation_stage.observe()
            
            self._update_dynamic_context(stage="DECISION", phase="STARTING")
            await self.decision_stage.decide()
                        
            self._update_dynamic_context(stage="EXECUTION", phase="STARTING")
            await self.execution_stage.execute()
            
            self._update_dynamic_context(stage="REFLECT", phase="STARTING")
            await self.reflect_stage.reflect()
                
            # Save checkpoint after completing all stages
            await self._save_checkpoint()
            
            # End execution tracking
            self.execution_tracker.end_execution("completed", {
                "stages_completed": ["observation", "decision", "execution", "reflect"],  # cleanup removed
            })
            
            # Mark cycle as complete in recorder
            try:
                self.cycle_recorder.complete_cycle("completed")
            except Exception as e:
                logger.debug(f"Failed to complete cycle recording: {e}")
                        
        except Exception as e:
            logger.error(f"Error in cognitive cycle: {e}", exc_info=True)
            self.execution_tracker.end_execution("failed", {"error": str(e)})
            
            # Reset context on error
            self._update_dynamic_context(stage="ERROR_RECOVERY", phase="RESET")
    
    # === HELPER METHODS USED BY STAGES ===
    
    # === SUPPORTING METHODS ===    
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
