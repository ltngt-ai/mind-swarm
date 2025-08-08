#!/usr/bin/env python3
"""Test the new memory ID system to ensure it works correctly."""

import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "subspace_template" / "grid" / "library" / "base_code" / "base_code_template"))

from memory.unified_memory_id import UnifiedMemoryID
from memory.memory_types import MemoryType

def test_memory_id_creation():
    """Test creating memory IDs with the new format."""
    print("Testing Memory ID Creation\n" + "="*50)
    
    # Test file memory IDs
    file_id = UnifiedMemoryID.create(MemoryType.FILE, "personal/memory/journal.md")
    print(f"File ID: {file_id}")
    
    grid_file_id = UnifiedMemoryID.create(MemoryType.FILE, "grid/community/cyber_directory.json")
    print(f"Grid File ID: {grid_file_id}")
    
    # Test with content hash
    hash_id = UnifiedMemoryID.create(MemoryType.FILE, "personal/memory/notes.txt", "content here")
    print(f"With Hash: {hash_id}")
    
    # Test observation IDs
    obs_id = UnifiedMemoryID.create_observation_id("new_message", "/personal/inbox/msg_001.msg")
    print(f"Observation ID: {obs_id}")
    
    # Test when path is a memory ID
    obs_from_memory = UnifiedMemoryID.create_observation_id("memory_focused", "file:grid/community/cyber_directory.json")
    print(f"Observation from Memory ID: {obs_from_memory}")
    
    print()

def test_memory_id_parsing():
    """Test parsing memory IDs."""
    print("Testing Memory ID Parsing\n" + "="*50)
    
    # Parse new format
    id1 = "file:personal/memory/journal.md"
    parts = UnifiedMemoryID.parse(id1)
    print(f"Parsing '{id1}':")
    print(f"  Type: {parts['type']}")
    print(f"  Path: {parts['path']}")
    print(f"  Namespace: {parts['namespace']}")
    print()
    
    # Parse with hash
    id2 = "file:grid/community/discussion.txt:abc123"
    parts = UnifiedMemoryID.parse(id2)
    print(f"Parsing '{id2}':")
    print(f"  Type: {parts['type']}")
    print(f"  Path: {parts['path']}")
    print(f"  Hash: {parts.get('hash', 'None')}")
    print()
    
    # Test legacy format handling
    try:
        legacy_id = "personal:file:personal:journal.md"
        parts = UnifiedMemoryID.parse(legacy_id)
        print(f"Parsing legacy '{legacy_id}':")
        print(f"  Type: {parts['type']}")
        print(f"  Path: {parts['path']}")
        print(f"  Namespace: {parts['namespace']}")
    except Exception as e:
        print(f"Error parsing legacy format: {e}")
    print()

def test_path_conversion():
    """Test converting filesystem paths to memory IDs."""
    print("Testing Path Conversion\n" + "="*50)
    
    paths = [
        "/personal/memory/journal.md",
        "/grid/community/cyber_directory.json",
        "personal/inbox/msg.txt",
        "grid/library/knowledge.yaml",
        "/some/random/personal/file.txt",
        "/another/grid/shared/doc.md"
    ]
    
    for path in paths:
        memory_id = UnifiedMemoryID.create_from_path(path)
        print(f"{path:40} -> {memory_id}")
    print()

def test_filesystem_path():
    """Test converting memory IDs back to filesystem paths."""
    print("Testing Memory ID to Filesystem Path\n" + "="*50)
    
    ids = [
        "file:personal/memory/journal.md",
        "file:grid/community/discussion.txt",
        "observation:personal/new_message/msg_001"
    ]
    
    for memory_id in ids:
        path = UnifiedMemoryID.to_filesystem_path(memory_id)
        print(f"{memory_id:45} -> {path}")
    print()

def test_pattern_matching():
    """Test pattern matching with the new format."""
    print("Testing Pattern Matching\n" + "="*50)
    
    test_ids = [
        "file:personal/memory/journal.md",
        "file:personal/inbox/msg.txt",
        "file:grid/community/discussion.txt",
        "observation:personal/new_message/msg_001"
    ]
    
    patterns = [
        "file:personal/*",
        "file:personal/memory/*",
        "file:grid/**",
        "observation:**"
    ]
    
    for pattern in patterns:
        print(f"\nPattern: {pattern}")
        for test_id in test_ids:
            matches = UnifiedMemoryID.matches_pattern(test_id, pattern)
            print(f"  {test_id:45} {'✓' if matches else '✗'}")
    print()

if __name__ == "__main__":
    test_memory_id_creation()
    test_memory_id_parsing()
    test_path_conversion()
    test_filesystem_path()
    test_pattern_matching()
    
    print("\n" + "="*50)
    print("All tests completed!")