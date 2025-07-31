"""Cognitive Loop - The agent's thinking process.

This implements the OODA loop (Observe, Orient, Decide, Act) for agent cognition.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from mind_swarm.agent.cognition.boot_rom import BootROM
from mind_swarm.agent.cognition.working_memory import WorkingMemory
from mind_swarm.utils.logging import logger


class CognitiveLoop:
    """The agent's cognitive loop - how they think."""
    
    def __init__(self, agent_id: str, home_path: Path):
        """Initialize the cognitive loop.
        
        Args:
            agent_id: The agent's identifier
            home_path: Path to agent's home directory
        """
        self.agent_id = agent_id
        self.home = home_path
        
        # Core components
        self.boot_rom = BootROM()
        self.working_memory = WorkingMemory()
        
        # Paths
        self.brain_path = self.home / "brain"
        self.inbox_path = self.home / "inbox"
        self.outbox_path = self.home / "outbox"
        self.memory_path = self.home / "memory"
        
        # State
        self.thinking = False
        
    async def observe(self) -> Optional[Dict[str, Any]]:
        """Observe - Check for new inputs (messages, questions)."""
        # Check inbox for new messages
        for msg_file in self.inbox_path.glob("*.msg"):
            try:
                message = json.loads(msg_file.read_text())
                logger.info(f"Observed new message: {message.get('type', 'unknown')}")
                return message
            except Exception as e:
                logger.error(f"Error reading message: {e}")
        
        return None
    
    async def orient(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """Orient - Understand what's being asked/required."""
        msg_type = observation.get("type", "")
        
        # Extract the core content
        if msg_type == "COMMAND":
            command = observation.get("command", "")
            params = observation.get("params", {})
            
            if command == "think":
                # It's a thinking task
                prompt = params.get("prompt", "")
                return {
                    "task_type": "thinking",
                    "content": prompt,
                    "requires": "reasoning"
                }
            elif command == "solve":
                # It's a problem to solve
                problem = params.get("problem", "")
                return {
                    "task_type": "problem_solving", 
                    "content": problem,
                    "requires": "analysis"
                }
        
        elif msg_type == "QUERY":
            query = observation.get("query", "")
            
            # Analyze the query
            if any(op in query for op in ["+", "-", "*", "/", "plus", "minus"]):
                return {
                    "task_type": "arithmetic",
                    "content": query,
                    "requires": "calculation"
                }
            elif "?" in query:
                return {
                    "task_type": "question",
                    "content": query,
                    "requires": "knowledge"
                }
        
        # Default orientation
        return {
            "task_type": "general",
            "content": str(observation),
            "requires": "thinking"
        }
    
    async def decide(self, orientation: Dict[str, Any]) -> Dict[str, Any]:
        """Decide - Choose how to approach the task."""
        task_type = orientation["task_type"]
        content = orientation["content"]
        
        # Set up working memory
        self.working_memory.set_current_task(content)
        
        # Get reasoning template from boot ROM
        template = self.boot_rom.get_reasoning_template(task_type)
        
        # Decide on approach
        if task_type == "arithmetic":
            return {
                "approach": "calculation",
                "template": template,
                "steps": [
                    "Identify the numbers",
                    "Identify the operation", 
                    "Perform the calculation",
                    "State the answer"
                ]
            }
        elif task_type == "question":
            return {
                "approach": "knowledge_search",
                "template": template,
                "steps": [
                    "Understand what's being asked",
                    "Search memory for relevant facts",
                    "Reason about the answer",
                    "Formulate response"
                ]
            }
        else:
            return {
                "approach": "general_reasoning",
                "template": template,
                "steps": [
                    "Break down the problem",
                    "Think through each part",
                    "Combine insights",
                    "Generate response"
                ]
            }
    
    async def act(self, decision: Dict[str, Any], observation: Dict[str, Any]) -> str:
        """Act - Execute the decided approach using the brain."""
        approach = decision["approach"]
        steps = decision["steps"]
        
        # Build thinking context
        context = self._build_thinking_context(decision)
        
        # Execute thinking steps
        if approach == "calculation":
            response = await self._think_arithmetic(
                self.working_memory.current_task,
                context
            )
        else:
            # General thinking
            response = await self._think_general(
                self.working_memory.current_task,
                context,
                steps
            )
        
        # Send response
        await self._send_response(observation, response)
        
        return response
    
    def _build_thinking_context(self, decision: Dict[str, Any]) -> str:
        """Build the context to send to the brain."""
        parts = []
        
        # Add boot ROM knowledge
        parts.append(self.boot_rom.format_for_thinking())
        
        # Add working memory
        parts.append(self.working_memory.format_for_thinking())
        
        # Add approach
        parts.append(f"# Approach: {decision['approach']}")
        parts.append(f"Template: {decision['template']}")
        
        return "\n".join(parts)
    
    async def _think_arithmetic(self, problem: str, context: str) -> str:
        """Think through an arithmetic problem."""
        # Add specific arithmetic context
        full_prompt = f"""{context}

# Arithmetic Problem
{problem}

Please solve this step by step:
1. What numbers are involved?
2. What operation should I perform?
3. What is the calculation?
4. What is the final answer?"""
        
        # Use brain to think
        response = await self._use_brain(full_prompt)
        
        # Extract just the answer if possible
        if "answer" in response.lower():
            lines = response.split("\n")
            for line in lines:
                if "answer" in line.lower() and "=" in line:
                    return line.strip()
        
        return response
    
    async def _think_general(self, task: str, context: str, steps: List[str]) -> str:
        """Think through a general problem."""
        # Build step-by-step prompt
        steps_text = "\n".join(f"{i+1}. {step}" for i, step in enumerate(steps))
        
        full_prompt = f"""{context}

# Task
{task}

Please think through this following these steps:
{steps_text}"""
        
        return await self._use_brain(full_prompt)
    
    async def _use_brain(self, prompt: str) -> str:
        """Use the brain interface to think."""
        self.thinking = True
        
        # Write to brain file
        self.brain_path.write_text(f"{prompt}\n<<<END_THOUGHT>>>")
        
        # Wait for response
        while True:
            content = self.brain_path.read_text()
            if "<<<THOUGHT_COMPLETE>>>" in content:
                # Extract response
                response = content.split("<<<THOUGHT_COMPLETE>>>")[0].strip()
                
                # Reset brain
                self.brain_path.write_text("This is your brain. Write your thoughts here to think.")
                
                self.thinking = False
                
                # Add to working memory
                self.working_memory.add_thought(f"Brain response: {response}")
                
                return response
            
            await asyncio.sleep(0.001)
    
    async def _send_response(self, original_message: Dict[str, Any], response: str):
        """Send a response message."""
        response_msg = {
            "from": self.agent_id,
            "to": original_message.get("from", "subspace"),
            "in_reply_to": original_message.get("id"),
            "type": "RESPONSE",
            "content": response,
            "timestamp": datetime.now().isoformat()
        }
        
        # Write to outbox
        msg_id = f"{self.agent_id}_{int(asyncio.get_event_loop().time() * 1000)}"
        outbox_file = self.outbox_path / f"{msg_id}.msg"
        outbox_file.write_text(json.dumps(response_msg, indent=2))
        
        logger.info(f"Sent response: {response}")
    
    async def run_cycle(self) -> bool:
        """Run one cycle of the cognitive loop.
        
        Returns:
            True if processed something, False if idle
        """
        # Observe
        observation = await self.observe()
        if not observation:
            return False
        
        # Orient
        orientation = await self.orient(observation)
        self.working_memory.add_thought(f"Task type: {orientation['task_type']}")
        
        # Decide  
        decision = await self.decide(orientation)
        self.working_memory.add_thought(f"Approach: {decision['approach']}")
        
        # Act
        await self.act(decision, observation)
        
        # Move processed message
        msg_file = list(self.inbox_path.glob("*.msg"))[0]
        processed_dir = self.inbox_path / "processed"
        processed_dir.mkdir(exist_ok=True)
        msg_file.rename(processed_dir / msg_file.name)
        
        return True