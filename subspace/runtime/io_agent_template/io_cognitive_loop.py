"""Cognitive loop for I/O Gateway agents."""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

from base_code_template.cognitive_loop import CognitiveLoop, ObservationMemoryBlock, TaskMemoryBlock
from base_code_template.memory_manager import MemoryManager, Priority

logger = logging.getLogger("agent.io_cognitive")


class IOBodyFileHandler:
    """Handles special body files for I/O agents."""
    
    def __init__(self, home_dir: Path):
        self.home_dir = home_dir
        self.network_file = home_dir / "network"
        self.user_io_file = home_dir / "user_io"
        
        # Track pending requests
        self.pending_network_requests: Dict[str, Dict] = {}
        self.pending_user_responses: Dict[str, Dict] = {}
        
        # Ensure files exist
        self.network_file.touch(exist_ok=True)
        self.user_io_file.touch(exist_ok=True)
    
    async def check_network_file(self) -> Optional[Dict[str, Any]]:
        """Check for network responses."""
        try:
            content = self.network_file.read_text().strip()
            if content and content.startswith('{'):
                response = json.loads(content)
                # Clear file after reading
                self.network_file.write_text("")
                
                # Match with pending request
                request_id = response.get("request_id")
                if request_id in self.pending_network_requests:
                    original_request = self.pending_network_requests.pop(request_id)
                    response["original_request"] = original_request
                
                return response
        except Exception as e:
            logger.error(f"Error reading network file: {e}")
        return None
    
    async def check_user_io_file(self) -> Optional[Dict[str, Any]]:
        """Check for user messages."""
        try:
            content = self.user_io_file.read_text().strip()
            if content and content.startswith('{'):
                message = json.loads(content)
                # Clear file after reading
                self.user_io_file.write_text("")
                return message
        except Exception as e:
            logger.error(f"Error reading user_io file: {e}")
        return None
    
    async def make_network_request(self, request: Dict[str, Any]) -> str:
        """Make a network request through the body file."""
        request_id = f"req_{int(datetime.now().timestamp() * 1000)}"
        request["request_id"] = request_id
        
        # Track pending request
        self.pending_network_requests[request_id] = request
        
        # Write request
        self.network_file.write_text(json.dumps(request, indent=2))
        logger.info(f"Network request {request_id}: {request['method']} {request['url']}")
        
        return request_id
    
    async def send_user_response(self, response: Dict[str, Any]):
        """Send response to user through body file."""
        self.user_io_file.write_text(json.dumps(response, indent=2))
        logger.info(f"Sent user response for session {response.get('session_id')}")


class IOCognitiveLoop(CognitiveLoop):
    """Extended cognitive loop for I/O agents."""
    
    def __init__(self, agent_id: str, home: Path):
        super().__init__(agent_id, home)
        self.io_handler = IOBodyFileHandler(home)
        
        # Load I/O-specific knowledge
        self._load_io_knowledge()
    
    def _load_io_knowledge(self):
        """Load I/O agent specific knowledge."""
        try:
            from io_agent_template.boot_rom import (
                NETWORK_PROTOCOL, USER_IO_PROTOCOL, 
                SECURITY_RULES, ROUTING_RULES
            )
            
            # Add to boot ROM
            self.boot_rom.extend([
                f"=== NETWORK PROTOCOL ===\n{NETWORK_PROTOCOL}",
                f"=== USER I/O PROTOCOL ===\n{USER_IO_PROTOCOL}",
                f"=== SECURITY RULES ===\n{SECURITY_RULES}",
                f"=== ROUTING RULES ===\n{ROUTING_RULES}"
            ])
            
            logger.info("Loaded I/O agent knowledge")
        except ImportError:
            logger.warning("I/O agent boot ROM not found, using defaults")
    
    async def observe(self) -> List[Dict[str, Any]]:
        """Extended observe for I/O agents - check special body files."""
        observations = await super().observe()
        
        # Check network responses
        network_response = await self.io_handler.check_network_file()
        if network_response:
            observations.append({
                "type": "network_response",
                "data": network_response,
                "timestamp": datetime.now()
            })
            
            # Create memory
            self.memory_manager.add_memory(
                ObservationMemoryBlock(
                    observation_type="network_response",
                    path="/home/network",
                    description=f"Network response: {network_response.get('status', 'unknown')}",
                    priority=Priority.HIGH
                )
            )
        
        # Check user messages
        user_message = await self.io_handler.check_user_io_file()
        if user_message:
            observations.append({
                "type": "user_message",
                "data": user_message,
                "timestamp": datetime.now()
            })
            
            # Create memory
            self.memory_manager.add_memory(
                ObservationMemoryBlock(
                    observation_type="user_message",
                    path="/home/user_io",
                    description=f"User message: {user_message.get('type', 'unknown')}",
                    priority=Priority.HIGH
                )
            )
        
        return observations
    
    async def decide(self, orientation: Dict[str, Any]) -> str:
        """Extended decide for I/O agents."""
        # Check if this is an I/O-specific task
        task_type = orientation.get("task_type", "")
        
        if task_type == "network_request":
            return "make_network_request"
        elif task_type == "user_interaction":
            return "send_user_response"
        elif task_type == "route_message":
            return "route_to_agent"
        else:
            # Fall back to standard decision making
            return await super().decide(orientation)
    
    async def act(self, action: str, context: Dict[str, Any]) -> Any:
        """Extended act for I/O agents."""
        if action == "make_network_request":
            # Extract request details from context
            request = context.get("network_request", {})
            request_id = await self.io_handler.make_network_request(request)
            
            return {
                "status": "pending",
                "request_id": request_id,
                "message": "Network request submitted"
            }
        
        elif action == "send_user_response":
            # Extract response details from context
            response = context.get("user_response", {})
            await self.io_handler.send_user_response(response)
            
            return {
                "status": "sent",
                "session_id": response.get("session_id"),
                "message": "Response sent to user"
            }
        
        elif action == "route_to_agent":
            # Route message to another agent
            target_agent = context.get("target_agent")
            message = context.get("message")
            
            if target_agent and message:
                # Send through standard mail system
                await self._send_message(target_agent, message)
                return {
                    "status": "routed",
                    "to": target_agent,
                    "message": "Message routed to agent"
                }
        
        else:
            # Fall back to standard actions
            return await super().act(action, context)
    
    async def _send_message(self, to_agent: str, content: Any):
        """Send a message to another agent."""
        message = {
            "from": self.agent_id,
            "to": to_agent,
            "type": "FORWARD",
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        # Generate unique message ID
        msg_id = f"{self.agent_id}_{int(datetime.now().timestamp() * 1000)}"
        msg_file = self.outbox_dir / f"{msg_id}.msg"
        
        # Write message
        msg_file.write_text(json.dumps(message, indent=2))
        logger.info(f"Routed message to {to_agent}")