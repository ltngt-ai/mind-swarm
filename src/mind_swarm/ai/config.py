"""AI configuration for Mind-Swarm.

This module provides configuration classes for AI providers and execution.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class BaseAIParams:
    """Shared AI parameters used across all configurations.
    
    Contains common parameters for model identification, provider settings,
    and generation parameters.
    """
    
    model_id: str  # Model identifier (e.g., "llama3.2:3b", "gpt-4")
    provider: str = "openrouter"  # AI service provider
    temperature: float = 0.7  # Generation temperature (0.0-2.0)
    max_tokens: Optional[int] = None  # Maximum tokens to generate
    
    def __post_init__(self) -> None:
        """Validate parameters after initialization."""
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError(
                f"temperature must be between 0.0 and 2.0, got {self.temperature}"
            )
        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {self.max_tokens}")
        if not self.model_id.strip():
            raise ValueError("model_id cannot be empty")
        if not self.provider.strip():
            raise ValueError("provider cannot be empty")


@dataclass
class AIExecutionConfig(BaseAIParams):
    """Configuration for AI execution (loops, providers).
    
    Extends BaseAIParams with execution-specific settings like API credentials
    and provider settings.
    """
    
    api_key: str = ""  # Will be validated in __post_init__
    provider_settings: Optional[Dict[str, Any]] = None
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        super().__post_init__()
        
        if self.provider != "ollama" and not self.api_key.strip():
            raise ValueError(f"api_key cannot be empty for provider {self.provider}")
        
        if self.provider_settings is None:
            self.provider_settings = {}
    
    def __repr__(self) -> str:
        return f"AIExecutionConfig(provider='{self.provider}', model_id='{self.model_id}', ...)"


@dataclass 
class LocalModelConfig(AIExecutionConfig):
    """Configuration for local models like Ollama."""
    
    api_key: str = "not-needed"  # Local models don't need API keys
    host: str = "http://localhost:11434"  # Ollama default host
    
    def __post_init__(self) -> None:
        """Set provider to ollama and validate."""
        self.provider = "ollama"
        super().__post_init__()


@dataclass
class PremiumModelConfig(AIExecutionConfig):
    """Configuration for premium models via OpenRouter."""
    
    site_url: str = "http://mind-swarm:8000"
    app_name: str = "Mind-Swarm"
    
    def __post_init__(self) -> None:
        """Ensure we have required settings for OpenRouter."""
        super().__post_init__()
        if not self.api_key:
            raise ValueError("Premium models require an API key")