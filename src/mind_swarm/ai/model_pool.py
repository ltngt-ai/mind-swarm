"""Unified model pool management for Mind-Swarm.

This module manages all available AI models with a priority-based system,
replacing the old preset and separate free/local/paid categorization.
"""

import json
import random
import time
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from enum import Enum

from mind_swarm.utils.logging import logger


class Priority(Enum):
    """Model priority levels."""
    PRIMARY = "primary"
    NORMAL = "normal"
    FALLBACK = "fallback"


class CostType(Enum):
    """Model cost types."""
    FREE = "free"
    PAID = "paid"


@dataclass
class ModelConfig:
    """Configuration for a model in the pool."""
    id: str
    name: str
    provider: str  # openrouter, openai-compatible, etc.
    priority: Priority
    cost_type: CostType
    context_length: int = 8192
    max_tokens: int = 4096
    temperature: float = 0.7
    api_settings: Dict[str, Any] = field(default_factory=dict)
    
    # Temporary promotion tracking
    promoted_until: Optional[datetime] = None
    original_priority: Optional[Priority] = None
    
    def is_promoted(self) -> bool:
        """Check if model is currently promoted."""
        if not self.promoted_until:
            return False
        return datetime.now() < self.promoted_until
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['priority'] = self.priority.value
        data['cost_type'] = self.cost_type.value
        if self.promoted_until:
            data['promoted_until'] = self.promoted_until.isoformat()
        if self.original_priority:
            data['original_priority'] = self.original_priority.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelConfig':
        """Create from dictionary."""
        # Convert string enums back
        data['priority'] = Priority(data['priority'])
        data['cost_type'] = CostType(data['cost_type'])
        
        # Handle datetime conversion
        if data.get('promoted_until'):
            data['promoted_until'] = datetime.fromisoformat(data['promoted_until'])
        if data.get('original_priority'):
            data['original_priority'] = Priority(data['original_priority'])
            
        return cls(**data)


