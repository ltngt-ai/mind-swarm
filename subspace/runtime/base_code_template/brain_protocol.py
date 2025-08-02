"""Generic Brain Protocol - Agent-defined thinking signatures.

This protocol allows agents to define their own thinking operations by specifying
signatures (task, inputs, outputs). The server dynamically creates DSPy signatures
from these specifications, with no knowledge of what specific thinking patterns mean.

Key points:
- Agents define what thinking operations they need
- Server just executes whatever signature specification it receives
- Adding new thinking modes only requires agent-side changes
- No fixed "types" or enums on the server
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
            
            return cls(
                output_values=data["output_values"],
                request_id=data["request_id"],
                signature_hash=data["signature_hash"],
                metadata=data.get("metadata")
            )
            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise ValueError(f"Invalid brain format: {e}")




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