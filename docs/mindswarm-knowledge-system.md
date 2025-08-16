# Mind-Swarm Knowledge System Implementation Guide

## Overview

This document outlines the implementation of a searchable knowledge system for Mind-Swarm Cybers using a hybrid RAG (Retrieval-Augmented Generation) approach with ChromaDB as the vector database backend.

## System Architecture

### Core Components

1. **Vector Database**: ChromaDB for efficient semantic search
2. **Embedding Model**: Sentence-BERT (all-MiniLM-L6-v2) for text vectorization
3. **Knowledge Storage**: Dual-collection system (personal + shared)
4. **Update System**: Incremental indexing with deduplication
5. **File Sync**: Automatic synchronization with JSON/Markdown files

## Installation Requirements

```bash
pip install chromadb
pip install sentence-transformers
pip install watchdog  # For file monitoring
pip install xxhash    # For fast hashing
```

## Implementation

### 1. Core Knowledge Base Class

```python
# knowledge_base.py
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class CyberKnowledgeBase:
    """
    Manages personal and shared knowledge for a Cyber agent.
    Uses ChromaDB for vector storage and retrieval.
    """
    
    def __init__(self, 
                 cyber_id: str,
                 shared_db_path: str = "./shared_knowledge",
                 personal_db_path: str = "./personal_knowledge",
                 embedding_model: str = "all-MiniLM-L6-v2"):
        """
        Initialize the knowledge base for a specific Cyber.
        
        Args:
            cyber_id: Unique identifier for the Cyber
            shared_db_path: Path to shared knowledge database
            personal_db_path: Path to personal knowledge database
            embedding_model: Name of the sentence transformer model
        """
        self.cyber_id = cyber_id
        
        # Create database directories if they don't exist
        Path(f"{personal_db_path}/{cyber_id}").mkdir(parents=True, exist_ok=True)
        Path(shared_db_path).mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB clients
        self.personal_client = chromadb.PersistentClient(
            path=f"{personal_db_path}/{cyber_id}"
        )
        self.shared_client = chromadb.PersistentClient(
            path=shared_db_path
        )
        
        # Initialize embedding function
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )
        
        # Initialize collections
        self.personal_collection = self._init_collection(
            self.personal_client, 
            f"cyber_{cyber_id}_knowledge"
        )
        self.shared_collection = self._init_collection(
            self.shared_client, 
            "shared_knowledge"
        )
        
        # Track knowledge hashes for deduplication
        self.knowledge_hashes = self._load_hash_index()
        
        logger.info(f"Knowledge base initialized for Cyber {cyber_id}")
    
    def _init_collection(self, client, name: str):
        """Initialize or retrieve a ChromaDB collection."""
        return client.get_or_create_collection(
            name=name,
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )
    
    def _load_hash_index(self) -> set:
        """Load existing content hashes to prevent duplicates."""
        hashes = set()
        
        # Load from personal collection
        try:
            personal_data = self.personal_collection.get()
            if personal_data and 'metadatas' in personal_data:
                for metadata in personal_data['metadatas']:
                    if metadata and 'content_hash' in metadata:
                        hashes.add(metadata['content_hash'])
        except Exception as e:
            logger.warning(f"Could not load personal hashes: {e}")
        
        # Load from shared collection (only this cyber's contributions)
        try:
            shared_data = self.shared_collection.get(
                where={"owner": self.cyber_id}
            )
            if shared_data and 'metadatas' in shared_data:
                for metadata in shared_data['metadatas']:
                    if metadata and 'content_hash' in metadata:
                        hashes.add(metadata['content_hash'])
        except Exception as e:
            logger.warning(f"Could not load shared hashes: {e}")
        
        return hashes
    
    def search(self, 
               query: str,
               scope: List[str] = ['personal', 'shared'],
               top_k: int = 5,
               metadata_filter: Optional[Dict] = None) -> List[Dict]:
        """
        Search for relevant knowledge across specified scopes.
        
        Args:
            query: Search query text
            scope: List of scopes to search ['personal', 'shared']
            top_k: Number of results to return
            metadata_filter: Optional metadata filters
        
        Returns:
            List of relevant knowledge entries
        """
        results = []
        
        if 'personal' in scope:
            personal_results = self._search_collection(
                self.personal_collection,
                query,
                top_k,
                metadata_filter
            )
            results.extend(personal_results)
        
        if 'shared' in scope:
            shared_filter = metadata_filter or {}
            # Don't retrieve private shared knowledge
            shared_filter["access_level"] = {"$ne": "private"}
            
            shared_results = self._search_collection(
                self.shared_collection,
                query,
                top_k,
                shared_filter
            )
            results.extend(shared_results)
        
        # Sort by relevance score and return top_k
        results.sort(key=lambda x: x.get('score', 0), reverse=True)
        return results[:top_k]
    
    def _search_collection(self, 
                          collection,
                          query: str,
                          top_k: int,
                          metadata_filter: Optional[Dict]) -> List[Dict]:
        """Search a specific collection."""
        try:
            query_result = collection.query(
                query_texts=[query],
                n_results=top_k,
                where=metadata_filter if metadata_filter else None
            )
            
            # Format results
            formatted_results = []
            if query_result['documents'] and query_result['documents'][0]:
                for i, doc in enumerate(query_result['documents'][0]):
                    formatted_results.append({
                        'content': doc,
                        'metadata': query_result['metadatas'][0][i] if query_result['metadatas'] else {},
                        'score': 1.0 - query_result['distances'][0][i] if query_result['distances'] else 0,
                        'id': query_result['ids'][0][i] if query_result['ids'] else None
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    def add_knowledge(self,
                     content: str,
                     metadata: Dict,
                     knowledge_type: str = 'personal') -> bool:
        """
        Add new knowledge to the database.
        
        Args:
            content: The knowledge content
            metadata: Metadata about the knowledge
            knowledge_type: 'personal' or 'shared'
        
        Returns:
            True if successfully added, False if duplicate
        """
        # Generate content hash for deduplication
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        if content_hash in self.knowledge_hashes:
            logger.debug(f"Duplicate knowledge detected: {content_hash[:8]}")
            return False
        
        # Add metadata fields
        metadata['content_hash'] = content_hash
        metadata['owner'] = self.cyber_id
        metadata['timestamp'] = datetime.now().isoformat()
        
        # Generate unique ID
        knowledge_id = f"{self.cyber_id}_{content_hash[:8]}_{datetime.now().timestamp()}"
        
        # Select collection
        collection = (self.personal_collection 
                     if knowledge_type == 'personal' 
                     else self.shared_collection)
        
        try:
            collection.add(
                documents=[content],
                metadatas=[metadata],
                ids=[knowledge_id]
            )
            self.knowledge_hashes.add(content_hash)
            logger.info(f"Added {knowledge_type} knowledge: {knowledge_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add knowledge: {e}")
            return False
    
    def update_knowledge(self, 
                        knowledge_id: str,
                        new_content: Optional[str] = None,
                        new_metadata: Optional[Dict] = None) -> bool:
        """Update existing knowledge entry."""
        # Implementation for updating existing knowledge
        pass
    
    def delete_knowledge(self, knowledge_id: str) -> bool:
        """Delete knowledge entry."""
        # Implementation for deleting knowledge
        pass
```

