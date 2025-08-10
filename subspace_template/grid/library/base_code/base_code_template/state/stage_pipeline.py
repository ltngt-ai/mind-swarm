"""Stage Pipeline Manager - Manages information flow between cognitive stages.

This module handles the explicit passing of information between observation,
decision, and execution stages, ensuring clear data flow and persistent state.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict

from ..utils.json_utils import DateTimeEncoder, safe_json_encode, safe_json_decode

logger = logging.getLogger("Cyber.pipeline")


@dataclass
class StageOutput:
    """Base class for stage outputs."""
    stage: str
    timestamp: datetime = field(default_factory=datetime.now)
    cycle_count: int = 0
    success: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['timestamp'] = data['timestamp'].isoformat()
        return data


@dataclass
class ObservationOutput(StageOutput):
    """Output from the observation stage."""
    understanding: str = ""
    situation_type: str = "normal"
    new_observations: List[Dict[str, Any]] = field(default_factory=list)
    relevant_goals: List[str] = field(default_factory=list)
    previous_results_reviewed: bool = False
    approach: str = ""
    
    def __post_init__(self):
        self.stage = "observation"


@dataclass
class DecisionOutput(StageOutput):
    """Output from the decision stage."""
    selected_actions: List[Dict[str, Any]] = field(default_factory=list)
    reasoning: str = ""
    addresses_goals: List[str] = field(default_factory=list)
    uses_orientation: bool = False
    
    def __post_init__(self):
        self.stage = "decision"


@dataclass
class ExecutionOutput(StageOutput):
    """Output from the execution stage."""
    completed_actions: List[Dict[str, Any]] = field(default_factory=list)
    failed_actions: List[Dict[str, Any]] = field(default_factory=list)
    results: List[Dict[str, Any]] = field(default_factory=list)
    side_effects: List[str] = field(default_factory=list)
    goal_progress: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        self.stage = "execution"


class StagePipeline:
    """Manages the flow of information between cognitive stages."""
    
    def __init__(self, memory_dir: Path):
        """Initialize the pipeline manager.
        
        Args:
            memory_dir: Directory for storing pipeline state
        """
        self.memory_dir = memory_dir
        self.pipeline_file = memory_dir / "stage_pipeline.json"
        
        # Current pipeline state
        self.current_pipeline = {
            "current_cycle": 0,
            "observation_output": None,
            "decision_output": None,
            "execution_output": None,
            "previous_cycle": None
        }
        
        # Load existing pipeline if available
        self.load_pipeline()
    
    def load_pipeline(self) -> bool:
        """Load pipeline state from disk.
        
        Returns:
            True if loaded successfully
        """
        try:
            if self.pipeline_file.exists():
                with open(self.pipeline_file, 'r') as f:
                    data = json.load(f)
                    self.current_pipeline = data
                    logger.info(f"Loaded pipeline state for cycle {data.get('current_cycle', 0)}")
                    return True
        except Exception as e:
            logger.error(f"Failed to load pipeline state: {e}")
        return False
    
    def save_pipeline(self) -> bool:
        """Save pipeline state to disk.
        
        Returns:
            True if saved successfully
        """
        try:
            pipeline_json = safe_json_encode(self.current_pipeline, indent=2)
            with open(self.pipeline_file, 'w') as f:
                f.write(pipeline_json)
            return True
        except Exception as e:
            logger.error(f"Failed to save pipeline state: {e}")
            return False
    
    def start_new_cycle(self, cycle_count: int):
        """Start a new cognitive cycle.
        
        Args:
            cycle_count: The cycle number
        """
        # Archive previous cycle
        if any([self.current_pipeline.get("observation_output"),
                self.current_pipeline.get("decision_output"),
                self.current_pipeline.get("execution_output")]):
            self.current_pipeline["previous_cycle"] = {
                "cycle": self.current_pipeline["current_cycle"],
                "observation": self.current_pipeline.get("observation_output"),
                "decision": self.current_pipeline.get("decision_output"),
                "execution": self.current_pipeline.get("execution_output")
            }
        
        # Reset current outputs
        self.current_pipeline["current_cycle"] = cycle_count
        self.current_pipeline["observation_output"] = None
        self.current_pipeline["decision_output"] = None
        self.current_pipeline["execution_output"] = None
        
        logger.info(f"Started new pipeline cycle {cycle_count}")
        self.save_pipeline()
    
    def write_observation(self, output: ObservationOutput):
        """Write observation stage output to pipeline.
        
        Args:
            output: The observation output
        """
        self.current_pipeline["observation_output"] = output.to_dict()
        self.save_pipeline()
        logger.info(f"Wrote observation output: {output.situation_type}")
    
    def write_decision(self, output: DecisionOutput):
        """Write decision stage output to pipeline.
        
        Args:
            output: The decision output
        """
        self.current_pipeline["decision_output"] = output.to_dict()
        self.save_pipeline()
        logger.info(f"Wrote decision output: {len(output.selected_actions)} actions")
    
    def write_execution(self, output: ExecutionOutput):
        """Write execution stage output to pipeline.
        
        Args:
            output: The execution output
        """
        self.current_pipeline["execution_output"] = output.to_dict()
        self.save_pipeline()
        logger.info(f"Wrote execution output: {len(output.completed_actions)} completed")
    
    def get_last_execution(self) -> Optional[Dict[str, Any]]:
        """Get the last execution output (from current or previous cycle).
        
        Returns:
            The last execution output or None
        """
        # Try current cycle first
        if self.current_pipeline.get("execution_output"):
            return self.current_pipeline["execution_output"]
        
        # Fall back to previous cycle
        if self.current_pipeline.get("previous_cycle"):
            return self.current_pipeline["previous_cycle"].get("execution")
        
        return None
    
    def get_observation(self) -> Optional[Dict[str, Any]]:
        """Get the current cycle's observation output.
        
        Returns:
            The observation output or None
        """
        return self.current_pipeline.get("observation_output")
    
    def get_decision(self) -> Optional[Dict[str, Any]]:
        """Get the current cycle's decision output.
        
        Returns:
            The decision output or None
        """
        return self.current_pipeline.get("decision_output")
    
    def get_pipeline_summary(self) -> Dict[str, Any]:
        """Get a summary of the current pipeline state.
        
        Returns:
            Summary of pipeline state
        """
        return {
            "current_cycle": self.current_pipeline.get("current_cycle", 0),
            "has_observation": self.current_pipeline.get("observation_output") is not None,
            "has_decision": self.current_pipeline.get("decision_output") is not None,
            "has_execution": self.current_pipeline.get("execution_output") is not None,
            "has_previous": self.current_pipeline.get("previous_cycle") is not None
        }