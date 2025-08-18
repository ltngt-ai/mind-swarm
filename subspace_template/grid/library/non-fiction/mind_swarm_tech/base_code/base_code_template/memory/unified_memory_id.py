"""Unified Memory ID system for consistent memory referencing.

This module provides helper functions for the new simplified memory ID system where:
- Memory IDs are just paths (no type prefix)
- Content type is a separate property on memory blocks
- Paths use consistent namespace prefixes (personal/ or grid/)
- Optional hash suffixes for uniqueness (#hash)

NOTE: Most functions in this module are now deprecated or simplified.
The primary purpose is to help with path normalization.
"""

import hashlib
import re
from typing import Optional, Dict, Any
from pathlib import Path
# MemoryType is no longer used - we use ContentType now


class UnifiedMemoryID:
    """Helper class for memory ID operations (mostly deprecated).
    
    In the new system, memory IDs are just paths with optional hash suffixes.
    Format: path[#hash]
    Examples:
        personal/notes/todo.txt
        grid/shared/data.json
        personal/memory/cache#a3f2b1c8
    """
    
    # Pattern for parsing new simplified IDs: path[#hash]
    ID_PATTERN = re.compile(r'^([^#]+)(?:#([a-f0-9]+))?$')
    
    @staticmethod
    def normalize_path(path: str) -> str:
        """Normalize a path to ensure consistent format.
        
        Args:
            path: Path to normalize
            
        Returns:
            Normalized path with proper namespace prefix
        """
        # Remove leading slash if present
        path = path.lstrip('/')
        
        # Ensure proper namespace prefix
        if not (path.startswith('personal/') or path.startswith('grid/')):
            # Try to extract the meaningful part
            if '/personal/' in path:
                # Extract everything after /personal/
                path = 'personal/' + path.split('/personal/')[-1]
            elif '/grid/' in path:
                # Extract everything after /grid/
                path = 'grid/' + path.split('/grid/')[-1]
            else:
                # Check for special virtual paths
                virtual_prefixes = ['boot_rom/', 'virtual/', 'restored']
                if not any(path.startswith(prefix) for prefix in virtual_prefixes):
                    # Default to personal if we can't determine
                    path = 'personal/' + path
        
        return path
    
    @staticmethod
    def create(
        mem_type: Any,  # Kept for compatibility but ignored
        path: str,
        content: Optional[str] = None
    ) -> str:
        """DEPRECATED: Create a memory ID (now just returns normalized path).
        
        This method is kept for backward compatibility but now simply
        returns the normalized path, optionally with a hash suffix.
        
        Args:
            mem_type: Type of memory (ignored in new system)
            path: Path to the memory
            content: Optional content for hash generation
            
        Returns:
            Normalized path with optional hash suffix
        """
        # Normalize the path
        path = UnifiedMemoryID.normalize_path(path)
        
        # Add hash suffix if content provided
        if content:
            content_hash = hashlib.sha256(content.encode()).hexdigest()[:8]
            return f"{path}#{content_hash}"
        else:
            return path
    
    @staticmethod
    def parse(memory_id: str) -> Dict[str, str]:
        """Parse a memory ID into components.
        
        In the new system, this just extracts the path and optional hash.
        For backward compatibility with old IDs (type:path format),
        it attempts to handle those as well.
        
        Args:
            memory_id: The ID to parse
            
        Returns:
            Dict with keys: path, hash (optional), namespace (derived)
        """
        # Check for old format (type:path[:hash])
        if ':' in memory_id and not '/' in memory_id.split(':')[0]:
            # This looks like an old format ID
            old_pattern = re.compile(r'^([^:]+):([^:#]+)(?:[:#]([a-f0-9]+))?$')
            match = old_pattern.match(memory_id)
            if match:
                mem_type, path, content_hash = match.groups()
                result = {
                    'type': mem_type,  # Keep for backward compat
                    'path': path,
                    'namespace': 'personal' if path.startswith('personal/') else 'grid'
                }
                if content_hash:
                    result['hash'] = content_hash
                return result
        
        # Parse new format (path[#hash])
        match = UnifiedMemoryID.ID_PATTERN.match(memory_id)
        if not match:
            # Just return as-is
            return {
                'path': memory_id,
                'namespace': 'personal' if 'personal' in memory_id else 'grid'
            }
        
        path, content_hash = match.groups()
        
        # Derive namespace from path
        if path.startswith('personal/'):
            namespace = 'personal'
        elif path.startswith('grid/'):
            namespace = 'grid'
        else:
            namespace = 'personal'  # Default
        
        result = {
            'path': path,
            'namespace': namespace
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
    def create_from_path(path: str, mem_type: Any = None) -> str:
        """DEPRECATED: Create a memory ID from a filesystem path.
        
        Now just normalizes the path (type is ignored).
        
        Args:
            path: Filesystem path
            mem_type: Memory type (ignored in new system)
            
        Returns:
            Normalized path
        """
        return UnifiedMemoryID.normalize_path(str(path))
    
    @staticmethod
    def create_observation_id(obs_type: str, path: str) -> str:
        """DEPRECATED: Create an observation ID with uniqueness.
        
        Now just creates a path with a hash suffix for uniqueness.
        
        Args:
            obs_type: Type of observation
            path: Path for the observation
            
        Returns:
            Path with hash suffix for uniqueness
        """
        # Normalize the path
        path_str = UnifiedMemoryID.normalize_path(str(path))
        
        # Default observations to personal/observations if not namespaced
        if not path_str.startswith('personal/observations/') and not path_str.startswith('grid/'):
            if path_str.startswith('personal/'):
                # Insert observations directory
                path_str = path_str.replace('personal/', 'personal/observations/', 1)
            else:
                path_str = f"personal/observations/{path_str}"
        
        # Create hash from obs_type and path for uniqueness
        content = f"{obs_type}:{path}"
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:8]
        
        return f"{path_str}#{content_hash}"
    
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