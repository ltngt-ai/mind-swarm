"""Agent Mind - The main class that coordinates all cognitive components.

This is the primary class that:
- Manages the cognitive loop
- Maintains agent state
- Handles lifecycle (startup, running, shutdown)
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from .boot_rom import BootROM

from .cognitive_loop import CognitiveLoop

logger = logging.getLogger("agent.mind")


class AgentMind:
    """The complete agent mind - coordinates all cognitive functions."""
    
    def __init__(self):
        """Initialize the agent mind."""
        # Get identity from environment
        self.name = os.environ.get("AGENT_NAME", "unknown")
        self.agent_type = os.environ.get("AGENT_TYPE", "general")
        
        # Set up paths
        self.home = Path("/home")
        self.grid = Path("/grid")
        
        # Load configuration if it exists
        self.config = self._load_config()
        
        # Initialize cognitive components
        self.boot_rom = BootROM()
        self.cognitive_loop = CognitiveLoop(self.name, self.home)
        
        # State
        self.running = False
        self.stop_requested = False
        self.start_time = datetime.now()
        self.state = "INITIALIZING"
        
        # Log startup
        logger.info(f"Agent mind initializing: {self.name}")
        for line in self.boot_rom.get_boot_sequence():
            logger.info(f"  {line}")
    
    def request_stop(self):
        """Request a graceful stop after the current cycle."""
        self.stop_requested = True
        logger.info("Stop requested - will exit after current cycle completes")
    
    def _load_config(self) -> dict:
        """Load agent configuration from file."""
        config_file = self.home / "config.json"
        if config_file.exists():
            try:
                return json.loads(config_file.read_text())
            except Exception as e:
                logger.error(f"Error loading config: {e}")
        
        # Default config
        return {
            "name": self.name,
            "type": self.agent_type
        }
    
    async def run(self):
        """Main agent execution loop."""
        logger.info(f"Agent {self.name} starting main loop")
        self.running = True
        self.state = "RUNNING"
        
        # Start heartbeat task
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        # Start status task
        status_task = asyncio.create_task(self._update_status_loop())
        
        try:
            # Main cognitive loop
            idle_cycles = 0
            
            while self.running and not self.stop_requested:
                # Run one cognitive cycle
                was_active = await self.cognitive_loop.run_cycle()
                
                # Check if stop was requested
                if self.stop_requested:
                    logger.info("Graceful stop requested, saving state and exiting...")
                    await self.cognitive_loop.save_memory()
                    break
                
                if was_active:
                    idle_cycles = 0
                    self.state = "THINKING"
                else:
                    idle_cycles += 1
                    self.state = "IDLE"
                    
                    # After being idle for a while, maybe explore
                    if idle_cycles > 10:  # About 5 seconds
                        await self._autonomous_action()
                        idle_cycles = 0
                
                # Brief pause between cycles
                await asyncio.sleep(0.5)
                
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
            self.state = "ERROR"
            
        finally:
            # Clean shutdown
            self.running = False
            heartbeat_task.cancel()
            status_task.cancel()
            
            try:
                await heartbeat_task
                await status_task
            except asyncio.CancelledError:
                pass
            
            logger.info(f"Agent {self.name} shutting down")
    
    async def _heartbeat_loop(self):
        """Maintain heartbeat file for monitoring."""
        heartbeat_file = self.home / "heartbeat.json"
        
        while self.running:
            try:
                heartbeat = {
                    "name": self.name,
                    "state": self.state,
                    "timestamp": datetime.now().isoformat(),
                    "uptime": (datetime.now() - self.start_time).total_seconds(),
                    "pid": os.getpid(),
                    "cycle_count": self.cognitive_loop.cycle_count,
                    "last_activity": self.cognitive_loop.last_activity.isoformat()
                }
                
                heartbeat_file.write_text(json.dumps(heartbeat, indent=2))
                
            except Exception as e:
                logger.error(f"Error updating heartbeat: {e}")
            
            await asyncio.sleep(5)
    
    async def _update_status_loop(self):
        """Update detailed status periodically."""
        status_file = self.home / "status.json"
        
        while self.running:
            try:
                # Get memory system summary
                wm_summary = self.cognitive_loop.memory_manager.get_memory_stats()
                
                status = {
                    "name": self.name,
                    "type": self.agent_type,
                    "state": self.state,
                    "timestamp": datetime.now().isoformat(),
                    "uptime": (datetime.now() - self.start_time).total_seconds(),
                    "cognitive": {
                        "cycle_count": self.cognitive_loop.cycle_count,
                        "working_memory": wm_summary
                    },
                    "config": self.config
                }
                
                status_file.write_text(json.dumps(status, indent=2))
                
            except Exception as e:
                logger.error(f"Error updating status: {e}")
            
            await asyncio.sleep(30)  # Update every 30 seconds
    
    async def _autonomous_action(self):
        """Take autonomous action when idle."""
        # For now, just log that we could explore
        logger.debug("Agent is idle - could explore the Grid or review memory")
        
        # In future: 
        # - Check Plaza for unanswered questions
        # - Review and organize memory
        # - Explore Grid areas
        # - Practice skills
        
        # Update state
        self.state = "EXPLORING"
        await asyncio.sleep(2)
        self.state = "IDLE"