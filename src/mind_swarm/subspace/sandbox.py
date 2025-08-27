"""Sandbox implementation using bubblewrap for Cyber isolation."""

import asyncio
import sys
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
        self.tools_dir = subspace_root / "grid" / "workshop"  # Keep for backward compat but don't create
        self.cyber_type = cyber_type
        self.cyber_rootfs = subspace_root / "cyber_rootfs"  # Debian rootfs for cybers
        
        # Ensure directories exist
        self.cyber_personal.mkdir(parents=True, exist_ok=True)
        self.grid_root.mkdir(parents=True, exist_ok=True)
        
        # Create Grid structure - only community and library
        (self.grid_root / "community").mkdir(exist_ok=True)
        (self.grid_root / "library").mkdir(exist_ok=True)
    
    def _build_bwrap_cmd(self, cmd: List[str], env: Optional[Dict[str, str]] = None) -> List[str]:
        """Build bubblewrap command with proper isolation.
        
        Args:
            cmd: Command to run inside sandbox
            env: Environment variables to pass
            
        Returns:
            Complete bubblewrap command
        """
        # Check if rootfs exists
        if not self.cyber_rootfs.exists() or not (self.cyber_rootfs / ".mind_swarm_rootfs").exists():
            logger.error(f"Cyber rootfs not found at {self.cyber_rootfs}")
            logger.error("Please run: sudo ./setup_cyber_rootfs.sh")
            raise RuntimeError("Cyber rootfs not initialized. Run setup_cyber_rootfs.sh as root.")
        
        bwrap_cmd = [
            "bwrap",
            # Die when parent process dies - prevents zombie processes
            "--die-with-parent",
            # Create new namespaces
            "--unshare-all",
            # No network access - Cybers think through body files
            
            # Use the Debian rootfs as the root filesystem
            "--bind", str(self.cyber_rootfs), "/",
        ]
        
        
        # Continue with rest of configuration
        bwrap_cmd.extend([
            # Proc and dev
            "--proc", "/proc",
            "--dev", "/dev",
            
            # Their Mind - their private space
            "--bind", str(self.cyber_personal), "/personal",
            
            # The Grid - where Cybers meet and collaborate
            "--bind", str(self.grid_root), "/grid",
            
            # Temp directory
            "--tmpfs", "/tmp",
            
            # Set working directory to .internal where base_code is
            "--chdir", "/personal/.internal",
            
            # Clean environment
            "--setenv", "CYBER_NAME", self.name,
            "--setenv", "HOME", "/personal",
            "--setenv", "PATH", "/usr/local/bin:/usr/bin:/bin",
            "--setenv", "PYTHONPATH", "/personal/.internal",
            "--setenv", "CYBER_TYPE", self.cyber_type,
            "--setenv", "USER", "cyber",
            "--setenv", "LANG", "C.UTF-8",
        ])
        
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
        
        logger.debug(f"Running sandboxed command for {self.name}: {' '.join(cmd)}")
        
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
            logger.warning(f"Command timed out for Cyber {self.name}")
            if proc:
                proc.terminate()
                await proc.wait()
            return -1, "", "Command timed out"
        except Exception as e:
            logger.error(f"Error running sandboxed command: {e}")
            return -1, "", str(e)
    
    def cleanup(self, delete_personal=False):
        """Clean up sandbox resources.
        
        Args:
            delete_personal: If True, delete the entire cyber personal directory.
                           Used when terminating a cyber permanently.
        """
        # Clean temporary files
        for tmp_file in self.cyber_personal.glob(".tmp_*"):
            tmp_file.unlink(missing_ok=True)
        
        # If requested, delete the entire cyber directory (for termination)
        if delete_personal and self.cyber_personal.exists():
            import shutil
            logger.info(f"Deleting cyber personal directory: {self.cyber_personal}")
            try:
                shutil.rmtree(self.cyber_personal)
                logger.info(f"Successfully deleted {self.cyber_personal}")
            except Exception as e:
                logger.error(f"Failed to delete {self.cyber_personal}: {e}")


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
        self.cyber_rootfs = self.root_path / "cyber_rootfs"  # Debian rootfs for cybers
        
        # Grid subdirectories
        self.community_dir = self.grid_dir / "community"  # Questions and discussions
        self.library_dir = self.grid_dir / "library"  # Shared knowledge
        
        for directory in [
            self.agents_dir,
            self.grid_dir,
            self.community_dir,
            self.library_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)
        
        self.sandboxes: Dict[str, BubblewrapSandbox] = {}
        
        # Initialize from template if needed
        self._initialize_from_template()
        
        # Check for Debian rootfs
        self._check_rootfs()
        
        # Prepare the Cyber runtime environment
        from mind_swarm.subspace.runtime_builder import AgentRuntimeBuilder
        self.runtime_builder = AgentRuntimeBuilder(self.root_path)
        self.runtime_builder.prepare_runtime()
        
        logger.info(f"Initialized subspace at {self.root_path}")
    
    def _initialize_from_template(self):
        """Initialize subspace directories from template using intelligent sync."""
        import shutil
        import subprocess
        
        # Find template directory
        # __file__ is src/mind_swarm/subspace/sandbox.py
        # Need to go up to project root: parent.parent.parent.parent
        template_dir = Path(__file__).parent.parent.parent.parent / "subspace_template"
        if not template_dir.exists():
            logger.warning(f"Template directory not found at {template_dir}")
            return
        
        # Check if sync script exists
        sync_script = Path(__file__).parent.parent.parent.parent / "scripts" / "sync_subspace.py"
        config_file = Path(__file__).parent.parent.parent.parent / "config" / "subspace_sync.yaml"
        
        if sync_script.exists() and config_file.exists():
            # Use the new sync system
            logger.info("Using intelligent sync system for template updates")
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(sync_script),
                        "--subspace", str(self.root_path),
                        "--template", str(template_dir),
                        "--config", str(config_file),
                    ],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    logger.info("Template sync completed successfully")
                else:
                    logger.warning(f"Template sync failed: {result.stderr}")
                    # Fall back to basic initialization for critical files
                    self._fallback_initialization(template_dir)
            except Exception as e:
                logger.error(f"Error running sync script: {e}")
                self._fallback_initialization(template_dir)
        else:
            # Fall back to old method if sync system not available
            logger.info("Sync system not available, using basic initialization")
            self._fallback_initialization(template_dir)
    
    def _fallback_initialization(self, template_dir: Path):
        """Fallback initialization for when sync system is not available."""
        import shutil
        
        # Only copy files that don't exist (non-destructive)
        grid_template = template_dir / "grid"
        if not grid_template.exists():
            return
        
        # Initialize basic structure if missing
        # Only copy community and library - workshop and bulletin are deprecated
        for subdir in ["community", "library"]:
            target_dir = self.grid_dir / subdir
            if not target_dir.exists():
                src_dir = grid_template / subdir
                if src_dir.exists():
                    logger.info(f"Initializing {subdir} from template")
                    shutil.copytree(src_dir, target_dir)
        
        # Copy critical files if missing
        agent_dir_file = self.community_dir / "cyber_directory.json"
        if not agent_dir_file.exists():
            src_agent_dir = grid_template / "community" / "cyber_directory.json"
            if src_agent_dir.exists():
                logger.info("Copying initial cyber_directory.json")
                shutil.copy2(src_agent_dir, agent_dir_file)
    
    def _check_rootfs(self):
        """Check if the Debian rootfs for cybers exists."""
        if not self.cyber_rootfs.exists() or not (self.cyber_rootfs / ".mind_swarm_rootfs").exists():
            logger.error(f"Cyber rootfs not found at {self.cyber_rootfs}")
            logger.error("Please run: sudo ./setup_cyber_rootfs.sh")
            logger.error("This creates a minimal Debian environment for cyber isolation")
            raise RuntimeError(
                f"Cyber rootfs not initialized at {self.cyber_rootfs}.\n"
                "Please run: sudo ./setup_cyber_rootfs.sh\n"
                "This is required for proper cyber isolation."
            )
        else:
            logger.info(f"Cyber rootfs found at {self.cyber_rootfs}")
    
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
        
        # Initialize organized Cyber directory structure
        # Internal system files (hidden from Cyber's conscious view)
        internal_dir = sandbox.cyber_personal / ".internal"
        internal_dir.mkdir(exist_ok=True)

        # Base code goes in internal
        base_code = internal_dir / "base_code"
        base_code.mkdir(exist_ok=True)

        # Internal logs
        (internal_dir / "logs").mkdir(exist_ok=True)
        # Mail directories (directly under personal)
        # Only inbox is visible to cybers (outbox and mail_archive are in .internal)
        (sandbox.cyber_personal / "inbox").mkdir(exist_ok=True)
        
        # Memory directory with subdirectories (now inside .internal)
        memory_dir = internal_dir / "memory"
        memory_dir.mkdir(exist_ok=True)
            
        # Copy Cyber code to base_code directory
        self._copy_agent_base_code(base_code, cyber_type)
        
        # Copy maintenance tasks to tasks directory
        self._copy_maintenance_tasks(internal_dir)
        
        # Copy boot ROM for this cyber type
        self._copy_boot_rom(internal_dir, cyber_type)
        
        logger.info(f"Created sandbox for Cyber {name}")
        return sandbox
    
    def remove_sandbox(self, name: str, delete_personal=True):
        """Remove a sandbox and clean up resources.
        
        Args:
            name: Cyber name
            delete_personal: If True, delete the cyber's personal directory (default: True for termination)
        """
        if name in self.sandboxes:
            self.sandboxes[name].cleanup(delete_personal=delete_personal)
            del self.sandboxes[name]
            logger.info(f"Removed sandbox for Cyber {name} (delete_personal={delete_personal})")
    
    def _copy_boot_rom(self, internal_dir: Path, cyber_type: str = "general"):
        """Copy the appropriate boot ROM to the cyber's internal directory.
        
        Args:
            internal_dir: The .internal directory in the cyber's home
            cyber_type: Type of cyber (general, io_gateway)
        """
        # Get the template directory
        template_root = Path(__file__).parent.parent.parent.parent / "subspace_template"
        
        # Select boot ROM based on cyber type
        if cyber_type == "io_gateway":
            boot_rom_src = template_root / "boot_rom" / "io_gateway.yaml"
        else:
            boot_rom_src = template_root / "boot_rom" / "general.yaml"
            
        if boot_rom_src.exists():
            boot_rom_dest = internal_dir / "boot_rom.yaml"
            import shutil
            shutil.copy2(boot_rom_src, boot_rom_dest)
            logger.debug(f"Copied boot ROM for {cyber_type} cyber")
        else:
            logger.warning(f"Boot ROM not found at {boot_rom_src}")
    
    def _copy_agent_base_code(self, base_code_dir: Path, cyber_type: str = "general"):
        """Copy Cyber base code to the Cyber's home directory.
        
        Args:
            base_code_dir: The base_code directory in Cyber's home
            cyber_type: Type of Cyber (general, io_gateway)
        """
        # Get the template directory from the source, not the runtime
        # __file__ is src/mind_swarm/subspace/sandbox.py
        template_root = Path(__file__).parent.parent.parent.parent / "subspace_template"
        
        # Choose template from library/non-fiction/mind_swarm_tech/base_code based on Cyber type
        if cyber_type == "io_gateway":
            template_dir = template_root / "grid" / "library" / "non-fiction" / "mind_swarm_tech" / "base_code" / "io_cyber_template"
        else:
            template_dir = template_root / "grid" / "library" / "non-fiction" / "mind_swarm_tech" / "base_code" / "base_code_template"
        
        if template_dir.exists():
            # Copy entire directory structure from template
            import shutil
            
            # For I/O Cybers, first copy base template as dependency
            if cyber_type == "io_gateway":
                base_template = template_root / "grid" / "library" / "non-fiction" / "mind_swarm_tech" / "base_code" / "base_code_template"
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
    
    def _copy_maintenance_tasks(self, internal_dir: Path):
        """Copy standard maintenance tasks to the Cyber's tasks directory.
        
        Args:
            internal_dir: The .internal directory in Cyber's home
        """
        # Create tasks directory structure
        tasks_dir = internal_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        
        # Create subdirectories (no active directory)
        for subdir in ["completed", "blocked", "hobby", "maintenance"]:
            (tasks_dir / subdir).mkdir(exist_ok=True)
        
        # Get the maintenance tasks template directory
        template_root = Path(__file__).parent.parent.parent.parent / "subspace_template"
        maintenance_template = template_root / "maintenance_tasks"
        
        if maintenance_template.exists():
            import shutil
            
            # Check if maintenance tasks already exist (don't overwrite existing tasks)
            maintenance_dir = tasks_dir / "maintenance"
            completed_dir = tasks_dir / "completed"
            blocked_dir = tasks_dir / "blocked"
            
            # Get list of all existing maintenance task IDs
            existing_mt_ids = set()
            for dir in [maintenance_dir, completed_dir, blocked_dir]:
                for f in dir.glob("MT-*.json"):
                    # Extract task ID from filename (e.g., "MT-001" from "MT-001_tidy_personal.json")
                    task_id = f.name.split('_')[0]
                    existing_mt_ids.add(task_id)
            
            # Copy maintenance tasks that don't already exist
            import json
            from datetime import datetime
            
            for task_file in maintenance_template.glob("*.json"):
                task_id = task_file.name.split('_')[0]
                
                if task_id not in existing_mt_ids:
                    # Load the task to mark it as completed
                    with open(task_file, 'r') as f:
                        task_data = json.load(f)
                    
                    # Mark as completed with timestamp
                    task_data['status'] = 'completed'
                    task_data['completed_at'] = datetime.now().isoformat()
                    
                    # Copy to completed directory instead of maintenance
                    # This way maintenance tasks start as completed and get reactivated based on tiredness
                    dst_file = completed_dir / task_file.name
                    with open(dst_file, 'w') as f:
                        json.dump(task_data, f, indent=2)
                    
                    logger.debug(f"Copied maintenance task {task_file.name} to completed folder")
                else:
                    logger.debug(f"Maintenance task {task_id} already exists, skipping")
        else:
            logger.warning(f"Maintenance tasks template not found at {maintenance_template}")
    
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