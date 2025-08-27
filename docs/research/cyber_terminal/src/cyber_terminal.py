"""
Cyber Terminal - Main Terminal Management System.

This module provides the main CyberTerminal class that coordinates
all terminal operations, session management, and I/O handling.
"""

import os
import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any, Tuple
from concurrent.futures import ThreadPoolExecutor

from .session import TerminalSession, SessionStatus, SessionInfo
from .pty_manager import PTYManager
from .process_manager import ProcessManager
from .terminal_buffer import TerminalBuffer
from .screen_content import ScreenContent
from .input_handler import InputHandler
from .session_store import SessionStore
from .exceptions import (
    CyberTerminalError, SessionError, SessionNotFoundError,
    SessionCreationError, SessionTerminatedError, TerminalIOError
)


logger = logging.getLogger(__name__)


class CyberTerminalConfig:
    """Configuration for CyberTerminal system."""
    
    def __init__(self,
                 max_sessions: int = 100,
                 session_timeout: int = 3600,  # 1 hour
                 buffer_size: int = 10000,     # lines of scrollback
                 cleanup_interval: int = 300,  # 5 minutes
                 log_level: str = 'INFO',
                 persistence_backend: str = 'sqlite',
                 db_path: Optional[str] = None,
                 auto_cleanup: bool = True,
                 auto_shutdown_sessions: bool = False):  # New option
        
        self.max_sessions = max_sessions
        self.session_timeout = session_timeout
        self.buffer_size = buffer_size
        self.cleanup_interval = cleanup_interval
        self.log_level = log_level
        self.persistence_backend = persistence_backend
        self.db_path = db_path
        self.auto_cleanup = auto_cleanup
        self.auto_shutdown_sessions = auto_shutdown_sessions  # Don't auto-terminate sessions


