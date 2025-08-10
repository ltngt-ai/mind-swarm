"""Cyber process manager that starts and manages Cyber processes in sandboxes."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Optional, Any
from uuid import uuid4

import aiofiles

from mind_swarm.subspace.sandbox import BubblewrapSandbox, SubspaceManager
from mind_swarm.utils.logging import logger
# Log rotation now handled inline in personal folders


class AgentProcess:
    """Represents a running Cyber process."""
    
    def __init__(self, name: str, process: asyncio.subprocess.Process, sandbox: BubblewrapSandbox):
        self.name = name
        self.process = process
        self.sandbox = sandbox
        self.log_tasks = []  # Tasks for reading stdout/stderr
        self.start_time = asyncio.get_event_loop().time()
    
    async def is_alive(self) -> bool:
        """Check if the Cyber process is still running."""
        return self.process.returncode is None
    
    async def send_message(self, message: Dict[str, Any]):
        """Send a message to the Cyber via its inbox."""
        msg_id = f"{message.get('from', 'subspace')}_{int(asyncio.get_event_loop().time() * 1000)}"
        message['id'] = msg_id
        
        inbox_dir = self.sandbox.cyber_personal / "comms" / "inbox"
        msg_file = inbox_dir / f"{msg_id}.msg"
        msg_file.write_text(json.dumps(message, indent=2))
        
        logger.debug(f"Sent message {msg_id} to Cyber {self.name}")
    
    async def shutdown(self, timeout: float = 60.0):
        """Shutdown the Cyber process gracefully."""
        logger.info(f"AgentProcess.shutdown() called for {self.name}")
        
        if self.process.returncode is not None:
            logger.info(f"Cyber {self.name} already terminated (returncode={self.process.returncode})")
            return
        
        # First create shutdown file to signal Cyber to exit gracefully
        shutdown_file = self.sandbox.cyber_personal / ".internal" / "shutdown"
        try:
            shutdown_file.write_text("SHUTDOWN")
            logger.info(f"Created shutdown file for Cyber {self.name}")
        except Exception as e:
            logger.error(f"Failed to create shutdown file for {self.name}: {e}")
        
        # Wait for Cyber to exit gracefully
        try:
            logger.info(f"Waiting up to {timeout}s for Cyber {self.name} to exit gracefully...")
            await asyncio.wait_for(self.process.wait(), timeout=timeout)
            logger.info(f"Cyber {self.name} exited gracefully")
            return
        except asyncio.TimeoutError:
            # If Cyber didn't exit, try terminating the process
            logger.warning(f"Cyber {self.name} didn't exit after {timeout}s, sending SIGTERM...")
            self.process.terminate()
        
        # Give it another moment to stop after SIGTERM
        try:
            await asyncio.wait_for(self.process.wait(), timeout=10.0)
            logger.info(f"Cyber {self.name} stopped after SIGTERM")
        except asyncio.TimeoutError:
            # Force stop if still not responding
            logger.warning(f"Cyber {self.name} still not responding, forcing stop...")
            
            # Try multiple kill strategies for bubblewrap
            import os
            import signal
            import subprocess
            
            pid = self.process.pid
            logger.info(f"Force stopping Cyber {self.name} (PID: {pid}) with multiple strategies")
            
            try:
                # Strategy 1: Kill process group
                pgid = os.getpgid(pid)
                logger.info(f"Strategy 1: Killing process group {pgid}")
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                logger.info(f"Process {pid} already stopped")
            except Exception as e:
                logger.error(f"Strategy 1 failed: {e}")
            
            try:
                # Strategy 2: Kill entire process tree including bwrap
                logger.info(f"Strategy 2: Killing entire process tree for PID {pid}")
                # First kill all children of the bwrap process
                subprocess.run(['pkill', '-KILL', '-P', str(pid)], check=False)
                # Then kill the bwrap process itself
                subprocess.run(['kill', '-KILL', str(pid)], check=False)
                # Also try to kill any processes that match the Cyber name pattern
                subprocess.run(['pkill', '-KILL', '-f', f'CYBER_NAME {self.name}'], check=False)
                subprocess.run(['pkill', '-KILL', '-f', f'bwrap.*{self.name}'], check=False)
            except Exception as e:
                logger.error(f"Strategy 2 failed: {e}")
            
            try:
                # Strategy 3: Regular asyncio kill
                logger.info(f"Strategy 3: Using process.kill()")
                self.process.kill()
            except Exception as e:
                logger.error(f"Strategy 3 failed: {e}")
            
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
                logger.info(f"Cyber {self.name} stopped (forced)")
            except asyncio.TimeoutError:
                logger.error(f"Failed to stop Cyber {self.name} - process may be unresponsive")
        
        # Close stdout/stderr to unblock any readers
        if self.process.stdout:
            try:
                self.process.stdout.close()
            except:
                pass
        if self.process.stderr:
            try:
                self.process.stderr.close()
            except:
                pass
        
        # Cancel log tasks
        logger.info(f"Cancelling {len(self.log_tasks)} log tasks for {self.name}")
        for task in self.log_tasks:
            if not task.done():
                task.cancel()
                # Don't wait for the tasks - they might be blocked on readline
        logger.info(f"AgentProcess.shutdown() complete for {self.name}")
    
    async def terminate(self, timeout: float = 5.0):
        """Terminate (kill) the Cyber process for deletion - no graceful shutdown."""
        logger.info(f"AgentProcess.terminate() called for {self.name}")
        
        if self.process.returncode is not None:
            logger.info(f"Cyber {self.name} already terminated (returncode={self.process.returncode})")
            return
        
        # For termination (deletion), we kill immediately without graceful shutdown
        logger.info(f"Force terminating Cyber {self.name} (deletion)")
        
        # Use improved kill strategies for bubblewrap
        import os
        import signal
        import subprocess
        
        pid = self.process.pid
        logger.info(f"Force terminating Cyber {self.name} (PID: {pid}) with multiple strategies")
        
        try:
            # Strategy 1: Kill process group
            pgid = os.getpgid(pid)
            logger.info(f"Strategy 1: Killing process group {pgid}")
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            logger.info(f"Process {pid} already stopped")
        except Exception as e:
            logger.error(f"Strategy 1 failed: {e}")
        
        try:
            # Strategy 2: Kill entire process tree including bwrap
            logger.info(f"Strategy 2: Killing entire process tree for PID {pid}")
            # First kill all children of the bwrap process
            subprocess.run(['pkill', '-KILL', '-P', str(pid)], check=False)
            # Then kill the bwrap process itself
            subprocess.run(['kill', '-KILL', str(pid)], check=False)
            # Also try to kill any processes that match the Cyber name pattern
            subprocess.run(['pkill', '-KILL', '-f', f'CYBER_NAME {self.name}'], check=False)
            subprocess.run(['pkill', '-KILL', '-f', f'bwrap.*{self.name}'], check=False)
        except Exception as e:
            logger.error(f"Strategy 2 failed: {e}")
        
        try:
            # Strategy 3: Regular asyncio kill
            logger.info(f"Strategy 3: Using process.kill()")
            self.process.kill()
        except Exception as e:
            logger.error(f"Strategy 3 failed: {e}")
        
        try:
            await asyncio.wait_for(self.process.wait(), timeout=5.0)
            logger.info(f"Cyber {self.name} terminated (forced)")
        except asyncio.TimeoutError:
            logger.error(f"Failed to terminate Cyber {self.name} - process may be unresponsive")
        
        # Close stdout/stderr to unblock any readers
        if self.process.stdout:
            try:
                self.process.stdout.close()
            except:
                pass
        if self.process.stderr:
            try:
                self.process.stderr.close()
            except:
                pass
        
        # Cancel log tasks
        logger.info(f"Cancelling {len(self.log_tasks)} log tasks for {self.name}")
        for task in self.log_tasks:
            if not task.done():
                task.cancel()
                # Don't wait for the tasks - they might be blocked on readline
        
        logger.info(f"AgentProcess.terminate() complete for {self.name}")


class AgentProcessManager:
    """Manages starting and stopping Cyber processes."""
    
    def __init__(self, subspace_manager: SubspaceManager):
        self.subspace = subspace_manager
        self.cybers: Dict[str, AgentProcess] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Cyber will be launched from the runtime directory
        self.runtime_launcher = None
        
        # Log rotator is no longer used - logs go to personal folders
        self.log_rotator = None
        
    async def start_agent(
        self,
        name: str,  # Required now
        cyber_type: str = "general",
        config: Optional[Dict[str, Any]] = None
    ) -> str:
        """Start an Cyber process.
        
        Args:
            name: Cyber name (required, must be unique)
            cyber_type: Type of Cyber (general, io_gateway)
            config: Cyber configuration including AI settings
            
        Returns:
            Cyber name
        """
        # Create sandbox using name and type
        sandbox = self.subspace.create_sandbox(name, cyber_type)
        
        # Write Cyber configuration
        cyber_config = {
            "name": name,
            "type": cyber_type,
            **(config or {})
        }
        config_file = sandbox.cyber_personal / ".internal" / "config.json"
        config_file.write_text(json.dumps(cyber_config, indent=2))
        
        # Prepare environment
        env = {
            "CYBER_NAME": name,
            "CYBER_TYPE": cyber_type,
            "PYTHONPATH": str(Path(__file__).parent.parent.parent),
        }
        
        # Clean up any leftover shutdown file from previous runs
        shutdown_file = sandbox.cyber_personal / ".internal" / "shutdown"
        if shutdown_file.exists():
            shutdown_file.unlink()
            logger.debug(f"Removed old shutdown file for {name}")
        
        # Launch Cyber process in sandbox
        logger.info(f"Starting Cyber process for {name}")
        
        # Build command to run Cyber from its base_code directory
        # The Cyber code is in /home/base_code when viewed from inside sandbox
        # Launch appropriate module based on Cyber type
        # All Cybers run from base_code directory
        cmd = ["python3", "-m", "base_code"]
        
        # Use sandbox to run the Cyber
        bwrap_cmd = sandbox._build_bwrap_cmd(cmd, env)
        
        # Start the process with a new process group
        process = await asyncio.create_subprocess_exec(
            *bwrap_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True  # This creates a new process group
        )
        
        # Track the Cyber
        agent_process = AgentProcess(name, process, sandbox)
        self.cybers[name] = agent_process
        
        # Set up logging for the Cyber
        await self._setup_agent_logging(agent_process)
        
        # Start monitoring if not already running
        if not self._monitor_task or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self._monitor_agents())
        
        logger.info(f"Cyber {name} process started with PID {process.pid}")
        return name
    
    async def shutdown_agent(self, name: str, timeout: float = 60.0):
        """Shutdown an Cyber process gracefully."""
        logger.info(f"shutdown_agent called for {name} with timeout={timeout}")
        
        if name not in self.cybers:
            logger.warning(f"Cyber {name} not found")
            return
        
        logger.info(f"Shutting down Cyber {name}")
        Cyber = self.cybers[name]
        
        logger.info(f"Calling Cyber.shutdown() for {name}")
        try:
            await Cyber.shutdown(timeout)
            logger.info(f"Cyber.shutdown() completed for {name}")
        except Exception as e:
            logger.error(f"Error shutting down Cyber {name}: {e}", exc_info=True)
        
        # Clean up
        logger.info(f"Removing {name} from Cybers dict")
        if name in self.cybers:  # Double check in case monitor removed it
            del self.cybers[name]
        
        logger.info(f"Removing sandbox for {name}")
        try:
            self.subspace.remove_sandbox(name)
            logger.info(f"Sandbox removed for {name}")
        except Exception as e:
            logger.error(f"Error removing sandbox for {name}: {e}")
        
        logger.info(f"shutdown_agent completed for {name}")
    
    async def terminate_agent(self, name: str, timeout: float = 5.0):
        """Terminate (delete) an Cyber process permanently."""
        logger.info(f"terminate_agent called for {name} with timeout={timeout}")
        
        if name not in self.cybers:
            logger.warning(f"Cyber {name} not found")
            return
        
        logger.info(f"Terminating Cyber {name}")
        Cyber = self.cybers[name]
        
        logger.info(f"Calling Cyber.terminate() for {name}")
        try:
            await Cyber.terminate(timeout)
            logger.info(f"Cyber.terminate() completed for {name}")
        except Exception as e:
            logger.error(f"Error terminating Cyber {name}: {e}", exc_info=True)
        
        # Clean up
        logger.info(f"Removing {name} from Cybers dict")
        if name in self.cybers:  # Double check in case monitor removed it
            del self.cybers[name]
        
        logger.info(f"Removing sandbox for {name}")
        try:
            self.subspace.remove_sandbox(name)
            logger.info(f"Sandbox removed for {name}")
        except Exception as e:
            logger.error(f"Error removing sandbox for {name}: {e}")
        
        logger.info(f"terminate_agent completed for {name}")
    
    async def send_message_to_agent(self, name: str, message: Dict[str, Any]):
        """Send a message to a specific Cyber."""
        if name not in self.cybers:
            logger.error(f"Cyber {name} not found")
            return
        
        await self.cybers[name].send_message(message)
    
    async def broadcast_message(self, message: Dict[str, Any], exclude: Optional[list] = None):
        """Broadcast a message to all Cybers."""
        exclude = exclude or []
        for name, Cyber in self.cybers.items():
            if name not in exclude:
                await Cyber.send_message(message)
    
    async def get_cyber_states(self) -> Dict[str, Dict[str, Any]]:
        """Get the current state of all Cybers."""
        states = {}
        
        for name, Cyber in self.cybers.items():
            # Check heartbeat file
            heartbeat_file = Cyber.sandbox.cyber_personal / ".internal" / "heartbeat.json"
            if heartbeat_file.exists():
                try:
                    async with aiofiles.open(heartbeat_file, 'r') as f:
                        content = await f.read()
                    heartbeat = json.loads(content)
                    states[name] = {
                        "name": name,
                        "alive": await Cyber.is_alive(),
                        "state": heartbeat.get("state", "UNKNOWN"),
                        "last_heartbeat": heartbeat.get("timestamp", 0),
                        "pid": heartbeat.get("pid"),
                        "uptime": asyncio.get_event_loop().time() - Cyber.start_time
                    }
                except Exception as e:
                    logger.error(f"Error reading heartbeat for {name}: {e}")
            else:
                states[name] = {
                    "name": name,
                    "alive": await Cyber.is_alive(),
                    "state": "NO_HEARTBEAT",
                    "uptime": asyncio.get_event_loop().time() - Cyber.start_time
                }
        
        return states
    
    async def _monitor_agents(self):
        """Monitor Cyber processes and restart if needed."""
        while self.cybers:
            try:
                # Check each Cyber
                dead_agents = []
                for name, Cyber in self.cybers.items():
                    if not await Cyber.is_alive():
                        logger.warning(f"Cyber {name} stopped unexpectedly (exit code: {Cyber.process.returncode})")
                        
                        # Try to get stderr output
                        if Cyber.process.stderr:
                            try:
                                stderr_output = await Cyber.process.stderr.read()
                                if stderr_output:
                                    logger.error(f"Cyber {name} stderr:\n{stderr_output.decode('utf-8', errors='replace')}")
                            except:
                                pass
                        
                        dead_agents.append(name)
                
                # Clean up dead Cybers
                for name in dead_agents:
                    del self.cybers[name]
                    # TODO: Optionally restart Cybers based on configuration
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in Cyber monitor: {e}")
                await asyncio.sleep(5)
    
    async def shutdown_all(self, timeout: float = 60.0):
        """Shutdown all Cybers gracefully."""
        logger.info("Shutting down all Cybers...")
        
        # Cancel monitor task first to prevent interference
        if self._monitor_task and not self._monitor_task.done():
            logger.info("Cancelling Cyber monitor task...")
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            logger.info("Cyber monitor task cancelled")
        
        # Send shutdown to all Cybers
        shutdown_tasks = []
        for name in list(self.cybers.keys()):
            shutdown_tasks.append(self.shutdown_agent(name, timeout))
        
        # Wait for all to complete
        if shutdown_tasks:
            logger.info(f"Waiting for {len(shutdown_tasks)} Cybers to shutdown...")
            results = await asyncio.gather(*shutdown_tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error shutting down Cyber: {result}")
        
        # Final cleanup: kill any remaining bwrap processes
        # This is a safety net in case some processes didn't terminate properly
        import subprocess
        try:
            logger.info("Final cleanup: killing any remaining bwrap processes...")
            # Kill all bwrap processes owned by this user
            result = subprocess.run(['pkill', '-KILL', '-f', 'bwrap'], capture_output=True, text=True)
            if result.returncode == 0:
                logger.warning("Had to force-kill some remaining bwrap processes")
            else:
                logger.info("No remaining bwrap processes found")
        except Exception as e:
            logger.error(f"Error during final bwrap cleanup: {e}")
        
        logger.info("All Cybers shut down")
    
    async def _setup_agent_logging(self, agent_process: AgentProcess):
        """Set up logging tasks for an Cyber process."""
        # Create logs directory in cyber's internal folder
        logs_dir = agent_process.sandbox.cyber_personal / ".internal" / "logs"
        logs_dir.mkdir(exist_ok=True)
        
        # Use fixed log file name for current session
        log_file = logs_dir / "current.log"
        
        # Create tasks to read stdout and stderr
        if agent_process.process.stdout:
            stdout_task = asyncio.create_task(
                self._read_and_log_stream(
                    agent_process.process.stdout,
                    log_file,
                    agent_process.name,
                    "stdout"
                )
            )
            agent_process.log_tasks.append(stdout_task)
        
        if agent_process.process.stderr:
            stderr_task = asyncio.create_task(
                self._read_and_log_stream(
                    agent_process.process.stderr,
                    log_file,
                    agent_process.name,
                    "stderr"
                )
            )
            agent_process.log_tasks.append(stderr_task)
    
    async def _read_and_log_stream(self, stream, log_file: Path, name: str, stream_name: str):
        """Read from a stream and write to log file with rotation support."""
        try:
            current_log_file = log_file
            
            while True:
                try:
                    # Add timeout to prevent blocking forever
                    line = await asyncio.wait_for(stream.readline(), timeout=1.0)
                    if not line:
                        break
                except asyncio.TimeoutError:
                    # Check if process is still alive
                    if name not in self.cybers:
                        logger.debug(f"Cyber {name} no longer exists, stopping log reader")
                        break
                    continue
                
                # Check if we need to rotate the log (10MB limit)
                if current_log_file.exists() and current_log_file.stat().st_size > 10 * 1024 * 1024:
                    # Close current file handle
                    if 'f' in locals():
                        f.close()
                    
                    # Rotate old log with timestamp
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    rotated_file = current_log_file.parent / f"cyber_{timestamp}.log"
                    current_log_file.rename(rotated_file)
                    logger.info(f"Rotated log for Cyber {name} to {rotated_file.name}")
                
                # Open file in append mode (or create if it doesn't exist after rotation)
                with open(current_log_file, 'a') as f:
                    # Decode and write to file
                    text = line.decode('utf-8', errors='replace')
                    f.write(text)
                    f.flush()
                    
                    # Also log important messages to server log
                    if stream_name == "stderr" or "ERROR" in text or "WARNING" in text:
                        logger.info(f"Cyber {name} {stream_name}: {text.strip()}")
                        
        except Exception as e:
            logger.error(f"Error reading {stream_name} for Cyber {name}: {e}")


# Keep CyberSpawner as an alias for backward compatibility during transition
CyberSpawner = AgentProcessManager