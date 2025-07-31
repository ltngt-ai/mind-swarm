#!/usr/bin/env python3
"""Test agent startup after fixing imports."""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mind_swarm.client import MindSwarmClient


async def test_agent_startup():
    """Test that agents can start properly."""
    print("=== Testing Agent Startup ===\n")
    
    client = MindSwarmClient()
    
    try:
        # Check server
        print("1. Checking server status...")
        status = await client.get_status()
        print(f"Server running with {len(status.agents)} agents\n")
        
        # Spawn a test agent
        print("2. Spawning test agent...")
        agent_config = {
            "ai_preset": "local_explorer",
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
            name="startup-test",
            config=agent_config
        )
        print(f"Spawned agent: {agent_id}")
        
        # Wait a bit for agent to initialize
        print("\n3. Waiting for agent initialization...")
        await asyncio.sleep(5)
        
        # Check if agent is still running
        print("\n4. Checking agent status...")
        agents = await client.list_agents()
        
        agent_found = False
        for agent in agents:
            if agent["id"] == agent_id:
                agent_found = True
                print(f"Agent {agent['name']}:")
                print(f"  Status: {agent['status']}")
                print(f"  Running: {'Yes' if agent['status'] != 'DEAD' else 'No'}")
                
                # Check if we can see the agent log
                agent_log = Path(f"/home/deano/projects/mind-swarm/subspace/agents/{agent_id}/agent.log")
                if agent_log.exists():
                    print(f"\n5. Agent log contents:")
                    print(agent_log.read_text()[:500])
                else:
                    print(f"\n5. No agent log found at {agent_log}")
        
        if not agent_found:
            print(f"ERROR: Agent {agent_id} not found in agent list!")
        
        # Try to send a simple message
        print("\n6. Sending test message...")
        await client.send_command(agent_id, "ping", {})
        
        await asyncio.sleep(2)
        
        # Clean up
        print("\n7. Cleaning up...")
        try:
            await client.terminate_agent(agent_id)
            print("Agent terminated")
        except:
            print("Agent already terminated or not found")
        
        await client.close()
        
        if agent_found:
            print("\n✓ Agent startup test completed successfully!")
        else:
            print("\n✗ Agent startup test failed!")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_agent_startup())