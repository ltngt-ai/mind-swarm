"""Test Examples - Comprehensive testing and examples for the generic DSPy protocol.

This module demonstrates various use cases and validates the functionality of the
generic brain protocol system.
"""

import os
import sys
import time
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, List

# Import our modules
from generic_brain_protocol import (
    SignatureSpec, SignatureBuilder, GenericThinkingRequest, 
    GenericThinkingResponse, create_request, quick_request
)
from dspy_signature_server import DSPySignatureServer, BrainFileProcessor
from brain_client import BrainClient, SimpleBrain, quick_ask, quick_solve


class TestRunner:
    """Test runner for the generic brain protocol system."""
    
    def __init__(self):
        self.server = DSPySignatureServer()
        self.test_results = []
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Set up communication directories
        self.comm_dir = self.temp_dir / "brain_comm"
        self.client = BrainClient(str(self.comm_dir), timeout=5.0)
        
        print(f"Test environment: {self.temp_dir}")
    
    def run_test(self, name: str, test_func):
        """Run a single test and record results."""
        print(f"\n=== Testing: {name} ===")
        try:
            start_time = time.time()
            result = test_func()
            duration = time.time() - start_time
            
            self.test_results.append({
                "name": name,
                "success": True,
                "duration": duration,
                "result": result
            })
            print(f"✓ PASSED ({duration:.2f}s)")
            return True
            
        except Exception as e:
            self.test_results.append({
                "name": name,
                "success": False,
                "error": str(e)
            })
            print(f"✗ FAILED: {e}")
            return False
    
    def test_signature_creation(self):
        """Test dynamic signature creation."""
        spec = SignatureSpec(
            task="Test signature creation",
            description="A test signature for validation",
            inputs={"test_input": "A test input field"},
            outputs={"test_output": "A test output field"}
        )
        
        # Test hash generation
        hash1 = spec.get_hash()
        hash2 = spec.get_hash()
        assert hash1 == hash2, "Hash should be consistent"
        
        # Test serialization
        spec_dict = spec.to_dict()
        spec_restored = SignatureSpec.from_dict(spec_dict)
        assert spec_restored.task == spec.task
        assert spec_restored.inputs == spec.inputs
        
        return "Signature creation and serialization works"
    
    def test_request_validation(self):
        """Test request validation."""
        spec = SignatureSpec(
            task="Test validation",
            description="Test request validation",
            inputs={"required_input": "A required input"},
            outputs={"output": "An output"}
        )
        
        # Valid request
        valid_request = GenericThinkingRequest(
            signature=spec,
            input_values={"required_input": "test value"}
        )
        errors = valid_request.validate()
        assert len(errors) == 0, f"Valid request should have no errors: {errors}"
        
        # Invalid request - missing input
        invalid_request = GenericThinkingRequest(
            signature=spec,
            input_values={}
        )
        errors = invalid_request.validate()
        assert len(errors) > 0, "Invalid request should have errors"
        
        return "Request validation works correctly"
    
    def test_brain_format_serialization(self):
        """Test brain format serialization and deserialization."""
        spec = SignatureSpec(
            task="Test serialization",
            description="Test brain format",
            inputs={"input1": "First input"},
            outputs={"output1": "First output"}
        )
        
        request = GenericThinkingRequest(
            signature=spec,
            input_values={"input1": "test value"},
            context={"test": True}
        )
        
        # Test request serialization
        brain_format = request.to_brain_format()
        assert "<<<END_THOUGHT>>>" in brain_format
        
        # Test request deserialization
        restored_request = GenericThinkingRequest.from_brain_format(brain_format)
        assert restored_request.signature.task == spec.task
        assert restored_request.input_values == request.input_values
        
        # Test response serialization
        response = GenericThinkingResponse(
            output_values={"output1": "test output"},
            request_id=request.request_id,
            signature_hash=spec.get_hash()
        )
        
        response_format = response.to_brain_format()
        assert "<<<THOUGHT_COMPLETE>>>" in response_format
        
        # Test response deserialization
        restored_response = GenericThinkingResponse.from_brain_format(response_format)
        assert restored_response.output_values == response.output_values
        
        return "Brain format serialization works correctly"
    
    def test_server_processing(self):
        """Test server-side request processing."""
        spec = SignatureSpec(
            task="Test server processing",
            description="Test that the server can process requests",
            inputs={"question": "A question to answer"},
            outputs={"answer": "The answer to the question"}
        )
        
        request = GenericThinkingRequest(
            signature=spec,
            input_values={"question": "What is 2 + 2?"}
        )
        
        # Process the request
        response = self.server.process_request(request)
        
        assert response.request_id == request.request_id
        assert response.signature_hash == spec.get_hash()
        assert "answer" in response.output_values
        
        return f"Server processing works: {response.output_values['answer']}"
    
    def test_signature_caching(self):
        """Test signature caching functionality."""
        spec = SignatureSpec(
            task="Test caching",
            description="Test signature caching",
            inputs={"input": "Test input"},
            outputs={"output": "Test output"}
        )
        
        request1 = GenericThinkingRequest(signature=spec, input_values={"input": "value1"})
        request2 = GenericThinkingRequest(signature=spec, input_values={"input": "value2"})
        
        # First request should create signature
        response1 = self.server.process_request(request1)
        cache_stats1 = self.server.get_cache_stats()
        
        # Second request should use cached signature
        response2 = self.server.process_request(request2)
        cache_stats2 = self.server.get_cache_stats()
        
        # Check that cache was used
        assert cache_stats1["size"] == 1
        assert cache_stats2["size"] == 1  # Same signature, so same cache size
        
        # Check that the cached signature was used more than once
        cached_sig = None
        for sig_info in cache_stats2["signatures"]:
            if sig_info["task"] == spec.task:
                cached_sig = sig_info
                break
        
        assert cached_sig is not None
        assert cached_sig["use_count"] >= 2
        
        return f"Caching works: {cached_sig['use_count']} uses"
    
    def test_signature_builders(self):
        """Test the signature builder helpers."""
        # Test OODA builders
        observe_sig = SignatureBuilder.ooda_observe()
        assert "working_memory" in observe_sig.inputs
        assert "observations" in observe_sig.outputs
        
        orient_sig = SignatureBuilder.ooda_orient()
        assert "observations" in orient_sig.inputs
        assert "understanding" in orient_sig.outputs
        
        decide_sig = SignatureBuilder.ooda_decide()
        assert "understanding" in decide_sig.inputs
        assert "decision" in decide_sig.outputs
        
        act_sig = SignatureBuilder.ooda_act()
        assert "decision" in act_sig.inputs
        assert "steps" in act_sig.outputs
        
        # Test custom builder
        custom_sig = SignatureBuilder.custom(
            task="Custom task",
            inputs={"custom_input": "Custom input description"},
            outputs={"custom_output": "Custom output description"}
        )
        assert custom_sig.task == "Custom task"
        assert "custom_input" in custom_sig.inputs
        
        return "Signature builders work correctly"
    
    def test_ooda_loop_integration(self):
        """Test a complete OODA loop using the server."""
        # Observe
        observe_request = create_request(
            SignatureBuilder.ooda_observe(),
            {
                "working_memory": "Working on testing the brain protocol",
                "new_messages": "Need to validate OODA loop functionality",
                "environment_state": "Test environment is ready"
            }
        )
        observe_response = self.server.process_request(observe_request)
        observations = observe_response.output_values.get("observations", "")
        
        # Orient
        orient_request = create_request(
            SignatureBuilder.ooda_orient(),
            {
                "observations": observations,
                "current_task": "Testing OODA loop",
                "recent_history": "Just started testing"
            }
        )
        orient_response = self.server.process_request(orient_request)
        understanding = orient_response.output_values.get("understanding", "")
        
        # Decide
        decide_request = create_request(
            SignatureBuilder.ooda_decide(),
            {
                "understanding": understanding,
                "available_actions": "Continue testing; Report results; Fix issues",
                "goals": "Validate OODA loop functionality",
                "constraints": "Must complete within test timeframe"
            }
        )
        decide_response = self.server.process_request(decide_request)
        decision = decide_response.output_values.get("decision", "")
        
        # Act
        act_request = create_request(
            SignatureBuilder.ooda_act(),
            {
                "decision": decision,
                "approach": "Systematic testing approach",
                "available_tools": "Test framework; Assertion methods",
                "current_state": "In testing phase"
            }
        )
        act_response = self.server.process_request(act_request)
        steps = act_response.output_values.get("steps", "")
        
        return f"OODA loop completed: {decision} -> {steps}"
    
    def test_problem_solving(self):
        """Test problem-solving capabilities."""
        problem_request = create_request(
            SignatureBuilder.solve_problem("mathematical"),
            {
                "problem": "If I have 10 apples and give away 3, then buy 5 more, how many do I have?",
                "context": "Simple arithmetic word problem",
                "available_resources": "Basic math operations"
            }
        )
        
        response = self.server.process_request(problem_request)
        solution = response.output_values.get("solution", "")
        answer = response.output_values.get("answer", "")
        
        return f"Problem solved: {solution} -> Answer: {answer}"
    
    def test_question_answering(self):
        """Test question-answering capabilities."""
        qa_request = create_request(
            SignatureBuilder.answer_question("technology"),
            {
                "question": "What are the main benefits of using caching in software systems?",
                "context": "Software engineering discussion",
                "knowledge_base": "General software engineering knowledge"
            }
        )
        
        response = self.server.process_request(qa_request)
        answer = response.output_values.get("answer", "")
        confidence = response.output_values.get("confidence", "")
        
        return f"Question answered with confidence {confidence}: {answer[:100]}..."
    
    def test_custom_signatures(self):
        """Test completely custom signature creation."""
        # Create a custom signature for code review
        code_review_request = quick_request(
            task="Review this code for potential issues",
            inputs={
                "code": "The code to review",
                "language": "Programming language",
                "focus_areas": "Specific areas to focus on"
            },
            outputs={
                "issues": "List of potential issues found",
                "suggestions": "Suggestions for improvement",
                "overall_quality": "Overall code quality assessment"
            },
            input_values={
                "code": "def add(a, b): return a + b",
                "language": "Python",
                "focus_areas": "Style, efficiency, error handling"
            }
        )
        
        response = self.server.process_request(code_review_request)
        issues = response.output_values.get("issues", "")
        suggestions = response.output_values.get("suggestions", "")
        
        return f"Code review completed: Issues: {issues}, Suggestions: {suggestions}"
    
    def run_all_tests(self):
        """Run all tests and report results."""
        print("Starting Generic DSPy Protocol Test Suite")
        print("=" * 50)
        
        tests = [
            ("Signature Creation", self.test_signature_creation),
            ("Request Validation", self.test_request_validation),
            ("Brain Format Serialization", self.test_brain_format_serialization),
            ("Server Processing", self.test_server_processing),
            ("Signature Caching", self.test_signature_caching),
            ("Signature Builders", self.test_signature_builders),
            ("OODA Loop Integration", self.test_ooda_loop_integration),
            ("Problem Solving", self.test_problem_solving),
            ("Question Answering", self.test_question_answering),
            ("Custom Signatures", self.test_custom_signatures),
        ]
        
        passed = 0
        failed = 0
        
        for name, test_func in tests:
            if self.run_test(name, test_func):
                passed += 1
            else:
                failed += 1
        
        print("\n" + "=" * 50)
        print(f"Test Results: {passed} passed, {failed} failed")
        
        if failed == 0:
            print("🎉 All tests passed!")
        else:
            print("❌ Some tests failed")
        
        # Show cache statistics
        print(f"\nFinal cache stats: {self.server.get_cache_stats()}")
        
        return failed == 0


