#!/usr/bin/env python3
"""
Cognitive Loop Demonstration for AI Agents.

This script demonstrates a complete AI agent cognitive loop where each
iteration is a separate Python process execution. This simulates how
an AI agent would interact with terminal programs:

1. Create session (separate process)
2. Loop: Read → Think → Act (each step is separate process)
3. Terminate session (separate process)

This example shows interaction with a Python REPL to solve a simple problem.
"""

import sys
import os
import subprocess
import json
import time

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def run_workflow_command(action, *args, **kwargs):
    """
    Execute a workflow command in a separate Python process.
    
    This simulates how each cognitive loop iteration would be
    a completely separate Python execution.
    """
    script_path = os.path.join(os.path.dirname(__file__), 'multi_process_workflow.py')
    
    # Build command
    cmd = ['python3', script_path, '--json', action]
    cmd.extend(args)
    
    # Add optional arguments
    for key, value in kwargs.items():
        if value is not None:
            cmd.extend([f'--{key.replace("_", "-")}', str(value)])
    
    print(f"Executing: {' '.join(cmd)}")
    
    # Run in separate process
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return None
    
    try:
        return json.loads(result.stdout.split('\n')[-2])  # Get JSON from last line
    except (json.JSONDecodeError, IndexError):
        print(f"Raw output: {result.stdout}")
        return None


def ai_agent_think(screen_content):
    """
    Simulate AI agent thinking process.
    
    In a real implementation, this would be where the LLM
    analyzes the screen content and decides what to do next.
    """
    text = screen_content.get('text', '')
    
    # Simple rule-based "AI" for demonstration
    if '>>>' in text and 'Traceback' not in text:
        # Python prompt is ready, no errors
        if 'fibonacci' not in text:
            return {'action': 'input', 'data': 'def fibonacci(n):\n    if n <= 1: return n\n    return fibonacci(n-1) + fibonacci(n-2)'}
        elif 'fibonacci(10)' not in text:
            return {'action': 'input', 'data': 'print(f"Fibonacci(10) = {fibonacci(10)}")'}
        elif 'exit()' not in text:
            return {'action': 'input', 'data': 'exit()'}
        else:
            return {'action': 'done'}
    
    elif 'Traceback' in text or 'Error' in text:
        # There's an error, try to fix it
        return {'action': 'input', 'data': 'print("Error occurred, trying again...")'}
    
    elif 'Python' in text and '>>>' not in text:
        # Python is starting up
        return {'action': 'wait'}
    
    else:
        # Default action
        return {'action': 'input', 'data': 'print("Hello from AI agent!")'}


def cognitive_loop_demo():
    """
    Demonstrate a complete cognitive loop with separate processes.
    """
    print("=== AI Agent Cognitive Loop Demo ===")
    print("Each step runs in a separate Python process")
    print()
    
    # Step 1: Create session (Process 1)
    print("Step 1: Creating Python session...")
    session_result = run_workflow_command('create', 'python3', name='ai_demo')
    
    if not session_result:
        print("Failed to create session")
        return
    
    session_id = session_result['session_id']
    print(f"Session created: {session_id}")
    print()
    
    # Wait for Python to start
    time.sleep(2)
    
    # Cognitive loop iterations
    iteration = 0
    max_iterations = 10
    
    while iteration < max_iterations:
        iteration += 1
        print(f"=== Iteration {iteration} ===")
        
        # Step 2: Read screen (Process N)
        print("Reading screen...")
        screen_result = run_workflow_command('read', session_id)
        
        if not screen_result:
            print("Failed to read screen")
            break
        
        print("Screen content:")
        print("-" * 30)
        print(screen_result['text'])
        print("-" * 30)
        
        # Step 3: Think (AI decision making)
        print("AI thinking...")
        decision = ai_agent_think(screen_result)
        print(f"AI decision: {decision}")
        
        # Step 4: Act based on decision (Process N+1)
        if decision['action'] == 'input':
            print(f"Sending input: {repr(decision['data'])}")
            input_result = run_workflow_command('input', session_id, decision['data'])
            
            if not input_result:
                print("Failed to send input")
                break
            
            # Wait for command to execute
            time.sleep(1)
        
        elif decision['action'] == 'wait':
            print("Waiting for system to be ready...")
            time.sleep(2)
        
        elif decision['action'] == 'done':
            print("AI agent completed the task!")
            break
        
        print()
    
    # Final step: Terminate session (Process Final)
    print("Terminating session...")
    term_result = run_workflow_command('terminate', session_id)
    
    if term_result:
        print("Session terminated successfully")
    else:
        print("Failed to terminate session")
    
    print("\n=== Demo Complete ===")


