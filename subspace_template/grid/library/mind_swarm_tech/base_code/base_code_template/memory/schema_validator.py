"""Schema validation for memory formats.

This module provides validation for custom MIME types used in the memory system.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger("Cyber.memory.schema_validator")


class SchemaValidator:
    """Validates memory content against predefined schemas."""
    
    def __init__(self):
        """Initialize the schema validator."""
        self.schemas = {}
        self._load_schemas()
        
    def _load_schemas(self):
        """Load schemas from the schemas directory."""
        schema_dir = Path("/grid/library/schemas")
        
        if not schema_dir.exists():
            logger.warning(f"Schema directory not found: {schema_dir}")
            return
            
        # Map of mime types to schema files
        # Note: memory-blocks are internal structures, not user-created
        schema_mappings = {
            "application/knowledge": "knowledge_format.json",
            "application/message": "message_format.json"
        }
        
        for mime_type, schema_file in schema_mappings.items():
            schema_path = schema_dir / schema_file
            if schema_path.exists():
                try:
                    with open(schema_path, 'r') as f:
                        self.schemas[mime_type] = json.load(f)
                    logger.info(f"Loaded schema for {mime_type}")
                except Exception as e:
                    logger.error(f"Failed to load schema {schema_file}: {e}")
                    
    def validate(self, content: Dict[str, Any], mime_type: str) -> tuple[bool, List[str]]:
        """Validate content against a schema.
        
        Args:
            content: Content to validate
            mime_type: MIME type to validate against
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        # If we don't have jsonschema library, do basic validation
        try:
            import jsonschema
        except ImportError:
            return self._basic_validate(content, mime_type)
            
        if mime_type not in self.schemas:
            return True, []  # No schema to validate against
            
        schema = self.schemas[mime_type]
        errors = []
        
        try:
            jsonschema.validate(instance=content, schema=schema)
            return True, []
        except jsonschema.ValidationError as e:
            errors.append(str(e.message))
            # Collect all validation errors
            validator = jsonschema.Draft7Validator(schema)
            for error in validator.iter_errors(content):
                error_path = ".".join(str(p) for p in error.path)
                if error_path:
                    errors.append(f"{error_path}: {error.message}")
                else:
                    errors.append(error.message)
            return False, errors
        except Exception as e:
            errors.append(f"Unexpected validation error: {e}")
            return False, errors
            
    def _basic_validate(self, content: Dict[str, Any], mime_type: str) -> tuple[bool, List[str]]:
        """Basic validation without jsonschema library.
        
        Args:
            content: Content to validate
            mime_type: MIME type to validate against
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        if mime_type == "application/knowledge":
            # Validate knowledge format
            if not isinstance(content, dict):
                errors.append("Content must be a dictionary")
            elif "metadata" not in content:
                errors.append("Missing required field: metadata")
            elif "content" not in content:
                errors.append("Missing required field: content")
            else:
                metadata = content.get("metadata", {})
                if not isinstance(metadata, dict):
                    errors.append("Metadata must be a dictionary")
                elif "title" not in metadata:
                    errors.append("Metadata missing required field: title")
                elif "category" not in metadata:
                    errors.append("Metadata missing required field: category")
                    
                if not isinstance(content.get("content"), str):
                    errors.append("Content field must be a string")
                elif not content["content"].strip():
                    errors.append("Content field cannot be empty")
                    
        elif mime_type == "application/message":
            # Validate message format
            required_fields = ["type", "from", "to", "timestamp"]
            for field in required_fields:
                if field not in content:
                    errors.append(f"Missing required field: {field}")
                    
            if "type" in content:
                valid_types = ["COMMAND", "QUERY", "RESPONSE", "NOTIFICATION", "ERROR", "SHUTDOWN"]
                if content["type"] not in valid_types:
                    errors.append(f"Invalid message type: {content['type']}")
                    
                # Type-specific validation
                if content["type"] == "COMMAND" and "command" not in content:
                    errors.append("COMMAND type requires command field")
                elif content["type"] == "RESPONSE" and "in_reply_to" not in content:
                    errors.append("RESPONSE type requires in_reply_to field")
                elif content["type"] == "ERROR" and "error" not in content:
                    errors.append("ERROR type requires error field")
                    
        return len(errors) == 0, errors
        
    def validate_before_write(self, content: Any, mime_type: str) -> bool:
        """Validate content before writing to memory.
        
        Args:
            content: Content to validate
            mime_type: MIME type to validate against
            
        Returns:
            True if valid, raises ValueError if not
        """
        # Only validate user-created structured formats
        # Memory blocks are internal and don't need validation
        if mime_type not in ["application/knowledge", "application/message"]:
            return True
            
        # Parse content if it's a string
        if isinstance(content, str):
            try:
                import yaml
                content = yaml.safe_load(content)
            except:
                try:
                    content = json.loads(content)
                except:
                    # Not structured data, allow it
                    return True
                    
        is_valid, errors = self.validate(content, mime_type)
        
        if not is_valid:
            error_msg = f"Validation failed for {mime_type}:\n" + "\n".join(f"  - {e}" for e in errors)
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        return True