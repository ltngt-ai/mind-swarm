"""Sandbox implementation using bubblewrap for Cyber isolation."""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any

from mind_swarm.core.config import settings
from mind_swarm.utils.logging import logger


class BubblewrapSandbox:
    """Manages sandboxed Cyber execution using bubblewrap."""
    
    def __init__(self, name: str, subspace_root: Path, cyber_type: str = "general"):
        """Initialize sandbox for an Cyber.
        
        Args:
            name: Unique name for the Cyber
            subspace_root: Root directory of the subspace
            cyber_type: Type of Cyber (general, io_gateway)
        """
        self.name = name
        self.subspace_root = subspace_root
        self.cyber_personal = subspace_root / "cybers" / name
        self.grid_root = subspace_root / "grid"
        self.tools_dir = subspace_root / "grid" / "workshop"
        self.cyber_type = cyber_type
        
        # Ensure directories exist
        self.cyber_personal.mkdir(parents=True, exist_ok=True)
        self.grid_root.mkdir(parents=True, exist_ok=True)
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        
        # Create Grid structure
        (self.grid_root / "community").mkdir(exist_ok=True)
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
            # Die when parent process dies - prevents zombie processes
            "--die-with-parent",
            # Create new namespaces
            "--unshare-all",
            # No network access - Cybers think through body files
            
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
            "--bind", str(self.cyber_personal), "/personal",
            
            # The Grid - where Cybers meet and collaborate
            "--bind", str(self.grid_root), "/grid",
            
            # Grid tools are part of the workshop
            "--ro-bind", str(self.tools_dir), "/grid/workshop",
            
            # Temp directory
            "--tmpfs", "/tmp",
            
            # Set working directory to .internal where base_code is
            "--chdir", "/personal/.internal",
            
            # Clean environment
            "--setenv", "CYBER_NAME", self.name,
            "--setenv", "HOME", "/personal",
            "--setenv", "PATH", "/grid/workshop:/usr/bin:/bin",
            "--setenv", "PYTHONPATH", "/personal/.internal",
            "--setenv", "CYBER_TYPE", self.cyber_type,
        ]
        
        # Add special body files for I/O Cybers
        if self.cyber_type == "io_gateway":
            io_bodies_dir = self.cyber_personal / ".io_bodies"
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
                "--bind", str(network_file), "/personal/network",
                "--bind", str(user_io_file), "/personal/user_io",
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
        
        logger.debug(f"Running sandboxed command for {self.cyber_id}: {' '.join(cmd)}")
        
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
            logger.warning(f"Command timed out for Cyber {self.cyber_id}")
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
        code_file = self.cyber_personal / ".tmp_code.py"
        code_file.write_text(code)
        
        # Run the code
        returncode, stdout, stderr = await self.run_command(
            ["python3", "/personal/Cyber/.tmp_code.py"],
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
        # Note: We don't delete cyber_personal as it contains persistent data
        # Only clean temporary files
        for tmp_file in self.cyber_personal.glob(".tmp_*"):
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
        self.agents_dir = self.root_path / "cybers"
        self.grid_dir = self.root_path / "grid"
        
        # Grid subdirectories
        self.community_dir = self.grid_dir / "community"  # Questions and discussions
        self.library_dir = self.grid_dir / "library"  # Shared knowledge
        self.workshop_dir = self.grid_dir / "workshop"  # Tools
        self.bulletin_dir = self.grid_dir / "bulletin"  # Announcements
        
        for directory in [
            self.agents_dir,
            self.grid_dir,
            self.community_dir,
            self.library_dir,
            self.workshop_dir,
            self.bulletin_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)
        
        self.sandboxes: Dict[str, BubblewrapSandbox] = {}
        
        # Initialize from template if needed
        self._initialize_from_template()
        
        # Prepare the Cyber runtime environment
        from mind_swarm.subspace.runtime_builder import AgentRuntimeBuilder
        self.runtime_builder = AgentRuntimeBuilder(self.root_path)
        self.runtime_builder.prepare_runtime()
        self.runtime_builder.create_tools_directory()
        
        logger.info(f"Initialized subspace at {self.root_path}")
    
    def _initialize_from_template(self):
        """Initialize subspace directories from template if they don't exist."""
        import shutil
        
        # Find template directory
        # __file__ is src/mind_swarm/subspace/sandbox.py
        # Need to go up to project root: parent.parent.parent.parent
        template_dir = Path(__file__).parent.parent.parent.parent / "subspace_template"
        if not template_dir.exists():
            logger.warning(f"Template directory not found at {template_dir}")
            return
        
        # Note: Removed redundant runtime directory copying - base_code is accessed directly from library
        
        # Copy grid structure if needed
        grid_template = template_dir / "grid"
        if grid_template.exists():
            # Always sync ROM from template (for development)
            rom_dir = self.library_dir / "rom"
            # ROM is now in knowledge/sections/rom in the template
            src_rom = grid_template / "library" / "knowledge" / "sections" / "rom"
            if src_rom.exists():
                if rom_dir.exists():
                    logger.info("Updating ROM knowledge from template")
                    shutil.rmtree(rom_dir)
                else:
                    logger.info("Copying ROM knowledge from template")
                shutil.copytree(src_rom, rom_dir)
            else:
                logger.warning(f"ROM source not found at {src_rom}")
            
            # Always sync base_code from template (for development)
            base_code_dir = self.library_dir / "base_code"
            src_base_code = grid_template / "library" / "base_code"
            if src_base_code.exists():
                if base_code_dir.exists():
                    logger.info("Updating base_code in library from template")
                    shutil.rmtree(base_code_dir)
                else:
                    logger.info("Copying base_code to library")
                shutil.copytree(src_base_code, base_code_dir)
            
            # Copy knowledge schema if missing
            schema_file = self.library_dir / "KNOWLEDGE_SCHEMA.md"
            if not schema_file.exists():
                src_schema = grid_template / "library" / "KNOWLEDGE_SCHEMA.md"
                if src_schema.exists():
                    shutil.copy2(src_schema, schema_file)
            
            # Copy actions directory if missing or update it
            actions_dir = self.library_dir / "actions"
            # Actions are now in knowledge/sections/actions in the template
            src_actions = grid_template / "library" / "knowledge" / "sections" / "actions"
            if src_actions.exists():
                if actions_dir.exists():
                    logger.info("Updating actions knowledge from template")
                    shutil.rmtree(actions_dir)
                else:
                    logger.info("Copying actions knowledge to library")
                shutil.copytree(src_actions, actions_dir)
            else:
                logger.warning(f"Actions source not found at {src_actions}")
            
            # Copy README files
            for subdir in ["community", "workshop", "library"]:
                readme = getattr(self, f"{subdir}_dir") / "README.md"
                if not readme.exists():
                    src_readme = grid_template / subdir / "README.md"
                    if src_readme.exists():
                        shutil.copy2(src_readme, readme)
        
        # Initialize Cyber directory in plaza
        agent_dir_file = self.community_dir / "cyber_directory.json"
        if not agent_dir_file.exists():
            src_agent_dir = grid_template / "community" / "cyber_directory.json"
            if src_agent_dir.exists():
                logger.info("Copying initial cyber_directory.json to plaza")
                shutil.copy2(src_agent_dir, agent_dir_file)
    
    def create_sandbox(self, name: str, cyber_type: str = "general") -> BubblewrapSandbox:
        """Create a sandbox for an Cyber.
        
        Args:
            name: Unique Cyber name
            cyber_type: Type of Cyber (general, io_gateway)
            
        Returns:
            Configured sandbox instance
        """
        # Check if Cyber already exists (on disk or in memory)
        agent_exists = name in self.sandboxes or (self.agents_dir / name).exists()
        
        if name in self.sandboxes:
            # Cyber already in memory
            sandbox = self.sandboxes[name]
        else:
            # Create new sandbox instance
            sandbox = BubblewrapSandbox(name, self.root_path, cyber_type)
            self.sandboxes[name] = sandbox
        
        # For existing Cybers, update their base_code and structure
        if agent_exists:
            # Create new organized directory structure
            internal_dir = sandbox.cyber_personal / ".internal"
            internal_dir.mkdir(exist_ok=True)
            
            base_code = internal_dir / "base_code"
            if not base_code.exists():
                logger.info(f"Creating base_code directory for existing Cyber {name}")
                base_code.mkdir(exist_ok=True)
            logger.info(f"Updating base_code for existing Cyber {name}")
            self._copy_agent_base_code(base_code, cyber_type)
            
            # Create organized directory structure
            # Communications
            comms_dir = sandbox.cyber_personal / "comms"
            comms_dir.mkdir(exist_ok=True)
            for subdir in ["inbox", "outbox", "drafts", "sent"]:
                (comms_dir / subdir).mkdir(exist_ok=True)
            
            # Memory areas
            memory_dir = sandbox.cyber_personal / "memory"
            memory_dir.mkdir(exist_ok=True)
            # Only create directories that are actually used by the cyber code
            for subdir in ["orientations",  # Used by observation_stage for orientations
                         "action_results"]:  # Used by all actions for their results
                (memory_dir / subdir).mkdir(exist_ok=True)
            
            # Internal logs
            (internal_dir / "logs").mkdir(exist_ok=True)
            
            return sandbox
        
        # Initialize organized Cyber directory structure
        # Internal system files (hidden from Cyber's conscious view)
        internal_dir = sandbox.cyber_personal / ".internal"
        internal_dir.mkdir(exist_ok=True)
        
        # Base code goes in internal
        base_code = internal_dir / "base_code"
        base_code.mkdir(exist_ok=True)
        
        # Internal logs
        (internal_dir / "logs").mkdir(exist_ok=True)
        
        # Communications directory
        comms_dir = sandbox.cyber_personal / "comms"
        comms_dir.mkdir(exist_ok=True)
        for subdir in ["inbox", "outbox", "drafts", "sent"]:
            (comms_dir / subdir).mkdir(exist_ok=True)
        
        # Memory directory with subdirectories
        memory_dir = sandbox.cyber_personal / "memory"
        memory_dir.mkdir(exist_ok=True)
        # Only create directories that are actually used by the cyber code
        for subdir in ["orientations",  # Used by observation_stage for orientations
                     "action_results"]:  # Used by all actions for their results
            (memory_dir / subdir).mkdir(exist_ok=True)
        
        # Copy Cyber code to base_code directory
        self._copy_agent_base_code(base_code, cyber_type)
        
        logger.info(f"Created sandbox for Cyber {name}")
        return sandbox
    
    def remove_sandbox(self, name: str):
        """Remove a sandbox and clean up resources.
        
        Args:
            name: Cyber name
        """
        if name in self.sandboxes:
            self.sandboxes[name].cleanup()
            del self.sandboxes[name]
            logger.info(f"Removed sandbox for Cyber {name}")
    
    def _copy_agent_base_code(self, base_code_dir: Path, cyber_type: str = "general"):
        """Copy Cyber base code to the Cyber's home directory.
        
        Args:
            base_code_dir: The base_code directory in Cyber's home
            cyber_type: Type of Cyber (general, io_gateway)
        """
        # Choose template from library/base_code based on Cyber type
        if cyber_type == "io_gateway":
            template_dir = self.library_dir / "base_code" / "io_cyber_template"
        else:
            template_dir = self.library_dir / "base_code" / "base_code_template"
        
        if template_dir.exists():
            # Copy entire directory structure from template
            import shutil
            
            # For I/O Cybers, first copy base template as dependency
            if cyber_type == "io_gateway":
                base_template = self.library_dir / "base_code" / "base_code_template"
                if base_template.exists():
                    # Create base_code_template subdirectory
                    base_dest = base_code_dir / "base_code_template"
                    if base_dest.exists():
                        shutil.rmtree(base_dest)
                    shutil.copytree(base_template, base_dest)
                    logger.debug("Copied base_code_template for I/O Cyber")
            
            # First copy all .py files in the root
            for py_file in template_dir.glob("*.py"):
                dst_file = base_code_dir / py_file.name
                shutil.copy2(py_file, dst_file)
                logger.debug(f"Copied {py_file.name} to Cyber base_code")
            
            # Then copy all subdirectories
            for subdir in template_dir.iterdir():
                if subdir.is_dir() and not subdir.name.startswith('.'):
                    dst_subdir = base_code_dir / subdir.name
                    if dst_subdir.exists():
                        shutil.rmtree(dst_subdir)
                    shutil.copytree(subdir, dst_subdir)
                    logger.debug(f"Copied directory {subdir.name} to Cyber base_code")
        else:
            # Fallback: copy directly from source
            src_dir = Path(__file__).parent.parent / "agent_sandbox"
            if src_dir.exists():
                import shutil
                for py_file in src_dir.glob("*.py"):
                    dst_file = base_code_dir / py_file.name
                    shutil.copy2(py_file, dst_file)
                    logger.debug(f"Copied {py_file.name} to Cyber base_code")
            else:
                logger.error("No Cyber base code found to copy!")
    
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