"""Registry for Cyber types and their configurations."""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from mind_swarm.schemas.cyber_types import (
    CyberType, CyberTypeConfig, get_cyber_type_config
)
from mind_swarm.utils.logging import logger


class CyberInfo:
    """Information about a registered Cyber."""
    
    def __init__(
        self,
        name: str,
        cyber_type: CyberType,
        status: str = "active",
        capabilities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.cyber_type = cyber_type
        self.status = status
        self.capabilities = capabilities or []
        self.metadata = metadata or {}
        self.registered_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        # Simplified format: just name, mail address, and info
        return {
            "name": self.name,
            "mail_address": f"{self.name}@mind-swarm.local",
            "info": ""  # Will be populated from greeting.md when available
        }


class CyberRegistry:
    """Central registry for all Cybers in the system."""
    
    def __init__(self, subspace_root: Path):
        """Initialize the Cyber registry.
        
        Args:
            subspace_root: Root path of the subspace
        """
        self.subspace_root = subspace_root
        self.community_dir = subspace_root / "grid" / "community"
        self.directory_file = self.community_dir / "cyber_directory.json"
        
        # In-memory cache
        self._cybers: Dict[str, CyberInfo] = {}
        self._io_agents: List[str] = []
        self._general_agents: List[str] = []
        
        # Ensure community directory exists
        self.community_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing registry
        self._load_registry()
    
    def _load_registry(self):
        """Load Cyber registry from disk."""
        if self.directory_file.exists():
            try:
                with open(self.directory_file, 'r') as f:
                    data = json.load(f)
                
                # Load all Cybers from flat list
                for cyber_data in data.get("cybers", []):
                    # Determine Cyber type from string
                    type_str = cyber_data.get("type", "general")
                    cyber_type = CyberType.IO_GATEWAY if type_str == "io_gateway" else CyberType.GENERAL
                    
                    Cyber = CyberInfo(
                        name=cyber_data["name"],
                        cyber_type=cyber_type,
                        status=cyber_data.get("status", "active"),
                        capabilities=cyber_data.get("capabilities", []),
                        metadata=cyber_data.get("metadata", {})
                    )
                    
                    # Set registered_at if available
                    if "registered_at" in cyber_data:
                        Cyber.registered_at = cyber_data["registered_at"]
                    
                    self._cybers[Cyber.name] = Cyber
                    
                    # Add to type-specific lists
                    if cyber_type == CyberType.IO_GATEWAY:
                        self._io_agents.append(Cyber.name)
                    else:
                        self._general_agents.append(Cyber.name)
                
                logger.info(f"Loaded {len(self._cybers)} Cybers from community registry")
            except Exception as e:
                logger.error(f"Failed to load Cyber registry: {e}")
                self._save_registry()  # Create empty registry
    
    def _save_registry(self):
        """Save Cyber registry to disk."""
        # Collect all Cybers in simplified format
        all_agents = []
        for name, cyber in self._cybers.items():
            # Check for greeting.md if cyber directory exists
            cyber_dict = cyber.to_dict()
            cyber_dir = self.subspace_root / "cybers" / name
            greeting_file = cyber_dir / "greeting.md"
            
            # If greeting.md exists, read its content for the info field
            if greeting_file.exists():
                try:
                    with open(greeting_file, 'r') as f:
                        cyber_dict["info"] = f.read().strip()
                except Exception:
                    pass  # Keep empty info on read error
            
            all_agents.append(cyber_dict)
        
        # Simplified structure: just the list of cybers
        data = {
            "last_updated": datetime.now().isoformat(),
            "cybers": all_agents
        }
        
        try:
            with open(self.directory_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug("Cyber registry saved to community")
        except Exception as e:
            logger.error(f"Failed to save Cyber registry: {e}")
    
    def register_agent(
        self,
        name: str,
        cyber_type: CyberType,
        capabilities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CyberInfo:
        """Register a new Cyber in the system.
        
        Args:
            name: Cyber name
            cyber_type: Type of Cyber
            capabilities: List of Cyber capabilities
            metadata: Additional metadata
            
        Returns:
            CyberInfo object
        """
        # Get default capabilities from type config
        if capabilities is None and cyber_type == CyberType.IO_GATEWAY:
            type_config = get_cyber_type_config(cyber_type)
            if type_config.server_component:
                capabilities = type_config.server_component.capabilities
        
        Cyber = CyberInfo(name, cyber_type, "active", capabilities, metadata)
        self._cybers[name] = Cyber
        
        # Add to appropriate list
        if cyber_type == CyberType.IO_GATEWAY:
            if name not in self._io_agents:
                self._io_agents.append(name)
        else:
            if name not in self._general_agents:
                self._general_agents.append(name)
        
        self._save_registry()
        logger.info(f"Registered {cyber_type.value} Cyber: {name}")
        
        return Cyber
    
    def unregister_agent(self, name: str):
        """Remove an Cyber from the registry."""
        if name in self._cybers:
            del self._cybers[name]
            
            # Remove from lists
            if name in self._io_agents:
                self._io_agents.remove(name)
            if name in self._general_agents:
                self._general_agents.remove(name)
            
            self._save_registry()
            logger.info(f"Unregistered Cyber: {name}")
    
    def update_agent_status(self, name: str, status: str):
        """Update an Cyber's status."""
        if name in self._cybers:
            self._cybers[name].status = status
            self._save_registry()
    
    def get_agent(self, name: str) -> Optional[CyberInfo]:
        """Get information about a specific Cyber."""
        return self._cybers.get(name)
    
    def get_agents_by_type(self, cyber_type: CyberType) -> List[CyberInfo]:
        """Get all Cybers of a specific type."""
        return [
            Cyber for Cyber in self._cybers.values()
            if Cyber.cyber_type == cyber_type and Cyber.status == "active"
        ]
    
    def get_io_agents(self) -> List[CyberInfo]:
        """Get all active I/O Cybers."""
        return self.get_agents_by_type(CyberType.IO_GATEWAY)
    
    def find_io_agent_with_capability(self, capability: str) -> Optional[str]:
        """Find an I/O Cyber with a specific capability.
        
        Args:
            capability: Required capability (e.g., "user_interaction", "web_access")
            
        Returns:
            Cyber name if found, None otherwise
        """
        for Cyber in self.get_io_agents():
            if capability in Cyber.capabilities:
                return Cyber.name
        return None
    
    def get_cyber_type_config(self, cyber_type: CyberType) -> CyberTypeConfig:
        """Get configuration for a specific Cyber type."""
        return get_cyber_type_config(cyber_type)
    
    def refresh_registry(self):
        """Refresh the registry to update info fields from greeting.md files."""
        self._save_registry()
        logger.debug("Registry refreshed with latest greeting.md content")
    
    async def update_registry(self):
        """Update registry to include developer accounts."""
        # Import here to avoid circular import
        from mind_swarm.subspace.developer_registry import DeveloperRegistry
        
        dev_registry = DeveloperRegistry(self.subspace_root)
        developers = dev_registry.list_developers()
        
        # Add each developer to the Cyber registry
        for dev_name, dev_info in developers.items():
            cyber_name = dev_info["cyber_name"]
            
            # Create Cyber info for developer
            Cyber = CyberInfo(
                name=cyber_name,
                cyber_type=CyberType.GENERAL,  # Developers are like general Cybers
                status="active",
                capabilities=["mail", "command", "developer"],
                metadata={
                    "developer_name": dev_name,
                    "full_name": dev_info.get("full_name"),
                    "email": dev_info.get("email"),
                    "is_developer": True
                }
            )
            Cyber.registered_at = dev_info.get("registered_at", datetime.now().isoformat())
            
            # Register in memory
            self._cybers[cyber_name] = Cyber
            if cyber_name not in self._general_agents:
                self._general_agents.append(cyber_name)
        
        # Save updated registry
        self._save_registry()