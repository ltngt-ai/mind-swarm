#!/usr/bin/env python3
"""
Basic functionality test for Cyber Terminal.

This script tests the core functionality of the terminal system
with simple commands and interactive programs.
"""

import time
import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.cyber_terminal import CyberTerminal, CyberTerminalConfig


def test_basic_commands():
    """Test basic shell commands."""
    print("=== Testing Basic Commands ===")
    
    config = CyberTerminalConfig(log_level='INFO')
    
    with CyberTerminal(config) as terminal:
        # Create a bash session
        session_id = terminal.create_session("bash", name="test_bash")
        print(f"Created session: {session_id}")
        
        # Wait for shell to initialize
        time.sleep(1)
        
        # Read initial prompt
        content = terminal.read_screen(session_id)
        print("Initial screen:")
        print(content.text)
        print("-" * 40)
        
        # Test simple commands
        commands = [
            "echo 'Hello from Cyber Terminal!'",
            "pwd",
            "ls -la /tmp",
            "date",
            "whoami"
        ]
        
        for cmd in commands:
            print(f"Executing: {cmd}")
            terminal.send_input(session_id, cmd)
            
            # Wait for command to execute
            time.sleep(0.5)
            
            # Read output
            content = terminal.read_screen(session_id)
            print("Output:")
            print(content.text)
            print("-" * 40)
        
        # Test session info
        info = terminal.get_session_info(session_id)
        print(f"Session info: {info.name}, PID: {info.process_id}, Status: {info.status}")
        
        # Terminate session
        terminal.terminate_session(session_id)
        print("Session terminated")


def test_python_repl():
    """Test Python REPL interaction."""
    print("\n=== Testing Python REPL ===")
    
    with CyberTerminal() as terminal:
        # Create Python session
        session_id = terminal.create_session("python3", name="python_test")
        print(f"Created Python session: {session_id}")
        
        # Wait for Python to start
        time.sleep(1)
        
        # Read Python prompt
        content = terminal.read_screen(session_id)
        print("Python startup:")
        print(content.text)
        print("-" * 40)
        
        # Test Python commands
        python_commands = [
            "print('Hello from Python!')",
            "x = 42",
            "print(f'The answer is {x}')",
            "import math",
            "print(f'Pi is approximately {math.pi:.4f}')",
            "for i in range(3): print(f'Count: {i}')"
        ]
        
        for cmd in python_commands:
            print(f"Python: {cmd}")
            terminal.send_input(session_id, cmd)
            
            # Wait for execution
            time.sleep(0.5)
            
            # Read output
            content = terminal.read_screen(session_id)
            print("Output:")
            print(content.text)
            print("-" * 40)
        
        # Exit Python
        terminal.send_input(session_id, "exit()")
        time.sleep(0.5)
        
        print("Python session completed")


def test_special_keys():
    """Test special key handling."""
    print("\n=== Testing Special Keys ===")
    
    with CyberTerminal() as terminal:
        # Create bash session
        session_id = terminal.create_session("bash", name="key_test")
        
        # Wait for shell
        time.sleep(1)
        
        # Test command history navigation
        print("Testing command history...")
        
        # Enter a command
        terminal.send_input(session_id, "echo 'first command'")
        time.sleep(0.5)
        
        # Enter another command
        terminal.send_input(session_id, "echo 'second command'")
        time.sleep(0.5)
        
        # Start typing a new command but don't finish
        terminal.send_input(session_id, "echo 'partial", input_type='text_no_newline')
        
        # Use Up arrow to get previous command
        terminal.send_input(session_id, "Up", input_type='key')
        time.sleep(0.2)
        
        # Read screen to see command history
        content = terminal.read_screen(session_id)
        print("After Up arrow:")
        print(content.text)
        print("-" * 40)
        
        # Test Ctrl+C
        print("Testing Ctrl+C...")
        terminal.send_input(session_id, "Ctrl+C", input_type='key')
        time.sleep(0.5)
        
        content = terminal.read_screen(session_id)
        print("After Ctrl+C:")
        print(content.text)
        print("-" * 40)
        
        # Test Tab completion
        print("Testing Tab completion...")
        terminal.send_input(session_id, "ec", input_type='text_no_newline')
        terminal.send_input(session_id, "Tab", input_type='key')
        time.sleep(0.5)
        
        content = terminal.read_screen(session_id)
        print("After Tab completion:")
        print(content.text)
        print("-" * 40)
        
        terminal.terminate_session(session_id)


