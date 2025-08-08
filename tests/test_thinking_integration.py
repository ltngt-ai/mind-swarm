#!/usr/bin/env python3
"""Integration test for the complete thinking pipeline.

This simulates what happens when an Cyber thinks through the brain interface.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mind_swarm.subspace.brain_handler_v2 import BrainHandlerV2
from mind_swarm.subspace.dspy_config import configure_dspy_for_mind_swarm


def create_thinking_request(signature_type: str, inputs: dict) -> str:
    """Create a thinking request in the expected format."""
    
    signatures = {
        "observe": {
            "task": "What has changed or needs attention?",
            "description": "Observe the environment and identify what's new or important",
            "inputs": {
                "working_memory": "Current contents of working memory",
                "new_messages": "Any new messages in inbox",
                "environment_state": "Current state of my environment"
            },
            "outputs": {
                "observations": "List of things that are new or need attention",
                "priority": "Which observation is most important"
            }
        },
        "orient": {
            "task": "What does this mean and what kind of situation am I in?",
            "description": "Understand the context and meaning of observations",
            "inputs": {
                "observations": "What was observed",
                "current_task": "Any task I'm currently working on",
                "recent_history": "Recent actions and their outcomes"
            },
            "outputs": {
                "situation_type": "What kind of situation this is",
                "understanding": "What I understand about the situation",
                "relevant_knowledge": "What knowledge or skills apply here"
            }
        },
        "arithmetic": {
            "task": "Solve this arithmetic problem step by step",
            "description": "Perform mathematical calculations",
            "inputs": {
                "problem": "The math problem to solve",
                "context": "Any context about the problem"
            },
            "outputs": {
                "steps": "Step by step solution",
                "answer": "The final answer",
                "verification": "How to check the answer is correct"
            }
        }
    }
    
    request = {
        "type": "thinking_request",
        "signature": signatures[signature_type],
        "input_values": inputs,
        "context": {}
    }
    
    return json.dumps(request, indent=2) + "\n<<<END_THOUGHT>>>"


async def simulate_agent_thinking():
    """Simulate an Cyber thinking through a problem."""
    
    print("=== Mind-Swarm Thinking Integration Test ===\n")
    
    # Check for API key
    if not os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        print("Warning: No API key found. Set OPENROUTER_API_KEY or OPENAI_API_KEY")
        print("Using mock responses for demonstration\n")
        use_mock = True
    else:
        use_mock = False
    
    # Configure brain handler
    if use_mock:
        # Mock configuration
        lm_config = {
            "provider": "mock",
            "model": "mock-model",
            "temperature": 0.7,
            "max_tokens": 1000
        }
    else:
        # Use local AI server configuration
        lm_config = {
            "provider": "local",
            "model": "llama3.2:3b",
            "api_key": "dummy",
            "temperature": 0.7,
            "max_tokens": 1000,
            "provider_settings": {
                "host": "http://192.168.1.147:1234"
            }
        }
    
    # Create brain handler
    brain = BrainHandlerV2(lm_config)
    
    # Simulate Cyber receiving "What is 2+2?" question
    print("Cyber receives question: 'What is 2+2?'\n")
    
    # Step 1: OBSERVE - What's new?
    print("=== Step 1: OBSERVE ===")
    observe_request = create_thinking_request("observe", {
        "working_memory": "Empty - just started",
        "new_messages": "1 new message: QUERY from user asking 'What is 2+2?'",
        "environment_state": "Cycle 1, no current task"
    })
    
    if use_mock:
        observe_response = {
            "output_values": {
                "observations": ["New query from user needs response", "Query is asking for arithmetic calculation"],
                "priority": "Respond to user's arithmetic question"
            },
            "metadata": {"operation": "observe"}
        }
        print(f"Mock Response: {json.dumps(observe_response, indent=2)}\n")
    else:
        response = await brain.process_thinking_request("Cyber-001", observe_request)
        print(f"Response: {response}\n")
        observe_response = json.loads(response.replace("<<<THOUGHT_COMPLETE>>>", ""))
    
    # Step 2: ORIENT - What does it mean?
    print("=== Step 2: ORIENT ===")
    observations = observe_response["output_values"].get("observations", [])
    if isinstance(observations, list):
        observations_str = "; ".join(observations)
    else:
        observations_str = str(observations)
    
    orient_request = create_thinking_request("orient", {
        "observations": observations_str,
        "current_task": "None",
        "recent_history": "Just started, no previous actions"
    })
    
    if use_mock:
        orient_response = {
            "output_values": {
                "situation_type": "arithmetic_problem",
                "understanding": "User wants me to solve a simple addition problem",
                "relevant_knowledge": "Basic arithmetic operations"
            },
            "metadata": {"operation": "orient"}
        }
        print(f"Mock Response: {json.dumps(orient_response, indent=2)}\n")
    else:
        response = await brain.process_thinking_request("Cyber-001", orient_request)
        print(f"Response: {response}\n")
        orient_response = json.loads(response.replace("<<<THOUGHT_COMPLETE>>>", ""))
    
    # Step 3: Solve the arithmetic
    print("=== Step 3: SOLVE ARITHMETIC ===")
    arithmetic_request = create_thinking_request("arithmetic", {
        "problem": "What is 2+2?",
        "context": "User query that needs a numerical answer"
    })
    
    if use_mock:
        arithmetic_response = {
            "output_values": {
                "steps": "1. Identify the numbers: 2 and 2\n2. Identify the operation: addition (+)\n3. Add: 2 + 2 = 4",
                "answer": "4",
                "verification": "We can verify by counting: 2 items plus 2 more items equals 4 items total"
            },
            "metadata": {"operation": "arithmetic"}
        }
        print(f"Mock Response: {json.dumps(arithmetic_response, indent=2)}\n")
    else:
        response = await brain.process_thinking_request("Cyber-001", arithmetic_request)
        print(f"Response: {response}\n")
        arithmetic_response = json.loads(response.replace("<<<THOUGHT_COMPLETE>>>", ""))
    
    # Final answer
    answer = arithmetic_response["output_values"].get("answer", "Unknown")
    print(f"=== FINAL ANSWER ===")
    print(f"The answer to 2+2 is: {answer}")
    
    # Show the complete thinking chain
    print("\n=== THINKING CHAIN ===")
    print(f"1. Observed: New arithmetic question from user")
    print(f"2. Understood: Simple addition problem requiring calculation")
    print(f"3. Solved: 2 + 2 = {answer}")
    print(f"4. Ready to respond to user with answer: {answer}")


async def test_legacy_format():
    """Test handling of legacy thinking format."""
    print("\n=== Testing Legacy Format ===")
    
    # Mock config
    lm_config = {
        "provider": "mock",
        "model": "mock-model",
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    brain = BrainHandlerV2(lm_config)
    
    # Legacy format request
    legacy_request = "What is the meaning of life?\n<<<END_THOUGHT>>>"
    
    print(f"Legacy request: {legacy_request}")
    
    # In real usage, this would call the LLM
    # For testing, we'll just show the format
    print("Would process as general question and return response")


if __name__ == "__main__":
    print("Running Mind-Swarm Thinking Integration Test\n")
    
    # Run the simulation
    asyncio.run(simulate_agent_thinking())
    
    # Test legacy format
    asyncio.run(test_legacy_format())