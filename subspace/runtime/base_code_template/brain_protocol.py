"""Brain Protocol - Defines how agents communicate thinking requests across the sandbox boundary.

The brain interface uses a DSPy-inspired signature approach where each thinking
operation has:
- A clear question or task
- Defined inputs with their descriptions
- Expected outputs with their descriptions

This allows the server-side brain to use DSPy or other LLM frameworks while
the agent side remains simple and sandbox-contained.
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime


class ThinkingSignature:
    """Represents a thinking operation signature."""
    
    def __init__(self, 
                 task: str,
                 description: str,
                 inputs: Dict[str, str],
                 outputs: Dict[str, str]):
        """Initialize a thinking signature.
        
        Args:
            task: The question or task to perform
            description: Longer description of what this thinking step does
            inputs: Dict of input_name -> description
            outputs: Dict of output_name -> description
        """
        self.task = task
        self.description = description
        self.inputs = inputs
        self.outputs = outputs
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "task": self.task,
            "description": self.description,
            "inputs": self.inputs,
            "outputs": self.outputs
        }


class ThinkingRequest:
    """A request to think about something."""
    
    def __init__(self, 
                 signature: ThinkingSignature,
                 input_values: Dict[str, Any],
                 context: Optional[Dict[str, Any]] = None):
        """Initialize a thinking request.
        
        Args:
            signature: The thinking operation signature
            input_values: Actual values for the inputs
            context: Optional additional context
        """
        self.signature = signature
        self.input_values = input_values
        self.context = context or {}
        self.timestamp = datetime.now().isoformat()
        
    def to_brain_format(self) -> str:
        """Format for writing to brain file."""
        # Create a structured format that the server can parse
        request = {
            "type": "thinking_request",
            "signature": self.signature.to_dict(),
            "input_values": self.input_values,
            "context": self.context,
            "timestamp": self.timestamp
        }
        
        # Convert to JSON for transport
        return json.dumps(request, indent=2) + "\n<<<END_THOUGHT>>>"


class ThinkingResponse:
    """A response from thinking."""
    
    def __init__(self, output_values: Dict[str, Any], metadata: Optional[Dict] = None):
        """Initialize thinking response.
        
        Args:
            output_values: The outputs produced
            metadata: Optional metadata about the thinking
        """
        self.output_values = output_values
        self.metadata = metadata or {}
        
    @classmethod
    def from_brain_format(cls, content: str) -> 'ThinkingResponse':
        """Parse response from brain file format."""
        # Remove the completion marker
        response_text = content.split("<<<THOUGHT_COMPLETE>>>")[0].strip()
        
        try:
            # Try to parse as JSON first
            response_data = json.loads(response_text)
            if isinstance(response_data, dict) and "output_values" in response_data:
                return cls(
                    output_values=response_data["output_values"],
                    metadata=response_data.get("metadata", {})
                )
        except json.JSONDecodeError:
            pass
        
        # Fallback: treat as single text output
        return cls(output_values={"response": response_text})


# Pre-defined signatures for common cognitive operations
class CognitiveSignatures:
    """Standard thinking signatures for the OODA loop."""
    
    OBSERVE = ThinkingSignature(
        task="What has changed or needs attention?",
        description="Observe the environment and identify what's new or important",
        inputs={
            "working_memory": "Current contents of working memory",
            "new_messages": "Any new messages in inbox",
            "environment_state": "Current state of my environment"
        },
        outputs={
            "observations": "List of things that are new or need attention",
            "priority": "Which observation is most important"
        }
    )
    
    ORIENT = ThinkingSignature(
        task="What does this mean and what kind of situation am I in?",
        description="Understand the context and meaning of observations",
        inputs={
            "observations": "What was observed",
            "current_task": "Any task I'm currently working on",
            "recent_history": "Recent actions and their outcomes"
        },
        outputs={
            "situation_type": "What kind of situation this is",
            "understanding": "What I understand about the situation",
            "relevant_knowledge": "What knowledge or skills apply here"
        }
    )
    
    DECIDE = ThinkingSignature(
        task="What should I do about this?",
        description="Decide on the best approach or action to take",
        inputs={
            "understanding": "My understanding of the situation",
            "available_actions": "What actions I can take",
            "goals": "My current goals or objectives",
            "constraints": "Any constraints or limitations"
        },
        outputs={
            "decision": "What I've decided to do",
            "approach": "How I'll approach it",
            "reasoning": "Why this is the best choice"
        }
    )
    
    ACT_PLANNING = ThinkingSignature(
        task="How exactly should I execute this decision?",
        description="Plan the specific steps to implement the decision",
        inputs={
            "decision": "What was decided",
            "approach": "The chosen approach",
            "available_tools": "Tools and interfaces available",
            "current_state": "Current state to work from"
        },
        outputs={
            "steps": "Ordered list of steps to take",
            "first_action": "The immediate next action"
        }
    )
    
    REFLECT = ThinkingSignature(
        task="What happened and what did I learn?",
        description="Reflect on actions taken and results achieved",
        inputs={
            "action_taken": "What action was performed",
            "expected_outcome": "What was expected to happen",
            "actual_outcome": "What actually happened",
            "surprises": "Anything unexpected"
        },
        outputs={
            "assessment": "How well did it go",
            "lessons": "What was learned",
            "next_time": "What to do differently next time"
        }
    )
    
    # Specific thinking operations
    SOLVE_ARITHMETIC = ThinkingSignature(
        task="Solve this arithmetic problem step by step",
        description="Perform mathematical calculations",
        inputs={
            "problem": "The math problem to solve",
            "context": "Any context about the problem"
        },
        outputs={
            "steps": "Step by step solution",
            "answer": "The final answer",
            "verification": "How to check the answer is correct"
        }
    )
    
    ANSWER_QUESTION = ThinkingSignature(
        task="Answer this question based on available knowledge",
        description="Provide a thoughtful answer to a question",
        inputs={
            "question": "The question to answer",
            "context": "Context about the question",
            "relevant_knowledge": "Any relevant facts or information"
        },
        outputs={
            "answer": "The answer to the question",
            "confidence": "How confident in the answer",
            "reasoning": "The reasoning behind the answer"
        }
    )