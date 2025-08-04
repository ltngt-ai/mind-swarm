"""Model selection logic for choosing appropriate AI models for agents.

This module provides strategies for selecting models based on availability,
performance metrics, and agent requirements.
"""

import random
from typing import Dict, List, Optional, Any
from enum import Enum

from mind_swarm.ai.model_registry import ModelRegistry, ModelInfo
from mind_swarm.utils.logging import logger


class SelectionStrategy(Enum):
    """Model selection strategies."""
    RANDOM_CURATED = "random_curated"  # Random from curated free list
    RANDOM_FREE = "random_free"  # Random from all free models
    BEST_PERFORMANCE = "best_performance"  # Highest success rate + speed
    LEAST_USED = "least_used"  # Least recently used for load balancing
    FALLBACK_LOCAL = "fallback_local"  # Local models only


class ModelSelector:
    """Selects appropriate models for agents based on various strategies."""
    
    def __init__(self, registry: ModelRegistry):
        """Initialize the model selector.
        
        Args:
            registry: Model registry instance
        """
        self.registry = registry
        
    def select_model(
        self,
        strategy: SelectionStrategy = SelectionStrategy.RANDOM_CURATED,
        constraints: Optional[Dict[str, Any]] = None
    ) -> Optional[ModelInfo]:
        """Select a model based on strategy and constraints.
        
        Args:
            strategy: Selection strategy to use
            constraints: Optional constraints (e.g., min_context_length)
            
        Returns:
            Selected model or None if no suitable model found
        """
        candidates = self._get_candidates(strategy, constraints)
        
        if not candidates:
            logger.warning(f"No models found for strategy {strategy}")
            # Fall back to local models
            return self._select_fallback_local()
            
        if strategy == SelectionStrategy.RANDOM_CURATED:
            return random.choice(candidates)
            
        elif strategy == SelectionStrategy.RANDOM_FREE:
            return random.choice(candidates)
            
        elif strategy == SelectionStrategy.BEST_PERFORMANCE:
            return self._select_best_performance(candidates)
            
        elif strategy == SelectionStrategy.LEAST_USED:
            return self._select_least_used(candidates)
            
        elif strategy == SelectionStrategy.FALLBACK_LOCAL:
            return candidates[0] if candidates else None
            
        else:
            # Default to random selection
            return random.choice(candidates)
            
    def _get_candidates(
        self,
        strategy: SelectionStrategy,
        constraints: Optional[Dict[str, Any]] = None
    ) -> List[ModelInfo]:
        """Get candidate models based on strategy and constraints.
        
        Args:
            strategy: Selection strategy
            constraints: Optional constraints
            
        Returns:
            List of candidate models
        """
        # Start with base candidates based on strategy
        if strategy == SelectionStrategy.RANDOM_CURATED:
            candidates = self.registry.get_free_models(curated_only=True)
        elif strategy == SelectionStrategy.FALLBACK_LOCAL:
            candidates = [
                m for m in self.registry.get_free_models()
                if m.id.startswith("ollama/")
            ]
        else:
            # For other strategies, start with all free models
            candidates = self.registry.get_free_models()
            
        # Apply constraints
        if constraints:
            candidates = self._apply_constraints(candidates, constraints)
            
        return candidates
        
    def _apply_constraints(
        self,
        models: List[ModelInfo],
        constraints: Dict[str, Any]
    ) -> List[ModelInfo]:
        """Apply constraints to filter models.
        
        Args:
            models: List of models to filter
            constraints: Constraints to apply
            
        Returns:
            Filtered list of models
        """
        filtered = models
        
        # Filter by context length
        if "min_context_length" in constraints:
            min_ctx = constraints["min_context_length"]
            filtered = [m for m in filtered if m.context_length >= min_ctx]
            
        # Filter by capabilities
        if constraints.get("requires_functions"):
            filtered = [m for m in filtered if m.supports_functions]
            
        if constraints.get("requires_vision"):
            filtered = [m for m in filtered if m.supports_vision]
            
        return filtered
        
    def _select_best_performance(self, candidates: List[ModelInfo]) -> ModelInfo:
        """Select model with best performance metrics.
        
        Args:
            candidates: List of candidate models
            
        Returns:
            Best performing model
        """
        # Score models based on success rate and speed
        best_model = None
        best_score = -1
        
        for model in candidates:
            metrics = self.registry.metrics.get(model.id)
            if not metrics or metrics.total_requests == 0:
                # No data, give it a neutral score
                score = 0.5
            else:
                # Combine success rate and speed (normalized)
                success_score = metrics.success_rate
                # Normalize speed score (faster is better, cap at 1000ms)
                speed_score = max(0, 1 - (metrics.avg_time_ms / 1000))
                score = (success_score * 0.7) + (speed_score * 0.3)
                
            if score > best_score:
                best_score = score
                best_model = model
                
        return best_model or candidates[0]
        
    def _select_least_used(self, candidates: List[ModelInfo]) -> ModelInfo:
        """Select least recently used model for load balancing.
        
        Args:
            candidates: List of candidate models
            
        Returns:
            Least recently used model
        """
        # Find model with oldest last success time
        least_used = None
        oldest_time = float('inf')
        
        for model in candidates:
            metrics = self.registry.metrics.get(model.id)
            if not metrics:
                # Never used, perfect candidate
                return model
                
            last_use = metrics.last_success_time or 0
            if last_use < oldest_time:
                oldest_time = last_use
                least_used = model
                
        return least_used or candidates[0]
        
    def _select_fallback_local(self) -> Optional[ModelInfo]:
        """Select a local fallback model.
        
        Returns:
            Local model or None
        """
        local_models = [
            m for m in self.registry.models.values()
            if m.id.startswith("ollama/")
        ]
        
        if local_models:
            # Prefer smaller models for fallback
            return min(local_models, key=lambda m: m.context_length)
            
        return None
        
    def get_model_config(
        self,
        model: ModelInfo,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get configuration dict for a model.
        
        Args:
            model: Selected model
            api_key: API key for the provider
            
        Returns:
            Configuration dictionary for the model
        """
        # Determine provider and settings
        if model.id.startswith("ollama/"):
            provider = "ollama"
            model_id = model.id.replace("ollama/", "")
            # Will use default localhost settings
            config = {
                "provider": provider,
                "model": model_id,
            }
        else:
            # OpenRouter model
            provider = "openrouter"
            config = {
                "provider": provider,
                "model": model.id,
                "api_key": api_key,
            }
            
        # Add common settings
        config.update({
            "temperature": 0.7,
            "max_tokens": min(model.max_output_tokens or 4096, 4096),
        })
        
        return config