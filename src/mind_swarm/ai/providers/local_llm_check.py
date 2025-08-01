"""Local LLM server health check and model detection."""

import asyncio
import aiohttp
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


async def check_local_llm_server(base_url: str = "http://192.168.1.147:1234") -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Check if local LLM server is running and get model info.
    
    Args:
        base_url: The base URL of the local LLM server
        
    Returns:
        Tuple of (is_healthy, model_info)
    """
    try:
        # First check if server is responding
        async with aiohttp.ClientSession() as session:
            # Try to get model info from OpenAI-compatible endpoint
            models_url = f"{base_url}/v1/models"
            
            async with session.get(models_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract model information
                    models = data.get("data", [])
                    if models:
                        model_info = {
                            "server_url": base_url,
                            "available": True,
                            "models": [
                                {
                                    "id": model.get("id", "unknown"),
                                    "created": model.get("created"),
                                    "owned_by": model.get("owned_by", "local")
                                }
                                for model in models
                            ],
                            "primary_model": models[0].get("id", "unknown") if models else None
                        }
                        
                        logger.info(f"Local LLM server healthy at {base_url}")
                        logger.info(f"Available models: {[m['id'] for m in model_info['models']]}")
                        
                        return True, model_info
                    else:
                        # Server responds but no models
                        return True, {
                            "server_url": base_url,
                            "available": True,
                            "models": [],
                            "primary_model": None,
                            "warning": "Server running but no models loaded"
                        }
                else:
                    logger.warning(f"Local LLM server returned status {response.status}")
                    return False, None
                    
    except asyncio.TimeoutError:
        logger.warning(f"Timeout connecting to local LLM server at {base_url}")
        return False, {"error": "Connection timeout", "server_url": base_url}
        
    except aiohttp.ClientError as e:
        logger.warning(f"Cannot connect to local LLM server at {base_url}: {e}")
        return False, {"error": str(e), "server_url": base_url}
        
    except Exception as e:
        logger.error(f"Unexpected error checking local LLM server: {e}")
        return False, {"error": f"Unexpected error: {e}", "server_url": base_url}


async def get_model_capabilities(base_url: str, model_id: str) -> Optional[Dict[str, Any]]:
    """Get detailed capabilities of a specific model.
    
    Args:
        base_url: The base URL of the local LLM server
        model_id: The model ID to query
        
    Returns:
        Model capabilities or None if unavailable
    """
    try:
        async with aiohttp.ClientSession() as session:
            # Try completion endpoint to test model
            test_url = f"{base_url}/v1/completions"
            test_payload = {
                "model": model_id,
                "prompt": "Hello",
                "max_tokens": 1,
                "temperature": 0
            }
            
            async with session.post(
                test_url, 
                json=test_payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    # Model works
                    return {
                        "model_id": model_id,
                        "completion_capable": True,
                        "chat_capable": True,  # Assume chat if completion works
                    }
                else:
                    error_text = await response.text()
                    logger.warning(f"Model test failed: {error_text}")
                    return {
                        "model_id": model_id,
                        "completion_capable": False,
                        "error": error_text
                    }
                    
    except Exception as e:
        logger.error(f"Error testing model {model_id}: {e}")
        return None


def format_server_status(is_healthy: bool, model_info: Optional[Dict[str, Any]]) -> str:
    """Format server status for display.
    
    Args:
        is_healthy: Whether server is healthy
        model_info: Model information if available
        
    Returns:
        Formatted status string
    """
    if not is_healthy:
        if model_info and "error" in model_info:
            return f"❌ Local LLM server unavailable: {model_info['error']}"
        return "❌ Local LLM server is not running"
    
    if not model_info:
        return "⚠️ Local LLM server running but status unknown"
    
    if model_info.get("warning"):
        return f"⚠️ {model_info['warning']}"
    
    models = model_info.get("models", [])
    if not models:
        return "⚠️ Local LLM server running but no models available"
    
    primary = model_info.get("primary_model", "unknown")
    model_count = len(models)
    
    return f"✅ Local LLM server ready - Model: {primary} ({model_count} available)"


# Convenience function for CLI/startup checks
async def verify_local_llm_ready(base_url: Optional[str] = None) -> bool:
    """Simple check if local LLM is ready for use.
    
    Args:
        base_url: Optional override for server URL
        
    Returns:
        True if ready, False otherwise
    """
    url = base_url or "http://192.168.1.147:1234"
    is_healthy, model_info = await check_local_llm_server(url)
    
    if is_healthy and model_info and model_info.get("models"):
        return True
    
    return False