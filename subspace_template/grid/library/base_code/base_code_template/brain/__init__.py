"""Brain Interface Module - AI thinking operations abstraction.

This module provides clean abstractions for AI thinking operations,
separating brain communication logic from cognitive orchestration.
"""

from .brain_interface import BrainInterface, MessageProcessor

__all__ = [
    "BrainInterface",
    "MessageProcessor"
]