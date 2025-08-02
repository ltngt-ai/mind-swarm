"""Brain Client - Simple interface for agents to use the generic brain protocol.

This module provides a clean, easy-to-use interface for agents running in sandboxes
to make thinking requests using the generic DSPy protocol without needing to understand
the underlying communication details.
"""

import os
import json
import time
import tempfile
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from dataclasses import dataclass

from generic_brain_protocol import (
    SignatureSpec, SignatureBuilder, GenericThinkingRequest, 
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
    
    def __init__(self, 
                 communication_dir: str = "/tmp/brain_comm",
                 timeout: float = 30.0,
                 poll_interval: float = 0.5):
        """Initialize the brain client.
        
        Args:
            communication_dir: Directory for brain communication files
            timeout: Maximum time to wait for responses
            poll_interval: How often to check for responses
        """
        self.communication_dir = Path(communication_dir)
        self.timeout = timeout
        self.poll_interval = poll_interval
        
        # Create communication directories
        self.input_dir = self.communication_dir / "input"
        self.output_dir = self.communication_dir / "output"
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
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
    
    def observe(self, 
                working_memory: str,
                new_messages: str = "",
                environment_state: str = "",
                custom_inputs: Optional[Dict[str, str]] = None) -> ThinkingResult:
        """OODA Loop: Observe the environment."""
        
        signature = SignatureBuilder.ooda_observe(custom_inputs)
        input_values = {
            "working_memory": working_memory,
            "new_messages": new_messages,
            "environment_state": environment_state
        }
        
        # Add any custom input values
        if custom_inputs:
            for key in custom_inputs.keys():
                if key not in input_values:
                    input_values[key] = ""
        
        request = create_request(signature, input_values)
        return self._send_request(request)
    
    def orient(self,
               observations: str,
               current_task: str = "",
               recent_history: str = "",
               custom_inputs: Optional[Dict[str, str]] = None) -> ThinkingResult:
        """OODA Loop: Orient and understand the situation."""
        
        signature = SignatureBuilder.ooda_orient(custom_inputs)
        input_values = {
            "observations": observations,
            "current_task": current_task,
            "recent_history": recent_history
        }
        
        # Add any custom input values
        if custom_inputs:
            for key in custom_inputs.keys():
                if key not in input_values:
                    input_values[key] = ""
        
        request = create_request(signature, input_values)
        return self._send_request(request)
    
    def decide(self,
               understanding: str,
               available_actions: Union[str, List[str]],
               goals: str = "",
               constraints: str = "",
               custom_inputs: Optional[Dict[str, str]] = None) -> ThinkingResult:
        """OODA Loop: Decide what to do."""
        
        signature = SignatureBuilder.ooda_decide(custom_inputs)
        
        # Convert list to string if needed
        if isinstance(available_actions, list):
            available_actions = "; ".join(available_actions)
        
        input_values = {
            "understanding": understanding,
            "available_actions": available_actions,
            "goals": goals,
            "constraints": constraints
        }
        
        # Add any custom input values
        if custom_inputs:
            for key in custom_inputs.keys():
                if key not in input_values:
                    input_values[key] = ""
        
        request = create_request(signature, input_values)
        return self._send_request(request)
    
    def act(self,
            decision: str,
            approach: str,
            available_tools: Union[str, List[str]] = "",
            current_state: str = "",
            custom_inputs: Optional[Dict[str, str]] = None) -> ThinkingResult:
        """OODA Loop: Plan how to act on the decision."""
        
        signature = SignatureBuilder.ooda_act(custom_inputs)
        
        # Convert list to string if needed
        if isinstance(available_tools, list):
            available_tools = "; ".join(available_tools)
        
        input_values = {
            "decision": decision,
            "approach": approach,
            "available_tools": available_tools,
            "current_state": current_state
        }
        
        # Add any custom input values
        if custom_inputs:
            for key in custom_inputs.keys():
                if key not in input_values:
                    input_values[key] = ""
        
        request = create_request(signature, input_values)
        return self._send_request(request)
    
    def solve_problem(self,
                     problem: str,
                     context: str = "",
                     available_resources: str = "",
                     problem_type: str = "general") -> ThinkingResult:
        """Solve a problem step by step."""
        
        signature = SignatureBuilder.solve_problem(problem_type)
        input_values = {
            "problem": problem,
            "context": context,
            "available_resources": available_resources
        }
        
        request = create_request(signature, input_values)
        return self._send_request(request)
    
    def answer_question(self,
                       question: str,
                       context: str = "",
                       knowledge_base: str = "",
                       domain: str = "general") -> ThinkingResult:
        """Answer a question thoughtfully."""
        
        signature = SignatureBuilder.answer_question(domain)
        input_values = {
            "question": question,
            "context": context,
            "knowledge_base": knowledge_base
        }
        
        request = create_request(signature, input_values)
        return self._send_request(request)
    
    def _send_request(self, request: GenericThinkingRequest) -> ThinkingResult:
        """Send a request and wait for response."""
        
        try:
            # Write request to input file
            input_file = self.input_dir / f"request_{request.request_id}.json"
            input_file.write_text(request.to_brain_format())
            
            # Wait for response
            start_time = time.time()
            while time.time() - start_time < self.timeout:
                # Look for response file
                response_files = list(self.output_dir.glob(f"response_{request.request_id}.json"))
                error_files = list(self.output_dir.glob(f"error_*.json"))
                
                if response_files:
                    response_file = response_files[0]
                    content = response_file.read_text()
                    response = GenericThinkingResponse.from_brain_format(content)
                    
                    # Clean up
                    response_file.unlink()
                    
                    return ThinkingResult(
                        outputs=response.output_values,
                        request_id=response.request_id,
                        success=True,
                        metadata=response.metadata
                    )
                
                # Check for error files (less specific matching)
                if error_files:
                    error_file = error_files[-1]  # Get most recent
                    content = error_file.read_text()
                    try:
                        response = GenericThinkingResponse.from_brain_format(content)
                        error_msg = response.output_values.get("error", "Unknown error")
                        
                        # Clean up
                        error_file.unlink()
                        
                        return ThinkingResult(
                            outputs={},
                            request_id=request.request_id,
                            success=False,
                            error=error_msg
                        )
                    except:
                        pass
                
                time.sleep(self.poll_interval)
            
            # Timeout
            return ThinkingResult(
                outputs={},
                request_id=request.request_id,
                success=False,
                error=f"Timeout after {self.timeout} seconds"
            )
            
        except Exception as e:
            return ThinkingResult(
                outputs={},
                request_id=request.request_id,
                success=False,
                error=f"Client error: {e}"
            )


class SimpleBrain:
    """Ultra-simple interface for basic thinking operations."""
    
    def __init__(self, client: Optional[BrainClient] = None):
        """Initialize with optional custom client."""
        self.client = client or BrainClient()
    
    def ask(self, question: str, context: str = "") -> str:
        """Ask a simple question and get a text answer."""
        result = self.client.answer_question(question, context)
        if result.success:
            return result.get("answer", "No answer provided")
        else:
            return f"Error: {result.error}"
    
    def solve(self, problem: str, context: str = "") -> str:
        """Solve a problem and get the solution."""
        result = self.client.solve_problem(problem, context)
        if result.success:
            return result.get("solution", "No solution provided")
        else:
            return f"Error: {result.error}"
    
    def decide(self, situation: str, options: List[str], goals: str = "") -> str:
        """Make a decision given a situation and options."""
        options_str = "; ".join(options)
        result = self.client.decide(
            understanding=situation,
            available_actions=options_str,
            goals=goals
        )
        if result.success:
            return result.get("decision", "No decision provided")
        else:
            return f"Error: {result.error}"


# Convenience functions for one-off operations
def quick_think(task: str, **inputs) -> ThinkingResult:
    """Quick thinking operation with automatic input/output inference."""
    client = BrainClient()
    
    # Create simple signature
    input_specs = {k: f"Input: {k}" for k in inputs.keys()}
    output_specs = {"result": "The result of the thinking operation"}
    
    return client.think(
        task=task,
        inputs=input_specs,
        outputs=output_specs,
        input_values=inputs
    )


def quick_ask(question: str, context: str = "") -> str:
    """Quick question asking."""
    brain = SimpleBrain()
    return brain.ask(question, context)


def quick_solve(problem: str, context: str = "") -> str:
    """Quick problem solving."""
    brain = SimpleBrain()
    return brain.solve(problem, context)


# Example usage
if __name__ == "__main__":
    # Create client
    client = BrainClient()
    
    # Example 1: OODA Loop
    print("=== OODA Loop Example ===")
    
    # Observe
    obs_result = client.observe(
        working_memory="Working on a Python project",
        new_messages="User wants DSPy integration",
        environment_state="Development environment ready"
    )
    print(f"Observations: {obs_result.get('observations')}")
    
    # Orient
    orient_result = client.orient(
        observations=obs_result.get('observations', ''),
        current_task="Implementing DSPy protocol"
    )
    print(f"Understanding: {orient_result.get('understanding')}")
    
    # Decide
    decide_result = client.decide(
        understanding=orient_result.get('understanding', ''),
        available_actions=["Create generic protocol", "Use existing protocol", "Research alternatives"],
        goals="Create flexible DSPy integration"
    )
    print(f"Decision: {decide_result.get('decision')}")
    
    # Example 2: Simple operations
    print("\n=== Simple Operations ===")
    
    brain = SimpleBrain()
    answer = brain.ask("What are the benefits of caching in software systems?")
    print(f"Answer: {answer}")
    
    solution = brain.solve("How to implement a thread-safe cache in Python?")
    print(f"Solution: {solution}")
    
    # Example 3: Custom thinking
    print("\n=== Custom Thinking ===")
    
    result = client.think(
        task="Analyze the trade-offs of this design decision",
        inputs={
            "decision": "The design decision to analyze",
            "criteria": "Criteria for evaluation"
        },
        outputs={
            "pros": "Advantages of this decision",
            "cons": "Disadvantages of this decision", 
            "recommendation": "Overall recommendation"
        },
        input_values={
            "decision": "Using dynamic signature creation vs predefined types",
            "criteria": "Flexibility, performance, maintainability, complexity"
        }
    )
    
    if result.success:
        print(f"Pros: {result.get('pros')}")
        print(f"Cons: {result.get('cons')}")
        print(f"Recommendation: {result.get('recommendation')}")
    else:
        print(f"Error: {result.error}")

