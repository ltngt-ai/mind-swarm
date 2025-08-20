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
communication.send_message(to="Alice", subject="Factorial Calculation", content=message)
```