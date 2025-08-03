"""Sandbox implementation using bubblewrap for agent isolation."""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any

from mind_swarm.core.config import settings
from mind_swarm.utils.logging import logger


class BubblewrapSandbox:
    """Manages sandboxed agent execution using bubblewrap."""
    
    def __init__(self, name: str, subspace_root: Path, agent_type: str = "general"):
        """Initialize sandbox for an agent.
        
        Args:
            name: Unique name for the agent
            subspace_root: Root directory of the subspace
            agent_type: Type of agent (general, io_gateway)
        """
        self.name = name
        self.subspace_root = subspace_root
        self.agent_home = subspace_root / "agents" / name
        self.grid_root = subspace_root / "grid"
        self.tools_dir = subspace_root / "grid" / "workshop"
        self.agent_type = agent_type
        
        # Ensure directories exist
        self.agent_home.mkdir(parents=True, exist_ok=True)
        self.grid_root.mkdir(parents=True, exist_ok=True)
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        
        # Create Grid structure
        (self.grid_root / "plaza").mkdir(exist_ok=True)
        (self.grid_root / "library").mkdir(exist_ok=True)
        (self.grid_root / "bulletin").mkdir(exist_ok=True)
    
    def _build_bwrap_cmd(self, cmd: List[str], env: Optional[Dict[str, str]] = None) -> List[str]:
        """Build bubblewrap command with proper isolation.
        
        Args:
            cmd: Command to run inside sandbox
            env: Environment variables to pass
            
        Returns:
            Complete bubblewrap command
        """
        bwrap_cmd = [
            "bwrap",
            # Create new namespaces
            "--unshare-all",
            # No network access - agents think through body files
            
            # Create a minimal root filesystem
            # Only bind what's absolutely necessary for Python to run
            "--ro-bind", "/usr/bin/python3", "/usr/bin/python3",
            
            # Bind only the specific Python libraries we need
            "--ro-bind", "/usr/lib/python3", "/usr/lib/python3",
            "--ro-bind", "/usr/lib/python3.12", "/usr/lib/python3.12",
            
            # Minimal system libraries needed by Python
            "--ro-bind", "/lib", "/lib",
            "--ro-bind", "/lib64", "/lib64",
            
            # Create empty directories to provide structure
            "--dir", "/usr",
            "--dir", "/usr/bin",
            "--dir", "/bin",
            
            # Only bind the absolute essentials
            "--ro-bind", "/bin/sh", "/bin/sh",  # Basic shell for subprocess
            
            # Proc and dev
            "--proc", "/proc",
            "--dev", "/dev",
            
            # Their Mind - their private space (just "home" to them)
            "--bind", str(self.agent_home), "/home",
            
            # The Grid - where agents meet and collaborate
            "--bind", str(self.grid_root), "/grid",
            
            # Grid tools are part of the workshop
            "--ro-bind", str(self.tools_dir), "/grid/workshop",
            
            # Temp directory
            "--tmpfs", "/tmp",
            
            # Set working directory to home
            "--chdir", "/home",
            
            # Clean environment
            "--setenv", "AGENT_NAME", self.name,
            "--setenv", "HOME", "/home",
            "--setenv", "PATH", "/grid/workshop:/usr/bin:/bin",
            "--setenv", "PYTHONPATH", "/home",
            "--setenv", "AGENT_TYPE", self.agent_type,
        ]
        
        # Add special body files for I/O agents
        if self.agent_type == "io_gateway":
            io_bodies_dir = self.agent_home / ".io_bodies"
            io_bodies_dir.mkdir(exist_ok=True)
            
            # Create body files if they don't exist
            network_file = io_bodies_dir / "network"
            if not network_file.exists():
                network_file.write_text("")
            
            user_io_file = io_bodies_dir / "user_io"
            if not user_io_file.exists():
                user_io_file.write_text("")
            
            # Bind special body files
            bwrap_cmd.extend([
                "--bind", str(network_file), "/home/network",
                "--bind", str(user_io_file), "/home/user_io",
            ])
        
        # Add custom environment variables
        if env:
            for key, value in env.items():
                bwrap_cmd.extend(["--setenv", key, value])
        
        # Add the actual command
        bwrap_cmd.extend(["--"] + cmd)
        
        return bwrap_cmd
    
    async def run_command(
        self,
        cmd: List[str],
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> tuple[int, str, str]:
        """Run a command in the sandbox.
        
        Args:
            cmd: Command to execute
            env: Environment variables
            timeout: Execution timeout in seconds
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        bwrap_cmd = self._build_bwrap_cmd(cmd, env)
        
        logger.debug(f"Running sandboxed command for {self.agent_id}: {' '.join(cmd)}")
        
        proc = None  # Ensure proc is always defined
        try:
            proc = await asyncio.create_subprocess_exec(
                *bwrap_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout or settings.subspace.agent_cpu_limit_percent,
            )
            
            return proc.returncode or 0, stdout.decode(), stderr.decode()
            
        except asyncio.TimeoutError:
            logger.warning(f"Command timed out for agent {self.agent_id}")
            if proc:
                proc.terminate()
                await proc.wait()
            return -1, "", "Command timed out"
        except Exception as e:
            logger.error(f"Error running sandboxed command: {e}")
            return -1, "", str(e)
    
    async def run_python_code(self, code: str, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Run Python code in the sandbox.
        
        Args:
            code: Python code to execute
            timeout: Execution timeout
            
        Returns:
            Dictionary with execution results
        """
        # Write code to temporary file
        code_file = self.agent_home / ".tmp_code.py"
        code_file.write_text(code)
        
        # Run the code
        returncode, stdout, stderr = await self.run_command(
            ["python3", "/home/agent/.tmp_code.py"],
            timeout=timeout,
        )
        
        # Clean up
        code_file.unlink(missing_ok=True)
        
        return {
            "success": returncode == 0,
            "stdout": stdout,
            "stderr": stderr,
            "returncode": returncode,
        }
    
    def cleanup(self):
        """Clean up sandbox resources."""
        # Note: We don't delete agent_home as it contains persistent data
        # Only clean temporary files
        for tmp_file in self.agent_home.glob(".tmp_*"):
            tmp_file.unlink(missing_ok=True)


class SubspaceManager:
    """Manages the entire subspace environment."""
    
    def __init__(self, root_path: Optional[Path] = None):
        """Initialize the subspace manager.
        
        Args:
            root_path: Root directory for subspace (defaults to settings)
        """
        self.root_path = root_path or settings.subspace.root_path
        logger.info(f"SubspaceManager initializing with root_path: {self.root_path}")
        self.root_path.mkdir(parents=True, exist_ok=True)
        
        # Create standard directories
        self.agents_dir = self.root_path / "agents"
        self.grid_dir = self.root_path / "grid"
        self.runtime_dir = self.root_path / "runtime"
        
        # Grid subdirectories
        self.plaza_dir = self.grid_dir / "plaza"  # Questions and discussions
        self.library_dir = self.grid_dir / "library"  # Shared knowledge
        self.workshop_dir = self.grid_dir / "workshop"  # Tools
        self.bulletin_dir = self.grid_dir / "bulletin"  # Announcements
        
        for directory in [
            self.agents_dir,
            self.grid_dir,
            self.plaza_dir,
            self.library_dir,
            self.workshop_dir,
            self.bulletin_dir,
            self.runtime_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)
        
        self.sandboxes: Dict[str, BubblewrapSandbox] = {}
        
        # Prepare the agent runtime environment
        from mind_swarm.subspace.runtime_builder import AgentRuntimeBuilder
        self.runtime_builder = AgentRuntimeBuilder(self.root_path)
        self.runtime_builder.prepare_runtime()
        self.runtime_builder.create_tools_directory()
        
        logger.info(f"Initialized subspace at {self.root_path}")
    
    def create_sandbox(self, name: str, agent_type: str = "general") -> BubblewrapSandbox:
        """Create a sandbox for an agent.
        
        Args:
            name: Unique agent name
            agent_type: Type of agent (general, io_gateway)
            
        Returns:
            Configured sandbox instance
        """
        # Check if agent already exists (on disk or in memory)
        agent_exists = name in self.sandboxes or (self.agents_dir / name).exists()
        
        if name in self.sandboxes:
            # Agent already in memory
            sandbox = self.sandboxes[name]
        else:
            # Create new sandbox instance
            sandbox = BubblewrapSandbox(name, self.root_path, agent_type)
            self.sandboxes[name] = sandbox
        
        # For existing agents, update their base_code
        if agent_exists:
            base_code = sandbox.agent_home / "base_code"
            if base_code.exists():
                logger.info(f"Updating base_code for existing agent {name}")
                self._copy_agent_base_code(base_code, agent_type)
            return sandbox
        
        # Initialize agent directories
        inbox = sandbox.agent_home / "inbox"
        outbox = sandbox.agent_home / "outbox"
        drafts = sandbox.agent_home / "drafts"
        memory = sandbox.agent_home / "memory"
        base_code = sandbox.agent_home / "base_code"
        
        for directory in [inbox, outbox, drafts, memory, base_code]:
            directory.mkdir(exist_ok=True)
        
        # Copy agent code to base_code directory
        self._copy_agent_base_code(base_code, agent_type)
        
        logger.info(f"Created sandbox for agent {name}")
        return sandbox
    
    def remove_sandbox(self, name: str):
        """Remove a sandbox and clean up resources.
        
        Args:
            name: Agent name
        """
        if name in self.sandboxes:
            self.sandboxes[name].cleanup()
            del self.sandboxes[name]
            logger.info(f"Removed sandbox for agent {name}")
    
    def _copy_agent_base_code(self, base_code_dir: Path, agent_type: str = "general"):
        """Copy agent base code to the agent's home directory.
        
        Args:
            base_code_dir: The base_code directory in agent's home
            agent_type: Type of agent (general, io_gateway)
        """
        # Choose template based on agent type
        if agent_type == "io_gateway":
            template_dir = self.runtime_dir / "io_agent_template"
        else:
            template_dir = self.runtime_dir / "base_code_template"
        
        if template_dir.exists():
            # Copy entire directory structure from template
            import shutil
            
            # For I/O agents, first copy base template as dependency
            if agent_type == "io_gateway":
                base_template = self.runtime_dir / "base_code_template"
                if base_template.exists():
                    # Create base_code_template subdirectory
                    base_dest = base_code_dir / "base_code_template"
                    if base_dest.exists():
                        shutil.rmtree(base_dest)
                    shutil.copytree(base_template, base_dest)
                    logger.debug("Copied base_code_template for I/O agent")
            
            # First copy all .py files in the root
            for py_file in template_dir.glob("*.py"):
                dst_file = base_code_dir / py_file.name
                shutil.copy2(py_file, dst_file)
                logger.debug(f"Copied {py_file.name} to agent base_code")
            
            # Then copy all subdirectories
            for subdir in template_dir.iterdir():
                if subdir.is_dir() and not subdir.name.startswith('.'):
                    dst_subdir = base_code_dir / subdir.name
                    if dst_subdir.exists():
                        shutil.rmtree(dst_subdir)
                    shutil.copytree(subdir, dst_subdir)
                    logger.debug(f"Copied directory {subdir.name} to agent base_code")
        else:
            # Fallback: copy directly from source
            src_dir = Path(__file__).parent.parent / "agent_sandbox"
            if src_dir.exists():
                import shutil
                for py_file in src_dir.glob("*.py"):
                    dst_file = base_code_dir / py_file.name
                    shutil.copy2(py_file, dst_file)
                    logger.debug(f"Copied {py_file.name} to agent base_code")
            else:
                logger.error("No agent base code found to copy!")
    
    async def check_bubblewrap(self) -> bool:
        """Check if bubblewrap is installed and available.
        
        Returns:
            True if bubblewrap is available
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "bwrap", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return proc.returncode == 0
        except FileNotFoundError:
            logger.error("Bubblewrap (bwrap) not found. Please install it.")
            return False