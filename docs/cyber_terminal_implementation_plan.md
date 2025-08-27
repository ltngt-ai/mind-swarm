# Cyber Terminal Implementation Plan for Mind-Swarm

## Executive Summary

Implement a terminal interaction system that allows Cybers to create and manage multiple terminal sessions during their execution phase. Each Cyber can have N open terminals, interact with them through a Python module API, see terminal screens in their working memory, and send commands via body files.

## Architecture Overview

### Core Design Principles

1. **Multi-Terminal Support**: Each Cyber can manage up to N concurrent terminal sessions
2. **Sandbox Integration**: Terminals run within the Cyber's bubblewrap sandbox
3. **Body File Communication**: Terminal I/O through special body files (like brain/network)
4. **Memory Integration**: Terminal screens appear as memory blocks in working memory
5. **Stateless Interaction**: Each cognitive cycle can read/write terminals independently

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                        Subspace Server                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            Terminal Manager (Server Side)             │   │
│  │  - Session registry                                   │   │
│  │  - PTY management                                     │   │
│  │  - Process lifecycle                                  │   │
│  │  - Body file handlers                                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│                    Body File Bridge                          │
│                           │                                  │
└───────────────────────────┼──────────────────────────────────┘
                            │
                   Sandbox Boundary
                            │
┌───────────────────────────┼──────────────────────────────────┐
│                    Cyber Sandbox                              │
│                           │                                   │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              Terminal Python Module                    │    │
│  │  - Session creation/management                        │    │
│  │  - Screen reading                                     │    │
│  │  - Command sending                                    │    │
│  │  - Integration with execution stage                   │    │
│  └──────────────────────────────────────────────────────┘    │
│                           │                                   │
│  ┌──────────────────────────────────────────────────────┐    │
│  │            Cognitive Loop & Memory System              │    │
│  │  - Terminal screens as memory blocks                  │    │
│  │  - Context builder integration                        │    │
│  │  - Execution stage terminal actions                   │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

## Implementation Phases

### Phase 1: Server-Side Terminal Infrastructure

#### 1.1 Terminal Manager Component
```python
# src/mind_swarm/subspace/terminal_manager.py

class CyberTerminalManager:
    """Manages terminal sessions for all Cybers."""
    
    def __init__(self, subspace_coordinator):
        self.coordinator = subspace_coordinator
        self.sessions = {}  # {cyber_id: {session_id: TerminalSession}}
        self.max_sessions_per_cyber = 5
        
    async def create_session(self, cyber_id: str, command: str = "bash") -> str:
        """Create a new terminal session for a Cyber."""
        # Create PTY pair
        # Spawn process in Cyber's sandbox context
        # Register session
        # Return session_id
        
    async def handle_terminal_body(self, cyber_id: str, body_content: dict):
        """Process terminal body file requests."""
        # Parse command (create, read, write, close)
        # Execute appropriate action
        # Write response back to body file
```

#### 1.2 Body File Structure
```json
// /subspace/cybers/{name}/.internal/terminal
{
  "request": {
    "action": "create|read|write|close|list",
    "session_id": "term-001",
    "data": {
      // Action-specific data
      "command": "python3",  // for create
      "input": "print('hello')",  // for write
      "format": "text|structured"  // for read
    }
  },
  "response": {
    "status": "success|error",
    "session_id": "term-001",
    "data": {
      // Response data
      "screen": "...",  // for read
      "sessions": [...]  // for list
    }
  }
}
```

### Phase 2: Cyber-Side Python Module

#### 2.1 Terminal API Module
```python
# subspace_template/grid/library/base_code/base_code_template/python_modules/terminal.py

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
print(f"Python version: {output}")
terminal.close(session_id)
```

