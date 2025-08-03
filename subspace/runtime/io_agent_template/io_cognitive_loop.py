"""Cognitive loop for I/O Gateway agents."""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

from .base_code_template.cognitive_loop import CognitiveLoop
from .base_code_template.memory import ObservationMemoryBlock, TaskMemoryBlock, Priority

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
            from .boot_rom import (
                NETWORK_PROTOCOL, USER_IO_PROTOCOL, 
                SECURITY_RULES, ROUTING_RULES
            )
            
            # Store I/O specific knowledge
            self.io_knowledge = {
                "network_protocol": NETWORK_PROTOCOL,
                "user_io_protocol": USER_IO_PROTOCOL,
                "security_rules": SECURITY_RULES,
                "routing_rules": ROUTING_RULES
            }
            
            logger.info("Loaded I/O agent knowledge")
        except ImportError:
            logger.warning("I/O agent boot ROM not found, using defaults")
            self.io_knowledge = {
                "network_protocol": "Handle network requests through /home/network body file",
                "user_io_protocol": "Handle user interactions through /home/user_io body file",
                "security_rules": "Validate all external requests for safety",
                "routing_rules": "Route messages between internal agents and external systems"
            }
    
    async def observe(self) -> Optional[Dict[str, Any]]:
        """Extended observe for I/O agents - check special body files."""
        # First check standard observations (messages, etc)
        observation = await super().observe()
        if observation:
            return observation
        
        # Check network responses
        network_response = await self.io_handler.check_network_file()
        if network_response:
            # Create memory
            self.memory_manager.add_memory(
                ObservationMemoryBlock(
                    observation_type="network_response",
                    path="/home/network",
                    description=f"Network response: {network_response.get('status', 'unknown')}",
                    priority=Priority.HIGH
                )
            )
            
            return {
                "type": "network_response",
                "data": network_response,
                "timestamp": datetime.now().isoformat()
            }
        
        # Check user messages
        user_message = await self.io_handler.check_user_io_file()
        if user_message:
            # Create memory
            self.memory_manager.add_memory(
                ObservationMemoryBlock(
                    observation_type="user_message",
                    path="/home/user_io",
                    description=f"User message: {user_message.get('type', 'unknown')}",
                    priority=Priority.HIGH
                )
            )
            
            return {
                "type": "user_message",
                "data": user_message,
                "timestamp": datetime.now().isoformat()
            }
        
        return None
    
    async def decide(self, orientation: Dict[str, Any]) -> Dict[str, Any]:
        """Extended decide for I/O agents."""
        # Check if this is an I/O-specific task
        task_type = orientation.get("task_type", "")
        observation = orientation.get("observation", {})
        
        if observation.get("type") == "network_response":
            return {
                "action": "handle_network_response",
                "reason": "Process network response from body file",
                "decision_text": "Handle network response"
            }
        elif observation.get("type") == "user_message":
            return {
                "action": "handle_user_message",
                "reason": "Process user message from body file",
                "decision_text": "Handle user interaction"
            }
        
        # Check if this is a network-related request
        question = orientation.get("question", "").lower()
        request = orientation.get("request", "").lower()
        all_text = f"{question} {request}"
        
        # Keywords that indicate network requests
        network_keywords = ["fetch", "get", "post", "http", "https", "url", "website", "webpage", "api", "download"]
        
        if any(keyword in all_text for keyword in network_keywords):
            # This looks like a network request
            return {
                "action": "make_network_request",
                "reason": "User is asking to fetch content from the web",
                "decision_text": "Make a network request"
            }
        
        # Fall back to standard decision making
        return await super().decide(orientation)
    
    async def act(self, observation: Dict[str, Any], 
                  orientation: Dict[str, Any], 
                  decision: Dict[str, Any]):
        """Extended act for I/O agents."""
        action = decision.get("action", "")
        
        if action == "handle_network_response":
            # Process network response
            response_data = observation.get("data", {})
            original_request = response_data.get("original_request", {})
            
            # Log the response
            logger.info(f"Network response: {response_data.get('status')} for {original_request.get('url')}")
            
            # Could route response back to requesting agent if needed
            
        elif action == "handle_user_message":
            # Process user message
            user_data = observation.get("data", {})
            message_type = user_data.get("type", "unknown")
            
            logger.info(f"User message type: {message_type}")
            
            # Handle different message types
            if message_type == "request":
                # Process user request
                await self._handle_user_request(user_data)
            elif message_type == "query":
                # Route query to appropriate agent
                await self._route_user_query(user_data)
        
        elif action == "make_network_request":
            # Extract URL from the request
            question = observation.get("question", "")
            command = observation.get("command", "")
            full_text = f"{question} {command}"
            
            # Parse the URL from the request
            import re
            url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
            urls = re.findall(url_pattern, full_text)
            
            if not urls:
                # Try to find common domain patterns
                domain_pattern = r'(?:www\.)?([a-zA-Z0-9-]+\.(?:com|org|net|edu|gov|co\.uk|io))'
                domains = re.findall(domain_pattern, full_text)
                if domains:
                    urls = [f"https://{domain}" if not domain.startswith('www.') else f"https://{domain}" for domain in domains]
            
            if urls:
                url = urls[0]  # Take the first URL found
                logger.info(f"Making network request to {url}")
                
                # Create network request
                network_request = {
                    "method": "GET",
                    "url": url,
                    "headers": {
                        "User-Agent": "Mind-Swarm-IO-Agent/1.0"
                    }
                }
                
                # Write request to network body file
                request_id = await self.io_handler.make_network_request(network_request)
                
                # Create a task memory for tracking
                self.memory_manager.add_memory(
                    TaskMemoryBlock(
                        task_type="network_request",
                        description=f"Fetching {url}",
                        status="pending",
                        priority=Priority.HIGH,
                        metadata={"request_id": request_id, "url": url}
                    )
                )
                
                logger.info(f"Network request {request_id} submitted")
            else:
                logger.warning("No URL found in request")
        
        else:
            # Fall back to standard actions
            await super().act(observation, orientation, decision)
    
    async def _handle_user_request(self, user_data: Dict[str, Any]):
        """Handle a user request."""
        # Example: validate and process request
        request_type = user_data.get("request_type")
        
        if request_type == "network":
            # Make network request on behalf of user
            network_request = {
                "method": user_data.get("method", "GET"),
                "url": user_data.get("url"),
                "headers": user_data.get("headers", {})
            }
            request_id = await self.io_handler.make_network_request(network_request)
            logger.info(f"Made network request {request_id} for user")
    
    async def _route_user_query(self, user_data: Dict[str, Any]):
        """Route user query to appropriate agent."""
        query = user_data.get("query", "")
        target_agent = user_data.get("target_agent")
        
        if target_agent:
            # Send to specific agent
            await self._send_message(target_agent, {
                "type": "USER_QUERY",
                "query": query,
                "from_user": user_data.get("user_id"),
                "session_id": user_data.get("session_id")
            })
    
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