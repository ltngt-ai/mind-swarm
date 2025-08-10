"""Observation Stage - Gathering and understanding information.

This stage encompasses:
1. Perceive - Scan the environment for changes
2. Observe - Select what deserves attention  
3. Orient - Understand the situation

The output of this stage is an understanding of what's happening.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json

from ..memory import Priority, ObservationMemoryBlock, FileMemoryBlock
from ..memory.tag_filter import TagFilter
from ..perception import EnvironmentScanner
from ..brain import BrainInterface

logger = logging.getLogger("Cyber.stages.observation")


class ObservationStage:
    """Handles the observation phase of cognition.
    
    This stage is responsible for:
    - Scanning the environment for changes (Perceive)
    - Selecting what needs attention (Observe)
    - Understanding the situation (Orient)
    """
    
    # Knowledge tags to exclude during observation stage
    # We don't need action implementation details when observing
    KNOWLEDGE_BLACKLIST = {
        "action_guide", 
        "action_implementation", 
        "execution", 
        "procedures", 
        "tools",
        "background"
    }
    
    def __init__(self, cognitive_loop):
        """Initialize the observation stage.
        
        Args:
            cognitive_loop: Reference to the main cognitive loop
        """
        self.cognitive_loop = cognitive_loop
        self.memory_system = cognitive_loop.memory_system
        self.environment_scanner = cognitive_loop.environment_scanner
        self.brain_interface = cognitive_loop.brain_interface
        self.memory_dir = cognitive_loop.memory_dir
        self.file_manager = cognitive_loop.file_manager
        
    async def run(self) -> Optional[Dict[str, Any]]:
        """Run the complete observation stage.
        
        Returns:
            Orientation data if something needs attention, None otherwise
        """
        logger.info("=== OBSERVATION STAGE ===")
        
        # Phase 1: Perceive - Scan environment
        observations = await self.perceive()
        
        # Phase 2: Observe - Select focus
        selected_observation = await self.observe()
        
        if not selected_observation:
            logger.info("👁️ No immediate focus needed")
            return None
            
        # Phase 3: Orient - Understand situation
        orientation = await self.orient(selected_observation)
        
        return orientation
    
    async def perceive(self) -> list:
        """PERCEIVE - Scan environment and update memory with observations.
        
        Returns:
            List of observations found
        """
        logger.info("📡 Perceiving environment...")
        
        # Update dynamic context
        self.cognitive_loop._update_dynamic_context(last_activity=datetime.now().isoformat())
        
        # Scan environment
        observations = self.environment_scanner.scan_environment(full_scan=False)
        
        # Add observations to memory
        significant_count = 0
        high_priority_items = []
        
        for obs in observations:
            self.memory_system.add_memory(obs)
            if obs.priority != Priority.LOW:
                significant_count += 1
                if obs.priority == Priority.HIGH:
                    # Handle different memory block types
                    if hasattr(obs, 'observation_type'):
                        # ObservationMemoryBlock
                        high_priority_items.append(f"{obs.observation_type}: {obs.path[:100]}")
                    elif isinstance(obs, FileMemoryBlock) and obs.metadata.get('file_type') == 'message':
                        # FileMemoryBlock representing a message
                        from_agent = obs.metadata.get('from_agent', 'unknown')
                        subject = obs.metadata.get('subject', 'No subject')
                        high_priority_items.append(f"message from {from_agent}: {subject[:100]}")
                    else:
                        # Other memory block types
                        high_priority_items.append(f"{obs.type.name if hasattr(obs, 'type') else 'unknown'}: {str(obs)[:100]}")
        
        if significant_count > 0:
            logger.info(f"📡 Perceived {significant_count} significant changes ({len(observations)} total)")
            for item in high_priority_items[:3]:  # Show top 3 high priority items
                logger.info(f"  • {item}")
        else:
            logger.info("📡 Environment scan - no significant changes detected")
            
        return observations
    
    async def observe(self) -> Optional[Dict[str, Any]]:
        """OBSERVE - Intelligently select the most important observation.
        
        Returns:
            Selected observation or None if nothing needs attention
        """
        logger.info("👁️ Observing what needs attention...")
        
        # Create tag filter for observation stage with our blacklist
        tag_filter = TagFilter(blacklist=self.KNOWLEDGE_BLACKLIST)
        
        # Build full working memory context with filtering
        memory_context = self.memory_system.build_context(
            max_tokens=self.cognitive_loop.max_context_tokens // 2,
            current_task="Deciding what to focus on",
            selection_strategy="balanced",
            tag_filter=tag_filter
        )
        
        # Log what's in the context
        if "processed_observations.json" in memory_context:
            logger.debug("✓ processed_observations.json is in working memory")
        else:
            logger.warning("✗ processed_observations.json NOT in working memory")
        
        # Let the AI brain see everything and decide what to focus on
        observation = await self._select_focus_from_memory(memory_context)
        
        # Update cycle state with selected observation
        self.cognitive_loop._update_cycle_state(current_observation=observation)
        
        if observation:
            if observation.get("type") == "COMMAND":
                logger.info(f"👁️ Selected MESSAGE from {observation.get('from', 'unknown')}: {observation.get('command', 'no command')}")
            elif observation.get("type") == "QUERY":
                logger.info(f"👁️ Selected QUERY from {observation.get('from', 'unknown')}: {observation.get('query', 'no query')[:100]}")
            else:
                logger.info(f"👁️ Selected {observation.get('observation_type', 'observation')}: {str(observation.get('content', observation))[:100]}")
        
        return observation
    
    async def orient(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """ORIENT - Understand the situation and build context.
        
        Args:
            observation: The selected observation to orient to
            
        Returns:
            Orientation data including understanding and approach
        """
        logger.info("🧭 Orienting to understand situation...")
        
        # Create tag filter for observation stage with our blacklist
        tag_filter = TagFilter(blacklist=self.KNOWLEDGE_BLACKLIST)
        
        # Build working memory context for orientation with filtering
        working_memory = self.memory_system.build_context(
            max_tokens=self.cognitive_loop.max_context_tokens // 2,
            current_task="Understanding the current situation",
            selection_strategy="balanced",
            tag_filter=tag_filter
        )
        
        # Use brain to understand the situation
        logger.info("🧠 Analyzing situation and understanding context...")
        orientation_response = await self.brain_interface.analyze_situation(observation, working_memory)
        
        # Extract the useful content from the response
        output_values = orientation_response.get("output_values", {})
        
        # Create a clean orientation record with only useful information
        orientation_data = {
            "timestamp": datetime.now().isoformat(),
            "cycle_count": self.cognitive_loop.cycle_count,
            "observation": observation,  # What we're orienting to
            "understanding": output_values.get("understanding", ""),
            "situation_type": output_values.get("situation_type", "unknown"),
            "approach": output_values.get("approach", "")
        }
        
        # Save orientation to file
        orientations_dir = self.memory_dir / "orientations"
        self.file_manager.ensure_directory(orientations_dir)
        
        timestamp = datetime.now()
        orientation_file = orientations_dir / f"orient_{timestamp.strftime('%Y%m%d_%H%M%S')}_{self.cognitive_loop.cycle_count}.json"
        
        with open(orientation_file, 'w') as f:
            json.dump(orientation_data, f, indent=2)
        
        # Create observation for the orientation
        orientation_observation = ObservationMemoryBlock(
            observation_type="self_orientation",
            path=str(orientation_file),
            priority=Priority.MEDIUM,
            confidence=1.0,
            metadata={
                "file_type": "orientation",
                "cycle_count": self.cognitive_loop.cycle_count,
                "timestamp": timestamp.isoformat()
            }
        )
        
        # Add observation to memory system
        self.memory_system.add_memory(orientation_observation)
        logger.info(f"💭 Orientation stored: {orientation_file.name}")
        
        # Also create FileMemoryBlock for immediate access
        orientation_memory = FileMemoryBlock(
            location=str(orientation_file),
            priority=Priority.HIGH,
            confidence=1.0,
            metadata={"file_type": "orientation"}
        )
        
        # Add to working memory
        self.memory_system.add_memory(orientation_memory)
        
        # Store just the file reference in cycle state
        self.cognitive_loop._update_cycle_state(current_orientation_id=orientation_memory.id)
        
        return orientation_data
    
    async def _select_focus_from_memory(self, memory_context: str) -> Optional[Dict[str, Any]]:
        """Use brain to select what to focus on from full memory context.
        
        Args:
            memory_context: The full working memory context
            
        Returns:
            Selected observation or None
        """
        selection_result = await self.brain_interface.select_focus_from_memory(memory_context)
        
        if not selection_result:
            return None
            
        memory_id = selection_result["memory_id"]
        reasoning = selection_result["reasoning"]
        obsolete_observations = selection_result.get("obsolete_observations", [])
        
        # Remove obsolete observations from memory
        if obsolete_observations:
            logger.info(f"Removing {len(obsolete_observations)} obsolete observations:")
            for obs_id in obsolete_observations:
                try:
                    self.memory_system.remove_memory(obs_id)
                    logger.info(f"  - Removed: {obs_id}")
                except Exception as e:
                    logger.warning(f"  - Failed to remove {obs_id}: {e}")
            
            # Also remove from processed_observations.json
            self.cognitive_loop._remove_obsolete_from_processed(obsolete_observations)
        
        # Check if there's actually a memory to retrieve
        if not memory_id:
            # Brain decided no focus needed (just cleanup)
            logger.debug(f"Brain decided no focus needed: {reasoning}")
            return None
        
        # Retrieve the selected memory
        observation = self.brain_interface.retrieve_memory_by_id(
            memory_id, self.memory_system, reasoning
        )
        
        if not observation:
            logger.warning(f"Failed to retrieve memory {memory_id}")
            return None
        
        # Only record if this is actually an observation (not a file or other memory type)
        if memory_id.startswith("observation:"):
            logger.info(f"Recording processed observation: {memory_id}")
            self.cognitive_loop._record_processed_observation(memory_id, observation)
        else:
            logger.debug(f"Not recording {memory_id} as it's not an observation")
            
        return observation