def demo_client_usage():
    """Demonstrate client usage patterns."""
    print("\n" + "=" * 50)
    print("Client Usage Demonstration")
    print("=" * 50)
    
    # Note: This would require the server to be running
    # For demo purposes, we'll show the API usage
    
    print("\n1. Simple Brain Interface:")
    print("brain = SimpleBrain()")
    print("answer = brain.ask('What is machine learning?')")
    print("# Would return: 'Machine learning is...'")
    
    print("\n2. OODA Loop with BrainClient:")
    print("client = BrainClient()")
    print("obs = client.observe('Current state', 'New info', 'Environment')")
    print("orient = client.orient(obs['observations'], 'Current task')")
    print("decision = client.decide(orient['understanding'], ['Option A', 'Option B'])")
    print("plan = client.act(decision['decision'], decision['approach'])")
    
    print("\n3. Custom Thinking:")
    print("result = client.think(")
    print("    task='Analyze this design decision',")
    print("    inputs={'decision': 'The decision to analyze'},")
    print("    outputs={'pros': 'Advantages', 'cons': 'Disadvantages'},")
    print("    input_values={'decision': 'Use microservices architecture'}")
    print(")")
    
    print("\n4. Quick Operations:")
    print("answer = quick_ask('What is the capital of France?')")
    print("solution = quick_solve('How to sort a list in Python?')")


