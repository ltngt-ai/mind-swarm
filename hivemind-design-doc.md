# Hive Mind Memory Model Design Document

## Overview

This document details the memory architecture for the hive mind AI system, focusing on the dual-layer approach: symbolic memory (Python objects) and context memory (JSON for LLM).

## Memory Architecture

### Two-Layer Memory System

```
┌─────────────────────────────────────────────────┐
│                 Filesystem                       │
│         (Persistent Shared Memory)               │
└─────────────────────────────────────────────────┘
                      ↕
┌─────────────────────────────────────────────────┐
│            Symbolic Memory Layer                 │
│         (Python Objects/References)              │
└─────────────────────────────────────────────────┘
                      ↕
┌─────────────────────────────────────────────────┐
│            Context Memory Layer                  │
│          (JSON Array for LLM)                    │
└─────────────────────────────────────────────────┘
```

## Symbolic Memory Model

### Base Memory Block

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime

class Priority(Enum):
    CRITICAL = 1  # Always included, never dropped
    HIGH = 2      # Included unless space critical
    MEDIUM = 3    # Included based on relevance
    LOW = 4       # Background info, often dropped

class MemoryType(Enum):
    ROM = "rom"
    FILE = "file"
    STATUS = "status"
    TASK = "task"
    MESSAGE = "message"
    KNOWLEDGE = "knowledge"
    HISTORY = "history"
    CONTEXT = "context"

@dataclass
class MemoryBlock:
    """Base class for all memory blocks"""
    type: MemoryType
    id: str
    confidence: float = 1.0
    priority: Priority = Priority.MEDIUM
    timestamp: datetime = None
    expiry: Optional[datetime] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}
```

### Specialized Memory Blocks

```python
@dataclass
class FileMemoryBlock(MemoryBlock):
    """Reference to file content"""
    location: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    digest: Optional[str] = None  # For change detection
    
    def __post_init__(self):
        super().__post_init__()
        self.type = MemoryType.FILE
        if self.start_line is not None and self.end_line is not None:
            self.id = f"{self.location}:{self.start_line}-{self.end_line}"
        else:
            self.id = self.location

@dataclass
class StatusMemoryBlock(MemoryBlock):
    """System status information"""
    status_type: str  # "mailbox", "task_queue", "system_health"
    value: Any
    
    def __post_init__(self):
        super().__post_init__()
        self.type = MemoryType.STATUS
        self.priority = Priority.HIGH  # Status usually important

@dataclass
class TaskMemoryBlock(MemoryBlock):
    """Current task representation"""
    task_id: str
    description: str
    project: Optional[str] = None
    dependencies: List[str] = None
    status: str = "pending"
    
    def __post_init__(self):
        super().__post_init__()
        self.type = MemoryType.TASK
        self.priority = Priority.HIGH

@dataclass
class MessageMemoryBlock(MemoryBlock):
    """Inter-agent messages"""
    from_agent: str
    to_agent: str
    subject: str
    preview: str  # First N characters
    full_path: str  # Path to full message
    read: bool = False
    
    def __post_init__(self):
        super().__post_init__()
        self.type = MemoryType.MESSAGE
        if not self.read:
            self.priority = Priority.HIGH

@dataclass
class KnowledgeMemoryBlock(MemoryBlock):
    """Reference to knowledge base entries"""
    topic: str
    subtopic: Optional[str] = None
    location: str
    relevance_score: float = 0.5
    
    def __post_init__(self):
        super().__post_init__()
        self.type = MemoryType.KNOWLEDGE

@dataclass
class HistoryMemoryBlock(MemoryBlock):
    """Recent agent actions/thoughts"""
    action_type: str
    action_detail: str
    result: Optional[str] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.type = MemoryType.HISTORY
        self.priority = Priority.MEDIUM

@dataclass
class ContextMemoryBlock(MemoryBlock):
    """Derived context from recent activities"""
    context_type: str  # "project_context", "conversation_context"
    summary: str
    related_ids: List[str] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.type = MemoryType.CONTEXT
```

## Memory Management

### Working Memory Manager

```python
class WorkingMemoryManager:
    def __init__(self, max_tokens: int = 100000):
        self.max_tokens = max_tokens
        self.symbolic_memory: List[MemoryBlock] = []
        self.context_memory: List[Dict] = []
        self.memory_index: Dict[str, MemoryBlock] = {}
        
    def add_memory(self, block: MemoryBlock):
        """Add a memory block to symbolic memory"""
        self.symbolic_memory.append(block)
        self.memory_index[block.id] = block
        
    def remove_memory(self, memory_id: str):
        """Remove a memory block"""
        if memory_id in self.memory_index:
            block = self.memory_index[memory_id]
            self.symbolic_memory.remove(block)
            del self.memory_index[memory_id]
    
    def update_confidence(self, memory_id: str, confidence: float):
        """Update confidence score for a memory block"""
        if memory_id in self.memory_index:
            self.memory_index[memory_id].confidence = confidence