### 2. Cognitive Loop Integration

```python
# cognitive_integration.py
from typing import Dict, List, Optional, Any
import time
from collections import OrderedDict
from knowledge_base import CyberKnowledgeBase

class EnhancedCognitiveCycle:
    """
    Enhanced cognitive cycle with integrated knowledge retrieval.
    """
    
    def __init__(self, cyber_id: str, cache_ttl: int = 60):
        """
        Initialize cognitive cycle with knowledge base.
        
        Args:
            cyber_id: Unique identifier for the Cyber
            cache_ttl: Cache time-to-live in seconds
        """
        self.cyber_id = cyber_id
        self.kb = CyberKnowledgeBase(cyber_id)
        self.cache_ttl = cache_ttl
        
        # LRU cache for query results
        self.query_cache = OrderedDict()
        self.cache_timestamps = {}
        self.max_cache_size = 100
    
    def think(self, 
              current_context: Dict,
              task: Optional[Dict] = None) -> Dict:
        """
        Main cognitive loop with automatic knowledge retrieval.
        
        Args:
            current_context: Current environmental/situational context
            task: Optional current task information
        
        Returns:
            Action decision with rationale
        """
        # Step 1: Analyze context and extract key concepts
        key_concepts = self._extract_concepts(current_context, task)
        
        # Step 2: Retrieve relevant knowledge
        relevant_knowledge = self._retrieve_with_cache(
            query=self._build_query(key_concepts),
            metadata_filter=self._build_filters(current_context, task)
        )
        
        # Step 3: Augment context with knowledge
        enhanced_context = self._augment_context(
            current_context,
            relevant_knowledge,
            task
        )
        
        # Step 4: Make decision based on enhanced context
        action = self._decide_action(enhanced_context)
        
        # Step 5: Learn from decision if applicable
        if action.get('generates_knowledge'):
            self._update_knowledge_from_action(action)
        
        return action
    
    def _extract_concepts(self, 
                         context: Dict,
                         task: Optional[Dict]) -> List[str]:
        """Extract key concepts from context and task."""
        concepts = []
        
        # Extract from context
        if 'environment' in context:
            concepts.extend(context['environment'].get('objects', []))
            concepts.extend(context['environment'].get('conditions', []))
        
        if 'recent_events' in context:
            for event in context['recent_events']:
                if 'type' in event:
                    concepts.append(event['type'])
        
        # Extract from task
        if task:
            if 'goal' in task:
                concepts.append(task['goal'])
            if 'constraints' in task:
                concepts.extend(task['constraints'])
        
        return list(set(concepts))  # Remove duplicates
    
    def _build_query(self, concepts: List[str]) -> str:
        """Build search query from concepts."""
        if not concepts:
            return "general knowledge"
        
        # Combine concepts into a coherent query
        return " ".join(concepts[:5])  # Limit to top 5 concepts
    
    def _build_filters(self, 
                      context: Dict,
                      task: Optional[Dict]) -> Optional[Dict]:
        """Build metadata filters based on context."""
        filters = {}
        
        # Filter by task category if available
        if task and 'category' in task:
            filters['category'] = task['category']
        
        # Filter by relevance timeframe
        if 'timeframe' in context:
            if context['timeframe'] == 'recent':
                # Only get knowledge from last 7 days
                from datetime import datetime, timedelta
                cutoff = (datetime.now() - timedelta(days=7)).isoformat()
                filters['timestamp'] = {"$gte": cutoff}
        
        return filters if filters else None
    
    def _retrieve_with_cache(self, 
                            query: str,
                            metadata_filter: Optional[Dict] = None) -> List[Dict]:
        """Retrieve knowledge with caching."""
        # Generate cache key
        cache_key = f"{query}_{str(metadata_filter)}"
        
        # Check cache
        if cache_key in self.query_cache:
            timestamp = self.cache_timestamps[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                # Move to end (LRU)
                self.query_cache.move_to_end(cache_key)
                return self.query_cache[cache_key]
        
        # Perform search
        results = self.kb.search(
            query=query,
            scope=['personal', 'shared'],
            top_k=5,
            metadata_filter=metadata_filter
        )
        
        # Update cache
        self._update_cache(cache_key, results)
        
        return results
    
    def _update_cache(self, key: str, value: List[Dict]):
        """Update LRU cache."""
        # Remove oldest if cache is full
        if len(self.query_cache) >= self.max_cache_size:
            oldest = next(iter(self.query_cache))
            del self.query_cache[oldest]
            del self.cache_timestamps[oldest]
        
        self.query_cache[key] = value
        self.cache_timestamps[key] = time.time()
    
    def _augment_context(self, 
                        context: Dict,
                        knowledge: List[Dict],
                        task: Optional[Dict]) -> Dict:
        """Augment context with retrieved knowledge."""
        enhanced = context.copy()
        
        # Add knowledge to context
        enhanced['retrieved_knowledge'] = knowledge
        
        # Extract key insights
        insights = []
        for item in knowledge:
            if item['score'] > 0.7:  # High relevance threshold
                insights.append({
                    'content': item['content'],
                    'relevance': item['score'],
                    'source': item['metadata'].get('source', 'unknown')
                })
        
        enhanced['key_insights'] = insights
        
        # Add task-specific knowledge if applicable
        if task:
            task_knowledge = [k for k in knowledge 
                            if k['metadata'].get('category') == task.get('category')]
            enhanced['task_specific_knowledge'] = task_knowledge
        
        return enhanced
    
    def _decide_action(self, enhanced_context: Dict) -> Dict:
        """
        Make action decision based on enhanced context.
        This is where you'd integrate with your AI model.
        """
        action = {
            'type': 'explore',  # Default action
            'confidence': 0.5,
            'rationale': [],
            'generates_knowledge': False
        }
        
        # Use retrieved knowledge to inform decision
        if enhanced_context.get('key_insights'):
            # Adjust action based on insights
            for insight in enhanced_context['key_insights']:
                if 'danger' in insight['content'].lower():
                    action['type'] = 'avoid'
                    action['rationale'].append('Knowledge indicates danger')
                elif 'opportunity' in insight['content'].lower():
                    action['type'] = 'investigate'
                    action['rationale'].append('Knowledge suggests opportunity')
        
        # Mark if this action will generate new knowledge
        if action['type'] in ['explore', 'investigate', 'experiment']:
            action['generates_knowledge'] = True
        
        return action
    
    def _update_knowledge_from_action(self, action: Dict):
        """Update knowledge base based on action results."""
        if 'result' in action and action['result']:
            content = f"Action {action['type']} resulted in: {action['result']}"
            metadata = {
                'category': 'experience',
                'action_type': action['type'],
                'confidence': action.get('confidence', 0),
                'tags': ['learned', 'action_result']
            }
            
            self.kb.add_knowledge(
                content=content,
                metadata=metadata,
                knowledge_type='personal'
            )
```

