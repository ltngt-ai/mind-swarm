"""Server-side brain handler - processes thinking requests from agents.

This is where the actual intelligence happens. It receives structured
thinking requests from agents and uses DSPy to process them, returning
structured responses.
"""

import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

import dspy

from mind_swarm.utils.logging import logger


class BrainHandler:
    """Handles brain thinking requests from agents."""
    
    def __init__(self, ai_service):
        """Initialize brain handler.
        
        Args:
            ai_service: The AI service to use for thinking
        """
        self.ai_service = ai_service
        
        # Initialize DSPy with the AI service
        # This would need proper configuration based on the AI service type
        # For now, we'll assume it's configured elsewhere
        
        # Cache of DSPy signatures for common operations
        self.signatures = {}
        self._init_signatures()
        
    def _init_signatures(self):
        """Initialize DSPy signatures for standard cognitive operations."""
        
        # Observation signature
        class ObserveSignature(dspy.Signature):
            """Observe the environment and identify what needs attention."""
            working_memory = dspy.InputField(desc="Current contents of working memory")
            new_messages = dspy.InputField(desc="Any new messages in inbox")
            environment_state = dspy.InputField(desc="Current state of environment")
            
            observations = dspy.OutputField(desc="List of things that are new or need attention")
            priority = dspy.OutputField(desc="Which observation is most important")
        
        self.signatures["observe"] = ObserveSignature
        
        # Orientation signature
        class OrientSignature(dspy.Signature):
            """Understand the context and meaning of observations."""
            observations = dspy.InputField(desc="What was observed")
            current_task = dspy.InputField(desc="Any task currently being worked on")
            recent_history = dspy.InputField(desc="Recent actions and outcomes")
            
            situation_type = dspy.OutputField(desc="What kind of situation this is")
            understanding = dspy.OutputField(desc="What I understand about the situation")
            relevant_knowledge = dspy.OutputField(desc="What knowledge or skills apply")
        
        self.signatures["orient"] = OrientSignature
        
        # Decision signature
        class DecideSignature(dspy.Signature):
            """Decide on the best approach or action to take."""
            understanding = dspy.InputField(desc="Understanding of the situation")
            available_actions = dspy.InputField(desc="What actions can be taken")
            goals = dspy.InputField(desc="Current goals or objectives")
            constraints = dspy.InputField(desc="Any constraints or limitations")
            
            decision = dspy.OutputField(desc="What to do")
            approach = dspy.OutputField(desc="How to approach it")
            reasoning = dspy.OutputField(desc="Why this is the best choice")
        
        self.signatures["decide"] = DecideSignature
        
        # Action planning signature
        class ActPlanningSignature(dspy.Signature):
            """Plan the specific steps to implement a decision."""
            decision = dspy.InputField(desc="What was decided")
            approach = dspy.InputField(desc="The chosen approach")
            available_tools = dspy.InputField(desc="Tools and interfaces available")
            current_state = dspy.InputField(desc="Current state to work from")
            
            steps = dspy.OutputField(desc="Ordered list of steps to take")
            first_action = dspy.OutputField(desc="The immediate next action")
        
        self.signatures["act_planning"] = ActPlanningSignature
        
        # Arithmetic signature
        class ArithmeticSignature(dspy.Signature):
            """Solve arithmetic problems step by step."""
            problem = dspy.InputField(desc="The math problem to solve")
            context = dspy.InputField(desc="Any context about the problem")
            
            steps = dspy.OutputField(desc="Step by step solution")
            answer = dspy.OutputField(desc="The final answer")
            verification = dspy.OutputField(desc="How to verify the answer")
        
        self.signatures["arithmetic"] = ArithmeticSignature
        
        # Question answering signature
        class QuestionSignature(dspy.Signature):
            """Answer questions based on available knowledge."""
            question = dspy.InputField(desc="The question to answer")
            context = dspy.InputField(desc="Context about the question")
            relevant_knowledge = dspy.InputField(desc="Any relevant facts")
            
            answer = dspy.OutputField(desc="The answer to the question")
            confidence = dspy.OutputField(desc="Confidence level (high/medium/low)")
            reasoning = dspy.OutputField(desc="The reasoning process")
        
        self.signatures["question"] = QuestionSignature
        
        # Reflection signature
        class ReflectSignature(dspy.Signature):
            """Reflect on actions and learn from outcomes."""
            action_taken = dspy.InputField(desc="What action was performed")
            expected_outcome = dspy.InputField(desc="What was expected")
            actual_outcome = dspy.InputField(desc="What actually happened")
            surprises = dspy.InputField(desc="Anything unexpected")
            
            assessment = dspy.OutputField(desc="How well it went")
            lessons = dspy.OutputField(desc="What was learned")
            next_time = dspy.OutputField(desc="What to do differently")
        
        self.signatures["reflect"] = ReflectSignature
    
    async def process_thinking_request(self, agent_id: str, request_text: str) -> str:
        """Process a thinking request from an agent.
        
        Args:
            agent_id: The agent making the request
            request_text: The thinking request in JSON format
            
        Returns:
            Response text to write back to brain file
        """
        try:
            # Parse the request
            request = json.loads(request_text.replace("<<<END_THOUGHT>>>", "").strip())
            
            if request.get("type") != "thinking_request":
                # Handle legacy format - just a plain prompt
                return await self._handle_legacy_prompt(agent_id, request_text)
            
            # Extract signature and inputs
            signature_info = request.get("signature", {})
            input_values = request.get("input_values", {})
            
            # Determine which signature to use
            signature_type = self._identify_signature_type(signature_info)
            
            if signature_type in self.signatures:
                # Use DSPy signature
                response = await self._process_with_dspy(
                    signature_type,
                    input_values,
                    agent_id
                )
            else:
                # Fallback to general processing
                response = await self._process_general(
                    signature_info,
                    input_values,
                    agent_id
                )
            
            # Format response
            return self._format_response(response)
            
        except json.JSONDecodeError:
            # Handle as plain text prompt
            return await self._handle_legacy_prompt(agent_id, request_text)
        except Exception as e:
            logger.error(f"Error processing thinking request: {e}", exc_info=True)
            return f"Error in thinking: {str(e)}"
    
    def _identify_signature_type(self, signature_info: Dict) -> str:
        """Identify which DSPy signature to use based on the task."""
        task = signature_info.get("task", "").lower()
        
        if "what has changed" in task or "observe" in task:
            return "observe"
        elif "what does this mean" in task or "orient" in task:
            return "orient"
        elif "what should i do" in task or "decide" in task:
            return "decide"
        elif "how exactly" in task or "execute" in task:
            return "act_planning"
        elif "arithmetic" in task or "math" in task:
            return "arithmetic"
        elif "answer" in task and "question" in task:
            return "question"
        elif "reflect" in task or "learn" in task:
            return "reflect"
        
        return "general"
    
    async def _process_with_dspy(self, signature_type: str, inputs: Dict, agent_id: str) -> Dict:
        """Process using a specific DSPy signature."""
        signature_class = self.signatures[signature_type]
        
        # Create a DSPy predictor
        predictor = dspy.Predict(signature_class)
        
        # Execute the prediction
        # Note: This is simplified - in reality we'd need to properly
        # configure DSPy with the AI service
        try:
            # For now, we'll simulate DSPy processing
            # In production, this would actually use the configured LM
            result = await self._simulate_dspy_processing(
                signature_type,
                inputs,
                agent_id
            )
            
            return {
                "output_values": result,
                "metadata": {
                    "signature_type": signature_type,
                    "processed_by": "dspy"
                }
            }
            
        except Exception as e:
            logger.error(f"DSPy processing error: {e}")
            return {
                "output_values": {"error": str(e)},
                "metadata": {"error": True}
            }
    
    async def _simulate_dspy_processing(self, signature_type: str, inputs: Dict, agent_id: str) -> Dict:
        """Simulate DSPy processing until properly integrated."""
        # Build a prompt based on the signature type and inputs
        prompt = self._build_prompt_from_signature(signature_type, inputs)
        
        # Use the AI service
        response = await self.ai_service.generate(prompt)
        
        # Parse response into expected outputs
        return self._parse_response_for_signature(signature_type, response)
    
    def _build_prompt_from_signature(self, signature_type: str, inputs: Dict) -> str:
        """Build a prompt from signature type and inputs."""
        # This is a simplified version - DSPy would handle this more elegantly
        
        if signature_type == "observe":
            return f"""As an agent in the Mind-Swarm, observe your environment and identify what needs attention.

Working Memory:
{inputs.get('working_memory', 'Empty')}

New Messages:
{inputs.get('new_messages', 'None')}

Environment State:
{inputs.get('environment_state', 'Unknown')}

Please identify:
1. What observations are important (list them)
2. Which observation has the highest priority

Format your response as:
OBSERVATIONS: [list of observations]
PRIORITY: [most important observation]"""
        
        elif signature_type == "arithmetic":
            return f"""Solve this arithmetic problem step by step.

Problem: {inputs.get('problem', '')}
Context: {inputs.get('context', '')}

Show:
1. Step by step solution
2. The final answer
3. How to verify the answer is correct"""
        
        # Add more signature types as needed
        else:
            return f"Process this thinking request:\n{json.dumps(inputs, indent=2)}"
    
    def _parse_response_for_signature(self, signature_type: str, response: str) -> Dict:
        """Parse AI response into expected output format."""
        # This is simplified - would be more sophisticated in practice
        
        if signature_type == "observe":
            # Try to extract observations and priority
            lines = response.split('\n')
            observations = []
            priority = ""
            
            for line in lines:
                if line.startswith("OBSERVATIONS:"):
                    observations = [line.replace("OBSERVATIONS:", "").strip()]
                elif line.startswith("PRIORITY:"):
                    priority = line.replace("PRIORITY:", "").strip()
                elif line.strip().startswith("-") or line.strip().startswith("•"):
                    observations.append(line.strip().lstrip("-•").strip())
            
            return {
                "observations": observations if observations else [response],
                "priority": priority if priority else "Process new information"
            }
        
        elif signature_type == "arithmetic":
            # Try to extract answer
            answer = None
            for line in response.split('\n'):
                if 'answer' in line.lower() and ('=' in line or ':' in line):
                    # Extract number after = or :
                    parts = line.split('=' if '=' in line else ':')
                    if len(parts) > 1:
                        answer = parts[1].strip()
                        break
            
            return {
                "steps": response,
                "answer": answer if answer else "Could not determine",
                "verification": "Check by reversing the operation"
            }
        
        # Default parsing
        return {"response": response}
    
    async def _process_general(self, signature_info: Dict, inputs: Dict, agent_id: str) -> Dict:
        """Process a general thinking request without a specific signature."""
        # Build a general prompt
        prompt = f"""Task: {signature_info.get('task', 'Think about this')}

Description: {signature_info.get('description', '')}

Inputs:
{json.dumps(inputs, indent=2)}

Expected outputs: {', '.join(signature_info.get('outputs', {}).keys())}

Please provide a thoughtful response addressing the task."""
        
        response = await self.ai_service.generate(prompt)
        
        return {
            "output_values": {"response": response},
            "metadata": {"processed_by": "general"}
        }
    
    async def _handle_legacy_prompt(self, agent_id: str, prompt: str) -> str:
        """Handle legacy-style plain text prompts."""
        # Clean up the prompt
        prompt = prompt.replace("<<<END_THOUGHT>>>", "").strip()
        
        # Just pass it through to the AI service
        response = await self.ai_service.generate(prompt)
        
        return response
    
    def _format_response(self, response: Dict) -> str:
        """Format response for writing back to brain file."""
        # Convert to JSON for structured responses
        return json.dumps(response, indent=2) + "\n<<<THOUGHT_COMPLETE>>>"