def test_session_persistence():
    """Test session persistence and recovery."""
    print("\n=== Testing Session Persistence ===")
    
    # Create a session and save it
    session_id = None
    with CyberTerminal() as terminal:
        session_id = terminal.create_session("bash", name="persistent_test")
        
        # Execute a command
        terminal.send_input(session_id, "export TEST_VAR='persistence_test'")
        time.sleep(0.5)
        
        terminal.send_input(session_id, "echo $TEST_VAR")
        time.sleep(0.5)
        
        content = terminal.read_screen(session_id)
        print("Before persistence test:")
        print(content.text)
        print("-" * 40)
        
        print(f"Session {session_id} should be persisted...")
    
    # Create new terminal instance (simulating restart)
    print("Creating new terminal instance...")
    with CyberTerminal() as terminal:
        sessions = terminal.list_sessions()
        print(f"Found {len(sessions)} persisted sessions")
        
        for session in sessions:
            print(f"Session: {session.session_id}, Name: {session.name}, Status: {session.status}")
            
            if session.name == "persistent_test":
                # Try to interact with persisted session
                terminal.send_input(session.session_id, "echo 'Session recovered!'")
                time.sleep(0.5)
                
                content = terminal.read_screen(session.session_id)
                print("After recovery:")
                print(content.text)
                print("-" * 40)
                
                # Clean up
                terminal.terminate_session(session.session_id)


def test_multiple_sessions():
    """Test multiple concurrent sessions."""
    print("\n=== Testing Multiple Sessions ===")
    
    with CyberTerminal() as terminal:
        # Create multiple sessions
        sessions = []
        
        # Bash session
        bash_id = terminal.create_session("bash", name="multi_bash")
        sessions.append(("bash", bash_id))
        
        # Python session
        python_id = terminal.create_session("python3", name="multi_python")
        sessions.append(("python", python_id))
        
        # Another bash session
        bash2_id = terminal.create_session("bash", name="multi_bash2")
        sessions.append(("bash2", bash2_id))
        
        # Wait for all to initialize
        time.sleep(2)
        
        # Interact with each session
        for session_type, session_id in sessions:
            print(f"Interacting with {session_type} session {session_id}")
            
            if session_type.startswith("bash"):
                terminal.send_input(session_id, f"echo 'Hello from {session_type}!'")
            elif session_type == "python":
                terminal.send_input(session_id, f"print('Hello from {session_type}!')")
            
            time.sleep(0.5)
            
            content = terminal.read_screen(session_id)
            print(f"{session_type} output:")
            print(content.text)
            print("-" * 40)
        
        # List all sessions
        all_sessions = terminal.list_sessions()
        print(f"Total active sessions: {len(all_sessions)}")
        
        for session in all_sessions:
            print(f"  {session.name}: {session.session_id} ({session.status})")
        
        # Clean up all sessions
        for _, session_id in sessions:
            terminal.terminate_session(session_id)
        
        print("All sessions terminated")


def main():
    """Run all tests."""
    print("Cyber Terminal - Comprehensive Test Suite")
    print("=" * 50)
    
    try:
        test_basic_commands()
        test_python_repl()
        test_special_keys()
        test_session_persistence()
        test_multiple_sessions()
        
        print("\n" + "=" * 50)
        print("All tests completed successfully!")
        
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

