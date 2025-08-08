# OODIA Loop Test Example

This document shows how the new Instruct phase fixes parameter mistakes automatically.

## The Problem (Before OODIA)

cyber decides to use search_memory but uses wrong parameter name:
```
Action: search_memory
Params: {"content": "cybers in the grid"}  # Wrong! Should be "query"
Result: ERROR - No search query provided
```

## The Solution (With OODIA)

The cognitive loop now follows: Observe → Orient → Decide → **Instruct** → Act

### What Happens in the Instruct Phase

1. **Load Action Knowledge**
   - Loads `/grid/library/actions/search_memory.json`
   - Adds knowledge to working memory
   - cyber now "remembers" how to use the action

2. **Parameter Validation**
   - Checks parameter schema
   - Finds "content" is not a valid parameter
   - Discovers "content" is an alias for "query"

3. **Automatic Correction**
   - Renames "content" → "query"
   - Logs: `Corrected parameter: 'content' -> 'query' for action search_memory`

4. **Execution**
   - Action now has correct parameters
   - Executes successfully

## Example Flow

```
DECIDE Phase:
- cyber: "I'll search for cybers"
- Action: search_memory
- Params: {"content": "cybers in the grid"}

INSTRUCT Phase:
- Load: /grid/library/actions/search_memory.json
- Detect: "content" is alias for "query"
- Correct: {"query": "cybers in the grid"}

ACT Phase:
- Execute: search_memory with corrected params
- Success: Found 3 cybers in grid
```

## Benefits

1. **Self-Correcting**: cybers fix their own mistakes
2. **Learning**: Action knowledge is loaded when needed
3. **Natural**: Like remembering how to use a tool when you pick it up
4. **Extensible**: Easy to add new corrections and patterns

## Additional Features

- **Missing Parameters**: Brain can fill in missing required params
- **Default Values**: Applies defaults for optional params
- **Multiple Corrections**: Can fix multiple issues in one pass
- **Preserves Intent**: Maintains what the cyber wanted to do

This makes cybers more robust and reduces failures from simple parameter mistakes!