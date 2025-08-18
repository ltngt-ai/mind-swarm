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
    FileMemoryBlock,
    Priority, ContentType
)
from .perception import EnvironmentScanner
from .knowledge.simplified_knowledge import SimplifiedKnowledgeManager
from .state import CyberStateManager, ExecutionStateTracker
from .utils import CognitiveUtils, FileManager
from .brain import BrainInterface
from .stages import ObservationStage, ReflectStage, DecisionStage, ExecutionStage, CleanupStage

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
        self.cleanup_stage = CleanupStage(self)
    
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
            
            # Create FileMemoryBlock for this buffer
            # Use sandbox path directly
            buffer_memory = FileMemoryBlock(
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
                content_type=ContentType.MINDSWARM_SYSTEM  # Mark as system memory
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
            updated_buffer = FileMemoryBlock(
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
                content_type=ContentType.MINDSWARM_SYSTEM  # Mark as system memory
            )
            self.memory_system.add_memory(updated_buffer)
            self.pipeline_buffers[stage] = updated_buffer
    
    def get_current_pipeline(self, stage: str) -> FileMemoryBlock:
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
        
        # Pipeline using FileMemoryBlocks
        # Each stage has a single buffer that gets cleared each cycle
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
            boot_memory = FileMemoryBlock(
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
        
        # Add identity to memory (pinned so always visible)
        self._init_identity_memory()
        
        # Initialize dynamic context file
        self._init_dynamic_context()
        
        # Add location files to memory
        self._init_location_memory()
        
        # Add reflection file if it exists from a previous run
        self._ensure_reflection_in_memory()
    
    def _init_identity_memory(self):
        """Add Cyber identity file to working memory as pinned."""
        identity_file = self.personal / ".internal" / "identity.json"
        if identity_file.exists():
            # Use the sandbox path directly - cyber sees /personal/.internal/identity.json
            identity_memory = FileMemoryBlock(
                location="personal/.internal/identity.json",
                priority=Priority.SYSTEM,  # System-controlled identity
                confidence=1.0,
                pinned=True,  # Always in working memory
                metadata={"file_type": "identity", "description": "My identity and configuration"},
                cycle_count=self.cycle_count,  # When this memory was added
                content_type=ContentType.MINDSWARM_SYSTEM  # Mark as system memory
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
                "current_location": "/grid/community/school/onboarding/new_cyber_introduction"  # Starting location for new Cybers
            }
            with open(self.dynamic_context_file, 'w') as f:
                json.dump(context_data, f, indent=2)
            logger.info(f"Created initial dynamic_context.json for new Cyber")
        
        # Add to memory as pinned so Cyber always sees current context
        # Use the sandbox path directly - cyber sees /personal/.internal/memory/dynamic_context.json
        self.dynamic_context_location = "personal/.internal/memory/dynamic_context.json"
        context_memory = FileMemoryBlock(
            location=self.dynamic_context_location,
            priority=Priority.SYSTEM,  # System-controlled runtime context
            confidence=1.0,
            pinned=True,  # Always in working memory
            metadata={"file_type": "dynamic_context", "description": "Current runtime context"},
            cycle_count=self.cycle_count,  # Will always match file content now
            no_cache=True,  # Don't cache, always read from disk
            content_type=ContentType.MINDSWARM_SYSTEM  # Mark as system memory
        )
        self.memory_system.add_memory(context_memory)
        self.dynamic_context_memory_id = context_memory.id
        logger.info("Initialized dynamic_context.json")
    
    def _init_location_memory(self):
        """Add location tracking files to memory."""
        self._ensure_location_files_in_memory()
    
    def _read_dynamic_context(self):
        """Read the dynamic context file if it exists."""
        try:
            if self.dynamic_context_file.exists():
                with open(self.dynamic_context_file, 'r') as f:
                    return json.load(f)
        except:
            pass
        return {}
    
    def _ensure_location_files_in_memory(self):
        """Ensure location files are in memory, creating them if needed."""
        # Create/update current_location.txt
        current_location_file = self.memory_dir / "current_location.txt"
        current_location_id = "memory:personal/.internal/memory/current_location.txt"
        
        # Create the file if it doesn't exist
        if not current_location_file.exists():
            # Get current location from dynamic context or use default
            dynamic_context = self._read_dynamic_context()
            current_loc = dynamic_context.get("current_location", "/personal")
            
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
                current_location_memory = FileMemoryBlock(
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
        
        # Create/update personal_location.txt
        personal_location_file = self.memory_dir / "personal_location.txt"
        personal_location_id = "memory:personal/.internal/memory/personal_location.txt"
        
        # Create the file if it doesn't exist
        if not personal_location_file.exists():
            # Create basic personal directory listing
            personal_content = "| /personal (your home directory)\n"
            # List actual directories if they exist
            if self.personal.exists():
                for item in sorted(self.personal.iterdir()):
                    if item.is_dir() and not item.name.startswith('.'):
                        personal_content += f"|---- 📁 {item.name}/\n"
                for item in sorted(self.personal.iterdir()):
                    if item.is_file() and not item.name.startswith('.'):
                        personal_content += f"|---- 📄 {item.name}\n"
            personal_location_file.write_text(personal_content)
            logger.info("Created personal_location.txt with personal directory listing")
        
        if personal_location_file.exists():
            # Check if already in memory
            existing_memory = self.memory_system.get_memory(personal_location_id)
            if existing_memory:
                # Update the cycle count to keep it fresh
                self.memory_system.touch_memory(personal_location_id, self.cycle_count)
            else:
                personal_location_memory = FileMemoryBlock(
                    location="personal/.internal/memory/personal_location.txt",
                    priority=Priority.SYSTEM,  # System-controlled location tracking
                    confidence=1.0,
                    pinned=True,  # Always visible
                    metadata={"file_type": "location", "description": "Map of my personal directory"},
                    cycle_count=self.cycle_count,
                    no_cache=True,  # Always read fresh
                    content_type=ContentType.TEXT_PLAIN  # Plain text location file
                )
                self.memory_system.add_memory(personal_location_memory)
                logger.info(f"Added personal_location.txt to pinned memory with id: {personal_location_memory.id}")
    
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
                    "current_location": "/grid/community/school/onboarding/new_cyber_introduction"
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
                reflection_memory = FileMemoryBlock(
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
            
            # Clear pipeline buffers at start of new cycle
            if self.cycle_count > 0:  # Don't clear on first cycle
                self._clear_pipeline_buffers()
            
            # Update dynamic context at the start of each cycle
            self._update_dynamic_context(stage="STARTING", phase="INIT")
            
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
            
            self._update_dynamic_context(stage="CLEANUP", phase="STARTING")
            await self.cleanup_stage.cleanup(self.cycle_count)
                
            # Save checkpoint after completing all stages
            await self._save_checkpoint()
            
            # End execution tracking
            self.execution_tracker.end_execution("completed", {
                "stages_completed": ["observation", "decision", "execution", "reflect", "cleanup"],
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
