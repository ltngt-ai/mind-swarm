"""
# Environment API for cybers to interact with their system environment.

## Environment

The Environment class provides methods to execute system commands and
interact with the cyber's environment through shell operations.

## Usage Examples

### Execute Commands
```python
# Run a simple command
result = environment.exec_command("ls -la")
print(result['stdout'])

# Run with custom timeout
result = environment.exec_command("sleep 5 && echo 'done'", timeout=10)
if result['returncode'] == 0:
    print(f"Success: {result['stdout']}")
else:
    print(f"Failed: {result['stderr']}")
```

## Important Notes
1. **Default timeout is 120 seconds**
2. **Commands run synchronously - the cyber waits for completion**
3. **Both stdout and stderr are captured**
4. **Return code indicates success (0) or failure (non-zero)**
"""

import subprocess
import os
import json
from pathlib import Path
from typing import Dict, Any


class EnvironmentError(Exception):
    """Base exception for environment operations."""
    pass


class EnvironmentTimeoutError(EnvironmentError):
    """Raised when a command times out."""
    pass


class Environment:
    """
    Main environment interface for system interaction.
    
    Provides methods to execute shell commands and interact
    with the system environment.
    """
    
    def __init__(self, context: Dict[str, Any]):
        """Initialize the environment system.
        
        Args:
            context: Cyber context containing personal_dir and other info
        """
        self.context = context
        self.personal_dir = Path(context.get("personal_dir", "/personal"))
        
        # Get current location from dynamic context to use as working directory
        self._update_working_dir()
    
    def _update_working_dir(self):
        """Update working directory from the cyber's current location."""
        try:
            unified_state_file = self.personal_dir / ".internal" / "memory" / "unified_state.json"
            if unified_state_file.exists():
                with open(unified_state_file, 'r') as f:
                    state = json.load(f)
                    current_location = state.get("location", {}).get("current_location", str(self.personal_dir))
                    # Map the location to the actual filesystem path
                    if current_location.startswith("/personal"):
                        # Replace /personal with the actual personal directory path
                        self.working_dir = Path(str(self.personal_dir) + current_location[9:])
                    elif current_location.startswith("/grid"):
                        # Map /grid to the actual grid location
                        self.working_dir = Path(current_location)
                    else:
                        self.working_dir = self.personal_dir
            else:
                self.working_dir = self.personal_dir
        except Exception:
            # Fallback to personal directory if we can't read location
            self.working_dir = self.personal_dir
    
    def exec_command(self, command: str, timeout: float = 120) -> Dict[str, Any]:
        """[DEPRECATED] Execute a shell command synchronously.
        
        WARNING: This method is DEPRECATED. Use terminal.exec_command() instead.
        The terminal API provides network access which this method lacks.
        
        This method does NOT have network access. Commands like curl, wget, 
        or other network operations will fail. Use terminal.exec_command() 
        for all command execution needs, especially network operations.
        
        Args:
            command: The shell command to execute
            timeout: Maximum seconds to wait for completion (default: 120)
            
        Returns:
            Dictionary containing:
                - stdout: The standard output from the command
                - stderr: The standard error output from the command
                - returncode: The exit code (0 = success)
                - timed_out: Boolean indicating if command timed out
            
        DEPRECATED - Use instead:
            ```python
            import terminal
            # Has network access!
            result = terminal.exec_command("curl https://api.example.com")
            print(result)
            ```
        """
        
        # Log deprecation warning
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"environment.exec_command() is DEPRECATED. Use terminal.exec_command() instead. "
            f"Command '{command[:50]}...' may fail if it requires network access."
        )
        if not command or not isinstance(command, str):
            raise EnvironmentError("Command must be a non-empty string")
        
        if timeout <= 0:
            raise EnvironmentError("Timeout must be positive")
        
        # Limit maximum timeout to 10 minutes for safety
        if timeout > 600:
            timeout = 600
        
        # Update working directory to cyber's current location
        self._update_working_dir()
        
        result = {
            "stdout": "",
            "stderr": "",
            "returncode": -1,
            "timed_out": False
        }
        
        try:
            # Run the command with shell=True to support shell features
            # Set cwd to cyber's current location
            process = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.working_dir),
                env=os.environ.copy()
            )
            
            result["stdout"] = process.stdout
            result["stderr"] = process.stderr
            result["returncode"] = process.returncode
            
        except subprocess.TimeoutExpired as e:
            result["timed_out"] = True
            result["stdout"] = e.stdout if e.stdout else ""
            result["stderr"] = e.stderr if e.stderr else ""
            result["returncode"] = -1
            
            # Also raise an exception so the cyber knows it timed out
            raise EnvironmentTimeoutError(
                f"Command timed out after {timeout} seconds: {command[:50]}..."
            )
            
        except Exception as e:
            raise EnvironmentError(f"Failed to execute command: {e}")
        
        return result