#!/usr/bin/env python3
"""Test script to verify knowledge and CBR systems are working."""

import asyncio
import json
from pathlib import Path
import sys
import os

# Add the src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mind_swarm.subspace.knowledge_handler import KnowledgeHandler
from mind_swarm.subspace.cbr_handler import CBRHandler

async def test_systems():
    """Test both knowledge and CBR systems."""
    subspace_root = Path("/opt/mind-swarm/subspace")
    subspace_root.mkdir(exist_ok=True)
    
    print("=" * 50)
    print("Testing Knowledge and CBR Systems")
    print("=" * 50)
    
    # Test Knowledge System
    print("\n1. Testing Knowledge System...")
    try:
        knowledge = KnowledgeHandler(subspace_root)
        
        if knowledge.enabled:
            print("✓ Knowledge system initialized successfully")
            print(f"  Mode: {knowledge.client_type}")
            
            # Try to add some test knowledge
            success, kid = await knowledge.add_shared_knowledge(
                "Test knowledge: The sky is blue.",
                metadata={"tags": ["test", "color"], "category": "fact"}
            )
            
            if success:
                print(f"✓ Added test knowledge: {kid}")
                
                # Search for it
                results = await knowledge.search_shared_knowledge("blue sky", limit=1)
                if results:
                    print(f"✓ Search working - found {len(results)} result(s)")
                else:
                    print("⚠ Search returned no results")
            else:
                print(f"✗ Failed to add knowledge: {kid}")
        else:
            print("✗ Knowledge system is disabled (ChromaDB not available)")
            
    except Exception as e:
        print(f"✗ Knowledge system error: {e}")
    
    # Test CBR System
    print("\n2. Testing CBR System...")
    try:
        # Try to reuse ChromaDB client from knowledge if available
        if knowledge.enabled:
            cbr = CBRHandler(subspace_root, 
                           chroma_client=knowledge.chroma_client,
                           embedding_fn=knowledge.embedding_fn)
        else:
            cbr = CBRHandler(subspace_root)
        
        if cbr.enabled:
            print("✓ CBR system initialized successfully")
            
            # Create a test case
            test_request = {
                "request_id": "test_001",
                "operation": "store",
                "case": {
                    "problem_context": "Need to process CSV files",
                    "solution": "Use pandas to read and analyze",
                    "outcome": "Successfully processed files",
                    "metadata": {
                        "success_score": 0.9,
                        "tags": ["csv", "pandas"],
                        "shared": False
                    }
                }
            }
            
            # Store a test case
            handler = cbr.get_handler("test_cyber")
            if handler:
                response = await cbr.handle_request("test_cyber", test_request)
                if response and response.get("status") == "success":
                    print(f"✓ Stored test case: {response.get('case_id')}")
                    
                    # Try to retrieve it
                    retrieve_request = {
                        "request_id": "test_002",
                        "operation": "retrieve",
                        "context": "How to handle CSV files",
                        "options": {"limit": 1}
                    }
                    
                    response = await cbr.handle_request("test_cyber", retrieve_request)
                    if response and response.get("status") == "success":
                        cases = response.get("cases", [])
                        if cases:
                            print(f"✓ Retrieved {len(cases)} case(s)")
                        else:
                            print("⚠ No cases retrieved")
                    else:
                        print(f"✗ Retrieval failed: {response.get('error') if response else 'No response'}")
                else:
                    print(f"✗ Failed to store case: {response.get('error') if response else 'No response'}")
            else:
                print("✗ Failed to create CBR handler")
        else:
            print("✗ CBR system is disabled (ChromaDB not available)")
            
    except Exception as e:
        print(f"✗ CBR system error: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Summary:")
    if knowledge.enabled and cbr.enabled:
        print("✓ Both systems are operational")
        print("\nTo complete installation:")
        print("1. Restart the mind-swarm server")
        print("2. The cybers will now have access to knowledge and CBR")
    else:
        print("⚠ Some systems are not available")
        print("\nPlease ensure ChromaDB is installed:")
        print("  pip install chromadb sentence-transformers")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(test_systems())