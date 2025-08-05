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

from ..memory.memory_types import Priority, MemoryType
from ..memory.memory_blocks import (
    MemoryBlock,
    FileMemoryBlock, MessageMemoryBlock, ObservationMemoryBlock,
    KnowledgeMemoryBlock, StatusMemoryBlock
)
from ..memory.unified_memory_id import UnifiedMemoryID

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
    
    def __init__(self, home_path: Path, grid_path: Path):
        """Initialize scanner.
        
        Args:
            home_path: Agent's home directory
            grid_path: Grid directory containing shared spaces
        """
        self.home_path = Path(home_path)
        self.grid_path = Path(grid_path)
        
        # Directories to monitor
        self.inbox_path = self.home_path / "inbox"
        self.memory_path = self.home_path / "memory"
        self.plaza_path = self.grid_path / "plaza"
        self.library_path = self.grid_path / "library"
        self.bulletin_path = self.grid_path / "bulletin"
        self.workshop_path = self.grid_path / "workshop"
        
        # Track file states for change detection
        self.file_states: Dict[str, FileState] = {}
        
        # Track processed messages to avoid duplicates
        self.processed_messages: Set[str] = set()
        
        # Track observation IDs to prevent duplicates
        self.seen_observation_ids: Set[str] = set()
        
        # Last scan time
        self.last_scan = datetime.now()
        
        # Initialize baseline to prevent startup flood
        self._initialize_baseline()
    
    def _initialize_baseline(self):
        """Initialize file state tracking for all existing files to prevent startup flood.
        
        This establishes a baseline of existing files so only actual changes
        after agent startup are reported as observations.
        """
        logger.debug("Initializing environment baseline...")
        
        paths_to_baseline = []
        
        # Add grid paths that we monitor
        if self.library_path and self.library_path.exists():
            paths_to_baseline.append(self.library_path)
        if self.plaza_path and self.plaza_path.exists():
            paths_to_baseline.append(self.plaza_path)
        if self.bulletin_path and self.bulletin_path.exists():
            paths_to_baseline.append(self.bulletin_path)
        if self.workshop_path and self.workshop_path.exists():
            paths_to_baseline.append(self.workshop_path)
        
        # Scan all these paths and record their current state
        baseline_count = 0
        for base_path in paths_to_baseline:
            try:
                # Recursively get all files in this directory
                for file_path in base_path.rglob("*"):
                    if file_path.is_file() and not file_path.name.startswith('.'):
                        try:
                            # Record current state without creating observations
                            current_state = FileState(file_path)
                            self.file_states[str(file_path)] = current_state
                            baseline_count += 1
                        except Exception as e:
                            logger.debug(f"Skipping file {file_path} in baseline: {e}")
            except Exception as e:
                logger.warning(f"Error initializing baseline for {base_path}: {e}")
        
        logger.debug(f"Initialized baseline with {baseline_count} files")
    
    def scan_environment(self, full_scan: bool = False) -> List[MemoryBlock]:
        """Scan environment and return new observations as memory blocks.
        
        Args:
            full_scan: If True, ignore baseline and scan everything as new.
                      If False, only report actual changes since baseline.
            
        Returns:
            List of memory blocks for observations
        """
        if full_scan:
            # Clear baseline to treat everything as new
            old_baseline = self.file_states.copy()
            self.file_states.clear()
            self.seen_observation_ids.clear()
            
            memories = self._do_scan()
            
            # Restore baseline for future scans
            self.file_states = old_baseline
            return memories
        else:
            return self._do_scan()
    
    def _do_scan(self) -> List[MemoryBlock]:
        """Perform the actual environment scan."""
        memories = []
        scan_start = datetime.now()
        
        # Scan different areas
        memories.extend(self._scan_inbox())
        memories.extend(self._scan_grid_areas())
        memories.extend(self._scan_memory_dir())
        memories.extend(self._scan_workshop())
        
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
                    
                    # Create observation with deduplication
                    obs_memory = self._create_observation(
                        "message_arrived",
                        str(msg_file),
                        Priority.HIGH
                    )
                    if obs_memory:
                        memories.append(obs_memory)
                    
                    self.processed_messages.add(str(msg_file))
                    
                except Exception as e:
                    logger.error(f"Error reading message {msg_file}: {e}")
        
        except Exception as e:
            logger.error(f"Error scanning inbox: {e}")
        
        return memories
    
    def _scan_grid_areas(self) -> List[MemoryBlock]:
        """Scan grid areas for updates."""
        memories = []
        
        # Scan plaza (community discussions)
        if self.plaza_path and self.plaza_path.exists():
            memories.extend(self._scan_directory(
                self.plaza_path,
                "plaza_discussion",
                "Plaza discussion"
            ))
        
        # Scan library (shared knowledge) - only YAML files
        if self.library_path and self.library_path.exists():
            for pattern in ["*.yaml", "*.yml"]:
                for knowledge_file in self.library_path.rglob(pattern):
                    state = self._check_file_state(knowledge_file)
                    if state:  # New or changed
                        # Extract topic from path
                        rel_path = knowledge_file.relative_to(self.library_path)
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
                        
                        obs_memory = self._create_observation(
                            "library_updated",
                            str(knowledge_file),
                            Priority.MEDIUM
                        )
                        if obs_memory:
                            memories.append(obs_memory)
        
        # Scan bulletin (announcements)
        if self.bulletin_path and self.bulletin_path.exists():
            memories.extend(self._scan_directory(
                self.bulletin_path,
                "announcement",
                "Bulletin announcement"
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
                        obs_memory = self._create_observation(
                            obs_type,
                            str(file_path),
                            Priority.HIGH if obs_type == "plaza_bulletin" else Priority.MEDIUM
                        )
                        if obs_memory:
                            memories.append(obs_memory)
                        
                        # Also create file memory for important files
                        # Skip .md files to avoid JSON parsing errors
                        if file_path.suffix in ['.txt', '.json', '.yaml', '.yml']:
                            memories.append(FileMemoryBlock(
                                location=str(file_path),
                                priority=Priority.MEDIUM,
                                confidence=0.8
                            ))
        
        except Exception as e:
            logger.error(f"Error scanning {directory}: {e}")
        
        return memories
    
    def _scan_memory_dir(self) -> List[MemoryBlock]:
        """Scan agent's memory directory for important files only."""
        memories = []
        
        if not self.memory_path.exists():
            return memories
        
        try:
            # Only observe the journal file - it's user-visible content
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
            
            # Skip all JSON memory files (memory_snapshot.json, etc)
            # These are internal state and observing them creates noise
        
        except Exception as e:
            logger.error(f"Error scanning memory directory: {e}")
        
        return memories
    
    def _scan_workshop(self) -> List[MemoryBlock]:
        """Scan workshop for available tools."""
        memories = []
        
        if not self.workshop_path or not self.workshop_path.exists():
            return memories
        
        try:
            # Look for executable scripts
            for tool_file in self.workshop_path.iterdir():
                if tool_file.is_file() and os.access(tool_file, os.X_OK):
                    state = self._check_file_state(tool_file)
                    if state:  # New tool
                        obs_memory = self._create_observation(
                            "tool_available",
                            str(tool_file),
                            Priority.LOW
                        )
                        if obs_memory:
                            memories.append(obs_memory)
        
        except Exception as e:
            logger.error(f"Error scanning workshop: {e}")
        
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
    
    def _create_observation(self, obs_type: str, path: str, priority: Priority) -> Optional[ObservationMemoryBlock]:
        """Create an observation with deduplication.
        
        Returns None if this exact observation has been seen before.
        """
        # Create the observation memory block
        obs_memory = ObservationMemoryBlock(
            observation_type=obs_type,
            path=path,
            priority=priority
        )
        
        # Check if we've seen this exact observation before
        if obs_memory.id in self.seen_observation_ids:
            logger.debug(f"Skipping duplicate observation: {obs_memory.id}")
            return None
        
        # Track this observation
        self.seen_observation_ids.add(obs_memory.id)
        return obs_memory
    
    def reset_tracking(self):
        """Reset all tracking state (for testing or fresh start)."""
        self.file_states.clear()
        self.processed_messages.clear()
        self.seen_observation_ids.clear()
        self.last_scan = datetime.now()