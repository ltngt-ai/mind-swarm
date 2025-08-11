"""Action coordination and execution management.

This module handles loading available actions, validating parameters,
preparing actions for execution, and processing results.
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import json

from ..knowledge.knowledge_manager import KnowledgeManager
from ..memory import ObservationMemoryBlock, Priority
from ..utils.cognitive_utils import CognitiveUtils

logger = logging.getLogger("Cyber.actions.coordinator")


class ActionCoordinator:
    """Coordinates action loading, validation, and execution."""
    
    def __init__(self, cyber_type: str = 'general'):
        """Initialize action coordinator.
        
        Args:
            cyber_type: Type of Cyber for action filtering
        """
        self.cyber_type = cyber_type
        self.cognitive_utils = CognitiveUtils()
        
        # Import action classes here to avoid circular import
        from .. import actions
        self.Action = actions.Action
        self.ActionStatus = actions.ActionStatus
        self.action_registry = actions.action_registry
        
        # Action tracking
        self.action_history = []
        self.max_history = 100
        
        # Performance metrics
        self.action_metrics = {
            "total_executed": 0,
            "successful": 0,
            "failed": 0,
            "by_action": {}
        }
        
    def get_available_actions(self) -> List[str]:
        """Get list of available actions for this Cyber type.
        
        Returns:
            List of action names
        """
        return self.action_registry.get_actions_for_agent(self.cyber_type)
        
    def validate_action(self, action_name: str, params: Dict[str, Any],
                       knowledge_manager: Optional[KnowledgeManager] = None) -> Tuple[bool, Optional[str]]:
        """Validate an action and its parameters.
        
        Args:
            action_name: Name of the action
            params: Action parameters
            knowledge_manager: Optional knowledge manager for schema lookup
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if action exists for this Cyber type
        available_actions = self.get_available_actions()
        if action_name not in available_actions:
            return False, f"Action '{action_name}' not available for Cyber type '{self.cyber_type}'"
            
        # If knowledge manager provided, validate against schema
        if knowledge_manager:
            action_knowledge = knowledge_manager.get_action_knowledge(action_name)
            if action_knowledge:
                schema = action_knowledge.get("parameter_schema", {})
                
                # Check required parameters
                for param_name, param_info in schema.items():
                    if param_info.get("required", False) and param_name not in params:
                        return False, f"Missing required parameter: {param_name}"
                        
                # Validate parameter types
                for param_name, param_value in params.items():
                    if param_name in schema:
                        expected_type = schema[param_name].get("type")
                        if expected_type and not self._check_param_type(param_value, expected_type):
                            return False, f"Invalid type for {param_name}: expected {expected_type}"
                            
        return True, None
        
    def _check_param_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type.
        
        Args:
            value: Value to check
            expected_type: Expected type string
            
        Returns:
            True if type matches
        """
        type_map = {
            "string": str,
            "str": str,
            "int": int,
            "integer": int,
            "float": float,
            "number": (int, float),
            "bool": bool,
            "boolean": bool,
            "list": list,
            "array": list,
            "dict": dict,
            "object": dict
        }
        
        expected = type_map.get(expected_type.lower())
        if expected:
            return isinstance(value, expected)
        return True  # Unknown type, allow it
        
    def prepare_action(self, action_name: str, params: Dict[str, Any],
                      knowledge_manager: Optional[KnowledgeManager] = None):
        """Prepare an action for execution.
        
        Args:
            action_name: Name of the action
            params: Action parameters
            knowledge_manager: Optional knowledge manager for corrections
            
        Returns:
            Prepared Action object or None if failed
        """
        # Create action instance
        action = self.action_registry.create_action(self.cyber_type, action_name)
        if not action:
            available_actions = self.action_registry.get_actions_for_agent(self.cyber_type)
            logger.error(f"Failed to create action '{action_name}' for Cyber type '{self.cyber_type}'")
            logger.error(f"Available actions for {self.cyber_type}: {', '.join(available_actions)}")
            return None
            
        # Apply parameter corrections if knowledge available
        corrected_params = params.copy()
        
        if knowledge_manager:
            action_knowledge = knowledge_manager.get_action_knowledge(action_name)
            if action_knowledge:
                corrected_params = self._apply_corrections(
                    params, 
                    action_knowledge.get("raw_data", {})
                )
                
        # Set parameters
        try:
            action.with_params(**corrected_params)
            return action
        except Exception as e:
            logger.error(f"Failed to set action parameters: {e}")
            return None
            
    def _apply_corrections(self, params: Dict[str, Any], 
                          action_knowledge: Dict[str, Any]) -> Dict[str, Any]:
        """Apply parameter corrections based on action knowledge.
        
        Args:
            params: Original parameters
            action_knowledge: Action knowledge data
            
        Returns:
            Corrected parameters
        """
        corrected = params.copy()
        
        # Get correction rules
        corrections = action_knowledge.get("common_corrections", [])
        schema = action_knowledge.get("parameter_schema", {})
        
        # Apply alias corrections
        for param_name, param_info in schema.items():
            if param_name not in corrected:
                # Check aliases
                aliases = param_info.get("aliases", [])
                for alias in aliases:
                    if alias in corrected:
                        corrected[param_name] = corrected.pop(alias)
                        logger.debug(f"Applied alias correction: {alias} -> {param_name}")
                        break
                        
        # Apply specific corrections
        for correction in corrections:
            if_param = correction.get("if_param")
            then_rename = correction.get("then_rename")
            if if_param in corrected and then_rename:
                corrected[then_rename] = corrected.pop(if_param)
                logger.debug(f"Applied correction: {if_param} -> {then_rename}")
                
        # Apply defaults for missing optional parameters
        for param_name, param_info in schema.items():
            if param_name not in corrected and "default" in param_info:
                corrected[param_name] = param_info["default"]
                logger.debug(f"Applied default for {param_name}: {param_info['default']}")
                
        return corrected
        
    async def execute_action(self, action, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an action and track results.
        
        Args:
            action: Action to execute
            context: Execution context
            
        Returns:
            Execution result dictionary
        """
        start_time = datetime.now()
        
        # Track execution start
        self.action_metrics["total_executed"] += 1
        
        # Update action-specific metrics
        if action.name not in self.action_metrics["by_action"]:
            self.action_metrics["by_action"][action.name] = {
                "executed": 0,
                "successful": 0,
                "failed": 0,
                "total_duration": 0.0
            }
        self.action_metrics["by_action"][action.name]["executed"] += 1
        
        try:
            # Execute the action
            logger.info(f"Executing action: {action.name}")
            result = await action.execute(context)
            
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()
            
            # Create result dictionary
            execution_result = {
                "action_name": action.name,
                "status": result.status.value,
                "success": result.status == self.ActionStatus.COMPLETED,
                "result": result.result,
                "error": result.error,
                "duration": duration,
                "timestamp": start_time.isoformat(),
                "context_summary": self._summarize_context(context)
            }
            
            # Update metrics
            if result.status == self.ActionStatus.COMPLETED:
                self.action_metrics["successful"] += 1
                self.action_metrics["by_action"][action.name]["successful"] += 1
            else:
                self.action_metrics["failed"] += 1
                self.action_metrics["by_action"][action.name]["failed"] += 1
                
            self.action_metrics["by_action"][action.name]["total_duration"] += duration
            
            # Add to history
            self._add_to_history(execution_result)
            
            return execution_result
            
        except Exception as e:
            logger.error(f"Error executing action {action.name}: {e}", exc_info=True)
            
            # Create error result
            duration = (datetime.now() - start_time).total_seconds()
            execution_result = {
                "action_name": action.name,
                "status": "error",
                "success": False,
                "result": None,
                "error": str(e),
                "duration": duration,
                "timestamp": start_time.isoformat(),
                "context_summary": self._summarize_context(context)
            }
            
            # Update failure metrics
            self.action_metrics["failed"] += 1
            self.action_metrics["by_action"][action.name]["failed"] += 1
            
            self._add_to_history(execution_result)
            
            return execution_result
            
    def _summarize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Create a summary of execution context.
        
        Args:
            context: Full execution context
            
        Returns:
            Context summary
        """
        summary = {
            "cyber_id": context.get("cyber_id", "unknown"),
            "task_id": context.get("task_id"),
            "has_observation": "observation" in context,
            "has_orientation": "orientation" in context
        }
        
        # Add key context elements
        if "observation" in context and isinstance(context["observation"], dict):
            summary["observation_type"] = context["observation"].get("type", "unknown")
            
        if "orientation" in context and isinstance(context["orientation"], dict):
            summary["task_type"] = context["orientation"].get("task_type", "unknown")
            
        return summary
        
    def _add_to_history(self, execution_result: Dict[str, Any]):
        """Add execution result to history.
        
        Args:
            execution_result: Result to add
        """
        # Create compact history entry
        history_entry = {
            "action": execution_result["action_name"],
            "status": execution_result["status"],
            "duration": execution_result["duration"],
            "timestamp": execution_result["timestamp"],
            "error": execution_result.get("error") if not execution_result["success"] else None
        }
        
        self.action_history.append(history_entry)
        
        # Trim history if needed
        if len(self.action_history) > self.max_history:
            self.action_history = self.action_history[-self.max_history:]
            
    def process_action_results(self, results: List[Dict[str, Any]], 
                             memory_manager: Any,
                             cycle_count: int) -> List[ObservationMemoryBlock]:
        """Process action results and create memory observations.
        
        All observations are backed by actual files in the filesystem.
        
        Args:
            results: List of action results
            memory_manager: Memory manager for storing observations
            cycle_count: Current cycle count from cognitive loop
            
        Returns:
            List of created observation memories
        """
        observations = []
        
        # Save action results to disk (these ARE the memory files)
        results_dir = Path("/personal/memory/action_results")
        results_dir.mkdir(parents=True, exist_ok=True)
        
        # Use the passed cycle_count directly
        
        for i, result in enumerate(results):
            # Create unique filename for this action result
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            action_name = result['action_name'].replace(' ', '_').replace('/', '_')
            filename = f"action_{timestamp}_{i}_{action_name}.json"
            filepath = results_dir / filename
            
            # Create descriptive message
            if result["success"]:
                message = f"Result of action '{result['action_name']}': Success"
                if result.get("result"):
                    result_str = str(result["result"])
                    if len(result_str) <= 100:
                        message += f" - {result_str}"
            else:
                message = f"Result of action '{result['action_name']}': Failed"
                if result.get("error"):
                    error_str = str(result["error"])
                    if len(error_str) <= 100:
                        message += f" - {error_str}"
            
            # Determine if we should include content directly (< 1KB)
            inline_content = None
            if result.get("result"):
                result_str = str(result["result"])
                if len(result_str) < 1024:  # Less than 1KB
                    inline_content = result_str
            
            # Write the complete result to file
            result_data = {
                "observation_type": "action_result",
                "action_name": result["action_name"],
                "action_index": i,
                "status": result["status"],
                "success": result["success"],
                "duration": result["duration"],
                "result": result.get("result"),
                "error": result.get("error"),
                "parameters": result.get("parameters", {}),
                "cycle_count": cycle_count
            }
            
            # Write to file
            with open(filepath, 'w') as f:
                json.dump(result_data, f, indent=2, default=str)
            
            # Create observation pointing to the file
            obs = ObservationMemoryBlock(
                observation_type="action_result",
                path=str(filepath),
                message=message,
                cycle_count=cycle_count,
                content=inline_content,  # Include small results directly
                priority=Priority.HIGH if result["success"] else Priority.MEDIUM
            )
            
            observations.append(obs)
            
            # Add to memory if manager provided
            if memory_manager:
                memory_manager.add_memory(obs)
                
        return observations
        
    def _format_result_summary(self, result: Dict[str, Any]) -> str:
        """Format a brief summary of action result.
        
        Args:
            result: Action result
            
        Returns:
            Summary string
        """
        if result["success"]:
            if result.get("result"):
                return str(result["result"])[:100] + "..." if len(str(result["result"])) > 100 else str(result["result"])
            else:
                return "Completed successfully"
        else:
            return f"Failed: {result.get('error', 'Unknown error')}"
            
    def get_action_history(self, limit: int = 10, 
                          action_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent action execution history.
        
        Args:
            limit: Maximum entries to return
            action_name: Filter by specific action
            
        Returns:
            List of history entries
        """
        history = self.action_history
        
        if action_name:
            history = [h for h in history if h["action"] == action_name]
            
        return history[-limit:] if history else []
        
    def get_action_metrics(self) -> Dict[str, Any]:
        """Get action execution metrics.
        
        Returns:
            Metrics dictionary
        """
        # Calculate success rate
        success_rate = (self.action_metrics["successful"] / 
                       self.action_metrics["total_executed"] * 100
                       if self.action_metrics["total_executed"] > 0 else 0)
        
        # Calculate per-action metrics
        action_stats = {}
        for action_name, metrics in self.action_metrics["by_action"].items():
            if metrics["executed"] > 0:
                action_stats[action_name] = {
                    "executed": metrics["executed"],
                    "success_rate": (metrics["successful"] / metrics["executed"] * 100),
                    "average_duration": metrics["total_duration"] / metrics["executed"]
                }
                
        return {
            "total_executed": self.action_metrics["total_executed"],
            "successful": self.action_metrics["successful"],
            "failed": self.action_metrics["failed"],
            "success_rate": success_rate,
            "by_action": action_stats
        }
        
    def reset_metrics(self):
        """Reset action metrics."""
        self.action_metrics = {
            "total_executed": 0,
            "successful": 0,
            "failed": 0,
            "by_action": {}
        }
        logger.info("Action metrics reset")