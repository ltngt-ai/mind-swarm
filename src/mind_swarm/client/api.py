"""Mind-Swarm client API for connecting to the server."""

import asyncio
import json
from typing import Dict, Any, Optional, List
from pathlib import Path

import httpx
import websockets
from pydantic import BaseModel

from mind_swarm.utils.logging import logger


class AgentInfo(BaseModel):
    """Agent information."""
    agent_id: str
    alive: bool
    state: str
    uptime: float
    inbox_count: int
    outbox_count: int
    

class ServerStatus(BaseModel):
    """Server status information."""
    agents: Dict[str, Dict[str, Any]]
    plaza_questions: int
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
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/")
                return response.status_code == 200
        except Exception:
            return False
    
    async def get_status(self) -> ServerStatus:
        """Get server and agent status.
        
        Returns:
            Server status information
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/status")
            response.raise_for_status()
            return ServerStatus(**response.json())
    
    async def spawn_agent(
        self, 
        name: Optional[str] = None,
        use_premium: bool = False,
        config: Optional[Dict[str, Any]] = None
    ) -> str:
        """Spawn a new agent.
        
        Args:
            name: Optional agent name
            use_premium: Whether to use premium AI model
            config: Additional configuration
            
        Returns:
            Agent ID
        """
        payload = {
            "name": name,
            "use_premium": use_premium,
            "config": config or {}
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/agents/spawn",
                json=payload
            )
            response.raise_for_status()
            return response.json()["agent_id"]
    
    async def terminate_agent(self, agent_id: str):
        """Terminate an agent.
        
        Args:
            agent_id: ID of agent to terminate
        """
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{self.base_url}/agents/{agent_id}")
            response.raise_for_status()
    
    async def send_command(
        self, 
        agent_id: str, 
        command: str, 
        params: Optional[Dict[str, Any]] = None
    ):
        """Send a command to an agent.
        
        Args:
            agent_id: Target agent ID
            command: Command to send
            params: Optional command parameters
        """
        payload = {
            "command": command,
            "params": params or {}
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/agents/{agent_id}/command",
                json=payload
            )
            response.raise_for_status()
    
    async def create_plaza_question(self, text: str, created_by: str = "user") -> str:
        """Create a new plaza question.
        
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
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/plaza/questions",
                json=payload
            )
            response.raise_for_status()
            return response.json()["question_id"]
    
    async def get_agent_states(self) -> Dict[str, Dict[str, Any]]:
        """Get states of all agents.
        
        Returns:
            Dictionary of agent states keyed by agent name
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/agents/all")
            response.raise_for_status()
            data = response.json()
            
            # Convert list of agents to dict keyed by name
            agents = data.get("agents", [])
            agent_dict = {}
            for agent in agents:
                name = agent.get("name", agent.get("agent_id", "unknown"))
                agent_dict[name] = agent
            
            return agent_dict
    
    async def get_plaza_questions(self) -> List[Dict[str, Any]]:
        """Get all plaza questions.
        
        Returns:
            List of questions
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/plaza/questions")
            response.raise_for_status()
            return response.json()["questions"]
    
    async def connect_websocket(self, on_event=None):
        """Connect to server WebSocket for real-time updates.
        
        Args:
            on_event: Callback for events (async function)
        """
        async def _ws_handler():
            try:
                async with websockets.connect(self.ws_url) as websocket:
                    self._ws_connection = websocket
                    logger.info("Connected to server WebSocket")
                    
                    async for message in websocket:
                        try:
                            event = json.loads(message)
                            if on_event:
                                await on_event(event)
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