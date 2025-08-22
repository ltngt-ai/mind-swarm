"""WebSocket state management for multiple clients.

This module tracks what each WebSocket client has received and manages
delta computation for efficient updates.
"""

import asyncio
import json
from typing import Dict, Any, Optional, List, Set
from datetime import datetime
from dataclasses import dataclass, field
from fastapi import WebSocket
import hashlib

from mind_swarm.utils.logging import logger
from mind_swarm.subspace.cycle_recorder import get_cycle_recorder
from mind_swarm.server.monitoring_events import get_event_emitter
from pathlib import Path


@dataclass
class ClientState:
    """State tracking for a single WebSocket client."""
    client_id: str
    websocket: WebSocket
    connected_at: datetime
    subscriptions: Set[str] = field(default_factory=set)  # Cyber names to watch
    last_event_id: Optional[str] = None
    last_cycle_numbers: Dict[str, int] = field(default_factory=dict)  # cyber -> last seen cycle
    pending_events: List[Dict[str, Any]] = field(default_factory=list)
    is_developer: bool = False
    filter_settings: Dict[str, Any] = field(default_factory=dict)
    
    def is_subscribed_to(self, cyber_name: str) -> bool:
        """Check if client is subscribed to a cyber."""
        return "*" in self.subscriptions or cyber_name in self.subscriptions


