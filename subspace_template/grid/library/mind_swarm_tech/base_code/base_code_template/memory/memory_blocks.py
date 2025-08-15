"""Memory block definitions for the Cyber memory system.

Provides the core data structures for symbolic memory representation.
Each block represents a reference to content in the filesystem.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from .memory_types import Priority, MemoryType
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
                 cycle_count: Optional[int] = None):
        """Initialize base memory block."""
        self.confidence = confidence
        self.priority = priority
        self.timestamp = timestamp or datetime.now()
        self.expiry = expiry
        self.metadata = metadata or {}
        self.pinned = pinned  # When True, memory is never removed by memory management
        self.cycle_count = cycle_count  # Track which cycle this memory was created in
        
        # These must be set by subclasses
        self.type: MemoryType
        self.id: str


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
    no_cache: bool = False  # If True, content should not be cached (e.g., memory-mapped files)
    block_type: Optional[MemoryType] = None  # Override the default FILE type (e.g., KNOWLEDGE)
    

    def __post_init__(self):
        """Initialize base class and set type."""
        super().__init__(
            confidence=self.confidence,
            priority=self.priority,
            timestamp=self.timestamp,
            expiry=self.expiry,
            metadata=self.metadata,
            pinned=self.pinned,
            cycle_count=self.cycle_count
        )
        # Use provided block_type or default to FILE
        self.type = self.block_type if self.block_type else MemoryType.FILE
        
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
        
        # Generate unified ID
        self.id = UnifiedMemoryID.create_from_path(self.location, self.type)
        
        # Add line range suffix if specified
        if self.start_line is not None and self.end_line is not None:
            parts = UnifiedMemoryID.parse(self.id)
            path_with_lines = f"{parts['path']}/lines-{self.start_line}-{self.end_line}"
            self.id = UnifiedMemoryID.create(
                self.type,
                path_with_lines,
                f"{self.location}:{self.start_line}-{self.end_line}"
            )
        elif self.digest:
            # Add content hash if we have a digest
            parts = UnifiedMemoryID.parse(self.id)
            self.id = UnifiedMemoryID.create(
                self.type,
                parts['path'],
                self.digest
            )


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
        # Don't pass timestamp to parent - we don't use it
        super().__init__(
            confidence=self.confidence,
            priority=self.priority,
            timestamp=None,  # No timestamp needed
            expiry=self.expiry,
            metadata=None,  # No metadata
            pinned=self.pinned,
            cycle_count=self.cycle_count  # Pass cycle_count to parent
        )
        self.type = MemoryType.OBSERVATION
        
        # Use unified ID that prevents duplication
        # Include cycle count in ID to make observations unique per cycle
        self.id = UnifiedMemoryID.create_observation_id(
            self.observation_type,
            f"{self.path}:cycle_{self.cycle_count}"
        )