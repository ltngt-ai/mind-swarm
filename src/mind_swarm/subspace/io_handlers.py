"""Handlers for I/O agent body files."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

import httpx

from mind_swarm.utils.logging import logger


class NetworkBodyHandler:
    """Handles network requests from I/O agents through the network body file."""
    
    def __init__(self, agent_name: str, network_file: Path):
        """Initialize the network handler.
        
        Args:
            agent_name: Name of the I/O agent
            network_file: Path to the network body file
        """
        self.agent_name = agent_name
        self.network_file = network_file
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            follow_redirects=True
        )
        
    async def handle_request(self, content: str) -> str:
        """Handle a network request from the body file.
        
        Args:
            content: JSON content from the body file
            
        Returns:
            JSON response to write back to the body file
        """
        try:
            # Parse request
            request = json.loads(content)
            request_id = request.get("request_id", "unknown")
            
            logger.info(f"Network request from {self.agent_name}: {request.get('method')} {request.get('url')}")
            
            # Validate request
            if not request.get("url"):
                return json.dumps({
                    "request_id": request_id,
                    "error": "Missing URL in request",
                    "status": 400
                })
            
            # Make HTTP request
            method = request.get("method", "GET").upper()
            url = request.get("url")
            headers = request.get("headers", {})
            body = request.get("body")
            timeout = request.get("timeout", 30)
            
            try:
                response = await self.client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    data=body if isinstance(body, str) else json.dumps(body) if body else None,
                    timeout=timeout
                )
                
                # Build response
                result = {
                    "request_id": request_id,
                    "status": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.text,
                    "url": str(response.url),  # Final URL after redirects
                    "timestamp": datetime.now().isoformat()
                }
                
                logger.info(f"Network response for {self.agent_name}: {response.status_code} from {url}")
                
                return json.dumps(result, indent=2)
                
            except httpx.TimeoutException:
                return json.dumps({
                    "request_id": request_id,
                    "error": "Request timed out",
                    "status": 408,
                    "timestamp": datetime.now().isoformat()
                })
            except httpx.RequestError as e:
                return json.dumps({
                    "request_id": request_id,
                    "error": f"Request failed: {str(e)}",
                    "status": 0,
                    "timestamp": datetime.now().isoformat()
                })
                
        except json.JSONDecodeError:
            return json.dumps({
                "error": "Invalid JSON in request",
                "status": 400,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error handling network request for {self.agent_name}: {e}")
            return json.dumps({
                "error": f"Internal error: {str(e)}",
                "status": 500,
                "timestamp": datetime.now().isoformat()
            })
    
    async def close(self):
        """Clean up resources."""
        await self.client.aclose()


class UserIOBodyHandler:
    """Handles user I/O requests from I/O agents through the user_io body file."""
    
    def __init__(self, agent_name: str, user_io_file: Path):
        """Initialize the user I/O handler.
        
        Args:
            agent_name: Name of the I/O agent
            user_io_file: Path to the user_io body file
        """
        self.agent_name = agent_name
        self.user_io_file = user_io_file
        self.sessions: Dict[str, Dict[str, Any]] = {}
        
    async def handle_request(self, content: str) -> str:
        """Handle a user I/O request from the body file.
        
        Args:
            content: JSON content from the body file
            
        Returns:
            JSON response to write back to the body file
        """
        try:
            # Parse request
            message = json.loads(content)
            session_id = message.get("session_id", "default")
            message_type = message.get("type", "response")
            
            logger.info(f"User I/O from {self.agent_name}: type={message_type}, session={session_id}")
            
            # For now, just acknowledge the message
            # In the future, this would interface with actual user connections
            return json.dumps({
                "status": "acknowledged",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            })
            
        except json.JSONDecodeError:
            return json.dumps({
                "error": "Invalid JSON in message",
                "status": "error",
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error handling user I/O for {self.agent_name}: {e}")
            return json.dumps({
                "error": f"Internal error: {str(e)}",
                "status": "error", 
                "timestamp": datetime.now().isoformat()
            })