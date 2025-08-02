"""DSPy Signature Server - Dynamic signature creation and execution with caching.

This module provides the server-side functionality for creating and executing
DSPy signatures dynamically based on generic protocol requests.
"""

import os
import json
import time
import logging
from typing import Dict, Any, Optional, Type, Union
from pathlib import Path
from threading import Lock
from dataclasses import dataclass

# Import DSPy (this would be available on the server side)
try:
    import dspy
    DSPY_AVAILABLE = True
except ImportError:
    DSPY_AVAILABLE = False
    # Mock DSPy classes for development/testing
    class MockDSPy:
        class Signature:
            pass
        class InputField:
            def __init__(self, desc: str):
                self.desc = desc
        class OutputField:
            def __init__(self, desc: str):
                self.desc = desc
        class ChainOfThought:
            def __init__(self, signature):
                self.signature = signature
            def __call__(self, **kwargs):
                # Mock response for testing
                return type('MockResponse', (), {
                    key: f"Mock output for {key}: {desc}" 
                    for key, desc in self.signature._outputs.items()
                })()
    dspy = MockDSPy()

from generic_brain_protocol import (
    SignatureSpec, GenericThinkingRequest, GenericThinkingResponse
)


@dataclass
class CachedSignature:
    """A cached DSPy signature with metadata."""
    signature_class: Type
    signature_spec: SignatureSpec
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
        self.logger = logging.getLogger(__name__)
    
    def create_signature_class(self, spec: SignatureSpec) -> Type[dspy.Signature]:
        """Create a DSPy signature class from a specification."""
        
        # Create input fields
        input_fields = {}
        for name, description in spec.inputs.items():
            input_fields[name] = dspy.InputField(desc=description)
        
        # Create output fields
        output_fields = {}
        for name, description in spec.outputs.items():
            output_fields[name] = dspy.OutputField(desc=description)
        
        # Store field info for mock responses
        all_fields = {**input_fields, **output_fields}
        all_fields['_inputs'] = spec.inputs
        all_fields['_outputs'] = spec.outputs
        all_fields['__doc__'] = f"{spec.task}\n\n{spec.description}"
        
        # Create the signature class dynamically
        signature_class = type(
            f"DynamicSignature_{spec.get_hash()[:8]}",
            (dspy.Signature,),
            all_fields
        )
        
        self.logger.info(f"Created signature class for task: {spec.task}")
        return signature_class
    
    def validate_signature_spec(self, spec: SignatureSpec) -> list[str]:
        """Validate a signature specification."""
        errors = []
        
        if not spec.task.strip():
            errors.append("Task cannot be empty")
        
        if not spec.inputs:
            errors.append("Must have at least one input")
        
        if not spec.outputs:
            errors.append("Must have at least one output")
        
        # Check for valid field names (Python identifiers)
        for field_name in list(spec.inputs.keys()) + list(spec.outputs.keys()):
            if not field_name.isidentifier():
                errors.append(f"Invalid field name: '{field_name}' (must be valid Python identifier)")
        
        # Check for conflicts between input and output names
        input_names = set(spec.inputs.keys())
        output_names = set(spec.outputs.keys())
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
        self.logger = logging.getLogger(__name__)
    
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
    
    def put(self, signature_hash: str, signature_class: Type, spec: SignatureSpec):
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
                        "task": cached.signature_spec.task,
                        "use_count": cached.use_count,
                        "age_seconds": time.time() - cached.created_at
                    }
                    for h, cached in self.cache.items()
                ]
            }


