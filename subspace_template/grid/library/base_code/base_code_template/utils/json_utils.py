"""JSON utility functions for the cognitive loop.

This module provides JSON encoding/decoding utilities that handle
special types like datetime objects and provide safe serialization.
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime objects."""
    
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def safe_json_encode(data: Any, indent: Optional[int] = None) -> str:
    """Safely encode data to JSON string.
    
    Args:
        data: Data to encode
        indent: Number of spaces for indentation (None for compact)
        
    Returns:
        JSON string representation
    """
    try:
        return json.dumps(data, cls=DateTimeEncoder, indent=indent)
    except Exception as e:
        # Fallback to string representation if encoding fails
        return json.dumps({"error": f"Failed to encode: {str(e)}", "data": str(data)})


def safe_json_decode(json_str: str) -> Any:
    """Safely decode JSON string to Python object.
    
    Args:
        json_str: JSON string to decode
        
    Returns:
        Decoded Python object or None if decoding fails
    """
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Try to clean common issues
        cleaned = json_str.strip()
        if cleaned.startswith("'") and cleaned.endswith("'"):
            # Replace single quotes with double quotes
            cleaned = cleaned[1:-1].replace("'", '"')
            try:
                return json.loads(cleaned)
            except:
                pass
        return None
    except Exception:
        return None


def validate_json_structure(data: Dict, schema: Dict) -> bool:
    """Validate JSON structure against a simple schema.
    
    Args:
        data: Data to validate
        schema: Schema dict with required fields
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(data, dict):
        return False
        
    # Check required fields
    required_fields = schema.get("required", [])
    for field in required_fields:
        if field not in data:
            return False
            
    # Check field types if specified
    field_types = schema.get("types", {})
    for field, expected_type in field_types.items():
        if field in data and not isinstance(data[field], expected_type):
            return False
            
    return True