"""Memory persistence module for saving and restoring agent memory snapshots.

This module handles all memory snapshot operations, separating persistence
logic from the core cognitive loop.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from .memory import (
    WorkingMemoryManager, Priority, MemoryType,
    FileMemoryBlock, MessageMemoryBlock, ObservationMemoryBlock,
    CycleStateMemoryBlock, KnowledgeMemoryBlock
)

logger = logging.getLogger("agent.memory_persistence")


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime objects."""
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


class MemoryPersistence:
    """Handles saving and restoring memory snapshots to disk."""
    
    def __init__(self, memory_dir: Path):
        """Initialize memory persistence.
        
        Args:
            memory_dir: Directory to store memory snapshots
        """
        self.memory_dir = memory_dir
        self.memory_dir.mkdir(exist_ok=True)
        
    def save_snapshot(self, memory_manager: WorkingMemoryManager, cycle_count: int) -> bool:
        """Save current memory state to disk.
        
        Args:
            memory_manager: The working memory manager to snapshot
            cycle_count: Current cycle count for periodic backups
            
        Returns:
            True if successful, False otherwise
        """
        try:
            snapshot = memory_manager.create_snapshot()
            
            # Save to fixed filename for resume (atomic write to prevent corruption)
            memory_file = self.memory_dir / "memory_snapshot.json"
            temp_file = self.memory_dir / "memory_snapshot.tmp"
            
            # Write to temp file first
            with open(temp_file, 'w') as f:
                json.dump(snapshot, f, indent=2, cls=DateTimeEncoder)
            
            # Atomic rename (on POSIX systems, rename is atomic)
            temp_file.replace(memory_file)
            
            # Also save timestamped backup periodically
            if cycle_count % 100 == 0:
                backup_file = self.memory_dir / f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(backup_file, 'w') as f:
                    json.dump(snapshot, f, indent=2, cls=DateTimeEncoder)
                logger.debug(f"Saved memory backup to {backup_file.name}")
                
                # Clean old backups (keep last 5)
                backups = sorted(self.memory_dir.glob("snapshot_*.json"))
                if len(backups) > 5:
                    for old_backup in backups[:-5]:
                        old_backup.unlink()
                        
            return True
                    
        except Exception as e:
            logger.error(f"Error saving memory snapshot: {e}")
            return False
    
    def load_snapshot(self, memory_manager: WorkingMemoryManager) -> Optional[int]:
        """Load memory snapshot from disk.
        
        Args:
            memory_manager: The working memory manager to restore into
            
        Returns:
            The restored cycle count if successful, None otherwise
        """
        memory_snapshot_file = self.memory_dir / "memory_snapshot.json"
        
        if not memory_snapshot_file.exists():
            return None
            
        try:
            # Load existing memory snapshot
            with open(memory_snapshot_file, 'r') as f:
                snapshot = json.load(f)
                
            cycle_count = self._restore_from_snapshot(memory_manager, snapshot)
            return cycle_count
            
        except Exception as e:
            logger.error(f"Failed to load memory snapshot: {e}")
            return None
    
    def _restore_from_snapshot(self, memory_manager: WorkingMemoryManager, 
                              snapshot: Dict[str, Any]) -> int:
        """Restore memory from a snapshot.
        
        Args:
            memory_manager: The working memory manager to restore into
            snapshot: The snapshot data
            
        Returns:
            The restored cycle count
        """
        memories = snapshot.get('memories', [])
        logger.info(f"Restoring from snapshot with {len(memories)} memories")
        
        # Restore configuration from snapshot
        if 'max_tokens' in snapshot:
            memory_manager.max_tokens = snapshot['max_tokens']
        if 'current_task_id' in snapshot:
            memory_manager.current_task_id = snapshot['current_task_id']
        if 'active_topics' in snapshot:
            memory_manager.active_topics = set(snapshot['active_topics'])
        
        # Track cycle count from cycle state
        cycle_count = 0
        
        # Reconstruct memory blocks
        for mem_data in memories:
            try:
                memory_type = MemoryType(mem_data['type'])
                
                # Reconstruct based on type
                if memory_type == MemoryType.CYCLE_STATE:
                    # Special handling for cycle state
                    memory = CycleStateMemoryBlock(
                        cycle_state=mem_data['cycle_state'],
                        cycle_count=mem_data['cycle_count'],
                        current_observation=mem_data.get('current_observation'),
                        current_orientation=mem_data.get('current_orientation'),
                        current_actions=mem_data.get('current_actions'),
                        confidence=mem_data.get('confidence', 1.0),
                        priority=Priority[mem_data.get('priority', 'CRITICAL')]
                    )
                    # Update cycle count from saved state
                    cycle_count = memory.cycle_count
                    
                elif memory_type == MemoryType.FILE:
                    memory = FileMemoryBlock(
                        location=mem_data['location'],
                        start_line=mem_data.get('start_line'),
                        end_line=mem_data.get('end_line'),
                        digest=mem_data.get('digest'),
                        confidence=mem_data.get('confidence', 1.0),
                        priority=Priority[mem_data.get('priority', 'MEDIUM')]
                    )
                    
                elif memory_type == MemoryType.MESSAGE:
                    memory = MessageMemoryBlock(
                        from_agent=mem_data['from_agent'],
                        to_agent=mem_data['to_agent'],
                        subject=mem_data.get('subject', ''),
                        preview=mem_data.get('preview', ''),
                        full_path=mem_data['full_path'],
                        read=mem_data.get('read', False),
                        confidence=mem_data.get('confidence', 1.0),
                        priority=Priority[mem_data.get('priority', 'HIGH')]
                    )
                    
                elif memory_type == MemoryType.OBSERVATION:
                    memory = ObservationMemoryBlock(
                        observation_type=mem_data['observation_type'],
                        path=mem_data.get('path', ''),
                        description=mem_data['description'],
                        confidence=mem_data.get('confidence', 1.0),
                        priority=Priority[mem_data.get('priority', 'MEDIUM')]
                    )
                    
                elif memory_type == MemoryType.KNOWLEDGE:
                    memory = KnowledgeMemoryBlock(
                        topic=mem_data['topic'],
                        location=mem_data['location'],
                        subtopic=mem_data.get('subtopic', ''),
                        relevance_score=mem_data.get('relevance_score', 0.8),
                        confidence=mem_data.get('confidence', 1.0),
                        priority=Priority[mem_data.get('priority', 'MEDIUM')],
                        metadata=mem_data.get('metadata', {})
                    )
                    
                else:
                    # Skip other types for now
                    continue
                
                # Restore timestamps
                if 'timestamp' in mem_data:
                    memory.timestamp = datetime.fromisoformat(mem_data['timestamp'])
                if 'expiry' in mem_data and mem_data['expiry']:
                    memory.expiry = datetime.fromisoformat(mem_data['expiry'])
                
                # Add to memory manager
                memory_manager.add_memory(memory)
                
            except Exception as e:
                logger.warning(f"Failed to restore memory: {e}")
                continue
        
        return cycle_count