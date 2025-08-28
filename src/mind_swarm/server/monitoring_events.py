"""Monitoring event emitter for Mind-Swarm UI.

This module provides event emission functionality for the monitoring interface.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime

from mind_swarm.utils.logging import logger
from mind_swarm.server.schemas.events import make_event


class MonitoringEventEmitter:
    """Emits monitoring events via websocket."""
    
    def __init__(self, server=None):
        """Initialize the event emitter.
        
        Args:
            server: Reference to MindSwarmServer instance
        """
        self.server = server
        self.cyber_cycles: Dict[str, int] = {}  # Track current cycle per cyber
        
    async def emit_agent_state_changed(self, cyber_name: str, old_state: str, new_state: str):
        """Emit an Cyber state change event."""
        if not self.server:
            return
            
        event = make_event(
            "agent_state_changed",
            {
                "name": cyber_name,
                "old_state": old_state,
                "new_state": new_state,
            },
        )
        await self.server._broadcast_event(event)
        logger.debug(f"Emitted agent_state_changed: {cyber_name} {old_state} -> {new_state}")
        
    async def emit_agent_thinking(self, cyber_name: str, thought: str, token_count: Optional[int] = None):
        """Emit an Cyber thinking event."""
        if not self.server:
            return
            
        data = {
            "name": cyber_name,
            "thought": thought[:200] + "..." if len(thought) > 200 else thought,
        }
        if token_count is not None:
            data["token_count"] = token_count
        event = make_event("agent_thinking", data)
        await self.server._broadcast_event(event)
        
    async def emit_message_sent(self, from_agent: str, to_agent: str, subject: str):
        """Emit a message sent event."""
        if not self.server:
            return
            
        event = make_event(
            "message_sent",
            {"from": from_agent, "to": to_agent, "subject": subject},
        )
        await self.server._broadcast_event(event)
        logger.debug(f"Emitted message_sent: {from_agent} -> {to_agent}: {subject}")
        
    async def emit_file_activity(self, cyber_name: str, action: str, path: str):
        """Emit a file activity event."""
        if not self.server:
            return
            
        event = make_event(
            "file_activity",
            {"cyber": cyber_name, "action": action, "path": path},
        )
        await self.server._broadcast_event(event)
        
    async def emit_system_metrics(self, metrics: Dict[str, Any]):
        """Emit system metrics update."""
        if not self.server:
            return
            
        event = make_event("system_metrics", metrics)
        await self.server._broadcast_event(event)
    
    async def emit_cycle_started(self, cyber_name: str, cycle_number: int):
        """Emit cycle started event."""
        if not self.server:
            return
        
        self.cyber_cycles[cyber_name] = cycle_number
        
        event = make_event(
            "cycle_started",
            {"cyber": cyber_name, "cycle_number": cycle_number},
        )
        await self.server._broadcast_event(event)
        logger.debug(f"Emitted cycle_started: {cyber_name} cycle {cycle_number}")
    
    async def emit_cycle_completed(self, cyber_name: str, cycle_number: int, duration_ms: int):
        """Emit cycle completed event."""
        if not self.server:
            return
        
        event = make_event(
            "cycle_completed",
            {
                "cyber": cyber_name,
                "cycle_number": cycle_number,
                "duration_ms": duration_ms,
            },
        )
        await self.server._broadcast_event(event)
        logger.debug(f"Emitted cycle_completed: {cyber_name} cycle {cycle_number}")
    
    async def emit_stage_started(self, cyber_name: str, cycle_number: int, stage: str):
        """Emit stage started event."""
        if not self.server:
            return
        
        event = make_event(
            "stage_started",
            {"cyber": cyber_name, "cycle_number": cycle_number, "stage": stage},
        )
        await self.server._broadcast_event(event)
        logger.debug(f"Emitted stage_started: {cyber_name} cycle {cycle_number} stage {stage}")
    
    async def emit_stage_completed(self, cyber_name: str, cycle_number: int, stage: str, 
                                  stage_data: Optional[Dict[str, Any]] = None):
        """Emit stage completed event with results."""
        if not self.server:
            return
        
        event = make_event(
            "stage_completed",
            {
                "cyber": cyber_name,
                "cycle_number": cycle_number,
                "stage": stage,
                "stage_data": stage_data or {},
            },
        )
        await self.server._broadcast_event(event)
        logger.debug(f"Emitted stage_completed: {cyber_name} cycle {cycle_number} stage {stage}")
    
    async def emit_memory_changed(self, cyber_name: str, operation: str, memory_info: Dict[str, Any]):
        """Emit memory system change event."""
        if not self.server:
            return
        
        cycle_number = self.cyber_cycles.get(cyber_name, 0)
        
        event = make_event(
            "memory_changed",
            {
                "cyber": cyber_name,
                "cycle_number": cycle_number,
                "operation": operation,
                "memory_info": memory_info,
            },
        )
        await self.server._broadcast_event(event)
    
    async def emit_message_activity(self, from_cyber: str, to_cyber: str, 
                                   message_type: str, content: Dict[str, Any]):
        """Emit message activity event with full content."""
        if not self.server:
            return
        
        from_cycle = self.cyber_cycles.get(from_cyber, 0)
        
        event = make_event(
            "message_activity",
            {
                "from": from_cyber,
                "to": to_cyber,
                "from_cycle": from_cycle,
                "message_type": message_type,
                "content": content,
            },
        )
        await self.server._broadcast_event(event)
        logger.debug(f"Emitted message_activity: {from_cyber} -> {to_cyber}")
    
    async def emit_brain_thinking(self, cyber_name: str, stage: str, 
                                 request: Dict[str, Any], response: Optional[Dict[str, Any]] = None):
        """Emit brain thinking event with stage context."""
        if not self.server:
            return
        
        cycle_number = self.cyber_cycles.get(cyber_name, 0)
        
        event = make_event(
            "brain_thinking",
            {
                "cyber": cyber_name,
                "cycle_number": cycle_number,
                "stage": stage,
                "request": request,
                "response": response,
            },
        )
        await self.server._broadcast_event(event)
    
    async def emit_file_operation(self, cyber_name: str, operation: str, 
                                 path: str, details: Optional[Dict[str, Any]] = None):
        """Emit detailed file operation event."""
        if not self.server:
            return
        
        cycle_number = self.cyber_cycles.get(cyber_name, 0)
        
        event = make_event(
            "file_operation",
            {
                "cyber": cyber_name,
                "cycle_number": cycle_number,
                "operation": operation,
                "path": path,
                "details": details or {},
            },
        )
        await self.server._broadcast_event(event)
    
    async def emit_token_usage(self, cyber_name: str, stage: str, tokens: Dict[str, int]):
        """Emit token usage statistics."""
        if not self.server:
            return
        
        cycle_number = self.cyber_cycles.get(cyber_name, 0)
        
        event = make_event(
            "token_usage",
            {
                "cyber": cyber_name,
                "cycle_number": cycle_number,
                "stage": stage,
                "tokens": tokens,
            },
        )
        await self.server._broadcast_event(event)


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
