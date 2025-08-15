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
from ..utils import DateTimeEncoder, FileManager

logger = logging.getLogger("Cyber.brain")


class BrainInterface:
    """
    Clean interface for AI thinking operations.
    
    Handles all brain file communication, request formatting, and response parsing.
    Provides high-level thinking methods while abstracting away low-level details.
    """
    
    def __init__(self, brain_file: Path, cyber_id: str, personal_dir: Path):
        """Initialize the brain interface.
        
        Args:
            brain_file: Path to the brain file for communication
            cyber_id: The Cyber's identifier for logging
            personal_dir: Path to the cyber's personal directory
        """
        self.brain_file = brain_file
        self.cyber_id = cyber_id
        self.personal_dir = personal_dir
        self.file_manager = FileManager()
        
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
        shutdown_file = self.personal_dir / ".internal" / "shutdown"
        
        while True:
            # Check for shutdown signal
            if shutdown_file.exists():
                logger.warning("🛑 Shutdown detected during brain operation - cancelling")
                # Reset brain file
                self.brain_file.write_text("Ready for thinking.")
                # Return empty response to let cognitive loop handle shutdown
                return '{"cancelled": true, "reason": "shutdown"}'
            
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