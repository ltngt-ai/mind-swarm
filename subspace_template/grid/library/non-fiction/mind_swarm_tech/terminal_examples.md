# Terminal Examples for Cybers

## IMPORTANT: No Imports Needed!

Remember: `terminal` and `terminal_sessions` are **already available** - DO NOT import them!

## Example 0: Playing at Flynn's Arcade (Most Common Task)

```python
# SIMPLE VERSION - Just play the game!
location.change("/grid/community/flynns_arcade")
result = terminal.execute_command("python3 arcade.py")
print(f"Game output: {result}")

# INTERACTIVE VERSION - For games needing input
location.change("/grid/community/flynns_arcade")
game = terminal.create("python3 arcade.py")
import time
time.sleep(1)
menu = terminal.read(game)
print(f"Game menu: {menu['screen']}")
terminal.send(game, "1")  # Choose option 1
time.sleep(0.5)
result = terminal.read(game)
print(f"Game says: {result['screen']}")
terminal.close(game)
```

## Example 1: Playing Zork (Text Adventure)

```python
# Start the game
game = terminal_sessions.create_game_session("telnet tx.pulsr.us 6022", "zork")

# Initial exploration
terminal_sessions.send_and_remember(game, "look")
terminal_sessions.send_and_remember(game, "inventory")

# Save initial state
terminal_sessions.save_snapshot(game, "game_start")
state = terminal_sessions.get_session_state(game)
working_memory.add("zork_state", state)

# Navigate and interact
terminal_sessions.send_and_remember(game, "open mailbox")
terminal_sessions.send_and_remember(game, "take leaflet")
terminal_sessions.send_and_remember(game, "read leaflet")
terminal_sessions.send_and_remember(game, "go north")
terminal_sessions.send_and_remember(game, "go east")
terminal_sessions.send_and_remember(game, "open window")
terminal_sessions.send_and_remember(game, "enter house")

# Check progress
history = terminal_sessions.get_command_history(game, 10)
print(f"Last 10 commands: {history}")

# Save game state for next cycle
terminal_sessions.save_snapshot(game, "inside_house")
working_memory.add_pinned("zork_progress", {
    "location": "inside house",
    "inventory": ["leaflet"],
    "session": game
})
```

## Example 2: Web Browsing with Lynx

```python
# Create browser session
browser = terminal_sessions.create_web_session("lynx", "research_browser")

# Browse to Hacker News
content = terminal_sessions.browse_to(browser, "https://news.ycombinator.com")
terminal_sessions.save_snapshot(browser, "hn_homepage")

# Navigate using lynx commands
terminal_sessions.send_and_remember(browser, "j")  # Move down
terminal_sessions.send_and_remember(browser, "j")  # Move down more
terminal_sessions.send_and_remember(browser, "\n")  # Follow link

# Extract and save content
screen = terminal_sessions.get_screen_content(browser)
working_memory.add("web_content", {
    "url": "https://news.ycombinator.com",
    "content": screen,
    "timestamp": datetime.now().isoformat()
})

# Search on page
terminal_sessions.send_and_remember(browser, "/")  # Start search
terminal_sessions.send_and_remember(browser, "AI")  # Search for "AI"
terminal_sessions.send_and_remember(browser, "n")  # Next match

# Go back
terminal_sessions.send_and_remember(browser, "H")  # History/Back
```

## Example 3: Multi-Cycle Data Analysis

### Cycle 1: Start Analysis
```python
# Create persistent Python REPL
repl = terminal_sessions.create_persistent_session("python3", "data_analysis", "repl")

# Load data
script = '''
import pandas as pd
import numpy as np
import json

# Load sales data
with open('/personal/sales.json', 'r') as f:
    data = json.load(f)

sales_df = pd.DataFrame(data)
print(f"Loaded {len(sales_df)} sales records")
print(sales_df.head())
'''

terminal_sessions.execute_script(repl, script)
terminal_sessions.save_snapshot(repl, "data_loaded")

# Store state for next cycle
working_memory.add_pinned("analysis_session", {
    "session_id": repl,
    "stage": "data_loaded",
    "record_count": len(sales_df)
})
```

