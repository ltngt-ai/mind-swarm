"""Memory selector with priority and relevance scoring.

Selects which memories to include in LLM context based on:
- Priority levels (CRITICAL always included)
- Relevance to current task
- Recency of information
- Token budget constraints
"""

from typing import List, Dict, Any, Set, Optional, Callable
from datetime import datetime, timedelta
import logging
import re

from .memory_types import Priority, MemoryType
from .memory_blocks import (
    MemoryBlock,
    FileMemoryBlock,
    ObservationMemoryBlock
)
from .context_builder import ContextBuilder

logger = logging.getLogger("Cyber.memory.selector")


class RelevanceScorer:
    """Calculates relevance scores for memories."""
    
    def __init__(self):
        """Initialize the relevance scorer."""
        self.task_keywords: Set[str] = set()
        self.recent_files: Set[str] = set()
        self.conversation_context: List[str] = []
        self.active_topics: Set[str] = set()
    
    def update_task_context(self, task: str):
        """Update task keywords from current task description."""
        # Extract keywords (simple tokenization)
        words = re.findall(r'\w+', task.lower())
        # Filter out common words
        common_words = {'the', 'a', 'an', 'is', 'are', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
        self.task_keywords = {w for w in words if w not in common_words and len(w) > 2}
        logger.debug(f"Task keywords: {self.task_keywords}")
    
    def add_recent_file(self, filepath: str):
        """Track recently accessed files."""
        self.recent_files.add(filepath)
        # Keep only last 10 files
        if len(self.recent_files) > 10:
            self.recent_files.pop()
    
    def score_memory(self, memory: MemoryBlock) -> float:
        """Calculate relevance score for a memory block.
        
        Returns:
            Score between 0.0 and 1.0
        """
        base_score = memory.confidence
        
        # Recency boost
        age = (datetime.now() - memory.timestamp).total_seconds()
        recency_factor = self._calculate_recency_factor(age, memory.type)
        
        # Type-specific scoring
        type_score = self._score_by_type(memory)
        
        # Keyword relevance
        keyword_score = self._calculate_keyword_relevance(memory)
        
        # Combine scores (weighted average)
        final_score = (
            base_score * 0.3 +
            recency_factor * 0.2 +
            type_score * 0.3 +
            keyword_score * 0.2
        )
        
        return min(max(final_score, 0.0), 1.0)
    
    def _calculate_recency_factor(self, age_seconds: float, mem_type: MemoryType) -> float:
        """Calculate recency factor based on age and type."""
        # Different decay rates for different types
        decay_rates = {
            MemoryType.OBSERVATION: 300,    # 5 minutes
            MemoryType.FILE: 3600,          # 1 hour
            MemoryType.KNOWLEDGE: 86400,    # 24 hours
        }
        
        decay_rate = decay_rates.get(mem_type, 3600)
        if decay_rate == float('inf'):
            return 1.0
        
        # Exponential decay
        return 0.5 ** (age_seconds / decay_rate)
    
    def _score_by_type(self, memory: MemoryBlock) -> float:
        """Score based on memory type and content."""
        if isinstance(memory, FileMemoryBlock):
            # Boost if file was recently accessed
            if memory.location in self.recent_files:
                return 0.9
            # Check if file is related to active topics
            for topic in self.active_topics:
                if topic.lower() in memory.location.lower():
                    return 0.7
            return 0.4
            
        # No special handling for messages - they're just files
        # The LLM can read the content and understand it's a message
            
        elif isinstance(memory, ObservationMemoryBlock):
            # Recent observations are important
            return 0.8
            
        elif isinstance(memory, FileMemoryBlock) and memory.type == MemoryType.KNOWLEDGE:
            # Knowledge memories use confidence as relevance
            return memory.confidence
            
        else:
            return 0.5
    
    def _calculate_keyword_relevance(self, memory: MemoryBlock) -> float:
        """Calculate relevance based on keyword overlap."""
        if not self.task_keywords:
            return 0.5  # Neutral if no keywords
        
        # Extract text to check
        text_to_check = []
        
        if hasattr(memory, 'description'):
            text_to_check.append(getattr(memory, 'description', ''))
        if hasattr(memory, 'subject'):
            text_to_check.append(getattr(memory, 'subject', ''))
        if hasattr(memory, 'topic'):
            text_to_check.append(getattr(memory, 'topic', ''))
        if hasattr(memory, 'location'):
            text_to_check.append(getattr(memory, 'location', ''))
        
        # Add metadata
        text_to_check.extend(str(v) for v in memory.metadata.values())
        
        # Combine and tokenize
        combined_text = ' '.join(text_to_check).lower()
        words = set(re.findall(r'\w+', combined_text))
        
        # Calculate overlap
        overlap = len(words & self.task_keywords)
        if not words:
            return 0.5
        
        return min(overlap / len(self.task_keywords), 1.0)


class MemorySelector:
    """Selects memories to include in context based on constraints."""
    
    def __init__(self, context_builder: ContextBuilder):
        """Initialize memory selector.
        
        Args:
            context_builder: Builder for estimating token counts
        """
        self.context_builder = context_builder
        self.relevance_scorer = RelevanceScorer()
    
    def select_memories(self, 
                       symbolic_memory: List[MemoryBlock],
                       max_tokens: int,
                       current_task: Optional[str] = None,
                       selection_strategy: str = "balanced") -> List[MemoryBlock]:
        """Select memories to include in context.
        
        Args:
            symbolic_memory: All available memories
            max_tokens: Maximum token budget
            current_task: Current task description for relevance
            selection_strategy: Strategy - "balanced", "recent", "relevant"
            
        Returns:
            Selected memory blocks within token budget
        """
        # Update relevance context
        if current_task:
            self.relevance_scorer.update_task_context(current_task)
        
        # Apply selection strategy
        if selection_strategy == "recent":
            return self._select_recent(symbolic_memory, max_tokens)
        elif selection_strategy == "relevant":
            return self._select_relevant(symbolic_memory, max_tokens)
        else:
            return self._select_balanced(symbolic_memory, max_tokens)
    
    def _select_balanced(self, memories: List[MemoryBlock], max_tokens: int) -> List[MemoryBlock]:
        """Balanced selection considering priority, relevance, and pinning."""
        logger.info(f"Selecting from {len(memories)} total memories")
        
        # First, separate pinned memories - they're always included
        pinned_memories = [m for m in memories if m.pinned]
        unpinned_memories = [m for m in memories if not m.pinned]
        
        # Calculate tokens for pinned memories
        pinned_tokens = sum(self.context_builder.estimate_tokens(m) for m in pinned_memories)
        
        if pinned_tokens > max_tokens:
            logger.warning(f"Pinned memories alone exceed token budget: {pinned_tokens} > {max_tokens}")
            # Still include all pinned memories
            return pinned_memories
        
        # Start with all pinned memories
        selected = pinned_memories.copy()
        used_tokens = pinned_tokens
        remaining_tokens = max_tokens - pinned_tokens
        
        # Debug log pinned memories
        pinned_ids = [m.id for m in pinned_memories]
        logger.info(f"Pinned memories ({len(pinned_ids)}): {pinned_ids}")
        
        # Log location files specifically
        location_memories = [m for m in pinned_memories if 'location' in m.id.lower()]
        if location_memories:
            logger.info(f"Location memories in pinned: {[m.id for m in location_memories]}")
        else:
            logger.warning("No location memories found in pinned memories!")
        
        # Separate unpinned by priority
        priority_groups = {
            Priority.CRITICAL: [],
            Priority.HIGH: [],
            Priority.MEDIUM: [],
            Priority.LOW: []
        }
        
        for memory in unpinned_memories:
            priority_groups[memory.priority].append(memory)
        
        # Calculate relevance scores for unpinned
        scored_memories = []
        for priority, group in priority_groups.items():
            for memory in group:
                score = self.relevance_scorer.score_memory(memory)
                scored_memories.append((memory, priority.value, score))
        
        # Sort by priority first, then relevance
        scored_memories.sort(key=lambda x: (x[1], -x[2]))
        
        # Reserve space for critical unpinned memories
        critical_tokens = sum(
            self.context_builder.estimate_tokens(m) 
            for m in priority_groups[Priority.CRITICAL]
        )
        
        if critical_tokens > remaining_tokens:
            logger.warning(f"Critical unpinned memories exceed remaining budget: {critical_tokens} > {remaining_tokens}")
        
        # Add unpinned memories in order
        for memory, _, score in scored_memories:
            tokens = self.context_builder.estimate_tokens(memory)
            
            # Always include critical unpinned
            if memory.priority == Priority.CRITICAL:
                selected.append(memory)
                used_tokens += tokens
                continue
            
            # For others, check budget with buffer
            buffer_factor = {
                Priority.HIGH: 0.8,      # 80% of budget
                Priority.MEDIUM: 0.9,    # 90% of budget
                Priority.LOW: 0.95       # 95% of budget
            }
            
            threshold = max_tokens * buffer_factor.get(memory.priority, 0.9)
            
            if used_tokens + tokens <= threshold:
                selected.append(memory)
                used_tokens += tokens
            elif memory.priority == Priority.HIGH and score > 0.8:
                # Try to squeeze in high priority, high relevance items
                if used_tokens + tokens <= max_tokens * 0.98:
                    selected.append(memory)
                    used_tokens += tokens
        
        logger.info(f"Selected {len(selected)} memories using {used_tokens} tokens (budget: {max_tokens})")
        return selected
    
    def _select_recent(self, memories: List[MemoryBlock], max_tokens: int) -> List[MemoryBlock]:
        """Select most recent memories first (with pinned always included)."""
        # First, separate pinned memories
        pinned_memories = [m for m in memories if m.pinned]
        unpinned_memories = [m for m in memories if not m.pinned]
        
        # Calculate tokens for pinned memories
        pinned_tokens = sum(self.context_builder.estimate_tokens(m) for m in pinned_memories)
        
        if pinned_tokens > max_tokens:
            logger.warning(f"Pinned memories alone exceed token budget: {pinned_tokens} > {max_tokens}")
            return pinned_memories
        
        # Start with all pinned memories
        selected = pinned_memories.copy()
        used_tokens = pinned_tokens
        
        # Sort unpinned by timestamp descending
        sorted_unpinned = sorted(unpinned_memories, key=lambda m: m.timestamp, reverse=True)
        
        # Always include critical unpinned first
        for memory in sorted_unpinned:
            if memory.priority == Priority.CRITICAL:
                tokens = self.context_builder.estimate_tokens(memory)
                selected.append(memory)
                used_tokens += tokens
        
        # Then add recent unpinned memories
        for memory in sorted_unpinned:
            if memory.priority == Priority.CRITICAL:
                continue  # Already added
                
            tokens = self.context_builder.estimate_tokens(memory)
            if used_tokens + tokens <= max_tokens * 0.95:
                selected.append(memory)
                used_tokens += tokens
        
        return selected
    
    def _select_relevant(self, memories: List[MemoryBlock], max_tokens: int) -> List[MemoryBlock]:
        """Select most relevant memories based on scoring (with pinned always included)."""
        # First, separate pinned memories
        pinned_memories = [m for m in memories if m.pinned]
        unpinned_memories = [m for m in memories if not m.pinned]
        
        # Calculate tokens for pinned memories
        pinned_tokens = sum(self.context_builder.estimate_tokens(m) for m in pinned_memories)
        
        if pinned_tokens > max_tokens:
            logger.warning(f"Pinned memories alone exceed token budget: {pinned_tokens} > {max_tokens}")
            return pinned_memories
        
        # Start with all pinned memories
        selected = pinned_memories.copy()
        used_tokens = pinned_tokens
        
        # Score unpinned memories
        scored = []
        for memory in unpinned_memories:
            score = self.relevance_scorer.score_memory(memory)
            scored.append((memory, score))
        
        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Add unpinned memories in relevance order, respecting priority minimums
        critical_added = False
        high_count = 0
        
        for memory, score in scored:
            tokens = self.context_builder.estimate_tokens(memory)
            
            # Always include critical unpinned
            if memory.priority == Priority.CRITICAL:
                selected.append(memory)
                used_tokens += tokens
                critical_added = True
            elif used_tokens + tokens <= max_tokens * 0.9:
                selected.append(memory)
                used_tokens += tokens
                if memory.priority == Priority.HIGH:
                    high_count += 1
        
        # Ensure we have some high priority items
        if high_count < 3:
            high_priority = [m for m, _ in scored if m.priority == Priority.HIGH and m not in selected]
            for memory in high_priority[:3 - high_count]:
                tokens = self.context_builder.estimate_tokens(memory)
                if used_tokens + tokens <= max_tokens:
                    selected.append(memory)
                    used_tokens += tokens
        
        return selected
    
    def update_access_patterns(self, selected_memories: List[MemoryBlock]):
        """Update scorer with access patterns from selected memories."""
        for memory in selected_memories:
            if isinstance(memory, FileMemoryBlock):
                self.relevance_scorer.add_recent_file(memory.location)