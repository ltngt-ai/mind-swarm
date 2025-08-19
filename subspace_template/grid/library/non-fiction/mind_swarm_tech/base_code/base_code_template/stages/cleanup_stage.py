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
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..cognitive_loop import CognitiveLoop
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
    
    def __init__(self, cognitive_loop: 'CognitiveLoop'):
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
            exclude_content_types=[]
        )
        
        logger.debug(f"Built cleanup context with {len(memory_context)} chars")
        
        # Use brain to identify what to clean up
        logger.debug("Calling _identify_cleanup_targets...")
        cleanup_decisions = await self._identify_cleanup_targets(memory_context)
        logger.debug(f"Cleanup decisions: {cleanup_decisions}")
        
        if cleanup_decisions:          
            # Clean up identified obsolete memory blocks
            obsolete_memories = cleanup_decisions.get("obsolete_memories", [])
            for mem_id in obsolete_memories:
                if self.memory_system.remove_memory(mem_id):
                    logger.debug(f"🧹 Removed obsolete memory: {mem_id}")
                    results["obsolete_memories"].append(mem_id)
        
        # Also do automatic cleanup of expired memories
        expired = self.memory_system.cleanup_expired()
        
        results["expired_count"] = expired
        if expired:
            logger.info(f"🧹 Cleaned up {expired} expired memories")
        
        
        # Log cleanup completion
        total_cleaned = len(results["obsolete_memories"]) + expired
        if total_cleaned > 0:
            logger.info(f"✨ Cleanup completed for cycle {cycle_count}: {total_cleaned} items cleaned")
    
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
1. Memories that no longer need to be in working memory
2. Duplicate memories
""",
                "inputs": {
                    "working_memory": "Your current working memory with all items including their cycle counts"
                },
                "outputs": {
                    "reasoning": "Brief explanation of cleanup decisions",
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
        
        response = await self.brain._use_brain(json.dumps(thinking_request))
        if response:
            try:
                result = json.loads(response)
                output_values = result.get("output_values", {})
                logger.debug(f"Cleanup identification result: {output_values}")
                
                # Parse the cleanup targets
                obsolete_memories = output_values.get("obsolete_memories", [])
                                
                if isinstance(obsolete_memories, str):
                    try:
                        obsolete_memories = json.loads(obsolete_memories)
                    except:
                        obsolete_memories = []
                
                return {
                    "obsolete_memories": obsolete_memories,
                    "reasoning": output_values.get("reasoning", "")
                }
            except Exception as e:
                logger.warning(f"Failed to parse brain response: {e}")
                return None
        else:
            logger.warning("No response from brain")
            return None