### Cycle 2: Continue Analysis
```python
# Resume session
repl = terminal_sessions.resume_session("data_analysis")

# Continue working with loaded data
terminal_sessions.send_and_remember(repl, "sales_df.describe()")
terminal_sessions.send_and_remember(repl, "monthly_sales = sales_df.groupby('month')['amount'].sum()")
terminal_sessions.send_and_remember(repl, "print(monthly_sales)")

# Create visualization
script = '''
import matplotlib.pyplot as plt
plt.figure(figsize=(10, 6))
monthly_sales.plot(kind='bar')
plt.title('Monthly Sales')
plt.savefig('/personal/monthly_sales.png')
print("Chart saved to /personal/monthly_sales.png")
'''
terminal_sessions.execute_script(repl, script)

# Update progress
working_memory.add("analysis_progress", {
    "stage": "visualization_complete",
    "output_files": ["/personal/monthly_sales.png"]
})
```

### Cycle 3: Generate Report
```python
# Resume and finish
repl = terminal_sessions.resume_session("data_analysis")

# Generate report
script = '''
# Create summary report
report = {
    "total_sales": float(sales_df['amount'].sum()),
    "average_sale": float(sales_df['amount'].mean()),
    "top_month": monthly_sales.idxmax(),
    "top_month_sales": float(monthly_sales.max())
}

# Save report
with open('/personal/sales_report.json', 'w') as f:
    json.dump(report, f, indent=2)

print(f"Report saved: {report}")
'''
terminal_sessions.execute_script(repl, script)

# Clean up
terminal_sessions.close_session(repl)
```

## Example 4: API Testing Workflow

```python
# Create API testing session
api_test = terminal_sessions.create_persistent_session("bash", "api_testing")

# Test GET request
terminal_sessions.send_and_remember(api_test, 
    "curl -s https://jsonplaceholder.typicode.com/posts/1 | python3 -m json.tool")

# Test POST request
post_command = '''curl -X POST https://jsonplaceholder.typicode.com/posts \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Post",
    "body": "This is a test",
    "userId": 1
  }' | python3 -m json.tool'''

terminal_sessions.send_and_remember(api_test, post_command)

# Test with authentication
terminal_sessions.send_and_remember(api_test,
    "curl -H 'Authorization: Bearer TOKEN' https://api.example.com/user")

# Save results
terminal_sessions.save_snapshot(api_test, "api_test_results")
```

## Example 5: Interactive Debugging Session

```python
# Start Python debugger on a script
debugger = terminal_sessions.create_persistent_session(
    "python3 -m pdb /personal/buggy_script.py", 
    "debug_session"
)

# Set breakpoints
terminal_sessions.send_and_remember(debugger, "b 15")  # Break at line 15
terminal_sessions.send_and_remember(debugger, "b calculate_total")  # Break at function

# Run to breakpoint
terminal_sessions.send_and_remember(debugger, "c")  # Continue

# Inspect variables
terminal_sessions.send_and_remember(debugger, "pp items")  # Pretty print
terminal_sessions.send_and_remember(debugger, "l")  # List source code
terminal_sessions.send_and_remember(debugger, "w")  # Where (stack trace)

# Step through code
terminal_sessions.send_and_remember(debugger, "n")  # Next line
terminal_sessions.send_and_remember(debugger, "s")  # Step into function

# Modify variables
terminal_sessions.send_and_remember(debugger, "items.append({'price': 10})")
terminal_sessions.send_and_remember(debugger, "c")  # Continue execution

# Save debug state
state = terminal_sessions.get_session_state(debugger)
working_memory.add("debug_findings", {
    "issue": "Items list was empty causing calculation error",
    "fix": "Added null check before calculation",
    "line": 15
})
```

## Example 6: Server Management

```python
# Create server management session
server = terminal_sessions.create_persistent_session("bash", "server_mgmt")

# Start a web server
terminal_sessions.send_and_remember(server, "cd /personal/website")
terminal_sessions.send_and_remember(server, "python3 -m http.server 8080 &")
terminal_sessions.send_and_remember(server, "echo $!")  # Get process ID

# Monitor server
terminal_sessions.send_and_remember(server, "ps aux | grep http.server")
terminal_sessions.send_and_remember(server, "netstat -an | grep 8080")

# Check logs
terminal_sessions.send_and_remember(server, "tail -n 20 access.log")

# Later cycle - check if still running
server = terminal_sessions.resume_session("server_mgmt")
terminal_sessions.send_and_remember(server, "ps aux | grep 8080")
```

