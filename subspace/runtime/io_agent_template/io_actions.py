"""I/O Agent specific actions."""

from typing import Dict, Any
import json
import re
from datetime import datetime
from pathlib import Path

from base_code_template.actions import Action, ActionResult, ActionStatus, Priority
from base_code_template.memory import TaskMemoryBlock


class MakeNetworkRequestAction(Action):
    """Make an HTTP request through the network body file."""
    
    def __init__(self):
        super().__init__("make_network_request", "Make HTTP request to external URL", Priority.HIGH)
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Write network request to body file."""
        url = self.params.get("url")
        method = self.params.get("method", "GET")
        headers = self.params.get("headers", {})
        body = self.params.get("body")
        
        if not url:
            # Try to extract URL from the original request
            original_text = context.get("original_text", "")
            urls = self._extract_urls(original_text)
            
            if urls:
                url = urls[0]
            else:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error="No URL specified or found in request"
                )
        
        try:
            # Get IO handler from context
            io_handler = context.get("io_handler")
            if not io_handler:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error="No IO handler available"
                )
            
            # Create network request
            network_request = {
                "method": method,
                "url": url,
                "headers": headers or {"User-Agent": "Mind-Swarm-IO-Agent/1.0"},
                "body": body
            }
            
            # Make the request
            request_id = await io_handler.make_network_request(network_request)
            
            # Create task memory to track the request
            memory_manager = context.get("memory_manager")
            if memory_manager:
                task_memory = TaskMemoryBlock(
                    task_type="network_request",
                    description=f"Fetching {url}",
                    status="pending",
                    priority=Priority.HIGH,
                    metadata={
                        "request_id": request_id,
                        "url": url,
                        "method": method
                    }
                )
                memory_manager.add_memory(task_memory)
                
                # Store task ID in context for tracking
                context["network_task_id"] = task_memory.id
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result={
                    "request_id": request_id,
                    "url": url,
                    "status": "request_sent"
                }
            )
        except Exception as e:
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=str(e)
            )
    
    def _extract_urls(self, text: str) -> list[str]:
        """Extract URLs from text."""
        # First try explicit URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, text)
        
        if not urls:
            # Try common domain patterns
            domain_pattern = r'(?:www\.)?([a-zA-Z0-9-]+\.(?:com|org|net|edu|gov|co\.uk|io))'
            domains = re.findall(domain_pattern, text)
            if domains:
                urls = [f"https://{domain}" if not domain.startswith('www.') else f"https://{domain}" for domain in domains]
        
        return urls


class CheckNetworkResponseAction(Action):
    """Check if network response has arrived."""
    
    def __init__(self):
        super().__init__("check_network_response", "Check for network response", Priority.HIGH)
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Check if response is available in network body file."""
        try:
            # For now, we'll rely on the observe phase to detect responses
            # This action confirms we're waiting for a response
            
            task_id = context.get("network_task_id")
            if task_id:
                memory_manager = context.get("memory_manager")
                if memory_manager:
                    task_memory = memory_manager.access_memory(task_id)
                    if task_memory and task_memory.status == "pending":
                        return ActionResult(
                            self.name,
                            ActionStatus.COMPLETED,
                            result={"status": "waiting_for_response"}
                        )
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result={"status": "no_pending_request"}
            )
        except Exception as e:
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=str(e)
            )


class ProcessNetworkResponseAction(Action):
    """Process a received network response."""
    
    def __init__(self):
        super().__init__("process_network_response", "Process HTTP response")
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Process the network response data."""
        response_data = self.params.get("response_data", {})
        
        try:
            status = response_data.get("status", 0)
            body = response_data.get("body", "")
            url = response_data.get("url", "")
            
            # Update task memory
            task_id = context.get("network_task_id")
            if task_id:
                memory_manager = context.get("memory_manager")
                if memory_manager:
                    task_memory = memory_manager.access_memory(task_id)
                    if task_memory:
                        task_memory.status = "completed"
                        task_memory.metadata["response_status"] = status
                        task_memory.metadata["response_length"] = len(body)
            
            # Store response in memory
            memory_dir = context.get("memory_dir")
            if memory_dir and body:
                # Save response to memory
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"network_response_{timestamp}.txt"
                response_file = Path(memory_dir) / filename
                
                # Save response with metadata
                content = f"URL: {url}\n"
                content += f"Status: {status}\n"
                content += f"Timestamp: {datetime.now().isoformat()}\n"
                content += f"\n--- RESPONSE BODY ---\n{body[:10000]}"  # Limit size
                
                response_file.write_text(content)
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result={
                    "status": status,
                    "url": url,
                    "body_length": len(body),
                    "saved_to_memory": bool(memory_dir and body)
                }
            )
        except Exception as e:
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=str(e)
            )


class SendUserResponseAction(Action):
    """Send response to user through user_io body file."""
    
    def __init__(self):
        super().__init__("send_user_response", "Send response to user")
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Write response to user_io body file."""
        content = self.params.get("content", "")
        response_type = self.params.get("type", "response")
        session_id = self.params.get("session_id", "default")
        
        try:
            io_handler = context.get("io_handler")
            if not io_handler:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error="No IO handler available"
                )
            
            response = {
                "type": response_type,
                "content": content,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            }
            
            await io_handler.send_user_response(response)
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result={"sent": True, "session_id": session_id}
            )
        except Exception as e:
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=str(e)
            )


# Register I/O agent actions
def register_io_actions(registry):
    """Register all I/O agent actions."""
    registry.register_action("io_gateway", "make_network_request", MakeNetworkRequestAction)
    registry.register_action("io_gateway", "check_network_response", CheckNetworkResponseAction)
    registry.register_action("io_gateway", "process_network_response", ProcessNetworkResponseAction)
    registry.register_action("io_gateway", "send_user_response", SendUserResponseAction)