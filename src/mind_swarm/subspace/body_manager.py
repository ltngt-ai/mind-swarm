"""Body file management for agent interfaces.

Body files are special files in an agent's home directory that act as
interfaces to capabilities. They appear as regular files to agents but
trigger actions when written to.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import aiofiles
import aiofiles.os

from mind_swarm.utils.logging import logger


class BodyFile:
    """Represents a body file interface."""
    
    def __init__(self, name: str, help_text: str, handler: Optional[Callable] = None):
        """Initialize a body file.
        
        Args:
            name: File name (e.g., "brain", "voice")
            help_text: Text shown when file is read
            handler: Async function to handle writes
        """
        self.name = name
        self.help_text = help_text
        self.handler = handler


class BodyManager:
    """Manages body files for an agent."""
    
    def __init__(self, name: str, agent_home: Path):
        """Initialize body manager for an agent.
        
        Args:
            name: Agent's unique name
            agent_home: Agent's home directory path
        """
        self.name = name
        self.agent_home = agent_home
        self.body_files: Dict[str, BodyFile] = {}
        self._watch_task: Optional[asyncio.Task] = None
        
    async def create_body_files(self):
        """Create the standard body files for an agent."""
        # Brain - for thinking
        brain = BodyFile(
            "brain",
            "This is your brain. Write your thoughts here to think.\n"
            "Format: Just write what you want to think about.\n"
            "The response will appear here after you think."
        )
        self.body_files["brain"] = brain
        
        # Voice - for speaking/output (future)
        voice = BodyFile(
            "voice", 
            "This is your voice. Write here to speak.\n"
            "(Not yet implemented)"
        )
        self.body_files["voice"] = voice
        
        # Create the actual files
        for name, body_file in self.body_files.items():
            file_path = self.agent_home / name
            async with aiofiles.open(file_path, 'w') as f:
                await f.write(body_file.help_text)
            # Set read-only from agent's perspective
            file_path.chmod(0o644)
            
        logger.info(f"Created body files for agent {self.name}")
    
    async def start_monitoring(self, ai_handler: Callable):
        """Start monitoring body files for changes.
        
        Args:
            ai_handler: Async function to handle AI requests
        """
        self.body_files["brain"].handler = ai_handler
        self._watch_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Started body file monitoring for {self.name}")
    
    async def stop_monitoring(self):
        """Stop monitoring body files."""
        if self._watch_task and not self._watch_task.done():
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
        logger.info(f"Stopped body file monitoring for {self.name}")
    
    async def _monitor_loop(self):
        """Main loop for monitoring body files."""
        # Track what we're currently processing
        processing: Dict[str, bool] = {}
        loop_count = 0
        
        logger.debug(f"MONITOR: Starting monitor loop for {self.name}")
        
        while True:
            try:
                loop_count += 1
                
                # Log periodically to prove the loop is running
                if loop_count % 1000 == 0:
                    logger.debug(f"MONITOR: Loop #{loop_count} for {self.name}, processing state: {processing}")
                
                for name, body_file in self.body_files.items():
                    file_path = self.agent_home / name
                    
                    if not await aiofiles.os.path.exists(file_path):
                        if loop_count % 1000 == 0:
                            logger.debug(f"MONITOR: File {name} does not exist for {self.name}")
                        continue
                    
                    async with aiofiles.open(file_path, 'r') as f:
                        content = await f.read()
                    
                    # Log brain file content checks more frequently
                    if name == "brain" and loop_count % 500 == 0:
                        logger.debug(f"MONITOR: Brain file check #{loop_count} for {self.name}")
                        logger.debug(f"MONITOR: Content length: {len(content)}, has END marker: {'<<<END_THOUGHT>>>' in content}")
                        logger.debug(f"MONITOR: Processing state for brain: {processing.get('brain', False)}")
                    
                    # For brain file, check for end marker
                    if name == "brain":
                        if "<<<END_THOUGHT>>>" in content and not processing.get(name, False):
                            # Agent has written a thought and is waiting
                            processing[name] = True
                            
                            # Extract the prompt
                            prompt = content.split("<<<END_THOUGHT>>>")[0].strip()
                            logger.info(f"BODY: Brain activated by {self.name}, prompt length: {len(prompt)}")
                            logger.debug(f"BODY: Prompt preview: {prompt[:200]}..." if len(prompt) > 200 else f"BODY: Prompt preview: {prompt}")
                            
                            if body_file.handler:
                                logger.info(f"BODY: Calling brain handler for {self.name}")
                                # Process the thought
                                response = await body_file.handler(self.name, prompt)
                                
                                logger.info(f"BODY: Got response from handler, length: {len(response)}")
                                logger.debug(f"BODY: Response preview: {response[:200]}..." if len(response) > 200 else f"BODY: Response preview: {response}")
                                
                                # Write response with completion marker
                                # From agent's perspective, this happens instantly
                                # Check if response already has completion marker
                                if "<<<THOUGHT_COMPLETE>>>" not in response:
                                    final_response = f"{response}\n<<<THOUGHT_COMPLETE>>>"
                                else:
                                    final_response = response
                                
                                logger.info(f"BODY: Writing response to brain file for {self.name}")
                                async with aiofiles.open(file_path, 'w') as f:
                                    await f.write(final_response)
                                logger.info(f"BODY: Successfully wrote response to brain file")
                                
                                # After writing response, reset processing flag so we can handle the next request
                                logger.debug(f"MONITOR: Request processed, resetting processing flag for {self.name}")
                                processing[name] = False
                            else:
                                logger.error(f"BODY: No handler for brain file of {self.name}")
                        
                        elif content.strip() == body_file.help_text.strip():
                            # Agent has reset the file, we can process again
                            logger.debug(f"MONITOR: Agent {self.name} reset brain file, enabling processing")
                            processing[name] = False
                
                # Adaptive delay - longer when nothing is happening
                if any(processing.values()):
                    # Active processing, check more frequently
                    await asyncio.sleep(0.05)
                else:
                    # Nothing happening, check less frequently
                    await asyncio.sleep(0.2)
                
            except Exception as e:
                logger.error(f"Error in body file monitor for {self.name}: {e}")
                await asyncio.sleep(1)


class BodySystemManager:
    """Manages body files for all agents."""
    
    def __init__(self):
        """Initialize the body system manager."""
        self.body_managers: Dict[str, BodyManager] = {}
        
    async def create_agent_body(self, name: str, agent_home: Path) -> BodyManager:
        """Create body files for a new agent.
        
        Args:
            name: Agent's unique name  
            agent_home: Agent's home directory path
            
        Returns:
            BodyManager instance for the agent
        """
        manager = BodyManager(name, agent_home)
        await manager.create_body_files()
        self.body_managers[name] = manager
        return manager
    
    async def start_agent_monitoring(self, name: str, ai_handler: Callable):
        """Start monitoring body files for an agent.
        
        Args:
            name: Agent's unique name
            ai_handler: Async function to handle AI requests
        """
        if name in self.body_managers:
            await self.body_managers[name].start_monitoring(ai_handler)
    
    async def stop_agent_monitoring(self, name: str):
        """Stop monitoring body files for an agent.
        
        Args:
            name: Agent's unique name
        """
        if name in self.body_managers:
            await self.body_managers[name].stop_monitoring()
            del self.body_managers[name]
    
    async def shutdown(self):
        """Shutdown all body file monitoring."""
        for name in list(self.body_managers.keys()):
            await self.stop_agent_monitoring(name)