"""Shared memory type definitions to avoid circular imports.

This module contains the core enums used throughout the memory system.
"""

from enum import Enum


class Priority(Enum):
    """Memory priority levels for selection algorithm.
    
    Lower numeric values = higher priority.
    FOUNDATIONAL and SYSTEM are special autonomous priorities.
    """
    FOUNDATIONAL = 0  # ROM knowledge, absolute foundation
    SYSTEM = 1        # System-controlled memories (pipelines, dynamic context)
    CRITICAL = 2      # User-critical, always included
    HIGH = 3          # Important, included unless space critical  
    MEDIUM = 4        # Normal priority, included based on relevance
    LOW = 5           # Background info, often dropped


class MemoryType(Enum):
    """Types of memory blocks."""
    FILE = "memory"
    KNOWLEDGE = "knowledge"
    OBSERVATION = "observation"
    SYSTEM = "system"  # System-controlled memories (pipelines, dynamic context)