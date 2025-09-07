#!/usr/bin/env python3
"""Manual tool to probe the knowledge sync API with scope parameter.

This script performs real HTTP calls to a running Mind‑Swarm server and is
intended for manual testing only. It is skipped during automated pytest runs.
"""

import pytest

# Skip this module in CI/automated test runs
pytestmark = pytest.mark.skip(reason="manual integration script; exclude from CI")

import httpx
import json
import asyncio
from typing import Optional

API_BASE_URL = "http://localhost:8000"

async def test_sync_endpoint(scope: Optional[str] = None):
    """Test the sync endpoint with different scopes."""
    
    async with httpx.AsyncClient() as client:
        # Build URL with scope parameter
        url = f"{API_BASE_URL}/knowledge/sync"
        params = {"scope": scope} if scope else {}
        
        print(f"\n--- Testing scope: {scope or 'default (all)'} ---")
        
        # Try GET request
        print(f"Testing GET {url}")
        try:
            response = await client.get(url, params=params)
            print(f"GET Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print_response(data)
            else:
                print(f"GET Error: {response.text}")
        except Exception as e:
            print(f"GET Exception: {e}")
        
        # Try POST request
        print(f"\nTesting POST {url}")
        try:
            response = await client.post(url, params=params)
            print(f"POST Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print_response(data)
            else:
                print(f"POST Error: {response.text}")
        except Exception as e:
            print(f"POST Exception: {e}")

def print_response(data: dict):
    """Pretty print the response data."""
    
    print(f"Status: {data.get('status', 'N/A')}")
    print(f"Message: {data.get('message', 'N/A')}")
    
    if "config" in data:
        config = data["config"]
        print(f"Config Version: {config.get('version', 'N/A')}")
        print(f"Scope Applied: {config.get('scope', 'N/A')}")
        print(f"Roots Processed: {', '.join(config.get('roots_processed', []))}")
    
    if "stats" in data:
        stats = data["stats"]
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
        print(f"  - Errors: {stats.get('errors', 0)}")
        print(f"  - Security Blocked: {stats.get('security_blocked', 0)}")
    
    if "warnings" in data:
        print(f"\nWarnings:")
        for warning in data["warnings"]:
            print(f"  - {warning}")

async def main():
    """Main test function."""
    
    print("="*60)
    print("Testing Knowledge Sync API with Scopes")
    print("="*60)
    print(f"API URL: {API_BASE_URL}")
    
    # Check if server is running
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}/health")
            if response.status_code != 200:
                print("\n⚠️  Server not available at", API_BASE_URL)
                print("Please ensure the Mind-Swarm server is running:")
                print("  ./run.sh server")
                return
        except Exception:
            print("\n⚠️  Server not available at", API_BASE_URL)
            print("Please ensure the Mind-Swarm server is running:")
            print("  ./run.sh server")
            return
    
    # Test different scopes
    scopes = [None, 'all', 'library', 'template', 'community', 'invalid']
    
    for scope in scopes:
        await test_sync_endpoint(scope)
        print()

if __name__ == "__main__":
    asyncio.run(main())