### 3. Incremental Update System

```python
# incremental_updater.py
from typing import List, Dict, Optional
from threading import Thread, Lock
from queue import Queue
import time
import logging
from knowledge_base import CyberKnowledgeBase

logger = logging.getLogger(__name__)

class IncrementalKnowledgeUpdater:
    """
    Handles incremental updates to the knowledge base with batching
    and deduplication.
    """
    
    def __init__(self, 
                 knowledge_base: CyberKnowledgeBase,
                 batch_size: int = 10,
                 batch_timeout: float = 5.0):
        """
        Initialize the updater.
        
        Args:
            knowledge_base: The knowledge base to update
            batch_size: Number of updates to batch together
            batch_timeout: Maximum time to wait before processing batch
        """
        self.kb = knowledge_base
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        
        # Thread-safe queue for updates
        self.update_queue = Queue()
        self.processing_lock = Lock()
        
        # Start background processor
        self.processor_thread = Thread(target=self._process_updates, daemon=True)
        self.processor_thread.start()
        
        # Statistics
        self.stats = {
            'total_added': 0,
            'duplicates_rejected': 0,
            'batches_processed': 0
        }
    
    def add_knowledge(self, 
                     content: str,
                     metadata: Dict,
                     knowledge_type: str = 'personal',
                     priority: int = 0):
        """
        Queue knowledge for addition.
        
        Args:
            content: Knowledge content
            metadata: Knowledge metadata
            knowledge_type: 'personal' or 'shared'
            priority: Higher priority items are processed first
        """
        self.update_queue.put({
            'content': content,
            'metadata': metadata,
            'knowledge_type': knowledge_type,
            'priority': priority,
            'timestamp': time.time()
        })
    
    def _process_updates(self):
        """Background thread to process update queue."""
        batch = []
        last_process_time = time.time()
        
        while True:
            try:
                # Wait for item with timeout
                timeout = max(0.1, self.batch_timeout - (time.time() - last_process_time))
                
                try:
                    item = self.update_queue.get(timeout=timeout)
                    batch.append(item)
                except:
                    pass  # Timeout is normal
                
                # Process batch if conditions met
                should_process = (
                    len(batch) >= self.batch_size or
                    (len(batch) > 0 and time.time() - last_process_time >= self.batch_timeout)
                )
                
                if should_process:
                    self._process_batch(batch)
                    batch = []
                    last_process_time = time.time()
                    
            except Exception as e:
                logger.error(f"Update processor error: {e}")
                time.sleep(1)
    
    def _process_batch(self, batch: List[Dict]):
        """Process a batch of updates."""
        if not batch:
            return
        
        with self.processing_lock:
            # Sort by priority
            batch.sort(key=lambda x: x['priority'], reverse=True)
            
            # Group by knowledge type
            personal_items = []
            shared_items = []
            
            for item in batch:
                if item['knowledge_type'] == 'personal':
                    personal_items.append(item)
                else:
                    shared_items.append(item)
            
            # Process each group
            for items, knowledge_type in [(personal_items, 'personal'), 
                                         (shared_items, 'shared')]:
                if items:
                    success_count = self._batch_add(items, knowledge_type)
                    self.stats['total_added'] += success_count
                    self.stats['duplicates_rejected'] += len(items) - success_count
            
            self.stats['batches_processed'] += 1
            
            logger.info(f"Processed batch of {len(batch)} items. "
                       f"Total added: {self.stats['total_added']}, "
                       f"Duplicates: {self.stats['duplicates_rejected']}")
    
    def _batch_add(self, items: List[Dict], knowledge_type: str) -> int:
        """Add multiple items to knowledge base."""
        success_count = 0
        
        for item in items:
            success = self.kb.add_knowledge(
                content=item['content'],
                metadata=item['metadata'],
                knowledge_type=knowledge_type
            )
            if success:
                success_count += 1
        
        return success_count
    
    def flush(self):
        """Force process all pending updates."""
        batch = []
        while not self.update_queue.empty():
            try:
                batch.append(self.update_queue.get_nowait())
            except:
                break
        
        if batch:
            self._process_batch(batch)
    
    def get_stats(self) -> Dict:
        """Get updater statistics."""
        return self.stats.copy()
```

