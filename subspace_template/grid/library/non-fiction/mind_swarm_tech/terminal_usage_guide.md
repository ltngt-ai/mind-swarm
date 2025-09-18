# Terminal Usage Guide for Cybers

## CRITICAL: No Import Required!

**IMPORTANT:** The `terminal` and `terminal_sessions` APIs are **already available** in your execution environment. You do NOT need to import them!

❌ **WRONG - This will cause ModuleNotFoundError:**
```python
import terminal  # DON'T DO THIS!
from terminal import Terminal  # DON'T DO THIS EITHER!
import terminal_sessions  # ALSO WRONG!
```

✅ **CORRECT - Just use them directly:**
```python
# They're already loaded for you!
session = terminal.create("bash")
result = terminal.execute_command("ls")
```

## Overview
The terminal API allows you to create interactive terminal sessions for running commands, playing games, browsing the web, and automating complex workflows. With the new `terminal_sessions` API, your sessions can persist across cognitive cycles.

## Basic Terminal Operations

### Creating Sessions
```python
# Basic terminal session
session = terminal.create("bash")

# Named session for easy retrieval
session = terminal.create("python3", name="data_analysis")

# Persistent session that survives cycles
session = terminal_sessions.create_persistent_session("python3", "my_repl")
```

### Sending Commands
```python
# Send a command
terminal.send(session, "ls -la")

# Wait and read response
import time
time.sleep(0.5)
output = terminal.read(session)
print(output['screen'])

# Send and remember (with history tracking)
response = terminal_sessions.send_and_remember(session, "pwd")
```

### Session Management
```python
# List active sessions
sessions = terminal.list_sessions()
for s in sessions:
    print(f"{s['session_id']}: {s['command']}")

# Close a session
terminal.close(session)

# Resume a named session
session = terminal_sessions.resume_session("my_repl")
```

## Web Browsing

### Using Text Browsers
```python
# Create a web browser session
browser = terminal_sessions.create_web_session("lynx", "news_browser")

# Navigate to a URL
content = terminal_sessions.browse_to(browser, "https://news.ycombinator.com")

# Save a snapshot for later reference
terminal_sessions.save_snapshot(browser, "hn_frontpage")

# Navigate links (lynx commands)
terminal.send(browser, "j")  # Move down
terminal.send(browser, "k")  # Move up  
terminal.send(browser, "\n")  # Follow link
terminal.send(browser, "H")  # Back
```

### Using curl for APIs
```python
# Create curl session
api_session = terminal.create("bash", "api_client")

# Make API request
terminal.send(api_session, "curl -s https://api.github.com/users/torvalds")
time.sleep(1)
response = terminal.read(api_session)
json_data = response['screen']

# POST request with data
terminal.send(api_session, '''curl -X POST https://api.example.com/data \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}' ''')
```

### Using wget for Downloads
```python
# Download file
downloader = terminal.create("bash", "downloader")
terminal.send(downloader, "wget https://example.com/file.pdf")

# Download with custom name
terminal.send(downloader, "wget -O report.pdf https://example.com/document")

# Download entire website
terminal.send(downloader, "wget -r -l 2 https://example.com")
```

## Playing Text Adventure Games

### Connecting to Games
```python
# Telnet games
game = terminal_sessions.create_game_session("telnet adventure.com 2023", "zork")

# SSH games
game = terminal_sessions.create_game_session("ssh nethack@alt.org", "nethack")

# Local games
game = terminal_sessions.create_game_session("frotz zork1.z5", "local_zork")
```

### Game Interaction Patterns
```python
# Start and explore
terminal_sessions.send_and_remember(game, "look")
terminal_sessions.send_and_remember(game, "inventory")
terminal_sessions.send_and_remember(game, "examine lamp")

# Movement
terminal_sessions.send_and_remember(game, "north")
terminal_sessions.send_and_remember(game, "go west")
terminal_sessions.send_and_remember(game, "enter house")

# Object interaction
terminal_sessions.send_and_remember(game, "take sword")
terminal_sessions.send_and_remember(game, "open door")
terminal_sessions.send_and_remember(game, "use key on lock")

# Save game state for decision making
state = terminal_sessions.get_session_state(game)
working_memory.add("game_state", state)

# Get command history to understand context
history = terminal_sessions.get_command_history(game, limit=10)
working_memory.add("game_history", history)
```

### MUD (Multi-User Dungeon) Games
```python
# Connect to MUD
mud = terminal_sessions.create_game_session("telnet mud.example.com 4000", "my_mud")

# Login sequence
terminal_sessions.send_and_remember(mud, "MyUsername")
terminal_sessions.send_and_remember(mud, "MyPassword")

# MUD commands
terminal_sessions.send_and_remember(mud, "say Hello everyone!")
terminal_sessions.send_and_remember(mud, "who")  # See who's online
terminal_sessions.send_and_remember(mud, "map")  # View area map
terminal_sessions.send_and_remember(mud, "skills")  # Check abilities
```

## Multi-Cycle Workflows

### Persistent Data Analysis
```python
# Cycle 1: Start analysis
repl = terminal_sessions.create_persistent_session("python3", "data_analysis")
terminal_sessions.execute_script(repl, '''
import pandas as pd
import numpy as np
data = pd.read_csv('/personal/sales.csv')
print(f"Loaded {len(data)} records")
''')

# Cycle 2: Continue analysis
repl = terminal_sessions.resume_session("data_analysis")
if repl:
    terminal_sessions.send_and_remember(repl, "data.describe()")
    terminal_sessions.send_and_remember(repl, "monthly = data.groupby('month').sum()")

# Cycle 3: Generate report
repl = terminal_sessions.resume_session("data_analysis")
if repl:
    terminal_sessions.send_and_remember(repl, "monthly.to_csv('/personal/report.csv')")
```

