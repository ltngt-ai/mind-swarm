"""
# Knowledge API for Cybers

## Core Concept: Semantic Knowledge Storage
The `Knowledge` class provides semantic search and storage capabilities for cybers,
enabling both personal and shared knowledge management through ChromaDB.

Knowledge is stored with vector embeddings for semantic similarity search,
allowing cybers to find conceptually related information even when exact terms don't match.

## Examples

### Intention: "I want to know about cognitive architecture."
```python
cognitive_architecture_info = knowledge.remember("cognitive architecture")
memory["/personal/cognitive_architecture"] = cognitive_architecture_info
```

### Intention: "I want to know what I personally know about cognitive architecture."
```python
results = knowledge.search("cognitive architecture", scope=["personal"], limit=5)
for item in results:
    relevance = item['score']            # How relevant (0-1)
    if relevance > 0.8:
        content = item['content']           # The knowledge text
```
### Intention: "What's the knowledge ID for best practice for writing YAML documentation?"
```python
results = knowledge.search("best practice for writing yaml documentation")
best_score = 0.0
best_id = ""
for item in results:
    if item['score'] > best_score:
        best_score = item['score']
        best_id = item['id']
```
### Intention: "Let's share what I've learned about YAML documentation best practices with tags: [yaml, best_practices]."
```python
knowledge.store(
    content="I've learned some best practices for YAML documentation...",
    tags=["yaml", "best_practices"],
    personal=False  # Share with the hive mind
)
```

### Intention: "Let's add our thoughts about best YAML documentation to our personal knowledge base."
```python
knowledge.store(
    content="My thoughts on best YAML documentation practices...",
    tags=["yaml", "best_practices"],
    personal=True
)
```

### Intention: "Let's add our /personal/notes/lessons_about_yaml.md to the [#<yaml_documentation_best_practices_id>]."
```python
existing = knowledge.get("#<yaml_documentation_best_practices_id>")
if existing:
    knowledge.update(
        "#<yaml_documentation_best_practices_id>",
        content=existing['content'] + memory["/personal/notes/lessons_about_yaml.md"],
        metadata={"iterations": existing['metadata'].get('iterations', 0) + 1}
    )
```

### Intention: "Find the knowledge for tags[architecture, memory]"
```python
# Find all knowledge with specific tags
architecture_knowledge = knowledge.search_by_tags(["architecture", "memory"])
for item in architecture_knowledge:
    if item['score'] > 0.7:  # High relevance
        print(f"Found: {item['content']}")
```

### Intention: "Let's forget my personal notes about YAML documentation."
```python
results = knowledge.search("yaml documentation", scope=["personal"], limit=5)
for item in results:
    knowledge.forget(item['id'])
```

### General Managing Knowledge
```python
# Get knowledge by ID
existing = knowledge.get("knowledge_123")
if existing:
    print(f"Content: {existing['content']}")
    print(f"Tags: {existing['metadata'].get('tags')}")

# Append to existing knowledge
existing = knowledge.get("knowledge_123")
if existing:
    updated_content = existing['content'] + "\n\nNew insights learned today..."
    knowledge.update("knowledge_123", content=updated_content)

# Remove knowledge by ID
success = knowledge.forget("knowledge_123")

# Update existing knowledge (replaces content)
knowledge.update("knowledge_123", content="Revised understanding of OODA loops")
knowledge.update("knowledge_123", tags=["cognitive", "updated", "important"])
knowledge.update("knowledge_123", metadata={"confidence": 0.95})

# Check before storing duplicates
existing = knowledge.search("my new insight", limit=3)
if not existing or all(r['score'] < 0.8 for r in existing):
    # No close matches, safe to store
    knowledge.store("my new insight", tags=["discovery"])
```

### Metadata Fields
- **tags**: List of categories (stored as a list of strings)
- **confidence**: Float between 0.0 and 1.0
- **category**: Type of knowledge
- **cyber_id**: Automatically added (who created it)
- **timestamp**: Automatically added (when created)
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class Knowledge:
    """
    Knowledge API for cybers. Semantic similarity-based knowledge management for both personal and shared knowledge.
    """
    
    def __init__(self, memory_context):
        """
        Initialize the Knowledge API.
        
        Args:
            memory_context: The Memory instance to access context
        """
        self.memory = memory_context
        self.knowledge_file = Path("/personal/.internal/knowledge_api")
        self.request_counter = 0
        self._last_request_time = 0
        self._min_request_interval = 0.1  # Minimum time between requests
        
    def search(self, query: str, limit: int = 5, scope: Optional[List[str]] = None, 
               timeout: float = 5.0) -> List[Dict[str, Any]]:
        """
