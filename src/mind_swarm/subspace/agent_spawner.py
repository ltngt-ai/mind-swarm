"""Agent spawner that launches agents as separate processes in sandboxes."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Optional, Any
from uuid import uuid4

from mind_swarm.subspace.sandbox import BubblewrapSandbox, SubspaceManager
from mind_swarm.utils.logging import logger


class AgentProcess:
    """Represents a running agent process."""
    
    def __init__(self, agent_id: str, process: asyncio.subprocess.Process, sandbox: BubblewrapSandbox):
        self.agent_id = agent_id
        self.process = process
        self.sandbox = sandbox
        self.log_tasks = []  # Tasks for reading stdout/stderr
        self.start_time = asyncio.get_event_loop().time()
    
    async def is_alive(self) -> bool:
        """Check if the agent process is still running."""
        return self.process.returncode is None
    
    async def send_message(self, message: Dict[str, Any]):
        """Send a message to the agent via its inbox."""
        msg_id = f"{message.get('from', 'subspace')}_{int(asyncio.get_event_loop().time() * 1000)}"
        message['id'] = msg_id
        
        inbox_dir = self.sandbox.agent_home / "inbox"
        msg_file = inbox_dir / f"{msg_id}.msg"
        msg_file.write_text(json.dumps(message, indent=2))
        
        logger.debug(f"Sent message {msg_id} to agent {self.agent_id}")
    
    async def terminate(self, timeout: float = 5.0):
        """Gracefully terminate the agent."""
        # Send shutdown message
        await self.send_message({
            "type": "SHUTDOWN",
            "from": "subspace",
            "reason": "Termination requested"
        })
        
        # Wait for graceful shutdown
        try:
            await asyncio.wait_for(self.process.wait(), timeout=timeout)
            logger.info(f"Agent {self.agent_id} terminated gracefully")
        except asyncio.TimeoutError:
            logger.warning(f"Agent {self.agent_id} didn't shutdown gracefully, forcing...")
            self.process.terminate()
            await self.process.wait()
        
        # Cancel log tasks
        for task in self.log_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass


class AgentSpawner:
    """Manages spawning agents as separate processes."""
    
    def __init__(self, subspace_manager: SubspaceManager):
        self.subspace = subspace_manager
        self.agents: Dict[str, AgentProcess] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Agent will be launched from the runtime directory
        self.runtime_launcher = None
        
    async def spawn_agent(
        self,
        name: Optional[str] = None,
        agent_type: str = "general",
        config: Optional[Dict[str, Any]] = None
    ) -> str:
        """Spawn a new AI agent process.
        
        Args:
            name: Agent name (auto-generated if not provided)
            agent_type: Ignored, kept for compatibility
            config: Agent configuration including AI settings
            
        Returns:
            Agent ID
        """
        # Generate agent ID
        agent_id = f"agent-{uuid4().hex[:8]}"
        
        # Create sandbox
        sandbox = self.subspace.create_sandbox(agent_id)
        
        # Write agent configuration
        agent_config = {
            "id": agent_id,
            "name": name or f"Agent-{agent_id[-4:]}",
            "type": agent_type,
            **(config or {})
        }
        config_file = sandbox.agent_home / "config.json"
        config_file.write_text(json.dumps(agent_config, indent=2))
        
        # Prepare environment
        env = {
            "AGENT_ID": agent_id,
            "AGENT_TYPE": agent_type,
            "PYTHONPATH": str(Path(__file__).parent.parent.parent),
        }
        
        # Launch agent process in sandbox
        logger.info(f"Spawning agent {agent_id} ({name or 'unnamed'})")
        
        # Build command to run agent from its base_code directory
        # The agent code is in /home/base_code when viewed from inside sandbox
        cmd = ["python3", "-m", "base_code"]
        
        # Use sandbox to run the agent
        bwrap_cmd = sandbox._build_bwrap_cmd(cmd, env)
        
        # Start the process
        process = await asyncio.create_subprocess_exec(
            *bwrap_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        # Track the agent
        agent_process = AgentProcess(agent_id, process, sandbox)
        self.agents[agent_id] = agent_process
        
        # Set up logging for the agent
        await self._setup_agent_logging(agent_process)
        
        # Start monitoring if not already running
        if not self._monitor_task or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self._monitor_agents())
        
        logger.info(f"Agent {agent_id} spawned with PID {process.pid}")
        return agent_id
    
    async def terminate_agent(self, agent_id: str, timeout: float = 5.0):
        """Terminate an agent process."""
        if agent_id not in self.agents:
            logger.warning(f"Agent {agent_id} not found")
            return
        
        agent = self.agents[agent_id]
        await agent.terminate(timeout)
        
        # Clean up
        del self.agents[agent_id]
        self.subspace.remove_sandbox(agent_id)
    
    async def send_message_to_agent(self, agent_id: str, message: Dict[str, Any]):
        """Send a message to a specific agent."""
        if agent_id not in self.agents:
            logger.error(f"Agent {agent_id} not found")
            return
        
        await self.agents[agent_id].send_message(message)
    
    async def broadcast_message(self, message: Dict[str, Any], exclude: Optional[list] = None):
        """Broadcast a message to all agents."""
        exclude = exclude or []
        for agent_id, agent in self.agents.items():
            if agent_id not in exclude:
                await agent.send_message(message)
    
    async def get_agent_states(self) -> Dict[str, Dict[str, Any]]:
        """Get the current state of all agents."""
        states = {}
        
        for agent_id, agent in self.agents.items():
            # Check heartbeat file
            heartbeat_file = agent.sandbox.agent_home / "heartbeat.json"
            if heartbeat_file.exists():
                try:
                    heartbeat = json.loads(heartbeat_file.read_text())
                    states[agent_id] = {
                        "id": agent_id,
                        "alive": await agent.is_alive(),
                        "state": heartbeat.get("state", "UNKNOWN"),
                        "last_heartbeat": heartbeat.get("timestamp", 0),
                        "pid": heartbeat.get("pid"),
                        "uptime": asyncio.get_event_loop().time() - agent.start_time
                    }
                except Exception as e:
                    logger.error(f"Error reading heartbeat for {agent_id}: {e}")
            else:
                states[agent_id] = {
                    "id": agent_id,
                    "alive": await agent.is_alive(),
                    "state": "NO_HEARTBEAT",
                    "uptime": asyncio.get_event_loop().time() - agent.start_time
                }
        
        return states
    
    async def _monitor_agents(self):
        """Monitor agent processes and restart if needed."""
        while self.agents:
            try:
                # Check each agent
                dead_agents = []
                for agent_id, agent in self.agents.items():
                    if not await agent.is_alive():
                        logger.warning(f"Agent {agent_id} died (exit code: {agent.process.returncode})")
                        
                        # Try to get stderr output
                        if agent.process.stderr:
                            try:
                                stderr_output = await agent.process.stderr.read()
                                if stderr_output:
                                    logger.error(f"Agent {agent_id} stderr:\n{stderr_output.decode('utf-8', errors='replace')}")
                            except:
                                pass
                        
                        dead_agents.append(agent_id)
                
                # Clean up dead agents
                for agent_id in dead_agents:
                    del self.agents[agent_id]
                    # TODO: Optionally restart agents based on configuration
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in agent monitor: {e}")
                await asyncio.sleep(5)
    
    async def shutdown_all(self, timeout: float = 10.0):
        """Shutdown all agents gracefully."""
        logger.info("Shutting down all agents...")
        
        # Send shutdown to all agents
        shutdown_tasks = []
        for agent_id in list(self.agents.keys()):
            shutdown_tasks.append(self.terminate_agent(agent_id, timeout))
        
        # Wait for all to complete
        if shutdown_tasks:
            await asyncio.gather(*shutdown_tasks, return_exceptions=True)
        
        # Cancel monitor task
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
        
        logger.info("All agents shut down")
    
    async def _setup_agent_logging(self, agent_process: AgentProcess):
        """Set up logging tasks for an agent process."""
        # Create logs directory outside the sandbox
        logs_dir = self.subspace.root_path / "logs" / "agents"
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Log file path
        log_file = logs_dir / f"{agent_process.agent_id}.log"
        
        # Create tasks to read stdout and stderr
        if agent_process.process.stdout:
            stdout_task = asyncio.create_task(
                self._read_and_log_stream(
                    agent_process.process.stdout,
                    log_file,
                    agent_process.agent_id,
                    "stdout"
                )
            )
            agent_process.log_tasks.append(stdout_task)
        
        if agent_process.process.stderr:
            stderr_task = asyncio.create_task(
                self._read_and_log_stream(
                    agent_process.process.stderr,
                    log_file,
                    agent_process.agent_id,
                    "stderr"
                )
            )
            agent_process.log_tasks.append(stderr_task)
    
    async def _read_and_log_stream(self, stream, log_file: Path, agent_id: str, stream_name: str):
        """Read from a stream and write to log file."""
        try:
            with open(log_file, 'a') as f:
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    
                    # Decode and write to file
                    text = line.decode('utf-8', errors='replace')
                    f.write(text)
                    f.flush()
                    
                    # Also log important messages to server log
                    if stream_name == "stderr" or "ERROR" in text or "WARNING" in text:
                        logger.info(f"Agent {agent_id} {stream_name}: {text.strip()}")
                        
        except Exception as e:
            logger.error(f"Error reading {stream_name} for agent {agent_id}: {e}")