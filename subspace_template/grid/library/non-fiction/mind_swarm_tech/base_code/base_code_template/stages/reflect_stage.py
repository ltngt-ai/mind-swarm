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
To help your other Cybers, rate this cycle's solution on a scale from 0.0 to 1.0. Be conservative in your scoring.
This score should represent how well the execution's results addressed the decision's intentions and the observation's suggested problem.

IMPORTANT: Create a single-line summary describing what was accomplished this cycle, including any completed tasks or goals.
""",
                "inputs": {
                    "working_memory": "Your current working memory including execution results"
                },
                "outputs": {
                    "cycle_summary": "A single-line summary of what was accomplished this cycle (keep concise, under 200 chars)",
                    "insights": "Key insights from the execution results",
                    "lessons_learned": "What you learned that will help in future",
                    "knowledge_query": "Suggest a NLP knowledge query that you think will help the next cycle",
                    "solution_score": "How well the execution's results addressed the decision's intentions and the observation's suggested problem"
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
        
        # Extract solution score
        solution_score_str = output_values.get("solution_score", "0.5")
        try:
            # Parse the score, handling various formats
            if isinstance(solution_score_str, (int, float)):
                solution_score = float(solution_score_str)
            else:
                # Extract number from string like "0.8" or "0.8/1.0"
                import re
                match = re.search(r'(\d*\.?\d+)', str(solution_score_str))
                solution_score = float(match.group(1)) if match else 0.5
            solution_score = max(0.0, min(1.0, solution_score))  # Clamp to [0, 1]
        except:
            solution_score = 0.5  # Default to partial success
                
        # Extract execution output if available (truncate to prevent overflow)
        execution_output = ""
        max_output_chars = 2000  # Reasonable limit for diagnostic output
        if last_execution and "results" in last_execution:
            for result in last_execution.get("results", []):
                if result.get("output"):
                    output = result["output"]
                    if len(output) > max_output_chars:
                        # Truncate with indicator
                        execution_output = output[:max_output_chars] + f"\n... (truncated {len(output) - max_output_chars} chars)"
                    else:
                        execution_output = output
                    break
        
        reflection_content = {
            "insights": output_values.get("insights", ""),
            "lessons_learned": output_values.get("lessons_learned", ""),
            "solution_score": solution_score,
            "execution_output": execution_output  # Add print output from execution
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
        
        # Store successful solutions as CBR cases
        await self._store_cbr_case(solution_score, reflection_content)
        
        # Update both activity log and location memory with the cycle summary
        await self._update_memories_with_summary(output_values)
        
        # Log key insights if any
        if output_values.get("insights"):
            logger.info(f"  Insights: {output_values['insights'][:200]}")
        if output_values.get("knowledge_query"):
            logger.info(f"  Knowledge query: {output_values['knowledge_query'][:200]}")
            
        # Execute the suggested knowledge query and add results to working memory
        if output_values.get("knowledge_query"):
            query = output_values["knowledge_query"]
            logger.info(f"🔍 Executing suggested knowledge query: {query[:100]}...")
            
            # Search the knowledge base using the correct method
            results = self.knowledge_manager.remember_knowledge(query, limit=1)
            
            if results:
                # Create a memory block for the knowledge query results
                from ..memory import MemoryBlock, Priority
                
                # Save the results to a file
                knowledge_results_file = self.cognitive_loop.memory_dir / "reflection_knowledge_query_results.json"
                knowledge_data = {
                    "query": query,
                    "timestamp": datetime.now().isoformat(),
                    "cycle_count": self.cognitive_loop.cycle_count,
                    "results": results
                }
                
                with open(knowledge_results_file, 'w') as f:
                    json.dump(knowledge_data, f, indent=2)
                
                # Add to working memory - use regular JSON content type, not KNOWLEDGE
                knowledge_memory = MemoryBlock(
                    location="personal/.internal/memory/reflection_knowledge_query_results.json",
                    priority=Priority.HIGH,
                    pinned=False,
                    metadata={
                        "file_type": "knowledge_results",
                        "query": query[:100],
                        "description": f"Knowledge query results from reflection stage",
                        "result_count": len(results)
                    },
                    cycle_count=self.cognitive_loop.cycle_count,
                    no_cache=True
                )
                
                # Remove old knowledge results if they exist
                knowledge_id = "personal/.internal/memory/reflection_knowledge_query_results.json"
                existing = self.cognitive_loop.memory_system.get_memory(knowledge_id)
                if existing:
                    self.cognitive_loop.memory_system.remove_memory(knowledge_id)
                    
                self.cognitive_loop.memory_system.add_memory(knowledge_memory)
                logger.info(f"✅ Added knowledge query results to working memory")
            
            else:
                logger.info("📚 No knowledge results found for query")
            
        # Store insights to personal knowledge base for long-term memory
        await self._store_insights_to_knowledge(output_values)
        
        # Clean up stage instructions before leaving
        self._cleanup_stage_instructions()
    
    async def _store_cbr_case(self, solution_score: float, reflection_content: dict):
        """Store a CBR case if the solution was successful enough.
        
        Args:
            solution_score: Success score from reflection (0-1)
            reflection_content: The reflection data
            execution_data: The execution pipeline data
        """
      
        try:
            # Get the decision and observation data for context
            decision_buffer = self.cognitive_loop.get_current_pipeline("decision")
            decision_file = self.cognitive_loop.personal.parent / decision_buffer.location
            observation_buffer = self.cognitive_loop.get_current_pipeline("observation")
            observation_file = self.cognitive_loop.personal.parent / observation_buffer.location
            
            # Read pipeline data
            with open(decision_file, 'r') as f:
                decision_data = json.load(f)
            with open(observation_file, 'r') as f:
                observation_data = json.load(f)
            # Get the problem context from observation data
            # Use situation summary as the problem context since that describes what we were dealing with
            problem_context = observation_data.get("situation_summary", "")
            if not problem_context:
                # Fallback to recommended focus if no situation summary
                problem_context = observation_data.get("recommended_focus", "")
            if not problem_context:
                # Final fallback - describe based on task suggestions
                task_suggestions = observation_data.get("task_suggestions", "")
                if task_suggestions:
                    problem_context = f"Task management: {task_suggestions[:200]}"
                else:
                    problem_context = "General cognitive cycle processing"

            # Extract solution (the intention/action taken)
            solution = decision_data.get("intention", "")[:500]
            if not solution:
                solution = "No clear intention recorded"
            
            # Extract outcome from execution results
            outcome = reflection_content.get("lessons_learned", "")
            if isinstance(outcome, list):
                outcome = str(outcome)  # Convert list to string
            
            # Determine tags based on content
            tags = []
            if "file" in solution.lower() or "read" in solution.lower() or "write" in solution.lower():
                tags.append("file_operation")
            if "message" in solution.lower() or "communicate" in solution.lower():
                tags.append("communication")
            if "analyze" in solution.lower() or "understand" in solution.lower():
                tags.append("analysis")
            if "create" in solution.lower() or "generate" in solution.lower():
                tags.append("creation")
            
            # Initialize CBR API
            from ..python_modules.cbr import CBR
            
            # Create a temporary context for CBR
            cbr_context = {
                'cyber_id': self.cognitive_loop.cyber_id,
                'personal_dir': str(self.cognitive_loop.personal)
            }
            
            # Create memory mock for CBR
            class MemoryMock:
                def __init__(self, context):
                    self._context = context
            
            cbr_api = CBR(MemoryMock(cbr_context))
                       
            # Store the case with advice included
            case_id = cbr_api.store_case(
                problem=problem_context,
                solution=solution,
                outcome=outcome,
                success_score=solution_score,
                tags=tags,
                metadata={
                    "cycle_count": self.cognitive_loop.cycle_count,
                    "cbr_cases_used": decision_data.get("cbr_cases_used", []),
                },
                timeout=3.0
            )
            
        except Exception as e:
            logger.error(f"Failed to store CBR case: {e}")
            # Don't fail the reflection stage if CBR storage fails
    
    async def _store_insights_to_knowledge(self, output_values: dict):
        """Store reflection insights to personal knowledge base for long-term memory.
        
        Args:
            output_values: The output from the brain's reflection
        """
        try:
            # Extract key information
            insights = output_values.get("insights", "")
            lessons = output_values.get("lessons_learned", "")
            
            if not insights and not lessons:
                logger.debug("No insights or lessons to store in knowledge base")
                return
            
            # Initialize Knowledge API using Memory context
            from ..python_modules.memory import Memory
            from ..python_modules.knowledge import Knowledge
            
            # Create context for Memory API (matching execution_stage.py structure)
            memory_context = {
                'cognitive_loop': self.cognitive_loop,
                'memory_system': self.memory_system,
                'brain_interface': self.brain_interface,
                'cyber_id': self.cognitive_loop.cyber_id,
                'personal_dir': str(self.cognitive_loop.personal),
                'outbox_dir': str(self.cognitive_loop.outbox_dir),
                'memory_dir': str(self.cognitive_loop.memory_dir),
                'current_location': '/personal'
            }
            memory_instance = Memory(memory_context)
            knowledge_api = Knowledge(memory_instance)
            
            # Categorize the insight based on content
            tags = ["reflection", "insights", f"cycle_{self.cognitive_loop.cycle_count}"]
            
            # Add tags based on content themes
            content_lower = (insights + " " + lessons).lower()
            if "error" in content_lower or "fail" in content_lower:
                tags.append("error_handling")
            if "improve" in content_lower or "better" in content_lower:
                tags.append("improvement")
            if "learn" in content_lower:
                tags.append("lesson")
            if "understand" in content_lower:
                tags.append("understanding")
            if "pattern" in content_lower:
                tags.append("pattern_recognition")
            if "next time" in content_lower or "future" in content_lower:
                tags.append("future_guidance")
            
            # Format the knowledge content - simple and clean
            knowledge_content = f"""Cycle {self.cognitive_loop.cycle_count} Reflection

Insights:
{insights}

Lessons Learned:
{lessons}"""
            
            # Store to personal knowledge base
            knowledge_id = knowledge_api.store(
                content=knowledge_content,
                tags=tags,
                personal=True,  # Store as personal knowledge
                metadata={
                    "cycle_count": self.cognitive_loop.cycle_count,
                    "type": "reflection_insight",
                    "timestamp": datetime.now().isoformat()
                },
                timeout=3.0
            )
                
            if knowledge_id:
                logger.info(f"📚 Stored reflection insights to personal knowledge base: {knowledge_id}")                    
                    
        except Exception as e:
            logger.error(f"Error storing insights to knowledge base: {e}")
            # Don't fail the reflection stage if knowledge storage fails
    
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
            
            # Keep only last 10 entries
            entries = entries[-10:]
            
            # Write updated activity log
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