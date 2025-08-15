"""Runtime builder that prepares a clean Cyber environment."""

import shutil
import sys
from pathlib import Path
from typing import List, Set

from mind_swarm.utils.logging import logger


class AgentRuntimeBuilder:
    """Builds a minimal runtime environment for Cybers."""
    
    def __init__(self, subspace_root: Path):
        """Initialize the runtime builder.
        
        Args:
            subspace_root: Root directory of the subspace
        """
        self.subspace_root = subspace_root
        self.library_dir = subspace_root / "grid" / "library"
        
    def prepare_runtime(self):
        """Prepare the Cyber runtime environment."""
        logger.info("Preparing Cyber runtime environment...")
        
        # Verify the base code templates exist in library
        self._verify_base_code_templates()
        
        logger.info("Cyber runtime environment prepared")
    
    def _verify_base_code_templates(self):
        """Verify the base code templates exist in library.
        
        The base_code templates are maintained in grid/library/mind_swarm_tech/base_code
        and copied to each Cyber's home directory when they are created.
        """
        base_code_dir = self.library_dir / "mind_swarm_tech" / "base_code"
        base_template = base_code_dir / "base_code_template"
        io_template = base_code_dir / "io_cyber_template"
        
        if not base_template.exists():
            logger.error(f"Base code template not found at: {base_template}")
            logger.error("Please ensure grid/library/mind_swarm_tech/base_code/base_code_template exists")
            return
        
        if not io_template.exists():
            logger.warning(f"IO template not found at: {io_template}")
        
        # Verify content
        py_files = list(base_template.glob("*.py"))
        subdirs = [d for d in base_template.iterdir() if d.is_dir() and not d.name.startswith('.')]
        
        logger.info(f"Base code template found with {len(py_files)} files and {len(subdirs)} subdirectories")
    
    def _copy_minimal_dependencies(self):
        """Copy only the minimal dependencies Cybers need."""
        # Create a minimal set of modules Cybers actually need
        # This should NOT include our implementation details
        
        # Standard library modules Cybers might need
        # (These are already available through Python installation)
        
        # For now, we'll just ensure the Cyber can import what it needs
        # from the standard library. No mind_swarm modules should be
        # accessible to Cybers except through the runtime.
        pass
    
    
    def create_tools_directory(self):
        """Create and populate the workshop with safe tools."""
        workshop_dir = self.subspace_root / "grid" / "workshop"
        workshop_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a simple example tool
        hello_tool = workshop_dir / "hello"
        hello_tool.write_text('''#!/bin/bash
echo "Hello from the Grid workshop!"
echo "Cyber ID: $AGENT_ID"
''')
        hello_tool.chmod(0o755)
        
        # Create a tool for Cybers to check their environment
        env_tool = workshop_dir / "check_env"
        env_tool.write_text('''#!/bin/bash
echo "=== Cyber Environment ==="
echo "Cyber ID: $AGENT_ID"
echo "Home: $HOME"
echo "Current Location: $PWD"
echo "PATH: $PATH"
echo ""
echo "=== Your Reality ==="
ls -la /
echo ""
echo "=== Your Home ==="
ls -la ~
echo ""
echo "=== The Grid ==="
ls -la /grid
''')
        env_tool.chmod(0o755)
        
        logger.info(f"Created tools in workshop: {workshop_dir}")
    
    def validate_sandbox_safety(self) -> List[str]:
        """Validate that the sandbox doesn't expose dangerous paths.
        
        Returns:
            List of warnings if any unsafe configurations detected
        """
        warnings = []
        
        # Check that we're not exposing our source code
        if (self.runtime_dir / "mind_swarm").exists():
            warnings.append("Source code is exposed in runtime!")
        
        # Check that we're not exposing system Python packages
        # (This would be checked during actual sandbox creation)
        
        return warnings