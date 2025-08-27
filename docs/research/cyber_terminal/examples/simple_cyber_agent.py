#!/usr/bin/env python3
"""
Simple Cyber Agent Example.

This demonstrates how to build a simple AI agent that uses the
multi-process cognitive loop pattern to interact with terminal programs.

Each cognitive step (read/think/act) is designed to be run as a
separate Python process execution.
"""

import sys
import os
import json
import argparse

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.cyber_terminal import CyberTerminal


class SimpleCyberAgent:
    """
    A simple AI agent that can interact with terminal programs.
    
    This agent is designed to work with the multi-process pattern
    where each method call happens in a separate Python execution.
    """
    
    def __init__(self, session_id=None):
        self.session_id = session_id
        self.terminal = CyberTerminal()
    
    def create_session(self, command, name=None):
        """Create a new terminal session."""
        self.session_id = self.terminal.create_session(
            command=command,
            name=name or f"cyber_agent_{command.replace(' ', '_')}"
        )
        return self.session_id
    
    def observe(self):
        """Read and analyze the current screen state."""
        if not self.session_id:
            raise ValueError("No active session")
        
        content = self.terminal.read_screen(self.session_id)
        
        observation = {
            'text': content.text,
            'cursor_position': content.cursor_position,
            'terminal_size': content.terminal_size,
            'lines': content.lines,
            'analysis': self._analyze_screen(content.text)
        }
        
        return observation
    
    def _analyze_screen(self, text):
        """
        Analyze screen content and extract meaningful information.
        
        In a real AI agent, this would use an LLM to understand
        the current state and context.
        """
        analysis = {
            'has_prompt': False,
            'has_error': False,
            'program_type': 'unknown',
            'ready_for_input': False,
            'last_output': ''
        }
        
        lines = text.strip().split('\n')
        if lines:
            last_line = lines[-1]
            analysis['last_output'] = last_line
            
            # Detect different program types and states
            if '>>>' in last_line or '... ' in last_line:
                analysis['program_type'] = 'python'
                analysis['has_prompt'] = True
                analysis['ready_for_input'] = True
            
            elif '$' in last_line and '@' in last_line:
                analysis['program_type'] = 'bash'
                analysis['has_prompt'] = True
                analysis['ready_for_input'] = True
            
            elif 'bc' in text and not last_line.strip():
                analysis['program_type'] = 'bc'
                analysis['ready_for_input'] = True
            
            # Check for errors
            if any(error_word in text.lower() for error_word in 
                   ['error', 'traceback', 'exception', 'failed', 'not found']):
                analysis['has_error'] = True
        
        return analysis
    
    def think(self, observation):
        """
        Decide what action to take based on observation.
        
        In a real AI agent, this would be where the LLM
        processes the observation and decides on the next action.
        """
        analysis = observation['analysis']
        text = observation['text']
        
        # Simple rule-based decision making for demonstration
        if analysis['program_type'] == 'python':
            return self._think_python(text, analysis)
        elif analysis['program_type'] == 'bash':
            return self._think_bash(text, analysis)
        elif analysis['program_type'] == 'bc':
            return self._think_bc(text, analysis)
        else:
            return {'action': 'wait', 'reason': 'Unknown program type'}
    
    def _think_python(self, text, analysis):
        """Decision making for Python REPL."""
        if analysis['has_error']:
            return {'action': 'input', 'data': 'print("Recovering from error...")', 'reason': 'Error recovery'}
        
        if 'hello' not in text.lower():
            return {'action': 'input', 'data': 'print("Hello from Cyber Agent!")', 'reason': 'Initial greeting'}
        
        if 'import math' not in text:
            return {'action': 'input', 'data': 'import math', 'reason': 'Import math module'}
        
        if 'math.pi' not in text:
            return {'action': 'input', 'data': 'print(f"Pi = {math.pi:.4f}")', 'reason': 'Show pi value'}
        
        if 'exit()' not in text:
            return {'action': 'input', 'data': 'exit()', 'reason': 'Exit Python'}
        
        return {'action': 'done', 'reason': 'Task completed'}
    
    def _think_bash(self, text, analysis):
        """Decision making for Bash shell."""
        if 'hello' not in text.lower():
            return {'action': 'input', 'data': 'echo "Hello from Cyber Agent!"', 'reason': 'Initial greeting'}
        
        if 'pwd' not in text:
            return {'action': 'input', 'data': 'pwd', 'reason': 'Show current directory'}
        
        if 'date' not in text:
            return {'action': 'input', 'data': 'date', 'reason': 'Show current date'}
        
        if 'exit' not in text:
            return {'action': 'input', 'data': 'exit', 'reason': 'Exit shell'}
        
        return {'action': 'done', 'reason': 'Task completed'}
    
    def _think_bc(self, text, analysis):
        """Decision making for bc calculator."""
        if '2+2' not in text:
            return {'action': 'input', 'data': '2+2', 'reason': 'Basic addition'}
        
        if 'sqrt(16)' not in text:
            return {'action': 'input', 'data': 'sqrt(16)', 'reason': 'Square root calculation'}
        
        if 'quit' not in text:
            return {'action': 'input', 'data': 'quit', 'reason': 'Exit calculator'}
        
        return {'action': 'done', 'reason': 'Task completed'}
    
    def act(self, decision):
        """Execute the decided action."""
        if not self.session_id:
            raise ValueError("No active session")
        
        if decision['action'] == 'input':
            success = self.terminal.send_input(
                self.session_id,
                decision['data']
            )
            return {'success': success, 'action': decision['action'], 'data': decision['data']}
        
        elif decision['action'] == 'wait':
            return {'success': True, 'action': 'wait', 'duration': 1}
        
        elif decision['action'] == 'done':
            return {'success': True, 'action': 'done'}
        
        else:
            return {'success': False, 'error': f"Unknown action: {decision['action']}"}
    
    def terminate_session(self):
        """Terminate the current session."""
        if self.session_id:
            success = self.terminal.terminate_session(self.session_id)
            return {'success': success, 'session_id': self.session_id}
        return {'success': True, 'message': 'No active session'}
    
    def get_session_info(self):
        """Get information about the current session."""
        if not self.session_id:
            return {'error': 'No active session'}
        
        try:
            info = self.terminal.get_session_info(self.session_id)
            return {
                'session_id': info.session_id,
                'name': info.name,
                'command': info.command,
                'status': info.status.value,
                'uptime': str(info.uptime),
                'terminal_size': info.terminal_size
            }
        except Exception as e:
            return {'error': str(e)}


