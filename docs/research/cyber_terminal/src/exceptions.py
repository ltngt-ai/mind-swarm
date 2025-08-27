"""
Exception classes for the Cyber Terminal system.

This module defines the exception hierarchy used throughout the system
for comprehensive error handling and recovery.
"""

from typing import Optional


class CyberTerminalError(Exception):
    """Base exception for all Cyber Terminal errors."""
    
    def __init__(self, message: str, session_id: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.session_id = session_id


class SessionError(CyberTerminalError):
    """Base class for session-related errors."""
    pass


class SessionNotFoundError(SessionError):
    """Raised when attempting to access a non-existent session."""
    
    def __init__(self, session_id: str):
        super().__init__(f"Session not found: {session_id}", session_id)


class SessionCreationError(SessionError):
    """Raised when session creation fails."""
    
    def __init__(self, command: str, reason: str):
        super().__init__(f"Failed to create session for command '{command}': {reason}")
        self.command = command
        self.reason = reason


class SessionTerminatedError(SessionError):
    """Raised when attempting to interact with a terminated session."""
    
    def __init__(self, session_id: str):
        super().__init__(f"Session has been terminated: {session_id}", session_id)


class IOError(CyberTerminalError):
    """Base class for I/O related errors."""
    pass


class TerminalIOError(IOError):
    """Raised when terminal I/O operations fail."""
    
    def __init__(self, message: str, session_id: Optional[str] = None, errno: Optional[int] = None):
        super().__init__(message, session_id)
        self.errno = errno


class ProcessIOError(IOError):
    """Raised when process I/O operations fail."""
    
    def __init__(self, message: str, process_id: Optional[int] = None):
        super().__init__(message)
        self.process_id = process_id


class ConfigurationError(CyberTerminalError):
    """Base class for configuration-related errors."""
    pass


class InvalidCommandError(ConfigurationError):
    """Raised when an invalid command is provided."""
    
    def __init__(self, command: str, reason: str = "Command not found or not executable"):
        super().__init__(f"Invalid command '{command}': {reason}")
        self.command = command
        self.reason = reason


class PermissionError(ConfigurationError):
    """Raised when insufficient permissions prevent operation."""
    
    def __init__(self, operation: str, reason: str = "Insufficient permissions"):
        super().__init__(f"Permission denied for operation '{operation}': {reason}")
        self.operation = operation
        self.reason = reason


class PTYError(CyberTerminalError):
    """Base class for PTY-related errors."""
    pass


class PTYCreationError(PTYError):
    """Raised when PTY creation fails."""
    
    def __init__(self, reason: str):
        super().__init__(f"Failed to create PTY: {reason}")
        self.reason = reason


class PTYOperationError(PTYError):
    """Raised when PTY operations fail."""
    
    def __init__(self, message: str, session_id: Optional[str] = None):
        super().__init__(message, session_id)


class ProcessError(CyberTerminalError):
    """Base class for process-related errors."""
    pass


class ProcessCreationError(ProcessError):
    """Raised when process creation fails."""
    
    def __init__(self, command: str, reason: str):
        super().__init__(f"Failed to create process for command '{command}': {reason}")
        self.command = command
        self.reason = reason


class ProcessOperationError(ProcessError):
    """Raised when process operations fail."""
    
    def __init__(self, message: str, process_id: Optional[int] = None):
        super().__init__(message)
        self.process_id = process_id

