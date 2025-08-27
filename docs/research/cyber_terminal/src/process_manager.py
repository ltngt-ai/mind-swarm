"""
Process management for terminal sessions.

This module handles spawning, monitoring, and controlling processes
within terminal sessions.
"""

import os
import signal
import subprocess
import threading
import time
from typing import Dict, Optional, List, Callable
import logging
from datetime import datetime

from .exceptions import SessionCreationError, ProcessIOError, InvalidCommandError
from .session import TerminalSession, SessionStatus


logger = logging.getLogger(__name__)


class ProcessManager:
    """Manages process lifecycle for terminal sessions."""
    
    def __init__(self):
        self.active_processes: Dict[str, Dict] = {}
        self.process_monitors: Dict[str, threading.Thread] = {}
        self._shutdown_event = threading.Event()
        
    def spawn_process(self, session: TerminalSession, slave_fd: int) -> int:
        """
        Spawn a process for the terminal session.
        
        Args:
            session: Terminal session configuration
            slave_fd: Slave file descriptor for PTY
            
        Returns:
            Process ID of spawned process
            
        Raises:
            SessionCreationError: If process spawning fails
            InvalidCommandError: If command is invalid
        """
        try:
            # Validate command exists
            command_parts = session.command.split()
            if not command_parts:
                raise InvalidCommandError(session.command, "Empty command")
            
            executable = command_parts[0]
            if not self._is_command_valid(executable):
                raise InvalidCommandError(executable, "Command not found in PATH")
            
            # Fork process
            pid = os.fork()
            
            if pid == 0:
                # Child process
                self._setup_child_process(session, slave_fd)
                
                # Execute command
                try:
                    # Change working directory
                    if session.working_directory:
                        os.chdir(session.working_directory)
                    
                    # Set environment variables
                    env = os.environ.copy()
                    env.update(session.environment)
                    
                    # Execute the command
                    os.execvpe(executable, command_parts, env)
                    
                except Exception as e:
                    logger.error(f"Failed to execute command in child process: {e}")
                    os._exit(1)
            
            else:
                # Parent process
                logger.info(f"Spawned process {pid} for session {session.session_id}")
                
                # Store process information
                self.active_processes[session.session_id] = {
                    'pid': pid,
                    'command': session.command,
                    'started_at': datetime.now(),
                    'status': 'running'
                }
                
                # Start monitoring thread
                self._start_process_monitor(session.session_id, pid)
                
                return pid
                
        except OSError as e:
            raise SessionCreationError(session.command, f"Fork failed: {e}")
    
    def _setup_child_process(self, session: TerminalSession, slave_fd: int):
        """Set up child process environment."""
        try:
            # Create new session
            os.setsid()
            
            # Set controlling terminal
            os.dup2(slave_fd, 0)  # stdin
            os.dup2(slave_fd, 1)  # stdout
            os.dup2(slave_fd, 2)  # stderr
            
            # Close the slave fd as it's now duplicated
            if slave_fd > 2:
                os.close(slave_fd)
            
            # Set terminal environment variables
            os.environ['TERM'] = 'xterm-256color'
            os.environ['COLUMNS'] = str(session.terminal_size[1])
            os.environ['LINES'] = str(session.terminal_size[0])
            
        except OSError as e:
            logger.error(f"Failed to set up child process: {e}")
            os._exit(1)
    
    def _is_command_valid(self, command: str) -> bool:
        """Check if command exists and is executable."""
        try:
            # Check if it's an absolute path
            if os.path.isabs(command):
                return os.path.isfile(command) and os.access(command, os.X_OK)
            
            # Search in PATH
            for path_dir in os.environ.get('PATH', '').split(os.pathsep):
                if path_dir:
                    full_path = os.path.join(path_dir, command)
                    if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                        return True
            
            return False
            
        except Exception:
            return False
    
    def _start_process_monitor(self, session_id: str, pid: int):
        """Start monitoring thread for process."""
        def monitor_process():
            try:
                while not self._shutdown_event.is_set():
                    try:
                        # Check if process is still alive
                        os.kill(pid, 0)
                        time.sleep(1)  # Check every second
                        
                    except OSError:
                        # Process has terminated
                        logger.info(f"Process {pid} for session {session_id} has terminated")
                        
                        # Get exit status
                        try:
                            _, exit_status = os.waitpid(pid, os.WNOHANG)
                            exit_code = os.WEXITSTATUS(exit_status) if os.WIFEXITED(exit_status) else -1
                        except OSError:
                            exit_code = -1
                        
                        # Update process info
                        if session_id in self.active_processes:
                            self.active_processes[session_id]['status'] = 'terminated'
                            self.active_processes[session_id]['exit_code'] = exit_code
                            self.active_processes[session_id]['terminated_at'] = datetime.now()
                        
                        break
                        
            except Exception as e:
                logger.error(f"Error in process monitor for session {session_id}: {e}")
        
        monitor_thread = threading.Thread(target=monitor_process, daemon=True)
        monitor_thread.start()
        self.process_monitors[session_id] = monitor_thread
    
    def terminate_process(self, session_id: str, force: bool = False) -> bool:
        """
        Terminate process for session.
        
        Args:
            session_id: Session identifier
            force: If True, use SIGKILL instead of SIGTERM
            
        Returns:
            True if termination successful
        """
        process_info = self.active_processes.get(session_id)
        if not process_info:
            return True  # Already terminated
        
        pid = process_info['pid']
        
        try:
            # Send termination signal
            sig = signal.SIGKILL if force else signal.SIGTERM
            os.kill(pid, sig)
            
            logger.info(f"Sent signal {sig} to process {pid} for session {session_id}")
            
            # Wait for process to terminate (with timeout)
            timeout = 5.0  # 5 seconds
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    os.kill(pid, 0)  # Check if still alive
                    time.sleep(0.1)
                except OSError:
                    # Process terminated
                    break
            else:
                # Timeout - force kill if we used SIGTERM
                if not force:
                    logger.warning(f"Process {pid} didn't terminate gracefully, force killing")
                    os.kill(pid, signal.SIGKILL)
            
            return True
            
        except OSError as e:
            if e.errno == 3:  # ESRCH - No such process
                logger.info(f"Process {pid} for session {session_id} already terminated")
                return True
            
            logger.error(f"Failed to terminate process {pid} for session {session_id}: {e}")
            return False
    
    def is_process_alive(self, session_id: str) -> bool:
        """Check if process is still alive."""
        process_info = self.active_processes.get(session_id)
        if not process_info:
            return False
        
        if process_info['status'] == 'terminated':
            return False
        
        pid = process_info['pid']
        
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    
    def get_process_info(self, session_id: str) -> Optional[Dict]:
        """Get process information for session."""
        return self.active_processes.get(session_id)
    
    def reconnect_process(self, session_id: str, process_id: int) -> bool:
        """
        Reconnect to an existing process.
        
        Args:
            session_id: Session identifier
            process_id: Process ID to reconnect to
            
        Returns:
            True if reconnection successful
        """
        try:
            # Verify process is still alive
            try:
                os.kill(process_id, 0)
            except (OSError, ProcessLookupError):
                logger.warning(f"Process {process_id} is no longer alive")
                return False
            
            # Store process information
            self.active_processes[session_id] = {
                'pid': process_id,
                'command': 'reconnected',
                'started_at': datetime.now(),
                'status': 'running',
                'reconnected': True
            }
            
            # Start monitoring thread
            self._start_process_monitor(session_id, process_id)
            
            logger.info(f"Reconnected to process {process_id} for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reconnect to process {process_id}: {e}")
            return False
    
    def list_active_processes(self) -> List[str]:
        """Get list of session IDs with active processes."""
        active = []
        for session_id, info in self.active_processes.items():
            if info['status'] == 'running' and self.is_process_alive(session_id):
                active.append(session_id)
        return active
    
    def get_process_stats(self, session_id: str) -> Dict:
        """Get process statistics (CPU, memory usage)."""
        process_info = self.active_processes.get(session_id)
        if not process_info:
            return {}
        
        pid = process_info['pid']
        
        try:
            # Read from /proc/pid/stat for basic stats
            with open(f'/proc/{pid}/stat', 'r') as f:
                stat_data = f.read().split()
            
            # Read memory info from /proc/pid/status
            memory_kb = 0
            try:
                with open(f'/proc/{pid}/status', 'r') as f:
                    for line in f:
                        if line.startswith('VmRSS:'):
                            memory_kb = int(line.split()[1])
                            break
            except (IOError, ValueError):
                pass
            
            return {
                'pid': pid,
                'memory_usage': memory_kb * 1024,  # Convert to bytes
                'cpu_usage': 0.0,  # Would need more complex calculation
                'status': process_info['status'],
                'started_at': process_info['started_at']
            }
            
        except (IOError, ValueError, IndexError):
            return {
                'pid': pid,
                'memory_usage': 0,
                'cpu_usage': 0.0,
                'status': process_info['status'],
                'started_at': process_info['started_at']
            }
    
    def cleanup_session(self, session_id: str):
        """Clean up process resources for session."""
        # Terminate process if still running
        if self.is_process_alive(session_id):
            self.terminate_process(session_id, force=True)
        
        # Clean up tracking data
        if session_id in self.active_processes:
            del self.active_processes[session_id]
        
        if session_id in self.process_monitors:
            # Monitor thread will exit when process terminates
            del self.process_monitors[session_id]
        
        logger.info(f"Cleaned up process resources for session {session_id}")
    
    def shutdown(self):
        """Shutdown process manager and clean up all processes."""
        self._shutdown_event.set()
        
        # Don't automatically terminate processes - they should persist
        # Only clean up tracking data
        logger.info("Process manager shutdown complete")
    
    def __del__(self):
        """Cleanup on destruction."""
        self.shutdown()

