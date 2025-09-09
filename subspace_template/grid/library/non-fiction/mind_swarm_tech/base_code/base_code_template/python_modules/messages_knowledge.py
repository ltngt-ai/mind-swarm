"""
# Messages Knowledge API for Cybers

## Core Concept: Semantic Message Storage
The Messages Knowledge API provides semantic storage and retrieval for messages,
replacing file-based inbox/outbox with a knowledge database approach.

Messages are stored with rich metadata enabling semantic search, conversation
threading, and context-aware retrieval.

## Examples

### Intention: "Store a received message in knowledge"
```python
msg_id = messages_knowledge.store_message(
    from_cyber="Alice",
    to_cyber="Bob", 
    subject="Memory optimization ideas",
    content="I've been working on memory compression...",
    message_type="MESSAGE"
)
print(f"Stored message with ID: {msg_id}")
```

### Intention: "Search for messages from a specific cyber"
```python
alice_messages = messages_knowledge.search_messages(
    query="Alice",
    filters={"from": "Alice"}
)
for msg in alice_messages:
    print(f"{msg['subject']}: {msg['content'][:100]}...")
```

### Intention: "Find related messages in a conversation thread"
```python
thread = messages_knowledge.get_conversation_thread(
    subject="Memory optimization",
    participants=["Alice", "Bob"]
)
for msg in thread:
    print(f"{msg['from']} -> {msg['to']}: {msg['content'][:50]}...")
```

### Intention: "Mark a message as processed"
```python
messages_knowledge.mark_processed(msg_id)
```

## Best Practices
1. Use semantic queries for better context retrieval
2. Store messages immediately upon receipt
3. Include metadata for threading and search
4. Clean up old processed messages periodically
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger("Cyber.messages_knowledge")


class MessagesKnowledgeError(Exception):
    """Base exception for message knowledge errors."""
    pass


class MessagesKnowledge:
    """Manages message storage and retrieval using the knowledge database."""
    
    def __init__(self, context_or_knowledge):
        """Initialize the Messages Knowledge API.
        
        Args:
            context_or_knowledge: Either execution context dict or Knowledge API instance
        """
        if isinstance(context_or_knowledge, dict):
            # Initialize from context
            self.context = context_or_knowledge
            self.cyber_id = context_or_knowledge.get('cyber_id', 'unknown')
            
            # Get Knowledge API from context
            from .knowledge import Knowledge
            memory_api = context_or_knowledge.get('memory_api')
            if not memory_api:
                raise MessagesKnowledgeError("Memory API required in context")
            self.knowledge = Knowledge(memory_api)
        else:
            # Direct Knowledge API instance
            self.knowledge = context_or_knowledge
            self.cyber_id = 'unknown'
    
    def store_message(self,
                     from_cyber: str,
                     to_cyber: str,
                     subject: str,
                     content: str,
                     message_type: str = "MESSAGE",
                     metadata: Optional[Dict[str, Any]] = None,
                     message_id: Optional[str] = None) -> str:
        """Store a message in the knowledge database.
        
        Args:
            from_cyber: Sender cyber ID
            to_cyber: Recipient cyber ID
            subject: Message subject
            content: Message content
            message_type: Type of message (MESSAGE, COMMAND, QUERY, etc.)
            metadata: Additional metadata
            message_id: Optional specific message ID
            
        Returns:
            Knowledge ID of stored message
            
        Example:
            msg_id = messages_knowledge.store_message(
                from_cyber="Alice",
                to_cyber=self.cyber_id,
                subject="Collaboration request",
                content="Would you like to work together?"
            )
        """
        if not message_id:
            # Generate unique message ID
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            message_id = f"{from_cyber}_{to_cyber}_{timestamp}_{uuid.uuid4().hex[:8]}"
        
        # Create knowledge entry with semantic content
        semantic_content = f"""
