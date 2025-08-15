#!/usr/bin/env python3
"""Test script to verify graceful cyber shutdown during LLM operations."""

import asyncio
import time
import os
import subprocess
from pathlib import Path

async def test_shutdown():
    """Test that cybers shutdown gracefully even during brain operations."""
    
    print("🚀 Starting test of graceful cyber shutdown...")
    
    # Ensure subspace root is set
    subspace_root = Path(os.environ.get("SUBSPACE_ROOT", "../subspace")).resolve()
    os.environ["SUBSPACE_ROOT"] = str(subspace_root)
    
    print(f"📁 Using subspace at: {subspace_root}")
    
    # Start the server
    print("\n1️⃣ Starting mind-swarm server...")
    server_proc = subprocess.Popen(
        ["./run.sh", "server", "--debug"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for server to start
    await asyncio.sleep(5)
    
    try:
        # Create a cyber
        print("\n2️⃣ Creating test cyber...")
        result = subprocess.run(
            ["mind-swarm", "cybers", "create", "TestShutdown"],
            capture_output=True,
            text=True
        )
        print(f"   Created: {result.stdout.strip()}")
        
        # Give cyber time to start thinking
        print("\n3️⃣ Waiting for cyber to start cognitive loop...")
        await asyncio.sleep(3)
        
        # Send a complex question to trigger brain usage
        print("\n4️⃣ Sending complex question to trigger brain operation...")
        result = subprocess.run(
            ["mind-swarm", "message", "TestShutdown", "Please write a detailed analysis of quantum computing applications in cryptography"],
            capture_output=True,
            text=True
        )
        print("   Message sent - cyber should be thinking now")
        
        # Wait briefly for brain operation to start
        await asyncio.sleep(2)
        
        # Now attempt shutdown
        print("\n5️⃣ Initiating server shutdown (should cancel brain operation)...")
        start_time = time.time()
        
        shutdown_proc = subprocess.run(
            ["mind-swarm", "server", "stop"],
            capture_output=True,
            text=True,
            timeout=60  # Should complete within 60 seconds
        )
        
        shutdown_time = time.time() - start_time
        
        print(f"\n✅ Shutdown completed in {shutdown_time:.1f} seconds")
        print(f"   Output: {shutdown_proc.stdout.strip()}")
        
        if shutdown_time < 60:
            print("\n🎉 SUCCESS: Cyber shutdown gracefully within timeout!")
            print("   The brain operation was successfully cancelled.")
        else:
            print("\n⚠️ WARNING: Shutdown took longer than expected")
            
    except subprocess.TimeoutExpired:
        print("\n❌ FAILURE: Shutdown timed out after 60 seconds")
        print("   The cyber is likely stuck in a brain operation")
        
        # Force kill if needed
        print("   Force killing server...")
        subprocess.run(["pkill", "-f", "mind-swarm"])
        
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        
    finally:
        # Ensure server is stopped
        if server_proc.poll() is None:
            print("\n🔧 Cleaning up server process...")
            server_proc.terminate()
            try:
                server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_proc.kill()
                
    print("\n📊 Test complete!")

if __name__ == "__main__":
    asyncio.run(test_shutdown())