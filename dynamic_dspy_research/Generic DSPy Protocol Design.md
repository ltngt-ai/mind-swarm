# Generic DSPy Protocol Design

## Overview

The current brain protocol requires predefined signature types on the server side. This design proposes a generic protocol where DSPy signatures are created dynamically from client requests, eliminating the need for server-side type definitions.

## Key Changes

### 1. Dynamic Signature Specification

Instead of referencing predefined types like `OBSERVE` or `DECIDE`, clients will specify the complete signature inline:

```json
{
  "type": "generic_thinking_request",
  "signature": {
    "task": "What should I do about this situation?",
    "description": "Analyze the situation and decide on the best course of action",
    "inputs": {
      "situation": "Description of the current situation",
      "available_actions": "List of possible actions I can take",
      "constraints": "Any limitations or constraints to consider"
    },
    "outputs": {
      "decision": "The recommended decision or action",
      "reasoning": "Explanation of why this is the best choice",
      "confidence": "Confidence level in this decision (0-1)"
    }
  },
  "input_values": {
    "situation": "I need to choose between two job offers...",
    "available_actions": ["Accept job A", "Accept job B", "Negotiate with both"],
    "constraints": "Must decide within 48 hours"
  },
  "context": {
    "priority": "high",
    "domain": "career_decision"
  }
}
```

### 2. Server-Side Dynamic Signature Creation

The server will:
1. Parse the signature specification from the request
2. Create a DSPy signature class dynamically
3. Cache the signature for reuse (keyed by signature hash)
4. Execute the signature with the provided inputs
5. Return the structured outputs

### 3. Signature Caching Strategy

To avoid recreating identical signatures:
- Generate a hash from the signature specification (task + inputs + outputs)
- Cache compiled DSPy signatures using this hash as the key
- Reuse cached signatures for identical specifications

### 4. Backward Compatibility

The new protocol can coexist with the old one:
- Keep existing predefined signatures as convenience methods
- Allow clients to use either approach
- Gradually migrate to the generic approach

## Benefits

1. **No Server Updates Required**: New thinking patterns don't require server code changes
2. **Flexible Signatures**: Clients can create task-specific signatures on demand
3. **Reduced Coupling**: Client and server are less tightly coupled
4. **Easier Testing**: Can test different signature variations without server deployment
5. **Performance**: Caching ensures repeated signatures are fast

## Implementation Plan

### Phase 1: Core Protocol
- Define JSON schema for generic requests
- Implement dynamic signature creation
- Add basic caching

### Phase 2: Advanced Features
- Signature validation and error handling
- Performance optimization
- Monitoring and debugging tools

### Phase 3: Migration
- Provide migration utilities
- Update documentation
- Deprecate old approach gradually

## Example Use Cases

### 1. OODA Loop Operations
```json
{
  "signature": {
    "task": "Observe the current situation",
    "inputs": {"environment": "Current state description"},
    "outputs": {"observations": "Key things to notice", "priority": "Most important item"}
  }
}
```

### 2. Mathematical Problem Solving
```json
{
  "signature": {
    "task": "Solve this math problem step by step",
    "inputs": {"problem": "Mathematical expression or word problem"},
    "outputs": {"solution": "Step-by-step solution", "answer": "Final numerical answer"}
  }
}
```

### 3. Creative Writing
```json
{
  "signature": {
    "task": "Generate creative content based on prompts",
    "inputs": {"genre": "Writing genre", "prompt": "Creative prompt", "length": "Desired length"},
    "outputs": {"content": "Generated creative content", "style_notes": "Notes about the style used"}
  }
}
```

## Technical Considerations

### Signature Hashing
Use a stable hash of the signature specification:
```python
import hashlib
import json

def signature_hash(signature_spec):
    # Ensure consistent ordering for hashing
    canonical = json.dumps(signature_spec, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()
```

### DSPy Integration
```python
import dspy
from typing import Dict, Any

def create_dynamic_signature(signature_spec: Dict[str, Any]):
    # Create input fields
    inputs = {}
    for name, desc in signature_spec["inputs"].items():
        inputs[name] = dspy.InputField(desc=desc)
    
    # Create output fields  
    outputs = {}
    for name, desc in signature_spec["outputs"].items():
        outputs[name] = dspy.OutputField(desc=desc)
    
    # Create the signature class dynamically
    signature_class = type(
        "DynamicSignature",
        (dspy.Signature,),
        {**inputs, **outputs, "__doc__": signature_spec["task"]}
    )
    
    return signature_class
```

### Error Handling
- Validate signature specifications before processing
- Provide clear error messages for malformed requests
- Handle DSPy execution errors gracefully
- Log signature creation and execution for debugging

This design provides a flexible, scalable approach to DSPy integration while maintaining the simplicity of the file-based communication protocol.

