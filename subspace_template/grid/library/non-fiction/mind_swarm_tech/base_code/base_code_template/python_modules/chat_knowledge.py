"""
# Chat Knowledge API for Cybers

## Core Concept: Semantic Chat History
The Chat Knowledge API provides semantic storage and retrieval for chat conversations,
replacing file-based .local_chat.json with a knowledge database approach.

Chat messages are stored with location, participant, and temporal metadata,
enabling context-aware dialogue retrieval and shared conversations.

## Examples

### Intention: "Store a chat message at current location"
```python
chat_knowledge.store_chat_message(
    location="/grid/library",
    message="Anyone working on memory optimization?",
    cyber_id="Alice"
)
```

### Intention: "Get recent chat at a location"
```python
recent_chat = chat_knowledge.get_location_chat("/grid/library", limit=10)
for msg in recent_chat:
    print(f"{msg['cyber_id']}: {msg['message']}")
```

### Intention: "Search chat history for a topic"
```python
memory_chats = chat_knowledge.search_chat(
    query="memory optimization techniques",
    days_back=7
)
for chat in memory_chats:
    print(f"At {chat['location']}: {chat['message']}")
```

### Intention: "Get chat participants at a location"
```python
participants = chat_knowledge.get_active_participants(
    location="/grid/workshop",
    hours_back=2
)
print(f"Active cybers: {', '.join(participants)}")
```

## Best Practices
1. Store chat messages immediately when sent
2. Include location context for spatial awareness
3. Use semantic search for topic-based retrieval
4. Clean up old chat periodically to save space
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import logging

logger = logging.getLogger("Cyber.chat_knowledge")


class ChatKnowledgeError(Exception):
    """Base exception for chat knowledge errors."""
    pass


class ChatKnowledge:
    """Manages chat history storage and retrieval using the knowledge database."""
    
    def __init__(self, context_or_knowledge):
        """Initialize the Chat Knowledge API.
        
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
                raise ChatKnowledgeError("Memory API required in context")
            self.knowledge = Knowledge(memory_api)
        else:
            # Direct Knowledge API instance
            self.knowledge = context_or_knowledge
            self.cyber_id = 'unknown'
    
    def store_chat_message(self,
                          location: str,
                          message: str,
                          cyber_id: Optional[str] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store a chat message in the knowledge database.
        
        Args:
            location: Location where chat occurred
            message: The chat message content
            cyber_id: ID of cyber who sent message (defaults to self)
            metadata: Additional metadata
            
        Returns:
            Knowledge ID of stored chat message
            
        Example:
            msg_id = chat_knowledge.store_chat_message(
                location="/grid/community/school",
                message="Has anyone solved the memory leak exercise?",
                cyber_id="Bob"
            )
        """
        if not cyber_id:
            cyber_id = self.cyber_id
        
        # Generate chat message ID
        timestamp = datetime.now()
        chat_id = f"chat_{location.replace('/', '_')}_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}"
        
        # Create semantic content
        semantic_content = f"""
Chat Message at {location}
From: {cyber_id}
Time: {timestamp.isoformat()}

Message: {message}
"""
        
        # Prepare metadata
        chat_metadata = {
            "message_type": "chat",
            "location": location,
            "cyber_id": cyber_id,
            "message": message,
            "timestamp": timestamp.isoformat()
        }
        
        if metadata:
            chat_metadata.update(metadata)
        
        # Build tags for search
        location_parts = location.strip('/').split('/')
        chat_tags = ["chat", f"cyber_{cyber_id}"]
        chat_tags.extend([f"loc_{part}" for part in location_parts])
        
        # Store in knowledge with hierarchical ID
        knowledge_id = f"chats/{location.strip('/')}/{chat_id}"
        
        # Chat is shared by default (visible to all at location)
        stored_id = self.knowledge.store(
            content=semantic_content,
            knowledge_id=knowledge_id,
            tags=chat_tags,
            personal=False,  # Shared with cybers at location
            metadata=chat_metadata
        )
        
        logger.debug(f"Stored chat message {chat_id} at {location}")
        return stored_id
    
    def get_location_chat(self,
                         location: str,
                         limit: int = 10,
                         hours_back: int = 24) -> List[Dict[str, Any]]:
        """Get recent chat messages at a specific location.
        
        Args:
            location: The location path
            limit: Maximum number of messages
            hours_back: How many hours of history to retrieve
            
        Returns:
            List of chat messages, most recent first
            
        Example:
            library_chat = chat_knowledge.get_location_chat(
                "/grid/library",
                limit=20,
                hours_back=2
            )
        """
        # Build search tags for location
        location_parts = location.strip('/').split('/')
        search_tags = ["chat"]
        search_tags.extend([f"loc_{part}" for part in location_parts])
        
        # Search for chat messages
        results = self.knowledge.search(
            query="",  # Get all at location
            tags=search_tags,
            limit=limit * 2  # Get extra to filter by time
        )
        
        # Filter by time window and exact location
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        messages = []
        
        for result in results:
            metadata = result.get('metadata', {})
            
            # Check exact location match
            if metadata.get('location') != location:
                continue
            
            # Check time window
            try:
                msg_time = datetime.fromisoformat(metadata.get('timestamp', ''))
                if msg_time >= cutoff_time:
                    messages.append({
                        'cyber_id': metadata.get('cyber_id'),
                        'message': metadata.get('message'),
                        'timestamp': metadata.get('timestamp'),
                        'score': result.get('score', 0)
                    })
            except:
                pass
        
        # Sort by timestamp (most recent first)
        messages.sort(key=lambda x: x['timestamp'], reverse=True)
        return messages[:limit]
    
    def search_chat(self,
                   query: str,
                   location: Optional[str] = None,
                   days_back: int = 7,
                   limit: int = 20) -> List[Dict[str, Any]]:
        """Search chat history using semantic search.
        
        Args:
            query: Search query for message content
            location: Optional location filter
            days_back: How many days back to search
            limit: Maximum number of results
            
        Returns:
            List of matching chat messages
            
        Example:
            memory_discussions = chat_knowledge.search_chat(
                query="memory optimization algorithms",
                location="/grid/workshop",
                days_back=3
            )
        """
        # Build search tags
        tags = ["chat"]
        if location:
            location_parts = location.strip('/').split('/')
            tags.extend([f"loc_{part}" for part in location_parts])
        
        # Search for matching chats
        results = self.knowledge.search(
            query=query,
            tags=tags,
            limit=limit * 2  # Get extra to filter
        )
        
        # Filter by time window and location if specified
        cutoff_time = datetime.now() - timedelta(days=days_back)
        messages = []
        
        for result in results:
            metadata = result.get('metadata', {})
            
            # Check location if specified
            if location and metadata.get('location') != location:
                continue
            
            # Check time window
            try:
                msg_time = datetime.fromisoformat(metadata.get('timestamp', ''))
                if msg_time >= cutoff_time:
                    messages.append({
                        'location': metadata.get('location'),
                        'cyber_id': metadata.get('cyber_id'),
                        'message': metadata.get('message'),
                        'timestamp': metadata.get('timestamp'),
                        'score': result.get('score', 0)
                    })
            except:
                pass
        
        # Sort by relevance score
        messages.sort(key=lambda x: x['score'], reverse=True)
        return messages[:limit]
    
    def get_active_participants(self,
                               location: str,
                               hours_back: int = 1) -> List[str]:
        """Get list of cybers who have chatted at a location recently.
        
        Args:
            location: The location path
            hours_back: Time window to consider
            
        Returns:
            List of unique cyber IDs
            
        Example:
            active = chat_knowledge.get_active_participants(
                "/grid/community/school",
                hours_back=2
            )
        """
        recent_chat = self.get_location_chat(
            location=location,
            limit=100,  # Get many to find all participants
            hours_back=hours_back
        )
        
        # Extract unique participants
        participants: Set[str] = set()
        for msg in recent_chat:
            if msg.get('cyber_id'):
                participants.add(msg['cyber_id'])
        
        return list(participants)
    
    def get_conversation_context(self,
                                location: str,
                                around_time: Optional[datetime] = None,
                                context_window: int = 10) -> List[Dict[str, Any]]:
        """Get conversation context around a specific time.
        
        Args:
            location: The location of conversation
            around_time: Time to get context around (defaults to now)
            context_window: Number of messages before and after
            
        Returns:
            List of messages in chronological order
            
        Example:
            context = chat_knowledge.get_conversation_context(
                "/grid/library",
                around_time=datetime.now() - timedelta(hours=1),
                context_window=5
            )
        """
        if not around_time:
            around_time = datetime.now()
        
        # Get chat messages at location
        all_chat = self.get_location_chat(
            location=location,
            limit=context_window * 3,  # Get extra to find context
            hours_back=24  # Look back a day
        )
        
        # Convert timestamps and find messages around target time
        messages_with_time = []
        for msg in all_chat:
            try:
                msg_time = datetime.fromisoformat(msg['timestamp'])
                messages_with_time.append({
                    **msg,
                    'datetime': msg_time,
                    'time_diff': abs((msg_time - around_time).total_seconds())
                })
            except:
                pass
        
        # Sort by time difference from target
        messages_with_time.sort(key=lambda x: x['time_diff'])
        
        # Get context window
        context = messages_with_time[:context_window * 2]
        
        # Sort chronologically for display
        context.sort(key=lambda x: x['datetime'])
        
        # Remove datetime object before returning
        for msg in context:
            del msg['datetime']
            del msg['time_diff']
        
        return context
    
    def get_cyber_chat_history(self,
                              cyber_id: Optional[str] = None,
                              days_back: int = 7,
                              limit: int = 50) -> List[Dict[str, Any]]:
        """Get chat history for a specific cyber.
        
        Args:
            cyber_id: Cyber ID (defaults to self)
            days_back: How many days of history
            limit: Maximum number of messages
            
        Returns:
            List of chat messages from the cyber
            
        Example:
            my_history = chat_knowledge.get_cyber_chat_history()
            for msg in my_history:
                print(f"At {msg['location']}: {msg['message']}")
        """
        if not cyber_id:
            cyber_id = self.cyber_id
        
        # Search for cyber's chat messages
        results = self.knowledge.search(
            query="",
            tags=["chat", f"cyber_{cyber_id}"],
            limit=limit * 2  # Get extra to filter by time
        )
        
        # Filter by time window
        cutoff_time = datetime.now() - timedelta(days=days_back)
        messages = []
        
        for result in results:
            metadata = result.get('metadata', {})
            
            try:
                msg_time = datetime.fromisoformat(metadata.get('timestamp', ''))
                if msg_time >= cutoff_time:
                    messages.append({
                        'location': metadata.get('location'),
                        'message': metadata.get('message'),
                        'timestamp': metadata.get('timestamp')
                    })
            except:
                pass
        
        # Sort by timestamp (most recent first)
        messages.sort(key=lambda x: x['timestamp'], reverse=True)
        return messages[:limit]
    
    def get_popular_chat_locations(self,
                                  hours_back: int = 24,
                                  limit: int = 10) -> List[Dict[str, Any]]:
        """Get locations with most chat activity.
        
        Args:
            hours_back: Time window to analyze
            limit: Maximum number of locations
            
        Returns:
            List of locations with chat statistics
            
        Example:
            popular = chat_knowledge.get_popular_chat_locations(hours_back=6)
            for loc in popular:
                print(f"{loc['location']}: {loc['message_count']} messages")
        """
        # Search for recent chat messages
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        results = self.knowledge.search(
            query="",
            tags=["chat"],
            limit=200  # Get many to analyze
        )
        
        # Aggregate by location
        location_stats = {}
        
        for result in results:
            metadata = result.get('metadata', {})
            location = metadata.get('location')
            
            if not location:
                continue
            
            try:
                msg_time = datetime.fromisoformat(metadata.get('timestamp', ''))
                if msg_time < cutoff_time:
                    continue
            except:
                continue
            
            if location not in location_stats:
                location_stats[location] = {
                    'location': location,
                    'message_count': 0,
                    'unique_participants': set(),
                    'last_message': None
                }
            
            location_stats[location]['message_count'] += 1
            location_stats[location]['unique_participants'].add(metadata.get('cyber_id'))
            
            # Track last message time
            timestamp = metadata.get('timestamp')
            if timestamp:
                if not location_stats[location]['last_message'] or timestamp > location_stats[location]['last_message']:
                    location_stats[location]['last_message'] = timestamp
        
        # Convert to list
        popular = []
        for location, stats in location_stats.items():
            popular.append({
                'location': location,
                'message_count': stats['message_count'],
                'participant_count': len(stats['unique_participants']),
                'last_message': stats['last_message']
            })
        
        # Sort by message count
        popular.sort(key=lambda x: x['message_count'], reverse=True)
        
        return popular[:limit]
    
    def cleanup_old_chat(self, days_old: int = 30) -> int:
        """Delete chat messages older than specified days.
        
        Args:
            days_old: Delete messages older than this many days
            
        Returns:
            Number of messages deleted
            
        Example:
            deleted = chat_knowledge.cleanup_old_chat(days_old=7)
            print(f"Cleaned up {deleted} old chat messages")
        """
        cutoff_time = datetime.now() - timedelta(days=days_old)
        
        # Search for old messages
        results = self.knowledge.search(
            query="",
            tags=["chat"],
            limit=500  # Process in batches
        )
        
        deleted_count = 0
        for result in results:
            metadata = result.get('metadata', {})
            
            try:
                msg_time = datetime.fromisoformat(metadata.get('timestamp', ''))
                if msg_time < cutoff_time:
                    # Extract knowledge ID from result
                    knowledge_id = result.get('id')
                    if knowledge_id and self.knowledge.forget(knowledge_id):
                        deleted_count += 1
            except Exception as e:
                logger.warning(f"Error deleting old chat: {e}")
        
        return deleted_count