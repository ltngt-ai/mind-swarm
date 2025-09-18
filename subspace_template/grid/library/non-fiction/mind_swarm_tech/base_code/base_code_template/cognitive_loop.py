"""Cognitive Loop - Four-stage architecture.

This refactored version uses a four-stage cognitive architecture:
1. Observation Stage
2. Decision Stage
3. Execution Stage
4. Reflection Stage
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
from .knowledge.knowledge_context_builder import KnowledgeContextBuilder
from .state import UnifiedStateManager, StateSection, ExecutionStateTracker
from .utils import CognitiveUtils, FileManager
from .brain import BrainInterface
from .stages import ObservationStage, ReflectStage, DecisionStage, ExecutionStage
from .cycle_recorder_client import get_cycle_recorder

logger = logging.getLogger("Cyber.cognitive")


class CognitiveLoop:
    """
    Streamlined cognitive processing engine using four-stage architecture.

    The cognitive loop is organized into four fundamental stages:
    1. Observation - Gather and understand information
    2. Decision - Choose what to do
    3. Execution - Take action
    4. Reflection - Reflect on what has happened
    """
    
    def __init__(self, cyber_id: str, personal: Path, 
                 max_context_tokens: int = 32000,
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
    
    
    
    def _initialize_managers(self):
        """Initialize all supporting managers."""
        # Unified memory system
        self.memory_system = MemorySystem(
            filesystem_root=self.personal.parent,
            max_tokens=self.max_context_tokens
        )
        
        # Knowledge system
        self.knowledge_manager = SimplifiedKnowledgeManager()
        
        # State management - using new unified state manager
        self.state_manager = UnifiedStateManager(self.cyber_id, self.memory_dir)
        self.execution_tracker = ExecutionStateTracker(self.cyber_id, self.memory_dir)

        # Knowledge context builder (requires state_manager)
        self.knowledge_context = KnowledgeContextBuilder(
            self.knowledge_manager,
            self.memory_system,
            self.state_manager,
        )
                
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
        # Now retrieved from knowledge database instead of file
        boot_rom = self.knowledge_manager.get_boot_rom(cyber_type=self.cyber_type)
        if boot_rom:
            # Create a pinned memory for the boot ROM
            # Ensure metadata has all required fields for knowledge validation
            metadata = {
                'title': boot_rom.get('title', 'Boot ROM'),
                'category': boot_rom.get('category', 'boot_rom'),
                'tags': boot_rom.get('tags', ['identity', 'core', 'boot']),
                'content': boot_rom.get('content', ''),
                'knowledge_id': boot_rom.get('knowledge_id', 'boot_rom')
            }
            
            # Add any additional fields from boot_rom
            for key, value in boot_rom.items():
                if key not in metadata:
                    metadata[key] = value
            
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
            # Update memory system with resumed cycle count
            self.memory_system.update_cycle(self.cycle_count)
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
            
            # Only set onboarding location if no visited locations exist (truly new cyber)
            visited_locations = self.state_manager.get_value(StateSection.LOCATION, "visited_locations", [])
            if not visited_locations:
                self.state_manager.update_location("/grid/community/school/onboarding/new_cyber_introduction")
                logger.info(f"Set initial location to onboarding for new Cyber")
            else:
                logger.info(f"Preserving existing location for resumed Cyber")
            
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
                    pinned=False,  # Let memory selector manage based on priority
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
    
    def _refresh_boot_rom(self):
        """Refresh boot ROM from knowledge database.
        
        This is called each cycle to ensure the cyber always has the latest
        identity and instructions from the semantic knowledge database.
        """
        try:
            # Retrieve boot ROM from knowledge database
            boot_rom = self.knowledge_manager.get_boot_rom(cyber_type=self.cyber_type)
            if boot_rom:
                # Ensure metadata has all required fields for knowledge schema
                metadata = {
                    'title': boot_rom.get('title', 'Boot ROM'),
                    'category': boot_rom.get('category', 'boot_rom'),
                    'tags': boot_rom.get('tags', ['identity', 'core', 'boot']),
                    'content': boot_rom.get('content', ''),
                    'knowledge_id': boot_rom.get('knowledge_id', 'boot_rom')
                }
                
                # Add any additional fields from boot_rom
                for key, value in boot_rom.items():
                    if key not in metadata:
                        metadata[key] = value
                
                # Map cyber_type to the actual knowledge ID with templates/ prefix
                if self.cyber_type == "io_gateway":
                    boot_rom_id = "templates/concepts/identity/io_gateway_boot_rom.yaml"
                else:
                    boot_rom_id = "templates/concepts/identity/general_cyber_boot_rom.yaml"
                    
                boot_memory = MemoryBlock(
                    location="/personal/.internal/boot_rom.yaml",
                    confidence=1.0,
                    priority=Priority.FOUNDATIONAL,
                    metadata=metadata,
                    pinned=True,
                    cycle_count=self.cycle_count,
                    content_type=ContentType.MINDSWARM_KNOWLEDGE
                )
                
                # Remove old boot ROM memory if exists
                boot_rom_id = boot_memory.id
                self.memory_system.remove_memory(boot_rom_id)
                
                # Add fresh boot ROM
                self.memory_system.add_memory(boot_memory)
                logger.debug(f"Refreshed boot ROM from knowledge DB for cycle {self.cycle_count}")
            else:
                logger.warning(f"Could not refresh boot ROM from knowledge DB")
        except Exception as e:
            logger.error(f"Error refreshing boot ROM: {e}")
    
    def _ensure_reflection_in_memory(self):
        """Ensure reflection from last cycle is available in memory via knowledge DB.
        
        Note: Reflections are now stored in the semantic knowledge database
        as pipeline data, not in files. This method is kept for compatibility
        but no longer adds file-based memories.
        """
        # Reflections are now accessed via pipeline_knowledge API
        # No need to add file-based memory blocks
        pass
    
    
    
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
            
            # Update memory system with current cycle for aging
            self.memory_system.update_cycle(self.cycle_count)
            
            # Set cycle in recorder
            self.cycle_recorder.set_cycle(self.cycle_count)
            
            # Refresh boot ROM from knowledge database each cycle
            # This ensures cybers always have the latest identity and instructions
            self._refresh_boot_rom()
            
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
            
            # Update biofeedback with memory stats
            try:
                memory_stats = self.memory_system.get_memory_stats()
                task_id = self.state_manager.get_value(StateSection.TASK, "current_task_id")
                task_info = {
                    'id': task_id,
                    'summary': self.state_manager.get_value(StateSection.TASK, "current_task_summary")
                } if task_id else None
                
                self.state_manager.update_biofeedback(
                    current_task=task_info,
                    memory_stats=memory_stats
                )
                logger.debug(f"Updated biofeedback with memory stats: {memory_stats.get('total_memories', 0)} memories")
            except Exception as e:
                logger.debug(f"Failed to update biofeedback: {e}")
                
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
            
            # Periodic memory cleanup - every 5 cycles
            if self.cycle_count % 5 == 0:
                try:
                    # Clean up old memories (older than 100 cycles)
                    old_count = self.memory_system.cleanup_old_memories(self.cycle_count, max_age_cycles=100)
                    if old_count > 0:
                        logger.info(f"Cleaned up {old_count} old memories (> 100 cycles old)")
                    
                    # Also clean up expired memories
                    expired_count = self.memory_system.cleanup_expired()
                    if expired_count > 0:
                        logger.info(f"Cleaned up {expired_count} expired memories")
                    
                    # Clean up cache
                    cache_count = self.memory_system.cleanup_cache()
                    if cache_count > 0:
                        logger.debug(f"Cleaned up {cache_count} expired cache entries")
                        
                except Exception as e:
                    logger.error(f"Error during periodic memory cleanup: {e}")
                        
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
