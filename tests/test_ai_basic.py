#!/usr/bin/env python3
"""Test basic AI provider functionality."""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mind_swarm.ai.config import AIExecutionConfig
from mind_swarm.ai.providers.factory import create_ai_service
from mind_swarm.ai.presets import preset_manager


async def test_local_server():
    """Test local OpenAI-compatible server."""
    print("Test 1: Local OpenAI-compatible server")
    try:
        # Create config for local server
        config = AIExecutionConfig(
            model_id="gpt-3.5-turbo",  # Model name expected by local server
            provider="local",
            api_key="dummy",
            temperature=0.7,
            max_tokens=100,
            provider_settings={
                "host": "http://localhost:1234"  # Common local server port
            }
        )
        
        # Create service
        service = create_ai_service(config)
        
        # Test simple generation
        prompt = "What is 2+2? Answer with just the number."
        print(f"Sending to local server: {prompt}")
        
        response = await service.generate(prompt)
        print(f"Response: {response}")
        print("✓ Local server test passed\n")
        
    except Exception as e:
        print(f"✗ Local server test failed: {e}")
        print("Make sure local OpenAI-compatible server is running on port 1234")
        print("You can start one with: lmstudio, ollama, or localai\n")


async def test_ollama():
    """Test Ollama server."""
    print("Test 2: Ollama server")
    try:
        # Create config for Ollama
        config = AIExecutionConfig(
            model_id="llama3.2:3b",  # Common Ollama model
            provider="ollama",
            api_key="not-needed",
            temperature=0.7,
            max_tokens=100,
            provider_settings={
                "host": "http://localhost:11434"  # Default Ollama port
            }
        )
        
        # Create service
        service = create_ai_service(config)
        
        # Test simple generation
        prompt = "What is 2+2? Answer with just the number."
        print(f"Sending to Ollama: {prompt}")
        
        response = await service.generate(prompt)
        print(f"Response: {response}")
        print("✓ Ollama test passed\n")
        
    except Exception as e:
        print(f"✗ Ollama test failed: {e}")
        print("Make sure Ollama is running: ollama serve")
        print("And you have a model: ollama pull llama3.2:3b\n")


async def test_openrouter():
    """Test OpenRouter API."""
    print("Test 3: OpenRouter API")
    
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Skipping - OPENROUTER_API_KEY not set")
        print("Set it with: export OPENROUTER_API_KEY=your-key\n")
        return
    
    try:
        # Create config for OpenRouter
        config = AIExecutionConfig(
            model_id="meta-llama/llama-3.2-3b-instruct:free",
            provider="openrouter",
            api_key=api_key,
            temperature=0.7,
            max_tokens=100
        )
        
        # Create service
        service = create_ai_service(config)
        
        # Test simple generation
        prompt = "What is 2+2? Answer with just the number."
        print(f"Sending to OpenRouter: {prompt}")
        
        response = await service.generate(prompt)
        print(f"Response: {response}")
        print("✓ OpenRouter test passed\n")
        
    except Exception as e:
        print(f"✗ OpenRouter test failed: {e}\n")


async def test_presets():
    """Test using presets."""
    print("Test 4: Using presets")
    
    # List available presets
    print(f"Available presets: {preset_manager.list_presets()}")
    
    try:
        # Get a preset config
        preset_name = "local_explorer"
        config = preset_manager.get_config(preset_name)
        print(f"\nUsing preset '{preset_name}': {config}")
        
        # Create service from preset
        service = create_ai_service(config)
        
        # Test
        prompt = "What is 2+2? Answer with just the number."
        print(f"Sending with preset: {prompt}")
        
        response = await service.generate(prompt)
        print(f"Response: {response}")
        print("✓ Preset test passed\n")
        
    except Exception as e:
        print(f"✗ Preset test failed: {e}\n")


async def test_streaming():
    """Test streaming generation."""
    print("Test 5: Streaming generation")
    
    try:
        # Use local preset
        config = preset_manager.get_config("local_explorer")
        service = create_ai_service(config)
        
        prompt = "Count from 1 to 5, one number per line."
        print(f"Streaming prompt: {prompt}")
        print("Response: ", end="", flush=True)
        
        full_response = ""
        async for chunk in service.stream_generate(prompt):
            if chunk.delta_content:
                print(chunk.delta_content, end="", flush=True)
                full_response += chunk.delta_content
        
        print()  # New line after streaming
        print("✓ Streaming test passed\n")
        
    except Exception as e:
        print(f"\n✗ Streaming test failed: {e}\n")


async def main():
    """Run all tests."""
    print("=== Testing Basic AI Provider Functionality ===\n")
    
    # Run tests in order
    await test_local_server()
    await test_ollama()
    await test_openrouter()
    await test_presets()
    await test_streaming()
    
    print("=== Tests Complete ===")


if __name__ == "__main__":
    asyncio.run(main())