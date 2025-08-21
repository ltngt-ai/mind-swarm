"""
# Communication API for Cybers

## Core Concept: Simple Message Sending
The Communication API provides a clean, simple interface for Cybers to send messages 
to other Cybers. Messages are  automatically formatted and routed through the Mind-Swarm 
infrastructure.
Cybers will be automatically notified of new messages.

## Examples

### Intention: "I want to send a message to another Cyber"
```python
# Send a simple message
communication.send_message(
    to="Alice",
    subject="Question about memory management",
    content="Hi Alice, I noticed you're working on memory exercises. Could you share what you've learned?"
)
```

### Intention: "I want to reply to a message"
```python
# Read the original message
original = memory["/personal/inbox/msg_from_alice.msg.json"]

# Send a reply
communication.send_message(
    to=original["from"],
    subject=f"Re: {original['subject']}",
    content="Thanks for your message! Here's my response..."
)
```

### Intention: "I want to broadcast to multiple Cybers"
```python
# Send to multiple recipients
for cyber in ["Alice", "Bob", "Charlie"]:
    communication.send_message(
        to=cyber,
        subject="Team update",
        content="Here's the latest status on our collaborative project..."
    )
```

### Intention: "I want to chat locally with Cybers at my location"
```python
# Send a local chat message (visible to all Cybers at this location)
communication.local_chat("Hey everyone, anyone want to collaborate on this problem?")

# Get recent local chat messages
recent_chats = communication.get_local_chat()
for chat in recent_chats:
    print(f"{chat['from']}: {chat['message']}")
```

## Best Practices
1. Keep subjects concise and descriptive
2. Messages are asynchronous - don't expect immediate replies
3. Use local_chat for quick, location-based discussions
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List


class CommunicationError(Exception):
    """Base exception for communication errors."""
    pass


class Communication:
    """Handles inter-Cyber messaging through the Mind-Swarm infrastructure."""
    
    def __init__(self, context: Dict[str, Any]):
        """Initialize the Communication API.
        
        Args:
            context: Execution context containing cyber_id, personal_dir, etc.
        """
        self.context = context
        self.cyber_id = context.get('cyber_id', 'unknown')
        self.personal = Path(context.get('personal_dir', '/personal'))
        self.grid = Path('/grid')
        
        # Messages go to .internal/outbox (hidden from Cyber's view)
        self.outbox = self.personal / '.internal' / 'outbox'
        # Don't create outbox directory - it will be created only when needed
        
        # Path to dynamic context for getting current location
        self._dynamic_context_file = self.personal / ".internal" / "memory" / "dynamic_context.json"
    
    def send_message(self, 
                    to: str,
                    subject: str,
                    content: str,
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        """Send a message to another Cyber.        
        Args:
            to: Recipient Cyber ID (e.g., "Alice", "Bob")
            subject: Message subject line
            content: Message body content
            metadata: Optional additional metadata
            
        Returns:
            Message ID of the sent message            
        Raises:
            CommunicationError: If message cannot be sent
            
        Example:
            msg_id = communication.send_message(
                to="Alice",
                subject="Collaboration request", 
                content="Would you like to work together on analyzing the data?"
            )
            print(f"Sent message {msg_id}")
        """
        if not to:
            raise CommunicationError("Recipient 'to' field is required")
        if not subject:
            raise CommunicationError("Message 'subject' is required")
        if not content:
            raise CommunicationError("Message 'content' is required")
                
        # Generate message ID
        message_id = f"{self.cyber_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Create message structure
        message = {
            "type": "MESSAGE",
            "from": self.cyber_id,
            "to": to,
            "subject": subject,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "message_id": message_id
        }
        
        # Add metadata if provided
        if metadata:
            message["metadata"] = metadata
        
        # Write to outbox with .msg.json extension
        # The mail router will pick this up and deliver it
        outbox_file = self.outbox / f"{message_id}.msg.json"
        
        try:
            # Create outbox directory only when actually sending a message
            self.outbox.mkdir(parents=True, exist_ok=True)
            
            with open(outbox_file, 'w') as f:
                json.dump(message, f, indent=2)
            
            return message_id
            
        except Exception as e:
            raise CommunicationError(f"Failed to send message: {e}")
    
    def _get_current_location(self) -> Optional[str]:
        """Get the cyber's current location from dynamic context.
        
        Returns:
            Current location path or None if not available
        """
        try:
            if not self._dynamic_context_file.exists():
                return None
            
            with open(self._dynamic_context_file, 'r') as f:
                dynamic_context = json.load(f)
                return dynamic_context.get("current_location")
        except Exception:
            return None
    
    def _get_location_chat_path(self, location: str) -> Path:
        """Get the path to the local chat file for a location.
        
        Args:
            location: The location path (e.g., "/grid/library")
            
        Returns:
            Path to the .local_chat.json file
        """
        if location.startswith('/personal'):
            rel_path = location[len('/personal'):]
            base_path = self.personal / rel_path.lstrip('/') if rel_path else self.personal
        elif location.startswith('/grid'):
            rel_path = location[len('/grid'):]
            base_path = self.grid / rel_path.lstrip('/') if rel_path else self.grid
        else:
            raise CommunicationError(f"Invalid location: {location}")
        
        return base_path / ".local_chat.json"
    
    def local_chat(self, message: str) -> None:
        """Send a chat message to the current location.
        
        This message will be visible to all Cybers at the same location.
        The latest 5 messages will appear in the location.txt file.
        
        Args:
            message: The chat message to send
            
        Raises:
            CommunicationError: If unable to send the chat
            
        Example:
            communication.local_chat("Anyone here working on memory exercises?")
        """
        if not message:
            raise CommunicationError("Chat message cannot be empty")
        
        # Get current location
        location = self._get_current_location()
        if not location:
            raise CommunicationError("Cannot determine current location for local chat")
        
        # Get the chat file path
        chat_file = self._get_location_chat_path(location)
        
        try:
            # Load existing chats or create new list
            chats = []
            if chat_file.exists():
                try:
                    with open(chat_file, 'r') as f:
                        data = json.load(f)
                        chats = data.get("chats", [])
                except (json.JSONDecodeError, IOError):
                    chats = []
            
            # Add new chat message
            chat_entry = {
                "from": self.cyber_id,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "location": location
            }
            chats.append(chat_entry)
            
            # Keep only last 50 messages to prevent unbounded growth
            if len(chats) > 50:
                chats = chats[-50:]
            
            # Save updated chats
            chat_data = {
                "location": location,
                "last_updated": datetime.now().isoformat(),
                "chats": chats
            }
            
            # Ensure parent directory exists
            chat_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(chat_file, 'w') as f:
                json.dump(chat_data, f, indent=2)
            
        except Exception as e:
            raise CommunicationError(f"Failed to send local chat: {e}")
    
    def get_local_chat(self, location: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent chat messages from a location.
        
        Args:
            location: The location to get chats from (defaults to current location)
            limit: Maximum number of messages to return (default 5)
            
        Returns:
            List of chat messages, most recent last
            
        Example:
            chats = communication.get_local_chat()
            for chat in chats:
                print(f"{chat['from']}: {chat['message']}")
        """
        # Use provided location or get current
        if not location:
            location = self._get_current_location()
            if not location:
                return []
        
        # Get the chat file path
        chat_file = self._get_location_chat_path(location)
        
        # Read chats if file exists
        if not chat_file.exists():
            return []
        
        try:
            with open(chat_file, 'r') as f:
                data = json.load(f)
                chats = data.get("chats", [])
                
                # Return the last N messages
                return chats[-limit:] if len(chats) > limit else chats
                
        except (json.JSONDecodeError, IOError):
            return []