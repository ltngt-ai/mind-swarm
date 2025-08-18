"""Simplified knowledge system that uses the existing Knowledge API.

This wraps the existing Knowledge class for stage-specific operations.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Any

# Import the existing Knowledge class from python_modules
from ..python_modules.knowledge import Knowledge

logger = logging.getLogger("Cyber.knowledge.simplified")


class SimplifiedKnowledgeManager:
    """Manages knowledge access through the existing Knowledge API."""
    
    def __init__(self):
        """Initialize the simplified knowledge manager."""
        # Create a dummy memory instance for Knowledge (it needs Memory for init)
        # Knowledge needs _context attribute
        class DummyMemory:
            memory_api = None
            _context = {
                "cyber_id": "unknown",
                "personal": Path("/personal"),
                "memory_dir": Path("/personal/.internal/memory")
            }
            
        self.knowledge = Knowledge(DummyMemory())
        
    def get_stage_instructions(self, stage_name: str) -> Optional[Dict[str, Any]]:
        """Fetch instructions for a specific cognitive stage.
        
        Args:
            stage_name: Name of the stage (observation, decision, execution, reflection, cleanup)
            
        Returns:
            Stage instructions or None if not found
        """
        try:
            # The stage instructions have consistent IDs based on their path
            knowledge_id = f"stages/{stage_name}_stage.yaml"
            
            # Directly get by ID - no caching at cyber level
            # Server should handle caching and invalidation
            result = self.knowledge.get(knowledge_id)
            
            if result:
                return result
                    
        except Exception as e:
            logger.error(f"Failed to fetch stage instructions for {stage_name}: {e}")
            
        return None
        
    def search_knowledge(self, query: str, limit: int = 5) -> list:
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
        
    def get_boot_rom(self) -> Optional[Dict[str, Any]]:
        """Get the boot ROM content for this cyber.
        
        The boot ROM should be copied to /personal/.internal/boot_rom.yaml
        at cyber initialization.
        
        Returns:
            Boot ROM content with metadata and content fields
        """
        boot_rom_path = Path("/personal/.internal/boot_rom.yaml")
        
        if not boot_rom_path.exists():
            logger.warning("Boot ROM not found at expected location")
            return None
            
        try:
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