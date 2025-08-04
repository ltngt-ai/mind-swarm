"""Brain activity monitor for WebSocket events.

This module monitors agent brain activity and emits events for visualization.
"""

import json
import time
from typing import Optional, Dict, Any
from pathlib import Path

from mind_swarm.utils.logging import logger

# Import monitoring events if available
try:
    from mind_swarm.server.monitoring_events import get_event_emitter
    _has_monitoring = True
except ImportError:
    _has_monitoring = False


class BrainMonitor:
    """Monitors agent brain activity and emits events."""
    
    def __init__(self):
        """Initialize the brain monitor."""
        self.logger = logger
        self._pending_requests: Dict[str, Dict[str, Any]] = {}
        
    async def on_brain_request(self, agent_id: str, request_text: str):
        """Called when an agent makes a brain request.
        
        Args:
            agent_id: The agent making the request
            request_text: The thinking request text
        """
        if not _has_monitoring:
            return
            
        try:
            # Parse and store the request for matching with response
            request_text = request_text.split("<<<END_THOUGHT>>>")[0].strip()
            request_data = json.loads(request_text)
            
            # Store the signature info for when we get the response
            self._pending_requests[agent_id] = {
                'signature': request_data.get('signature', {}),
                'task': request_data.get('signature', {}).get('task', 'Thinking'),
                'display_field': request_data.get('signature', {}).get('display_field', None),
                'timestamp': time.time()
            }
            
            self.logger.debug(f"Stored brain request from {agent_id}, display_field: {self._pending_requests[agent_id].get('display_field')}")
            
        except Exception as e:
            self.logger.debug(f"Failed to parse brain request: {e}")
    
    async def on_brain_response(self, agent_id: str, response_text: str):
        """Called when an agent receives a brain response.
        
        Args:
            agent_id: The agent receiving the response
            response_text: The response text
        """
        if not _has_monitoring:
            return
            
        try:
            # Get the pending request info
            request_info = self._pending_requests.get(agent_id)
            if not request_info:
                return
                
            # Parse the response (remove completion marker)
            response_json = response_text.split("<<<THOUGHT_COMPLETE>>>")[0].strip()
            response_data = json.loads(response_json)
            
            # Determine what to display
            thought = None
            display_field = request_info.get('display_field')
            output_values = response_data.get('output_values', {})
            
            if display_field and display_field in output_values:
                # Use the specified display field
                thought = str(output_values[display_field])
            elif 'reasoning' in output_values:
                # Default to reasoning if available
                thought = str(output_values['reasoning'])
            elif 'action' in output_values:
                # Or action if available
                thought = str(output_values['action'])
            elif 'answer' in output_values:
                # Or answer
                thought = str(output_values['answer'])
            else:
                # Fall back to the task name + first output field
                for key, value in output_values.items():
                    if key not in ['error']:
                        thought = f"{request_info['task']}: {value}"
                        break
            
            if thought:
                # Emit the thought bubble event
                emitter = get_event_emitter()
                await emitter.emit_agent_thinking(agent_id, thought)
                self.logger.debug(f"Emitted thought for {agent_id}: {thought}")
            
            # Clean up the pending request
            del self._pending_requests[agent_id]
            
        except Exception as e:
            self.logger.debug(f"Failed to process brain response: {e}")
    
    async def on_file_activity(self, agent_id: str, path: str, action: str):
        """Called when an agent accesses files.
        
        Args:
            agent_id: The agent accessing files
            path: The file path
            action: The action (read, write, etc.)
        """
        if not _has_monitoring:
            return
            
        try:
            emitter = get_event_emitter()
            await emitter.emit_file_activity(agent_id, action, path)
        except Exception as e:
            self.logger.debug(f"Failed to emit file activity: {e}")


# Global brain monitor instance
_brain_monitor: Optional[BrainMonitor] = None


def get_brain_monitor() -> BrainMonitor:
    """Get the global brain monitor instance."""
    global _brain_monitor
    if _brain_monitor is None:
        _brain_monitor = BrainMonitor()
    return _brain_monitor