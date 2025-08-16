"""Tag-based filtering for memory context building.

This module provides whitelist/blacklist filtering based on metadata tags,
allowing different cognitive stages to see only relevant knowledge.

Note: Tag filtering is independent of memory pinning. Pinning ensures memories
stay in working memory (retention), while tag filtering controls what's visible
in each cognitive stage (relevance). These are separate concerns.
"""

import logging
from typing import List, Set, Optional, Dict, Any
from .memory_blocks import MemoryBlock

logger = logging.getLogger("Cyber.memory.tag_filter")


class TagFilter:
    """Filters memories based on metadata tags using blacklist approach.
    
    Only knowledge memories are filtered - all other memory types pass through.
    Knowledge is excluded only if it has tags in the blacklist.
    """
    
    def __init__(self, blacklist: Optional[Set[str]] = None):
        """Initialize tag filter.
        
        Args:
            blacklist: Set of tags to exclude from knowledge memories
        """
        self.blacklist = blacklist if blacklist is not None else set()
        
        # Always include critical system tags regardless of blacklist
        self.always_include = {"critical", "urgent", "system", "error"}
        
        logger.debug(f"Initialized TagFilter with blacklist: {self.blacklist}")
    
    def should_include(self, memory: MemoryBlock) -> bool:
        """Check if a memory should be included based on its tags.
        
        Only filters knowledge memories - all other types pass through.
        Knowledge is excluded only if it has blacklisted tags.
        
        Args:
            memory: Memory block to check
            
        Returns:
            True if memory should be included, False otherwise
        """
        from .memory_types import ContentType
        
        # Only filter knowledge memories - everything else passes through
        if not hasattr(memory, 'content_type') or memory.content_type != ContentType.MINDSWARM_KNOWLEDGE:
            return True
        
        # No blacklist means include all knowledge
        if not self.blacklist:
            return True
        
        # Get tags from metadata
        metadata = getattr(memory, 'metadata', {}) or {}
        tags = set()
        
        # Extract tags from various metadata fields
        if isinstance(metadata.get('tags'), list):
            tags.update(metadata['tags'])
        if metadata.get('category'):
            tags.add(metadata['category'])
        
        # Check for always-include tags (critical, urgent, system, error)
        if tags & self.always_include:
            return True
        
        # Exclude if any tag is in the blacklist
        if tags & self.blacklist:
            return False
        
        # Include by default (no blacklisted tags found)
        return True
    
    def filter_memories(self, memories: List[MemoryBlock]) -> List[MemoryBlock]:
        """Filter a list of memories based on tags.
        
        Args:
            memories: List of memory blocks to filter
            
        Returns:
            Filtered list of memory blocks
        """
        filtered = []
        excluded_count = 0
        
        for memory in memories:
            if self.should_include(memory):
                filtered.append(memory)
            else:
                excluded_count += 1
        
        if excluded_count > 0:
            logger.debug(f"Tag filter excluded {excluded_count}/{len(memories)} memories")
        
        return filtered
    
    def add_blacklist_tags(self, tags: Set[str]):
        """Add tags to the blacklist.
        
        Args:
            tags: Set of tags to add to blacklist
        """
        self.blacklist.update(tags)
        logger.debug(f"Added {len(tags)} tags to blacklist")
    
    def remove_blacklist_tags(self, tags: Set[str]):
        """Remove tags from the blacklist.
        
        Args:
            tags: Set of tags to remove from blacklist
        """
        self.blacklist -= tags
        logger.debug(f"Removed {len(tags)} tags from blacklist")
    
    def get_config(self) -> Dict[str, Any]:
        """Get current filter configuration.
        
        Returns:
            Dictionary with current blacklist configuration
        """
        return {
            "blacklist": list(self.blacklist),
            "always_include": list(self.always_include)
        }