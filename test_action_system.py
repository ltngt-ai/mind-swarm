#!/usr/bin/env python3
"""Test script to verify the explicit JSON array action system."""

import json
from pathlib import Path
from datetime import datetime

# Create test message for Alice
test_message = {
    "type": "COMMAND",
    "from": "test_script",
    "to": "Alice",
    "command": "think",
    "params": {
        "query": "Fetch the contents of https://example.com and tell me what the page is about"
    },
    "timestamp": datetime.now().isoformat()
}

# Write to a test file
test_file = Path("test_network_request.msg")
test_file.write_text(json.dumps(test_message, indent=2))

print(f"Created test message: {test_file}")
print(f"Message content: {json.dumps(test_message, indent=2)}")
print("\nTo test:")
print("1. Make sure Alice is running")
print("2. Copy this file to Alice's inbox: cp test_network_request.msg subspace/agents/Alice/inbox/")
print("3. Watch the logs to see if Alice properly parses the action list")