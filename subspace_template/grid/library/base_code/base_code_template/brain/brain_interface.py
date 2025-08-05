"""Brain Interface - Clean abstraction for AI thinking operations.

This module provides a clean interface between the cognitive loop and AI thinking,
handling all brain file communication, request formatting, and response parsing.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

from ..memory import (
    WorkingMemoryManager, MemorySelector, ContextBuilder,
    MessageMemoryBlock, ObservationMemoryBlock, MemoryType
)
# Import Protocol for type checking
from typing import Protocol

class MemoryManagerProtocol(Protocol):
    """Protocol for memory manager compatibility."""
    @property
    def symbolic_memory(self) -> list:
        ...
    def mark_message_read(self, memory_id: str) -> None:
        ...
from ..actions import Action
from ..utils import DateTimeEncoder, FileManager

logger = logging.getLogger("agent.brain")


class BrainInterface:
    """
    Clean interface for AI thinking operations.
    
    Handles all brain file communication, request formatting, and response parsing.
    Provides high-level thinking methods while abstracting away low-level details.
    """
    
    def __init__(self, brain_file: Path, agent_id: str):
        """Initialize the brain interface.
        
        Args:
            brain_file: Path to the brain file for communication
            agent_id: The agent's identifier for logging
        """
        self.brain_file = brain_file
        self.agent_id = agent_id
        self.file_manager = FileManager()
        
    async def select_focus_from_memory(
        self, 
        memory_context: str
    ) -> Optional[Dict[str, Any]]:
        """Use brain to select what to focus on from full memory context.
        
        Args:
            memory_context: Complete memory context for the brain to analyze
            
        Returns:
            Selected memory item as dict, or None if no focus needed
        """
        thinking_request = {
            "signature": {
                "instruction": "Review your working memory and decide what deserves immediate attention. Look at timestamps, priorities, and your current situation. You can focus on any memory item by returning its ID, or return 'none' if no immediate focus is needed.",
                "inputs": {
                    "working_memory": "Your current symbolic memory with all observations, messages, tasks, and context"
                },
                "outputs": {
                    "memory_id": "The exact memory ID to focus on (e.g. 'message:inbox:from-alice/urgent-request:abc123') or 'none'",
                    "reasoning": "Why this memory deserves attention right now based on timestamps, priority, and context"
                },
                "display_field": "reasoning"
            },
            "input_values": {
                "working_memory": memory_context
            }
        }
        
        response = await self._use_brain(json.dumps(thinking_request, cls=DateTimeEncoder))
        return self._parse_memory_selection_response(response)
    
    async def analyze_situation(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """Use brain to analyze and orient to the situation.
        
        Args:
            observation: The observation to analyze
            
        Returns:
            Orientation data including situation type, understanding, etc.
        """
        thinking_request = {
            "signature": {
                "task": "What does this mean and how should I handle it?",
                "description": "Understand the context and meaning of observations",
                "inputs": {
                    "observations": "What was observed",
                },
                "outputs": {
                    "situation_type": "What kind of situation this is",
                    "understanding": "What I understand about the situation",
                    "relevant_knowledge": "What knowledge or skills apply"
                },
                "display_field": "understanding"
            },
            "input_values": {
                "observations": json.dumps(observation),
            },
            "request_id": f"orient_{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        response = await self._use_brain(json.dumps(thinking_request))
        return self._parse_orientation_response(response, observation)
    
    async def make_decision(
        self, 
        orientation: Dict[str, Any], 
        context: str
    ) -> List[Dict[str, Any]]:
        """Use brain to decide on actions.
        
        Args:
            orientation: Current situation understanding
            context: Decision-making context from memory
            
        Returns:
            List of action specifications as dicts
        """
        thinking_request = {
            "signature": {
                "task": "What actions should I take?",
                "description": "Decide what actions to take based on the situation",
                "inputs": {
                    "situation": "Current situation and understanding",
                    "working_memory": "Your memories including available actions",
                    "goal": "What needs to be accomplished"
                },
                "outputs": {
                    "actions": "JSON array of actions to take",
                    "reasoning": "Why these actions make sense"
                },
                "display_field": "reasoning"
            },
            "input_values": {
                "situation": orientation.get("reasoning", "Need to process this request"),
                "working_memory": context,
                "goal": orientation.get("content", "unknown request")
            },
            "request_id": f"decide_{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        response = await self._use_brain(json.dumps(thinking_request))
        return self._parse_action_decision_response(response)
    
    def retrieve_memory_by_id(
        self, 
        memory_id: str, 
        memory_manager: MemoryManagerProtocol,
        reasoning: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a specific memory by ID and convert to observation format.
        
        Args:
            memory_id: The memory ID to retrieve
            memory_manager: Memory manager instance
            reasoning: Brain's reasoning for selecting this memory
            
        Returns:
            Memory converted to observation format, or None if not found
        """
        # Find the memory by ID
        memory_block = None
        for memory in memory_manager.symbolic_memory:
            if memory.id == memory_id:
                memory_block = memory
                break
        
        if not memory_block:
            logger.warning(f"Memory ID not found: {memory_id}")
            return None
        
        logger.info(f"🧠 Brain reasoning: {reasoning}")
        
        # Handle different memory types
        if isinstance(memory_block, MessageMemoryBlock):
            return self._process_message_memory(memory_block, reasoning)
        elif isinstance(memory_block, ObservationMemoryBlock):
            return self._convert_observation_memory(memory_block, reasoning)
        else:
            # For other memory types, convert to observation format
            return {
                "from": "memory",
                "type": "MEMORY_FOCUS",
                "memory_type": memory_block.type.name,
                "content": str(memory_block),
                "id": memory_id,
                "timestamp": memory_block.timestamp.isoformat() if memory_block.timestamp else datetime.now().isoformat(),
                "observe_reasoning": reasoning
            }
    
    # === PRIVATE BRAIN COMMUNICATION METHODS ===
    
    async def _use_brain(self, prompt: str) -> str:
        """Use the brain file interface for thinking.
        
        Args:
            prompt: The thinking request as JSON string
            
        Returns:
            Brain response as string
        """
        # Parse the thinking request to get task info
        try:
            request_data = json.loads(prompt)
            task = request_data.get("signature", {}).get("task", "thinking")
            logger.info(f"🧠 Brain thinking: {task}")
        except:
            logger.info("🧠 Brain thinking...")
        
        # Escape markers
        escaped_prompt = prompt.replace("<<<THOUGHT_COMPLETE>>>", "[THOUGHT_COMPLETE]")
        escaped_prompt = escaped_prompt.replace("<<<END_THOUGHT>>>", "[END_THOUGHT]")
        
        # Write prompt
        self.brain_file.write_text(f"{escaped_prompt}\n<<<END_THOUGHT>>>")
        
        # Wait for response
        wait_count = 0
        while True:
            content = self.brain_file.read_text()
            
            if "<<<THOUGHT_COMPLETE>>>" in content:
                # Extract response
                prompt_end = content.find("<<<END_THOUGHT>>>")
                if prompt_end != -1:
                    response_start = prompt_end + len("<<<END_THOUGHT>>>")
                    response = content[response_start:].strip()
                    response = response.replace("<<<THOUGHT_COMPLETE>>>", "").strip()
                else:
                    response = content.split("<<<THOUGHT_COMPLETE>>>")[0].strip()
                    
                # Log brain response summary
                try:
                    response_data = json.loads(response)
                    if "output_values" in response_data:
                        # Show key output from brain
                        outputs = response_data["output_values"]
                        if "reasoning" in outputs:
                            reasoning = outputs["reasoning"][:100]
                            logger.info(f"🧠 Brain reasoning: {reasoning}")
                        elif "understanding" in outputs:
                            understanding = outputs["understanding"][:100]  
                            logger.info(f"🧠 Brain understanding: {understanding}")
                except:
                    logger.info("🧠 Brain response received")
                    
                # Reset brain
                self.brain_file.write_text("Ready for thinking.")
                
                return response
                
            wait_count += 1
            if wait_count % 100 == 0:
                logger.debug(f"⏳ Waiting for brain response ({wait_count/100:.1f}s)")
                
            await asyncio.sleep(0.01)
    
    # === RESPONSE PARSING METHODS ===
    
    def _parse_memory_selection_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse brain response to get selected memory ID.
        
        Args:
            response: Raw brain response
            
        Returns:
            Memory selection result with ID and reasoning, or None
        """
        try:
            result = json.loads(response)
            output_values = result.get("output_values", {})
            memory_id = output_values.get("memory_id", "")
            reasoning = output_values.get("reasoning", "")
            
            # Debug logging to understand what the brain is returning
            logger.debug(f"🧠 Brain output_values: {output_values}")
            logger.info(f"🧠 Brain selected: '{memory_id}' - {reasoning}")
            
            if memory_id == "none" or not memory_id:
                return None
            
            return {
                "memory_id": memory_id,
                "reasoning": reasoning
            }
                
        except Exception as e:
            logger.error(f"Failed to parse memory selection: {e}")
            
        return None
    
    def _parse_orientation_response(
        self, 
        response: str, 
        observation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse brain response for orientation.
        
        Args:
            response: Raw brain response
            observation: Original observation data
            
        Returns:
            Orientation data dict
        """
        try:
            result = json.loads(response)
            output = result.get("output_values", {})
            
            return {
                "task_type": output.get("situation_type", "unknown"),
                "understanding": output.get("understanding", ""),
                "approach": output.get("approach", "thinking"),
                "requires_response": True,
                "content": observation.get("command", observation.get("query", str(observation))),
                "timestamp": datetime.now(),
                "from": observation.get("from", "unknown"),
                "original_message": observation
            }
            
        except Exception as e:
            logger.error(f"Failed to parse orientation: {e}")
            return {
                "task_type": "unknown",
                "approach": "thinking",
                "requires_response": True,
                "content": str(observation),
                "timestamp": datetime.now()
            }
    
    def _parse_action_decision_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse brain response for action decision.
        
        Args:
            response: Raw brain response
            
        Returns:
            List of action specifications as dicts
        """
        actions = []
        
        try:
            result = json.loads(response)
            action_data = result.get("output_values", {}).get("actions", "[]")
            
            # Clean up markdown if present
            if isinstance(action_data, str) and "```" in action_data:
                start = action_data.find("```json") + 7 if "```json" in action_data else action_data.find("```") + 3
                end = action_data.rfind("```")
                if start < end:
                    action_data = action_data[start:end].strip()
                    
            # Parse actions
            if isinstance(action_data, str):
                action_objects = json.loads(action_data)
            else:
                action_objects = action_data
                
            # Return action specifications as dicts
            for spec in action_objects:
                if isinstance(spec, dict):
                    actions.append({
                        "name": spec.get("action"),
                        "params": spec.get("params", {})
                    })
                        
        except Exception as e:
            logger.error(f"Failed to parse action decision: {e}")
            
        return actions
    
    # === MEMORY CONVERSION METHODS ===
    
    def _process_message_memory(
        self, 
        msg: MessageMemoryBlock, 
        reasoning: str
    ) -> Optional[Dict[str, Any]]:
        """Process a selected message memory.
        
        Args:
            msg: Message memory block to process
            reasoning: Brain's reasoning for selecting this message
            
        Returns:
            Processed message as dict, or None if failed
        """
        try:
            msg_path = Path(msg.full_path)
            if msg_path.exists():
                message = json.loads(msg_path.read_text())
                message["observe_reasoning"] = reasoning
                return message
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            
        return None
    
    def _convert_observation_memory(
        self, 
        obs: ObservationMemoryBlock, 
        reasoning: str
    ) -> Dict[str, Any]:
        """Convert observation memory to standard format.
        
        Args:
            obs: Observation memory block to convert
            reasoning: Brain's reasoning for selecting this observation
            
        Returns:
            Observation in standard format
        """
        return {
            "from": "environment",
            "type": "OBSERVATION", 
            "observation_type": obs.observation_type,
            "content": obs.path,
            "path": obs.path,
            "timestamp": obs.timestamp.isoformat() if obs.timestamp else datetime.now().isoformat(),
            "id": obs.id,
            "observe_reasoning": reasoning
        }


class MessageProcessor:
    """Helper class for processing messages selected by the brain."""
    
    def __init__(self, inbox_dir: Path, file_manager: FileManager):
        """Initialize message processor.
        
        Args:
            inbox_dir: Path to agent's inbox directory
            file_manager: File manager instance
        """
        self.inbox_dir = inbox_dir
        self.file_manager = file_manager
    
    def process_selected_message(
        self, 
        msg: MessageMemoryBlock, 
        memory_manager: MemoryManagerProtocol,
        environment_scanner
    ) -> Optional[Dict[str, Any]]:
        """Process a selected message (mark as read, move to processed).
        
        Args:
            msg: Message memory block to process
            memory_manager: Memory manager instance
            environment_scanner: Environment scanner instance
            
        Returns:
            Processed message data, or None if failed
        """
        try:
            msg_path = Path(msg.full_path)
            if msg_path.exists():
                message = json.loads(msg_path.read_text())
                
                # Mark as read
                memory_manager.mark_message_read(msg.id)
                environment_scanner.mark_message_processed(str(msg_path))
                
                # Move to processed
                processed_dir = self.inbox_dir / "processed"
                self.file_manager.ensure_directory(processed_dir)
                msg_path.rename(processed_dir / msg_path.name)
                
                return message
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            
        return None