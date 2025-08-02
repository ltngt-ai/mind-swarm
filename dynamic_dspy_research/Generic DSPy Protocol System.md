# Generic DSPy Protocol System

A flexible, dynamic protocol for creating and executing DSPy signatures without requiring predefined types on the server side. This system allows agents running in sandboxes to specify thinking operations dynamically while maintaining performance through intelligent caching.

## Overview

The Generic DSPy Protocol eliminates the need for predefined signature types by allowing clients to specify complete DSPy signatures inline with their requests. The server dynamically creates and caches these signatures, providing both flexibility and performance.

### Key Features

- **Dynamic Signature Creation**: Create DSPy signatures on-the-fly from JSON specifications
- **Intelligent Caching**: Automatic caching of compiled signatures for performance
- **File-based Communication**: Works across sandbox boundaries using file I/O
- **Backward Compatibility**: Can coexist with existing predefined signature systems
- **Type Safety**: Full validation of signature specifications and requests
- **Easy Migration**: Simple path from fixed types to dynamic signatures

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Sandbox       │    │  Communication   │    │   Server        │
│   Agent         │    │  Layer           │    │   Side          │
│                 │    │                  │    │                 │
│ ┌─────────────┐ │    │ ┌──────────────┐ │    │ ┌─────────────┐ │
│ │BrainClient  │◄┼────┼►│ File I/O     │◄┼────┼►│DSPy Server  │ │
│ │             │ │    │ │ Protocol     │ │    │ │             │ │
│ └─────────────┘ │    │ └──────────────┘ │    │ └─────────────┘ │
│                 │    │                  │    │        │        │
│ ┌─────────────┐ │    │                  │    │ ┌─────────────┐ │
│ │SimpleBrain  │ │    │                  │    │ │Signature    │ │
│ │             │ │    │                  │    │ │Cache        │ │
│ └─────────────┘ │    │                  │    │ └─────────────┘ │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Quick Start

### 1. Basic Usage

```python
from brain_client import BrainClient

# Create a client
client = BrainClient()

# Ask a question
result = client.answer_question(
    question="What are the benefits of microservices?",
    context="Software architecture discussion"
)

if result.success:
    print(f"Answer: {result['answer']}")
else:
    print(f"Error: {result.error}")
```

### 2. OODA Loop

```python
# Observe
obs = client.observe(
    working_memory="Current project state",
    new_messages="User feedback received",
    environment_state="Development environment ready"
)

# Orient
orient = client.orient(
    observations=obs['observations'],
    current_task="Implementing new feature"
)

# Decide
decision = client.decide(
    understanding=orient['understanding'],
    available_actions=["Implement immediately", "Research first", "Ask for clarification"],
    goals="Deliver high-quality feature"
)

# Act
plan = client.act(
    decision=decision['decision'],
    approach=decision['approach']
)
```

### 3. Custom Thinking

```python
# Create a completely custom signature
result = client.think(
    task="Analyze this code for security vulnerabilities",
    inputs={
        "code": "The source code to analyze",
        "language": "Programming language",
        "security_focus": "Specific security concerns"
    },
    outputs={
        "vulnerabilities": "List of potential security issues",
        "severity": "Risk assessment for each issue",
        "recommendations": "Specific remediation steps"
    },
    input_values={
        "code": "def login(username, password): ...",
        "language": "Python",
        "security_focus": "Authentication, input validation, SQL injection"
    }
)
```

## Installation and Setup

### Server Side

1. **Install Dependencies**:
   ```bash
   pip install dspy-ai
   ```

2. **Start the Server**:
   ```python
   from dspy_signature_server import DSPySignatureServer, BrainFileProcessor
   
   # Configure DSPy
   import dspy
   dspy.settings.configure(lm=dspy.OpenAI(model="gpt-3.5-turbo"))
   
   # Create and start server
   server = DSPySignatureServer()
   processor = BrainFileProcessor(server)
   processor.watch_and_process()  # Starts watching for requests
   ```

### Client Side (Sandbox)

