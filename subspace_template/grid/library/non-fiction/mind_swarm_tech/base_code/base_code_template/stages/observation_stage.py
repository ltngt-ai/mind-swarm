"""Observation stage for the cognitive loop.

This stage performs intelligence gathering and briefing:
1. Scans for new observations (messages, files, changes)
2. Reads actual content of important items
3. Reviews current tasks and suggests updates
4. Provides comprehensive briefing to Decision stage
"""

import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
# Avoid server package dependency in sandbox; use env defaults.
try:  # pragma: no cover
    from mind_swarm.core.config import KNOWLEDGE_QUERY_TRUNCATE_CHARS as _TRUNC
except Exception:
    import os
    try:
        _TRUNC = int(os.environ.get("KNOWLEDGE_QUERY_TRUNCATE_CHARS", "400"))
    except Exception:
        _TRUNC = 400
KNOWLEDGE_QUERY_TRUNCATE_CHARS = _TRUNC

from ..memory.memory_blocks import MemoryBlock
from ..memory.memory_types import Priority, ContentType
from ..memory.tag_filter import TagFilter

logger = logging.getLogger("Cyber.stages.observation")


class ObservationStage:
    """Intelligence briefing stage that gathers information and suggests task updates."""
    
    # Knowledge tags to exclude from observation stage context
    KNOWLEDGE_BLACKLIST = {"decision", "execution", "reflect"}
    
    def __init__(self, cognitive_loop):
        """Initialize the observation stage.
        
        Args:
            cognitive_loop: Reference to the main cognitive loop
        """
        self.cognitive_loop = cognitive_loop
        self.memory_system = cognitive_loop.memory_system
        self.brain_interface = cognitive_loop.brain_interface
        self.environment_scanner = cognitive_loop.environment_scanner
        self.personal = cognitive_loop.personal
        self.knowledge_manager = cognitive_loop.knowledge_manager
        
        # Stage-specific memory ID for tracking if instructions are loaded
        self.stage_knowledge_id = None
    
    def _load_stage_instructions(self):
        """Load stage instructions from knowledge into memory."""
        stage_data = self.knowledge_manager.get_stage_instructions('observation')
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
                location="/personal/.internal/knowledge_observation_stage",
                confidence=1.0,
                priority=Priority.FOUNDATIONAL,
                metadata=yaml_content,  # This has title, category, tags, content fields
                pinned=False,
                cycle_count=self.cognitive_loop.cycle_count,
                content_type=ContentType.MINDSWARM_KNOWLEDGE
            )
            self.memory_system.add_memory(stage_memory)
            self.stage_knowledge_id = stage_memory.id
            logger.debug("Loaded observation stage instructions into memory")
        else:
            logger.warning("No stage instructions found for observation stage")
            self.stage_knowledge_id = None
    
    def _cleanup_stage_instructions(self):
        """Remove stage instructions from working memory."""
        if hasattr(self, 'stage_knowledge_id') and self.stage_knowledge_id:
            if self.memory_system.remove_memory(self.stage_knowledge_id):
                logger.debug("Removed observation stage instructions from memory")
            self.stage_knowledge_id = None
    
    def _read_message_content(self, message_path: str) -> Optional[Dict[str, Any]]:
        """Read the full content of a message file.
        
        Args:
            message_path: Path to the message file
            
        Returns:
            Message data dictionary or None if can't read
        """
        try:
            message_file = Path(message_path)
            if message_file.exists():
                with open(message_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.debug(f"Could not read message {message_path}: {e}")
        return None
    
    def _read_reflection(self) -> Optional[Dict[str, Any]]:
        """Read the reflection from last cycle.
        
        Returns:
            Reflection data or None
        """
        # Try to get from knowledge database first
        try:
            from ..python_modules.reflection_knowledge import ReflectionKnowledge
            from ..python_modules.memory import Memory
            from ..python_modules.knowledge import Knowledge
            
            # Create memory context for Knowledge API
            memory_context = {
                'cognitive_loop': self.cognitive_loop,
                'memory_system': self.cognitive_loop.memory_system,
                'brain_interface': None,
                'cyber_id': self.cognitive_loop.cyber_id,
                'personal_dir': self.cognitive_loop.memory_dir.parent,
                'outbox_dir': self.cognitive_loop.memory_dir.parent / 'outbox',
                'memory_dir': self.cognitive_loop.memory_dir,
                'current_location': '/personal'
            }
            
            # Create Memory API instance, then Knowledge API
            memory_api = Memory(memory_context)
            knowledge_api = Knowledge(memory_api)
            reflection_knowledge = ReflectionKnowledge(knowledge_api)
            
            # Get the most recent reflection
            recent_reflections = reflection_knowledge.get_recent_reflections(limit=1)
            if recent_reflections:
                latest = recent_reflections[0]
                return {
                    "insights": latest.get("insights", ""),
                    "lessons_learned": latest.get("lessons_learned", "")
                }
        except Exception as e:
            logger.debug(f"Could not read reflection from knowledge DB: {e}")
        
        # No file fallback - we only use knowledge DB now
        return None
    
    def _query_semantic_knowledge(self, situation_summary: str, recommended_focus: str) -> Dict[str, Any]:
        """Query the semantic database for relevant past experiences and knowledge.
        
        Args:
            situation_summary: Current situation description
            recommended_focus: What we should focus on
            
        Returns:
            Dictionary containing relevant past experiences, answered questions, and patterns
        """
        learning_context = {
            "past_experiences": [],
            "relevant_questions": [],
            "successful_strategies": [],
            "knowledge_gaps": []
        }
        
        try:
            # Search for relevant past experiences based on the current situation
            if situation_summary:
                # Search for similar situations
                situation_results = self.knowledge_manager.search_knowledge(
                    query=situation_summary,
                    limit=3
                )
                
                # Filter for execution results and past experiences
                for result in situation_results:
                    if result.get('metadata', {}).get('category') == 'execution_result':
                        learning_context["past_experiences"].append({
                            'content': result.get('content', ''),
                            'relevance': result.get('relevance', 0.0)
                        })
                    elif 'strategy' in result.get('metadata', {}).get('tags', []):
                        learning_context["successful_strategies"].append({
                            'content': result.get('content', ''),
                            'relevance': result.get('relevance', 0.0)
                        })
            
            # Search for knowledge related to recommended focus
            if recommended_focus:
                focus_results = self.knowledge_manager.search_knowledge(
                    query=recommended_focus,
                    limit=2
                )
                
                # Look for relevant questions or guidance
                for result in focus_results:
                    if 'question' in result.get('metadata', {}).get('tags', []):
                        learning_context["relevant_questions"].append({
                            'content': result.get('content', ''),
                            'relevance': result.get('relevance', 0.0)
                        })
            
            # Identify knowledge gaps (areas without much knowledge)
            # This is simple for now - if we found very little, it's a gap
            total_found = (len(learning_context["past_experiences"]) + 
                          len(learning_context["successful_strategies"]) +
                          len(learning_context["relevant_questions"]))
            
            if total_found < 2:
                learning_context["knowledge_gaps"].append(
                    "Limited knowledge about current situation - consider exploring and documenting findings"
                )
                
        except Exception as e:
            logger.debug(f"Failed to query semantic knowledge: {e}")
            # Return the empty context rather than crashing
        
        return learning_context
    
    def _formulate_questions(self, situation_summary: str, learning_context: Dict[str, Any]) -> List[str]:
        """Formulate questions based on current situation and knowledge gaps.
        
        Args:
            situation_summary: Current situation
            learning_context: Context from semantic queries
            
        Returns:
            List of questions to explore
        """
        questions = []
        
        try:
            # If we have knowledge gaps, formulate questions about them
            for gap in learning_context.get("knowledge_gaps", []):
                if "No prior experience" in gap:
                    questions.append(f"What should I know about {situation_summary[:50]}?")
                elif "No answered questions" in gap:
                    topic = gap.split(":")[-1].strip() if ":" in gap else "this situation"
                    questions.append(f"What are the key considerations for {topic}?")
            
            # If we found past experiences but they're not highly relevant, ask for clarification
            past_exp = learning_context.get("past_experiences", [])
            if past_exp and all(exp.get("relevance", 0) < 0.8 for exp in past_exp):
                questions.append("How does this situation differ from my past experiences?")
            
            # If no successful strategies found, ask for guidance
            if not learning_context.get("successful_strategies"):
                questions.append("What strategies have worked for similar situations?")
                
        except Exception as e:
            logger.debug(f"Error formulating questions: {e}")
            
        return questions[:3]  # Limit to top 3 questions
    
    def _get_current_tasks(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get current task status.
        
        Returns:
            Dictionary with 'active', 'blocked', and 'completed' task lists
        """
        tasks = {
            "active": [],
            "blocked": [],
            "completed": []
        }
        
        tasks_dir = self.personal / ".internal" / "tasks"
        
        # Read active tasks
        active_dir = tasks_dir / "active"
        if active_dir.exists():
            for task_file in active_dir.glob("task_*.json"):
                try:
                    with open(task_file, 'r') as f:
                        task_data = json.load(f)
                        tasks["active"].append(task_data)
                except Exception:
                    pass
        
        # Read blocked tasks
        blocked_dir = tasks_dir / "blocked"
        if blocked_dir.exists():
            for task_file in blocked_dir.glob("task_*.json"):
                try:
                    with open(task_file, 'r') as f:
                        task_data = json.load(f)
                        tasks["blocked"].append(task_data)
                except Exception:
                    pass
        
        # Read recent completed tasks (last 5)
        completed_dir = tasks_dir / "completed"
        if completed_dir.exists():
            completed_files = sorted(completed_dir.glob("task_*.json"), 
                                    key=lambda x: x.stat().st_mtime, 
                                    reverse=True)[:5]
            for task_file in completed_files:
                try:
                    with open(task_file, 'r') as f:
                        task_data = json.load(f)
                        tasks["completed"].append(task_data)
                except Exception:
                    pass
        
        return tasks
    
    async def observe(self):
        """OBSERVE - Gather intelligence and provide comprehensive briefing.
        
        This is an intelligence briefing stage that:
        1. Scans for new observations
        2. Reads actual content of messages and important files
        3. Reviews reflection from last cycle
        4. Analyzes current tasks
        
        Returns:
            Briefing data for Decision stage
        """
        logger.info("=== OBSERVATION STAGE (Intelligence Briefing) ===")
        logger.info("📊 Gathering intelligence and preparing briefing...")
        
        # Load stage instructions into memory if not already present
        self._load_stage_instructions()
        
        # 1. Scan environment for new observations
        logger.info("📡 Scanning for new observations...")
        self.cognitive_loop._update_dynamic_context(stage="OBSERVATION", phase="SCAN")
        observations = self.environment_scanner.scan_environment(
            full_scan=False, 
            cycle_count=self.cognitive_loop.cycle_count
        )
        
        # 2. Read actual content of new messages
        message_contents = []
        if observations:
            logger.info(f"📋 Found {len(observations)} new observations")
            for obs in observations:
                if obs.get('observation_type') == 'new_message' and 'path' in obs:
                    msg_content = self._read_message_content(obs['path'])
                    if msg_content:
                        message_contents.append({
                            "from": msg_content.get('from', 'unknown'),
                            "subject": msg_content.get('subject', 'No subject'),
                            "content": msg_content.get('content', ''),
                            "timestamp": msg_content.get('timestamp', ''),
                            "path": obs['path']
                        })
            
        # 5. Build comprehensive context for analysis
        self.cognitive_loop._update_dynamic_context(stage="OBSERVATION", phase="ANALYZE")
        
        # Create tag filter for observation stage
        tag_filter = TagFilter(blacklist=self.KNOWLEDGE_BLACKLIST)
        
        # Build working memory context
        memory_context = self.memory_system.build_context(
            max_tokens=self.cognitive_loop.max_context_tokens // 2,
            current_task="Analyzing situation and preparing intelligence briefing",
            selection_strategy="balanced",
            tag_filter=tag_filter,
            exclude_content_types=[]
        )
        
        # 6. Prepare only NEW information not in working memory
        new_information = ""
        if message_contents:
            new_information += "=== NEW MESSAGES ===\n"
            for msg in message_contents:
                new_information += f"From: {msg['from']}\n"
                new_information += f"Subject: {msg['subject']}\n"
                new_information += f"Content: {msg['content']}\n\n"
        
        if observations:
            new_information += f"=== OBSERVATIONS ({len(observations)} total) ===\n"
            for obs in observations[:5]:  # Limit to avoid token waste
                new_information += f"- {obs.get('observation_type')}: {obs.get('message', '')[:100]}\n"
        
        # 7. Use brain to analyze and suggest task updates
        logger.info("🧠 Analyzing intelligence and preparing briefing...")

        # Build concise knowledge context related to new information and location
        try:
            # Only truncate the query string if a positive limit is configured
            q = new_information
            if new_information and KNOWLEDGE_QUERY_TRUNCATE_CHARS and KNOWLEDGE_QUERY_TRUNCATE_CHARS > 0:
                q = new_information[:KNOWLEDGE_QUERY_TRUNCATE_CHARS]
            knowledge_context = self.cognitive_loop.knowledge_context.build(
                stage="observation",
                queries=[q] if new_information else ["current situation"],
                limit=3,
                budget_chars=800,
                blacklist_tags=self.KNOWLEDGE_BLACKLIST,
            )
        except Exception:
            knowledge_context = ""

        thinking_request = {
            "signature": {
                "instruction": """
You are preparing an intelligence briefing for the Decision stage.
Your working memory already contains current task, recent reflections, and context.
Focus on analyzing the new information provided and suggesting what to do regarding tasks and todos.
""",
                "inputs": {
                    "working_memory": "Current working memory including tasks and reflections",
                    "new_information": "New messages and observations this cycle",
                    "helpful_knowledge": "Concise relevant knowledge for this situation (may be empty)"
                },
                "outputs": {
                    "situation_summary": "Brief summary of the current situation",
                    "recommended_focus": "What should be the focus for this cycle"
                },
                "display_field": "situation_summary"
            },
            "input_values": {
                "working_memory": memory_context,
                "new_information": new_information if new_information else "No new messages or observations this cycle",
                "helpful_knowledge": knowledge_context
            },
            "request_id": f"observe_{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        response = await self.brain_interface._use_brain(json.dumps(thinking_request))
        analysis_response = json.loads(response)
        
        # Extract the analysis
        output_values = analysis_response.get("output_values", {})
        results = ""
        if output_values.get("recommended_focus"):
            query = output_values["recommended_focus"]
            results = self.knowledge_manager.remember_knowledge(query, limit=1)
        
        # 8. Query semantic knowledge for learning context
        logger.info("🔍 Querying semantic knowledge for relevant experiences...")
        situation_summary = output_values.get("situation_summary", "")
        recommended_focus = output_values.get("recommended_focus", "")
        
        learning_context = self._query_semantic_knowledge(situation_summary, recommended_focus)
        
        # 9. Formulate questions based on knowledge gaps
        questions_to_explore = self._formulate_questions(situation_summary, learning_context)
        
        # Log learning insights
        if learning_context["past_experiences"]:
            logger.info(f"📚 Found {len(learning_context['past_experiences'])} relevant past experiences")
        if learning_context["successful_strategies"]:
            logger.info(f"✅ Found {len(learning_context['successful_strategies'])} successful strategies")
        if questions_to_explore:
            logger.info(f"❓ Formulated {len(questions_to_explore)} questions to explore")

        # 10. Create briefing for Decision stage (now includes learning context)
        intelligence_briefing = {
            "cycle_count": self.cognitive_loop.cycle_count,
            "situation_summary": output_values.get("situation_summary", "No significant changes"),
            "recommended_focus": output_values.get("recommended_focus", "Continue current activities"),
            "new_message_paths": [msg['path'] for msg in message_contents] if message_contents else [],
            "observation_count": len(observations),
            "recommended_focus_knowledge": results,
            "learning_context": learning_context,
            "questions_to_explore": questions_to_explore,
        }
        
        # Store in knowledge database
        try:
            from ..python_modules.pipeline_knowledge import PipelineKnowledge
            from ..python_modules.memory import Memory
            from ..python_modules.knowledge import Knowledge
            
            # Create memory context for Knowledge API
            memory_context = {
                'cognitive_loop': self.cognitive_loop,
                'memory_system': self.cognitive_loop.memory_system,
                'brain_interface': None,
                'cyber_id': self.cognitive_loop.cyber_id,
                'personal_dir': self.cognitive_loop.memory_dir.parent,
                'outbox_dir': self.cognitive_loop.memory_dir.parent / 'outbox',
                'memory_dir': self.cognitive_loop.memory_dir,
                'current_location': '/personal'
            }
            
            # Create Memory API instance, then Knowledge API
            memory_api = Memory(memory_context)
            knowledge_api = Knowledge(memory_api)
            # Pass context to PipelineKnowledge so it has cyber_id
            pipeline_knowledge = PipelineKnowledge(memory_context)
            
            buffer_id = pipeline_knowledge.store_stage_output(
                stage="observation",
                cycle_number=self.cognitive_loop.cycle_count,
                output=intelligence_briefing
            )
            logger.debug(f"Stored observation output in knowledge DB: {buffer_id}")
        except Exception as e:
            logger.error(f"Failed to store observation in knowledge DB: {e}")
        
        logger.info(f"📊 Intelligence briefing prepared and written to pipeline")
        
        # Record stage data for cycle history
        try:
            # Get current working memory snapshot
            working_memory_snapshot = self.memory_system.create_snapshot()
            
            # Record the stage completion
            self.cognitive_loop.cycle_recorder.record_stage(
                stage_name="observation",
                working_memory=working_memory_snapshot,
                llm_input=thinking_request,
                llm_output=analysis_response,
                stage_output=intelligence_briefing,
                token_usage=analysis_response.get("token_usage", {})
            )
        except Exception as e:
            logger.debug(f"Failed to record observation stage: {e}")
        
        # Clean up stage instructions before leaving
        self._cleanup_stage_instructions()
        
        return intelligence_briefing