### 4. File Synchronization System

```python
# file_sync.py
from pathlib import Path
from typing import List, Dict, Set
import json
import hashlib
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from knowledge_base import CyberKnowledgeBase
from incremental_updater import IncrementalKnowledgeUpdater

logger = logging.getLogger(__name__)

class KnowledgeFileSync(FileSystemEventHandler):
    """
    Monitors and syncs knowledge from JSON/Markdown files.
    """
    
    def __init__(self, 
                 knowledge_base: CyberKnowledgeBase,
                 updater: IncrementalKnowledgeUpdater,
                 watch_dirs: List[str],
                 chunk_size: int = 1000):
        """
        Initialize file sync system.
        
        Args:
            knowledge_base: Knowledge base instance
            updater: Incremental updater instance
            watch_dirs: Directories to watch for knowledge files
            chunk_size: Maximum characters per chunk
        """
        self.kb = knowledge_base
        self.updater = updater
        self.watch_dirs = watch_dirs
        self.chunk_size = chunk_size
        
        # Track file checksums
        self.file_checksums = {}
        
        # Setup file watchers
        self.observer = Observer()
        for directory in watch_dirs:
            self.observer.schedule(self, directory, recursive=True)
    
    def start(self):
        """Start file monitoring."""
        # Initial sync
        self.sync_all_files()
        
        # Start watching for changes
        self.observer.start()
        logger.info(f"File sync started for directories: {self.watch_dirs}")
    
    def stop(self):
        """Stop file monitoring."""
        self.observer.stop()
        self.observer.join()
    
    def sync_all_files(self):
        """Sync all existing knowledge files."""
        for directory in self.watch_dirs:
            path = Path(directory)
            if path.exists():
                # Process JSON files
                for file_path in path.glob("**/*.json"):
                    self._process_file(file_path)
                
                # Process Markdown files
                for file_path in path.glob("**/*.md"):
                    self._process_file(file_path)
    
    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory:
            file_path = Path(event.src_path)
            if file_path.suffix in ['.json', '.md']:
                self._process_file(file_path)
    
    def on_created(self, event):
        """Handle file creation events."""
        self.on_modified(event)
    
    def _process_file(self, file_path: Path):
        """Process a knowledge file."""
        try:
            # Check if file has changed
            current_checksum = self._get_file_checksum(file_path)
            
            if (str(file_path) in self.file_checksums and 
                self.file_checksums[str(file_path)] == current_checksum):
                return  # File hasn't changed
            
            # Parse file based on type
            if file_path.suffix == '.json':
                knowledge_items = self._parse_json_file(file_path)
            elif file_path.suffix == '.md':
                knowledge_items = self._parse_markdown_file(file_path)
            else:
                return
            
            # Add knowledge items
            for item in knowledge_items:
                self.updater.add_knowledge(
                    content=item['content'],
                    metadata=item['metadata'],
                    knowledge_type=item.get('type', 'shared')
                )
            
            # Update checksum
            self.file_checksums[str(file_path)] = current_checksum
            
            logger.info(f"Processed file: {file_path} ({len(knowledge_items)} items)")
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
    
    def _get_file_checksum(self, file_path: Path) -> str:
        """Calculate file checksum."""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def _parse_json_file(self, file_path: Path) -> List[Dict]:
        """Parse JSON knowledge file."""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        items = []
        
        # Handle different JSON structures
        if isinstance(data, list):
            # Array of knowledge items
            for item in data:
                items.append(self._process_json_item(item, file_path))
        elif isinstance(data, dict):
            if 'knowledge' in data:
                # Wrapped knowledge array
                for item in data['knowledge']:
                    items.append(self._process_json_item(item, file_path))
            else:
                # Single knowledge item
                items.append(self._process_json_item(data, file_path))
        
        return items
    
    def _process_json_item(self, item: Dict, file_path: Path) -> Dict:
        """Process a single JSON knowledge item."""
        # Extract or generate metadata
        metadata = item.get('metadata', {})
        metadata['source_file'] = str(file_path)
        metadata['file_type'] = 'json'
        
        # Determine knowledge type from path or metadata
        knowledge_type = 'personal' if 'personal' in str(file_path) else 'shared'
        
        return {
            'content': item.get('content', str(item)),
            'metadata': metadata,
            'type': item.get('type', knowledge_type)
        }
    
    def _parse_markdown_file(self, file_path: Path) -> List[Dict]:
        """Parse Markdown knowledge file."""
        with open(file_path, 'r') as f:
            content = f.read()
        
        items = []
        
        # Extract metadata from frontmatter if present
        metadata = self._extract_frontmatter(content)
        metadata['source_file'] = str(file_path)
        metadata['file_type'] = 'markdown'
        
        # Chunk content if necessary
        chunks = self._chunk_text(content, self.chunk_size)
        
        for i, chunk in enumerate(chunks):
            chunk_metadata = metadata.copy()
            chunk_metadata['chunk_index'] = i
            chunk_metadata['total_chunks'] = len(chunks)
            
            items.append({
                'content': chunk,
                'metadata': chunk_metadata,
                'type': 'shared'
            })
        
        return items
    
    def _extract_frontmatter(self, content: str) -> Dict:
        """Extract YAML frontmatter from Markdown."""
        metadata = {}
        
        if content.startswith('---'):
            try:
                import yaml
                end_index = content.find('---', 3)
                if end_index > 0:
                    frontmatter = content[3:end_index]
                    metadata = yaml.safe_load(frontmatter) or {}
            except:
                pass
        
        return metadata
    
    def _chunk_text(self, text: str, max_size: int) -> List[str]:
        """Split text into chunks."""
        if len(text) <= max_size:
            return [text]
        
        chunks = []
        current_chunk = ""
        
        # Try to split on paragraph boundaries
        paragraphs = text.split('\n\n')
        
        for para in paragraphs:
            if len(current_chunk) + len(para) <= max_size:
                current_chunk += para + '\n\n'
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + '\n\n'
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
```

