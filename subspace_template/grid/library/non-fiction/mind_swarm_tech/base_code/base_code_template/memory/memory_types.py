"""Shared memory type definitions to avoid circular imports.

This module contains the core enums used throughout the memory system.
"""

from enum import Enum


class Priority(Enum):
    """Memory priority levels for selection algorithm.
    
    Lower numeric values = higher priority.
    FOUNDATIONAL and SYSTEM are special autonomous priorities.
    """
    FOUNDATIONAL = 0  # ROM knowledge, absolute foundation
    SYSTEM = 1        # System-controlled memories (pipelines, dynamic context)
    CRITICAL = 2      # User-critical, always included
    HIGH = 3          # Important, included unless space critical  
    MEDIUM = 4        # Normal priority, included based on relevance
    LOW = 5           # Background info, often dropped


class ContentType(Enum):
    """Content types for memory blocks using MIME types and custom Mind-Swarm types.
    
    Standard MIME types for common file formats plus custom types for Mind-Swarm
    specific content like observations, goals, and internal structures.
    """
    # Text formats
    TEXT_PLAIN = "text/plain"
    TEXT_MARKDOWN = "text/markdown"
    TEXT_HTML = "text/html"
    TEXT_CSV = "text/csv"
    
    # Data formats
    APPLICATION_JSON = "application/json"
    APPLICATION_YAML = "application/x-yaml"
    APPLICATION_XML = "application/xml"
    APPLICATION_TOML = "application/toml"
    
    # Code formats
    TEXT_PYTHON = "text/x-python"
    TEXT_JAVASCRIPT = "text/javascript"
    TEXT_TYPESCRIPT = "text/typescript"
    TEXT_SHELL = "text/x-shellscript"
    
    # Binary formats
    APPLICATION_OCTET_STREAM = "application/octet-stream"
    IMAGE_PNG = "image/png"
    IMAGE_JPEG = "image/jpeg"
    IMAGE_GIF = "image/gif"
    
    # Mind-Swarm specific types (only 2 currently defined)
    MINDSWARM_MESSAGE = "application/x-mindswarm-message"
    MINDSWARM_KNOWLEDGE = "application/x-mindswarm-knowledge"
    
    # Unknown/default
    UNKNOWN = "application/octet-stream"
    
    @classmethod
    def from_file_extension(cls, path: str) -> 'ContentType':
        """Determine content type from file extension.
        
        Args:
            path: File path or name
            
        Returns:
            Appropriate ContentType enum value
        """
        import os
        ext = os.path.splitext(path)[1].lower()
        
        extension_map = {
            '.txt': cls.TEXT_PLAIN,
            '.md': cls.TEXT_MARKDOWN,
            '.markdown': cls.TEXT_MARKDOWN,
            '.html': cls.TEXT_HTML,
            '.htm': cls.TEXT_HTML,
            '.csv': cls.TEXT_CSV,
            '.json': cls.APPLICATION_JSON,
            '.yaml': cls.APPLICATION_YAML,
            '.yml': cls.APPLICATION_YAML,
            '.xml': cls.APPLICATION_XML,
            '.toml': cls.APPLICATION_TOML,
            '.py': cls.TEXT_PYTHON,
            '.js': cls.TEXT_JAVASCRIPT,
            '.ts': cls.TEXT_TYPESCRIPT,
            '.sh': cls.TEXT_SHELL,
            '.bash': cls.TEXT_SHELL,
            '.png': cls.IMAGE_PNG,
            '.jpg': cls.IMAGE_JPEG,
            '.jpeg': cls.IMAGE_JPEG,
            '.gif': cls.IMAGE_GIF,
        }
        
        return extension_map.get(ext, cls.UNKNOWN)