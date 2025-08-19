"""Observation Stage - Understanding the situation through environmental scanning.

This stage scans the environment for changes and creates understanding
from observations about the current situation.

The output of this stage is reasoning about what's happening and its relevance.
"""

import logging
from typing import TYPE_CHECKING
from datetime import datetime
import json
import time

if TYPE_CHECKING:
    from ..cognitive_loop import CognitiveLoop

from ..memory.tag_filter import TagFilter
from ..perception import EnvironmentScanner

logger = logging.getLogger("Cyber.stages.observation")


class ObservationStage:
    """Handles the observation phase of cognition.
    
    This stage is responsible for:
    - Scanning the environment for changes
    - Processing incoming messages  
    - Creating contextual understanding from observations
    """
    
    # Knowledge tags to exclude during observation stage
    # We don't need action implementation details when observing
    KNOWLEDGE_BLACKLIST = {
        "action_guide", 
        "action_implementation", 
        "execution", 
        "execution_only",  # Execution stage specific
        "decision_only",  # Decision stage specific
        "reflection_only",  # Reflection stage specific
        "procedures", 
        "tools",
        "background"
    }
    
    def __init__(self, cognitive_loop: 'CognitiveLoop'):
        """Initialize the observation stage.
        
        Args:
            cognitive_loop: Reference to the main cognitive loop
        """
        self.cognitive_loop = cognitive_loop
        self.memory_system = cognitive_loop.memory_system
        self.environment_scanner: EnvironmentScanner = cognitive_loop.environment_scanner
        self.brain_interface = cognitive_loop.brain_interface
        self.memory_dir = cognitive_loop.memory_dir
        self.file_manager = cognitive_loop.file_manager
        self.knowledge_manager = cognitive_loop.knowledge_manager
    
    def _load_stage_instructions(self):
        """Load stage instructions from knowledge into memory."""
        # Fetch from knowledge system
        stage_data = self.knowledge_manager.get_stage_instructions('observation')
        if stage_data:
            logger.info(f"Got stage instructions, type: {type(stage_data)}, keys: {stage_data.keys() if isinstance(stage_data, dict) else 'not a dict'}")
            from ..memory.memory_blocks import FileMemoryBlock
            from ..memory.memory_types import Priority, ContentType
            import yaml
            
            # stage_data has: content (YAML string), metadata (DB metadata), id, source
            # Parse the YAML content to get the actual knowledge fields
            try:
                content = stage_data.get('content', stage_data) if isinstance(stage_data, dict) else stage_data
                logger.info(f"Parsing content of type {type(content)}, first 100 chars: {str(content)[:100]}")
                yaml_content = yaml.safe_load(content)
                logger.info(f"Parsed YAML successfully, keys: {yaml_content.keys() if isinstance(yaml_content, dict) else 'not a dict'}")
                # yaml_content now has: title, category, tags, content (the actual instructions)
            except Exception as e:
                logger.error(f"Failed to parse stage instructions YAML: {e}")
                return
            
            # Create a memory block for stage instructions
            # Use .internal path so cyber knows it's system-managed
            # Pass the parsed YAML content as metadata for validation
            stage_memory = FileMemoryBlock(
                location="/personal/.internal/knowledge_observation_stage",
                confidence=1.0,
                priority=Priority.FOUNDATIONAL,
                metadata=yaml_content,  # This has title, category, tags, content fields
                pinned=True,  # Stage instructions should always be included
                cycle_count=self.cognitive_loop.cycle_count,
                content_type=ContentType.MINDSWARM_KNOWLEDGE
            )
            try:
                self.memory_system.add_memory(stage_memory)
                self.stage_knowledge_id = stage_memory.id
                logger.info(f"Successfully added stage memory with ID: {stage_memory.id}")
            except Exception as e:
                logger.error(f"Failed to add stage memory: {e}")
                self.stage_knowledge_id = None
                return
        else:
            logger.warning("No stage instructions found for observation stage")
            self.stage_knowledge_id = None
    
    def _cleanup_stage_instructions(self):
        """Remove stage instructions from working memory."""
        if hasattr(self, 'stage_knowledge_id') and self.stage_knowledge_id:
            if self.memory_system.remove_memory(self.stage_knowledge_id):
                logger.debug("Removed observation stage instructions from memory")
            self.stage_knowledge_id = None
    
    async def observe(self):
        """OBSERVE - Understand the situation from observations.
        
        This phase first scans for new observations, then analyzes all observations 
        and produces orientation with reasoning and relevance.
        
        Returns:
            Orientation data including reasoning and relevance, or None
        """
        logger.info("=== OBSERVATION STAGE ===")
        logger.info("👁️ Observing and reasoning about the situation...")
        
        # Load stage instructions into memory if not already present
        self._load_stage_instructions()
        
        # First, scan environment for new observations
        logger.info("📡 Scanning for new observations...")
        self.cognitive_loop._update_dynamic_context(stage="OBSERVATION", phase="SCAN")
        observations = self.environment_scanner.scan_environment(
            full_scan=False, 
            cycle_count=self.cognitive_loop.cycle_count
        )
        
        # Log observations summary
        if observations:
            logger.info(f"📋 Found {len(observations)} new observations")
            # Group by type for logging
            obs_by_type = {}
            for obs in observations:
                obs_type = obs.get('observation_type', 'unknown')
                obs_by_type[obs_type] = obs_by_type.get(obs_type, 0) + 1
            for obs_type, count in obs_by_type.items():
                logger.debug(f"  - {obs_type}: {count}")
        else:
            logger.debug("No new observations found")
        
        # Update dynamic context before LLM call - OBSERVE phase
        self.cognitive_loop._update_dynamic_context(stage="OBSERVATION", phase="OBSERVE")
        
        # Create tag filter for observation stage with our blacklist
        tag_filter = TagFilter(blacklist=self.KNOWLEDGE_BLACKLIST)
        
        # Build working memory context for reasoning about the situation
        memory_context = self.memory_system.build_context(
            max_tokens=self.cognitive_loop.max_context_tokens // 2,
            current_task="Understanding the current situation from observations",
            selection_strategy="balanced",
            tag_filter=tag_filter,
            exclude_content_types=[]  # Include all relevant memory types
        )
        
        # Include observations in the context for brain analysis
        observation_summary = ""
        if observations:
            observation_summary = "\n\n=== NEW OBSERVATIONS ===\n"
            for obs in observations:
                obs_type = obs.get('observation_type', 'unknown')
                message = obs.get('message', '')
                priority = obs.get('priority', 'MEDIUM')
                observation_summary += f"[{priority}] {obs_type}: {message}\n"
                # Include additional details if present
                if 'content' in obs and obs['content']:
                    # Truncate long content
                    content = obs['content']
                    if len(content) > 500:
                        content = content[:497] + "..."
                    observation_summary += f"  Details: {content}\n"
        
        # Use brain to analyze the situation from all observations
        logger.info("🧠 Analyzing situation from observations...")

        thinking_request = {
            "signature": {
                "instruction": """
Review all observations to identify relevant changes.
Consider how they relate to the situation, goals, tasks and reflections from last cycle.
Based on your observations, suggest what problem should be addressed this cycle.
Don't plan how to act on this information, just identify what needs attention.
Always start your output with [[ ## reasoning ## ]]
""",
                "inputs": {
                    "working_memory": "Your working memory",
                    "new_observations": "Recent observations from environment scan"
                },
                "outputs": {
                    "reasoning": "Your short explaination of reasoning",
                    "relevance": "How the observations relate to the current situation",
                    "suggested_problem": "A clear statement of what problem or task should be addressed this cycle (1-2 sentences)",
                },
                "display_field": "reasoning"
            },
            "input_values": {
                "working_memory": memory_context,
                "new_observations": observation_summary if observation_summary else "No new observations"
            },
            "request_id": f"observe_{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        response = await self.brain_interface._use_brain(json.dumps(thinking_request))
        orientation_response = json.loads(response)
        
        # Extract the useful content from the response
        output_values = orientation_response.get("output_values", {})
        
        # Debug log to see what we got
        logger.debug(f"Brain response output_values: {output_values}")
        
        # Create orientation data - handle template placeholders
        reasoning = output_values.get("reasoning", "")
        relevance = output_values.get("relevance", "")
        suggested_problem = output_values.get("suggested_problem", "")
        
        # Check for template placeholders and replace with meaningful defaults
        if reasoning == "{reasoning}" or not reasoning:
            reasoning = "Analyzing current observations"
        if relevance == "{relevance}" or not relevance:
            relevance = "Observations being processed for context"
        if suggested_problem == "{suggested_problem}" or not suggested_problem:
            suggested_problem = "Continue exploring and understanding the environment"
        
        observartion_result_data = {
            "cycle_count": self.cognitive_loop.cycle_count,
            "reasoning": reasoning,
            "relevance": relevance,
            "suggested_problem": suggested_problem,
            "observations": observations  # Include raw observations for reference
        }
        
        # Write to observation pipeline buffer
        observation_buffer = self.cognitive_loop.get_current_pipeline("observation")
        buffer_file = self.cognitive_loop.personal.parent / observation_buffer.location
        
        # Write the observation data to the buffer
        with open(buffer_file, 'w') as f:
            json.dump(observartion_result_data, f, indent=2)
        
        # Touch the memory block so it knows when the file was updated
        self.cognitive_loop.memory_system.touch_memory(observation_buffer.id, self.cognitive_loop.cycle_count)
        
        logger.info(f"💭 Observation written to pipeline buffer")
        
        # Clean up stage instructions before leaving
        self._cleanup_stage_instructions()