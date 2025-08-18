"""Memory persistence module for saving and restoring Cyber memory snapshots.

This module handles all memory snapshot operations, separating persistence
logic from the core cognitive loop.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from .memory import (
    WorkingMemoryManager, Priority, ContentType,
    FileMemoryBlock
)

logger = logging.getLogger("Cyber.memory_persistence")


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
                # Get content type from data
                content_type_str = mem_data.get('content_type', 'UNKNOWN')
                content_type = ContentType[content_type_str] if hasattr(ContentType, content_type_str) else ContentType.UNKNOWN
                
                # Reconstruct based on content type
                # ObservationMemoryBlock removed - observations are now ephemeral
                # ObservationMemoryBlock and MINDSWARM_OBSERVATION removed - skip any old ones
                if mem_data.get('memory_class') == 'ObservationMemoryBlock':
                    logger.debug(f"Skipping obsolete ObservationMemoryBlock from persistence: {mem_data.get('id')}")
                    continue
                else:
                    # Default to FileMemoryBlock for everything else
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
                
                # Add to memory manager
                memory_manager.add_memory(memory)
                
            except Exception as e:
                logger.warning(f"Failed to restore memory: {e}")
                continue
        
        return cycle_count