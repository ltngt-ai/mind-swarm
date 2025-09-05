"""Knowledge sync configuration loader and validator.

Loads and validates the knowledge_sync.yaml configuration file,
providing structured access to sync roots, filters, and behavior settings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern

import yaml

from mind_swarm.utils.logging import logger


def is_binary_file(file_path: Path, sample_size: int = 8192) -> bool:
    """Check if a file appears to be binary by looking for null bytes.
    
    Args:
        file_path: Path to the file to check
        sample_size: Number of bytes to sample (default 8192)
        
    Returns:
        True if file appears to be binary, False otherwise
    """
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(sample_size)
            if b'\x00' in chunk:
                return True
            # Check for high ratio of non-printable characters
            text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
            non_text = len([b for b in chunk if b not in text_chars])
            return non_text / len(chunk) > 0.30 if chunk else False
    except Exception:
        # If we can't read the file, assume it's binary for safety
        return True


@dataclass
class SyncRoot:
    """Configuration for a knowledge sync root."""
    name: str
    source_path: str
    id_prefix: str
    description: str
    enabled: bool = True
    priority: int = 50
    runtime: bool = False  # If True, use runtime path instead of template path


@dataclass
class ContentFilter:
    """Pattern-based content filter."""
    pattern: str
    description: str
    compiled_pattern: Pattern = field(init=False, repr=False)
    
    def __post_init__(self):
        """Compile the regex pattern."""
        self.compiled_pattern = re.compile(self.pattern)
    
    def matches(self, content: str) -> bool:
        """Check if content matches the filter pattern."""
        return bool(self.compiled_pattern.search(content))


@dataclass
class KnowledgeSyncConfig:
    """Knowledge sync configuration."""
    version: str
    sync_roots: List[SyncRoot]
    include_patterns: List[str]
    exclude_patterns: List[str]
    security_denylist: List[str]
    content_filters: Dict[str, Any]
    sync_behavior: Dict[str, Any]
    metadata_defaults: Dict[str, Any]
    logging: Dict[str, Any]
    
    # Compiled patterns for efficient matching
    _include_compiled: List[Pattern] = field(default_factory=list, init=False, repr=False)
    _exclude_compiled: List[Pattern] = field(default_factory=list, init=False, repr=False)
    _security_compiled: List[Pattern] = field(default_factory=list, init=False, repr=False)
    _content_denylist: List[ContentFilter] = field(default_factory=list, init=False, repr=False)
    
    def __post_init__(self):
        """Compile patterns for efficient matching."""
        # Compile glob patterns to regex
        self._include_compiled = [self._glob_to_regex(p) for p in self.include_patterns]
        self._exclude_compiled = [self._glob_to_regex(p) for p in self.exclude_patterns]
        self._security_compiled = [self._glob_to_regex(p) for p in self.security_denylist]
        
        # Compile content filters
        content_denylist = self.content_filters.get("content_denylist", [])
        for filter_spec in content_denylist:
            if isinstance(filter_spec, dict) and "pattern" in filter_spec:
                try:
                    self._content_denylist.append(
                        ContentFilter(
                            pattern=filter_spec["pattern"],
                            description=filter_spec.get("description", "")
                        )
                    )
                except re.error as e:
                    logger.warning(f"Invalid content filter regex: {filter_spec['pattern']}: {e}")
    
    @staticmethod
    def _glob_to_regex(pattern: str) -> Pattern:
        """Convert a glob pattern to a compiled regex.
        
        Args:
            pattern: Glob pattern (e.g., "*.md", "**/*.yaml")
            
        Returns:
            Compiled regex pattern
        """
        
        # Save original for checking patterns
        original = pattern
        
        # Replace glob patterns with placeholders before escaping
        pattern = pattern.replace('**/', '__GLOBSTAR_SLASH__')
        pattern = pattern.replace('**', '__GLOBSTAR__')
        pattern = pattern.replace('*', '__STAR__')
        pattern = pattern.replace('?', '__QUESTION__')
        
        # Escape special regex characters
        escaped = re.escape(pattern)
        
        # Replace placeholders with regex patterns
        escaped = escaped.replace('__GLOBSTAR_SLASH__', '.*')  # ** matches any path depth
        escaped = escaped.replace('__GLOBSTAR__', '.*')  # ** at end
        escaped = escaped.replace('__STAR__', '[^/]*')  # * matches within segment
        escaped = escaped.replace('__QUESTION__', '.')  # ? matches single char
        
        # For patterns starting with *, we want to match any path ending
        if original.startswith('**/'):
            # Match any path starting with this pattern
            regex = escaped
        elif original.startswith('*'):
            # Match files with this pattern anywhere
            regex = f"(^|.*/){escaped}$"
        elif '/' not in original:
            # Simple filename pattern - match in any directory
            regex = f"(^|.*/){escaped}$"
        else:
            # Path pattern - match from beginning
            regex = f"^{escaped}$"
        
        return re.compile(regex, re.IGNORECASE)
    
    def should_include_file(self, file_path: Path) -> bool:
        """Check if a file should be included based on include patterns.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file matches any include pattern
        """
        path_str = file_path.as_posix()
        return any(pattern.match(path_str) or pattern.match(file_path.name) 
                  for pattern in self._include_compiled)
    
    def should_exclude_file(self, file_path: Path) -> bool:
        """Check if a file should be excluded based on exclude patterns.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file matches any exclude pattern
        """
        path_str = file_path.as_posix()
        return any(pattern.match(path_str) or pattern.match(file_path.name) 
                  for pattern in self._exclude_compiled)
    
    def is_security_risk(self, file_path: Path) -> bool:
        """Check if a file path indicates a security risk.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file matches any security denylist pattern
        """
        path_str = file_path.as_posix()
        return any(pattern.match(path_str) or pattern.match(file_path.name) 
                  for pattern in self._security_compiled)
    
    def validate_file_type(self, file_path: Path) -> bool:
        """Validate that file type is explicitly allowed.
        
        Uses a whitelist approach - only explicitly allowed extensions are permitted.
        
        Args:
            file_path: Path to validate
            
        Returns:
            True if file type is allowed, False otherwise
        """
        # Extract extension (lowercase, without dot)
        suffix = file_path.suffix.lower()
        if not suffix:
            return False
            
        # Define allowed extensions (whitelist)
        allowed_extensions = {
            '.md', '.markdown', '.txt', '.rst',  # Documentation
            '.yaml', '.yml', '.json', '.toml',   # Structured data
            '.knowledge', '.prompt', '.template'  # Knowledge-specific
        }
        
        return suffix in allowed_extensions
    
    def is_path_suspicious(self, file_path: Path) -> Optional[str]:
        """Check if a file path structure indicates potential security risk.
        
        Args:
            file_path: Path to check
            
        Returns:
            Reason if suspicious, None otherwise
        """
        path_str = file_path.as_posix().lower()
        
        # Check for hidden files/directories (except .gitignore and .gitkeep which might be ok)
        if '/.internal/' in path_str:
            return "Internal directory access"
        
        # Get just the filename
        filename = file_path.name
        if filename.startswith('.') and filename not in ['.gitignore', '.gitkeep']:
            return "Hidden file"
        
        # Check for hidden directories in the path
        parts = path_str.split('/')
        for part in parts[:-1]:  # Exclude the filename itself
            if part.startswith('.') and part not in ['.git']:
                return "Hidden directory"
        
        # Check for backup/temporary patterns in path
        suspicious_patterns = [
            ('~', 'Backup file'),
            ('.swp', 'Editor swap file'),
            ('.swo', 'Editor swap file'),
            ('.orig', 'Merge conflict file'),
            ('.rej', 'Patch reject file'),
            ('#', 'Editor autosave file'),
        ]
        
        for pattern, reason in suspicious_patterns:
            if pattern in path_str:
                return reason
        
        return None
    
    def has_sensitive_content(self, content: str) -> Optional[str]:
        """Check if content contains sensitive patterns.
        
        Args:
            content: File content to check
            
        Returns:
            Description of first matched pattern, or None if no match
        """
        for content_filter in self._content_denylist:
            if content_filter.matches(content):
                return content_filter.description
        
        # Additional heuristic checks
        # Check for base64 encoded secrets (common pattern)
        import re
        # Look for long base64 strings that look like tokens/secrets
        base64_pattern = re.compile(r'(?:^|[^A-Za-z0-9+/])([A-Za-z0-9+/]{40,}={0,2})(?:[^A-Za-z0-9+/]|$)')
        matches = base64_pattern.findall(content)
        for match in matches:
            # Check if it might be a secret (has mixed case, numbers)
            if any(c.isupper() for c in match) and any(c.islower() for c in match) and any(c.isdigit() for c in match):
                # Additional check - secrets often have high entropy
                if len(set(match)) > len(match) * 0.5:  # High character diversity
                    return "Potential base64 encoded secret"
        
        return None
    
    def get_root_by_name(self, name: str) -> Optional[SyncRoot]:
        """Get a sync root configuration by name.
        
        Args:
            name: Root name to find
            
        Returns:
            SyncRoot if found, None otherwise
        """
        for root in self.sync_roots:
            if root.name == name:
                return root
        return None
    
    def perform_file_sanity_checks(self, file_path: Path, content: bytes) -> Optional[str]:
        """Perform comprehensive sanity checks on a file.
        
        Args:
            file_path: Path to the file
            content: Raw file content as bytes
            
        Returns:
            Error message if check fails, None if all checks pass
        """
        # Check file size limits
        max_size = self.content_filters.get("max_file_size", 10485760)
        min_size = self.content_filters.get("min_file_size", 1)
        
        file_size = len(content)
        if file_size > max_size:
            return f"File too large: {file_size} bytes (max: {max_size})"
        if file_size < min_size:
            return f"File too small: {file_size} bytes (min: {min_size})"
        
        # Check for executable permissions or shebang first
        try:
            if content.startswith(b'#!'):
                return "Executable script detected (shebang)"
        except:
            pass
        
        # Check for null bytes in text files
        if b'\x00' in content:
            return "Null bytes detected in file"
        
        # Check encoding - should be valid UTF-8
        try:
            content.decode('utf-8')
        except UnicodeDecodeError:
            return "Invalid UTF-8 encoding"
        
        # Check if binary (do this after UTF-8 check to distinguish between binary and invalid encoding)
        if self.content_filters.get("skip_binary", True) and not content.startswith(b'#!'):
            if is_binary_file(file_path):
                return "Binary file detected"
        
        return None
    
    def get_enabled_roots(self) -> List[SyncRoot]:
        """Get all enabled sync roots sorted by priority.
        
        Returns:
            List of enabled sync roots in priority order (highest first)
        """
        return sorted(
            [root for root in self.sync_roots if root.enabled],
            key=lambda r: r.priority,
            reverse=True
        )


def load_knowledge_sync_config(config_path: Optional[Path] = None) -> KnowledgeSyncConfig:
    """Load knowledge sync configuration from YAML file.
    
    Args:
        config_path: Path to config file (defaults to config/knowledge_sync.yaml)
        
    Returns:
        Loaded and validated configuration
        
    Raises:
        FileNotFoundError: If config file not found
        ValueError: If config is invalid
    """
    if config_path is None:
        # Default to config/knowledge_sync.yaml relative to project root
        config_path = Path(__file__).parent.parent.parent.parent / "config" / "knowledge_sync.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Knowledge sync config not found: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    if not isinstance(data, dict):
        raise ValueError("Invalid config format: expected dictionary")
    
    # Validate required fields
    required = ["version", "sync_roots", "include_patterns", "exclude_patterns", 
                "security_denylist"]
    missing = [field for field in required if field not in data]
    if missing:
        raise ValueError(f"Missing required config fields: {missing}")
    
    # Convert sync_roots to SyncRoot objects
    sync_roots = []
    for root_data in data.get("sync_roots", []):
        if not isinstance(root_data, dict):
            continue
        sync_roots.append(SyncRoot(
            name=root_data.get("name", ""),
            source_path=root_data.get("source_path", ""),
            id_prefix=root_data.get("id_prefix", ""),
            description=root_data.get("description", ""),
            enabled=root_data.get("enabled", True),
            priority=root_data.get("priority", 50),
            runtime=root_data.get("runtime", False)
        ))
    
    return KnowledgeSyncConfig(
        version=data["version"],
        sync_roots=sync_roots,
        include_patterns=data.get("include_patterns", []),
        exclude_patterns=data.get("exclude_patterns", []),
        security_denylist=data.get("security_denylist", []),
        content_filters=data.get("content_filters", {}),
        sync_behavior=data.get("sync_behavior", {}),
        metadata_defaults=data.get("metadata_defaults", {}),
        logging=data.get("logging", {})
    )