### 5. Integration with Mind-Swarm Cyber

```python
# cyber_integration.py
from typing import Dict, Optional, Any
import logging
from datetime import datetime
from knowledge_base import CyberKnowledgeBase
from cognitive_integration import EnhancedCognitiveCycle
from incremental_updater import IncrementalKnowledgeUpdater
from file_sync import KnowledgeFileSync

logger = logging.getLogger(__name__)

class EnhancedCyber:
    """
    Enhanced Cyber agent with integrated knowledge system.
    """
    
    def __init__(self, 
                 cyber_id: str,
                 config: Dict,
                 knowledge_dirs: Optional[List[str]] = None):
        """
        Initialize enhanced Cyber with knowledge capabilities.
        
        Args:
            cyber_id: Unique identifier for this Cyber
            config: Configuration dictionary
            knowledge_dirs: Directories to watch for knowledge files
        """
        self.id = cyber_id
        self.config = config
        
        # Initialize knowledge components
        self.knowledge_base = CyberKnowledgeBase(
            cyber_id=cyber_id,
            shared_db_path=config.get('shared_knowledge_path', './shared_knowledge'),
            personal_db_path=config.get('personal_knowledge_path', './personal_knowledge')
        )
        
        self.cognitive_cycle = EnhancedCognitiveCycle(cyber_id)
        
        self.updater = IncrementalKnowledgeUpdater(
            knowledge_base=self.knowledge_base,
            batch_size=config.get('knowledge_batch_size', 10),
            batch_timeout=config.get('knowledge_batch_timeout', 5.0)
        )
        
        # Setup file sync if directories provided
        self.file_sync = None
        if knowledge_dirs:
            self.file_sync = KnowledgeFileSync(
                knowledge_base=self.knowledge_base,
                updater=self.updater,
                watch_dirs=knowledge_dirs
            )
            self.file_sync.start()
        
        # Track state
        self.current_task = None
        self.experience_buffer = []
        
        logger.info(f"Enhanced Cyber {cyber_id} initialized")
    
    def process_cycle(self, environment_state: Dict) -> Dict:
        """
        Main processing cycle with integrated knowledge.
        
        Args:
            environment_state: Current state of the environment
        
        Returns:
            Action to take
        """
        # Use cognitive cycle with automatic knowledge retrieval
        action = self.cognitive_cycle.think(
            current_context=environment_state,
            task=self.current_task
        )
        
        # Store experience for learning
        self.experience_buffer.append({
            'state': environment_state,
            'action': action,
            'timestamp': datetime.now()
        })
        
        # Learn from experience periodically
        if len(self.experience_buffer) >= 10:
            self._consolidate_experiences()
        
        return action
    
    def _consolidate_experiences(self):
        """Consolidate experiences into knowledge."""
        if not self.experience_buffer:
            return
        
        # Analyze patterns in experiences
        patterns = self._analyze_experience_patterns(self.experience_buffer)
        
        for pattern in patterns:
            self.updater.add_knowledge(
                content=pattern['description'],
                metadata={
                    'category': 'learned_pattern',
                    'confidence': pattern['confidence'],
                    'frequency': pattern['frequency'],
                    'tags': pattern['tags']
                },
                knowledge_type='personal'
            )
        
        # Clear buffer
        self.experience_buffer = []
    
    def _analyze_experience_patterns(self, experiences: List[Dict]) -> List[Dict]:
        """Analyze experiences for patterns."""
        patterns = []
        
        # Group by action type
        action_groups = {}
        for exp in experiences:
            action_type = exp['action']['type']
            if action_type not in action_groups:
                action_groups[action_type] = []
            action_groups[action_type].append(exp)
        
        # Extract patterns from groups
        for action_type, group in action_groups.items():
            if len(group) >= 3:  # Minimum frequency for pattern
                pattern = {
                    'description': f"Action '{action_type}' frequently taken in similar contexts",
                    'confidence': len(group) / len(experiences),
                    'frequency': len(group),
                    'tags': [action_type, 'behavioral_pattern']
                }
                patterns.append(pattern)
        
        return patterns
    
    def share_knowledge(self, content: str, metadata: Dict):
        """Share knowledge with other Cybers."""
        metadata['shared_by'] = self.id
        metadata['access_level'] = metadata.get('access_level', 'public')
        
        self.updater.add_knowledge(
            content=content,
            metadata=metadata,
            knowledge_type='shared',
            priority=1  # Higher priority for shared knowledge
        )
    
    def query_knowledge(self, query: str, scope: List[str] = None) -> List[Dict]:
        """
        Query knowledge base directly.
        
        Args:
            query: Search query
            scope: Scopes to search (default: ['personal', 'shared'])
        
        Returns:
            List of relevant knowledge entries
        """
        if scope is None:
            scope = ['personal', 'shared']
        
        return self.knowledge_base.search(
            query=query,
            scope=scope,
            top_k=10
        )
    
    def get_knowledge_stats(self) -> Dict:
        """Get statistics about knowledge base."""
        stats = {
            'cyber_id': self.id,
            'updater_stats': self.updater.get_stats(),
            'cache_size': len(self.cognitive_cycle.query_cache),
            'experience_buffer_size': len(self.experience_buffer)
        }
        
        # Get collection sizes
        try:
            personal_data = self.knowledge_base.personal_collection.get()
            stats['personal_knowledge_count'] = len(personal_data.get('ids', []))
        except:
            stats['personal_knowledge_count'] = 0
        
        try:
            shared_data = self.knowledge_base.shared_collection.get(
                where={"owner": self.id}
            )
            stats['shared_contributions'] = len(shared_data.get('ids', []))
        except:
            stats['shared_contributions'] = 0
        
        return stats
    
    def shutdown(self):
        """Clean shutdown of knowledge systems."""
        logger.info(f"Shutting down Cyber {self.id}")
        
        # Flush pending updates
        self.updater.flush()
        
        # Stop file sync
        if self.file_sync:
            self.file_sync.stop()
        
        # Consolidate final experiences
        self._consolidate_experiences()
```