Message from {from_cyber} to {to_cyber}
Subject: {subject}
Type: {message_type}
Timestamp: {datetime.now().isoformat()}

Content:
{content}
"""
        
        # Prepare metadata
        msg_metadata = {
            "message_type": message_type,
            "from": from_cyber,
            "to": to_cyber,
            "subject": subject,
            "timestamp": datetime.now().isoformat(),
            "message_id": message_id,
            "processed": False,
            "cyber_specific": to_cyber == self.cyber_id  # Is this for me?
        }
        
        if metadata:
            msg_metadata.update(metadata)
        
        # Store in knowledge with hierarchical ID
        knowledge_id = f"messages/{to_cyber}/{message_id}"
        
        # Store as personal if it's for this cyber, shared otherwise
        personal = (to_cyber == self.cyber_id)
        
        stored_id = self.knowledge.store(
            content=semantic_content,
            knowledge_id=knowledge_id,
            tags=["message", f"from_{from_cyber}", f"to_{to_cyber}", message_type.lower()],
            personal=personal,
            metadata=msg_metadata
        )
        
        logger.info(f"Stored message {message_id} as knowledge {stored_id}")
        return stored_id
    
    def search_messages(self,
                       query: str,
                       filters: Optional[Dict[str, Any]] = None,
                       limit: int = 10) -> List[Dict[str, Any]]:
        """Search for messages using semantic search.
        
        Args:
            query: Search query (semantic search)
            filters: Optional filters (from, to, subject, etc.)
            limit: Maximum number of results
            
        Returns:
            List of matching messages with metadata
            
        Example:
            recent_alice = messages_knowledge.search_messages(
                query="memory optimization",
                filters={"from": "Alice"},
                limit=5
            )
        """
        # Build search tags from filters
        tags = ["message"]
        if filters:
            if "from" in filters:
                tags.append(f"from_{filters['from']}")
            if "to" in filters:
                tags.append(f"to_{filters['to']}")
            if "message_type" in filters:
                tags.append(filters["message_type"].lower())
        
        # Search in knowledge
        results = self.knowledge.search(
            query=query,
            tags=tags,
            limit=limit
        )
        
        # Extract message data from results
        messages = []
        for result in results:
            if result.get('metadata'):
                msg_data = {
                    'message_id': result['metadata'].get('message_id'),
                    'from': result['metadata'].get('from'),
                    'to': result['metadata'].get('to'),
                    'subject': result['metadata'].get('subject'),
                    'timestamp': result['metadata'].get('timestamp'),
                    'content': result.get('content', ''),
                    'score': result.get('score', 0),
                    'processed': result['metadata'].get('processed', False)
                }
                messages.append(msg_data)
        
        return messages
    
    def get_unprocessed_messages(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get unprocessed messages for this cyber.
        
        Args:
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of unprocessed messages
            
        Example:
            new_messages = messages_knowledge.get_unprocessed_messages()
            for msg in new_messages:
                print(f"New from {msg['from']}: {msg['subject']}")
                # Process message...
                messages_knowledge.mark_processed(msg['message_id'])
        """
        # Search for messages to this cyber that aren't processed
        messages = self.search_messages(
            query="",  # Get all
            filters={"to": self.cyber_id},
            limit=limit * 2  # Get more to filter
        )
        
        # Filter unprocessed
        unprocessed = [msg for msg in messages if not msg.get('processed', False)]
        return unprocessed[:limit]
    
    def get_conversation_thread(self,
                               subject: str = None,
                               participants: List[str] = None,
                               days_back: int = 7) -> List[Dict[str, Any]]:
        """Get a conversation thread between participants.
        
        Args:
            subject: Optional subject to filter by
            participants: List of cyber IDs involved
            days_back: How many days back to search
            
        Returns:
            List of messages in chronological order
            
        Example:
            thread = messages_knowledge.get_conversation_thread(
                subject="Memory optimization",
                participants=["Alice", "Bob", self.cyber_id]
            )
        """
        # Build search query
        query_parts = []
        if subject:
            query_parts.append(subject)
        if participants:
            query_parts.extend(participants)
        
        query = " ".join(query_parts) if query_parts else ""
        
        # Search for relevant messages
        messages = self.search_messages(query=query, limit=50)
        
        # Filter by participants if specified
        if participants:
            filtered = []
            for msg in messages:
                if (msg.get('from') in participants or 
                    msg.get('to') in participants):
                    filtered.append(msg)
            messages = filtered
        
        # Filter by time window
        cutoff_time = datetime.now() - timedelta(days=days_back)
        time_filtered = []
        for msg in messages:
            try:
                msg_time = datetime.fromisoformat(msg.get('timestamp', ''))
                if msg_time >= cutoff_time:
                    time_filtered.append(msg)
            except:
                # Include messages with invalid timestamps
                time_filtered.append(msg)
        
        # Sort chronologically
        time_filtered.sort(key=lambda x: x.get('timestamp', ''))
        
        return time_filtered
    
    def mark_processed(self, message_id: str) -> bool:
        """Mark a message as processed.
        
        Args:
            message_id: The message ID to mark as processed
            
        Returns:
            True if successfully marked
            
        Example:
            if messages_knowledge.mark_processed(msg_id):
                print("Message marked as processed")
        """
        # Build knowledge ID
        knowledge_id = f"messages/{self.cyber_id}/{message_id}"
        
        # Get existing message
        existing = self.knowledge.get(knowledge_id)
        if not existing:
            logger.warning(f"Message {message_id} not found")
            return False
        
        # Update metadata
        metadata = existing.get('metadata', {})
        metadata['processed'] = True
        metadata['processed_at'] = datetime.now().isoformat()
        
        # Update in knowledge
        success = self.knowledge.update(
            knowledge_id=knowledge_id,
            content=existing.get('content', ''),
            metadata=metadata
        )
        
        return success
    
    def get_message_by_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific message by ID.
        
        Args:
            message_id: The message ID to retrieve
            
        Returns:
            Message data or None if not found
            
        Example:
            msg = messages_knowledge.get_message_by_id("Alice_Bob_20250109_123045_abc123")
            if msg:
                print(f"Subject: {msg['subject']}")
        """
        # Try to get from knowledge
        knowledge_id = f"messages/{self.cyber_id}/{message_id}"
        result = self.knowledge.get(knowledge_id)
        
        if result:
            return {
                'message_id': result.get('metadata', {}).get('message_id'),
                'from': result.get('metadata', {}).get('from'),
                'to': result.get('metadata', {}).get('to'),
                'subject': result.get('metadata', {}).get('subject'),
                'content': result.get('content', ''),
                'timestamp': result.get('metadata', {}).get('timestamp'),
                'processed': result.get('metadata', {}).get('processed', False)
            }
        
        return None
    
    def delete_old_messages(self, days_old: int = 30) -> int:
        """Delete messages older than specified days.
        
        Args:
            days_old: Delete messages older than this many days
            
        Returns:
            Number of messages deleted
            
        Example:
            deleted = messages_knowledge.delete_old_messages(days_old=14)
            print(f"Cleaned up {deleted} old messages")
        """
        cutoff_time = datetime.now() - timedelta(days=days_old)
        
        # Search for old messages
        old_messages = self.search_messages(
            query="",
            filters={"to": self.cyber_id},
            limit=100
        )
        
        deleted_count = 0
        for msg in old_messages:
            try:
                msg_time = datetime.fromisoformat(msg.get('timestamp', ''))
                if msg_time < cutoff_time:
                    knowledge_id = f"messages/{self.cyber_id}/{msg['message_id']}"
                    if self.knowledge.forget(knowledge_id):
                        deleted_count += 1
            except Exception as e:
                logger.warning(f"Error deleting message {msg.get('message_id')}: {e}")
        
        return deleted_count