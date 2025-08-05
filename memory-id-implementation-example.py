"""
Example implementation of the Unified Memory ID System for Mind-Swarm.

This shows how the new ID system would work in practice with full
backward compatibility and semantic understanding.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from enum import Enum


def calculate_content_hash(content: Union[str, bytes, Path]) -> str:
    """Calculate a content hash for deduplication."""
    if isinstance(content, Path):
        if content.exists():
            content = content.read_bytes()
        else:
            content = str(content).encode()
    elif isinstance(content, str):
        content = content.encode()
    
    return hashlib.sha256(content).hexdigest()


@dataclass
class UnifiedMemoryID:
    """Unified memory ID system for all memory types.
    
    Format: {type}:{namespace}:{semantic_path}[:{content_hash}]
    
    Examples:
        - file:personal:notes/daily/2024-01-15:a7b9c2
        - message:inbox:from-alice/about-project:b8c3d1
        - knowledge:rom:cognitive/ooda-loop:e9f1a2
    """
    
    type: str  # file, message, knowledge, observation, task, etc.
    namespace: str  # personal, shared, inbox, rom, grid, etc.
    semantic_path: str  # meaningful path like "notes/daily/2024-01-15"
    content_hash: Optional[str] = None  # 6-char hash of content
    
    def __str__(self) -> str:
        """Generate the ID string."""
        base = f"{self.type}:{self.namespace}:{self.semantic_path}"
        if self.content_hash:
            return f"{base}:{self.content_hash}"
        return base
    
    @classmethod
    def from_file_path(cls, file_path: Path, home_dir: Path, content: Optional[str] = None) -> 'UnifiedMemoryID':
        """Create ID from file path with intelligent namespace detection."""
        # Normalize the path
        file_path = file_path.resolve()
        
        # Determine namespace based on location
        if file_path.is_relative_to(home_dir / "memory"):
            namespace = "personal"
            base_path = home_dir / "memory"
        elif file_path.is_relative_to(home_dir.parent / "grid" / "plaza"):
            namespace = "plaza"
            base_path = home_dir.parent / "grid" / "plaza"
        elif file_path.is_relative_to(home_dir.parent / "grid" / "library"):
            namespace = "library"
            base_path = home_dir.parent / "grid" / "library"
        elif file_path.is_relative_to(home_dir.parent / "grid" / "workshop"):
            namespace = "workshop"
            base_path = home_dir.parent / "grid" / "workshop"
        elif file_path.is_relative_to(home_dir.parent / "grid"):
            namespace = "shared"
            base_path = home_dir.parent / "grid"
        elif file_path.is_relative_to(home_dir):
            namespace = "agent"
            base_path = home_dir
        else:
            namespace = "system"
            base_path = file_path.parent
        
        # Generate semantic path
        try:
            semantic_path = str(file_path.relative_to(base_path))
        except ValueError:
            semantic_path = file_path.name
        
        # Remove file extension for cleaner IDs
        if semantic_path.endswith(('.json', '.txt', '.md', '.yaml')):
            semantic_path = semantic_path.rsplit('.', 1)[0]
        
        # Calculate content hash
        content_hash = None
        if content:
            content_hash = calculate_content_hash(content)[:6]
        elif file_path.exists():
            content_hash = calculate_content_hash(file_path)[:6]
        
        return cls(
            type="file",
            namespace=namespace,
            semantic_path=semantic_path,
            content_hash=content_hash
        )
    
    @classmethod
    def from_message(cls, from_agent: str, subject: str, content: str, 
                     message_path: Optional[Path] = None) -> 'UnifiedMemoryID':
        """Create ID for a message."""
        # Clean agent name and subject for path
        from_clean = from_agent.lower().replace(" ", "-")
        subject_clean = subject.lower()[:30].replace(" ", "-").replace("/", "-")
        
        semantic_path = f"from-{from_clean}/{subject_clean}"
        content_hash = calculate_content_hash(content)[:6]
        
        return cls(
            type="message",
            namespace="inbox",
            semantic_path=semantic_path,
            content_hash=content_hash
        )
    
    @classmethod
    def from_observation(cls, obs_type: str, target: str, description: str) -> 'UnifiedMemoryID':
        """Create ID for an observation."""
        # Create semantic path from observation details
        target_clean = target.replace("/", "-").replace(" ", "-")
        obs_clean = obs_type.replace("_", "-")
        
        semantic_path = f"{obs_clean}/{target_clean}"
        content_hash = calculate_content_hash(description)[:6]
        
        return cls(
            type="observation",
            namespace="transient",  # Observations are temporary
            semantic_path=semantic_path,
            content_hash=content_hash
        )
    
    @classmethod
    def from_knowledge(cls, topic: str, subtopic: Optional[str] = None, 
                      source: str = "rom", content: Optional[str] = None) -> 'UnifiedMemoryID':
        """Create ID for knowledge entries."""
        if subtopic:
            semantic_path = f"{topic}/{subtopic}"
        else:
            semantic_path = topic
        
        content_hash = None
        if content:
            content_hash = calculate_content_hash(content)[:6]
        
        return cls(
            type="knowledge",
            namespace=source,  # rom, learned, derived
            semantic_path=semantic_path,
            content_hash=content_hash
        )
    
    @classmethod
    def parse(cls, id_string: str) -> 'UnifiedMemoryID':
        """Parse an ID string back into components."""
        parts = id_string.split(":", 3)
        if len(parts) < 3:
            raise ValueError(f"Invalid memory ID format: {id_string}")
        
        return cls(
            type=parts[0],
            namespace=parts[1],
            semantic_path=parts[2],
            content_hash=parts[3] if len(parts) > 3 else None
        )
    
    def matches_pattern(self, pattern: str) -> bool:
        """Check if this ID matches a glob-like pattern.
        
        Examples:
            - "file:personal:notes/*" matches all personal notes
            - "message:inbox:from-alice/*" matches all messages from alice
            - "*:*:*project*" matches anything with 'project' in the path
        """
        import fnmatch
        return fnmatch.fnmatch(str(self), pattern)
    
    def to_file_path(self, home_dir: Path) -> Path:
        """Convert semantic ID back to a file path."""
        # Map namespace to base directory
        namespace_map = {
            "personal": home_dir / "memory",
            "agent": home_dir,
            "plaza": home_dir.parent / "grid" / "plaza",
            "library": home_dir.parent / "grid" / "library",
            "workshop": home_dir.parent / "grid" / "workshop",
            "shared": home_dir.parent / "grid",
            "inbox": home_dir / "inbox",
            "outbox": home_dir / "outbox"
        }
        
        base_dir = namespace_map.get(self.namespace, home_dir)
        
        # Reconstruct the path
        file_path = base_dir / self.semantic_path
        
        # Add appropriate extension if missing
        if not file_path.suffix:
            if self.type == "message":
                file_path = file_path.with_suffix(".json")
            elif self.type in ["file", "knowledge"]:
                # Try to find the actual file
                for ext in [".md", ".txt", ".json", ".yaml"]:
                    test_path = file_path.with_suffix(ext)
                    if test_path.exists():
                        file_path = test_path
                        break
        
        return file_path


class MemoryIDTranslator:
    """Translate between old and new memory ID formats."""
    
    def __init__(self, home_dir: Path):
        self.home_dir = home_dir
        self.translation_cache: Dict[str, str] = {}
    
    def translate_to_unified(self, old_id: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Convert old ID format to new unified format.
        
        Handles various old formats:
        - Raw paths: /home/agent/memory/notes.txt
        - File with range: /path/to/file.py:10-20
        - Message IDs: msg:/home/agent/inbox/message-123.json
        - Knowledge IDs: knowledge:topic:subtopic
        - Observation IDs: obs:/path/to/file:timestamp
        """
        # Check cache first
        if old_id in self.translation_cache:
            return self.translation_cache[old_id]
        
        try:
            # Handle different old patterns
            if old_id.startswith("msg:"):
                # Old message format
                path = Path(old_id[4:])
                unified = UnifiedMemoryID.from_file_path(path, self.home_dir)
                unified.type = "message"
                unified.namespace = "inbox"
                
            elif old_id.startswith("obs:"):
                # Old observation format - obs:path:timestamp
                parts = old_id[4:].rsplit(":", 1)
                path = parts[0]
                unified = UnifiedMemoryID(
                    type="observation",
                    namespace="transient",
                    semantic_path=path.replace("/", "-"),
                    content_hash=None  # Lost in old format
                )
                
            elif old_id.startswith("knowledge:"):
                # Already somewhat unified
                parts = old_id.split(":", 2)
                topic = parts[1] if len(parts) > 1 else "general"
                subtopic = parts[2] if len(parts) > 2 else None
                unified = UnifiedMemoryID.from_knowledge(topic, subtopic)
                
            elif ":" in old_id and old_id.count(":") == 1:
                # File with line range: /path/to/file:10-20
                file_path, line_range = old_id.rsplit(":", 1)
                unified = UnifiedMemoryID.from_file_path(Path(file_path), self.home_dir)
                # Preserve line range in semantic path
                unified.semantic_path += f"#L{line_range}"
                
            else:
                # Assume it's a file path
                unified = UnifiedMemoryID.from_file_path(Path(old_id), self.home_dir)
            
            new_id = str(unified)
            self.translation_cache[old_id] = new_id
            return new_id
            
        except Exception as e:
            # If translation fails, return original
            print(f"Warning: Could not translate ID {old_id}: {e}")
            return old_id
    
    def translate_from_unified(self, unified_id: str) -> str:
        """Convert unified ID back to old format for compatibility."""
        try:
            uid = UnifiedMemoryID.parse(unified_id)
            
            if uid.type == "message":
                # Convert back to msg: format
                file_path = uid.to_file_path(self.home_dir)
                return f"msg:{file_path}"
            
            elif uid.type == "observation":
                # Can't fully reconstruct timestamp, use current
                return f"obs:{uid.semantic_path}:{datetime.now().timestamp()}"
            
            elif uid.type == "knowledge":
                # Convert back to knowledge: format
                return f"knowledge:{uid.semantic_path.replace('/', ':')}"
            
            else:
                # Convert to file path
                file_path = uid.to_file_path(self.home_dir)
                
                # Check for line range in semantic path
                if "#L" in uid.semantic_path:
                    path_part, line_part = uid.semantic_path.split("#L", 1)
                    return f"{file_path}:{line_part}"
                
                return str(file_path)
                
        except Exception as e:
            print(f"Warning: Could not translate from unified ID {unified_id}: {e}")
            return unified_id


