"""Test suite for CBR path-based IDs and retrieval functionality.

This module tests:
1. Store with request.case_id and metadata.case_path
2. Retrieve by ID and export round-trip using path
3. Metadata sanitization
4. update_score functionality
5. Backward compatibility with auto-generated IDs
"""

import pytest
import pytest_asyncio
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

from src.mind_swarm.subspace.cbr_handler import CBRHandler, CyberCBRHandler
from src.mind_swarm.utils.id_policy import normalize_cbr_case_id


# Mock ChromaDB for testing
class MockCollection:
    """Mock ChromaDB collection for testing."""
    
    def __init__(self, name: str):
        self.name = name
        self.storage = {}  # id -> {"document": str, "metadata": dict}
        
    def add(self, documents: List[str], metadatas: List[Dict], ids: List[str]):
        """Add documents to the collection."""
        for doc, meta, id_ in zip(documents, metadatas, ids):
            if id_ in self.storage:
                raise ValueError(f"ID already exists: {id_}")
            self.storage[id_] = {
                "document": doc,
                "metadata": meta,
                "id": id_
            }
    
    def get(self, ids: List[str] = None, where: Dict = None, limit: int = None):
        """Get documents from the collection."""
        if ids:
            results = {"documents": [], "metadatas": [], "ids": []}
            for id_ in ids:
                if id_ in self.storage:
                    item = self.storage[id_]
                    results["documents"].append(item["document"])
                    results["metadatas"].append(item["metadata"])
                    results["ids"].append(id_)
            return results if results["documents"] else {}
        
        # Return all items if no IDs specified
        results = {"documents": [], "metadatas": [], "ids": []}
        for id_, item in self.storage.items():
            results["documents"].append(item["document"])
            results["metadatas"].append(item["metadata"])
            results["ids"].append(id_)
        return results if results["documents"] else {}
    
    def update(self, ids: List[str], metadatas: List[Dict] = None, documents: List[str] = None):
        """Update documents in the collection."""
        for i, id_ in enumerate(ids):
            if id_ in self.storage:
                if metadatas and i < len(metadatas):
                    self.storage[id_]["metadata"] = metadatas[i]
                if documents and i < len(documents):
                    self.storage[id_]["document"] = documents[i]
    
    def delete(self, ids: List[str]):
        """Delete documents from the collection."""
        for id_ in ids:
            if id_ in self.storage:
                del self.storage[id_]
    
    def query(self, query_texts: List[str], n_results: int = 5):
        """Mock query implementation."""
        # Return mock results for testing
        results = {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
            "ids": [[]]
        }
        
        # Add some mock results if there are items in storage
        for id_, item in list(self.storage.items())[:n_results]:
            results["documents"][0].append(item["document"])
            results["metadatas"][0].append(item["metadata"])
            results["distances"][0].append(0.5)  # Mock distance
            results["ids"][0].append(id_)
        
        return results


class MockChromaClient:
    """Mock ChromaDB client for testing."""
    
    def __init__(self):
        self.collections = {}
    
    def get_collection(self, name: str, **kwargs):
        """Get a collection by name."""
        if name not in self.collections:
            raise ValueError(f"Collection {name} does not exist")
        return self.collections[name]
    
    def create_collection(self, name: str, **kwargs):
        """Create a new collection."""
        if name in self.collections:
            raise ValueError(f"Collection {name} already exists")
        self.collections[name] = MockCollection(name)
        return self.collections[name]
    
    def get_or_create_collection(self, name: str, **kwargs):
        """Get or create a collection."""
        if name not in self.collections:
            self.collections[name] = MockCollection(name)
        return self.collections[name]


@pytest_asyncio.fixture
async def cbr_handler(tmp_path):
    """Create a CBR handler with mock ChromaDB."""
    with patch('src.mind_swarm.subspace.cbr_handler.CHROMADB_AVAILABLE', True):
        handler = CBRHandler(subspace_root=tmp_path, chroma_client=MockChromaClient())
        handler.enabled = True
        return handler


