#!/usr/bin/env python3
"""Test script to verify mail routing functionality."""

import asyncio
import json
from pathlib import Path
from datetime import datetime
import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mind_swarm.subspace.coordinator import MessageRouter
from mind_swarm.utils.logging import setup_logging, logger

async def test_mail_routing():
    """Test the mail routing system."""
    # Set up logging
    setup_logging(level="DEBUG")
    
    # Get subspace root from environment or use default
    subspace_root = Path(os.environ.get("SUBSPACE_ROOT", "/tmp/test_subspace"))
    logger.info(f"Using subspace root: {subspace_root}")
    
    # Create test directories
    agents_dir = subspace_root / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    
    # Create two test agents
    agent1_dir = agents_dir / "agent-001"
    agent2_dir = agents_dir / "agent-002"
    
    for agent_dir in [agent1_dir, agent2_dir]:
        agent_dir.mkdir(exist_ok=True)
        (agent_dir / "inbox").mkdir(exist_ok=True)
        (agent_dir / "outbox").mkdir(exist_ok=True)
    
    # Create a test message from agent-001 to agent-002
    test_message = {
        "from": "agent-001",
        "to": "agent-002",
        "type": "TEST",
        "content": "Hello agent-002, this is a test message!",
        "timestamp": datetime.now().isoformat()
    }
    
    # Write message to agent-001's outbox
    msg_file = agent1_dir / "outbox" / "test_message.msg"
    msg_file.write_text(json.dumps(test_message, indent=2))
    logger.info(f"Created test message in agent-001's outbox: {msg_file}")
    
    # Create router and test routing
    router = MessageRouter(subspace_root)
    
    logger.info("Running message routing...")
    routed_count = await router.route_outbox_messages()
    logger.info(f"Routed {routed_count} messages")
    
    # Check if message was delivered
    inbox_files = list((agent2_dir / "inbox").glob("*.msg"))
    if inbox_files:
        logger.info(f"Message successfully delivered to agent-002's inbox!")
        for inbox_file in inbox_files:
            content = inbox_file.read_text()
            logger.info(f"Message content: {content}")
    else:
        logger.error("Message was NOT delivered to agent-002's inbox!")
    
    # Check if message was moved to sent
    sent_files = list((agent1_dir / "outbox" / "sent").glob("*.msg"))
    if sent_files:
        logger.info("Message was moved to sent folder")
    else:
        logger.warning("Message was not moved to sent folder")
    
    # Test error handling - send to non-existent agent
    error_test_message = {
        "from": "agent-001",
        "to": "agent-999",  # Non-existent
        "type": "TEST",
        "content": "This should fail",
        "timestamp": datetime.now().isoformat()
    }
    
    error_msg_file = agent1_dir / "outbox" / "error_test.msg"
    error_msg_file.write_text(json.dumps(error_test_message, indent=2))
    
    logger.info("Testing error handling with non-existent recipient...")
    routed_count = await router.route_outbox_messages()
    logger.info(f"Routed {routed_count} messages")
    
    # Check for delivery error in agent-001's inbox
    error_msgs = list((agent1_dir / "inbox").glob("*.msg"))
    if error_msgs:
        logger.info("Delivery error message found in sender's inbox!")
        for error_msg in error_msgs:
            content = json.loads(error_msg.read_text())
            if content.get("type") == "DELIVERY_ERROR":
                logger.info(f"Error message: {content.get('error')}")

if __name__ == "__main__":
    asyncio.run(test_mail_routing())