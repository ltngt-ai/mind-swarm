"""Developer registry for managing developer accounts in the subspace."""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class DeveloperRegistry:
    """Manages developer accounts that can interact with Cybers."""
    
    def __init__(self, subspace_root: Path):
        """Initialize developer registry.
        
        Args:
            subspace_root: Root directory of the subspace
        """
        self.subspace_root = subspace_root
        self.registry_file = subspace_root / "shared" / "directory" / "developers.json"
        self.current_developer_file = subspace_root / "shared" / "directory" / "current_developer.json"
        self._ensure_registry_exists()
    
    def _ensure_registry_exists(self):
        """Ensure registry file and directory exist."""
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.registry_file.exists():
            self._save_registry({})
        if not self.current_developer_file.exists():
            self._save_current_developer(None)
    
    def _load_registry(self) -> Dict[str, Dict[str, Any]]:
        """Load developer registry from file."""
        try:
            with open(self.registry_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load developer registry: {e}")
            return {}
    
    def _save_registry(self, registry: Dict[str, Dict[str, Any]]):
        """Save developer registry to file."""
        try:
            with open(self.registry_file, 'w') as f:
                json.dump(registry, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save developer registry: {e}")
    
    def _load_current_developer(self) -> Optional[str]:
        """Load current developer setting."""
        try:
            with open(self.current_developer_file, 'r') as f:
                data = json.load(f)
                return data.get("current_developer")
        except Exception:
            return None
    
    def _save_current_developer(self, developer_name: Optional[str]):
        """Save current developer setting."""
        try:
            with open(self.current_developer_file, 'w') as f:
                json.dump({"current_developer": developer_name}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save current developer: {e}")
    
    def register_developer(self, name: str, full_name: Optional[str] = None, 
                          email: Optional[str] = None) -> str:
        """Register a new developer.
        
        Args:
            name: Developer username (will have _dev suffix added)
            full_name: Optional full name
            email: Optional email address
            
        Returns:
            The developer Cyber name (e.g., "deano_dev")
        """
        registry = self._load_registry()
        
        # Create developer entry
        developer_id = f"{name}_dev"
        registry[name] = {
            "cyber_name": developer_id,
            "full_name": full_name or name,
            "email": email,
            "registered_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat()
        }
        
        self._save_registry(registry)
        
        # Create developer Cyber directory structure
        self._create_developer_directories(developer_id)
        
        # If this is the first developer, set as current
        if self._load_current_developer() is None:
            self.set_current_developer(name)
        
        logger.info(f"Registered developer: {name} as {developer_id}")
        return developer_id
    
    def _create_developer_directories(self, developer_id: str):
        """Create Cyber-like directory structure for developer."""
        # Create main Cyber directory
        cyber_dir = self.subspace_root / "cybers" / developer_id
        cyber_dir.mkdir(parents=True, exist_ok=True)
        
        # Create organized directory structure matching new Cyber layout
        # Mail directories (directly under cyber directory)
        inbox_dir = cyber_dir / "inbox"
        inbox_dir.mkdir(exist_ok=True)
        
        # Don't create outbox directory - it should only be created when needed
        # outbox_dir = cyber_dir / "outbox"
        # outbox_dir.mkdir(exist_ok=True)
        
        mail_archive_dir = cyber_dir / "mail_archive"
        mail_archive_dir.mkdir(exist_ok=True)
        
        # Create memory directory (developers might have memory too)
        memory_dir = cyber_dir / "memory"
        memory_dir.mkdir(exist_ok=True)
        
        # Create .internal directory for system files
        internal_dir = cyber_dir / ".internal"
        internal_dir.mkdir(exist_ok=True)
        
        # Create a simple info file
        info_file = cyber_dir / "developer_info.json"
        info = {
            "type": "developer",
            "name": developer_id,
            "created_at": datetime.now().isoformat(),
            "note": "This is a developer account - no cognitive processing"
        }
        
        with open(info_file, 'w') as f:
            json.dump(info, f, indent=2)
        
        logger.info(f"Created developer directories for {developer_id}")
    
    def get_developer(self, name: str) -> Optional[Dict[str, Any]]:
        """Get developer information by name."""
        registry = self._load_registry()
        return registry.get(name)
    
    def get_current_developer(self) -> Optional[Dict[str, Any]]:
        """Get current developer information."""
        current_name = self._load_current_developer()
        if current_name:
            return self.get_developer(current_name)
        return None
    
    def set_current_developer(self, name: str) -> bool:
        """Set the current developer.
        
        Args:
            name: Developer username
            
        Returns:
            True if successful, False if developer not found
        """
        registry = self._load_registry()
        if name not in registry:
            return False
        
        self._save_current_developer(name)
        
        # Update last active
        registry[name]["last_active"] = datetime.now().isoformat()
        self._save_registry(registry)
        
        logger.info(f"Set current developer to: {name}")
        return True
    
    def list_developers(self) -> Dict[str, Dict[str, Any]]:
        """List all registered developers."""
        return self._load_registry()
    
    def update_developer_activity(self, name: str):
        """Update developer's last active timestamp."""
        registry = self._load_registry()
        if name in registry:
            registry[name]["last_active"] = datetime.now().isoformat()
            self._save_registry(registry)
    
    def get_agent_entry(self, name: str) -> Optional[Dict[str, Any]]:
        """Get Cyber registry entry for a developer.
        
        Returns Cyber-style entry for inclusion in Cybers.json
        """
        dev = self.get_developer(name)
        if not dev:
            return None
        
        return {
            "type": "developer",
            "capabilities": ["mail", "command"],
            "status": "active",
            "created_at": dev["registered_at"],
            "metadata": {
                "developer_name": name,
                "full_name": dev.get("full_name"),
                "email": dev.get("email")
            }
        }
    
    def check_developer_inbox(self, developer_name: str, include_read: bool = False) -> List[Dict[str, Any]]:
        """Check developer's inbox for messages.
        
        Args:
            developer_name: Developer username (without _dev suffix)
            include_read: If True, include processed/read messages
            
        Returns:
            List of messages with file paths
        """
        # Check new location in shared/directory/developers/{name}/inbox
        inbox_dir = self.subspace_root / "shared" / "directory" / "developers" / developer_name / "inbox"
        
        messages = []
        
        # Get all messages from inbox
        if inbox_dir.exists():
            for msg_file in sorted(inbox_dir.glob("*.msg.json")):
                try:
                    with open(msg_file, 'r') as f:
                        message = json.load(f)
                        message['_file_path'] = str(msg_file)
                        # Check if message is marked as read
                        is_read = message.get('read', False)
                        message['_read'] = is_read
                        
                        # Only add message if we should include it
                        if not is_read or include_read:
                            messages.append(message)
                except Exception as e:
                    logger.error(f"Failed to read message {msg_file}: {e}")
        
        return messages
    
    def mark_message_as_read(self, developer_name: str, message_path: str) -> bool:
        """Mark a message as read by updating the 'read' field.
        
        Args:
            developer_name: Developer username (without _dev suffix)
            message_path: Path to the message file
            
        Returns:
            True if successful
        """
        try:
            msg_path = Path(message_path)
            if not msg_path.exists():
                logger.error(f"Message file not found: {message_path}")
                return False
            
            # Instead of moving the file, update the 'read' field in the message
            with open(msg_path, 'r') as f:
                message = json.load(f)
            
            message['read'] = True
            
            # Write back the updated message
            with open(msg_path, 'w') as f:
                json.dump(message, f, indent=2)
            
            logger.info(f"Marked message as read: {msg_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to mark message as read: {e}")
            return False