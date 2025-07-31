#!/usr/bin/env python3
"""Test DSPy integration with Mind-Swarm AI providers."""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import dspy
from mind_swarm.subspace.dspy_config import configure_dspy_for_mind_swarm
from mind_swarm.ai.presets import preset_manager


def test_basic_dspy():
    """Test basic DSPy functionality."""
    print("=== Testing Basic DSPy Integration ===\n")
    
    # Test 1: Configure with local preset
    print("Test 1: Configure DSPy with local AI server")
    try:
        # Get config from preset
        config = preset_manager.get_config("local_explorer")
        print(f"Using config: {config}\n")
        
        # Configure DSPy
        lm = configure_dspy_for_mind_swarm(config.__dict__)
        print("✓ DSPy configured successfully\n")
        
        # Test 2: Basic generation
        print("Test 2: Basic text generation")
        prompt = "What is 2+2? Answer with just the number."
        
        # Test our LM directly
        response = lm.basic_request(prompt)
        print(f"Direct LM response: {response}")
        print("✓ Direct generation works\n")
        
        # Test 3: DSPy signature
        print("Test 3: DSPy signature prediction")
        
        class SimpleQA(dspy.Signature):
            """Answer questions with short responses."""
            question = dspy.InputField()
            answer = dspy.OutputField(desc="short answer")
        
        # Create predictor
        qa = dspy.Predict(SimpleQA)
        
        # Test prediction
        result = qa(question="What is 2+2?")
        print(f"DSPy prediction result: {result.answer}")
        print("✓ DSPy signatures work\n")
        
        # Test 4: More complex signature
        print("Test 4: Complex signature with multiple outputs")
        
        class MathProblem(dspy.Signature):
            """Solve math problems step by step."""
            problem = dspy.InputField(desc="math problem to solve")
            steps = dspy.OutputField(desc="solution steps")
            answer = dspy.OutputField(desc="final numerical answer")
        
        math_solver = dspy.Predict(MathProblem)
        result = math_solver(problem="What is 15 + 27?")
        print(f"Steps: {result.steps}")
        print(f"Answer: {result.answer}")
        print("✓ Complex signatures work\n")
        
    except Exception as e:
        print(f"✗ DSPy test failed: {e}")
        import traceback
        traceback.print_exc()


def test_dspy_chat_format():
    """Test DSPy with chat message format."""
    print("Test 5: Chat message format")
    
    try:
        # Configure DSPy
        config = preset_manager.get_config("local_explorer")
        lm = configure_dspy_for_mind_swarm(config.__dict__)
        
        # Test our __call__ method with messages
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is 2+2? Answer with just the number."}
        ]
        
        response = lm(messages)
        print(f"Chat format response: {response}")
        print("✓ Chat format works\n")
        
    except Exception as e:
        print(f"✗ Chat format test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("Running DSPy integration tests...\n")
    test_basic_dspy()
    test_dspy_chat_format()
    print("=== Tests Complete ===")