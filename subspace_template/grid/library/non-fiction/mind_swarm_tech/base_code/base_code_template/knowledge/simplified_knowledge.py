"""Simplified knowledge system that uses the existing Knowledge API.

This wraps the existing Knowledge class for stage-specific operations.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Any

# Import the existing Knowledge class from python_modules
from ..python_modules.knowledge import Knowledge
from .constants import DEFAULT_SEARCH_LIMIT, DEFAULT_PERSONAL_PATH, DEFAULT_MEMORY_DIR_PATH

logger = logging.getLogger("Cyber.knowledge.simplified")


class SimplifiedKnowledgeManager:
    """Manages knowledge access through the existing Knowledge API."""
    
    def __init__(self, memory_context: Optional[Any] = None):
        """Initialize the simplified knowledge manager.
        
        Args:
            memory_context: Optional memory context. If None, creates a minimal context.
        """
        if memory_context is None:
            memory_context = self._create_minimal_context()
        self.knowledge = Knowledge(memory_context)
    
    def _create_minimal_context(self):
        """Create a minimal memory context for standalone usage."""
        class MinimalMemoryContext:
            """Minimal memory context for Knowledge API."""
            memory_api = None
            _context = {
                "cyber_id": "unknown",
                "personal": Path(DEFAULT_PERSONAL_PATH),
                "memory_dir": Path(DEFAULT_MEMORY_DIR_PATH)
            }
        
        return MinimalMemoryContext()
        
    def get_stage_instructions(self, stage_name: str) -> Optional[Dict[str, Any]]:
        """Fetch instructions for a specific cognitive stage.
        
        Args:
            stage_name: Name of the stage (observation, decision, execution, reflection, cleanup)
            
        Returns:
            Stage instructions or None if not found
        """
        try:
            # The stage instructions have consistent IDs based on their path in initial_knowledge
            # The coordinator prefixes with "templates/" and includes the .yaml extension
            knowledge_id = f"templates/stages/{stage_name}_stage.yaml"
            
            # Directly get by ID - no caching at cyber level
            # Server should handle caching and invalidation
            result = self.knowledge.get(knowledge_id)
            
            if result:
                return result
                    
        except Exception as e:
            logger.error(f"Failed to fetch stage instructions for {stage_name}: {e}")
            
        return None

    def remember_knowledge(self, query: str, limit: int = 1) -> str:
        """You the remember shortcut for fetching the results the knowledge base.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of matching knowledge items
        """
        try:
            return self.knowledge.remember(context=query, limit=limit)
        except Exception as e:
            logger.error(f"Knowledge search failed: {e}")
            return ""

    def search_knowledge(self, query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> list:
        """Search the knowledge base.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of matching knowledge items
        """
        try:
            return self.knowledge.search(query=query, limit=limit)
        except Exception as e:
            logger.error(f"Knowledge search failed: {e}")
            return []
        
    def store_knowledge(self, content: str, metadata: Dict[str, Any]) -> bool:
        """Store new knowledge.
        
        Args:
            content: Knowledge content
            metadata: Metadata including tags, category, etc.
            
        Returns:
            Success status
        """
        try:
            tags = metadata.get('tags', [])
            personal = metadata.get('personal', True)
            
            # Remove tags and personal from metadata since they're separate args
            clean_metadata = {k: v for k, v in metadata.items() 
                            if k not in ['tags', 'personal']}
            
            knowledge_id = self.knowledge.store(
                content=content,
                tags=tags,
                personal=personal,
                metadata=clean_metadata
            )
            
            return knowledge_id is not None
                
        except Exception as e:
            logger.error(f"Failed to store knowledge: {e}")
            return False
        
    def get_boot_rom(self, cyber_type: str = "general") -> Optional[Dict[str, Any]]:
        """Get the boot ROM content from the knowledge database.
        
        Boot ROM is now stored in the semantic knowledge database instead of
        as a file. This retrieves it based on the cyber type.
        
        Args:
            cyber_type: Type of cyber ("general" or "io_gateway")
        
        Returns:
            Boot ROM content with metadata and content fields
        """
        try:
            # Determine the knowledge ID based on cyber type
            # The knowledge_id includes the "templates/" prefix added by the coordinator
            if cyber_type == "io_gateway":
                knowledge_id = "templates/concepts/identity/io_gateway_boot_rom.yaml"
            else:
                knowledge_id = "templates/concepts/identity/general_cyber_boot_rom.yaml"
            
            # Retrieve from knowledge database
            result = self.knowledge.get(knowledge_id)
            
            if result:
                logger.info(f"Successfully retrieved boot ROM for {cyber_type} cyber from knowledge DB")
                return result
            else:
                logger.warning(f"Boot ROM not found in knowledge DB for {cyber_type} cyber")
                # Fall back to file-based boot ROM if available for backward compatibility
                boot_rom_path = Path("/personal/.internal/boot_rom.yaml")
                if boot_rom_path.exists():
                    logger.info("Falling back to file-based boot ROM")
                    import yaml
                    with open(boot_rom_path, 'r') as f:
                        data = yaml.safe_load(f)
            
            # Validate new pure YAML format - fields at top level
            if not isinstance(data, dict):
                logger.error("Boot ROM is not a valid YAML dictionary")
                return None
            
            # Boot ROM uses the new format with fields at top level
            # No nested metadata structure anymore
                
            return data
        except Exception as e:
            logger.error(f"Failed to load boot ROM: {e}")
            return None