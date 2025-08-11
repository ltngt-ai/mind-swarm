"""Execution Stage - Preparing and executing actions.

This stage encompasses:
1. Instruct - Prepare and validate actions
2. Act - Execute the actions

The input is the action list from decision stage.
The output is the results of executed actions.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

from ..actions import ActionCoordinator
from ..memory import Priority, MemoryType
from ..memory.tag_filter import TagFilter
from ..utils import ReferenceResolver
import json

logger = logging.getLogger("Cyber.stages.execution")


class ExecutionStage:
    """Handles the execution phase of cognition.
    
    This stage is responsible for:
    - Validating and preparing actions (Instruct)
    - Executing the actions (Act)
    - Processing results
    """
    
    # Knowledge tags to exclude during execution stage
    # We don't need observation/perception details when executing
    KNOWLEDGE_BLACKLIST = {
        "observation",
        "background",
        "raw_perception",
        "perception"
    }
    
    def __init__(self, cognitive_loop):
        """Initialize the execution stage.
        
        Args:
            cognitive_loop: Reference to the main cognitive loop
        """
        self.cognitive_loop = cognitive_loop
        self.memory_system = cognitive_loop.memory_system
        self.action_coordinator = cognitive_loop.action_coordinator
        self.knowledge_manager = cognitive_loop.knowledge_manager
        self.execution_tracker = cognitive_loop.execution_tracker
        
        # Paths
        self.cyber_id = cognitive_loop.cyber_id
        self.personal = cognitive_loop.personal
        self.outbox_dir = cognitive_loop.outbox_dir
        self.memory_dir = cognitive_loop.memory_dir
        
    async def run(self) -> List[Dict[str, Any]]:
        """Run the execution stage.
        
        Reads the actions from the current pipeline and executes them.
            
        Returns:
            List of action results
        """
        logger.info("=== EXECUTION STAGE ===")
        
        # Read decision buffer to get decision data
        decision_buffer = self.cognitive_loop.get_current_pipeline("decision")
        decision_file = self.cognitive_loop.personal.parent / decision_buffer.location
        
        try:
            with open(decision_file, 'r') as f:
                decision_data = json.load(f)
                action_data = decision_data.get("selected_actions", [])
        except:
            action_data = []
        
        if not action_data:
            logger.info("⚡ No actions to execute")
            return []
        
        # Phase 1: Instruct - Validate and prepare actions
        validated_actions = await self.instruct(action_data)
        
        if not validated_actions:
            logger.warning("📋 No valid actions after validation")
            return []
        
        # Phase 2: Act - Execute the actions
        results = await self.act(validated_actions)
        
        return results
    
    async def instruct(self, action_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """INSTRUCT - Prepare and validate actions for execution.
        
        Args:
            action_data: Raw action specifications
            
        Returns:
            List of validated action specifications
        """
        logger.info(f"📋 Validating and preparing {len(action_data)} actions...")
        
        # Update phase to INSTRUCT
        self.cognitive_loop._update_dynamic_context(stage="EXECUTION", phase="INSTRUCT")
        
        corrected_actions = []
        validation_errors = 0
        
        for action_spec in action_data:
            # Load action knowledge and apply corrections
            action_name = action_spec.get("name", "")
            params = action_spec.get("params", {})
            
            # Validate and prepare action
            is_valid, error = self.action_coordinator.validate_action(
                action_name, params, self.knowledge_manager
            )
            
            if is_valid:
                # Apply corrections from knowledge
                action = self.action_coordinator.prepare_action(
                    action_name, params, self.knowledge_manager
                )
                if action:
                    corrected_actions.append({
                        "name": action.name,
                        "params": action.params
                    })
                    logger.info(f"  ✅ {action.name} - ready for execution")
            else:
                validation_errors += 1
                logger.warning(f"  ❌ {action_name} - {error}")
                
        if validation_errors > 0:
            logger.info(f"📋 Validated {len(corrected_actions)}/{len(action_data)} actions ({validation_errors} failed)")
        else:
            logger.info(f"📋 All {len(corrected_actions)} actions validated successfully")
        
        # Track corrected actions
        self.cognitive_loop.action_tracker.set_actions(corrected_actions)
        
        return corrected_actions
    
    async def act(self, action_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """ACT - Execute the decided actions.
        
        Args:
            action_data: Validated action specifications
            
        Returns:
            List of action results
        """
        logger.info(f"⚡ Executing {len(action_data)} actions...")
        
        # Update phase to ACT
        self.cognitive_loop._update_dynamic_context(stage="EXECUTION", phase="ACT")
        
        # Create tag filter for execution stage with our blacklist
        tag_filter = TagFilter(blacklist=self.KNOWLEDGE_BLACKLIST)
        
        # Build execution context with working memory
        context = {
            "cognitive_loop": self.cognitive_loop,
            "memory_system": self.memory_system,
            "cyber_id": self.cyber_id,
            "personal_dir": self.personal,
            "outbox_dir": self.outbox_dir,
            "memory_dir": self.memory_dir,
            "tag_filter": tag_filter  # Make available for actions that need filtered context
        }
        
        # Recreate action objects
        actions = []
        for data in action_data:
            action = self.action_coordinator.prepare_action(
                data["name"], 
                data.get("params", {}),
                self.knowledge_manager
            )
            if action:
                actions.append(action)
        
        # Execute each action
        results = []
        successful_actions = 0
        reference_resolver = ReferenceResolver()
        
        for i, action in enumerate(actions):
            # Resolve @last references in parameters before execution
            if context.get("last_action_result") and action.params:
                resolved_params = reference_resolver.resolve_references(action.params, context)
                action.params = resolved_params
                logger.debug(f"Resolved params for {action.name}: {resolved_params}")
            
            logger.info(f"⚡ Executing action {i+1}/{len(actions)}: {action.name}")
            
            result = await self.action_coordinator.execute_action(action, context)
            results.append(result)
            
            # Log result
            if result["success"]:
                successful_actions += 1
                if result.get("result"):
                    # Show a summary of the result
                    result_str = str(result["result"])
                    if len(result_str) > 150:
                        result_str = result_str[:150] + "..."
                    logger.info(f"  ✅ {action.name} completed: {result_str}")
                else:
                    logger.info(f"  ✅ {action.name} completed successfully")
                    
                # Update context with result for subsequent actions
                context[f"action_{i}_result"] = result["result"]
                context["last_action_result"] = result["result"]
            else:
                error_msg = result.get("error", "Unknown error")
                status = result.get("status", "unknown")
                logger.warning(f"  ❌ {action.name} failed: {error_msg}")
                if status != "unknown":
                    logger.warning(f"    Status: {status}")
                if result.get("result"):
                    logger.warning(f"    Details: {str(result['result'])[:200]}")
                
                # Stop on critical failure
                if action.priority == Priority.HIGH:
                    logger.warning("Critical action failed, stopping sequence")
                    break
                
        # Process results into observations with cycle count
        self.action_coordinator.process_action_results(
            results, 
            self.memory_system, 
            self.cognitive_loop.cycle_count
        )
        
        logger.info(f"⚡ Action phase complete: {successful_actions}/{len(results)} successful")
        
        # Categorize actions into completed and failed
        completed_actions = []
        failed_actions = []
        side_effects = []
        
        for result in results:
            action_summary = {
                "name": result.get("action"),
                "params": result.get("params", {}),
                "status": result.get("status")
            }
            
            if result.get("status") == "completed":
                completed_actions.append(action_summary)
                # Track side effects (e.g., files created, messages sent)
                if "memory" in result.get("action", "").lower():
                    side_effects.append(f"Modified memory: {result.get('result', {}).get('file_path', 'unknown')}")
                elif "message" in result.get("action", "").lower():
                    side_effects.append(f"Sent message to {result.get('params', {}).get('to', 'unknown')}")
            else:
                failed_actions.append(action_summary)
        
        # Track goal progress from current pipeline
        goal_manager = self.cognitive_loop.goal_manager
        
        goal_progress = {}
        # Get decision data from decision buffer
        decision_buffer = self.cognitive_loop.get_current_pipeline("decision")
        decision_file = self.cognitive_loop.personal.parent / decision_buffer.location
        try:
            with open(decision_file, 'r') as f:
                decision_data = json.load(f)
                addresses_goals = decision_data.get("addresses_goals", [])
                for goal_id in addresses_goals:
                    # Simple progress tracking - can be enhanced
                    goal_progress[goal_id] = {
                        "actions_completed": len(completed_actions),
                        "actions_failed": len(failed_actions)
                    }
        except:
            pass  # No decision data available
        
        # Write to execution pipeline buffer
        execution_content = {
            "timestamp": datetime.now().isoformat(),
            "cycle_count": self.cognitive_loop.cycle_count,
            "completed_actions": completed_actions,
            "failed_actions": failed_actions,
            "results": results,
            "side_effects": side_effects,
            "goal_progress": goal_progress
        }
        
        execution_buffer = self.cognitive_loop.get_current_pipeline("execution")
        buffer_file = self.cognitive_loop.personal.parent / execution_buffer.location
        
        with open(buffer_file, 'w') as f:
            json.dump(execution_content, f, indent=2)
        
        # Touch the memory block so it knows when the file was updated
        self.cognitive_loop.memory_system.touch_memory(execution_buffer.id, self.cognitive_loop.cycle_count)
        
        logger.info(f"⚡ Execution written to pipeline buffer: {len(completed_actions)} completed, {len(failed_actions)} failed")
        
        # Clear tracked actions after execution
        self.cognitive_loop.action_tracker.clear_actions()
        
        return results