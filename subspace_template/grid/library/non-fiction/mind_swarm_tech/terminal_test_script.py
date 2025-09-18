#!/usr/bin/env python3
"""
Terminal Test Script for Cybers

This script demonstrates how to use the terminal and terminal_sessions APIs
to play a simple text adventure game and browse the web.

Run this in your execution stage to test terminal capabilities.
"""

import time
from datetime import datetime

print("=== Terminal Capability Test ===")
print("Testing terminal sessions for games and web browsing\n")

# Test 1: Basic Terminal Session
print("Test 1: Creating basic terminal session...")
try:
    # Create a basic bash session
    basic_session = terminal.create("bash", "test_bash")
    print(f"✓ Created session: {basic_session}")
    
    # Send a command
    terminal.send(basic_session, "echo 'Hello from terminal!'")
    time.sleep(0.3)
    
    # Read output
    output = terminal.read(basic_session)
    print(f"✓ Command output: {output['screen'][:100]}")
    
    # Close session
    terminal.close(basic_session)
    print("✓ Session closed\n")
except Exception as e:
    print(f"✗ Basic terminal test failed: {e}\n")

# Test 2: Persistent Session with terminal_sessions
print("Test 2: Creating persistent session...")
try:
    # Create persistent Python REPL
    repl = terminal_sessions.create_persistent_session("python3", "test_repl", "repl")
    print(f"✓ Created persistent session: {repl}")
    
    # Execute some Python
    response = terminal_sessions.send_and_remember(repl, "x = 42")
    response = terminal_sessions.send_and_remember(repl, "print(f'The answer is {x}')")
    print(f"✓ Python output: {response['screen'][:100]}")
    
    # Save snapshot
    snapshot_id = terminal_sessions.save_snapshot(repl, "test_snapshot")
    print(f"✓ Saved snapshot: {snapshot_id}")
    
    # Get session state
    state = terminal_sessions.get_session_state(repl)
    print(f"✓ Session active: {state['active']}")
    
    # Store in working memory
    working_memory.add("test_session_state", state)
    print("✓ Stored state in working memory\n")
    
except Exception as e:
    print(f"✗ Persistent session test failed: {e}\n")

# Test 3: Web Browsing (if network available)
print("Test 3: Testing web browsing...")
try:
    # Create web browser session
    browser = terminal_sessions.create_web_session("curl", "test_browser")
    print(f"✓ Created web session: {browser}")
    
    # Try to fetch a simple webpage
    terminal_sessions.send_and_remember(browser, "curl -I https://example.com")
    time.sleep(1)
    
    response = terminal_sessions.get_screen_content(browser)
    if "200 OK" in response or "HTTP" in response:
        print("✓ Successfully accessed web!")
        print(f"  Response preview: {response[:150]}")
    else:
        print("△ Web access returned unexpected response")
    
    # Save web content
    terminal_sessions.save_snapshot(browser, "web_test")
    print("✓ Saved web snapshot\n")
    
except Exception as e:
    print(f"△ Web browsing test skipped or failed: {e}")
    print("  (This is OK if network access is not available)\n")

# Test 4: Game Session (Simple number guessing game simulation)
print("Test 4: Testing game session...")
try:
    # Create a simple interactive Python game
    game = terminal_sessions.create_game_session("python3", "number_game")
    print(f"✓ Created game session: {game}")
    
    # Start a simple number guessing game
    game_script = '''
import random
target = random.randint(1, 10)
print("I'm thinking of a number between 1 and 10!")
print(f"(Hint: it's {target})")
    '''
    
    results = terminal_sessions.execute_script(game, game_script)
    print("✓ Game initialized")
    
    # Make a guess
    terminal_sessions.send_and_remember(game, f"guess = {5}")
    terminal_sessions.send_and_remember(game, "print(f'You guessed {guess}')")
    terminal_sessions.send_and_remember(game, "print('Game Over!')")
    
    # Get game history
    history = terminal_sessions.get_command_history(game, 5)
    print(f"✓ Game commands executed: {len(history)}")
    
    # Save game state
    game_state = terminal_sessions.get_session_state(game)
    working_memory.add_pinned("game_test_state", {
        "session": game,
        "history": history,
        "timestamp": datetime.now().isoformat()
    })
    print("✓ Game state saved to working memory\n")
    
except Exception as e:
    print(f"✗ Game session test failed: {e}\n")

# Test 5: Session Recovery
print("Test 5: Testing session recovery...")
try:
    # Try to get the REPL session we created earlier
    recovered = terminal_sessions.get_session("test_repl")
    if recovered:
        print(f"✓ Recovered session: {recovered}")
        
        # Verify the variable is still there
        terminal_sessions.send_and_remember(recovered, "print(f'x is still {x}')")
        response = terminal_sessions.get_screen_content(recovered)
        if "42" in response:
            print("✓ Session state preserved!")
        else:
            print("△ Session exists but state unclear")
    else:
        print("△ Could not recover session (this is OK for first run)")
    
except Exception as e:
    print(f"△ Session recovery test failed: {e}\n")

# Test 6: List all active sessions
print("Test 6: Listing active sessions...")
try:
    active = terminal_sessions.list_active_sessions()
    print(f"✓ Found {len(active)} active sessions:")
    for session in active:
        print(f"  - {session['name']} ({session['type']}): {session['commands']} commands")
    print()
except Exception as e:
    print(f"✗ Listing sessions failed: {e}\n")

# Summary
print("=== Test Summary ===")
print("Terminal capabilities have been tested!")
print("The following features are now available:")
print("1. Basic terminal sessions for commands")
print("2. Persistent sessions that survive cycles")
print("3. Web browsing capabilities (if network available)")
print("4. Game session management")
print("5. Session recovery and state preservation")
print("6. Working memory integration")
print("\nCybers can now play text adventures and browse the web!")

# Store test results
test_results = {
    "test_time": datetime.now().isoformat(),
    "capabilities": [
        "terminal_sessions",
        "persistent_state",
        "web_browsing",
        "game_playing",
        "session_recovery"
    ],
    "status": "complete"
}

working_memory.add("terminal_test_results", test_results)
print("\nTest results stored in working memory.")