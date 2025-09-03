"""
Unit tests for metadata normalization and content hash utilities.
"""

import pytest
import json
from src.mind_swarm.utils.metadata_helpers import (
    normalize_metadata_value,
    normalize_metadata,
    denormalize_list_value,
    compute_content_hash,
    compute_short_hash,
    metadata_has_changed,
    content_has_changed,
    prepare_for_chromadb,
    extract_lists_from_metadata,
    normalize_cyber_metadata
)


class TestNormalizeMetadataValue:
    """Test single value normalization."""
    
    def test_none_value(self):
        """None should become empty string."""
        assert normalize_metadata_value(None) == ""
    
    def test_string_value(self):
        """Strings should pass through unchanged."""
        assert normalize_metadata_value("hello") == "hello"
        assert normalize_metadata_value("") == ""
    
    def test_numeric_values(self):
        """Numbers should pass through unchanged."""
        assert normalize_metadata_value(42) == 42
        assert normalize_metadata_value(3.14) == 3.14
        assert normalize_metadata_value(0) == 0
    
    def test_boolean_values(self):
        """Booleans should pass through unchanged."""
        assert normalize_metadata_value(True) is True
        assert normalize_metadata_value(False) is False
    
    def test_empty_list(self):
        """Empty list should become empty string."""
        assert normalize_metadata_value([]) == ""
    
    def test_simple_list(self):
        """Lists should become comma-separated strings."""
        assert normalize_metadata_value(["a", "b", "c"]) == "a,b,c"
        assert normalize_metadata_value([1, 2, 3]) == "1,2,3"
    
    def test_mixed_list(self):
        """Mixed type lists should convert all items to strings."""
        assert normalize_metadata_value(["hello", 42, True]) == "hello,42,True"
    
    def test_list_with_none(self):
        """Lists with None should handle it properly."""
        assert normalize_metadata_value([None, "a", None]) == "None,a,None"
    
    def test_simple_dict(self):
        """Dicts should become JSON strings."""
        result = normalize_metadata_value({"key": "value"})
        assert result == '{"key":"value"}'
    
    def test_nested_dict(self):
        """Nested dicts should serialize to JSON."""
        data = {"outer": {"inner": "value"}}
        result = normalize_metadata_value(data)
        assert json.loads(result) == data
    
    def test_dict_with_sorted_keys(self):
        """Dict keys should be sorted for consistency."""
        data = {"z": 1, "a": 2, "m": 3}
        result = normalize_metadata_value(data)
        assert result == '{"a":2,"m":3,"z":1}'
    
    def test_complex_object(self):
        """Complex objects should convert to string."""
        class CustomObject:
            def __str__(self):
                return "custom_object"
        
        obj = CustomObject()
        assert normalize_metadata_value(obj) == "custom_object"


class TestNormalizeMetadata:
    """Test full metadata dictionary normalization."""
    
    def test_empty_metadata(self):
        """Empty metadata should return empty dict."""
        assert normalize_metadata({}) == {}
        assert normalize_metadata(None) == {}
    
    def test_simple_metadata(self):
        """Simple metadata should normalize values."""
        input_meta = {
            "name": "test",
            "count": 5,
            "active": True
        }
        expected = {
            "name": "test",
            "count": 5,
            "active": True
        }
        assert normalize_metadata(input_meta) == expected
    
    def test_metadata_with_lists(self):
        """Metadata with lists should convert to comma-separated."""
        input_meta = {
            "tags": ["ai", "ml", "nlp"],
            "scores": [1, 2, 3],
            "empty": []
        }
        expected = {
            "tags": "ai,ml,nlp",
            "scores": "1,2,3",
            "empty": ""
        }
        assert normalize_metadata(input_meta) == expected
    
    def test_metadata_with_none_values(self):
        """None values should become empty strings."""
        input_meta = {
            "field1": None,
            "field2": "value"
        }
        expected = {
            "field1": "",
            "field2": "value"
        }
        assert normalize_metadata(input_meta) == expected
    
    def test_metadata_with_none_key(self):
        """None keys should be skipped."""
        input_meta = {
            None: "value",
            "valid": "data"
        }
        expected = {
            "valid": "data"
        }
        assert normalize_metadata(input_meta) == expected
    
    def test_metadata_with_nested_structures(self):
        """Nested structures should be JSON-serialized."""
        input_meta = {
            "simple": "value",
            "nested": {"inner": {"deep": "value"}},
            "mixed": ["a", {"b": "c"}]
        }
        result = normalize_metadata(input_meta)
        assert result["simple"] == "value"
        assert json.loads(result["nested"]) == {"inner": {"deep": "value"}}
        # Mixed list becomes string
        assert "a" in result["mixed"]


