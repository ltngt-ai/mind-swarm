"""DSPy configuration for Mind-Swarm brain handlers.

This module handles the configuration of DSPy with various language model providers.
"""

import os
from typing import Dict, Any, Optional, List

import dspy

from mind_swarm.utils.logging import logger


class MindSwarmDSPyLM(dspy.LM):
    """Custom DSPy language model that uses our AI service configuration."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with Mind-Swarm AI service config.
        
        Args:
            config: Configuration containing provider, model, API keys, etc.
        """
        # Extract config values
        model = config.get("model", "gpt-3.5-turbo")
        provider = config.get("provider", "openai")
        cache = config.get("cache", False)
        
        # Initialize parent with model
        super().__init__(model=model, cache=cache)
        
        # Store our config
        self.config = config
        self.provider = provider
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 1000)
        
        # Debug: log the config we received
        logger.info(f"DSPy LM initializing with config: {config}")
        logger.info(f"DSPy LM parsed values - provider: {self.provider}, model: {self.model}, temp: {self.temperature}, max_tokens: {self.max_tokens}")
        
        # Set up provider-specific configuration
        self._setup_provider()
        
        # Track history for DSPy
        self.history = []
        self.kwargs = {}  # DSPy expects this attribute
        
    def _setup_provider(self):
        """Set up provider-specific configuration."""
        if self.provider == "openrouter":
            # OpenRouter uses OpenAI-compatible API
            self.api_base = "https://openrouter.ai/api/v1"
            self.api_key = self.config.get("api_key") or os.getenv("OPENROUTER_API_KEY")
            logger.debug(f"OpenRouter setup - api_key from config: {'yes' if self.config.get('api_key') else 'no'}, from env: {'yes' if os.getenv('OPENROUTER_API_KEY') else 'no'}")
            logger.debug(f"Final api_key: {self.api_key[:10] if self.api_key else 'None'}...")
        
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
    
    def _get_provider_settings(self) -> Dict[str, Any]:
        """Get provider-specific settings for AI service creation."""
        settings = {}
        
        if self.provider == "openrouter":
            # OpenRouter needs site_url and app_name
            settings["site_url"] = "http://mind-swarm:8000"
            settings["app_name"] = "Mind-Swarm"
        elif self.provider in ["local", "ollama", "openai_compatible"]:
            # Local providers need the host URL
            if hasattr(self, 'api_base') and self.api_base:
                settings["host"] = self.api_base
        
        return settings
    
    def basic_request(self, prompt: str, **kwargs) -> str:
        """Make a basic request to the language model.
        
        Args:
            prompt: The prompt to send
            **kwargs: Additional parameters
            
        Returns:
            The model's response
        """
        # This should not be called in async-only system
        raise NotImplementedError("MindSwarmDSPyLM only supports async operations. DSPy should use aforward/acall.")
    
    def __call__(self, prompt: str = None, messages: List[Dict[str, Any]] = None, **kwargs) -> List[Dict[str, Any]]:
        """Sync call - not supported in async-only system."""
        raise NotImplementedError("MindSwarmDSPyLM only supports async operations. Use acall() instead.")
    
    async def acall(self, prompt: str = None, messages: List[Dict[str, Any]] = None, **kwargs) -> List[Dict[str, Any]]:
        """Async call method for DSPy compatibility.
        
        Args:
            prompt: Optional prompt string
            messages: Optional messages list
            **kwargs: Additional parameters
            
        Returns:
            List with completion dict containing 'text' key
        """
        # Create and use our AI service
        from mind_swarm.ai.config import AIExecutionConfig
        from mind_swarm.ai.providers.factory import create_ai_service
        
        # Override temperature and max_tokens if provided
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        
        # Build AIExecutionConfig from our config
        logger.debug(f"Creating AIExecutionConfig with api_key: {self.api_key[:10] if self.api_key else 'None'}...")
        
        ai_config = AIExecutionConfig(
            model_id=self.model,
            provider=self.provider,
            api_key=self.api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            provider_settings=self._get_provider_settings()
        )
        
        logger.debug(f"AIExecutionConfig created - provider: {ai_config.provider}, has api_key: {bool(ai_config.api_key)}")
        
        # Create AI service
        ai_service = create_ai_service(ai_config)
        
        # Determine what to send
        if messages:
            # Use messages directly
            logger.debug(f"DSPy acall with messages: {len(messages)} messages")
        elif prompt:
            # Convert prompt to messages
            messages = [{"role": "user", "content": prompt}]
            logger.debug(f"DSPy acall with prompt: {prompt[:50]}...")
        else:
            # No input
            logger.warning("DSPy acall with no prompt or messages")
            return []
        
        try:
            # Use our AI service to generate response
            result = await ai_service.chat_completion(messages)
            response_text = result["message"]["content"]
            
            logger.debug(f"DSPy LM response: {response_text[:100]}...")
            
            # Track in history
            self.history.append({
                "messages": messages,
                "response": response_text,
                "usage": result.get("usage", {})
            })
            
            # Return in DSPy expected format
            return [{"text": response_text}]
            
        except Exception as e:
            logger.error(f"Error in DSPy acall: {e}")
            raise
    
    async def aforward(self, **kwargs):
        """Async forward method for DSPy compatibility.
        
        DSPy uses this as the primary generation method.
        """
        # Extract prompt/messages from kwargs
        prompt = kwargs.pop("prompt", None)
        messages = kwargs.pop("messages", None)
        
        logger.debug(f"DSPy aforward called with kwargs: {list(kwargs.keys())}")
        
        # Call acall with extracted values
        completions = await self.acall(prompt=prompt, messages=messages, **kwargs)
        
        # DSPy expects just the text from forward
        if completions and isinstance(completions[0], dict) and "text" in completions[0]:
            return completions[0]["text"]
        
        logger.warning("DSPy aforward returning empty string")
        return ""
    
    def forward(self, **kwargs):
        """Sync forward - not supported."""
        raise NotImplementedError("MindSwarmDSPyLM only supports async operations. Use aforward() instead.")
    
    def call(self, **kwargs):
        """Sync call - not supported."""
        raise NotImplementedError("MindSwarmDSPyLM only supports async operations. Use acall() instead.")
    
    def infer_provider(self) -> str:
        """Return 'custom' to prevent DSPy from using litellm."""
        return "custom"
    
    def inspect_history(self, n: int = 1) -> List[Dict[str, Any]]:
        """Get recent history entries."""
        return list(self.history[-n:]) if self.history else []


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
    
    try:
        preset_config = preset_manager.get_config(preset_name)
        if not preset_config:
            logger.error(f"Preset {preset_name} not found")
            return None
        
        # Convert AIExecutionConfig to dict for our DSPy LM
        config_dict = {
            "provider": preset_config.provider,
            "model": preset_config.model_id,
            "api_key": preset_config.api_key,
            "temperature": preset_config.temperature,
            "max_tokens": preset_config.max_tokens,
        }
        
        # Add provider settings if any
        if preset_config.provider_settings:
            config_dict.update(preset_config.provider_settings)
        
        return configure_dspy_for_mind_swarm(config_dict)
        
    except Exception as e:
        logger.error(f"Failed to create DSPy LM from preset {preset_name}: {e}")
        return None