## Usage Example

```python
# example_usage.py

# Initialize enhanced Cyber with knowledge system
cyber = EnhancedCyber(
    cyber_id="cyber_001",
    config={
        'shared_knowledge_path': './knowledge/shared',
        'personal_knowledge_path': './knowledge/personal',
        'knowledge_batch_size': 10,
        'knowledge_batch_timeout': 5.0
    },
    knowledge_dirs=['./knowledge/files/shared', './knowledge/files/personal']
)

# Process a cycle with automatic knowledge retrieval
environment = {
    'environment': {
        'objects': ['tree', 'rock', 'stream'],
        'conditions': ['sunny', 'warm']
    },
    'recent_events': [
        {'type': 'discovered', 'object': 'berry_bush'}
    ]
}

action = cyber.process_cycle(environment)
print(f"Action decided: {action}")

# Manually query knowledge
results = cyber.query_knowledge("berries food safe")
for result in results:
    print(f"Found: {result['content'][:100]}... (relevance: {result['score']:.2f})")

# Share knowledge with other Cybers
cyber.share_knowledge(
    content="Berry bushes near streams are often safe to eat",
    metadata={
        'category': 'survival',
        'confidence': 0.8,
        'tags': ['food', 'berries', 'safety']
    }
)

# Get knowledge statistics
stats = cyber.get_knowledge_stats()
print(f"Knowledge stats: {stats}")

# Shutdown cleanly
cyber.shutdown()
```