@pytest_asyncio.fixture
async def cyber_handler(cbr_handler):
    """Create a cyber-specific CBR handler."""
    return cbr_handler.get_handler("test_cyber")


class TestPathBasedIDs:
    """Test path-based ID functionality."""
    
    @pytest.mark.asyncio
    async def test_store_with_explicit_case_id(self, cyber_handler):
        """Test storing a case with explicit case_id in request."""
        request = {
            "request_id": "req_1",
            "case_id": "custom_case_123",
            "case": {
                "problem_context": "How to optimize performance?",
                "solution": "Use caching and indexing",
                "outcome": "50% improvement",
                "metadata": {
                    "tags": ["performance", "optimization"],
                    "success_score": 0.9
                }
            }
        }
        
        response = await cyber_handler.store(request)
        
        assert response["status"] == "success"
        assert response["case_id"] == "custom_case_123"
        
        # Verify case can be retrieved
        get_request = {"request_id": "req_2", "case_id": "custom_case_123"}
        get_response = await cyber_handler.get(get_request)
        
        assert get_response["status"] == "success"
        assert get_response["case"]["case_id"] == "custom_case_123"
        assert "performance,optimization" in get_response["case"]["metadata"]["tags"]
    
    @pytest.mark.asyncio
    async def test_store_with_case_path_metadata(self, cyber_handler):
        """Test storing a case with case_path in metadata."""
        request = {
            "request_id": "req_1",
            "case": {
                "problem_context": "Database query slow",
                "solution": "Add index on user_id column",
                "outcome": "Query time reduced from 5s to 0.1s",
                "metadata": {
                    "case_path": "Database/Performance/Slow Query Fix",
                    "success_score": 0.95
                }
            }
        }
        
        response = await cyber_handler.store(request)
        
        assert response["status"] == "success"
        # Should normalize the path to cases/database/performance/slow-query-fix
        expected_id = normalize_cbr_case_id("Database/Performance/Slow Query Fix")
        assert response["case_id"] == expected_id
        assert response["case_id"] == "cases/database/performance/slow-query-fix"
        
        # Verify metadata preservation
        get_request = {"request_id": "req_2", "case_id": response["case_id"]}
        get_response = await cyber_handler.get(get_request)
        
        assert get_response["status"] == "success"
        assert get_response["case"]["metadata"]["case_path"] == "Database/Performance/Slow Query Fix"
    
    @pytest.mark.asyncio
    async def test_store_with_auto_generated_id(self, cyber_handler):
        """Test backward compatibility with auto-generated IDs."""
        request = {
            "request_id": "req_1",
            "case": {
                "problem_context": "Memory leak in application",
                "solution": "Fix circular references",
                "outcome": "Memory usage stable",
                "metadata": {
                    "success_score": 0.8
                }
            }
        }
        
        response = await cyber_handler.store(request)
        
        assert response["status"] == "success"
        # Should generate an ID like cbr_test_cyber_hash_timestamp
        assert response["case_id"].startswith("cbr_test_cyber_")
        assert len(response["case_id"].split("_")) >= 4
    
    @pytest.mark.asyncio
    async def test_duplicate_id_prevention(self, cyber_handler):
        """Test that duplicate IDs are prevented."""
        case_data = {
            "problem_context": "Test problem",
            "solution": "Test solution",
            "outcome": "Success",
            "metadata": {"case_path": "Test/Case/One"}
        }
        
        # Store first case
        request1 = {"request_id": "req_1", "case": case_data}
        response1 = await cyber_handler.store(request1)
        assert response1["status"] == "success"
        
        # Try to store second case with same path
        request2 = {"request_id": "req_2", "case": case_data}
        response2 = await cyber_handler.store(request2)
        
        assert response2["status"] == "error"
        assert "already exists" in response2["error"]
    
    @pytest.mark.asyncio
    async def test_explicit_id_takes_precedence(self, cyber_handler):
        """Test that explicit case_id takes precedence over case_path."""
        request = {
            "request_id": "req_1",
            "case_id": "explicit_id_123",
            "case": {
                "problem_context": "Priority test",
                "solution": "Test solution",
                "outcome": "Success",
                "metadata": {
                    "case_path": "This/Should/Be/Ignored"
                }
            }
        }
        
        response = await cyber_handler.store(request)
        
        assert response["status"] == "success"
        assert response["case_id"] == "explicit_id_123"
        
        # Verify case_path is still preserved in metadata
        get_response = await cyber_handler.get({"case_id": "explicit_id_123"})
        assert get_response["case"]["metadata"]["case_path"] == "This/Should/Be/Ignored"


