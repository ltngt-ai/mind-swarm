# Metadata Normalization and Content Hash Utilities

## Overview

This module provides shared helpers for preparing metadata for ChromaDB storage and detecting content changes through deterministic hashing. These utilities ensure consistent handling of metadata across the Mind-Swarm knowledge system.

## Key Components

### 1. Metadata Normalization (`normalize_metadata`)

Converts metadata values to ChromaDB-compatible types:
- **Lists** → Comma-separated strings (e.g., `["a", "b"]` → `"a,b"`)
- **Dicts/Objects** → JSON strings (with sorted keys for consistency)
- **None** → Empty string
- **Primitives** (str, int, float, bool) → Pass through unchanged

### 2. Content Hashing (`compute_content_hash`)

Creates deterministic SHA256 hashes for:
- Content deduplication
- Change detection
- Idempotent imports

Features:
- Combines content and metadata into single hash
- Normalizes metadata before hashing for consistency
- Supports unicode and special characters

### 3. Change Detection

- `content_has_changed`: Detects changes in content or metadata
- `metadata_has_changed`: Compares normalized metadata for differences

### 4. Cyber-Specific Normalization (`normalize_cyber_metadata`)

Handles common cyber metadata fields:
- **Standard fields**: cyber_id, timestamp, source, category, title
- **Boolean fields**: personal, active, archived (with string parsing)
- **List fields**: tags, topics, capabilities, dependencies  
- **Numeric fields**: priority, version, score (preserves int vs float)

## Usage Examples

### Basic Metadata Normalization

```python
from src.mind_swarm.utils.metadata_helpers import normalize_metadata

metadata = {
    "tags": ["ai", "ml", "nlp"],
    "priority": 1,
    "config": {"model": "gpt-4"},
    "empty": None
}

normalized = normalize_metadata(metadata)
# Result: {
#     "tags": "ai,ml,nlp",
#     "priority": 1,
#     "config": '{"model":"gpt-4"}',
#     "empty": ""
# }
```

### Content Hash for Deduplication

```python
from src.mind_swarm.utils.metadata_helpers import compute_content_hash

content = "Knowledge content here..."
metadata = {"tags": ["important"], "version": 1}

hash_id = compute_content_hash(content, metadata)
# Returns consistent 64-character SHA256 hash
```

### Change Detection

```python
from src.mind_swarm.utils.metadata_helpers import content_has_changed

# Check if content or metadata changed
if content_has_changed(old_content, new_content, old_meta, new_meta):
    # Update the knowledge entry
    pass
else:
    # Skip unchanged content
    pass
```

## Integration Points

### Knowledge Handler
- Uses `normalize_cyber_metadata` for all metadata storage
- Generates IDs with `compute_short_hash`
- Normalizes metadata in store, update, and CLI methods

### Import Script
- Adds `content_hash` to metadata for change detection
- Checks existing knowledge before importing
- Reports unchanged vs updated items

## Testing

Comprehensive test coverage includes:
- 51 unit tests for all normalization functions
- 5 integration tests for real-world scenarios
- Edge cases: unicode, special characters, empty values
- Idempotency verification

Run tests:
```bash
pytest tests/test_metadata_helpers.py
pytest tests/test_metadata_integration.py
```

## Benefits

1. **Consistency**: All metadata follows same normalization rules
2. **Idempotency**: Same content always produces same hash
3. **Change Detection**: Efficient comparison without full content comparison
4. **ChromaDB Compatibility**: Ensures all metadata types are supported
5. **Deduplication**: Content hashes prevent duplicate storage