"""AI preset management for Mind-Swarm.

This module provides a preset system for AI configurations, allowing
easy switching between models and providers without code changes.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

from mind_swarm.ai.config import AIExecutionConfig
from mind_swarm.utils.logging import logger


class AIPreset:
    """Represents a single AI preset configuration."""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize from preset data.
        
        Args:
            data: Preset configuration dictionary
        """
        self.name = data["name"]
        self.provider = data["provider"]
        self.model = data["model"]
        self.temperature = data.get("temperature", 0.7)
        self.max_tokens = data.get("max_tokens", 4096)
        self.api_settings = data.get("api_settings", {})
        
        # For local models, extract host from model field if present
        if self.provider in ["ollama", "local"] and "@" in self.model:
            # Format: model@host (e.g., llama3.2:3b@192.168.1.100:11434)
            self.model, host = self.model.split("@", 1)
            self.api_settings["host"] = f"http://{host}" if not host.startswith("http") else host
    
    def to_config(self, api_key: Optional[str] = None) -> AIExecutionConfig:
        """Convert preset to AIExecutionConfig.
        
        Args:
            api_key: Optional API key override
            
        Returns:
            AIExecutionConfig instance
        """
        # For local providers, use dummy key
        if self.provider in ["ollama", "local"]:
            api_key = api_key or "not-needed"
        
        return AIExecutionConfig(
            model_id=self.model,
            provider=self.provider,
            api_key=api_key or "",
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            provider_settings=self.api_settings,
        )
    
    def __repr__(self) -> str:
        return f"AIPreset(name='{self.name}', provider='{self.provider}', model='{self.model}')"


class AIPresetManager:
    """Manages AI presets loaded from configuration."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the preset manager.
        
        Args:
            config_path: Path to presets YAML file
        """
        self.config_path = config_path or Path("ai_presets.yaml")
        self.presets: Dict[str, AIPreset] = {}
        self._load_presets()
    
    def _load_presets(self):
        """Load presets from configuration file."""
        # Try multiple locations
        search_paths = [
            self.config_path,
            Path.cwd() / self.config_path,
            Path(__file__).parent.parent.parent.parent / self.config_path,  # Project root
        ]
        
        for path in search_paths:
            if path.exists():
                try:
                    with open(path) as f:
                        data = yaml.safe_load(f)
                    
                    if data and "ai_presets" in data:
                        for preset_data in data["ai_presets"]:
                            preset = AIPreset(preset_data)
                            self.presets[preset.name] = preset
                        
                        logger.info(f"Loaded {len(self.presets)} AI presets from {path}")
                        return
                except Exception as e:
                    logger.error(f"Failed to load AI presets from {path}: {e}")
        
        # If no file found, create default presets
        logger.warning("No AI presets file found, using defaults")
        self._create_default_presets()
    
    def _create_default_presets(self):
        """Create default presets if no config file is found."""
        defaults = [
            {
                "name": "local_explorer",
                "provider": "ollama",
                "model": "llama3.2:3b",
                "temperature": 0.7,
                "max_tokens": 2048,
            },
            {
                "name": "local_smart",
                "provider": "ollama", 
                "model": "llama3.2:8b",
                "temperature": 0.5,
                "max_tokens": 4096,
            },
            {
                "name": "fast_cheap",
                "provider": "openrouter",
                "model": "google/gemini-2.0-flash-exp:free",
                "temperature": 0.5,
                "max_tokens": 4096,
            },
            {
                "name": "smart_expensive",
                "provider": "openrouter",
                "model": "anthropic/claude-3.5-sonnet",
                "temperature": 0.7,
                "max_tokens": 4096,
            },
            {
                "name": "ultra_smart",
                "provider": "openrouter",
                "model": "anthropic/claude-3.5-opus",
                "temperature": 0.7,
                "max_tokens": 8192,
            },
        ]
        
        for preset_data in defaults:
            preset = AIPreset(preset_data)
            self.presets[preset.name] = preset
    
    def get_preset(self, name: str) -> Optional[AIPreset]:
        """Get a preset by name.
        
        Args:
            name: Preset name
            
        Returns:
            AIPreset instance or None if not found
        """
        return self.presets.get(name)
    
    def get_config(self, preset_name: str, api_key: Optional[str] = None) -> AIExecutionConfig:
        """Get AIExecutionConfig from a preset name.
        
        Args:
            preset_name: Name of the preset
            api_key: Optional API key override
            
        Returns:
            AIExecutionConfig instance
            
        Raises:
            ValueError: If preset not found
        """
        preset = self.get_preset(preset_name)
        if not preset:
            raise ValueError(
                f"Unknown AI preset: {preset_name}. "
                f"Available presets: {list(self.presets.keys())}"
            )
        
        return preset.to_config(api_key)
    
    def list_presets(self) -> List[str]:
        """List available preset names.
        
        Returns:
            List of preset names
        """
        return list(self.presets.keys())
    
    def save_presets(self, path: Optional[Path] = None):
        """Save current presets to YAML file.
        
        Args:
            path: Optional path override
        """
        path = path or self.config_path
        
        data = {
            "ai_presets": [
                {
                    "name": preset.name,
                    "provider": preset.provider,
                    "model": preset.model,
                    "temperature": preset.temperature,
                    "max_tokens": preset.max_tokens,
                    **({"api_settings": preset.api_settings} if preset.api_settings else {}),
                }
                for preset in self.presets.values()
            ]
        }
        
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Saved {len(self.presets)} AI presets to {path}")


# Global preset manager instance
preset_manager = AIPresetManager()