"""Decision Stage V2 - Producing plain text intentions instead of structured actions.

This stage encompasses:
1. Decide - Generate natural language description of what to do

The input is the orientation/reasoning from the observation stage.
The output is a plain text intention describing what the cyber wants to accomplish.
"""

import logging
from typing import Dict, Any, TYPE_CHECKING


import json
import time
from datetime import datetime

if TYPE_CHECKING:
    from ..cognitive_loop import CognitiveLoop
from ..memory.tag_filter import TagFilter
from ..memory import ContentType

logger = logging.getLogger("Cyber.stages.decision_v2")


class DecisionStage:
    """Handles the decision phase of cognition using natural language intentions.
    
    This stage is responsible for:
    - Taking the reasoning from observation stage
    - Deciding what to do in plain language
    - Returning a clear intention for the execution stage to implement
    """
    
    # Knowledge tags to exclude during decision stage
    KNOWLEDGE_BLACKLIST = {
        "low_level_details",
        "observation",  # Don't need observation details
        "implementation_details",
        "api_documentation",  # Don't need API docs when expressing intent
        "execution",  # Execution-specific knowledge for script generation
        "execution_only",  # Python API docs only needed in execution
        "reflection_only",  # Reflection stage specific
        "action_implementation"  # Implementation details for execution stage
    }
    
    def __init__(self, cognitive_loop: 'CognitiveLoop'):
        """Initialize the decision stage.
        
        Args:
            cognitive_loop: Reference to the main cognitive loop
        """
        self.cognitive_loop = cognitive_loop
        self.memory_system = cognitive_loop.memory_system
        self.brain_interface = cognitive_loop.brain_interface
        self.knowledge_manager = cognitive_loop.knowledge_manager
    
    def _load_stage_instructions(self):
        """Load stage instructions from knowledge into memory."""
        stage_data = self.knowledge_manager.get_stage_instructions('decision')
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
                location="/personal/.internal/knowledge_decision_stage",
                confidence=1.0,
                priority=Priority.FOUNDATIONAL,
                metadata=yaml_content,  # This has title, category, tags, content fields
                pinned=False,
                cycle_count=self.cognitive_loop.cycle_count,
                content_type=ContentType.MINDSWARM_KNOWLEDGE
            )
            self.memory_system.add_memory(stage_memory)
            self.stage_knowledge_id = stage_memory.id
            logger.debug("Loaded decision stage instructions into memory")
        else:
            self.stage_knowledge_id = None
    
    def _cleanup_stage_instructions(self):
        """Remove stage instructions from working memory."""
        if hasattr(self, 'stage_knowledge_id') and self.stage_knowledge_id:
            if self.memory_system.remove_memory(self.stage_knowledge_id):
                logger.debug("Removed decision stage instructions from memory")
            self.stage_knowledge_id = None
        
    async def decide(self):
        """Run the decision stage.
        
        Reads the observation from the current pipeline and decides on intentions.
            
        Returns:
            Dict containing the plain text intention and context
        """
        logger.info("=== DECISION STAGE ===")
        
        # Load stage instructions
        self._load_stage_instructions()
                       
        # Update dynamic context - DECIDE phase (brain LLM call)
        self.cognitive_loop._update_dynamic_context(stage="DECISION", phase="DECIDE")
        
        # Create tag filter for decision stage with our blacklist
        tag_filter = TagFilter(blacklist=self.KNOWLEDGE_BLACKLIST)
        
        # Read the full intelligence briefing from observation buffer
        observation_buffer = self.cognitive_loop.get_current_pipeline("observation")
        observation_file = self.cognitive_loop.personal.parent / observation_buffer.location
        
        observation_data = {}
        try:
            with open(observation_file, 'r') as f:
                observation_data = json.load(f)
                logger.debug(f"Read intelligence briefing from observation stage")
        except Exception as e:
            logger.debug(f"Could not read observation buffer: {e}")
        
        # Extract key information from the briefing
        suggested_problem = observation_data.get("recommended_focus", "")
        task_suggestions = observation_data.get("task_suggestions", "")
        
        # Build decision context - goals and tasks come from working memory
        current_task = "Deciding what to do based on current situation, goals and tasks"
        
        decision_context = self.memory_system.build_context(
            max_tokens=self.cognitive_loop.max_context_tokens // 2,
            current_task=current_task,
            selection_strategy="balanced",
            tag_filter=tag_filter,
            exclude_content_types=[]
        )
        
        # Retrieve similar CBR cases using the suggested problem
        cbr_cases = await self._retrieve_cbr_cases(suggested_problem if suggested_problem else decision_context)
        
        # Use brain to generate intention
        logger.info("🤔 Generating intention based on situation...")
        intention_response = await self._generate_intention(decision_context, cbr_cases)
        
        # Extract intention from the response
        output_values = intention_response.get("output_values", {})
        intention = output_values.get("intention", "")
        reasoning = output_values.get("reasoning", "No explicit reasoning provided")
        
        # Log the decision
        if intention:
            logger.info(f"🤔 Generated intention: {intention[:100]}...")
        else:
            logger.info("🤔 No action needed at this time")
        
        # Write to decision pipeline buffer
        decision_content = {
            "intention": intention,
            "reasoning": reasoning,
            "cbr_cases_used": [case.get('case_id', '') for case in cbr_cases] if cbr_cases else []
        }
        
        decision_buffer = self.cognitive_loop.get_current_pipeline("decision")
        buffer_file = self.cognitive_loop.personal.parent / decision_buffer.location
        
        with open(buffer_file, 'w') as f:
            json.dump(decision_content, f, indent=2)
        
        # Touch the memory block so it knows when the file was updated
        self.cognitive_loop.memory_system.touch_memory(decision_buffer.id, self.cognitive_loop.cycle_count)
        
        logger.info(f"💭 Decision intention written to pipeline buffer")
            
    async def _retrieve_cbr_cases(self, problem_or_context: str) -> list:
        """Retrieve similar CBR cases to help with decision making.
        
        Args:
            problem_or_context: Either a specific problem statement or decision context
            
        Returns:
            List of relevant CBR cases
        """
        try:
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
            
            # Use the problem statement directly if it's short, otherwise summarize
            context_summary = problem_or_context[:1000]  # Use first 1000 chars
            
            # Retrieve similar cases
            cases = cbr_api.retrieve_similar_cases(
                context=context_summary,
                limit=3,
                min_score=0.6,
                timeout=3.0
            )
            
            if cases:
                logger.info(f"🔍 Retrieved {len(cases)} similar CBR cases")
                for case in cases:
                    logger.debug(f"  - Case {case.get('case_id', 'unknown')}: score {case.get('weighted_score', 0):.2f}")
                    # Log more details to debug
                    logger.info(f"  CBR Case content - Problem: {case.get('problem_context', 'N/A')[:50]}...")
                    logger.info(f"  CBR Case solution: {case.get('solution', 'N/A')[:50]}...")
            
            return cases
            
        except Exception as e:
            logger.error(f"Failed to retrieve CBR cases: {e}")
            return []
    
    async def _generate_intention(self, memory_context: str, cbr_cases: list) -> Dict[str, Any]:
        """Use brain to generate a plain text intention.
        
        Args:
            memory_context: Working memory context
            cbr_cases: List of similar CBR cases
            
        Returns:
            Dict with intention and metadata
        """
        # Format CBR cases for inclusion in prompt
        cbr_context = ""
        if cbr_cases:
            cbr_context = "\n\n## Similar Past Solutions\n"
            for i, case in enumerate(cbr_cases, 1):
                score = case.get('metadata', {}).get('success_score', 0)               
                cbr_context += f"\n{i}. [Success: {score:.2f}]"
                cbr_context += "\n"
                cbr_context += f"  Problem: {case.get('problem_context', 'N/A')}\n"
                cbr_context += f"  Solution: {case.get('solution', 'N/A')}\n"
                cbr_context += f"  Result: {case.get('outcome', 'N/A')}\n"
            logger.info(f"📚 Added CBR context with {len(cbr_cases)} cases to decision prompt")
            logger.debug(f"CBR context preview: {cbr_context[:200]}...")
        else:
            logger.debug("No CBR cases to add to decision prompt")
        
        # Combine memory context with CBR cases
        full_context = memory_context + cbr_context
        
        # Debug: Log if CBR is actually in the context
        if cbr_cases:
            if "## Similar Past Solutions" in full_context:
                logger.info("✅ CBR cases ARE in the full context being sent to brain")
            else:
                logger.warning("❌ CBR cases NOT found in full context - this is a bug!")
        else:
            logger.debug("No CBR cases available yet (database may be empty)")
        
        thinking_request = {
            "signature": {
                "instruction": """
Review your working memory to understand the current situation and what needs to be done.

If similar past solutions are provided, consider whether they might help with the current situation.
Learn from past successes but adapt to the current context.

Decide what you want to do over 3 scales, goals, tasks and the next cycle.

Describe in plain language what you want to accomplish.
Be specific about your plan but don't worry about implementation details.
Think of this as telling a skilled assistant what you want done, not how to do it.

Always start your output with [[ ## reasoning ## ]]
""",
                "inputs": {
                    "working_memory": "Your complete working memory including the recent orientation and any similar past solutions"
                },
                "outputs": {
                    "reasoning": "Why this intention makes sense given the situation",
                    "intention": "A clear description of what you want to accomplish (or empty string if nothing needed)",
                },
                "display_field": "reasoning"
            },
            "input_values": {
                "working_memory": full_context
            },
            "request_id": f"decide_intention_{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        response = await self.brain_interface._use_brain(json.dumps(thinking_request))
        result = json.loads(response)
        
        # Write to decision pipeline buffer
        logger.info(f"💭 Decision intention written to pipeline buffer")
        
        # Record stage data for cycle history
        try:
            # Get current working memory snapshot
            working_memory_snapshot = self.memory_system.create_snapshot()
            
            # Record the stage completion
            self.cognitive_loop.cycle_recorder.record_stage(
                stage_name="decision",
                working_memory=working_memory_snapshot,
                llm_input=thinking_request,
                llm_output=result,
                stage_output=result.get("output_values", {}),
                token_usage=result.get("token_usage", {})
            )
        except Exception as e:
            logger.debug(f"Failed to record decision stage: {e}")
        
        # Clean up stage instructions before leaving
        self._cleanup_stage_instructions()
        
        return result