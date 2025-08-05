"""Memory block definitions for the agent memory system.

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
                 pinned: bool = False):
        """Initialize base memory block."""
        self.confidence = confidence
        self.priority = priority
        self.timestamp = timestamp or datetime.now()
        self.expiry = expiry
        self.metadata = metadata or {}
        self.pinned = pinned  # When True, memory is never removed by memory management
        
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
    

    def __post_init__(self):
        """Initialize base class and set type."""
        super().__init__(
            confidence=self.confidence,
            priority=self.priority,
            timestamp=self.timestamp,
            expiry=self.expiry,
            metadata=self.metadata,
            pinned=self.pinned
        )
        self.type = MemoryType.FILE
        
        # Generate unified ID
        base_id = UnifiedMemoryID.create_from_path(self.location, MemoryType.FILE)
        
        # Add line range to semantic path if specified
        if self.start_line is not None and self.end_line is not None:
            parts = UnifiedMemoryID.parse(base_id)
            semantic_path = f"{parts['semantic_path']}/lines-{self.start_line}-{self.end_line}"
            self.id = UnifiedMemoryID.create(
                MemoryType.FILE, 
                parts['namespace'], 
                semantic_path,
                f"{self.location}:{self.start_line}-{self.end_line}"
            )
        else:
            # Add content hash if we have a digest
            if self.digest:
                parts = UnifiedMemoryID.parse(base_id)
                self.id = UnifiedMemoryID.create(
                    MemoryType.FILE,
                    parts['namespace'],
                    parts['semantic_path'],
                    self.digest
                )
            else:
                self.id = base_id


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
    

    def __post_init__(self):
        """Initialize base class and set type."""
        super().__init__(
            confidence=self.confidence,
            priority=self.priority,
            timestamp=self.timestamp,
            expiry=self.expiry,
            metadata=self.metadata,
            pinned=self.pinned
        )
        self.type = MemoryType.STATUS
        
        # Status is always in system namespace
        self.id = UnifiedMemoryID.create(MemoryType.STATUS, 'system', self.status_type)


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
            pinned=self.pinned
        )
        self.type = MemoryType.TASK
        
        # Create semantic path from project and task ID
        if self.project:
            semantic_path = f"{self.project}/{self.task_id}"
        else:
            semantic_path = f"general/{self.task_id}"
        
        # Tasks are in personal namespace
        self.id = UnifiedMemoryID.create(MemoryType.TASK, 'personal', semantic_path)
        
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
    pinned: bool = False
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
        
        # Create semantic path from sender and subject
        semantic_path = f"from-{self.from_agent}/{self.subject.lower().replace(' ', '-')}"
        
        # Determine namespace based on path
        namespace = 'inbox' if '/inbox/' in self.full_path else 'outbox'
        
        # Create ID with content hash based on full message info
        content = f"{self.from_agent}:{self.to_agent}:{self.subject}:{self.preview}"
        self.id = UnifiedMemoryID.create(MemoryType.MESSAGE, namespace, semantic_path, content)


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
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize base class and set type."""
        super().__init__(
            confidence=self.confidence,
            priority=self.priority,
            timestamp=self.timestamp,
            expiry=self.expiry,
            metadata=self.metadata,
            pinned=self.pinned
        )
        self.type = MemoryType.KNOWLEDGE
        
        # Create semantic path from topic/subtopic
        semantic_path = self.topic
        if self.subtopic:
            semantic_path = f"{self.topic}/{self.subtopic}"
        
        # Determine namespace from location
        namespace = 'library' if '/library/' in self.location else 'rom'
        
        # Create ID with content identifier
        self.id = UnifiedMemoryID.create(MemoryType.KNOWLEDGE, namespace, semantic_path)




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
    
    def __post_init__(self):
        """Initialize base class and set type."""
        super().__init__(
            confidence=self.confidence,
            priority=self.priority,
            timestamp=self.timestamp,
            expiry=self.expiry,
            metadata=self.metadata,
            pinned=self.pinned
        )
        self.type = MemoryType.CONTEXT
        
        # Create semantic path with context type and timestamp
        semantic_path = f"{self.context_type}/{self.timestamp.strftime('%Y%m%d-%H%M%S')}"
        
        # Context is derived, so in analysis namespace
        # Include content hash based on summary
        self.id = UnifiedMemoryID.create(MemoryType.CONTEXT, 'analysis', semantic_path, self.summary)
        
        if self.related_ids is None:
            self.related_ids = []


@dataclass
class ObservationMemoryBlock(MemoryBlock):
    """Filesystem observations - new files, changes, etc."""
    observation_type: str
    path: str
    confidence: float = 1.0
    priority: Priority = Priority.HIGH
    timestamp: Optional[datetime] = None
    expiry: Optional[datetime] = None
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
            pinned=self.pinned
        )
        self.type = MemoryType.OBSERVATION
        
        # Use unified ID that prevents duplication
        self.id = UnifiedMemoryID.create_observation_id(
            self.observation_type,
            self.path
        )



@dataclass
class CycleStateMemoryBlock(MemoryBlock):
    """Stores the current state of the cognitive cycle for resumable execution."""
    cycle_state: str  # Current state: perceive, observe, orient, decide, act
    cycle_count: int
    current_observation: Optional[Dict[str, Any]] = None
    current_orientation: Optional[Dict[str, Any]] = None
    current_actions: Optional[List[Dict[str, Any]]] = None
    last_observe_time: Optional[datetime] = None  # Track when observe last ran
    confidence: float = 1.0
    priority: Priority = Priority.LOW  # Internal bookkeeping, not actionable for agent
    timestamp: Optional[datetime] = None
    expiry: Optional[datetime] = None
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
            pinned=self.pinned
        )
        self.type = MemoryType.CYCLE_STATE
        
        # Cycle state is a singleton in system namespace
        self.id = UnifiedMemoryID.create(MemoryType.CYCLE_STATE, 'system', 'current')


@dataclass
class IdentityMemoryBlock(MemoryBlock):
    """Agent identity and vital statistics - always included in working memory."""
    name: str
    agent_type: str
    model: str
    max_context_length: int
    provider: str
    created_at: str  # ISO timestamp
    capabilities: Optional[List[str]] = None
    confidence: float = 1.0
    priority: Priority = Priority.LOW  # Background identity, not actionable focus
    timestamp: Optional[datetime] = None
    expiry: Optional[datetime] = None
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
            pinned=self.pinned
        )
        self.type = MemoryType.IDENTITY
        
        # Identity is a singleton in system namespace
        self.id = UnifiedMemoryID.create(MemoryType.IDENTITY, 'system', 'self')
        
        if self.capabilities is None:
            self.capabilities = []