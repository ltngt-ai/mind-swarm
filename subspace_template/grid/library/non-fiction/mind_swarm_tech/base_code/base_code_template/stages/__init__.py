"""Cognitive stages for the Mind-Swarm cyber.

The cognitive loop is organized into three fundamental stages:

1. Observation Stage - Gathering and understanding information
   - Perceive: Scan the environment
   - Observe: Select what needs attention
   - Orient: Understand the situation

2. Decision Stage - Choosing what to do
   - Decide: Choose actions based on understanding

3. Execution Stage - Taking action
   - Instruct: Prepare and validate actions
   - Act: Execute the actions
"""

from .observation_stage import ObservationStage
from .decision_stage import DecisionStage
from .execution_stage import ExecutionStage
from .reflect_stage import ReflectStage
from .cleanup_stage import CleanupStage

__all__ = ['ObservationStage', 'DecisionStage', 'ExecutionStage', 'ReflectStage', 'CleanupStage']