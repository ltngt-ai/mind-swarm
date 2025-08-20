"""Content loader for lazy loading of filesystem content.

Only loads actual file content when a memory block is selected for context.
Includes caching to avoid repeated file reads.
"""

import json
import yaml
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging

from .memory_blocks import (
    MemoryBlock
)
from .memory_types import ContentType

logger = logging.getLogger("Cyber.memory.loader")


class ContentCache:
    """Simple cache for loaded content with TTL."""
    
    def __init__(self, ttl_seconds: int = 300):
        """Initialize cache with time-to-live in seconds."""
        self.ttl = timedelta(seconds=ttl_seconds)
        self.cache: Dict[str, Tuple[str, datetime]] = {}
    
    def get(self, key: str) -> Optional[str]:
        """Get content from cache if not expired."""
        if key in self.cache:
            content, timestamp = self.cache[key]
            if datetime.now() - timestamp < self.ttl:
                return content
            else:
                # Expired, remove it
                del self.cache[key]
        return None
    
    def put(self, key: str, content: str) -> None:
        """Store content in cache."""
        self.cache[key] = (content, datetime.now())
    
    def invalidate(self, key: str) -> bool:
        """Invalidate a specific cache entry.
        
        Args:
            key: The cache key to invalidate
            
        Returns:
            True if the entry was found and removed, False otherwise
        """
        if key in self.cache:
            del self.cache[key]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cached content."""
        self.cache.clear()
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count."""
        now = datetime.now()
        expired_keys = [
            key for key, (_, timestamp) in self.cache.items()
            if now - timestamp >= self.ttl
        ]
        for key in expired_keys:
            del self.cache[key]
        return len(expired_keys)


