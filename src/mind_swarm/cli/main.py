"""Main CLI application for Mind-Swarm."""

import asyncio
import signal
import subprocess
import sys
import time
import shlex
from pathlib import Path
from typing import Optional, Dict, Any

import typer
from rich.console import Console
from rich.table import Table

from mind_swarm.core.config import settings
from mind_swarm.client import MindSwarmClient
from mind_swarm.utils.logging import logger, setup_logging

app = typer.Typer(name="mind-swarm", help="Mind-Swarm: Multi-agent AI system")
console = Console()

# Import subcommands
from mind_swarm.cli.check_llm import app as check_llm_app
app.add_typer(check_llm_app, name="check-llm", help="Check local LLM server status")

# Import logs command
from mind_swarm.cli.commands.logs import logs
app.command()(logs)


class MindSwarmCLI:
    """Main CLI application class."""
    
    def __init__(self):
        self.client = MindSwarmClient()
        self._running = False
        self._ws_events = []
        self.coordinator = None  # Only used for local mode
    
    async def handle_ws_event(self, event: Dict[str, Any]):
        """Handle WebSocket events from server."""
        # Store event for later display
        self._ws_events.append(event)
        
        # Display certain events immediately
        event_type = event.get("type", "")
        if event_type == "agent_created":
            console.print(f"[green]Agent created: {event.get('agent_name')}[/green]")
        elif event_type == "agent_terminated":
            console.print(f"[yellow]Agent terminated: {event.get('agent_name')}[/yellow]")
        elif event_type == "agent_state_change":
            console.print(f"[blue]Agent {event.get('agent_name')} state: {event.get('new_state')}[/blue]")
    
    async def check_server(self) -> bool:
        """Check if the server is running and accessible."""
        try:
            if await self.client.check_server():
                return True
            else:
                console.print("[bold red]Cannot connect to Mind-Swarm server![/bold red]")
                console.print("Start the server with: [cyan]mind-swarm server start[/cyan]")
                console.print("or: [cyan]./run.sh server[/cyan]")
                return False
        except Exception as e:
            console.print(f"[bold red]Cannot connect to Mind-Swarm server: {e}[/bold red]")
            console.print("Start the server with: [cyan]mind-swarm server start[/cyan]")
            console.print("or: [cyan]./run.sh server[/cyan]")
            return False
    
    async def initialize(self):
        """Initialize the Mind-Swarm system."""
        console.print("[bold green]Initializing Mind-Swarm...[/bold green]")
        
        # Initialize subspace coordinator
        self.coordinator = SubspaceCoordinator()
        
        # Check bubblewrap availability
        if not await self.coordinator.subspace.check_bubblewrap():
            console.print("[bold red]Error: Bubblewrap (bwrap) is required but not found.[/bold red]")
            console.print("Please install it: [cyan]sudo apt install bubblewrap[/cyan]")
            raise SystemExit(1)
        
        await self.coordinator.start()
        
        console.print("[bold green]Mind-Swarm initialized successfully![/bold green]")
    
    async def create_initial_agents(self, count: int = 3):
        """Create initial set of agents."""
        console.print(f"[cyan]Creating {count} initial agents...[/cyan]")
        
        for i in range(count):
            try:
                agent_id = await self.client.create_agent(
                    name=f"Explorer-{i+1}",
                )
                console.print(f"  ✓ Created Explorer-{i+1} ({agent_id})")
            except Exception as e:
                console.print(f"  ✗ Failed to create agent: {e}", style="red")
    
    async def show_status(self):
        """Display current system status."""
        try:
            # Get agent states from server
            states = await self.client.get_agent_states()
            
            # Create status table
            table = Table(title="Mind-Swarm Status")
            table.add_column("Agent Name", style="cyan")
            table.add_column("Alive", style="green")
            table.add_column("State")
            table.add_column("Uptime", justify="right")
            table.add_column("Inbox", justify="right")
            table.add_column("Outbox", justify="right")
            
            for agent_name, info in states.items():
                table.add_row(
                    agent_name,
                    "✓" if info.get("alive", False) else "✗",
                    info.get("state", "UNKNOWN"),
                    f"{info.get('uptime', 0):.1f}s",
                    str(info.get("inbox_count", 0)),
                    str(info.get("outbox_count", 0)),
                )
            
            console.print(table)
            
            # Show shared questions
            questions = await self.client.get_plaza_questions()
            if questions:
                console.print(f"\n[bold]Plaza Questions:[/bold] {len(questions)}")
                
        except Exception as e:
            console.print(f"[red]Error getting status: {e}[/red]")
    
    def show_presets(self):
        """Display available AI presets."""
        from mind_swarm.ai.presets import preset_manager
        
        table = Table(title="Available AI Presets")
        table.add_column("Name", style="cyan")
        table.add_column("Provider", style="yellow")
        table.add_column("Model", style="green")
        table.add_column("Temperature")
        table.add_column("Max Tokens", justify="right")
        table.add_column("Current", style="magenta")
        
        # Get current presets from settings
        current_local = settings.ai_models.local_preset
        current_premium = settings.ai_models.premium_preset
        
        for preset_name in preset_manager.list_presets():
            preset = preset_manager.get_preset(preset_name)
            if preset:
                current = ""
                if preset_name == current_local:
                    current = "Local"
                elif preset_name == current_premium:
                    current = "Premium"
                
                table.add_row(
                    preset.name,
                    preset.provider,
                    preset.model,
                    str(preset.temperature),
                    str(preset.max_tokens),
                    current,
                )
        
        console.print(table)
    
    async def run_interactive(self):
        """Run interactive mode."""
        self._running = True
        
        console.print("[bold]Mind-Swarm Interactive Mode[/bold]")
        console.print("Commands:")
        console.print("  [cyan]status[/cyan] - Show agent status")
        console.print("  [cyan]create [--io] [name][/cyan] - Create a new AI agent")
        console.print("  [cyan]terminate <name>[/cyan] - Terminate an agent")
        console.print("  [cyan]command <name> <command> [params][/cyan] - Send command to agent")
        console.print("  [cyan]message <name> <text>[/cyan] - Send message to agent")
        console.print("  [cyan]question <text>[/cyan] - Create a shared question")
        console.print("  [cyan]presets[/cyan] - List available AI presets")
        console.print("  [cyan]dev register <name> [full_name] [email][/cyan] - Register developer")
        console.print("  [cyan]dev current [name][/cyan] - Show/set current developer")
        console.print("  [cyan]dev list[/cyan] - List registered developers")
        console.print("  [cyan]mailbox[/cyan] - Check developer mailbox")
        console.print("  [cyan]quit[/cyan] - Exit the system")
        console.print("\n[dim]Tip: Use 'quit' or Ctrl+C to exit[/dim]")
        
        while self._running:
            try:
                # Show prompt and get command
                command = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: console.input("[bold]mind-swarm>[/bold] "),
                )
                
                if not command:
                    continue
                
                # Use shlex to properly handle quoted strings
                try:
                    parts = shlex.split(command.strip())
                except ValueError as e:
                    console.print(f"Invalid command syntax: {e}", style="red")
                    continue
                    
                if not parts:
                    continue
                
                cmd = parts[0].lower()
                
                if cmd == "quit" or cmd == "exit":
                    self._running = False
                
                elif cmd == "status":
                    await self.show_status()
                
                elif cmd == "create":
                    # Parse create options: create [--io] [name]
                    is_io_agent = False
                    agent_name = None
                    
                    for i, part in enumerate(parts[1:], 1):
                        if part == "--io":
                            is_io_agent = True
                        else:
                            agent_name = part
                    
                    # Determine agent type
                    agent_type = "io_gateway" if is_io_agent else "general"
                    
                    agent_name_result = await self.client.create_agent(
                        name=agent_name,
                        agent_type=agent_type,
                    )
                    type_str = "I/O Gateway" if is_io_agent else "General"
                    console.print(f"Created {agent_name_result} [{type_str}]")
                
                elif cmd == "terminate" and len(parts) > 1:
                    agent_name = parts[1]
                    await self.client.terminate_agent(agent_name)
                    console.print(f"Terminated agent {agent_name}")
                
                elif cmd == "command" and len(parts) >= 3:
                    # command <agent_name> <command> [params]
                    agent_name = parts[1]
                    command = parts[2]
                    params = {"input": " ".join(parts[3:])} if len(parts) > 3 else {}
                    
                    await self.client.send_command(agent_name, command, params)
                    console.print(f"Command '{command}' sent to {agent_name}")
                
                elif cmd == "message" and len(parts) >= 3:
                    # message <agent_name> <text>
                    agent_name = parts[1]
                    message_text = " ".join(parts[2:])
                    
                    await self.client.send_message(agent_name, message_text)
                    console.print(f"Message sent to {agent_name}")
                
                elif cmd == "question" and len(parts) > 1:
                    # Post a question to the Plaza
                    question_text = " ".join(parts[1:])
                    q_id = await self.client.create_plaza_question(question_text)
                    console.print(f"Posted to Plaza: {q_id}")
                
                elif cmd == "presets":
                    self.show_presets()
                
                elif cmd == "dev" and len(parts) > 1:
                    # Developer commands
                    subcmd = parts[1].lower()
                    
                    if subcmd == "register" and len(parts) >= 3:
                        # dev register <name> [full_name] [email]
                        name = parts[2]
                        full_name = parts[3] if len(parts) > 3 else None
                        email = parts[4] if len(parts) > 4 else None
                        
                        try:
                            agent_name = await self.client.register_developer(name, full_name, email)
                            console.print(f"[green]Registered developer {name} as {agent_name}[/green]")
                        except Exception as e:
                            console.print(f"[red]Failed to register developer: {e}[/red]")
                    
                    elif subcmd == "current":
                        if len(parts) > 2:
                            # Set current developer
                            name = parts[2]
                            try:
                                success = await self.client.set_current_developer(name)
                                if success:
                                    console.print(f"[green]Set current developer to {name}[/green]")
                                else:
                                    console.print(f"[red]Developer {name} not found[/red]")
                            except Exception as e:
                                console.print(f"[red]Failed to set developer: {e}[/red]")
                        else:
                            # Show current developer
                            try:
                                dev = await self.client.get_current_developer()
                                if dev:
                                    console.print(f"Current developer: {dev['agent_name']} ({dev.get('full_name', 'N/A')})")
                                else:
                                    console.print("No current developer set")
                            except Exception as e:
                                console.print(f"[red]Failed to get current developer: {e}[/red]")
                    
                    elif subcmd == "list":
                        # List all developers
                        try:
                            developers = await self.client.list_developers()
                            if developers:
                                table = Table(title="Registered Developers")
                                table.add_column("Username", style="cyan")
                                table.add_column("Agent Name", style="green")
                                table.add_column("Full Name")
                                table.add_column("Email")
                                table.add_column("Last Active")
                                
                                for name, info in developers.items():
                                    table.add_row(
                                        name,
                                        info["agent_name"],
                                        info.get("full_name", "N/A"),
                                        info.get("email", "N/A"),
                                        info.get("last_active", "N/A")[:19]  # Trim timestamp
                                    )
                                
                                console.print(table)
                            else:
                                console.print("No developers registered")
                        except Exception as e:
                            console.print(f"[red]Failed to list developers: {e}[/red]")
                    
                    else:
                        console.print(f"Unknown dev command: {subcmd}", style="red")
                
                elif cmd == "mailbox":
                    # Enhanced mailbox with options
                    if len(parts) > 1:
                        subcmd = parts[1].lower()
                        
                        if subcmd == "read" and len(parts) > 2:
                            # Mark message as read
                            try:
                                msg_index = int(parts[2]) - 1
                                success = await self.client.mark_message_read(msg_index)
                                if success:
                                    console.print(f"[green]Message {parts[2]} marked as read[/green]")
                                else:
                                    console.print(f"[red]Failed to mark message as read[/red]")
                            except ValueError:
                                console.print("[red]Invalid message number[/red]")
                            except Exception as e:
                                console.print(f"[red]Error: {e}[/red]")
                        
                        elif subcmd == "all":
                            # Show all messages including read ones
                            try:
                                messages = await self.client.check_mailbox(include_read=True)
                                if messages:
                                    unread = [m for m in messages if not m.get('_read', False)]
                                    read = [m for m in messages if m.get('_read', False)]
                                    
                                    console.print(f"[cyan]Mailbox ({len(unread)} unread, {len(read)} read):[/cyan]")
                                    
                                    for i, msg in enumerate(messages, 1):
                                        status = "[dim]" if msg.get('_read') else "[bold]"
                                        console.print(f"\n{status}Message {i}:{'' if msg.get('_read') else '[/bold]'}")
                                        console.print(f"  From: {msg.get('from', 'unknown')}")
                                        console.print(f"  Time: {msg.get('timestamp', 'unknown')[:19]}")
                                        
                                        if msg.get('type') == 'text':
                                            console.print(f"  Content: {msg.get('content', '')}")
                                        else:
                                            console.print(f"  Type: {msg.get('type', 'unknown')}")
                                else:
                                    console.print("No messages in mailbox")
                            except Exception as e:
                                console.print(f"[red]Failed to check mailbox: {e}[/red]")
                        
                        else:
                            console.print("Usage: mailbox [all|read <num>]")
                    
                    else:
                        # Show unread messages by default
                        try:
                            messages = await self.client.check_mailbox()
                            if messages:
                                console.print(f"[cyan]You have {len(messages)} unread messages:[/cyan]")
                                for i, msg in enumerate(messages, 1):
                                    console.print(f"\n[bold]Message {i}:[/bold]")
                                    console.print(f"  From: {msg.get('from', 'unknown')}")
                                    console.print(f"  Type: {msg.get('type', 'unknown')}")
                                    console.print(f"  Time: {msg.get('timestamp', 'unknown')[:19]}")
                                    
                                    if msg.get('type') == 'text':
                                        console.print(f"  Content: {msg.get('content', '')}")
                                    elif msg.get('type') == 'COMMAND':
                                        console.print(f"  Command: {msg.get('command', '')}")
                                        if msg.get('params'):
                                            console.print(f"  Params: {msg.get('params')}")
                                    else:
                                        console.print(f"  Data: {msg}")
                                
                                console.print("\n[dim]Use 'mailbox read <num>' to mark as read[/dim]")
                                console.print("[dim]Use 'mailbox all' to see all messages[/dim]")
                            else:
                                console.print("No unread messages")
                        except Exception as e:
                            console.print(f"[red]Failed to check mailbox: {e}[/red]")
                
                else:
                    console.print(f"Unknown command: {command}", style="red")
                
            except (EOFError, KeyboardInterrupt):
                # Handle Ctrl+C or Ctrl+D gracefully
                self._running = False
                console.print("\n[yellow]Exiting...[/yellow]")
                break
            except Exception as e:
                console.print(f"Error: {e}", style="red")
                logger.error(f"Command error: {e}", exc_info=True)
    
    async def shutdown(self):
        """Shutdown the system gracefully."""
        console.print("[yellow]Shutting down Mind-Swarm...[/yellow]")
        
        if self.coordinator:
            await self.coordinator.stop()
        
        console.print("[green]Mind-Swarm shutdown complete.[/green]")