```

### Memory Selection Algorithm

```python
class MemorySelector:
    def __init__(self, token_counter):
        self.token_counter = token_counter
        
    def select_memories(self, 
                       symbolic_memory: List[MemoryBlock],
                       max_tokens: int) -> List[MemoryBlock]:
        """Select memories to include in context"""
        
        # Step 1: Separate by priority
        critical = [m for m in symbolic_memory if m.priority == Priority.CRITICAL]
        high = [m for m in symbolic_memory if m.priority == Priority.HIGH]
        medium = [m for m in symbolic_memory if m.priority == Priority.MEDIUM]
        low = [m for m in symbolic_memory if m.priority == Priority.LOW]
        
        # Step 2: Sort within priority by relevance score
        high.sort(key=lambda m: (m.confidence, m.timestamp), reverse=True)
        medium.sort(key=lambda m: (m.confidence, m.timestamp), reverse=True)
        low.sort(key=lambda m: (m.confidence, m.timestamp), reverse=True)
        
        # Step 3: Build context respecting token limit
        selected = []
        used_tokens = 0
        
        # Always include critical
        for memory in critical:
            tokens = self.estimate_tokens(memory)
            selected.append(memory)
            used_tokens += tokens
            
        # Add high priority
        for memory in high:
            tokens = self.estimate_tokens(memory)
            if used_tokens + tokens < max_tokens * 0.8:  # Leave 20% buffer
                selected.append(memory)
                used_tokens += tokens
                
        # Add medium if space
        for memory in medium:
            tokens = self.estimate_tokens(memory)
            if used_tokens + tokens < max_tokens * 0.9:
                selected.append(memory)
                used_tokens += tokens
                
        # Add low if ample space
        for memory in low:
            tokens = self.estimate_tokens(memory)
            if used_tokens + tokens < max_tokens * 0.95:
                selected.append(memory)
                used_tokens += tokens
                
        return selected
```

## Context Memory Generation

### Content Loader

```python
class ContentLoader:
    def __init__(self, filesystem_root: str):
        self.filesystem_root = filesystem_root
        self.cache = {}  # Simple cache for repeated reads
        
    def load_content(self, memory: MemoryBlock) -> str:
        """Load actual content for a memory block"""
        
        if isinstance(memory, FileMemoryBlock):
            return self.load_file_content(memory)
        elif isinstance(memory, MessageMemoryBlock):
            return self.load_message_content(memory)
        elif isinstance(memory, KnowledgeMemoryBlock):
            return self.load_knowledge_content(memory)
        # ... other types
        
    def load_file_content(self, memory: FileMemoryBlock) -> str:
        """Load file content with caching"""
        cache_key = f"{memory.location}:{memory.digest}"
        
        if cache_key in self.cache:
            content = self.cache[cache_key]
        else:
            with open(memory.location, 'r') as f:
                if memory.start_line is not None:
                    lines = f.readlines()
                    content = ''.join(lines[memory.start_line:memory.end_line])
                else:
                    content = f.read()
            self.cache[cache_key] = content
            
        return content
```

### Context Builder

```python
class ContextBuilder:
    def __init__(self, content_loader: ContentLoader):
        self.content_loader = content_loader
        
    def build_context(self, selected_memories: List[MemoryBlock]) -> List[Dict]:
        """Convert symbolic memories to JSON context"""
        context = []
        
        for memory in selected_memories:
            content = self.content_loader.load_content(memory)
            
            context_entry = {
                "id": memory.id,
                "content": content,
                "confidence": memory.confidence,
                "priority": memory.priority.name.lower(),
                "metadata": self.build_metadata(memory)
            }
            
            context.append(context_entry)
            
        return context
    
    def build_metadata(self, memory: MemoryBlock) -> Dict:
        """Build metadata for context entry"""
        metadata = {
            "type": memory.type.value,
            "timestamp": memory.timestamp.isoformat(),
            **memory.metadata
        }
        
        # Add type-specific metadata
        if isinstance(memory, FileMemoryBlock):
            metadata["source"] = memory.location
            if memory.start_line is not None:
                metadata["lines"] = f"{memory.start_line}-{memory.end_line}"
                
        elif isinstance(memory, TaskMemoryBlock):
            metadata["task_id"] = memory.task_id
            metadata["status"] = memory.status
            
        # ... other types
        
        return metadata
