"""Environment scanner for filesystem perception.

Scans the Cyber's filesystem environment and creates memory blocks
for relevant changes and observations.
"""

import json
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime
import logging

from ..memory.memory_types import Priority, ContentType
from ..memory.memory_blocks import (
    MemoryBlock,
    FileMemoryBlock, ObservationMemoryBlock
)

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
        self.inbox_path = self.personal_path / "inbox"
        self.memory_path = self.personal_path / ".internal" / "memory"
        self.community_path = self.grid_path / "community"
        self.library_path = self.grid_path / "library"
        self.announcements_path = self.grid_path / "community" / "announcements"
        self.workshop_path = self.grid_path / "workshop"
        
        # Track file states for change detection
        self.file_states: Dict[str, FileState] = {}
        
        # Track processed messages to avoid duplicates
        self.processed_messages: Set[str] = set()
        
        # Track observation IDs to prevent duplicates
        self.seen_observation_ids: Set[str] = set()
        
        # Track current location contents
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
        if self.announcements_path and self.announcements_path.exists():
            paths_to_baseline.append(self.announcements_path)
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
    
    def scan_environment(self, full_scan: bool = False, cycle_count: int = 0):
        """Scan environment and adds new observations as memory blocks.
        Args:
            full_scan: If True, ignore baseline and scan everything as new.
                      If False, only report actual changes since baseline.
            cycle_count: Current cycle count for observations
            
        """
        if full_scan:
            # Clear baseline to treat everything as new
            old_baseline = self.file_states.copy()
            self.file_states.clear()
            self.seen_observation_ids.clear()
            
            self._do_scan(cycle_count)
            
            # Restore baseline for future scans
            self.file_states = old_baseline
        else:
            self._do_scan(cycle_count)

    def _do_scan(self, cycle_count: int = 0):
        """Perform the actual environment scan.
        
        Args:
            cycle_count: Current cycle count for observations
        """
        memories = []
        scan_start = datetime.now()
        
        # Always scan current location first (like looking around the room)
        memories.extend(self._scan_current_location(cycle_count))
        
        # Also scan personal directory structure (like knowing your home)
        memories.extend(self._scan_personal_location(cycle_count))
        
        # Scan different areas
        memories.extend(self._scan_inbox(cycle_count))
        memories.extend(self._scan_announcements(cycle_count))
        
        self.last_scan = scan_start
        
        # Log summary of what was found
        if memories:
            # Count message files by checking metadata
            message_count = len([m for m in memories if isinstance(m, FileMemoryBlock) and m.metadata.get('file_type') == 'message'])
            file_count = len([m for m in memories if isinstance(m, FileMemoryBlock)])
            obs_count = len([m for m in memories if isinstance(m, ObservationMemoryBlock)])
            logger.debug(f"Scan details: {message_count} messages, {file_count} files, {obs_count} observations")
        
        logger.debug(f"Environment scan found {len(memories)} observations")
            
    def _scan_personal_location(self, cycle_count: int = 0) -> List[MemoryBlock]:
        """Scan personal directory and create a system memory with its structure.
        
        This provides cybers with awareness of their personal space organization,
        excluding .internal directories which are system-only.
        
        Args:
            cycle_count: Current cycle count for observations
        """
        memories = []
        
        try:
            # Create personal location file showing directory structure
            personal_location_file = self.personal_path / ".internal" / "memory" / "personal_location.txt"
            
            # Collect directories and files for tree display, excluding .internal
            lines = []
            lines.append("| /personal (your home directory)")
            
            # Scan top-level personal directory
            directories = []
            files = []
            
            for item in sorted(self.personal_path.iterdir()):
                # Skip ALL hidden files/dirs especially .internal
                if item.name.startswith('.'):
                    continue
                
                if item.is_dir():
                    directories.append(item.name)
                else:
                    files.append(item.name)
            
            # Add directories first with their contents
            for dir_name in directories:
                lines.append(f"|---- 📁 {dir_name}/")
                
                # Show contents of important directories (goals, tasks)
                if dir_name in ['goals', 'tasks']:
                    dir_path = self.personal_path / dir_name
                    if dir_path.exists():
                        sub_items = []
                        try:
                            for sub_item in sorted(dir_path.iterdir()):
                                if not sub_item.name.startswith('.'):
                                    icon = '📁' if sub_item.is_dir() else '📄'
                                    sub_items.append(f"|       {icon} {sub_item.name}")
                        except:
                            pass
                        
                        if sub_items:
                            for sub_line in sub_items:
                                lines.append(sub_line)
                        else:
                            lines.append("|       (empty)")
            
            # Then files
            for file_name in files:
                lines.append(f"|---- 📄 {file_name}")
            
            # If nothing visible, add a note
            if not directories and not files:
                lines.append("|---- (no visible files or directories)")
            
            contents_text = "\n".join(lines)
            
            # Save to file
            personal_location_file.parent.mkdir(parents=True, exist_ok=True)
            with open(personal_location_file, 'w') as f:
                f.write(contents_text)

            # Create a memory for personal structure
            personal_memory = FileMemoryBlock(
                location=str(personal_location_file.relative_to(self.personal_path.parent)),
                priority=Priority.SYSTEM, 
                confidence=1.0,
                pinned=True,  # Always in working memory
                metadata={
                    "file_type": "personal_structure",
                    "description": "Your personal directory structure",
                    "tip": "Keep your personal structure clean and tidy"
                },
                cycle_count=cycle_count,
                no_cache=True,  # Always fresh
                content_type=ContentType.MINDSWARM_SYSTEM
            )
            memories.append(personal_memory)
            
            logger.debug(f"Created personal location memory with {len(directories)} dirs and {len(files)} files")
            
        except Exception as e:
            logger.error(f"Error scanning personal location: {e}")
        
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
                logger.warning(f"Invalid location format: {current_location}")
                return memories
            
            logger.info(f"Scanning location: {current_location} -> actual_path: {actual_path}")
            
            # Only scan if location exists and is a directory
            if not actual_path.exists():
                logger.warning(f"Location does not exist: {actual_path}")
                return memories
            if not actual_path.is_dir():
                logger.warning(f"Location is not a directory: {actual_path}")
                return memories
            
            # Check if current_location.txt exists
            location_contents_file = self.personal_path / ".internal" / "memory" / "current_location.txt"
            
            # Check if we need to rescan this location
            needs_rescan = False
            if self.last_location_scanned != current_location:
                # Location changed, definitely need to rescan
                needs_rescan = True
            elif not location_contents_file.exists():
                # File doesn't exist, need to create it
                needs_rescan = True
            else:
                # Location hasn't changed and file exists, check if contents changed
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
                # No changes and file exists, return the existing location memory
                location_memory = FileMemoryBlock(
                    location=str(location_contents_file),
                    confidence=1.0,
                    priority=Priority.FOUNDATIONAL,
                    pinned=True,  # Always visible
                    metadata={
                        "file_type": "current_location",
                        "description": f"Looking around at: {current_location}",
                        "location": current_location
                    },
                    cycle_count=cycle_count,
                    content_type=ContentType.MINDSWARM_SYSTEM
                )
                memories.append(location_memory)
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
                content_type=ContentType.MINDSWARM_SYSTEM
            )
            memories.append(location_memory)
            
            # Update tracking
            self.last_location_scanned = current_location
            
            logger.debug(f"Scanned location {current_location}: {total_items} items")
            
        except Exception as e:
            logger.error(f"Error scanning current location: {e}")
        
        return memories
    
    def _scan_announcements(self, cycle_count: int = 0) -> List[MemoryBlock]:
        """Scan community announcements for important updates.
        
        For JSON announcement files, we check the actual content to detect
        new announcements, not just file modification time.
        
        Args:
            cycle_count: Current cycle count for observations
        """
        memories = []
        
        if not self.announcements_path or not self.announcements_path.exists():
            return memories
        
        try:
            # Look for announcement files
            for ann_file in self.announcements_path.glob("*.json"):
                try:
                    # For JSON files, check actual announcement content
                    import json
                    with open(ann_file, 'r') as f:
                        data = json.load(f)
                    
                    # Track which announcements we've seen
                    current_announcements = set()
                    new_announcements = []
                    
                    if 'announcements' in data:
                        for ann in data['announcements']:
                            ann_id = ann.get('id', f"{ann.get('date', 'unknown')}_{ann.get('title', 'untitled')}")
                            current_announcements.add(ann_id)
                            
                            # Check if this announcement is new
                            tracking_key = f"announcement_{ann_file.name}_{ann_id}"
                            if tracking_key not in self.seen_observation_ids:
                                self.seen_observation_ids.add(tracking_key)
                                new_announcements.append(ann)
                    
                    # Create observation for new announcements
                    if new_announcements:
                        for ann in new_announcements:
                            message = f"📢 NEW ANNOUNCEMENT: {ann.get('title', 'System Update')}\n"
                            message += f"Priority: {ann.get('priority', 'NORMAL')}\n"
                            message += f"Message: {ann.get('message', 'Check announcement file for details')}"
                            
                            obs_memory = ObservationMemoryBlock(
                                observation_type="new_announcement",
                                path=str(ann_file),
                                message=message,
                                cycle_count=cycle_count,
                                priority=Priority.CRITICAL if ann.get('priority') == 'HIGH' else Priority.HIGH,
                                content=json.dumps(ann, indent=2)  # Include full announcement in content
                            )
                            memories.append(obs_memory)
                            
                            logger.info(f"Found new announcement: {ann.get('title', 'untitled')}")
                        
                        # Also add the announcement file itself to working memory
                        from ..memory.memory_blocks import FileMemoryBlock
                        ann_file_memory = FileMemoryBlock(
                            location=str(ann_file.relative_to(self.grid_path.parent.parent)),
                            priority=Priority.HIGH,
                            confidence=1.0,
                            metadata={
                                "file_type": "announcement",
                                "has_new": len(new_announcements) > 0,
                                "announcement_count": len(current_announcements)
                            },
                            cycle_count=cycle_count,
                            content_type=ContentType.APPLICATION_JSON
                        )
                        memories.append(ann_file_memory)
                    
                    # Also check file state for other changes
                    state = self._check_file_state(ann_file)
                    if state and not new_announcements:
                        # File changed but no new announcements - might be metadata update
                        obs_memory = ObservationMemoryBlock(
                            observation_type="announcement_file_update",
                            path=str(ann_file),
                            message=f"Announcement file {ann_file.name} was updated (metadata or format change)",
                            cycle_count=cycle_count,
                            priority=Priority.LOW
                        )
                        memories.append(obs_memory)
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON announcement file {ann_file}: {e}")
                    # Fall back to simple file change detection
                    state = self._check_file_state(ann_file)
                    if state:
                        obs_memory = ObservationMemoryBlock(
                            observation_type="announcement_update",
                            path=str(ann_file),
                            message=f"IMPORTANT: Announcements file {ann_file.name} changed but couldn't parse content",
                            cycle_count=cycle_count,
                            priority=Priority.HIGH
                        )
                        memories.append(obs_memory)
                except Exception as e:
                    logger.error(f"Error reading announcement file {ann_file}: {e}")
        
        except Exception as e:
            logger.error(f"Error scanning announcements: {e}")
        
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
                            Priority.MEDIUM,
                            cycle_count
                        )
                        if obs_memory:
                            memories.append(obs_memory)
        
        except Exception as e:
            logger.error(f"Error scanning {directory}: {e}")
        
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