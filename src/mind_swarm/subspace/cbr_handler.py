"""
Case-Based Reasoning handler for Mind-Swarm cybers using ChromaDB for storage.
Provides storage, retrieval and scoring of problem-solution cases.
"""

import os
import json
import time
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import asyncio
import math

try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logging.warning("ChromaDB not installed. CBR system will be disabled.")

logger = logging.getLogger(__name__)


class CyberCBRHandler:
    """Handles CBR operations for a specific cyber."""
    
    def __init__(self, cyber_id: str, personal_cbr_collection, shared_cbr_collection):
        self.cyber_id = cyber_id
        self.personal_cbr = personal_cbr_collection
        self.shared_cbr = shared_cbr_collection
        self.request_cache = {}  # Cache recent requests
        
    async def retrieve(self, request: Dict) -> Dict:
        """Retrieve similar cases based on context."""
        try:
            context = request.get('context', '')
            options = request.get('options', {})
            limit = min(options.get('limit', 3), 5)  # Cap at 5
            min_score = options.get('min_score', 0.5)
            
            cases = []
            
            # Search personal CBR cases
            if self.personal_cbr:
                try:
                    personal_results = self.personal_cbr.query(
                        query_texts=[context],
                        n_results=limit * 2  # Get more to filter by score
                    )
                    cases.extend(self._format_cases(personal_results, 'personal'))
                except Exception as e:
                    logger.error(f"Error searching personal CBR: {e}")
            
            # Search shared CBR cases
            if self.shared_cbr:
                try:
                    shared_results = self.shared_cbr.query(
                        query_texts=[context],
                        n_results=limit * 2
                    )
                    cases.extend(self._format_cases(shared_results, 'shared'))
                except Exception as e:
                    logger.error(f"Error searching shared CBR: {e}")
            
            # Apply temporal decay to success scores
            current_time = datetime.now()
            for case in cases:
                if 'metadata' in case and 'timestamp' in case['metadata']:
                    try:
                        case_time = datetime.fromisoformat(case['metadata']['timestamp'])
                        days_old = (current_time - case_time).days
                        decay_factor = 0.95 ** (days_old / 7)  # Weekly decay
                        original_score = case['metadata'].get('success_score', 0.7)
                        case['metadata']['success_score'] = original_score * decay_factor
                    except:
                        pass
            
            # Calculate weighted scores (similarity * success_score)
            for case in cases:
                similarity = case.get('similarity', 0)
                success = case['metadata'].get('success_score', 0.7)
                source_weight = 1.2 if case.get('source') == 'personal' else 1.0
                case['weighted_score'] = similarity * success * source_weight
            
            # Filter by minimum score and sort by weighted score
            cases = [c for c in cases if c['weighted_score'] >= min_score]
            cases.sort(key=lambda x: x['weighted_score'], reverse=True)
            cases = cases[:limit]
            
            return {
                "request_id": request.get('request_id'),
                "status": "success",
                "cases": cases
            }
            
        except Exception as e:
            logger.error(f"CBR retrieve error for {self.cyber_id}: {e}")
            return {
                "request_id": request.get('request_id'),
                "status": "error",
                "error": str(e),
                "cases": []
            }
    
    async def store(self, request: Dict) -> Dict:
        """Store a new CBR case."""
        try:
            case = request.get('case', {})
            
            # Generate unique case ID
            content_str = f"{case.get('problem_context', '')}_{case.get('solution', '')}"
            content_hash = hashlib.md5(content_str.encode()).hexdigest()[:8]
            case_id = f"cbr_{self.cyber_id}_{content_hash}_{int(time.time())}"
            
            # Prepare case document
            case_doc = json.dumps({
                "problem_context": case.get('problem_context', ''),
                "solution": case.get('solution', ''),
                "outcome": case.get('outcome', '')
            })
            
            # Prepare metadata
            metadata = case.get('metadata', {})
            metadata['cyber_id'] = self.cyber_id
            metadata['case_id'] = case_id
            metadata['case_type'] = 'cbr_case'
            
            # Convert lists to strings for ChromaDB (it doesn't accept lists in metadata)
            if 'tags' in metadata and isinstance(metadata['tags'], list):
                metadata['tags'] = ','.join(metadata['tags']) if metadata['tags'] else ''
            
            # Convert cbr_cases_used list to string
            if 'cbr_cases_used' in metadata and isinstance(metadata['cbr_cases_used'], list):
                metadata['cbr_cases_used'] = ','.join(metadata['cbr_cases_used']) if metadata['cbr_cases_used'] else ''
            
            # Ensure timestamp
            if 'timestamp' not in metadata:
                metadata['timestamp'] = datetime.now().isoformat()
            
            # Determine collection (personal by default)
            collection = self.personal_cbr if not metadata.get('shared', False) else self.shared_cbr
            
            # Store in ChromaDB
            collection.add(
                documents=[case_doc],
                metadatas=[metadata],
                ids=[case_id]
            )
            
            logger.info(f"Stored CBR case {case_id} for {self.cyber_id}")
            
            return {
                "request_id": request.get('request_id'),
                "status": "success",
                "case_id": case_id
            }
            
        except Exception as e:
            logger.error(f"CBR store error for {self.cyber_id}: {e}")
            return {
                "request_id": request.get('request_id'),
                "status": "error",
                "error": str(e)
            }
    
    async def update_score(self, request: Dict) -> Dict:
        """Update the score of an existing case."""
        try:
            case_id = request.get('case_id')
            updates = request.get('updates', {})
            
            # Try to find the case in both collections
            case_data = None
            collection = None
            
            # Check personal collection
            try:
                result = self.personal_cbr.get(ids=[case_id])
                if result and result.get('documents'):
                    case_data = result
                    collection = self.personal_cbr
            except:
                pass
            
            # Check shared collection if not found
            if not case_data:
                try:
                    result = self.shared_cbr.get(ids=[case_id])
                    if result and result.get('documents'):
                        case_data = result
                        collection = self.shared_cbr
                except:
                    pass
            
            if not case_data or not collection:
                return {
                    "request_id": request.get('request_id'),
                    "status": "error",
                    "error": "Case not found"
                }
            
            # Update metadata
            metadata = case_data['metadatas'][0] if case_data.get('metadatas') else {}
            
            # Update success score if provided
            if 'success_score' in updates:
                metadata['success_score'] = updates['success_score']
            
            # Increment usage count if requested
            if updates.get('increment_usage'):
                metadata['usage_count'] = metadata.get('usage_count', 0) + 1
                metadata['last_used'] = datetime.now().isoformat()
                # Boost score slightly for successful reuse
                current_score = metadata.get('success_score', 0.7)
                metadata['success_score'] = min(0.95, current_score + 0.05)
            
            # Update in ChromaDB
            collection.update(
                ids=[case_id],
                metadatas=[metadata]
            )
            
            logger.info(f"Updated CBR case {case_id}")
            
            return {
                "request_id": request.get('request_id'),
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"CBR update error for {self.cyber_id}: {e}")
            return {
                "request_id": request.get('request_id'),
                "status": "error",
                "error": str(e)
            }
    
    async def get(self, request: Dict) -> Dict:
        """Get a specific case by ID."""
        try:
            case_id = request.get('case_id')
            
            # Try both collections
            for collection in [self.personal_cbr, self.shared_cbr]:
                if not collection:
                    continue
                try:
                    result = collection.get(ids=[case_id])
                    if result and result.get('documents'):
                        case_data = json.loads(result['documents'][0])
                        case_data['metadata'] = result['metadatas'][0] if result.get('metadatas') else {}
                        case_data['case_id'] = case_id
                        
                        return {
                            "request_id": request.get('request_id'),
                            "status": "success",
                            "case": case_data
                        }
                except:
                    continue
            
            return {
                "request_id": request.get('request_id'),
                "status": "error",
                "error": "Case not found"
            }
            
        except Exception as e:
            logger.error(f"CBR get error for {self.cyber_id}: {e}")
            return {
                "request_id": request.get('request_id'),
                "status": "error",
                "error": str(e)
            }
    
    async def share(self, request: Dict) -> Dict:
        """Share a personal case with the hive mind."""
        try:
            case_id = request.get('case_id')
            
            # Get case from personal collection
            result = self.personal_cbr.get(ids=[case_id])
            if not result or not result.get('documents'):
                return {
                    "request_id": request.get('request_id'),
                    "status": "error",
                    "error": "Case not found in personal collection"
                }
            
            # Copy to shared collection
            document = result['documents'][0]
            metadata = result['metadatas'][0] if result.get('metadatas') else {}
            metadata['shared'] = True
            metadata['shared_by'] = self.cyber_id
            metadata['shared_at'] = datetime.now().isoformat()
            
            self.shared_cbr.add(
                documents=[document],
                metadatas=[metadata],
                ids=[case_id]
            )
            
            logger.info(f"Shared CBR case {case_id}")
            
            return {
                "request_id": request.get('request_id'),
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"CBR share error for {self.cyber_id}: {e}")
            return {
                "request_id": request.get('request_id'),
                "status": "error",
                "error": str(e)
            }
    
    async def forget(self, request: Dict) -> Dict:
        """Remove a case from storage."""
        try:
            case_id = request.get('case_id')
            
            deleted = False
            # Try to delete from both collections
            for collection in [self.personal_cbr, self.shared_cbr]:
                if not collection:
                    continue
                try:
                    collection.delete(ids=[case_id])
                    deleted = True
                except:
                    pass
            
            if deleted:
                logger.info(f"Deleted CBR case {case_id}")
                return {
                    "request_id": request.get('request_id'),
                    "status": "success"
                }
            else:
                return {
                    "request_id": request.get('request_id'),
                    "status": "error",
                    "error": "Case not found"
                }
                
        except Exception as e:
            logger.error(f"CBR forget error for {self.cyber_id}: {e}")
            return {
                "request_id": request.get('request_id'),
                "status": "error",
                "error": str(e)
            }
    
    async def statistics(self, request: Dict) -> Dict:
        """Get CBR usage statistics."""
        try:
            stats = {
                'total_cases': 0,
                'personal_cases': 0,
                'shared_cases': 0,
                'avg_success_score': 0.0,
                'reuse_count': 0,
                'top_tags': [],
                'oldest_case': None,
                'newest_case': None
            }
            
            all_scores = []
            all_tags = {}
            oldest = None
            newest = None
            
            # Gather stats from personal collection
            if self.personal_cbr:
                try:
                    result = self.personal_cbr.get()
                    if result and result.get('metadatas'):
                        stats['personal_cases'] = len(result['metadatas'])
                        for meta in result['metadatas']:
                            if meta.get('success_score'):
                                all_scores.append(meta['success_score'])
                            stats['reuse_count'] += meta.get('usage_count', 0)
                            
                            # Track tags
                            for tag in meta.get('tags', []):
                                all_tags[tag] = all_tags.get(tag, 0) + 1
                            
                            # Track timestamps
                            if meta.get('timestamp'):
                                ts = meta['timestamp']
                                if not oldest or ts < oldest:
                                    oldest = ts
                                if not newest or ts > newest:
                                    newest = ts
                except Exception as e:
                    logger.error(f"Error getting personal CBR stats: {e}")
            
            # Gather stats from shared collection
            if self.shared_cbr:
                try:
                    result = self.shared_cbr.get(
                        where={"cyber_id": self.cyber_id}
                    )
                    if result and result.get('metadatas'):
                        stats['shared_cases'] = len(result['metadatas'])
                        for meta in result['metadatas']:
                            if meta.get('success_score'):
                                all_scores.append(meta['success_score'])
                except Exception as e:
                    logger.error(f"Error getting shared CBR stats: {e}")
            
            # Calculate aggregates
            stats['total_cases'] = stats['personal_cases'] + stats['shared_cases']
            if all_scores:
                stats['avg_success_score'] = sum(all_scores) / len(all_scores)
            
            # Top tags
            if all_tags:
                sorted_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)
                stats['top_tags'] = [tag for tag, _ in sorted_tags[:5]]
            
            stats['oldest_case'] = oldest
            stats['newest_case'] = newest
            
            return {
                "request_id": request.get('request_id'),
                "status": "success",
                "statistics": stats
            }
            
        except Exception as e:
            logger.error(f"CBR statistics error for {self.cyber_id}: {e}")
            return {
                "request_id": request.get('request_id'),
                "status": "error",
                "error": str(e),
                "statistics": {}
            }
    
    async def recent(self, request: Dict) -> Dict:
        """Get recently stored cases."""
        try:
            options = request.get('options', {})
            days = options.get('days', 7)
            limit = min(options.get('limit', 10), 20)
            
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            cases = []
            
            # Get from personal collection
            if self.personal_cbr:
                try:
                    result = self.personal_cbr.get(
                        where={"$and": [
                            {"cyber_id": self.cyber_id},
                            {"timestamp": {"$gte": cutoff_date}}
                        ]}
                    )
                    if result and result.get('documents'):
                        for i, doc in enumerate(result['documents']):
                            case = json.loads(doc)
                            case['metadata'] = result['metadatas'][i]
                            case['case_id'] = result['ids'][i]
                            cases.append(case)
                except Exception as e:
                    logger.error(f"Error getting recent personal cases: {e}")
            
            # Sort by timestamp
            cases.sort(key=lambda x: x['metadata'].get('timestamp', ''), reverse=True)
            cases = cases[:limit]
            
            return {
                "request_id": request.get('request_id'),
                "status": "success",
                "cases": cases
            }
            
        except Exception as e:
            logger.error(f"CBR recent error for {self.cyber_id}: {e}")
            return {
                "request_id": request.get('request_id'),
                "status": "error",
                "error": str(e),
                "cases": []
            }
    
    def _format_cases(self, results: Dict, source: str) -> List[Dict]:
        """Format ChromaDB results into CBR cases."""
        cases = []
        
        if not results or not results.get('documents'):
            return cases
        
        documents = results['documents'][0] if results.get('documents') else []
        metadatas = results['metadatas'][0] if results.get('metadatas') else []
        distances = results['distances'][0] if results.get('distances') else []
        ids = results['ids'][0] if results.get('ids') else []
        
        for i in range(len(documents)):
            try:
                case_data = json.loads(documents[i])
                
                # Calculate similarity score from distance (ChromaDB uses L2 distance)
                # Convert to similarity score (0-1, where 1 is identical)
                distance = distances[i] if i < len(distances) else 1.0
                similarity = 1.0 / (1.0 + distance)  # Convert distance to similarity
                
                case = {
                    'case_id': ids[i] if i < len(ids) else f"unknown_{i}",
                    'problem_context': case_data.get('problem_context', ''),
                    'solution': case_data.get('solution', ''),
                    'outcome': case_data.get('outcome', ''),
                    'metadata': metadatas[i] if i < len(metadatas) else {},
                    'similarity': similarity,
                    'source': source
                }
                
                cases.append(case)
                
            except Exception as e:
                logger.error(f"Error formatting case: {e}")
                continue
        
        return cases


