"""Cyber state management for persistence across server restarts."""

import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from mind_swarm.utils.logging import logger


@dataclass
class CyberState:
    """Persistent Cyber state."""
    name: str  # Primary identifier
    created_at: str
    last_active: str
    memory_snapshot: Dict[str, Any]
    config: Dict[str, Any]
    total_uptime: float = 0.0
    activation_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CyberState':
        """Create from dictionary."""
        # Remove lifecycle if present (for backward compatibility)
        data.pop('lifecycle', None)
        return cls(**data)


class AgentNameGenerator:
    """Generate memorable names for Cybers."""
    
    # Names in alphabetical order for easy tracking
    NAMES = [
        "Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace", "Henry",
        "Iris", "Jack", "Kate", "Leo", "Maya", "Noah", "Olivia", "Peter",
        "Quinn", "Rose", "Sam", "Tara", "Uma", "Victor", "Wendy", "Xavier",
        "Yara", "Zoe"
    ]
    
    # I-based names for I/O Cybers
    IO_NAMES = [
        "Ian", "Ivy", "Isaac", "Isabel", "Igor", "Irene", "Ivan", "Isla",
        "Ira", "Ingrid", "Indigo", "Imogen", "Ike", "Ilana", "Inigo", "Ida"
    ]
    
    def __init__(self, used_names: Optional[List[str]] = None):
        """Initialize with list of already used names."""
        self.used_names = set(used_names or [])
        
    def get_next_name(self, cyber_type: str = "general") -> str:
        """Get the next available name for the Cyber type."""
        if cyber_type == "io_gateway":
            return self._get_next_io_name()
        else:
            return self._get_next_general_name()
    
    def _get_next_general_name(self) -> str:
        """Get the next available general Cyber name."""
        for name in self.NAMES:
            if name not in self.used_names:
                self.used_names.add(name)
                return name
        
        # If all names used, add numbers
        counter = 2
        while True:
            for name in self.NAMES:
                numbered_name = f"{name}{counter}"
                if numbered_name not in self.used_names:
                    self.used_names.add(numbered_name)
                    return numbered_name
            counter += 1
    
    def _get_next_io_name(self) -> str:
        """Get the next available I/O Cyber name with -io suffix."""
        for base_name in self.IO_NAMES:
            io_name = f"{base_name}-io"
            if io_name not in self.used_names:
                self.used_names.add(io_name)
                return io_name
        
        # If all I/O names used, add numbers
        counter = 2
        while True:
            for base_name in self.IO_NAMES:
                numbered_name = f"{base_name}{counter}-io"
                if numbered_name not in self.used_names:
                    self.used_names.add(numbered_name)
                    return numbered_name
            counter += 1
    
    def get_agent_number(self, name: str) -> int:
        """Get the Cyber number from name (1-based)."""
        # Check if it's an I/O Cyber name
        if name.endswith("-io"):
            base_name = name[:-3]  # Remove "-io" suffix
            # Strip any numbers from the end
            base_name = base_name.rstrip('0123456789')
            if base_name in self.IO_NAMES:
                return self.IO_NAMES.index(base_name) + 1000  # I/O Cybers start at 1000
        else:
            # Strip any numbers from the end
            base_name = name.rstrip('0123456789')
            if base_name in self.NAMES:
                return self.NAMES.index(base_name) + 1
        return -1