### Intention: "I want to interact with a database CLI"
```python
session_id = terminal.create("sqlite3 /data/my_database.db")
terminal.send(session_id, ".tables")
tables = terminal.read(session_id)
for table in tables.split('\n'):
    terminal.send(session_id, f"SELECT COUNT(*) FROM {table};")
    count = terminal.read(session_id)
    print(f"{table}: {count} rows")
```
"""

class Terminal:
    def __init__(self, context):
        self.context = context
        self.terminal_body = Path('/personal/.internal/terminal')
        
    def create(self, command: str = "bash", name: str = None) -> str:
        """Create a new terminal session."""
        request = {
            "action": "create",
            "data": {"command": command, "name": name}
        }
        response = self._send_request(request)
        return response['session_id']
        
    def send(self, session_id: str, input_text: str):
        """Send input to a terminal session."""
        request = {
            "action": "write",
            "session_id": session_id,
            "data": {"input": input_text}
        }
        self._send_request(request)
        
    def read(self, session_id: str, format: str = "text") -> str:
        """Read current screen content from a terminal."""
        request = {
            "action": "read",
            "session_id": session_id,
            "data": {"format": format}
        }
        response = self._send_request(request)
        return response['data']['screen']
        
    def list_sessions(self) -> List[dict]:
        """List all active terminal sessions."""
        request = {"action": "list"}
        response = self._send_request(request)
        return response['data']['sessions']
        
    def close(self, session_id: str):
        """Close a terminal session."""
        request = {
            "action": "close",
            "session_id": session_id
        }
        self._send_request(request)
```

### Phase 3: Memory Integration

#### 3.1 Terminal Screen Memory Blocks
```python
# In perception/environment_scanner.py

def _scan_terminal_sessions(self) -> List[MemoryBlock]:
    """Scan active terminal sessions and create memory blocks."""
    blocks = []
    
    # Check for terminal sessions
    terminal_body = self.personal / '.internal' / 'terminal'
    if terminal_body.exists():
        # Read terminal state
        # Create memory blocks for each session screen
        for session in active_sessions:
            block = MemoryBlock(
                id=f"terminal/{session['id']}/screen",
                type=MemoryType.TERMINAL,
                priority=Priority.HIGH,
                content=f"Terminal {session['name']} ({session['command']}):\n{session['screen']}",
                metadata={
                    "session_id": session['id'],
                    "command": session['command'],
                    "cursor": session['cursor_position']
                }
            )
            blocks.append(block)
    
    return blocks
```

### Phase 4: Execution Stage Integration

#### 4.1 Terminal Actions in Execution Stage
```python
# In stages/execution_stage.py

async def _execute_terminal_action(self, action: dict) -> dict:
    """Execute terminal-related actions."""
    terminal = self.context.get_api('terminal')
    
    action_type = action.get('terminal_action')
    
    if action_type == 'create_session':
        session_id = terminal.create(
            command=action.get('command', 'bash'),
            name=action.get('name')
        )
        return {"session_id": session_id, "status": "created"}
        
    elif action_type == 'run_command':
        session_id = action.get('session_id')
        command = action.get('command')
        
        # Send command
        terminal.send(session_id, command)
        
        # Wait for output
        await asyncio.sleep(0.5)
        
        # Read result
        output = terminal.read(session_id)
        return {"output": output, "status": "executed"}
        
    elif action_type == 'interactive_session':
        # Handle multi-step terminal interaction
        session_id = action.get('session_id')
        steps = action.get('steps', [])
        
        results = []
        for step in steps:
            terminal.send(session_id, step['input'])
            await asyncio.sleep(step.get('wait', 0.5))
            output = terminal.read(session_id)
            results.append({
                "input": step['input'],
                "output": output
            })
        
        return {"results": results, "status": "completed"}
```

## API Endpoints

### REST API Extensions

```python
# In src/mind_swarm/server/api.py

@app.post("/cybers/{cyber_id}/terminals")
async def create_terminal(cyber_id: str, request: TerminalRequest):
    """Create a new terminal session for a Cyber."""
    session_id = await terminal_manager.create_session(
        cyber_id=cyber_id,
        command=request.command
    )
    return {"session_id": session_id}

@app.get("/cybers/{cyber_id}/terminals")
async def list_terminals(cyber_id: str):
    """List all terminal sessions for a Cyber."""
    sessions = terminal_manager.get_sessions(cyber_id)
    return {"sessions": sessions}

@app.post("/cybers/{cyber_id}/terminals/{session_id}/input")
async def send_terminal_input(cyber_id: str, session_id: str, request: InputRequest):
    """Send input to a terminal session."""
    await terminal_manager.send_input(cyber_id, session_id, request.input)
    return {"status": "sent"}

@app.get("/cybers/{cyber_id}/terminals/{session_id}/screen")
async def read_terminal_screen(cyber_id: str, session_id: str):
    """Read current screen content from a terminal."""
    screen = await terminal_manager.read_screen(cyber_id, session_id)
    return {"screen": screen}

@app.delete("/cybers/{cyber_id}/terminals/{session_id}")
async def close_terminal(cyber_id: str, session_id: str):
    """Close a terminal session."""
    await terminal_manager.close_session(cyber_id, session_id)
    return {"status": "closed"}
```

### WebSocket Events

```python
# Terminal-related WebSocket events
{
    "type": "terminal_created",
    "cyber_id": "Alice",
    "session_id": "term-001",
    "command": "python3"
}

{
    "type": "terminal_output",
    "cyber_id": "Alice", 
    "session_id": "term-001",
    "output": ">>> print('Hello')\nHello"
}

{
    "type": "terminal_closed",
    "cyber_id": "Alice",
    "session_id": "term-001"
}
```

## Use Cases

### 1. Code Testing and Debugging
```python
# Cyber running tests in isolated terminal
session = terminal.create("python3")
terminal.send(session, "import unittest")
terminal.send(session, "exec(open('test_suite.py').read())")
results = terminal.read(session)
# Analyze test results in working memory
```

### 2. Database Operations
```python
# Cyber managing database through CLI
session = terminal.create("psql -U cyber -d mindswarm")
terminal.send(session, "\\dt")  # List tables
tables = terminal.read(session)
# Process table list and perform operations
```

### 3. System Monitoring
```python
# Cyber monitoring system resources
session = terminal.create("bash")
terminal.send(session, "top -b -n 1")
stats = terminal.read(session)
# Parse and analyze system statistics
```

### 4. Interactive Tool Automation
```python
# Cyber automating interactive CLI tools
session = terminal.create("npm init")
# Read prompts and respond appropriately
while "package name:" in terminal.read(session):
    terminal.send(session, "my-project")
    # Continue through initialization prompts
```

## Configuration

### Server Configuration
```python
# In .env or config
CYBER_MAX_TERMINALS=5          # Max terminals per Cyber
TERMINAL_TIMEOUT=3600          # Terminal session timeout (seconds)
TERMINAL_BUFFER_SIZE=10000     # Lines of scrollback per terminal
TERMINAL_CLEANUP_INTERVAL=300  # Cleanup check interval (seconds)
```

### Cyber Configuration
```yaml
# In cyber identity or config
terminal:
  enabled: true
  max_sessions: 3
  default_shell: bash
  allowed_commands:
    - python3
    - node
    - sqlite3
    - bash
  forbidden_commands:
    - sudo
    - rm -rf
```

## Security Considerations

1. **Sandbox Isolation**: All terminals run within the Cyber's existing bubblewrap sandbox
2. **Command Filtering**: Optionally restrict which commands Cybers can execute
3. **Resource Limits**: Enforce limits on number of sessions and resource usage
4. **Output Sanitization**: Filter sensitive information from terminal output
5. **Session Timeouts**: Automatic cleanup of idle sessions

## Benefits

1. **Enhanced Capabilities**: Cybers can interact with any CLI tool or REPL
2. **Persistent Sessions**: Terminals survive across cognitive cycles
3. **Memory Integration**: Terminal state visible in working memory for decision-making
4. **Parallel Operations**: Multiple terminals for concurrent tasks
5. **Debugging Support**: Cybers can test and debug their own code
6. **Tool Automation**: Automate any interactive CLI application

## Implementation Timeline

- **Week 1**: Server-side terminal manager and PTY handling
- **Week 2**: Body file handlers and API endpoints
- **Week 3**: Cyber-side Python module and memory integration
- **Week 4**: Execution stage actions and testing
- **Week 5**: Security hardening and optimization
- **Week 6**: Documentation and examples

## Success Metrics

- Cybers can create and manage multiple terminal sessions
- Terminal screens appear in working memory
- Commands execute reliably with proper output capture
- No process leaks or orphaned terminals
- Minimal performance impact on cognitive loop
- Clear documentation and examples for Cyber developers

## Next Steps

1. Review and approve implementation plan
2. Set up development branch for terminal feature
3. Begin Phase 1 implementation (server-side infrastructure)
4. Create test suite for terminal functionality
5. Develop example use cases for Cybers