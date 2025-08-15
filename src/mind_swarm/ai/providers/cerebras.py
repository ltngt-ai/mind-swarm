"""Cerebras AI Service implementation.

Cerebras provides extremely fast inference with their custom hardware.
This provider uses the OpenAI-compatible API endpoint at https://api.cerebras.ai/v1.
"""

from typing import Optional

from mind_swarm.ai.config import AIExecutionConfig
from mind_swarm.ai.providers.openai_compatible import OpenAICompatibleService
from mind_swarm.utils.logging import logger


class CerebrasService(OpenAICompatibleService):
    """Cerebras AI API wrapper using OpenAI-compatible interface.
    
    Cerebras provides blazing fast inference optimized for their hardware.
    API documentation: https://inference-docs.cerebras.ai/
    """
    
    def __init__(self, config: AIExecutionConfig):
        """Initialize Cerebras service.
        
        Args:
            config: AI execution configuration with Cerebras API key
        """
        # Cerebras uses a fixed endpoint
        api_url = "https://api.cerebras.ai/v1"
        
        # Initialize with Cerebras-specific settings
        super().__init__(config, api_url=api_url)
        
        # Validate API key
        if not config.api_key:
            raise ValueError(
                "Cerebras API key is required. "
                "Set CEREBRAS_API_KEY environment variable or provide in config."
            )
        
        logger.info(f"Initialized Cerebras service with model: {config.model_id}")