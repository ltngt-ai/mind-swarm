"""Memory block definitions for the Cyber memory system.

Provides the core data structures for symbolic memory representation.
Each block represents a reference to content in the filesystem.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from .memory_types import Priority, ContentType
from .unified_memory_id import UnifiedMemoryID


class MemoryBlock:
    """Base class for all memory blocks - not a dataclass to avoid inheritance issues."""
    
    def __init__(self, 
                 confidence: float = 1.0,
                 priority: Priority = Priority.MEDIUM,
                 timestamp: Optional[datetime] = None,
                 expiry: Optional[datetime] = None,
                 metadata: Optional[Dict[str, Any]] = None,
                 pinned: bool = False,
                 cycle_count: Optional[int] = None,
                 content_type: Optional[ContentType] = None):
        """Initialize base memory block."""
        self.confidence = confidence
        self.priority = priority
        self.timestamp = timestamp or datetime.now()
        self.expiry = expiry
        self.metadata = metadata or {}
        self.pinned = pinned  # When True, memory is never removed by memory management
        self.cycle_count = cycle_count  # Track which cycle this memory was created in
        self.content_type = content_type or ContentType.UNKNOWN  # Content type of the memory
        
        # This must be set by subclasses
        self.id: str  # Now just a path, no type prefix


@dataclass
class FileMemoryBlock(MemoryBlock):
    """Reference to file content."""
    location: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    digest: Optional[str] = None
    confidence: float = 1.0
    priority: Priority = Priority.MEDIUM
    timestamp: Optional[datetime] = None
    expiry: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    pinned: bool = False
    cycle_count: Optional[int] = None
    content_type: Optional[ContentType] = None  # Explicit content type
    no_cache: bool = False  # If True, content should not be cached (e.g., memory-mapped files)
    

    def __post_init__(self):
        """Initialize base class and set type."""
        # Detect content type from file extension if not provided
        if self.content_type is None:
            self.content_type = ContentType.from_file_extension(self.location)
        
        super().__init__(
            confidence=self.confidence,
            priority=self.priority,
            timestamp=self.timestamp,
            expiry=self.expiry,
            metadata=self.metadata,
            pinned=self.pinned,
            cycle_count=self.cycle_count,
            content_type=self.content_type
        )
        
        # CRITICAL: FileMemoryBlock MUST reference an actual file on disk
        # Working memory is a symbolic view of disk-based memory, NOT in-memory storage
        from pathlib import Path
        
        # Special case for virtual files that don't need disk backing
        virtual_prefixes = ['boot_rom/', 'virtual/', 'restored']
        is_virtual = any(self.location.startswith(prefix) for prefix in virtual_prefixes)
        
        if not is_virtual:
            # Try to resolve the path to check if file exists
            try:
                # Handle both absolute and relative paths
                if self.location.startswith('/'):
                    file_path = Path(self.location)
                elif self.location.startswith('personal/'):
                    # This is relative to the cyber's filesystem root
                    # We can't check from here, but log for debugging
                    import logging
                    logger = logging.getLogger("Cyber.memory")
                    logger.debug(f"FileMemoryBlock created for cyber-relative path: {self.location}")
                elif self.location.startswith('grid/'):
                    # Grid-relative path
                    import logging
                    logger = logging.getLogger("Cyber.memory")
                    logger.debug(f"FileMemoryBlock created for grid-relative path: {self.location}")
                else:
                    # This shouldn't happen - all paths should be properly namespaced
                    import logging
                    logger = logging.getLogger("Cyber.memory")
                    logger.warning(f"FileMemoryBlock created with unnamespaced path: {self.location}")
            except Exception as e:
                import logging
                logger = logging.getLogger("Cyber.memory")
                logger.debug(f"Path validation for FileMemoryBlock: {e}")
        
        # Use path as ID - clean it up to be consistent
        path_str = str(self.location)
        
        # Remove leading slash if present
        if path_str.startswith('/'):
            path_str = path_str[1:]
        
        # Ensure proper namespace prefix
        if not (path_str.startswith('personal/') or path_str.startswith('grid/')):
            # Try to extract the meaningful part
            if '/personal/' in path_str:
                # Extract everything after /personal/
                path_str = 'personal/' + path_str.split('/personal/')[-1]
            elif '/grid/' in path_str:
                # Extract everything after /grid/
                path_str = 'grid/' + path_str.split('/grid/')[-1]
            else:
                # Default to personal if we can't determine
                # unless it's a special virtual path
                virtual_prefixes = ['boot_rom/', 'virtual/', 'restored']
                if not any(path_str.startswith(prefix) for prefix in virtual_prefixes):
                    path_str = 'personal/' + path_str
        
        # Set the ID to just the path - no suffixes
        # Line ranges and digests are already stored as properties
        self.id = path_str


@dataclass
class ObservationMemoryBlock(MemoryBlock):
    """Simple observation - something that happened."""
    observation_type: str  # Type of observation (action_result, file_change, new_message, etc.)
    path: str  # Path to the file containing details
    message: str  # What happened (e.g., "Result of action 'respond': Message sent successfully")
    cycle_count: int  # Which cycle this happened in
    content: Optional[str] = None  # Optional - small content included directly (< 1KB)
    confidence: float = 1.0
    priority: Priority = Priority.HIGH
    expiry: Optional[datetime] = None
    pinned: bool = False
    
    def __post_init__(self):
        """Initialize base class and set type."""
        # Observations have a special Mind-Swarm content type
        content_type = ContentType.MINDSWARM_OBSERVATION
        
        # Don't pass timestamp to parent - we don't use it
        super().__init__(
            confidence=self.confidence,
            priority=self.priority,
            timestamp=None,  # No timestamp needed
            expiry=self.expiry,
            metadata=None,  # No metadata
            pinned=self.pinned,
            cycle_count=self.cycle_count,  # Pass cycle_count to parent
            content_type=content_type
        )
        
        # Use path as ID with observation type and cycle for uniqueness
        path_str = str(self.path)
        if path_str.startswith('/'):
            path_str = path_str[1:]
        
        # Ensure proper namespace prefix
        if not (path_str.startswith('personal/') or path_str.startswith('grid/')):
            # Default observations to personal namespace
            path_str = f"personal/observations/{path_str}"
        
        # Use path as ID - uniqueness is handled by properties
        # observation_type and cycle_count are already stored as properties
        self.id = path_str