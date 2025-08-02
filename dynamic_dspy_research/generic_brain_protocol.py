"""Generic Brain Protocol - Dynamic DSPy signature creation from text interface.

This protocol allows agents to specify DSPy signatures dynamically without requiring
predefined types on the server side. The server creates and caches DSPy signatures
based on the signature specification provided in each request.
"""

import json
import hashlib
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from dataclasses import dataclass, asdict


@dataclass
class SignatureSpec:
    """Specification for a DSPy signature that can be created dynamically."""
    
    task: str  # The main task or question
    description: str  # Detailed description of what this signature does
    inputs: Dict[str, str]  # input_name -> description
    outputs: Dict[str, str]  # output_name -> description
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SignatureSpec':
        """Create from dictionary."""
        return cls(**data)
    
    def get_hash(self) -> str:
        """Generate a stable hash for caching purposes."""
        # Create canonical representation for consistent hashing
        canonical = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass
class GenericThinkingRequest:
    """A generic thinking request with dynamic signature specification."""
    
    signature: SignatureSpec
    input_values: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    
    def __post_init__(self):
        """Initialize computed fields."""
        if self.context is None:
            self.context = {}
        if self.request_id is None:
            self.request_id = f"req_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        self.timestamp = datetime.now().isoformat()
    
    def validate(self) -> List[str]:
        """Validate the request and return any errors."""
        errors = []
        
        # Check that all required signature inputs have values
        for input_name in self.signature.inputs.keys():
            if input_name not in self.input_values:
                errors.append(f"Missing input value for '{input_name}'")
        
        # Check for extra input values
        for input_name in self.input_values.keys():
            if input_name not in self.signature.inputs:
                errors.append(f"Unexpected input value '{input_name}' not in signature")
        
        # Basic validation of signature structure
        if not self.signature.task.strip():
            errors.append("Signature task cannot be empty")
        
        if not self.signature.inputs:
            errors.append("Signature must have at least one input")
            
        if not self.signature.outputs:
            errors.append("Signature must have at least one output")
        
        return errors
    
    def to_brain_format(self) -> str:
        """Format for writing to brain communication file."""
        request_data = {
            "type": "generic_thinking_request",
            "request_id": self.request_id,
            "signature": self.signature.to_dict(),
            "input_values": self.input_values,
            "context": self.context,
            "timestamp": self.timestamp
        }
        
        return json.dumps(request_data, indent=2) + "\n<<<END_THOUGHT>>>"
    
    @classmethod
    def from_brain_format(cls, content: str) -> 'GenericThinkingRequest':
        """Parse request from brain communication format."""
        # Remove the end marker if present
        request_text = content.split("<<<END_THOUGHT>>>")[0].strip()
        
        try:
            data = json.loads(request_text)
            
            # Validate it's the right type
            if data.get("type") != "generic_thinking_request":
                raise ValueError(f"Expected 'generic_thinking_request', got '{data.get('type')}'")
            
            # Create signature spec
            signature = SignatureSpec.from_dict(data["signature"])
            
            # Create request
            return cls(
                signature=signature,
                input_values=data["input_values"],
                context=data.get("context"),
                request_id=data.get("request_id")
            )
            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise ValueError(f"Invalid brain format: {e}")