class TestMetadataSanitization:
    """Test metadata sanitization for ChromaDB compatibility."""
    
    @pytest.mark.asyncio
    async def test_sanitize_list_metadata(self, cyber_handler):
        """Test that lists in metadata are properly sanitized."""
        request = {
            "request_id": "req_1",
            "case": {
                "problem_context": "Test with list metadata",
                "solution": "Solution",
                "outcome": "Success",
                "metadata": {
                    "tags": ["tag1", "tag2", "tag3"],
                    "cbr_cases_used": ["case_a", "case_b"],
                    "scores": [0.8, 0.9, 0.7]
                }
            }
        }
        
        response = await cyber_handler.store(request)
        assert response["status"] == "success"
        
        # Retrieve and verify
        get_response = await cyber_handler.get({"case_id": response["case_id"]})
        metadata = get_response["case"]["metadata"]
        
        # Lists should be converted to comma-separated strings
        assert metadata["tags"] == "tag1,tag2,tag3"
        assert metadata["cbr_cases_used"] == "case_a,case_b"
        assert metadata["scores"] == "0.8,0.9,0.7"
    
    @pytest.mark.asyncio
    async def test_sanitize_dict_metadata(self, cyber_handler):
        """Test that dicts in metadata are JSON serialized."""
        request = {
            "request_id": "req_1",
            "case": {
                "problem_context": "Test with dict metadata",
                "solution": "Solution",
                "outcome": "Success",
                "metadata": {
                    "complex_data": {"key1": "value1", "key2": 123},
                    "nested": {"level1": {"level2": "value"}}
                }
            }
        }
        
        response = await cyber_handler.store(request)
        assert response["status"] == "success"
        
        # Retrieve and verify
        get_response = await cyber_handler.get({"case_id": response["case_id"]})
        metadata = get_response["case"]["metadata"]
        
        # Dicts should be JSON serialized
        assert isinstance(metadata["complex_data"], str)
        assert json.loads(metadata["complex_data"]) == {"key1": "value1", "key2": 123}
        assert isinstance(metadata["nested"], str)
        assert json.loads(metadata["nested"]) == {"level1": {"level2": "value"}}
    
    @pytest.mark.asyncio
    async def test_sanitize_primitive_types(self, cyber_handler):
        """Test that primitive types are preserved."""
        request = {
            "request_id": "req_1",
            "case": {
                "problem_context": "Test primitives",
                "solution": "Solution",
                "outcome": "Success",
                "metadata": {
                    "string_val": "test string",
                    "int_val": 42,
                    "float_val": 3.14,
                    "bool_val": True,
                    "none_val": None
                }
            }
        }
        
        response = await cyber_handler.store(request)
        assert response["status"] == "success"
        
        # Retrieve and verify
        get_response = await cyber_handler.get({"case_id": response["case_id"]})
        metadata = get_response["case"]["metadata"]
        
        assert metadata["string_val"] == "test string"
        assert metadata["int_val"] == 42
        assert metadata["float_val"] == 3.14
        assert metadata["bool_val"] is True
        # None values might be filtered out by ChromaDB