### Long-Running Processes
```python
# Start a server
server = terminal_sessions.create_persistent_session("bash", "web_server")
terminal_sessions.send_and_remember(server, "cd /personal/website")
terminal_sessions.send_and_remember(server, "python -m http.server 8080 &")

# Check status in later cycle
server = terminal_sessions.resume_session("web_server")
if server:
    terminal_sessions.send_and_remember(server, "ps aux | grep http.server")
    terminal_sessions.send_and_remember(server, "netstat -an | grep 8080")
```

### Interactive Debugging
```python
# Start debugger
debugger = terminal_sessions.create_persistent_session("python3 -m pdb script.py", "debug_session")

# Set breakpoints
terminal_sessions.send_and_remember(debugger, "b 42")  # Break at line 42
terminal_sessions.send_and_remember(debugger, "b function_name")  # Break at function

# Debug commands
terminal_sessions.send_and_remember(debugger, "n")  # Next line
terminal_sessions.send_and_remember(debugger, "s")  # Step into
terminal_sessions.send_and_remember(debugger, "c")  # Continue
terminal_sessions.send_and_remember(debugger, "pp variable")  # Pretty print
terminal_sessions.send_and_remember(debugger, "l")  # List code
```

## Terminal Patterns and Best Practices

### Session Naming Convention
```python
# Use descriptive names for easy retrieval
game_session = "adventure_game_zork"
web_session = "research_wikipedia" 
data_session = "analysis_sales_2024"
server_session = "api_server_production"
```

### Error Handling
```python
try:
    session = terminal_sessions.resume_session("my_session")
    if not session:
        # Session doesn't exist, create new one
        session = terminal_sessions.create_persistent_session("bash", "my_session")
    
    response = terminal_sessions.send_and_remember(session, "command")
    
except TerminalSessionError as e:
    print(f"Terminal error: {e}")
    # Handle error appropriately
```

### Saving Important State
```python
# Before ending a cycle, save important state
if game_session:
    # Save snapshot
    terminal_sessions.save_snapshot(game_session, f"cycle_{cycle_number}_end")
    
    # Store in working memory
    state = terminal_sessions.get_session_state(game_session)
    working_memory.add_pinned("game_progress", state)
    
    # Add to knowledge for long-term memory
    knowledge.store(
        content=f"Game state at cycle {cycle_number}: {state['screen']}",
        tags=["game", "zork", "progress"],
        personal=True
    )
```

### Efficient Command Execution
```python
# Batch commands when possible
script = '''
cd /personal/project
git status
git diff
git log --oneline -5
'''
results = terminal_sessions.execute_script(session, script)

# Use command chaining
terminal.send(session, "cd /tmp && wget file.txt && cat file.txt")

# Use background processes for long operations
terminal.send(session, "long_process &")
terminal.send(session, "echo $!")  # Get process ID
```

## Common Terminal Commands

### File Operations
```bash
ls -la              # List files with details
cd /path           # Change directory
pwd                # Print working directory
cat file.txt       # Display file content
head -n 10 file    # First 10 lines
tail -f log.txt    # Follow log file
grep "pattern" file # Search in file
find . -name "*.py" # Find files
```

### Network Operations
```bash
curl -I url        # Get headers only
curl -L url        # Follow redirects
wget -c url        # Continue download
ping -c 4 host     # Ping 4 times
traceroute host    # Trace network path
netstat -an        # Network connections
ss -tulpn          # Socket statistics
```

### Process Management
```bash
ps aux             # List all processes
top                # Interactive process viewer
htop               # Better process viewer
kill PID           # Terminate process
killall name       # Kill by name
jobs               # List background jobs
fg                 # Bring to foreground
bg                 # Send to background
```

### Text Processing
```bash
sed 's/old/new/g'  # Replace text
awk '{print $1}'   # Print first column
cut -d',' -f2      # Cut by delimiter
sort -n            # Numeric sort
uniq -c            # Count unique
wc -l              # Count lines
tr 'a-z' 'A-Z'     # Transform text
```

## Advanced Terminal Usage

### Terminal Multiplexing
```python
# Using screen or tmux for persistent sessions
terminal.send(session, "screen -S mysession")
terminal.send(session, "tmux new -s work")

# Detach and reattach
terminal.send(session, "Ctrl-a d")  # Screen detach
terminal.send(session, "Ctrl-b d")  # Tmux detach
terminal.send(session, "screen -r mysession")  # Reattach
```

### SSH Tunneling
```python
# Create SSH tunnel for secure access
tunnel = terminal.create("bash", "ssh_tunnel")
terminal.send(tunnel, "ssh -L 8080:localhost:80 user@server")

# SOCKS proxy
terminal.send(tunnel, "ssh -D 1080 user@server")
```

### Docker Containers
```python
# Run container
docker = terminal.create("bash", "docker_mgmt")
terminal.send(docker, "docker run -it ubuntu bash")

# Manage containers
terminal.send(docker, "docker ps -a")
terminal.send(docker, "docker logs container_id")
terminal.send(docker, "docker exec -it container_id bash")
```

## Remember

1. **Sessions persist** - Use terminal_sessions for multi-cycle work
2. **Name sessions** - Makes them easy to retrieve later
3. **Save snapshots** - Capture important moments
4. **Track history** - Commands are remembered automatically
5. **Handle errors** - Sessions might not exist when resuming
6. **Use working memory** - Store session state for decisions
7. **Clean up** - Close sessions when done to free resources

With these terminal capabilities, you can:
- Play text adventure games across multiple cycles
- Browse the web and remember what you found
- Run long data analysis sessions
- Manage servers and services
- Debug code interactively
- Automate complex workflows

The terminal is your window to the wider digital world - use it wisely!