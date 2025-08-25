#!/usr/bin/env python3
"""Fix multiple JSON encoding in task files."""

import json
import os
from pathlib import Path

def decode_multiple_json(content):
    """Decode multiple levels of JSON encoding."""
    decoded = content
    level = 0
    
    while True:
        try:
            if isinstance(decoded, str) and (decoded.startswith('"') or decoded.startswith('{')):
                decoded = json.loads(decoded)
                level += 1
            else:
                break
        except:
            break
    
    return decoded, level

def fix_file(filepath):
    """Fix multiple JSON encoding in a file."""
    print(f"Processing: {filepath}")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    decoded, levels = decode_multiple_json(content)
    
    if levels > 1:
        print(f"  Found {levels} levels of encoding")
        
        # Backup original
        backup_path = str(filepath) + '.backup'
        with open(backup_path, 'w') as f:
            f.write(content)
        print(f"  Backed up to: {backup_path}")
        
        # Write fixed version
        with open(filepath, 'w') as f:
            json.dump(decoded, f, indent=2)
        print(f"  Fixed file with proper JSON")
        
        return True
    else:
        print(f"  File is OK (only {levels} level of encoding)")
        return False

def main():
    """Fix all multi-encoded task files."""
    base_path = Path('/home/deano/projects/subspace/cybers')
    fixed_count = 0
    
    print("Scanning for multi-encoded JSON files...\n")
    
    for cyber_dir in base_path.glob('*'):
        if cyber_dir.is_dir():
            # Check current_available_tasks
            tasks_dir = cyber_dir / 'current_available_tasks'
            if tasks_dir.exists():
                for task_file in tasks_dir.glob('*.json'):
                    if fix_file(task_file):
                        fixed_count += 1
            
            # Check .internal/tasks
            for task_type in ['maintenance', 'hobby', 'community']:
                task_dir = cyber_dir / '.internal' / 'tasks' / task_type
                if task_dir.exists():
                    for task_file in task_dir.glob('*.json'):
                        if fix_file(task_file):
                            fixed_count += 1
    
    print(f"\nFixed {fixed_count} files with multiple JSON encoding")
    
    # Clean up Carol's specific files we know are affected
    carol_files = [
        '/home/deano/projects/subspace/cybers/Carol/current_available_tasks/HT-002.json',
        '/home/deano/projects/subspace/cybers/Carol/current_available_tasks/HT-009.json',
        '/home/deano/projects/subspace/cybers/Carol/current_available_tasks/MT-004.json',
        '/home/deano/projects/subspace/cybers/Carol/current_available_tasks/MT-003.json',
    ]
    
    print("\nSpecifically checking Carol's files...")
    for filepath in carol_files:
        if Path(filepath).exists():
            fix_file(filepath)

if __name__ == '__main__':
    main()