class TestDenormalizeListValue:
    """Test converting comma-separated strings back to lists."""
    
    def test_empty_string(self):
        """Empty string should return empty list."""
        assert denormalize_list_value("") == []
        assert denormalize_list_value(None) == []
    
    def test_simple_list(self):
        """Simple comma-separated should split correctly."""
        assert denormalize_list_value("a,b,c") == ["a", "b", "c"]
    
    def test_list_with_spaces(self):
        """Spaces should be trimmed."""
        assert denormalize_list_value("a, b , c") == ["a", "b", "c"]
    
    def test_single_value(self):
        """Single value should return single-item list."""
        assert denormalize_list_value("single") == ["single"]
    
    def test_custom_separator(self):
        """Custom separators should work."""
        assert denormalize_list_value("a|b|c", separator="|") == ["a", "b", "c"]
    
    def test_empty_items_filtered(self):
        """Empty items should be filtered out."""
        assert denormalize_list_value("a,,b,,,c") == ["a", "b", "c"]


class TestContentHashing:
    """Test content hashing functions."""
    
    def test_simple_content_hash(self):
        """Content should produce consistent hash."""
        content = "Hello, world!"
        hash1 = compute_content_hash(content)
        hash2 = compute_content_hash(content)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length
    
    def test_content_with_metadata_hash(self):
        """Content with metadata should affect hash."""
        content = "Hello, world!"
        metadata = {"key": "value"}
        
        hash_without = compute_content_hash(content)
        hash_with = compute_content_hash(content, metadata)
        
        assert hash_without != hash_with
    
    def test_metadata_order_doesnt_matter(self):
        """Metadata key order shouldn't affect hash."""
        content = "test"
        meta1 = {"a": 1, "b": 2, "c": 3}
        meta2 = {"c": 3, "a": 1, "b": 2}
        
        hash1 = compute_content_hash(content, meta1)
        hash2 = compute_content_hash(content, meta2)
        
        assert hash1 == hash2
    
    def test_short_hash(self):
        """Short hash should truncate correctly."""
        content = "Test content"
        
        hash8 = compute_short_hash(content, length=8)
        assert len(hash8) == 8
        
        hash16 = compute_short_hash(content, length=16)
        assert len(hash16) == 16
        assert hash16.startswith(hash8)
    
    def test_unicode_content(self):
        """Unicode content should hash correctly."""
        content = "Hello 世界 🌍"
        hash_val = compute_content_hash(content)
        assert len(hash_val) == 64


class TestChangeDetection:
    """Test change detection functions."""
    
    def test_metadata_no_change(self):
        """Identical metadata should not show change."""
        meta1 = {"key": "value", "num": 42}
        meta2 = {"key": "value", "num": 42}
        assert not metadata_has_changed(meta1, meta2)
    
    def test_metadata_value_changed(self):
        """Changed value should be detected."""
        meta1 = {"key": "value1"}
        meta2 = {"key": "value2"}
        assert metadata_has_changed(meta1, meta2)
    
    def test_metadata_key_added(self):
        """Added key should be detected."""
        meta1 = {"key": "value"}
        meta2 = {"key": "value", "new": "data"}
        assert metadata_has_changed(meta1, meta2)
    
    def test_metadata_type_normalization(self):
        """Type differences that normalize the same shouldn't show change."""
        # These should normalize to the same value
        meta1 = {"tags": ["a", "b", "c"]}
        meta2 = {"tags": "a,b,c"}
        assert not metadata_has_changed(meta1, meta2)
    
    def test_content_no_change(self):
        """Identical content should not show change."""
        content = "Same content"
        assert not content_has_changed(content, content)
    
    def test_content_changed(self):
        """Different content should show change."""
        assert content_has_changed("content1", "content2")
    
    def test_content_with_metadata_change(self):
        """Metadata change should be detected even with same content."""
        content = "Same content"
        meta1 = {"version": 1}
        meta2 = {"version": 2}
        assert content_has_changed(content, content, meta1, meta2)


class TestPrepareForChromaDB:
    """Test the convenience preparation function."""
    
    def test_basic_preparation(self):
        """Basic preparation should normalize and add hash."""
        content = "Test content"
        metadata = {"tags": ["a", "b"], "count": 5}
        
        result = prepare_for_chromadb(content, metadata)
        
        assert result["content"] == content
        assert result["metadata"]["tags"] == "a,b"
        assert result["metadata"]["count"] == 5
        assert "content_hash" in result["metadata"]
    
    def test_preparation_without_hash(self):
        """Should be able to skip hash computation."""
        content = "Test content"
        metadata = {"key": "value"}
        
        result = prepare_for_chromadb(content, metadata, compute_hash=False)
        
        assert "content_hash" not in result["metadata"]
    
    def test_preparation_without_metadata(self):
        """Should work with no metadata."""
        content = "Test content"
        
        result = prepare_for_chromadb(content)
        
        assert result["content"] == content
        assert "content_hash" in result["metadata"]


