#!/usr/bin/env python3
"""Fix for cognitive_loop_v2.py compatibility issue.

This creates a wrapper that ensures the observe phase returns
the expected format whether using DSPy or plain dict responses.
"""

import sys
from pathlib import Path

def create_compatible_observe_wrapper():
    """Create a compatible observe wrapper that handles both dict and DSPy responses."""
    
    wrapper_code = '''
    async def _observe_compatible(self) -> Dict[str, Any]:
        """Wrapper for observe that ensures compatibility."""
        result = await self._observe()
        
        # If it's already a dict with the expected structure, return as-is
        if isinstance(result, dict) and "observations" in result:
            # Wrap in a simple object that has the expected attributes
            class ObserveResult:
                def __init__(self, data):
                    self.output_values = data
                    self.metadata = data.get("metadata", {})
            
            return ObserveResult(result)
        
        # If it has output_values (DSPy response), return as-is
        elif hasattr(result, "output_values"):
            return result
        
        # Otherwise, wrap whatever we got
        else:
            class ObserveResult:
                def __init__(self, data):
                    self.output_values = {"observations": data} if data else {}
                    self.metadata = {}
            
            return ObserveResult(result)
    '''
    
    return wrapper_code


def patch_cognitive_loop(file_path: Path):
    """Patch a cognitive_loop_v2.py file to handle the compatibility issue."""
    
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return False
    
    content = file_path.read_text()
    
    # Check if already patched
    if "_observe_compatible" in content:
        print(f"Already patched: {file_path}")
        return True
    
    # Find the line with the error
    error_line = "if observations.output_values.get"
    if error_line not in content:
        print(f"Error line not found in: {file_path}")
        return False
    
    # Add the wrapper method after the _observe method
    lines = content.split('\n')
    new_lines = []
    
    # First, add the import if needed
    added_import = False
    for i, line in enumerate(lines):
        new_lines.append(line)
        if line.startswith("from typing import") and not added_import:
            new_lines.append("from typing import Dict, Any, Union")
            added_import = True
    
    # Now patch the observe call
    patched_content = '\n'.join(new_lines)
    
    # Replace the direct call with a safe access
    patched_content = patched_content.replace(
        "observations = await self._observe()",
        """observations = await self._observe()
        
        # Handle both dict and DSPy response formats
        if isinstance(observations, dict):
            # Create a wrapper with expected attributes
            class ObserveResult:
                def __init__(self, data):
                    self.output_values = data
                    self.metadata = data.get("metadata", {})
            observations = ObserveResult(observations)
        elif not hasattr(observations, 'output_values'):
            # Wrap in expected format
            class ObserveResult:
                def __init__(self, data):
                    self.output_values = {"observations": []}
                    self.metadata = {}
            observations = ObserveResult(observations)"""
    )
    
    # Write back
    file_path.write_text(patched_content)
    print(f"Patched: {file_path}")
    return True


def main():
    """Patch all cognitive_loop_v2.py files."""
    
    # Find all cognitive_loop_v2.py files in runtime and Cyber directories
    base_path = Path("/personal/deano/projects/mind-swarm")
    
    files_to_patch = [
        base_path / "subspace/runtime/base_code_template/cognitive_loop_v2.py",
    ]
    
    # Also find any in Cyber directories
    agent_base = base_path / "subspace/Cybers"
    if agent_base.exists():
        for cyber_dir in agent_base.iterdir():
            if cyber_dir.is_dir():
                cognitive_file = cyber_dir / "base_code" / "cognitive_loop_v2.py"
                if cognitive_file.exists():
                    files_to_patch.append(cognitive_file)
    
    print("Patching cognitive loop files for compatibility...\n")
    
    for file_path in files_to_patch:
        if file_path.exists():
            patch_cognitive_loop(file_path)
    
    print("\nDone!")


if __name__ == "__main__":
    main()