## Configuration File Format

```json
{
  "knowledge_system": {
    "embedding_model": "all-MiniLM-L6-v2",
    "vector_dimensions": 384,
    "shared_knowledge_path": "./knowledge/shared",
    "personal_knowledge_path": "./knowledge/personal",
    "knowledge_batch_size": 10,
    "knowledge_batch_timeout": 5.0,
    "cache_ttl": 60,
    "max_cache_size": 100,
    "chunk_size": 1000,
    "watch_directories": [
      "./knowledge/files/shared",
      "./knowledge/files/personal"
    ]
  },
  "search_settings": {
    "default_top_k": 5,
    "relevance_threshold": 0.7,
    "metadata_filters": {
      "exclude_private": true,
      "max_age_days": 30
    }
  }
}
```

## Knowledge File Formats

### JSON Format
```json
{
  "knowledge": [
    {
      "content": "Trees provide shelter and resources",
      "metadata": {
        "category": "environment",
        "tags": ["trees", "shelter", "resources"],
        "confidence": 0.9
      },
      "type": "shared"
    }
  ]
}
```

### Markdown Format
```markdown
---
category: skills
tags: [navigation, exploration]
confidence: 0.85
---

# Navigation Skills

When exploring new territories, always maintain awareness of landmarks...
```

## Performance Considerations

