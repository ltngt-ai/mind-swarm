"""Main entry point for I/O Gateway agents."""

import asyncio
import os
import sys
import logging

# Set up logging - follow the same pattern as general agents
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("agent")

from .io_mind import IOAgentMind


async def main():
    """Main entry point for I/O agent."""
    # Verify we're in a sandbox - same as general agents
    if not os.environ.get("AGENT_NAME"):
        print("ERROR: This must be run inside a Mind-Swarm sandbox")
        sys.exit(1)
    
    logger.info("I/O Gateway Agent starting...")
    
    try:
        # Create and run the I/O agent mind
        mind = IOAgentMind()
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