def main():
    """
    Command-line interface for the Simple Cyber Agent.
    
    This demonstrates how each cognitive step can be executed
    as a separate Python process.
    """
    parser = argparse.ArgumentParser(description="Simple Cyber Agent")
    parser.add_argument('--session-id', help='Session ID to use')
    parser.add_argument('--json', action='store_true', help='Output JSON')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Create session
    create_parser = subparsers.add_parser('create', help='Create new session')
    create_parser.add_argument('program', help='Program to run (python3, bash, bc)')
    create_parser.add_argument('--name', help='Session name')
    
    # Observe (read screen)
    observe_parser = subparsers.add_parser('observe', help='Observe current state')
    
    # Think (analyze and decide)
    think_parser = subparsers.add_parser('think', help='Think and decide action')
    
    # Act (execute decision)
    act_parser = subparsers.add_parser('act', help='Execute action')
    act_parser.add_argument('action', help='Action to take')
    act_parser.add_argument('--data', help='Data for action')
    
    # Cognitive step (observe + think + act in one call)
    step_parser = subparsers.add_parser('step', help='Perform one cognitive step')
    
    # Session management
    info_parser = subparsers.add_parser('info', help='Get session info')
    term_parser = subparsers.add_parser('terminate', help='Terminate session')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Create agent
    agent = SimpleCyberAgent(args.session_id)
    result = None
    
    try:
        if args.command == 'create':
            session_id = agent.create_session(args.program, args.name)
            result = {'session_id': session_id, 'program': args.program}
            if not args.json:
                print(f"Created session: {session_id}")
        
        elif args.command == 'observe':
            result = agent.observe()
            if not args.json:
                print("Observation:")
                print(f"  Program: {result['analysis']['program_type']}")
                print(f"  Ready: {result['analysis']['ready_for_input']}")
                print(f"  Has Error: {result['analysis']['has_error']}")
                print("Screen content:")
                print(result['text'])
        
        elif args.command == 'think':
            observation = agent.observe()
            decision = agent.think(observation)
            result = {'observation': observation, 'decision': decision}
            if not args.json:
                print(f"Decision: {decision['action']}")
                print(f"Reason: {decision['reason']}")
                if 'data' in decision:
                    print(f"Data: {decision['data']}")
        
        elif args.command == 'act':
            decision = {'action': args.action, 'data': args.data}
            result = agent.act(decision)
            if not args.json:
                print(f"Action executed: {result['success']}")
        
        elif args.command == 'step':
            # Full cognitive step
            observation = agent.observe()
            decision = agent.think(observation)
            action_result = agent.act(decision)
            
            result = {
                'observation': observation,
                'decision': decision,
                'action_result': action_result
            }
            
            if not args.json:
                print(f"Cognitive Step:")
                print(f"  Decision: {decision['action']} - {decision['reason']}")
                print(f"  Success: {action_result['success']}")
        
        elif args.command == 'info':
            result = agent.get_session_info()
            if not args.json:
                if 'error' in result:
                    print(f"Error: {result['error']}")
                else:
                    print("Session Info:")
                    for key, value in result.items():
                        print(f"  {key}: {value}")
        
        elif args.command == 'terminate':
            result = agent.terminate_session()
            if not args.json:
                print(f"Termination: {result['success']}")
        
        # Output JSON if requested
        if args.json and result:
            print(json.dumps(result, indent=2))
    
    except Exception as e:
        error_result = {'error': str(e)}
        if args.json:
            print(json.dumps(error_result, indent=2))
        else:
            print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

