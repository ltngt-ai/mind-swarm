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

# Load environment variables from .env file if it exists BEFORE any imports
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)  # Override to ensure we get the latest values
except ImportError:
    # dotenv not installed, try manual loading
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip()
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    os.environ[key.strip()] = value

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
        
        # Define PID file path
        pid_file = Path("/tmp/mind-swarm-server.pid")
        
        try:
            # Start the server in a separate task
            # This will fail early if there are initialization problems (like missing rootfs)
            server_task = asyncio.create_task(self.server.run())
            
            # Give the server a moment to initialize and detect any startup failures
            await asyncio.sleep(1.0)
            
            # Check if the server task failed immediately
            if server_task.done():
                # Server failed to start, get the exception
                exc = server_task.exception()
                if exc:
                    logger.error(f"Server failed to start: {exc}")
                    raise exc
            
            # Only create PID file after successful startup
            pid_file.write_text(str(os.getpid()))
            logger.debug(f"Created PID file: {pid_file}")
            
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
            
            # Kill any remaining bwrap processes
            logger.info("Cleaning up any remaining bwrap processes...")
            try:
                import subprocess
                
                # Strategy 1: Kill all bwrap processes - this works from command line
                result = subprocess.run(['pkill', '-9', 'bwrap'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info("Successfully killed bwrap processes with pkill")
                
                # Strategy 2: Kill all processes that have bwrap as parent
                # This catches any lingering child processes
                result2 = subprocess.run(['pkill', '-9', '-P', '$(pgrep bwrap)'], 
                                       shell=True, capture_output=True, text=True)
                if result2.returncode == 0:
                    logger.info("Killed child processes of bwrap")
                
                # Strategy 3: Final backstop - kill anything with bwrap in the command line
                # This catches bwrap processes that might have been missed
                result3 = subprocess.run(['pkill', '-9', '-f', 'bwrap'], 
                                       capture_output=True, text=True)
                if result3.returncode == 0:
                    logger.info("Killed remaining processes with bwrap in command")
                
                # Strategy 4: Nuclear option - killall
                subprocess.run(['killall', '-9', 'bwrap'], 
                             capture_output=True, text=True, check=False)
                
            except Exception as e:
                logger.error(f"Error killing bwrap processes: {e}")
            
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
    parser.add_argument("--llm-debug", action="store_true", help="Enable LLM API call logging")
    
    args = parser.parse_args()
    
    # Set up logging - clear log on startup
    log_path = Path(args.log_file)
    level = "DEBUG" if args.debug else "INFO"
    setup_logging(level=level, log_file=log_path, clear_log=True)
    
    # Set LLM debug flag in environment for DSPy config to pick up
    if args.llm_debug:
        os.environ["MIND_SWARM_LLM_DEBUG"] = "true"
        os.environ["MIND_SWARM_LOG_FILE"] = str(log_path)
        llm_log_path = log_path.parent / "mind-swarm-llm.log"
        # Clear the LLM log file on startup
        if llm_log_path.exists():
            llm_log_path.write_text("")
            logger.info(f"Cleared LLM debug log: {llm_log_path}")
        logger.info(f"LLM API call logging enabled to: {llm_log_path}")
    
    logger.info(f"Starting Mind-Swarm server daemon on {args.host}:{args.port}")
    logger.info(f"Logging to: {args.log_file}")
    
    # Log API key status
    if os.getenv("CEREBRAS_API_KEY"):
        key_preview = os.getenv("CEREBRAS_API_KEY")[:10] + "..."
        logger.info(f"CEREBRAS_API_KEY loaded: {key_preview}")
    else:
        logger.warning("CEREBRAS_API_KEY not found in environment - Cerebras models won't work")
    
    # Run the daemon
    daemon = ServerDaemon(args.host, args.port)
    
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        logger.info("Server daemon interrupted")
    except Exception as e:
        logger.error(f"Server daemon error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()