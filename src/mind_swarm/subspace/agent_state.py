"""Agent state management for persistence across server restarts."""

import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

from mind_swarm.utils.logging import logger


class AgentLifecycle(Enum):
    """Agent lifecycle states."""
    NASCENT = "nascent"       # Just created, never run
    ACTIVE = "active"         # Currently running
    SLEEPING = "sleeping"     # Process stopped, state saved
    HIBERNATING = "hibernating"  # Long-term storage


@dataclass
class AgentState:
    """Persistent agent state."""
    name: str  # Primary identifier
    created_at: str
    last_active: str
    lifecycle: AgentLifecycle
    memory_snapshot: Dict[str, Any]
    config: Dict[str, Any]
    total_uptime: float = 0.0
    activation_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['lifecycle'] = self.lifecycle.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentState':
        """Create from dictionary."""
        data['lifecycle'] = AgentLifecycle(data['lifecycle'])
        return cls(**data)


class AgentNameGenerator:
    """Generate memorable names for agents."""
    
    # Names in alphabetical order for easy tracking
    NAMES = [
        "Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace", "Henry",
        "Iris", "Jack", "Kate", "Leo", "Maya", "Noah", "Olivia", "Peter",
        "Quinn", "Rose", "Sam", "Tara", "Uma", "Victor", "Wendy", "Xavier",
        "Yara", "Zoe"
    ]
    
    def __init__(self, used_names: Optional[List[str]] = None):
        """Initialize with list of already used names."""
        self.used_names = set(used_names or [])
        
    def get_next_name(self) -> str:
        """Get the next available name."""
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
    
    def get_agent_number(self, name: str) -> int:
        """Get the agent number from name (1-based)."""
        # Strip any numbers from the end
        base_name = name.rstrip('0123456789')
        
        if base_name in self.NAMES:
            return self.NAMES.index(base_name) + 1
        return -1


class AgentStateManager:
    """Manages persistent agent state across server restarts."""
    
    def __init__(self, subspace_root: Path):
        self.subspace_root = subspace_root
        self.state_dir = subspace_root / "agent_states"
        self.state_dir.mkdir(exist_ok=True)
        
        self.states: Dict[str, AgentState] = {}
        self.name_generator = AgentNameGenerator()
        
        # Load existing states
        self._load_states()
    
    def _load_states(self):
        """Load all agent states from disk."""
        for state_file in self.state_dir.glob("*.json"):
            try:
                data = json.loads(state_file.read_text())
                state = AgentState.from_dict(data)
                self.states[state.name] = state
                
                # Track used names
                if state.name:
                    self.name_generator.used_names.add(state.name)
                    
                logger.info(f"Loaded agent state: {state.name} ({state.agent_id})")
            except Exception as e:
                logger.error(f"Failed to load agent state from {state_file}: {e}")
    
    def create_agent(self, name: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> AgentState:
        """Create a new agent state."""
        # Use provided name or generate memorable name
        if name:
            # Check if name already exists
            if name in self.states:
                raise ValueError(f"Agent with name '{name}' already exists")
            # Track the name as used
            self.name_generator.used_names.add(name)
        else:
            name = self.name_generator.get_next_name()
        
        state = AgentState(
            name=name,
            created_at=datetime.now().isoformat(),
            last_active=datetime.now().isoformat(),
            lifecycle=AgentLifecycle.NASCENT,
            memory_snapshot={},
            config=config or {},
            total_uptime=0.0,
            activation_count=0
        )
        
        self.states[name] = state
        self._save_state(state)
        
        agent_num = self.name_generator.get_agent_number(name)
        logger.info(f"Created agent #{agent_num}: {name}")
        
        return state
    
    def get_state(self, name: str) -> Optional[AgentState]:
        """Get agent state by name."""
        return self.states.get(name)
    
    # Removed get_state_by_name - no longer needed since name is the key
    
    def list_agents(self) -> List[AgentState]:
        """List all known agents."""
        return list(self.states.values())
    
    def update_lifecycle(self, name: str, lifecycle: AgentLifecycle):
        """Update agent lifecycle state."""
        if name in self.states:
            self.states[name].lifecycle = lifecycle
            self.states[name].last_active = datetime.now().isoformat()
            self._save_state(self.states[name])
    
    def save_memory_snapshot(self, name: str, memory: Dict[str, Any]):
        """Save agent memory snapshot."""
        if name in self.states:
            self.states[name].memory_snapshot = memory
            self._save_state(self.states[name])
    
    def increment_activation(self, name: str):
        """Increment activation count when agent is started."""
        if name in self.states:
            self.states[name].activation_count += 1
            self._save_state(self.states[name])
    
    def update_uptime(self, name: str, session_uptime: float):
        """Update total uptime when agent stops."""
        if name in self.states:
            self.states[name].total_uptime += session_uptime
            self._save_state(self.states[name])
    
    def _save_state(self, state: AgentState):
        """Save agent state to disk."""
        state_file = self.state_dir / f"{state.name}.json"
        state_file.write_text(json.dumps(state.to_dict(), indent=2))
    
    def prepare_shutdown(self) -> List[str]:
        """Prepare for shutdown, return list of active agents to notify."""
        active_agents = []
        for name, state in self.states.items():
            if state.lifecycle == AgentLifecycle.ACTIVE:
                active_agents.append(name)
        return active_agents
    
    def mark_all_sleeping(self):
        """Mark all active agents as sleeping (for shutdown)."""
        for name, state in self.states.items():
            if state.lifecycle == AgentLifecycle.ACTIVE:
                state.lifecycle = AgentLifecycle.SLEEPING
                self._save_state(state)