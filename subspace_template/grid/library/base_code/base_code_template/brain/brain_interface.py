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
    ObservationMemoryBlock, MemoryType, FileMemoryBlock, Priority
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
    def remove_memory(self, memory_id: str) -> None:
        ...
from ..actions import Action
from ..utils import DateTimeEncoder, FileManager

logger = logging.getLogger("Cyber.brain")


class BrainInterface:
    """
    Clean interface for AI thinking operations.
    
    Handles all brain file communication, request formatting, and response parsing.
    Provides high-level thinking methods while abstracting away low-level details.
    """
    
    def __init__(self, brain_file: Path, cyber_id: str):
        """Initialize the brain interface.
        
        Args:
            brain_file: Path to the brain file for communication
            cyber_id: The Cyber's identifier for logging
        """
        self.brain_file = brain_file
        self.cyber_id = cyber_id
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
                "instruction": """
Review your working memory and decide what deserves immediate attention. 
You can see a file with ID starting with 'memory:personal/memory/processed_observations.json' - its content shows observations you've already handled. 
Any observation whose memory_id appears in that content has ALREADY BEEN PROCESSED and should NOT be selected again. Instead, list those in obsolete_observations for cleanup. Select an OBSERVATION (ID starting with 'observation:') that is NOT in the processed observations list. If all observations are already processed, return 'none' for memory_id. 
For obsolete_observations, list any observation IDs that appear in the processed observations content or are duplicates.
Always start your output with [[ ## reasoning ## ]]
""",
                "inputs": {
                    "working_memory": "Your current symbolic memory with all observations, messages, tasks, and context"
                },
                "outputs": {
                    "reasoning": "Why this memory deserves attention right now",
                    "memory_id": "The exact memory ID to focus on (e.g. 'observation:personal/new_message/msg_123:abc') or 'none'",
                    "obsolete_observations": "JSON array of observation IDs that are no longer relevant and can be removed, e.g. [\"observation:personal/action_result/old_action:123\", \"observation:personal/new_message/already_processed:456\"]"
                },
                "display_field": "reasoning"
            },
            "input_values": {
                "working_memory": memory_context
            }
        }
        
        response = await self._use_brain(json.dumps(thinking_request, cls=DateTimeEncoder))
        return self._parse_memory_selection_response(response)
    
    async def analyze_situation(self, observation: Dict[str, Any], working_memory: str) -> Dict[str, Any]:
        """Use brain to analyze and orient to the situation.
        
        Args:
            observation: The observation from observe phase
            working_memory: Current working memory context
            
        Returns:
            Orientation data including situation type, understanding, etc.
        """
        thinking_request = {
            "signature": {
                "instruction": """
You have observed something that needs your attention. 
Review your working memory and the specific observation to understand what's happening and how to respond.
Always start your output with [[ ## understanding ## ]]
""",
                "inputs": {
                    "working_memory": "Your current working memory with all context",
                    "observation": "The specific thing you observed that needs attention"
                },
                "outputs": {
                    "understanding": "What you understand about this situation and what it means",
                    "situation_type": "What kind of situation this is (e.g., 'message', 'task', 'file_change', 'status_update')",
                    "approach": "How you plan to approach handling this"
                },
                "display_field": "understanding"
            },
            "input_values": {
                "working_memory": working_memory,
                "observation": json.dumps(observation)
            },
            "request_id": f"orient_{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        response = await self._use_brain(json.dumps(thinking_request))
        # Just return the raw response - no parsing needed
        return json.loads(response)
    
    async def reflect_on_execution(self, memory_context: str) -> Optional[Dict[str, Any]]:
        """Use brain to reflect on previous execution results.
        
        This is the REFLECT stage where the brain learns from what happened.
        
        Args:
            memory_context: Working memory context with execution results
            
        Returns:
            Reflection data including insights and lessons learned
        """
        thinking_request = {
            "signature": {
                "instruction": """
Review the previous execution results in your memory. Reflect on what worked, what didn't, 
and what you learned. Consider how this affects your goals and priorities.
Your pipeline memory contains the last execution results.
""",
                "inputs": {
                    "working_memory": "Your current working memory including execution results"
                },
                "outputs": {
                    "insights": "Key insights from the execution results",
                    "lessons_learned": "What you learned that will help in future",
                    "goal_updates": "How your goals or priorities should change based on results",
                    "priority_adjustments": "What priorities need adjustment", 
                    "next_focus": "What you should focus on next based on this reflection"
                },
                "display_field": "insights"
            },
            "input_values": {
                "working_memory": memory_context
            },
            "request_id": f"reflect_{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        response = await self._use_brain(json.dumps(thinking_request))
        return json.loads(response)
    
    async def analyze_situation_from_observations(self, memory_context: str) -> Optional[Dict[str, Any]]:
        """Use brain to analyze the situation from all observations.
        
        This is the new OBSERVE phase where the brain understands the situation
        from all available observations in memory.
        
        Args:
            memory_context: Working memory context with all observations
            
        Returns:
            Orientation data including understanding and approach, or None
        """
        thinking_request = {
            "signature": {
                "instruction": """
Review all observations in your working memory to understand the current situation.
Look at all observations, messages, file changes, and other information to build a complete picture.
Determine what type of situation this is and how you should approach it.
Always start your output with [[ ## understanding ## ]]
""",
                "inputs": {
                    "working_memory": "Your current working memory with all observations and context"
                },
                "outputs": {
                    "understanding": "Your comprehensive understanding of the current situation based on all observations",
                    "situation_type": "The type of situation (e.g., 'new_message', 'task_request', 'file_update', 'maintenance', 'no_action_needed')",
                    "approach": "Your planned approach to handle this situation",
                },
                "display_field": "understanding"
            },
            "input_values": {
                "working_memory": memory_context
            },
            "request_id": f"observe_{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        response = await self._use_brain(json.dumps(thinking_request))
        result = json.loads(response)
        
        # Check if there's actually something to address
        output_values = result.get("output_values", {})
        situation_type = output_values.get("situation_type", "").lower()
        
        # If there's nothing to do, return None
        if situation_type in ["no_action_needed", "none", "nothing", ""]:
            return None
            
        return result
    
    async def identify_obsolete_observations(self, memory_context: str) -> Optional[Dict[str, Any]]:
        """Use brain to identify obsolete observations for cleanup.
        
        This is the CLEANUP phase where the brain identifies which observations
        are no longer relevant or have been processed.
        
        Args:
            memory_context: Working memory context for identifying obsolete items
            
        Returns:
            Dict with lists of obsolete and processed observation IDs, or None
        """
        thinking_request = {
            "signature": {
                "instruction": """
Review your working memory to identify observations that can be cleaned up.
Each observation has a cycle_count showing when it was created.
Look for:
1. Old observations from many cycles ago that are no longer relevant
2. Duplicate observations about the same thing
3. Action results that have been superseded by newer results
4. Observations about things that have already been handled

Be conservative - only mark observations as obsolete if you're certain they're no longer needed.
Current cycle count is in your working memory.
Always start your output with [[ ## reasoning ## ]]
""",
                "inputs": {
                    "working_memory": "Your working memory with observations including their cycle counts"
                },
                "outputs": {
                    "reasoning": "Why these observations can be cleaned up",
                    "obsolete_observations": "JSON array of observation IDs that are obsolete and can be removed, e.g. [\"observation:personal/action_result/old:cycle_5\"]"
                },
                "display_field": "reasoning"
            },
            "input_values": {
                "working_memory": memory_context
            },
            "request_id": f"cleanup_{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        response = await self._use_brain(json.dumps(thinking_request))
        result = json.loads(response)
        
        output_values = result.get("output_values", {})
        
        # Parse the JSON array from string if needed
        obsolete_json = output_values.get("obsolete_observations", "[]")
        
        try:
            if isinstance(obsolete_json, str):
                obsolete_observations = json.loads(obsolete_json)
            else:
                obsolete_observations = obsolete_json
        except:
            obsolete_observations = []
        
        # Return None if nothing to clean up
        if not obsolete_observations:
            return None
            
        return {
            "obsolete_observations": obsolete_observations
        }
    
    async def make_decision(
        self, 
        working_memory: str
    ) -> List[Dict[str, Any]]:
        """Use brain to decide on actions.
        
        Args:
            working_memory: Full working memory context including orientation
            
        Returns:
            List of action specifications as dicts
        """
        thinking_request = {
            "signature": {
                "instruction": """
Review your working memory to understand the current situation. 
You should see an orientation file that explains what's happening. 
Based on this understanding and your available actions, decide what to do next.
Always start your output with [[ ## reasoning ## ]]
""",
                "inputs": {
                    "working_memory": "Your complete working memory including the recent orientation and available actions"
                },
                "outputs": {
                    "reasoning": "Why these actions make sense given the situation",
                    "actions": "JSON array of actions to take, e.g. [{\"action\": \"respond\", \"params\": {\"message\": \"Hello\"}}]",
                },
                "display_field": "reasoning"
            },
            "input_values": {
                "working_memory": working_memory
            },
            "request_id": f"decide_{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        response = await self._use_brain(json.dumps(thinking_request))
        # Just return the raw response - no parsing needed
        return json.loads(response)
    
    def retrieve_memory_by_id(
        self, 
        memory_id: str, 
        memory_manager: MemoryManagerProtocol,
        reasoning: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a specific memory by ID and focus on it.
        
        For observations, this reads the referenced file.
        For files, this reads the file content.
        
        Args:
            memory_id: The memory ID to retrieve
            memory_manager: Memory manager instance
            reasoning: Brain's reasoning for selecting this memory
            
        Returns:
            Focused content as observation format, or None if not found
        """
        # Handle "none" or similar responses gracefully
        if not memory_id or memory_id.lower() in ["none", "null", "nil", ""]:
            logger.debug(f"No memory to retrieve (memory_id: {memory_id}), reasoning: {reasoning}")
            return None
        
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
        logger.info(f"Retrieved memory type: {type(memory_block).__name__}, ID: {memory_id}")
        
        # Handle different memory types
        if isinstance(memory_block, ObservationMemoryBlock):
            logger.info(f"Processing ObservationMemoryBlock: {memory_block.observation_type}")
            return self._focus_on_observation(memory_block, reasoning, memory_manager)
        elif isinstance(memory_block, FileMemoryBlock):
            logger.info(f"Processing FileMemoryBlock: {memory_block.location}")
            return self._focus_on_file(memory_block, reasoning)
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
    
    def _focus_on_observation(
        self, 
        obs: ObservationMemoryBlock, 
        reasoning: str,
        memory_manager: MemoryManagerProtocol
    ) -> Optional[Dict[str, Any]]:
        """Focus on an observation by reading its referenced content.
        
        Args:
            obs: Observation memory block
            reasoning: Brain's reasoning for focusing
            
        Returns:
            Content of the observation focus, or None if failed
        """
        try:
            file_path = Path(obs.path)
            
            # Mark observation as focused
            if not obs.metadata:
                obs.metadata = {}
            obs.metadata["focused"] = True
            obs.metadata["focused_at"] = datetime.now().isoformat()
            obs.priority = Priority.LOW  # Lower priority after being focused
            
            # Handle different observation types
            logger.info(f"Focusing on observation type: {obs.observation_type}, path: {obs.path}")
            if obs.observation_type == "new_message" and file_path.exists():
                logger.info(f"Processing message file: {file_path}")
                # Read message file
                message_content = json.loads(file_path.read_text())
                
                # Move to processed folder
                processed_dir = file_path.parent / "processed"
                processed_dir.mkdir(exist_ok=True)
                new_path = processed_dir / file_path.name
                logger.info(f"Moving message from {file_path} to {new_path}")
                file_path.rename(new_path)
                
                # Remove the observation from memory since message has been processed
                memory_manager.remove_memory(obs.id)
                logger.info(f"Removed processed message observation: {obs.id}")
                
                # Update the FileMemoryBlock to point to the new location
                for memory in list(memory_manager.symbolic_memory):
                    if (isinstance(memory, FileMemoryBlock) and 
                        memory.location == str(file_path)):
                        # Remove old reference
                        memory_manager.remove_memory(memory.id)
                        
                        # Create new FileMemoryBlock with updated path
                        updated_memory = FileMemoryBlock(
                            location=str(new_path),
                            priority=Priority.LOW,  # Lower priority since processed
                            confidence=memory.confidence,
                            metadata=memory.metadata
                        )
                        memory_manager.add_memory(updated_memory)
                        logger.info(f"Updated message file location: {file_path} -> {new_path}")
                
                # Return message as observation
                return {
                    "type": message_content.get("type", "MESSAGE"),
                    "from": message_content.get("from", "unknown"),
                    "to": message_content.get("to", "me"),
                    "subject": message_content.get("subject", "No subject"),
                    "content": message_content.get("content", ""),
                    "timestamp": message_content.get("timestamp", datetime.now().isoformat()),
                    "observe_reasoning": reasoning,
                    "file_moved_to": str(new_path)
                }
            
            elif file_path.exists():
                # Observation is just a notification that something changed
                # All info is already in the observation ID
                return {
                    "type": "OBSERVATION_NOTICE",
                    "id": obs.id,
                    "notification": "Memory has changed",
                    "observe_reasoning": reasoning
                }
            else:
                # Observation without file (e.g., status changes)
                return {
                    "type": "OBSERVATION_FOCUS",
                    "id": obs.id,  # Include the memory ID
                    "observation_type": obs.observation_type,
                    "path": obs.path,
                    "metadata": obs.metadata,
                    "observe_reasoning": reasoning
                }
                
        except Exception as e:
            logger.error(f"Error focusing on observation: {e}", exc_info=True)
            return None
    
    def _focus_on_file(
        self, 
        file_block: FileMemoryBlock, 
        reasoning: str
    ) -> Optional[Dict[str, Any]]:
        """Focus on a file by reading its content.
        
        Args:
            file_block: File memory block
            reasoning: Brain's reasoning for focusing
            
        Returns:
            File content as observation, or None if failed
        """
        try:
            file_path = Path(file_block.location)
            
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return None
                
            content = file_path.read_text()
            
            # Check if it's a message file
            if file_block.metadata and file_block.metadata.get("file_type") == "message":
                try:
                    message_data = json.loads(content)
                    return {
                        "type": message_data.get("type", "MESSAGE"),
                        "from": message_data.get("from", "unknown"),
                        "content": message_data.get("content", ""),
                        "file_path": str(file_path),
                        "observe_reasoning": reasoning
                    }
                except:
                    pass
            
            # Return generic file content
            return {
                "type": "FILE_FOCUS",
                "file_path": str(file_path),
                "content": content,
                "metadata": file_block.metadata,
                "observe_reasoning": reasoning
            }
                
        except Exception as e:
            logger.error(f"Error focusing on file: {e}", exc_info=True)
            return None
    
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
            
            # Parse obsolete observations first (before checking memory_id)
            obsolete_json = output_values.get("obsolete_observations", "[]")
            try:
                if isinstance(obsolete_json, str):
                    obsolete_observations = json.loads(obsolete_json)
                else:
                    obsolete_observations = obsolete_json
            except:
                obsolete_observations = []
            
            # Even if no focus is needed, we still return obsolete observations
            if memory_id == "none" or not memory_id:
                return {
                    "memory_id": None,
                    "reasoning": reasoning,
                    "obsolete_observations": obsolete_observations
                }
            
            return {
                "memory_id": memory_id,
                "reasoning": reasoning,
                "obsolete_observations": obsolete_observations
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
