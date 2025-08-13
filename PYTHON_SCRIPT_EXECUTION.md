# Python Script-Based Execution Model

## Overview

Mind-Swarm Cybers now use a Python script-based execution model where:

1. **Decision Stage** produces plain language intentions (what to do)
2. **Execution Stage** generates and runs Python scripts (how to do it)

This provides unlimited computational flexibility and eliminates action parameter errors.

## How It Works

### Decision Stage
```
Input: Observation/Understanding
Output: Plain text intention

Example: "Calculate the factorial of 10 and send the result to Alice"
```

### Execution Stage
```
Input: Plain text intention
Process: Generate Python script with action modules
Output: Execution results

Generated script:
import math
result = math.factorial(10)
message = f"The factorial of 10 is {result}"
send_message.send(to="Alice", content=message)
```

## Available Action Modules

### Core Modules (All Cybers)

**send_message** - Send messages to other cybers
```python
send_message.send(to="cyber_name", content="message", message_type="MESSAGE")
```

**memory** - Memory operations
```python
memory.add(content="text", memory_type="note", priority="medium")
memory.search(query="search terms", limit=10)
memory.get_working_memory()
```

**read_file** - Read files
```python
read_file.read(path="/personal/file.txt")
```

**write_file** - Write files
```python
write_file.write(path="/personal/file.txt", content="text", append=False)
```

**think** - Deep reasoning (async)
```python
await think.deeply(topic="subject", approach="analytical")
```

### I/O Cyber Modules

**network** - Network operations
```python
network.request(url="https://...", method="GET", data=None)
```

**user_io** - User interaction
```python
user_io.display("message to user")
```

## Python Capabilities

All standard Python operations are available:
- Math: `import math`
- JSON: `import json`
- DateTime: `from datetime import datetime`
- Collections: `from collections import Counter`
- Statistics: `import statistics`
- Regular expressions: `import re`
- And more...

## Examples

### Simple Calculation
```python
# Intention: "Calculate the sum of squares from 1 to 10"

# Generated script:
result = sum(i**2 for i in range(1, 11))
print(f"Sum of squares: {result}")
```

### Data Processing
```python
# Intention: "Analyze message frequency and save insights"

# Generated script:
messages = memory.search("from", limit=20)
from collections import Counter

senders = []
for msg in messages:
    if "from" in msg.get("content", ""):
        sender = msg["content"].split("from")[1].split()[0]
        senders.append(sender)

frequency = Counter(senders)
insight = f"Message frequency: {dict(frequency)}"
memory.add(content=insight, memory_type="insight", priority="high")
```

### Complex Task
```python
# Intention: "Read tasks, complete calculations, report results"

# Generated script:
task_file = read_file.read("/personal/tasks.json")
if task_file["success"]:
    import json
    tasks = json.loads(task_file["content"])
    
    results = []
    for task in tasks:
        if task["type"] == "calculate":
            try:
                result = eval(task["expression"], {"__builtins__": {}})
                results.append(f"{task['name']}: {result}")
            except Exception as e:
                results.append(f"{task['name']}: Error - {e}")
    
    output = "\n".join(results)
    write_file.write("/personal/results.txt", output)
    send_message.send(to="coordinator", content=f"Completed {len(results)} tasks")
```

## Benefits

- **No parameter errors** - AI generates correct code
- **Unlimited capabilities** - Full Python environment
- **Natural expression** - Plain language intentions
- **Better debugging** - Scripts are logged
- **More reliable** - Leverages LLM code generation strengths

## Architecture

```
subspace_template/grid/library/base_code/base_code_template/
├── stages/
│   ├── observation_stage.py      # Gathers information
│   ├── decision_stage_v2.py      # Generates intentions
│   ├── execution_stage_v2.py     # Generates and runs scripts
│   └── reflect_stage.py          # Learns from results
├── cognitive_loop.py              # Main loop using V2 stages
└── mind.py                        # Cyber mind coordinator
```

The system is now fully integrated - no environment variables or configuration needed.