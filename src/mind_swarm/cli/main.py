"""Main CLI application for Mind-Swarm."""

import asyncio
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

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


class MindSwarmCLI:
    """Main CLI application class."""
    
    def __init__(self):
        self.client = MindSwarmClient()
        self._running = False
        self._ws_events = []
    
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
    
    async def spawn_initial_agents(self, count: int = 3):
        """Spawn initial set of agents."""
        console.print(f"[cyan]Spawning {count} initial agents...[/cyan]")
        
        for i in range(count):
            try:
                # First agent uses premium AI, others use local
                use_premium = (i == 0)
                agent_id = await self.coordinator.spawn_agent(
                    name=f"Explorer-{i+1}",
                    use_premium=use_premium,
                )
                ai_type = "Premium" if use_premium else "Local"
                console.print(f"  ✓ Spawned Explorer-{i+1} ({agent_id}) [AI: {ai_type}]")
            except Exception as e:
                console.print(f"  ✗ Failed to spawn agent: {e}", style="red")
    
    async def show_status(self):
        """Display current system status."""
        if not self.coordinator:
            console.print("[red]System not initialized[/red]")
            return
        
        # Create status table
        table = Table(title="Mind-Swarm Status")
        table.add_column("Agent ID", style="cyan")
        table.add_column("Alive", style="green")
        table.add_column("State")
        table.add_column("Uptime", justify="right")
        table.add_column("Inbox", justify="right")
        table.add_column("Outbox", justify="right")
        
        states = await self.coordinator.get_agent_states()
        for agent_id, info in states.items():
            table.add_row(
                agent_id,
                "✓" if info.get("alive", False) else "✗",
                info.get("state", "UNKNOWN"),
                f"{info.get('uptime', 0):.1f}s",
                str(info.get("inbox_count", 0)),
                str(info.get("outbox_count", 0)),
            )
        
        console.print(table)
        
        # Show shared questions
        questions = self.coordinator.get_plaza_questions()
        if questions:
            console.print(f"\n[bold]Plaza Questions:[/bold] {len(questions)}")
    
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
        
        # Set up signal handlers
        def signal_handler(sig, frame):
            self._running = False
            console.print("\n[yellow]Shutting down...[/yellow]")
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        console.print("[bold]Mind-Swarm Interactive Mode[/bold]")
        console.print("Commands:")
        console.print("  [cyan]status[/cyan] - Show agent status")
        console.print("  [cyan]spawn [--premium] [name][/cyan] - Spawn an AI agent")
        console.print("  [cyan]terminate <id>[/cyan] - Terminate an agent")
        console.print("  [cyan]command <agent_id> <command> [params][/cyan] - Send command to agent")
        console.print("  [cyan]question <text>[/cyan] - Create a shared question")
        console.print("  [cyan]presets[/cyan] - List available AI presets")
        console.print("  [cyan]quit[/cyan] - Exit the system")
        
        while self._running:
            try:
                # Show prompt and get command
                command = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: console.input("[bold]mind-swarm>[/bold] "),
                )
                
                if not command:
                    continue
                
                parts = command.strip().split()
                if not parts:
                    continue
                
                cmd = parts[0].lower()
                
                if cmd == "quit" or cmd == "exit":
                    self._running = False
                
                elif cmd == "status":
                    await self.show_status()
                
                elif cmd == "spawn":
                    # Parse spawn options: spawn [--premium] [name]
                    use_premium = False
                    agent_name = None
                    
                    for i, part in enumerate(parts[1:], 1):
                        if part == "--premium":
                            use_premium = True
                        else:
                            agent_name = part
                    
                    agent_id = await self.client.spawn_agent(
                        name=agent_name,
                        use_premium=use_premium,
                    )
                    ai_type = "Premium" if use_premium else "Local"
                    console.print(f"Spawned {agent_name or 'Agent'} ({agent_id}) [AI: {ai_type}]")
                
                elif cmd == "terminate" and len(parts) > 1:
                    agent_id = parts[1]
                    await self.client.terminate_agent(agent_id)
                    console.print(f"Terminated agent {agent_id}")
                
                elif cmd == "command" and len(parts) >= 3:
                    # command <agent_id> <command> [params]
                    agent_id = parts[1]
                    command = parts[2]
                    params = {"input": " ".join(parts[3:])} if len(parts) > 3 else {}
                    
                    await self.client.send_command(agent_id, command, params)
                    console.print(f"Command '{command}' sent to {agent_id}")
                
                elif cmd == "question" and len(parts) > 1:
                    # Post a question to the Plaza
                    question_text = " ".join(parts[1:])
                    q_id = await self.client.create_plaza_question(question_text)
                    console.print(f"Posted to Plaza: {q_id}")
                
                elif cmd == "presets":
                    self.show_presets()
                
                else:
                    console.print(f"Unknown command: {command}", style="red")
                
            except EOFError:
                self._running = False
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
    spawn_agents: int = typer.Option(0, "--spawn", "-s", help="Number of agents to spawn on connect"),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", "-i/-n", help="Run in interactive mode"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug logging"),
):
    """Connect to running Mind-Swarm server."""
    # Set up logging
    level = "DEBUG" if debug else "INFO"
    setup_logging(level=level)
    
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
            
            # Spawn initial agents if requested
            if spawn_agents > 0:
                await cli.spawn_initial_agents(spawn_agents)
            
            if interactive:
                await cli.run_interactive()
            else:
                # Just show status and exit
                await cli.show_status()
        
        except KeyboardInterrupt:
            pass
        finally:
            await cli.shutdown()
    
    asyncio.run(main())


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
    console.print(f"Local model: {settings.ai_models.local_model}")
    console.print(f"Premium model: {settings.ai_models.premium_model}")
    
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
            
            # Wait for shutdown
            for _ in range(10):
                time.sleep(0.5)
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    console.print("[green]Server stopped[/green]")
                    return
            
            console.print("[yellow]Server still running, sending SIGKILL[/yellow]")
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
        
        # Tail the log file
        console.print(f"[cyan]Tailing {log_file}...[/cyan]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")
        
        try:
            subprocess.run(["tail", "-f", str(log_file)])
        except KeyboardInterrupt:
            pass
    
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Valid actions: start, stop, restart, logs")


if __name__ == "__main__":
    app()