"""Reference resolver for @last syntax in action parameters.

This module handles resolving @last references in action parameters,
allowing actions to reference results from previous actions.
"""

import re
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("Cyber.utils.reference_resolver")


class ReferenceResolver:
    """Resolves @last references in action parameters."""
    
    @staticmethod
    def resolve_references(params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve @last references in parameters.
        
        Args:
            params: Action parameters potentially containing @last references
            context: Execution context with last_action_result
            
        Returns:
            Parameters with references resolved
        """
        if not context.get("last_action_result"):
            # No previous result, return params unchanged
            return params
            
        last_result = context["last_action_result"]
        resolved = {}
        
        for key, value in params.items():
            resolved[key] = ReferenceResolver._resolve_value(value, last_result)
            
        return resolved
    
    @staticmethod
    def _resolve_value(value: Any, last_result: Any) -> Any:
        """Recursively resolve references in a value.
        
        Args:
            value: Value to resolve (may contain @last references)
            last_result: The last action result to reference
            
        Returns:
            Value with references resolved
        """
        if isinstance(value, str):
            # Check for @last references
            if "@last" in value:
                return ReferenceResolver._resolve_string(value, last_result)
            return value
            
        elif isinstance(value, dict):
            # Recursively resolve dictionary values
            return {k: ReferenceResolver._resolve_value(v, last_result) 
                    for k, v in value.items()}
                    
        elif isinstance(value, list):
            # Recursively resolve list items
            return [ReferenceResolver._resolve_value(item, last_result) 
                    for item in value]
                    
        else:
            # Other types pass through unchanged
            return value
    
    @staticmethod
    def _resolve_string(text: str, last_result: Any) -> Any:
        """Resolve @last references in a string.
        
        Args:
            text: String potentially containing @last references
            last_result: The last action result
            
        Returns:
            String with references resolved, or the extracted value if entire string is a reference
        """
        # Pattern to match @last or @last.path.to.value
        pattern = r'@last(?:\.([a-zA-Z0-9_.\[\]]+))?'
        
        # Check if entire string is just a reference (for type preservation)
        full_match = re.fullmatch(pattern, text)
        if full_match:
            path = full_match.group(1)
            value = ReferenceResolver._extract_path(last_result, path)
            logger.debug(f"Resolved full reference '{text}' to: {value}")
            return value
        
        # Special handling for Python code context - preserve string literals
        if "print(" in text or "=" in text:
            # This looks like Python code, do smart replacement
            def replace_ref(match):
                path = match.group(1)
                value = ReferenceResolver._extract_path(last_result, path)
                # For Python code, properly quote strings
                if isinstance(value, str):
                    # Escape quotes and return as Python string literal
                    escaped = value.replace('\\', '\\\\').replace('"', '\\"')
                    return f'"{escaped}"'
                elif isinstance(value, (dict, list)):
                    return json.dumps(value)
                else:
                    return str(value)
        else:
            # Regular string replacement
            def replace_ref(match):
                path = match.group(1)
                value = ReferenceResolver._extract_path(last_result, path)
                # Convert to string for replacement
                if isinstance(value, (dict, list)):
                    return json.dumps(value)
                return str(value)
        
        resolved = re.sub(pattern, replace_ref, text)
        logger.debug(f"Resolved string '{text}' to: '{resolved}'")
        return resolved
    
    @staticmethod
    def _extract_path(obj: Any, path: Optional[str]) -> Any:
        """Extract value from object using dot/bracket notation path.
        
        Args:
            obj: Object to extract from
            path: Path like "result.content" or "results[0].memory_id"
            
        Returns:
            Extracted value or the original object if no path
        """
        if not path:
            return obj
            
        current = obj
        
        # Split path on dots and brackets
        parts = re.split(r'[.\[\]]', path)
        parts = [p for p in parts if p]  # Remove empty strings
        
        try:
            for part in parts:
                if part.isdigit():
                    # Array index
                    current = current[int(part)]
                else:
                    # Dictionary key or object attribute
                    if isinstance(current, dict):
                        current = current.get(part)
                    else:
                        # Try as attribute
                        current = getattr(current, part, None)
                        
                if current is None:
                    logger.warning(f"Path '{path}' not found in last result")
                    return f"@last.{path}"  # Return unresolved reference
                    
            return current
            
        except (KeyError, IndexError, AttributeError, TypeError) as e:
            logger.warning(f"Error resolving path '{path}': {e}")
            return f"@last.{path}"  # Return unresolved reference