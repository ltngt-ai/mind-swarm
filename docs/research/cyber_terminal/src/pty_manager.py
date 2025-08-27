#!/usr/bin/env python3
"""
PTY (Pseudo-Terminal) Manager for Cyber Terminal.

This module handles the creation and management of pseudo-terminals
for terminal sessions.
"""

import os
import pty
import select
import termios
import struct
import fcntl
import logging
from typing import Dict, Optional, Tuple, Any
from threading import Lock

from .exceptions import PTYCreationError, PTYOperationError

logger = logging.getLogger(__name__)


class PTYManager:
    """
    Manages pseudo-terminals for terminal sessions.
    
    This class handles PTY creation, I/O operations, and cleanup.
    """
    
    def __init__(self):
        self.active_ptys: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
    
    def create_pty(self, session_id: str, terminal_size: Tuple[int, int] = (24, 80)) -> Tuple[int, int]:
        """
        Create a new pseudo-terminal.
        
        Args:
            session_id: Unique session identifier
            terminal_size: Terminal dimensions (rows, cols)
            
        Returns:
            Tuple of (master_fd, slave_fd)
            
        Raises:
            PTYCreationError: If PTY creation fails
        """
        try:
            # Create PTY pair
            master_fd, slave_fd = pty.openpty()
            
            # Configure terminal settings
            self._configure_terminal(slave_fd, terminal_size)
            
            # Store PTY information
            with self._lock:
                self.active_ptys[session_id] = {
                    'master_fd': master_fd,
                    'slave_fd': slave_fd,
                    'terminal_size': terminal_size,
                    'created_at': None  # Will be set by process manager
                }
            
            logger.info(f"Created PTY for session {session_id}: master={master_fd}, slave={slave_fd}")
            return master_fd, slave_fd
            
        except OSError as e:
            raise PTYCreationError(f"Failed to create PTY: {e}")
    
    def reconnect_pty(self, session_id: str, master_fd: int, slave_fd: int) -> bool:
        """
        Reconnect to an existing PTY.
        
        Args:
            session_id: Session identifier
            master_fd: Master file descriptor
            slave_fd: Slave file descriptor
            
        Returns:
            True if reconnection successful
        """
        try:
            # Verify the file descriptors are still valid
            try:
                # Try to get terminal attributes to verify FDs are valid
                termios.tcgetattr(slave_fd)
            except (OSError, termios.error):
                logger.warning(f"PTY file descriptors {master_fd}/{slave_fd} are no longer valid")
                return False
            
            # Store PTY information
            with self._lock:
                self.active_ptys[session_id] = {
                    'master_fd': master_fd,
                    'slave_fd': slave_fd,
                    'terminal_size': (24, 80),  # Default, will be updated if needed
                    'reconnected': True
                }
            
            logger.info(f"Reconnected to PTY for session {session_id}: master={master_fd}, slave={slave_fd}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reconnect PTY for session {session_id}: {e}")
            return False
    
    def _configure_terminal(self, slave_fd: int, terminal_size: Tuple[int, int]):
        """Configure terminal settings."""
        try:
            # Set terminal size
            rows, cols = terminal_size
            winsize = struct.pack('HHHH', rows, cols, 0, 0)
            fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)
            
            # Get current terminal attributes
            attrs = termios.tcgetattr(slave_fd)
            
            # Configure for raw mode with some processing
            attrs[0] &= ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK | termios.ISTRIP |
                         termios.INLCR | termios.IGNCR | termios.ICRNL | termios.IXON)
            attrs[1] &= ~termios.OPOST
            attrs[2] &= ~(termios.CSIZE | termios.PARENB)
            attrs[2] |= termios.CS8
            attrs[3] &= ~(termios.ECHO | termios.ECHONL | termios.ICANON | termios.ISIG | termios.IEXTEN)
            
            # Set minimum characters and timeout
            attrs[6][termios.VMIN] = 1
            attrs[6][termios.VTIME] = 0
            
            # Apply settings
            termios.tcsetattr(slave_fd, termios.TCSANOW, attrs)
            
        except (OSError, termios.error) as e:
            logger.warning(f"Failed to configure terminal: {e}")
    
    def read_output(self, session_id: str, timeout: float = 0.1) -> bytes:
        """
        Read output from PTY master.
        
        Args:
            session_id: Session identifier
            timeout: Read timeout in seconds
            
        Returns:
            Output data as bytes
            
        Raises:
            PTYOperationError: If read operation fails
        """
        pty_info = self.active_ptys.get(session_id)
        if not pty_info:
            raise PTYOperationError(f"No PTY found for session {session_id}")
        
        master_fd = pty_info['master_fd']
        
        try:
            # Use select to check if data is available
            ready, _, _ = select.select([master_fd], [], [], timeout)
            
            if ready:
                # Read available data
                data = os.read(master_fd, 4096)
                return data
            else:
                return b''
                
        except OSError as e:
            if e.errno == 5:  # Input/output error - PTY closed
                logger.info(f"PTY closed for session {session_id}")
                return b''
            else:
                raise PTYOperationError(f"Failed to read from PTY: {e}")
    
    def write_input(self, session_id: str, data: bytes) -> int:
        """
        Write input to PTY master.
        
        Args:
            session_id: Session identifier
            data: Input data to write
            
        Returns:
            Number of bytes written
            
        Raises:
            PTYOperationError: If write operation fails
        """
        pty_info = self.active_ptys.get(session_id)
        if not pty_info:
            raise PTYOperationError(f"No PTY found for session {session_id}")
        
        master_fd = pty_info['master_fd']
        
        try:
            bytes_written = os.write(master_fd, data)
            return bytes_written
            
        except OSError as e:
            raise PTYOperationError(f"Failed to write to PTY: {e}")
    
    def resize_terminal(self, session_id: str, rows: int, cols: int) -> bool:
        """
        Resize terminal.
        
        Args:
            session_id: Session identifier
            rows: New number of rows
            cols: New number of columns
            
        Returns:
            True if resize successful
        """
        pty_info = self.active_ptys.get(session_id)
        if not pty_info:
            return False
        
        slave_fd = pty_info['slave_fd']
        
        try:
            # Set new terminal size
            winsize = struct.pack('HHHH', rows, cols, 0, 0)
            fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)
            
            # Update stored size
            with self._lock:
                self.active_ptys[session_id]['terminal_size'] = (rows, cols)
            
            logger.info(f"Resized terminal for session {session_id} to {rows}x{cols}")
            return True
            
        except (OSError, KeyError) as e:
            logger.error(f"Failed to resize terminal for session {session_id}: {e}")
            return False
    
    def get_terminal_size(self, session_id: str) -> Optional[Tuple[int, int]]:
        """
        Get current terminal size.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Terminal size as (rows, cols) or None if not found
        """
        pty_info = self.active_ptys.get(session_id)
        if pty_info:
            return pty_info['terminal_size']
        return None
    
    def close_pty(self, session_id: str) -> bool:
        """
        Close PTY for session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if close successful
        """
        pty_info = self.active_ptys.get(session_id)
        if not pty_info:
            return False
        
        try:
            # Close file descriptors
            master_fd = pty_info['master_fd']
            slave_fd = pty_info['slave_fd']
            
            # Only close if we're not reconnected (to avoid closing FDs we don't own)
            if not pty_info.get('reconnected', False):
                try:
                    os.close(master_fd)
                except OSError:
                    pass
                
                try:
                    os.close(slave_fd)
                except OSError:
                    pass
            
            # Remove from active PTYs
            with self._lock:
                del self.active_ptys[session_id]
            
            logger.info(f"Closed PTY for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error closing PTY for session {session_id}: {e}")
            return False
    
    def get_pty_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get PTY information for session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            PTY information dictionary or None if not found
        """
        return self.active_ptys.get(session_id)
    
    def is_pty_active(self, session_id: str) -> bool:
        """Check if PTY is active for session."""
        return session_id in self.active_ptys
    
    def cleanup_all(self):
        """Clean up all active PTYs."""
        # Don't automatically close PTYs - sessions should persist
        # Just clear tracking data
        logger.info("PTY manager cleanup complete")
    
    def __del__(self):
        """Cleanup on destruction."""
        # Don't auto-cleanup on destruction for persistence
        pass