class CyberTerminal:
    """Main terminal interaction system for AI agents."""
    
    def __init__(self, config: Optional[CyberTerminalConfig] = None):
        self.config = config or CyberTerminalConfig()
        
        # Initialize components
        self.pty_manager = PTYManager()
        self.process_manager = ProcessManager()
        self.input_handler = InputHandler()
        self.session_store = SessionStore(self.config.db_path)
        
        # Session management
        self.sessions: Dict[str, TerminalSession] = {}
        self.terminal_buffers: Dict[str, TerminalBuffer] = {}
        self.last_read_times: Dict[str, datetime] = {}
        
        # Event system
        self.event_callbacks: Dict[str, List[Callable]] = {}
        
        # Background tasks
        self._cleanup_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        
        # Initialize system
        self._initialize()
    
    def _initialize(self):
        """Initialize the terminal system."""
        # Set up logging
        logging.basicConfig(level=getattr(logging, self.config.log_level))
        
        # Load existing sessions
        self._load_existing_sessions()
        
        # Start background cleanup if enabled
        if self.config.auto_cleanup:
            self._start_cleanup_thread()
        
        logger.info("CyberTerminal system initialized")
    
    def _load_existing_sessions(self):
        """Load existing sessions from storage."""
        try:
            stored_sessions = self.session_store.load_active_sessions()
            
            for session in stored_sessions:
                # Check if process is still alive using direct PID check
                try:
                    os.kill(session.process_id, 0)
                    process_alive = True
                except (OSError, ProcessLookupError):
                    process_alive = False
                
                if process_alive:
                    # Reconnect to the session
                    self.sessions[session.session_id] = session
                    
                    # Reconnect to PTY
                    try:
                        self.pty_manager.reconnect_pty(session.session_id, session.pty_master, session.pty_slave)
                    except Exception as e:
                        logger.warning(f"Failed to reconnect PTY for session {session.session_id}: {e}")
                        continue
                    
                    # Reconnect to process
                    try:
                        self.process_manager.reconnect_process(session.session_id, session.process_id)
                    except Exception as e:
                        logger.warning(f"Failed to reconnect process for session {session.session_id}: {e}")
                        continue
                    
                    # Create terminal buffer
                    buffer = TerminalBuffer(
                        session.terminal_size[0],
                        session.terminal_size[1],
                        self.config.buffer_size
                    )
                    self.terminal_buffers[session.session_id] = buffer
                    
                    logger.info(f"Restored session {session.session_id}")
                else:
                    # Mark as terminated
                    session.status = SessionStatus.TERMINATED
                    self.session_store.save_session(session)
            
            logger.info(f"Loaded {len(self.sessions)} existing sessions")
            
        except Exception as e:
            logger.error(f"Failed to load existing sessions: {e}")
    
    def _start_cleanup_thread(self):
        """Start background cleanup thread."""
        def cleanup_worker():
            while not self._shutdown_event.wait(self.config.cleanup_interval):
                try:
                    self._cleanup_inactive_sessions()
                    self.session_store.cleanup_terminated_sessions()
                except Exception as e:
                    logger.error(f"Error in cleanup thread: {e}")
        
        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        logger.info("Started background cleanup thread")
    
    def _cleanup_inactive_sessions(self):
        """Clean up inactive sessions."""
        current_time = datetime.now()
        timeout_delta = timedelta(seconds=self.config.session_timeout)
        
        sessions_to_cleanup = []
        
        for session_id, session in self.sessions.items():
            if current_time - session.last_activity > timeout_delta:
                if not self.process_manager.is_process_alive(session_id):
                    sessions_to_cleanup.append(session_id)
        
        for session_id in sessions_to_cleanup:
            logger.info(f"Cleaning up inactive session {session_id}")
            self.terminate_session(session_id)
    
    def create_session(self, 
                      command: str,
                      working_dir: Optional[str] = None,
                      env: Optional[Dict[str, str]] = None,
                      name: Optional[str] = None,
                      terminal_size: Tuple[int, int] = (24, 80)) -> str:
        """
        Create a new terminal session.
        
        Args:
            command: Command to execute
            working_dir: Working directory (defaults to /tmp)
            env: Environment variables
            name: Session name (auto-generated if not provided)
            terminal_size: Terminal dimensions (rows, cols)
            
        Returns:
            Session ID
            
        Raises:
            SessionCreationError: If session creation fails
            InvalidCommandError: If command is invalid
        """
        # Check session limit
        if len(self.sessions) >= self.config.max_sessions:
            raise SessionCreationError(command, "Maximum session limit reached")
        
        # Create session object
        session = TerminalSession.create_new(
            command=command,
            name=name,
            working_directory=working_dir or "/tmp",
            environment=env or {},
            terminal_size=terminal_size
        )
        
        try:
            # Create PTY
            master_fd, slave_fd = self.pty_manager.create_pty(session.session_id, session.terminal_size)
            session.pty_master = master_fd
            session.pty_slave = slave_fd
            
            # Spawn process
            pid = self.process_manager.spawn_process(session, slave_fd)
            session.process_id = pid
            session.status = SessionStatus.RUNNING
            
            # Create terminal buffer
            buffer = TerminalBuffer(
                terminal_size[0], 
                terminal_size[1], 
                self.config.buffer_size
            )
            self.terminal_buffers[session.session_id] = buffer
            
            # Store session
            self.sessions[session.session_id] = session
            self.session_store.save_session(session)
            
            # Initialize read time
            self.last_read_times[session.session_id] = datetime.now()
            
            # Emit event
            self._emit_event('session_created', session.session_id, session)
            
            logger.info(f"Created session {session.session_id}: {command}")
            return session.session_id
            
        except Exception as e:
            # Cleanup on failure
            if session.session_id in self.sessions:
                del self.sessions[session.session_id]
            if session.session_id in self.terminal_buffers:
                del self.terminal_buffers[session.session_id]
            
            self.pty_manager.close_pty(session.session_id)
            
            if isinstance(e, (SessionCreationError, InvalidCommandError)):
                raise
            else:
                raise SessionCreationError(command, str(e))
    
    def read_screen(self, 
                   session_id: str,
                   format: str = 'text',
                   lines: Optional[int] = None,
                   since_last: bool = False) -> ScreenContent:
        """
        Read screen content from terminal session.
        
        Args:
            session_id: Session identifier
            format: Output format ('text', 'structured', 'raw', 'ansi')
            lines: Limit to last N lines
            since_last: Return only new content since last read
            
        Returns:
            Screen content
            
        Raises:
            SessionNotFoundError: If session doesn't exist
            SessionTerminatedError: If session is terminated
        """
        session = self._get_session(session_id)
        buffer = self.terminal_buffers.get(session_id)
        
        if not buffer:
            raise SessionNotFoundError(session_id)
        
        # Update buffer with new data
        self._update_terminal_buffer(session_id)
        
        # Get content
        if since_last:
            # Implementation would track what was read before
            # For now, return current content
            content = buffer.get_screen_content(format, lines)
        else:
            content = buffer.get_screen_content(format, lines)
        
        # Update last read time
        self.last_read_times[session_id] = datetime.now()
        session.update_activity()
        self.session_store.save_session(session)
        
        return content
    
    def send_input(self, 
                  session_id: str,
                  data: str,
                  input_type: str = 'text') -> bool:
        """
        Send input to terminal session.
        
        Args:
            session_id: Session identifier
            data: Input data
            input_type: Type of input ('text', 'text_no_newline', 'control', 'key')
            
        Returns:
            True if input sent successfully
            
        Raises:
            SessionNotFoundError: If session doesn't exist
            SessionTerminatedError: If session is terminated
        """
        session = self._get_session(session_id)
        
        if session.status == SessionStatus.TERMINATED:
            raise SessionTerminatedError(session_id)
        
        try:
            # Process input
            processed_data = self.input_handler.process_input(data, input_type)
            
            # Send to PTY
            bytes_written = self.pty_manager.write_input(session_id, processed_data)
            
            # Update activity
            session.update_activity()
            self.session_store.save_session(session)
            
            # Emit event
            self._emit_event('input_sent', session_id, data, input_type)
            
            logger.debug(f"Sent {bytes_written} bytes to session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send input to session {session_id}: {e}")
            return False
    
    def get_session_info(self, session_id: str) -> SessionInfo:
        """
        Get session information.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session information
            
        Raises:
            SessionNotFoundError: If session doesn't exist
        """
        session = self._get_session(session_id)
        
        # Get process stats
        process_stats = self.process_manager.get_process_stats(session_id)
        
        info = SessionInfo.from_session(session)
        info.memory_usage = process_stats.get('memory_usage', 0)
        info.cpu_usage = process_stats.get('cpu_usage', 0.0)
        
        return info
    
    def list_sessions(self) -> List[SessionInfo]:
        """
        List all active sessions.
        
        Returns:
            List of session information
        """
        session_infos = []
        
        for session in self.sessions.values():
            try:
                info = self.get_session_info(session.session_id)
                session_infos.append(info)
            except Exception as e:
                logger.warning(f"Failed to get info for session {session.session_id}: {e}")
        
        return session_infos
    
    def terminate_session(self, session_id: str, force: bool = False) -> bool:
        """
        Terminate a terminal session.
        
        Args:
            session_id: Session identifier
            force: Force termination with SIGKILL
            
        Returns:
            True if termination successful
        """
        session = self.sessions.get(session_id)
        if not session:
            return True  # Already terminated
        
        try:
            # Terminate process
            self.process_manager.terminate_process(session_id, force)
            
            # Close PTY
            self.pty_manager.close_pty(session_id)
            
            # Update session status
            session.status = SessionStatus.TERMINATED
            session.update_activity()
            self.session_store.save_session(session)
            
            # Clean up tracking data
            if session_id in self.terminal_buffers:
                del self.terminal_buffers[session_id]
            if session_id in self.last_read_times:
                del self.last_read_times[session_id]
            del self.sessions[session_id]
            
            # Emit event
            self._emit_event('session_terminated', session_id)
            
            logger.info(f"Terminated session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to terminate session {session_id}: {e}")
            return False
    
    def resize_terminal(self, session_id: str, rows: int, cols: int) -> bool:
        """
        Resize terminal for session.
        
        Args:
            session_id: Session identifier
            rows: New number of rows
            cols: New number of columns
            
        Returns:
            True if resize successful
        """
        session = self._get_session(session_id)
        
        try:
            # Resize PTY
            success = self.pty_manager.resize_terminal(session_id, rows, cols)
            
            if success:
                # Update session
                session.terminal_size = (rows, cols)
                self.session_store.save_session(session)
                
                # Resize buffer
                buffer = self.terminal_buffers.get(session_id)
                if buffer:
                    buffer.resize(rows, cols)
                
                logger.info(f"Resized session {session_id} to {rows}x{cols}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to resize session {session_id}: {e}")
            return False
    
    def subscribe(self, event_type: str, callback: Callable):
        """
        Subscribe to system events.
        
        Args:
            event_type: Type of event to subscribe to
            callback: Callback function
        """
        if event_type not in self.event_callbacks:
            self.event_callbacks[event_type] = []
        
        self.event_callbacks[event_type].append(callback)
        logger.debug(f"Subscribed to event type: {event_type}")
    
    def unsubscribe(self, event_type: str, callback: Callable):
        """
        Unsubscribe from system events.
        
        Args:
            event_type: Type of event to unsubscribe from
            callback: Callback function to remove
        """
        if event_type in self.event_callbacks:
            try:
                self.event_callbacks[event_type].remove(callback)
                logger.debug(f"Unsubscribed from event type: {event_type}")
            except ValueError:
                pass
    
    def _get_session(self, session_id: str) -> TerminalSession:
        """Get session or raise exception if not found."""
        session = self.sessions.get(session_id)
        if not session:
            raise SessionNotFoundError(session_id)
        return session
    
    def _update_terminal_buffer(self, session_id: str):
        """Update terminal buffer with new data from PTY."""
        buffer = self.terminal_buffers.get(session_id)
        if not buffer:
            return
        
        try:
            # Read new data from PTY
            data = self.pty_manager.read_output(session_id, timeout=0.01)
            
            if data:
                # Process data through terminal buffer
                buffer.process_data(data)
                
                # Emit event for new output
                self._emit_event('output_received', session_id, data)
                
        except Exception as e:
            logger.debug(f"No new data for session {session_id}: {e}")
    
    def _emit_event(self, event_type: str, *args, **kwargs):
        """Emit event to subscribers."""
        callbacks = self.event_callbacks.get(event_type, [])
        
        for callback in callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in event callback for {event_type}: {e}")
    
    def shutdown(self):
        """Shutdown the terminal system."""
        logger.info("Shutting down CyberTerminal system")
        
        # Stop cleanup thread
        self._shutdown_event.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
        
        # Only terminate sessions if auto_shutdown_sessions is enabled
        if self.config.auto_shutdown_sessions:
            # Terminate all sessions
            session_ids = list(self.sessions.keys())
            for session_id in session_ids:
                self.terminate_session(session_id, force=True)
        else:
            # Just disconnect from sessions, don't terminate them
            logger.info("Preserving sessions (auto_shutdown_sessions=False)")
            self.sessions.clear()
            self.terminal_buffers.clear()
            self.last_read_times.clear()
        
        # Shutdown managers
        self.process_manager.shutdown()
        self.pty_manager.cleanup_all()
        
        logger.info("CyberTerminal system shutdown complete")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()


