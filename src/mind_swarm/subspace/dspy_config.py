"""DSPy configuration for Mind-Swarm brain handlers.

This module handles the configuration of DSPy with various language model providers.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

import dspy

from mind_swarm.utils.logging import logger

# Set up dedicated LLM debug logger
llm_logger = logging.getLogger("mind_swarm.llm_debug")
llm_logger.setLevel(logging.INFO)
llm_logger.propagate = False  # Don't propagate to parent logger

# Global flag to track if we've set up the file handler
_llm_logger_configured = False

def _ensure_llm_logger():
    """Ensure LLM logger is configured with file handler if needed."""
    global _llm_logger_configured
    
    if _llm_logger_configured:
        return
        
    # Check if LLM debug is enabled
    if os.getenv("MIND_SWARM_LLM_DEBUG", "false").lower() == "true":
        # Get the main log file path and create llm debug log next to it
        main_log = os.getenv("MIND_SWARM_LOG_FILE", "/tmp/mind-swarm.log")
        llm_log_path = Path(main_log).parent / "mind-swarm-llm.log"
        
        # Create file handler
        file_handler = logging.FileHandler(llm_log_path, mode='a')
        file_handler.setLevel(logging.INFO)
        
        # Simple format without timestamps (they're in the log content)
        formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(formatter)
        
        llm_logger.addHandler(file_handler)
        logger.info(f"LLM debug logging configured to: {llm_log_path}")
        
        # Test write to ensure it's working
        llm_logger.info("=== LLM Debug Log Started ===\n")
        
    _llm_logger_configured = True


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
        
        logger.info(f"Initializing MindSwarmDSPyLM with provider={provider}, model={model}")
        
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
            logger.debug(f"Final api_key: {self.api_key if self.api_key else 'None'}")
        
        elif self.provider == "openai":
            self.api_key = self.config.get("api_key") or os.getenv("OPENAI_API_KEY")
            self.api_base = self.config.get("base_url")
        
        elif self.provider == "anthropic":
            self.api_key = self.config.get("api_key") or os.getenv("ANTHROPIC_API_KEY")
        
        elif self.provider in ["openai_compatible", "local", "ollama"]:
            # Local or custom OpenAI-compatible endpoint
            self.api_key = self.config.get("api_key", "dummy")
            
            # Check for base_url in config or provider_settings/api_settings
            base_url = self.config.get("base_url")
            if not base_url:
                # Check provider_settings or api_settings for host
                settings = self.config.get("provider_settings") or self.config.get("api_settings")
                if settings and isinstance(settings, dict) and "host" in settings:
                    base_url = settings["host"]
                else:
                    base_url = "http://192.168.1.147:1234"
            
            # For local providers, base_url is the host URL, api_base is used by openai_compatible
            self.api_base = base_url
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
            # Local providers need the host URL (without /v1)
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
        logger.info(f"=== acall invoked! Provider: {self.provider}, Model: {self.model} ===")
        # Create and use our AI service
        from mind_swarm.ai.config import AIExecutionConfig
        from mind_swarm.ai.providers.factory import create_ai_service
        
        # Check if LLM debug is enabled
        llm_debug = os.getenv("MIND_SWARM_LLM_DEBUG", "false").lower() == "true"
        if llm_debug:
            logger.debug(f"LLM debug enabled, about to log API call")
        
        # Override temperature and max_tokens if provided
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        
        # Build AIExecutionConfig from our config
        logger.debug(f"Creating AIExecutionConfig with api_key: {self.api_key if self.api_key else 'None'}")
        
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
            logger.debug(f"DSPy acall with prompt: {prompt}")
        else:
            # No input
            logger.warning("DSPy acall with no prompt or messages")
            return []
        
        # Log full API call if LLM debug is enabled
        if llm_debug:
            _ensure_llm_logger()  # Configure logger if not already done
            import datetime
            timestamp = datetime.datetime.now().isoformat()
            llm_logger.info(f"\n{'='*80}")
            llm_logger.info(f"LLM API CALL [{timestamp}]")
            llm_logger.info(f"{'='*80}")
            llm_logger.info(f"Model: {self.model}")
            llm_logger.info(f"Provider: {self.provider}")
            llm_logger.info(f"Temperature: {temperature}")
            llm_logger.info(f"Max Tokens: {max_tokens}")
            llm_logger.info("")
            
            for i, msg in enumerate(messages):
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                
                # Debug: Check for truncation
                if 'Message Protocol' in content and 'MESSAGE' not in content:
                    llm_logger.info(f"WARNING: Message Protocol appears truncated!")
                    llm_logger.info(f"Content length: {len(content)}")
                    llm_logger.info(f"Last 50 chars: {repr(content[-50:])}")
                
                llm_logger.info(f"--- Message {i+1} ({role}) ---")
                
                # Replace all literal \n with actual newlines throughout the content
                expanded_content = content.replace('\\n', '\n')
                llm_logger.info(expanded_content)
                
                llm_logger.info("")  # Empty line between messages
            
            llm_logger.info(f"{'='*80}\n")
        
        try:
            # Use our AI service to generate response
            result = await ai_service.chat_completion(messages)
            response_text = result["message"]["content"]
            
            logger.debug(f"DSPy LM response: {response_text}")
            
            # Log full response if LLM debug is enabled
            if llm_debug:
                _ensure_llm_logger()  # Configure logger if not already done
                
                llm_logger.info(f"{'='*80}")
                llm_logger.info("LLM API RESPONSE")
                llm_logger.info(f"{'='*80}")
                
                # Replace all literal \n with actual newlines
                expanded_response = response_text.replace('\\n', '\n')
                llm_logger.info(expanded_response)
                
                if "usage" in result:
                    llm_logger.info("")
                    llm_logger.info("Token Usage:")
                    for key, value in result['usage'].items():
                        llm_logger.info(f"  {key}: {value}")
                
                llm_logger.info(f"{'='*80}\n")
            
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
    logger.info(f"Configuring DSPy with Mind-Swarm LM for model: {config.get('model')}")
    lm = MindSwarmDSPyLM(config)
    dspy.settings.configure(lm=lm)
    logger.info(f"DSPy configured successfully with LM: {lm}")
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
            # Map host to base_url for local providers
            if "host" in preset_config.provider_settings:
                config_dict["base_url"] = preset_config.provider_settings["host"]
        
        return configure_dspy_for_mind_swarm(config_dict)
        
    except Exception as e:
        logger.error(f"Failed to create DSPy LM from preset {preset_name}: {e}")
        return None