class WebSocketStateManager:
    """Manages state for multiple WebSocket clients."""
    
    def __init__(self):
        """Initialize the state manager."""
        self.clients: Dict[str, ClientState] = {}
        self.event_history: List[Dict[str, Any]] = []  # Keep last N events
        self.max_history_size = 1000
        self.event_counter = 0
        self.logger = logger
        self._lock = asyncio.Lock()
    
    async def register_client(self, websocket: WebSocket, client_id: Optional[str] = None) -> str:
        """Register a new WebSocket client.
        
        Args:
            websocket: The WebSocket connection
            client_id: Optional client ID (will generate if not provided)
            
        Returns:
            The client ID
        """
        async with self._lock:
            if not client_id:
                # Generate unique client ID
                client_id = hashlib.md5(
                    f"{id(websocket)}:{datetime.now().isoformat()}".encode()
                ).hexdigest()[:12]
            
            client = ClientState(
                client_id=client_id,
                websocket=websocket,
                connected_at=datetime.now()
            )
            
            self.clients[client_id] = client
            self.logger.info(f"Registered WebSocket client {client_id}")
            
            # Send initial state
            await self._send_initial_state(client)
            
            return client_id
    
    async def unregister_client(self, client_id: str) -> None:
        """Unregister a WebSocket client.
        
        Args:
            client_id: The client ID to unregister
        """
        async with self._lock:
            if client_id in self.clients:
                del self.clients[client_id]
                self.logger.info(f"Unregistered WebSocket client {client_id}")
    
    async def update_subscriptions(self, client_id: str, subscriptions: List[str]) -> None:
        """Update client subscriptions.
        
        Args:
            client_id: The client ID
            subscriptions: List of cyber names to subscribe to (or ["*"] for all)
        """
        async with self._lock:
            if client_id not in self.clients:
                return
            
            client = self.clients[client_id]
            client.subscriptions = set(subscriptions)
            self.logger.debug(f"Updated subscriptions for {client_id}: {subscriptions}")
    
    async def update_filter(self, client_id: str, filter_settings: Dict[str, Any]) -> None:
        """Update client filter settings.
        
        Args:
            client_id: The client ID
            filter_settings: Filter configuration
        """
        async with self._lock:
            if client_id not in self.clients:
                return
            
            client = self.clients[client_id]
            client.filter_settings = filter_settings
            self.logger.debug(f"Updated filters for {client_id}: {filter_settings}")
    
    async def broadcast_event(self, event: Dict[str, Any]) -> None:
        """Broadcast an event to all relevant clients.
        
        Args:
            event: The event to broadcast
        """
        # Add event ID and store in history
        self.event_counter += 1
        event["event_id"] = f"evt_{self.event_counter:08d}"
        
        # Add to history (bounded)
        self.event_history.append(event)
        if len(self.event_history) > self.max_history_size:
            self.event_history.pop(0)
        
        # Send to relevant clients
        disconnected = []
        for client_id, client in self.clients.items():
            try:
                # Check if client should receive this event
                if self._should_send_event(client, event):
                    await client.websocket.send_json(event)
                    client.last_event_id = event["event_id"]
                    
                    # Update cycle tracking if applicable
                    if "data" in event and "cyber" in event["data"]:
                        cyber_name = event["data"]["cyber"]
                        if "cycle_number" in event["data"]:
                            client.last_cycle_numbers[cyber_name] = event["data"]["cycle_number"]
                            
            except Exception as e:
                self.logger.warning(f"Failed to send event to {client_id}: {e}")
                disconnected.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected:
            await self.unregister_client(client_id)
    
    async def send_to_client(self, client_id: str, message: Dict[str, Any]) -> bool:
        """Send a message to a specific client.
        
        Args:
            client_id: The client ID
            message: The message to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        if client_id not in self.clients:
            return False
        
        client = self.clients[client_id]
        try:
            await client.websocket.send_json(message)
            return True
        except Exception as e:
            self.logger.warning(f"Failed to send to {client_id}: {e}")
            await self.unregister_client(client_id)
            return False
    
    async def get_client_state(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get the state of a specific client.
        
        Args:
            client_id: The client ID
            
        Returns:
            Client state dictionary or None
        """
        if client_id not in self.clients:
            return None
        
        client = self.clients[client_id]
        return {
            "client_id": client_id,
            "connected_at": client.connected_at.isoformat(),
            "subscriptions": list(client.subscriptions),
            "last_event_id": client.last_event_id,
            "last_cycle_numbers": client.last_cycle_numbers,
            "is_developer": client.is_developer,
            "filter_settings": client.filter_settings
        }
    
    async def get_all_clients(self) -> List[Dict[str, Any]]:
        """Get state of all connected clients.
        
        Returns:
            List of client state dictionaries
        """
        return [
            await self.get_client_state(client_id)
            for client_id in self.clients
        ]
    
    async def replay_events(self, client_id: str, from_event_id: Optional[str] = None,
                          from_timestamp: Optional[datetime] = None) -> None:
        """Replay events to a client from a specific point.
        
        Args:
            client_id: The client ID
            from_event_id: Start from this event ID (exclusive)
            from_timestamp: Start from this timestamp (exclusive)
        """
        if client_id not in self.clients:
            return
        
        client = self.clients[client_id]
        
        # Find starting point in history
        start_index = 0
        if from_event_id:
            for i, event in enumerate(self.event_history):
                if event.get("event_id") == from_event_id:
                    start_index = i + 1
                    break
        elif from_timestamp:
            for i, event in enumerate(self.event_history):
                event_time = datetime.fromisoformat(event.get("timestamp", ""))
                if event_time > from_timestamp:
                    start_index = i
                    break
        
        # Send events from starting point
        for event in self.event_history[start_index:]:
            if self._should_send_event(client, event):
                try:
                    await client.websocket.send_json(event)
                    client.last_event_id = event["event_id"]
                except Exception as e:
                    self.logger.warning(f"Failed to replay event to {client_id}: {e}")
                    break
    
    def _should_send_event(self, client: ClientState, event: Dict[str, Any]) -> bool:
        """Check if an event should be sent to a client.
        
        Args:
            client: The client state
            event: The event to check
            
        Returns:
            True if event should be sent
        """
        # Apply subscription filter
        if event.get("type") in ["agent_created", "agent_terminated", "system_metrics"]:
            # System-wide events go to all clients
            return True
        
        # Check cyber-specific events
        if "data" in event and "cyber" in event["data"]:
            cyber_name = event["data"]["cyber"]
            if not client.is_subscribed_to(cyber_name):
                return False
        
        # Apply type filters if configured
        if client.filter_settings.get("event_types"):
            allowed_types = client.filter_settings["event_types"]
            if event.get("type") not in allowed_types:
                return False
        
        # Apply stage filters if configured
        if client.filter_settings.get("stages"):
            allowed_stages = client.filter_settings["stages"]
            if "data" in event and "stage" in event["data"]:
                if event["data"]["stage"] not in allowed_stages:
                    return False
        
        # Apply minimum severity filter for errors/warnings
        if client.filter_settings.get("min_severity"):
            # This would need event severity levels to be implemented
            pass
        
        return True
    
    async def _send_initial_state(self, client: ClientState) -> None:
        """Send initial state to a newly connected client.
        
        Args:
            client: The client state
        """
        try:
            # Send connection confirmation with client info
            await client.websocket.send_json({
                "type": "connection_established",
                "data": {
                    "client_id": client.client_id,
                    "server_time": datetime.now().isoformat(),
                    "event_history_size": len(self.event_history)
                },
                "timestamp": datetime.now().isoformat()
            })
            
            # Optionally replay recent events
            if self.event_history:
                # Send last 10 events as catch-up
                for event in self.event_history[-10:]:
                    if self._should_send_event(client, event):
                        await client.websocket.send_json(event)
                        client.last_event_id = event["event_id"]
                        
        except Exception as e:
            self.logger.error(f"Failed to send initial state to {client.client_id}: {e}")
    
    async def handle_client_message(self, client_id: str, message: Dict[str, Any]) -> None:
        """Handle a message from a client.
        
        Args:
            client_id: The client ID
            message: The message from the client
        """
        if client_id not in self.clients:
            return
        
        msg_type = message.get("type")
        
        if msg_type == "subscribe":
            # Update subscriptions
            subscriptions = message.get("cybers", ["*"])
            await self.update_subscriptions(client_id, subscriptions)
            
            # Send confirmation
            await self.send_to_client(client_id, {
                "type": "subscription_updated",
                "data": {"subscriptions": subscriptions},
                "timestamp": datetime.now().isoformat()
            })
            
        elif msg_type == "filter":
            # Update filters
            filters = message.get("filters", {})
            await self.update_filter(client_id, filters)
            
            # Send confirmation
            await self.send_to_client(client_id, {
                "type": "filter_updated",
                "data": {"filters": filters},
                "timestamp": datetime.now().isoformat()
            })
            
        elif msg_type == "replay":
            # Replay events from a point
            from_event = message.get("from_event_id")
            from_time = message.get("from_timestamp")
            if from_time:
                from_time = datetime.fromisoformat(from_time)
            await self.replay_events(client_id, from_event, from_time)
            
        elif msg_type == "ping":
            # Respond to ping
            await self.send_to_client(client_id, {
                "type": "pong",
                "timestamp": datetime.now().isoformat()
            })
            
        elif msg_type == "get_current_reflection":
            # Get current reflection for a cyber
            await self._handle_get_current_reflection(client_id, message)
            
        elif msg_type == "get_cycle_data":
            # Get data for a specific cycle
            await self._handle_get_cycle_data(client_id, message)
            
        elif msg_type == "get_cycles":
            # List cycles for a cyber
            await self._handle_get_cycles(client_id, message)
    
    async def _handle_get_current_reflection(self, client_id: str, message: Dict[str, Any]) -> None:
        """Handle request for current reflection of a cyber."""
        cyber_name = message.get("cyber")
        if not cyber_name:
            await self.send_to_client(client_id, {
                "type": "error",
                "data": {"error": "cyber name required"},
                "request_id": message.get("request_id"),
                "timestamp": datetime.now().isoformat()
            })
            return
        
        try:
            # Get subspace root from environment or default
            import os
            subspace_root = Path(os.environ.get("SUBSPACE_ROOT", "../subspace"))
            recorder = get_cycle_recorder(subspace_root, event_emitter=get_event_emitter())
            
            # Try to get reflection from memory first (most current)
            reflection_file = Path(os.environ.get("SUBSPACE_ROOT", "../subspace")) / "cybers" / cyber_name / ".internal" / "memory" / "reflection_on_last_cycle.json"
            reflection = None
            cycle_data = None
            
            if reflection_file.exists():
                try:
                    import json
                    with open(reflection_file, 'r') as f:
                        reflection_data = json.load(f)
                        # Extract insights which is the main reflection text
                        if isinstance(reflection_data, dict):
                            reflection = reflection_data.get("insights", reflection_data)
                        else:
                            reflection = reflection_data
                except:
                    pass
            
            # Fallback to cycle data if no memory file
            if not reflection:
                cycle_data = await recorder.get_current_cycle(cyber_name)
                if cycle_data and "reflection_from_last_cycle" in cycle_data:
                    reflection = cycle_data["reflection_from_last_cycle"]
                    if isinstance(reflection, dict):
                        reflection = reflection.get("insights", reflection)
                elif cycle_data and "reflection" in cycle_data:
                    reflection_stage = cycle_data.get("reflection", {})
                    reflection = reflection_stage.get("stage_output", {})
                    if isinstance(reflection, dict):
                        reflection = reflection.get("insights", reflection)
            
            # Get cycle number if we don't have cycle_data yet
            if not cycle_data:
                cycle_data = await recorder.get_current_cycle(cyber_name)
            
            await self.send_to_client(client_id, {
                "type": "current_reflection",
                "data": {
                    "cyber": cyber_name,
                    "reflection": reflection,
                    "cycle_number": cycle_data.get("metadata", {}).get("cycle_number") if cycle_data else None
                },
                "request_id": message.get("request_id"),
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Failed to get current reflection for {cyber_name}: {e}")
            await self.send_to_client(client_id, {
                "type": "error",
                "data": {"error": str(e)},
                "request_id": message.get("request_id"),
                "timestamp": datetime.now().isoformat()
            })
    
    async def _handle_get_cycle_data(self, client_id: str, message: Dict[str, Any]) -> None:
        """Handle request for specific cycle data."""
        cyber_name = message.get("cyber")
        cycle_number = message.get("cycle_number")
        
        if not cyber_name or cycle_number is None:
            await self.send_to_client(client_id, {
                "type": "error",
                "data": {"error": "cyber name and cycle_number required"},
                "request_id": message.get("request_id"),
                "timestamp": datetime.now().isoformat()
            })
            return
        
        try:
            import os
            subspace_root = Path(os.environ.get("SUBSPACE_ROOT", "../subspace"))
            recorder = get_cycle_recorder(subspace_root, event_emitter=get_event_emitter())
            
            cycle_data = await recorder.get_cycle_data(cyber_name, cycle_number)
            
            await self.send_to_client(client_id, {
                "type": "cycle_data",
                "data": {
                    "cyber": cyber_name,
                    "cycle_number": cycle_number,
                    "data": cycle_data
                },
                "request_id": message.get("request_id"),
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Failed to get cycle data for {cyber_name}: {e}")
            await self.send_to_client(client_id, {
                "type": "error",
                "data": {"error": str(e)},
                "request_id": message.get("request_id"),
                "timestamp": datetime.now().isoformat()
            })
    
    async def _handle_get_cycles(self, client_id: str, message: Dict[str, Any]) -> None:
        """Handle request for list of cycles."""
        cyber_name = message.get("cyber")
        limit = message.get("limit", 100)
        
        if not cyber_name:
            await self.send_to_client(client_id, {
                "type": "error",
                "data": {"error": "cyber name required"},
                "request_id": message.get("request_id"),
                "timestamp": datetime.now().isoformat()
            })
            return
        
        try:
            import os
            subspace_root = Path(os.environ.get("SUBSPACE_ROOT", "../subspace"))
            recorder = get_cycle_recorder(subspace_root, event_emitter=get_event_emitter())
            
            cycles = await recorder.list_cycles(cyber_name, limit)
            
            await self.send_to_client(client_id, {
                "type": "cycles_list",
                "data": {
                    "cyber": cyber_name,
                    "cycles": cycles
                },
                "request_id": message.get("request_id"),
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Failed to list cycles for {cyber_name}: {e}")
            await self.send_to_client(client_id, {
                "type": "error",
                "data": {"error": str(e)},
                "request_id": message.get("request_id"),
                "timestamp": datetime.now().isoformat()
            })


# Global instance for easy access
_ws_state_manager: Optional[WebSocketStateManager] = None


def get_ws_state_manager() -> WebSocketStateManager:
    """Get the global WebSocket state manager instance.
    
    Returns:
        The global WebSocketStateManager instance
    """
    global _ws_state_manager
    if _ws_state_manager is None:
        _ws_state_manager = WebSocketStateManager()
    return _ws_state_manager