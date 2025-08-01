#!/usr/bin/env python3
"""Mind-Swarm server daemon.

This runs as a standalone process providing the API for CLI clients to connect to.
"""

import asyncio
import signal
import sys
import os
from pathlib import Path
import argparse

from mind_swarm.server.api import MindSwarmServer
from mind_swarm.utils.logging import setup_logging, logger
from mind_swarm.core.config import settings


class ServerDaemon:
    """Server daemon manager."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8888):
        self.server = MindSwarmServer(host, port)
        self._shutdown_event = asyncio.Event()
        
    def handle_signal(self, sig, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {sig}")
        self._shutdown_event.set()
    
    async def run(self):
        """Run the server daemon."""
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)
        
        # Create PID file
        pid_file = Path("/tmp/mind-swarm-server.pid")
        pid_file.write_text(str(os.getpid()))
        
        try:
            # Run server until shutdown
            server_task = asyncio.create_task(self.server.run())
            shutdown_task = asyncio.create_task(self._shutdown_event.wait())
            
            # Wait for either server error or shutdown signal
            done, pending = await asyncio.wait(
                [server_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        finally:
            # Clean up PID file
            if pid_file.exists():
                pid_file.unlink()


def main():
    """Main entry point for server daemon."""
    parser = argparse.ArgumentParser(description="Mind-Swarm Server Daemon")
    parser.add_argument("--host", default="127.0.0.1", help="Server host address")
    parser.add_argument("--port", type=int, default=8888, help="Server port")
    # Default log file in project root
    project_root = Path(__file__).parent.parent.parent.parent
    default_log = project_root / "mind-swarm.log"
    parser.add_argument("--log-file", default=str(default_log), help="Log file path")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Clear the log file when starting fresh
    log_path = Path(args.log_file)
    if log_path.exists():
        log_path.write_text("")  # Clear the file
    
    # Set up logging
    level = "DEBUG" if args.debug else "INFO"
    setup_logging(level=level, log_file=log_path)
    
    logger.info(f"Starting Mind-Swarm server daemon on {args.host}:{args.port}")
    logger.info(f"Logging to: {args.log_file}")
    
    # Run the daemon
    daemon = ServerDaemon(args.host, args.port)
    
    try:
        import os
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        logger.info("Server daemon interrupted")
    except Exception as e:
        logger.error(f"Server daemon error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()