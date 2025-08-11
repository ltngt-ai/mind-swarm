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
        self.type = MemoryType.FILE
        
        # Generate unified ID
        self.id = UnifiedMemoryID.create_from_path(self.location, MemoryType.FILE)
        
        # Add line range suffix if specified
        if self.start_line is not None and self.end_line is not None:
            parts = UnifiedMemoryID.parse(self.id)
            path_with_lines = f"{parts['path']}/lines-{self.start_line}-{self.end_line}"
            self.id = UnifiedMemoryID.create(
                MemoryType.FILE,
                path_with_lines,
                f"{self.location}:{self.start_line}-{self.end_line}"
            )
        elif self.digest:
            # Add content hash if we have a digest
            parts = UnifiedMemoryID.parse(self.id)
            self.id = UnifiedMemoryID.create(
                MemoryType.FILE,
                parts['path'],
                self.digest
            )


@dataclass
class StatusMemoryBlock(MemoryBlock):
    """System status information."""
    status_type: str
    value: Any
    confidence: float = 1.0
    priority: Priority = Priority.HIGH
    timestamp: Optional[datetime] = None
    expiry: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    pinned: bool = False
    cycle_count: Optional[int] = None
    

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
        self.type = MemoryType.STATUS
        
        # Status is always in system namespace
        self.id = UnifiedMemoryID.create(MemoryType.STATUS, f"personal/system/{self.status_type}")


@dataclass
class TaskMemoryBlock(MemoryBlock):
    """Current task representation."""
    task_id: str
    description: str
    project: Optional[str] = None
    dependencies: Optional[List[str]] = None
    status: str = "pending"
    confidence: float = 1.0
    priority: Priority = Priority.HIGH
    timestamp: Optional[datetime] = None
    expiry: Optional[datetime] = None
    cycle_count: Optional[int] = None
    pinned: bool = False
    metadata: Optional[Dict[str, Any]] = None
    
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
        self.type = MemoryType.TASK
        
        # Create path from project and task ID
        if self.project:
            path = f"personal/tasks/{self.project}/{self.task_id}"
        else:
            path = f"personal/tasks/general/{self.task_id}"
        
        self.id = UnifiedMemoryID.create(MemoryType.TASK, path)
        
        if self.dependencies is None:
            self.dependencies = []


# MessageMemoryBlock removed - messages are now FileMemoryBlock with metadata

@dataclass
class KnowledgeMemoryBlock(MemoryBlock):
    """Reference to knowledge base entries."""
    topic: str
    location: str
    subtopic: Optional[str] = None
    relevance_score: float = 0.5
    confidence: float = 1.0
    priority: Priority = Priority.MEDIUM
    timestamp: Optional[datetime] = None
    expiry: Optional[datetime] = None
    pinned: bool = False
    cycle_count: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    
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
        self.type = MemoryType.KNOWLEDGE
        
        # Create path from location and topic/subtopic
        if '/library/' in self.location:
            if self.subtopic:
                path = f"grid/library/{self.topic}/{self.subtopic}"
            else:
                path = f"grid/library/{self.topic}"
        else:
            # ROM or other knowledge
            if self.subtopic:
                path = f"personal/knowledge/{self.topic}/{self.subtopic}"
            else:
                path = f"personal/knowledge/{self.topic}"
        
        self.id = UnifiedMemoryID.create(MemoryType.KNOWLEDGE, path)




@dataclass
class ContextMemoryBlock(MemoryBlock):
    """Derived context from recent activities."""
    context_type: str
    summary: str
    related_ids: Optional[List[str]] = None
    confidence: float = 1.0
    priority: Priority = Priority.MEDIUM
    timestamp: Optional[datetime] = None
    expiry: Optional[datetime] = None
    pinned: bool = False
    metadata: Optional[Dict[str, Any]] = None
    cycle_count: Optional[int] = None
    
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
        self.type = MemoryType.CONTEXT
        
        # Create path with context type and timestamp
        path = f"personal/analysis/{self.context_type}/{self.timestamp.strftime('%Y%m%d-%H%M%S')}"
        
        # Include content hash based on summary
        self.id = UnifiedMemoryID.create(MemoryType.CONTEXT, path, self.summary)
        
        if self.related_ids is None:
            self.related_ids = []


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




# IdentityMemoryBlock removed - use pinned FileMemoryBlock for identity.json instead