1. **Copy Protocol Files**:
   - `generic_brain_protocol.py`
   - `brain_client.py`

2. **Use the Client**:
   ```python
   from brain_client import BrainClient, SimpleBrain
   
   # Simple interface
   brain = SimpleBrain()
   answer = brain.ask("What is machine learning?")
   
   # Full interface
   client = BrainClient()
   result = client.solve_problem("How to optimize database queries?")
   ```

## API Reference

### BrainClient

The main client interface for making thinking requests.

#### Methods

##### `think(task, inputs, outputs, input_values, description=None, context=None)`
Create a custom thinking request.

**Parameters:**
- `task` (str): The thinking task or question
- `inputs` (Dict[str, str]): Input field names and descriptions
- `outputs` (Dict[str, str]): Output field names and descriptions
- `input_values` (Dict[str, Any]): Actual values for the inputs
- `description` (str, optional): Detailed description of the task
- `context` (Dict[str, Any], optional): Additional context

**Returns:** `ThinkingResult`

##### OODA Loop Methods

- `observe(working_memory, new_messages="", environment_state="")` → `ThinkingResult`
- `orient(observations, current_task="", recent_history="")` → `ThinkingResult`
- `decide(understanding, available_actions, goals="", constraints="")` → `ThinkingResult`
- `act(decision, approach, available_tools="", current_state="")` → `ThinkingResult`

##### Specialized Methods

- `solve_problem(problem, context="", available_resources="", problem_type="general")` → `ThinkingResult`
- `answer_question(question, context="", knowledge_base="", domain="general")` → `ThinkingResult`

### SimpleBrain

Simplified interface for basic operations.

#### Methods

- `ask(question, context="")` → `str`: Ask a question and get a text answer
- `solve(problem, context="")` → `str`: Solve a problem and get the solution
- `decide(situation, options, goals="")` → `str`: Make a decision given options

### ThinkingResult

Result object returned by thinking operations.

#### Properties

- `outputs` (Dict[str, Any]): The output values from the thinking operation
- `success` (bool): Whether the operation succeeded
- `error` (str, optional): Error message if operation failed
- `request_id` (str): Unique identifier for the request
- `metadata` (Dict[str, Any], optional): Additional metadata

#### Methods

- `get(key, default=None)`: Get an output value with default
- `[key]`: Dictionary-style access to outputs

## Protocol Specification

### Request Format

```json
{
  "type": "generic_thinking_request",
  "request_id": "req_20240102_143022_123456",
  "signature": {
    "task": "The main thinking task or question",
    "description": "Detailed description of what this signature does",
    "inputs": {
      "input_name": "Description of this input",
      "another_input": "Description of another input"
    },
    "outputs": {
      "output_name": "Description of this output",
      "another_output": "Description of another output"
    }
  },
  "input_values": {
    "input_name": "Actual value for the input",
    "another_input": "Another actual value"
  },
  "context": {
    "priority": "high",
    "domain": "software_engineering"
  },
  "timestamp": "2024-01-02T14:30:22.123456"
}
<<<END_THOUGHT>>>
```

### Response Format

```json
{
  "type": "generic_thinking_response",
  "request_id": "req_20240102_143022_123456",
  "signature_hash": "a1b2c3d4e5f6...",
  "output_values": {
    "output_name": "The generated output value",
    "another_output": "Another generated output value"
  },
  "metadata": {
    "cached": true,
    "execution_time": 1641132622.123,
    "signature_task": "The main thinking task or question"
  },
  "timestamp": "2024-01-02T14:30:23.456789"
}
<<<THOUGHT_COMPLETE>>>
```

## Migration Guide

### From Fixed Types to Dynamic Signatures

#### Old Approach (Fixed Types)
```python
# Server side - required predefined CognitiveSignatures
request = ThinkingRequest(
    signature=CognitiveSignatures.OBSERVE,
    input_values={
        "working_memory": "current state",
        "new_messages": "new info"
    }
)
```

