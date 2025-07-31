#!/usr/bin/env python3
"""Test agent spawning and thinking."""

import asyncio
import aiohttp
import json

async def test_agent():
    async with aiohttp.ClientSession() as session:
        # 1. Spawn an agent
        async with session.post(
            "http://localhost:8888/agents/spawn",
            json={"name": "test-thinker", "use_premium": False}
        ) as resp:
            result = await resp.json()
            agent_id = result["agent_id"]
            print(f"Spawned agent: {agent_id}")
        
        # 2. Give it a simple math task
        await asyncio.sleep(2)  # Let agent start up
        
        async with session.post(
            f"http://localhost:8888/agents/{agent_id}/command",
            json={"command": "think", "params": {"task": "What is 2 + 2?"}}
        ) as resp:
            result = await resp.json()
            print(f"Sent command: {result}")
        
        # 3. Wait and check status
        await asyncio.sleep(5)
        
        async with session.get(f"http://localhost:8888/agents/{agent_id}") as resp:
            status = await resp.json()
            print(f"Agent status: {json.dumps(status, indent=2)}")

if __name__ == "__main__":
    asyncio.run(test_agent())