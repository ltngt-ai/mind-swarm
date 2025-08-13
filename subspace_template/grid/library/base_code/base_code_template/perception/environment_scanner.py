"""Environment scanner for filesystem perception.

Scans the Cyber's filesystem environment and creates memory blocks
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
    FileMemoryBlock, ObservationMemoryBlock,
    StatusMemoryBlock
)
from ..memory.unified_memory_id import UnifiedMemoryID

logger = logging.getLogger("Cyber.perception")


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
    
    def __init__(self, personal_path: Path, grid_path: Path):
        """Initialize scanner.
        
        Args:
            personal_path: Cyber's personal directory
            grid_path: Grid directory containing shared spaces
        """
        self.personal_path = Path(personal_path)
        self.grid_path = Path(grid_path)
        
        # Directories to monitor
        self.inbox_path = self.personal_path / "comms" / "inbox"
        self.memory_path = self.personal_path / ".internal" / "memory"
        self.community_path = self.grid_path / "community"
        self.library_path = self.grid_path / "library"
        self.bulletin_path = self.grid_path / "bulletin"
        self.workshop_path = self.grid_path / "workshop"
        
        # Track file states for change detection
        self.file_states: Dict[str, FileState] = {}
        
        # Track processed messages to avoid duplicates
        self.processed_messages: Set[str] = set()
        
        # Track observation IDs to prevent duplicates
        self.seen_observation_ids: Set[str] = set()
        
        # Track current location contents
        self.current_location_contents: Optional[Dict[str, Any]] = None
        self.last_location_scanned: Optional[str] = None
        
        # Last scan time
        self.last_scan = datetime.now()
        
        # Initialize baseline to prevent startup flood
        self._initialize_baseline()
    
    def _initialize_baseline(self):
        """Initialize file state tracking for all existing files to prevent startup flood.
        
        This establishes a baseline of existing files so only actual changes
        after Cyber startup are reported as observations.
        """
        logger.debug("Initializing environment baseline...")
        
        paths_to_baseline = []
        
        # Add grid paths that we monitor
        if self.library_path and self.library_path.exists():
            paths_to_baseline.append(self.library_path)
        if self.community_path and self.community_path.exists():
            paths_to_baseline.append(self.community_path)
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
    
    def scan_environment(self, full_scan: bool = False, cycle_count: int = 0) -> List[MemoryBlock]:
        """Scan environment and return new observations as memory blocks.
        
        Args:
            full_scan: If True, ignore baseline and scan everything as new.
                      If False, only report actual changes since baseline.
            cycle_count: Current cycle count for observations
            
        Returns:
            List of memory blocks for observations
        """
        if full_scan:
            # Clear baseline to treat everything as new
            old_baseline = self.file_states.copy()
            self.file_states.clear()
            self.seen_observation_ids.clear()
            
            memories = self._do_scan(cycle_count)
            
            # Restore baseline for future scans
            self.file_states = old_baseline
            return memories
        else:
            return self._do_scan(cycle_count)
    
    def _do_scan(self, cycle_count: int = 0) -> List[MemoryBlock]:
        """Perform the actual environment scan.
        
        Args:
            cycle_count: Current cycle count for observations
        """
        memories = []
        scan_start = datetime.now()
        
        # Always scan current location first (like looking around the room)
        memories.extend(self._scan_current_location(cycle_count))
        
        # Scan different areas
        memories.extend(self._scan_inbox(cycle_count))
        memories.extend(self._scan_grid_areas(cycle_count))
        memories.extend(self._scan_memory_dir(cycle_count))
        memories.extend(self._scan_workshop(cycle_count))
        
        # Add status memories
        memories.extend(self._create_status_memories())
        
        self.last_scan = scan_start
        
        # Log summary of what was found
        if memories:
            # Count message files by checking metadata
            message_count = len([m for m in memories if isinstance(m, FileMemoryBlock) and m.metadata.get('file_type') == 'message'])
            file_count = len([m for m in memories if isinstance(m, FileMemoryBlock)])
            obs_count = len([m for m in memories if isinstance(m, ObservationMemoryBlock)])
            logger.debug(f"Scan details: {message_count} messages, {file_count} files, {obs_count} observations")
        
        logger.debug(f"Environment scan found {len(memories)} observations")
        
        return memories
    
    def _scan_current_location(self, cycle_count: int = 0) -> List[MemoryBlock]:
        """Scan current location and create a system memory with its contents.
        
        This is like a Cyber looking around the room - automatically providing
        awareness of what's in their current location.
        
        Args:
            cycle_count: Current cycle count for observations
        """
        memories = []
        
        try:
            # Get current location from dynamic context
            # Note: Scanner doesn't have access to cognitive_loop's memory map,
            # so we read the file directly, handling the null-padded format
            current_location = None
            dynamic_context_file = self.personal_path / ".internal" / "memory" / "dynamic_context.json"
            
            if dynamic_context_file.exists():
                try:
                    # Read as standard JSON file
                    with open(dynamic_context_file, 'r') as f:
                        dynamic_context = json.load(f)
                        current_location = dynamic_context.get("current_location")
                except Exception as e:
                    logger.debug(f"Error reading dynamic context: {e}")
                    return memories  # Can't scan without location
            
            # If we still don't have a location, can't continue
            if not current_location:
                logger.debug("No current location available, skipping location scan")
                return memories
            
            # Map virtual location to actual path
            if current_location.startswith('/personal'):
                rel_path = current_location[len('/personal'):]
                actual_path = self.personal_path / rel_path.lstrip('/') if rel_path else self.personal_path
            elif current_location.startswith('/grid'):
                rel_path = current_location[len('/grid'):]
                actual_path = self.grid_path / rel_path.lstrip('/') if rel_path else self.grid_path
            else:
                # Invalid location, skip
                return memories
            
            # Only scan if location exists and is a directory
            if not actual_path.exists() or not actual_path.is_dir():
                return memories
            
            # Check if we need to rescan this location
            if self.last_location_scanned == current_location:
                # Location hasn't changed, check if contents changed
                needs_rescan = False
                for item in actual_path.iterdir():
                    item_str = str(item)
                    if item_str not in self.file_states:
                        needs_rescan = True
                        break
                    current_state = FileState(item)
                    if current_state.has_changed(self.file_states[item_str]):
                        needs_rescan = True
                        break
                
                if not needs_rescan:
                    # No changes, return existing memory
                    return memories
            
            # Collect directories and files for tree display
            directories = []
            files = []
            
            for item in sorted(actual_path.iterdir()):
                # Skip ALL hidden files/dirs and certain system directories completely
                if item.name.startswith('.') or item.name in ['__pycache__', '.git']:
                    continue
                
                # Update file state tracking
                item_str = str(item)
                self.file_states[item_str] = FileState(item)
                
                if item.is_dir():
                    directories.append((item.name, '📁'))
                else:
                    files.append((item.name, '📄'))
            
            # Build tree-style text representation
            lines = []
            lines.append(f"| {current_location} (📁=memory group, 📄=memory)")
            
            # Add directories first
            for name, icon in directories:
                lines.append(f"|---- {icon} {name}")
            
            # Then files
            for name, icon in files:
                lines.append(f"|---- {icon} {name}")
            
            # If empty, add a note
            if not directories and not files:
                lines.append("|---- (empty)")
            
            contents_text = "\n".join(lines)
            total_items = len(directories) + len(files)
            
            # Create location contents file as plain text  
            location_contents_file = self.personal_path / ".internal" / "memory" / "current_location.txt"
            location_contents_file.parent.mkdir(parents=True, exist_ok=True)
            with open(location_contents_file, 'w') as f:
                f.write(contents_text)
            
            # Create a SYSTEM priority memory for location contents
            location_memory = FileMemoryBlock(
                location=str(location_contents_file.relative_to(self.personal_path.parent)),
                priority=Priority.SYSTEM,  # System-controlled, like looking around
                confidence=1.0,
                pinned=True,  # Always visible
                metadata={
                    "file_type": "current_location",
                    "description": f"Looking around at: {current_location}",
                    "location": current_location,
                    "item_count": total_items
                },
                cycle_count=cycle_count,
                no_cache=True,  # Always fresh
                block_type=MemoryType.SYSTEM
            )
            memories.append(location_memory)
            
            # Update tracking
            self.last_location_scanned = current_location
            self.current_location_contents = contents_text
            
            logger.debug(f"Scanned location {current_location}: {total_items} items")
            
        except Exception as e:
            logger.error(f"Error scanning current location: {e}")
        
        return memories
    
    def _scan_inbox(self, cycle_count: int = 0) -> List[MemoryBlock]:
        """Scan inbox for new messages.
        
        Args:
            cycle_count: Current cycle count for observations
        """
        memories = []
        
        if not self.inbox_path.exists():
            return memories
        
        try:
            # Look for message files
            for msg_file in self.inbox_path.glob("*.msg"):
                if str(msg_file) in self.processed_messages:
                    continue
                
                try:
                    # Read message header for metadata
                    msg_data = json.loads(msg_file.read_text())
                    
                    # Create file memory for the message file
                    file_memory = FileMemoryBlock(
                        location=str(msg_file),
                        priority=Priority.HIGH,
                        confidence=1.0,
                        metadata={
                            "file_type": "message",
                            "from_agent": msg_data.get("from", "unknown"),
                            "to_agent": msg_data.get("to", "me"),
                            "subject": msg_data.get("subject", "No subject")
                        },
                        cycle_count=cycle_count  # When this file was discovered
                    )
                    memories.append(file_memory)
                    
                    # Create observation pointing to the message file
                    obs_memory = ObservationMemoryBlock(
                        observation_type="new_message",
                        path=str(msg_file),  # Direct path to the file
                        message=f"New message from {msg_data.get('from', 'unknown')}: {msg_data.get('subject', 'No subject')}",
                        cycle_count=cycle_count,
                        priority=Priority.HIGH
                    )
                    memories.append(obs_memory)
                    
                    self.processed_messages.add(str(msg_file))
                    
                except Exception as e:
                    logger.error(f"Error reading message {msg_file}: {e}")
        
        except Exception as e:
            logger.error(f"Error scanning inbox: {e}")
        
        return memories
    
    def _scan_grid_areas(self, cycle_count: int = 0) -> List[MemoryBlock]:
        """Scan grid areas for updates.
        
        Args:
            cycle_count: Current cycle count for observations
        """
        memories = []
        
        # Scan community (discussions)
        if self.community_path and self.community_path.exists():
            memories.extend(self._scan_directory(
                self.community_path,
                "community_discussion",
                "Community discussion",
                cycle_count
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
                        
                        knowledge_memory = FileMemoryBlock(
                            location=str(knowledge_file),
                            priority=Priority.MEDIUM,
                            confidence=0.7,  # Default relevance
                            block_type=MemoryType.KNOWLEDGE
                        )
                        memories.append(knowledge_memory)
                        
                        obs_memory = self._create_observation(
                            "library_updated",
                            str(knowledge_file),
                            Priority.MEDIUM,
                            cycle_count
                        )
                        if obs_memory:
                            memories.append(obs_memory)
        
        # Scan bulletin (announcements)
        if self.bulletin_path and self.bulletin_path.exists():
            memories.extend(self._scan_directory(
                self.bulletin_path,
                "announcement",
                "Bulletin announcement",
                cycle_count
            ))
        
        return memories
    
    def _scan_directory(self, directory: Path, obs_type: str, description: str, cycle_count: int = 0) -> List[MemoryBlock]:
        """Scan a directory for new or changed files.
        
        Args:
            directory: Directory to scan
            obs_type: Type of observation
            description: Description of the observation
            cycle_count: Current cycle count for observations
        """
        memories = []
        
        try:
            for file_path in directory.iterdir():
                if file_path.is_file() and not file_path.name.startswith('.'):
                    state = self._check_file_state(file_path)
                    if state:  # New or changed
                        obs_memory = self._create_observation(
                            obs_type,
                            str(file_path),
                            Priority.HIGH if obs_type == "plaza_bulletin" else Priority.MEDIUM,
                            cycle_count
                        )
                        if obs_memory:
                            memories.append(obs_memory)
                        
                        # Also create file memory for important files
                        # Skip .md files to avoid JSON parsing errors
                        if file_path.suffix in ['.txt', '.json', '.yaml', '.yml']:
                            memories.append(FileMemoryBlock(
                                location=str(file_path),
                                priority=Priority.MEDIUM,
                                confidence=0.8,
                                cycle_count=cycle_count  # When this file was discovered
                            ))
        
        except Exception as e:
            logger.error(f"Error scanning {directory}: {e}")
        
        return memories
    
    def _scan_memory_dir(self, cycle_count: int = 0) -> List[MemoryBlock]:
        """Scan Cyber's memory directory for important files only.
        
        Args:
            cycle_count: Current cycle count for observations
        """
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
                        metadata={"type": "journal"},
                        cycle_count=cycle_count  # When journal was updated
                    ))
                    
                    # Also create an observation for the journal update
                    obs_memory = self._create_observation(
                        "journal_updated",
                        str(journal_file),
                        Priority.MEDIUM,
                        cycle_count
                    )
                    if obs_memory:
                        memories.append(obs_memory)
            
            # Skip all JSON memory files (memory_snapshot.json, etc)
            # These are internal state and observing them creates noise
        
        except Exception as e:
            logger.error(f"Error scanning memory directory: {e}")
        
        return memories
    
    def _scan_workshop(self, cycle_count: int = 0) -> List[MemoryBlock]:
        """Scan workshop for available tools.
        
        Args:
            cycle_count: Current cycle count for observations
        """
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
                            Priority.LOW,
                            cycle_count
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
        
        # Removed last_scan status as it's not useful for decision-making
        # The cyber doesn't need to know when the last scan was done
        
        return memories
    
    def mark_message_processed(self, message_path: str):
        """Mark a message as processed."""
        self.processed_messages.add(message_path)
    
    def _create_observation(self, obs_type: str, path: str, priority: Priority, cycle_count: int = 0) -> Optional[ObservationMemoryBlock]:
        """Create an observation with deduplication.
        
        Returns None if this exact observation has been seen before.
        """
        # Create descriptive message based on observation type
        file_name = Path(path).name
        if obs_type == "file_change":
            message = f"File changed: {file_name}"
        elif obs_type == "new_file":
            message = f"New file created: {file_name}"
        elif obs_type == "file_deleted":
            message = f"File deleted: {file_name}"
        else:
            message = f"{obs_type}: {file_name}"
        
        # Create the observation memory block
        obs_memory = ObservationMemoryBlock(
            observation_type=obs_type,
            path=path,
            message=message,
            cycle_count=cycle_count,
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