#### New Approach (Dynamic)
```python
# Client side - no server changes needed
result = client.observe(
    working_memory="current state",
    new_messages="new info"
)

# Or completely custom
result = client.think(
    task="Custom observation task",
    inputs={
        "context": "Current context to observe",
        "focus": "What to focus on"
    },
    outputs={
        "insights": "Key insights discovered",
        "next_steps": "Recommended next steps"
    },
    input_values={
        "context": "current state",
        "focus": "new information"
    }
)
```

### Migration Steps

1. **Phase 1**: Deploy the new server alongside the old one
2. **Phase 2**: Update clients to use the new protocol for new features
3. **Phase 3**: Gradually migrate existing functionality
4. **Phase 4**: Deprecate the old protocol

## Performance and Caching

### Signature Caching

The system automatically caches compiled DSPy signatures based on their specification hash:

- **Cache Key**: SHA-256 hash of the signature specification (task + inputs + outputs)
- **Cache Size**: Configurable (default: 100 signatures)
- **TTL**: Configurable (default: 1 hour)
- **Eviction**: Least Recently Used (LRU)

### Cache Statistics

```python
server = DSPySignatureServer()
stats = server.get_cache_stats()

print(f"Cached signatures: {stats['size']}")
for sig in stats['signatures']:
    print(f"  {sig['task']}: {sig['use_count']} uses")
```

### Performance Tips

1. **Reuse Signatures**: Identical signature specifications will use cached versions
2. **Batch Requests**: Process multiple requests with the same signature efficiently
3. **Monitor Cache**: Use cache statistics to optimize signature design
4. **Tune Cache Size**: Adjust based on your signature variety and memory constraints

## Error Handling

### Common Errors

1. **Invalid Signature**: Missing required fields or invalid field names
2. **Missing Inputs**: Required input values not provided
3. **Timeout**: Server response timeout (default: 30 seconds)
4. **Server Error**: DSPy execution failure

### Error Response Format

```python
result = client.think(...)
if not result.success:
    print(f"Error: {result.error}")
    # Handle error appropriately
```

## Advanced Usage

### Custom Signature Builders

```python
from generic_brain_protocol import SignatureBuilder

# Create reusable signature patterns
def create_code_review_signature(language="Python"):
    return SignatureBuilder.custom(
        task=f"Review {language} code for quality and best practices",
        inputs={
            "code": f"The {language} code to review",
            "standards": "Coding standards to apply",
            "focus_areas": "Specific areas to focus on"
        },
        outputs={
            "issues": "List of issues found",
            "suggestions": "Improvement suggestions",
            "rating": "Overall quality rating (1-10)"
        }
    )

# Use the custom builder
signature = create_code_review_signature("JavaScript")
result = client.think(
    signature.task,
    signature.inputs,
    signature.outputs,
    {
        "code": "function add(a, b) { return a + b; }",
        "standards": "ES6+, functional programming",
        "focus_areas": "Performance, readability, error handling"
    }
)
```

### File-based Communication Setup

```python
# Custom communication directories
client = BrainClient(
    communication_dir="/custom/brain/comm",
    timeout=60.0,  # 1 minute timeout
    poll_interval=0.1  # Check every 100ms
)

# Server processor with custom directories
processor = BrainFileProcessor(
    server,
    input_dir="/custom/brain/comm/input",
    output_dir="/custom/brain/comm/output"
)
```

## Troubleshooting

### Common Issues

1. **No Response**: Check that the server is running and communication directories exist
2. **Timeout Errors**: Increase timeout or check server performance
3. **Invalid Signatures**: Validate field names are valid Python identifiers
4. **Cache Issues**: Monitor cache statistics and adjust size if needed

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Enable detailed logging
client = BrainClient()
result = client.think(...)  # Will show detailed logs
```

## Examples

See the following files for complete examples:

- `usage_example.py`: Basic usage patterns
- `test_examples.py`: Comprehensive test suite
- `brain_client.py`: Client implementation with examples

## Contributing

1. Follow the existing code style and patterns
2. Add tests for new functionality
3. Update documentation for API changes
4. Ensure backward compatibility when possible

## License

This project is provided as-is for educational and development purposes.

