"""Cognitive Loop - The agent's thinking process implementation.

Implements the OODA loop (Observe, Orient, Decide, Act) with
integration of Boot ROM knowledge and Working Memory.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from .boot_rom import BootROM
from .working_memory import WorkingMemory

logger = logging.getLogger("agent.cognitive")


class CognitiveLoop:
    """The agent's cognitive loop - coordinates thinking."""
    
    def __init__(self, agent_id: str, home: Path):
        """Initialize the cognitive loop.
        
        Args:
            agent_id: The agent's identifier
            home: Path to agent's home directory
        """
        self.agent_id = agent_id
        self.home = home
        
        # Core cognitive components
        self.boot_rom = BootROM()
        self.working_memory = WorkingMemory()
        
        # File interfaces
        self.brain_file = self.home / "brain"
        self.inbox_dir = self.home / "inbox"
        self.outbox_dir = self.home / "outbox"
        self.memory_dir = self.home / "memory"
        
        # Ensure directories exist
        self.inbox_dir.mkdir(exist_ok=True)
        self.outbox_dir.mkdir(exist_ok=True)
        self.memory_dir.mkdir(exist_ok=True)
        
        # State
        self.cycle_count = 0
        self.last_activity = datetime.now()
    
    async def run_cycle(self) -> bool:
        """Run one complete cognitive cycle.
        
        Returns:
            True if something was processed, False if idle
        """
        self.cycle_count += 1
        
        # OBSERVE - Check environment for inputs
        observation = await self.observe()
        if not observation:
            return False
        
        # ORIENT - Understand what we're dealing with
        orientation = await self.orient(observation)
        
        # DECIDE - Choose approach
        decision = await self.decide(orientation)
        
        # ACT - Execute the decision
        await self.act(observation, orientation, decision)
        
        self.last_activity = datetime.now()
        return True
    
    async def observe(self) -> Optional[Dict[str, Any]]:
        """Observe - Check for inputs (messages, state changes)."""
        # Check inbox for messages
        msg_files = list(self.inbox_dir.glob("*.msg"))
        if msg_files:
            # Process oldest first
            msg_file = min(msg_files, key=lambda f: f.stat().st_mtime)
            try:
                message = json.loads(msg_file.read_text())
                
                # Move to processed
                processed_dir = self.inbox_dir / "processed"
                processed_dir.mkdir(exist_ok=True)
                msg_file.rename(processed_dir / msg_file.name)
                
                logger.info(f"Observed message: {message.get('type', 'unknown')}")
                self.working_memory.add_observation(f"Received {message.get('type', 'unknown')} message")
                
                return message
                
            except Exception as e:
                logger.error(f"Error reading message {msg_file}: {e}")
                msg_file.unlink()  # Remove corrupted message
        
        return None
    
    async def orient(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """Orient - Analyze and understand the observation."""
        msg_type = observation.get("type", "")
        
        orientation = {
            "msg_type": msg_type,
            "from": observation.get("from", "unknown"),
            "requires_response": True
        }
        
        # Analyze based on message type
        if msg_type == "COMMAND":
            command = observation.get("command", "")
            params = observation.get("params", {})
            
            if command == "think":
                content = params.get("prompt", "")
                orientation.update({
                    "task_type": self._classify_task(content),
                    "content": content,
                    "approach": "thinking"
                })
            else:
                orientation.update({
                    "task_type": "command",
                    "content": command,
                    "params": params,
                    "approach": "execution"
                })
                
        elif msg_type == "QUERY":
            query = observation.get("query", "")
            orientation.update({
                "task_type": self._classify_task(query),
                "content": query,
                "approach": "answering"
            })
            
        elif msg_type == "SHUTDOWN":
            orientation.update({
                "task_type": "shutdown",
                "requires_response": False,
                "approach": "termination"
            })
        
        self.working_memory.add_observation(f"Task type: {orientation.get('task_type', 'unknown')}")
        return orientation
    
    def _classify_task(self, content: str) -> str:
        """Classify the type of task based on content."""
        content_lower = content.lower()
        
        # Check for arithmetic
        if any(op in content_lower for op in ['+', '-', '*', '/', 'plus', 'minus', 'times', 'divided', 'add', 'subtract']):
            return "arithmetic"
        
        # Check for question words
        if any(q in content_lower for q in ['what', 'why', 'how', 'when', 'where', 'who', '?']):
            return "question"
        
        # Check for analysis keywords
        if any(word in content_lower for word in ['analyze', 'explain', 'describe', 'compare']):
            return "analytical"
        
        return "general"
    
    async def decide(self, orientation: Dict[str, Any]) -> Dict[str, Any]:
        """Decide - Choose how to approach the task."""
        task_type = orientation.get("task_type", "general")
        approach = orientation.get("approach", "thinking")
        
        # Get reasoning template from boot ROM
        template = self.boot_rom.get_reasoning_template(task_type)
        
        decision = {
            "approach": approach,
            "template": template,
            "task_type": task_type
        }
        
        # Set up working memory
        if "content" in orientation:
            self.working_memory.set_task(
                orientation["content"],
                source=orientation.get("from", "unknown"),
                task_type=task_type
            )
        
        # Add specific decision logic based on task type
        if task_type == "arithmetic":
            decision["steps"] = [
                "Identify the numbers in the problem",
                "Identify the mathematical operation",
                "Perform the calculation step by step",
                "Verify the result",
                "State the final answer clearly"
            ]
        elif task_type == "shutdown":
            decision["action"] = "terminate"
        else:
            decision["steps"] = [
                "Understand what is being asked",
                "Break down the problem if complex",
                "Apply relevant knowledge and reasoning",
                "Formulate a clear response"
            ]
        
        self.working_memory.add_reasoning_step(f"Decided approach: {approach} using {task_type} template")
        return decision
    
    async def act(self, observation: Dict[str, Any], orientation: Dict[str, Any], decision: Dict[str, Any]):
        """Act - Execute the decided approach."""
        if decision.get("action") == "terminate":
            logger.info("Received shutdown command")
            # The main loop will handle actual termination
            return
        
        # Most actions involve thinking
        if decision["approach"] in ["thinking", "answering"]:
            response = await self._think_about_task(orientation["content"], decision)
            
            # Send response if needed
            if orientation.get("requires_response", True):
                await self._send_response(observation, response)
    
    async def _think_about_task(self, task: str, decision: Dict[str, Any]) -> str:
        """Use the brain to think about a task."""
        # Build thinking context
        context_parts = [
            self.boot_rom.format_core_knowledge(),
            self.working_memory.format_for_thinking(),
            "",
            "=== CURRENT THINKING TASK ===",
            f"Task: {task}",
            f"Approach: {decision['template']['approach']}",
            ""
        ]
        
        if "steps" in decision:
            context_parts.append("Steps to follow:")
            for i, step in enumerate(decision["steps"], 1):
                context_parts.append(f"{i}. {step}")
            context_parts.append("")
        
        context_parts.append("Please think through this step by step:")
        
        full_context = "\n".join(context_parts)
        
        # Use brain interface
        response = await self._use_brain(full_context)
        
        # Update working memory with result
        self.working_memory.add_reasoning_step("Completed thinking", result=response)
        
        return response
    
    async def _use_brain(self, prompt: str) -> str:
        """Use the brain file interface to think."""
        # Write prompt with end marker
        self.brain_file.write_text(f"{prompt}\n<<<END_THOUGHT>>>")
        
        # Wait for response
        while True:
            content = self.brain_file.read_text()
            if "<<<THOUGHT_COMPLETE>>>" in content:
                # Extract response
                response = content.split("<<<THOUGHT_COMPLETE>>>")[0].strip()
                
                # Reset brain for next use
                self.brain_file.write_text("This is your brain. Write your thoughts here to think.")
                
                return response
            
            # Brief pause to avoid spinning
            await asyncio.sleep(0.01)
    
    async def _send_response(self, original_msg: Dict[str, Any], response: str):
        """Send a response message."""
        response_msg = {
            "from": self.agent_id,
            "to": original_msg.get("from", "subspace"),
            "in_reply_to": original_msg.get("id"),
            "type": "RESPONSE",
            "content": response,
            "timestamp": datetime.now().isoformat()
        }
        
        # Generate unique message ID
        msg_id = f"{self.agent_id}_{int(datetime.now().timestamp() * 1000)}"
        msg_file = self.outbox_dir / f"{msg_id}.msg"
        
        # Write message
        msg_file.write_text(json.dumps(response_msg, indent=2))
        
        logger.info(f"Sent response to {response_msg['to']}")