"""Main entry point for I/O Gateway agents."""

import asyncio
import logging
import os
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("agent.io")

# Import the I/O cognitive loop
from io_agent_template.io_cognitive_loop import IOCognitiveLoop


async def main():
    """Main entry point for I/O agent."""
    agent_id = os.environ.get("AGENT_NAME", "io-agent")
    agent_type = os.environ.get("AGENT_TYPE", "io_gateway")
    home = Path("/home")
    
    logger.info(f"I/O Gateway Agent starting: {agent_id}")
    logger.info(f"Agent type: {agent_type}")
    
    # Verify we have the special body files
    network_file = home / "network"
    user_io_file = home / "user_io"
    
    if network_file.exists():
        logger.info("Network body file available")
    else:
        logger.warning("Network body file not found!")
    
    if user_io_file.exists():
        logger.info("User I/O body file available")
    else:
        logger.warning("User I/O body file not found!")
    
    # Create and run the cognitive loop
    try:
        loop = IOCognitiveLoop(agent_id, home)
        logger.info("Starting I/O cognitive loop...")
        await loop.run()
    except KeyboardInterrupt:
        logger.info("I/O agent interrupted by user")
    except Exception as e:
        logger.error(f"I/O agent error: {e}", exc_info=True)
    finally:
        logger.info("I/O agent shutting down")


if __name__ == "__main__":
    asyncio.run(main())