class CBRHandler:
    """Main CBR handler managing all cyber CBR operations."""
    
    def __init__(self, subspace_root: Path, chroma_client=None, embedding_fn=None):
        """Initialize CBR handler.
        
        Args:
            subspace_root: Root directory for subspace
            chroma_client: Existing ChromaDB client (optional)
            embedding_fn: Existing embedding function (optional)
        """
        self.subspace_root = subspace_root
        self.handlers = {}  # cyber_id -> CyberCBRHandler
        self.enabled = CHROMADB_AVAILABLE
        
        if not self.enabled:
            logger.warning("CBR system disabled - ChromaDB not available")
            return
        
        # Use provided client or create new one
        if chroma_client:
            self.chroma_client = chroma_client
            logger.info("Using existing ChromaDB client for CBR")
        else:
            # Initialize ChromaDB client
            try:
                chroma_host = os.getenv('CHROMADB_HOST', 'localhost')
                chroma_port = int(os.getenv('CHROMADB_PORT', 8000))
                
                try:
                    self.chroma_client = chromadb.HttpClient(
                        host=chroma_host,
                        port=chroma_port
                    )
                    self.chroma_client.heartbeat()
                    logger.info(f"CBR connected to ChromaDB at {chroma_host}:{chroma_port}")
                except:
                    logger.info("CBR using embedded ChromaDB")
                    cbr_db_path = self.subspace_root / "cbr_db"
                    cbr_db_path.mkdir(exist_ok=True)
                    self.chroma_client = chromadb.PersistentClient(
                        path=str(cbr_db_path)
                    )
            except Exception as e:
                logger.error(f"Failed to initialize ChromaDB for CBR: {e}")
                self.enabled = False
                return
        
        # Use provided or create embedding function
        self.embedding_fn = embedding_fn
        if not self.embedding_fn:
            try:
                self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="BAAI/bge-large-en-v1.5",
                    device="cpu"
                )
                logger.info("CBR using BGE embedding model")
            except:
                logger.info("CBR using default embeddings")
                self.embedding_fn = None
    
    def get_handler(self, cyber_id: str) -> Optional[CyberCBRHandler]:
        """Get or create a CBR handler for a specific cyber."""
        if not self.enabled:
            return None
        
        if cyber_id not in self.handlers:
            # Create collections for this cyber
            personal_collection = self._get_or_create_collection(f"cbr_personal_{cyber_id}")
            shared_collection = self._get_or_create_collection("cbr_shared")
            
            self.handlers[cyber_id] = CyberCBRHandler(
                cyber_id=cyber_id,
                personal_cbr_collection=personal_collection,
                shared_cbr_collection=shared_collection
            )
            logger.info(f"Created CBR handler for {cyber_id}")
        
        return self.handlers[cyber_id]
    
    def _get_or_create_collection(self, name: str):
        """Get or create a ChromaDB collection."""
        try:
            return self.chroma_client.get_collection(
                name=name,
                embedding_function=self.embedding_fn
            )
        except:
            return self.chroma_client.create_collection(
                name=name,
                embedding_function=self.embedding_fn,
                metadata={"hnsw:space": "cosine"}
            )
    
    async def handle_request(self, cyber_id: str, request: Dict) -> Optional[Dict]:
        """Handle a CBR request from a cyber."""
        if not self.enabled:
            return None
        
        handler = self.get_handler(cyber_id)
        if not handler:
            return None
        
        operation = request.get('operation')
        
        if operation == 'retrieve':
            return await handler.retrieve(request)
        elif operation == 'store':
            return await handler.store(request)
        elif operation == 'update_score':
            return await handler.update_score(request)
        elif operation == 'get':
            return await handler.get(request)
        elif operation == 'share':
            return await handler.share(request)
        elif operation == 'forget':
            return await handler.forget(request)
        elif operation == 'statistics':
            return await handler.statistics(request)
        elif operation == 'recent':
            return await handler.recent(request)
        else:
            return {
                "request_id": request.get('request_id'),
                "status": "error",
                "error": f"Unknown operation: {operation}"
            }
    
    async def export_all_cases(self, include_shared: bool = True) -> List[Dict]:
        """Export all CBR cases for backup/preservation.
        
        Args:
            include_shared: Whether to include shared collection cases
            
        Returns:
            List of all CBR cases with full metadata
        """
        if not self.enabled:
            return []
        
        all_cases = []
        
        try:
            # Export from personal collections
            for cyber_id, handler in self.handlers.items():
                if handler.personal_cbr:
                    try:
                        results = handler.personal_cbr.get(limit=10000)
                        if results and results.get('documents'):
                            for i, doc in enumerate(results['documents']):
                                if doc:
                                    case = {
                                        'id': results['ids'][i] if i < len(results['ids']) else None,
                                        'problem': doc,  # The problem context
                                        'metadata': results['metadatas'][i] if i < len(results['metadatas']) else {},
                                        'cyber_id': cyber_id,
                                        'collection': 'personal'
                                    }
                                    all_cases.append(case)
                    except Exception as e:
                        logger.error(f"Error exporting personal CBR for {cyber_id}: {e}")
            
            # Export from shared collection
            if include_shared and self.shared_cbr:
                try:
                    results = self.shared_cbr.get(limit=10000)
                    if results and results.get('documents'):
                        for i, doc in enumerate(results['documents']):
                            if doc:
                                metadata = results['metadatas'][i] if i < len(results['metadatas']) else {}
                                case = {
                                    'id': results['ids'][i] if i < len(results['ids']) else None,
                                    'problem': doc,
                                    'metadata': metadata,
                                    'cyber_id': metadata.get('cyber_id', 'unknown'),
                                    'collection': 'shared'
                                }
                                all_cases.append(case)
                except Exception as e:
                    logger.error(f"Error exporting shared CBR: {e}")
            
            logger.info(f"Exported {len(all_cases)} CBR cases")
            return all_cases
            
        except Exception as e:
            logger.error(f"Error during CBR export: {e}")
            return []
    
    async def import_cases(self, cases: List[Dict]) -> Tuple[int, int]:
        """Import CBR cases from backup.
        
        Args:
            cases: List of case dictionaries to import
            
        Returns:
            Tuple of (successful_imports, failed_imports)
        """
        if not self.enabled:
            return 0, 0
        
        success = 0
        failed = 0
        
        for case in cases:
            try:
                cyber_id = case.get('cyber_id', 'unknown')
                collection_type = case.get('collection', 'personal')
                
                # Get or create handler for cyber
                handler = self.get_handler(cyber_id)
                if not handler:
                    # Create handler if needed
                    handler = CyberCBRHandler(
                        cyber_id,
                        self._get_or_create_collection(f"cbr_personal_{cyber_id}"),
                        self.shared_cbr
                    )
                    self.handlers[cyber_id] = handler
                
                # Determine target collection
                if collection_type == 'shared':
                    collection = self.shared_cbr
                else:
                    collection = handler.personal_cbr
                
                if collection:
                    # Prepare data for import
                    case_id = case.get('id', f"imported_{cyber_id}_{int(time.time()*1000)}")
                    problem = case.get('problem', '')
                    metadata = case.get('metadata', {})
                    
                    # Ensure cyber_id is in metadata
                    metadata['cyber_id'] = cyber_id
                    
                    # Add to collection
                    collection.add(
                        documents=[problem],
                        metadatas=[metadata],
                        ids=[case_id]
                    )
                    success += 1
                else:
                    failed += 1
                    
            except Exception as e:
                logger.error(f"Error importing case: {e}")
                failed += 1
        
        logger.info(f"Imported {success} cases successfully, {failed} failed")
        return success, failed