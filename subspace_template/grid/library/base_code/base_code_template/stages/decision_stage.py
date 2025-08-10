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

logger = logging.getLogger("Cyber.stages.decision")


class DecisionStage:
    """Handles the decision phase of cognition.
    
    This stage is responsible for:
    - Taking the understanding from observation stage
    - Deciding what actions to take
    - Returning a list of actions for execution
    """
    
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
        
    async def run(self, orientation: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Run the decision stage.
        
        Args:
            orientation: The orientation data from observation stage
            
        Returns:
            List of action specifications to execute
        """
        logger.info("=== DECISION STAGE ===")
        
        # Get orientation ID from cycle state
        cycle_state = self.cognitive_loop._get_cycle_state()
        orientation_id = getattr(cycle_state, 'current_orientation_id', None)
        
        if not orientation_id:
            logger.warning("No orientation ID found in cycle state")
            return []
        
        # Create tag filter for decision stage
        tag_filter = TagFilter.for_decision_stage()
        
        # Build decision context - this will include the orientation file reference
        decision_context = self.memory_system.build_context(
            max_tokens=self.cognitive_loop.max_context_tokens // 2,
            current_task="Deciding on actions",
            selection_strategy="balanced",
            tag_filter=tag_filter
        )
        
        # Use brain to decide on actions
        logger.info("🤔 Making decision based on situation...")
        # The brain will see the orientation file in working memory and can read it
        decision_response = await self.brain_interface.make_decision(decision_context)
        
        # Extract actions from the response
        output_values = decision_response.get("output_values", {})
        actions_json = output_values.get("actions", "[]")
        
        # Parse the actions JSON string
        try:
            if isinstance(actions_json, str):
                action_specs = json.loads(actions_json)
            else:
                action_specs = actions_json
        except:
            logger.error("Failed to parse actions from decision")
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
        
        # Save actions as serializable data and update cycle state
        action_data = [{"name": a.name, "params": a.params} for a in actions]
        self.cognitive_loop._update_cycle_state(current_actions=action_data)
        
        return action_data