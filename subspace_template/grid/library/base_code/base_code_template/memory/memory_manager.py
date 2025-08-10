"""Working Memory Manager - manages symbolic memory for Cybers.

This is the core memory management system that holds symbolic references
to filesystem content without loading the actual data until needed.
"""

from typing import List, Dict, Optional, Set, Any
from datetime import datetime, timedelta
from pathlib import Path
import logging

from .memory_blocks import (
    MemoryBlock, Priority, MemoryType,
    FileMemoryBlock, ObservationMemoryBlock,
    CycleStateMemoryBlock, KnowledgeMemoryBlock
)

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
    
    def cleanup_old_observations(self, max_age_seconds: int = 3600) -> int:
        """Remove old observation entries beyond max age (except pinned ones)."""
        cutoff = datetime.now() - timedelta(seconds=max_age_seconds)
        old_observations = [
            m for m in self.get_memories_by_type(MemoryType.OBSERVATION)
            if m.timestamp < cutoff and m.priority == Priority.LOW and not m.pinned
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
                    "type": memory.type.value,
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
        # Removed MessageMemoryBlock handling - messages are now FileMemoryBlock
        elif isinstance(memory, ObservationMemoryBlock):
            fields.update({
                "observation_type": memory.observation_type,
                "path": memory.path
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
    
    def restore_from_snapshot(self, snapshot: Dict[str, Any], knowledge_manager=None) -> bool:
        """Restore memory state from a snapshot.
        
        Args:
            snapshot: Snapshot data to restore from
            knowledge_manager: Optional knowledge manager to reload ROM
            
        Returns:
            True if successfully restored
        """
        try:
            # Clear current memory
            self.symbolic_memory.clear()
            
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
            
            cycle_state_found = False
            
            for mem_data in memories:
                try:
                    memory_type = MemoryType(mem_data.get('type', 'UNKNOWN'))
                    
                    if memory_type == MemoryType.CYCLE_STATE:
                        # Restore cycle state
                        memory = CycleStateMemoryBlock(
                            cycle_state=mem_data.get('cycle_state', 'perceive'),
                            cycle_count=mem_data.get('cycle_count', 0),
                            current_observation=mem_data.get('current_observation'),
                            current_orientation=mem_data.get('current_orientation'),
                            current_actions=mem_data.get('current_actions'),
                            confidence=mem_data.get('confidence', 1.0),
                            priority=Priority[mem_data.get('priority', 'CRITICAL')]
                        )
                        cycle_state_found = True
                        
                    elif memory_type == MemoryType.FILE:
                        memory = FileMemoryBlock(
                            location=mem_data['location'],
                            start_line=mem_data.get('start_line'),
                            end_line=mem_data.get('end_line'),
                            digest=mem_data.get('digest'),
                            confidence=mem_data.get('confidence', 1.0),
                            priority=Priority[mem_data.get('priority', 'MEDIUM')]
                        )
                        
                    # Skip MESSAGE type - messages are now FileMemoryBlock
                    elif memory_type == MemoryType.MESSAGE:
                        logger.debug("Skipping MESSAGE type - messages are now FileMemoryBlock")
                        continue
                        
                    elif memory_type == MemoryType.OBSERVATION:
                        memory = ObservationMemoryBlock(
                            observation_type=mem_data['observation_type'],
                            path=mem_data.get('path', ''),
                            message=mem_data.get('message', mem_data.get('description', 'Restored observation')),
                            cycle_count=mem_data.get('cycle_count', 0),
                            content=mem_data.get('content'),
                            confidence=mem_data.get('confidence', 1.0),
                            priority=Priority[mem_data.get('priority', 'MEDIUM')]
                        )
                        
                    elif memory_type == MemoryType.KNOWLEDGE:
                        memory = KnowledgeMemoryBlock(
                            topic=mem_data.get('topic', 'general'),
                            location=mem_data.get('location', 'restored'),
                            subtopic=mem_data.get('subtopic', ''),
                            relevance_score=mem_data.get('relevance_score', 1.0),
                            confidence=mem_data.get('confidence', 1.0),
                            priority=Priority[mem_data.get('priority', 'MEDIUM')],
                            metadata=mem_data.get('metadata', {})
                        )
                        
                    else:
                        # Skip unknown types
                        logger.warning(f"Unknown memory type: {memory_type}")
                        continue
                    
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
            
            # If no cycle state found, this will be handled by the cognitive loop
            if not cycle_state_found:
                logger.info("No cycle state found in snapshot")
            
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