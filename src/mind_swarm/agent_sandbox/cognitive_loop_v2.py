"""Cognitive Loop V2 - Intelligence through structured thinking at every step.

Instead of hardcoded logic, every step in the OODA loop involves actual
thinking using structured signatures. The agent orchestrates thinking
operations but doesn't contain the intelligence - that comes from the
LLM through the brain interface.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from .boot_rom import BootROM
from .working_memory import WorkingMemory
from .brain_protocol import (
    ThinkingRequest, ThinkingResponse, CognitiveSignatures
)

logger = logging.getLogger("agent.cognitive_v2")


class CognitiveLoopV2:
    """Cognitive loop that thinks at every step."""
    
    def __init__(self, agent_id: str, home: Path):
        """Initialize the cognitive loop.
        
        Args:
            agent_id: The agent's identifier
            home: Path to agent's home directory
        """
        self.agent_id = agent_id
        self.home = home
        
        # Core components
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
        """Run one complete OODA cycle with thinking at each step.
        
        Returns:
            True if something significant happened, False if idle
        """
        self.cycle_count += 1
        logger.debug(f"Starting cognitive cycle {self.cycle_count}")
        
        # OBSERVE - What's changed?
        observations = await self._observe()
        
        if not observations.get("observations"):
            # Nothing new observed
            return False
        
        # ORIENT - What does this mean?
        orientation = await self._orient(observations)
        
        # DECIDE - What should I do?
        decision = await self._decide(orientation)
        
        # ACT - Execute the decision
        result = await self._act(decision)
        
        # REFLECT - What did I learn?
        await self._reflect(decision, result)
        
        self.last_activity = datetime.now()
        return True
    
    async def _observe(self) -> Dict[str, Any]:
        """Observe phase - use thinking to identify what's changed."""
        # Gather inputs for observation
        inputs = {
            "working_memory": self.working_memory.format_for_thinking(),
            "new_messages": await self._check_messages(),
            "environment_state": await self._get_environment_state()
        }
        
        # Think about what we're observing
        request = ThinkingRequest(
            signature=CognitiveSignatures.OBSERVE,
            input_values=inputs
        )
        
        response = await self._think(request)
        
        # Update working memory with observations
        observations = response.output_values.get("observations", [])
        if isinstance(observations, str):
            observations = [observations]
        
        for obs in observations:
            self.working_memory.add_observation(obs)
        
        return response.output_values
    
    async def _orient(self, observations: Dict[str, Any]) -> Dict[str, Any]:
        """Orient phase - understand what the observations mean."""
        # Prepare inputs
        inputs = {
            "observations": observations.get("observations", []),
            "current_task": self.working_memory.current_task or "None",
            "recent_history": self._get_recent_history()
        }
        
        # Think about orientation
        request = ThinkingRequest(
            signature=CognitiveSignatures.ORIENT,
            input_values=inputs
        )
        
        response = await self._think(request)
        
        # Update understanding
        understanding = response.output_values.get("understanding", "")
        self.working_memory.add_thought(f"Situation: {understanding}")
        
        return response.output_values
    
    async def _decide(self, orientation: Dict[str, Any]) -> Dict[str, Any]:
        """Decide phase - determine what action to take."""
        # Prepare inputs
        inputs = {
            "understanding": orientation.get("understanding", ""),
            "available_actions": self._get_available_actions(),
            "goals": self._get_current_goals(),
            "constraints": self._get_constraints()
        }
        
        # Think about decision
        request = ThinkingRequest(
            signature=CognitiveSignatures.DECIDE,
            input_values=inputs
        )
        
        response = await self._think(request)
        
        # Record decision
        decision = response.output_values.get("decision", "")
        self.working_memory.add_reasoning_step(f"Decided: {decision}")
        
        return response.output_values
    
    async def _act(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Act phase - execute the decision."""
        # First plan the execution
        plan_inputs = {
            "decision": decision.get("decision", ""),
            "approach": decision.get("approach", ""),
            "available_tools": self._get_available_tools(),
            "current_state": self.working_memory.format_for_thinking()
        }
        
        plan_request = ThinkingRequest(
            signature=CognitiveSignatures.ACT_PLANNING,
            input_values=plan_inputs
        )
        
        plan = await self._think(plan_request)
        
        # Execute based on the plan
        first_action = plan.output_values.get("first_action", "")
        
        # Here we would execute specific actions based on what was decided
        # For now, we'll handle some basic cases
        if "send message" in first_action.lower():
            return await self._execute_send_message(decision)
        elif "answer" in first_action.lower() or "solve" in first_action.lower():
            return await self._execute_answer(decision)
        else:
            return {"executed": first_action, "status": "completed"}
    
    async def _reflect(self, decision: Dict[str, Any], result: Dict[str, Any]):
        """Reflect phase - learn from what happened."""
        inputs = {
            "action_taken": decision.get("decision", ""),
            "expected_outcome": decision.get("approach", ""),
            "actual_outcome": str(result),
            "surprises": "None identified yet"
        }
        
        request = ThinkingRequest(
            signature=CognitiveSignatures.REFLECT,
            input_values=inputs
        )
        
        response = await self._think(request)
        
        # Store lessons learned
        lessons = response.output_values.get("lessons", "")
        if lessons:
            self.working_memory.add_thought(f"Learned: {lessons}")
    
    async def _think(self, request: ThinkingRequest) -> ThinkingResponse:
        """Send a thinking request through the brain interface."""
        logger.info(f"AGENT: Starting _think for {self.agent_id}")
        
        # Write request to brain file
        request_text = request.to_brain_format()
        logger.info(f"AGENT: Writing to brain file, length: {len(request_text)}")
        self.brain_file.write_text(request_text)
        logger.info(f"AGENT: Successfully wrote to brain file")
        
        # Wait for response
        wait_count = 0
        while True:
            content = self.brain_file.read_text()
            wait_count += 1
            
            if "<<<THOUGHT_COMPLETE>>>" in content:
                logger.info(f"AGENT: Got response after {wait_count} checks, content length: {len(content)}")
                logger.info(f"AGENT: Response preview: {content}")
                
                # Parse response
                response = ThinkingResponse.from_brain_format(content)
                logger.info(f"AGENT: Parsed response successfully")
                
                # Reset brain for next use
                self.brain_file.write_text("This is your brain. Write your thoughts here to think.")
                logger.info(f"AGENT: Reset brain file for next use")
                
                return response
            
            if wait_count % 100 == 0:  # Log every 100 checks (1 second)
                logger.info(f"AGENT: Still waiting for response, check #{wait_count}")
            
            await asyncio.sleep(0.01)
    
    # Helper methods for gathering inputs
    
    async def _check_messages(self) -> str:
        """Check for new messages in inbox."""
        new_messages = []
        for msg_file in self.inbox_dir.glob("*.msg"):
            try:
                msg = json.loads(msg_file.read_text())
                new_messages.append(f"{msg.get('type', 'unknown')} from {msg.get('from', 'unknown')}")
            except:
                pass
        
        return f"{len(new_messages)} new messages: {', '.join(new_messages)}" if new_messages else "No new messages"
    
    async def _get_environment_state(self) -> str:
        """Get current environment state."""
        state_parts = [
            f"Cycle: {self.cycle_count}",
            f"Current task: {self.working_memory.current_task or 'None'}",
            f"Working memory items: {len(self.working_memory.thoughts)}"
        ]
        return "; ".join(state_parts)
    
    def _get_recent_history(self) -> str:
        """Get recent action history."""
        recent = list(self.working_memory.thoughts)[-3:]
        return "; ".join(t["content"] for t in recent) if recent else "No recent history"
    
    def _get_available_actions(self) -> str:
        """List available actions."""
        return "Check messages, Answer questions, Send messages, Explore Grid, Update memory, Think about topic"
    
    def _get_current_goals(self) -> str:
        """Get current goals."""
        return "Help others, Learn and grow, Answer questions accurately, Collaborate with other agents"
    
    def _get_constraints(self) -> str:
        """Get current constraints."""
        return "Must work within sandbox, Can only communicate through messages, Limited working memory"
    
    def _get_available_tools(self) -> str:
        """Get available tools."""
        return "Brain (thinking), Inbox/Outbox (messaging), Memory (storage), Grid access"
    
    # Action execution methods
    
    async def _execute_send_message(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a message sending action."""
        # This would be more sophisticated in practice
        # For now, just log it
        logger.info(f"Would send message based on decision: {decision.get('decision', '')}")
        return {"status": "message_sent", "details": "Message sending not fully implemented"}
    
    async def _execute_answer(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an answer/response action."""
        # Get the specific question/task
        task = self.working_memory.current_task
        
        if not task:
            return {"status": "no_task", "details": "No current task to answer"}
        
        # Determine what kind of answer is needed
        if any(op in task.lower() for op in ['+', '-', '*', '/', 'plus', 'minus']):
            # Arithmetic problem
            return await self._solve_arithmetic(task)
        else:
            # General question
            return await self._answer_question(task)
    
    async def _solve_arithmetic(self, problem: str) -> Dict[str, Any]:
        """Solve an arithmetic problem."""
        request = ThinkingRequest(
            signature=CognitiveSignatures.SOLVE_ARITHMETIC,
            input_values={
                "problem": problem,
                "context": "User asked me to solve this"
            }
        )
        
        response = await self._think(request)
        
        # Send the answer
        answer = response.output_values.get("answer", "Could not solve")
        await self._send_response(answer)
        
        return {"status": "answered", "answer": answer}
    
    async def _answer_question(self, question: str) -> Dict[str, Any]:
        """Answer a general question."""
        request = ThinkingRequest(
            signature=CognitiveSignatures.ANSWER_QUESTION,
            input_values={
                "question": question,
                "context": self.working_memory.format_for_thinking(),
                "relevant_knowledge": self.boot_rom.format_core_knowledge()
            }
        )
        
        response = await self._think(request)
        
        # Send the answer
        answer = response.output_values.get("answer", "I don't know")
        await self._send_response(answer)
        
        return {"status": "answered", "answer": answer}
    
    async def _send_response(self, content: str):
        """Send a response message."""
        # Get original message from working memory context
        # For now, respond to "subspace"
        response_msg = {
            "from": self.agent_id,
            "to": self.working_memory.task_source or "subspace",
            "type": "RESPONSE",
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        msg_id = f"{self.agent_id}_{int(datetime.now().timestamp() * 1000)}"
        msg_file = self.outbox_dir / f"{msg_id}.msg"
        msg_file.write_text(json.dumps(response_msg, indent=2))
        
        logger.info(f"Sent response: {content}")