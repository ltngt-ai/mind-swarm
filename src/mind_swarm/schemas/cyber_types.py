"""Cyber type definitions and configurations."""

from enum import Enum
from typing import List, Optional, Dict, Any
from dataclasses import dataclass


class CyberType(Enum):
    """Types of Cybers in the Mind-Swarm system."""
    GENERAL = "general"          # Standard Cybers for thinking and collaboration
    IO_GATEWAY = "io_gateway"    # I/O bridge Cybers for external communication
    # Future types:
    # RESEARCHER = "researcher"  # Specialized in research tasks
    # CODER = "coder"           # Specialized in code generation
    # ANALYST = "analyst"       # Specialized in data analysis


@dataclass
class SandboxConfig:
    """Sandbox configuration for different Cyber types."""
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
    """Configuration for server-side Cyber components (I/O Cybers only)."""
    enabled: bool = False
    handler_class: str = ""  # e.g., "IOCyberHandler"
    capabilities: List[str] = None  # e.g., ["user_interaction", "web_access"]
    
    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []


@dataclass
class CyberTypeConfig:
    """Complete configuration for a Cyber type."""
    cyber_type: CyberType
    display_name: str
    description: str
    sandbox_config: SandboxConfig
    server_component: Optional[ServerComponentConfig] = None
    
    # Cyber behavior hints
    default_personality: Dict[str, Any] = None
    default_knowledge: List[str] = None
    
    def __post_init__(self):
        if self.default_personality is None:
            self.default_personality = {}
        if self.default_knowledge is None:
            self.default_knowledge = []


# Default configurations for each Cyber type
CYBER_TYPE_CONFIGS = {
    CyberType.GENERAL: CyberTypeConfig(
        cyber_type=CyberType.GENERAL,
        display_name="General Cyber",
        description="Standard Cyber for thinking, learning, and collaboration",
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
    
    CyberType.IO_GATEWAY: CyberTypeConfig(
        cyber_type=CyberType.IO_GATEWAY,
        display_name="I/O Gateway Cyber", 
        description="Bridge Cyber for external communication and user interaction",
        sandbox_config=SandboxConfig(
            memory_limit_mb=1024,  # More memory for buffering
            cpu_limit_percent=30,  # More CPU for request handling
            additional_body_files=["network", "user_io"]
        ),
        server_component=ServerComponentConfig(
            enabled=True,
            handler_class="IOCyberHandler",
            capabilities=["user_interaction", "network_requests", "api_gateway"]
        ),
        default_personality={
            "response_style": "helpful",
            "security_awareness": 0.9,
            "request_validation": 0.95
        },
        default_knowledge=[
            "I am an I/O gateway Cyber",
            "I bridge the internal world with external systems",
            "I validate and route requests between Cybers and the outside world",
            "I maintain security by filtering potentially harmful requests"
        ]
    )
}


def get_cyber_type_config(cyber_type: CyberType) -> CyberTypeConfig:
    """Get configuration for a specific Cyber type."""
    return CYBER_TYPE_CONFIGS.get(cyber_type, CYBER_TYPE_CONFIGS[CyberType.GENERAL])