class TestUpdateScore:
    """Test update_score functionality."""
    
    @pytest.mark.asyncio
    async def test_update_success_score(self, cyber_handler):
        """Test updating the success score of a case."""
        # Store a case
        store_request = {
            "request_id": "req_1",
            "case_id": "score_test_1",
            "case": {
                "problem_context": "Score test",
                "solution": "Solution",
                "outcome": "Initial outcome",
                "metadata": {"success_score": 0.5}
            }
        }
        
        await cyber_handler.store(store_request)
        
        # Update the score
        update_request = {
            "request_id": "req_2",
            "case_id": "score_test_1",
            "updates": {"success_score": 0.9}
        }
        
        response = await cyber_handler.update_score(update_request)
        assert response["status"] == "success"
        
        # Verify the update
        get_response = await cyber_handler.get({"case_id": "score_test_1"})
        assert get_response["case"]["metadata"]["success_score"] == 0.9
    
    @pytest.mark.asyncio
    async def test_increment_usage_count(self, cyber_handler):
        """Test incrementing usage count and boosting score."""
        # Store a case
        store_request = {
            "request_id": "req_1",
            "case_id": "usage_test_1",
            "case": {
                "problem_context": "Usage test",
                "solution": "Solution",
                "outcome": "Outcome",
                "metadata": {"success_score": 0.7, "usage_count": 2}
            }
        }
        
        await cyber_handler.store(store_request)
        
        # Increment usage
        update_request = {
            "request_id": "req_2",
            "case_id": "usage_test_1",
            "updates": {"increment_usage": True}
        }
        
        response = await cyber_handler.update_score(update_request)
        assert response["status"] == "success"
        
        # Verify the update
        get_response = await cyber_handler.get({"case_id": "usage_test_1"})
        metadata = get_response["case"]["metadata"]
        
        assert metadata["usage_count"] == 3
        assert metadata["success_score"] == 0.75  # Boosted by 0.05
        assert "last_used" in metadata
    
    @pytest.mark.asyncio
    async def test_update_nonexistent_case(self, cyber_handler):
        """Test updating a case that doesn't exist."""
        update_request = {
            "request_id": "req_1",
            "case_id": "nonexistent_case",
            "updates": {"success_score": 0.9}
        }
        
        response = await cyber_handler.update_score(update_request)
        
        assert response["status"] == "error"
        assert "not found" in response["error"].lower()


