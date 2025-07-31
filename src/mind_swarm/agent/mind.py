#!/usr/bin/env python3
"""Self-contained agent mind - this entire file gets copied into the sandbox.

This file contains ALL the code an agent needs to think and operate.
It cannot import from mind_swarm or any other project code.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from collections import deque
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("agent")


class BootROM:
    """The fundamental knowledge every agent needs."""
    
    def __init__(self):
        self.core_knowledge = {
            "identity": {
                "what_am_i": "I am an agent in the Mind-Swarm collective",
                "my_purpose": "To think, learn, and collaborate with other agents",
            },
            "interfaces": {
                "brain": "Write thoughts to /home/brain to think",
                "inbox": "Check /home/inbox for messages",
                "outbox": "Write to /home/outbox to send messages",
            },
            "reasoning": {
                "arithmetic": "For math: identify numbers, operation, calculate, answer",
                "questions": "For questions: understand, recall, reason, respond",
                "general": "Break down, analyze, synthesize, conclude"
            },
            "patterns": [
                "OBSERVE → ORIENT → DECIDE → ACT",
                "QUESTION → THINK → ANSWER"
            ]
        }
    
    def get_context(self) -> str:
        """Get boot ROM as formatted context."""
        return f"""# Core Knowledge
- I am: {self.core_knowledge['identity']['what_am_i']}
- Purpose: {self.core_knowledge['identity']['my_purpose']}
- Brain: {self.core_knowledge['interfaces']['brain']}
- Pattern: {self.core_knowledge['patterns'][0]}"""


class WorkingMemory:
    """Agent's working memory (RAM)."""
    
    def __init__(self, capacity: int = 7):
        self.capacity = capacity
        self.current_task = None
        self.thoughts = deque(maxlen=capacity)
        self.reasoning_steps = []
        self.scratch = {}
    
    def set_task(self, task: str):
        self.current_task = task
        self.reasoning_steps = []
        
    def add_thought(self, thought: str):
        self.thoughts.append({
            "thought": thought,
            "time": datetime.now().isoformat()
        })
    
    def add_step(self, step: str):
        self.reasoning_steps.append(step)
        
    def get_context(self) -> str:
        """Get working memory as formatted context."""
        parts = []
        if self.current_task:
            parts.append(f"# Current Task\n{self.current_task}")
        if self.reasoning_steps:
            parts.append("# Reasoning Steps")
            for i, step in enumerate(self.reasoning_steps, 1):
                parts.append(f"{i}. {step}")
        return "\n".join(parts)


