#!/usr/bin/env python3
"""
Multi-Process Workflow Examples for Cyber Terminal.

This demonstrates the key use case where each cognitive loop iteration
is a separate Python process execution:

1. Python Process 1: Create session, exit
2. Python Process 2: Read screen, exit  
3. Python Process 3: Send input, exit
4. Python Process 4: Read screen, exit
5. ... (repeat until done)
6. Python Process N: Terminate session, exit

Each process is completely independent and sessions persist between executions.
"""

import sys
import os
import argparse
import json
import time

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.cyber_terminal import CyberTerminal, CyberTerminalConfig


def create_session(command, name=None, working_dir=None):
    """
    Step 1: Create a new terminal session.
    
    This Python process creates a session and then exits.
    The session continues running in the background.
    """
    print(f"Creating session for command: {command}")
    
    # Don't use context manager - we want session to persist
    terminal = CyberTerminal()
    session_id = terminal.create_session(
        command=command,
        name=name,
        working_dir=working_dir,
        terminal_size=(24, 80)
    )
    
    print(f"Session created: {session_id}")
    print(f"Session name: {name or 'auto-generated'}")
    
    # Wait a moment for session to initialize
    time.sleep(1)
    
    # Don't call terminal.shutdown() - let session persist
    
    # Return session info
    return {
        'session_id': session_id,
        'command': command,
        'name': name,
        'status': 'created'
    }


def read_screen(session_id, format_type='text', lines=None):
    """
    Step 2: Read screen content from existing session.
    
    This Python process connects to the existing session,
    reads the screen, and then exits.
    """
    print(f"Reading screen from session: {session_id}")
    
    terminal = CyberTerminal()
    try:
        # Read current screen content
        content = terminal.read_screen(
            session_id=session_id,
            format=format_type,
            lines=lines
        )
        
        result = {
            'session_id': session_id,
            'text': content.text,
            'cursor_position': content.cursor_position,
            'terminal_size': content.terminal_size,
            'timestamp': content.timestamp.isoformat(),
            'has_more': content.has_more,
            'lines': content.lines
        }
        
        print("Screen content:")
        print("-" * 40)
        print(content.text)
        print("-" * 40)
        
        return result
        
    except Exception as e:
        print(f"Error reading screen: {e}")
        return {'error': str(e)}


def send_input(session_id, input_data, input_type='text'):
    """
    Step 3: Send input to existing session.
    
    This Python process connects to the existing session,
    sends input, and then exits.
    """
    print(f"Sending input to session: {session_id}")
    print(f"Input: {repr(input_data)} (type: {input_type})")
    
    terminal = CyberTerminal()
    try:
        success = terminal.send_input(
            session_id=session_id,
            data=input_data,
            input_type=input_type
        )
        
        if success:
            print("Input sent successfully")
            return {'session_id': session_id, 'status': 'sent', 'input': input_data}
        else:
            print("Failed to send input")
            return {'session_id': session_id, 'status': 'failed', 'input': input_data}
            
    except Exception as e:
        print(f"Error sending input: {e}")
        return {'error': str(e)}


def list_sessions():
    """
    Utility: List all active sessions.
    
    This can be called from any Python process to see
    what sessions are currently running.
    """
    print("Listing active sessions...")
    
    terminal = CyberTerminal()
    sessions = terminal.list_sessions()
    
    if not sessions:
        print("No active sessions found")
        return []
    
    session_list = []
    print(f"Found {len(sessions)} active sessions:")
    print(f"{'ID':<12} {'Name':<20} {'Command':<30} {'Status':<12}")
    print("-" * 75)
    
    for session in sessions:
        session_data = {
            'session_id': session.session_id,
            'name': session.name,
            'command': session.command,
            'status': session.status.value,
            'created_at': session.created_at.isoformat(),
            'uptime': str(session.uptime)
        }
        session_list.append(session_data)
        
        print(f"{session.session_id[:12]:<12} {session.name[:20]:<20} "
              f"{session.command[:30]:<30} {session.status.value:<12}")
    
    return session_list


