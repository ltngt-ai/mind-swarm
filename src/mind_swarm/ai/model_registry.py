"""Model registry for managing available AI models and their metadata.

This module fetches and caches model information from providers like OpenRouter,
categorizes them by cost, and tracks performance metrics.
"""

import asyncio
import json
import time
import yaml
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

from mind_swarm.ai.providers.openrouter import OpenRouterAIService
from mind_swarm.ai.config import AIExecutionConfig
from mind_swarm.utils.logging import logger


@dataclass
class ModelInfo:
    """Information about an AI model."""
    id: str
    name: str
    provider: str  # The actual provider (e.g., "anthropic", "google")
    context_length: int
    max_output_tokens: Optional[int]
    input_cost: float  # Cost per million tokens
    output_cost: float  # Cost per million tokens
    is_free: bool
    supports_functions: bool = False
    supports_vision: bool = False
    
    @property
    def is_priced(self) -> bool:
        """Check if this is a priced model."""
        return not self.is_free


@dataclass
class ModelMetrics:
    """Performance metrics for a model."""
    model_id: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    total_time_ms: float = 0
    last_error: Optional[str] = None
    last_error_time: Optional[float] = None
    last_success_time: Optional[float] = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests
    
    @property
    def avg_time_ms(self) -> float:
        """Calculate average response time in milliseconds."""
        if self.successful_requests == 0:
            return 0.0
        return self.total_time_ms / self.successful_requests
    
    @property
    def tokens_per_second(self) -> float:
        """Calculate average tokens per second."""
        if self.total_time_ms == 0 or self.total_tokens == 0:
            return 0.0
        return (self.total_tokens / self.total_time_ms) * 1000


