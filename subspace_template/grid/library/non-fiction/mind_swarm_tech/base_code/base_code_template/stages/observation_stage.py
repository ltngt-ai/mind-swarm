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

from ..memory.memory_blocks import MemoryBlock
from ..memory.memory_types import Priority, ContentType
from ..memory.tag_filter import TagFilter

logger = logging.getLogger("Cyber.stages.observation")


class ObservationStage:
    """Intelligence briefing stage that gathers information and suggests task updates."""
    
    # Knowledge tags to exclude from observation stage context
    KNOWLEDGE_BLACKLIST = {"decision", "execution", "reflect", "cleanup"}
    
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
        
        # Stage-specific memory ID for tracking if instructions are loaded
        self.stage_knowledge_id = None
    
    def _load_stage_instructions(self):
        """Load stage-specific instructions into working memory."""
        stage_file = self.personal / ".internal" / "knowledge" / "observation_stage.md"
        
        if stage_file.exists():
            # Create memory block for stage instructions
            stage_memory = MemoryBlock(
                location=f"personal/.internal/knowledge/observation_stage.md",
                priority=Priority.HIGH,
                confidence=0.9,
                pinned=False,
                metadata={
                    "knowledge_type": "stage_instructions",
                    "stage": "observation",
                    "description": "Instructions for observation stage"
                },
                cycle_count=self.cognitive_loop.cycle_count,
                tags=["observation", "stage_instructions"],
                content_type=ContentType.MARKDOWN
            )
            
            # Try to add to memory
            try:
                self.stage_knowledge_id = self.memory_system.add_memory(stage_memory)
                logger.debug(f"Loaded observation stage instructions with id: {self.stage_knowledge_id}")
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
        reflection_file = self.personal / ".internal" / "memory" / "reflection_on_last_cycle.json"
        try:
            if reflection_file.exists():
                with open(reflection_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.debug(f"Could not read reflection: {e}")
        return None
    
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
        
        This is now an intelligence briefing stage that:
        1. Scans for new observations
        2. Reads actual content of messages and important files
        3. Reviews reflection from last cycle
        4. Analyzes current tasks
        5. Provides detailed briefing with task suggestions
        
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
        
        # Tasks and reflection are already in working memory - no need to read them again
        
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
        
        thinking_request = {
            "signature": {
                "instruction": """You are preparing an intelligence briefing for the Decision stage.

Your working memory already contains current tasks, recent reflections, and context.
Focus on analyzing the new information provided and suggesting task updates.

Based on your analysis, provide:
1. A summary of what's happening
2. Task suggestions (what tasks to create, complete, or update)
3. What should be the focus for this cycle

Format your task suggestions as specific actions:
- "Create task: [summary]" for new tasks
- "Complete task: [task_id]" for tasks that seem done based on reflection
- "Update task: [task_id] - [what to update]" for task modifications

Always start with [[ ## Briefing ## ]]""",
                "inputs": {
                    "working_memory": "Current working memory including tasks and reflections",
                    "new_information": "New messages and observations this cycle"
                },
                "outputs": {
                    "situation_summary": "Brief summary of the current situation",
                    "task_suggestions": "Specific task create/complete/update suggestions",
                    "recommended_focus": "What should be the focus for this cycle"
                },
                "display_field": "situation_summary"
            },
            "input_values": {
                "working_memory": memory_context,
                "new_information": new_information if new_information else "No new messages or observations this cycle"
            },
            "request_id": f"observe_{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        response = await self.brain_interface._use_brain(json.dumps(thinking_request))
        analysis_response = json.loads(response)
        
        # Extract the analysis
        output_values = analysis_response.get("output_values", {})
        
        # 8. Create briefing for Decision stage (only analysis results, not raw data)
        intelligence_briefing = {
            "cycle_count": self.cognitive_loop.cycle_count,
            "situation_summary": output_values.get("situation_summary", "No significant changes"),
            "task_suggestions": output_values.get("task_suggestions", "No task changes suggested"),
            "recommended_focus": output_values.get("recommended_focus", "Continue current activities"),
            "new_message_paths": [msg['path'] for msg in message_contents] if message_contents else [],
            "observation_count": len(observations)
        }
        
        # Write to observation pipeline buffer for Decision stage
        observation_buffer = self.cognitive_loop.get_current_pipeline("observation")
        buffer_file = self.cognitive_loop.personal.parent / observation_buffer.location
        
        with open(buffer_file, 'w') as f:
            json.dump(intelligence_briefing, f, indent=2)
        
        # Touch the memory block so it knows when the file was updated
        self.cognitive_loop.memory_system.touch_memory(observation_buffer.id, self.cognitive_loop.cycle_count)
        
        logger.info(f"📊 Intelligence briefing prepared and written to pipeline")
        
        # Clean up stage instructions before leaving
        self._cleanup_stage_instructions()
        
        return intelligence_briefing