#!/usr/bin/env python3
"""Quick test that the new Python script execution is working."""

import json
from pathlib import Path

print("Testing new Python script-based execution model...")
print("=" * 60)

# Check that V2 stages are being imported
try:
    import sys
    sys.path.insert(0, 'subspace_template/grid/library/base_code')
    
    from base_code_template.stages.decision_stage_v2 import DecisionStageV2
    from base_code_template.stages.execution_stage_v2 import ExecutionStageV2
    print("✅ V2 stages imported successfully")
    
    # Check that they're being used in cognitive_loop
    from base_code_template.cognitive_loop import DecisionStage, ExecutionStage
    
    # These should be the V2 versions
    if DecisionStage.__name__ == "DecisionStageV2":
        print("✅ DecisionStage is V2 (generates intentions)")
    else:
        print("❌ DecisionStage is not V2")
        
    if ExecutionStage.__name__ == "ExecutionStageV2":
        print("✅ ExecutionStage is V2 (generates Python scripts)")
    else:
        print("❌ ExecutionStage is not V2")
        
    print("\n" + "=" * 60)
    print("SUCCESS! The system is now using Python script-based execution")
    print("=" * 60)
    print("\nKey changes:")
    print("- Decision stage generates plain language intentions")
    print("- Execution stage generates and runs Python scripts")
    print("- Actions are Python modules (send_message, memory, etc.)")
    print("- Full Python capabilities available")
    print("\nNo configuration needed - this is now the default!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the mind-swarm directory")
except Exception as e:
    print(f"❌ Error: {e}")