#!/usr/bin/env python3
"""Test script to verify CBR metadata sanitization fix."""

import json
from typing import Any

def _sanitize_metadata_value(value: Any) -> Any:
    """Sanitize a metadata value for ChromaDB storage.
    
    ChromaDB only accepts str, int, float, bool, or None.
    Nested dicts and lists are serialized to JSON strings.
    """
    # Handle None and primitives
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    
    # Handle lists - convert to comma-separated string or JSON
    if isinstance(value, list):
        # Try to join simple lists as comma-separated
        if all(isinstance(item, (str, int, float, bool)) for item in value):
            return ','.join(str(item) for item in value)
        else:
            # Complex list - serialize as JSON
            try:
                return json.dumps(value)
            except:
                return str(value)
    
    # Handle dicts - serialize as JSON
    if isinstance(value, dict):
        try:
            return json.dumps(value)
        except:
            return str(value)
    
    # Handle any other type - convert to string
    try:
        return str(value)
    except:
        return None

# Test cases that would cause the error
test_cases = [
    # The problematic case from the error log
    {
        "type": "TypeError",
        "message": "Execution error: TypeError: expected string or bytes-like object, got 'TrackedDict' at line 12",
        "line": 12
    },
    # Simple values that should pass through
    "simple_string",
    123,
    45.67,
    True,
    None,
    # Lists
    ["tag1", "tag2", "tag3"],
    [1, 2, 3],
    [{"nested": "dict"}, {"in": "list"}],
    # Complex nested structure
    {
        "error_details": {
            "type": "TypeError",
            "message": "Some error",
            "line": 42,
            "nested": {
                "deep": "value"
            }
        }
    }
]

print("Testing CBR metadata sanitization:")
print("=" * 50)

for i, test_value in enumerate(test_cases, 1):
    print(f"\nTest {i}: {type(test_value).__name__}")
    print(f"Input: {test_value}")
    
    result = _sanitize_metadata_value(test_value)
    result_type = type(result).__name__ if result is not None else "None"
    
    print(f"Output type: {result_type}")
    print(f"Output: {result}")
    
    # Verify ChromaDB compatibility
    is_compatible = result is None or isinstance(result, (str, int, float, bool))
    print(f"ChromaDB compatible: {is_compatible}")
    
    if not is_compatible:
        print("  ⚠️ WARNING: Not compatible with ChromaDB!")
    else:
        print("  ✅ Compatible with ChromaDB")

print("\n" + "=" * 50)
print("Test complete!")