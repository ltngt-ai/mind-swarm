"""Mind-Swarm client API for connecting to the server."""

import asyncio
import json
from typing import Dict, Any, Optional, List
from pathlib import Path

import httpx
import websockets
from pydantic import BaseModel

from mind_swarm.utils.logging import logger


class CyberInfo(BaseModel):
    """Cyber information."""
    cyber_id: str
    alive: bool
    state: str
    uptime: float
    inbox_count: int
    outbox_count: int
    

class ServerStatus(BaseModel):
    """Server status information."""
    Cybers: Dict[str, Dict[str, Any]]
    community_questions: int
    server_uptime: float
    server_start_time: str


class MindSwarmClient:
    """Client for connecting to Mind-Swarm server."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8888):
        """Initialize the client.
        
        Args:
            host: Server host address
            port: Server port
        """
        self.base_url = f"http://{host}:{port}"
        self.ws_url = f"ws://{host}:{port}/ws"
        self._ws_connection = None
        self._ws_task = None
    
    async def check_server(self) -> bool:
        """Check if server is running and accessible.
        
        Returns:
            True if server is accessible
        """
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
                response = await client.get(f"{self.base_url}/")
                return response.status_code == 200
        except Exception:
            return False
    
    async def get_status(self) -> ServerStatus:
        """Get server and Cyber status.
        
        Returns:
            Server status information
        """
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.get(f"{self.base_url}/status")
            response.raise_for_status()
            return ServerStatus(**response.json())
    
    async def create_agent(
        self, 
        name: Optional[str] = None,
        cyber_type: str = "general",
        config: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new Cyber.
        
        Args:
            name: Optional Cyber name
            cyber_type: Type of Cyber (general, io_gateway)
            config: Additional configuration
            
        Returns:
            Cyber ID
        """
        payload = {
            "name": name,
            "cyber_type": cyber_type,
            "config": config or {}
        }
        
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.post(
                f"{self.base_url}/Cybers/create",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            # Server returns 'name' not 'cyber_id' now
            return data.get("name", data.get("cyber_id", "unknown"))
    
    async def terminate_agent(self, cyber_id: str):
        """Terminate an Cyber.
        
        Args:
            cyber_id: Name of Cyber to terminate
        """
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.delete(f"{self.base_url}/Cybers/{cyber_id}")
            response.raise_for_status()
    
    
    async def send_command(
        self, 
        cyber_id: str, 
        command: str, 
        params: Optional[Dict[str, Any]] = None
    ):
        """Send a command to an Cyber.
        
        Args:
            cyber_id: Target Cyber name
            command: Command to send
            params: Optional command parameters
        """
        payload = {
            "command": command,
            "params": params or {}
        }
        
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.post(
                f"{self.base_url}/Cybers/{cyber_id}/command",
                json=payload
            )
            response.raise_for_status()
    
    async def send_message(
        self,
        cyber_id: str,
        content: str,
        message_type: str = "text"
    ):
        """Send a message to an Cyber.
        
        Args:
            cyber_id: Target Cyber name
            content: Message content
            message_type: Type of message (default: "text")
        """
        payload = {
            "content": content,
            "message_type": message_type
        }
        
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.post(
                f"{self.base_url}/Cybers/{cyber_id}/message",
                json=payload
            )
            response.raise_for_status()
    
    async def create_community_question(self, text: str, created_by: str = "user") -> str:
        """Create a new community question.
        
        Args:
            text: Question text
            created_by: Creator identifier
            
        Returns:
            Question ID
        """
        payload = {
            "text": text,
            "created_by": created_by
        }
        
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.post(
                f"{self.base_url}/community/questions",
                json=payload
            )
            response.raise_for_status()
            return response.json()["question_id"]
    
    async def update_announcements(
        self, 
        title: str, 
        message: str, 
        priority: str = "HIGH",
        expires: Optional[str] = None
    ) -> bool:
        """Update system announcements for all Cybers.
        
        Args:
            title: Announcement title
            message: Announcement message
            priority: Priority level (CRITICAL, HIGH, MEDIUM, LOW)
            expires: Optional expiration date in ISO format
            
        Returns:
            True if successful
        """
        payload = {
            "title": title,
            "message": message,
            "priority": priority
        }
        if expires:
            payload["expires"] = expires
        
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.post(
                f"{self.base_url}/community/announcements",
                json=payload
            )
            response.raise_for_status()
            return response.json().get("success", False)
    
    async def clear_announcements(self) -> bool:
        """Clear all system announcements.
        
        Returns:
            True if successful
        """
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.delete(
                f"{self.base_url}/community/announcements"
            )
            response.raise_for_status()
            return response.json().get("success", False)
    
    async def get_cyber_states(self) -> Dict[str, Dict[str, Any]]:
        """Get states of all Cybers.
        
        Returns:
            Dictionary of Cyber states keyed by Cyber name
        """
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.get(f"{self.base_url}/Cybers/all")
            response.raise_for_status()
            data = response.json()
            
            # Convert list of Cybers to dict keyed by name
            Cybers = data.get("cybers", [])
            agent_dict = {}
            for Cyber in Cybers:
                name = Cyber.get("name", Cyber.get("cyber_id", "unknown"))
                agent_dict[name] = Cyber
            
            return agent_dict
    
    async def get_community_questions(self) -> List[Dict[str, Any]]:
        """Get all community questions.
        
        Returns:
            List of questions
        """
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.get(f"{self.base_url}/community/questions")
            response.raise_for_status()
            return response.json()["questions"]
    
    async def register_developer(self, name: str, full_name: Optional[str] = None,
                               email: Optional[str] = None) -> str:
        """Register a new developer.
        
        Args:
            name: Developer username
            full_name: Optional full name
            email: Optional email address
            
        Returns:
            Developer Cyber name (e.g., "deano_dev")
        """
        payload = {
            "name": name,
            "full_name": full_name,
            "email": email
        }
        
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.post(
                f"{self.base_url}/developers/register",
                json=payload
            )
            response.raise_for_status()
            return response.json()["cyber_name"]
    
    async def set_current_developer(self, name: str) -> bool:
        """Set the current developer.
        
        Args:
            name: Developer username
            
        Returns:
            True if successful
        """
        payload = {"name": name}
        
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.post(
                f"{self.base_url}/developers/current",
                json=payload
            )
            response.raise_for_status()
            return response.json()["success"]
    
    async def get_current_developer(self) -> Optional[Dict[str, Any]]:
        """Get current developer information."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.get(f"{self.base_url}/developers/current")
            response.raise_for_status()
            return response.json().get("developer")
    
    async def list_developers(self) -> Dict[str, Dict[str, Any]]:
        """List all registered developers."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.get(f"{self.base_url}/developers")
            response.raise_for_status()
            return response.json()["developers"]
    
    async def check_mailbox(self, include_read: bool = False) -> List[Dict[str, Any]]:
        """Check current developer's mailbox."""
        params = {"include_read": include_read}
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.get(f"{self.base_url}/developers/mailbox", params=params)
            response.raise_for_status()
            return response.json()["messages"]
    
    async def mark_message_read(self, message_index: int) -> bool:
        """Mark a message as read by index."""
        payload = {"message_index": message_index}
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.post(
                f"{self.base_url}/developers/mailbox/read",
                json=payload
            )
            response.raise_for_status()
            return response.json()["success"]
    
    async def connect_websocket(self, on_event=None):
        """Connect to server WebSocket for real-time updates.
        
        Args:
            on_event: Callback for events (async function)
        """
        async def _ws_handler():
            try:
                # Configure WebSocket with longer timeouts and ping interval
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=60,  # Send ping every 60 seconds
                    ping_timeout=30,   # Wait 30 seconds for pong
                    close_timeout=30   # Wait 30 seconds for close
                ) as websocket:
                    self._ws_connection = websocket
                    logger.info("Connected to server WebSocket")
                    
                    async for message in websocket:
                        try:
                            # Handle ping/pong messages
                            if message == "ping":
                                await websocket.send("pong")
                                continue
                            elif message == "pong":
                                # Server acknowledged our ping
                                continue
                                
                            # Try to parse as JSON
                            try:
                                event = json.loads(message)
                                if on_event:
                                    await on_event(event)
                            except json.JSONDecodeError:
                                # Not JSON, might be echo or other text message
                                logger.debug(f"Received non-JSON message: {message}")
                        except Exception as e:
                            logger.error(f"Error handling WebSocket message: {e}")
                            
            except Exception as e:
                logger.error(f"WebSocket connection error: {e}")
            finally:
                self._ws_connection = None
        
        self._ws_task = asyncio.create_task(_ws_handler())
    
    async def disconnect_websocket(self):
        """Disconnect from WebSocket."""
        if self._ws_connection:
            await self._ws_connection.close()
        
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
    
    def is_server_running(self) -> bool:
        """Check if server is running by looking for PID file.
        
        Returns:
            True if server appears to be running
        """
        pid_file = Path("/tmp/mind-swarm-server.pid")
        if not pid_file.exists():
            return False
        
        try:
            pid = int(pid_file.read_text().strip())
            # Check if process exists
            import os
            os.kill(pid, 0)
            return True
        except (ValueError, ProcessLookupError, PermissionError):
            return False
    
    # Knowledge System Methods
    
    async def search_knowledge(self, query: str, limit: int = 10) -> List[Dict]:
        """Search the knowledge system.
        
        Args:
            query: Search query
            limit: Maximum results to return
            
        Returns:
            List of knowledge items
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/knowledge/search",
                params={"query": query, "limit": limit}
            )
            response.raise_for_status()
            return response.json()
    
    async def add_knowledge(self, content: str, tags: List[str] = None) -> Optional[str]:
        """Add knowledge to the shared system.
        
        Args:
            content: Knowledge content
            tags: Optional tags for categorization
            
        Returns:
            Knowledge ID if successful
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/knowledge/add",
                json={
                    "content": content,
                    "metadata": {"tags": tags or []}
                }
            )
            response.raise_for_status()
            result = response.json()
            return result.get("knowledge_id") if result.get("success") else None
    
    async def list_knowledge(self, limit: int = 100) -> List[Dict]:
        """List all shared knowledge.
        
        Args:
            limit: Maximum items to return
            
        Returns:
            List of knowledge items
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/knowledge/list",
                params={"limit": limit}
            )
            response.raise_for_status()
            return response.json()
    
    async def remove_knowledge(self, knowledge_id: str) -> bool:
        """Remove knowledge from the system.
        
        Args:
            knowledge_id: ID of knowledge to remove
            
        Returns:
            True if successful
        """
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/knowledge/{knowledge_id}"
            )
            response.raise_for_status()
            result = response.json()
            return result.get("success", False)
    
    async def get_knowledge_stats(self) -> Dict:
        """Get knowledge system statistics.
        
        Returns:
            Statistics dictionary
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/knowledge/stats")
            response.raise_for_status()
            return response.json()
    
    # Freeze/Unfreeze Methods
    
    async def freeze_cyber(self, cyber_name: str) -> Dict[str, Any]:
        """Freeze a single Cyber to a tar.gz archive."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.post(f"{self.base_url}/cybers/freeze/{cyber_name}")
            response.raise_for_status()
            return response.json()
    
    async def freeze_all_cybers(self) -> Dict[str, Any]:
        """Freeze all Cybers to a tar.gz archive."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.post(f"{self.base_url}/cybers/freeze-all")
            response.raise_for_status()
            return response.json()
    
    async def unfreeze_cybers(self, archive_path: str, force: bool = False) -> Dict[str, Any]:
        """Unfreeze Cybers from a tar.gz archive."""
        payload = {"archive_path": archive_path, "force": force}
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.post(f"{self.base_url}/cybers/unfreeze", json=payload)
            response.raise_for_status()
            return response.json()
    
    async def list_frozen_cybers(self) -> Dict[str, Any]:
        """List all frozen Cyber archives."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.get(f"{self.base_url}/cybers/frozen")
            response.raise_for_status()
            return response.json()