class TestRetrievalAndExport:
    """Test retrieval and export functionality with path-based IDs."""
    
    @pytest.mark.asyncio
    async def test_retrieve_similar_cases(self, cyber_handler):
        """Test retrieving similar cases based on context."""
        # Store several cases
        cases = [
            {
                "case_id": "cases/db/slow-query",
                "problem_context": "Database query running slow",
                "solution": "Add index",
                "metadata": {"success_score": 0.9}
            },
            {
                "case_id": "cases/db/connection-pool",
                "problem_context": "Database connection timeouts",
                "solution": "Increase pool size",
                "metadata": {"success_score": 0.8}
            },
            {
                "case_id": "cases/api/rate-limit",
                "problem_context": "API rate limiting issues",
                "solution": "Implement caching",
                "metadata": {"success_score": 0.85}
            }
        ]
        
        for case_data in cases:
            request = {
                "request_id": f"store_{case_data['case_id']}",
                "case_id": case_data["case_id"],
                "case": {
                    "problem_context": case_data["problem_context"],
                    "solution": case_data["solution"],
                    "outcome": "Success",
                    "metadata": case_data["metadata"]
                }
            }
            await cyber_handler.store(request)
        
        # Retrieve similar cases
        retrieve_request = {
            "request_id": "retrieve_1",
            "context": "Database performance problem",
            "options": {"limit": 3, "min_score": 0.0}
        }
        
        response = await cyber_handler.retrieve(retrieve_request)
        
        assert response["status"] == "success"
        assert "cases" in response
        assert len(response["cases"]) > 0
        
        # Verify cases have similarity scores
        for case in response["cases"]:
            assert "similarity" in case
            assert "weighted_score" in case
            assert "case_id" in case
    
    @pytest.mark.asyncio
    async def test_get_case_by_path_id(self, cyber_handler):
        """Test retrieving a specific case by its path-based ID."""
        # Store a case with path
        store_request = {
            "request_id": "req_1",
            "case": {
                "problem_context": "Memory optimization needed",
                "solution": "Use object pooling",
                "outcome": "30% reduction in allocations",
                "metadata": {
                    "case_path": "Performance/Memory/Object Pooling"
                }
            }
        }
        
        store_response = await cyber_handler.store(store_request)
        case_id = store_response["case_id"]
        
        # Get the case by its normalized ID
        get_request = {"request_id": "req_2", "case_id": case_id}
        get_response = await cyber_handler.get(get_request)
        
        assert get_response["status"] == "success"
        assert get_response["case"]["case_id"] == case_id
        assert get_response["case"]["metadata"]["case_path"] == "Performance/Memory/Object Pooling"
    
    @pytest.mark.asyncio
    async def test_round_trip_with_path_ids(self, cyber_handler):
        """Test that cases with path IDs can be exported and re-imported."""
        # Store cases with path IDs
        original_cases = [
            {
                "case_id": "cases/testing/unit-test-strategy",
                "problem_context": "Need better test coverage",
                "solution": "Implement test pyramid",
                "metadata": {
                    "case_path": "Testing/Unit Test Strategy",
                    "success_score": 0.85
                }
            },
            {
                "case_id": "cases/deployment/rollback-procedure",
                "problem_context": "Deployment failure recovery",
                "solution": "Blue-green deployment",
                "metadata": {
                    "case_path": "Deployment/Rollback Procedure",
                    "success_score": 0.9
                }
            }
        ]
        
        # Store the cases
        for case_data in original_cases:
            request = {
                "request_id": f"store_{case_data['case_id']}",
                "case_id": case_data["case_id"],
                "case": {
                    "problem_context": case_data["problem_context"],
                    "solution": case_data["solution"],
                    "outcome": "Success",
                    "metadata": case_data["metadata"]
                }
            }
            await cyber_handler.store(request)
        
        # Verify cases can be retrieved by their path-based IDs
        for case_data in original_cases:
            get_response = await cyber_handler.get({"case_id": case_data["case_id"]})
            assert get_response["status"] == "success"
            assert get_response["case"]["metadata"]["case_path"] == case_data["metadata"]["case_path"]
            assert get_response["case"]["metadata"]["success_score"] == case_data["metadata"]["success_score"]


class TestBackwardCompatibility:
    """Test backward compatibility with existing auto-generated IDs."""
    
    @pytest.mark.asyncio
    async def test_mixed_id_types(self, cyber_handler):
        """Test that path-based and auto-generated IDs can coexist."""
        # Store case with auto-generated ID
        auto_request = {
            "request_id": "req_1",
            "case": {
                "problem_context": "Auto ID case",
                "solution": "Solution 1",
                "outcome": "Success"
            }
        }
        auto_response = await cyber_handler.store(auto_request)
        auto_id = auto_response["case_id"]
        
        # Store case with path-based ID
        path_request = {
            "request_id": "req_2",
            "case": {
                "problem_context": "Path ID case",
                "solution": "Solution 2",
                "outcome": "Success",
                "metadata": {"case_path": "Category/Subcategory/Case"}
            }
        }
        path_response = await cyber_handler.store(path_request)
        path_id = path_response["case_id"]
        
        # Store case with explicit ID
        explicit_request = {
            "request_id": "req_3",
            "case_id": "explicit_custom_id",
            "case": {
                "problem_context": "Explicit ID case",
                "solution": "Solution 3",
                "outcome": "Success"
            }
        }
        explicit_response = await cyber_handler.store(explicit_request)
        explicit_id = explicit_response["case_id"]
        
        # Verify all three can be retrieved
        for case_id in [auto_id, path_id, explicit_id]:
            get_response = await cyber_handler.get({"case_id": case_id})
            assert get_response["status"] == "success"
            assert get_response["case"]["case_id"] == case_id
    
    @pytest.mark.asyncio
    async def test_legacy_id_format_preserved(self, cyber_handler):
        """Test that legacy cbr_cyber_hash_timestamp IDs still work."""
        # Simulate a legacy ID
        legacy_id = f"cbr_test_cyber_abc123_{int(time.time())}"
        
        request = {
            "request_id": "req_1",
            "case_id": legacy_id,
            "case": {
                "problem_context": "Legacy case",
                "solution": "Legacy solution",
                "outcome": "Success"
            }
        }
        
        response = await cyber_handler.store(request)
        
        assert response["status"] == "success"
        assert response["case_id"] == legacy_id
        
        # Verify retrieval
        get_response = await cyber_handler.get({"case_id": legacy_id})
        assert get_response["status"] == "success"
        assert get_response["case"]["case_id"] == legacy_id


