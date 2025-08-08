# Compute Actions Usage Examples

This document demonstrates how cybers can use the new compute actions for general-purpose Python computation.

## execute_python Action

The `execute_python` action allows cybers to run Python code in a sandboxed environment with access to safe built-ins and common modules.

### Basic Examples

#### 1. Simple Arithmetic
```json
{
  "action": "execute_python",
  "params": {
    "code": "result = 2 + 2\nprint(f'The answer is {result}')",
    "description": "Basic arithmetic"
  }
}
```

Expected output:
```json
{
  "success": true,
  "output": "The answer is 4",
  "variables": {"result": 4},
  "execution_time": "0.001 seconds"
}
```

#### 2. Using Math Module
```json
{
  "action": "execute_python",
  "params": {
    "code": "import math\narea = math.pi * 5**2\nprint(f'Area of circle with radius 5: {area:.2f}')",
    "description": "Calculate circle area"
  }
}
```

#### 3. Data Processing
```json
{
  "action": "execute_python",
  "params": {
    "code": "data = [1, 2, 3, 4, 5]\navg = sum(data) / len(data)\nprint(f'Average: {avg}')\nprint(f'Squared values: {[x**2 for x in data]}')",
    "description": "Process list data"
  }
}
```

#### 4. String Manipulation
```json
{
  "action": "execute_python",
  "params": {
    "code": "text = 'hello world'\nwords = text.split()\ncapitalized = ' '.join(word.capitalize() for word in words)\nprint(f'Original: {text}')\nprint(f'Capitalized: {capitalized}')",
    "description": "String processing"
  }
}
```

#### 5. Using Statistics Module
```json
{
  "action": "execute_python",
  "params": {
    "code": "import statistics\ndata = [10, 20, 30, 40, 50, 25, 35]\nmean = statistics.mean(data)\nmedian = statistics.median(data)\nstdev = statistics.stdev(data)\nprint(f'Mean: {mean}')\nprint(f'Median: {median}')\nprint(f'Std Dev: {stdev:.2f}')",
    "description": "Statistical analysis"
  }
}
```

#### 6. JSON Processing
```json
{
  "action": "execute_python",
  "params": {
    "code": "import json\ndata = {'name': 'cyber', 'tasks': ['think', 'compute', 'respond']}\njson_str = json.dumps(data, indent=2)\nprint('JSON representation:')\nprint(json_str)",
    "description": "JSON manipulation"
  }
}
```

#### 7. Date/Time Operations
```json
{
  "action": "execute_python",
  "params": {
    "code": "from datetime import datetime, timedelta\nnow = datetime.now()\nfuture = now + timedelta(days=7)\nprint(f'Today: {now.strftime(\"%Y-%m-%d\")}')\nprint(f'Next week: {future.strftime(\"%Y-%m-%d\")}')",
    "description": "Date calculations"
  }
}
```

#### 8. Complex Computation with Variable Persistence
```json
{
  "action": "execute_python",
  "params": {
    "code": "# Fibonacci sequence\ndef fibonacci(n):\n    if n <= 1:\n        return n\n    a, b = 0, 1\n    for _ in range(2, n+1):\n        a, b = b, a + b\n    return b\n\n# Calculate first 10 Fibonacci numbers\nfib_sequence = [fibonacci(i) for i in range(10)]\nprint(f'First 10 Fibonacci numbers: {fib_sequence}')\n\n# Store for later use\nfib_dict = {i: fibonacci(i) for i in range(10)}",
    "description": "Fibonacci calculation",
    "persist_variables": true
  }
}
```

### Available Safe Modules

The following modules are available in the sandboxed environment:
- `math` - Mathematical functions
- `statistics` - Statistical functions
- `json` - JSON encoder/decoder
- `re` - Regular expressions
- `datetime` - Date and time handling
- `itertools` - Iterator functions
- `functools` - Functional programming tools
- `collections` - Specialized container datatypes

### Safe Built-ins

The following built-in functions are available:
- Math: `abs`, `round`, `min`, `max`, `sum`, `pow`, `divmod`
- Type conversion: `int`, `float`, `str`, `bool`, `complex`
- Collections: `list`, `tuple`, `dict`, `set`, `frozenset`
- Iteration: `range`, `enumerate`, `zip`, `map`, `filter`, `sorted`, `reversed`
- Logic: `all`, `any`
- String: `ord`, `chr`, `bin`, `hex`, `oct`
- Other: `len`, `type`, `isinstance`, `print`

### Limitations

1. **No file system access** - Cannot read/write files
2. **No network access** - Cannot make HTTP requests
3. **No system operations** - Cannot execute system commands
4. **No imports beyond safe modules** - Limited to pre-approved modules
5. **No infinite loops** - Code should complete quickly
6. **Memory limits** - Large data structures may be truncated in results

### Error Handling

The action provides detailed error information:

```json
{
  "action": "execute_python",
  "params": {
    "code": "print(undefined_variable)",
    "description": "Error example"
  }
}
```

Returns:
```json
{
  "success": false,
  "error": "Error executing Python code: NameError: name 'undefined_variable' is not defined",
  "result": {
    "exception_type": "NameError",
    "exception_message": "name 'undefined_variable' is not defined",
    "traceback": "..."
  }
}
```

## simplify_expression Action

For quick mathematical expression evaluation without full Python overhead:

```json
{
  "action": "simplify_expression",
  "params": {
    "expression": "2 + 2 * 3 - 1"
  }
}
```

Returns:
```json
{
  "success": true,
  "result": {
    "expression": "2 + 2 * 3 - 1",
    "result": 7,
    "type": "int"
  }
}
```

This action only supports basic arithmetic operations and is faster for simple calculations.

## Integration in cyber Decision Making

cybers can now use these compute actions in their decision-making process:

```python
# In the decide() method, cyber might choose:
actions = [
    {
        "action": "execute_python",
        "params": {
            "code": "result = 15 * 23\nprint(f'15 times 23 equals {result}')",
            "description": "Calculate product"
        }
    },
    {
        "action": "send_message",
        "params": {
            "to": "user",
            "content": "The calculation is complete. 15 × 23 = 345"
        }
    },
    {
        "action": "finish",
        "params": {}
    }
]
```

This enables cybers to perform complex computations as part of their cognitive processes.