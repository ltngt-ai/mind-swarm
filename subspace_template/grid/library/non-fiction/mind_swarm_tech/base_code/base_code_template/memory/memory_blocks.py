"""Memory block definition for the Cyber memory system.

Provides the core data structure for symbolic memory representation.
Each block represents a reference to content in the filesystem.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime
from .memory_types import Priority, ContentType


@dataclass
class MemoryBlock:
    """Reference to file content in the filesystem.
    
    All memory in the system is file-based. Working memory is just a 
    symbolic view of disk-based memory, NOT in-memory storage.
    """
    location: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    digest: Optional[str] = None
    confidence: float = 1.0
    priority: Priority = Priority.MEDIUM
    timestamp: Optional[datetime] = None
    expiry: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    pinned: bool = False  # When True, memory is never removed by memory management
    cycle_count: Optional[int] = None  # Track which cycle this memory was created in
    content_type: Optional[ContentType] = None  # Explicit content type
    no_cache: bool = False  # If True, content should not be cached (e.g., memory-mapped files)
    

    def __post_init__(self):
        """Initialize and validate the memory block."""
        # Set timestamp if not provided
        if self.timestamp is None:
            self.timestamp = datetime.now()
        
        # Initialize metadata if not provided
        if self.metadata is None:
            self.metadata = {}
        
        # Detect content type from file extension if not provided
        if self.content_type is None:
            self.content_type = ContentType.from_file_extension(self.location)
        
        # CRITICAL: MemoryBlock MUST reference an actual file on disk
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
                    logger.debug(f"MemoryBlock created for cyber-relative path: {self.location}")
                elif self.location.startswith('grid/'):
                    # Grid-relative path
                    import logging
                    logger = logging.getLogger("Cyber.memory")
                    logger.debug(f"MemoryBlock created for grid-relative path: {self.location}")
                else:
                    # This shouldn't happen - all paths should be properly namespaced
                    import logging
                    logger = logging.getLogger("Cyber.memory")
                    logger.warning(f"MemoryBlock created with unnamespaced path: {self.location}")
            except Exception as e:
                import logging
                logger = logging.getLogger("Cyber.memory")
                logger.debug(f"Path validation for MemoryBlock: {e}")
        
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