class AsyncCyberTerminal:
    """Asynchronous version of CyberTerminal for async/await usage."""
    
    def __init__(self, config: Optional[CyberTerminalConfig] = None):
        self._terminal = CyberTerminal(config)
        self._executor = None
    
    async def create_session(self, *args, **kwargs) -> str:
        """Async version of create_session."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, 
            self._terminal.create_session, 
            *args, **kwargs
        )
    
    async def read_screen(self, *args, **kwargs) -> ScreenContent:
        """Async version of read_screen."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._terminal.read_screen,
            *args, **kwargs
        )
    
    async def send_input(self, *args, **kwargs) -> bool:
        """Async version of send_input."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._terminal.send_input,
            *args, **kwargs
        )
    
    async def get_session_info(self, *args, **kwargs) -> SessionInfo:
        """Async version of get_session_info."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._terminal.get_session_info,
            *args, **kwargs
        )
    
    async def list_sessions(self) -> List[SessionInfo]:
        """Async version of list_sessions."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._terminal.list_sessions
        )
    
    async def terminate_session(self, *args, **kwargs) -> bool:
        """Async version of terminate_session."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._terminal.terminate_session,
            *args, **kwargs
        )
    
    def subscribe(self, *args, **kwargs):
        """Subscribe to events (synchronous)."""
        return self._terminal.subscribe(*args, **kwargs)
    
    def unsubscribe(self, *args, **kwargs):
        """Unsubscribe from events (synchronous)."""
        return self._terminal.unsubscribe(*args, **kwargs)
    
    async def shutdown(self):
        """Async shutdown."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._executor, self._terminal.shutdown)
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.shutdown()

