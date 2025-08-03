"""Brain Client - Simple interface for agents to use the generic brain protocol.

This module provides a clean, easy-to-use interface for agents running in sandboxes
to make thinking requests using the generic DSPy protocol without needing to understand
the underlying communication details.
"""

import os
import json
import time
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from dataclasses import dataclass

from brain_protocol import (
    SignatureSpec, GenericThinkingRequest, 
    GenericThinkingResponse, create_request, quick_request
)


@dataclass
class ThinkingResult:
    """Result from a thinking operation."""
    outputs: Dict[str, Any]
    request_id: str
    success: bool
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access to outputs."""
        return self.outputs.get(key)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get an output value with a default."""
        return self.outputs.get(key, default)


class BrainClient:
    """Client for making thinking requests to the brain server."""
    
    def __init__(self, brain_path: Path = None):
        """Initialize the brain client.
        
        Args:
            brain_path: Path to brain file (defaults to /home/brain)
        """
        self.brain_path = brain_path or Path("/home/brain")
    
    def think(self, 
              task: str,
              inputs: Dict[str, str],
              outputs: Dict[str, str],
              input_values: Dict[str, Any],
              description: Optional[str] = None,
              context: Optional[Dict[str, Any]] = None) -> ThinkingResult:
        """Make a thinking request with a custom signature.
        
        Args:
            task: The thinking task or question
            inputs: Dictionary of input_name -> description
            outputs: Dictionary of output_name -> description  
            input_values: Actual values for the inputs
            description: Optional detailed description
            context: Optional additional context
            
        Returns:
            ThinkingResult with the outputs
        """
        request = quick_request(task, inputs, outputs, input_values, description)
        if context:
            request.context.update(context)
        
        return self._send_request(request)
    
    def think_with_signature(self, signature: SignatureSpec, input_values: Dict[str, Any],
                            context: Optional[Dict[str, Any]] = None) -> ThinkingResult:
        """Make a thinking request with a predefined signature.
        
        Args:
            signature: The signature specification (from agent_signatures or custom)
            input_values: Values for the signature's inputs
            context: Optional additional context
            
        Returns:
            ThinkingResult with the outputs
        """
        request = create_request(signature, input_values, context)
        return self._send_request(request)
    
    def _send_request(self, request: GenericThinkingRequest) -> ThinkingResult:
        """Send a request to the brain and wait for response."""
        
        try:
            # Write request to brain file
            self.brain_path.write_text(request.to_brain_format())
            
            # Read response
            response_text = self.brain_path.read_text()
            
            # Parse response
            response = GenericThinkingResponse.from_brain_format(response_text)
            
            return ThinkingResult(
                outputs=response.output_values,
                request_id=response.request_id,
                success=True,
                metadata=response.metadata
            )
            
        except Exception as e:
            return ThinkingResult(
                outputs={},
                request_id=request.request_id,
                success=False,
                error=f"Brain client error: {e}"
            )




