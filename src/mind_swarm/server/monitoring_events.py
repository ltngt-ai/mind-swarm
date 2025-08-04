"""Monitoring event emitter for Mind-Swarm UI.

This module provides event emission functionality for the monitoring interface.
"""

from typing import Dict, Any, Optional
from datetime import datetime

from mind_swarm.utils.logging import logger


class MonitoringEventEmitter:
    """Emits monitoring events via websocket."""
    
    def __init__(self, server=None):
        """Initialize the event emitter.
        
        Args:
            server: Reference to MindSwarmServer instance
        """
        self.server = server
        
    async def emit_agent_state_changed(self, agent_name: str, old_state: str, new_state: str):
        """Emit an agent state change event."""
        if not self.server:
            return
            
        await self.server._broadcast_event({
            "type": "agent_state_changed",
            "data": {
                "name": agent_name,
                "old_state": old_state,
                "new_state": new_state
            },
            "timestamp": datetime.now().isoformat()
        })
        logger.debug(f"Emitted agent_state_changed: {agent_name} {old_state} -> {new_state}")
        
    async def emit_agent_thinking(self, agent_name: str, thought: str, token_count: Optional[int] = None):
        """Emit an agent thinking event."""
        if not self.server:
            return
            
        data = {
            "name": agent_name,
            "thought": thought[:200] + "..." if len(thought) > 200 else thought  # Truncate long thoughts
        }
        if token_count is not None:
            data["token_count"] = token_count
            
        await self.server._broadcast_event({
            "type": "agent_thinking",
            "data": data,
            "timestamp": datetime.now().isoformat()
        })
        
    async def emit_message_sent(self, from_agent: str, to_agent: str, subject: str):
        """Emit a message sent event."""
        if not self.server:
            return
            
        await self.server._broadcast_event({
            "type": "message_sent",
            "data": {
                "from": from_agent,
                "to": to_agent,
                "subject": subject
            },
            "timestamp": datetime.now().isoformat()
        })
        logger.debug(f"Emitted message_sent: {from_agent} -> {to_agent}: {subject}")
        
    async def emit_file_activity(self, agent_name: str, action: str, path: str):
        """Emit a file activity event."""
        if not self.server:
            return
            
        await self.server._broadcast_event({
            "type": "file_activity",
            "data": {
                "agent": agent_name,
                "action": action,  # read, write, create, delete
                "path": path
            },
            "timestamp": datetime.now().isoformat()
        })
        
    async def emit_system_metrics(self, metrics: Dict[str, Any]):
        """Emit system metrics update."""
        if not self.server:
            return
            
        await self.server._broadcast_event({
            "type": "system_metrics",
            "data": metrics,
            "timestamp": datetime.now().isoformat()
        })


# Global event emitter instance
_event_emitter: Optional[MonitoringEventEmitter] = None


def get_event_emitter() -> MonitoringEventEmitter:
    """Get the global event emitter instance."""
    global _event_emitter
    if _event_emitter is None:
        _event_emitter = MonitoringEventEmitter()
    return _event_emitter


def set_server_reference(server):
    """Set the server reference for the event emitter."""
    emitter = get_event_emitter()
    emitter.server = server