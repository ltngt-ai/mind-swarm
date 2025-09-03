"""
Metadata normalization and content hash utilities for ChromaDB integration.

This module provides shared helpers to prepare metadata for ChromaDB storage
and detect content changes via deterministic hashing.
"""

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


def normalize_metadata_value(value: Any) -> Union[str, int, float, bool]:
    """Normalize a single metadata value for ChromaDB.

    ChromaDB metadata values must be strings, numbers, or booleans.
    This function converts complex types appropriately:
    - Lists -> comma-separated strings
    - Dicts/complex objects -> JSON strings
    - None -> empty string

    Args:
        value: The value to normalize

    Returns:
        A normalized value suitable for ChromaDB metadata
    """
    if value is None:
        return ""

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, list):
        # Convert lists to comma-separated strings
        if not value:
            return ""
        # Ensure all items are strings
        str_items = [str(item) for item in value]
        return ",".join(str_items)

    if isinstance(value, dict):
        # Convert dicts to JSON strings
        try:
            return json.dumps(value, sort_keys=True, separators=(',', ':'))
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to JSON-serialize dict: {e}, converting to string")
            return str(value)

    # For any other type, convert to string
    return str(value)


def normalize_metadata(metadata: Dict[str, Any]) -> Dict[str, Union[str, int, float, bool]]:
    """Normalize all metadata values for ChromaDB storage.

    Processes a dictionary of metadata, converting all values to ChromaDB-compatible types.

    Args:
        metadata: Dictionary of metadata to normalize

    Returns:
        Dictionary with all values normalized for ChromaDB
    """
    if not metadata:
        return {}

    normalized = {}
    for key, value in metadata.items():
        # Skip None keys
        if key is None:
            continue

        # Ensure key is a string
        str_key = str(key)

        # Normalize the value
        normalized[str_key] = normalize_metadata_value(value)

    return normalized


def denormalize_list_value(value: str, separator: str = ",") -> List[str]:
    """Convert a comma-separated string back to a list.

    Args:
        value: The string value to denormalize
        separator: The separator used (default: comma)

    Returns:
        List of strings, or empty list if value is empty
    """
    if not value or not isinstance(value, str):
        return []

    # Split and strip whitespace from each item
    items = [item.strip() for item in value.split(separator)]
    # Filter out empty strings
    return [item for item in items if item]


