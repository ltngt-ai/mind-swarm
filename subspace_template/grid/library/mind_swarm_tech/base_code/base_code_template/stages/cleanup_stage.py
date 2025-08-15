"""Cleanup Stage - Memory and system maintenance.

This stage performs cleanup and maintenance tasks to keep the cyber's
memory and file system organized and efficient.

The cleanup stage runs at the end of each cognitive cycle to:
- Remove obsolete observations
- Clean up expired memories
- Manage memory budget
- Clean up old script execution files
"""

import logging
import json
from typing import Dict, Any, Optional

from ..memory.tag_filter import TagFilter

logger = logging.getLogger("Cyber.stages.cleanup")


class CleanupStage:
    """Handles the cleanup and maintenance phase of cognition.
    
    This stage is responsible for:
    - Identifying and removing obsolete observations
    - Cleaning up expired memories
    - Managing memory budget to stay within token limits
    - Removing old script execution files
    - Performing other maintenance tasks
    """
    
    # Knowledge tags to exclude during cleanup stage
    # We focus on maintenance and system health, not action details
    KNOWLEDGE_BLACKLIST = {
        "action_guide", 
        "action_implementation", 
        "execution", 
        "procedures", 
        "tools"
    }
    
    def __init__(self, cognitive_loop):
        """Initialize the cleanup stage.
        
        Args:
            cognitive_loop: The parent cognitive loop instance
        """
        self.cognitive_loop = cognitive_loop
        self.memory_system = cognitive_loop.memory_system
        self.brain = cognitive_loop.brain_interface
        self.max_context_tokens = cognitive_loop.max_context_tokens
        
    async def cleanup(self, cycle_count: int):
        """Perform cleanup and maintenance tasks.
        Args:
            cycle_count: Current cycle number            
        """
        logger.debug(f"Starting cleanup for cycle {cycle_count}")
        
        results = {
            "cycle": cycle_count,
            "obsolete_observations": [],
            "obsolete_memories": [],
            "expired_count": 0,
            "old_observations_count": 0,
            "script_files_cleaned": 0
        }
        
        # Get context for intelligent cleanup decisions
        memory_context = self.memory_system.build_context(
            max_tokens=self.max_context_tokens // 4,  # Smaller context for cleanup
            current_task="Identifying obsolete memories and observations for cleanup",
            selection_strategy="recent",
            tag_filter=TagFilter(blacklist=self.KNOWLEDGE_BLACKLIST),
            exclude_types=[]
        )
        
        logger.debug(f"Built cleanup context with {len(memory_context)} chars")
        
        # Use brain to identify what to clean up
        logger.debug("Calling _identify_cleanup_targets...")
        cleanup_decisions = await self._identify_cleanup_targets(memory_context)
        logger.debug(f"Cleanup decisions: {cleanup_decisions}")
        
        if cleanup_decisions:
            # Clean up identified obsolete observations
            obsolete_observations = cleanup_decisions.get("obsolete_observations", [])
            for obs_id in obsolete_observations:
                if self.memory_system.remove_memory(obs_id):
                    logger.debug(f"🧹 Removed obsolete observation: {obs_id}")
                    results["obsolete_observations"].append(obs_id)
            
            # Clean up identified obsolete memory blocks
            obsolete_memories = cleanup_decisions.get("obsolete_memories", [])
            for mem_id in obsolete_memories:
                if self.memory_system.remove_memory(mem_id):
                    logger.debug(f"🧹 Removed obsolete memory: {mem_id}")
                    results["obsolete_memories"].append(mem_id)
        
        # Also do automatic cleanup of expired memories
        expired = self.memory_system.cleanup_expired()
        old_observations = self.memory_system.cleanup_old_observations(max_age_seconds=1800)
        
        results["expired_count"] = expired
        results["old_observations_count"] = old_observations
        
        if expired or old_observations:
            logger.info(f"🧹 Cleaned up {expired} expired, {old_observations} old memories")
        
        # Clean up old script execution files
        script_files_cleaned = await self._cleanup_old_script_executions()
        results["script_files_cleaned"] = script_files_cleaned
        
        if script_files_cleaned > 0:
            logger.info(f"🧹 Cleaned up {script_files_cleaned} old script execution files")
        
        # Log cleanup completion
        total_cleaned = (len(results["obsolete_observations"]) + 
                        len(results["obsolete_memories"]) + 
                        expired + old_observations + script_files_cleaned)
        
        if total_cleaned > 0:
            logger.info(f"✨ Cleanup completed for cycle {cycle_count}: {total_cleaned} items cleaned")
    
    async def _cleanup_old_script_executions(self, max_age_minutes: int = 30, keep_recent: int = 10) -> int:
        """Clean up old script execution files from action_results directory.
        
        Args:
            max_age_minutes: Maximum age in minutes before files are eligible for cleanup
            keep_recent: Always keep at least this many recent files
            
        Returns:
            Number of files cleaned up
        """
        import time
        
        action_results_dir = self.cognitive_loop.memory_dir / "action_results"
        if not action_results_dir.exists():
            return 0
        
        # Get all script execution files
        script_files = list(action_results_dir.glob("script_execution_*.json"))
        if len(script_files) <= keep_recent:
            return 0  # Don't clean up if we have fewer than the minimum to keep
        
        # Sort by modification time (newest first)
        script_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        # Always keep the most recent files
        files_to_check = script_files[keep_recent:]
        
        current_time = time.time()
        max_age_seconds = max_age_minutes * 60
        cleaned_count = 0
        
        for file_path in files_to_check:
            try:
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    # Remove associated memory if it exists
                    memory_id = f"memory:{file_path.relative_to(self.cognitive_loop.personal.parent)}"
                    if self.memory_system.remove_memory(memory_id):
                        logger.debug(f"Removed memory for old script execution: {memory_id}")
                    
                    # Delete the file
                    file_path.unlink()
                    cleaned_count += 1
                    logger.debug(f"Deleted old script execution file: {file_path.name}")
            except Exception as e:
                logger.error(f"Error cleaning up script file {file_path}: {e}")
        
        return cleaned_count
    
    async def _identify_cleanup_targets(self, memory_context: str) -> Optional[Dict[str, Any]]:
        """Use brain to identify what needs cleanup.
        
        Args:
            memory_context: Working memory context for cleanup decisions
            
        Returns:
            Dict with cleanup targets or None
        """
        import time
        from datetime import datetime
        
        logger.debug("_identify_cleanup_targets called")
        
        thinking_request = {
            "signature": {
                "instruction": """
Review your working memory to identify items that can be cleaned up.
Each memory has a cycle_count showing when it was created.
Look for:
1. Old observations from many cycles ago that are no longer relevant
2. Duplicate observations about the same thing
3. Memories that no longer need to be in working memory
4. Observations about files that no longer exist
5. Duplicate memories

Only suggest cleanup for items that are truly obsolete and no longer needed.
Be conservative - when in doubt, keep the memory.
""",
                "inputs": {
                    "working_memory": "Your current working memory with all items including their cycle counts"
                },
                "outputs": {
                    "reasoning": "Brief explanation of cleanup decisions",
                    "obsolete_observations": "JSON array of observation IDs that can be removed (e.g. [\"obs_123\", \"obs_456\"])",
                    "obsolete_memories": "JSON array of other memory IDs that can be removed"
                },
                "display_field": "reasoning"
            },
            "input_values": {
                "working_memory": memory_context
            },
            "request_id": f"cleanup_{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        start_time = time.time()
        response = await self.brain._use_brain(json.dumps(thinking_request))
        elapsed = time.time() - start_time
        logger.debug(f"Brain cleanup identification took {elapsed:.2f}s")
        
        if response:
            try:
                result = json.loads(response)
                output_values = result.get("output_values", {})
                logger.debug(f"Cleanup identification result: {output_values}")
                
                # Parse the cleanup targets
                obsolete_observations = output_values.get("obsolete_observations", [])
                obsolete_memories = output_values.get("obsolete_memories", [])
                
                # Parse JSON strings if needed
                if isinstance(obsolete_observations, str):
                    try:
                        obsolete_observations = json.loads(obsolete_observations)
                    except:
                        obsolete_observations = []
                
                if isinstance(obsolete_memories, str):
                    try:
                        obsolete_memories = json.loads(obsolete_memories)
                    except:
                        obsolete_memories = []
                
                return {
                    "obsolete_observations": obsolete_observations,
                    "obsolete_memories": obsolete_memories,
                    "reasoning": output_values.get("reasoning", "")
                }
            except Exception as e:
                logger.warning(f"Failed to parse brain response: {e}")
                return None
        else:
            logger.warning("No response from brain")
            return None