def create_migration_example():
    """Show how to migrate from the old protocol to the new one."""
    print("\n" + "=" * 50)
    print("Migration Example: Old vs New Protocol")
    print("=" * 50)
    
    print("\nOLD PROTOCOL (Fixed Types):")
    print("```python")
    print("# Server side - required predefined types")
    print("request = ThinkingRequest(")
    print("    signature=CognitiveSignatures.OBSERVE,")
    print("    input_values={'working_memory': 'current state'}")
    print(")")
    print("```")
    
    print("\nNEW PROTOCOL (Dynamic):")
    print("```python")
    print("# Client side - no server changes needed")
    print("result = client.observe(")
    print("    working_memory='current state',")
    print("    new_messages='new info'")
    print(")")
    print("")
    print("# Or completely custom:")
    print("result = client.think(")
    print("    task='Custom thinking task',")
    print("    inputs={'custom_input': 'Description'},")
    print("    outputs={'custom_output': 'Description'},")
    print("    input_values={'custom_input': 'value'}")
    print(")")
    print("```")
    
    print("\nBENEFITS:")
    print("✓ No server code changes for new thinking patterns")
    print("✓ Clients can create task-specific signatures")
    print("✓ Caching ensures performance")
    print("✓ Backward compatible with existing patterns")


if __name__ == "__main__":
    # Run the test suite
    runner = TestRunner()
    success = runner.run_all_tests()
    
    # Show usage demonstrations
    demo_client_usage()
    create_migration_example()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