class TestExtractLists:
    """Test list extraction from normalized metadata."""
    
    def test_extract_single_list(self):
        """Should extract specified list field."""
        metadata = {
            "tags": "a,b,c",
            "other": "value"
        }
        
        result = extract_lists_from_metadata(metadata, ["tags"])
        
        assert result["tags"] == ["a", "b", "c"]
        assert result["other"] == "value"
    
    def test_extract_multiple_lists(self):
        """Should extract multiple list fields."""
        metadata = {
            "tags": "a,b",
            "categories": "x,y,z",
            "single": "value"
        }
        
        result = extract_lists_from_metadata(metadata, ["tags", "categories"])
        
        assert result["tags"] == ["a", "b"]
        assert result["categories"] == ["x", "y", "z"]
        assert result["single"] == "value"
    
    def test_extract_missing_field(self):
        """Missing fields should be ignored."""
        metadata = {"other": "value"}
        
        result = extract_lists_from_metadata(metadata, ["tags"])
        
        assert result == metadata
    
    def test_extract_non_string_field(self):
        """Non-string fields should be left alone."""
        metadata = {
            "tags": 42,
            "other": "value"
        }
        
        result = extract_lists_from_metadata(metadata, ["tags"])
        
        assert result["tags"] == 42


class TestNormalizeCyberMetadata:
    """Test cyber-specific metadata normalization."""
    
    def test_standard_fields(self):
        """Standard fields should be normalized."""
        metadata = {
            "cyber_id": "cyber-123",
            "timestamp": "2024-01-01T00:00:00",
            "source": "test",
            "category": "knowledge",
            "title": "Test Title",
            "description": "Test description"
        }
        
        result = normalize_cyber_metadata(metadata)
        
        for key in metadata:
            assert result[key] == metadata[key]
    
    def test_boolean_fields(self):
        """Boolean fields should be properly converted."""
        test_cases = [
            ({"personal": "true"}, True),
            ({"personal": "false"}, False),
            ({"personal": "1"}, True),
            ({"personal": "0"}, False),
            ({"personal": "yes"}, True),
            ({"personal": "no"}, False),
            ({"personal": True}, True),
            ({"personal": False}, False),
        ]
        
        for input_meta, expected in test_cases:
            result = normalize_cyber_metadata(input_meta)
            assert result["personal"] is expected
    
    def test_list_fields(self):
        """List fields should be comma-separated."""
        metadata = {
            "tags": ["ai", "ml"],
            "topics": ["tech", "science"],
            "capabilities": [],
            "dependencies": ["dep1"]
        }
        
        result = normalize_cyber_metadata(metadata)
        
        assert result["tags"] == "ai,ml"
        assert result["topics"] == "tech,science"
        assert result["capabilities"] == ""
        assert result["dependencies"] == "dep1"
    
    def test_numeric_fields(self):
        """Numeric fields should preserve type when possible."""
        metadata = {
            "priority": 1,
            "version": 2.5,
            "score": "3.14"
        }
        
        result = normalize_cyber_metadata(metadata)
        
        assert result["priority"] == 1
        assert result["version"] == 2.5
        assert result["score"] == 3.14
    
    def test_numeric_whole_numbers(self):
        """Whole numbers should be converted to int."""
        metadata = {
            "priority": "5.0",
            "version": 3.0
        }
        
        result = normalize_cyber_metadata(metadata)
        
        assert result["priority"] == 5
        assert isinstance(result["priority"], int)
        assert result["version"] == 3
        assert isinstance(result["version"], int)
    
    def test_invalid_numeric(self):
        """Invalid numeric values should be stored as strings."""
        metadata = {
            "priority": "high",
            "score": "N/A"
        }
        
        result = normalize_cyber_metadata(metadata)
        
        assert result["priority"] == "high"
        assert result["score"] == "N/A"
    
    def test_additional_fields(self):
        """Additional fields should be normalized."""
        metadata = {
            "custom_field": "value",
            "custom_list": ["a", "b"],
            "custom_dict": {"nested": "value"}
        }
        
        result = normalize_cyber_metadata(metadata)
        
        assert result["custom_field"] == "value"
        assert result["custom_list"] == "a,b"
        assert json.loads(result["custom_dict"]) == {"nested": "value"}
    
    def test_mixed_metadata(self):
        """Mixed metadata should all be handled correctly."""
        metadata = {
            "cyber_id": "test-123",
            "personal": True,
            "tags": ["urgent", "review"],
            "priority": 1,
            "custom": {"data": "value"},
            "empty_list": [],
            "none_value": None
        }
        
        result = normalize_cyber_metadata(metadata)
        
        assert result["cyber_id"] == "test-123"
        assert result["personal"] is True
        assert result["tags"] == "urgent,review"
        assert result["priority"] == 1
        assert json.loads(result["custom"]) == {"data": "value"}
        assert result["empty_list"] == ""
        assert result["none_value"] == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])