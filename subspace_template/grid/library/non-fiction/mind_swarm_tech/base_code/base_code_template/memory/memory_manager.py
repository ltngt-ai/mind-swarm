"""Working Memory Manager - manages symbolic memory for Cybers.

This is the core memory management system that holds symbolic references
to filesystem content without loading the actual data until needed.
"""

from typing import List, Dict, Optional, Set, Any
from datetime import datetime, timedelta
from pathlib import Path
import logging

from .memory_blocks import (
    MemoryBlock, Priority,
    FileMemoryBlock
)
from .memory_types import ContentType

logger = logging.getLogger("Cyber.memory")


class WorkingMemoryManager:
    """Manages the Cyber's working memory with symbolic references."""
    
    def __init__(self, max_tokens: int = 100000):
        """Initialize the memory manager.
        
        Args:
            max_tokens: Maximum token budget for context
        """
        self.max_tokens = max_tokens
        self.symbolic_memory: List[MemoryBlock] = []
        self.memory_index: Dict[str, MemoryBlock] = {}
        
        # Track memory categories for quick access by content type
        self.memories_by_content_type: Dict[str, List[MemoryBlock]] = {}
        
        # Track recent accesses for relevance
        self.access_history: Dict[str, datetime] = {}
        
        # Active context tracking
        self.current_task_id: Optional[str] = None
        self.active_topics: Set[str] = set()
    
    def add_memory(self, block: MemoryBlock) -> None:
        """Add a memory block to symbolic memory.
        
        If a memory with the same ID already exists, it will be replaced.
        The ID should be unique - use location/path as the ID.
        Line ranges and digests are stored as properties, not in the ID.
        """
        # Check if memory already exists
        if block.id in self.memory_index:
            # Update existing memory
            old_block = self.memory_index[block.id]
            self.symbolic_memory.remove(old_block)
            # Remove from content type tracking
            content_type_str = old_block.content_type.value if hasattr(old_block.content_type, 'value') else str(old_block.content_type)
            if content_type_str in self.memories_by_content_type:
                if old_block in self.memories_by_content_type[content_type_str]:
                    self.memories_by_content_type[content_type_str].remove(old_block)
        
        # Add new memory
        self.symbolic_memory.append(block)
        self.memory_index[block.id] = block
        
        # Track by content type
        content_type_str = block.content_type.value if hasattr(block.content_type, 'value') else str(block.content_type)
        if content_type_str not in self.memories_by_content_type:
            self.memories_by_content_type[content_type_str] = []
        self.memories_by_content_type[content_type_str].append(block)
        
        # Log pinned memories at INFO level for visibility
        if block.pinned:
            logger.info(f"Added PINNED memory: {block.id} (content_type={content_type_str}, priority={block.priority.name})")
        else:
            logger.debug(f"Added memory: {block.id} (content_type={content_type_str}, priority={block.priority.name})")
    
    def remove_memory(self, memory_id: str) -> None:
        """Remove a memory block."""
        if memory_id in self.memory_index:
            block = self.memory_index[memory_id]
            
            # Safely remove from symbolic_memory
            if block in self.symbolic_memory:
                self.symbolic_memory.remove(block)
            
            # Safely remove from memories_by_content_type
            content_type_str = block.content_type.value if hasattr(block.content_type, 'value') else str(block.content_type)
            if content_type_str in self.memories_by_content_type:
                if block in self.memories_by_content_type[content_type_str]:
                    self.memories_by_content_type[content_type_str].remove(block)
            
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
    
    def get_memories_by_content_type(self, content_type: ContentType) -> List[MemoryBlock]:
        """Get all memories of a specific content type."""
        content_type_str = content_type.value if hasattr(content_type, 'value') else str(content_type)
        return self.memories_by_content_type.get(content_type_str, []).copy()
    
    def get_recent_memories(self, seconds: int = 300) -> List[MemoryBlock]:
        """Get memories created in the last N seconds."""
        cutoff = datetime.now() - timedelta(seconds=seconds)
        return [m for m in self.symbolic_memory if m.timestamp > cutoff]
    
    def mark_message_read(self, memory_id: str) -> None:
        """Mark an observation as focused/read by lowering its priority.
        
        This is used when focusing on observations, especially message notifications.
        """
        memory = self.access_memory(memory_id)
        if memory and isinstance(memory, ObservationMemoryBlock):
            memory.metadata['focused'] = True
            memory.metadata['focused_at'] = datetime.now().isoformat()
            memory.priority = Priority.LOW
            logger.debug(f"Marked observation {memory_id} as focused")
    
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
        """Remove expired memories and return count removed (except pinned ones)."""
        now = datetime.now()
        expired = [m for m in self.symbolic_memory if m.expiry and m.expiry < now and not m.pinned]
        
        for memory in expired:
            self.remove_memory(memory.id)
        
        return len(expired)
    
    # ObservationMemoryBlock removed - observations are now ephemeral
    # cleanup_old_observations method removed
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get statistics about current memory state."""
        type_counts = {
            content_type: len(memories)
            for content_type, memories in self.memories_by_content_type.items()
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
            "active_topics": list(self.active_topics)
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
                    "memory_class": memory.__class__.__name__,  # Save the actual class type
                    "content_type": memory.content_type.value if hasattr(memory.content_type, 'value') else str(memory.content_type),
                    "id": memory.id,
                    "confidence": memory.confidence,
                    "priority": memory.priority.name,
                    "timestamp": memory.timestamp.isoformat(),
                    "expiry": memory.expiry.isoformat() if memory.expiry else None,
                    "pinned": memory.pinned,
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
        # ObservationMemoryBlock removed - observations are now ephemeral
        # Removed MessageMemoryBlock handling - messages are now FileMemoryBlock
        # Add other types as needed
        
        return fields
    
    def restore_from_snapshot(self, snapshot: Dict[str, Any], knowledge_manager=None) -> bool:
        """Restore memory state from a snapshot.
        
        Args:
            snapshot: Snapshot data to restore from
            knowledge_manager: Optional knowledge manager to reload ROM
            
        Returns:
            True if successfully restored
        """
        try:
            # Clear current memory - MUST clear both to stay in sync!
            self.symbolic_memory.clear()
            self.memory_index.clear()
            self.memories_by_content_type.clear()
            self.access_history.clear()
            
            # Restore configuration
            if 'max_tokens' in snapshot:
                self.max_tokens = snapshot['max_tokens']
            if 'current_task_id' in snapshot:
                self.current_task_id = snapshot['current_task_id']
            if 'active_topics' in snapshot:
                self.active_topics = set(snapshot['active_topics'])
            
            # Restore memories
            memories = snapshot.get('memories', [])
            logger.info(f"Restoring {len(memories)} memories from snapshot")
            
            
            for mem_data in memories:
                try:
                    # Get content type from data
                    content_type_str = mem_data.get('content_type', 'UNKNOWN')
                    content_type = ContentType[content_type_str] if hasattr(ContentType, content_type_str) else ContentType.UNKNOWN
                    
                    # Use memory_class if available, otherwise use content_type to determine class
                    memory_class = mem_data.get('memory_class')
                    
                    if memory_class == 'ObservationMemoryBlock' or content_type == ContentType.MINDSWARM_OBSERVATION:
                        memory = ObservationMemoryBlock(
                            observation_type=mem_data.get('observation_type', 'unknown'),
                            path=mem_data.get('path', ''),
                            message=mem_data.get('message', 'Restored observation'),
                            cycle_count=mem_data.get('cycle_count', 0),
                            content=mem_data.get('content'),
                            confidence=mem_data.get('confidence', 1.0),
                            priority=Priority[mem_data.get('priority', 'MEDIUM')],
                            pinned=mem_data.get('pinned', False)
                        )
                    else:
                        # Everything else is FileMemoryBlock
                        memory = FileMemoryBlock(
                            location=mem_data.get('location', 'unknown'),
                            start_line=mem_data.get('start_line'),
                            end_line=mem_data.get('end_line'),
                            digest=mem_data.get('digest'),
                            confidence=mem_data.get('confidence', 1.0),
                            priority=Priority[mem_data.get('priority', 'MEDIUM')],
                            metadata=mem_data.get('metadata', {}),
                            pinned=mem_data.get('pinned', False),
                            content_type=content_type
                        )
                    
                    # Restore timestamps
                    if 'timestamp' in mem_data:
                        memory.timestamp = datetime.fromisoformat(mem_data['timestamp'])
                    if 'expiry' in mem_data and mem_data['expiry']:
                        memory.expiry = datetime.fromisoformat(mem_data['expiry'])
                    
                    # Add to memory
                    self.add_memory(memory)
                    
                except Exception as e:
                    logger.warning(f"Failed to restore memory: {e}")
                    continue
            
            
            # Always reload ROM to ensure it's present
            if knowledge_manager:
                knowledge_manager.load_rom_into_memory(self)
            
            logger.info("Memory successfully restored from snapshot")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore memory from snapshot: {e}")
            return False
    
    def load_from_snapshot_file(self, memory_dir: Path, knowledge_manager=None) -> bool:
        """Load memory from a snapshot file.
        
        Args:
            memory_dir: Directory containing memory snapshot
            knowledge_manager: Optional knowledge manager to reload ROM
            
        Returns:
            True if successfully loaded, False otherwise
        """
        import json
        
        memory_snapshot_file = memory_dir / "memory_snapshot.json"
        
        if not memory_snapshot_file.exists():
            return False
            
        try:
            # Load snapshot
            with open(memory_snapshot_file, 'r') as f:
                snapshot = json.load(f)
                
            # Restore from snapshot
            return self.restore_from_snapshot(snapshot, knowledge_manager)
            
        except Exception as e:
            logger.error(f"Failed to load memory from snapshot file: {e}")
            return False