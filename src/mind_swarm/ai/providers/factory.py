"""Factory for creating AI service providers."""

from typing import Dict, Type

from mind_swarm.ai.config import AIExecutionConfig
from mind_swarm.ai.providers.base import AIService
from mind_swarm.ai.providers.openai_compatible import OpenAICompatibleService
from mind_swarm.ai.providers.openrouter import OpenRouterAIService
from mind_swarm.utils.logging import logger


# Registry of available providers
PROVIDERS: Dict[str, Type[AIService]] = {
    "openai": OpenAICompatibleService,
    "ollama": OpenAICompatibleService,
    "local": OpenAICompatibleService,
    "openrouter": OpenRouterAIService,
}


def create_ai_service(config: AIExecutionConfig) -> AIService:
    """Create an AI service instance based on configuration.
    
    Args:
        config: AI execution configuration
        
    Returns:
        AI service instance
        
    Raises:
        ValueError: If provider is not supported
    """
    provider = config.provider.lower()
    
    if provider not in PROVIDERS:
        raise ValueError(
            f"Unknown provider: {provider}. "
            f"Available providers: {list(PROVIDERS.keys())}"
        )
    
    provider_class = PROVIDERS[provider]
    logger.info(f"Creating AI service for provider: {provider}")
    
    return provider_class(config)


def register_provider(name: str, provider_class: Type[AIService]) -> None:
    """Register a custom AI provider.
    
    Args:
        name: Provider name
        provider_class: Provider class (must inherit from AIService)
    """
    if not issubclass(provider_class, AIService):
        raise ValueError(f"{provider_class} must inherit from AIService")
    
    PROVIDERS[name.lower()] = provider_class
    logger.info(f"Registered AI provider: {name}")