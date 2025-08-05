"""Unified Memory ID system for consistent memory referencing.

This module provides a semantic ID system that:
- Uses consistent format across all memory types
- Enables pattern matching and relationship discovery
- Includes content hashing for deduplication
- Provides semantic understanding from IDs alone
"""

import hashlib
import re
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from .memory_types import MemoryType


class UnifiedMemoryID:
    """Manages unified memory IDs with format: type:namespace:semantic_path[:hash]"""
    
    # Pattern for parsing IDs
    ID_PATTERN = re.compile(r'^([^:]+):([^:]+):([^:]+)(?::([a-f0-9]{6}))?$')
    
    @staticmethod
    def create(
        mem_type: MemoryType,
        namespace: str,
        semantic_path: str,
        content: Optional[str] = None
    ) -> str:
        """Create a new unified memory ID.
        
        Args:
            mem_type: Type of memory (MemoryType enum)
            namespace: Namespace (personal, shared, inbox, etc.)
            semantic_path: Semantic path describing content
            content: Optional content for hash generation
            
        Returns:
            Unified memory ID string
        """
        # Get string value from enum
        type_str = mem_type.value
        
        # Clean up semantic path
        semantic_path = semantic_path.strip('/')
        
        # Generate content hash if content provided
        if content:
            content_hash = hashlib.sha256(content.encode()).hexdigest()[:6]
            return f"{type_str}:{namespace}:{semantic_path}:{content_hash}"
        else:
            return f"{type_str}:{namespace}:{semantic_path}"
    
    @staticmethod
    def parse(memory_id: str) -> Dict[str, str]:
        """Parse a unified memory ID into components.
        
        Args:
            memory_id: The ID to parse
            
        Returns:
            Dict with keys: type, namespace, semantic_path, hash (optional)
        """
        match = UnifiedMemoryID.ID_PATTERN.match(memory_id)
        if not match:
            raise ValueError(f"Invalid memory ID format: {memory_id}")
        
        mem_type, namespace, semantic_path, content_hash = match.groups()
        
        result = {
            'type': mem_type,
            'namespace': namespace,
            'semantic_path': semantic_path
        }
        
        if content_hash:
            result['hash'] = content_hash
            
        return result
    
    @staticmethod
    def matches_pattern(memory_id: str, pattern: str) -> bool:
        """Check if a memory ID matches a pattern.
        
        Patterns support wildcards:
        - * matches any single segment
        - ** matches any number of segments
        
        Examples:
        - "file:personal:*" matches any personal file
        - "file:personal:notes/*" matches any note
        - "message:inbox:**" matches any inbox message
        """
        # Convert pattern to regex
        pattern_parts = pattern.split(':')
        id_parts = memory_id.split(':')
        
        # Must have same number of main parts (type:namespace:path)
        if len(pattern_parts) < 3 or len(id_parts) < 3:
            return False
        
        # Check type and namespace
        if pattern_parts[0] != '*' and pattern_parts[0] != id_parts[0]:
            return False
        if pattern_parts[1] != '*' and pattern_parts[1] != id_parts[1]:
            return False
        
        # Check semantic path
        pattern_path = pattern_parts[2]
        id_path = id_parts[2]
        
        # Handle ** wildcard
        if '**' in pattern_path:
            prefix = pattern_path.split('**')[0]
            return id_path.startswith(prefix)
        
        # Handle * wildcards
        pattern_segments = pattern_path.split('/')
        id_segments = id_path.split('/')
        
        if len(pattern_segments) != len(id_segments):
            return False
        
        for p_seg, i_seg in zip(pattern_segments, id_segments):
            if p_seg != '*' and p_seg != i_seg:
                return False
        
        return True
    
    @staticmethod
    def extract_semantic_info(memory_id: str) -> Dict[str, Any]:
        """Extract semantic information from an ID.
        
        Returns:
            Dict with semantic interpretations
        """
        parts = UnifiedMemoryID.parse(memory_id)
        info = {
            'type': parts['type'],
            'namespace': parts['namespace'],
            'path_segments': parts['semantic_path'].split('/'),
            'depth': len(parts['semantic_path'].split('/')),
            'has_content_hash': 'hash' in parts
        }
        
        # Add type-specific interpretations
        if parts['type'] == 'message':
            segments = info['path_segments']
            if len(segments) >= 2:
                info['from_agent'] = segments[0].replace('from-', '')
                info['subject_hint'] = segments[1]
        
        elif parts['type'] == 'file':
            if info['namespace'] == 'personal':
                info['is_private'] = True
            elif info['namespace'] == 'shared':
                info['is_shared'] = True
        
        elif parts['type'] == 'knowledge':
            if len(info['path_segments']) >= 1:
                info['topic'] = info['path_segments'][0]
                if len(info['path_segments']) >= 2:
                    info['subtopic'] = info['path_segments'][1]
        
        return info
    
    @staticmethod
    def create_from_path(path: str, mem_type: MemoryType = MemoryType.FILE) -> str:
        """Create a memory ID from a filesystem path.
        
        Args:
            path: Filesystem path
            mem_type: Memory type (default: MemoryType.FILE)
            
        Returns:
            Unified memory ID
        """
        path_obj = Path(path)
        
        # Determine namespace from path
        if '/home/' in str(path):
            if '/memory/' in str(path):
                namespace = 'personal'
                # Extract semantic path from memory directory
                semantic_parts = str(path).split('/memory/')[-1]
            elif '/inbox/' in str(path):
                namespace = 'inbox'
                semantic_parts = path_obj.stem  # Just filename without extension
            elif '/outbox/' in str(path):
                namespace = 'outbox'
                semantic_parts = path_obj.stem
            else:
                namespace = 'personal'
                semantic_parts = path_obj.name
        elif '/grid/' in str(path):
            if '/plaza/' in str(path):
                namespace = 'plaza'
            elif '/library/' in str(path):
                namespace = 'library'
            elif '/workshop/' in str(path):
                namespace = 'workshop'
            elif '/bulletin/' in str(path):
                namespace = 'bulletin'
            else:
                namespace = 'shared'
            
            # Extract path after grid area
            for area in ['plaza', 'library', 'workshop', 'bulletin']:
                if f'/{area}/' in str(path):
                    semantic_parts = str(path).split(f'/{area}/')[-1]
                    break
            else:
                semantic_parts = path_obj.name
        else:
            namespace = 'unknown'
            semantic_parts = path_obj.name
        
        # Keep the full filename including extension
        semantic_path = semantic_parts
        
        return UnifiedMemoryID.create(mem_type, namespace, semantic_path)
    
    @staticmethod
    def create_observation_id(obs_type: str, path: str) -> str:
        """Create an observation ID that prevents duplication.
        
        Uses content hash of type+path to ensure unique observations.
        """
        # Create semantic path from observation type and path
        path_obj = Path(path)
        semantic_path = f"{obs_type}/{path_obj.name}"
        
        # Determine namespace
        if '/grid/' in path:
            namespace = 'shared'
        else:
            namespace = 'personal'
        
        # Create content hash from identifying information
        content = f"{obs_type}:{path}"
        
        return UnifiedMemoryID.create(MemoryType.OBSERVATION, namespace, semantic_path, content)