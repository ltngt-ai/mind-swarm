#!/usr/bin/env python3
"""
Cleanup script to remove old cyber_states directory and move logs to personal folders.
Run this once after the refactoring is complete.
"""

import shutil
from pathlib import Path
import json
import sys

def main():
    # Get subspace root
    subspace_root = Path(__file__).parent.parent / "subspace"
    if not subspace_root.exists():
        print(f"Subspace directory not found: {subspace_root}")
        return 1
    
    print(f"Cleaning up old structure in {subspace_root}")
    
    # 1. Remove cyber_states directory if it exists
    cyber_states_dir = subspace_root / "cyber_states"
    if cyber_states_dir.exists():
        print(f"Removing old cyber_states directory: {cyber_states_dir}")
        shutil.rmtree(cyber_states_dir)
        print("  ✓ Removed cyber_states directory")
    else:
        print("  - No cyber_states directory found")
    
    # 2. Move logs from central logs directory to personal folders
    logs_dir = subspace_root / "logs" / "cybers"
    cybers_dir = subspace_root / "cybers"
    
    if logs_dir.exists():
        print(f"Moving logs from {logs_dir} to personal folders")
        
        for cyber_log_dir in logs_dir.iterdir():
            if cyber_log_dir.is_dir():
                cyber_name = cyber_log_dir.name
                cyber_personal = cybers_dir / cyber_name
                
                if cyber_personal.exists():
                    # Create logs directory in personal folder
                    personal_logs = cyber_personal / "logs"
                    personal_logs.mkdir(exist_ok=True)
                    
                    # Move all log files
                    for log_file in cyber_log_dir.glob("*.log"):
                        dest = personal_logs / log_file.name
                        print(f"  Moving {log_file.name} for {cyber_name}")
                        shutil.move(str(log_file), str(dest))
                    
                    # Remove empty cyber log directory
                    if not list(cyber_log_dir.iterdir()):
                        cyber_log_dir.rmdir()
                        print(f"  ✓ Moved logs for {cyber_name}")
        
        # Remove empty logs structure if everything moved
        if logs_dir.exists() and not list(logs_dir.iterdir()):
            logs_dir.rmdir()
            parent = logs_dir.parent
            if parent.name == "logs" and not list(parent.iterdir()):
                parent.rmdir()
                print("  ✓ Removed empty logs directory")
    else:
        print("  - No central logs directory found")
    
    # 3. Check for any agent_states references and rename to cyber_states
    print("\nChecking for old agent_state.json files to rename...")
    for cyber_dir in cybers_dir.iterdir():
        if cyber_dir.is_dir():
            memory_dir = cyber_dir / "memory"
            if memory_dir.exists():
                agent_state_file = memory_dir / "agent_state.json"
                if agent_state_file.exists():
                    cyber_state_file = memory_dir / "cyber_state.json"
                    print(f"  Renaming {agent_state_file} -> {cyber_state_file}")
                    agent_state_file.rename(cyber_state_file)
    
    print("\n✅ Cleanup complete!")
    return 0

if __name__ == "__main__":
    sys.exit(main())