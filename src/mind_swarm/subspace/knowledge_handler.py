"""
Knowledge handler for Mind-Swarm cybers using ChromaDB for vector storage.
Provides search and storage capabilities through body file interface.
"""

import os
import json
import time
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import asyncio

try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logging.warning("ChromaDB not installed. Knowledge system will be disabled.")

logger = logging.getLogger(__name__)


class CyberKnowledgeHandler:
    """Handles knowledge operations for a specific cyber."""
    
    def __init__(self, cyber_id: str, personal_collection, shared_collection):
        self.cyber_id = cyber_id
        self.personal_collection = personal_collection
        self.shared_collection = shared_collection
        self.request_cache = {}  # Cache recent requests to avoid duplicates
        
    async def search(self, request: Dict) -> Dict:
        """Search for relevant knowledge."""
        try:
            query = request.get('query', '')
            options = request.get('options', {})
            limit = min(options.get('limit', 5), 20)  # Cap at 20 results
            scope = options.get('scope', ['personal', 'shared'])
            
            results = []
            
            # Search personal knowledge
            if 'personal' in scope and self.personal_collection:
                try:
                    personal_results = self.personal_collection.query(
                        query_texts=[query],
                        n_results=limit
                    )
                    results.extend(self._format_results(personal_results, 'personal'))
                except Exception as e:
                    logger.error(f"Error searching personal knowledge: {e}")
            
            # Search shared knowledge
            if 'shared' in scope and self.shared_collection:
                try:
                    # Don't retrieve other cybers' personal knowledge
                    shared_results = self.shared_collection.query(
                        query_texts=[query],
                        n_results=limit,
                        where={"$or": [
                            {"personal": {"$eq": False}},
                            {"personal": {"$exists": False}}
                        ]}
                    )
                    results.extend(self._format_results(shared_results, 'shared'))
                except Exception as e:
                    logger.error(f"Error searching shared knowledge: {e}")
            
            # Sort by relevance score and limit
            results.sort(key=lambda x: x.get('score', 0), reverse=True)
            results = results[:limit]
            
            return {
                "request_id": request.get('request_id'),
                "status": "success",
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Search error for {self.cyber_id}: {e}")
            return {
                "request_id": request.get('request_id'),
                "status": "error",
                "error": str(e),
                "results": []
            }
    
    async def store(self, request: Dict) -> Dict:
        """Store new knowledge."""
        try:
            content = request.get('content', '')
            metadata = request.get('metadata', {})
            is_personal = metadata.get('personal', False)
            
            # Generate unique ID
            content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
            knowledge_id = f"{self.cyber_id}_{content_hash}_{int(time.time())}"
            
            # Prepare metadata - convert lists to strings for ChromaDB
            full_metadata = {
                'cyber_id': self.cyber_id,
                'timestamp': datetime.now().isoformat(),
                'personal': is_personal
            }
            
            # Add metadata, converting lists to strings
            for key, value in metadata.items():
                if key != 'personal':  # Skip, already handled
                    if isinstance(value, list):
                        full_metadata[key] = ','.join(str(v) for v in value) if value else ''
                    else:
                        full_metadata[key] = value
            
            # Select collection
            collection = self.personal_collection if is_personal else self.shared_collection
            
            # Store the knowledge
            collection.add(
                documents=[content],
                metadatas=[full_metadata],
                ids=[knowledge_id]
            )
            
            logger.info(f"Stored {'personal' if is_personal else 'shared'} knowledge for {self.cyber_id}: {knowledge_id}")
            
            return {
                "request_id": request.get('request_id'),
                "status": "success",
                "knowledge_id": knowledge_id
            }
            
        except Exception as e:
            logger.error(f"Store error for {self.cyber_id}: {e}")
            return {
                "request_id": request.get('request_id'),
                "status": "error",
                "error": str(e)
            }
    
    async def get(self, request: Dict) -> Dict:
        """Get knowledge by ID."""
        try:
            knowledge_id = request.get('knowledge_id')
            if not knowledge_id:
                return {
                    "request_id": request.get('request_id'),
                    "status": "error",
                    "error": "knowledge_id is required"
                }
            
            # Try to get from both collections
            result = None
            source = None
            
            # Try personal collection first
            try:
                data = self.personal_collection.get(ids=[knowledge_id])
                if data and data.get('documents') and data['documents'][0]:
                    result = {
                        'content': data['documents'][0],
                        'metadata': data['metadatas'][0] if data.get('metadatas') else {},
                        'id': knowledge_id,
                        'source': 'personal',
                        'score': 1.0  # Direct lookup has perfect score
                    }
                    source = 'personal'
            except:
                pass
            
            # Try shared collection if not found
            if not result:
                try:
                    data = self.shared_collection.get(ids=[knowledge_id])
                    if data and data.get('documents') and data['documents'][0]:
                        result = {
                            'content': data['documents'][0],
                            'metadata': data['metadatas'][0] if data.get('metadatas') else {},
                            'id': knowledge_id,
                            'source': 'shared',
                            'score': 1.0  # Direct lookup has perfect score
                        }
                        source = 'shared'
                except:
                    pass
            
            if result:
                logger.info(f"Retrieved knowledge {knowledge_id} from {source} for {self.cyber_id}")
                return {
                    "request_id": request.get('request_id'),
                    "status": "success",
                    "result": result
                }
            else:
                return {
                    "request_id": request.get('request_id'),
                    "status": "success",
                    "result": None  # Not found, but not an error
                }
                
        except Exception as e:
            logger.error(f"Get error for {self.cyber_id}: {e}")
            return {
                "request_id": request.get('request_id'),
                "status": "error",
                "error": str(e)
            }
    
    async def forget(self, request: Dict) -> Dict:
        """Remove knowledge by ID."""
        try:
            knowledge_id = request.get('knowledge_id')
            if not knowledge_id:
                return {
                    "request_id": request.get('request_id'),
                    "status": "error",
                    "error": "knowledge_id is required"
                }
            
            # Try to delete from both collections
            deleted = False
            try:
                self.personal_collection.delete(ids=[knowledge_id])
                deleted = True
            except:
                pass
            
            try:
                self.shared_collection.delete(ids=[knowledge_id])
                deleted = True
            except:
                pass
            
            if deleted:
                logger.info(f"Deleted knowledge {knowledge_id} for {self.cyber_id}")
                return {
                    "request_id": request.get('request_id'),
                    "status": "success"
                }
            else:
                return {
                    "request_id": request.get('request_id'),
                    "status": "error",
                    "error": "Knowledge not found"
                }
                
        except Exception as e:
            logger.error(f"Forget error for {self.cyber_id}: {e}")
            return {
                "request_id": request.get('request_id'),
                "status": "error",
                "error": str(e)
            }
    
    async def update(self, request: Dict) -> Dict:
        """Update existing knowledge by ID."""
        try:
            knowledge_id = request.get('knowledge_id')
            if not knowledge_id:
                return {
                    "request_id": request.get('request_id'),
                    "status": "error",
                    "error": "knowledge_id is required"
                }
            
            # Try to get existing knowledge from both collections
            existing_data = None
            collection = None
            
            try:
                # Try personal collection first
                result = self.personal_collection.get(ids=[knowledge_id])
                if result and result.get('documents'):
                    existing_data = result
                    collection = self.personal_collection
            except:
                pass
            
            if not existing_data:
                try:
                    # Try shared collection
                    result = self.shared_collection.get(ids=[knowledge_id])
                    if result and result.get('documents'):
                        existing_data = result
                        collection = self.shared_collection
                except:
                    pass
            
            if not existing_data or not collection:
                return {
                    "request_id": request.get('request_id'),
                    "status": "error",
                    "error": "Knowledge not found"
                }
            
            # Prepare updated data
            existing_content = existing_data['documents'][0] if existing_data.get('documents') else ""
            existing_metadata = existing_data['metadatas'][0] if existing_data.get('metadatas') else {}
            
            # Update content if provided
            new_content = request.get('content', existing_content)
            
            # Update metadata
            new_metadata = dict(existing_metadata)
            new_metadata['updated_at'] = datetime.now().isoformat()
            new_metadata['updated_by'] = self.cyber_id
            
            # Update tags if provided
            if 'tags' in request:
                tags = request['tags']
                if isinstance(tags, list):
                    new_metadata['tags'] = ','.join(str(t) for t in tags) if tags else ''
                else:
                    new_metadata['tags'] = tags
            
            # Update additional metadata if provided
            if 'metadata' in request:
                for key, value in request['metadata'].items():
                    if isinstance(value, list):
                        new_metadata[key] = ','.join(str(v) for v in value) if value else ''
                    else:
                        new_metadata[key] = value
            
            # Delete and re-add (ChromaDB doesn't have direct update)
            collection.delete(ids=[knowledge_id])
            collection.add(
                documents=[new_content],
                metadatas=[new_metadata],
                ids=[knowledge_id]
            )
            
            logger.info(f"Updated knowledge {knowledge_id} for {self.cyber_id}")
            
            return {
                "request_id": request.get('request_id'),
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Update error for {self.cyber_id}: {e}")
            return {
                "request_id": request.get('request_id'),
                "status": "error",
                "error": str(e)
            }
    
    def _format_results(self, query_results: Dict, source: str) -> List[Dict]:
        """Format ChromaDB query results."""
        formatted = []
        
        if not query_results or not query_results.get('documents'):
            return formatted
        
        documents = query_results['documents'][0] if query_results['documents'] else []
        metadatas = query_results['metadatas'][0] if query_results.get('metadatas') else []
        distances = query_results['distances'][0] if query_results.get('distances') else []
        ids = query_results['ids'][0] if query_results.get('ids') else []
        
        for i, doc in enumerate(documents):
            if doc:  # Skip None documents
                formatted.append({
                    'content': doc,
                    'score': 1.0 - distances[i] if i < len(distances) else 0.5,
                    'metadata': metadatas[i] if i < len(metadatas) else {},
                    'id': ids[i] if i < len(ids) else None,
                    'source': source
                })
        
        return formatted


class KnowledgeHandler:
    """Main knowledge handler managing all cyber knowledge operations."""
    
    def __init__(self, subspace_root: Path):
        self.subspace_root = subspace_root
        self.handlers = {}  # cyber_id -> CyberKnowledgeHandler
        self.enabled = CHROMADB_AVAILABLE
        self.embedding_fn = None  # Store embedding function for reuse
        
        if not self.enabled:
            logger.warning("Knowledge system disabled - ChromaDB not available")
            return
        
        # Initialize ChromaDB client
        try:
            # Try to connect to ChromaDB server
            chroma_host = os.getenv('CHROMADB_HOST', 'localhost')
            chroma_port = int(os.getenv('CHROMADB_PORT', 8000))
            
            # First try HTTP client (server mode)
            try:
                self.chroma_client = chromadb.HttpClient(
                    host=chroma_host,
                    port=chroma_port
                )
                # Test connection
                self.chroma_client.heartbeat()
                logger.info(f"Connected to ChromaDB server at {chroma_host}:{chroma_port}")
                self.client_type = 'http'
            except:
                # Fall back to persistent client (embedded mode)
                logger.info("ChromaDB server not available, using embedded mode")
                knowledge_db_path = self.subspace_root / "knowledge_db"
                knowledge_db_path.mkdir(exist_ok=True)
                self.chroma_client = chromadb.PersistentClient(
                    path=str(knowledge_db_path)
                )
                self.client_type = 'embedded'
            
            # Create embedding function using BGE model for better semantic search
            # BGE (BAAI General Embedding) models are excellent for semantic similarity
            try:
                self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="BAAI/bge-large-en-v1.5",
                    device="cpu"  # Use CPU for development
                )
                logger.info("Using BGE-large embedding model for better semantic search")
            except Exception as e:
                logger.warning(f"Failed to load BGE model, using default: {e}")
                self.embedding_fn = None  # Will use ChromaDB default
            
            # Initialize shared collection
            self.shared_collection = self.chroma_client.get_or_create_collection(
                name="mindswarm_shared",
                metadata={"hnsw:space": "cosine"},
                embedding_function=self.embedding_fn
            )
            
            logger.info(f"Knowledge system initialized ({self.client_type} mode)")
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self.enabled = False
    
    def get_cyber_handler(self, cyber_id: str) -> Optional[CyberKnowledgeHandler]:
        """Get or create a handler for a specific cyber."""
        if not self.enabled:
            return None
        
        if cyber_id not in self.handlers:
            try:
                # Create personal collection for this cyber with same embedding function
                personal_collection = self.chroma_client.get_or_create_collection(
                    name=f"cyber_{cyber_id}_personal",
                    metadata={"hnsw:space": "cosine"},
                    embedding_function=self.embedding_fn  # Use same embedding as shared
                )
                
                self.handlers[cyber_id] = CyberKnowledgeHandler(
                    cyber_id, personal_collection, self.shared_collection
                )
                logger.info(f"Created knowledge handler for {cyber_id}")
                
            except Exception as e:
                logger.error(f"Failed to create handler for {cyber_id}: {e}")
                return None
        
        return self.handlers[cyber_id]
    
    async def process_request(self, cyber_id: str, request: Dict) -> Dict:
        """Process a knowledge request from a cyber."""
        if not self.enabled:
            return {
                "request_id": request.get('request_id'),
                "status": "error",
                "error": "Knowledge system not available"
            }
        
        handler = self.get_cyber_handler(cyber_id)
        if not handler:
            return {
                "request_id": request.get('request_id'),
                "status": "error",
                "error": "Failed to initialize knowledge handler"
            }
        
        operation = request.get('operation')
        
        if operation == 'search':
            return await handler.search(request)
        elif operation == 'store':
            return await handler.store(request)
        elif operation == 'get':
            return await handler.get(request)
        elif operation == 'forget':
            return await handler.forget(request)
        elif operation == 'update':
            return await handler.update(request)
        else:
            return {
                "request_id": request.get('request_id'),
                "status": "error",
                "error": f"Unknown operation: {operation}"
            }
    
    # CLI management methods
    async def add_shared_knowledge_with_id(self, knowledge_id: str, content: str, metadata: Dict = None) -> Tuple[bool, str]:
        """Add knowledge to shared collection with specific ID."""
        if not self.enabled:
            return False, "Knowledge system not available"
        
        try:
            # Prepare metadata - convert lists to strings for ChromaDB
            full_metadata = {
                'source': metadata.get('source', 'initial_knowledge'),
                'timestamp': datetime.now().isoformat(),
                'personal': False
            }
            
            if metadata:
                for key, value in metadata.items():
                    if isinstance(value, list):
                        # Convert lists to comma-separated strings
                        full_metadata[key] = ','.join(str(v) for v in value) if value else ''
                    else:
                        full_metadata[key] = value
            
            # Add to shared collection with specified ID
            self.shared_collection.add(
                documents=[content],
                metadatas=[full_metadata],
                ids=[knowledge_id]
            )
            
            return True, knowledge_id
            
        except Exception as e:
            return False, str(e)
    
    async def get_shared_knowledge(self, knowledge_id: str) -> Optional[Dict]:
        """Get knowledge by ID from shared collection.
        
        Args:
            knowledge_id: The ID to look up
            
        Returns:
            Knowledge dict if found, None otherwise
        """
        if not self.enabled:
            return None
        
        try:
            # Try to get by exact ID
            result = self.shared_collection.get(
                ids=[knowledge_id],
                include=['documents', 'metadatas']
            )
            
            if result and result['documents'] and result['documents'][0]:
                return {
                    'id': knowledge_id,
                    'content': result['documents'][0],
                    'metadata': result['metadatas'][0] if result['metadatas'] else {}
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get knowledge by ID {knowledge_id}: {e}")
            return None
    
    async def add_shared_knowledge(self, content: str, metadata: Dict = None) -> Tuple[bool, str]:
        """Add knowledge to shared collection (for CLI use)."""
        if not self.enabled:
            return False, "Knowledge system not available"
        
        try:
            # Generate ID
            content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
            knowledge_id = f"cli_{content_hash}_{int(time.time())}"
            
            # Prepare metadata - convert lists to strings for ChromaDB
            full_metadata = {
                'source': 'cli',
                'timestamp': datetime.now().isoformat(),
                'personal': False
            }
            
            if metadata:
                for key, value in metadata.items():
                    if isinstance(value, list):
                        # Convert lists to comma-separated strings
                        full_metadata[key] = ','.join(str(v) for v in value) if value else ''
                    else:
                        full_metadata[key] = value
            
            # Add to shared collection
            self.shared_collection.add(
                documents=[content],
                metadatas=[full_metadata],
                ids=[knowledge_id]
            )
            
            return True, knowledge_id
            
        except Exception as e:
            return False, str(e)
    
    async def search_shared_knowledge(self, query: str, limit: int = 10) -> List[Dict]:
        """Search shared knowledge (for CLI use)."""
        if not self.enabled:
            return []
        
        try:
            results = self.shared_collection.query(
                query_texts=[query],
                n_results=limit
            )
            
            # Format results
            formatted = []
            if results and results.get('documents'):
                documents = results['documents'][0]
                metadatas = results['metadatas'][0] if results.get('metadatas') else []
                distances = results['distances'][0] if results.get('distances') else []
                ids = results['ids'][0] if results.get('ids') else []
                
                for i, doc in enumerate(documents):
                    if doc:
                        formatted.append({
                            'id': ids[i] if i < len(ids) else None,
                            'content': doc,
                            'score': 1.0 - distances[i] if i < len(distances) else 0.5,
                            'metadata': metadatas[i] if i < len(metadatas) else {}
                        })
            
            return formatted
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    async def remove_shared_knowledge(self, knowledge_id: str) -> Tuple[bool, str]:
        """Remove knowledge from shared collection (for CLI use)."""
        if not self.enabled:
            return False, "Knowledge system not available"
        
        try:
            self.shared_collection.delete(ids=[knowledge_id])
            return True, "Knowledge removed successfully"
        except Exception as e:
            return False, str(e)
    
    async def update_shared_knowledge(self, knowledge_id: str, content: str = None, metadata: Dict = None) -> Tuple[bool, str]:
        """Update knowledge in shared collection (for CLI use)."""
        if not self.enabled:
            return False, "Knowledge system not available"
        
        try:
            # Get existing knowledge
            existing = self.shared_collection.get(ids=[knowledge_id])
            if not existing or not existing.get('documents'):
                return False, "Knowledge not found"
            
            # Prepare updated content and metadata
            new_content = content if content is not None else existing['documents'][0]
            existing_metadata = existing['metadatas'][0] if existing.get('metadatas') else {}
            new_metadata = {
                **existing_metadata,
                **(metadata or {}),
                'updated_at': datetime.now().isoformat()
            }
            
            # Delete and re-add (ChromaDB doesn't have direct update)
            self.shared_collection.delete(ids=[knowledge_id])
            self.shared_collection.add(
                documents=[new_content],
                metadatas=[new_metadata],
                ids=[knowledge_id]
            )
            
            return True, "Knowledge updated successfully"
            
        except Exception as e:
            return False, str(e)
    
    async def export_all_knowledge(self, limit: int = 10000) -> List[Dict]:
        """Export all knowledge with full content (for backup/export).
        
        Args:
            limit: Maximum number of items to return (default 10000)
            
        Returns:
            List of knowledge documents with full content
        """
        if not self.enabled:
            return []
        
        try:
            # Get all documents (up to limit) with full content
            results = self.shared_collection.get(limit=limit)
            
            formatted = []
            if results:
                documents = results.get('documents', [])
                metadatas = results.get('metadatas', [])
                ids = results.get('ids', [])
                
                for i, doc in enumerate(documents):
                    if doc:
                        formatted.append({
                            'id': ids[i] if i < len(ids) else None,
                            'content': doc,  # Full content, no truncation
                            'metadata': metadatas[i] if i < len(metadatas) else {}
                        })
            
            return formatted
            
        except Exception as e:
            logger.error(f"Export error: {e}")
            return []
    
    async def list_shared_knowledge(self, limit: int = 100, truncate: bool = True) -> List[Dict]:
        """List all shared knowledge.
        
        Args:
            limit: Maximum number of items to return
            truncate: Whether to truncate content for display (default True for CLI)
        """
        if not self.enabled:
            return []
        
        try:
            # Get all documents (up to limit)
            results = self.shared_collection.get(limit=limit)
            
            formatted = []
            if results:
                documents = results.get('documents', [])
                metadatas = results.get('metadatas', [])
                ids = results.get('ids', [])
                
                for i, doc in enumerate(documents):
                    if doc:
                        # Only truncate if requested (for CLI display)
                        content = doc[:100] + '...' if (truncate and len(doc) > 100) else doc
                        formatted.append({
                            'id': ids[i] if i < len(ids) else None,
                            'content': content,
                            'metadata': metadatas[i] if i < len(metadatas) else {}
                        })
            
            return formatted
            
        except Exception as e:
            logger.error(f"List error: {e}")
            return []
    
    def get_stats(self) -> Dict:
        """Get knowledge system statistics."""
        if not self.enabled:
            return {"enabled": False}
        
        try:
            shared_count = len(self.shared_collection.get(limit=1)['ids'])
            
            stats = {
                "enabled": True,
                "mode": self.client_type,
                "shared_knowledge_count": shared_count,
                "active_cybers": len(self.handlers),
                "cybers": {}
            }
            
            # Get per-cyber stats
            for cyber_id, handler in self.handlers.items():
                try:
                    personal_count = len(handler.personal_collection.get(limit=1)['ids'])
                    stats["cybers"][cyber_id] = {
                        "personal_knowledge_count": personal_count
                    }
                except:
                    pass
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"enabled": True, "error": str(e)}