1. **Embedding Model**: Use `all-MiniLM-L6-v2` for optimal speed/quality balance
2. **Batch Size**: Adjust based on available memory (10-50 recommended)
3. **Cache TTL**: 60 seconds default, increase for stable knowledge
4. **Chunk Size**: 1000 characters balances context and retrieval precision
5. **Index Type**: ChromaDB uses HNSW by default, optimal for most cases

## Monitoring and Debugging

```python
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mindswarm_knowledge.log'),
        logging.StreamHandler()
    ]
)

# Monitor performance
from time import time

start = time()
results = cyber.query_knowledge("test query")
print(f"Query took {time() - start:.3f} seconds")

# Check knowledge statistics periodically
stats = cyber.get_knowledge_stats()
print(f"Personal knowledge: {stats['personal_knowledge_count']}")
print(f"Shared contributions: {stats['shared_contributions']}")
print(f"Cache hit rate: {stats['cache_size'] / stats['updater_stats']['total_added']:.2%}")
```

## Next Steps

1. **Test with small dataset** to verify functionality
2. **Benchmark query performance** with your typical knowledge size
3. **Tune parameters** based on your Cybers' behavior patterns
4. **Implement domain-specific metadata** for your use case
5. **Add specialized retrievers** for different knowledge types
6. **Consider adding a reranking layer** for improved relevance

## Additional Resources

- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Sentence Transformers](https://www.sbert.net/)
- [RAG Best Practices](https://github.com/dair-ai/Prompt-Engineering-Guide/blob/main/guides/prompts-rag.md)
