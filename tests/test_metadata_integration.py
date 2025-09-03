"""
Integration tests for metadata normalization with knowledge handler.
"""

import pytest
import tempfile
from pathlib import Path
import yaml
import asyncio

from src.mind_swarm.utils.metadata_helpers import (
    normalize_metadata,
    compute_content_hash,
    content_has_changed
)


def test_metadata_normalization_example():
    """Test a real-world example of metadata normalization."""
    
    # Example metadata from a knowledge entry
    raw_metadata = {
        "title": "Understanding OODA Loop",
        "tags": ["ooda", "decision-making", "strategy"],
        "category": "cognitive_frameworks",
        "cyber_id": "cyber-123",
        "personal": True,
        "priority": 1,
        "dependencies": ["observation", "orientation", "decision", "action"],
        "metadata": {
            "author": "Boyd",
            "year": 1976
        },
        "empty_field": None,
        "score": "4.5"
    }
    
    # Normalize the metadata
    normalized = normalize_metadata(raw_metadata)
    
    # Check that lists are comma-separated
    assert normalized["tags"] == "ooda,decision-making,strategy"
    assert normalized["dependencies"] == "observation,orientation,decision,action"
    
    # Check that nested dict is JSON
    import json
    meta_dict = json.loads(normalized["metadata"])
    assert meta_dict["author"] == "Boyd"
    assert meta_dict["year"] == 1976
    
    # Check None becomes empty string
    assert normalized["empty_field"] == ""
    
    # Check other fields pass through
    assert normalized["title"] == "Understanding OODA Loop"
    assert normalized["category"] == "cognitive_frameworks"
    assert normalized["personal"] is True
    assert normalized["priority"] == 1
    assert normalized["score"] == "4.5"


def test_content_hash_stability():
    """Test that content hashing is stable and deterministic."""
    
    content = """
    # OODA Loop Framework
    
    The OODA loop is a decision-making framework consisting of:
    1. Observe
    2. Orient
    3. Decide
    4. Act
    """
    
    metadata = {
        "tags": ["framework", "decision"],
        "category": "cognitive"
    }
    
    # Compute hash multiple times
    hash1 = compute_content_hash(content, metadata)
    hash2 = compute_content_hash(content, metadata)
    hash3 = compute_content_hash(content, metadata)
    
    # All should be identical
    assert hash1 == hash2 == hash3
    
    # Hash should be 64 chars (SHA256)
    assert len(hash1) == 64
    
    # Different content should produce different hash
    different_content = content + "\n\nAdditional information."
    hash_different = compute_content_hash(different_content, metadata)
    assert hash_different != hash1


def test_change_detection_with_normalization():
    """Test that change detection works with metadata normalization."""
    
    content = "Test knowledge content"
    
    # Original metadata with list
    meta1 = {
        "tags": ["ai", "ml", "nlp"],
        "version": 1
    }
    
    # "Changed" metadata with same list as string (should be detected as no change)
    meta2 = {
        "tags": "ai,ml,nlp",  # Same list, different format
        "version": 1
    }
    
    # Actually changed metadata
    meta3 = {
        "tags": ["ai", "ml", "nlp", "cv"],  # Added item
        "version": 1
    }
    
    # No change should be detected between meta1 and meta2
    assert not content_has_changed(content, content, meta1, meta2)
    
    # Change should be detected between meta1 and meta3
    assert content_has_changed(content, content, meta1, meta3)


def test_import_idempotency():
    """Test that importing the same content multiple times is idempotent."""
    
    # Simulate knowledge content
    knowledge_data = {
        "title": "Test Knowledge",
        "tags": ["test", "example"],
        "content": "This is test knowledge content.",
        "metadata": {
            "source": "test_suite",
            "version": "1.0"
        }
    }
    
    # Convert to YAML (as import script does)
    yaml_content = yaml.dump(knowledge_data, default_flow_style=False)
    
    # Compute hash for first import
    import_metadata1 = {
        "title": knowledge_data["title"],
        "tags": knowledge_data["tags"],
        "category": "imported"
    }
    hash1 = compute_content_hash(yaml_content, import_metadata1)
    
    # Compute hash for second import (should be identical)
    import_metadata2 = {
        "title": knowledge_data["title"],
        "tags": knowledge_data["tags"],
        "category": "imported"
    }
    hash2 = compute_content_hash(yaml_content, import_metadata2)
    
    assert hash1 == hash2, "Same content should produce same hash"


def test_metadata_with_special_characters():
    """Test metadata normalization with special characters and edge cases."""
    
    metadata = {
        "title": "Knowledge with 特殊字符 and émojis 🎉",
        "tags": ["unicode", "测试", "émoji"],
        "nested": {
            "deep": {
                "value": "with \"quotes\" and 'apostrophes'"
            }
        },
        "empty_list": [],
        "single_item_list": ["alone"],
        "number_list": [1, 2.5, 3],
        "mixed_list": ["text", 42, True, None]
    }
    
    normalized = normalize_metadata(metadata)
    
    # Unicode should be preserved
    assert "特殊字符" in normalized["title"]
    assert "🎉" in normalized["title"]
    
    # Lists with unicode
    assert "测试" in normalized["tags"]
    assert "émoji" in normalized["tags"]
    
    # Nested structure preserved in JSON
    import json
    nested = json.loads(normalized["nested"])
    assert nested["deep"]["value"] == 'with "quotes" and \'apostrophes\''
    
    # Edge cases
    assert normalized["empty_list"] == ""
    assert normalized["single_item_list"] == "alone"
    assert normalized["number_list"] == "1,2.5,3"
    assert normalized["mixed_list"] == "text,42,True,None"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])