def multi_agent_demo():
    """
    Demonstrate multiple AI agents working with different sessions.
    """
    print("\n=== Multi-Agent Demo ===")
    print("Multiple AI agents working simultaneously")
    print()
    
    # Create multiple sessions for different agents
    agents = [
        {'name': 'math_agent', 'command': 'python3'},
        {'name': 'shell_agent', 'command': 'bash'},
        {'name': 'calc_agent', 'command': 'bc -l'}
    ]
    
    sessions = []
    
    # Each agent creates its session (separate processes)
    for agent in agents:
        print(f"Creating session for {agent['name']}...")
        result = run_workflow_command('create', agent['command'], name=agent['name'])
        
        if result:
            sessions.append({
                'agent': agent['name'],
                'session_id': result['session_id'],
                'command': agent['command']
            })
            print(f"  Session: {result['session_id']}")
    
    print(f"\nCreated {len(sessions)} agent sessions")
    
    # Each agent performs one action (separate processes)
    actions = [
        {'agent': 'math_agent', 'input': 'import math; print(f"Pi = {math.pi}")'},
        {'agent': 'shell_agent', 'input': 'echo "Hello from shell agent"'},
        {'agent': 'calc_agent', 'input': '2 + 2'}
    ]
    
    time.sleep(2)  # Let sessions initialize
    
    for action in actions:
        # Find the session for this agent
        session = next((s for s in sessions if s['agent'] == action['agent']), None)
        
        if session:
            print(f"\n{action['agent']} performing action...")
            
            # Send input (separate process)
            run_workflow_command('input', session['session_id'], action['input'])
            time.sleep(1)
            
            # Read result (separate process)
            result = run_workflow_command('read', session['session_id'])
            
            if result:
                print(f"{action['agent']} output:")
                print(result['text'][-200:])  # Last 200 chars
    
    # Clean up all sessions (separate processes)
    print("\nCleaning up agent sessions...")
    for session in sessions:
        run_workflow_command('terminate', session['session_id'])
        print(f"  Terminated {session['agent']}")
    
    print("Multi-agent demo complete")


def persistence_demo():
    """
    Demonstrate session persistence across system "restarts".
    """
    print("\n=== Persistence Demo ===")
    print("Demonstrating session survival across Python process restarts")
    print()
    
    # Create a session
    print("Creating persistent session...")
    result = run_workflow_command('create', 'bash', name='persistent_demo')
    
    if not result:
        print("Failed to create session")
        return
    
    session_id = result['session_id']
    print(f"Session created: {session_id}")
    
    # Set up some state in the session
    time.sleep(1)
    print("Setting up session state...")
    run_workflow_command('input', session_id, 'export DEMO_VAR="I persist across processes!"')
    time.sleep(0.5)
    run_workflow_command('input', session_id, 'cd /tmp')
    time.sleep(0.5)
    
    # Read initial state
    result = run_workflow_command('read', session_id)
    print("Initial session state:")
    print(result['text'][-200:])
    
    print("\n--- Simulating Python process restart ---")
    print("(In real usage, the Python process would exit here)")
    print("(The session continues running in the background)")
    print("(A new Python process would start and reconnect)")
    
    # Simulate reconnection by listing sessions
    print("\nReconnecting to existing sessions...")
    sessions = run_workflow_command('list')
    
    if sessions:
        print(f"Found {len(sessions)} persistent sessions:")
        for session in sessions:
            if session['name'] == 'persistent_demo':
                print(f"  Found our session: {session['session_id']}")
                
                # Verify state persisted
                print("Checking if state persisted...")
                run_workflow_command('input', session_id, 'echo $DEMO_VAR')
                time.sleep(0.5)
                run_workflow_command('input', session_id, 'pwd')
                time.sleep(0.5)
                
                result = run_workflow_command('read', session_id)
                print("Persistent session state:")
                print(result['text'][-200:])
                
                # Clean up
                run_workflow_command('terminate', session_id)
                print("Session terminated")
                break
    else:
        print("No persistent sessions found")


def main():
    """
    Run all cognitive loop demonstrations.
    """
    print("Cyber Terminal - Cognitive Loop Demonstrations")
    print("=" * 60)
    
    try:
        # Basic cognitive loop
        cognitive_loop_demo()
        
        # Multi-agent scenario
        multi_agent_demo()
        
        # Persistence demonstration
        persistence_demo()
        
        print("\n" + "=" * 60)
        print("All demonstrations completed successfully!")
        
    except KeyboardInterrupt:
        print("\nDemonstrations cancelled by user")
    except Exception as e:
        print(f"\nError during demonstration: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