Search for relevant knowledge.
Args:
    query: What to search for
    limit: Maximum results to return (capped at 20)
    scope: List of scopes to search ["personal", "shared"] (default: both)
    timeout: How long to wait for response

Returns:
    List of relevant knowledge items
    Each item in the list contains:
    {
        'content': str,        # The actual knowledge text/content
        'score': float,        # Relevance score (0.0 to 1.0, higher = more relevant)
        'metadata': dict,      # Metadata dictionary containing:
                                #   - 'cyber_id': who created it
                                #   - 'timestamp': when it was created
                                #   - 'tags': comma-separated string of tags
                                #   - 'personal': boolean (True if personal knowledge)
                                #   - 'category': type of knowledge (if set)
                                #   - 'confidence': float (0-1) if set
                                #   - any other custom metadata
        'id': str,            # Unique knowledge ID (for updates/deletion)
        'source': str         # Either 'personal' or 'shared' (which collection it came from)
    }
    The score is particularly useful - it's a similarity score from 0.0 to 1.0 where:
    - 1.0 = Perfect match
    - 0.8+ = Very relevant
    - 0.5-0.8 = Somewhat relevant
    - <0.5 = Weakly relevant
"""
        # Rate limiting
        self._wait_for_rate_limit()
        
        # Prepare request
        request_id = self._generate_request_id()
        scope = scope or ["personal", "shared"]
        
        request = {
            "request_id": request_id,
            "operation": "search",
            "query": query,
            "options": {
                "limit": min(limit, 20),  # Cap at 20
                "scope": scope
            }
        }
        
        # Send request and get response
        response = self._send_request(request, timeout)
        
        if response and response.get("status") == "success":
            return response.get("results", [])
        else:
            error = response.get("error", "Unknown error") if response else "Timeout"
            logger.warning(f"Knowledge search failed: {error}")
            return []
    
    def store(self, content: str, tags: Optional[List[str]] = None, 
              personal: bool = False, metadata: Optional[Dict[str, Any]] = None,
              timeout: float = 5.0) -> Optional[str]:
        """
        Store new knowledge.
        
        Args:
            content: The knowledge to store
            tags: Optional list of tags for categorization.
            personal: If True, stores as personal knowledge (not shared with hive mind).
            metadata: Additional metadata to store. The 'tags' and 'personal' arguments
                      will be merged into this dictionary.
            timeout: How long to wait for response
            
        Returns:
            Knowledge ID if successfully stored, None otherwise
        """
        # Rate limiting
        self._wait_for_rate_limit()
        
        # Prepare request
        request_id = self._generate_request_id()
        
        # Build metadata
        full_metadata: Dict[str, Any] = {
            "tags": tags if tags is not None else [],
            "personal": personal
        }
        if metadata:
            full_metadata.update(metadata)
        
        request = {
            "request_id": request_id,
            "operation": "store",
            "content": content,
            "metadata": full_metadata
        }
        
        # Send request and get response
        response = self._send_request(request, timeout)
        
        if response and response.get("status") == "success":
            knowledge_id = response.get("knowledge_id")
            logger.info(f"Stored {'personal' if personal else 'shared'} knowledge: {knowledge_id}")
            return knowledge_id
        else:
            error = response.get("error", "Unknown error") if response else "Timeout"
            logger.warning(f"Knowledge store failed: {error}")
            return None
    
    def get(self, knowledge_id: str, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """
        Get knowledge by its ID.
        
        Args:
            knowledge_id: ID of knowledge to retrieve
            timeout: How long to wait for response
            
        Returns:
            Knowledge item dictionary if found, None otherwise
            Returns same structure as search() results
            
        Example:
            # Get existing knowledge to append to it
            existing = knowledge.get("knowledge_123")
            if existing:
                updated_content = existing['content'] + "\n\nAdditional insights..."
                knowledge.update("knowledge_123", content=updated_content)
        """
        # Rate limiting
        self._wait_for_rate_limit()
        
        # Prepare request
        request_id = self._generate_request_id()
        
        request = {
            "request_id": request_id,
            "operation": "get",
            "knowledge_id": knowledge_id
        }
        
        # Send request and get response
        response = self._send_request(request, timeout)
        
        if response and response.get("status") == "success":
            result = response.get("result")
            if result:
                logger.info(f"Retrieved knowledge: {knowledge_id}")
                return result
            else:
                logger.warning(f"Knowledge not found: {knowledge_id}")
                return None
        else:
            error = response.get("error", "Unknown error") if response else "Timeout"
            logger.warning(f"Knowledge get failed: {error}")
            return None
    
    def forget(self, knowledge_id: str, timeout: float = 5.0) -> bool:
        """
        Remove knowledge by ID.
        
        Args:
            knowledge_id: ID of knowledge to remove
            timeout: How long to wait for response
            
        Returns:
            True if successfully removed, False otherwise
        """
        # Rate limiting
        self._wait_for_rate_limit()
        
        # Prepare request
        request_id = self._generate_request_id()
        
        request = {
            "request_id": request_id,
            "operation": "forget",
            "knowledge_id": knowledge_id
        }
        
        # Send request and get response
        response = self._send_request(request, timeout)
        
        if response and response.get("status") == "success":
            logger.info(f"Forgot knowledge: {knowledge_id}")
            return True
        else:
            error = response.get("error", "Unknown error") if response else "Timeout"
            logger.warning(f"Knowledge forget failed: {error}")
            return False
    
    def update(self, knowledge_id: str, content: Optional[str] = None, 
               tags: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None,
               timeout: float = 5.0) -> bool:
        """
        Update existing knowledge by ID. Any provided fields will overwrite existing ones.
        
        Args:
            knowledge_id: ID of knowledge to update
            content: New content (if provided, replaces existing content)
            tags: New list of tags (if provided, replaces existing tags)
            metadata: Dictionary of metadata fields to update or add.
            timeout: How long to wait for response
            
        Returns:
            True if successfully updated, False otherwise
            
        Example:
            # Update content only
            knowledge.update("knowledge_123", content="Updated insight about OODA loops")
            
            # Update tags only
            knowledge.update("knowledge_123", tags=["cognitive", "updated"])
            
            # Update metadata only
            knowledge.update("knowledge_123", metadata={"confidence": 0.95})
        """
        # Rate limiting
        self._wait_for_rate_limit()
        
        # Prepare request
        request_id = self._generate_request_id()
        
        request: Dict[str, Any] = {
            "request_id": request_id,
            "operation": "update",
            "knowledge_id": knowledge_id
        }
        
        # Add optional update fields
        if content is not None:
            request["content"] = content
        if tags is not None:
            request["tags"] = tags
        if metadata is not None:
            request["metadata"] = metadata
        
        # Send request and get response
        response = self._send_request(request, timeout)
        
        if response and response.get("status") == "success":
            logger.info(f"Updated knowledge: {knowledge_id}")
            return True
        else:
            error = response.get("error", "Unknown error") if response else "Timeout"
            logger.warning(f"Knowledge update failed: {error}")
            return False
    
    def remember(self, context: str, limit: int = 3) -> str:
        """
        Get formatted knowledge for brain augmentation.
        
        This is a convenience method that searches for relevant knowledge
        and formats it for inclusion in brain prompts.
        
        Args:
            context: Current context to find relevant knowledge for
            limit: Maximum items to include
            
        Returns:
            Formatted string of relevant knowledge for brain prompt
        """
        results = self.search(context, limit=limit)
        
        if not results:
            return ""
        
        knowledge_text = "\n## Relevant Knowledge\n\n"
        for i, item in enumerate(results, 1):
            # Include content
            knowledge_text += f"{i}. {item['content']}\n"
            
            # Add metadata if available
            metadata = item.get('metadata', {})
            if metadata.get('tags'):
                knowledge_text += f"   Tags: {', '.join(metadata['tags'])}\n"
            if metadata.get('cyber_id'):
                knowledge_text += f"   Source: {metadata['cyber_id']}\n"
            if item.get('score', 0) > 0:
                knowledge_text += f"   Relevance: {item['score']:.2f}\n"
            
            knowledge_text += "\n"
        
        return knowledge_text
    
    def share_learning(self, content: str, category: str = "experience", 
                      confidence: float = 0.8) -> Optional[str]:
        """
        Share a learning or insight with the hive mind.
        
        This is a convenience method for storing knowledge with
        appropriate metadata for shared learnings.
        
        Args:
            content: The learning or insight to share
            category: Category of the learning (e.g., "experience", "discovery", "warning")
            confidence: Confidence level (0-1)
            
        Returns:
            Knowledge ID if stored successfully
        """
        return self.store(
            content=content,
            tags=["learning", category],
            personal=False,
            metadata={
                "category": category,
                "confidence": confidence,
                "type": "learning"
            }
        )
    
    def search_by_tags(self, tags: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for knowledge by tags.
        
        Args:
            tags: Tags to search for
            limit: Maximum results
            
        Returns:
            List of matching knowledge items
        """
        # Build a query from tags
        query = " ".join(tags)
        return self.search(query, limit=limit)
    
    # Private helper methods
    
    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        cyber_id = self.memory._context.get('cyber_id', 'unknown')
        self.request_counter += 1
        timestamp = int(time.time() * 1000)
        return f"knowledge_{cyber_id}_{timestamp}_{self.request_counter}"
    
    def _wait_for_rate_limit(self):
        """Enforce rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._min_request_interval:
            time.sleep(self._min_request_interval - time_since_last)
        self._last_request_time = time.time()
    
    def _send_request(self, request: Dict[str, Any], timeout: float) -> Optional[Dict[str, Any]]:
        """
        Send a request to the knowledge body file and wait for response.
        
        Args:
            request: Request dictionary
            timeout: How long to wait for response
            
        Returns:
            Response dictionary or None if timeout
        """
        try:
            # Write request with end marker
            request_text = json.dumps(request, indent=2)
            full_request = f"{request_text}\n<<<END_KNOWLEDGE_REQUEST>>>"
            self.knowledge_file.write_text(full_request)
            
            # Wait for response with completion marker
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    content = self.knowledge_file.read_text()
                    
                    # Check for completion marker
                    if "<<<KNOWLEDGE_COMPLETE>>>" in content:
                        # Extract response (everything before the marker)
                        response_text = content.split("<<<KNOWLEDGE_COMPLETE>>>")[0].strip()
                        
                        # Parse the response
                        response = json.loads(response_text)
                        
                        # Verify this is our response
                        if response.get("request_id") == request["request_id"]:
                            # Clear the file for next request
                            self.knowledge_file.write_text("")
                            return response
                        
                except json.JSONDecodeError:
                    # Response might still be writing
                    pass
                except Exception as e:
                    logger.error(f"Error reading knowledge response: {e}")
                    
                # Small delay before checking again
                time.sleep(0.05)
            
            # Timeout reached - clear file
            self.knowledge_file.write_text("")
            logger.warning(f"Knowledge request timed out after {timeout}s")
            return None
            
        except Exception as e:
            logger.error(f"Error sending knowledge request: {e}")
            return None
    
    def __repr__(self) -> str:
        """String representation."""
        cyber_id = self.memory._context.get('cyber_id', 'unknown')
        return f"Knowledge(cyber_id='{cyber_id}')"