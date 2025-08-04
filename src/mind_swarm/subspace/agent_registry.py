"""Registry for agent types and their configurations."""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from mind_swarm.schemas.agent_types import (
    AgentType, AgentTypeConfig, get_agent_type_config
)
from mind_swarm.utils.logging import logger


class AgentInfo:
    """Information about a registered agent."""
    
    def __init__(
        self,
        name: str,
        agent_type: AgentType,
        status: str = "active",
        capabilities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.agent_type = agent_type
        self.status = status
        self.capabilities = capabilities or []
        self.metadata = metadata or {}
        self.registered_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "type": self.agent_type.value,
            "status": self.status,
            "capabilities": self.capabilities,
            "metadata": self.metadata,
            "registered_at": self.registered_at
        }


class AgentRegistry:
    """Central registry for all agents in the system."""
    
    def __init__(self, subspace_root: Path):
        """Initialize the agent registry.
        
        Args:
            subspace_root: Root path of the subspace
        """
        self.subspace_root = subspace_root
        self.plaza_dir = subspace_root / "grid" / "plaza"
        self.directory_file = self.plaza_dir / "agent_directory.json"
        
        # In-memory cache
        self._agents: Dict[str, AgentInfo] = {}
        self._io_agents: List[str] = []
        self._general_agents: List[str] = []
        
        # Ensure plaza exists
        self.plaza_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing registry
        self._load_registry()
    
    def _load_registry(self):
        """Load agent registry from disk."""
        if self.directory_file.exists():
            try:
                with open(self.directory_file, 'r') as f:
                    data = json.load(f)
                
                # Load all agents from flat list
                for agent_data in data.get("agents", []):
                    # Determine agent type from string
                    type_str = agent_data.get("type", "general")
                    agent_type = AgentType.IO_GATEWAY if type_str == "io_gateway" else AgentType.GENERAL
                    
                    agent = AgentInfo(
                        name=agent_data["name"],
                        agent_type=agent_type,
                        status=agent_data.get("status", "active"),
                        capabilities=agent_data.get("capabilities", []),
                        metadata=agent_data.get("metadata", {})
                    )
                    
                    # Set registered_at if available
                    if "registered_at" in agent_data:
                        agent.registered_at = agent_data["registered_at"]
                    
                    self._agents[agent.name] = agent
                    
                    # Add to type-specific lists
                    if agent_type == AgentType.IO_GATEWAY:
                        self._io_agents.append(agent.name)
                    else:
                        self._general_agents.append(agent.name)
                
                logger.info(f"Loaded {len(self._agents)} agents from plaza registry")
            except Exception as e:
                logger.error(f"Failed to load agent registry: {e}")
                self._save_registry()  # Create empty registry
    
    def _save_registry(self):
        """Save agent registry to disk."""
        # Collect all agents
        all_agents = []
        for name, agent in self._agents.items():
            all_agents.append(agent.to_dict())
        
        # Calculate stats
        stats = {
            "total_agents": len(self._agents),
            "active_agents": len([a for a in self._agents.values() if a.status == "active"]),
            "by_type": {}
        }
        
        # Count by type
        for agent in self._agents.values():
            type_name = agent.agent_type.value
            stats["by_type"][type_name] = stats["by_type"].get(type_name, 0) + 1
        
        data = {
            "last_updated": datetime.now().isoformat(),
            "agents": all_agents,
            "stats": stats
        }
        
        try:
            with open(self.directory_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug("Agent registry saved to plaza")
        except Exception as e:
            logger.error(f"Failed to save agent registry: {e}")
    
    def register_agent(
        self,
        name: str,
        agent_type: AgentType,
        capabilities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentInfo:
        """Register a new agent in the system.
        
        Args:
            name: Agent name
            agent_type: Type of agent
            capabilities: List of agent capabilities
            metadata: Additional metadata
            
        Returns:
            AgentInfo object
        """
        # Get default capabilities from type config
        if capabilities is None and agent_type == AgentType.IO_GATEWAY:
            type_config = get_agent_type_config(agent_type)
            if type_config.server_component:
                capabilities = type_config.server_component.capabilities
        
        agent = AgentInfo(name, agent_type, "active", capabilities, metadata)
        self._agents[name] = agent
        
        # Add to appropriate list
        if agent_type == AgentType.IO_GATEWAY:
            if name not in self._io_agents:
                self._io_agents.append(name)
        else:
            if name not in self._general_agents:
                self._general_agents.append(name)
        
        self._save_registry()
        logger.info(f"Registered {agent_type.value} agent: {name}")
        
        return agent
    
    def unregister_agent(self, name: str):
        """Remove an agent from the registry."""
        if name in self._agents:
            agent = self._agents[name]
            del self._agents[name]
            
            # Remove from lists
            if name in self._io_agents:
                self._io_agents.remove(name)
            if name in self._general_agents:
                self._general_agents.remove(name)
            
            self._save_registry()
            logger.info(f"Unregistered agent: {name}")
    
    def update_agent_status(self, name: str, status: str):
        """Update an agent's status."""
        if name in self._agents:
            self._agents[name].status = status
            self._save_registry()
    
    def get_agent(self, name: str) -> Optional[AgentInfo]:
        """Get information about a specific agent."""
        return self._agents.get(name)
    
    def get_agents_by_type(self, agent_type: AgentType) -> List[AgentInfo]:
        """Get all agents of a specific type."""
        return [
            agent for agent in self._agents.values()
            if agent.agent_type == agent_type and agent.status == "active"
        ]
    
    def get_io_agents(self) -> List[AgentInfo]:
        """Get all active I/O agents."""
        return self.get_agents_by_type(AgentType.IO_GATEWAY)
    
    def find_io_agent_with_capability(self, capability: str) -> Optional[str]:
        """Find an I/O agent with a specific capability.
        
        Args:
            capability: Required capability (e.g., "user_interaction", "web_access")
            
        Returns:
            Agent name if found, None otherwise
        """
        for agent in self.get_io_agents():
            if capability in agent.capabilities:
                return agent.name
        return None
    
    def get_agent_type_config(self, agent_type: AgentType) -> AgentTypeConfig:
        """Get configuration for a specific agent type."""
        return get_agent_type_config(agent_type)
    
    async def update_registry(self):
        """Update registry to include developer accounts."""
        # Import here to avoid circular import
        from mind_swarm.subspace.developer_registry import DeveloperRegistry
        
        dev_registry = DeveloperRegistry(self.subspace_root)
        developers = dev_registry.list_developers()
        
        # Add each developer to the agent registry
        for dev_name, dev_info in developers.items():
            agent_name = dev_info["agent_name"]
            
            # Create agent info for developer
            agent = AgentInfo(
                name=agent_name,
                agent_type=AgentType.GENERAL,  # Developers are like general agents
                status="active",
                capabilities=["mail", "command", "developer"],
                metadata={
                    "developer_name": dev_name,
                    "full_name": dev_info.get("full_name"),
                    "email": dev_info.get("email"),
                    "is_developer": True
                }
            )
            agent.registered_at = dev_info.get("registered_at", datetime.now().isoformat())
            
            # Register in memory
            self._agents[agent_name] = agent
            if agent_name not in self._general_agents:
                self._general_agents.append(agent_name)
        
        # Save updated registry
        self._save_registry()