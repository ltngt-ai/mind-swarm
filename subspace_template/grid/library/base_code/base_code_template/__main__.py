#!/usr/bin/env python3
"""Agent entry point - this is what runs when the agent starts."""

import asyncio
import os
import sys
import logging
import signal

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

# Global variable for the mind instance
mind_instance = None


async def main():
    """Main entry point for the agent."""
    global mind_instance
    
    # Verify we're in a sandbox
    if not os.environ.get("AGENT_NAME"):
        print("ERROR: This must be run inside a Mind-Swarm sandbox")
        sys.exit(1)
    
    logger.info("Agent starting...")
    
    try:
        # Create and run the agent mind
        mind_instance = AgentMind()
        await mind_instance.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


def run_with_signals():
    """Run the agent with proper signal handling."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Set up signal handler
    def signal_handler():
        logger.info("Received shutdown signal")
        if mind_instance:
            mind_instance.request_stop()
    
    # Add signal handler for SIGTERM
    if sys.platform != "win32":  # Signal handlers don't work the same on Windows
        loop.add_signal_handler(signal.SIGTERM, signal_handler)
    
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Agent interrupted")
    finally:
        if sys.platform != "win32":
            loop.remove_signal_handler(signal.SIGTERM)
        loop.close()


if __name__ == "__main__":
    try:
        run_with_signals()
    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        sys.exit(1)