#!/usr/bin/env python3
"""Manual tool to exercise knowledge sync with the scope parameter.

This script initializes Subspace components and performs real sync operations.
It requires local dependencies (e.g., bubblewrap) and a configured environment.
It is skipped during automated pytest discovery/runs.
"""

import pytest

# Skip this module in CI/automated test runs
pytestmark = pytest.mark.skip(reason="manual integration script; exclude from CI")

import asyncio
import os
from pathlib import Path
import sys
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from mind_swarm.subspace.coordinator import SubspaceCoordinator
from mind_swarm.subspace.sandbox import SubspaceManager
from mind_swarm.utils.logging import logger

async def test_sync_with_scopes():
    """Test knowledge sync with different scope values."""
    
    # Setup test environment
    os.environ["SUBSPACE_ROOT"] = str(Path(__file__).parent / "test_subspace")
    
    # Create coordinator
    subspace = SubspaceManager()
    coordinator = SubspaceCoordinator(subspace)
    
    # Initialize if needed
    if not coordinator.knowledge_handler or not coordinator.knowledge_handler.enabled:
        logger.info("Knowledge system not available, initializing...")
        await coordinator.initialize()
    
    print("\n" + "="*60)
    print("Testing Knowledge Sync with Scopes")
    print("="*60)
    
    # Test different scopes
    scopes = ['template', 'library', 'community', 'all', None]
    
    for scope in scopes:
        print(f"\n--- Testing scope: {scope or 'default (all)'} ---")
        try:
            result = await coordinator.sync_knowledge(scope=scope)
            
            if result["status"] == "success":
                stats = result.get("stats", {})
                config = result.get("config", {})
                
                print(f"Status: {result['status']}")
                print(f"Message: {result['message']}")
                print(f"Config Version: {config.get('version', 'N/A')}")
                print(f"Scope Applied: {config.get('scope', 'N/A')}")
                print(f"Roots Processed: {', '.join(config.get('roots_processed', []))}")
                
                if "summary" in stats:
                    summary = stats["summary"]
                    print(f"\nSummary:")
                    print(f"  - Total Files Scanned: {summary.get('total_files_scanned', 0)}")
                    print(f"  - Total Processed: {summary.get('total_processed', 0)}")
                    print(f"  - Total Skipped: {summary.get('total_skipped', 0)}")
                    print(f"  - Success Rate: {summary.get('success_rate', '0%')}")
                    print(f"  - Roots Count: {summary.get('roots_count', 0)}")
                
                print(f"\nDetails:")
                print(f"  - Added: {stats.get('added', 0)}")
                print(f"  - Updated: {stats.get('updated', 0)}")
                print(f"  - Unchanged: {stats.get('unchanged', 0)}")
                print(f"  - Migrated: {stats.get('migrated', 0)}")
                print(f"  - Errors: {stats.get('errors', 0)}")
                print(f"  - Skipped: {stats.get('skipped', 0)}")
                print(f"  - Security Blocked: {stats.get('security_blocked', 0)}")
                
                if "warnings" in result:
                    print(f"\nWarnings:")
                    for warning in result["warnings"]:
                        print(f"  - {warning}")
            else:
                print(f"Error: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"Exception: {e}")
            import traceback
            traceback.print_exc()
    
    # Test invalid scope
    print(f"\n--- Testing invalid scope: 'invalid' ---")
    try:
        result = await coordinator.sync_knowledge(scope='invalid')
        print(f"Status: {result['status']}")
        print(f"Message: {result['message']}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_sync_with_scopes())
