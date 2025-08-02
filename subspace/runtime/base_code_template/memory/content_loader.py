"""Content loader for lazy loading of filesystem content.

Only loads actual file content when a memory block is selected for context.
Includes caching to avoid repeated file reads.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging

from .memory_blocks import (
    MemoryBlock, FileMemoryBlock, MessageMemoryBlock, 
    KnowledgeMemoryBlock, ObservationMemoryBlock
)

logger = logging.getLogger("agent.memory.loader")


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
            filesystem_root: Root directory of the agent's filesystem
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
        if isinstance(memory, FileMemoryBlock):
            return self.load_file_content(memory)
        elif isinstance(memory, MessageMemoryBlock):
            return self.load_message_content(memory)
        elif isinstance(memory, KnowledgeMemoryBlock):
            return self.load_knowledge_content(memory)
        elif isinstance(memory, ObservationMemoryBlock):
            return self.format_observation(memory)
        else:
            # For other types, return a string representation
            return self._default_content(memory)
    
    def load_file_content(self, memory: FileMemoryBlock) -> str:
        """Load file content with caching."""
        # Handle virtual files (like boot ROM)
        if memory.metadata.get("virtual", False):
            return memory.metadata.get("content", "[Virtual file - no content]")
        
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
            
            if file_path.stat().st_size > 1_000_000:  # 1MB limit
                return f"[File too large: {memory.location} - {file_path.stat().st_size} bytes]"
            
            content = file_path.read_text(encoding='utf-8', errors='replace')
            
            # Cache the full content
            self.cache.put(cache_key, content)
            
            # Return requested lines
            return self._extract_lines(content, memory.start_line, memory.end_line)
            
        except Exception as e:
            logger.error(f"Error loading file {memory.location}: {e}")
            return f"[Error loading file: {memory.location} - {str(e)}]"
    
    def load_message_content(self, memory: MessageMemoryBlock) -> str:
        """Load message content from file."""
        cache_key = f"message:{memory.full_path}"
        
        # Check cache
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            msg_path = self._resolve_path(memory.full_path)
            
            if not msg_path.exists():
                # Return preview if file not found
                return f"Subject: {memory.subject}\n\n{memory.preview}"
            
            # Load message file
            msg_data = json.loads(msg_path.read_text())
            
            # Format message content
            content = self._format_message(msg_data, memory)
            
            # Cache it
            self.cache.put(cache_key, content)
            
            return content
            
        except Exception as e:
            logger.error(f"Error loading message {memory.full_path}: {e}")
            return f"Subject: {memory.subject}\n\n{memory.preview}"
    
    def load_knowledge_content(self, memory: KnowledgeMemoryBlock) -> str:
        """Load knowledge content from file."""
        cache_key = f"knowledge:{memory.location}"
        
        # Check cache
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            knowledge_path = self._resolve_path(memory.location)
            
            if not knowledge_path.exists():
                return f"[Knowledge not found: {memory.topic}]"
            
            content = knowledge_path.read_text(encoding='utf-8', errors='replace')
            
            # Format with topic header
            formatted = f"=== KNOWLEDGE: {memory.topic} ===\n"
            if memory.subtopic:
                formatted += f"Subtopic: {memory.subtopic}\n"
            formatted += f"\n{content}"
            
            # Cache it
            self.cache.put(cache_key, formatted)
            
            return formatted
            
        except Exception as e:
            logger.error(f"Error loading knowledge {memory.location}: {e}")
            return f"[Error loading knowledge: {memory.topic}]"
    
    def format_observation(self, memory: ObservationMemoryBlock) -> str:
        """Format an observation for context."""
        return (
            f"[OBSERVATION: {memory.observation_type}]\n"
            f"Path: {memory.path}\n"
            f"Description: {memory.description}\n"
            f"Time: {memory.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    
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
    
    def _format_message(self, msg_data: Dict[str, Any], memory: MessageMemoryBlock) -> str:
        """Format a message for display."""
        lines = [
            f"From: {memory.from_agent}",
            f"To: {memory.to_agent}",
            f"Subject: {memory.subject}",
            f"Time: {msg_data.get('timestamp', 'unknown')}",
            "",
            msg_data.get('content', memory.preview)
        ]
        
        return '\n'.join(lines)
    
    def _default_content(self, memory: MemoryBlock) -> str:
        """Generate default content for unknown memory types."""
        return (
            f"[{memory.type.value.upper()}]\n"
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