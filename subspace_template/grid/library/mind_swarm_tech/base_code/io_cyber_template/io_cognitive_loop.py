"""Cognitive loop for I/O Gateway Cybers."""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

from .base_code_template.cognitive_loop import CognitiveLoop
from .base_code_template.memory import ObservationMemoryBlock, Priority
from .base_code_template.actions import Action, ActionResult, ActionStatus, action_registry
from .io_actions import register_io_actions
from .base_code_template.memory_actions import register_memory_actions
from .base_code_template.goal_actions import register_goal_actions

logger = logging.getLogger("Cyber.io_cognitive")


class IOBodyFileHandler:
    """Handles special body files for I/O Cybers."""
    
    def __init__(self, personal_dir: Path):
        self.personal_dir = personal_dir
        self.network_file = personal_dir / "network"
        self.user_io_file = personal_dir / "user_io"
        
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
    """Extended cognitive loop for I/O Cybers."""
    
    def __init__(self, cyber_id: str, personal: Path):
        super().__init__(cyber_id, personal, cyber_type='io_cyber')
        self.io_handler = IOBodyFileHandler(personal)
        
        # Register base actions first (memory and goals)
        register_memory_actions(action_registry)
        register_goal_actions(action_registry)
        
        # Then register I/O specific actions
        register_io_actions(action_registry)
        
        # Load I/O-specific knowledge
        self._load_io_knowledge()
    
    def _load_io_knowledge(self):
        """Load I/O Cyber specific knowledge."""
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
            
            logger.info("Loaded I/O Cyber knowledge")
        except ImportError:
            logger.warning("I/O Cyber boot ROM not found, using defaults")
            self.io_knowledge = {
                "network_protocol": "Handle network requests through /personal/network body file",
                "user_io_protocol": "Handle user interactions through /personal/user_io body file",
                "security_rules": "Validate all external requests for safety",
                "routing_rules": "Route messages between internal Cybers and external systems"
            }
    
    async def observe(self) -> Optional[Dict[str, Any]]:
        """Extended observe for I/O Cybers - check special body files."""
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
                    path="/personal/network",
                    message=f"Network response: {network_response.get('status', 'unknown')}",
                    cycle_count=self.cycle_count,
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
                    path="/personal/user_io",
                    message=f"User message: {user_message.get('type', 'unknown')}",
                    cycle_count=self.cycle_count,
                    priority=Priority.HIGH
                )
            )
            
            return {
                "type": "user_message",
                "data": user_message,
                "timestamp": datetime.now().isoformat()
            }
        
        return None
    
    async def decide(self, orientation: Dict[str, Any]) -> List[Action]:
        """Extended decide for I/O Cybers."""
        # Check if this is an I/O-specific task
        observation = orientation.get("observation", {})
        obs_type = observation.get("type", "")
        
        # Handle network response
        if obs_type == "network_response":
            actions = []
            
            # Process the response
            process_action = action_registry.create_action('io_gateway', 'process_network_response')
            if process_action:
                process_action.with_params(response_data=observation.get("data", {}))
                actions.append(process_action)
            
            # Send response to requester
            send_action = action_registry.create_action('io_gateway', 'send_message')
            if send_action:
                from_agent = orientation.get("from", "user")
                send_action.with_params(
                    to=from_agent,
                    type="RESPONSE",
                    content=""  # Will be filled based on processed response
                )
                actions.append(send_action)
            
            return actions
        
        # Handle user message
        elif obs_type == "user_message":
            # For now, use standard decision making
            return await super().decide(orientation)
        
        # Check if this is a network-related request
        content = orientation.get("content", "").lower()
        question = orientation.get("question", "").lower()
        all_text = f"{content} {question}"
        
        # Keywords that indicate network requests
        network_keywords = ["fetch", "get", "post", "http", "https", "url", "website", "webpage", "api", "download"]
        
        if any(keyword in all_text for keyword in network_keywords):
            # This is a network request
            actions = []
            
            # Make the network request
            network_action = action_registry.create_action('io_gateway', 'make_network_request')
            if network_action:
                network_action.with_params(url=None)  # Will be extracted from text
                actions.append(network_action)
            
            # Wait for response
            wait_action = action_registry.create_action('io_gateway', 'wait')
            if wait_action:
                wait_action.with_params(duration=0.5, condition="network_response")
                actions.append(wait_action)
            
            # Don't finish yet - we need to wait for the response
            return actions
        
        # Fall back to standard decision making
        return await super().decide(orientation)
    
    
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
        """Route user query to appropriate Cyber."""
        query = user_data.get("query", "")
        target_agent = user_data.get("target_agent")
        
        if target_agent:
            # Send to specific Cyber
            await self._send_message(target_agent, {
                "type": "USER_QUERY",
                "query": query,
                "from_user": user_data.get("user_id"),
                "session_id": user_data.get("session_id")
            })
    
    async def _send_message(self, to_agent: str, content: Any):
        """Send a message to another Cyber."""
        message = {
            "from": self.cyber_id,
            "to": to_agent,
            "type": "FORWARD",
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        # Generate unique message ID
        msg_id = f"{self.cyber_id}_{int(datetime.now().timestamp() * 1000)}"
        msg_file = self.outbox_dir / f"{msg_id}.msg"
        
        # Write message
        msg_file.write_text(json.dumps(message, indent=2))
        logger.info(f"Routed message to {to_agent}")