class ContentLoader:
    """Loads actual content for memory blocks from the filesystem."""
    
    def __init__(self, filesystem_root: Path, cache_ttl: int = 300):
        """Initialize content loader.
        
        Args:
            filesystem_root: Root directory of the Cyber's filesystem
            cache_ttl: Cache time-to-live in seconds
        """
        self.filesystem_root = Path(filesystem_root)
        self.cache = ContentCache(ttl_seconds=cache_ttl)
    
    def load_content(self, memory: MemoryBlock) -> str:
        """Load actual content for a memory block.
        
        Args:
            memory: The memory block to load content for
            
        Returns:
            The loaded content as a string
        """
        if isinstance(memory, MemoryBlock):
            # Check if it's a knowledge memory block
            if hasattr(memory, 'content_type') and memory.content_type == ContentType.MINDSWARM_KNOWLEDGE:
                return self.load_knowledge_content(memory)
            else:
                return self.load_file_content(memory)
        # ObservationMemoryBlock removed - observations are now ephemeral
        else:
            # For other types, return a string representation
            return self._default_content(memory)
    
    def load_file_content(self, memory: MemoryBlock) -> str:
        """Load file content with caching."""
        # Handle virtual files (like boot ROM)
        if memory.metadata.get("virtual", False):
            return memory.metadata.get("content", "[Virtual file - no content]")
        
        # Skip cache for no_cache files (e.g., memory-mapped files)
        if not getattr(memory, 'no_cache', False):
            # Build cache key
            cache_key = f"file:{memory.location}:{memory.digest or 'no-digest'}"
            
            # Check cache first
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for {memory.location}")
                return self._extract_lines(cached, memory.start_line, memory.end_line)
        
        # Load from filesystem
        try:
            file_path = self._resolve_path(memory.location)
            
            if not file_path.exists():
                return f"[File not found: {memory.location}]"
            
            # Handle directories
            if file_path.is_dir():
                # Create a directory listing
                try:
                    items = []
                    for item in sorted(file_path.iterdir()):
                        if item.is_dir():
                            items.append(f"📁 {item.name}/")
                        else:
                            size = item.stat().st_size
                            items.append(f"📄 {item.name} ({size} bytes)")
                    
                    content = f"Directory: {file_path}\n"
                    content += f"Contains {len(items)} items:\n\n"
                    content += "\n".join(items)
                    
                    # Cache the directory listing
                    self.cache.put(cache_key, content)
                    return content
                    
                except Exception as e:
                    return f"[Error listing directory: {memory.location} - {str(e)}]"
            
            if file_path.stat().st_size > 1_000_000:  # 1MB limit
                return f"[File too large: {memory.location} - {file_path.stat().st_size} bytes]"
            
            # Read file content
            if file_path.suffix == '.json' and 'dynamic_context' in file_path.name:
                # For memory-mapped dynamic_context, read as binary and stop at null
                with open(file_path, 'rb') as f:
                    content_bytes = f.read(4096)  # Max size of memory-mapped file
                    null_pos = content_bytes.find(b'\0')
                    if null_pos != -1:
                        content = content_bytes[:null_pos].decode('utf-8')
                    else:
                        content = content_bytes.decode('utf-8', errors='replace')
            else:
                content = file_path.read_text(encoding='utf-8', errors='replace')
            
            # Cache the full content (unless no_cache is set)
            if not getattr(memory, 'no_cache', False):
                cache_key = f"file:{memory.location}:{memory.digest or 'no-digest'}"
                self.cache.put(cache_key, content)
            
            # Return requested lines
            return self._extract_lines(content, memory.start_line, memory.end_line)
            
        except Exception as e:
            logger.error(f"Error loading file {memory.location}: {e}")
            return f"[Error loading file: {memory.location} - {str(e)}]"
    
    # Removed load_message_content - messages are just MemoryBlock now
    
    def load_knowledge_content(self, memory: MemoryBlock) -> str:
        """Load knowledge content from metadata or file."""
        # Check if content is in metadata (for ROM and in-memory knowledge)
        if memory.metadata and memory.metadata.get("content"):
            return memory.metadata["content"]
        
        # Otherwise load from file
        cache_key = f"knowledge:{memory.location}"
        
        # Check cache
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            knowledge_path = self._resolve_path(memory.location)
            
            if not knowledge_path.exists():
                return f"[Knowledge not found: {memory.topic}]"
            
            # Load and parse knowledge file
            file_content = knowledge_path.read_text(encoding='utf-8', errors='replace')
            knowledge_data = yaml.safe_load(file_content)
            
            # Extract content from knowledge file
            content = knowledge_data.get("content", "[No content in knowledge file]")
            
            # Cache it
            self.cache.put(cache_key, content)
            
            return content
            
        except Exception as e:
            logger.error(f"Error loading knowledge {memory.location}: {e}")
            return f"[Error loading knowledge: {memory.topic}]"
    
    # ObservationMemoryBlock removed - observations are now ephemeral
    
    def _resolve_path(self, path_str: str) -> Path:
        """Resolve a path relative to filesystem root."""
        path = Path(path_str)
        
        # If absolute and under filesystem root, use as-is
        if path.is_absolute():
            if str(path).startswith(str(self.filesystem_root)):
                return path
            else:
                # Security: don't allow paths outside filesystem root
                raise ValueError(f"Path outside filesystem root: {path}")
        
        # Otherwise, resolve relative to filesystem root
        return self.filesystem_root / path
    
    def _extract_lines(self, content: str, start_line: Optional[int], end_line: Optional[int]) -> str:
        """Extract specific lines from content."""
        if start_line is None and end_line is None:
            return content
        
        lines = content.split('\n')
        
        # Convert to 0-based indexing
        start = (start_line - 1) if start_line else 0
        end = end_line if end_line else len(lines)
        
        # Ensure valid range
        start = max(0, min(start, len(lines)))
        end = max(start, min(end, len(lines)))
        
        return '\n'.join(lines[start:end])
    
    # Removed _format_message - LLM can read raw JSON
    
    def _default_content(self, memory: MemoryBlock) -> str:
        """Generate default content for unknown memory types."""
        return (
            f"[{memory.content_type.value.upper() if hasattr(memory.content_type, 'value') else str(memory.content_type).upper()}]\n"
            f"ID: {memory.id}\n"
            f"Priority: {memory.priority.name}\n"
            f"Confidence: {memory.confidence:.2f}\n"
            f"Metadata: {json.dumps(memory.metadata, indent=2)}"
        )
    
    def compute_file_digest(self, file_path: str) -> Optional[str]:
        """Compute SHA256 digest of a file for change detection."""
        try:
            path = self._resolve_path(file_path)
            if path.exists():
                content = path.read_bytes()
                return hashlib.sha256(content).hexdigest()[:16]  # First 16 chars
        except Exception as e:
            logger.error(f"Error computing digest for {file_path}: {e}")
        
        return None
    
    def invalidate_file(self, file_path: str) -> bool:
        """Invalidate cache for a specific file.
        
        Args:
            file_path: Path to the file to invalidate
            
        Returns:
            True if cache was invalidated, False otherwise
        """
        # Try to match any cache key that contains this file path
        # Cache keys are like "file:/path/to/file:digest"
        invalidated = False
        keys_to_remove = []
        
        for key in self.cache.cache.keys():
            if key.startswith(f"file:{file_path}:"):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            if self.cache.invalidate(key):
                invalidated = True
                logger.debug(f"Invalidated cache for: {key}")
        
        return invalidated