def compute_content_hash(content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """Compute a deterministic hash for content and optional metadata.

    Creates a SHA256 hash of the normalized content and metadata, suitable for
    detecting changes or deduplication.

    Args:
        content: The main content to hash
        metadata: Optional metadata to include in the hash

    Returns:
        Hexadecimal SHA256 hash string
    """
    hasher = hashlib.sha256()

    # Hash the content
    hasher.update(content.encode('utf-8'))

    # If metadata is provided, normalize and hash it
    if metadata:
        # Normalize metadata first to ensure consistency
        normalized = normalize_metadata(metadata)

        # Sort keys for deterministic ordering
        sorted_meta = dict(sorted(normalized.items()))

        # Convert to JSON for consistent representation
        meta_json = json.dumps(sorted_meta, sort_keys=True, separators=(',', ':'))
        hasher.update(meta_json.encode('utf-8'))

    return hasher.hexdigest()


def compute_short_hash(content: str, length: int = 8) -> str:
    """Compute a short hash suitable for IDs.

    Args:
        content: The content to hash
        length: Number of characters to return (default: 8)

    Returns:
        Truncated hexadecimal hash string
    """
    full_hash = compute_content_hash(content)
    return full_hash[:length]


def metadata_has_changed(old_metadata: Dict[str, Any], new_metadata: Dict[str, Any]) -> bool:
    """Check if metadata has changed between two versions.

    Normalizes both metadata dictionaries before comparison to handle
    type differences that don't represent actual changes.

    Args:
        old_metadata: Previous metadata
        new_metadata: New metadata

    Returns:
        True if metadata has changed, False otherwise
    """
    # Normalize both for fair comparison
    old_normalized = normalize_metadata(old_metadata)
    new_normalized = normalize_metadata(new_metadata)

    # Compare normalized versions
    return old_normalized != new_normalized


def content_has_changed(
    old_content: str,
    new_content: str,
    old_metadata: Optional[Dict[str, Any]] = None,
    new_metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Check if content or metadata has changed.

    Uses content hashing for efficient comparison.

    Args:
        old_content: Previous content
        new_content: New content
        old_metadata: Previous metadata (optional)
        new_metadata: New metadata (optional)

    Returns:
        True if content or metadata has changed, False otherwise
    """
    old_hash = compute_content_hash(old_content, old_metadata)
    new_hash = compute_content_hash(new_content, new_metadata)

    return old_hash != new_hash


def prepare_for_chromadb(
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    compute_hash: bool = True
) -> Dict[str, Any]:
    """Prepare content and metadata for ChromaDB storage.

    This is a convenience function that normalizes metadata and optionally
    adds a content hash for change detection.

    Args:
        content: The content to store
        metadata: Optional metadata dictionary
        compute_hash: Whether to add a content_hash to metadata

    Returns:
        Dictionary with 'content' and 'metadata' keys ready for ChromaDB
    """
    # Start with normalized metadata
    normalized = normalize_metadata(metadata) if metadata else {}

    # Optionally add content hash for change detection
    if compute_hash:
        normalized['content_hash'] = compute_content_hash(content, metadata)

    return {
        'content': content,
        'metadata': normalized
    }


def extract_lists_from_metadata(metadata: Dict[str, Any], list_fields: List[str]) -> Dict[str, Any]:
    """Extract and denormalize list fields from metadata.

    Useful for converting ChromaDB metadata back to original form with proper lists.

    Args:
        metadata: Metadata dictionary from ChromaDB
        list_fields: List of field names that should be converted back to lists

    Returns:
        Metadata dictionary with specified fields converted to lists
    """
    result = dict(metadata)

    for field in list_fields:
        if field in result and isinstance(result[field], str):
            result[field] = denormalize_list_value(result[field])

    return result


# Specific metadata field handlers for common Mind-Swarm fields
def normalize_cyber_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize metadata specific to cyber knowledge entries.

    Handles common cyber metadata fields with appropriate conversions.

    Args:
        metadata: Raw cyber metadata

    Returns:
        Normalized metadata for ChromaDB
    """
    normalized = {}

    # Standard fields
    standard_fields = ['cyber_id', 'timestamp', 'source', 'category', 'title', 'description']
    for field in standard_fields:
        if field in metadata:
            normalized[field] = normalize_metadata_value(metadata[field])

    # Boolean fields
    boolean_fields = ['personal', 'active', 'archived']
    for field in boolean_fields:
        if field in metadata:
            value = metadata[field]
            # Ensure boolean type
            if isinstance(value, str):
                normalized[field] = value.lower() in ('true', '1', 'yes')
            else:
                normalized[field] = bool(value)

    # List fields (will be comma-separated)
    list_fields = ['tags', 'topics', 'capabilities', 'dependencies']
    for field in list_fields:
        if field in metadata:
            normalized[field] = normalize_metadata_value(metadata[field])

    # Numeric fields
    numeric_fields = ['priority', 'version', 'score']
    for field in numeric_fields:
        if field in metadata:
            value = metadata[field]
            try:
                if isinstance(value, int):
                    # Already an int, keep it
                    normalized[field] = value
                elif isinstance(value, float):
                    # If float is whole number, convert to int
                    if value.is_integer():
                        normalized[field] = int(value)
                    else:
                        normalized[field] = value
                else:
                    # Try parsing as float first
                    num_val = float(value)
                    # Convert to int if it's a whole number
                    if num_val.is_integer():
                        normalized[field] = int(num_val)
                    else:
                        normalized[field] = num_val
            except (ValueError, TypeError):
                # If parsing fails, store as string
                normalized[field] = normalize_metadata_value(value)

    # Handle any additional fields not covered above
    for key, value in metadata.items():
        if key not in normalized:
            normalized[key] = normalize_metadata_value(value)

    return normalized
