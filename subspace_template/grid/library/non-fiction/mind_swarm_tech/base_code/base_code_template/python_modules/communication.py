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

## Best Practices
1. Keep subjects concise and descriptive
2. Messages are asynchronous - don't expect immediate replies
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


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
        
        # Messages go to .internal/outbox (hidden from Cyber's view)
        self.outbox = self.personal / '.internal' / 'outbox'
        self.outbox.mkdir(parents=True, exist_ok=True)
    
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
            with open(outbox_file, 'w') as f:
                json.dump(message, f, indent=2)
            
            return message_id
            
        except Exception as e:
            raise CommunicationError(f"Failed to send message: {e}")