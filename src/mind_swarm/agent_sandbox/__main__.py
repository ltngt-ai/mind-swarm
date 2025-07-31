#!/usr/bin/env python3
"""Agent entry point - this is what runs when the agent starts."""

import asyncio
import os
import sys
import logging

# Set up logging - only to stdout/stderr which will be captured by subspace
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Only stdout, no file handler
    ]
)
logger = logging.getLogger("agent")

from .mind import AgentMind


async def main():
    """Main entry point for the agent."""
    # Verify we're in a sandbox
    if not os.environ.get("AGENT_ID"):
        print("ERROR: This must be run inside a Mind-Swarm sandbox")
        sys.exit(1)
    
    logger.info("Agent starting...")
    
    try:
        # Create and run the agent mind
        mind = AgentMind()
        await mind.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Agent interrupted")
    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        sys.exit(1)