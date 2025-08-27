"""
Terminal Management API for Cybers

## Core Concept: Interactive Terminal Sessions
The Terminal API allows Cybers to create and manage terminal sessions
for running commands, interacting with REPLs, and automating CLI tools.

## Examples

### Intention: "I want to run a Python script"
```python
session_id = terminal.create("python3")
terminal.send(session_id, "import sys")
terminal.send(session_id, "print(sys.version)")
output = terminal.read(session_id)
print(f"Python version: {output['screen']}")
terminal.close(session_id)
```

### Intention: "I want to interact with a database CLI"
```python
session_id = terminal.create("sqlite3 /data/my_database.db")
terminal.send(session_id, ".tables")
tables = terminal.read(session_id)
for table in tables['screen'].split('\\n'):
    if table.strip():
        terminal.send(session_id, f"SELECT COUNT(*) FROM {table};")
        count = terminal.read(session_id)
        print(f"{table}: {count['screen']}")
```

### Intention: "I want to test my code"
```python
session = terminal.create("python3")
terminal.send(session, "exec(open('/personal/my_script.py').read())")
result = terminal.read(session)
if "Error" in result['screen']:
    print("Test failed:", result['screen'])
else:
    print("Test passed!")
```

### Intention: "I want to run shell commands"
```python
session = terminal.create("bash")
terminal.send(session, "ls -la /grid/workshop/")
files = terminal.read(session)
print("Workshop contents:", files['screen'])

terminal.send(session, "grep -r 'TODO' /personal/")
todos = terminal.read(session)
print("Found TODOs:", todos['screen'])
```

## Best Practices
1. Always close sessions when done to free resources
2. Check session output for errors before proceeding
3. Use appropriate shells/interpreters for tasks
4. Handle terminal responses gracefully
5. Don't leave sensitive data in terminal history
"""

import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger("Cyber.terminal")


class TerminalError(Exception):
    """Base exception for terminal errors."""
    pass


