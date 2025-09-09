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
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8888):
        self.host = host
        self.port = port
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
        
        # Define PID file path with port number
        pid_file = Path(f"/tmp/mind-swarm-server-{self.port}.pid")
        
        try:
            # Start the server in a separate task
            # This will fail early if there are initialization problems (like missing rootfs)
            server_task = asyncio.create_task(self.server.run())
            shutdown_waiter = asyncio.create_task(self._shutdown_event.wait())

            # Race: either the server exits (unexpected) or we get a shutdown signal
            done, pending = await asyncio.wait(
                {server_task, shutdown_waiter}, return_when=asyncio.FIRST_COMPLETED
            )

            if server_task in done and not shutdown_waiter.done():
                # Server stopped unexpectedly during startup/runtime
                exc = server_task.exception()
                if exc:
                    logger.error(f"Server crashed during startup/runtime: {exc}", exc_info=True)
                else:
                    logger.error("Server stopped unexpectedly with no exception. Check uvicorn logs and port conflicts.")
                # Propagate to finally for cleanup
                return

            # Only create PID file after successful startup (we received a shutdown signal later)
            try:
                pid_file.write_text(str(os.getpid()))
                logger.debug(f"Created PID file: {pid_file}")
            except Exception:
                # Best-effort; not fatal under systemd
                pass
            
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
                import shutil
                import subprocess
                
                pkill_path = shutil.which('pkill')
                pgrep_path = shutil.which('pgrep')

                if pkill_path:
                    # Try direct kill of bwrap processes
                    subprocess.run([pkill_path, '-9', 'bwrap'], capture_output=True, text=True, check=False)
                    # Try killing by command match as a backstop
                    subprocess.run([pkill_path, '-9', '-f', 'bwrap'], capture_output=True, text=True, check=False)
                    # If pgrep is available, try killing children of any bwrap PIDs
                    if pgrep_path:
                        subprocess.run(f"{pkill_path} -9 -P $({pgrep_path} bwrap)", shell=True,
                                       capture_output=True, text=True, check=False)
                else:
                    # Fallback: manually scan /proc for bwrap processes and SIGKILL them
                    import os
                    import signal as _signal
                    killed = 0
                    for entry in os.listdir('/proc'):
                        if not entry.isdigit():
                            continue
                        pid = int(entry)
                        cmdline_path = f"/proc/{pid}/cmdline"
                        comm_path = f"/proc/{pid}/comm"
                        try:
                            found = False
                            if os.path.exists(cmdline_path):
                                with open(cmdline_path, 'rb') as f:
                                    data = f.read().replace(b'\x00', b' ').decode(errors='ignore')
                                    if 'bwrap' in data:
                                        found = True
                            if not found and os.path.exists(comm_path):
                                with open(comm_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    if 'bwrap' in f.read():
                                        found = True
                            if found:
                                os.kill(pid, _signal.SIGKILL)
                                killed += 1
                        except ProcessLookupError:
                            pass
                        except PermissionError:
                            # Skip processes we cannot access
                            continue
                        except Exception:
                            # Keep cleanup best-effort; do not fail shutdown
                            continue
                    if killed:
                        logger.info(f"Killed {killed} bwrap-related process(es) via /proc scan")
            except Exception as e:
                # Best-effort cleanup; log and continue without raising
                logger.warning(f"Non-fatal issue during bwrap cleanup: {e}")
            
            # Stop the uvicorn server properly
            if hasattr(self.server, 'server') and self.server.server:
                logger.info("Shutting down uvicorn server...")
                # Set should_exit to stop the server
                self.server.server.should_exit = True
                # Force close all connections
                self.server.server.force_exit = True
            
            # Cancel the server task
            if not server_task.done():
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
    parser.add_argument("--host", default="0.0.0.0", help="Server host address (0.0.0.0 for network access)")
    # Use port from env if available, otherwise default to 8888
    default_port = int(os.environ.get("MIND_SWARM_PORT", 8888))
    parser.add_argument("--port", type=int, default=default_port, help="Server port")
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
