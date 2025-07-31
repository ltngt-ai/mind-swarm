"""Base classes for AI service providers."""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional

from mind_swarm.ai.config import AIExecutionConfig


class AIStreamChunk:
    """Represents a chunk of streaming AI response."""
    
    def __init__(
        self,
        delta_content: Optional[str] = None,
        delta_tool_call_part: Optional[Any] = None,
        finish_reason: Optional[str] = None,
        usage: Optional[Dict[str, int]] = None,
    ):
        self.delta_content = delta_content
        self.delta_tool_call_part = delta_tool_call_part
        self.finish_reason = finish_reason
        self.usage = usage  # Token usage data
    
    def __repr__(self) -> str:
        parts = []
        if self.delta_content:
            parts.append(f"content={self.delta_content!r}")
        if self.delta_tool_call_part:
            parts.append("tool_call=...")
        if self.finish_reason:
            parts.append(f"finish={self.finish_reason!r}")
        return f"AIStreamChunk({', '.join(parts)})"


class AIService(ABC):
    """Base class for AI service providers.
    
    Each provider should accept an AIExecutionConfig in their constructor
    and implement the required methods.
    """
    
    def __init__(self, config: AIExecutionConfig):
        """Initialize with execution configuration.
        
        Args:
            config: AI execution configuration containing model, credentials, etc.
        """
        self.config = config
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Generate a response from a prompt.
        
        Args:
            prompt: User prompt
            system: System prompt (optional)
            **kwargs: Additional parameters
            
        Returns:
            Generated response text
        """
        pass
    
    @abstractmethod
    async def stream_generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[AIStreamChunk, None]:
        """Stream a response from a prompt.
        
        Args:
            prompt: User prompt
            system: System prompt (optional)
            **kwargs: Additional parameters
            
        Yields:
            AIStreamChunk objects
        """
        pass
    
    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Chat completion with optional tools.
        
        Args:
            messages: List of chat messages
            tools: Optional tool definitions
            **kwargs: Additional parameters
            
        Returns:
            Completion response including message and usage
        """
        pass
    
    @abstractmethod
    async def stream_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[AIStreamChunk, None]:
        """Stream chat completion with tools support.
        
        Args:
            messages: List of chat messages  
            tools: Optional tool definitions
            **kwargs: Additional parameters
            
        Yields:
            AIStreamChunk objects
        """
        pass