"""
Session management data structures and enums.

This module defines the core data structures used for managing
terminal sessions throughout the system.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Tuple, Optional
import uuid


class SessionStatus(Enum):
    """Enumeration of possible session states."""
    CREATING = "creating"
    RUNNING = "running"
    PAUSED = "paused"
    TERMINATED = "terminated"
    ERROR = "error"


@dataclass
class TerminalSession:
    """Core terminal session data structure."""
    
    session_id: str
    name: str
    command: str
    process_id: int
    status: SessionStatus
    working_directory: str
    environment: Dict[str, str]
    created_at: datetime
    last_activity: datetime
    terminal_size: Tuple[int, int]
    pty_master: int
    pty_slave: int
    
    # Optional fields with defaults
    exit_code: Optional[int] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def create_new(cls, command: str, name: Optional[str] = None, 
                   working_directory: str = "/tmp",
                   environment: Optional[Dict[str, str]] = None,
                   terminal_size: Tuple[int, int] = (24, 80)) -> 'TerminalSession':
        """Create a new terminal session with default values."""
        
        session_id = str(uuid.uuid4())
        if name is None:
            name = f"session_{session_id[:8]}"
        
        if environment is None:
            environment = {}
        
        now = datetime.now()
        
        return cls(
            session_id=session_id,
            name=name,
            command=command,
            process_id=0,  # Will be set when process is spawned
            status=SessionStatus.CREATING,
            working_directory=working_directory,
            environment=environment,
            created_at=now,
            last_activity=now,
            terminal_size=terminal_size,
            pty_master=-1,  # Will be set when PTY is created
            pty_slave=-1    # Will be set when PTY is created
        )
    
    @property
    def uptime(self) -> timedelta:
        """Calculate session uptime."""
        return datetime.now() - self.created_at
    
    @property
    def is_active(self) -> bool:
        """Check if session is in an active state."""
        return self.status in (SessionStatus.RUNNING, SessionStatus.PAUSED)
    
    @property
    def is_terminated(self) -> bool:
        """Check if session has been terminated."""
        return self.status == SessionStatus.TERMINATED
    
    def update_activity(self):
        """Update the last activity timestamp."""
        self.last_activity = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for serialization."""
        return {
            'session_id': self.session_id,
            'name': self.name,
            'command': self.command,
            'process_id': self.process_id,
            'status': self.status.value,
            'working_directory': self.working_directory,
            'environment': self.environment,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'terminal_size': self.terminal_size,
            'pty_master': self.pty_master,
            'pty_slave': self.pty_slave,
            'exit_code': self.exit_code,
            'error_message': self.error_message,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TerminalSession':
        """Create session from dictionary (deserialization)."""
        return cls(
            session_id=data['session_id'],
            name=data['name'],
            command=data['command'],
            process_id=data['process_id'],
            status=SessionStatus(data['status']),
            working_directory=data['working_directory'],
            environment=data['environment'],
            created_at=datetime.fromisoformat(data['created_at']),
            last_activity=datetime.fromisoformat(data['last_activity']),
            terminal_size=tuple(data['terminal_size']),
            pty_master=data['pty_master'],
            pty_slave=data['pty_slave'],
            exit_code=data.get('exit_code'),
            error_message=data.get('error_message'),
            metadata=data.get('metadata', {})
        )


@dataclass
class SessionInfo:
    """Lightweight session information for API responses."""
    
    session_id: str
    name: str
    command: str
    process_id: int
    status: SessionStatus
    working_directory: str
    created_at: datetime
    last_activity: datetime
    uptime: timedelta
    terminal_size: Tuple[int, int]
    memory_usage: int = 0
    cpu_usage: float = 0.0
    
    @classmethod
    def from_session(cls, session: TerminalSession) -> 'SessionInfo':
        """Create SessionInfo from TerminalSession."""
        return cls(
            session_id=session.session_id,
            name=session.name,
            command=session.command,
            process_id=session.process_id,
            status=session.status,
            working_directory=session.working_directory,
            created_at=session.created_at,
            last_activity=session.last_activity,
            uptime=session.uptime,
            terminal_size=session.terminal_size
        )

