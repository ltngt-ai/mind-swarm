"""
Terminal Manager for Cyber Terminal Sessions.

Manages terminal sessions for Cybers, including PTY creation,
process management, and body file communication.
"""

import os
import pty
import select
import termios
import tty
import fcntl
import struct
import json
import asyncio
import logging
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
import subprocess
import signal

logger = logging.getLogger(__name__)


@dataclass
class TerminalSession:
    """Represents a terminal session."""
    session_id: str
    cyber_id: str
    command: str
    name: Optional[str]
    pid: int
    master_fd: int
    created_at: datetime
    last_activity: datetime
    terminal_size: Tuple[int, int] = (24, 80)  # rows, cols
    screen_buffer: List[str] = None
    cursor_position: Tuple[int, int] = (0, 0)
    is_active: bool = True
    
    def __post_init__(self):
        if self.screen_buffer is None:
            self.screen_buffer = [''] * self.terminal_size[0]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'session_id': self.session_id,
            'cyber_id': self.cyber_id,
            'command': self.command,
            'name': self.name,
            'pid': self.pid,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'terminal_size': self.terminal_size,
            'cursor_position': self.cursor_position,
            'is_active': self.is_active
        }


class CyberTerminalManager:
    """Manages terminal sessions for all Cybers."""
    
    def __init__(self, subspace_coordinator):
        self.coordinator = subspace_coordinator
        self.sessions: Dict[str, Dict[str, TerminalSession]] = {}  # {cyber_id: {session_id: TerminalSession}}
        self.max_sessions_per_cyber = 5
        self.terminal_timeout = 3600  # 1 hour
        self.buffer_size = 10000  # lines of scrollback
        self._cleanup_task = None
        self._read_tasks = {}  # Track async read tasks
        
    async def start(self):
        """Start the terminal manager."""
        logger.info("Starting Cyber Terminal Manager")
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
    async def stop(self):
        """Stop the terminal manager and cleanup."""
        logger.info("Stopping Cyber Terminal Manager")
        if self._cleanup_task:
            self._cleanup_task.cancel()
            
        # Close all sessions
        for cyber_id in list(self.sessions.keys()):
            for session_id in list(self.sessions[cyber_id].keys()):
                await self.close_session(cyber_id, session_id)
    
    async def create_session(self, cyber_id: str, command: str = "bash", 
                           name: Optional[str] = None,
                           working_dir: Optional[str] = None) -> str:
        """Create a new terminal session for a Cyber.
        
        Args:
            cyber_id: ID of the Cyber
            command: Command to execute (default: bash)
            name: Optional name for the session
            working_dir: Working directory for the command
            
        Returns:
            Session ID
        """
        # Check session limit
        if cyber_id not in self.sessions:
            self.sessions[cyber_id] = {}
        
        if len(self.sessions[cyber_id]) >= self.max_sessions_per_cyber:
            raise ValueError(f"Cyber {cyber_id} has reached maximum session limit ({self.max_sessions_per_cyber})")
        
        # Generate session ID
        session_id = f"term-{uuid.uuid4().hex[:8]}"
        
        # Get cyber's home directory
        cyber_dir = self.coordinator.subspace.cybers_dir / cyber_id
        if not cyber_dir.exists():
            raise ValueError(f"Cyber {cyber_id} not found")
        
        if working_dir is None:
            working_dir = str(cyber_dir)
        
        try:
            # Create PTY
            master_fd, slave_fd = pty.openpty()
            
            # Set terminal size
            winsize = struct.pack('HHHH', 24, 80, 0, 0)
            fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)
            
            # Fork and exec
            pid = os.fork()
            if pid == 0:  # Child process
                # Set up the slave terminal
                os.setsid()
                os.dup2(slave_fd, 0)  # stdin
                os.dup2(slave_fd, 1)  # stdout
                os.dup2(slave_fd, 2)  # stderr
                
                # Close file descriptors
                os.close(master_fd)
                os.close(slave_fd)
                
                # Change to working directory
                os.chdir(working_dir)
                
                # Set environment
                env = os.environ.copy()
                env['TERM'] = 'xterm-256color'
                env['HOME'] = str(cyber_dir)
                env['USER'] = cyber_id
                
                # Execute command
                os.execvpe('/bin/bash', ['/bin/bash', '-c', command], env)
                
            # Parent process
            os.close(slave_fd)
            
            # Make master_fd non-blocking
            flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
            fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            # Create session
            session = TerminalSession(
                session_id=session_id,
                cyber_id=cyber_id,
                command=command,
                name=name or command,
                pid=pid,
                master_fd=master_fd,
                created_at=datetime.now(),
                last_activity=datetime.now()
            )
            
            self.sessions[cyber_id][session_id] = session
            
            # Start reading from terminal
            self._read_tasks[session_id] = asyncio.create_task(
                self._read_terminal_output(cyber_id, session_id)
            )
            
            logger.info(f"Created terminal session {session_id} for Cyber {cyber_id}: {command}")
            
            # Broadcast event
            await self.coordinator.broadcast_event({
                'type': 'terminal_created',
                'cyber_id': cyber_id,
                'session_id': session_id,
                'command': command,
                'name': name
            })
            
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to create terminal session for {cyber_id}: {e}")
            raise
    
    async def send_input(self, cyber_id: str, session_id: str, input_text: str):
        """Send input to a terminal session.
        
        Args:
            cyber_id: ID of the Cyber
            session_id: ID of the session
            input_text: Text to send (newline will be added)
        """
        if cyber_id not in self.sessions or session_id not in self.sessions[cyber_id]:
            raise ValueError(f"Session {session_id} not found for Cyber {cyber_id}")
        
        session = self.sessions[cyber_id][session_id]
        
        if not session.is_active:
            raise ValueError(f"Session {session_id} is not active")
        
        try:
            # Add newline if not present
            if not input_text.endswith('\n'):
                input_text += '\n'
            
            # Write to master PTY
            os.write(session.master_fd, input_text.encode())
            
            # Update activity
            session.last_activity = datetime.now()
            
            logger.debug(f"Sent input to {cyber_id}/{session_id}: {input_text.strip()}")
            
        except Exception as e:
            logger.error(f"Failed to send input to {cyber_id}/{session_id}: {e}")
            raise
    
    async def read_screen(self, cyber_id: str, session_id: str, 
                         format: str = "text") -> Dict[str, Any]:
        """Read current screen content from a terminal.
        
        Args:
            cyber_id: ID of the Cyber
            session_id: ID of the session
            format: Output format (text, structured, raw)
            
        Returns:
            Screen content based on format
        """
        if cyber_id not in self.sessions or session_id not in self.sessions[cyber_id]:
            raise ValueError(f"Session {session_id} not found for Cyber {cyber_id}")
        
        session = self.sessions[cyber_id][session_id]
        
        # Update activity
        session.last_activity = datetime.now()
        
        if format == "text":
            # Return clean text
            return {
                'screen': '\n'.join(session.screen_buffer),
                'cursor': session.cursor_position
            }
        elif format == "structured":
            # Return structured data
            return {
                'screen': '\n'.join(session.screen_buffer),
                'lines': session.screen_buffer,
                'cursor_position': session.cursor_position,
                'terminal_size': session.terminal_size,
                'session_info': {
                    'session_id': session_id,
                    'command': session.command,
                    'name': session.name,
                    'created_at': session.created_at.isoformat(),
                    'is_active': session.is_active
                }
            }
        elif format == "raw":
            # Return raw buffer
            return {
                'buffer': session.screen_buffer,
                'cursor': session.cursor_position,
                'size': session.terminal_size
            }
        else:
            raise ValueError(f"Unknown format: {format}")
    
    async def list_sessions(self, cyber_id: str) -> List[Dict[str, Any]]:
        """List all sessions for a Cyber.
        
        Args:
            cyber_id: ID of the Cyber
            
        Returns:
            List of session information
        """
        if cyber_id not in self.sessions:
            return []
        
        sessions = []
        for session in self.sessions[cyber_id].values():
            sessions.append({
                'session_id': session.session_id,
                'command': session.command,
                'name': session.name,
                'created_at': session.created_at.isoformat(),
                'last_activity': session.last_activity.isoformat(),
                'is_active': session.is_active
            })
        
        return sessions
    
    async def close_session(self, cyber_id: str, session_id: str):
        """Close a terminal session.
        
        Args:
            cyber_id: ID of the Cyber
            session_id: ID of the session
        """
        if cyber_id not in self.sessions or session_id not in self.sessions[cyber_id]:
            raise ValueError(f"Session {session_id} not found for Cyber {cyber_id}")
        
        session = self.sessions[cyber_id][session_id]
        
        try:
            # Cancel read task
            if session_id in self._read_tasks:
                self._read_tasks[session_id].cancel()
                del self._read_tasks[session_id]
            
            # Terminate process
            if session.pid:
                try:
                    os.kill(session.pid, signal.SIGTERM)
                    # Wait briefly for clean exit
                    await asyncio.sleep(0.5)
                    # Force kill if still running
                    try:
                        os.kill(session.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                except ProcessLookupError:
                    pass
            
            # Close master FD
            if session.master_fd:
                try:
                    os.close(session.master_fd)
                except OSError:
                    pass
            
            # Remove session
            del self.sessions[cyber_id][session_id]
            
            # Clean up empty cyber entry
            if not self.sessions[cyber_id]:
                del self.sessions[cyber_id]
            
            logger.info(f"Closed terminal session {session_id} for Cyber {cyber_id}")
            
            # Broadcast event
            await self.coordinator.broadcast_event({
                'type': 'terminal_closed',
                'cyber_id': cyber_id,
                'session_id': session_id
            })
            
        except Exception as e:
            logger.error(f"Failed to close session {cyber_id}/{session_id}: {e}")
            raise
    
    async def handle_terminal_body(self, cyber_id: str, body_path: Path):
        """Process terminal body file requests.
        
        Args:
            cyber_id: ID of the Cyber
            body_path: Path to the terminal body file
        """
        try:
            # Read request
            with open(body_path, 'r') as f:
                data = json.load(f)
            
            request = data.get('request', {})
            action = request.get('action')
            
            response = {'status': 'error', 'message': 'Unknown action'}
            
            if action == 'create':
                # Create new session
                command = request.get('data', {}).get('command', 'bash')
                name = request.get('data', {}).get('name')
                
                session_id = await self.create_session(cyber_id, command, name)
                response = {
                    'status': 'success',
                    'session_id': session_id,
                    'data': {'session_id': session_id}
                }
                
            elif action == 'read':
                # Read screen
                session_id = request.get('session_id')
                format = request.get('data', {}).get('format', 'text')
                
                screen_data = await self.read_screen(cyber_id, session_id, format)
                response = {
                    'status': 'success',
                    'session_id': session_id,
                    'data': screen_data
                }
                
            elif action == 'write':
                # Send input
                session_id = request.get('session_id')
                input_text = request.get('data', {}).get('input', '')
                
                await self.send_input(cyber_id, session_id, input_text)
                response = {
                    'status': 'success',
                    'session_id': session_id,
                    'data': {'sent': True}
                }
                
            elif action == 'list':
                # List sessions
                sessions = await self.list_sessions(cyber_id)
                response = {
                    'status': 'success',
                    'data': {'sessions': sessions}
                }
                
            elif action == 'close':
                # Close session
                session_id = request.get('session_id')
                
                await self.close_session(cyber_id, session_id)
                response = {
                    'status': 'success',
                    'session_id': session_id,
                    'data': {'closed': True}
                }
            
            # Write response
            data['response'] = response
            with open(body_path, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to handle terminal body for {cyber_id}: {e}")
            # Write error response
            try:
                with open(body_path, 'r') as f:
                    data = json.load(f)
                data['response'] = {
                    'status': 'error',
                    'message': str(e)
                }
                with open(body_path, 'w') as f:
                    json.dump(data, f, indent=2)
            except:
                pass
    
    async def _read_terminal_output(self, cyber_id: str, session_id: str):
        """Continuously read output from terminal.
        
        Args:
            cyber_id: ID of the Cyber
            session_id: ID of the session
        """
        session = self.sessions[cyber_id][session_id]
        
        while session.is_active:
            try:
                # Check if data is available
                ready, _, _ = select.select([session.master_fd], [], [], 0.1)
                
                if ready:
                    # Read available data
                    data = os.read(session.master_fd, 4096)
                    
                    if data:
                        # Process output and update screen buffer
                        output = data.decode('utf-8', errors='replace')
                        self._update_screen_buffer(session, output)
                        
                        # Broadcast output event
                        await self.coordinator.broadcast_event({
                            'type': 'terminal_output',
                            'cyber_id': cyber_id,
                            'session_id': session_id,
                            'output': output
                        })
                    else:
                        # Process has exited
                        session.is_active = False
                        break
                        
                await asyncio.sleep(0.1)
                
            except OSError:
                # Terminal closed
                session.is_active = False
                break
            except Exception as e:
                logger.error(f"Error reading terminal output for {cyber_id}/{session_id}: {e}")
                await asyncio.sleep(1)
    
    def _update_screen_buffer(self, session: TerminalSession, output: str):
        """Update terminal screen buffer with new output.
        
        Simple implementation - just appends lines.
        A full implementation would handle ANSI escape sequences.
        """
        lines = output.split('\n')
        
        for line in lines[:-1]:
            # Add line to buffer
            session.screen_buffer.append(line)
            
            # Limit buffer size
            if len(session.screen_buffer) > self.buffer_size:
                session.screen_buffer = session.screen_buffer[-self.buffer_size:]
        
        # Handle partial line
        if lines[-1]:
            if session.screen_buffer:
                session.screen_buffer[-1] += lines[-1]
            else:
                session.screen_buffer.append(lines[-1])
    
    async def _cleanup_loop(self):
        """Periodically cleanup inactive sessions."""
        while True:
            try:
                await asyncio.sleep(300)  # 5 minutes
                
                now = datetime.now()
                
                for cyber_id in list(self.sessions.keys()):
                    for session_id in list(self.sessions[cyber_id].keys()):
                        session = self.sessions[cyber_id][session_id]
                        
                        # Check timeout
                        inactive_time = (now - session.last_activity).total_seconds()
                        if inactive_time > self.terminal_timeout:
                            logger.info(f"Closing inactive session {cyber_id}/{session_id}")
                            await self.close_session(cyber_id, session_id)
                        
                        # Check if process is still alive
                        elif session.pid:
                            try:
                                os.kill(session.pid, 0)
                            except ProcessLookupError:
                                logger.info(f"Process died for session {cyber_id}/{session_id}")
                                session.is_active = False
                                await self.close_session(cyber_id, session_id)
                                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")