```

## Memory Optimization Strategies

### Compression Techniques

```python
class MemoryCompressor:
    def __init__(self):
        self.summarizer = None  # Could use LLM for summarization
        
    def compress_if_needed(self, content: str, memory: MemoryBlock) -> str:
        """Compress content if too large"""
        
        # Different strategies based on memory type
        if memory.type == MemoryType.FILE:
            return self.compress_code(content, memory)
        elif memory.type == MemoryType.KNOWLEDGE:
            return self.compress_knowledge(content, memory)
        elif memory.type == MemoryType.HISTORY:
            return self.compress_history(content, memory)
        
        return content
    
    def compress_code(self, content: str, memory: FileMemoryBlock) -> str:
        """Compress code files"""
        # Could extract:
        # - Function signatures only
        # - Remove comments
        # - Extract relevant sections
        lines = content.split('\n')
        
        # Example: Keep only function definitions and class declarations
        compressed = []
        for line in lines:
            if any(keyword in line for keyword in ['def ', 'class ', 'import ']):
                compressed.append(line)
                
        return '\n'.join(compressed)
```

### Relevance Scoring

```python
class RelevanceScorer:
    def __init__(self):
        self.task_keywords = set()
        self.recent_files = set()
        self.conversation_context = []
        
    def score_memory(self, memory: MemoryBlock) -> float:
        """Calculate relevance score for a memory block"""
        base_score = memory.confidence
        
        # Recency boost
        age = (datetime.now() - memory.timestamp).total_seconds()
        recency_score = 1.0 / (1.0 + age / 3600)  # Decay over hours
        
        # Type-specific scoring
        if isinstance(memory, FileMemoryBlock):
            if memory.location in self.recent_files:
                base_score *= 1.5
                
        elif isinstance(memory, KnowledgeMemoryBlock):
            # Check keyword overlap
            topic_words = set(memory.topic.lower().split())
            overlap = len(topic_words & self.task_keywords)
            base_score *= (1.0 + overlap * 0.2)
            
        return min(base_score * recency_score, 1.0)
```

## Memory Lifecycle

### Memory Creation Pipeline

```python
def create_memory_from_action(action: str, result: Any) -> MemoryBlock:
    """Create appropriate memory block from agent action"""
    
    if action == "read_file":
        return FileMemoryBlock(
            location=result['path'],
            start_line=result.get('start_line'),
            end_line=result.get('end_line'),
            digest=result.get('digest'),
            priority=Priority.HIGH
        )
    elif action == "check_mailbox":
        messages = []
        for msg in result['messages']:
            messages.append(MessageMemoryBlock(
                from_agent=msg['from'],
                to_agent=msg['to'],
                subject=msg['subject'],
                preview=msg['content'][:100],
                full_path=msg['path'],
                read=False
            ))
        return messages
    # ... other actions
```

### Memory Decay and Cleanup

```python
class MemoryJanitor:
    def cleanup_memories(self, memories: List[MemoryBlock]) -> List[MemoryBlock]:
        """Remove expired or low-value memories"""
        active_memories = []
        
        for memory in memories:
            # Check expiry
            if memory.expiry and datetime.now() > memory.expiry:
                continue
                
            # Check relevance threshold
            if memory.confidence < 0.1 and memory.priority == Priority.LOW:
                continue
                
            # Type-specific cleanup
            if isinstance(memory, HistoryMemoryBlock):
                # Keep only recent history
                age = (datetime.now() - memory.timestamp).total_seconds()
                if age > 3600 and memory.priority != Priority.HIGH:
                    continue
                    
            active_memories.append(memory)
            
        return active_memories
```

## Example Usage

```python
# Initialize memory system
manager = WorkingMemoryManager(max_tokens=100000)
selector = MemorySelector(token_counter)
loader = ContentLoader("/hivemind")
builder = ContextBuilder(loader)

# Add ROM (always critical)
rom_memory = FileMemoryBlock(
    location="/hivemind/agents/agent_001/ROM.md",
    priority=Priority.CRITICAL,
    confidence=1.0
)
manager.add_memory(rom_memory)

# Add current task
task_memory = TaskMemoryBlock(
    task_id="TASK-042",
    description="Implement authentication module",
    project="project_alpha",
    status="in_progress",
    priority=Priority.HIGH
)
manager.add_memory(task_memory)

# Add relevant files
for file_path in relevant_files:
    file_memory = FileMemoryBlock(
        location=file_path,
        priority=Priority.MEDIUM,
        confidence=0.8
    )
    manager.add_memory(file_memory)

# Build context for LLM
selected = selector.select_memories(manager.symbolic_memory, manager.max_tokens)
context = builder.build_context(selected)

# Send to LLM
llm_response = llm.complete(json.dumps(context))
```

## Performance Considerations

1. **Lazy Loading**: Only load file content when selected for context
2. **Caching**: Cache frequently accessed files with TTL
3. **Incremental Updates**: Update only changed portions of memory
4. **Parallel Loading**: Load multiple files concurrently
5. **Memory Pooling**: Reuse memory objects to reduce allocation

## Future Enhancements

1. **Semantic Chunking**: Break large files into semantic units
2. **Cross-Reference Index**: Track relationships between memories
3. **Learned Relevance**: ML model for relevance scoring
4. **Differential Memory**: Track changes between think cycles
5. **Memory Compression**: LLM-based summarization for large content