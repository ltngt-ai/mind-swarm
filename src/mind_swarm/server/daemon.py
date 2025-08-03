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
        self._shutting_down = False
        
    def handle_signal(self):
        """Handle shutdown signals."""
        if not self._shutting_down:
            logger.info("Received shutdown signal")
            self._shutdown_event.set()
        else:
            logger.debug("Ignoring duplicate shutdown signal")
    
    async def run(self):
        """Run the server daemon."""
        # Set up signal handlers using asyncio
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self.handle_signal)
        
        # Create PID file
        pid_file = Path("/tmp/mind-swarm-server.pid")
        pid_file.write_text(str(os.getpid()))
        
        try:
            # Start the server in a separate task
            server_task = asyncio.create_task(self.server.run())
            
            # Wait for shutdown signal
            await self._shutdown_event.wait()
            
            # Mark that we're shutting down to prevent duplicate handling
            self._shutting_down = True
            
            logger.info("Shutdown signal received, stopping server gracefully...")
            
            # Remove signal handlers immediately to prevent re-entry
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                try:
                    loop.remove_signal_handler(sig)
                except Exception:
                    pass
            
            # Call the server's shutdown method to properly close everything
            try:
                await self.server.shutdown()
                logger.info("Server shutdown complete")
            except Exception as e:
                logger.error(f"Error during server shutdown: {e}")
            
            # Stop the uvicorn server properly
            if hasattr(self.server, 'server') and self.server.server:
                logger.info("Shutting down uvicorn server...")
                # Set should_exit to stop the server
                self.server.server.should_exit = True
                # Force close all connections
                self.server.server.force_exit = True
            
            # Cancel the server task
            server_task.cancel()
            try:
                await asyncio.wait_for(server_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                logger.info("Server task cancelled/timed out")
            except Exception as e:
                logger.error(f"Error cancelling server task: {e}")
                    
        finally:
            # Remove signal handlers
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.remove_signal_handler(sig)
            
            # Clean up PID file
            if pid_file.exists():
                pid_file.unlink()
            
            logger.info("Server daemon exiting")
            # Force exit to ensure the process terminates
            import sys
            sys.exit(0)


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