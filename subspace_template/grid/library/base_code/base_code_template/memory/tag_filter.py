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
    """Filters memories based on metadata tags using whitelist/blacklist approach."""
    
    # Default tag configurations for each stage
    STAGE_CONFIGS = {
        "observation": {
            "whitelist": {
                "observation", "perception", "environment", "messages", 
                "identity", "context", "memory_management", "self_awareness"
            },
            "blacklist": {
                "action_guide", "action_implementation", "execution"
            }
        },
        "decision": {
            "whitelist": {
                "decision_making", "planning", "action_guide", "strategy",
                "identity", "context", "goals", "priorities"
            },
            "blacklist": {
                "action_implementation", "low_level_details"
            }
        },
        "execution": {
            "whitelist": {
                "action_guide", "action_implementation", "execution",
                "tools", "procedures", "identity", "context"
            },
            "blacklist": {
                "observation_details", "raw_perception"
            }
        },
        "general": {
            # Default configuration - no filtering
            "whitelist": set(),  # Empty means allow all
            "blacklist": set()   # Empty means block none
        }
    }
    
    def __init__(self, stage: Optional[str] = None, 
                 custom_whitelist: Optional[Set[str]] = None,
                 custom_blacklist: Optional[Set[str]] = None):
        """Initialize tag filter.
        
        Args:
            stage: Cognitive stage name (observation, decision, execution, general)
            custom_whitelist: Custom tags to allow (overrides stage defaults)
            custom_blacklist: Custom tags to block (overrides stage defaults)
        """
        self.stage = stage or "general"
        
        # Load stage-specific configuration
        config = self.STAGE_CONFIGS.get(self.stage, self.STAGE_CONFIGS["general"])
        
        # Use custom or default configurations
        self.whitelist = custom_whitelist if custom_whitelist is not None else config["whitelist"].copy()
        self.blacklist = custom_blacklist if custom_blacklist is not None else config["blacklist"].copy()
        
        # Always include critical system tags
        self.always_include = {"critical", "urgent", "system", "error"}
        
        logger.debug(f"Initialized TagFilter for stage '{self.stage}' - "
                    f"whitelist: {len(self.whitelist)} tags, blacklist: {len(self.blacklist)} tags")
    
    def should_include(self, memory: MemoryBlock) -> bool:
        """Check if a memory should be included based on its tags.
        
        Args:
            memory: Memory block to check
            
        Returns:
            True if memory should be included, False otherwise
        """
        # Note: We don't check pinned status here - that's a memory management concern
        # Tag filtering is about relevance/visibility, not memory retention
        
        # Get tags from metadata
        metadata = getattr(memory, 'metadata', {}) or {}
        tags = set()
        
        # Extract tags from various metadata fields
        if isinstance(metadata.get('tags'), list):
            tags.update(metadata['tags'])
        if metadata.get('category'):
            tags.add(metadata['category'])
        if metadata.get('file_type'):
            tags.add(metadata['file_type'])
        
        # Add memory type as implicit tag
        if hasattr(memory, 'type'):
            tags.add(memory.type.value)
        
        # Check for always-include tags
        if tags & self.always_include:
            return True
        
        # Apply blacklist first (explicit exclusions)
        if self.blacklist and tags & self.blacklist:
            return False
        
        # Apply whitelist (if empty, allow all)
        if self.whitelist:
            return bool(tags & self.whitelist)
        
        # If no whitelist specified, include by default
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
    
    def add_whitelist_tags(self, tags: Set[str]):
        """Add tags to the whitelist.
        
        Args:
            tags: Set of tags to add to whitelist
        """
        self.whitelist.update(tags)
        logger.debug(f"Added {len(tags)} tags to whitelist")
    
    def add_blacklist_tags(self, tags: Set[str]):
        """Add tags to the blacklist.
        
        Args:
            tags: Set of tags to add to blacklist
        """
        self.blacklist.update(tags)
        logger.debug(f"Added {len(tags)} tags to blacklist")
    
    def remove_whitelist_tags(self, tags: Set[str]):
        """Remove tags from the whitelist.
        
        Args:
            tags: Set of tags to remove from whitelist
        """
        self.whitelist -= tags
        logger.debug(f"Removed {len(tags)} tags from whitelist")
    
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
            Dictionary with current whitelist and blacklist
        """
        return {
            "stage": self.stage,
            "whitelist": list(self.whitelist),
            "blacklist": list(self.blacklist),
            "always_include": list(self.always_include)
        }
    
    @classmethod
    def for_observation_stage(cls) -> 'TagFilter':
        """Create a filter optimized for the observation stage."""
        return cls(stage="observation")
    
    @classmethod
    def for_decision_stage(cls) -> 'TagFilter':
        """Create a filter optimized for the decision stage."""
        return cls(stage="decision")
    
    @classmethod
    def for_execution_stage(cls) -> 'TagFilter':
        """Create a filter optimized for the execution stage."""
        return cls(stage="execution")