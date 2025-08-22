"""Client-side cycle recording for cybers.

This module provides a simple interface for cybers to record their
cycle data directly from within their stages.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger("Cyber.cycle_recorder")


class CycleRecorderClient:
    """Client-side recorder that cybers use to record their own activity."""
    
    def __init__(self, cyber_id: str, personal_path: Path):
        """Initialize the cycle recorder client.
        
        Args:
            cyber_id: The cyber's ID
            personal_path: Path to cyber's personal directory
        """
        self.cyber_id = cyber_id
        self.cycles_dir = personal_path / ".internal" / "cycles"
        self.cycles_dir.mkdir(parents=True, exist_ok=True)
        self.current_cycle = 0
        
    def set_cycle(self, cycle_number: int):
        """Set the current cycle number."""
        self.current_cycle = cycle_number
        self.current_cycle_dir = self.cycles_dir / f"cycle_{cycle_number:06d}"
        self.current_cycle_dir.mkdir(parents=True, exist_ok=True)
        
        # Update current.json pointer
        current_file = self.cycles_dir / "current.json"
        with open(current_file, 'w') as f:
            json.dump({
                "cycle_number": cycle_number,
                "started_at": datetime.now().isoformat()
            }, f, indent=2)
    
    def record_stage(self, stage_name: str, 
                     working_memory: Optional[Dict[str, Any]] = None,
                     llm_input: Optional[Dict[str, Any]] = None,
                     llm_output: Optional[Dict[str, Any]] = None,
                     stage_output: Optional[Dict[str, Any]] = None,
                     token_usage: Optional[Dict[str, int]] = None):
        """Record data for a completed stage.
        
        This should be called at the end of each stage's main() function.
        
        Args:
            stage_name: Name of the stage (observation, decision, execution, reflection, cleanup)
            working_memory: Current working memory state
            llm_input: What was sent to the LLM (brain request)
            llm_output: What the LLM returned (brain response)
            stage_output: What the stage produced (pipeline buffer content)
            token_usage: Tokens used in this stage
        """
        if not self.current_cycle_dir:
            logger.warning(f"No cycle directory set, cannot record stage {stage_name}")
            return
            
        try:
            # Create stage record
            stage_data = {
                "stage": stage_name,
                "timestamp": datetime.now().isoformat(),
                "cycle_number": self.current_cycle,
                "working_memory": working_memory or {},
                "llm_input": llm_input or {},
                "llm_output": llm_output or {},
                "stage_output": stage_output or {},
                "token_usage": token_usage or {}
            }
            
            # Write stage file (includes working memory)
            stage_file = self.current_cycle_dir / f"{stage_name}.json"
            with open(stage_file, 'w') as f:
                json.dump(stage_data, f, indent=2)
            
            logger.debug(f"Recorded {stage_name} stage for cycle {self.current_cycle}")
            
        except Exception as e:
            logger.error(f"Failed to record stage {stage_name}: {e}")
    
    def record_reflection(self, reflection_data: Dict[str, Any]):
        """Record reflection data.
        
        Args:
            reflection_data: The reflection data to record
        """
        if not self.current_cycle_dir:
            return
            
        try:
            reflection_file = self.current_cycle_dir / "reflection_from_last_cycle.json"
            with open(reflection_file, 'w') as f:
                json.dump(reflection_data, f, indent=2)
            logger.debug(f"Recorded reflection for cycle {self.current_cycle}")
        except Exception as e:
            logger.error(f"Failed to record reflection: {e}")
    
    def record_brain_interaction(self, request: Dict[str, Any], response: Dict[str, Any]):
        """Record a brain request/response pair.
        
        Args:
            request: The brain request
            response: The brain response
        """
        if not self.current_cycle_dir:
            return
            
        try:
            # Load existing brain interactions
            brain_file = self.current_cycle_dir / "brain_interactions.json"
            if brain_file.exists():
                with open(brain_file, 'r') as f:
                    interactions = json.load(f)
            else:
                interactions = []
            
            # Add new interaction
            interactions.append({
                "timestamp": datetime.now().isoformat(),
                "request": request,
                "response": response
            })
            
            # Write back
            with open(brain_file, 'w') as f:
                json.dump(interactions, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to record brain interaction: {e}")
    
    def complete_cycle(self, status: str = "completed"):
        """Mark the current cycle as complete.
        
        Args:
            status: Final status of the cycle
        """
        if not self.current_cycle_dir:
            return
            
        try:
            # Update cycle metadata
            metadata_file = self.current_cycle_dir / "metadata.json"
            metadata = {
                "cycle_number": self.current_cycle,
                "status": status,
                "completed_at": datetime.now().isoformat()
            }
            
            # If metadata exists, update it
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    existing = json.load(f)
                metadata = {**existing, **metadata}
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
                
            logger.debug(f"Completed cycle {self.current_cycle} with status {status}")
            
        except Exception as e:
            logger.error(f"Failed to complete cycle: {e}")


# Global instance for the cyber to use
_recorder: Optional[CycleRecorderClient] = None


def get_cycle_recorder(cyber_id: str, personal_path: Path) -> CycleRecorderClient:
    """Get or create the global cycle recorder.
    
    Args:
        cyber_id: The cyber's ID
        personal_path: Path to cyber's personal directory
        
    Returns:
        The cycle recorder instance
    """
    global _recorder
    if _recorder is None:
        _recorder = CycleRecorderClient(cyber_id, personal_path)
    return _recorder