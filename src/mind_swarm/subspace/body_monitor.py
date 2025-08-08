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
        
    async def add_agent(self, cyber_id: str, cyber_personal: Path, ai_handler: Callable):
        """Add an Cyber to monitor.
        
        Args:
            cyber_id: Cyber's unique identifier
            cyber_personal: Path to Cyber's home directory
            ai_handler: Async function to handle AI requests
        """
        if not HAS_WATCHDOG:
            logger.warning("Watchdog not available, falling back to polling")
            return
            
        # Create handler for this Cyber
        handler = BodyFileHandler(cyber_id, cyber_personal, ai_handler, self.loop)
        self.handlers[cyber_id] = handler
        
        # Create observer for the Cyber's home directory
        observer = Observer()
        observer.schedule(handler, str(cyber_personal), recursive=False)
        observer.start()
        
        self.observers[cyber_id] = observer
        logger.info(f"Started inotify monitoring for {cyber_id}")
    
    async def remove_agent(self, cyber_id: str):
        """Stop monitoring an Cyber.
        
        Args:
            cyber_id: Cyber's unique identifier
        """
        if cyber_id in self.observers:
            self.observers[cyber_id].stop()
            self.observers[cyber_id].join(timeout=1)
            del self.observers[cyber_id]
            del self.handlers[cyber_id]
            logger.info(f"Stopped inotify monitoring for {cyber_id}")
    
    async def shutdown(self):
        """Shutdown all monitoring."""
        for cyber_id in list(self.observers.keys()):
            await self.remove_agent(cyber_id)


class BodyFileHandler(FileSystemEventHandler):
    """Handles file system events for body files."""
    
    def __init__(self, cyber_id: str, cyber_personal: Path, ai_handler: Callable, loop):
        """Initialize the handler.
        
        Args:
            cyber_id: Cyber's unique identifier
            cyber_personal: Path to Cyber's home directory
            ai_handler: Async function to handle AI requests
            loop: Event loop for async operations
        """
        self.cyber_id = cyber_id
        self.cyber_personal = cyber_personal
        self.ai_handler = ai_handler
        self.loop = loop
        self.processing: Set[str] = set()
        
    def on_modified(self, event):
        """Handle file modification events."""
        if isinstance(event, FileModifiedEvent) and not event.is_directory:
            file_path = Path(event.src_path)
            
            # Only care about body files
            if file_path.name == "brain" and file_path.parent == self.cyber_personal:
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
                logger.debug(f"Brain activated by {self.cyber_id}: {prompt[:50]}...")
                
                # Process the thought
                response = await self.ai_handler(self.cyber_id, prompt)
                
                # Write response with completion marker
                async with aiofiles.open(file_path, 'w') as f:
                    await f.write(f"{response}\n<<<THOUGHT_COMPLETE>>>")
                
            elif content.startswith("This is your brain"):
                # File was reset, ready for next thought
                self.processing.discard("brain")
                
        except Exception as e:
            logger.error(f"Error processing brain file for {self.cyber_id}: {e}")
            self.processing.discard("brain")


class EpollBodyMonitor:
    """Alternative implementation using epoll for efficiency."""
    
    def __init__(self):
        """Initialize the epoll-based monitor."""
        self.cybers: Dict[str, Dict] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start the monitoring loop."""
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        
    async def add_agent(self, cyber_id: str, cyber_personal: Path, ai_handler: Callable):
        """Add an Cyber to monitor."""
        brain_path = cyber_personal / "brain"
        
        # Open file for monitoring
        fd = os.open(str(brain_path), os.O_RDONLY | os.O_NONBLOCK)
        
        self.cybers[cyber_id] = {
            'home': cyber_personal,
            'brain_fd': fd,
            'brain_path': brain_path,
            'ai_handler': ai_handler,
            'processing': False
        }
        
        logger.info(f"Added {cyber_id} to epoll monitoring")
    
    async def remove_agent(self, cyber_id: str):
        """Stop monitoring an Cyber."""
        if cyber_id in self.cybers:
            os.close(self.cybers[cyber_id]['brain_fd'])
            del self.cybers[cyber_id]
    
    async def _monitor_loop(self):
        """Main monitoring loop using asyncio."""
        while True:
            # Check all Cybers
            for cyber_id, cyber_info in self.cybers.items():
                try:
                    brain_path = cyber_info['brain_path']
                    
                    # Check file modification time
                    # (In production, would use actual epoll or inotify)
                    try:
                        async with aiofiles.open(brain_path, 'r') as f:
                            content = await f.read()
                        
                        if "<<<END_THOUGHT>>>" in content and not cyber_info['processing']:
                            cyber_info['processing'] = True
                            
                            # Process asynchronously
                            asyncio.create_task(
                                self._process_thought(cyber_id, content)
                            )
                            
                        elif content.startswith("This is your brain"):
                            cyber_info['processing'] = False
                    except FileNotFoundError:
                        pass
                        
                except Exception as e:
                    logger.error(f"Error monitoring {cyber_id}: {e}")
            
            # Sleep briefly to prevent CPU spinning
            await asyncio.sleep(0.1)
    
    async def _process_thought(self, cyber_id: str, content: str):
        """Process a thought from an Cyber."""
        cyber_info = self.cybers[cyber_id]
        
        try:
            # Extract prompt
            prompt = content.split("<<<END_THOUGHT>>>")[0].strip()
            
            # Call AI handler
            response = await cyber_info['ai_handler'](cyber_id, prompt)
            
            # Write response
            async with aiofiles.open(cyber_info['brain_path'], 'w') as f:
                await f.write(f"{response}\n<<<THOUGHT_COMPLETE>>>")
            
        except Exception as e:
            logger.error(f"Error processing thought for {cyber_id}: {e}")
        finally:
            cyber_info['processing'] = False
    
    async def shutdown(self):
        """Shutdown monitoring."""
        if self._monitor_task:
            self._monitor_task.cancel()
            
        for cyber_id in list(self.cybers.keys()):
            await self.remove_agent(cyber_id)


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