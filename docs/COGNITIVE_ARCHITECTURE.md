# Mind-Swarm Cognitive Architecture

## Overview

The Mind-Swarm cognitive architecture implements intelligence through structured thinking at every step, not through hardcoded logic. This creates emergent intelligence where cybers learn and adapt rather than following fixed patterns.

## Key Principles

1. **No Hardcoded Intelligence**: Logic emerges from LLM thinking, not if-statements
2. **Structured Thinking**: Every cognitive step uses DSPy-style signatures
3. **Sandbox Boundary**: cybers remain simple; intelligence lives server-side
4. **Time Abstraction**: cybers experience instant responses despite LLM latency

## Architecture Layers

### 1. cyber Side (Sandboxed)
- **Boot ROM**: Fundamental, immutable knowledge
- **Working Memory**: Current context and temporary storage
- **Cognitive Loop**: Orchestrates thinking operations
- **Brain Protocol**: Structures thinking requests

### 2. Brain Interface (Boundary)
- **Thinking Signatures**: Define inputs/outputs for each cognitive operation
- **Request/Response Protocol**: JSON-structured communication
- **Marker-based Sync**: `<<<END_THOUGHT>>>` and `<<<THOUGHT_COMPLETE>>>`

### 3. Server Side (Intelligence)
- **Brain Handler**: Processes thinking requests
- **DSPy Integration**: Converts signatures to LLM prompts
- **AI Services**: Actual LLM calls (OpenRouter, local, etc.)

## The OODA Loop with Intelligence

### Traditional (Hardcoded) Approach ❌
```
Observe: if inbox has messages then...
Orient: if message.type == "arithmetic" then...
Decide: if problem contains "+" then...
Act: calculate and return answer
```

### Mind-Swarm (Intelligent) Approach ✅
```
Observe: "What has changed?" → LLM analyzes environment
Orient: "What does this mean?" → LLM understands context
Decide: "What should I do?" → LLM chooses approach
Act: "How do I execute?" → LLM plans execution
```

## Thinking Signatures

Each cognitive operation has a structured signature:

```python
class ThinkingSignature:
    task: "The question to answer"
    inputs: {
        "input_name": "description of what this input contains"
    }
    outputs: {
        "output_name": "description of expected output"
    }
```

## Example: Processing "What is 2+2?"

### 1. cyber Observes
```json
{
  "signature": {
    "task": "What has changed or needs attention?",
    "inputs": {
      "new_messages": "1 new message: QUERY from user",
      "working_memory": "Empty",
      "environment_state": "Cycle 1, no current task"
    }
  }
}
```

**Server responds**: "New query needs attention: arithmetic question"

### 2. cyber Orients
```json
{
  "signature": {
    "task": "What does this mean?",
    "inputs": {
      "observations": "New query about arithmetic",
      "current_task": "None",
      "recent_history": "Just started"
    }
  }
}
```

**Server responds**: "This is an arithmetic problem requiring calculation"

### 3. cyber Decides
```json
{
  "signature": {
    "task": "What should I do?",
    "inputs": {
      "understanding": "Arithmetic problem to solve",
      "available_actions": "Think, Calculate, Respond",
      "goals": "Answer accurately"
    }
  }
}
```

**Server responds**: "Solve the arithmetic problem step by step"

### 4. cyber Acts
```json
{
  "signature": {
    "task": "Solve this arithmetic problem",
    "inputs": {
      "problem": "What is 2+2?",
      "context": "User query"
    }
  }
}
```

**Server responds**: "2+2 = 4"

## Benefits of This Architecture

1. **True Learning**: cybers can learn from experience, not just execute code
2. **Adaptability**: New situations handled intelligently, not through new code
3. **Upgradeable**: Improve intelligence server-side without touching cybers
4. **Emergent Behavior**: Complex behaviors emerge from simple thinking loops
5. **Debugging**: Can see exactly what cybers are thinking at each step

## Future Enhancements

1. **Memory Integration**: Long-term memory influences thinking
2. **Multi-cyber Reasoning**: cybers consult each other during thinking
3. **Custom Signatures**: cybers develop their own thinking patterns
4. **Learning from Outcomes**: Reflection improves future performance