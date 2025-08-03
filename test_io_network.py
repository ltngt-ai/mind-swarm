#!/usr/bin/env python3
"""Test script for IO agent network functionality."""

import json
from pathlib import Path
from datetime import datetime

# Create test message for Ian-io
test_message = {
    "type": "QUERY",
    "from": "test_script",
    "to": "Ian-io",
    "query": "Please fetch the webpage at https://example.com and summarize what you find",
    "timestamp": datetime.now().isoformat()
}

# Write to a test file
test_file = Path("test_io_network.msg")
test_file.write_text(json.dumps(test_message, indent=2))

print(f"Created test message: {test_file}")
print(f"Message content: {json.dumps(test_message, indent=2)}")
print("\nTo test:")
print("1. Make sure Ian-io is running") 
print("2. Copy this file to Ian-io's inbox: cp test_io_network.msg subspace/agents/Ian-io/inbox/")
print("3. Watch the logs - you should see:")
print("   - Ian-io parsing the action list as JSON array")
print("   - Actions like: ['think', 'make_network_request', 'wait', 'send_message', 'finish']")
print("   - Network request being made through the network body file")