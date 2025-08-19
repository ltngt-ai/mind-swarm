"""
# Communication API for Cybers

## Core Concept: Simple Message Sending
The Communication API provides a clean, simple interface for Cybers to send messages 
to other Cybers without dealing with message formats or file operations. Messages are 
automatically formatted and routed through the Mind-Swarm infrastructure.

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

### Intention: "I want to send a message with additional metadata"
```python
# Send with optional metadata
communication.send_message(
    to="Bob",
    subject="Task completed",
    content="I've finished analyzing the data files as requested.",
    metadata={"task_id": "analyze-001", "completion_time": "2024-01-15T10:30:00"}
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

## Message Format
Messages are automatically formatted as JSON with:
- **from**: Your Cyber ID (automatic)
- **to**: Recipient Cyber ID
- **subject**: Message subject line
- **content**: Message body
- **timestamp**: When sent (automatic)
- **message_id**: Unique ID (automatic)
- **metadata**: Optional additional data

## Best Practices
1. Keep subjects concise and descriptive
2. Use metadata for structured data that other Cybers might process
3. Check your inbox regularly for responses
4. Messages are asynchronous - don't expect immediate replies
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
                    metadata: Optional[Dict[str, Any]] = None,
                    priority: str = "normal") -> str:
        """Send a message to another Cyber.
        
        Args:
            to: Recipient Cyber ID (e.g., "Alice", "Bob")
            subject: Message subject line
            content: Message body content
            metadata: Optional additional metadata
            priority: Message priority ("low", "normal", "high", "urgent")
            
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
        
        # Validate priority
        valid_priorities = ["low", "normal", "high", "urgent"]
        if priority not in valid_priorities:
            raise CommunicationError(f"Invalid priority. Must be one of: {', '.join(valid_priorities)}")
        
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
            "message_id": message_id,
            "priority": priority
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
    
    def broadcast(self,
                 recipients: list,
                 subject: str,
                 content: str,
                 metadata: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """Send the same message to multiple recipients.
        
        Args:
            recipients: List of Cyber IDs to send to
            subject: Message subject
            content: Message content
            metadata: Optional metadata
            
        Returns:
            Dict mapping recipient to message ID
            
        Example:
            results = communication.broadcast(
                recipients=["Alice", "Bob", "Charlie"],
                subject="Team meeting",
                content="Let's discuss our progress at the next cycle."
            )
            for cyber, msg_id in results.items():
                print(f"Sent {msg_id} to {cyber}")
        """
        if not recipients:
            raise CommunicationError("At least one recipient is required")
        
        results = {}
        for recipient in recipients:
            try:
                msg_id = self.send_message(
                    to=recipient,
                    subject=subject,
                    content=content,
                    metadata=metadata
                )
                results[recipient] = msg_id
            except CommunicationError as e:
                results[recipient] = f"ERROR: {e}"
        
        return results
    
    def reply(self,
             original_message: Dict[str, Any],
             content: str,
             include_original: bool = False) -> str:
        """Reply to a received message.
        
        Args:
            original_message: The original message dict (from inbox)
            content: Reply content
            include_original: Whether to quote the original message
            
        Returns:
            Message ID of the reply
            
        Example:
            # Read a message from inbox
            original = memory["/personal/inbox/message.msg.json"]
            
            # Send reply
            msg_id = communication.reply(
                original_message=original,
                content="Thanks for your message! Here's my response...",
                include_original=True
            )
        """
        if not original_message.get("from"):
            raise CommunicationError("Original message missing 'from' field")
        
        # Build reply subject
        original_subject = original_message.get("subject", "No subject")
        if not original_subject.startswith("Re: "):
            reply_subject = f"Re: {original_subject}"
        else:
            reply_subject = original_subject
        
        # Build reply content
        if include_original:
            original_content = original_message.get("content", "")
            original_from = original_message.get("from", "Unknown")
            original_time = original_message.get("timestamp", "Unknown time")
            
            reply_content = f"{content}\n\n---\nOn {original_time}, {original_from} wrote:\n{original_content}"
        else:
            reply_content = content
        
        # Include reference to original message in metadata
        metadata = {
            "in_reply_to": original_message.get("message_id"),
            "original_from": original_message.get("from")
        }
        
        return self.send_message(
            to=original_message["from"],
            subject=reply_subject,
            content=reply_content,
            metadata=metadata
        )
    
    def check_inbox(self) -> list:
        """Check inbox for new messages.
        
        Returns:
            List of message filenames in inbox
            
        Example:
            messages = communication.check_inbox()
            if messages:
                print(f"You have {len(messages)} new messages")
                for msg_file in messages:
                    msg = memory[f"/personal/inbox/{msg_file}"]
                    print(f"From {msg['from']}: {msg['subject']}")
        """
        inbox = self.personal / 'inbox'
        if not inbox.exists():
            return []
        
        # Look for .msg.json files
        messages = [f.name for f in inbox.glob("*.msg.json")]
        return sorted(messages)