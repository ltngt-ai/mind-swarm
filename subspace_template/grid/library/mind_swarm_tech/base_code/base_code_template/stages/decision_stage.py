"""Decision Stage V2 - Producing plain text intentions instead of structured actions.

This stage encompasses:
1. Decide - Generate natural language description of what to do

The input is the orientation/reasoning from the observation stage.
The output is a plain text intention describing what the cyber wants to accomplish.
"""

import logging
from typing import Dict, Any, Optional
import json
import time
from datetime import datetime

from ..brain import BrainInterface
from ..memory.tag_filter import TagFilter
from ..memory import MemoryType

logger = logging.getLogger("Cyber.stages.decision_v2")


class DecisionStage:
    """Handles the decision phase of cognition using natural language intentions.
    
    This stage is responsible for:
    - Taking the reasoning from observation stage
    - Deciding what to do in plain language
    - Returning a clear intention for the execution stage to implement
    """
    
    # Knowledge tags to exclude during decision stage
    KNOWLEDGE_BLACKLIST = {
        "low_level_details",
        "observation",  # Don't need observation details
        "implementation_details",
        "api_documentation",  # Don't need API docs when expressing intent
        "execution",  # Execution-specific knowledge for script generation
        "execution_only",  # Python API docs only needed in execution
        "reflection_only",  # Reflection stage specific
        "action_implementation"  # Implementation details for execution stage
    }
    
    def __init__(self, cognitive_loop):
        """Initialize the decision stage.
        
        Args:
            cognitive_loop: Reference to the main cognitive loop
        """
        self.cognitive_loop = cognitive_loop
        self.memory_system = cognitive_loop.memory_system
        self.brain_interface = cognitive_loop.brain_interface
        self.knowledge_manager = cognitive_loop.knowledge_manager
        
    async def decide(self):
        """Run the decision stage.
        
        Reads the observation from the current pipeline and decides on intentions.
            
        Returns:
            Dict containing the plain text intention and context
        """
        logger.info("=== DECISION STAGE ===")
        
        # Read observation buffer to get observation data
        observation_buffer = self.cognitive_loop.get_current_pipeline("observation")
        observation_file = self.cognitive_loop.personal.parent / observation_buffer.location
        
        try:
            with open(observation_file, 'r') as f:
                observation_data = json.load(f)
                has_observation = bool(observation_data) and observation_data != {}
        except:
            observation_data = {}
            has_observation = False
        
        if not has_observation:
            logger.debug("No observation data in current pipeline")
            return {"intention": None, "reasoning": "No observation to act upon"}
        
        # Update dynamic context - DECIDE phase (brain LLM call)
        self.cognitive_loop._update_dynamic_context(stage="DECISION", phase="DECIDE")
        
        # Create tag filter for decision stage with our blacklist
        tag_filter = TagFilter(blacklist=self.KNOWLEDGE_BLACKLIST)
        
        # Build decision context - goals and tasks come from working memory
        current_task = "Deciding what to do based on current situation, goals and tasks"
        
        decision_context = self.memory_system.build_context(
            max_tokens=self.cognitive_loop.max_context_tokens // 2,
            current_task=current_task,
            selection_strategy="balanced",
            tag_filter=tag_filter,
            exclude_types=[MemoryType.OBSERVATION]  # Don't need raw observations
        )
        
        # Use brain to generate intention
        logger.info("🤔 Generating intention based on situation...")
        intention_response = await self._generate_intention(decision_context)
        
        # Extract intention from the response
        output_values = intention_response.get("output_values", {})
        intention = output_values.get("intention", "")
        reasoning = output_values.get("reasoning", "No explicit reasoning provided")
        priority = output_values.get("priority", "normal")
        
        # Log the decision
        if intention:
            logger.info(f"🤔 Generated intention: {intention[:100]}...")
            logger.info(f"   Priority: {priority}")
        else:
            logger.info("🤔 No action needed at this time")
        
        # Write to decision pipeline buffer
        decision_content = {
            "timestamp": datetime.now().isoformat(),
            "cycle_count": self.cognitive_loop.cycle_count,
            "intention": intention,
            "reasoning": reasoning,
            "priority": priority,
            "has_observation": has_observation,
            "observation_context": observation_data.get("reasoning", "")
        }
        
        decision_buffer = self.cognitive_loop.get_current_pipeline("decision")
        buffer_file = self.cognitive_loop.personal.parent / decision_buffer.location
        
        with open(buffer_file, 'w') as f:
            json.dump(decision_content, f, indent=2)
        
        # Touch the memory block so it knows when the file was updated
        self.cognitive_loop.memory_system.touch_memory(decision_buffer.id, self.cognitive_loop.cycle_count)
        
        logger.info(f"💭 Decision intention written to pipeline buffer")
            
    async def _generate_intention(self, memory_context: str) -> Dict[str, Any]:
        """Use brain to generate a plain text intention.
        
        Args:
            memory_context: Working memory context
            
        Returns:
            Dict with intention and metadata
        """
        thinking_request = {
            "signature": {
                "instruction": """
Review your working memory to understand the current situation and what needs to be done.
You should see an orientation that explains what's happening.

Instead of choosing specific actions, describe in plain language what you want to accomplish.
Be specific about your goals but don't worry about implementation details.

Think of this as telling a skilled assistant what you want done, not how to do it.

Examples of good intentions:
- "Send a friendly greeting to Alice explaining that I'm a new cyber and would like to collaborate"
- "Analyze the recent messages from Bob and create a summary of the key points"
- "Update my memory with the insights from the conversation and mark the task as complete"
- "Think deeply about the implications of the new information and how it affects our strategy"

Examples of poor intentions (too implementation-focused):
- "Execute send_message action with parameters to='Alice' and content='Hello'"
- "Call the think action with depth='deep'"

Always start your output with [[ ## reasoning ## ]]
""",
                "inputs": {
                    "working_memory": "Your complete working memory including the recent orientation"
                },
                "outputs": {
                    "reasoning": "Why this intention makes sense given the situation",
                    "intention": "A clear description of what you want to accomplish (or empty string if nothing needed)",
                    "priority": "Priority level: 'urgent', 'high', 'normal', or 'low'"
                },
                "display_field": "reasoning"
            },
            "input_values": {
                "working_memory": memory_context
            },
            "request_id": f"decide_intention_{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        response = await self.brain_interface._use_brain(json.dumps(thinking_request))
        return json.loads(response)