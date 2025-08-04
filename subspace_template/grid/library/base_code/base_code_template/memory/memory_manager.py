"""Working Memory Manager - manages symbolic memory for agents.

This is the core memory management system that holds symbolic references
to filesystem content without loading the actual data until needed.
"""

from typing import List, Dict, Optional, Set, Any
from datetime import datetime, timedelta
import logging

from .memory_blocks import (
    MemoryBlock, Priority, MemoryType,
    FileMemoryBlock, MessageMemoryBlock, ObservationMemoryBlock
)

logger = logging.getLogger("agent.memory")


class WorkingMemoryManager:
    """Manages the agent's working memory with symbolic references."""
    
    def __init__(self, max_tokens: int = 100000):
        """Initialize the memory manager.
        
        Args:
            max_tokens: Maximum token budget for context
        """
        self.max_tokens = max_tokens
        self.symbolic_memory: List[MemoryBlock] = []
        self.memory_index: Dict[str, MemoryBlock] = {}
        
        # Track memory categories for quick access
        self.memories_by_type: Dict[MemoryType, List[MemoryBlock]] = {
            mem_type: [] for mem_type in MemoryType
        }
        
        # Track recent accesses for relevance
        self.access_history: Dict[str, datetime] = {}
        
        # Active context tracking
        self.current_task_id: Optional[str] = None
        self.active_topics: Set[str] = set()
    
    def add_memory(self, block: MemoryBlock) -> None:
        """Add a memory block to symbolic memory."""
        # Check if memory already exists
        if block.id in self.memory_index:
            # Update existing memory
            old_block = self.memory_index[block.id]
            self.symbolic_memory.remove(old_block)
            self.memories_by_type[old_block.type].remove(old_block)
        
        # Add new memory
        self.symbolic_memory.append(block)
        self.memory_index[block.id] = block
        self.memories_by_type[block.type].append(block)
        
        logger.debug(f"Added memory: {block.id} (type={block.type.value}, priority={block.priority.name})")
    
    def remove_memory(self, memory_id: str) -> None:
        """Remove a memory block."""
        if memory_id in self.memory_index:
            block = self.memory_index[memory_id]
            self.symbolic_memory.remove(block)
            self.memories_by_type[block.type].remove(block)
            del self.memory_index[memory_id]
            
            # Clean up access history
            if memory_id in self.access_history:
                del self.access_history[memory_id]
            
            logger.debug(f"Removed memory: {memory_id}")
    
    def update_confidence(self, memory_id: str, confidence: float) -> None:
        """Update confidence score for a memory block."""
        if memory_id in self.memory_index:
            self.memory_index[memory_id].confidence = max(0.0, min(1.0, confidence))
    
    def access_memory(self, memory_id: str) -> Optional[MemoryBlock]:
        """Access a memory and update access history."""
        if memory_id in self.memory_index:
            self.access_history[memory_id] = datetime.now()
            return self.memory_index[memory_id]
        return None
    
    def get_memories_by_type(self, memory_type: MemoryType) -> List[MemoryBlock]:
        """Get all memories of a specific type."""
        return self.memories_by_type.get(memory_type, []).copy()
    
    def get_recent_memories(self, seconds: int = 300) -> List[MemoryBlock]:
        """Get memories created in the last N seconds."""
        cutoff = datetime.now() - timedelta(seconds=seconds)
        return [m for m in self.symbolic_memory if m.timestamp > cutoff]
    
    def get_unread_messages(self) -> List[MessageMemoryBlock]:
        """Get all unread messages."""
        messages = self.get_memories_by_type(MemoryType.MESSAGE)
        return [m for m in messages if isinstance(m, MessageMemoryBlock) and not m.read]
    
    def mark_message_read(self, message_id: str) -> None:
        """Mark a message as read and lower its priority."""
        memory = self.access_memory(message_id)
        if memory and isinstance(memory, MessageMemoryBlock):
            memory.read = True
            memory.priority = Priority.MEDIUM
    
    def set_current_task(self, task_id: str) -> None:
        """Set the current active task."""
        self.current_task_id = task_id
        logger.debug(f"Set current task: {task_id}")
    
    def add_active_topic(self, topic: str) -> None:
        """Add a topic to the active topics set."""
        self.active_topics.add(topic)
    
    def remove_active_topic(self, topic: str) -> None:
        """Remove a topic from active topics."""
        self.active_topics.discard(topic)
    
    def cleanup_expired(self) -> int:
        """Remove expired memories and return count removed."""
        now = datetime.now()
        expired = [m for m in self.symbolic_memory if m.expiry and m.expiry < now]
        
        for memory in expired:
            self.remove_memory(memory.id)
        
        return len(expired)
    
    def cleanup_old_observations(self, max_age_seconds: int = 3600) -> int:
        """Remove old observation entries beyond max age."""
        cutoff = datetime.now() - timedelta(seconds=max_age_seconds)
        old_observations = [
            m for m in self.get_memories_by_type(MemoryType.OBSERVATION)
            if m.timestamp < cutoff and m.priority == Priority.LOW
        ]
        
        for memory in old_observations:
            self.remove_memory(memory.id)
        
        return len(old_observations)
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get statistics about current memory state."""
        type_counts = {
            mem_type.value: len(memories)
            for mem_type, memories in self.memories_by_type.items()
        }
        
        priority_counts = {
            priority.name: sum(1 for m in self.symbolic_memory if m.priority == priority)
            for priority in Priority
        }
        
        return {
            "total_memories": len(self.symbolic_memory),
            "by_type": type_counts,
            "by_priority": priority_counts,
            "current_task": self.current_task_id,
            "active_topics": list(self.active_topics),
            "unread_messages": len(self.get_unread_messages())
        }
    
    def create_snapshot(self) -> Dict[str, Any]:
        """Create a snapshot of current memory state for persistence."""
        return {
            "timestamp": datetime.now().isoformat(),
            "max_tokens": self.max_tokens,
            "current_task_id": self.current_task_id,
            "active_topics": list(self.active_topics),
            "memories": [
                {
                    "type": memory.type.value,
                    "id": memory.id,
                    "confidence": memory.confidence,
                    "priority": memory.priority.name,
                    "timestamp": memory.timestamp.isoformat(),
                    "expiry": memory.expiry.isoformat() if memory.expiry else None,
                    "metadata": memory.metadata,
                    # Type-specific fields
                    **self._get_type_specific_fields(memory)
                }
                for memory in self.symbolic_memory
            ]
        }
    
    def _get_type_specific_fields(self, memory: MemoryBlock) -> Dict[str, Any]:
        """Extract type-specific fields from a memory block."""
        fields = {}
        
        if isinstance(memory, FileMemoryBlock):
            fields.update({
                "location": memory.location,
                "start_line": memory.start_line,
                "end_line": memory.end_line,
                "digest": memory.digest
            })
        elif isinstance(memory, MessageMemoryBlock):
            fields.update({
                "from_agent": memory.from_agent,
                "to_agent": memory.to_agent,
                "subject": memory.subject,
                "preview": memory.preview,
                "full_path": memory.full_path,
                "read": memory.read
            })
        elif isinstance(memory, ObservationMemoryBlock):
            fields.update({
                "observation_type": memory.observation_type,
                "path": memory.path,
                "description": memory.description
            })
        elif hasattr(memory, 'cycle_state'):  # CycleStateMemoryBlock
            fields.update({
                "cycle_state": memory.cycle_state,
                "cycle_count": memory.cycle_count,
                "current_observation": memory.current_observation,
                "current_orientation": memory.current_orientation,
                "current_actions": memory.current_actions
            })
        # Add other types as needed
        
        return fields