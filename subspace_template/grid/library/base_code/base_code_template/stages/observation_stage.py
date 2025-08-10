"""Observation Stage - Understanding and managing observations.

This stage encompasses:
1. Observe - Understand the situation from observations
2. Cleanup - Clean up obsolete observations

The output of this stage is an understanding of what's happening.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json

from ..memory import Priority, ObservationMemoryBlock, FileMemoryBlock, MemoryType
from ..memory.tag_filter import TagFilter
from ..perception import EnvironmentScanner
from ..brain import BrainInterface
from ..state.stage_pipeline import ObservationOutput
from ..state.goal_manager import GoalStatus

logger = logging.getLogger("Cyber.stages.observation")


class ObservationStage:
    """Handles the observation phase of cognition.
    
    This stage is responsible for:
    - Understanding the situation from observations (Observe)
    - Cleaning up obsolete observations (Cleanup)
    """
    
    # Knowledge tags to exclude during observation stage
    # We don't need action implementation details when observing
    KNOWLEDGE_BLACKLIST = {
        "action_guide", 
        "action_implementation", 
        "execution", 
        "procedures", 
        "tools",
        "background"
    }
    
    def __init__(self, cognitive_loop):
        """Initialize the observation stage.
        
        Args:
            cognitive_loop: Reference to the main cognitive loop
        """
        self.cognitive_loop = cognitive_loop
        self.memory_system = cognitive_loop.memory_system
        self.environment_scanner = cognitive_loop.environment_scanner
        self.brain_interface = cognitive_loop.brain_interface
        self.memory_dir = cognitive_loop.memory_dir
        self.file_manager = cognitive_loop.file_manager
        
    async def run(self) -> Optional[Dict[str, Any]]:
        """Run the complete observation stage.
        
        Returns:
            Orientation data if something needs attention, None otherwise
        """
        logger.info("=== OBSERVATION STAGE ===")
        
        # Phase 0: Reflect - Review previous execution results and update goals
        await self.reflect()
        
        # Phase 1: Observe - Understand the situation from observations
        orientation = await self.observe()
        
        # Phase 2: Cleanup - Clean up obsolete/processed observations
        await self.cleanup()
        
        return orientation
    
    async def reflect(self):
        """REFLECT - Review previous execution results and update goals.
        
        This phase looks at what happened in the last execution and updates
        goals and tasks accordingly.
        """
        logger.info("🔍 Reflecting on previous execution results...")
        self.cognitive_loop._update_dynamic_context(stage="OBSERVATION", phase="REFLECT")
        
        # Get last execution results from pipeline
        last_execution = self.cognitive_loop.stage_pipeline.get_last_execution()
        if not last_execution:
            logger.debug("No previous execution to reflect on")
            return
        
        # Review completed actions and update tasks
        goal_manager = self.cognitive_loop.goal_manager
        completed_actions = last_execution.get('completed_actions', [])
        failed_actions = last_execution.get('failed_actions', [])
        
        # Update task progress based on action results
        active_tasks = goal_manager.get_active_tasks()
        for task in active_tasks:
            # Check if any completed actions relate to this task
            for action in completed_actions:
                if task.description.lower() in str(action).lower():
                    goal_manager.add_task_action(task.id, {
                        'action': action,
                        'status': 'completed',
                        'cycle': self.cognitive_loop.cycle_count - 1
                    })
            
            for action in failed_actions:
                if task.description.lower() in str(action).lower():
                    goal_manager.add_task_action(task.id, {
                        'action': action,
                        'status': 'failed',
                        'cycle': self.cognitive_loop.cycle_count - 1
                    })
        
        logger.info(f"Reflected on {len(completed_actions)} completed and {len(failed_actions)} failed actions")
    
    async def observe(self) -> Optional[Dict[str, Any]]:
        """OBSERVE - Understand the situation from observations.
        
        This phase first scans for new observations, then analyzes all observations 
        and produces an orientation/understanding.
        
        Returns:
            Orientation data including understanding and approach, or None
        """
        logger.info("👁️ Observing and understanding the situation...")
        
        # First, scan environment for new observations
        logger.info("📡 Scanning for new observations...")
        self.cognitive_loop._update_dynamic_context(stage="OBSERVATION", phase="SCAN")
        observations = self.environment_scanner.scan_environment(
            full_scan=False, 
            cycle_count=self.cognitive_loop.cycle_count
        )
        
        # Add all observations and memories from environment scanner
        # Observations point to the actual files that changed, not to saved observations
        significant_count = 0
        for memory in observations:
            # Add all memories to the memory system
            self.memory_system.add_memory(memory)
            
            # Count significant observations
            if isinstance(memory, ObservationMemoryBlock):
                if memory.priority != Priority.LOW:
                    significant_count += 1
                logger.debug(f"Observation: {memory.observation_type} for {memory.path}")
        
        if significant_count > 0:
            logger.info(f"📡 Found {significant_count} significant changes ({len(observations)} total)")
        else:
            logger.debug("📡 No significant changes detected")
        
        # Update dynamic context before LLM call - OBSERVE phase
        self.cognitive_loop._update_dynamic_context(stage="OBSERVATION", phase="OBSERVE")
        
        # Create tag filter for observation stage with our blacklist
        tag_filter = TagFilter(blacklist=self.KNOWLEDGE_BLACKLIST)
        
        # Build working memory context for understanding the situation
        memory_context = self.memory_system.build_context(
            max_tokens=self.cognitive_loop.max_context_tokens // 2,
            current_task="Understanding the current situation from observations",
            selection_strategy="balanced",
            tag_filter=tag_filter,
            exclude_types=[]  # Include all relevant memory types
        )
        
        # Use brain to analyze the situation from all observations
        logger.info("🧠 Analyzing situation from observations...")
        
        # The brain will look at all observations and understand the situation
        orientation_response = await self.brain_interface.analyze_situation_from_observations(memory_context)
        
        if not orientation_response:
            logger.info("👁️ No significant situation to address")
            return None
        
        # Extract the useful content from the response
        output_values = orientation_response.get("output_values", {})
        
        # Debug log to see what we got
        logger.debug(f"Brain response output_values: {output_values}")
        
        # Create orientation data - handle template placeholders
        understanding = output_values.get("understanding", "")
        situation_type = output_values.get("situation_type", "unknown")
        approach = output_values.get("approach", "")
        
        # Check for template placeholders and replace with meaningful defaults
        if understanding == "{understanding}" or not understanding:
            understanding = "Analyzing current observations"
        if situation_type == "{situation_type}" or not situation_type:
            situation_type = "observation_review"
        if approach == "{approach}" or not approach:
            approach = "Continue monitoring and processing observations"
        
        orientation_data = {
            "timestamp": datetime.now().isoformat(),
            "cycle_count": self.cognitive_loop.cycle_count,
            "understanding": understanding,
            "situation_type": situation_type,
            "approach": approach
        }
        
        # Save orientation to file
        orientations_dir = self.memory_dir / "orientations"
        self.file_manager.ensure_directory(orientations_dir)
        
        timestamp = datetime.now()
        orientation_file = orientations_dir / f"orient_{timestamp.strftime('%Y%m%d_%H%M%S')}_{self.cognitive_loop.cycle_count}.json"
        
        with open(orientation_file, 'w') as f:
            json.dump(orientation_data, f, indent=2)
        
        # Create observation for the orientation
        orientation_observation = ObservationMemoryBlock(
            observation_type="self_orientation",
            path=str(orientation_file),
            message="Created orientation for current situation",
            cycle_count=self.cognitive_loop.cycle_count,
            priority=Priority.MEDIUM,
            confidence=1.0
        )
        
        # Add observation to memory system
        self.memory_system.add_memory(orientation_observation)
        logger.info(f"💭 Orientation stored: {orientation_file.name}")
        
        # Also create FileMemoryBlock for immediate access
        orientation_memory = FileMemoryBlock(
            location=str(orientation_file),
            priority=Priority.HIGH,
            confidence=1.0
        )
        
        # Add to working memory
        self.memory_system.add_memory(orientation_memory)
        
        # Store just the file reference in cycle state
        # Orientation is now tracked through memory system, not cycle state
        
        # Get relevant goals for this orientation
        goal_manager = self.cognitive_loop.goal_manager
        active_goals = goal_manager.get_active_goals()
        relevant_goal_ids = []
        for goal in active_goals:
            # Simple relevance check - can be made more sophisticated
            if (situation_type in ["task_received", "work_needed"] or 
                goal.priority == "high"):
                relevant_goal_ids.append(goal.id)
        
        # Write to pipeline
        pipeline_output = ObservationOutput(
            stage="observation",
            cycle_count=self.cognitive_loop.cycle_count,
            understanding=understanding,
            situation_type=situation_type,
            new_observations=[{"type": obs.observation_type, "path": obs.path} 
                            for obs in self.memory_system.get_memories_by_type(MemoryType.OBSERVATION)
                            if isinstance(obs, ObservationMemoryBlock) and 
                            obs.cycle_count == self.cognitive_loop.cycle_count],
            relevant_goals=relevant_goal_ids,
            previous_results_reviewed=self.cognitive_loop.stage_pipeline.get_last_execution() is not None,
            approach=approach
        )
        self.cognitive_loop.stage_pipeline.write_observation(pipeline_output)
        logger.info(f"📝 Wrote observation output to pipeline with {len(relevant_goal_ids)} relevant goals")
                
        return orientation_data
    
    async def cleanup(self) -> None:
        """CLEANUP - Clean up obsolete observations that are no longer relevant.
        
        The cyber determines what's obsolete based on cycle counts and context.
        """
        logger.info("🧹 Cleaning up observations...")
        
        # Update phase to CLEANUP
        self.cognitive_loop._update_dynamic_context(stage="OBSERVATION", phase="CLEANUP")
        
        # Get the brain's assessment of what to clean up
        memory_context = self.memory_system.build_context(
            max_tokens=self.cognitive_loop.max_context_tokens // 4,  # Smaller context for cleanup
            current_task="Identifying obsolete observations to clean up based on cycle counts",
            selection_strategy="recent",
            tag_filter=TagFilter(blacklist=self.KNOWLEDGE_BLACKLIST),
            exclude_types=[]  # Include all relevant memory types
        )
        
        cleanup_result = await self.brain_interface.identify_obsolete_observations(memory_context)
        
        if cleanup_result:
            obsolete_observations = cleanup_result.get("obsolete_observations", [])
            
            # Remove obsolete observations
            if obsolete_observations:
                logger.info(f"Removing {len(obsolete_observations)} obsolete observations:")
                for obs_id in obsolete_observations:
                    try:
                        self.memory_system.remove_memory(obs_id)
                        logger.info(f"  - Removed: {obs_id}")
                    except Exception as e:
                        logger.warning(f"  - Failed to remove {obs_id}: {e}")