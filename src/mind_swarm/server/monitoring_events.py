"""Monitoring event emitter for Mind-Swarm UI.

This module provides event emission functionality for the monitoring interface.
"""

from typing import Dict, Any, Optional, List
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
        self.cyber_cycles: Dict[str, int] = {}  # Track current cycle per cyber
        
    async def emit_agent_state_changed(self, cyber_name: str, old_state: str, new_state: str):
        """Emit an Cyber state change event."""
        if not self.server:
            return
            
        await self.server._broadcast_event({
            "type": "agent_state_changed",
            "data": {
                "name": cyber_name,
                "old_state": old_state,
                "new_state": new_state
            },
            "timestamp": datetime.now().isoformat()
        })
        logger.debug(f"Emitted agent_state_changed: {cyber_name} {old_state} -> {new_state}")
        
    async def emit_agent_thinking(self, cyber_name: str, thought: str, token_count: Optional[int] = None):
        """Emit an Cyber thinking event."""
        if not self.server:
            return
            
        data = {
            "name": cyber_name,
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
        
    async def emit_file_activity(self, cyber_name: str, action: str, path: str):
        """Emit a file activity event."""
        if not self.server:
            return
            
        await self.server._broadcast_event({
            "type": "file_activity",
            "data": {
                "cyber": cyber_name,
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
    
    async def emit_cycle_started(self, cyber_name: str, cycle_number: int):
        """Emit cycle started event."""
        if not self.server:
            return
        
        self.cyber_cycles[cyber_name] = cycle_number
        
        await self.server._broadcast_event({
            "type": "cycle_started",
            "data": {
                "cyber": cyber_name,
                "cycle_number": cycle_number
            },
            "timestamp": datetime.now().isoformat()
        })
        logger.debug(f"Emitted cycle_started: {cyber_name} cycle {cycle_number}")
    
    async def emit_cycle_completed(self, cyber_name: str, cycle_number: int, duration_ms: int):
        """Emit cycle completed event."""
        if not self.server:
            return
        
        await self.server._broadcast_event({
            "type": "cycle_completed",
            "data": {
                "cyber": cyber_name,
                "cycle_number": cycle_number,
                "duration_ms": duration_ms
            },
            "timestamp": datetime.now().isoformat()
        })
        logger.debug(f"Emitted cycle_completed: {cyber_name} cycle {cycle_number}")
    
    async def emit_stage_started(self, cyber_name: str, cycle_number: int, stage: str):
        """Emit stage started event."""
        if not self.server:
            return
        
        await self.server._broadcast_event({
            "type": "stage_started",
            "data": {
                "cyber": cyber_name,
                "cycle_number": cycle_number,
                "stage": stage
            },
            "timestamp": datetime.now().isoformat()
        })
        logger.debug(f"Emitted stage_started: {cyber_name} cycle {cycle_number} stage {stage}")
    
    async def emit_stage_completed(self, cyber_name: str, cycle_number: int, stage: str, 
                                  stage_data: Optional[Dict[str, Any]] = None):
        """Emit stage completed event with results."""
        if not self.server:
            return
        
        await self.server._broadcast_event({
            "type": "stage_completed",
            "data": {
                "cyber": cyber_name,
                "cycle_number": cycle_number,
                "stage": stage,
                "stage_data": stage_data or {}
            },
            "timestamp": datetime.now().isoformat()
        })
        logger.debug(f"Emitted stage_completed: {cyber_name} cycle {cycle_number} stage {stage}")
    
    async def emit_memory_changed(self, cyber_name: str, operation: str, memory_info: Dict[str, Any]):
        """Emit memory system change event."""
        if not self.server:
            return
        
        cycle_number = self.cyber_cycles.get(cyber_name, 0)
        
        await self.server._broadcast_event({
            "type": "memory_changed",
            "data": {
                "cyber": cyber_name,
                "cycle_number": cycle_number,
                "operation": operation,  # add, remove, update
                "memory_info": memory_info
            },
            "timestamp": datetime.now().isoformat()
        })
    
    async def emit_message_activity(self, from_cyber: str, to_cyber: str, 
                                   message_type: str, content: Dict[str, Any]):
        """Emit message activity event with full content."""
        if not self.server:
            return
        
        from_cycle = self.cyber_cycles.get(from_cyber, 0)
        
        await self.server._broadcast_event({
            "type": "message_activity",
            "data": {
                "from": from_cyber,
                "to": to_cyber,
                "from_cycle": from_cycle,
                "message_type": message_type,
                "content": content
            },
            "timestamp": datetime.now().isoformat()
        })
        logger.debug(f"Emitted message_activity: {from_cyber} -> {to_cyber}")
    
    async def emit_brain_thinking(self, cyber_name: str, stage: str, 
                                 request: Dict[str, Any], response: Optional[Dict[str, Any]] = None):
        """Emit brain thinking event with stage context."""
        if not self.server:
            return
        
        cycle_number = self.cyber_cycles.get(cyber_name, 0)
        
        await self.server._broadcast_event({
            "type": "brain_thinking",
            "data": {
                "cyber": cyber_name,
                "cycle_number": cycle_number,
                "stage": stage,
                "request": request,
                "response": response
            },
            "timestamp": datetime.now().isoformat()
        })
    
    async def emit_file_operation(self, cyber_name: str, operation: str, 
                                 path: str, details: Optional[Dict[str, Any]] = None):
        """Emit detailed file operation event."""
        if not self.server:
            return
        
        cycle_number = self.cyber_cycles.get(cyber_name, 0)
        
        await self.server._broadcast_event({
            "type": "file_operation",
            "data": {
                "cyber": cyber_name,
                "cycle_number": cycle_number,
                "operation": operation,  # read, write, create, delete
                "path": path,
                "details": details or {}
            },
            "timestamp": datetime.now().isoformat()
        })
    
    async def emit_token_usage(self, cyber_name: str, stage: str, tokens: Dict[str, int]):
        """Emit token usage statistics."""
        if not self.server:
            return
        
        cycle_number = self.cyber_cycles.get(cyber_name, 0)
        
        await self.server._broadcast_event({
            "type": "token_usage",
            "data": {
                "cyber": cyber_name,
                "cycle_number": cycle_number,
                "stage": stage,
                "tokens": tokens
            },
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