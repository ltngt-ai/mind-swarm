"""
Command-line interface for Cyber Terminal.

This module provides a CLI for testing and managing terminal sessions.
"""

import argparse
import json
import sys
import time
from typing import Optional

from .cyber_terminal import CyberTerminal, CyberTerminalConfig
from .exceptions import CyberTerminalError


def create_session_command(args, terminal: CyberTerminal):
    """Handle create session command."""
    try:
        session_id = terminal.create_session(
            command=args.command,
            working_dir=args.working_dir,
            env=dict(args.env) if args.env else None,
            name=args.name,
            terminal_size=(args.rows, args.cols)
        )
        
        print(f"Created session: {session_id}")
        
        if args.interactive:
            interactive_session(terminal, session_id)
            
    except CyberTerminalError as e:
        print(f"Error creating session: {e}", file=sys.stderr)
        sys.exit(1)


def list_sessions_command(args, terminal: CyberTerminal):
    """Handle list sessions command."""
    try:
        sessions = terminal.list_sessions()
        
        if args.json:
            session_data = []
            for session in sessions:
                session_data.append({
                    'session_id': session.session_id,
                    'name': session.name,
                    'command': session.command,
                    'status': session.status.value,
                    'created_at': session.created_at.isoformat(),
                    'uptime': str(session.uptime),
                    'terminal_size': session.terminal_size
                })
            print(json.dumps(session_data, indent=2))
        else:
            if not sessions:
                print("No active sessions")
                return
            
            print(f"{'ID':<12} {'Name':<20} {'Command':<30} {'Status':<12} {'Uptime':<15}")
            print("-" * 90)
            
            for session in sessions:
                uptime_str = str(session.uptime).split('.')[0]  # Remove microseconds
                print(f"{session.session_id[:12]:<12} {session.name[:20]:<20} "
                      f"{session.command[:30]:<30} {session.status.value:<12} {uptime_str:<15}")
                
    except CyberTerminalError as e:
        print(f"Error listing sessions: {e}", file=sys.stderr)
        sys.exit(1)


def read_screen_command(args, terminal: CyberTerminal):
    """Handle read screen command."""
    try:
        content = terminal.read_screen(
            session_id=args.session_id,
            format=args.format,
            lines=args.lines
        )
        
        if args.json:
            print(json.dumps(content.to_dict(), indent=2))
        else:
            print(content.text)
            
    except CyberTerminalError as e:
        print(f"Error reading screen: {e}", file=sys.stderr)
        sys.exit(1)


def send_input_command(args, terminal: CyberTerminal):
    """Handle send input command."""
    try:
        success = terminal.send_input(
            session_id=args.session_id,
            data=args.input,
            input_type=args.input_type
        )
        
        if success:
            print("Input sent successfully")
        else:
            print("Failed to send input", file=sys.stderr)
            sys.exit(1)
            
    except CyberTerminalError as e:
        print(f"Error sending input: {e}", file=sys.stderr)
        sys.exit(1)


def terminate_session_command(args, terminal: CyberTerminal):
    """Handle terminate session command."""
    try:
        success = terminal.terminate_session(
            session_id=args.session_id,
            force=args.force
        )
        
        if success:
            print(f"Session {args.session_id} terminated")
        else:
            print("Failed to terminate session", file=sys.stderr)
            sys.exit(1)
            
    except CyberTerminalError as e:
        print(f"Error terminating session: {e}", file=sys.stderr)
        sys.exit(1)


def interactive_session(terminal: CyberTerminal, session_id: str):
    """Run interactive session mode."""
    print(f"Interactive mode for session {session_id}")
    print("Commands: 'read' to read screen, 'quit' to exit, or type input to send")
    print("-" * 60)
    
    try:
        while True:
            try:
                user_input = input("> ").strip()
                
                if user_input.lower() in ('quit', 'exit', 'q'):
                    break
                elif user_input.lower() == 'read':
                    content = terminal.read_screen(session_id)
                    print("Screen content:")
                    print("-" * 40)
                    print(content.text)
                    print("-" * 40)
                elif user_input:
                    terminal.send_input(session_id, user_input)
                    
                    # Wait a bit and show output
                    time.sleep(0.5)
                    content = terminal.read_screen(session_id)
                    if content.text.strip():
                        print(content.text)
                        
            except KeyboardInterrupt:
                print("\nExiting interactive mode...")
                break
            except CyberTerminalError as e:
                print(f"Error: {e}")
                break
                
    except Exception as e:
        print(f"Unexpected error: {e}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Cyber Terminal - Terminal Interaction System for AI Agents"
    )
    
    parser.add_argument(
        '--config', 
        help="Configuration file path"
    )
    parser.add_argument(
        '--log-level', 
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help="Logging level"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Create session command
    create_parser = subparsers.add_parser('create', help='Create new terminal session')
    create_parser.add_argument('command', help='Command to execute')
    create_parser.add_argument('--name', help='Session name')
    create_parser.add_argument('--working-dir', help='Working directory')
    create_parser.add_argument('--env', action='append', nargs=2, metavar=('KEY', 'VALUE'),
                              help='Environment variable (can be used multiple times)')
    create_parser.add_argument('--rows', type=int, default=24, help='Terminal rows')
    create_parser.add_argument('--cols', type=int, default=80, help='Terminal columns')
    create_parser.add_argument('--interactive', action='store_true',
                              help='Enter interactive mode after creation')
    
    # List sessions command
    list_parser = subparsers.add_parser('list', help='List active sessions')
    list_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # Read screen command
    read_parser = subparsers.add_parser('read', help='Read screen content')
    read_parser.add_argument('session_id', help='Session ID')
    read_parser.add_argument('--format', choices=['text', 'structured', 'raw', 'ansi'],
                            default='text', help='Output format')
    read_parser.add_argument('--lines', type=int, help='Limit to last N lines')
    read_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # Send input command
    input_parser = subparsers.add_parser('input', help='Send input to session')
    input_parser.add_argument('session_id', help='Session ID')
    input_parser.add_argument('input', help='Input to send')
    input_parser.add_argument('--type', dest='input_type',
                             choices=['text', 'text_no_newline', 'control', 'key'],
                             default='text', help='Input type')
    
    # Terminate session command
    term_parser = subparsers.add_parser('terminate', help='Terminate session')
    term_parser.add_argument('session_id', help='Session ID')
    term_parser.add_argument('--force', action='store_true', help='Force termination')
    
    # Interactive command
    interactive_parser = subparsers.add_parser('interactive', help='Interactive session mode')
    interactive_parser.add_argument('session_id', help='Session ID')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Create configuration
    config = CyberTerminalConfig(log_level=args.log_level)
    
    # Initialize terminal system
    try:
        with CyberTerminal(config) as terminal:
            if args.command == 'create':
                create_session_command(args, terminal)
            elif args.command == 'list':
                list_sessions_command(args, terminal)
            elif args.command == 'read':
                read_screen_command(args, terminal)
            elif args.command == 'input':
                send_input_command(args, terminal)
            elif args.command == 'terminate':
                terminate_session_command(args, terminal)
            elif args.command == 'interactive':
                interactive_session(terminal, args.session_id)
                
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

