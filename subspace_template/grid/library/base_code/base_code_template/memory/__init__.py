"""Memory system for agents - filesystem perception and context management."""

from .memory_types import Priority, MemoryType
from .memory_blocks import (
    MemoryBlock,
    FileMemoryBlock,
    StatusMemoryBlock,
    TaskMemoryBlock,
    MessageMemoryBlock,
    KnowledgeMemoryBlock,
    ContextMemoryBlock,
    ObservationMemoryBlock,
    CycleStateMemoryBlock,
    IdentityMemoryBlock,
)
from .memory_manager import WorkingMemoryManager
from .content_loader import ContentLoader
from .context_builder import ContextBuilder
from .memory_selector import MemorySelector
from .memory_system import MemorySystem

__all__ = [
    # Memory blocks
    "MemoryBlock",
    "Priority",
    "MemoryType",
    "FileMemoryBlock",
    "StatusMemoryBlock",
    "TaskMemoryBlock",
    "MessageMemoryBlock",
    "KnowledgeMemoryBlock",
    "ContextMemoryBlock",
    "ObservationMemoryBlock",
    "CycleStateMemoryBlock",
    "IdentityMemoryBlock",
    # Core components (individual - for backward compatibility)
    "WorkingMemoryManager",
    "ContentLoader",
    "ContextBuilder",
    "MemorySelector",
    # Unified facade (recommended)
    "MemorySystem",
]