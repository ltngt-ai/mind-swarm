"""OpenRouter AI Service implementation."""

import asyncio
import json
import threading
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
import requests

from mind_swarm.ai.config import AIExecutionConfig
from mind_swarm.ai.providers.base import AIService, AIStreamChunk
from mind_swarm.utils.logging import logger


API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS_API_URL = "https://openrouter.ai/api/v1/models"


class OpenRouterError(Exception):
    """Base exception for OpenRouter errors."""
    pass


class OpenRouterAuthError(OpenRouterError):
    """Authentication error."""
    pass


class OpenRouterRateLimitError(OpenRouterError):
    """Rate limit exceeded."""
    pass


class OpenRouterAIService(AIService):
    """OpenRouter API wrapper for AI services."""
    
    def __init__(
        self,
        config: AIExecutionConfig,
        shutdown_event: Optional[threading.Event] = None,
    ):
        """Initialize with AIExecutionConfig."""
        super().__init__(config)
        
        if config.provider != "openrouter":
            raise ValueError(f"Expected provider 'openrouter', got '{config.provider}'")
        
        self.api_key = config.api_key
        self.model = config.model_id
        self.params = {
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
        }
        
        if not self.api_key:
            raise ValueError("OpenRouter requires an API key")
        
        self.shutdown_event = shutdown_event
        self.site_url = config.provider_settings.get("site_url", "http://mind-swarm:8000")
        self.app_name = config.provider_settings.get("app_name", "Mind-Swarm")
    
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
                    API_URL, 
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
                    raise OpenRouterError("No choices in response")
                
                message_obj = choices[0].get("message", {})
                usage = data.get("usage", {})
                
                return {"response": data, "message": message_obj, "usage": usage}
                
            except httpx.RequestError as e:
                raise OpenRouterError(f"Network error: {e}") from e
    
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
                    API_URL,
                    headers=headers,
                    json=payload,
                    timeout=60.0
                ) as response:
                    if response.status_code >= 400:
                        self._handle_error_response(response)
                    
                    async for line in response.aiter_lines():
                        if self.shutdown_event and self.shutdown_event.is_set():
                            break
                        
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
                raise OpenRouterError(f"Streaming error: {e}") from e
    
    def list_models(self) -> List[Dict[str, Any]]:
        """Get available models from OpenRouter."""
        headers = self._get_headers()
        
        try:
            response = requests.get(MODELS_API_URL, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            models = data.get("data", [])
            return models if isinstance(models, list) else []
        except requests.exceptions.RequestException as e:
            raise OpenRouterError(f"Failed to fetch models: {e}") from e
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.site_url,
            "X-Title": self.app_name,
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
        for key in ["temperature", "max_tokens", "top_p", "frequency_penalty", "presence_penalty", "stop"]:
            if key in kwargs:
                payload[key] = kwargs[key]
        
        # Add tools
        if tools:
            payload["tools"] = tools
            payload["parallel_tool_calls"] = True
        
        return payload
    
    def _handle_error_response(self, response: Any) -> None:
        """Handle HTTP error responses."""
        status_code = response.status_code
        try:
            error_data = response.json()
            error_msg = error_data.get("error", {}).get("message", response.text)
        except Exception:
            error_msg = response.text
        
        if status_code == 401:
            raise OpenRouterAuthError(f"Authentication failed: {error_msg}")
        elif status_code == 429:
            raise OpenRouterRateLimitError(f"Rate limit exceeded: {error_msg}")
        else:
            raise OpenRouterError(f"API error {status_code}: {error_msg}")