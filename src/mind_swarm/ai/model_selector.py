"""Model selection logic for choosing appropriate AI models for Cybers.

This module provides model selection using the priority-based model pool.
"""

from typing import Optional, Dict, Any

from mind_swarm.ai.model_pool import model_pool, ModelConfig
from mind_swarm.ai.config import AIExecutionConfig
from mind_swarm.utils.logging import logger


class ModelSelector:
    """Selects appropriate models for Cybers using the model pool."""
    
    def __init__(self):
        """Initialize the model selector."""
        self.pool = model_pool
        
    def select_model(self, paid_allowed: bool = False) -> Optional[ModelConfig]:
        """Select a model from the pool.
        
        Args:
            paid_allowed: Whether paid models can be selected
            
        Returns:
            Selected model or None if no suitable model found
        """
        model = self.pool.select_model(paid_allowed=paid_allowed)
        
        if not model:
            logger.warning("No models available for selection")
            
        return model
    
    def get_model_config(self, model: ModelConfig) -> AIExecutionConfig:
        """Convert ModelConfig to AIExecutionConfig.
        
        Args:
            model: Selected model
            
        Returns:
            AIExecutionConfig for the model
        """
        # Get API key based on provider
        import os
        api_key = None
        
        # Check if this is a local model (has a host in api_settings)
        is_local = model.api_settings and "host" in model.api_settings
        
        if is_local:
            # Local models don't need API keys
            api_key = "dummy"
        else:
            # Check for custom API key environment variable
            if model.api_settings and "api_key_env" in model.api_settings:
                # Use custom environment variable for API key
                custom_key_env = model.api_settings["api_key_env"]
                api_key = os.getenv(custom_key_env)
                if not api_key:
                    logger.warning(f"Custom API key env var {custom_key_env} not found for model {model.id}")
            else:
                # Use default based on provider
                if model.provider == "openrouter":
                    api_key = os.getenv("OPENROUTER_API_KEY")
                elif model.provider == "openai":
                    api_key = os.getenv("OPENAI_API_KEY")
                elif model.provider == "anthropic":
                    api_key = os.getenv("ANTHROPIC_API_KEY")
                elif model.provider == "cerebras":
                    api_key = os.getenv("CEREBRAS_API_KEY")
        
        return AIExecutionConfig(
            model_id=model.id,
            provider=model.provider,
            api_key=api_key or "",
            temperature=model.temperature,
            max_tokens=model.max_tokens,
            provider_settings=model.api_settings
        )