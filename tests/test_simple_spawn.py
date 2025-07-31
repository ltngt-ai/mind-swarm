#!/usr/bin/env python3
"""Simple test to spawn an agent and check the error."""

import asyncio
import time
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mind_swarm.client import MindSwarmClient


async def test_simple_spawn():
    """Spawn an agent and wait to see what happens."""
    print("=== Simple Agent Spawn Test ===\n")
    
    client = MindSwarmClient()
    
    # Spawn agent
    print("Spawning agent...")
    agent_id = await client.spawn_agent(name="test-agent")
    print(f"Agent ID: {agent_id}")
    
    # Wait and check
    print("\nWaiting 10 seconds...")
    for i in range(10):
        time.sleep(1)
        print(f"  {i+1}s...")
        
        # Check if logs directory was created
        logs_dir = Path(f"/home/deano/projects/mind-swarm/subspace/agents/{agent_id}/logs")
        if logs_dir.exists():
            print(f"  Logs directory created!")
            log_file = logs_dir / "agent.log"
            if log_file.exists():
                print(f"  Log file found! Contents:")
                print(log_file.read_text())
                break
    
    print("\nChecking server logs...")
    
    # Check agent status via API
    try:
        status = await client.get_status()
        print(f"Server has {len(status.agents)} agents")
    except Exception as e:
        print(f"Error getting status: {e}")


if __name__ == "__main__":
    asyncio.run(test_simple_spawn())