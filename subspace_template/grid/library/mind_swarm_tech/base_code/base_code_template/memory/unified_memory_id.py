"""Unified Memory ID system for consistent memory referencing.

This module provides a semantic ID system that:
- Uses consistent format across all memory types
- Enables pattern matching and relationship discovery
- Includes content hashing for deduplication
- Provides semantic understanding from IDs alone
"""

import hashlib
import re
from typing import Optional, Dict, Any
from pathlib import Path
from .memory_types import MemoryType


class UnifiedMemoryID:
    """Manages unified memory IDs with format: type:path[:hash]"""
    
    # Pattern for parsing IDs: type:path[:hash]
    ID_PATTERN = re.compile(r'^([^:]+):([^:]+)(?::([a-f0-9]{6}))?$')
    
    @staticmethod
    def create(
        mem_type: MemoryType,
        path: str,
        content: Optional[str] = None
    ) -> str:
        """Create a new unified memory ID.
        
        Args:
            mem_type: Type of memory (MemoryType enum)
            path: Path to the memory (should include personal/ or grid/ prefix)
            content: Optional content for hash generation
            
        Returns:
            Unified memory ID string
        """
        # Get string value from enum
        type_str = mem_type.value
        
        # Clean up path - remove leading slash if present
        path = path.lstrip('/')
        
        # Generate content hash if content provided
        if content:
            content_hash = hashlib.sha256(content.encode()).hexdigest()[:6]
            return f"{type_str}:{path}:{content_hash}"
        else:
            return f"{type_str}:{path}"
    
    @staticmethod
    def parse(memory_id: str) -> Dict[str, str]:
        """Parse a unified memory ID into components.
        
        Args:
            memory_id: The ID to parse
            
        Returns:
            Dict with keys: type, path, hash (optional), namespace (derived)
        """
        match = UnifiedMemoryID.ID_PATTERN.match(memory_id)
        if not match:
            # Invalid format, return empty result
            return {
                'type': 'unknown',
                'path': memory_id,
                'namespace': 'unknown'
            }
        
        mem_type, path, content_hash = match.groups()
        
        # Derive namespace from path for backwards compatibility
        if path.startswith('personal/'):
            namespace = 'personal'
        elif path.startswith('grid/'):
            namespace = 'grid'
        elif path.startswith('inbox/') or path.startswith('outbox/'):
            namespace = 'personal'
        else:
            # Default to personal if unclear
            namespace = 'personal'
        
        result = {
            'type': mem_type,
            'path': path,
            'namespace': namespace  # Derived for compatibility
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
        - "memory:personal/*" matches any personal file
        - "memory:personal/notes/*" matches any note
        - "message:personal/inbox/**" matches any inbox message
        """
        # Convert pattern to regex
        pattern_parts = pattern.split(':')
        id_parts = memory_id.split(':')
        
        # Must have at least type:path
        if len(pattern_parts) < 2 or len(id_parts) < 2:
            return False
        
        # Check type
        if pattern_parts[0] != '*' and pattern_parts[0] != id_parts[0]:
            return False
        
        # Check path
        pattern_path = pattern_parts[1] if len(pattern_parts) > 1 else ''
        id_path = id_parts[1] if len(id_parts) > 1 else ''
        
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
            'namespace': parts.get('namespace', 'unknown'),
            'path_segments': parts['path'].split('/'),
            'depth': len(parts['path'].split('/')),
            'has_content_hash': 'hash' in parts
        }
        
        # Add type-specific interpretations
        if parts['type'] == 'message':
            segments = info['path_segments']
            # Skip the personal/grid prefix
            if len(segments) > 2:
                info['from_agent'] = segments[-2].replace('from-', '')
                info['subject_hint'] = segments[-1]
        
        elif parts['type'] == 'file':
            if 'personal' in parts['path']:
                info['is_private'] = True
            elif 'grid' in parts['path']:
                info['is_shared'] = True
        
        elif parts['type'] == 'knowledge':
            # Skip personal/grid prefix
            relevant_segments = [s for s in info['path_segments'] if s not in ['personal', 'grid', 'library']]
            if len(relevant_segments) >= 1:
                info['topic'] = relevant_segments[0]
                if len(relevant_segments) >= 2:
                    info['subtopic'] = relevant_segments[1]
        
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
        # Clean up the path
        path_str = str(path)
        
        # Remove leading slash if present
        if path_str.startswith('/'):
            path_str = path_str[1:]
        
        # If path already starts with personal/ or grid/, use as-is
        if path_str.startswith('personal/') or path_str.startswith('grid/'):
            return UnifiedMemoryID.create(mem_type, path_str)
        
        # Otherwise, try to extract the meaningful part
        if '/personal/' in path_str:
            # Extract everything after /personal/
            path_str = 'personal/' + path_str.split('/personal/')[-1]
        elif '/grid/' in path_str:
            # Extract everything after /grid/
            path_str = 'grid/' + path_str.split('/grid/')[-1]
        else:
            # Default to personal if we can't determine
            path_str = 'personal/' + path_str
        
        return UnifiedMemoryID.create(mem_type, path_str)
    
    @staticmethod
    def create_observation_id(obs_type: str, path: str) -> str:
        """Create an observation ID that prevents duplication.
        
        Uses content hash of type+path to ensure unique observations.
        """
        # If path is a memory ID, extract just the path part
        if ':' in path and not '/' in path.split(':')[0]:
            # This looks like a memory ID (type:path format)
            try:
                parts = UnifiedMemoryID.parse(path)
                path = parts['path']
            except:
                # If parsing fails, use as-is
                pass
        
        # Clean up the path
        path_str = str(path)
        if path_str.startswith('/'):
            path_str = path_str[1:]
        
        # Use the actual path for the observation ID - don't inject obs_type into path
        if path_str.startswith('personal/') or path_str.startswith('grid/'):
            # Path already has namespace prefix, use as-is
            obs_path = path_str
        else:
            # Determine from path content
            if '/grid/' in path_str:
                # Extract the grid-relative path
                grid_idx = path_str.find('grid/')
                obs_path = path_str[grid_idx:]
            elif '/personal/' in path_str:
                # Extract the personal-relative path
                personal_idx = path_str.find('personal/')
                obs_path = path_str[personal_idx:]
            else:
                # Default to personal namespace
                obs_path = f"personal/{path_str}"
        
        # Create content hash from identifying information
        content = f"{obs_type}:{path_str}"
        
        return UnifiedMemoryID.create(MemoryType.OBSERVATION, obs_path, content)
    
    @staticmethod
    def to_filesystem_path(memory_id: str, base_path: Optional[Path] = None) -> Path:
        """Convert a memory ID to a filesystem path.
        
        Args:
            memory_id: The memory ID to convert
            base_path: Optional base path to prepend
            
        Returns:
            Filesystem path
        """
        parts = UnifiedMemoryID.parse(memory_id)
        path = parts['path']
        
        if base_path:
            return base_path / path
        else:
            return Path(path)