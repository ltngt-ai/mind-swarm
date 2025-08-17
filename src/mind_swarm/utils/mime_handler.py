"""
MIME type handler for Mind-Swarm files.
Combines python-magic, standard mimetypes, and custom Mind-Swarm types.
"""

import json
import mimetypes
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

# Try to import python-magic, fall back to mimetypes if not available
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    print("python-magic not available, falling back to mimetypes module")


# Register custom Mind-Swarm MIME types
CUSTOM_MIME_TYPES = {
    # Mind-Swarm specific types
    'application/x-mindswarm-knowledge': ['.knowledge.yaml', '.knowledge.yml'],
    'application/x-mindswarm-message': ['.msg.json', '.msg.yaml'],
    'application/x-mindswarm-memory': ['.memory.json'],
    'application/x-mindswarm-action': ['.action.yaml'],
    'application/x-mindswarm-config': ['.config.yaml', '.config.json'],
    
    # Override some standard types for special handling
    'text/x-yaml': ['.yaml', '.yml'],  # Generic YAML
    'text/markdown': ['.md'],
}

# Extended attributes file for storing MIME types and metadata
EXTENDED_ATTRS_FILE = '.fileinfo.json'


class MimeHandler:
    """Handles MIME type detection and storage for Mind-Swarm files."""
    
    def __init__(self):
        # Initialize standard mimetypes
        mimetypes.init()
        
        # Register custom types
        for mime_type, extensions in CUSTOM_MIME_TYPES.items():
            for ext in extensions:
                mimetypes.add_type(mime_type, ext)
        
        # Initialize python-magic if available
        self.magic_mime = None
        if MAGIC_AVAILABLE:
            try:
                # Create magic instance for MIME type detection
                self.magic_mime = magic.Magic(mime=True)
            except Exception as e:
                print(f"Failed to initialize python-magic: {e}")
                self.magic_mime = None
    
    def write_file_with_type(
        self, 
        file_path: Path, 
        content: str, 
        mime_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Write a file and store its MIME type and metadata.
        
        Args:
            file_path: Path to write to
            content: File content
            mime_type: Explicit MIME type (if None, will auto-detect)
            metadata: Additional metadata to store
        
        Returns:
            Success status
        """
        try:
            # Write the actual file
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Determine MIME type
            if mime_type is None:
                mime_type = self.detect_mime_type(file_path, content)
            
            # Store metadata
            self._store_file_metadata(file_path, mime_type, metadata)
            
            return True
            
        except Exception as e:
            print(f"Error writing file with type: {e}")
            return False
    
    def detect_mime_type(self, file_path: Path, content: Optional[str] = None) -> str:
        """
        Detect MIME type using hybrid approach.
        
        Priority:
        1. Check stored metadata
        2. Use python-magic for content-based detection (if available)
        3. Check custom extensions (e.g., .knowledge.yaml)
        4. Directory-based hints
        5. Content sniffing for YAML/JSON
        6. Standard mimetypes module
        7. Default to text/plain
        """
        # 1. Check stored metadata
        stored_type = self._get_stored_mime_type(file_path)
        if stored_type:
            return stored_type
        
        # 2. Use python-magic if available and file exists
        if self.magic_mime and file_path.exists():
            try:
                magic_type = self.magic_mime.from_file(str(file_path))
                # Check if it's a type we want to override
                if magic_type not in ['text/plain', 'application/octet-stream']:
                    # For YAML/JSON files, continue to our custom detection
                    if not (magic_type in ['text/x-yaml', 'application/json'] and 
                            file_path.suffix in ['.yaml', '.yml', '.json']):
                        return magic_type
            except Exception:
                pass  # Fall through to other methods
        
        # 2. Check custom double extensions
        for mime_type, extensions in CUSTOM_MIME_TYPES.items():
            for ext in extensions:
                if str(file_path).endswith(ext):
                    return mime_type
        
        # 3. Directory-based hints
        path_str = str(file_path)
        if '/knowledge/' in path_str or '/initial_knowledge/' in path_str:
            if file_path.suffix in ['.yaml', '.yml']:
                return 'application/x-mindswarm-knowledge'
        elif '/inbox/' in path_str or '/outbox/' in path_str:
            if file_path.suffix in ['.json', '.yaml', '.yml']:
                return 'application/x-mindswarm-message'
        elif '/memory/' in path_str:
            if file_path.suffix == '.json':
                return 'application/x-mindswarm-memory'
        
        # 4. Content sniffing for structured files
        if file_path.suffix in ['.yaml', '.yml', '.json']:
            if content is None and file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read(1024)  # Read first 1KB for sniffing
                except:
                    pass
            
            if content:
                mime_type = self._sniff_content_type(file_path.suffix, content)
                if mime_type:
                    return mime_type
        
        # 5. Standard mimetypes
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type:
            return mime_type
        
        # 6. Default
        return 'text/plain'
    
    def _sniff_content_type(self, extension: str, content: str) -> Optional[str]:
        """
        Sniff content to determine Mind-Swarm specific type.
        """
        if extension in ['.yaml', '.yml']:
            try:
                # Try to parse YAML
                if content.startswith('---'):
                    # Front matter style - likely knowledge
                    return 'application/x-mindswarm-knowledge'
                
                data = yaml.safe_load(content)
                if isinstance(data, dict):
                    # Check for knowledge markers
                    if any(key in data for key in ['title', 'tags', 'category', 'content', 'description']):
                        return 'application/x-mindswarm-knowledge'
                    # Check for message markers
                    elif any(key in data for key in ['to', 'from', 'subject', 'body']):
                        return 'application/x-mindswarm-message'
                    # Check for action markers
                    elif any(key in data for key in ['action', 'execute', 'command']):
                        return 'application/x-mindswarm-action'
                    # Check for config markers
                    elif any(key in data for key in ['version', 'settings', 'config']):
                        return 'application/x-mindswarm-config'
            except:
                pass
            
            return 'text/x-yaml'  # Generic YAML
        
        elif extension == '.json':
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    # Check for message markers
                    if any(key in data for key in ['to', 'from', 'subject']):
                        return 'application/x-mindswarm-message'
                    # Check for memory markers
                    elif any(key in data for key in ['memories', 'observations', 'memory_type']):
                        return 'application/x-mindswarm-memory'
            except:
                pass
            
            return 'application/json'
        
        return None
    
    def _store_file_metadata(
        self, 
        file_path: Path, 
        mime_type: str, 
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Store file metadata in a hidden .fileinfo.json file in the same directory."""
        info_file = file_path.parent / EXTENDED_ATTRS_FILE
        
        # Load existing info
        file_info = {}
        if info_file.exists():
            try:
                with open(info_file, 'r') as f:
                    file_info = json.load(f)
            except:
                file_info = {}
        
        # Update with new info
        file_key = file_path.name
        file_info[file_key] = {
            'mime_type': mime_type,
            'created': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        # Write back
        try:
            with open(info_file, 'w') as f:
                json.dump(file_info, f, indent=2)
        except:
            pass  # Fail silently if we can't write metadata
    
    def _get_stored_mime_type(self, file_path: Path) -> Optional[str]:
        """Retrieve stored MIME type from metadata."""
        info_file = file_path.parent / EXTENDED_ATTRS_FILE
        
        if not info_file.exists():
            return None
        
        try:
            with open(info_file, 'r') as f:
                file_info = json.load(f)
            
            file_key = file_path.name
            if file_key in file_info:
                return file_info[file_key].get('mime_type')
        except:
            pass
        
        return None
    
    def get_file_info(self, file_path: Path) -> Tuple[str, Dict[str, Any]]:
        """
        Get complete file information including MIME type and metadata.
        
        Returns:
            Tuple of (mime_type, metadata)
        """
        mime_type = self.detect_mime_type(file_path)
        
        # Try to get stored metadata
        info_file = file_path.parent / EXTENDED_ATTRS_FILE
        metadata = {}
        
        if info_file.exists():
            try:
                with open(info_file, 'r') as f:
                    file_info = json.load(f)
                
                file_key = file_path.name
                if file_key in file_info:
                    metadata = file_info[file_key].get('metadata', {})
            except:
                pass
        
        return mime_type, metadata
    
    def is_mindswarm_type(self, mime_type: str) -> bool:
        """Check if a MIME type is a Mind-Swarm specific type."""
        return mime_type.startswith('application/x-mindswarm-')


# Global instance
mime_handler = MimeHandler()