"""Cycle-based recording system for cyber activity.

This module provides per-cyber, cycle-based storage of all cyber activities,
replacing the monolithic log file approach with structured, queryable data.
"""

import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict, field
from collections import deque
import aiofiles
from asyncio import Lock

from mind_swarm.utils.logging import logger


@dataclass
class CycleMetadata:
    """Metadata for a single cognitive cycle."""
    cycle_number: int
    start_time: str
    end_time: Optional[str] = None
    duration_ms: Optional[int] = None
    stages_completed: List[str] = field(default_factory=list)
    token_usage: Dict[str, int] = field(default_factory=dict)
    status: str = "in_progress"  # in_progress, completed, failed
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass 
class StageData:
    """Data for a single cognitive stage."""
    stage: str  # observation, decision, execution, reflection, cleanup
    start_time: str
    end_time: Optional[str] = None
    duration_ms: Optional[int] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    brain_requests: List[Dict[str, Any]] = field(default_factory=list)
    working_memory: Dict[str, Any] = field(default_factory=dict)  # Memory context at stage start
    llm_input: Dict[str, Any] = field(default_factory=dict)  # Full LLM prompt/context
    llm_output: Dict[str, Any] = field(default_factory=dict)  # Raw LLM response
    errors: List[str] = field(default_factory=list)
    token_usage: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class CycleRecorder:
    """Records and manages per-cyber, cycle-based activity data."""
    
    def __init__(self, subspace_root: Path, max_cycles_per_cyber: int = 100):
        """Initialize the cycle recorder.
        
        Args:
            subspace_root: Root path to subspace directory
            max_cycles_per_cyber: Maximum cycles to keep per cyber (older deleted)
        """
        self.subspace_root = Path(subspace_root)
        self.max_cycles = max_cycles_per_cyber
        self.active_cycles: Dict[str, CycleMetadata] = {}
        self.active_stages: Dict[str, StageData] = {}
        self.cycle_locks: Dict[str, Lock] = {}
        self.logger = logger
        
    def _get_cyber_cycles_dir(self, cyber_name: str) -> Path:
        """Get the cycles directory for a cyber."""
        return self.subspace_root / "cybers" / cyber_name / ".internal" / "cycles"
    
    def _get_cycle_dir(self, cyber_name: str, cycle_number: int) -> Path:
        """Get directory for a specific cycle."""
        return self._get_cyber_cycles_dir(cyber_name) / f"cycle_{cycle_number:06d}"
    
    async def start_cycle(self, cyber_name: str, cycle_number: int) -> None:
        """Start recording a new cycle.
        
        Args:
            cyber_name: Name of the cyber
            cycle_number: The cycle number
        """
        try:
            # Ensure cycles directory exists
            cycles_dir = self._get_cyber_cycles_dir(cyber_name)
            cycles_dir.mkdir(parents=True, exist_ok=True)
            
            # Create cycle directory
            cycle_dir = self._get_cycle_dir(cyber_name, cycle_number)
            cycle_dir.mkdir(exist_ok=True)
            
            # Initialize cycle metadata
            metadata = CycleMetadata(
                cycle_number=cycle_number,
                start_time=datetime.now().isoformat()
            )
            
            # Store in active cycles
            cycle_key = f"{cyber_name}:{cycle_number}"
            self.active_cycles[cycle_key] = metadata
            
            if cyber_name not in self.cycle_locks:
                self.cycle_locks[cyber_name] = Lock()
            
            # Write initial metadata
            await self._write_json(
                cycle_dir / "metadata.json",
                metadata.to_dict()
            )
            
            # Update current cycle pointer
            await self._write_json(
                cycles_dir / "current.json",
                {"cycle_number": cycle_number, "path": str(cycle_dir.relative_to(self.subspace_root))}
            )
            
            # Update index
            await self._update_index(cyber_name, cycle_number, "started")
            
            # Cleanup old cycles if needed
            await self._cleanup_old_cycles(cyber_name)
            
            self.logger.debug(f"Started recording cycle {cycle_number} for {cyber_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to start cycle recording for {cyber_name}: {e}")
    
    async def end_cycle(self, cyber_name: str, cycle_number: int, status: str = "completed") -> None:
        """End recording a cycle.
        
        Args:
            cyber_name: Name of the cyber
            cycle_number: The cycle number
            status: Final status (completed, failed)
        """
        try:
            cycle_key = f"{cyber_name}:{cycle_number}"
            metadata = self.active_cycles.get(cycle_key)
            
            if not metadata:
                self.logger.warning(f"No active cycle {cycle_number} for {cyber_name}")
                return
            
            # Update metadata
            metadata.end_time = datetime.now().isoformat()
            start = datetime.fromisoformat(metadata.start_time)
            end = datetime.fromisoformat(metadata.end_time)
            metadata.duration_ms = int((end - start).total_seconds() * 1000)
            metadata.status = status
            
            # Write final metadata
            cycle_dir = self._get_cycle_dir(cyber_name, cycle_number)
            await self._write_json(
                cycle_dir / "metadata.json",
                metadata.to_dict()
            )
            
            # Update index
            await self._update_index(cyber_name, cycle_number, status)
            
            # Remove from active cycles
            del self.active_cycles[cycle_key]
            
            self.logger.debug(f"Ended cycle {cycle_number} for {cyber_name} with status {status}")
            
        except Exception as e:
            self.logger.error(f"Failed to end cycle recording for {cyber_name}: {e}")
    
    async def record_stage(self, cyber_name: str, cycle_number: int, stage_name: str,
                          stage_data: Dict[str, Any]) -> None:
        """Record data for a cognitive stage.
        
        Args:
            cyber_name: Name of the cyber
            cycle_number: The cycle number
            stage_name: Name of the stage (observation, decision, etc.)
            stage_data: Data from the stage
        """
        try:
            cycle_dir = self._get_cycle_dir(cyber_name, cycle_number)
            if not cycle_dir.exists():
                await self.start_cycle(cyber_name, cycle_number)
                cycle_dir = self._get_cycle_dir(cyber_name, cycle_number)
            
            # Create stage data
            stage = StageData(
                stage=stage_name,
                start_time=stage_data.get("start_time", datetime.now().isoformat()),
                end_time=stage_data.get("end_time"),
                duration_ms=stage_data.get("duration_ms"),
                input_data=stage_data.get("input", {}),
                output_data=stage_data.get("output", {}),
                brain_requests=stage_data.get("brain_requests", []),
                working_memory=stage_data.get("working_memory", {}),
                llm_input=stage_data.get("llm_input", {}),
                llm_output=stage_data.get("llm_output", {}),
                errors=stage_data.get("errors", []),
                token_usage=stage_data.get("token_usage", {})
            )
            
            # Write stage data
            await self._write_json(
                cycle_dir / f"{stage_name}.json",
                stage.to_dict()
            )
            
            # Update cycle metadata
            cycle_key = f"{cyber_name}:{cycle_number}"
            if cycle_key in self.active_cycles:
                metadata = self.active_cycles[cycle_key]
                if stage_name not in metadata.stages_completed:
                    metadata.stages_completed.append(stage_name)
                
                # Aggregate token usage
                for key, value in stage.token_usage.items():
                    metadata.token_usage[key] = metadata.token_usage.get(key, 0) + value
                
                # Write updated metadata
                await self._write_json(
                    cycle_dir / "metadata.json",
                    metadata.to_dict()
                )
            
            self.logger.debug(f"Recorded {stage_name} stage for {cyber_name} cycle {cycle_number}")
            
        except Exception as e:
            self.logger.error(f"Failed to record stage {stage_name} for {cyber_name}: {e}")
    
    async def record_reflection(self, cyber_name: str, cycle_number: int, 
                               reflection_data: Dict[str, Any]) -> None:
        """Record reflection data for a cycle.
        
        This is typically the reflection_from_last_cycle that gets used
        in the next cycle's observation stage.
        
        Args:
            cyber_name: Name of the cyber
            cycle_number: The cycle number this reflection is FROM
            reflection_data: The reflection data
        """
        try:
            cycle_dir = self._get_cycle_dir(cyber_name, cycle_number)
            if not cycle_dir.exists():
                # Reflection might come after cycle ends, so create dir if needed
                cycle_dir.mkdir(parents=True, exist_ok=True)
            
            # Write reflection data
            await self._write_json(
                cycle_dir / "reflection_from_last_cycle.json",
                reflection_data
            )
            
            # Also store as regular reflection stage if not already there
            reflection_stage_file = cycle_dir / "reflection.json"
            if not reflection_stage_file.exists():
                await self.record_stage(
                    cyber_name, cycle_number, "reflection",
                    {"output": reflection_data}
                )
            
            self.logger.debug(f"Recorded reflection for {cyber_name} cycle {cycle_number}")
            
        except Exception as e:
            self.logger.error(f"Failed to record reflection for {cyber_name}: {e}")
    
    async def record_brain_request(self, cyber_name: str, cycle_number: int,
                                  request: Dict[str, Any], response: Optional[Dict[str, Any]] = None) -> None:
        """Record a brain request/response pair.
        
        Args:
            cyber_name: Name of the cyber
            cycle_number: The cycle number  
            request: The brain request data
            response: The brain response data (if available)
        """
        try:
            cycle_dir = self._get_cycle_dir(cyber_name, cycle_number)
            if not cycle_dir.exists():
                await self.start_cycle(cyber_name, cycle_number)
                cycle_dir = self._get_cycle_dir(cyber_name, cycle_number)
            
            # Load existing brain requests
            brain_file = cycle_dir / "brain_requests.json"
            if brain_file.exists():
                async with aiofiles.open(brain_file, 'r') as f:
                    brain_requests = json.loads(await f.read())
            else:
                brain_requests = []
            
            # Add new request/response
            brain_entry = {
                "timestamp": datetime.now().isoformat(),
                "request": request,
                "response": response
            }
            brain_requests.append(brain_entry)
            
            # Write back
            await self._write_json(brain_file, brain_requests)
            
        except Exception as e:
            self.logger.error(f"Failed to record brain request for {cyber_name}: {e}")
    
    async def record_message(self, cyber_name: str, cycle_number: int,
                           message_type: str, message: Dict[str, Any]) -> None:
        """Record a message sent or received.
        
        Args:
            cyber_name: Name of the cyber
            cycle_number: The cycle number
            message_type: "sent" or "received"
            message: The message data
        """
        try:
            cycle_dir = self._get_cycle_dir(cyber_name, cycle_number)
            if not cycle_dir.exists():
                await self.start_cycle(cyber_name, cycle_number)
                cycle_dir = self._get_cycle_dir(cyber_name, cycle_number)
            
            # Load existing messages
            messages_file = cycle_dir / "messages.json"
            if messages_file.exists():
                async with aiofiles.open(messages_file, 'r') as f:
                    messages = json.loads(await f.read())
            else:
                messages = {"sent": [], "received": []}
            
            # Add new message
            message_entry = {
                "timestamp": datetime.now().isoformat(),
                **message
            }
            messages[message_type].append(message_entry)
            
            # Write back
            await self._write_json(messages_file, messages)
            
        except Exception as e:
            self.logger.error(f"Failed to record message for {cyber_name}: {e}")
    
    async def record_file_operation(self, cyber_name: str, cycle_number: int,
                                   operation: str, path: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Record a filesystem operation.
        
        Args:
            cyber_name: Name of the cyber
            cycle_number: The cycle number
            operation: Type of operation (read, write, create, delete)
            path: File path
            details: Additional details about the operation
        """
        try:
            cycle_dir = self._get_cycle_dir(cyber_name, cycle_number)
            if not cycle_dir.exists():
                await self.start_cycle(cyber_name, cycle_number)
                cycle_dir = self._get_cycle_dir(cyber_name, cycle_number)
            
            # Load existing filesystem operations
            fs_file = cycle_dir / "filesystem.json"
            if fs_file.exists():
                async with aiofiles.open(fs_file, 'r') as f:
                    fs_ops = json.loads(await f.read())
            else:
                fs_ops = []
            
            # Add new operation
            fs_entry = {
                "timestamp": datetime.now().isoformat(),
                "operation": operation,
                "path": path,
                "details": details or {}
            }
            fs_ops.append(fs_entry)
            
            # Write back
            await self._write_json(fs_file, fs_ops)
            
        except Exception as e:
            self.logger.error(f"Failed to record file operation for {cyber_name}: {e}")
    
    async def get_cycle_data(self, cyber_name: str, cycle_number: int) -> Optional[Dict[str, Any]]:
        """Get all data for a specific cycle.
        
        Args:
            cyber_name: Name of the cyber
            cycle_number: The cycle number
            
        Returns:
            Dictionary containing all cycle data or None if not found
        """
        try:
            cycle_dir = self._get_cycle_dir(cyber_name, cycle_number)
            if not cycle_dir.exists():
                return None
            
            result = {}
            
            # Load all JSON files in the cycle directory
            for json_file in cycle_dir.glob("*.json"):
                async with aiofiles.open(json_file, 'r') as f:
                    data = json.loads(await f.read())
                    result[json_file.stem] = data
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to get cycle data for {cyber_name}: {e}")
            return None
    
    async def get_stage_data(self, cyber_name: str, cycle_number: int, stage: str) -> Optional[Dict[str, Any]]:
        """Get data for a specific stage in a cycle.
        
        Args:
            cyber_name: Name of the cyber
            cycle_number: The cycle number
            stage: Stage name
            
        Returns:
            Stage data or None if not found
        """
        try:
            cycle_dir = self._get_cycle_dir(cyber_name, cycle_number)
            stage_file = cycle_dir / f"{stage}.json"
            
            if not stage_file.exists():
                return None
            
            async with aiofiles.open(stage_file, 'r') as f:
                return json.loads(await f.read())
                
        except Exception as e:
            self.logger.error(f"Failed to get stage data for {cyber_name}: {e}")
            return None
    
    async def get_cycle_range(self, cyber_name: str, from_cycle: int, to_cycle: int) -> List[Dict[str, Any]]:
        """Get data for a range of cycles.
        
        Args:
            cyber_name: Name of the cyber
            from_cycle: Starting cycle number (inclusive)
            to_cycle: Ending cycle number (inclusive)
            
        Returns:
            List of cycle data dictionaries
        """
        results = []
        for cycle_num in range(from_cycle, to_cycle + 1):
            cycle_data = await self.get_cycle_data(cyber_name, cycle_num)
            if cycle_data:
                results.append(cycle_data)
        return results
    
    async def get_current_cycle(self, cyber_name: str) -> Optional[Dict[str, Any]]:
        """Get the current cycle data for a cyber.
        
        Args:
            cyber_name: Name of the cyber
            
        Returns:
            Current cycle data or None
        """
        try:
            cycles_dir = self._get_cyber_cycles_dir(cyber_name)
            current_file = cycles_dir / "current.json"
            
            if not current_file.exists():
                return None
            
            async with aiofiles.open(current_file, 'r') as f:
                current_info = json.loads(await f.read())
            
            return await self.get_cycle_data(cyber_name, current_info["cycle_number"])
            
        except Exception as e:
            self.logger.error(f"Failed to get current cycle for {cyber_name}: {e}")
            return None
    
    async def list_cycles(self, cyber_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """List available cycles for a cyber.
        
        Args:
            cyber_name: Name of the cyber
            limit: Maximum number of cycles to return
            
        Returns:
            List of cycle metadata
        """
        try:
            cycles_dir = self._get_cyber_cycles_dir(cyber_name)
            index_file = cycles_dir / "index.json"
            
            if not index_file.exists():
                return []
            
            async with aiofiles.open(index_file, 'r') as f:
                index = json.loads(await f.read())
            
            # Return most recent cycles up to limit
            cycles = index.get("cycles", [])
            return cycles[-limit:] if len(cycles) > limit else cycles
            
        except Exception as e:
            self.logger.error(f"Failed to list cycles for {cyber_name}: {e}")
            return []
    
    async def _write_json(self, path: Path, data: Any) -> None:
        """Write JSON data to a file asynchronously."""
        async with aiofiles.open(path, 'w') as f:
            await f.write(json.dumps(data, indent=2))
    
    async def _update_index(self, cyber_name: str, cycle_number: int, status: str) -> None:
        """Update the cycle index for a cyber."""
        try:
            cycles_dir = self._get_cyber_cycles_dir(cyber_name)
            index_file = cycles_dir / "index.json"
            
            # Use a lock to prevent concurrent writes
            async with self.cycle_locks.get(cyber_name, Lock()):
                # Load existing index with error recovery
                index = {"cycles": []}
                if index_file.exists():
                    try:
                        async with aiofiles.open(index_file, 'r') as f:
                            content = await f.read()
                            if content.strip():  # Only parse if not empty
                                index = json.loads(content)
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"Corrupted index for {cyber_name}, recreating: {e}")
                        # Try to salvage what we can by reading cycle directories
                        index = await self._rebuild_index(cyber_name)
                
                # Find or add cycle entry
                cycle_entry = None
                for entry in index["cycles"]:
                    if entry["cycle_number"] == cycle_number:
                        cycle_entry = entry
                        break
                
                if not cycle_entry:
                    cycle_entry = {
                        "cycle_number": cycle_number,
                        "timestamp": datetime.now().isoformat()
                    }
                    index["cycles"].append(cycle_entry)
                
                cycle_entry["status"] = status
                cycle_entry["last_updated"] = datetime.now().isoformat()
                
                # Sort by cycle number and limit size
                index["cycles"].sort(key=lambda x: x["cycle_number"])
                
                # Keep only last 500 cycles in index (older ones still exist on disk)
                if len(index["cycles"]) > 500:
                    index["cycles"] = index["cycles"][-500:]
                
                # Write atomically
                await self._write_json_atomic(index_file, index)
            
        except Exception as e:
            self.logger.error(f"Failed to update index for {cyber_name}: {e}")
    
    async def _rebuild_index(self, cyber_name: str) -> Dict[str, Any]:
        """Rebuild the index by scanning cycle directories."""
        cycles_dir = self._get_cyber_cycles_dir(cyber_name)
        index = {"cycles": []}
        
        try:
            # Scan for cycle directories
            for cycle_dir in cycles_dir.iterdir():
                if cycle_dir.is_dir() and cycle_dir.name.startswith("cycle_"):
                    try:
                        cycle_num = int(cycle_dir.name.split("_")[1])
                        # Check if metadata exists
                        metadata_file = cycle_dir / "metadata.json"
                        status = "unknown"
                        timestamp = datetime.fromtimestamp(cycle_dir.stat().st_mtime).isoformat()
                        
                        if metadata_file.exists():
                            try:
                                with open(metadata_file, 'r') as f:
                                    metadata = json.load(f)
                                    status = metadata.get("status", "unknown")
                                    timestamp = metadata.get("completed_at", timestamp)
                            except:
                                pass
                        
                        index["cycles"].append({
                            "cycle_number": cycle_num,
                            "status": status,
                            "timestamp": timestamp,
                            "last_updated": timestamp
                        })
                    except (ValueError, IndexError):
                        continue
            
            # Sort by cycle number
            index["cycles"].sort(key=lambda x: x["cycle_number"])
            
        except Exception as e:
            self.logger.error(f"Failed to rebuild index for {cyber_name}: {e}")
        
        return index
    
    async def _write_json_atomic(self, path: Path, data: Any) -> None:
        """Write JSON atomically to prevent corruption."""
        temp_file = path.with_suffix('.tmp')
        async with aiofiles.open(temp_file, 'w') as f:
            await f.write(json.dumps(data, indent=2))
        
        # Atomic rename on POSIX systems
        temp_file.replace(path)
    
    async def _cleanup_old_cycles(self, cyber_name: str) -> None:
        """Remove old cycles beyond the maximum limit."""
        try:
            cycles_dir = self._get_cyber_cycles_dir(cyber_name)
            
            # Get all cycle directories
            cycle_dirs = sorted([
                d for d in cycles_dir.iterdir()
                if d.is_dir() and d.name.startswith("cycle_")
            ])
            
            # Remove oldest cycles if we exceed the limit
            while len(cycle_dirs) > self.max_cycles:
                oldest = cycle_dirs.pop(0)
                
                # Remove directory and contents
                import shutil
                shutil.rmtree(oldest)
                
                self.logger.debug(f"Removed old cycle directory: {oldest}")
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup old cycles for {cyber_name}: {e}")


# Global instance for easy access
_cycle_recorder: Optional[CycleRecorder] = None


def get_cycle_recorder(subspace_root: Optional[Path] = None) -> CycleRecorder:
    """Get the global cycle recorder instance.
    
    Args:
        subspace_root: Root path to subspace (required on first call)
        
    Returns:
        The global CycleRecorder instance
    """
    global _cycle_recorder
    if _cycle_recorder is None:
        if subspace_root is None:
            raise ValueError("subspace_root required for first initialization")
        _cycle_recorder = CycleRecorder(subspace_root)
    return _cycle_recorder