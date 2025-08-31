"""Biofeedback monitoring system for Cybers."""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import deque
from pathlib import Path

from mind_swarm.utils.logging import logger


@dataclass
class BiofeedbackState:
    """Biofeedback state for a Cyber."""
    cyber: str
    boredom: float  # 0 to 100, percentage
    tiredness: float  # 0 to 100, percentage
    duty: float  # 0 to 100, percentage
    restlessness: float  # 0 to 100, percentage
    memory_pressure: float  # 0 to 100, percentage
    cycle: Optional[int] = None
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class BiofeedbackMonitor:
    """Monitor and track biofeedback data for all Cybers."""
    
    def __init__(self, history_minutes: int = 30):
        """Initialize the biofeedback monitor.
        
        Args:
            history_minutes: How many minutes of history to keep
        """
        self.history_minutes = history_minutes
        self.cyber_states: Dict[str, BiofeedbackState] = {}
        self.cyber_history: Dict[str, deque] = {}
        self._lock = asyncio.Lock()
        self._update_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start the biofeedback monitoring."""
        if self._update_task is None:
            self._update_task = asyncio.create_task(self._update_loop())
            logger.info("Biofeedback monitor started")
    
    async def stop(self):
        """Stop the biofeedback monitoring."""
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
            self._update_task = None
            logger.info("Biofeedback monitor stopped")
    
    async def _update_loop(self):
        """Continuously update biofeedback data."""
        while True:
            try:
                await asyncio.sleep(2)  # Update every 2 seconds
                await self._update_all_cybers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in biofeedback update loop: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    async def _update_all_cybers(self):
        """Update biofeedback for all active cybers by reading their unified_state.json files."""
        from mind_swarm.server.schemas.events import make_event
        
        # Get subspace root
        subspace_root = Path(os.environ.get("SUBSPACE_ROOT", "../subspace"))
        cybers_dir = subspace_root / "cybers"
        
        logger.debug(f"Biofeedback monitor checking cybers_dir: {cybers_dir}")
        
        if not cybers_dir.exists():
            logger.warning(f"Cybers directory does not exist: {cybers_dir}")
            return
        
        # Get server reference for broadcasting
        server = None
        try:
            from mind_swarm.server.monitoring_events import get_event_emitter
            emitter = get_event_emitter()
            if emitter and emitter.server:
                server = emitter.server
        except Exception as e:
            logger.debug(f"Could not get server reference for biofeedback: {e}")
        
        async with self._lock:
            # Scan all cyber directories for unified state files
            for cyber_dir in cybers_dir.iterdir():
                if not cyber_dir.is_dir():
                    continue
                
                cyber_name = cyber_dir.name
                
                # Skip developer accounts
                if cyber_name.endswith('_dev'):
                    continue
                
                # Check for unified state file
                unified_state_file = cyber_dir / ".internal" / "memory" / "unified_state.json"
                if not unified_state_file.exists():
                    continue
                
                # Parse the unified state file
                old_state = self.cyber_states.get(cyber_name)
                new_state = await self._parse_unified_state(cyber_name, unified_state_file)
                
                if new_state:
                    self.cyber_states[cyber_name] = new_state
                    
                    # Add to history
                    if cyber_name not in self.cyber_history:
                        self.cyber_history[cyber_name] = deque(maxlen=self.history_minutes * 30)  # 2-second intervals
                    self.cyber_history[cyber_name].append(new_state)
                    
                    # Clean old history entries
                    cutoff_time = datetime.now() - timedelta(minutes=self.history_minutes)
                    while (self.cyber_history[cyber_name] and 
                           datetime.fromisoformat(self.cyber_history[cyber_name][0].timestamp) < cutoff_time):
                        self.cyber_history[cyber_name].popleft()
                    
                    # Emit WebSocket event if state changed or periodically
                    if server:
                        # Always emit biofeedback events every cycle to keep UI updated
                        should_emit = True
                        
                        if should_emit:
                            try:
                                event = make_event("biofeedback", {
                                    "cyber": new_state.cyber,
                                    "boredom": float(new_state.boredom) if new_state.boredom is not None else 0,
                                    "tiredness": float(new_state.tiredness) if new_state.tiredness is not None else 0,
                                    "duty": float(new_state.duty) if new_state.duty is not None else 0,
                                    "restlessness": float(new_state.restlessness) if new_state.restlessness is not None else 0,
                                    "memory_pressure": float(new_state.memory_pressure) if new_state.memory_pressure is not None else 0,
                                    "cycle": new_state.cycle,
                                    "timestamp": new_state.timestamp
                                })
                                await server._broadcast_event(event)
                                logger.debug(f"Emitted biofeedback event for {cyber_name}: boredom={new_state.boredom}, tiredness={new_state.tiredness}, duty={new_state.duty}, restlessness={new_state.restlessness}, memory={new_state.memory_pressure}")
                            except Exception as e:
                                logger.debug(f"Could not emit biofeedback event: {e}")
    
    async def _parse_unified_state(self, cyber_name: str, unified_state_file: Path) -> Optional[BiofeedbackState]:
        """Parse a cyber's unified state file to extract biofeedback data."""
        try:
            with open(unified_state_file, 'r') as f:
                data = json.load(f)
            
            # Extract biofeedback values from the unified state
            biofeedback = data.get('biofeedback', {})
            cognitive = data.get('cognitive', {})
            
            boredom = float(biofeedback.get('boredom', 0))
            tiredness = float(biofeedback.get('tiredness', 0))
            duty = float(biofeedback.get('duty', 0))
            restlessness = float(biofeedback.get('restlessness', 0))
            memory_pressure = float(biofeedback.get('memory_pressure', 0))
            cycle = cognitive.get('cycle_count', None)
            
            return BiofeedbackState(
                cyber=cyber_name,
                boredom=boredom,
                tiredness=tiredness,
                duty=duty,
                restlessness=restlessness,
                memory_pressure=memory_pressure,
                cycle=cycle
            )
            
        except Exception as e:
            logger.debug(f"Error parsing unified state for {cyber_name}: {e}")
            return None
    
    async def get_current_state(self, cyber_name: str) -> Optional[BiofeedbackState]:
        """Get current biofeedback state for a cyber."""
        async with self._lock:
            return self.cyber_states.get(cyber_name)
    
    async def get_history(self, cyber_name: str, minutes: int = 15) -> List[BiofeedbackState]:
        """Get biofeedback history for a cyber."""
        async with self._lock:
            if cyber_name not in self.cyber_history:
                return []
            
            # Filter by time window
            cutoff_time = datetime.now() - timedelta(minutes=minutes)
            history = []
            for state in self.cyber_history[cyber_name]:
                if datetime.fromisoformat(state.timestamp) >= cutoff_time:
                    history.append(state)
            
            return history
    
    async def get_all_current_states(self) -> Dict[str, BiofeedbackState]:
        """Get current biofeedback states for all cybers."""
        async with self._lock:
            return dict(self.cyber_states)


# Global biofeedback monitor instance
_biofeedback_monitor: Optional[BiofeedbackMonitor] = None


def get_biofeedback_monitor() -> BiofeedbackMonitor:
    """Get the global biofeedback monitor instance."""
    global _biofeedback_monitor
    if _biofeedback_monitor is None:
        _biofeedback_monitor = BiofeedbackMonitor()
    return _biofeedback_monitor