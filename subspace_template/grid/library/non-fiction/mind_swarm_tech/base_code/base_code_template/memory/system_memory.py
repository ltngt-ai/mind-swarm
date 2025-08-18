"""System memory utilities for creating simple JSON data bag memories.

System memories are JSON files with ContentType.APPLICATION_JSON that don't
require formal structure - they're just bags of JSON data.
"""

from pathlib import Path
from typing import Dict, Any, Optional
import json
import logging

from .memory_blocks import FileMemoryBlock
from .memory_types import ContentType, Priority

logger = logging.getLogger("Cyber.memory.system")


def create_system_memory(location: str, 
                        data: Dict[str, Any],
                        pinned: bool = True,
                        cycle_count: Optional[int] = None) -> FileMemoryBlock:
    """Create a system memory block for a JSON data bag.
    
    System memories are simple JSON files without formal structure.
    They use ContentType.APPLICATION_JSON and Priority.SYSTEM by default.
    
    Args:
        location: Path to the JSON file (relative to cyber's view)
        data: Dictionary to store as JSON
        pinned: Whether to pin in memory (default True for system files)
        cycle_count: Optional cycle count when created
        
    Returns:
        FileMemoryBlock configured as a system memory
        
    Example:
        # Create identity memory
        identity_data = {
            "name": "Alice", 
            "cyber_type": "general",
            "capabilities": []
        }
        identity_memory = create_system_memory(
            "personal/.internal/identity.json",
            identity_data
        )
    """
    return FileMemoryBlock(
        location=location,
        content_type=ContentType.APPLICATION_JSON,
        priority=Priority.SYSTEM,
        confidence=1.0,
        pinned=pinned,
        cycle_count=cycle_count or 0,
        no_cache=True,  # System files often change, don't cache
        metadata={
            "is_system": True,
            "data_format": "json_bag"
        }
    )


def load_system_json(file_path: Path) -> Optional[Dict[str, Any]]:
    """Load a system JSON file as a data bag.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Dictionary of JSON data or None if error
    """
    try:
        if file_path.exists():
            with open(file_path, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load system JSON from {file_path}: {e}")
    return None


def save_system_json(file_path: Path, data: Dict[str, Any]) -> bool:
    """Save a system JSON data bag.
    
    Args:
        file_path: Path to save JSON file
        data: Dictionary to save as JSON
        
    Returns:
        True if saved successfully
    """
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save system JSON to {file_path}: {e}")
        return False