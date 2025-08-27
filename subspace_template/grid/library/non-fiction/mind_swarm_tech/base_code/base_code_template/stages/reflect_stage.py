"""Reflect Stage - Learn from previous execution results.

This stage reviews what happened in the last execution cycle and updates
understanding, goals, and priorities based on outcomes.

This is the 4th stage in the cognitive architecture.
"""

import json
import logging
from typing import TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from ..cognitive_loop import CognitiveLoop

logger = logging.getLogger("Cyber.stages.reflect")


class ReflectStage:
    """Handles the reflection phase of cognition.
    
    This stage is responsible for:
    - Reviewing previous execution results
    - Learning from successes and failures
    - Updating goals and priorities based on outcomes
    - Creating insights for future cycles
    """
    
    # Knowledge tags to exclude during reflection stage
    # We don't need execution implementation details when reflecting
    KNOWLEDGE_BLACKLIST = {
        "execution",  # Execution-specific knowledge
        "execution_only",  # Python API docs
        "decision_only",  # Decision stage specific
        "observation",  # Don't need raw observations
        "action_implementation",  # Implementation details
        "api_documentation",  # API reference
        "procedures",  # Step-by-step procedures
        "tools"  # Tool implementation details
    }
    
    def __init__(self, cognitive_loop: 'CognitiveLoop'):
        """Initialize the reflect stage.
        
        Args:
            cognitive_loop: Reference to the main cognitive loop
        """
        self.cognitive_loop = cognitive_loop
        self.memory_system = cognitive_loop.memory_system
        self.brain_interface = cognitive_loop.brain_interface
        self.knowledge_manager = cognitive_loop.knowledge_manager
    
    def _load_stage_instructions(self):
        """Load stage instructions from knowledge into memory."""
        stage_data = self.knowledge_manager.get_stage_instructions('reflection')
        if stage_data:
            from ..memory.memory_blocks import MemoryBlock
            from ..memory.memory_types import Priority, ContentType
            import yaml
            
            # stage_data has: content (YAML string), metadata (DB metadata), id, source
            # Parse the YAML content to get the actual knowledge fields
            try:
                yaml_content = yaml.safe_load(stage_data['content'])
                # yaml_content now has: title, category, tags, content (the actual instructions)
            except Exception as e:
                logger.error(f"Failed to parse stage instructions YAML: {e}")
                return
            
            # Pass the parsed YAML content as metadata for validation
            stage_memory = MemoryBlock(
                location="/personal/.internal/knowledge_reflection_stage",
                confidence=1.0,
                priority=Priority.FOUNDATIONAL,
                metadata=yaml_content,  # This has title, category, tags, content fields
                pinned=False,
                cycle_count=self.cognitive_loop.cycle_count,
                content_type=ContentType.MINDSWARM_KNOWLEDGE
            )
            self.memory_system.add_memory(stage_memory)
            self.stage_knowledge_id = stage_memory.id
            logger.debug("Loaded reflection stage instructions into memory")
        else:
            self.stage_knowledge_id = None
    
    def _cleanup_stage_instructions(self):
        """Remove stage instructions from working memory."""
        if hasattr(self, 'stage_knowledge_id') and self.stage_knowledge_id:
            if self.memory_system.remove_memory(self.stage_knowledge_id):
                logger.debug("Removed reflection stage instructions from memory")
            self.stage_knowledge_id = None
        
    async def reflect(self) -> None:
        """Run the reflection stage.
        
        Reviews the last execution and creates reflections in memory.
        Everything is handled by the brain through DSPy, not fixed logic.
        """
        logger.info("=== REFLECT STAGE ===")
        
        # Load stage instructions
        self._load_stage_instructions()
        
        # Update dynamic context
        self.cognitive_loop._update_dynamic_context(stage="REFLECT", phase="REVIEWING")
        
        # Check if there's an execution to reflect on from current pipeline
        # (It was filled by the execution stage in this cycle)
        execution_buffer = self.cognitive_loop.get_current_pipeline("execution")
        execution_file = self.cognitive_loop.personal.parent / execution_buffer.location
        
        import json
        try:
            with open(execution_file, 'r') as f:
                last_execution = json.load(f)
                if not last_execution or last_execution == {}:
                    logger.debug("No execution to reflect on")
                    return
        except:
            logger.debug("No execution to reflect on")
            return
        
        # Build context for reflection - let the brain see everything in memory
        from ..memory.tag_filter import TagFilter
        tag_filter = TagFilter(blacklist=self.KNOWLEDGE_BLACKLIST)
        
        memory_context = self.memory_system.build_context(
            max_tokens=self.cognitive_loop.max_context_tokens // 3,
            current_task="Reflecting on previous execution results",
            selection_strategy="recent",
            tag_filter=tag_filter
        )
        
        # Use brain to reflect on what happened
        logger.info("🔍 Reflecting on previous execution...")
        
        import time
        thinking_request = {
            "signature": {
                "instruction": """
Review the previous execution results in your memory. 
and reflect on what worked, what didn't, and what you learned.
Also create a single-line summary describing what was accomplished this cycle, including any completed tasks or goals for the activity log.
""",
                "inputs": {
                    "working_memory": "Your current working memory including execution results"
                },
                "outputs": {
                    "cycle_summary": "A single-line summary of what was accomplished this cycle (keep concise, under 200 chars)",
                    "insights": "Key insights from the execution results",
                },
                "display_field": "insights"
            },
            "input_values": {
                "working_memory": memory_context
            },
            "request_id": f"reflect_{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        response = await self.brain_interface._use_brain(json.dumps(thinking_request))
        reflection_response = json.loads(response)
        
        if not reflection_response:
            logger.debug("No reflections generated")
            return
        
        # Extract reflection content
        output_values = reflection_response.get("output_values", {})
               
        reflection_content = {
            "insights": output_values.get("insights", ""),
            "lessons_learned": output_values.get("lessons_learned", ""),
        }
        
        # Save as a reflection_on_last_cycle memory block
        reflection_file = self.cognitive_loop.memory_dir / "reflection_on_last_cycle.json"
        with open(reflection_file, 'w') as f:
            json.dump(reflection_content, f, indent=2)
        
        # Add or update the reflection memory block
        from ..memory import MemoryBlock, Priority
        reflection_memory = MemoryBlock(
            location="personal/.internal/memory/reflection_on_last_cycle.json",
            priority=Priority.HIGH,
            pinned=False,  # Not pinned, can be cleaned up if needed
            metadata={
                "file_type": "reflection",
                "description": "Reflection on the last execution cycle"
            },
            cycle_count=self.cognitive_loop.cycle_count,
            no_cache=True,  # Don't cache, always read fresh
        )
        
        # Remove old reflection if it exists and add new one
        reflection_id = "personal/.internal/memory/reflection_on_last_cycle.json"
        existing_memory = self.cognitive_loop.memory_system.get_memory(reflection_id)
        if existing_memory:
            self.cognitive_loop.memory_system.remove_memory(reflection_id)
        self.cognitive_loop.memory_system.add_memory(reflection_memory)
        
        logger.info(f"💭 Created reflection for cycle {self.cognitive_loop.cycle_count}")
               
        # Update both activity log and location memory with the cycle summary
        await self._update_memories_with_summary(output_values)
        
        # Log key insights if any
        if output_values.get("insights"):
            logger.info(f"  Insights: {output_values['insights']}")
        
        # Clean up stage instructions before leaving
        self._cleanup_stage_instructions()
           
    async def _update_memories_with_summary(self, reflection_outputs: dict):
        """Update both activity log and location memory with cycle summary.
        
        Uses the intelligent cycle_summary from reflection to create both:
        - A temporal history in activity.log
        - A spatial memory at the current location
        
        Args:
            reflection_outputs: The outputs from the reflection brain call
        """
        try:
            import json
            
            # Get the cycle summary from reflection
            cycle_summary = reflection_outputs.get("cycle_summary", "")
            if not cycle_summary:
                # Fallback to insights if no summary
                insights = reflection_outputs.get("insights", "")
                if insights:
                    # Take first sentence/line as summary
                    cycle_summary = insights.split('.')[0].strip()
                else:
                    cycle_summary = "Observed and reflected"
            
            # Get current and previous location from dynamic context
            dynamic_context_file = self.cognitive_loop.memory_dir / "dynamic_context.json"
            current_location = "/personal"
            previous_location = ""
            
            if dynamic_context_file.exists():
                with open(dynamic_context_file, 'r') as f:
                    dynamic_context = json.load(f)
                    current_location = dynamic_context.get("current_location", "/personal")
                    previous_location = dynamic_context.get("previous_location", "")
            
            # === Update Activity Log ===
            # Store in .internal since this is automated/system-generated
            activity_log_file = self.cognitive_loop.memory_dir / "activity.log"
            entries = []
            
            # Load existing entries
            if activity_log_file.exists():
                try:
                    with open(activity_log_file, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                entries.append(line)
                except:
                    entries = []
            
            # Add new entry with cycle number
            new_entry = f"Cycle {self.cognitive_loop.cycle_count:04d}: {cycle_summary}"
            entries.append(new_entry)
            
            # DO NOT TRUNCATE - activity.log should keep complete history
            # Truncation happens only in display (status.txt)
            
            # Write updated activity log with ALL entries
            with open(activity_log_file, 'w') as f:
                f.write('\n'.join(entries))
            
            logger.debug(f"Updated activity log: {new_entry}")
            
            # === Update Location Memory ===
            # Decide which location to remember - prefer previous if we just moved
            location_to_remember = previous_location if previous_location and previous_location != current_location else current_location
            
            # Skip if we're at /personal (not a meaningful location)
            if location_to_remember and location_to_remember != "/personal":
                # Store location memory as a file for easy retrieval during perception
                location_memories_dir = self.cognitive_loop.memory_dir / "location_memories"
                location_memories_dir.mkdir(exist_ok=True)
                
                location_key = location_to_remember.replace('/', '_').strip('_') or 'root'
                memory_file = location_memories_dir / f"{location_key}.json"
                
                # Load existing memories or create new structure
                if memory_file.exists():
                    with open(memory_file, 'r') as f:
                        location_data = json.load(f)
                else:
                    location_data = {
                        "location": location_to_remember,
                        "memories": []
                    }
                
                # Add the cycle summary as location memory
                new_memory = {
                    "summary": cycle_summary,
                    "observation": reflection_outputs.get("lessons_learned", "")[:200] if reflection_outputs.get("lessons_learned") else "",
                    "cycle": self.cognitive_loop.cycle_count,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Keep only last 5 memories per location
                location_data["memories"].insert(0, new_memory)
                location_data["memories"] = location_data["memories"][:5]
                
                # Save updated memories
                with open(memory_file, 'w') as f:
                    json.dump(location_data, f, indent=2)
                
                logger.debug(f"Stored location memory for {location_to_remember}: {cycle_summary}")
                
        except Exception as e:
            logger.error(f"Error updating memories with summary: {e}")
            # Don't fail the reflection stage if memory update fails
        
        # Record stage data for cycle history
        try:
            # Get current working memory snapshot
            working_memory_snapshot = self.memory_system.create_snapshot()
            
            # Record the stage completion
            self.cognitive_loop.cycle_recorder.record_stage(
                stage_name="reflection",
                working_memory=working_memory_snapshot,
                llm_input=thinking_request if 'thinking_request' in locals() else None,
                llm_output=reflection_response if 'reflection_response' in locals() else None,
                stage_output=reflection_outputs if 'reflection_outputs' in locals() else {},
                token_usage=reflection_response.get("token_usage", {}) if 'reflection_response' in locals() else {}
            )
            
            # Also record the reflection data specifically
            if 'reflection_outputs' in locals():
                self.cognitive_loop.cycle_recorder.record_reflection(reflection_outputs)
        except Exception as e:
            logger.debug(f"Failed to record reflection stage: {e}")