class Terminal:
    """Terminal management for interactive sessions."""
    
    def __init__(self, context: Dict[str, Any]):
        """Initialize the Terminal API.
        
        Args:
            context: Execution context containing personal_dir, etc.
        """
        self.context = context
        self.personal = Path(context.get('personal_dir', '/personal'))
        self.terminal_body = self.personal / '.internal' / 'terminal'
        
    def create(self, command: str = "bash", name: Optional[str] = None) -> str:
        """Create a new terminal session.
        
        Args:
            command: Command to execute (e.g., "python3", "bash", "node")
            name: Optional name for the session
            
        Returns:
            Session ID
            
        Example:
            session = terminal.create("python3", name="test_session")
        """
        request = {
            "action": "create",
            "data": {
                "command": command,
                "name": name or command
            }
        }
        
        response = self._send_request(request)
        
        if response['status'] == 'success':
            session_id = response.get('session_id') or response.get('data', {}).get('session_id')
            logger.info(f"Created terminal session: {session_id}")
            return session_id
        else:
            raise TerminalError(f"Failed to create session: {response.get('message', 'Unknown error')}")
    
    def send(self, session_id: str, input_text: str):
        """Send input to a terminal session.
        
        Args:
            session_id: ID of the session
            input_text: Text to send (newline will be added automatically)
            
        Example:
            terminal.send(session_id, "print('Hello')")
        """
        request = {
            "action": "write",
            "session_id": session_id,
            "data": {
                "input": input_text
            }
        }
        
        response = self._send_request(request)
        
        if response['status'] != 'success':
            raise TerminalError(f"Failed to send input: {response.get('message', 'Unknown error')}")
        
        # Give terminal time to process
        time.sleep(0.1)
    
    def read(self, session_id: str, format: str = "text") -> Dict[str, Any]:
        """Read current screen content from a terminal.
        
        Args:
            session_id: ID of the session
            format: Output format ("text", "structured", "raw")
            
        Returns:
            Dictionary with screen content based on format
            
        Example:
            output = terminal.read(session_id)
            print(output['screen'])
        """
        request = {
            "action": "read",
            "session_id": session_id,
            "data": {
                "format": format
            }
        }
        
        response = self._send_request(request)
        
        if response['status'] == 'success':
            return response.get('data', {})
        else:
            raise TerminalError(f"Failed to read screen: {response.get('message', 'Unknown error')}")
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all active terminal sessions.
        
        Returns:
            List of session information dictionaries
            
        Example:
            sessions = terminal.list_sessions()
            for session in sessions:
                print(f"{session['session_id']}: {session['command']}")
        """
        request = {"action": "list"}
        
        response = self._send_request(request)
        
        if response['status'] == 'success':
            return response.get('data', {}).get('sessions', [])
        else:
            raise TerminalError(f"Failed to list sessions: {response.get('message', 'Unknown error')}")
    
    def close(self, session_id: str):
        """Close a terminal session.
        
        Args:
            session_id: ID of the session to close
            
        Example:
            terminal.close(session_id)
        """
        request = {
            "action": "close",
            "session_id": session_id
        }
        
        response = self._send_request(request)
        
        if response['status'] == 'success':
            logger.info(f"Closed terminal session: {session_id}")
        else:
            raise TerminalError(f"Failed to close session: {response.get('message', 'Unknown error')}")
    
    def execute_command(self, command: str, shell: str = "bash") -> str:
        """Execute a single command and return output.
        
        Convenience method for one-off commands.
        
        Args:
            command: Command to execute
            shell: Shell to use (default: bash)
            
        Returns:
            Command output as string
            
        Example:
            result = terminal.execute_command("ls -la")
            print(result)
        """
        session = None
        try:
            # Create session
            session = self.create(shell)
            
            # Send command
            self.send(session, command)
            
            # Wait for execution
            time.sleep(0.5)
            
            # Read output
            output = self.read(session)
            
            return output.get('screen', '')
            
        finally:
            # Always cleanup
            if session:
                try:
                    self.close(session)
                except:
                    pass
    
    def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request to the terminal body file and get response.
        
        Args:
            request: Request data to send
            
        Returns:
            Response data from terminal handler
        """
        # Write request
        with open(self.terminal_body, 'w') as f:
            json.dump({"request": request}, f, indent=2)
        
        # Wait for response
        max_attempts = 50  # 5 seconds timeout
        for i in range(max_attempts):
            time.sleep(0.1)
            
            try:
                with open(self.terminal_body, 'r') as f:
                    data = json.load(f)
                
                if 'response' in data:
                    return data['response']
                    
            except (json.JSONDecodeError, FileNotFoundError):
                # File might be in process of being written
                continue
        
        raise TerminalError("Timeout waiting for terminal response")
    
    def interactive_session(self, session_id: str, steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute a series of interactive commands.
        
        Args:
            session_id: Session to use
            steps: List of step dictionaries with 'input' and optional 'wait' time
            
        Returns:
            List of results with input and output for each step
            
        Example:
            steps = [
                {"input": "x = 10", "wait": 0.2},
                {"input": "y = 20", "wait": 0.2},
                {"input": "print(x + y)", "wait": 0.5}
            ]
            results = terminal.interactive_session(session_id, steps)
        """
        results = []
        
        for step in steps:
            input_text = step.get('input', '')
            wait_time = step.get('wait', 0.3)
            
            # Send input
            self.send(session_id, input_text)
            
            # Wait for processing
            time.sleep(wait_time)
            
            # Read output
            output = self.read(session_id)
            
            results.append({
                'input': input_text,
                'output': output.get('screen', ''),
                'cursor': output.get('cursor')
            })
        
        return results


# Create singleton instance for module-level API
_terminal_instance = None

def get_terminal(context):
    """Get or create terminal instance."""
    global _terminal_instance
    if _terminal_instance is None:
        _terminal_instance = Terminal(context)
    return _terminal_instance

# Module-level convenience functions
def create(command: str = "bash", name: Optional[str] = None) -> str:
    """Create a new terminal session."""
    return get_terminal({}).create(command, name)

def send(session_id: str, input_text: str):
    """Send input to a terminal session."""
    return get_terminal({}).send(session_id, input_text)

def read(session_id: str, format: str = "text") -> Dict[str, Any]:
    """Read current screen content from a terminal."""
    return get_terminal({}).read(session_id, format)

def list_sessions() -> List[Dict[str, Any]]:
    """List all active terminal sessions."""
    return get_terminal({}).list_sessions()

def close(session_id: str):
    """Close a terminal session."""
    return get_terminal({}).close(session_id)

def execute_command(command: str, shell: str = "bash") -> str:
    """Execute a single command and return output."""
    return get_terminal({}).execute_command(command, shell)