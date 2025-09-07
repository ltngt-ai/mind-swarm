#!/usr/bin/env python3
"""
Test script for enhanced Knowledge API with explicit knowledge_id support.

This script tests:
1. Storing knowledge with explicit path-based IDs
2. Collision detection and version suffix strategy
3. Idempotent operations with same content
4. Retrieval by explicit IDs
"""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Assuming we have access to the knowledge handler
import sys
sys.path.append(str(Path(__file__).parent / "src"))

from mind_swarm.subspace.knowledge_handler import KnowledgeHandler, CyberKnowledgeHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_explicit_id_storage():
    """Test storing knowledge with explicit IDs."""
    
    # Create a mock subspace root
    test_root = Path("/tmp/test_knowledge_api")
    test_root.mkdir(exist_ok=True)
    
    # Initialize knowledge handler
    knowledge_handler = KnowledgeHandler(test_root)
    
    if not knowledge_handler.enabled:
        logger.error("ChromaDB not available - tests cannot run")
        return False
    
    # Get a cyber handler
    test_cyber_id = "test_cyber_001"
    cyber_handler = knowledge_handler.get_cyber_handler(test_cyber_id)
    
    if not cyber_handler:
        logger.error("Failed to create cyber handler")
        return False
    
    print("\n=== Testing Enhanced Knowledge API ===\n")
    
    # Test 1: Store with explicit path-based ID
    print("Test 1: Store with explicit path-based ID")
    request1 = {
        "request_id": "test_001",
        "operation": "store",
        "content": "This is documentation about the system architecture.",
        "knowledge_id": "docs/architecture/overview",
        "metadata": {
            "tags": ["architecture", "documentation"],
            "personal": False
        }
    }
    
    response1 = await cyber_handler.store(request1)
    assert response1["status"] == "success", f"Failed to store: {response1}"
    assert response1["knowledge_id"] == "docs/architecture/overview", f"ID mismatch: {response1['knowledge_id']}"
    print(f"✓ Stored with ID: {response1['knowledge_id']}")
    
    # Test 2: Retrieve by explicit ID
    print("\nTest 2: Retrieve by explicit ID")
    request2 = {
        "request_id": "test_002",
        "operation": "get",
        "knowledge_id": "docs/architecture/overview"
    }
    
    response2 = await cyber_handler.get(request2)
    assert response2["status"] == "success", f"Failed to get: {response2}"
    assert response2["result"] is not None, "Knowledge not found"
    assert response2["result"]["content"] == request1["content"], "Content mismatch"
    print(f"✓ Retrieved knowledge: {response2['result']['id']}")
    
    # Test 3: Idempotent operation - same content, same ID
    print("\nTest 3: Idempotent operation (same content)")
    request3 = {
        "request_id": "test_003",
        "operation": "store",
        "content": "This is documentation about the system architecture.",  # Same content
        "knowledge_id": "docs/architecture/overview",  # Same ID
        "metadata": {
            "tags": ["architecture", "documentation"],
            "personal": False
        }
    }
    
    response3 = await cyber_handler.store(request3)
    assert response3["status"] == "success", f"Failed idempotent store: {response3}"
    assert response3.get("idempotent") == True, "Should be idempotent"
    assert response3["knowledge_id"] == "docs/architecture/overview", f"ID changed: {response3['knowledge_id']}"
    print(f"✓ Idempotent operation succeeded, ID unchanged: {response3['knowledge_id']}")
    
    # Test 4: Collision handling - different content, same ID
    print("\nTest 4: Collision handling (different content)")
    request4 = {
        "request_id": "test_004",
        "operation": "store",
        "content": "This is UPDATED documentation about the system architecture.",  # Different content
        "knowledge_id": "docs/architecture/overview",  # Same ID
        "metadata": {
            "tags": ["architecture", "documentation", "updated"],
            "personal": False
        }
    }
    
    response4 = await cyber_handler.store(request4)
    assert response4["status"] == "success", f"Failed collision handling: {response4}"
    assert response4["knowledge_id"] != "docs/architecture/overview", f"ID should be versioned: {response4['knowledge_id']}"
    assert response4["knowledge_id"].startswith("docs/architecture/overview_v"), f"Wrong version format: {response4['knowledge_id']}"
    print(f"✓ Collision handled, versioned ID: {response4['knowledge_id']}")
    
    # Test 5: Store with hierarchical path ID
    print("\nTest 5: Store with hierarchical path ID")
    request5 = {
        "request_id": "test_005",
        "operation": "store",
        "content": "Architecture Decision Record #001: Use microservices",
        "knowledge_id": "architecture/decisions/ADR-001",
        "metadata": {
            "tags": ["adr", "architecture", "decisions"],
            "personal": False
        }
    }
    
    response5 = await cyber_handler.store(request5)
    assert response5["status"] == "success", f"Failed to store ADR: {response5}"
    assert response5["knowledge_id"] == "architecture/decisions/ADR-001", f"ID mismatch: {response5['knowledge_id']}"
    print(f"✓ Stored ADR with hierarchical ID: {response5['knowledge_id']}")
    
    # Test 6: Search for stored knowledge
    print("\nTest 6: Search for stored knowledge")
    request6 = {
        "request_id": "test_006",
        "operation": "search",
        "query": "architecture documentation",
        "options": {
            "limit": 5,
            "scope": ["shared"]
        }
    }
    
    response6 = await cyber_handler.search(request6)
    assert response6["status"] == "success", f"Search failed: {response6}"
    assert len(response6["results"]) > 0, "No results found"
    
    print(f"✓ Found {len(response6['results'])} results:")
    for result in response6["results"]:
        print(f"  - ID: {result['id']}, Score: {result['score']:.2f}")
    
    # Test 7: Update existing knowledge
    print("\nTest 7: Update existing knowledge")
    request7 = {
        "request_id": "test_007",
        "operation": "update",
        "knowledge_id": "docs/architecture/overview",
        "content": "REVISED: This is documentation about the system architecture with updates.",
        "metadata": {
            "updated_at": datetime.now().isoformat(),
            "version": "1.1"
        }
    }
    
    response7 = await cyber_handler.update(request7)
    assert response7["status"] == "success", f"Update failed: {response7}"
    print(f"✓ Updated knowledge: docs/architecture/overview")
    
    # Verify update
    get_request = {
        "request_id": "test_008",
        "operation": "get",
        "knowledge_id": "docs/architecture/overview"
    }
    
    get_response = await cyber_handler.get(get_request)
    assert get_response["result"]["content"].startswith("REVISED:"), "Update not applied"
    print(f"✓ Verified update was applied")
    
    print("\n=== All tests passed! ===\n")
    return True


async def main():
    """Run all tests."""
    try:
        success = await test_explicit_id_storage()
        if success:
            print("✅ Enhanced Knowledge API tests completed successfully!")
            return 0
        else:
            print("❌ Tests failed or could not run")
            return 1
    except Exception as e:
        logger.error(f"Test error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)