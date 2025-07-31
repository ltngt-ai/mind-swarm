"""OpenAI-compatible AI Service implementation.

This provider works with any OpenAI-compatible API including:
- OpenAI API
- Ollama (with OpenAI compatibility)
- LocalAI
- LM Studio
- vLLM
- Any other OpenAI-compatible endpoint
"""

import asyncio
import json
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from mind_swarm.ai.config import AIExecutionConfig
from mind_swarm.ai.providers.base import AIService, AIStreamChunk
from mind_swarm.utils.logging import logger


class OpenAICompatibleError(Exception):
    """Base exception for OpenAI-compatible API errors."""
    pass


class OpenAICompatibleService(AIService):
    """Generic OpenAI-compatible API wrapper.
    
    This works with any service that implements the OpenAI API specification.
    """
    
    def __init__(
        self,
        config: AIExecutionConfig,
        api_url: Optional[str] = None,
    ):
        """Initialize with AIExecutionConfig.
        
        Args:
            config: AI execution configuration
            api_url: Optional custom API URL (defaults based on provider)
        """
        super().__init__(config)
        
        # Determine API URL based on provider
        if api_url:
            self.api_url = api_url.rstrip("/")
        elif config.provider == "openai":
            self.api_url = "https://api.openai.com/v1"
        elif config.provider == "ollama":
            # Ollama's OpenAI-compatible endpoint
            host = config.provider_settings.get("host", "http://localhost:11434")
            self.api_url = f"{host}/v1"
        elif config.provider == "local":
            # Generic local endpoint
            host = config.provider_settings.get("host", "http://localhost:8000")
            self.api_url = f"{host}/v1"
        else:
            # Default to OpenAI
            self.api_url = "https://api.openai.com/v1"
        
        self.api_key = config.api_key or "dummy-key-for-local"
        self.model = config.model_id
        self.params = {
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
        }
        
        logger.info(f"Initialized OpenAI-compatible service for {config.provider} at {self.api_url}")
    
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Generate a response from a prompt."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        result = await self.chat_completion(messages, **kwargs)
        return result["message"]["content"]
    
    async def stream_generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[AIStreamChunk, None]:
        """Stream a response from a prompt."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        async for chunk in self.stream_chat_completion(messages, **kwargs):
            yield chunk
    
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Non-streaming chat completion."""
        headers = self._get_headers()
        payload = self._build_payload(messages, tools=tools, **kwargs)
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.api_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60.0
                )
                
                if response.status_code >= 400:
                    self._handle_error_response(response)
                
                data = response.json()
                
                # Extract message from choices
                choices = data.get("choices", [])
                if not choices:
                    raise OpenAICompatibleError("No choices in response")
                
                message_obj = choices[0].get("message", {})
                usage = data.get("usage", {})
                
                return {"response": data, "message": message_obj, "usage": usage}
                
            except httpx.RequestError as e:
                raise OpenAICompatibleError(f"Network error: {e}") from e
    
    async def stream_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[AIStreamChunk, None]:
        """Streaming chat completion."""
        headers = self._get_headers()
        payload = self._build_payload(messages, tools=tools, **kwargs)
        payload["stream"] = True
        
        async with httpx.AsyncClient() as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self.api_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60.0
                ) as response:
                    if response.status_code >= 400:
                        self._handle_error_response(response)
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            json_str = line[6:].strip()
                            if json_str == "[DONE]":
                                break
                            
                            try:
                                chunk_data = json.loads(json_str)
                                # Convert to AIStreamChunk
                                choices = chunk_data.get("choices", [])
                                if choices:
                                    choice = choices[0]
                                    delta = choice.get("delta", {})
                                    finish_reason = choice.get("finish_reason")
                                    usage = chunk_data.get("usage")
                                    
                                    yield AIStreamChunk(
                                        delta_content=delta.get("content"),
                                        delta_tool_call_part=delta.get("tool_calls"),
                                        finish_reason=finish_reason,
                                        usage=usage,
                                    )
                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to parse chunk: {e}")
                                
            except httpx.RequestError as e:
                raise OpenAICompatibleError(f"Streaming error: {e}") from e
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """Get available models from the API."""
        headers = self._get_headers()
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.api_url}/models",
                    headers=headers,
                    timeout=30.0
                )
                
                if response.status_code >= 400:
                    # Some local providers might not implement /models
                    logger.warning(f"Failed to list models: {response.status_code}")
                    return []
                
                data = response.json()
                models = data.get("data", [])
                return models if isinstance(models, list) else []
                
            except httpx.RequestError as e:
                logger.warning(f"Failed to fetch models: {e}")
                return []
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    def _build_payload(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Build the API payload."""
        payload: Dict[str, Any] = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
        }
        
        # Add base parameters
        if self.params.get("temperature") is not None:
            payload["temperature"] = self.params["temperature"]
        if self.params.get("max_tokens") is not None:
            payload["max_tokens"] = self.params["max_tokens"]
        
        # Override with provided params
        for key in ["temperature", "max_tokens", "top_p", "frequency_penalty", 
                    "presence_penalty", "stop", "seed", "top_k"]:
            if key in kwargs:
                payload[key] = kwargs[key]
        
        # Add tools if supported (not all providers support this)
        if tools:
            payload["tools"] = tools
            # Note: parallel_tool_calls might not be supported by all providers
            if self.config.provider in ["openai", "openrouter"]:
                payload["parallel_tool_calls"] = kwargs.get("parallel_tool_calls", True)
        
        # Add response format if specified
        if "response_format" in kwargs:
            payload["response_format"] = kwargs["response_format"]
        
        return payload
    
    def _handle_error_response(self, response: httpx.Response) -> None:
        """Handle HTTP error responses."""
        status_code = response.status_code
        try:
            error_data = response.json()
            # Try OpenAI error format first
            error_msg = error_data.get("error", {}).get("message", "")
            if not error_msg:
                # Fallback to plain message
                error_msg = error_data.get("message", response.text)
        except Exception:
            error_msg = response.text
        
        if status_code == 401:
            raise OpenAICompatibleError(f"Authentication failed: {error_msg}")
        elif status_code == 429:
            raise OpenAICompatibleError(f"Rate limit exceeded: {error_msg}")
        elif status_code == 404:
            raise OpenAICompatibleError(f"Endpoint not found (check API URL): {error_msg}")
        else:
            raise OpenAICompatibleError(f"API error {status_code}: {error_msg}")