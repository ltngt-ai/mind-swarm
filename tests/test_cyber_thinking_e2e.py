#!/usr/bin/env python3
"""End-to-end test of Cyber thinking through the Mind-Swarm system."""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mind_swarm.client import MindSwarmClient


async def test_agent_thinking_e2e():
    """Test a complete Cyber thinking scenario."""
    print("=== End-to-End Cyber Thinking Test ===\n")
    
    # Connect to the server
    client = MindSwarmClient()
    
    try:
        # Check server status
        print("1. Checking server status...")
        status = await client.get_status()
        print(f"Server uptime: {status.server_uptime:.1f}s")
        print(f"Cybers running: {len(status.Cybers)}\n")
        
        # Spawn a test Cyber
        print("2. Spawning test Cyber...")
        cyber_config = {
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
        
        cyber_id = await client.spawn_agent(
            name="test-thinker",
            config=cyber_config
        )
        print(f"Spawned Cyber: {cyber_id}\n")
        
        # Give Cyber time to initialize
        await asyncio.sleep(2)
        
        # Send a test question
        print("3. Sending arithmetic question...")
        await client.send_command(
            cyber_id,
            "think",
            {"question": "What is 15 + 27?"}
        )
        
        # Monitor Cyber responses
        print("4. Monitoring Cyber thinking...\n")
        
        # Wait for Cyber to process the question
        print("Waiting for Cyber to think...")
        await asyncio.sleep(15)  # Give Cyber time to process through brain handler
        
        # Check Cyber mailbox for response
        print("\n5. Checking Cyber mailbox...")
        messages = await client.get_agent_messages(cyber_id)
        
        for msg in messages:
            if msg.get("type") == "RESPONSE":
                print(f"Found response: {msg.get('content')}")
        
        # Get Cyber status
        print("\n6. Final Cyber status...")
        Cybers = await client.list_agents()
        for Cyber in Cybers:
            if Cyber["id"] == cyber_id:
                print(f"Cyber: {Cyber['name']}")
                print(f"Status: {Cyber['status']}")
                print(f"State: {json.dumps(Cyber.get('internal_state', {}), indent=2)}")
        
        # Cleanup
        print("\n7. Cleaning up...")
        try:
            await client.terminate_agent(cyber_id)
            print("Cyber terminated")
        except:
            print("Cyber already terminated")
        
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
    """Test a more complex Cyber conversation."""
    print("\n=== Cyber Conversation Test ===\n")
    
    client = MindSwarmClient()
    
    try:
        # Spawn an Cyber
        cyber_id = await client.spawn_agent(name="conversationalist")
        print(f"Cyber spawned: {cyber_id}")
        
        # Have a conversation
        questions = [
            "What is 2+2?",
            "Now multiply that result by 5",
            "What's the square root of that?",
        ]
        
        for i, question in enumerate(questions, 1):
            print(f"\n{i}. Asking: {question}")
            await client.send_command(cyber_id, "think", {"question": question})
            await asyncio.sleep(5)  # Wait for response
        
        # Cleanup
        await client.terminate_agent(cyber_id)
        await client.close()
        
    except Exception as e:
        print(f"Conversation test failed: {e}")
        await client.close()


if __name__ == "__main__":
    print("Running end-to-end Cyber thinking tests...\n")
    
    # Run tests
    asyncio.run(test_agent_thinking_e2e())
    
    # Optional: Run conversation test
    # asyncio.run(test_agent_conversation())