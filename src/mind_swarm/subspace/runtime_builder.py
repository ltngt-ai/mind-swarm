"""Runtime builder that prepares a clean agent environment."""

import shutil
import sys
from pathlib import Path
from typing import List, Set

from mind_swarm.utils.logging import logger


class AgentRuntimeBuilder:
    """Builds a minimal runtime environment for agents."""
    
    def __init__(self, subspace_root: Path):
        """Initialize the runtime builder.
        
        Args:
            subspace_root: Root directory of the subspace
        """
        self.subspace_root = subspace_root
        self.runtime_dir = subspace_root / "runtime" / "agent"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        
    def prepare_runtime(self):
        """Prepare the agent runtime environment."""
        logger.info("Preparing agent runtime environment...")
        
        # The runtime will now be in each agent's home/base_code
        # We'll copy the sandbox directory structure there
        self._prepare_agent_base_code()
        
        logger.info("Agent runtime environment prepared")
    
    def _prepare_agent_base_code(self):
        """Verify the base code template exists in runtime.
        
        The base_code_template is maintained manually in the runtime directory
        to ensure complete separation from the server code.
        """
        base_code_template = self.runtime_dir.parent / "base_code_template"
        
        if not base_code_template.exists():
            logger.error(f"Base code template not found at: {base_code_template}")
            logger.error("Please ensure runtime/base_code_template exists with agent code")
            return
        
        # Just verify it has content
        py_files = list(base_code_template.glob("*.py"))
        subdirs = [d for d in base_code_template.iterdir() if d.is_dir() and not d.name.startswith('.')]
        
        logger.info(f"Base code template found with {len(py_files)} files and {len(subdirs)} subdirectories")
    
    def _copy_minimal_dependencies(self):
        """Copy only the minimal dependencies agents need."""
        # Create a minimal set of modules agents actually need
        # This should NOT include our implementation details
        
        # Standard library modules agents might need
        # (These are already available through Python installation)
        
        # For now, we'll just ensure the agent can import what it needs
        # from the standard library. No mind_swarm modules should be
        # accessible to agents except through the runtime.
        pass
    
    
    def create_tools_directory(self):
        """Create and populate the workshop with safe tools."""
        workshop_dir = self.subspace_root / "grid" / "workshop"
        workshop_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a simple example tool
        hello_tool = workshop_dir / "hello"
        hello_tool.write_text('''#!/bin/bash
echo "Hello from the Grid workshop!"
echo "Agent ID: $AGENT_ID"
''')
        hello_tool.chmod(0o755)
        
        # Create a tool for agents to check their environment
        env_tool = workshop_dir / "check_env"
        env_tool.write_text('''#!/bin/bash
echo "=== Agent Environment ==="
echo "Agent ID: $AGENT_ID"
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