class DSPySignatureServer:
    """Server for processing generic thinking requests with DSPy."""
    
    def __init__(self, cache_size: int = 100, cache_ttl: int = 3600):
        """Initialize the server.
        
        Args:
            cache_size: Maximum number of signatures to cache
            cache_ttl: Cache time-to-live in seconds
        """
        self.factory = DSPySignatureFactory()
        self.cache = SignatureCache(cache_size, cache_ttl)
        self.logger = logging.getLogger(__name__)
        
        # Initialize DSPy (this would be done with actual model configuration)
        if DSPY_AVAILABLE:
            # Example: dspy.settings.configure(lm=dspy.OpenAI(model="gpt-3.5-turbo"))
            pass
    
    def process_request(self, request: GenericThinkingRequest) -> GenericThinkingResponse:
        """Process a generic thinking request."""
        
        # Validate the request
        validation_errors = request.validate()
        if validation_errors:
            raise ValueError(f"Invalid request: {'; '.join(validation_errors)}")
        
        # Validate the signature specification
        spec_errors = self.factory.validate_signature_spec(request.signature)
        if spec_errors:
            raise ValueError(f"Invalid signature: {'; '.join(spec_errors)}")
        
        signature_hash = request.signature.get_hash()
        
        # Try to get from cache
        cached = self.cache.get(signature_hash)
        if cached:
            signature_class = cached.signature_class
            self.logger.info(f"Using cached signature for {request.signature.task}")
        else:
            # Create new signature
            signature_class = self.factory.create_signature_class(request.signature)
            self.cache.put(signature_hash, signature_class, request.signature)
            self.logger.info(f"Created new signature for {request.signature.task}")
        
        # Execute the signature
        try:
            # Create a ChainOfThought module with the signature
            cot = dspy.ChainOfThought(signature_class)
            
            # Execute with the provided inputs
            result = cot(**request.input_values)
            
            # Extract outputs
            output_values = {}
            for output_name in request.signature.outputs.keys():
                output_values[output_name] = getattr(result, output_name, None)
            
            # Create response
            response = GenericThinkingResponse(
                output_values=output_values,
                request_id=request.request_id,
                signature_hash=signature_hash,
                metadata={
                    "cached": cached is not None,
                    "execution_time": time.time(),
                    "signature_task": request.signature.task
                }
            )
            
            self.logger.info(f"Successfully processed request {request.request_id}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error executing signature: {e}")
            raise RuntimeError(f"Signature execution failed: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()


class BrainFileProcessor:
    """Processes brain communication files using the DSPy server."""
    
    def __init__(self, server: DSPySignatureServer, 
                 input_dir: str = "/tmp/brain_input",
                 output_dir: str = "/tmp/brain_output"):
        """Initialize the file processor.
        
        Args:
            server: The DSPy signature server
            input_dir: Directory to watch for input files
            output_dir: Directory to write output files
        """
        self.server = server
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.logger = logging.getLogger(__name__)
        
        # Create directories if they don't exist
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def process_file(self, input_file: Path) -> Path:
        """Process a single brain input file."""
        
        try:
            # Read the request
            content = input_file.read_text()
            request = GenericThinkingRequest.from_brain_format(content)
            
            self.logger.info(f"Processing request {request.request_id} from {input_file.name}")
            
            # Process with the server
            response = self.server.process_request(request)
            
            # Write the response
            output_file = self.output_dir / f"response_{request.request_id}.json"
            output_file.write_text(response.to_brain_format())
            
            self.logger.info(f"Wrote response to {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"Error processing {input_file}: {e}")
            
            # Write error response
            error_response = GenericThinkingResponse(
                output_values={"error": str(e)},
                request_id=getattr(request, 'request_id', 'unknown'),
                signature_hash="error",
                metadata={"error": True, "error_type": type(e).__name__}
            )
            
            error_file = self.output_dir / f"error_{int(time.time())}.json"
            error_file.write_text(error_response.to_brain_format())
            return error_file
    
    def watch_and_process(self, poll_interval: float = 1.0):
        """Watch input directory and process files as they appear."""
        
        self.logger.info(f"Watching {self.input_dir} for brain requests...")
        
        processed_files = set()
        
        while True:
            try:
                # Find new files
                for input_file in self.input_dir.glob("*.json"):
                    if input_file not in processed_files:
                        self.process_file(input_file)
                        processed_files.add(input_file)
                        
                        # Clean up processed file
                        input_file.unlink()
                
                time.sleep(poll_interval)
                
            except KeyboardInterrupt:
                self.logger.info("Stopping file processor")
                break
            except Exception as e:
                self.logger.error(f"Error in watch loop: {e}")
                time.sleep(poll_interval)


# Example usage and testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Create server
    server = DSPySignatureServer()
    
    # Example request
    from generic_brain_protocol import SignatureBuilder, create_request
    
    # Test with OODA observe
    signature = SignatureBuilder.ooda_observe()
    request = create_request(
        signature=signature,
        input_values={
            "working_memory": "I'm working on a Python project",
            "new_messages": "User asked about DSPy integration",
            "environment_state": "Development environment is ready"
        },
        context={"priority": "high"}
    )
    
    print("Processing example request...")
    response = server.process_request(request)
    print(f"Response: {response.output_values}")
    
    # Show cache stats
    print(f"Cache stats: {server.get_cache_stats()}")

