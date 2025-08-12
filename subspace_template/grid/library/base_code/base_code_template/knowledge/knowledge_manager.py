"""Knowledge management system for the cognitive loop.

This module provides comprehensive knowledge management including
loading, organizing, querying, and managing knowledge from various sources.
"""

import json
import yaml
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Set

from .rom_loader import ROMLoader
from ..utils.file_utils import FileManager
from ..utils.cognitive_utils import CognitiveUtils
from ..memory import Priority

logger = logging.getLogger("Cyber.knowledge")


class KnowledgeManager:
    """Manages all knowledge operations for the cognitive system."""
    
    def __init__(self, library_path: Path = Path("/grid/library"), 
                 cyber_type: str = 'general'):
        """Initialize knowledge manager.
        
        Args:
            library_path: Path to the library directory
            cyber_type: Type of Cyber for specific knowledge
        """
        self.library_path = library_path
        self.cyber_type = cyber_type
        self.rom_loader = ROMLoader(library_path)
        self.file_manager = FileManager()
        self.cognitive_utils = CognitiveUtils()
        
        # Knowledge storage
        self.loaded_knowledge = {}
        self.knowledge_index = {}
        self.knowledge_stats = {
            "total_items": 0,
            "by_category": {},
            "by_source": {},
            "last_updated": datetime.now()
        }
        
    def initialize(self) -> bool:
        """Initialize the knowledge system.
        
        Returns:
            True if initialized successfully
        """
        try:
            # Load ROM data
            self._load_rom_knowledge()
            
            # Load action knowledge
            self._load_action_knowledge()
            
            # Build knowledge index
            self._build_knowledge_index()
            
            logger.info(f"Knowledge system initialized with {self.knowledge_stats['total_items']} items")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize knowledge system: {e}")
            return False
    
    def load_rom_into_memory(self, memory_manager) -> int:
        """Load ROM knowledge into working memory as pinned memories.
        
        This loads ROM as regular KnowledgeMemoryBlock instances that are pinned,
        making them behave like ROM but using the standard memory system.
        
        Args:
            memory_manager: The Cyber's working memory manager
            
        Returns:
            Number of ROM items loaded
        """
        rom_items = self.get_rom_content()
                    
        # Add each ROM item to working memory
        rom_count = 0
        for rom_item in rom_items:
            # Import here to avoid circular imports
            from ..memory import FileMemoryBlock, MemoryType
            
            metadata = rom_item.get("metadata", {})
            content = rom_item.get("content", "")
            
            # Create knowledge memory block that is pinned
            # Use the actual file path from the ROM item
            file_path = rom_item.get('file_path', f"knowledge/sections/rom/unknown/{rom_item.get('id', 'unknown')}")
            if not file_path.startswith('/'):
                file_path = '/' + file_path
            
            knowledge_memory = FileMemoryBlock(
                location=file_path,  # Use actual file path
                confidence=1.0,  # ROM is always highly confident
                priority=Priority(metadata.get("priority", 1)),  # ROM is critical
                metadata=metadata,  # Keep original metadata for content
                pinned=True,  # ROM is always pinned so it's never removed
                cycle_count=0,  # ROM loaded at initialization
                block_type=MemoryType.KNOWLEDGE  # Mark as knowledge type
            )
            
            # Add content to metadata for brain access
            knowledge_memory.metadata["content"] = content
            knowledge_memory.metadata["is_rom"] = True
            
            memory_manager.add_memory(knowledge_memory)
            rom_count += 1
            
        logger.info(f"Loaded {rom_count} ROM items into working memory as pinned memories")
        return rom_count
    
           
    def _load_rom_knowledge(self):
        """Load ROM knowledge into the system."""
        # Load all ROM for this Cyber type
        rom_data = self.rom_loader.get_all_rom(self.cyber_type)
        
        for rom_id, rom_content in rom_data.items():
            # Extract content and metadata
            content = self.rom_loader.extract_rom_content(rom_content)
            metadata = self.rom_loader.get_rom_metadata(rom_content)
            
            # Store in knowledge system
            knowledge_item = {
                "id": rom_id,
                "content": content,
                "metadata": metadata,
                "source": "rom",
                "loaded_at": datetime.now(),
                "file_path": rom_content.get('file_path')  # Include the file path from ROM loader
            }
            
            self.loaded_knowledge[rom_id] = knowledge_item
            self._update_stats(knowledge_item)
            
    def _load_action_knowledge(self):
        """Load action knowledge from the library."""
        actions_dir = self.library_path / "actions"
        
        if not actions_dir.exists():
            logger.warning("Actions directory not found")
            return
            
        # Load all action YAML files
        action_files = self.file_manager.list_directory(actions_dir, "*.yaml")
        action_files.extend(self.file_manager.list_directory(actions_dir, "*.yml"))
        
        for action_file in action_files:
            self._load_knowledge_file(action_file, knowledge_type="action")
            
    def _load_knowledge_file(self, file_path: Path, 
                           knowledge_type: str = "general") -> bool:
        """Load a knowledge file into the system.
        
        Args:
            file_path: Path to knowledge file
            knowledge_type: Type of knowledge
            
        Returns:
            True if loaded successfully
        """
        try:
            # Load file content
            content = self.file_manager.load_file(file_path)
            if not content:
                return False
                
            # Parse YAML
            knowledge_data = yaml.safe_load(content)
            
            # Validate version
            if knowledge_data.get("knowledge_version") != "1.0":
                logger.warning(f"Unknown knowledge version in {file_path}")
                return False
                
            # Extract metadata
            metadata = knowledge_data.get("metadata", {})
            metadata["knowledge_type"] = knowledge_type
            
            # Create knowledge item
            knowledge_id = file_path.stem
            knowledge_item = {
                "id": knowledge_id,
                "content": knowledge_data.get("content", ""),
                "metadata": metadata,
                "source": str(file_path),
                "loaded_at": datetime.now(),
                "raw_data": knowledge_data  # Keep original for action parameters etc
            }
            
            # Handle action-specific data
            if knowledge_type == "action":
                knowledge_item["parameter_schema"] = knowledge_data.get("parameter_schema", {})
                knowledge_item["common_corrections"] = knowledge_data.get("common_corrections", [])
                
            self.loaded_knowledge[knowledge_id] = knowledge_item
            self._update_stats(knowledge_item)
            return True
            
        except Exception as e:
            logger.error(f"Failed to load knowledge from {file_path}: {e}")
            return False
            
    def _build_knowledge_index(self):
        """Build an index for efficient knowledge queries."""
        self.knowledge_index = {
            "by_category": {},
            "by_tag": {},
            "by_type": {},
            "by_priority": {}
        }
        
        for knowledge_id, item in self.loaded_knowledge.items():
            metadata = item.get("metadata", {})
            
            # Index by category
            category = metadata.get("category", "general")
            if category not in self.knowledge_index["by_category"]:
                self.knowledge_index["by_category"][category] = []
            self.knowledge_index["by_category"][category].append(knowledge_id)
            
            # Index by tags
            tags = metadata.get("tags", [])
            for tag in tags:
                if tag not in self.knowledge_index["by_tag"]:
                    self.knowledge_index["by_tag"][tag] = []
                self.knowledge_index["by_tag"][tag].append(knowledge_id)
                
            # Index by type
            k_type = metadata.get("knowledge_type", "general")
            if k_type not in self.knowledge_index["by_type"]:
                self.knowledge_index["by_type"][k_type] = []
            self.knowledge_index["by_type"][k_type].append(knowledge_id)
            
            # Index by priority
            priority = metadata.get("priority", 3)
            if priority not in self.knowledge_index["by_priority"]:
                self.knowledge_index["by_priority"][priority] = []
            self.knowledge_index["by_priority"][priority].append(knowledge_id)
            
    def _update_stats(self, knowledge_item: Dict[str, Any]):
        """Update knowledge statistics.
        
        Args:
            knowledge_item: Knowledge item to include in stats
        """
        self.knowledge_stats["total_items"] += 1
        
        metadata = knowledge_item.get("metadata", {})
        
        # Update category stats
        category = metadata.get("category", "general")
        if category not in self.knowledge_stats["by_category"]:
            self.knowledge_stats["by_category"][category] = 0
        self.knowledge_stats["by_category"][category] += 1
        
        # Update source stats
        source = knowledge_item.get("source", "unknown")
        if source not in self.knowledge_stats["by_source"]:
            self.knowledge_stats["by_source"][source] = 0
        self.knowledge_stats["by_source"][source] += 1
        
        self.knowledge_stats["last_updated"] = datetime.now()
        
    def query_knowledge(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query knowledge based on criteria.
        
        Args:
            query: Query criteria dict with fields like:
                - category: Category to filter by
                - tags: List of tags to match
                - type: Knowledge type
                - priority: Minimum priority
                - limit: Maximum results
                
        Returns:
            List of matching knowledge items
        """
        results = []
        candidates = set(self.loaded_knowledge.keys())
        
        # Filter by category
        if "category" in query:
            category_items = set(self.knowledge_index["by_category"].get(query["category"], []))
            candidates &= category_items
            
        # Filter by tags (any match)
        if "tags" in query and query["tags"]:
            tag_items = set()
            for tag in query["tags"]:
                tag_items.update(self.knowledge_index["by_tag"].get(tag, []))
            if tag_items:
                candidates &= tag_items
                
        # Filter by type
        if "type" in query:
            type_items = set(self.knowledge_index["by_type"].get(query["type"], []))
            candidates &= type_items
            
        # Filter by priority
        if "priority" in query:
            priority_items = set()
            for p in range(query["priority"], 6):  # Priorities 1-5
                priority_items.update(self.knowledge_index["by_priority"].get(p, []))
            if priority_items:
                candidates &= priority_items
                
        # Build results
        for knowledge_id in candidates:
            results.append(self.loaded_knowledge[knowledge_id])
            
        # Apply limit
        limit = query.get("limit", 100)
        if len(results) > limit:
            # Sort by priority and take top N
            results.sort(key=lambda x: x.get("metadata", {}).get("priority", 3), reverse=True)
            results = results[:limit]
            
        return results
        
    def get_knowledge_by_id(self, knowledge_id: str) -> Optional[Dict[str, Any]]:
        """Get specific knowledge item by ID.
        
        Args:
            knowledge_id: Knowledge identifier
            
        Returns:
            Knowledge item or None
        """
        return self.loaded_knowledge.get(knowledge_id)
        
    def get_action_knowledge(self, action_name: str) -> Optional[Dict[str, Any]]:
        """Get knowledge for a specific action.
        
        Args:
            action_name: Name of the action
            
        Returns:
            Action knowledge or None
        """
        # Try direct lookup first
        action_knowledge = self.get_knowledge_by_id(action_name)
        if action_knowledge and action_knowledge.get("metadata", {}).get("knowledge_type") == "action":
            return action_knowledge
            
        # Search by type and name
        results = self.query_knowledge({
            "type": "action",
            "limit": 10
        })
        
        for item in results:
            if item["id"] == action_name or item.get("metadata", {}).get("name") == action_name:
                return item
                
        return None
        
    def get_rom_content(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get ROM content, optionally filtered by category.
        
        Args:
            category: Optional category filter
            
        Returns:
            List of ROM knowledge items
        """
        query = {"source": "rom"}
        if category:
            query["category"] = category
            
        # ROM items are those loaded from ROM
        rom_items = []
        for item in self.loaded_knowledge.values():
            if item.get("source") == "rom":
                if not category or item.get("metadata", {}).get("category") == category:
                    rom_items.append(item)
                    
        return rom_items
        
    def get_knowledge_stats(self) -> Dict[str, Any]:
        """Get knowledge system statistics.
        
        Returns:
            Statistics dictionary
        """
        return self.knowledge_stats.copy()
        
    def organize_knowledge(self) -> Dict[str, List[str]]:
        """Organize knowledge into a structured hierarchy.
        
        Returns:
            Organized knowledge structure
        """
        organized = {
            "rom": {
                "general": [],
                "agent_specific": []
            },
            "actions": [],
            "concepts": {},
            "procedures": []
        }
        
        for knowledge_id, item in self.loaded_knowledge.items():
            metadata = item.get("metadata", {})
            
            # Organize ROM
            if item.get("source") == "rom":
                if metadata.get("category") == "general":
                    organized["rom"]["general"].append(knowledge_id)
                else:
                    organized["rom"]["agent_specific"].append(knowledge_id)
                    
            # Organize actions
            elif metadata.get("knowledge_type") == "action":
                organized["actions"].append(knowledge_id)
                
            # Organize by category
            category = metadata.get("category", "general")
            if category not in organized["concepts"]:
                organized["concepts"][category] = []
            organized["concepts"][category].append(knowledge_id)
            
        return organized
        
    def refresh_knowledge(self):
        """Refresh knowledge from sources."""
        logger.info("Refreshing knowledge system...")
        
        # Clear current knowledge
        self.loaded_knowledge.clear()
        self.knowledge_stats = {
            "total_items": 0,
            "by_category": {},
            "by_source": {},
            "last_updated": datetime.now()
        }
        
        # Reload
        self.initialize()