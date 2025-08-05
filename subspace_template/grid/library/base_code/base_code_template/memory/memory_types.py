"""Shared memory type definitions to avoid circular imports.

This module contains the core enums used throughout the memory system.
"""

from enum import Enum


class Priority(Enum):
    """Memory priority levels for selection algorithm."""
    CRITICAL = 1  # Always included, never dropped
    HIGH = 2      # Included unless space critical
    MEDIUM = 3    # Included based on relevance
    LOW = 4       # Background info, often dropped


class MemoryType(Enum):
    """Types of memory blocks."""
    ROM = "rom"
    FILE = "file"
    STATUS = "status"
    TASK = "task"
    MESSAGE = "message"
    KNOWLEDGE = "knowledge"
    CONTEXT = "context"
    OBSERVATION = "observation"
    CYCLE_STATE = "cycle_state"
    IDENTITY = "identity"