@app.command()
def connect(
    create_agents: int = typer.Option(0, "--create", "-c", help="Number of agents to create on connect"),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", "-i/-n", help="Run in interactive mode"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug logging"),
):
    """Connect to running Mind-Swarm server."""
    # Set up logging
    level = "DEBUG" if debug else "INFO"
    setup_logging(level=level)
    
    # In interactive mode, remove console handlers for clean CLI
    if interactive and not debug:
        import logging
        # Remove console handlers from all loggers
        for logger_name in ['mind_swarm', 'httpx', 'websockets', 'uvicorn', '']:
            logger = logging.getLogger(logger_name)
            logger.handlers = [h for h in logger.handlers if not hasattr(h, 'stream')]
            # Set higher level to prevent propagation
            if logger_name:
                logger.setLevel(logging.WARNING)
    
    # Create CLI client
    cli = MindSwarmCLI()
    
    async def main():
        try:
            # Check if server is running
            if not await cli.check_server():
                return
            
            console.print("[green]Connected to Mind-Swarm server[/green]")
            
            # Connect WebSocket for real-time updates
            await cli.client.connect_websocket(cli.handle_ws_event)
            
            # Create initial agents if requested
            if create_agents > 0:
                await cli.create_initial_agents(create_agents)
            
            if interactive:
                await cli.run_interactive()
            else:
                # Just show status and exit
                await cli.show_status()
        
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            logger.error(f"Connection error: {e}", exc_info=True)
        finally:
            # Disconnect websocket if connected
            if cli.client._ws_connection:
                await cli.client.disconnect_websocket()
            
            await cli.shutdown()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # This catches any keyboard interrupt during asyncio.run
        console.print("\n[yellow]Exiting...[/yellow]")


