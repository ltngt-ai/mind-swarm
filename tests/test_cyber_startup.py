#!/usr/bin/env python3
"""Test Cyber startup after fixing imports."""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mind_swarm.client import MindSwarmClient


async def test_agent_startup():
    """Test that Cybers can start properly."""
    print("=== Testing Cyber Startup ===\n")
    
    client = MindSwarmClient()
    
    try:
        # Check server
        print("1. Checking server status...")
        status = await client.get_status()
        print(f"Server running with {len(status.Cybers)} Cybers\n")
        
        # Spawn a test Cyber
        print("2. Spawning test Cyber...")
        cyber_config = {
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
        
        cyber_id = await client.spawn_agent(
            name="startup-test",
            config=cyber_config
        )
        print(f"Spawned Cyber: {cyber_id}")
        
        # Wait a bit for Cyber to initialize
        print("\n3. Waiting for Cyber initialization...")
        await asyncio.sleep(5)
        
        # Check if Cyber is still running
        print("\n4. Checking Cyber status...")
        Cybers = await client.list_agents()
        
        agent_found = False
        for Cyber in Cybers:
            if Cyber["id"] == cyber_id:
                agent_found = True
                print(f"Cyber {Cyber['name']}:")
                print(f"  Status: {Cyber['status']}")
                print(f"  Running: {'Yes' if Cyber['status'] != 'DEAD' else 'No'}")
                
                # Check if we can see the Cyber log
                agent_log = Path(f"/personal/deano/projects/mind-swarm/subspace/Cybers/{cyber_id}/Cyber.log")
                if agent_log.exists():
                    print(f"\n5. Cyber log contents:")
                    print(agent_log.read_text()[:500])
                else:
                    print(f"\n5. No Cyber log found at {agent_log}")
        
        if not agent_found:
            print(f"ERROR: Cyber {cyber_id} not found in Cyber list!")
        
        # Try to send a simple message
        print("\n6. Sending test message...")
        await client.send_command(cyber_id, "ping", {})
        
        await asyncio.sleep(2)
        
        # Clean up
        print("\n7. Cleaning up...")
        try:
            await client.terminate_agent(cyber_id)
            print("Cyber terminated")
        except:
            print("Cyber already terminated or not found")
        
        await client.close()
        
        if agent_found:
            print("\n✓ Cyber startup test completed successfully!")
        else:
            print("\n✗ Cyber startup test failed!")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_agent_startup())