"""ROM (Read-Only Memory) loader for Cyber knowledge.

This module handles loading and parsing of ROM data from
the library knowledge files.
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger("Cyber.knowledge.rom")


class ROMLoader:
    """Handles loading and management of ROM data."""
    
    def __init__(self, library_path: Path = Path("/grid/library")):
        """Initialize ROM loader.
        
        Args:
            library_path: Path to the library directory
        """
        self.library_path = library_path
        self.rom_cache = {}
        
    def load_rom_directory(self, rom_dir: Path, cyber_type: Optional[str] = None) -> Dict[str, Any]:
        """Load all ROM files from a directory.
        
        Args:
            rom_dir: Directory containing ROM files
            cyber_type: Optional Cyber type for specific ROM
            
        Returns:
            Dictionary of loaded ROM data
        """
        rom_data = {}
        rom_count = 0
        
        if not rom_dir.exists():
            logger.warning(f"ROM directory not found: {rom_dir}")
            return rom_data
            
        # Load YAML files only
        for pattern in ["*.yaml", "*.yml"]:
            for rom_file in rom_dir.glob(pattern):
                rom_content = self.load_rom_file(rom_file)
                if rom_content:
                    # Store the file path relative to library path in the content
                    rom_content['file_path'] = str(rom_file.relative_to(self.library_path.parent.parent))
                    rom_data[rom_file.stem] = rom_content
                    rom_count += 1
                    
        logger.info(f"Loaded {rom_count} ROM files from {rom_dir}")
        return rom_data
        
    def load_rom_file(self, rom_path: Path) -> Optional[Dict[str, Any]]:
        """Load a single ROM file.
        
        Args:
            rom_path: Path to ROM file
            
        Returns:
            ROM data or None if failed
        """
        try:
            # Check cache first
            cache_key = str(rom_path)
            if cache_key in self.rom_cache:
                return self.rom_cache[cache_key]
                
            # Load YAML file
            file_content = rom_path.read_text()
            rom_data = yaml.safe_load(file_content)
            
            # Validate ROM version
            if rom_data.get("knowledge_version") != "1.0":
                logger.warning(f"Unknown ROM version in {rom_path}")
                return None
                
            # Cache the data
            self.rom_cache[cache_key] = rom_data
            return rom_data
            
        except Exception as e:
            logger.error(f"Failed to load ROM from {rom_path}: {e}")
            return None
            
    def get_general_rom(self) -> Dict[str, Any]:
        """Load general ROM files available to all Cybers.
        
        Returns:
            Dictionary of general ROM data
        """
        general_rom_dir = self.library_path / "rom" / "general"
        return self.load_rom_directory(general_rom_dir)
        
    def get_agent_rom(self, cyber_type: str) -> Dict[str, Any]:
        """Load Cyber-specific ROM files.
        
        Args:
            cyber_type: Type of Cyber (e.g., 'io_cyber')
            
        Returns:
            Dictionary of Cyber-specific ROM data
        """
        agent_rom_dir = self.library_path / "rom" / cyber_type
        if agent_rom_dir.exists():
            return self.load_rom_directory(agent_rom_dir, cyber_type)
        return {}
        
    def get_all_rom(self, cyber_type: Optional[str] = None) -> Dict[str, Any]:
        """Load all applicable ROM for an Cyber.
        
        Args:
            cyber_type: Optional Cyber type for specific ROM
            
        Returns:
            Combined ROM data (general + Cyber-specific)
        """
        all_rom = {}
        
        # Load general ROM
        general_rom = self.get_general_rom()
        all_rom.update(general_rom)
        
        # Load Cyber-specific ROM if specified
        if cyber_type:
            agent_rom = self.get_agent_rom(cyber_type)
            all_rom.update(agent_rom)
            
        return all_rom
        
    def extract_rom_content(self, rom_data: Dict[str, Any]) -> str:
        """Extract the actual content from ROM data.
        
        Args:
            rom_data: ROM data dictionary
            
        Returns:
            Content string
        """
        content = rom_data.get("content", "")
        
        if isinstance(content, list):
            # Join list items with newlines
            return "\\n".join(content)
        elif isinstance(content, str):
            return content
        else:
            return str(content)
            
    def get_rom_metadata(self, rom_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from ROM data.
        
        Args:
            rom_data: ROM data dictionary
            
        Returns:
            Metadata dictionary
        """
        metadata = rom_data.get("metadata", {})
        
        # Add standard fields
        return {
            "id": rom_data.get("id", "unknown"),
            "title": rom_data.get("title", ""),
            "category": metadata.get("category", "general"),
            "tags": metadata.get("tags", []),
            "priority": metadata.get("priority", 3),
            "confidence": metadata.get("confidence", 1.0),
            "version": metadata.get("version", 1),
            "source": metadata.get("source", "library"),
            "is_rom": True
        }
        
    def clear_cache(self):
        """Clear the ROM cache."""
        self.rom_cache.clear()
        logger.debug("ROM cache cleared")