@app.command()
def status():
    """Check system and server status."""
    console.print("[bold]Mind-Swarm Status Check[/bold]")
    
    # Check if server is running
    client = MindSwarmClient()
    if client.is_server_running():
        console.print("[green]✓ Server is running (PID file exists)[/green]")
        
        # Try to connect
        async def check():
            if await client.check_server():
                console.print("[green]✓ Server is responding[/green]")
                try:
                    status = await client.get_status()
                    console.print(f"  Agents: {len(status.agents)}")
                    console.print(f"  Plaza questions: {status.plaza_questions}")
                    console.print(f"  Server uptime: {status.server_uptime:.1f}s")
                    
                    # Show local LLM status if available
                    if hasattr(status, 'local_llm_status') and status.local_llm_status:
                        llm_status = status.local_llm_status
                        if llm_status.get('healthy'):
                            models = llm_status.get('models', [])
                            if models:
                                primary = llm_status.get('primary_model', 'unknown')
                                console.print(f"  [green]✓ Local LLM: {primary} at {llm_status.get('url')}[/green]")
                            else:
                                console.print(f"  [yellow]⚠ Local LLM: Running but no models loaded[/yellow]")
                        else:
                            console.print(f"  [red]✗ Local LLM: Not available[/red]")
                except Exception as e:
                    console.print(f"[red]✗ Failed to get status: {e}[/red]")
            else:
                console.print("[red]✗ Server not responding (may be starting up)[/red]")
        
        asyncio.run(check())
    else:
        console.print("[yellow]✗ Server is not running[/yellow]")
        console.print("Start with: [cyan]mind-swarm server start[/cyan]")
    
    # Check configuration
    console.print(f"\nSubspace root: {settings.subspace.root_path}")
    console.print(f"Max agents: {settings.subspace.max_agents}")
    console.print(f"Local AI preset: {settings.ai_models.local_preset}")
    console.print(f"Premium AI preset: {settings.ai_models.premium_preset}")
    
    # Check bubblewrap
    try:
        result = subprocess.run(["bwrap", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            console.print("\n[green]✓ Bubblewrap installed[/green]")
        else:
            console.print("\n[red]✗ Bubblewrap error[/red]")
    except FileNotFoundError:
        console.print("\n[red]✗ Bubblewrap not found[/red]")


@app.command()
def server(
    action: str = typer.Argument(..., help="Action: start, stop, restart, logs"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug logging"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Server host"),
    port: int = typer.Option(8888, "--port", "-p", help="Server port"),
):
    """Manage Mind-Swarm server."""
    pid_file = Path("/tmp/mind-swarm-server.pid")
    # Use project root for log file
    project_root = Path(__file__).parent.parent.parent.parent
    log_file = project_root / "mind-swarm.log"
    
    if action == "start":
        # Check if already running
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                # Check if process exists
                import os
                os.kill(pid, 0)
                console.print(f"[yellow]Server already running (PID: {pid})[/yellow]")
                return
            except (ValueError, ProcessLookupError):
                # Stale PID file
                pid_file.unlink()
        
        console.print(f"[cyan]Starting Mind-Swarm server on {host}:{port}...[/cyan]")
        
        # Clear log file on start
        if log_file.exists():
            log_file.unlink()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Start server in background
        cmd = [
            sys.executable, "-m", "mind_swarm.server.daemon",
            "--host", host,
            "--port", str(port),
            "--log-file", str(log_file),
        ]
        if debug:
            cmd.append("--debug")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        
        # Wait a moment for startup
        time.sleep(2)
        
        # Check if it started
        if process.poll() is None:
            console.print(f"[green]Server started (PID: {process.pid})[/green]")
            console.print(f"Logs: {log_file}")
        else:
            console.print("[red]Server failed to start[/red]")
            console.print(f"Check logs: {log_file}")
    
    elif action == "stop":
        if not pid_file.exists():
            console.print("[yellow]Server not running[/yellow]")
            return
        
        try:
            pid = int(pid_file.read_text().strip())
            import os
            os.kill(pid, signal.SIGTERM)
            console.print(f"[green]Sent shutdown signal to server (PID: {pid})[/green]")
            
            # Wait for shutdown (up to 60 seconds)
            for i in range(120):
                time.sleep(0.5)
                try:
                    os.kill(pid, 0)
                    # Show progress every 5 seconds
                    if i > 0 and i % 10 == 0:
                        console.print(f"[yellow]Waiting for graceful shutdown... ({i//2}s)[/yellow]")
                except ProcessLookupError:
                    console.print("[green]Server stopped gracefully[/green]")
                    return
            
            console.print("[red]Server still running after 60s, sending SIGKILL[/red]")
            os.kill(pid, signal.SIGKILL)
            
        except (ValueError, ProcessLookupError):
            console.print("[yellow]Server not running (stale PID file)[/yellow]")
            pid_file.unlink()
    
    elif action == "restart":
        console.print("[cyan]Restarting server...[/cyan]")
        # First stop
        server("stop", debug=False, host=host, port=port)
        time.sleep(1)
        # Then start
        server("start", debug=debug, host=host, port=port)
    
    elif action == "logs":
        if not log_file.exists():
            console.print("[yellow]No log file found[/yellow]")
            return
        
        # Tail the log file with --follow=name to handle truncation
        console.print(f"[cyan]Tailing {log_file}...[/cyan]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")
        
        try:
            # Use --follow=name to handle file truncation/rotation
            # and --retry to keep trying if file is temporarily unavailable
            subprocess.run(["tail", "-f", "--follow=name", "--retry", str(log_file)])
        except subprocess.CalledProcessError:
            # Fallback to simple tail -f if options not supported
            subprocess.run(["tail", "-f", str(log_file)])
        except KeyboardInterrupt:
            pass
    
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Valid actions: start, stop, restart, logs")


if __name__ == "__main__":
    app()