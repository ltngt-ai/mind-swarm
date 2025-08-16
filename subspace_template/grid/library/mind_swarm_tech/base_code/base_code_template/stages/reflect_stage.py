"""Reflect Stage - Learn from previous execution results.

This stage reviews what happened in the last execution cycle and updates
understanding, goals, and priorities based on outcomes.

This is the 4th stage in the cognitive architecture.
"""

import logging
from typing import TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from ..cognitive_loop import CognitiveLoop

logger = logging.getLogger("Cyber.stages.reflect")


class ReflectStage:
    """Handles the reflection phase of cognition.
    
    This stage is responsible for:
    - Reviewing previous execution results
    - Learning from successes and failures
    - Updating goals and priorities based on outcomes
    - Creating insights for future cycles
    """
    
    # Knowledge tags to exclude during reflection stage
    # We don't need execution implementation details when reflecting
    KNOWLEDGE_BLACKLIST = {
        "execution",  # Execution-specific knowledge
        "execution_only",  # Python API docs
        "decision_only",  # Decision stage specific
        "observation",  # Don't need raw observations
        "action_implementation",  # Implementation details
        "api_documentation",  # API reference
        "procedures",  # Step-by-step procedures
        "tools"  # Tool implementation details
    }
    
    def __init__(self, cognitive_loop: 'CognitiveLoop'):
        """Initialize the reflect stage.
        
        Args:
            cognitive_loop: Reference to the main cognitive loop
        """
        self.cognitive_loop = cognitive_loop
        self.memory_system = cognitive_loop.memory_system
        self.brain_interface = cognitive_loop.brain_interface
        
    async def reflect(self) -> None:
        """Run the reflection stage.
        
        Reviews the last execution and creates reflections in memory.
        Everything is handled by the brain through DSPy, not fixed logic.
        """
        logger.info("=== REFLECT STAGE ===")
        
        # Update dynamic context
        self.cognitive_loop._update_dynamic_context(stage="REFLECT", phase="REVIEWING")
        
        # Check if there's an execution to reflect on from current pipeline
        # (It was filled by the execution stage in this cycle)
        execution_buffer = self.cognitive_loop.get_current_pipeline("execution")
        execution_file = self.cognitive_loop.personal.parent / execution_buffer.location
        
        import json
        try:
            with open(execution_file, 'r') as f:
                last_execution = json.load(f)
                if not last_execution or last_execution == {}:
                    logger.debug("No execution to reflect on")
                    return
        except:
            logger.debug("No execution to reflect on")
            return
        
        # Build context for reflection - let the brain see everything in memory
        from ..memory.tag_filter import TagFilter
        tag_filter = TagFilter(blacklist=self.KNOWLEDGE_BLACKLIST)
        
        memory_context = self.memory_system.build_context(
            max_tokens=self.cognitive_loop.max_context_tokens // 3,
            current_task="Reflecting on previous execution results",
            selection_strategy="recent",
            tag_filter=tag_filter
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
            "insights": output_values.get("insights", ""),
            "lessons_learned": output_values.get("lessons_learned", ""),
            "goal_updates": output_values.get("goal_updates", ""),
            "priority_adjustments": output_values.get("priority_adjustments", ""),
            "next_focus": output_values.get("next_focus", "")
        }
        
        # Save as a reflection_on_last_cycle memory block
        reflection_file = self.cognitive_loop.memory_dir / "reflection_on_last_cycle.json"
        with open(reflection_file, 'w') as f:
            json.dump(reflection_content, f, indent=2)
        
        # Add or update the reflection memory block
        from ..memory import FileMemoryBlock, Priority
        reflection_memory = FileMemoryBlock(
            location=str(reflection_file.relative_to(self.cognitive_loop.personal.parent)),
            priority=Priority.HIGH,
            pinned=False,  # Not pinned, can be cleaned up if needed
            metadata={
                "file_type": "reflection",
                "description": "Reflection on the last execution cycle"
            },
            cycle_count=self.cognitive_loop.cycle_count,
            no_cache=True,  # Don't cache, always read fresh
            # Regular file memory - content type will be auto-detected
        )
        
        # Remove old reflection if it exists and add new one
        reflection_id = f"memory:{reflection_file.relative_to(self.cognitive_loop.personal.parent)}"
        existing_memory = self.cognitive_loop.memory_system.get_memory(reflection_id)
        if existing_memory:
            self.cognitive_loop.memory_system.remove_memory(reflection_id)
        self.cognitive_loop.memory_system.add_memory(reflection_memory)
        
        logger.info(f"💭 Created reflection for cycle {self.cognitive_loop.cycle_count}")
        
        # Log key insights if any
        if output_values.get("insights"):
            logger.info(f"  Insights: {output_values['insights'][:200]}")
        if output_values.get("next_focus"):
            logger.info(f"  Next focus: {output_values['next_focus'][:200]}")