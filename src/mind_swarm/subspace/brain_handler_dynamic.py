"""Dynamic DSPy Signature Server - Server-side brain handler with dynamic signature creation.

This module provides the server-side functionality for creating and executing
DSPy signatures dynamically based on generic protocol requests from agents.
"""

import json
import time
import logging
import asyncio
from typing import Dict, Any, Optional, Type, Union
from pathlib import Path
from threading import Lock
from dataclasses import dataclass

import dspy

from mind_swarm.utils.logging import logger
from mind_swarm.subspace.dspy_config import configure_dspy_for_mind_swarm

# Import brain monitor if available
try:
    from mind_swarm.server.brain_monitor import get_brain_monitor
    _has_brain_monitor = True
except ImportError:
    _has_brain_monitor = False


@dataclass
class CachedSignature:
    """A cached DSPy signature with metadata."""
    signature_class: Type
    signature_spec: Dict[str, Any]
    created_at: float
    last_used: float
    use_count: int
    
    def mark_used(self):
        """Mark this signature as recently used."""
        self.last_used = time.time()
        self.use_count += 1


class DSPySignatureFactory:
    """Factory for creating DSPy signatures dynamically."""
    
    def __init__(self):
        self.logger = logger
    
    def create_signature_class(self, spec: Dict[str, Any]) -> Type[dspy.Signature]:
        """Create a DSPy signature class from a specification."""
        
        # Create input fields
        input_fields = {}
        for name, description in spec['inputs'].items():
            input_fields[name] = dspy.InputField(desc=description)
        
        # Create output fields
        output_fields = {}
        for name, description in spec['outputs'].items():
            output_fields[name] = dspy.OutputField(desc=description)
        
        # Combine all fields
        all_fields = {**input_fields, **output_fields}
        all_fields['__doc__'] = f"{spec['task']}\n\n{spec['description']}"
        
        # Create the signature class dynamically
        signature_class = type(
            f"DynamicSignature_{hash(spec['task'])&0xFFFFFFFF:08x}",
            (dspy.Signature,),
            all_fields
        )
        
        self.logger.info(f"Created signature class for task: {spec['task']}")
        return signature_class
    
    def validate_signature_spec(self, spec: Dict[str, Any]) -> list[str]:
        """Validate a signature specification."""
        errors = []
        
        if not spec.get('task', '').strip():
            errors.append("Task cannot be empty")
        
        if not spec.get('inputs'):
            errors.append("Must have at least one input")
        
        if not spec.get('outputs'):
            errors.append("Must have at least one output")
        
        # Check for valid field names (Python identifiers)
        for field_name in list(spec.get('inputs', {}).keys()) + list(spec.get('outputs', {}).keys()):
            if not field_name.isidentifier():
                errors.append(f"Invalid field name: '{field_name}' (must be valid Python identifier)")
        
        # Check for conflicts between input and output names
        input_names = set(spec.get('inputs', {}).keys())
        output_names = set(spec.get('outputs', {}).keys())
        conflicts = input_names & output_names
        if conflicts:
            errors.append(f"Input and output names cannot overlap: {conflicts}")
        
        return errors


