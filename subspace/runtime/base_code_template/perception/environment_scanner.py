"""Environment scanner for filesystem perception.

Scans the agent's filesystem environment and creates memory blocks
for relevant changes and observations.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
import logging

from ..memory.memory_blocks import (
    MemoryBlock, Priority, MemoryType,
    FileMemoryBlock, MessageMemoryBlock, ObservationMemoryBlock,
    KnowledgeMemoryBlock, StatusMemoryBlock
)

logger = logging.getLogger("agent.perception")


class FileState:
    """Tracks state of a file for change detection."""
    
    def __init__(self, path: Path):
        self.path = path
        self.last_modified = path.stat().st_mtime if path.exists() else 0
        self.size = path.stat().st_size if path.exists() else 0
        self.digest = self._compute_digest() if path.exists() else ""
    
    def _compute_digest(self) -> str:
        """Compute quick digest for change detection."""
        try:
            # For large files, just hash first/last 1KB
            if self.size > 10000:
                with open(self.path, 'rb') as f:
                    start = f.read(1024)
                    f.seek(-1024, 2)  # 1KB from end
                    end = f.read(1024)
                    content = start + end
            else:
                with open(self.path, 'rb') as f:
                    content = f.read()
            
            return hashlib.md5(content).hexdigest()[:8]
        except Exception:
            return ""
    
    def has_changed(self, other: 'FileState') -> bool:
        """Check if file has changed compared to another state."""
        return (self.last_modified != other.last_modified or 
                self.size != other.size or
                self.digest != other.digest)


class EnvironmentScanner:
    """Scans filesystem environment and creates memory blocks."""
    
    def __init__(self, home_path: Path, shared_path: Path, tools_path: Optional[Path] = None):
        """Initialize scanner.
        
        Args:
            home_path: Agent's home directory
            shared_path: Shared memory directory
            tools_path: Optional tools directory
        """
        self.home_path = Path(home_path)
        self.shared_path = Path(shared_path)
        self.tools_path = Path(tools_path) if tools_path else None
        
        # Directories to monitor
        self.inbox_path = self.home_path / "inbox"
        self.memory_path = self.home_path / "memory"
        self.plaza_path = self.shared_path / "plaza"
        self.questions_path = self.shared_path / "questions"
        self.knowledge_path = self.shared_path / "knowledge"
        
        # Track file states for change detection
        self.file_states: Dict[str, FileState] = {}
        
        # Track processed messages to avoid duplicates
        self.processed_messages: Set[str] = set()
        
        # Last scan time
        self.last_scan = datetime.now()
    
    def scan_environment(self, full_scan: bool = False) -> List[MemoryBlock]:
        """Scan environment and return new observations as memory blocks.
        
        Args:
            full_scan: If True, scan everything. If False, only changes.
            
        Returns:
            List of memory blocks for observations
        """
        memories = []
        scan_start = datetime.now()
        
        # Scan different areas
        memories.extend(self._scan_inbox())
        memories.extend(self._scan_shared_areas())
        memories.extend(self._scan_memory_dir())
        
        if self.tools_path:
            memories.extend(self._scan_tools())
        
        # Add status memories
        memories.extend(self._create_status_memories())
        
        self.last_scan = scan_start
        
        # Log summary of what was found
        if memories:
            message_count = len([m for m in memories if isinstance(m, MessageMemoryBlock)])
            file_count = len([m for m in memories if isinstance(m, FileMemoryBlock)])
            obs_count = len([m for m in memories if isinstance(m, ObservationMemoryBlock)])
            logger.debug(f"Scan details: {message_count} messages, {file_count} files, {obs_count} observations")
        
        logger.debug(f"Environment scan found {len(memories)} observations")
        
        return memories
    
    def _scan_inbox(self) -> List[MemoryBlock]:
        """Scan inbox for new messages."""
        memories = []
        
        if not self.inbox_path.exists():
            return memories
        
        try:
            # Look for message files
            for msg_file in self.inbox_path.glob("*.msg"):
                if str(msg_file) in self.processed_messages:
                    continue
                
                try:
                    # Read message
                    msg_data = json.loads(msg_file.read_text())
                    
                    # Create message memory
                    message_memory = MessageMemoryBlock(
                        from_agent=msg_data.get("from", "unknown"),
                        to_agent=msg_data.get("to", "me"),
                        subject=msg_data.get("subject", "No subject"),
                        preview=msg_data.get("content", "")[:100] + "...",
                        full_path=str(msg_file),
                        read=False,
                        priority=Priority.HIGH,
                        confidence=1.0
                    )
                    memories.append(message_memory)
                    
                    # Create observation
                    obs_memory = ObservationMemoryBlock(
                        observation_type="message_arrived",
                        path=str(msg_file),
                        description=f"New message from {msg_data.get('from', 'unknown')}: {msg_data.get('subject', 'No subject')}",
                        priority=Priority.HIGH
                    )
                    memories.append(obs_memory)
                    
                    self.processed_messages.add(str(msg_file))
                    
                except Exception as e:
                    logger.error(f"Error reading message {msg_file}: {e}")
        
        except Exception as e:
            logger.error(f"Error scanning inbox: {e}")
        
        return memories
    
    def _scan_shared_areas(self) -> List[MemoryBlock]:
        """Scan shared areas for updates."""
        memories = []
        
        # Scan plaza bulletin board
        if self.plaza_path and self.plaza_path.exists():
            memories.extend(self._scan_directory(
                self.plaza_path,
                "plaza_bulletin",
                "Plaza bulletin board"
            ))
        
        # Scan questions board
        if self.questions_path and self.questions_path.exists():
            memories.extend(self._scan_directory(
                self.questions_path,
                "shared_question",
                "Shared questions"
            ))
        
        # Scan knowledge base
        if self.knowledge_path and self.knowledge_path.exists():
            for knowledge_file in self.knowledge_path.rglob("*.md"):
                state = self._check_file_state(knowledge_file)
                if state:  # New or changed
                    # Extract topic from path
                    rel_path = knowledge_file.relative_to(self.knowledge_path)
                    topic = rel_path.parts[0] if rel_path.parts else "general"
                    subtopic = rel_path.stem if len(rel_path.parts) > 1 else None
                    
                    knowledge_memory = KnowledgeMemoryBlock(
                        topic=topic,
                        subtopic=subtopic,
                        location=str(knowledge_file),
                        relevance_score=0.7,  # Default relevance
                        priority=Priority.MEDIUM
                    )
                    memories.append(knowledge_memory)
                    
                    memories.append(ObservationMemoryBlock(
                        observation_type="knowledge_updated",
                        path=str(knowledge_file),
                        description=f"Knowledge base updated: {topic}" + (f"/{subtopic}" if subtopic else ""),
                        priority=Priority.MEDIUM
                    ))
        
        return memories
    
    def _scan_directory(self, directory: Path, obs_type: str, description: str) -> List[MemoryBlock]:
        """Scan a directory for new or changed files."""
        memories = []
        
        try:
            for file_path in directory.iterdir():
                if file_path.is_file() and not file_path.name.startswith('.'):
                    state = self._check_file_state(file_path)
                    if state:  # New or changed
                        memories.append(ObservationMemoryBlock(
                            observation_type=obs_type,
                            path=str(file_path),
                            description=f"{description}: {file_path.name}",
                            priority=Priority.HIGH if obs_type == "plaza_bulletin" else Priority.MEDIUM
                        ))
                        
                        # Also create file memory for important files
                        if file_path.suffix in ['.md', '.txt', '.json']:
                            memories.append(FileMemoryBlock(
                                location=str(file_path),
                                priority=Priority.MEDIUM,
                                confidence=0.8
                            ))
        
        except Exception as e:
            logger.error(f"Error scanning {directory}: {e}")
        
        return memories
    
    def _scan_memory_dir(self) -> List[MemoryBlock]:
        """Scan agent's memory directory."""
        memories = []
        
        if not self.memory_path.exists():
            return memories
        
        try:
            # Look for specific memory files
            journal_file = self.memory_path / "journal.md"
            if journal_file.exists():
                state = self._check_file_state(journal_file)
                if state:
                    memories.append(FileMemoryBlock(
                        location=str(journal_file),
                        priority=Priority.HIGH,
                        confidence=1.0,
                        metadata={"type": "journal"}
                    ))
            
            # Check for other memory files
            for mem_file in self.memory_path.glob("*.json"):
                state = self._check_file_state(mem_file)
                if state:
                    memories.append(ObservationMemoryBlock(
                        observation_type="memory_updated",
                        path=str(mem_file),
                        description=f"Memory file updated: {mem_file.name}",
                        priority=Priority.LOW
                    ))
        
        except Exception as e:
            logger.error(f"Error scanning memory directory: {e}")
        
        return memories
    
    def _scan_tools(self) -> List[MemoryBlock]:
        """Scan tools directory for available tools."""
        memories = []
        
        if not self.tools_path or not self.tools_path.exists():
            return memories
        
        try:
            # Look for executable scripts
            for tool_file in self.tools_path.iterdir():
                if tool_file.is_file() and os.access(tool_file, os.X_OK):
                    state = self._check_file_state(tool_file)
                    if state:  # New tool
                        memories.append(ObservationMemoryBlock(
                            observation_type="tool_available",
                            path=str(tool_file),
                            description=f"Tool available: {tool_file.name}",
                            priority=Priority.LOW
                        ))
        
        except Exception as e:
            logger.error(f"Error scanning tools: {e}")
        
        return memories
    
    def _check_file_state(self, file_path: Path) -> Optional[FileState]:
        """Check if file is new or changed, update tracking."""
        try:
            current_state = FileState(file_path)
            path_str = str(file_path)
            
            # Check if we've seen this file before
            if path_str in self.file_states:
                old_state = self.file_states[path_str]
                if current_state.has_changed(old_state):
                    self.file_states[path_str] = current_state
                    return current_state  # Changed
                else:
                    return None  # No change
            else:
                # New file
                self.file_states[path_str] = current_state
                return current_state
        
        except Exception as e:
            logger.error(f"Error checking file state for {file_path}: {e}")
            return None
    
    def _create_status_memories(self) -> List[MemoryBlock]:
        """Create status memories about current environment state."""
        memories = []
        
        # Inbox status
        try:
            unread_count = len([f for f in self.inbox_path.glob("*.msg") 
                               if str(f) not in self.processed_messages])
            if unread_count > 0:
                memories.append(StatusMemoryBlock(
                    status_type="mailbox",
                    value={"unread_messages": unread_count},
                    priority=Priority.HIGH
                ))
        except Exception:
            pass
        
        # Scan timing status
        memories.append(StatusMemoryBlock(
            status_type="last_scan",
            value={
                "timestamp": self.last_scan.isoformat(),
                "seconds_ago": (datetime.now() - self.last_scan).total_seconds()
            },
            priority=Priority.LOW
        ))
        
        return memories
    
    def mark_message_processed(self, message_path: str):
        """Mark a message as processed."""
        self.processed_messages.add(message_path)
    
    def reset_tracking(self):
        """Reset all tracking state (for testing or fresh start)."""
        self.file_states.clear()
        self.processed_messages.clear()
        self.last_scan = datetime.now()