class TestSharedCases:
    """Test shared case functionality with path-based IDs."""
    
    @pytest.mark.asyncio
    async def test_share_case_with_path_id(self, cbr_handler):
        """Test sharing a case with path-based ID between cybers."""
        cyber1_handler = cbr_handler.get_handler("cyber1")
        cyber2_handler = cbr_handler.get_handler("cyber2")
        
        # Cyber1 stores a case with path ID
        store_request = {
            "request_id": "req_1",
            "case": {
                "problem_context": "Shared knowledge case",
                "solution": "Collaborative solution",
                "outcome": "Great success",
                "metadata": {
                    "case_path": "Shared/Knowledge/Collaboration",
                    "success_score": 0.95
                }
            }
        }
        
        store_response = await cyber1_handler.store(store_request)
        case_id = store_response["case_id"]
        
        # Cyber1 shares the case
        share_request = {"request_id": "req_2", "case_id": case_id}
        share_response = await cyber1_handler.share(share_request)
        
        assert share_response["status"] == "success"
        
        # Cyber2 should be able to retrieve the shared case
        retrieve_request = {
            "request_id": "req_3",
            "context": "Collaborative solution needed",
            "options": {"limit": 5}
        }
        
        retrieve_response = await cyber2_handler.retrieve(retrieve_request)
        
        assert retrieve_response["status"] == "success"
        # The shared case should appear in results
        shared_cases = [c for c in retrieve_response["cases"] if c["source"] == "shared"]
        assert len(shared_cases) > 0


class TestErrorHandling:
    """Test error handling for edge cases."""
    
    @pytest.mark.asyncio
    async def test_empty_case_path(self, cyber_handler):
        """Test handling of empty case_path."""
        request = {
            "request_id": "req_1",
            "case": {
                "problem_context": "Test",
                "solution": "Solution",
                "outcome": "Success",
                "metadata": {"case_path": ""}
            }
        }
        
        response = await cyber_handler.store(request)
        
        # Should fall back to auto-generated ID
        assert response["status"] == "success"
        assert response["case_id"].startswith("cbr_test_cyber_")
    
    @pytest.mark.asyncio
    async def test_invalid_characters_in_path(self, cyber_handler):
        """Test normalization of paths with special characters."""
        request = {
            "request_id": "req_1",
            "case": {
                "problem_context": "Special chars test",
                "solution": "Solution",
                "outcome": "Success",
                "metadata": {
                    "case_path": "Path/With Spaces/And-Dashes/and_underscores"
                }
            }
        }
        
        response = await cyber_handler.store(request)
        
        assert response["status"] == "success"
        # Should normalize to lowercase with hyphens
        assert response["case_id"] == "cases/path/with-spaces/and-dashes/and_underscores"
    
    @pytest.mark.asyncio
    async def test_very_long_path(self, cyber_handler):
        """Test handling of very long paths."""
        long_path = "/".join(["Very", "Long", "Path"] * 20)
        
        request = {
            "request_id": "req_1",
            "case": {
                "problem_context": "Long path test",
                "solution": "Solution",
                "outcome": "Success",
                "metadata": {"case_path": long_path}
            }
        }
        
        response = await cyber_handler.store(request)
        
        # Should succeed with normalized long path
        assert response["status"] == "success"
        assert response["case_id"].startswith("cases/")
        assert len(response["case_id"]) > 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])