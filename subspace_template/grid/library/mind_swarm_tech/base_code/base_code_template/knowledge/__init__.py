"""Knowledge management module for the cognitive loop.

This package provides knowledge management functionality including
ROM (Read-Only Memory) loading, knowledge organization, and
semantic knowledge queries.
"""

from .knowledge_manager import KnowledgeManager
from .rom_loader import ROMLoader

__all__ = [
    'KnowledgeManager',
    'ROMLoader'
]