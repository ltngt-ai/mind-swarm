#!/usr/bin/env python3
"""Verify that the Mind-Swarm migration was successful."""

import sys
from pathlib import Path

def check_imports():
    """Check that basic imports work."""
    try:
        from mind_swarm.schemas.cyber_types import CyberType, CyberTypeConfig
        from mind_swarm.subspace.cyber_spawner import CyberSpawner
        from mind_swarm.subspace.cyber_registry import CyberRegistry
        from mind_swarm.subspace.cyber_state import CyberState
        print("✓ All renamed imports work correctly")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def check_filesystem():
    """Check that filesystem changes were made."""
    project_root = Path(__file__).parent
    
    checks = [
        (project_root / "subspace" / "cybers", "Cybers directory exists"),
        (project_root / "subspace" / "grid" / "community", "Community directory exists"),
        (project_root / "subspace" / "grid" / "library" / "knowledge", "Knowledge directory exists"),
        (project_root / "subspace_template" / "grid" / "library" / "base_code" / "io_cyber_template", "IO Cyber template exists"),
    ]
    
    all_good = True
    for path, description in checks:
        if path.exists():
            print(f"✓ {description}: {path.relative_to(project_root)}")
        else:
            print(f"✗ {description}: NOT FOUND")
            all_good = False
    
    # Check that old directories are gone
    old_paths = [
        (project_root / "subspace" / "agents", "Old agents directory removed"),
        (project_root / "subspace" / "agent_states", "Old agent_states directory removed"),
        (project_root / "subspace" / "grid" / "plaza", "Old plaza directory removed"),
    ]
    
    for path, description in old_paths:
        if not path.exists():
            print(f"✓ {description}")
        else:
            print(f"✗ {description}: STILL EXISTS")
            all_good = False
    
    return all_good

def check_memory_ids():
    """Check that memory ID system works with prefixes."""
    try:
        # This import path might need adjustment based on actual structure
        sys.path.insert(0, str(Path(__file__).parent / "subspace_template" / "grid" / "library" / "base_code" / "base_code_template"))
        from memory.unified_memory_id import UnifiedMemoryID
        from memory.memory_types import MemoryType
        
        # Test creating IDs with prefixes
        personal_id = UnifiedMemoryID.create(MemoryType.FILE, "personal", "notes/todo.txt")
        assert personal_id.startswith("personal:"), f"Personal ID should start with 'personal:' but got {personal_id}"
        
        grid_id = UnifiedMemoryID.create(MemoryType.FILE, "library", "knowledge/concepts.yaml")
        assert grid_id.startswith("grid:"), f"Grid ID should start with 'grid:' but got {grid_id}"
        
        # Test parsing IDs
        parsed = UnifiedMemoryID.parse(personal_id)
        assert parsed['prefix'] == 'personal', f"Expected prefix 'personal' but got {parsed.get('prefix')}"
        
        print(f"✓ Memory ID system works with prefixes")
        print(f"  Example personal ID: {personal_id}")
        print(f"  Example grid ID: {grid_id}")
        return True
    except Exception as e:
        print(f"✗ Memory ID error: {e}")
        return False

def main():
    """Run all verification checks."""
    print("="*60)
    print("MIND-SWARM MIGRATION VERIFICATION")
    print("="*60)
    print()
    
    results = []
    
    print("1. Checking Python imports...")
    results.append(check_imports())
    print()
    
    print("2. Checking filesystem structure...")
    results.append(check_filesystem())
    print()
    
    print("3. Checking memory ID system...")
    results.append(check_memory_ids())
    print()
    
    print("="*60)
    if all(results):
        print("✓ ALL CHECKS PASSED - Migration successful!")
        return 0
    else:
        print("✗ SOME CHECKS FAILED - Please review issues above")
        return 1

if __name__ == "__main__":
    sys.exit(main())