class CyberStateManager:
    """Manages persistent Cyber state across server restarts."""
    
    def __init__(self, subspace_root: Path):
        self.subspace_root = subspace_root
        self.cybers_dir = subspace_root / "cybers"
        self.cybers_dir.mkdir(exist_ok=True)
        
        self.states: Dict[str, CyberState] = {}
        self.name_generator = AgentNameGenerator()
        self._states_loaded = False
        
        # Don't load states in __init__ - will be done on first access
    
    async def load_states(self):
        """Load all Cyber states from disk."""
        if self._states_loaded:
            return
            
        import aiofiles
        # Look for state files in each cyber's directory
        for cyber_dir in self.cybers_dir.iterdir():
            if cyber_dir.is_dir():
                state_file = cyber_dir / "state.json"
                if state_file.exists():
                    try:
                        async with aiofiles.open(state_file, 'r') as f:
                            content = await f.read()
                        data = json.loads(content)
                        state = CyberState.from_dict(data)
                        self.states[state.name] = state
                        
                        # Track used names
                        if state.name:
                            self.name_generator.used_names.add(state.name)
                            
                        logger.info(f"Loaded Cyber state: {state.name}")
                    except Exception as e:
                        logger.error(f"Failed to load Cyber state from {state_file}: {e}")
        
        self._states_loaded = True
    
    async def create_agent(self, name: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> CyberState:
        """Create a new Cyber state."""
        # Use provided name or generate memorable name
        if name:
            # Check if name already exists
            if name in self.states:
                raise ValueError(f"Cyber with name '{name}' already exists")
            # Track the name as used
            self.name_generator.used_names.add(name)
        else:
            # Get Cyber type from config to generate appropriate name
            cyber_type = config.get("cyber_type", "general") if config else "general"
            name = self.name_generator.get_next_name(cyber_type)
        
        state = CyberState(
            name=name,
            created_at=datetime.now().isoformat(),
            last_active=datetime.now().isoformat(),
            memory_snapshot={},
            config=config or {},
            total_uptime=0.0,
            activation_count=0
        )
        
        self.states[name] = state
        await self._save_state(state)
        
        agent_num = self.name_generator.get_agent_number(name)
        logger.info(f"Created Cyber #{agent_num}: {name}")
        
        return state
    
    async def get_state(self, name: str) -> Optional[CyberState]:
        """Get Cyber state by name."""
        await self.load_states()  # Ensure states are loaded
        return self.states.get(name)
    
    # Removed get_state_by_name - no longer needed since name is the key
    
    async def list_agents(self) -> List[CyberState]:
        """List all known Cybers."""
        await self.load_states()  # Ensure states are loaded
        return list(self.states.values())
    
    async def update_last_active(self, name: str):
        """Update Cyber's last active timestamp."""
        await self.load_states()  # Ensure states are loaded
        if name in self.states:
            self.states[name].last_active = datetime.now().isoformat()
            await self._save_state(self.states[name])
    
    async def save_memory_snapshot(self, name: str, memory: Dict[str, Any]):
        """Save Cyber memory snapshot."""
        await self.load_states()  # Ensure states are loaded
        if name in self.states:
            self.states[name].memory_snapshot = memory
            await self._save_state(self.states[name])
    
    async def increment_activation(self, name: str):
        """Increment activation count when Cyber is started."""
        await self.load_states()  # Ensure states are loaded
        if name in self.states:
            self.states[name].activation_count += 1
            await self._save_state(self.states[name])
    
    async def update_uptime(self, name: str, session_uptime: float):
        """Update total uptime when Cyber stops."""
        await self.load_states()  # Ensure states are loaded
        if name in self.states:
            self.states[name].total_uptime += session_uptime
            await self._save_state(self.states[name])
    
    async def _save_state(self, state: CyberState):
        """Save Cyber state to disk."""
        import aiofiles
        # Save to cyber's personal folder
        cyber_dir = self.cybers_dir / state.name
        cyber_dir.mkdir(parents=True, exist_ok=True)
        state_file = cyber_dir / "state.json"
        async with aiofiles.open(state_file, 'w') as f:
            await f.write(json.dumps(state.to_dict(), indent=2))
    
    async def delete_agent(self, name: str):
        """Delete an Cyber's state (Cyber has been terminated)."""
        await self.load_states()  # Ensure states are loaded
        if name in self.states:
            # Remove from memory
            del self.states[name]
            # Remove from disk - state is in cyber's personal folder
            cyber_dir = self.cybers_dir / name
            if cyber_dir.exists():
                state_file = cyber_dir / "state.json"
                if state_file.exists():
                    state_file.unlink()
            logger.info(f"Deleted Cyber state for {name}")