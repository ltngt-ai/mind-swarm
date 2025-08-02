"""Memory block definitions for the agent memory system.

Provides the core data structures for symbolic memory representation.
Each block represents a reference to content in the filesystem.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime


class Priority(Enum):
    """Memory priority levels for selection algorithm."""
    CRITICAL = 1  # Always included, never dropped
    HIGH = 2      # Included unless space critical
    MEDIUM = 3    # Included based on relevance
    LOW = 4       # Background info, often dropped


class MemoryType(Enum):
    """Types of memory blocks."""
    ROM = "rom"
    FILE = "file"
    STATUS = "status"
    TASK = "task"
    MESSAGE = "message"
    KNOWLEDGE = "knowledge"
    HISTORY = "history"
    CONTEXT = "context"
    OBSERVATION = "observation"


class MemoryBlock:
    """Base class for all memory blocks - not a dataclass to avoid inheritance issues."""
    
    def __init__(self, 
                 confidence: float = 1.0,
                 priority: Priority = Priority.MEDIUM,
                 timestamp: Optional[datetime] = None,
                 expiry: Optional[datetime] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        """Initialize base memory block."""
        self.confidence = confidence
        self.priority = priority
        self.timestamp = timestamp or datetime.now()
        self.expiry = expiry
        self.metadata = metadata or {}
        
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
    
    def __post_init__(self):
        """Initialize base class and set type."""
        super().__init__(
            confidence=self.confidence,
            priority=self.priority,
            timestamp=self.timestamp,
            expiry=self.expiry,
            metadata=self.metadata
        )
        self.type = MemoryType.FILE
        if self.start_line is not None and self.end_line is not None:
            self.id = f"{self.location}:{self.start_line}-{self.end_line}"
        else:
            self.id = self.location


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
    
    def __post_init__(self):
        """Initialize base class and set type."""
        super().__init__(
            confidence=self.confidence,
            priority=self.priority,
            timestamp=self.timestamp,
            expiry=self.expiry,
            metadata=self.metadata
        )
        self.type = MemoryType.STATUS
        self.id = f"status:{self.status_type}"


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
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize base class and set type."""
        super().__init__(
            confidence=self.confidence,
            priority=self.priority,
            timestamp=self.timestamp,
            expiry=self.expiry,
            metadata=self.metadata
        )
        self.type = MemoryType.TASK
        self.id = f"task:{self.task_id}"
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class MessageMemoryBlock(MemoryBlock):
    """Inter-agent messages."""
    from_agent: str
    to_agent: str
    subject: str
    preview: str
    full_path: str
    read: bool = False
    confidence: float = 1.0
    priority: Priority = Priority.MEDIUM
    timestamp: Optional[datetime] = None
    expiry: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize base class and set type."""
        super().__init__(
            confidence=self.confidence,
            priority=self.priority if self.read else Priority.HIGH,
            timestamp=self.timestamp,
            expiry=self.expiry,
            metadata=self.metadata
        )
        self.type = MemoryType.MESSAGE
        self.id = f"msg:{self.full_path}"


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
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize base class and set type."""
        super().__init__(
            confidence=self.confidence,
            priority=self.priority,
            timestamp=self.timestamp,
            expiry=self.expiry,
            metadata=self.metadata
        )
        self.type = MemoryType.KNOWLEDGE
        if self.subtopic:
            self.id = f"knowledge:{self.topic}:{self.subtopic}"
        else:
            self.id = f"knowledge:{self.topic}"


@dataclass
class HistoryMemoryBlock(MemoryBlock):
    """Recent agent actions/thoughts."""
    action_type: str
    action_detail: str
    result: Optional[str] = None
    confidence: float = 1.0
    priority: Priority = Priority.MEDIUM
    timestamp: Optional[datetime] = None
    expiry: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize base class and set type."""
        super().__init__(
            confidence=self.confidence,
            priority=self.priority,
            timestamp=self.timestamp,
            expiry=self.expiry,
            metadata=self.metadata
        )
        self.type = MemoryType.HISTORY
        self.id = f"history:{self.action_type}:{self.timestamp.timestamp()}"


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
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize base class and set type."""
        super().__init__(
            confidence=self.confidence,
            priority=self.priority,
            timestamp=self.timestamp,
            expiry=self.expiry,
            metadata=self.metadata
        )
        self.type = MemoryType.CONTEXT
        self.id = f"context:{self.context_type}:{self.timestamp.timestamp()}"
        if self.related_ids is None:
            self.related_ids = []


@dataclass
class ObservationMemoryBlock(MemoryBlock):
    """Filesystem observations - new files, changes, etc."""
    observation_type: str
    path: str
    description: str
    confidence: float = 1.0
    priority: Priority = Priority.HIGH
    timestamp: Optional[datetime] = None
    expiry: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize base class and set type."""
        super().__init__(
            confidence=self.confidence,
            priority=self.priority,
            timestamp=self.timestamp,
            expiry=self.expiry,
            metadata=self.metadata
        )
        self.type = MemoryType.OBSERVATION
        self.id = f"obs:{self.path}:{self.timestamp.timestamp()}"