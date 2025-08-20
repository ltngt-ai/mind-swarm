"""DSPy configuration for Mind-Swarm brain handlers.

This module handles the configuration of DSPy with various language model providers.
"""

import os
import logging
import asyncio
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
            # Check if this is a local OpenAI-compatible endpoint
            # Check both api_settings and provider_settings
            api_settings = self.config.get("api_settings") or self.config.get("provider_settings")
            logger.info(f"OpenAI setup - api_settings: {api_settings}")
            
            if api_settings and isinstance(api_settings, dict) and "host" in api_settings:
                # This is a local OpenAI-compatible server
                self.api_base = api_settings["host"]
                self.api_key = "dummy"  # Local servers don't need real API keys
                logger.info(f"Using local OpenAI-compatible endpoint: {self.api_base}")
            else:
                # This is actual OpenAI API
                self.api_key = self.config.get("api_key") or os.getenv("OPENAI_API_KEY")
                self.api_base = self.config.get("base_url") or "https://api.openai.com/v1"
                logger.info(f"Using standard OpenAI API: {self.api_base}")
        
        elif self.provider == "cerebras":
            # Cerebras uses a fixed endpoint
            self.api_base = "https://api.cerebras.ai/v1"
            self.api_key = self.config.get("api_key") or os.getenv("CEREBRAS_API_KEY")
            logger.info(f"Cerebras setup - api_key from config: {'yes' if self.config.get('api_key') else 'no'}, from env: {'yes' if os.getenv('CEREBRAS_API_KEY') else 'no'}")
            
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
        elif self.provider == "openai":
            # For OpenAI, check if we have a custom host (local server)
            if hasattr(self, 'api_base') and self.api_base and self.api_base != "https://api.openai.com/v1":
                settings["host"] = self.api_base
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
        
        provider_settings = self._get_provider_settings()
        logger.info(f"Provider settings for {self.provider}: {provider_settings}")
        
        ai_config = AIExecutionConfig(
            model_id=self.model,
            provider=self.provider,
            api_key=self.api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            provider_settings=provider_settings
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
            # Check rate limits before making the call
            from mind_swarm.ai.token_tracker import token_tracker
            
            # Try to get cyber_id from kwargs first, then from instance attribute
            cyber_id = kwargs.get("cyber_id", getattr(self, "current_cyber_id", "unknown"))
            
            # Estimate tokens (rough estimate based on message length)
            estimated_tokens = sum(len(msg.get("content", "")) // 4 for msg in messages) + 500
            
            allowed, reason = token_tracker.check_rate_limit(
                cyber_id=cyber_id,
                provider=self.provider,
                estimated_tokens=estimated_tokens
            )
            
            if not allowed:
                logger.info(f"Rate limit for {cyber_id}: {reason}")
                # Parse wait time from the reason message if available
                import re
                
                wait_match = re.search(r'Wait ~(\d+)s', reason)
                if wait_match:
                    wait_time = int(wait_match.group(1))
                    # Add a small buffer
                    wait_time = min(wait_time + 2, 60)  # Cap at 60 seconds
                else:
                    wait_time = 30  # Default wait
                
                logger.info(f"Waiting {wait_time}s for token refill...")
                await asyncio.sleep(wait_time)
                
                # Check again after waiting
                allowed, reason = token_tracker.check_rate_limit(
                    cyber_id=cyber_id,
                    provider=self.provider,
                    estimated_tokens=estimated_tokens
                )
                
                if not allowed:
                    # Still not enough tokens, wait again
                    logger.warning(f"Still waiting for tokens: {reason}")
                    await asyncio.sleep(30)
                    # Try one more time
                    allowed, reason = token_tracker.check_rate_limit(
                        cyber_id=cyber_id,
                        provider=self.provider,
                        estimated_tokens=estimated_tokens
                    )
            
            # Use our AI service to generate response with retry logic
            max_retries = 3
            retry_count = 0
            last_error = None
            
            while retry_count < max_retries:
                try:
                    result = await ai_service.chat_completion(messages)
                    response_text = result["message"]["content"]
                    break  # Success, exit retry loop
                except Exception as e:
                    error_str = str(e).lower()
                    if "rate limit" in error_str or "429" in error_str or "requests per minute" in error_str:
                        retry_count += 1
                        if retry_count < max_retries:
                            # Exponential backoff: 2s, 4s, 8s
                            wait_time = 2 ** retry_count
                            logger.warning(f"Rate limit hit in DSPy acall, attempt {retry_count}/{max_retries}, waiting {wait_time}s")
                            
                            # Add jitter to avoid thundering herd
                            import random
                            jitter = random.uniform(0, 0.5)
                            await asyncio.sleep(wait_time + jitter)
                            continue
                        else:
                            last_error = e
                    else:
                        # Non-rate-limit error, don't retry
                        raise
            
            if retry_count >= max_retries and last_error:
                logger.error(f"Max retries ({max_retries}) exhausted for rate limit")
                raise last_error
            
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
            
            # Track token usage if available
            usage = result.get("usage", {})
            if usage:
                from mind_swarm.ai.token_tracker import token_tracker
                
                # Try to get cyber_id from kwargs first, then from instance attribute
                cyber_id = kwargs.get("cyber_id", getattr(self, "current_cyber_id", "unknown"))
                
                input_tokens = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
                
                if input_tokens or output_tokens:
                    token_tracker.track_usage(
                        cyber_id=cyber_id,
                        provider=self.provider,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens
                    )
                    logger.debug(f"Tracked token usage for {cyber_id}: {input_tokens} in, {output_tokens} out")
            
            # Track in history
            self.history.append({
                "messages": messages,
                "response": response_text,
                "usage": usage
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
        
        logger.debug(f"DSPy aforward called with kwargs: {kwargs}")
        
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


def get_dspy_lm_from_model_pool(paid_allowed: bool = False) -> Optional[dspy.LM]:
    """Get a configured DSPy LM by selecting from the model pool.
    
    Args:
        paid_allowed: Whether paid models can be selected
        
    Returns:
        Configured DSPy LM or None if no model available
    """
    from mind_swarm.ai.model_pool import model_pool
    from mind_swarm.ai.model_selector import ModelSelector
    
    try:
        selector = ModelSelector()
        model = selector.select_model(paid_allowed=paid_allowed)
        
        if not model:
            logger.error("No model available in pool")
            return None
        
        # Get execution config
        config = selector.get_model_config(model)
        
        # Convert to dict for DSPy LM
        config_dict = {
            "provider": config.provider,
            "model": config.model_id,
            "api_key": config.api_key,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
        }
        
        # Add provider settings if any
        if config.provider_settings:
            config_dict.update(config.provider_settings)
            # Map host to base_url for local providers
            if "host" in config.provider_settings:
                config_dict["base_url"] = config.provider_settings["host"]
        
        return configure_dspy_for_mind_swarm(config_dict)
        
    except Exception as e:
        logger.error(f"Failed to create DSPy LM from model pool: {e}")
        return None