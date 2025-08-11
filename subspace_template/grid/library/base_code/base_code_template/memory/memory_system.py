"""Unified memory system facade that coordinates all memory operations.

This facade provides a single interface to all memory functionality,
reducing complexity and improving coordination between components.
"""

import json
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime
from pathlib import Path
import logging

from .memory_types import Priority, MemoryType
from .memory_blocks import MemoryBlock
from .memory_manager import WorkingMemoryManager
from .memory_selector import MemorySelector, RelevanceScorer
from .context_builder import ContextBuilder
from .content_loader import ContentLoader

logger = logging.getLogger("Cyber.memory.system")


class MemorySystem:
    """Unified facade for all memory operations.
    
    This facade coordinates WorkingMemoryManager, MemorySelector, 
    ContextBuilder, and ContentLoader to provide a clean, single interface
    for all memory operations.
    """
    
    def __init__(self, 
                 filesystem_root: Path, 
                 max_tokens: int = 100000,
                 cache_ttl: int = 300):
        """Initialize the memory system.
        
        Args:
            filesystem_root: Root directory for content loading
            max_tokens: Maximum token budget for contexts
            cache_ttl: Content cache time-to-live in seconds
        """
        self.max_tokens = max_tokens
        self.filesystem_root = Path(filesystem_root)
        
        # Initialize components
        self._content_loader = ContentLoader(filesystem_root, cache_ttl)
        self._context_builder = ContextBuilder(self._content_loader)
        self._memory_manager = WorkingMemoryManager(max_tokens)
        self._memory_selector = MemorySelector(self._context_builder)
        
        # Performance tracking
        self._stats = {
            "memories_added": 0,
            "memories_removed": 0,
            "contexts_built": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        logger.info(f"Memory system initialized with {max_tokens} token budget")
    
    # === CORE MEMORY OPERATIONS ===
    
    def add_memory(self, memory: MemoryBlock) -> None:
        """Add a memory block to the system.
        
        Args:
            memory: Memory block to add
        """
        self._memory_manager.add_memory(memory)
        self._stats["memories_added"] += 1
        logger.debug(f"Added memory: {memory.id} (type={memory.type.value})")
    
    def remove_memory(self, memory_id: str) -> bool:
        """Remove a memory block from the system.
        
        Args:
            memory_id: ID of memory to remove
            
        Returns:
            True if memory was found and removed
        """
        if memory_id in self._memory_manager.memory_index:
            self._memory_manager.remove_memory(memory_id)
            self._stats["memories_removed"] += 1
            logger.debug(f"Removed memory: {memory_id}")
            return True
        return False
    
    def get_memory(self, memory_id: str) -> Optional[MemoryBlock]:
        """Get a specific memory block by ID.
        
        Args:
            memory_id: ID of memory to retrieve
            
        Returns:
            Memory block or None if not found
        """
        return self._memory_manager.access_memory(memory_id)
    
    def update_memory_confidence(self, memory_id: str, confidence: float) -> bool:
        """Update confidence score for a memory.
        
        Args:
            memory_id: ID of memory to update
            confidence: New confidence score (0.0-1.0)
            
        Returns:
            True if memory was found and updated
        """
        if memory_id in self._memory_manager.memory_index:
            self._memory_manager.update_confidence(memory_id, confidence)
            return True
        return False
    
    def touch_memory(self, memory_id: str, cycle_count: int) -> bool:
        """Update a memory's cycle_count to indicate it was modified.
        
        This is used when the underlying file is updated directly (e.g., via memory mapping)
        and the memory system needs to know the file has changed.
        
        Args:
            memory_id: ID of memory to touch
            cycle_count: Current cycle count when the file was updated
            
        Returns:
            True if memory was found and updated
        """
        if memory_id in self._memory_manager.memory_index:
            memory = self._memory_manager.memory_index[memory_id]
            if hasattr(memory, 'cycle_count'):
                memory.cycle_count = cycle_count
                logger.debug(f"Touched memory {memory_id} with cycle_count {cycle_count}")
                return True
        return False
    
    # === CONTEXT BUILDING ===
    
    def build_context(self,
                     max_tokens: Optional[int] = None,
                     current_task: Optional[str] = None,
                     selection_strategy: str = "balanced",
                     format_type: str = "json",
                     tag_filter: Optional['TagFilter'] = None,
                     exclude_types: Optional[List[MemoryType]] = None,
                     include_types: Optional[List[MemoryType]] = None) -> str:
        """Build LLM context from current memories.
        
        Args:
            max_tokens: Token budget (uses system default if None)
            current_task: Current task for relevance scoring
            selection_strategy: Selection strategy ("balanced", "recent", "relevant")
            format_type: Output format ("json", "structured", "narrative")
            tag_filter: Optional TagFilter to apply stage-specific filtering
            exclude_types: List of memory types to exclude (e.g., [MemoryType.OBSERVATION])
            include_types: List of memory types to include (if set, only these types are included)
            
        Returns:
            Formatted context string ready for LLM
        """
        token_budget = max_tokens or self.max_tokens
        
        # Get memories to consider
        memories_to_select = self._memory_manager.symbolic_memory
        
        # Debug: Log memory types in symbolic memory
        memory_type_counts = {}
        for m in memories_to_select:
            memory_type_counts[m.type.name] = memory_type_counts.get(m.type.name, 0) + 1
        logger.debug(f"Memory types available: {memory_type_counts}")
        
        # Filter by memory type if specified
        if include_types:
            memories_to_select = [m for m in memories_to_select if m.type in include_types]
            logger.debug(f"Include filter: {len(memories_to_select)} memories of types {include_types}")
        elif exclude_types:
            memories_to_select = [m for m in memories_to_select if m.type not in exclude_types]
            logger.debug(f"Exclude filter: kept {len(memories_to_select)} memories, excluded types {exclude_types}")
        
        # Apply tag filter if provided (only filters knowledge)
        if tag_filter:
            memories_to_select = tag_filter.filter_memories(memories_to_select)
            logger.debug(f"Tag filter reduced memories from {len(self._memory_manager.symbolic_memory)} to {len(memories_to_select)}")
        
        # Select memories
        selected_memories = self._memory_selector.select_memories(
            symbolic_memory=memories_to_select,
            max_tokens=token_budget,
            current_task=current_task,
            selection_strategy=selection_strategy
        )
        
        # Update access patterns for future relevance scoring
        self._memory_selector.update_access_patterns(selected_memories)
        
        # Build context
        context = self._context_builder.build_context(selected_memories, format_type)
        
        self._stats["contexts_built"] += 1
        logger.debug(f"Built context with {len(selected_memories)} memories, "
                    f"~{len(context)//4} tokens (budget: {token_budget})")
        
        return context
    
    def build_context_with_specific_memories(self, 
                                           memory_ids: List[str],
                                           format_type: str = "json") -> str:
        """Build context from specific memory IDs.
        
        Args:
            memory_ids: List of memory IDs to include
            format_type: Output format
            
        Returns:
            Formatted context string
        """
        memories = []
        for memory_id in memory_ids:
            memory = self.get_memory(memory_id)
            if memory:
                memories.append(memory)
            else:
                logger.warning(f"Memory not found: {memory_id}")
        
        context = self._context_builder.build_context(memories, format_type)
        self._stats["contexts_built"] += 1
        
        return context
    
    def estimate_context_tokens(self, memory_ids: Optional[List[str]] = None) -> int:
        """Estimate token count for memories.
        
        Args:
            memory_ids: Specific memories to estimate (all if None)
            
        Returns:
            Estimated token count
        """
        if memory_ids:
            memories = [self.get_memory(mid) for mid in memory_ids if self.get_memory(mid)]
        else:
            memories = self._memory_manager.symbolic_memory
            
        return sum(self._context_builder.estimate_tokens(m) for m in memories)
    
    # === MEMORY QUERIES ===
    
    def get_memories_by_type(self, memory_type: MemoryType) -> List[MemoryBlock]:
        """Get all memories of a specific type.
        
        Args:
            memory_type: Type of memories to retrieve
            
        Returns:
            List of memory blocks of the specified type
        """
        return self._memory_manager.get_memories_by_type(memory_type)
    
    def get_recent_memories(self, seconds: int = 300) -> List[MemoryBlock]:
        """Get memories created in the last N seconds.
        
        Args:
            seconds: Time window in seconds
            
        Returns:
            List of recent memory blocks
        """
        return self._memory_manager.get_recent_memories(seconds)
    
    def get_unread_messages(self) -> List[MemoryBlock]:
        """Get all unread message memories.
        
        Returns:
            List of unread message memory blocks
        """
        return self._memory_manager.get_unread_messages()
    
    def get_high_priority_memories(self) -> List[MemoryBlock]:
        """Get all high and critical priority memories.
        
        Returns:
            List of high/critical priority memories
        """
        return [m for m in self._memory_manager.symbolic_memory 
                if m.priority in (Priority.HIGH, Priority.CRITICAL)]
    
    def find_memories_by_keywords(self, keywords: List[str]) -> List[Tuple[MemoryBlock, float]]:
        """Find memories containing specific keywords with relevance scores.
        
        Args:
            keywords: List of keywords to search for
            
        Returns:
            List of (memory, relevance_score) tuples sorted by relevance
        """
        # Update relevance scorer with keywords
        scorer = self._memory_selector.relevance_scorer
        scorer.task_keywords = set(kw.lower() for kw in keywords)
        
        # Score all memories
        scored_memories = []
        for memory in self._memory_manager.symbolic_memory:
            score = scorer.score_memory(memory)
            if score > 0.3:  # Only include moderately relevant memories
                scored_memories.append((memory, score))
        
        # Sort by relevance
        scored_memories.sort(key=lambda x: x[1], reverse=True)
        return scored_memories
    
    # === TASK AND CONTEXT MANAGEMENT ===
    
    def set_current_task(self, task_id: str, task_description: Optional[str] = None) -> None:
        """Set the current active task for relevance scoring.
        
        Args:
            task_id: Task identifier
            task_description: Optional task description for keyword extraction
        """
        self._memory_manager.set_current_task(task_id)
        
        if task_description:
            self._memory_selector.relevance_scorer.update_task_context(task_description)
        
        logger.debug(f"Set current task: {task_id}")
    
    def add_active_topic(self, topic: str) -> None:
        """Add a topic to active topics for relevance scoring.
        
        Args:
            topic: Topic to add to active set
        """
        self._memory_manager.add_active_topic(topic)
        self._memory_selector.relevance_scorer.active_topics.add(topic)
    
    def remove_active_topic(self, topic: str) -> None:
        """Remove a topic from active topics.
        
        Args:
            topic: Topic to remove from active set
        """
        self._memory_manager.remove_active_topic(topic)
        self._memory_selector.relevance_scorer.active_topics.discard(topic)
    
    def mark_message_read(self, message_id: str) -> bool:
        """Mark a message as read and lower its priority.
        
        Args:
            message_id: ID of message to mark as read
            
        Returns:
            True if message was found and marked
        """
        memory = self.get_memory(message_id)
        if memory:
            self._memory_manager.mark_message_read(message_id)
            return True
        return False
    
    # === PERSISTENCE ===
    
    def create_snapshot(self) -> Dict[str, Any]:
        """Create a snapshot of current memory state.
        
        Returns:
            Dictionary containing snapshot data
        """
        snapshot = self._memory_manager.create_snapshot()
        snapshot["memory_system_stats"] = self._stats.copy()
        return snapshot
    
    def restore_from_snapshot(self, snapshot: Dict[str, Any], knowledge_manager=None) -> bool:
        """Restore memory state from snapshot.
        
        Args:
            snapshot: Snapshot data to restore from
            knowledge_manager: Optional knowledge manager for ROM loading
            
        Returns:
            True if successfully restored
        """
        success = self._memory_manager.restore_from_snapshot(snapshot, knowledge_manager)
        
        if success and "memory_system_stats" in snapshot:
            self._stats.update(snapshot["memory_system_stats"])
        
        return success
    
    def load_from_snapshot_file(self, memory_dir: Path, knowledge_manager=None) -> bool:
        """Load memory from snapshot file.
        
        Args:
            memory_dir: Directory containing memory snapshot
            knowledge_manager: Optional knowledge manager for ROM loading
            
        Returns:
            True if successfully loaded
        """
        return self._memory_manager.load_from_snapshot_file(memory_dir, knowledge_manager)
    
    def save_snapshot_to_file(self, memory_dir: Path) -> bool:
        """Save current memory state to snapshot file.
        
        Args:
            memory_dir: Directory to save snapshot in
            
        Returns:
            True if successfully saved
        """
        try:
            memory_dir.mkdir(parents=True, exist_ok=True)
            snapshot = self.create_snapshot()
            
            memory_file = memory_dir / "memory_snapshot.json"
            with open(memory_file, 'w') as f:
                json.dump(snapshot, f, indent=2, default=str)
            
            logger.info(f"Memory snapshot saved to {memory_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save memory snapshot: {e}")
            return False
    
    # === MAINTENANCE ===
    
    def cleanup_expired(self) -> int:
        """Remove expired memories.
        
        Returns:
            Number of memories removed
        """
        count = self._memory_manager.cleanup_expired()
        if count > 0:
            logger.info(f"Cleaned up {count} expired memories")
        return count
    
    def cleanup_old_observations(self, max_age_seconds: int = 3600) -> int:
        """Remove old observation memories.
        
        Args:
            max_age_seconds: Maximum age for observations
            
        Returns:
            Number of observations removed
        """
        count = self._memory_manager.cleanup_old_observations(max_age_seconds)
        if count > 0:
            logger.info(f"Cleaned up {count} old observations")
        return count
    
    def cleanup_cache(self) -> int:
        """Clean up expired cache entries.
        
        Returns:
            Number of cache entries removed
        """
        count = self._content_loader.cache.cleanup_expired()
        if count > 0:
            logger.debug(f"Cleaned up {count} expired cache entries")
        return count
    
    def clear_cache(self) -> None:
        """Clear all cached content."""
        self._content_loader.cache.clear()
        logger.debug("Memory system cache cleared")
    
    # === STATISTICS AND MONITORING ===
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get comprehensive memory statistics.
        
        Returns:
            Dictionary with memory statistics
        """
        base_stats = self._memory_manager.get_memory_stats()
        
        return {
            **base_stats,
            "cache_size": len(self._content_loader.cache.cache),
            "system_stats": self._stats.copy(),
            "max_tokens": self.max_tokens,
            "filesystem_root": str(self.filesystem_root)
        }
    
    def get_token_usage_breakdown(self) -> Dict[str, int]:
        """Get token usage by memory type.
        
        Returns:
            Dictionary mapping memory types to estimated token counts
        """
        breakdown = {}
        
        for mem_type in MemoryType:
            memories = self.get_memories_by_type(mem_type)
            if memories:
                tokens = sum(self._context_builder.estimate_tokens(m) for m in memories)
                breakdown[mem_type.value] = tokens
        
        return breakdown
    
    # === INTERNAL ACCESS (for advanced usage) ===
    
    @property
    def memory_manager(self) -> WorkingMemoryManager:
        """Access underlying memory manager (use carefully)."""
        return self._memory_manager
    
    @property
    def symbolic_memory(self) -> List[MemoryBlock]:
        """Access symbolic memory directly (for backward compatibility)."""
        return self._memory_manager.symbolic_memory
    
    @property
    def content_loader(self) -> ContentLoader:
        """Access underlying content loader (use carefully)."""
        return self._content_loader
    
    @property 
    def context_builder(self) -> ContextBuilder:
        """Access underlying context builder (use carefully)."""
        return self._context_builder
    
    @property
    def memory_selector(self) -> MemorySelector:
        """Access underlying memory selector (use carefully)."""
        return self._memory_selector