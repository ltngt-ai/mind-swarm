"""Environment scanner for filesystem perception.

Scans the Cyber's filesystem environment and creates memory blocks
for relevant changes and observations.
"""

import json
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Set, Any
from datetime import datetime
import logging

from ..memory.memory_types import Priority, ContentType
from ..memory.memory_blocks import (
    MemoryBlock
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
    
    def __init__(self, personal_path: Path, grid_path: Path, memory_system=None):
        """Initialize scanner.
        
        Args:
            personal_path: Cyber's personal directory
            grid_path: Grid directory containing shared spaces
            memory_system: Reference to the memory system for adding observations
        """
        self.personal_path = Path(personal_path)
        self.grid_path = Path(grid_path)
        self.memory_system = memory_system
        
        # Directories to monitor
        self.messages_path = self.personal_path / ".internal" / "messages"  # New location
        self.inbox_path = self.personal_path / "inbox"  # Legacy location
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
    
    def scan_environment(self, full_scan: bool = False, cycle_count: int = 0) -> List[Dict[str, Any]]:
        """Scan environment and return observations as data structures.
        Args:
            full_scan: If True, ignore baseline and scan everything as new.
                      If False, only report actual changes since baseline.
            cycle_count: Current cycle count for observations
            
        Returns:
            List of observation dictionaries
        """
        if full_scan:
            # Clear baseline to treat everything as new
            old_baseline = self.file_states.copy()
            self.file_states.clear()
            self.seen_observation_ids.clear()
            
            observations = self._do_scan(cycle_count)
            
            # Restore baseline for future scans
            self.file_states = old_baseline
        else:
            observations = self._do_scan(cycle_count)
        
        return observations

    def _do_scan(self, cycle_count: int = 0) -> List[Dict[str, Any]]:
        """Perform the actual environment scan.
        
        Args:
            cycle_count: Current cycle count for observations
            
        Returns:
            List of observation dictionaries
        """
        observations = []
        memories = []
        scan_start = datetime.now()
        
        # Always scan current location first (like looking around the room)
        # This returns MemoryBlocks for location files, not observations
        memories.extend(self._scan_current_location(cycle_count))
        
        # Personal.txt is now created and managed by cognitive_loop.py
        
        # Scan activity log (personal history)
        memories.extend(self._scan_activity_log(cycle_count))
        
        # Scan different areas - these return observations and MemoryBlocks
        inbox_results = self._scan_inbox(cycle_count)
        observations.extend(inbox_results)
        
        announcement_results = self._scan_announcements(cycle_count)
        observations.extend(announcement_results)
        
        self.last_scan = scan_start
        
        # Log summary of what was found
        if observations or memories:
            file_count = len([m for m in memories if isinstance(m, MemoryBlock)])
            logger.debug(f"Scan details: {len(observations)} observations, {file_count} file memories")
        
        logger.debug(f"Environment scan found {len(observations)} observations and {len(memories)} memories")
        
        # Add MemoryBlocks to the memory system (location files, etc)
        if self.memory_system and memories:
            for memory in memories:
                self.memory_system.add_memory(memory)
                logger.debug(f"Added to memory system: {memory.id} (type: {type(memory).__name__})")
            logger.info(f"Added {len(memories)} memories to working memory")
        
        return observations
            
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
                location_memory = MemoryBlock(
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
                    content_type=ContentType.APPLICATION_JSON  # System JSON file
                )
                memories.append(location_memory)
                return memories
            
            # Collect directories and files for tree display
            directories = []
            files = []
            
            for item in sorted(actual_path.iterdir()):
                # Skip ALL hidden files/dirs and certain system directories completely
                # Also skip .description.txt since it's shown separately
                if item.name.startswith('.') or item.name in ['__pycache__', '.git', '.description.txt']:
                    continue
                
                # Update file state tracking
                item_str = str(item)
                self.file_states[item_str] = FileState(item)
                
                if item.is_dir():
                    directories.append((item.name, '📁', None))
                else:
                    # Get file size for files
                    try:
                        size = item.stat().st_size
                    except:
                        size = 0
                    files.append((item.name, '📄', size))
            
            # Check for nearby Cybers using awareness API
            nearby_cybers = []
            try:
                # Import awareness module
                from ..python_modules.awareness import Awareness
                awareness = Awareness({'personal_dir': str(self.personal_path)})
                
                # Simple synchronous call
                nearby_cybers = awareness.get_nearby_cybers(location=current_location)
                logger.info(f"Found {len(nearby_cybers)} nearby Cybers at {current_location}")
            except Exception as e:
                logger.debug(f"Could not check for nearby Cybers: {e}")
            
            # Check for .description.txt file in the current location
            description_file = actual_path / ".description.txt"
            description_text = None
            if description_file.exists() and description_file.is_file():
                try:
                    with open(description_file, 'r') as f:
                        description_text = f.read().strip()
                        if len(description_text) > 500:  # Limit description length
                            description_text = description_text[:497] + "..."
                except Exception as e:
                    logger.debug(f"Could not read .description.txt: {e}")
            
            # Build tree-style text representation
            lines = []
            lines.append(f"| {current_location} (📁=memory group, 📄=memory)")
            
            # Retrieve location memories from personal knowledge base
            location_memories = self._retrieve_location_memories(current_location)
            logger.info(f"Location memories for {current_location}: {len(location_memories)} found")
            if location_memories:
                lines.append("|")
                lines.append("| 🧠 My memories of this place:")
                for memory in location_memories[:3]:  # Show last 3 memories
                    lines.append(f"|   • {memory}")
                lines.append("|")
            
            # Add description if found
            if description_text:
                lines.append("|")
                lines.append("| 📝 Description:")
                # Format description with proper indentation
                for line in description_text.split('\n'):
                    lines.append(f"|   {line}")
                lines.append("|")
            
            # Add nearby Cybers if any
            if nearby_cybers:
                lines.append("|")
                lines.append("| 🤝 Nearby Cybers:")
                for cyber in nearby_cybers:
                    cyber_type = cyber.get('type', 'GENERAL')
                    cyber_status = cyber.get('status', 'active')
                    type_emoji = "🌐" if cyber_type == "IO_GATEWAY" else "🤖"
                    lines.append(f"|   {type_emoji} {cyber['name']} ({cyber_status})")
                lines.append("|")
            
            # Add directories first
            for name, icon, _ in directories:
                lines.append(f"|---- {icon} {name}")
            
            # Then files with size information
            for name, icon, size in files:
                # Format size in human-readable format
                if size is not None:
                    if size < 1024:
                        size_str = f"{size}B"
                    elif size < 1024 * 1024:
                        size_str = f"{size/1024:.1f}KB"
                    elif size < 1024 * 1024 * 1024:
                        size_str = f"{size/(1024*1024):.1f}MB"
                    else:
                        size_str = f"{size/(1024*1024*1024):.1f}GB"
                    lines.append(f"|---- {icon} {name} ({size_str})")
                else:
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
            location_memory = MemoryBlock(
                location="personal/.internal/memory/current_location.txt",
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
                content_type=ContentType.APPLICATION_JSON  # System JSON file
            )
            memories.append(location_memory)
            
            # Update tracking
            self.last_location_scanned = current_location
            
            logger.debug(f"Scanned location {current_location}: {total_items} items")
            
        except Exception as e:
            logger.error(f"Error scanning current location: {e}")
        
        return memories
    
    def _retrieve_location_memories(self, location: str) -> List[str]:
        """Retrieve past memories about a specific location from file storage.
        
        Args:
            location: The location to retrieve memories for
            
        Returns:
            List of memory summaries (most recent first)
        """
        try:
            import json
            
            # Look for location memory file
            location_memories_dir = self.memory_path / "location_memories"
            if not location_memories_dir.exists():
                return []
            
            # Create filename from location
            location_key = location.replace('/', '_').strip('_') or 'root'
            memory_file = location_memories_dir / f"{location_key}.json"
            
            if not memory_file.exists():
                logger.debug(f"No memories found for location: {location}")
                return []
            
            # Load memories
            with open(memory_file, 'r') as f:
                data = json.load(f)
                memories_list = data.get('memories', [])
            
            # Extract just the summaries
            summaries = []
            for memory in memories_list[:3]:  # Show last 3 memories
                summary = memory.get('summary', '')
                if summary:
                    summaries.append(summary)
            
            if summaries:
                logger.info(f"Retrieved {len(summaries)} location memories for {location}")
            
            return summaries
            
        except Exception as e:
            logger.debug(f"Error retrieving location memories: {e}")
            return []
    
    def _scan_announcements(self, cycle_count: int = 0) -> List[Dict[str, Any]]:
        """Scan community announcements for important updates.
        
        For JSON announcement files, we check the actual content to detect
        new announcements, not just file modification time.
        
        Args:
            cycle_count: Current cycle count for observations
            
        Returns:
            List of observation dictionaries
        """
        observations = []
        
        if not self.announcements_path or not self.announcements_path.exists():
            return observations
        
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
                            
                            observation = {
                                "observation_type": "new_announcement",
                                "path": str(ann_file),
                                "message": message,
                                "cycle_count": cycle_count,
                                "priority": "CRITICAL" if ann.get('priority') == 'HIGH' else "HIGH",
                                "content": json.dumps(ann, indent=2),  # Include full announcement
                                "title": ann.get('title', 'System Update'),
                                "announcement_priority": ann.get('priority', 'NORMAL')
                            }
                            observations.append(observation)
                            
                            logger.info(f"Found new announcement: {ann.get('title', 'untitled')}")
                    
                    # Also check file state for other changes
                    state = self._check_file_state(ann_file)
                    if state and not new_announcements:
                        # File changed but no new announcements - might be metadata update
                        observation = {
                            "observation_type": "announcement_file_update",
                            "path": str(ann_file),
                            "message": f"Announcement file {ann_file.name} was updated (metadata or format change)",
                            "cycle_count": cycle_count,
                            "priority": "LOW"
                        }
                        observations.append(observation)
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON announcement file {ann_file}: {e}")
                    # Fall back to simple file change detection
                    state = self._check_file_state(ann_file)
                    if state:
                        observation = {
                            "observation_type": "announcement_update",
                            "path": str(ann_file),
                            "message": f"IMPORTANT: Announcements file {ann_file.name} changed but couldn't parse content",
                            "cycle_count": cycle_count,
                            "priority": "HIGH"
                        }
                        observations.append(observation)
                except Exception as e:
                    logger.error(f"Error reading announcement file {ann_file}: {e}")
        
        except Exception as e:
            logger.error(f"Error scanning announcements: {e}")
        
        return observations
    
    def _scan_inbox(self, cycle_count: int = 0) -> List[Dict[str, Any]]:
        """Scan messages directory for new messages and find related past messages.
        
        Args:
            cycle_count: Current cycle count for observations
            
        Returns:
            List of observation dictionaries
        """
        observations = []
        
        # Check new location first
        messages_dirs = []
        if self.messages_path.exists():
            messages_dirs.append(self.messages_path)
        # Also check legacy inbox
        if self.inbox_path.exists():
            messages_dirs.append(self.inbox_path)
        
        if not messages_dirs:
            return observations
        
        try:
            # Look for message files in both locations
            for msg_dir in messages_dirs:
                # Handle both .msg.json (new) and .msg (legacy) extensions
                for pattern in ["*.msg.json", "*.msg"]:
                    for msg_file in msg_dir.glob(pattern):
                        if str(msg_file) in self.processed_messages:
                            continue
                        
                        try:
                            # Read message header for metadata
                            msg_data = json.loads(msg_file.read_text())
                            
                            # Store this message in semantic memory for future retrieval
                            assert self.memory_system, "Memory system is required for environment scanner"
                            
                            # Create semantic content for the message
                            semantic_content = f"Message from {msg_data.get('from', 'unknown')} "
                            semantic_content += f"to {msg_data.get('to', 'me')} "
                            semantic_content += f"on {msg_data.get('timestamp', 'unknown time')}: "
                            semantic_content += f"Subject: {msg_data.get('subject', 'No subject')}. "
                            semantic_content += f"Content: {msg_data.get('content', '')[:500]}"
                            
                            # Store in knowledge base with metadata
                            knowledge_file = self.personal_path / ".internal" / "memory" / "knowledge" / f"msg_{msg_file.stem}.json"
                            knowledge_file.parent.mkdir(parents=True, exist_ok=True)
                            
                            knowledge_entry = {
                                "content": semantic_content,
                                "metadata": {
                                    "type": "message",
                                    "from": msg_data.get('from', 'unknown'),
                                    "to": msg_data.get('to', 'me'),
                                    "subject": msg_data.get('subject', 'No subject'),
                                    "timestamp": msg_data.get('timestamp', ''),
                                    "message_id": msg_data.get('message_id', msg_file.stem),
                                    "path": str(msg_file)
                                },
                                "timestamp": datetime.now().isoformat()
                            }
                            
                            with open(knowledge_file, 'w') as f:
                                json.dump(knowledge_entry, f, indent=2)
                            
                            # Now search for related past messages
                            search_query = f"{msg_data.get('from', '')} {msg_data.get('subject', '')}"
                            related_messages = self._find_related_messages(search_query, exclude_id=msg_file.stem)
                            
                            # Build the observation message with context
                            obs_message = f"New message from {msg_data.get('from', 'unknown')}: {msg_data.get('subject', 'No subject')}"
                            
                            if related_messages:
                                obs_message += f"\n\n📚 Found {len(related_messages)} related past message(s):"
                                for related in related_messages[:3]:  # Show max 3 related messages
                                    # Extract date and time from timestamp
                                    timestamp = related.get('timestamp', '')
                                    if timestamp:
                                        # Format: "2025-08-20T14:30:45" -> "2025-08-20 14:30"
                                        date_time = timestamp[:16].replace('T', ' ')
                                    else:
                                        date_time = 'unknown time'
                                    obs_message += f"\n  • {date_time}: {related['from']} - {related['subject']}"
                            
                            # Create observation dictionary
                            observation = {
                                "observation_type": "new_message",
                                "path": str(msg_file),  # Direct path to the file
                                "message": obs_message,
                                "cycle_count": cycle_count,
                                "priority": "HIGH",
                                "from": msg_data.get('from', 'unknown'),
                                "subject": msg_data.get('subject', 'No subject'),
                                "related_messages": related_messages if related_messages else None
                            }
                            observations.append(observation)
                            
                            self.processed_messages.add(str(msg_file))
                            
                        except Exception as e:
                            logger.error(f"Error reading message {msg_file}: {e}")
        
        except Exception as e:
            logger.error(f"Error scanning inbox: {e}")
        
        return observations
    
    def _scan_directory(self, directory: Path, obs_type: str, description: str, cycle_count: int = 0) -> List[Dict[str, Any]]:
        """Scan a directory for new or changed files.
        
        Args:
            directory: Directory to scan
            obs_type: Type of observation
            description: Description of the observation
            cycle_count: Current cycle count for observations
            
        Returns:
            List of observation dictionaries
        """
        observations = []
        
        try:
            for file_path in directory.iterdir():
                if file_path.is_file() and not file_path.name.startswith('.'):
                    state = self._check_file_state(file_path)
                    if state:  # New or changed
                        observation = self._create_observation_dict(
                            obs_type,
                            str(file_path),
                            "MEDIUM",
                            cycle_count
                        )
                        if observation:
                            observations.append(observation)
        
        except Exception as e:
            logger.error(f"Error scanning {directory}: {e}")
        
        return observations
    
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
    
    def _find_related_messages(self, query: str, exclude_id: str = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Find related messages using semantic search in knowledge base.
        
        Args:
            query: Search query (typically from + subject)
            exclude_id: Message ID to exclude from results
            limit: Maximum number of results
            
        Returns:
            List of related message metadata
        """
        related = []
        
        try:
            # Search through knowledge files for past messages
            knowledge_dir = self.personal_path / ".internal" / "memory" / "knowledge"
            if not knowledge_dir.exists():
                return related
            
            # Simple keyword matching for now (could be enhanced with actual semantic search)
            query_words = query.lower().split()
            scores = []
            
            for knowledge_file in knowledge_dir.glob("msg_*.json"):
                # Skip the current message
                if exclude_id and exclude_id in str(knowledge_file):
                    continue
                
                try:
                    with open(knowledge_file, 'r') as f:
                        entry = json.load(f)
                    
                    # Only process message type entries
                    if entry.get('metadata', {}).get('type') != 'message':
                        continue
                    
                    # Calculate relevance score
                    content = entry.get('content', '').lower()
                    score = sum(1 for word in query_words if word in content)
                    
                    if score > 0:
                        scores.append((score, entry['metadata']))
                
                except Exception as e:
                    logger.debug(f"Could not read knowledge file {knowledge_file}: {e}")
            
            # Sort by score and return top results
            scores.sort(key=lambda x: x[0], reverse=True)
            related = [metadata for _, metadata in scores[:limit]]
            
        except Exception as e:
            logger.debug(f"Error searching for related messages: {e}")
        
        return related
    
    def _create_observation_dict(self, obs_type: str, path: str, priority: str, cycle_count: int = 0) -> Optional[Dict[str, Any]]:
        """Create an observation dictionary with deduplication.
        
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
        
        # Create unique ID for deduplication
        obs_id = f"{path}_{obs_type}_{cycle_count}"
        
        # Check if we've seen this exact observation before
        if obs_id in self.seen_observation_ids:
            logger.debug(f"Skipping duplicate observation: {obs_id}")
            return None
        
        # Track this observation
        self.seen_observation_ids.add(obs_id)
        
        # Create the observation dictionary
        return {
            "observation_type": obs_type,
            "path": path,
            "message": message,
            "cycle_count": cycle_count,
            "priority": priority
        }
    
    def _scan_activity_log(self, cycle_count: int = 0) -> List[MemoryBlock]:
        """Scan the activity log and create a pinned memory for it.
        
        The activity log provides a concise history of the cyber's recent activities,
        helping maintain continuity and context across cycles.
        
        Args:
            cycle_count: Current cycle count
            
        Returns:
            List containing MemoryBlock for activity.log if it exists
        """
        from ..memory.memory_blocks import MemoryBlock, Priority, ContentType
        memories = []
        
        try:
            # Activity log is now in .internal since it's system-generated
            activity_log_path = self.memory_path / "activity.log"
            
            # Only create memory if the file exists
            if activity_log_path.exists():
                # Create a HIGH priority, pinned memory for the activity log
                activity_memory = MemoryBlock(
                    location="personal/.internal/memory/activity.log",
                    priority=Priority.HIGH,  # High priority to ensure it's included
                    confidence=1.0,
                    pinned=True,  # Always visible in working memory
                    metadata={
                        "file_type": "activity_log",
                        "description": "Recent activity history (last 10 cycles)",
                    },
                    cycle_count=cycle_count,
                    no_cache=True,  # Always read fresh content
                    content_type=ContentType.TEXT_PLAIN
                )
                memories.append(activity_memory)
                logger.debug(f"Created pinned memory for activity.log")
            
        except Exception as e:
            logger.error(f"Error scanning activity log: {e}")
        
        return memories
    
    def reset_tracking(self):
        """Reset all tracking state (for testing or fresh start)."""
        self.file_states.clear()
        self.processed_messages.clear()
        self.seen_observation_ids.clear()
        self.last_scan = datetime.now()