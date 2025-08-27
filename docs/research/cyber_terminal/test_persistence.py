#!/usr/bin/env python3
"""
Simple test to verify session persistence works correctly.
"""

import sys
import os
import time
import subprocess

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from src.cyber_terminal import CyberTerminal, CyberTerminalConfig


def test_persistence():
    """Test that sessions persist between Python process executions."""
    
    print("=== Testing Session Persistence ===")
    
    # Step 1: Create a session that should persist
    print("Step 1: Creating persistent session...")
    
    config = CyberTerminalConfig(auto_shutdown_sessions=False)
    terminal = CyberTerminal(config)
    
    session_id = terminal.create_session("bash", name="persistence_test")
    print(f"Created session: {session_id}")
    
    # Send a command to set up some state
    time.sleep(1)
    terminal.send_input(session_id, "export TEST_VAR='I should persist!'")
    time.sleep(0.5)
    
    # Read initial state
    content = terminal.read_screen(session_id)
    print("Initial state:")
    print(content.text[-200:])
    
    # Get process ID
    info = terminal.get_session_info(session_id)
    process_id = info.process_id
    print(f"Process ID: {process_id}")
    
    # Don't call shutdown - let the session persist
    print("Exiting Python without terminating session...")
    
    return session_id, process_id


def test_reconnect(expected_session_id, expected_process_id):
    """Test reconnecting to the persistent session."""
    
    print("\n=== Testing Reconnection ===")
    
    # Check if process is still alive
    try:
        os.kill(expected_process_id, 0)
        print(f"Process {expected_process_id} is still alive")
    except (OSError, ProcessLookupError):
        print(f"Process {expected_process_id} is dead")
        return False
    
    # Create new terminal instance
    config = CyberTerminalConfig(auto_shutdown_sessions=False)
    terminal = CyberTerminal(config)
    
    # List sessions
    sessions = terminal.list_sessions()
    print(f"Found {len(sessions)} sessions:")
    
    for session in sessions:
        print(f"  {session.session_id}: {session.name} ({session.status.value})")
        
        if session.session_id == expected_session_id:
            print(f"Found our session! Status: {session.status.value}")
            
            # Try to interact with it
            terminal.send_input(session.session_id, "echo $TEST_VAR")
            time.sleep(0.5)
            
            content = terminal.read_screen(session.session_id)
            print("Reconnected session state:")
            print(content.text[-200:])
            
            # Clean up
            terminal.terminate_session(session.session_id)
            print("Session terminated")
            return True
    
    print("Session not found!")
    return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "reconnect":
        # This is the reconnection test
        session_id = sys.argv[2]
        process_id = int(sys.argv[3])
        success = test_reconnect(session_id, process_id)
        sys.exit(0 if success else 1)
    else:
        # This is the initial test
        session_id, process_id = test_persistence()
        
        # Now run the reconnection test in a separate process
        print("\nRunning reconnection test in separate process...")
        result = subprocess.run([
            sys.executable, __file__, "reconnect", session_id, str(process_id)
        ], capture_output=True, text=True)
        
        print("Reconnection test output:")
        print(result.stdout)
        if result.stderr:
            print("Errors:")
            print(result.stderr)
        
        if result.returncode == 0:
            print("SUCCESS: Session persistence works!")
        else:
            print("FAILURE: Session persistence failed!")
            sys.exit(1)