def get_session_info(session_id):
    """
    Utility: Get detailed information about a specific session.
    """
    print(f"Getting info for session: {session_id}")
    
    terminal = CyberTerminal()
    try:
        info = terminal.get_session_info(session_id)
        
        session_data = {
            'session_id': info.session_id,
            'name': info.name,
            'command': info.command,
            'process_id': info.process_id,
            'status': info.status.value,
            'working_directory': info.working_directory,
            'created_at': info.created_at.isoformat(),
            'last_activity': info.last_activity.isoformat(),
            'uptime': str(info.uptime),
            'terminal_size': info.terminal_size,
            'memory_usage': info.memory_usage,
            'cpu_usage': info.cpu_usage
        }
        
        print("Session Information:")
        for key, value in session_data.items():
            print(f"  {key}: {value}")
        
        return session_data
        
    except Exception as e:
        print(f"Error getting session info: {e}")
        return {'error': str(e)}


def terminate_session(session_id, force=False):
    """
    Final Step: Terminate session.
    
    This Python process connects to the existing session,
    terminates it, and then exits.
    """
    print(f"Terminating session: {session_id}")
    
    terminal = CyberTerminal()
    try:
        success = terminal.terminate_session(session_id, force=force)
        
        if success:
            print("Session terminated successfully")
            return {'session_id': session_id, 'status': 'terminated'}
        else:
            print("Failed to terminate session")
            return {'session_id': session_id, 'status': 'failed'}
            
    except Exception as e:
        print(f"Error terminating session: {e}")
        return {'error': str(e)}


def main():
    """
    Command-line interface for multi-process workflow.
    
    Usage examples:
    
    # Step 1: Create session (Python process 1)
    python3 multi_process_workflow.py create "python3" --name "my_python"
    
    # Step 2: Read screen (Python process 2)  
    python3 multi_process_workflow.py read <session_id>
    
    # Step 3: Send input (Python process 3)
    python3 multi_process_workflow.py input <session_id> "print('Hello')"
    
    # Step 4: Read screen again (Python process 4)
    python3 multi_process_workflow.py read <session_id>
    
    # Final: Terminate (Python process N)
    python3 multi_process_workflow.py terminate <session_id>
    """
    parser = argparse.ArgumentParser(
        description="Multi-Process Cyber Terminal Workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=main.__doc__
    )
    
    subparsers = parser.add_subparsers(dest='action', help='Action to perform')
    
    # Create session
    create_parser = subparsers.add_parser('create', help='Create new session')
    create_parser.add_argument('command', help='Command to execute')
    create_parser.add_argument('--name', help='Session name')
    create_parser.add_argument('--working-dir', help='Working directory')
    create_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # Read screen
    read_parser = subparsers.add_parser('read', help='Read screen content')
    read_parser.add_argument('session_id', help='Session ID')
    read_parser.add_argument('--format', choices=['text', 'structured', 'raw', 'ansi'],
                            default='text', help='Output format')
    read_parser.add_argument('--lines', type=int, help='Limit to last N lines')
    read_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # Send input
    input_parser = subparsers.add_parser('input', help='Send input to session')
    input_parser.add_argument('session_id', help='Session ID')
    input_parser.add_argument('data', help='Input data to send')
    input_parser.add_argument('--type', dest='input_type',
                             choices=['text', 'text_no_newline', 'control', 'key'],
                             default='text', help='Input type')
    input_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # List sessions
    list_parser = subparsers.add_parser('list', help='List active sessions')
    list_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # Get session info
    info_parser = subparsers.add_parser('info', help='Get session information')
    info_parser.add_argument('session_id', help='Session ID')
    info_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # Terminate session
    term_parser = subparsers.add_parser('terminate', help='Terminate session')
    term_parser.add_argument('session_id', help='Session ID')
    term_parser.add_argument('--force', action='store_true', help='Force termination')
    term_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    if not args.action:
        parser.print_help()
        sys.exit(1)
    
    # Execute the requested action
    result = None
    
    try:
        if args.action == 'create':
            result = create_session(args.command, args.name, args.working_dir)
        
        elif args.action == 'read':
            result = read_screen(args.session_id, args.format, args.lines)
        
        elif args.action == 'input':
            result = send_input(args.session_id, args.data, args.input_type)
        
        elif args.action == 'list':
            result = list_sessions()
        
        elif args.action == 'info':
            result = get_session_info(args.session_id)
        
        elif args.action == 'terminate':
            result = terminate_session(args.session_id, args.force)
        
        # Output result
        if args.json and result:
            print(json.dumps(result, indent=2))
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