@dataclass
class GenericThinkingResponse:
    """Response from a generic thinking operation."""
    
    output_values: Dict[str, Any]
    request_id: str
    signature_hash: str
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize computed fields."""
        if self.metadata is None:
            self.metadata = {}
        self.timestamp = datetime.now().isoformat()
    
    def to_brain_format(self) -> str:
        """Format for writing to brain communication file."""
        response_data = {
            "type": "generic_thinking_response",
            "request_id": self.request_id,
            "signature_hash": self.signature_hash,
            "output_values": self.output_values,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }
        
        return json.dumps(response_data, indent=2) + "\n<<<THOUGHT_COMPLETE>>>"
    
    @classmethod
    def from_brain_format(cls, content: str) -> 'GenericThinkingResponse':
        """Parse response from brain communication format."""
        # Remove the completion marker
        response_text = content.split("<<<THOUGHT_COMPLETE>>>")[0].strip()
        
        try:
            data = json.loads(response_text)
            
            # Validate it's the right type
            if data.get("type") != "generic_thinking_response":
                raise ValueError(f"Expected 'generic_thinking_response', got '{data.get('type')}'")
            
            return cls(
                output_values=data["output_values"],
                request_id=data["request_id"],
                signature_hash=data["signature_hash"],
                metadata=data.get("metadata")
            )
            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise ValueError(f"Invalid brain format: {e}")


class SignatureBuilder:
    """Helper class for building common signature patterns."""
    
    @staticmethod
    def ooda_observe(custom_inputs: Optional[Dict[str, str]] = None) -> SignatureSpec:
        """Create an OODA Observe signature with optional custom inputs."""
        inputs = {
            "working_memory": "Current contents of working memory",
            "new_messages": "Any new messages or information",
            "environment_state": "Current state of the environment"
        }
        if custom_inputs:
            inputs.update(custom_inputs)
        
        return SignatureSpec(
            task="What has changed or needs attention?",
            description="Observe the environment and identify what's new or important",
            inputs=inputs,
            outputs={
                "observations": "List of things that are new or need attention",
                "priority": "Which observation is most important",
                "urgency": "How urgent is the most important observation"
            }
        )
    
    @staticmethod
    def ooda_orient(custom_inputs: Optional[Dict[str, str]] = None) -> SignatureSpec:
        """Create an OODA Orient signature with optional custom inputs."""
        inputs = {
            "observations": "What was observed",
            "current_task": "Any task currently being worked on",
            "recent_history": "Recent actions and their outcomes"
        }
        if custom_inputs:
            inputs.update(custom_inputs)
        
        return SignatureSpec(
            task="What does this mean and what kind of situation am I in?",
            description="Understand the context and meaning of observations",
            inputs=inputs,
            outputs={
                "situation_type": "What kind of situation this is",
                "understanding": "What I understand about the situation",
                "relevant_knowledge": "What knowledge or skills apply here"
            }
        )
    
    @staticmethod
    def ooda_decide(custom_inputs: Optional[Dict[str, str]] = None) -> SignatureSpec:
        """Create an OODA Decide signature with optional custom inputs."""
        inputs = {
            "understanding": "Understanding of the current situation",
            "available_actions": "What actions can be taken",
            "goals": "Current goals or objectives",
            "constraints": "Any constraints or limitations"
        }
        if custom_inputs:
            inputs.update(custom_inputs)
        
        return SignatureSpec(
            task="What should I do about this?",
            description="Decide on the best approach or action to take",
            inputs=inputs,
            outputs={
                "decision": "What should be done",
                "approach": "How to approach it",
                "reasoning": "Why this is the best choice"
            }
        )
    
    @staticmethod
    def ooda_act(custom_inputs: Optional[Dict[str, str]] = None) -> SignatureSpec:
        """Create an OODA Act signature with optional custom inputs."""
        inputs = {
            "decision": "What was decided",
            "approach": "The chosen approach",
            "available_tools": "Tools and interfaces available",
            "current_state": "Current state to work from"
        }
        if custom_inputs:
            inputs.update(custom_inputs)
        
        return SignatureSpec(
            task="How exactly should I execute this decision?",
            description="Plan the specific steps to implement the decision",
            inputs=inputs,
            outputs={
                "steps": "Ordered list of steps to take",
                "first_action": "The immediate next action",
                "success_criteria": "How to know if it worked"
            }
        )
    
    @staticmethod
    def solve_problem(problem_type: str = "general") -> SignatureSpec:
        """Create a problem-solving signature."""
        return SignatureSpec(
            task=f"Solve this {problem_type} problem step by step",
            description=f"Analyze and solve a {problem_type} problem systematically",
            inputs={
                "problem": "The problem to solve",
                "context": "Any relevant context or constraints",
                "available_resources": "Resources available for solving"
            },
            outputs={
                "analysis": "Analysis of the problem",
                "solution": "The proposed solution",
                "steps": "Step-by-step approach",
                "verification": "How to verify the solution works"
            }
        )
    
    @staticmethod
    def answer_question(domain: str = "general") -> SignatureSpec:
        """Create a question-answering signature."""
        return SignatureSpec(
            task=f"Answer this {domain} question thoughtfully",
            description=f"Provide a comprehensive answer to a {domain} question",
            inputs={
                "question": "The question to answer",
                "context": "Any relevant context",
                "knowledge_base": "Available knowledge or information"
            },
            outputs={
                "answer": "The answer to the question",
                "confidence": "Confidence level in the answer",
                "reasoning": "The reasoning behind the answer",
                "sources": "What knowledge was used"
            }
        )
    
    @staticmethod
    def custom(task: str, inputs: Dict[str, str], outputs: Dict[str, str], 
              description: Optional[str] = None) -> SignatureSpec:
        """Create a completely custom signature."""
        if description is None:
            description = f"Custom thinking operation: {task}"
        
        return SignatureSpec(
            task=task,
            description=description,
            inputs=inputs,
            outputs=outputs
        )


# Convenience functions for common operations
def create_request(signature: SignatureSpec, input_values: Dict[str, Any], 
                  context: Optional[Dict[str, Any]] = None) -> GenericThinkingRequest:
    """Create a generic thinking request."""
    return GenericThinkingRequest(
        signature=signature,
        input_values=input_values,
        context=context
    )


def quick_request(task: str, inputs: Dict[str, str], outputs: Dict[str, str],
                 input_values: Dict[str, Any], description: Optional[str] = None) -> GenericThinkingRequest:
    """Quickly create a request with inline signature definition."""
    signature = SignatureBuilder.custom(task, inputs, outputs, description)
    return create_request(signature, input_values)

