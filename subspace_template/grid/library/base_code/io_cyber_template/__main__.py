"""Main entry point for I/O Gateway Cybers."""

import asyncio
import os
import sys
import logging

# Set up logging - follow the same pattern as general Cybers
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("cyber")

from .io_mind import IOCyberMind


async def main():
    """Main entry point for I/O Cyber."""
    # Verify we're in a sandbox - same as general Cybers
    if not os.environ.get("CYBER_NAME"):
        print("ERROR: This must be run inside a Mind-Swarm sandbox")
        sys.exit(1)
    
    logger.info("I/O Gateway Cyber starting...")
    
    try:
        # Create and run the I/O Cyber mind
        mind = IOCyberMind()
        await mind.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Cyber interrupted")
    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        sys.exit(1)