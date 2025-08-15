"""Observation Stage - Understanding the situation through environmental scanning.

This stage scans the environment for changes and creates understanding
from observations about the current situation.

The output of this stage is reasoning about what's happening and its relevance.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json
import time

from ..memory import Priority, ObservationMemoryBlock, MemoryType
from ..memory.tag_filter import TagFilter
from ..perception import EnvironmentScanner
from ..brain import BrainInterface

logger = logging.getLogger("Cyber.stages.observation")


class ObservationStage:
    """Handles the observation phase of cognition.
    
    This stage is responsible for:
    - Scanning the environment for changes
    - Processing incoming messages  
    - Creating contextual understanding from observations
    """
    
    # Knowledge tags to exclude during observation stage
    # We don't need action implementation details when observing
    KNOWLEDGE_BLACKLIST = {
        "action_guide", 
        "action_implementation", 
        "execution", 
        "execution_only",  # Execution stage specific
        "decision_only",  # Decision stage specific
        "reflection_only",  # Reflection stage specific
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
        
        # Observe - Understand the situation from observations
        orientation = await self.observe()
        
        return orientation
    
    async def observe(self) -> Optional[Dict[str, Any]]:
        """OBSERVE - Understand the situation from observations.
        
        This phase first scans for new observations, then analyzes all observations 
        and produces orientation with reasoning and relevance.
        
        Returns:
            Orientation data including reasoning and relevance, or None
        """
        logger.info("👁️ Observing and reasoning about the situation...")
        
        # First, scan environment for new observations
        logger.info("📡 Scanning for new observations...")
        self.cognitive_loop._update_dynamic_context(stage="OBSERVATION", phase="SCAN")
        observations = self.environment_scanner.scan_environment(
            full_scan=False, 
            cycle_count=self.cognitive_loop.cycle_count
        )
        
        # Add all observations and memories from environment scanner
        # Observations point to the actual files that changed, not to saved observations
        significant_count = 0
        for memory in observations:
            # Add all memories to the memory system
            self.memory_system.add_memory(memory)
            
            # Count significant observations
            if isinstance(memory, ObservationMemoryBlock):
                if memory.priority != Priority.LOW:
                    significant_count += 1
                logger.debug(f"Observation: {memory.observation_type} for {memory.path}")
        
        if significant_count > 0:
            logger.info(f"📡 Found {significant_count} significant changes ({len(observations)} total)")
        else:
            logger.debug("📡 No significant changes detected")
            # Add a "no new observations" memory block so the Cyber knows scanning happened
            no_obs_memory = ObservationMemoryBlock(
                observation_type="no_new_observations",
                path="personal/.internal/memory/scan_status",
                message="No new observations this cycle - environment unchanged",
                cycle_count=self.cognitive_loop.cycle_count,
                content="The environment scan completed but found no new changes, messages, or events requiring attention.",
                priority=Priority.LOW
            )
            self.memory_system.add_memory(no_obs_memory)
            logger.debug("Added 'no new observations' status to memory")
        
        # Update dynamic context before LLM call - OBSERVE phase
        self.cognitive_loop._update_dynamic_context(stage="OBSERVATION", phase="OBSERVE")
        
        # Create tag filter for observation stage with our blacklist
        tag_filter = TagFilter(blacklist=self.KNOWLEDGE_BLACKLIST)
        
        # Build working memory context for reasoning about the situation
        memory_context = self.memory_system.build_context(
            max_tokens=self.cognitive_loop.max_context_tokens // 2,
            current_task="Understanding the current situation from observations",
            selection_strategy="balanced",
            tag_filter=tag_filter,
            exclude_types=[]  # Include all relevant memory types
        )
        
        # Use brain to analyze the situation from all observations
        logger.info("🧠 Analyzing situation from observations...")
        
        # The brain will look at all observations and understand the situation
        orientation_response = await self._analyze_situation_from_observations(memory_context)
        
        if not orientation_response:
            logger.info("👁️ No significant situation to address")
            return None
        
        # Extract the useful content from the response
        output_values = orientation_response.get("output_values", {})
        
        # Debug log to see what we got
        logger.debug(f"Brain response output_values: {output_values}")
        
        # Create orientation data - handle template placeholders
        reasoning = output_values.get("reasoning", "")
        relevance = output_values.get("relevance", "")
        
        # Check for template placeholders and replace with meaningful defaults
        if reasoning == "{reasoning}" or not reasoning:
            reasoning = "Analyzing current observations"
        if relevance == "{relevance}" or not relevance:
            relevance = "Observations being processed for context"
        
        orientation_data = {
            "timestamp": datetime.now().isoformat(),
            "cycle_count": self.cognitive_loop.cycle_count,
            "reasoning": reasoning,
            "relevance": relevance
        }
        
        # Write to observation pipeline buffer
        observation_buffer = self.cognitive_loop.get_current_pipeline("observation")
        buffer_file = self.cognitive_loop.personal.parent / observation_buffer.location
        
        # Write the observation data to the buffer
        with open(buffer_file, 'w') as f:
            json.dump(orientation_data, f, indent=2)
        
        # Touch the memory block so it knows when the file was updated
        self.cognitive_loop.memory_system.touch_memory(observation_buffer.id, self.cognitive_loop.cycle_count)
        
        logger.info(f"💭 Observation written to pipeline buffer")
        
        # Store just the file reference in cycle state
        # Orientation is now tracked through memory system, not cycle state
        
                
        return orientation_data
    
    async def _analyze_situation_from_observations(self, memory_context: str) -> Optional[Dict[str, Any]]:
        """Use brain to analyze the situation from all observations.
        
        This is the new OBSERVE phase where the brain understands the situation
        from all available observations in memory.
        
        Args:
            memory_context: Working memory context with all observations
            
        Returns:
            Orientation data including reasoning and relevance, or None
        """
        thinking_request = {
            "signature": {
                "instruction": """
Review all observations in your working memory to reason relevant changes.
Look at recent observations and how they relate to the current situation, goals and tasks.
Don't plan how to act on this information, just how it might be important.
Always start your output with [[ ## reasoning ## ]]
""",
                "inputs": {
                    "working_memory": "Your current working memory with all observations and context"
                },
                "outputs": {
                    "reasoning": "Your comprehensive reasoning of the current situation based on all observations",
                    "relevance": "How the observations relate to the current situation and goals",
                },
                "display_field": "reasoning"
            },
            "input_values": {
                "working_memory": memory_context
            },
            "request_id": f"observe_{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        response = await self.brain_interface._use_brain(json.dumps(thinking_request))
        result = json.loads(response)
        
        return result