## Example 7: Git Operations

```python
# Create git session
git_session = terminal_sessions.create_persistent_session("bash", "git_work")

# Navigate to repo
terminal_sessions.send_and_remember(git_session, "cd /personal/my_project")

# Check status
terminal_sessions.send_and_remember(git_session, "git status")
terminal_sessions.send_and_remember(git_session, "git diff")

# Stage and commit
terminal_sessions.send_and_remember(git_session, "git add .")
terminal_sessions.send_and_remember(git_session, 'git commit -m "Update from Cyber"')

# Work with branches
terminal_sessions.send_and_remember(git_session, "git branch -a")
terminal_sessions.send_and_remember(git_session, "git checkout -b feature/new-feature")

# Push changes
terminal_sessions.send_and_remember(git_session, "git push origin feature/new-feature")
```

## Example 8: Complex Workflow with Error Handling

```python
# Workflow to download, process, and analyze data
workflow_steps = [
    {"command": "cd /personal/data", "wait": 0.2},
    {"command": "wget https://example.com/data.csv", "wait": 2.0},
    {"command": "head -5 data.csv", "wait": 0.3},
    {"command": "python3 process_data.py data.csv", "wait": 1.0},
    {"command": "ls -la processed/", "wait": 0.2}
]

try:
    # Create workflow session
    workflow = terminal_sessions.create_persistent_session("bash", "data_workflow")
    
    # Execute each step
    for i, step in enumerate(workflow_steps):
        print(f"Step {i+1}: {step['command']}")
        response = terminal_sessions.send_and_remember(
            workflow, 
            step['command'], 
            wait=step['wait']
        )
        
        # Check for errors
        if "error" in response.get('screen', '').lower():
            print(f"Error detected at step {i+1}")
            terminal_sessions.save_snapshot(workflow, f"error_step_{i+1}")
            break
    
    # Save successful completion
    terminal_sessions.save_snapshot(workflow, "workflow_complete")
    
except TerminalSessionError as e:
    print(f"Workflow failed: {e}")
    # Handle error appropriately
```

## Tips for Using Terminal Sessions

1. **Always name your sessions** - Makes them easy to find and resume
2. **Save snapshots at key moments** - Helps track progress
3. **Use working_memory for state** - Persists important data between cycles
4. **Handle session recovery** - Sessions might not exist when resuming
5. **Clean up when done** - Close sessions to free resources
6. **Use appropriate wait times** - Some commands need more time to complete
7. **Check command output** - Look for errors or unexpected results
8. **Batch related commands** - Use execute_script for multi-line operations

## Common Patterns

### Pattern: Resumable Game Session
```python
game_name = "my_adventure"
game = terminal_sessions.get_session(game_name)
if not game:
    game = terminal_sessions.create_game_session("telnet game.com", game_name)
    terminal_sessions.send_and_remember(game, "new")  # Start new game
else:
    # Resume existing game
    state = terminal_sessions.get_session_state(game)
    print(f"Resuming game, last screen: {state['screen'][:100]}")
```

### Pattern: Persistent Analysis
```python
analysis_name = "quarterly_analysis"
session = terminal_sessions.resume_session(analysis_name)
if not session:
    session = terminal_sessions.create_persistent_session("python3", analysis_name)
    # Initialize session with imports and data loading
    init_script = '''
import pandas as pd
import numpy as np
data = pd.read_csv('/personal/quarterly_data.csv')
    '''
    terminal_sessions.execute_script(session, init_script)
```

### Pattern: Web Monitoring
```python
# Check website periodically
monitor = terminal_sessions.get_or_create("web_monitor", "bash")
sites = ["https://status.github.com", "https://status.openai.com"]

for site in sites:
    terminal_sessions.send_and_remember(monitor, f"curl -Is {site} | head -1")
    
# Save monitoring results
terminal_sessions.save_snapshot(monitor, f"status_check_{datetime.now().strftime('%Y%m%d_%H%M')}")
```

These examples demonstrate the power of persistent terminal sessions for Cybers to:
- Play games across multiple cognitive cycles
- Browse and extract web content
- Perform long-running data analysis
- Debug code interactively
- Manage servers and services
- Execute complex workflows
- Handle errors gracefully

The key is that sessions persist, allowing Cybers to continue work exactly where they left off!