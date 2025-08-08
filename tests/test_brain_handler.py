#!/usr/bin/env python3
"""Test the brain handler to ensure it processes thinking requests correctly."""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mind_swarm.subspace.brain_handler_v2 import BrainHandlerV2


async def test_brain_handler():
    """Test various thinking operations."""
    
    # Mock LM config for testing
    lm_config = {
        "provider": "openai",
        "model": "gpt-3.5-turbo",
        "api_key": "test-key",  # Would use real key in production
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    # Create brain handler
    brain = BrainHandlerV2(lm_config)
    
    print("Testing Brain Handler V2\n")
    
    # Test 1: Arithmetic problem
    print("=== Test 1: Arithmetic ===")
    arithmetic_request = {
        "type": "thinking_request",
        "signature": {
            "task": "Solve this arithmetic problem step by step",
            "inputs": {
                "problem": "The math problem to solve",
                "context": "Any context"
            },
            "outputs": {
                "steps": "Step by step solution",
                "answer": "The final answer",
                "verification": "How to verify"
            }
        },
        "input_values": {
            "problem": "What is 2+2?",
            "context": "User asked me to solve this"
        }
    }
    
    request_text = json.dumps(arithmetic_request) + "\n<<<END_THOUGHT>>>"
    
    try:
        response = await brain.process_thinking_request("test-Cyber-001", request_text)
        print(f"Response:\n{response}\n")
    except Exception as e:
        print(f"Error: {e}\n")
    
    # Test 2: Observation
    print("=== Test 2: Observation ===")
    observe_request = {
        "type": "thinking_request",
        "signature": {
            "task": "What has changed or needs attention?",
            "inputs": {
                "working_memory": "Current memory contents",
                "new_messages": "New messages",
                "environment_state": "Environment state"
            },
            "outputs": {
                "observations": "What needs attention",
                "priority": "Most important thing"
            }
        },
        "input_values": {
            "working_memory": "Currently working on: None",
            "new_messages": "1 new message: QUERY from user asking 'What is 2+2?'",
            "environment_state": "Cycle 1, just started, no current task"
        }
    }
    
    request_text = json.dumps(observe_request) + "\n<<<END_THOUGHT>>>"
    
    try:
        response = await brain.process_thinking_request("test-Cyber-001", request_text)
        print(f"Response:\n{response}\n")
    except Exception as e:
        print(f"Error: {e}\n")
    
    # Test 3: Legacy format
    print("=== Test 3: Legacy Format ===")
    legacy_request = "What is the capital of France?\n<<<END_THOUGHT>>>"
    
    try:
        response = await brain.process_thinking_request("test-Cyber-001", legacy_request)
        print(f"Response:\n{response}\n")
    except Exception as e:
        print(f"Error: {e}\n")


if __name__ == "__main__":
    # Note: This would need proper DSPy configuration with real API keys
    print("Note: This test requires proper API configuration to actually run DSPy")
    print("It demonstrates the structure but may not execute without valid credentials\n")
    
    # Uncomment to run with proper configuration
    # asyncio.run(test_brain_handler())