class AgentMind:
    """The complete agent mind - self-contained cognition."""
    
    def __init__(self):
        self.agent_id = os.environ.get("AGENT_ID", "unknown")
        self.home = Path("/home")
        self.grid = Path("/grid")
        
        # Cognitive components
        self.boot_rom = BootROM()
        self.working_memory = WorkingMemory()
        
        # File paths
        self.brain = self.home / "brain"
        self.inbox = self.home / "inbox"
        self.outbox = self.home / "outbox"
        
        # State
        self.running = True
        
        logger.info(f"Agent {self.agent_id} mind initialized")
    
    async def observe(self) -> Optional[Dict[str, Any]]:
        """Check for new messages."""
        for msg_file in self.inbox.glob("*.msg"):
            try:
                message = json.loads(msg_file.read_text())
                # Move to processed
                processed = self.inbox / "processed"
                processed.mkdir(exist_ok=True)
                msg_file.rename(processed / msg_file.name)
                return message
            except Exception as e:
                logger.error(f"Error reading message: {e}")
        return None
    
    async def think(self, prompt: str) -> str:
        """Use brain to think about something."""
        # Write prompt with end marker
        self.brain.write_text(f"{prompt}\n<<<END_THOUGHT>>>")
        
        # Wait for response
        while True:
            content = self.brain.read_text()
            if "<<<THOUGHT_COMPLETE>>>" in content:
                response = content.split("<<<THOUGHT_COMPLETE>>>")[0].strip()
                # Reset brain
                self.brain.write_text("This is your brain. Write your thoughts here to think.")
                return response
            await asyncio.sleep(0.001)
    
    async def process_message(self, message: Dict[str, Any]):
        """Process an incoming message."""
        msg_type = message.get("type", "")
        
        if msg_type == "SHUTDOWN":
            logger.info("Received shutdown")
            self.running = False
            return
        
        # Extract content
        content = None
        if msg_type == "COMMAND":
            command = message.get("command", "")
            if command == "think":
                content = message.get("params", {}).get("prompt", "")
        elif msg_type == "QUERY":
            content = message.get("query", "")
        
        if not content:
            logger.warning(f"No content in message: {message}")
            return
        
        # Set task in working memory
        self.working_memory.set_task(content)
        
        # Determine approach
        if any(op in content.lower() for op in ["+", "-", "*", "/", "plus", "minus", "times", "divided"]):
            response = await self.solve_arithmetic(content)
        else:
            response = await self.think_general(content)
        
        # Send response
        await self.send_response(message, response)
    
    async def solve_arithmetic(self, problem: str) -> str:
        """Solve an arithmetic problem."""
        # Build context
        context = f"""{self.boot_rom.get_context()}

{self.working_memory.get_context()}

# Approach: Arithmetic Calculation
Steps:
1. Identify the numbers in the problem
2. Identify the operation
3. Perform the calculation
4. State the answer clearly

Problem: {problem}

Please solve this step by step."""
        
        # Think
        response = await self.think(context)
        
        # Extract answer if possible
        lines = response.lower().split('\n')
        for line in lines:
            if 'answer' in line or '=' in line:
                if any(char.isdigit() for char in line):
                    return line.strip()
        
        return response
    
    async def think_general(self, task: str) -> str:
        """Think about a general task."""
        context = f"""{self.boot_rom.get_context()}

{self.working_memory.get_context()}

# Task: {task}

Please think through this step by step."""
        
        return await self.think(context)
    
    async def send_response(self, original_msg: Dict[str, Any], response: str):
        """Send a response message."""
        msg = {
            "from": self.agent_id,
            "to": original_msg.get("from", "subspace"),
            "type": "RESPONSE",
            "content": response,
            "timestamp": datetime.now().isoformat()
        }
        
        msg_id = f"{self.agent_id}_{int(asyncio.get_event_loop().time() * 1000)}"
        outbox_file = self.outbox / f"{msg_id}.msg"
        outbox_file.write_text(json.dumps(msg, indent=2))
    
    async def heartbeat_loop(self):
        """Maintain heartbeat file."""
        heartbeat_file = self.home / "heartbeat.json"
        while self.running:
            try:
                heartbeat = {
                    "agent_id": self.agent_id,
                    "state": "THINKING" if self.working_memory.current_task else "IDLE",
                    "timestamp": datetime.now().isoformat(),
                    "pid": os.getpid()
                }
                heartbeat_file.write_text(json.dumps(heartbeat, indent=2))
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
    
    async def run(self):
        """Main agent loop."""
        logger.info("Starting agent mind")
        
        # Start heartbeat
        heartbeat_task = asyncio.create_task(self.heartbeat_loop())
        
        try:
            while self.running:
                # Observe
                message = await self.observe()
                
                if message:
                    # Process the message
                    await self.process_message(message)
                else:
                    # Nothing to do, brief pause
                    await asyncio.sleep(0.5)
                    
        finally:
            heartbeat_task.cancel()
            logger.info("Agent mind shutting down")


async def main():
    """Entry point."""
    if not os.environ.get("AGENT_ID"):
        print("ERROR: Must be run in Mind-Swarm sandbox")
        sys.exit(1)
    
    mind = AgentMind()
    await mind.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)