class ModelRegistry:
    """Registry for available AI models and their metrics."""
    
    def __init__(self, cache_ttl_minutes: int = 60, config_dir: Optional[Path] = None):
        """Initialize the model registry.
        
        Args:
            cache_ttl_minutes: How long to cache model list
            config_dir: Directory containing curated_models.yaml and blacklist_models.yaml
        """
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self.models: Dict[str, ModelInfo] = {}
        self.metrics: Dict[str, ModelMetrics] = {}
        self.last_fetch_time: Optional[datetime] = None
        self._lock = asyncio.Lock()
        
        # Configuration
        self.config_dir = config_dir or Path("config")
        self.curated_models: List[str] = []
        self.blacklisted_models: Set[str] = set()
        self.blacklist_patterns: List[re.Pattern] = []
        self.use_curated_only: bool = True
        
        # Load configuration from YAML files
        self._load_configuration()
    
    def _load_configuration(self):
        """Load curated models and blacklist from YAML files."""
        # Load curated models
        curated_file = self.config_dir / "curated_models.yaml"
        if curated_file.exists():
            try:
                with open(curated_file, 'r') as f:
                    data = yaml.safe_load(f)
                    # Extract model IDs from the curated list
                    self.curated_models = [
                        model['id'] for model in data.get('curated_free_models', [])
                    ]
                    # Load config settings
                    config = data.get('config', {})
                    self.use_curated_only = config.get('use_curated_only', True)
                    logger.info(f"Loaded {len(self.curated_models)} curated models")
            except Exception as e:
                logger.error(f"Error loading curated models: {e}")
                # Fallback to hardcoded list
                self.curated_models = [
                    "google/gemini-2.0-flash-exp:free",
                    "meta-llama/llama-3.2-3b-instruct:free",
                    "meta-llama/llama-3.3-70b-instruct:free",
                    "qwen/qwen-2.5-72b-instruct:free",
                    "qwen/qwen-2.5-coder-32b-instruct:free",
                    "google/gemma-2-9b-it:free",
                ]
        
        # Load blacklist
        blacklist_file = self.config_dir / "blacklist_models.yaml"
        if blacklist_file.exists():
            try:
                with open(blacklist_file, 'r') as f:
                    data = yaml.safe_load(f)
                    # Load blacklisted model IDs
                    for model in data.get('blacklisted_models', []):
                        self.blacklisted_models.add(model['id'])
                    # Load temporary blacklist
                    for model in data.get('temporary_blacklist', []):
                        # Check if still within blacklist period
                        until = model.get('blacklisted_until')
                        if until:
                            until_date = datetime.strptime(until, "%Y-%m-%d")
                            if datetime.now() < until_date:
                                self.blacklisted_models.add(model['id'])
                    # Load pattern blacklist
                    for pattern_config in data.get('pattern_blacklist', []):
                        pattern = pattern_config.get('pattern')
                        if pattern:
                            self.blacklist_patterns.append(re.compile(pattern))
                    logger.info(f"Loaded {len(self.blacklisted_models)} blacklisted models and {len(self.blacklist_patterns)} patterns")
            except Exception as e:
                logger.error(f"Error loading blacklist: {e}")
    
    def is_model_blacklisted(self, model_id: str) -> bool:
        """Check if a model is blacklisted.
        
        Args:
            model_id: The model ID to check
            
        Returns:
            True if the model is blacklisted
        """
        # Check direct blacklist
        if model_id in self.blacklisted_models:
            return True
        
        # Check pattern blacklist
        for pattern in self.blacklist_patterns:
            if pattern.match(model_id):
                return True
        
        return False
        
    async def initialize(self, api_key: Optional[str] = None):
        """Initialize the registry by fetching available models.
        
        Args:
            api_key: OpenRouter API key
        """
        await self.refresh_models(api_key)
        
    async def refresh_models(self, api_key: Optional[str] = None, force: bool = False):
        """Refresh the model list from providers.
        
        Args:
            api_key: OpenRouter API key
            force: Force refresh even if cache is valid
        """
        async with self._lock:
            # Check cache
            if not force and self.last_fetch_time:
                if datetime.now() - self.last_fetch_time < self.cache_ttl:
                    logger.debug("Using cached model list")
                    return
            
            logger.info("Refreshing model list from providers")
            
            # Clear existing models
            self.models.clear()
            
            # Add local models first (always available)
            self._add_local_models()
            
            # Fetch from OpenRouter if API key is available
            if api_key:
                try:
                    await self._fetch_openrouter_models(api_key)
                except Exception as e:
                    logger.error(f"Failed to fetch OpenRouter models: {e}")
            
            self.last_fetch_time = datetime.now()
            logger.info(f"Loaded {len(self.models)} models total")
            
    def _add_local_models(self):
        """Add local/Ollama models to the registry."""
        local_models = [
            ModelInfo(
                id="ollama/llama3.2:3b",
                name="Llama 3.2 3B (Local)",
                provider="meta-llama",
                context_length=8192,
                max_output_tokens=2048,
                input_cost=0.0,
                output_cost=0.0,
                is_free=True,
            ),
            ModelInfo(
                id="ollama/llama3.2:8b",
                name="Llama 3.2 8B (Local)",
                provider="meta-llama",
                context_length=8192,
                max_output_tokens=4096,
                input_cost=0.0,
                output_cost=0.0,
                is_free=True,
            ),
        ]
        
        for model in local_models:
            self.models[model.id] = model
            # Initialize metrics
            if model.id not in self.metrics:
                self.metrics[model.id] = ModelMetrics(model_id=model.id)
                
    async def _fetch_openrouter_models(self, api_key: str):
        """Fetch models from OpenRouter API."""
        config = AIExecutionConfig(
            provider="openrouter",
            model_id="dummy",  # Not used for listing
            api_key=api_key,
        )
        
        service = OpenRouterAIService(config)
        
        try:
            models_data = service.list_models()
            
            for model_data in models_data:
                # Extract model info
                model_id = model_data.get("id", "")
                if not model_id:
                    continue
                    
                # Parse costs (OpenRouter provides costs per token)
                pricing = model_data.get("pricing", {})
                input_cost = float(pricing.get("prompt", 0)) * 1_000_000  # Convert to per million
                output_cost = float(pricing.get("completion", 0)) * 1_000_000
                
                model_info = ModelInfo(
                    id=model_id,
                    name=model_data.get("name", model_id),
                    provider=model_id.split("/")[0] if "/" in model_id else "unknown",
                    context_length=model_data.get("context_length", 4096),
                    max_output_tokens=model_data.get("max_completion_tokens"),
                    input_cost=input_cost,
                    output_cost=output_cost,
                    is_free=(input_cost == 0 and output_cost == 0),
                    supports_functions=model_data.get("supports_functions", False),
                    supports_vision=model_data.get("supports_vision", False),
                )
                
                self.models[model_id] = model_info
                
                # Initialize metrics if not exists
                if model_id not in self.metrics:
                    self.metrics[model_id] = ModelMetrics(model_id=model_id)
                    
            logger.info(f"Fetched {len(models_data)} models from OpenRouter")
            
        except Exception as e:
            logger.error(f"Error fetching OpenRouter models: {e}")
            raise
            
    def get_free_models(self, curated_only: bool = False) -> List[ModelInfo]:
        """Get list of free models.
        
        Args:
            curated_only: If True, only return curated models
            
        Returns:
            List of free models
        """
        if curated_only:
            # Return only curated models that exist in our registry
            return [
                self.models[model_id]
                for model_id in self.curated_models
                if model_id in self.models and not self.is_model_blacklisted(model_id)
            ]
        else:
            return [
                m for m in self.models.values() 
                if m.is_free and not self.is_model_blacklisted(m.id)
            ]
            
    def get_priced_models(self) -> List[ModelInfo]:
        """Get list of priced models.
        
        Returns:
            List of priced models
        """
        return [m for m in self.models.values() if m.is_priced]
        
    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """Get a specific model by ID.
        
        Args:
            model_id: Model ID
            
        Returns:
            ModelInfo or None if not found
        """
        return self.models.get(model_id)
        
    def update_metrics(
        self,
        model_id: str,
        success: bool,
        time_ms: float,
        tokens: int = 0,
        error: Optional[str] = None
    ):
        """Update metrics for a model.
        
        Args:
            model_id: Model ID
            success: Whether the request was successful
            time_ms: Response time in milliseconds
            tokens: Number of tokens processed
            error: Error message if failed
        """
        if model_id not in self.metrics:
            self.metrics[model_id] = ModelMetrics(model_id=model_id)
            
        metrics = self.metrics[model_id]
        metrics.total_requests += 1
        
        if success:
            metrics.successful_requests += 1
            metrics.total_time_ms += time_ms
            metrics.total_tokens += tokens
            metrics.last_success_time = time.time()
        else:
            metrics.failed_requests += 1
            metrics.last_error = error
            metrics.last_error_time = time.time()
            
    async def write_to_grid(self, grid_path: Path):
        """Write model information to the grid for agent visibility.
        
        Args:
            grid_path: Path to grid root
        """
        models_dir = grid_path / "library" / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        
        # Write available models
        models_data = {
            "last_updated": self.last_fetch_time.isoformat() if self.last_fetch_time else None,
            "free_models": [asdict(m) for m in self.get_free_models()],
            "priced_models": [asdict(m) for m in self.get_priced_models()],
            "curated_free_models": self.curated_models,
        }
        
        models_file = models_dir / "available_models.json"
        with open(models_file, "w") as f:
            json.dump(models_data, f, indent=2)
            
        # Write metrics
        metrics_data = {
            "last_updated": datetime.now().isoformat(),
            "metrics": {
                model_id: {
                    "model_id": m.model_id,
                    "total_requests": m.total_requests,
                    "success_rate": m.success_rate,
                    "avg_time_ms": m.avg_time_ms,
                    "tokens_per_second": m.tokens_per_second,
                    "last_error": m.last_error,
                    "last_error_time": m.last_error_time,
                    "last_success_time": m.last_success_time,
                }
                for model_id, m in self.metrics.items()
            }
        }
        
        metrics_file = models_dir / "model_metrics.json"
        with open(metrics_file, "w") as f:
            json.dump(metrics_data, f, indent=2)
            
        logger.debug(f"Wrote model data to {models_dir}")


# Global registry instance
model_registry = ModelRegistry()