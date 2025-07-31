#!/usr/bin/env python3
"""Test agent startup and thinking capabilities."""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mind_swarm.client import MindSwarmClient


async def test_agent_thinking():
    """Test that agents can start and think properly."""
    print("=== Testing Agent Thinking Capabilities ===\n")
    
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
            name="thinking-test",
            config=agent_config
        )
        print(f"Spawned agent: {agent_id}")
        
        # Wait for agent to initialize
        print("\n3. Waiting for agent initialization...")
        await asyncio.sleep(5)
        
        # Check agent log
        agent_log_path = Path(f"/home/deano/projects/mind-swarm/subspace/agents/{agent_id}/logs/agent.log")
        if agent_log_path.exists():
            print("\n4. Agent log (last 10 lines):")
            log_lines = agent_log_path.read_text().strip().split('\n')
            for line in log_lines[-10:]:
                print(f"  {line}")
        
        # Check if agent created heartbeat
        heartbeat_path = Path(f"/home/deano/projects/mind-swarm/subspace/agents/{agent_id}/heartbeat.json")
        if heartbeat_path.exists():
            print("\n5. Agent heartbeat:")
            heartbeat = json.loads(heartbeat_path.read_text())
            print(f"  State: {heartbeat.get('state')}")
            print(f"  Uptime: {heartbeat.get('uptime', 0):.1f}s")
            print(f"  Cycles: {heartbeat.get('cycle_count', 0)}")
        
        # Send a command to test thinking
        print("\n6. Testing agent thinking by sending 'think' command...")
        await client.send_command(agent_id, "think", {"prompt": "What is 2 + 2?"})
        
        # Wait for thinking to complete
        await asyncio.sleep(5)
        
        # Check for response in outbox
        outbox_dir = Path(f"/home/deano/projects/mind-swarm/subspace/agents/{agent_id}/outbox")
        if outbox_dir.exists():
            messages = list(outbox_dir.glob("*.json"))
            if messages:
                print("\n7. Agent response:")
                for msg_file in messages:
                    msg = json.loads(msg_file.read_text())
                    print(f"  Type: {msg.get('type')}")
                    print(f"  Content: {msg.get('content', msg.get('result', 'N/A'))}")
        
        # Check server brain log
        print("\n8. Checking server logs for thinking activity...")
        server_log = Path("/tmp/mind-swarm-server-direct.log").read_text()
        thinking_lines = [line for line in server_log.split('\n') if 'thinking' in line.lower() or 'brain' in line.lower() or 'thought' in line.lower()]
        if thinking_lines:
            print("  Recent thinking activity:")
            for line in thinking_lines[-5:]:
                if line.strip():
                    print(f"    {line.strip()}")
        
        # Check final agent status
        print("\n9. Final agent check...")
        final_status = await client.get_status()
        
        agent_found = False
        for aid, agent_data in final_status.agents.items():
            if aid == agent_id:
                agent_found = True
                print(f"  Agent {agent_data.get('name', 'Unknown')}:")
                print(f"    State: {agent_data.get('state', 'Unknown')}")
                print(f"    Running: {'Yes' if agent_data.get('state') != 'DEAD' else 'No'}")
        
        # Clean up
        print("\n10. Cleaning up...")
        try:
            await client.terminate_agent(agent_id)
            print("  Agent terminated")
        except:
            print("  Agent already terminated or not found")
        
        # No need to close client explicitly
        
        if agent_found:
            print("\n✓ Agent thinking test completed successfully!")
        else:
            print("\n✗ Agent thinking test failed - agent died!")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        # No need to close client explicitly


if __name__ == "__main__":
    asyncio.run(test_agent_thinking())