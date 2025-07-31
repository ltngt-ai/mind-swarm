"""DSPy configuration for Mind-Swarm brain handlers.

This module handles the configuration of DSPy with various language model providers.
"""

import os
from typing import Dict, Any, Optional

import dspy
from litellm import completion

from mind_swarm.utils.logging import logger


class MindSwarmDSPyLM(dspy.LM):
    """Custom DSPy language model that uses our AI service configuration."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with Mind-Swarm AI service config.
        
        Args:
            config: Configuration containing provider, model, API keys, etc.
        """
        self.config = config
        self.provider = config.get("provider", "openai")
        self.model = config.get("model", "gpt-3.5-turbo")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 1000)
        
        # Debug: log the config we received
        logger.info(f"DSPy LM initializing with config: {config}")
        
        # Set up provider-specific configuration
        self._setup_provider()
        
        self.history = []
        self.kwargs = {}  # DSPy expects this attribute
        
    def _setup_provider(self):
        """Set up provider-specific configuration."""
        if self.provider == "openrouter":
            # OpenRouter uses OpenAI-compatible API
            self.api_base = "https://openrouter.ai/api/v1"
            self.api_key = self.config.get("api_key") or os.getenv("OPENROUTER_API_KEY")
            # Prepend openrouter/ to model name if not already
            if not self.model.startswith("openrouter/"):
                self.model = f"openrouter/{self.model}"
        
        elif self.provider == "openai":
            self.api_key = self.config.get("api_key") or os.getenv("OPENAI_API_KEY")
            self.api_base = self.config.get("base_url")
        
        elif self.provider == "anthropic":
            self.api_key = self.config.get("api_key") or os.getenv("ANTHROPIC_API_KEY")
        
        elif self.provider in ["openai_compatible", "local", "ollama"]:
            # Local or custom OpenAI-compatible endpoint
            self.api_key = self.config.get("api_key", "dummy")
            # Use base_url directly from config
            base_url = self.config.get("base_url", "http://localhost:1234")
            self.api_base = f"{base_url}/v1" if not base_url.endswith("/v1") else base_url
            logger.info(f"Configured local provider with base URL: {self.api_base}")
        
        else:
            # Default values
            self.api_key = self.config.get("api_key", "")
            self.api_base = None
    
    def basic_request(self, prompt: str, **kwargs) -> str:
        """Make a basic request to the language model.
        
        Args:
            prompt: The prompt to send
            **kwargs: Additional parameters
            
        Returns:
            The model's response
        """
        # Override temperature and max_tokens if provided
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        
        try:
            # Use litellm for unified interface
            # For local/ollama, need to prefix the model
            if self.provider in ["local", "ollama"]:
                model_str = f"openai/{self.model}"  # Use OpenAI format for local servers
            else:
                model_str = self.model
            
            # PROOF: Log LLM request details
            logger.info(f"LM REQUEST: model={model_str}, api_base={getattr(self, 'api_base', 'None')}, temp={temperature}")
            logger.info(f"LM REQUEST PROMPT: {prompt}")
            
            response = completion(
                model=model_str,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=self.api_key,
                api_base=self.api_base if hasattr(self, 'api_base') else None,
            )
            
            response_text = response.choices[0].message.content
            logger.info(f"LM RESPONSE: {response_text}")
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            raise
    
    def __call__(self, messages: list[dict], **kwargs) -> list[dict]:
        """Make the LM callable with DSPy's expected interface.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional parameters
            
        Returns:
            List with single dict containing 'text' key (DSPy format)
        """
        # Convert messages to a single prompt
        prompt = ""
        for msg in messages:
            if msg["role"] == "system":
                prompt += f"System: {msg['content']}\n\n"
            elif msg["role"] == "user":
                prompt += f"User: {msg['content']}\n\n"
        
        # Get response
        response_text = self.basic_request(prompt, **kwargs)
        
        # Return in DSPy expected format - a list with single dict containing 'text'
        return [{"text": response_text}]


def configure_dspy_for_mind_swarm(config: Dict[str, Any]) -> dspy.LM:
    """Configure DSPy with a Mind-Swarm language model.
    
    Args:
        config: AI service configuration
        
    Returns:
        Configured language model
    """
    lm = MindSwarmDSPyLM(config)
    dspy.settings.configure(lm=lm)
    return lm


def get_dspy_lm_from_preset(preset_name: str) -> Optional[dspy.LM]:
    """Get a configured DSPy LM from a Mind-Swarm preset.
    
    Args:
        preset_name: Name of the AI preset
        
    Returns:
        Configured DSPy LM or None if preset not found
    """
    from mind_swarm.ai.presets import preset_manager
    
    preset_config = preset_manager.get_config(preset_name)
    if not preset_config:
        logger.error(f"Preset {preset_name} not found")
        return None
    
    return configure_dspy_for_mind_swarm(preset_config)