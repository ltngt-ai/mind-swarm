"""Unified model pool management for Mind-Swarm.

This module manages all available AI models with a priority-based system,
replacing the old preset and separate free/local/paid categorization.
"""

import json
import random
import time
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal, Tuple
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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['priority'] = self.priority.value
        data['cost_type'] = self.cost_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelConfig':
        """Create from dictionary."""
        # Convert string enums back
        data['priority'] = Priority(data['priority'])
        data['cost_type'] = CostType(data['cost_type'])
        return cls(**data)


@dataclass
class Promotion:
    """Represents a temporary promotion of a model."""
    model_id: str
    new_priority: Priority
    expires_at: datetime
    original_priority: Priority
    
    def is_active(self) -> bool:
        """Check if promotion is still active."""
        return datetime.now() < self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'model_id': self.model_id,
            'new_priority': self.new_priority.value,
            'expires_at': self.expires_at.isoformat(),
            'original_priority': self.original_priority.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Promotion':
        """Create from dictionary."""
        return cls(
            model_id=data['model_id'],
            new_priority=Priority(data['new_priority']),
            expires_at=datetime.fromisoformat(data['expires_at']),
            original_priority=Priority(data['original_priority'])
        )


class ModelPool:
    """Manages the pool of available AI models with priority-based selection."""
    
    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize the model pool.
        
        Args:
            storage_path: Path to store model pool state
        """
        import os
        
        # Determine storage path with fallback logic:
        # 1. Explicit path if provided
        # 2. SUBSPACE_ROOT if set (for server mode)
        # 3. /var/lib/mind-swarm for system-wide installation
        # 4. User home as last resort
        if storage_path:
            self.storage_path = storage_path
        elif os.getenv('SUBSPACE_ROOT'):
            # Server mode - use subspace root
            self.storage_path = Path(os.getenv('SUBSPACE_ROOT')) / ".mind-swarm" / "model_pool.json"
        elif Path('/var/lib/mind-swarm').exists() and os.access('/var/lib/mind-swarm', os.W_OK):
            # System installation with write access
            self.storage_path = Path('/var/lib/mind-swarm') / "model_pool.json"
        else:
            # Fall back to user home
            self.storage_path = Path.home() / ".mind-swarm" / "model_pool.json"
        self.models: Dict[str, ModelConfig] = {}
        self.promotions: Dict[str, Promotion] = {}  # Active promotions
        self.runtime_models: Dict[str, ModelConfig] = {}  # Models added at runtime
        
        # Log the storage path being used
        logger.info(f"Model pool using storage path: {self.storage_path}")
        
        # Initialize with default models from YAML
        self._load_yaml_models()
        
        # Load saved state (promotions and runtime models)
        self._load_state()
        
        # Clean up expired promotions
        self._cleanup_promotions()
    
    def _load_yaml_models(self):
        """Load models from YAML configuration files."""
        # Load OpenAI models
        self._load_openai_models()
        
        # Load OpenRouter models
        self._load_openrouter_models()
        
        # Load Cerebras models
        self._load_cerebras_models()
        
        logger.info(f"Loaded {len(self.models)} models from YAML configs")
    
    def _load_openai_models(self):
        """Load OpenAI and OpenAI-compatible models from YAML configuration."""
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
                            provider="openai",
                            priority=Priority(model_data['priority']),
                            cost_type=CostType(model_data['cost_type']),
                            context_length=model_data.get('context_length', 8192),
                            max_tokens=model_data.get('max_tokens', 4096),
                            temperature=model_data.get('temperature', 0.7),
                            api_settings=model_data.get('api_settings', {})
                        )
                        self.models[model.id] = model
                    
                    logger.info(f"Loaded {len(data.get('models', []))} OpenAI models from {config_path}")
                    return
                    
                except Exception as e:
                    logger.error(f"Failed to load OpenAI models from {config_path}: {e}")
        
        logger.warning("No OpenAI models configuration file found")
    
    def _load_openrouter_models(self):
        """Load OpenRouter models from YAML configuration."""
        import os
        if not os.getenv("OPENROUTER_API_KEY"):
            logger.debug("No OPENROUTER_API_KEY found, skipping OpenRouter models")
            return
            
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
                        self.models[model.id] = model
                    
                    logger.info(f"Loaded {len(data.get('models', []))} OpenRouter models from {config_path}")
                    return
                    
                except Exception as e:
                    logger.error(f"Failed to load OpenRouter models from {config_path}: {e}")
        
        logger.debug("No OpenRouter models configuration file found")
    
    def _load_cerebras_models(self):
        """Load Cerebras models from YAML configuration."""
        import os
        if not os.getenv("CEREBRAS_API_KEY"):
            logger.debug("No CEREBRAS_API_KEY found, skipping Cerebras models")
            return
            
        config_paths = [
            Path("config/cerebras_models.yaml"),
            Path(__file__).parent.parent.parent.parent / "config" / "cerebras_models.yaml",
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
                            provider="cerebras",
                            priority=Priority(model_data['priority']),
                            cost_type=CostType(model_data['cost_type']),
                            context_length=model_data.get('context_length', 8192),
                            max_tokens=model_data.get('max_tokens', 4096),
                            temperature=model_data.get('temperature', 0.7),
                            api_settings=model_data.get('api_settings', {})
                        )
                        self.models[model.id] = model
                    
                    logger.info(f"Loaded {len(data.get('models', []))} Cerebras models from {config_path}")
                    return
                    
                except Exception as e:
                    logger.error(f"Failed to load Cerebras models from {config_path}: {e}")
        
        logger.debug("No Cerebras models configuration file found")
    
    def _load_state(self):
        """Load saved state (promotions and runtime models) from disk."""
        if not self.storage_path.exists():
            return
            
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
            
            # Load active promotions
            for promo_data in data.get('promotions', []):
                try:
                    promotion = Promotion.from_dict(promo_data)
                    if promotion.is_active():
                        self.promotions[promotion.model_id] = promotion
                        logger.debug(f"Restored promotion for {promotion.model_id}")
                except Exception as e:
                    logger.warning(f"Failed to restore promotion: {e}")
            
            # Load runtime-added models
            for model_id, model_data in data.get('runtime_models', {}).items():
                try:
                    model = ModelConfig.from_dict(model_data)
                    self.runtime_models[model_id] = model
                    self.models[model_id] = model
                    logger.debug(f"Restored runtime model {model_id}")
                except Exception as e:
                    logger.warning(f"Failed to restore runtime model {model_id}: {e}")
            
            logger.info(f"Restored {len(self.promotions)} promotions and {len(self.runtime_models)} runtime models")
                
        except Exception as e:
            logger.error(f"Failed to load model pool state: {e}")
    
    def _save_state(self):
        """Save current state (promotions and runtime models) to disk."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Only save promotions and runtime models
            data = {
                'promotions': [
                    promo.to_dict() 
                    for promo in self.promotions.values() 
                    if promo.is_active()
                ],
                'runtime_models': {
                    model_id: model.to_dict()
                    for model_id, model in self.runtime_models.items()
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
        expired = []
        for model_id, promotion in list(self.promotions.items()):
            if not promotion.is_active():
                expired.append(model_id)
                del self.promotions[model_id]
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired promotions")
            self._save_state()
    
    def _get_effective_priority(self, model: ModelConfig) -> Priority:
        """Get the effective priority of a model, considering promotions.
        
        Args:
            model: Model configuration
            
        Returns:
            Effective priority (promoted or original)
        """
        if model.id in self.promotions:
            promotion = self.promotions[model.id]
            if promotion.is_active():
                return promotion.new_priority
        return model.priority
    
    def add_model(self, model: ModelConfig):
        """Add a runtime model to the pool.
        
        Args:
            model: Model configuration
        """
        self.models[model.id] = model
        self.runtime_models[model.id] = model
        self._save_state()
        logger.info(f"Added runtime model {model.id} ({model.cost_type.value}) with priority {model.priority.value}")
    
    def remove_model(self, model_id: str):
        """Remove a model from the pool.
        
        Args:
            model_id: Model ID to remove
        """
        if model_id in self.runtime_models:
            # Can only remove runtime models, not YAML-defined ones
            del self.models[model_id]
            del self.runtime_models[model_id]
            
            # Also remove any promotions
            if model_id in self.promotions:
                del self.promotions[model_id]
            
            self._save_state()
            logger.info(f"Removed runtime model {model_id}")
        elif model_id in self.models:
            logger.warning(f"Cannot remove YAML-defined model {model_id}. Remove from config file instead.")
        else:
            logger.warning(f"Model {model_id} not found")
    
    def promote_model(
        self, 
        model_id: str, 
        new_priority: Priority,
        duration_hours: Optional[float] = None
    ):
        """Promote a model to a different priority tier.
        
        Args:
            model_id: Model ID to promote
            new_priority: New priority level
            duration_hours: How long the promotion lasts (None = permanent)
        """
        model = self.models.get(model_id)
        
        if not model:
            raise ValueError(f"Model {model_id} not found")
        
        if duration_hours:
            # Temporary promotion
            promotion = Promotion(
                model_id=model_id,
                new_priority=new_priority,
                expires_at=datetime.now() + timedelta(hours=duration_hours),
                original_priority=model.priority
            )
            self.promotions[model_id] = promotion
            logger.info(f"Promoted {model_id} to {new_priority.value} for {duration_hours} hours")
        else:
            # Permanent promotion - update the model itself
            if model_id in self.runtime_models:
                # Runtime model - can change permanently
                model.priority = new_priority
                self.runtime_models[model_id].priority = new_priority
                logger.info(f"Permanently promoted runtime model {model_id} to {new_priority.value}")
            else:
                # YAML model - use indefinite promotion
                promotion = Promotion(
                    model_id=model_id,
                    new_priority=new_priority,
                    expires_at=datetime.max,  # Far future
                    original_priority=model.priority
                )
                self.promotions[model_id] = promotion
                logger.info(f"Promoted YAML model {model_id} to {new_priority.value} (indefinite)")
        
        self._save_state()
    
    def demote_model(self, model_id: str):
        """Remove promotion from a model.
        
        Args:
            model_id: Model ID to demote
        """
        removed = False
        
        # Remove promotion if exists
        if model_id in self.promotions:
            original_priority = self.promotions[model_id].original_priority
            del self.promotions[model_id]
            removed = True
            logger.info(f"Removed promotion from {model_id}, restored to {original_priority.value}")
        
        # For runtime models, check if priority was permanently changed
        if model_id in self.runtime_models:
            # Reset to NORMAL as default for runtime models
            self.models[model_id].priority = Priority.NORMAL
            self.runtime_models[model_id].priority = Priority.NORMAL
            removed = True
            logger.info(f"Reset runtime model {model_id} to NORMAL priority")
        
        if removed:
            self._save_state()
        else:
            logger.warning(f"Model {model_id} has no active promotion")
    
    def select_model(self, paid_allowed: bool = False) -> Optional[ModelConfig]:
        """Select a model using random selection within priority tiers.
        
        Args:
            paid_allowed: Whether paid models can be selected
            
        Returns:
            Selected model or None if no models available
        """
        # Clean up expired promotions first
        self._cleanup_promotions()
        
        # Filter candidates
        candidates = []
        for model in self.models.values():
            # Skip paid models if not allowed, UNLESS they are promoted
            if model.cost_type == CostType.PAID and not paid_allowed:
                # Check if this model is promoted - promoted paid models should be usable
                if model.id not in self.promotions or not self.promotions[model.id].is_active():
                    continue
            candidates.append(model)
        
        if not candidates:
            logger.warning("No models available in pool")
            return None
        
        # Group by effective priority
        primary = []
        normal = []
        fallback = []
        
        for model in candidates:
            effective_priority = self._get_effective_priority(model)
            if effective_priority == Priority.PRIMARY:
                primary.append(model)
            elif effective_priority == Priority.NORMAL:
                normal.append(model)
            else:
                fallback.append(model)
        
        # Select from highest available priority
        if primary:
            selected = random.choice(primary)
            tier = "primary"
        elif normal:
            selected = random.choice(normal)
            tier = "normal"
        elif fallback:
            selected = random.choice(fallback)
            tier = "fallback"
        else:
            logger.warning("No models available after filtering")
            return None
        
        logger.debug(f"Selected model {selected.id} from {tier} tier")
        return selected
    
    def list_models(self, include_paid: bool = True) -> List[Tuple[ModelConfig, Optional[Promotion]]]:
        """List all models in the pool with their promotion status.
        
        Args:
            include_paid: Whether to include paid models
            
        Returns:
            List of (model, promotion) tuples sorted by effective priority
        """
        results = []
        
        for model in self.models.values():
            # Skip paid models if requested
            if model.cost_type == CostType.PAID and not include_paid:
                continue
            
            # Get promotion if exists
            promotion = self.promotions.get(model.id) if model.id in self.promotions else None
            if promotion and not promotion.is_active():
                promotion = None
            
            results.append((model, promotion))
        
        # Sort by effective priority
        priority_order = {Priority.PRIMARY: 0, Priority.NORMAL: 1, Priority.FALLBACK: 2}
        results.sort(key=lambda x: (
            priority_order[x[1].new_priority if x[1] else x[0].priority],
            x[0].id
        ))
        
        return results
    
    def get_model(self, model_id: str) -> Optional[ModelConfig]:
        """Get a specific model by ID.
        
        Args:
            model_id: Model ID
            
        Returns:
            Model configuration or None
        """
        return self.models.get(model_id)
    
    def get_promotion(self, model_id: str) -> Optional[Promotion]:
        """Get active promotion for a model.
        
        Args:
            model_id: Model ID
            
        Returns:
            Active promotion or None
        """
        if model_id in self.promotions:
            promotion = self.promotions[model_id]
            if promotion.is_active():
                return promotion
        return None
    


# Global model pool instance
model_pool = ModelPool()