"""Brain Handler V2 - Server-side intelligence using DSPy.

This implements the actual thinking using DSPy modules for each cognitive
operation. It processes structured thinking requests from agents and returns
structured responses.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

import dspy

from mind_swarm.utils.logging import logger
from mind_swarm.subspace.dspy_config import configure_dspy_for_mind_swarm


# DSPy Signatures for cognitive operations
class ObserveSignature(dspy.Signature):
    """Observe the environment and identify what needs attention."""
    working_memory: str = dspy.InputField(desc="Current contents of working memory")
    new_messages: str = dspy.InputField(desc="Any new messages in inbox")
    environment_state: str = dspy.InputField(desc="Current state of environment")
    
    observations: str = dspy.OutputField(desc="List of things that are new or need attention, separated by semicolons")
    priority: str = dspy.OutputField(desc="Which observation is most important and why")


class OrientSignature(dspy.Signature):
    """Understand the context and meaning of observations."""
    observations: str = dspy.InputField(desc="What was observed")
    current_task: str = dspy.InputField(desc="Any task currently being worked on")
    recent_history: str = dspy.InputField(desc="Recent actions and outcomes")
    
    situation_type: str = dspy.OutputField(desc="What kind of situation this is (e.g., new_task, continuation, idle)")
    understanding: str = dspy.OutputField(desc="Clear understanding of what's happening and what it means")
    relevant_knowledge: str = dspy.OutputField(desc="What knowledge, skills, or past experiences apply here")


class DecideSignature(dspy.Signature):
    """Decide on the best approach or action to take."""
    understanding: str = dspy.InputField(desc="Understanding of the situation")
    available_actions: str = dspy.InputField(desc="What actions can be taken")
    goals: str = dspy.InputField(desc="Current goals or objectives")
    constraints: str = dspy.InputField(desc="Any constraints or limitations")
    
    decision: str = dspy.OutputField(desc="The specific action to take")
    approach: str = dspy.OutputField(desc="How to approach it strategically")
    reasoning: str = dspy.OutputField(desc="Why this is the best choice given the situation")


class ActPlanningSignature(dspy.Signature):
    """Plan the specific steps to implement a decision."""
    decision: str = dspy.InputField(desc="What was decided")
    approach: str = dspy.InputField(desc="The chosen approach")
    available_tools: str = dspy.InputField(desc="Tools and interfaces available")
    current_state: str = dspy.InputField(desc="Current state to work from")
    
    steps: str = dspy.OutputField(desc="Ordered list of concrete steps to take, separated by semicolons")
    first_action: str = dspy.OutputField(desc="The immediate next action to take")


class ReflectSignature(dspy.Signature):
    """Reflect on actions and learn from outcomes."""
    action_taken: str = dspy.InputField(desc="What action was performed")
    expected_outcome: str = dspy.InputField(desc="What was expected to happen")
    actual_outcome: str = dspy.InputField(desc="What actually happened")
    surprises: str = dspy.InputField(desc="Anything unexpected")
    
    assessment: str = dspy.OutputField(desc="Overall assessment of how well it went")
    lessons: str = dspy.OutputField(desc="Key lessons learned from this experience")
    next_time: str = dspy.OutputField(desc="What to do differently next time")


class ArithmeticSignature(dspy.Signature):
    """Solve arithmetic problems step by step."""
    problem: str = dspy.InputField(desc="The math problem to solve")
    context: str = dspy.InputField(desc="Any context about the problem")
    
    steps: str = dspy.OutputField(desc="Step by step solution showing all work")
    answer: str = dspy.OutputField(desc="The final numerical answer")
    verification: str = dspy.OutputField(desc="How to verify the answer is correct")


class QuestionAnsweringSignature(dspy.Signature):
    """Answer questions based on available knowledge."""
    question: str = dspy.InputField(desc="The question to answer")
    context: str = dspy.InputField(desc="Context about the question")
    relevant_knowledge: str = dspy.InputField(desc="Any relevant facts or knowledge")
    
    answer: str = dspy.OutputField(desc="Clear, complete answer to the question")
    confidence: str = dspy.OutputField(desc="Confidence level: high, medium, or low")
    reasoning: str = dspy.OutputField(desc="The reasoning process used to arrive at the answer")


class BrainHandlerV2:
    """Processes agent thinking requests using DSPy."""
    
    def __init__(self, lm_config: Dict[str, Any]):
        """Initialize the brain handler with language model configuration.
        
        Args:
            lm_config: Configuration for the language model
        """
        # Configure DSPy with the language model
        self._configure_dspy(lm_config)
        
        # Create predictors for each cognitive operation
        self.predictors = {
            "observe": dspy.Predict(ObserveSignature),
            "orient": dspy.Predict(OrientSignature),
            "decide": dspy.Predict(DecideSignature),
            "act_planning": dspy.Predict(ActPlanningSignature),
            "reflect": dspy.Predict(ReflectSignature),
            "arithmetic": dspy.Predict(ArithmeticSignature),
            "question": dspy.Predict(QuestionAnsweringSignature)
        }
        
        logger.info("BrainHandlerV2 initialized with DSPy predictors")
    
    def _configure_dspy(self, lm_config: Dict[str, Any]):
        """Configure DSPy with the appropriate language model."""
        # Use our custom DSPy configuration
        configure_dspy_for_mind_swarm(lm_config)
    
    async def process_thinking_request(self, agent_id: str, request_text: str) -> str:
        """Process a thinking request from an agent.
        
        Args:
            agent_id: The agent making the request
            request_text: The thinking request (JSON format)
            
        Returns:
            Response in the expected format
        """
        try:
            # Remove end marker and parse
            clean_text = request_text.replace("<<<END_THOUGHT>>>", "").strip()
            
            # Try to parse as JSON
            try:
                request_data = json.loads(clean_text)
            except json.JSONDecodeError:
                # Handle as legacy plain text
                return await self._handle_legacy_request(agent_id, clean_text)
            
            # Check if it's a structured thinking request
            if request_data.get("type") != "thinking_request":
                return await self._handle_legacy_request(agent_id, clean_text)
            
            # Extract components
            signature_info = request_data.get("signature", {})
            input_values = request_data.get("input_values", {})
            
            # Process the thinking request
            result = await self._process_thinking(
                agent_id,
                signature_info,
                input_values
            )
            
            # Format and return response
            return self._format_response(result)
            
        except Exception as e:
            logger.error(f"Error processing thinking request from {agent_id}: {e}", exc_info=True)
            return json.dumps({
                "output_values": {"error": str(e)},
                "metadata": {"error": True}
            }) + "\n<<<THOUGHT_COMPLETE>>>"
    
    async def _process_thinking(
        self, 
        agent_id: str,
        signature_info: Dict[str, Any],
        input_values: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process a structured thinking request."""
        # Identify which cognitive operation this is
        operation_type = self._identify_operation(signature_info)
        
        logger.info(f"Agent {agent_id} thinking: {operation_type}")
        
        # Get the appropriate predictor
        predictor = self.predictors.get(operation_type)
        if not predictor:
            logger.warning(f"No predictor for operation type: {operation_type}")
            return {
                "output_values": {
                    "response": f"I don't know how to handle '{operation_type}' operations yet."
                },
                "metadata": {"operation": operation_type, "fallback": True}
            }
        
        try:
            # Convert input values to strings (DSPy expects strings)
            str_inputs = self._stringify_inputs(input_values)
            
            # Execute the prediction
            prediction = predictor(**str_inputs)
            
            # Convert prediction to output values
            output_values = self._extract_outputs(prediction, operation_type)
            
            return {
                "output_values": output_values,
                "metadata": {
                    "operation": operation_type,
                    "agent_id": agent_id,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error in DSPy prediction: {e}", exc_info=True)
            return {
                "output_values": {"error": str(e)},
                "metadata": {"operation": operation_type, "error": True}
            }
    
    def _identify_operation(self, signature_info: Dict[str, Any]) -> str:
        """Identify which cognitive operation to use."""
        task = signature_info.get("task", "").lower()
        
        # Check for specific operations
        if "observe" in task or "what has changed" in task:
            return "observe"
        elif "orient" in task or "what does this mean" in task:
            return "orient"
        elif "decide" in task or "what should i do" in task:
            return "decide"
        elif "plan" in task or "how exactly" in task or "execute" in task:
            return "act_planning"
        elif "reflect" in task or "what happened" in task or "learn" in task:
            return "reflect"
        elif "arithmetic" in task or "solve" in task or "calculate" in task:
            return "arithmetic"
        elif "answer" in task or "question" in task:
            return "question"
        
        # Default to question answering
        return "question"
    
    def _stringify_inputs(self, input_values: Dict[str, Any]) -> Dict[str, str]:
        """Convert all input values to strings for DSPy."""
        str_inputs = {}
        
        for key, value in input_values.items():
            if isinstance(value, str):
                str_inputs[key] = value
            elif isinstance(value, list):
                # Join lists with semicolons
                str_inputs[key] = "; ".join(str(item) for item in value)
            elif isinstance(value, dict):
                # Convert dict to readable format
                str_inputs[key] = "; ".join(f"{k}: {v}" for k, v in value.items())
            else:
                str_inputs[key] = str(value)
        
        return str_inputs
    
    def _extract_outputs(self, prediction: Any, operation_type: str) -> Dict[str, Any]:
        """Extract output values from DSPy prediction."""
        outputs = {}
        
        # Get the signature class to know expected outputs
        signature_map = {
            "observe": ObserveSignature,
            "orient": OrientSignature,
            "decide": DecideSignature,
            "act_planning": ActPlanningSignature,
            "reflect": ReflectSignature,
            "arithmetic": ArithmeticSignature,
            "question": QuestionAnsweringSignature
        }
        
        signature_class = signature_map.get(operation_type)
        if not signature_class:
            # Fallback - extract all attributes
            for attr in dir(prediction):
                if not attr.startswith('_'):
                    value = getattr(prediction, attr, None)
                    if value is not None:
                        outputs[attr] = value
            return outputs
        
        # Extract expected outputs
        for field_name, field_obj in signature_class.__annotations__.items():
            # Skip input fields
            if hasattr(field_obj, '__origin__') and 'InputField' in str(field_obj):
                continue
            
            # Get the output value
            value = getattr(prediction, field_name, None)
            if value is not None:
                # Convert semicolon-separated lists back to lists for some fields
                if field_name in ["observations", "steps"] and ";" in str(value):
                    outputs[field_name] = [item.strip() for item in str(value).split(";")]
                else:
                    outputs[field_name] = value
        
        return outputs
    
    def _format_response(self, result: Dict[str, Any]) -> str:
        """Format the result for sending back to the agent."""
        return json.dumps(result, indent=2) + "\n<<<THOUGHT_COMPLETE>>>"
    
    async def _handle_legacy_request(self, agent_id: str, prompt: str) -> str:
        """Handle legacy plain-text thinking requests."""
        logger.info(f"Handling legacy request from {agent_id}")
        
        # Use the question answering predictor for general prompts
        predictor = self.predictors["question"]
        
        try:
            prediction = predictor(
                question=prompt,
                context=f"Agent {agent_id} is thinking",
                relevant_knowledge="I am an AI agent in the Mind-Swarm collective"
            )
            
            return prediction.answer + "\n<<<THOUGHT_COMPLETE>>>"
            
        except Exception as e:
            logger.error(f"Error in legacy request handling: {e}")
            return f"I encountered an error while thinking: {str(e)}\n<<<THOUGHT_COMPLETE>>>"