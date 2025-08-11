"""Decision Stage - Choosing what actions to take.

This stage encompasses:
1. Decide - Choose actions based on understanding

The input is the orientation/understanding from the observation stage.
The output is a list of actions to execute.
"""

import logging
from typing import Dict, Any, List, Optional
import json

from ..brain import BrainInterface
from ..actions import ActionCoordinator
from ..memory.tag_filter import TagFilter
from ..memory import MemoryType
from ..state.goal_manager import GoalStatus
from datetime import datetime

logger = logging.getLogger("Cyber.stages.decision")


class DecisionStage:
    """Handles the decision phase of cognition.
    
    This stage is responsible for:
    - Taking the understanding from observation stage
    - Deciding what actions to take
    - Returning a list of actions for execution
    """
    
    # Knowledge tags to exclude during decision stage
    KNOWLEDGE_BLACKLIST = {
        "low_level_details",
        "observation"
    }
    
    def __init__(self, cognitive_loop):
        """Initialize the decision stage.
        
        Args:
            cognitive_loop: Reference to the main cognitive loop
        """
        self.cognitive_loop = cognitive_loop
        self.memory_system = cognitive_loop.memory_system
        self.brain_interface = cognitive_loop.brain_interface
        self.action_coordinator = cognitive_loop.action_coordinator
        self.knowledge_manager = cognitive_loop.knowledge_manager
        
    async def run(self) -> List[Dict[str, Any]]:
        """Run the decision stage.
        
        Reads the observation from the current pipeline and decides on actions.
            
        Returns:
            List of action specifications to execute
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
            return []
        
        # Update dynamic context - DECIDE phase (brain LLM call)
        self.cognitive_loop._update_dynamic_context(stage="DECISION", phase="DECIDE")
        
        # Create tag filter for decision stage with our blacklist
        tag_filter = TagFilter(blacklist=self.KNOWLEDGE_BLACKLIST)
        
        # Build decision context - goals and tasks come from working memory
        current_task = "Deciding on actions based on current situation, goals and tasks"
        
        decision_context = self.memory_system.build_context(
            max_tokens=self.cognitive_loop.max_context_tokens // 2,
            current_task=current_task,
            selection_strategy="balanced",
            tag_filter=tag_filter,
            exclude_types=[MemoryType.OBSERVATION]  # Don't need raw observations
        )
        
        # Use brain to decide on actions
        logger.info("🤔 Making decision based on situation...")
        # The brain will see the orientation file in working memory and can read it
        decision_response = await self.brain_interface.make_decision(decision_context)
        
        # Extract actions from the response
        output_values = decision_response.get("output_values", {})
        actions_json = output_values.get("actions", "[]")
        
        # Debug log to see what we actually got
        logger.debug(f"Raw actions_json from brain: {repr(actions_json)}")
        
        # Parse the actions JSON string
        try:
            if isinstance(actions_json, str):
                action_specs = json.loads(actions_json)
            else:
                action_specs = actions_json
        except Exception as e:
            logger.error(f"Failed to parse actions from decision: {e}")
            logger.error(f"Actions JSON was: {repr(actions_json)}")
            action_specs = []
        
        # Ensure action_specs is iterable (not None)
        if action_specs is None:
            action_specs = []
        
        # Convert action specs to Action objects
        actions = []
        for spec in action_specs:
            action = self.action_coordinator.prepare_action(
                spec.get("action", spec.get("name", "")), 
                spec.get("params", {}), 
                self.knowledge_manager
            )
            if action:
                actions.append(action)
        
        # Log the decision
        if actions:
            logger.info(f"🤔 Decided on {len(actions)} actions:")
            for i, action in enumerate(actions[:5]):  # Show first 5 actions
                params_str = ""
                if action.params:
                    # Show key parameters
                    key_params = []
                    for k, v in list(action.params.items())[:3]:
                        if isinstance(v, str) and len(v) > 50:
                            key_params.append(f"{k}='{v[:50]}...'")
                        else:
                            key_params.append(f"{k}={v}")
                    if key_params:
                        params_str = f" ({', '.join(key_params)})"
                logger.info(f"  {i+1}. {action.name}{params_str}")
        else:
            logger.info("🤔 No actions decided")
        
        # Save actions as serializable data
        action_data = [{"name": a.name, "params": a.params} for a in actions]
        
        # Track which goals actions might address
        # Goals are now tracked through working memory, not directly
        addresses_goals = []
        
        # Extract reasoning from decision response
        reasoning = output_values.get("reasoning", "No explicit reasoning provided")
        
        # Write to decision pipeline buffer
        decision_content = {
            "timestamp": datetime.now().isoformat(),
            "cycle_count": self.cognitive_loop.cycle_count,
            "selected_actions": action_data,
            "reasoning": reasoning,
            "addresses_goals": list(set(addresses_goals)),  # Unique goal IDs
            "has_observation": has_observation
        }
        
        decision_buffer = self.cognitive_loop.get_current_pipeline("decision")
        buffer_file = self.cognitive_loop.personal.parent / decision_buffer.location
        
        with open(buffer_file, 'w') as f:
            json.dump(decision_content, f, indent=2)
        
        # Touch the memory block so it knows when the file was updated
        self.cognitive_loop.memory_system.touch_memory(decision_buffer.id, self.cognitive_loop.cycle_count)
        
        logger.info(f"💭 Decision written to pipeline buffer addressing {len(addresses_goals)} goals")
        
        return action_data