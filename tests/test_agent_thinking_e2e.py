#!/usr/bin/env python3
"""End-to-end test of agent thinking through the Mind-Swarm system."""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mind_swarm.client import MindSwarmClient


async def test_agent_thinking_e2e():
    """Test a complete agent thinking scenario."""
    print("=== End-to-End Agent Thinking Test ===\n")
    
    # Connect to the server
    client = MindSwarmClient()
    
    try:
        # Check server status
        print("1. Checking server status...")
        status = await client.get_status()
        print(f"Server uptime: {status.server_uptime:.1f}s")
        print(f"Agents running: {len(status.agents)}\n")
        
        # Spawn a test agent
        print("2. Spawning test agent...")
        agent_config = {
            "ai_preset": "local_explorer",  # Use local AI server
            "brain_config": {
                "provider": "local",
                "model": "llama3.2:3b",
                "temperature": 0.7,
                "max_tokens": 1000,
                "provider_settings": {
                    "host": "http://192.168.1.147:1234"
                }
            }
        }
        
        agent_id = await client.spawn_agent(
            name="test-thinker",
            config=agent_config
        )
        print(f"Spawned agent: {agent_id}\n")
        
        # Give agent time to initialize
        await asyncio.sleep(2)
        
        # Send a test question
        print("3. Sending arithmetic question...")
        await client.send_command(
            agent_id,
            "think",
            {"question": "What is 15 + 27?"}
        )
        
        # Monitor agent responses
        print("4. Monitoring agent thinking...\n")
        
        # Wait for agent to process the question
        print("Waiting for agent to think...")
        await asyncio.sleep(15)  # Give agent time to process through brain handler
        
        # Check agent mailbox for response
        print("\n5. Checking agent mailbox...")
        messages = await client.get_agent_messages(agent_id)
        
        for msg in messages:
            if msg.get("type") == "RESPONSE":
                print(f"Found response: {msg.get('content')}")
        
        # Get agent status
        print("\n6. Final agent status...")
        agents = await client.list_agents()
        for agent in agents:
            if agent["id"] == agent_id:
                print(f"Agent: {agent['name']}")
                print(f"Status: {agent['status']}")
                print(f"State: {json.dumps(agent.get('internal_state', {}), indent=2)}")
        
        # Cleanup
        print("\n7. Cleaning up...")
        try:
            await client.terminate_agent(agent_id)
            print("Agent terminated")
        except:
            print("Agent already terminated")
        
        # Close client
        await client.close()
        
        print("\n✓ End-to-end test completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Cleanup on error
        try:
            await client.close()
        except:
            pass


async def test_agent_conversation():
    """Test a more complex agent conversation."""
    print("\n=== Agent Conversation Test ===\n")
    
    client = MindSwarmClient()
    
    try:
        # Spawn an agent
        agent_id = await client.spawn_agent(name="conversationalist")
        print(f"Agent spawned: {agent_id}")
        
        # Have a conversation
        questions = [
            "What is 2+2?",
            "Now multiply that result by 5",
            "What's the square root of that?",
        ]
        
        for i, question in enumerate(questions, 1):
            print(f"\n{i}. Asking: {question}")
            await client.send_command(agent_id, "think", {"question": question})
            await asyncio.sleep(5)  # Wait for response
        
        # Cleanup
        await client.terminate_agent(agent_id)
        await client.close()
        
    except Exception as e:
        print(f"Conversation test failed: {e}")
        await client.close()


if __name__ == "__main__":
    print("Running end-to-end agent thinking tests...\n")
    
    # Run tests
    asyncio.run(test_agent_thinking_e2e())
    
    # Optional: Run conversation test
    # asyncio.run(test_agent_conversation())