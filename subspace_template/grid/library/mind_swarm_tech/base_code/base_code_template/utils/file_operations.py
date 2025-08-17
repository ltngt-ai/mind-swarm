"""
File operations utilities for cybers with MIME type support.
"""

import json
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, Tuple


class FileOperations:
    """File operations with MIME type awareness for cybers."""
    
    def __init__(self):
        # Map MIME types to handlers
        self.handlers = {
            'application/json': self._handle_json,
            'application/x-mindswarm-message': self._handle_message,
            'application/x-mindswarm-knowledge': self._handle_knowledge,
            'text/x-yaml': self._handle_yaml,
            'text/plain': self._handle_text,
            'text/markdown': self._handle_markdown,
        }
    
    def save_file(
        self, 
        path: str, 
        content: Any, 
        mime_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Save a file with explicit MIME type.
        
        Args:
            path: File path relative to /personal/
            content: Content to save (can be dict, list, or string)
            mime_type: Explicit MIME type (auto-detect if None)
            metadata: Additional metadata to store
        
        Returns:
            Success status
        """
        file_path = Path(path)
        
        # Auto-detect MIME type if not provided
        if mime_type is None:
            mime_type = self._guess_mime_type(file_path, content)
        
        # Convert content based on MIME type
        if mime_type in ['application/json', 'application/x-mindswarm-message', 'application/x-mindswarm-memory']:
            content_str = json.dumps(content, indent=2) if not isinstance(content, str) else content
        elif mime_type in ['text/x-yaml', 'application/x-mindswarm-knowledge', 'application/x-mindswarm-config']:
            content_str = yaml.dump(content, default_flow_style=False) if not isinstance(content, str) else content
        else:
            content_str = str(content)
        
        # Write file
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content_str)
            
            # Store metadata in .fileinfo.json
            self._store_metadata(file_path, mime_type, metadata)
            
            return True
        except Exception as e:
            print(f"Error saving file: {e}")
            return False
    
    def read_file(self, path: str) -> Tuple[Any, str, Dict[str, Any]]:
        """
        Read a file and return parsed content with MIME type.
        
        Returns:
            Tuple of (content, mime_type, metadata)
        """
        file_path = Path(path)
        
        if not file_path.exists():
            return None, 'application/octet-stream', {}
        
        # Get MIME type and metadata
        mime_type = self._detect_mime_type(file_path)
        metadata = self._get_metadata(file_path)
        
        # Read and parse based on MIME type
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_content = f.read()
            
            # Use appropriate handler
            handler = self.handlers.get(mime_type, self._handle_text)
            content = handler(raw_content)
            
            return content, mime_type, metadata
            
        except Exception as e:
            print(f"Error reading file: {e}")
            return None, mime_type, metadata
    
    def _handle_json(self, content: str) -> Any:
        """Parse JSON content."""
        try:
            return json.loads(content)
        except:
            return content
    
    def _handle_yaml(self, content: str) -> Any:
        """Parse YAML content."""
        try:
            return yaml.safe_load(content)
        except:
            return content
    
    def _handle_message(self, content: str) -> Dict[str, Any]:
        """Parse message format (JSON or YAML)."""
        try:
            # Try JSON first
            return json.loads(content)
        except:
            try:
                # Try YAML
                return yaml.safe_load(content)
            except:
                return {'content': content}
    
    def _handle_knowledge(self, content: str) -> Dict[str, Any]:
        """Parse knowledge format with front matter support."""
        if content.startswith('---'):
            # Front matter format
            try:
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    metadata = yaml.safe_load(parts[1])
                    return {
                        **metadata,
                        'content': parts[2].strip()
                    }
            except:
                pass
        
        # Try standard YAML
        try:
            return yaml.safe_load(content)
        except:
            return {'content': content}
    
    def _handle_markdown(self, content: str) -> str:
        """Handle markdown files."""
        return content
    
    def _handle_text(self, content: str) -> str:
        """Handle plain text files."""
        return content
    
    def _guess_mime_type(self, file_path: Path, content: Any) -> str:
        """Guess MIME type from file extension and content."""
        # Check extension
        ext = file_path.suffix.lower()
        
        if ext == '.json':
            return 'application/json'
        elif ext in ['.yaml', '.yml']:
            # Check if it's knowledge based on content
            if isinstance(content, dict):
                if any(key in content for key in ['title', 'tags', 'category']):
                    return 'application/x-mindswarm-knowledge'
                elif any(key in content for key in ['to', 'from', 'subject']):
                    return 'application/x-mindswarm-message'
            return 'text/x-yaml'
        elif ext == '.md':
            return 'text/markdown'
        elif ext == '.txt':
            return 'text/plain'
        
        # Check directory hints
        path_str = str(file_path)
        if '/inbox/' in path_str or '/outbox/' in path_str:
            return 'application/x-mindswarm-message'
        elif '/knowledge/' in path_str:
            return 'application/x-mindswarm-knowledge'
        
        return 'text/plain'
    
    def _detect_mime_type(self, file_path: Path) -> str:
        """Detect MIME type of existing file."""
        # First check stored metadata
        metadata = self._get_metadata(file_path)
        if metadata and 'mime_type' in metadata:
            return metadata['mime_type']
        
        # Read first part of file for content sniffing
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                sample = f.read(1024)
            return self._guess_mime_type(file_path, sample)
        except:
            return 'application/octet-stream'
    
    def _store_metadata(self, file_path: Path, mime_type: str, metadata: Optional[Dict[str, Any]]):
        """Store file metadata."""
        info_file = file_path.parent / '.fileinfo.json'
        
        # Load existing info
        file_info = {}
        if info_file.exists():
            try:
                with open(info_file, 'r') as f:
                    file_info = json.load(f)
            except:
                file_info = {}
        
        # Update
        file_info[file_path.name] = {
            'mime_type': mime_type,
            'metadata': metadata or {}
        }
        
        # Write back
        try:
            with open(info_file, 'w') as f:
                json.dump(file_info, f, indent=2)
        except:
            pass
    
    def _get_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Get stored metadata for a file."""
        info_file = file_path.parent / '.fileinfo.json'
        
        if not info_file.exists():
            return {}
        
        try:
            with open(info_file, 'r') as f:
                file_info = json.load(f)
            return file_info.get(file_path.name, {})
        except:
            return {}


# Example usage for cybers:
if __name__ == "__main__":
    file_ops = FileOperations()
    
    # Save a knowledge document
    knowledge = {
        'title': 'How to Use File Operations',
        'tags': ['files', 'tutorial'],
        'content': 'This is how you work with files...'
    }
    file_ops.save_file(
        '/personal/docs/tutorial.yaml',
        knowledge,
        mime_type='application/x-mindswarm-knowledge'
    )
    
    # Save a message
    message = {
        'to': 'Alice@mind-swarm.local',
        'from': 'Bob',
        'subject': 'Question about files',
        'body': 'How do I save files with proper types?'
    }
    file_ops.save_file(
        '/personal/outbox/msg_001.json',
        message,
        mime_type='application/x-mindswarm-message'
    )
    
    # Read a file (auto-detects type)
    content, mime_type, metadata = file_ops.read_file('/personal/docs/tutorial.yaml')
    print(f"Read {mime_type}: {content}")