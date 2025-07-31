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
    
    def __init__(self, agent_id: str, agent_home: Path):
        """Initialize body manager for an agent.
        
        Args:
            agent_id: Agent's unique identifier
            agent_home: Agent's home directory path
        """
        self.agent_id = agent_id
        self.agent_home = agent_home
        self.body_files: Dict[str, BodyFile] = {}
        self._watch_task: Optional[asyncio.Task] = None
        
    def create_body_files(self):
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
            file_path.write_text(body_file.help_text)
            # Set read-only from agent's perspective
            file_path.chmod(0o644)
            
        logger.info(f"Created body files for agent {self.agent_id}")
    
    async def start_monitoring(self, ai_handler: Callable):
        """Start monitoring body files for changes.
        
        Args:
            ai_handler: Async function to handle AI requests
        """
        self.body_files["brain"].handler = ai_handler
        self._watch_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Started body file monitoring for {self.agent_id}")
    
    async def stop_monitoring(self):
        """Stop monitoring body files."""
        if self._watch_task and not self._watch_task.done():
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
        logger.info(f"Stopped body file monitoring for {self.agent_id}")
    
    async def _monitor_loop(self):
        """Main loop for monitoring body files."""
        # Track what we're currently processing
        processing: Dict[str, bool] = {}
        
        while True:
            try:
                for name, body_file in self.body_files.items():
                    file_path = self.agent_home / name
                    
                    if not file_path.exists():
                        continue
                    
                    content = file_path.read_text()
                    
                    # For brain file, check for end marker
                    if name == "brain":
                        if "<<<END_THOUGHT>>>" in content and not processing.get(name, False):
                            # Agent has written a thought and is waiting
                            processing[name] = True
                            
                            # Extract the prompt
                            prompt = content.split("<<<END_THOUGHT>>>")[0].strip()
                            logger.debug(f"Brain activated by {self.agent_id}: {prompt[:50]}...")
                            
                            if body_file.handler:
                                # Process the thought
                                response = await body_file.handler(self.agent_id, prompt)
                                
                                # Write response with completion marker
                                # From agent's perspective, this happens instantly
                                # Check if response already has completion marker
                                if "<<<THOUGHT_COMPLETE>>>" not in response:
                                    file_path.write_text(f"{response}\n<<<THOUGHT_COMPLETE>>>")
                                else:
                                    file_path.write_text(response)
                        
                        elif content.strip() == body_file.help_text.strip():
                            # Agent has reset the file, we can process again
                            processing[name] = False
                
                # Adaptive delay - longer when nothing is happening
                if any(processing.values()):
                    # Active processing, check more frequently
                    await asyncio.sleep(0.05)
                else:
                    # Nothing happening, check less frequently
                    await asyncio.sleep(0.2)
                
            except Exception as e:
                logger.error(f"Error in body file monitor for {self.agent_id}: {e}")
                await asyncio.sleep(1)


class BodySystemManager:
    """Manages body files for all agents."""
    
    def __init__(self):
        """Initialize the body system manager."""
        self.body_managers: Dict[str, BodyManager] = {}
        
    def create_agent_body(self, agent_id: str, agent_home: Path) -> BodyManager:
        """Create body files for a new agent.
        
        Args:
            agent_id: Agent's unique identifier  
            agent_home: Agent's home directory path
            
        Returns:
            BodyManager instance for the agent
        """
        manager = BodyManager(agent_id, agent_home)
        manager.create_body_files()
        self.body_managers[agent_id] = manager
        return manager
    
    async def start_agent_monitoring(self, agent_id: str, ai_handler: Callable):
        """Start monitoring body files for an agent.
        
        Args:
            agent_id: Agent's unique identifier
            ai_handler: Async function to handle AI requests
        """
        if agent_id in self.body_managers:
            await self.body_managers[agent_id].start_monitoring(ai_handler)
    
    async def stop_agent_monitoring(self, agent_id: str):
        """Stop monitoring body files for an agent.
        
        Args:
            agent_id: Agent's unique identifier
        """
        if agent_id in self.body_managers:
            await self.body_managers[agent_id].stop_monitoring()
            del self.body_managers[agent_id]
    
    async def shutdown(self):
        """Shutdown all body file monitoring."""
        for agent_id in list(self.body_managers.keys()):
            await self.stop_agent_monitoring(agent_id)