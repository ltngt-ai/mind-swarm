"""Monitor cyber cycles and emit WebSocket events.

This module monitors when cybers start new cycles by watching their
current.json files and emits WebSocket events for clients.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Optional
import aiofiles

from mind_swarm.utils.logging import logger


class CycleMonitor:
    """Monitors cyber cycles and emits events."""
    
    def __init__(self, subspace_root: Path, event_emitter=None):
        """Initialize the cycle monitor.
        
        Args:
            subspace_root: Root path to subspace directory
            event_emitter: Optional MonitoringEventEmitter for WebSocket events
        """
        self.subspace_root = Path(subspace_root)
        self.event_emitter = event_emitter
        self.cyber_cycles: Dict[str, int] = {}  # Track last known cycle per cyber
        self.monitor_task: Optional[asyncio.Task] = None
        self.running = False
        
    async def start(self):
        """Start monitoring cycles."""
        if self.running:
            return
            
        self.running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Started cycle monitoring")
        
    async def stop(self):
        """Stop monitoring cycles."""
        self.running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped cycle monitoring")
        
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                # Check all cyber directories
                cybers_dir = self.subspace_root / "cybers"
                if cybers_dir.exists():
                    for cyber_dir in cybers_dir.iterdir():
                        if cyber_dir.is_dir():
                            await self._check_cyber_cycle(cyber_dir.name)
                
                # Check every 2 seconds
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error in cycle monitor loop: {e}")
                await asyncio.sleep(5)
    
    async def _check_cyber_cycle(self, cyber_name: str):
        """Check if a cyber has started a new cycle.
        
        Args:
            cyber_name: Name of the cyber to check
        """
        try:
            current_file = self.subspace_root / "cybers" / cyber_name / ".internal" / "cycles" / "current.json"
            
            if current_file.exists():
                # Read current cycle info
                async with aiofiles.open(current_file, 'r') as f:
                    content = await f.read()
                    if content.strip():
                        data = json.loads(content)
                        current_cycle = data.get("cycle_number", 0)
                        
                        # Check if this is a new cycle
                        last_known = self.cyber_cycles.get(cyber_name, -1)
                        if current_cycle > last_known:
                            # New cycle detected!
                            self.cyber_cycles[cyber_name] = current_cycle
                            
                            # Emit WebSocket event if we have an emitter
                            if self.event_emitter and last_known != -1:  # Don't emit on first detection
                                await self.event_emitter.emit_cycle_started(cyber_name, current_cycle)
                                logger.debug(f"Detected cycle {current_cycle} started for {cyber_name}")
                            
        except (json.JSONDecodeError, FileNotFoundError, KeyError):
            # File might not exist yet or be in transition
            pass
        except Exception as e:
            logger.error(f"Error checking cycle for {cyber_name}: {e}")
    
    async def add_cyber(self, cyber_name: str):
        """Add a cyber to monitor.
        
        Args:
            cyber_name: Name of the cyber to monitor
        """
        # Initialize tracking for this cyber
        await self._check_cyber_cycle(cyber_name)
        logger.debug(f"Added cycle monitoring for {cyber_name}")
    
    async def remove_cyber(self, cyber_name: str):
        """Remove a cyber from monitoring.
        
        Args:
            cyber_name: Name of the cyber to stop monitoring
        """
        if cyber_name in self.cyber_cycles:
            del self.cyber_cycles[cyber_name]
            logger.debug(f"Removed cycle monitoring for {cyber_name}")


# Global instance
_cycle_monitor: Optional[CycleMonitor] = None


def get_cycle_monitor(subspace_root: Optional[Path] = None, event_emitter=None) -> CycleMonitor:
    """Get the global cycle monitor instance.
    
    Args:
        subspace_root: Root path to subspace (required on first call)
        event_emitter: Optional MonitoringEventEmitter for WebSocket events
        
    Returns:
        The global CycleMonitor instance
    """
    global _cycle_monitor
    if _cycle_monitor is None:
        if subspace_root is None:
            raise ValueError("subspace_root required for first initialization")
        _cycle_monitor = CycleMonitor(subspace_root, event_emitter)
    return _cycle_monitor