# Example usage showing the benefits
def demonstrate_unified_ids():
    """Show how the unified ID system improves agent memory handling."""
    
    home_dir = Path("/home/agent")
    
    # Example 1: File memories with semantic meaning
    note_path = home_dir / "memory" / "reflections" / "oodia-learnings.md"
    note_id = UnifiedMemoryID.from_file_path(
        note_path, 
        home_dir,
        content="Today I learned about the OODIA loop..."
    )
    print(f"Note ID: {note_id}")
    # Output: file:personal:reflections/oodia-learnings:a7b9c2
    
    # Example 2: Message with semantic info
    message_id = UnifiedMemoryID.from_message(
        from_agent="Alice",
        subject="Project collaboration request", 
        content="Would you like to work together on..."
    )
    print(f"Message ID: {message_id}")
    # Output: message:inbox:from-alice/project-collaboration-request:d4e5f6
    
    # Example 3: Observation that's meaningful
    obs_id = UnifiedMemoryID.from_observation(
        obs_type="new_file",
        target="/grid/plaza/question-about-memory.md",
        description="New question posted about memory systems"
    )
    print(f"Observation ID: {obs_id}")
    # Output: observation:transient:new-file/grid-plaza-question-about-memory:b8c3d1
    
    # Example 4: Pattern matching for agent queries
    all_notes = "file:personal:notes/*"
    alice_messages = "message:inbox:from-alice/*"
    
    # Check if IDs match patterns
    print(f"\nPattern matching:")
    print(f"Is {note_id} a personal note? {note_id.matches_pattern('file:personal:*')}")
    print(f"Is {message_id} from Alice? {message_id.matches_pattern(alice_messages)}")
    
    # Example 5: Translation for backward compatibility
    translator = MemoryIDTranslator(home_dir)
    
    old_ids = [
        "/home/agent/memory/notes.txt",
        "msg:/home/agent/inbox/message-123.json",
        "knowledge:cognitive:ooda-loop",
        "/grid/plaza/question.md:10-20"
    ]
    
    print(f"\nID Translation:")
    for old_id in old_ids:
        new_id = translator.translate_to_unified(old_id)
        back_to_old = translator.translate_from_unified(new_id)
        print(f"Old: {old_id}")
        print(f"New: {new_id}")
        print(f"Back: {back_to_old}")
        print()


if __name__ == "__main__":
    demonstrate_unified_ids()