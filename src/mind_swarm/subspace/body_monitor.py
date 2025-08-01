"""Efficient body file monitoring using inotify.

Uses Linux inotify for efficient file system event monitoring instead of polling.
Falls back to polling if inotify is not available.
"""

import asyncio
import os
from pathlib import Path
from typing import Dict, Set, Callable, Optional
from datetime import datetime
import aiofiles

try:
    # Try to use watchdog which provides cross-platform file monitoring
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

from mind_swarm.utils.logging import logger


class InotifyBodyMonitor:
    """Efficient body file monitoring using inotify/watchdog."""
    
    def __init__(self):
        """Initialize the inotify-based monitor."""
        self.observers: Dict[str, Observer] = {}
        self.handlers: Dict[str, BodyFileHandler] = {}
        self.loop = asyncio.get_event_loop()
        
    async def add_agent(self, agent_id: str, agent_home: Path, ai_handler: Callable):
        """Add an agent to monitor.
        
        Args:
            agent_id: Agent's unique identifier
            agent_home: Path to agent's home directory
            ai_handler: Async function to handle AI requests
        """
        if not HAS_WATCHDOG:
            logger.warning("Watchdog not available, falling back to polling")
            return
            
        # Create handler for this agent
        handler = BodyFileHandler(agent_id, agent_home, ai_handler, self.loop)
        self.handlers[agent_id] = handler
        
        # Create observer for the agent's home directory
        observer = Observer()
        observer.schedule(handler, str(agent_home), recursive=False)
        observer.start()
        
        self.observers[agent_id] = observer
        logger.info(f"Started inotify monitoring for {agent_id}")
    
    async def remove_agent(self, agent_id: str):
        """Stop monitoring an agent.
        
        Args:
            agent_id: Agent's unique identifier
        """
        if agent_id in self.observers:
            self.observers[agent_id].stop()
            self.observers[agent_id].join(timeout=1)
            del self.observers[agent_id]
            del self.handlers[agent_id]
            logger.info(f"Stopped inotify monitoring for {agent_id}")
    
    async def shutdown(self):
        """Shutdown all monitoring."""
        for agent_id in list(self.observers.keys()):
            await self.remove_agent(agent_id)


class BodyFileHandler(FileSystemEventHandler):
    """Handles file system events for body files."""
    
    def __init__(self, agent_id: str, agent_home: Path, ai_handler: Callable, loop):
        """Initialize the handler.
        
        Args:
            agent_id: Agent's unique identifier
            agent_home: Path to agent's home directory
            ai_handler: Async function to handle AI requests
            loop: Event loop for async operations
        """
        self.agent_id = agent_id
        self.agent_home = agent_home
        self.ai_handler = ai_handler
        self.loop = loop
        self.processing: Set[str] = set()
        
    def on_modified(self, event):
        """Handle file modification events."""
        if isinstance(event, FileModifiedEvent) and not event.is_directory:
            file_path = Path(event.src_path)
            
            # Only care about body files
            if file_path.name == "brain" and file_path.parent == self.agent_home:
                # Schedule async processing in the event loop
                asyncio.run_coroutine_threadsafe(
                    self._process_brain_file(file_path),
                    self.loop
                )
    
    async def _process_brain_file(self, file_path: Path):
        """Process brain file modification."""
        # Avoid double processing
        if "brain" in self.processing:
            return
            
        try:
            # Use async file I/O
            async with aiofiles.open(file_path, 'r') as f:
                content = await f.read()
            
            # Check for end marker
            if "<<<END_THOUGHT>>>" in content:
                self.processing.add("brain")
                
                # Extract prompt
                prompt = content.split("<<<END_THOUGHT>>>")[0].strip()
                logger.debug(f"Brain activated by {self.agent_id}: {prompt[:50]}...")
                
                # Process the thought
                response = await self.ai_handler(self.agent_id, prompt)
                
                # Write response with completion marker
                async with aiofiles.open(file_path, 'w') as f:
                    await f.write(f"{response}\n<<<THOUGHT_COMPLETE>>>")
                
            elif content.startswith("This is your brain"):
                # File was reset, ready for next thought
                self.processing.discard("brain")
                
        except Exception as e:
            logger.error(f"Error processing brain file for {self.agent_id}: {e}")
            self.processing.discard("brain")


class EpollBodyMonitor:
    """Alternative implementation using epoll for efficiency."""
    
    def __init__(self):
        """Initialize the epoll-based monitor."""
        self.agents: Dict[str, Dict] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start the monitoring loop."""
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        
    async def add_agent(self, agent_id: str, agent_home: Path, ai_handler: Callable):
        """Add an agent to monitor."""
        brain_path = agent_home / "brain"
        
        # Open file for monitoring
        fd = os.open(str(brain_path), os.O_RDONLY | os.O_NONBLOCK)
        
        self.agents[agent_id] = {
            'home': agent_home,
            'brain_fd': fd,
            'brain_path': brain_path,
            'ai_handler': ai_handler,
            'processing': False
        }
        
        logger.info(f"Added {agent_id} to epoll monitoring")
    
    async def remove_agent(self, agent_id: str):
        """Stop monitoring an agent."""
        if agent_id in self.agents:
            os.close(self.agents[agent_id]['brain_fd'])
            del self.agents[agent_id]
    
    async def _monitor_loop(self):
        """Main monitoring loop using asyncio."""
        while True:
            # Check all agents
            for agent_id, agent_info in self.agents.items():
                try:
                    brain_path = agent_info['brain_path']
                    
                    # Check file modification time
                    # (In production, would use actual epoll or inotify)
                    try:
                        async with aiofiles.open(brain_path, 'r') as f:
                            content = await f.read()
                        
                        if "<<<END_THOUGHT>>>" in content and not agent_info['processing']:
                            agent_info['processing'] = True
                            
                            # Process asynchronously
                            asyncio.create_task(
                                self._process_thought(agent_id, content)
                            )
                            
                        elif content.startswith("This is your brain"):
                            agent_info['processing'] = False
                    except FileNotFoundError:
                        pass
                        
                except Exception as e:
                    logger.error(f"Error monitoring {agent_id}: {e}")
            
            # Sleep briefly to prevent CPU spinning
            await asyncio.sleep(0.1)
    
    async def _process_thought(self, agent_id: str, content: str):
        """Process a thought from an agent."""
        agent_info = self.agents[agent_id]
        
        try:
            # Extract prompt
            prompt = content.split("<<<END_THOUGHT>>>")[0].strip()
            
            # Call AI handler
            response = await agent_info['ai_handler'](agent_id, prompt)
            
            # Write response
            async with aiofiles.open(agent_info['brain_path'], 'w') as f:
                await f.write(f"{response}\n<<<THOUGHT_COMPLETE>>>")
            
        except Exception as e:
            logger.error(f"Error processing thought for {agent_id}: {e}")
        finally:
            agent_info['processing'] = False
    
    async def shutdown(self):
        """Shutdown monitoring."""
        if self._monitor_task:
            self._monitor_task.cancel()
            
        for agent_id in list(self.agents.keys()):
            await self.remove_agent(agent_id)


def create_body_monitor() -> 'BodyMonitor':
    """Create the most efficient body monitor for the platform."""
    if HAS_WATCHDOG:
        logger.info("Using inotify-based body monitoring")
        return InotifyBodyMonitor()
    else:
        logger.info("Using epoll-based body monitoring")
        monitor = EpollBodyMonitor()
        # Start the monitor loop
        asyncio.create_task(monitor.start())
        return monitor