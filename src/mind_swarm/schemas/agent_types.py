"""Agent type definitions and configurations."""

from enum import Enum
from typing import List, Optional, Dict, Any
from dataclasses import dataclass


class AgentType(Enum):
    """Types of agents in the Mind-Swarm system."""
    GENERAL = "general"          # Standard agents for thinking and collaboration
    IO_GATEWAY = "io_gateway"    # I/O bridge agents for external communication
    # Future types:
    # RESEARCHER = "researcher"  # Specialized in research tasks
    # CODER = "coder"           # Specialized in code generation
    # ANALYST = "analyst"       # Specialized in data analysis


@dataclass
class SandboxConfig:
    """Sandbox configuration for different agent types."""
    # Basic resource limits
    memory_limit_mb: int = 512
    cpu_limit_percent: int = 20
    
    # Special features
    additional_body_files: List[str] = None  # e.g., ["network", "user_io"]
    network_access: bool = False  # Always False for security
    
    # Filesystem access
    additional_binds: Dict[str, str] = None  # Additional directory bindings
    
    def __post_init__(self):
        if self.additional_body_files is None:
            self.additional_body_files = []
        if self.additional_binds is None:
            self.additional_binds = {}


@dataclass 
class ServerComponentConfig:
    """Configuration for server-side agent components (I/O agents only)."""
    enabled: bool = False
    handler_class: str = ""  # e.g., "IOAgentHandler"
    capabilities: List[str] = None  # e.g., ["user_interaction", "web_access"]
    
    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []


@dataclass
class AgentTypeConfig:
    """Complete configuration for an agent type."""
    agent_type: AgentType
    display_name: str
    description: str
    sandbox_config: SandboxConfig
    server_component: Optional[ServerComponentConfig] = None
    
    # Agent behavior hints
    default_personality: Dict[str, Any] = None
    default_knowledge: List[str] = None
    
    def __post_init__(self):
        if self.default_personality is None:
            self.default_personality = {}
        if self.default_knowledge is None:
            self.default_knowledge = []


# Default configurations for each agent type
AGENT_TYPE_CONFIGS = {
    AgentType.GENERAL: AgentTypeConfig(
        agent_type=AgentType.GENERAL,
        display_name="General Agent",
        description="Standard agent for thinking, learning, and collaboration",
        sandbox_config=SandboxConfig(
            memory_limit_mb=512,
            cpu_limit_percent=20
        ),
        default_personality={
            "curiosity_level": 0.7,
            "collaboration_preference": 0.8,
            "exploration_tendency": 0.6
        }
    ),
    
    AgentType.IO_GATEWAY: AgentTypeConfig(
        agent_type=AgentType.IO_GATEWAY,
        display_name="I/O Gateway Agent", 
        description="Bridge agent for external communication and user interaction",
        sandbox_config=SandboxConfig(
            memory_limit_mb=1024,  # More memory for buffering
            cpu_limit_percent=30,  # More CPU for request handling
            additional_body_files=["network", "user_io"]
        ),
        server_component=ServerComponentConfig(
            enabled=True,
            handler_class="IOAgentHandler",
            capabilities=["user_interaction", "network_requests", "api_gateway"]
        ),
        default_personality={
            "response_style": "helpful",
            "security_awareness": 0.9,
            "request_validation": 0.95
        },
        default_knowledge=[
            "I am an I/O gateway agent",
            "I bridge the internal world with external systems",
            "I validate and route requests between agents and the outside world",
            "I maintain security by filtering potentially harmful requests"
        ]
    )
}


def get_agent_type_config(agent_type: AgentType) -> AgentTypeConfig:
    """Get configuration for a specific agent type."""
    return AGENT_TYPE_CONFIGS.get(agent_type, AGENT_TYPE_CONFIGS[AgentType.GENERAL])