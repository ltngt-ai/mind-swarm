"""Reflect Stage - Learn from previous execution results.

This stage reviews what happened in the last execution cycle and updates
understanding, goals, and priorities based on outcomes.

This is the 4th stage in the cognitive architecture.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from ..brain import BrainInterface

logger = logging.getLogger("Cyber.stages.reflect")


class ReflectStage:
    """Handles the reflection phase of cognition.
    
    This stage is responsible for:
    - Reviewing previous execution results
    - Learning from successes and failures
    - Updating goals and priorities based on outcomes
    - Creating insights for future cycles
    """
    
    def __init__(self, cognitive_loop):
        """Initialize the reflect stage.
        
        Args:
            cognitive_loop: Reference to the main cognitive loop
        """
        self.cognitive_loop = cognitive_loop
        self.memory_system = cognitive_loop.memory_system
        self.brain_interface = cognitive_loop.brain_interface
        
    async def run(self) -> None:
        """Run the reflection stage.
        
        Reviews the last execution and creates reflections in memory.
        Everything is handled by the brain through DSPy, not fixed logic.
        """
        logger.info("=== REFLECT STAGE ===")
        
        # Update dynamic context
        self.cognitive_loop._update_dynamic_context(stage="REFLECT", phase="REVIEWING")
        
        # Check if there's a previous execution to reflect on
        # This is in the previous buffer since we haven't swapped yet
        prev_execution_buffer = self.cognitive_loop.get_previous_pipeline("execution")
        prev_execution_file = self.cognitive_loop.personal.parent / prev_execution_buffer.location
        
        import json
        try:
            with open(prev_execution_file, 'r') as f:
                last_execution = json.load(f)
                if not last_execution or last_execution == {}:
                    logger.debug("No previous execution to reflect on")
                    return
        except:
            logger.debug("No previous execution to reflect on")
            return
        
        # Build context for reflection - let the brain see everything in memory
        memory_context = self.memory_system.build_context(
            max_tokens=self.cognitive_loop.max_context_tokens // 3,
            current_task="Reflecting on previous execution results",
            selection_strategy="recent"
        )
        
        # Use brain to reflect on what happened
        logger.info("🔍 Reflecting on previous execution...")
        
        # The brain will analyze the execution results and create reflections
        reflection_response = await self.brain_interface.reflect_on_execution(memory_context)
        
        if not reflection_response:
            logger.debug("No reflections generated")
            return
        
        # Extract reflection content
        output_values = reflection_response.get("output_values", {})
        
        reflection_content = {
            "timestamp": datetime.now().isoformat(),
            "cycle_count": self.cognitive_loop.cycle_count,
            "execution_cycle": last_execution.get("cycle_count", 0),
            "insights": output_values.get("insights", ""),
            "lessons_learned": output_values.get("lessons_learned", ""),
            "goal_updates": output_values.get("goal_updates", ""),
            "priority_adjustments": output_values.get("priority_adjustments", ""),
            "next_focus": output_values.get("next_focus", "")
        }
        
        # Write to reflect pipeline buffer
        reflect_buffer = self.cognitive_loop.get_current_pipeline("reflect")
        buffer_file = self.cognitive_loop.personal.parent / reflect_buffer.location
        
        with open(buffer_file, 'w') as f:
            json.dump(reflection_content, f, indent=2)
        
        # Touch the memory block so it knows when the file was updated
        self.cognitive_loop.memory_system.touch_memory(reflect_buffer.id, self.cognitive_loop.cycle_count)
        
        logger.info(f"💭 Created reflection for cycle {self.cognitive_loop.cycle_count}")
        
        # Log key insights if any
        if output_values.get("insights"):
            logger.info(f"  Insights: {output_values['insights'][:200]}")
        if output_values.get("next_focus"):
            logger.info(f"  Next focus: {output_values['next_focus'][:200]}")