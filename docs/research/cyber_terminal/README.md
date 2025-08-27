# Cyber Terminal

A comprehensive terminal interaction system designed for AI agents (Cybers) to interact with command-line applications through a cognitive loop pattern of **read-screen → think → type-input**.

## Features

- **Multi-Agent Support**: Multiple AI agents can operate terminal sessions simultaneously
- **Persistent Sessions**: Sessions survive system restarts and agent reconnections  
- **Full Terminal Emulation**: Complete ANSI escape sequence processing and terminal state management
- **Flexible Input Handling**: Support for text, control sequences, and special keys
- **Multiple Output Formats**: Text, structured, raw, and ANSI-preserved formats
- **Event System**: Subscribe to session events for reactive programming
- **Session Management**: Create, monitor, and manage terminal sessions programmatically
- **Clean Python API**: Intuitive interface optimized for AI agent workflows

## Quick Start

### Installation

```bash
pip install cyber-terminal
```

### Basic Usage

```python
from cyber_terminal import CyberTerminal

# Create terminal system
with CyberTerminal() as terminal:
    # Start a session
    session_id = terminal.create_session("python3")
    
    # Read initial screen
    content = terminal.read_screen(session_id)
    print(content.text)
    
    # Send input
    terminal.send_input(session_id, "print('Hello from AI agent!')")
    
    # Read response
    content = terminal.read_screen(session_id)
    print(content.text)
```

### Cognitive Loop Pattern

```python
def ai_agent_loop(terminal, session_id):
    while True:
        # 1. Read current screen state
        screen = terminal.read_screen(session_id, format='structured')
        
        # 2. Think - analyze screen content (your AI logic here)
        next_action = analyze_screen_and_decide(screen.text)
        
        # 3. Type input based on analysis
        if next_action['type'] == 'command':
            terminal.send_input(session_id, next_action['command'])
        elif next_action['type'] == 'key':
            terminal.send_input(session_id, next_action['key'], input_type='key')
        elif next_action['type'] == 'done':
            break
        
        # Brief pause before next iteration
        time.sleep(0.5)
```

## API Reference

### CyberTerminal Class

#### Session Management

```python
# Create a new terminal session
session_id = terminal.create_session(
    command="bash",                    # Command to execute
    working_dir="/home/user",          # Working directory
    env={"TERM": "xterm-256color"},    # Environment variables
    name="my_session",                 # Session name
    terminal_size=(24, 80)             # Terminal dimensions
)

# List active sessions
sessions = terminal.list_sessions()

# Get session information
info = terminal.get_session_info(session_id)

# Terminate session
terminal.terminate_session(session_id, force=False)
```

#### Screen Reading

```python
# Read screen content
content = terminal.read_screen(
    session_id,
    format='text',        # 'text', 'structured', 'raw', 'ansi'
    lines=50,            # Limit to last N lines
    since_last=False     # Only new content since last read
)

# Access content properties
print(content.text)                    # Clean text content
print(content.cursor_position)         # (row, col)
print(content.terminal_size)           # (rows, cols)
print(content.lines)                   # List of lines
```

#### Input Handling

```python
# Send text input (with automatic newline)
terminal.send_input(session_id, "ls -la", input_type='text')

# Send text without newline
terminal.send_input(session_id, "partial", input_type='text_no_newline')

# Send special keys
terminal.send_input(session_id, "Up", input_type='key')
terminal.send_input(session_id, "Ctrl+C", input_type='key')

# Send control sequences
terminal.send_input(session_id, "\\x03", input_type='control')  # Ctrl+C
terminal.send_input(session_id, "^C", input_type='control')     # Ctrl+C
```

#### Event System

```python
# Subscribe to events
def on_session_created(session_id, session):
    print(f"New session created: {session_id}")

def on_output_received(session_id, data):
    print(f"New output from {session_id}: {len(data)} bytes")

terminal.subscribe('session_created', on_session_created)
terminal.subscribe('output_received', on_output_received)
```

### Async Support

```python
from cyber_terminal import AsyncCyberTerminal

async def async_example():
    async with AsyncCyberTerminal() as terminal:
        session_id = await terminal.create_session("python3")
        content = await terminal.read_screen(session_id)
        await terminal.send_input(session_id, "print('Async!')")
```

## Command Line Interface

The package includes a CLI for testing and session management:

