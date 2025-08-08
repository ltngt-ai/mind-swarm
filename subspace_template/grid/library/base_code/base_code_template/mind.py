"""Cyber Mind - The main class that coordinates all cognitive components.

This is the primary class that:
- Manages the cognitive loop
- Maintains Cyber state
- Handles lifecycle (startup, running, shutdown)
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
from .cognitive_loop import CognitiveLoop

logger = logging.getLogger("Cyber.mind")


class CyberMind:
    """The complete Cyber mind - coordinates all cognitive functions."""
    
    def __init__(self):
        """Initialize the Cyber mind."""
        # Set up paths
        self.personal = Path("/personal")
        self.grid = Path("/grid")
        
        # Load identity from file or fall back to environment
        self.identity = self._load_identity()
        self.name = self.identity.get("name", os.environ.get("CYBER_NAME", "unknown"))
        self.cyber_type = self.identity.get("cyber_type", os.environ.get("CYBER_TYPE", "general"))
        self.model = self.identity.get("model", "unknown")
        self.max_context_length = self.identity.get("max_context_length", 4096)
        
        # Load configuration if it exists
        self.config = self._load_config()
        
        # Initialize cognitive components
        self.cognitive_loop = CognitiveLoop(
            self.name, 
            self.personal, 
            max_context_tokens=self.max_context_length,
            cyber_type=self.cyber_type
        )
        
        # State
        self.running = False
        self.stop_requested = False
        self.start_time = datetime.now()
        self.state = "INITIALIZING"
        
        # Log startup
        logger.info(f"Cyber mind initializing: {self.name}")
        logger.info(f"  Model: {self.model}, Context: {self.max_context_length}")
    
    def request_stop(self):
        """Request a graceful stop after the current cycle."""
        self.stop_requested = True
        logger.info("Stop requested - will exit after current cycle completes")
    
    def _load_identity(self) -> dict:
        """Load Cyber identity from file."""
        identity_file = self.personal / "identity.json"
        if identity_file.exists():
            try:
                return json.loads(identity_file.read_text())
            except Exception as e:
                logger.error(f"Error loading identity: {e}")
        
        # Default identity from environment
        return {
            "name": os.environ.get("CYBER_NAME", "unknown"),
            "cyber_type": os.environ.get("CYBER_TYPE", "general"),
            "model": "unknown",
            "max_context_length": 4096,
            "provider": "unknown",
            "created_at": datetime.now().isoformat()
        }
    
    def _load_config(self) -> dict:
        """Load Cyber configuration from file."""
        config_file = self.personal / "config.json"
        if config_file.exists():
            try:
                return json.loads(config_file.read_text())
            except Exception as e:
                logger.error(f"Error loading config: {e}")
        
        # Default config
        return {
            "name": self.name,
            "type": self.cyber_type
        }
    
    async def run(self):
        """Main Cyber execution loop."""
        logger.info(f"Cyber {self.name} starting main loop")
        self.running = True
        self.state = "RUNNING"
        
        # Start heartbeat task
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        # Start status task
        status_task = asyncio.create_task(self._update_status_loop())
        
        # Start shutdown monitor task
        shutdown_task = asyncio.create_task(self._shutdown_monitor_loop())
        
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
            shutdown_task.cancel()
            
            try:
                await heartbeat_task
                await status_task
                await shutdown_task
            except asyncio.CancelledError:
                pass
            
            logger.info(f"Cyber {self.name} shutting down")
    
    async def _heartbeat_loop(self):
        """Maintain heartbeat file for monitoring."""
        heartbeat_file = self.personal / "heartbeat.json"
        
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
        status_file = self.personal / "status.json"
        
        while self.running:
            try:
                # Get memory system summary
                wm_summary = self.cognitive_loop.memory_system.get_memory_stats()
                
                status = {
                    "name": self.name,
                    "type": self.cyber_type,
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
    
    async def _shutdown_monitor_loop(self):
        """Monitor for shutdown signal from coordinator."""
        shutdown_file = self.personal / "shutdown"
        
        while self.running:
            try:
                if shutdown_file.exists():
                    logger.info("Shutdown file detected, initiating graceful shutdown...")
                    self.stop_requested = True
                    self.running = False
                    break
                    
            except Exception as e:
                logger.error(f"Error checking shutdown file: {e}")
            
            await asyncio.sleep(0.5)  # Check every 0.5 seconds
    
    async def _autonomous_action(self):
        """Take autonomous action when idle."""
        # For now, just log that we could explore
        logger.debug("Cyber is idle - could explore the Grid or review memory")
        
        # In future: 
        # - Check Plaza for unanswered questions
        # - Review and organize memory
        # - Explore Grid areas
        # - Practice skills
        
        # Update state
        self.state = "EXPLORING"
        await asyncio.sleep(2)
        self.state = "IDLE"