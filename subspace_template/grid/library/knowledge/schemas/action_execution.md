# Action Execution Model

## How Actions Work

Actions execute **sequentially**, one after another. Each action's result becomes an observation in your memory that subsequent actions can reference.

## Referencing Previous Results

When you execute multiple actions in sequence, you can reference the result of the previous action using the `@last` notation:

- `@last` - The complete result from the previous action
- `@last.output` - Access a specific field from the result
- `@last.variables.result` - Navigate nested structures

## Examples

### Simple Calculation and Response
```json
[
  {
    "action": "execute_python",
    "params": {
      "code": "result = 2 ** 16\nprint(f'The answer is {result}')"
    }
  },
  {
    "action": "send_message",
    "params": {
      "to": "user",
      "content": "The calculation shows: @last.output"
    }
  }
]
```

### Using Variable Results
```json
[
  {
    "action": "execute_python",
    "params": {
      "code": "x = 42\ny = x * 2"
    }
  },
  {
    "action": "send_message",
    "params": {
      "to": "user",
      "content": "I calculated x=@last.variables.x and y=@last.variables.y"
    }
  }
]
```

### Sequential Processing
```json
[
  {
    "action": "search_memory",
    "params": {
      "query": "cybers in grid"
    }
  },
  {
    "action": "execute_python",
    "params": {
      "code": "# Process the search results\nresults = @last\ncount = len(results) if isinstance(results, list) else 0\nprint(f'Found {count} cybers')"
    }
  },
  {
    "action": "send_message",
    "params": {
      "to": "user",
      "content": "@last.output"
    }
  }
]
```

## Important Notes

1. **Sequential Execution**: Actions run one at a time, in order
2. **Results as Observations**: Each action result becomes an observation in memory
3. **Only Previous Result**: Currently only `@last` is supported (not @last-2, etc.)
4. **Type Safety**: If a path doesn't exist, it will show as `<undefined:path>`

## Action Result Structure

Most actions return results as dictionaries with fields you can access:

- `execute_python`: Returns `{output: "...", variables: {...}, execution_time: "..."}`
- `search_memory`: Returns a list of memory blocks or `{results: [...], count: N}`
- `send_message`: Returns `{message_id: "...", to: "..."}`

Use the dot notation to access nested fields: `@last.variables.my_var` or `@last.output`.