```bash
# Create a new session
cyber-terminal create "python3" --name python_session --interactive

# List active sessions
cyber-terminal list

# Read screen content
cyber-terminal read <session_id>

# Send input to session
cyber-terminal input <session_id> "print('Hello')"

# Interactive mode
cyber-terminal interactive <session_id>

# Terminate session
cyber-terminal terminate <session_id>
```

## Configuration

```python
from cyber_terminal import CyberTerminal, CyberTerminalConfig

config = CyberTerminalConfig(
    max_sessions=50,           # Maximum concurrent sessions
    session_timeout=3600,      # Session timeout in seconds
    buffer_size=10000,         # Scrollback buffer size
    cleanup_interval=300,      # Cleanup interval in seconds
    log_level='INFO',          # Logging level
    auto_cleanup=True          # Enable automatic cleanup
)

terminal = CyberTerminal(config)
```

## Advanced Features

### Session Persistence

Sessions are automatically persisted to SQLite database and restored on system restart:

```python
# Sessions survive system restarts
terminal = CyberTerminal()
# Previously created sessions are automatically restored
sessions = terminal.list_sessions()
```

### Terminal Resizing

```python
# Resize terminal dynamically
terminal.resize_terminal(session_id, rows=30, cols=120)
```

### Multiple Output Formats

```python
# Text format (clean, AI-friendly)
content = terminal.read_screen(session_id, format='text')

# Structured format (with metadata)
content = terminal.read_screen(session_id, format='structured')
print(content.metadata['cursor_visible'])
print(content.metadata['terminal_modes'])

# Raw format (with character attributes)
content = terminal.read_screen(session_id, format='raw')
for line in content.formatted_lines:
    for char in line:
        print(f"'{char.char}' - bold: {char.attributes.bold}")
```

### Special Key Support

```python
# Navigation keys
terminal.send_input(session_id, "Up", input_type='key')
terminal.send_input(session_id, "Down", input_type='key')
terminal.send_input(session_id, "Home", input_type='key')
terminal.send_input(session_id, "End", input_type='key')

# Function keys
terminal.send_input(session_id, "F1", input_type='key')
terminal.send_input(session_id, "F12", input_type='key')

# Control combinations
terminal.send_input(session_id, "Ctrl+A", input_type='key')
terminal.send_input(session_id, "Alt+B", input_type='key')
```

## Use Cases

### Interactive Application Automation

```python
# Automate interactive installers, configuration tools, etc.
session_id = terminal.create_session("./installer.sh")

while True:
    screen = terminal.read_screen(session_id)
    
    if "Do you agree? (y/n)" in screen.text:
        terminal.send_input(session_id, "y")
    elif "Installation complete" in screen.text:
        break
    
    time.sleep(1)
```

### Development Environment Management

```python
# Manage development servers, REPLs, etc.
session_id = terminal.create_session("python3")

# Set up environment
terminal.send_input(session_id, "import numpy as np")
terminal.send_input(session_id, "import pandas as pd")

# Interactive analysis
while True:
    command = get_next_analysis_command()  # Your AI logic
    terminal.send_input(session_id, command)
    
    result = terminal.read_screen(session_id)
    process_analysis_result(result.text)  # Your AI logic
```

### Multi-Agent Coordination

```python
# Multiple agents working on different tasks
agents = []

for i, task in enumerate(tasks):
    session_id = terminal.create_session(task['command'])
    agent = AIAgent(terminal, session_id, task)
    agents.append(agent)

# Run agents concurrently
for agent in agents:
    agent.start()  # Each agent runs its own cognitive loop
```

## Architecture

The system is built with a modular architecture:

- **Terminal Buffer**: ANSI escape sequence processing and screen state management
- **PTY Manager**: Pseudo-terminal creation and I/O operations  
- **Process Manager**: Process lifecycle management and monitoring
- **Session Store**: SQLite-based persistence and session recovery
- **Input Handler**: Special key and control sequence processing
- **Event System**: Reactive programming support

## Requirements

- Python 3.8+
- Linux or macOS (PTY support required)
- No external dependencies (uses only Python standard library)

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please see CONTRIBUTING.md for guidelines.

## Support

- GitHub Issues: [Report bugs and request features](https://github.com/manus-ai/cyber-terminal/issues)
- Documentation: [Full API documentation](https://cyber-terminal.readthedocs.io/)
- Examples: See `examples/` directory for more usage patterns