class ModelPool:
    """Manages the pool of available AI models with priority-based selection."""
    
    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize the model pool.
        
        Args:
            storage_path: Path to store model pool state
        """
        self.storage_path = storage_path or Path.home() / ".mind-swarm" / "model_pool.json"
        self.models: Dict[str, ModelConfig] = {}
        self.paid_models: Dict[str, ModelConfig] = {}  # Separate paid model tracking
        
        # Initialize with default models
        self._initialize_defaults()
        
        # Load saved state if exists
        self._load_state()
        
        # Clean up expired promotions
        self._cleanup_promotions()
    
    def _initialize_defaults(self):
        """Initialize with default model configurations from YAML."""
        # Load OpenAI models from config
        self._load_openai_models()
        
        # Load OpenRouter models from config
        self._load_openrouter_models()
    
    def _load_openai_models(self):
        """Load OpenAI and OpenAI-compatible models from YAML configuration."""
        # Try multiple locations for the config file
        config_paths = [
            Path("config/openai_models.yaml"),
            Path(__file__).parent.parent.parent.parent / "config" / "openai_models.yaml",
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        data = yaml.safe_load(f)
                    
                    for model_data in data.get('models', []):
                        model = ModelConfig(
                            id=model_data['id'],
                            name=model_data['name'],
                            provider="openai",  # All use OpenAI provider
                            priority=Priority(model_data['priority']),
                            cost_type=CostType(model_data['cost_type']),
                            context_length=model_data.get('context_length', 8192),
                            max_tokens=model_data.get('max_tokens', 4096),
                            temperature=model_data.get('temperature', 0.7),
                            api_settings=model_data.get('api_settings', {})
                        )
                        
                        # Add to appropriate pool
                        if model.cost_type == CostType.PAID:
                            self.paid_models[model.id] = model
                        else:
                            self.models[model.id] = model
                    
                    logger.info(f"Loaded {len(data.get('models', []))} OpenAI models from {config_path}")
                    return
                    
                except Exception as e:
                    logger.error(f"Failed to load OpenAI models from {config_path}: {e}")
        
        logger.warning("No OpenAI models configuration file found")
    
    def _load_openrouter_models(self):
        """Load OpenRouter models from YAML configuration."""
        # Only load if API key is available
        import os
        if not os.getenv("OPENROUTER_API_KEY"):
            logger.debug("No OPENROUTER_API_KEY found, skipping OpenRouter models")
            return
            
        # Try multiple locations for the config file
        config_paths = [
            Path("config/openrouter_models.yaml"),
            Path(__file__).parent.parent.parent.parent / "config" / "openrouter_models.yaml",
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        data = yaml.safe_load(f)
                    
                    for model_data in data.get('models', []):
                        model = ModelConfig(
                            id=model_data['id'],
                            name=model_data['name'],
                            provider=model_data['provider'],
                            priority=Priority(model_data['priority']),
                            cost_type=CostType(model_data['cost_type']),
                            context_length=model_data.get('context_length', 8192),
                            max_tokens=model_data.get('max_tokens', 4096),
                            temperature=model_data.get('temperature', 0.7),
                            api_settings=model_data.get('api_settings', {})
                        )
                        
                        # Add to appropriate pool
                        if model.cost_type == CostType.PAID:
                            self.paid_models[model.id] = model
                        else:
                            self.models[model.id] = model
                    
                    logger.info(f"Loaded {len(data.get('models', []))} OpenRouter models from {config_path}")
                    return
                    
                except Exception as e:
                    logger.error(f"Failed to load OpenRouter models from {config_path}: {e}")
        
        logger.debug("No OpenRouter models configuration file found")
    
    def _load_state(self):
        """Load saved model pool state from disk and merge with YAML configs."""
        if not self.storage_path.exists():
            return
            
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
            
            # Track models before merging
            yaml_free = set(self.models.keys())
            yaml_paid = set(self.paid_models.keys())
            
            # Merge free models - only add if not from YAML
            for model_id, model_data in data.get('models', {}).items():
                if model_id not in yaml_free:
                    # This is a runtime-added model, keep it
                    self.models[model_id] = ModelConfig.from_dict(model_data)
                else:
                    # Model exists in YAML, check for promotions
                    saved_model = ModelConfig.from_dict(model_data)
                    if saved_model.promoted_until or saved_model.original_priority:
                        # Preserve promotion status
                        self.models[model_id].promoted_until = saved_model.promoted_until
                        self.models[model_id].original_priority = saved_model.original_priority
                        if saved_model.promoted_until:
                            self.models[model_id].priority = saved_model.priority
                
            # Merge paid models - only add if not from YAML
            for model_id, model_data in data.get('paid_models', {}).items():
                if model_id not in yaml_paid:
                    # This is a runtime-added model, keep it
                    self.paid_models[model_id] = ModelConfig.from_dict(model_data)
                else:
                    # Model exists in YAML, check for promotions
                    saved_model = ModelConfig.from_dict(model_data)
                    if saved_model.promoted_until or saved_model.original_priority:
                        # Preserve promotion status
                        self.paid_models[model_id].promoted_until = saved_model.promoted_until
                        self.paid_models[model_id].original_priority = saved_model.original_priority
                        if saved_model.promoted_until:
                            self.paid_models[model_id].priority = saved_model.priority
                
            # Count what was actually added from state
            added_free = len(self.models) - len(yaml_free)
            added_paid = len(self.paid_models) - len(yaml_paid)
            
            if added_free > 0 or added_paid > 0:
                logger.info(f"Merged state: added {added_free} free and {added_paid} paid runtime models")
        except Exception as e:
            logger.error(f"Failed to load model pool state: {e}")
    
    def _save_state(self):
        """Save current model pool state to disk."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'models': {
                    model_id: model.to_dict()
                    for model_id, model in self.models.items()
                },
                'paid_models': {
                    model_id: model.to_dict()
                    for model_id, model in self.paid_models.items()
                },
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.debug(f"Saved model pool state to {self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to save model pool state: {e}")
    
    def _cleanup_promotions(self):
        """Remove expired promotions."""
        now = datetime.now()
        cleaned = 0
        
        for model in list(self.models.values()) + list(self.paid_models.values()):
            if model.promoted_until and model.promoted_until < now:
                # Restore original priority
                if model.original_priority:
                    model.priority = model.original_priority
                model.promoted_until = None
                model.original_priority = None
                cleaned += 1
        
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} expired model promotions")
            self._save_state()
    
    def add_model(self, model: ModelConfig, is_paid: bool = False):
        """Add a model to the pool.
        
        Args:
            model: Model configuration
            is_paid: Whether this is a paid model
        """
        if is_paid:
            self.paid_models[model.id] = model
        else:
            self.models[model.id] = model
        self._save_state()
        logger.info(f"Added {'paid' if is_paid else 'free'} model {model.id} with priority {model.priority.value}")
    
    def remove_model(self, model_id: str):
        """Remove a model from the pool.
        
        Args:
            model_id: Model ID to remove
        """
        removed = False
        if model_id in self.models:
            del self.models[model_id]
            removed = True
        if model_id in self.paid_models:
            del self.paid_models[model_id]
            removed = True
            
        if removed:
            self._save_state()
            logger.info(f"Removed model {model_id}")
        else:
            logger.warning(f"Model {model_id} not found")
    
    def promote_model(
        self, 
        model_id: str, 
        new_priority: Priority,
        duration_hours: Optional[float] = None
    ):
        """Promote a model to a higher priority tier.
        
        Args:
            model_id: Model ID to promote
            new_priority: New priority level
            duration_hours: How long the promotion lasts (None = forever)
        """
        # Check both free and paid pools
        model = self.models.get(model_id) or self.paid_models.get(model_id)
        
        if not model:
            raise ValueError(f"Model {model_id} not found")
        
        # If it's a paid model, move it to free pool temporarily
        if model_id in self.paid_models:
            model = self.paid_models.pop(model_id)
            self.models[model_id] = model
            logger.info(f"Moving paid model {model_id} to free pool")
        
        # Store original priority if not already promoted
        if not model.original_priority:
            model.original_priority = model.priority
        
        model.priority = new_priority
        
        if duration_hours:
            model.promoted_until = datetime.now() + timedelta(hours=duration_hours)
            logger.info(f"Promoted {model_id} to {new_priority.value} for {duration_hours} hours")
        else:
            model.promoted_until = None
            model.original_priority = None
            logger.info(f"Permanently promoted {model_id} to {new_priority.value}")
        
        self._save_state()
    
    def demote_model(self, model_id: str):
        """Remove promotion from a model.
        
        Args:
            model_id: Model ID to demote
        """
        model = self.models.get(model_id)
        
        if not model:
            raise ValueError(f"Model {model_id} not found in free pool")
        
        if model.original_priority:
            model.priority = model.original_priority
            model.original_priority = None
        
        model.promoted_until = None
        
        # If it's a paid model, move it back
        if model.cost_type == CostType.PAID:
            self.paid_models[model_id] = self.models.pop(model_id)
            logger.info(f"Moving {model_id} back to paid pool")
        
        logger.info(f"Demoted {model_id} to {model.priority.value}")
        self._save_state()
    
    def select_model(self, paid_allowed: bool = False) -> Optional[ModelConfig]:
        """Select a model using random selection within priority tiers.
        
        Args:
            paid_allowed: Whether paid models can be selected
            
        Returns:
            Selected model or None if no models available
        """
        # Clean up expired promotions first
        self._cleanup_promotions()
        
        # Build candidate pools by priority
        candidates = self.models.values()
        
        if paid_allowed:
            candidates = list(candidates) + list(self.paid_models.values())
        
        # Group by priority
        primary = [m for m in candidates if m.priority == Priority.PRIMARY]
        normal = [m for m in candidates if m.priority == Priority.NORMAL]
        fallback = [m for m in candidates if m.priority == Priority.FALLBACK]
        
        # Select from highest available priority
        if primary:
            selected = random.choice(primary)
        elif normal:
            selected = random.choice(normal)
        elif fallback:
            selected = random.choice(fallback)
        else:
            logger.warning("No models available in pool")
            return None
        
        logger.debug(f"Selected model {selected.id} from {selected.priority.value} tier")
        return selected
    
    def list_models(self, include_paid: bool = True) -> List[ModelConfig]:
        """List all models in the pool.
        
        Args:
            include_paid: Whether to include paid models
            
        Returns:
            List of models sorted by priority
        """
        models = list(self.models.values())
        
        if include_paid:
            models.extend(self.paid_models.values())
        
        # Sort by priority (PRIMARY < NORMAL < FALLBACK)
        priority_order = {Priority.PRIMARY: 0, Priority.NORMAL: 1, Priority.FALLBACK: 2}
        models.sort(key=lambda m: (priority_order[m.priority], m.id))
        
        return models
    
    def get_model(self, model_id: str) -> Optional[ModelConfig]:
        """Get a specific model by ID.
        
        Args:
            model_id: Model ID
            
        Returns:
            Model configuration or None
        """
        return self.models.get(model_id) or self.paid_models.get(model_id)
    
    def load_from_registry(self, models: List[Dict[str, Any]], curated_ids: List[str]):
        """Load models from the existing registry format.
        
        Args:
            models: List of model data from registry
            curated_ids: List of curated model IDs
        """
        for model_data in models:
            model_id = model_data.get('id', '')
            if not model_id:
                continue
            
            # Determine priority based on curated status
            if model_id in curated_ids:
                priority = Priority.PRIMARY
            else:
                priority = Priority.NORMAL
            
            # Determine cost type
            is_free = (model_data.get('input_cost', 0) == 0 and 
                      model_data.get('output_cost', 0) == 0)
            cost_type = CostType.FREE if is_free else CostType.PAID
            
            # Determine provider
            if '/' in model_id:
                provider = model_id.split('/')[0]
            else:
                provider = 'unknown'
            
            model = ModelConfig(
                id=model_id,
                name=model_data.get('name', model_id),
                provider=provider,
                priority=priority,
                cost_type=cost_type,
                context_length=model_data.get('context_length', 8192),
                max_tokens=model_data.get('max_output_tokens', 4096)
            )
            
            if cost_type == CostType.PAID:
                self.paid_models[model_id] = model
            else:
                self.models[model_id] = model
        
        self._save_state()
        logger.info(f"Loaded {len(self.models)} free and {len(self.paid_models)} paid models from registry")


# Global model pool instance
model_pool = ModelPool()