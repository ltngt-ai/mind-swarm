# Cognitive Loop DSPy Access Fix

## Issue
The cognitive_loop_v2.py had incorrect attribute access patterns where it was trying to access `.output_values` and `.metadata` on dict objects that were already the extracted output values.

## Root Cause
The methods `_observe()`, `_orient()`, and `_decide()` all return `response.output_values` (a dict), not the full ThinkingResponse object. However, the shutdown checks were trying to access these dicts as if they were ThinkingResponse objects.

## Fix Applied
Changed the shutdown checks from:
```python
if observations.output_values.get("aborted") or observations.metadata.get("shutdown"):
```

To:
```python
if observations.get("aborted") or observations.get("shutdown"):
```

This fix was applied to:
1. `/home/deano/projects/mind-swarm/subspace/runtime/base_code_template/cognitive_loop_v2.py`
2. `/home/deano/projects/mind-swarm/subspace/agents/Alice/base_code/cognitive_loop_v2.py`

The fix ensures the code correctly accesses dict values instead of trying to access non-existent attributes.

## Result
This should resolve the AttributeError: 'dict' object has no attribute 'output_values' that was causing Alice to crash.