class SignatureCache:
    """Thread-safe cache for DSPy signatures."""
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        """Initialize the cache.
        
        Args:
            max_size: Maximum number of signatures to cache
            ttl_seconds: Time-to-live for cached signatures in seconds
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, CachedSignature] = {}
        self.lock = Lock()
        self.logger = logger
    
    def get(self, signature_hash: str) -> Optional[CachedSignature]:
        """Get a cached signature by hash."""
        with self.lock:
            cached = self.cache.get(signature_hash)
            if cached is None:
                return None
            
            # Check if expired
            if time.time() - cached.created_at > self.ttl_seconds:
                del self.cache[signature_hash]
                self.logger.info(f"Expired signature {signature_hash}")
                return None
            
            cached.mark_used()
            return cached
    
    def put(self, signature_hash: str, signature_class: Type, spec: Dict[str, Any]):
        """Cache a signature."""
        with self.lock:
            # Remove oldest if at capacity
            if len(self.cache) >= self.max_size:
                self._evict_oldest()
            
            cached = CachedSignature(
                signature_class=signature_class,
                signature_spec=spec,
                created_at=time.time(),
                last_used=time.time(),
                use_count=1
            )
            
            self.cache[signature_hash] = cached
            self.logger.info(f"Cached signature {signature_hash}")
    
    def _evict_oldest(self):
        """Evict the least recently used signature."""
        if not self.cache:
            return
        
        oldest_hash = min(self.cache.keys(), 
                         key=lambda h: self.cache[h].last_used)
        del self.cache[oldest_hash]
        self.logger.info(f"Evicted signature {oldest_hash}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "signatures": [
                    {
                        "hash": h[:8],
                        "task": cached.signature_spec['task'],
                        "use_count": cached.use_count,
                        "age_seconds": time.time() - cached.created_at
                    }
                    for h, cached in self.cache.items()
                ]
            }


class DynamicBrainHandler:
    """Dynamic brain handler for processing generic thinking requests with DSPy."""
    
    def __init__(self, ai_service, lm_config: Dict[str, Any], cache_size: int = 100, cache_ttl: int = 3600):
        """Initialize the handler.
        
        Args:
            ai_service: The AI service to use for thinking
            lm_config: Language model configuration for DSPy
            cache_size: Maximum number of signatures to cache
            cache_ttl: Cache time-to-live in seconds
        """
        self.ai_service = ai_service
        self.lm_config = lm_config
        self.factory = DSPySignatureFactory()
        self.cache = SignatureCache(cache_size, cache_ttl)
        self.logger = logger
        
        # Configure DSPy with the language model
        self._configure_dspy()
    
    def _configure_dspy(self):
        """Configure DSPy with the appropriate language model."""
        # Use the existing Mind-Swarm DSPy configuration
        self.lm = configure_dspy_for_mind_swarm(self.lm_config)
        self.logger.info(f"Configured DSPy with Mind-Swarm LM: {self.lm_config.get('model')}")
    
    async def process_thinking_request(self, agent_id: str, request_text: str) -> str:
        """Process a thinking request from an agent.
        
        Args:
            agent_id: The agent making the request
            request_text: The thinking request in JSON format
            
        Returns:
            Response text to write back to brain file
        """
        # Emit brain activity event
        if _has_brain_monitor:
            try:
                monitor = get_brain_monitor()
                await monitor.on_brain_request(agent_id, request_text)
            except Exception as e:
                self.logger.debug(f"Failed to emit brain activity: {e}")
        
        try:
            # Remove the end marker if present
            request_text = request_text.split("<<<END_THOUGHT>>>")[0].strip()
            
            # Parse the request
            request_data = json.loads(request_text)
                        
            # Extract components
            signature_spec = request_data['signature']
            input_values = request_data['input_values']
            request_id = request_data.get('request_id', 'unknown')
            context = request_data.get('context', {})
            
            # Validate the request
            errors = self._validate_request(signature_spec, input_values)
            if errors:
                return self._create_error_response(request_id, f"Invalid request: {'; '.join(errors)}")
            
            # Get signature hash
            import hashlib
            canonical = json.dumps(signature_spec, sort_keys=True)
            signature_hash = hashlib.sha256(canonical.encode()).hexdigest()
            
            # Try to get from cache
            cached = self.cache.get(signature_hash)
            if cached:
                signature_class = cached.signature_class
                self.logger.info(f"Using cached signature for {signature_spec['task']}")
            else:
                # Create new signature
                signature_class = self.factory.create_signature_class(signature_spec)
                self.cache.put(signature_hash, signature_class, signature_spec)
                self.logger.info(f"Created new signature for {signature_spec['task']}")
            
            # Execute the signature with retry on rate limit
            max_retries = 3
            retry_count = 0
            last_error = None
            
            while retry_count < max_retries:
                try:
                    # Create a ChainOfThought module with the signature
                    cot = dspy.ChainOfThought(signature_class)
                    
                    # Execute with the provided inputs (async)
                    result = await cot.aforward(**input_values)
                    
                    # Extract outputs
                    output_values = {}
                    for output_name in signature_spec['outputs'].keys():
                        output_values[output_name] = getattr(result, output_name, None)
                    
                    # Create response
                    response_data = {
                        "request_id": request_id,
                        "signature_hash": signature_hash,
                        "output_values": output_values,
                        "metadata": {
                            "cached": cached is not None,
                            "execution_time": time.time(),
                            "signature_task": signature_spec['task'],
                            "agent_id": agent_id,
                            "retry_count": retry_count,
                            "model_used": self.lm.model if hasattr(self, 'lm') else None
                        },
                        "timestamp": time.time()
                    }
                    
                    self.logger.info(f"Successfully processed request {request_id} for agent {agent_id}")
                    return json.dumps(response_data, indent=2) + "\n<<<THOUGHT_COMPLETE>>>"
                    
                except Exception as e:
                    last_error = e
                    error_str = str(e)
                    
                    # Check if it's a rate limit error
                    if "rate limit" in error_str.lower() or "429" in error_str:
                        retry_count += 1
                        if retry_count < max_retries:
                            self.logger.warning(f"Rate limit hit for agent {agent_id}, attempt {retry_count}/{max_retries}")
                            
                            # Try to switch to a different model
                            await self._switch_to_alternative_model(agent_id)
                            
                            # Brief delay before retry
                            await asyncio.sleep(1.0)
                            continue
                    
                    # For other errors, don't retry
                    self.logger.error(f"Error executing signature: {e}")
                    return self._create_error_response(request_id, f"Signature execution failed: {e}")
            
            # All retries exhausted
            self.logger.error(f"All retries exhausted for agent {agent_id}: {last_error}")
            return self._create_error_response(request_id, f"Rate limit persists after {max_retries} retries: {last_error}")
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in request: {e}")
            return self._create_error_response("unknown", f"Invalid JSON: {e}")
        except Exception as e:
            self.logger.error(f"Error processing request: {e}")
            return self._create_error_response("unknown", f"Processing error: {e}")
    
    def _validate_request(self, signature_spec: Dict[str, Any], input_values: Dict[str, Any]) -> list[str]:
        """Validate a thinking request."""
        errors = []
        
        # Validate signature spec
        spec_errors = self.factory.validate_signature_spec(signature_spec)
        errors.extend(spec_errors)
        
        # Check that all required signature inputs have values
        for input_name in signature_spec.get('inputs', {}).keys():
            if input_name not in input_values:
                errors.append(f"Missing input value for '{input_name}'")
        
        # Check for extra input values
        for input_name in input_values.keys():
            if input_name not in signature_spec.get('inputs', {}):
                errors.append(f"Unexpected input value '{input_name}' not in signature")
        
        return errors
    
    def _create_error_response(self, request_id: str, error_message: str) -> str:
        """Create an error response."""
        response_data = {
            "request_id": request_id,
            "signature_hash": "error",
            "output_values": {"error": error_message},
            "metadata": {
                "error": True,
                "error_type": "processing_error",
                "timestamp": time.time()
            }
        }
        return json.dumps(response_data, indent=2) + "\n<<<THOUGHT_COMPLETE>>>"
        
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()
    
    async def _switch_to_alternative_model(self, agent_id: str):
        """Switch to an alternative model when rate limited.
        
        Args:
            agent_id: The agent requesting the switch
        """
        from mind_swarm.ai.model_selector import ModelSelector, SelectionStrategy
        from mind_swarm.ai.model_registry import model_registry
        from mind_swarm.ai.presets import preset_manager
        
        try:
            # Get the model selector with registry
            selector = ModelSelector(model_registry)
            
            # Try to select a different free model from curated list
            new_model_info = selector.select_model(
                strategy=SelectionStrategy.RANDOM_CURATED
            )
            
            if new_model_info and new_model_info.id != getattr(self.lm, 'model', None):
                self.logger.info(f"Switching from {getattr(self.lm, 'model', 'unknown')} to {new_model_info.id} for agent {agent_id}")
                
                # Reconfigure DSPy with the new model
                config = {
                    'provider': 'openrouter',
                    'model': new_model_info.id,
                    'api_key': self.lm_config.get('api_key'),
                    'temperature': self.lm_config.get('temperature', 0.7),
                    'max_tokens': self.lm_config.get('max_tokens', 4096)
                }
                self.lm = configure_dspy_for_mind_swarm(config)
                self.lm_config['model'] = new_model_info.id
            else:
                # No alternative curated model, fall back to local default
                self.logger.warning(f"No alternative curated model for agent {agent_id}, falling back to local default")
                
                # Get the default preset (local model)
                default_preset = preset_manager.get_preset("default")
                if default_preset:
                    config = {
                        'provider': default_preset.provider,
                        'model': default_preset.model,
                        'temperature': default_preset.temperature,
                        'max_tokens': default_preset.max_tokens,
                        'api_settings': default_preset.api_settings
                    }
                    self.lm = configure_dspy_for_mind_swarm(config)
                    self.lm_config.update(config)
                    self.logger.info(f"Switched to local model {default_preset.model} for agent {agent_id}")
                
        except Exception as e:
            self.logger.error(f"Error switching models for agent {agent_id}: {e}")