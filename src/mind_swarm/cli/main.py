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

app = typer.Typer(name="mind-swarm", help="Mind-Swarm: Multi-Cyber AI system")
console = Console()

# Import subcommands
from mind_swarm.cli.check_llm import app as check_llm_app
app.add_typer(check_llm_app, name="check-llm", help="Check local LLM server status")

# Import logs command
from mind_swarm.cli.commands.logs import logs
app.command()(logs)

# Import models command
from mind_swarm.cli.commands.models import app as models_app
app.add_typer(models_app, name="models", help="Manage AI models")

# Import sync-openrouter command
from mind_swarm.cli.commands.sync_openrouter import app as sync_openrouter_app
app.add_typer(sync_openrouter_app, name="sync-openrouter", help="Sync models from OpenRouter API")


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
            console.print(f"[green]Cyber created: {event.get('cyber_name')}[/green]")
        elif event_type == "agent_terminated":
            console.print(f"[yellow]Cyber terminated: {event.get('cyber_name')}[/yellow]")
        elif event_type == "agent_state_change":
            console.print(f"[blue]Cyber {event.get('cyber_name')} state: {event.get('new_state')}[/blue]")
    
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
        """Create initial set of Cybers."""
        console.print(f"[cyan]Creating {count} initial Cybers...[/cyan]")
        
        for i in range(count):
            try:
                cyber_id = await self.client.create_agent(
                    name=f"Explorer-{i+1}",
                )
                console.print(f"  ✓ Created Explorer-{i+1} ({cyber_id})")
            except Exception as e:
                console.print(f"  ✗ Failed to create Cyber: {e}", style="red")
    
    async def show_status(self):
        """Display current system status."""
        try:
            # Get Cyber states from server
            states = await self.client.get_cyber_states()
            
            # Create status table
            table = Table(title="Mind-Swarm Status")
            table.add_column("Cyber Name", style="cyan")
            table.add_column("Alive", style="green")
            table.add_column("State")
            table.add_column("Uptime", justify="right")
            table.add_column("Inbox", justify="right")
            table.add_column("Outbox", justify="right")
            
            for cyber_name, info in states.items():
                table.add_row(
                    cyber_name,
                    "✓" if info.get("alive", False) else "✗",
                    info.get("state", "UNKNOWN"),
                    f"{info.get('uptime', 0):.1f}s",
                    str(info.get("inbox_count", 0)),
                    str(info.get("outbox_count", 0)),
                )
            
            console.print(table)
            
            # Show shared questions
            questions = await self.client.get_community_questions()
            if questions:
                console.print(f"\n[bold]Community Questions:[/bold] {len(questions)}")
                
        except Exception as e:
            console.print(f"[red]Error getting status: {e}[/red]")
    
    def promote_model(self, model_id: str, priority: str, duration: Optional[float] = None):
        """Promote a model to a different priority tier."""
        from mind_swarm.ai.model_pool import model_pool, Priority
        
        try:
            # Parse priority
            priority_enum = Priority(priority.lower())
            
            # Promote the model
            model_pool.promote_model(model_id, priority_enum, duration)
            
            if duration:
                console.print(f"[green]✓ Model {model_id} promoted to {priority} for {duration} hours[/green]")
            else:
                console.print(f"[green]✓ Model {model_id} permanently promoted to {priority}[/green]")
                
        except ValueError as e:
            console.print(f"[red]✗ Error: {e}[/red]")
            console.print("Valid priorities: primary, normal, fallback")
        except Exception as e:
            console.print(f"[red]✗ Failed to promote model: {e}[/red]")
    
    def demote_model(self, model_id: str):
        """Remove promotion from a model, restoring its original priority."""
        from mind_swarm.ai.model_pool import model_pool
        
        try:
            model_pool.demote_model(model_id)
            console.print(f"[green]✓ Model {model_id} demoted to original priority[/green]")
        except ValueError as e:
            console.print(f"[red]✗ Error: {e}[/red]")
        except Exception as e:
            console.print(f"[red]✗ Failed to demote model: {e}[/red]")
    
    async def sync_openrouter_models(self):
        """Sync OpenRouter models from their API."""
        import os
        import subprocess
        from pathlib import Path
        
        # Check for API key
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            console.print("[red]✗ No OPENROUTER_API_KEY found in environment[/red]")
            console.print("[dim]Set OPENROUTER_API_KEY in .env file to use OpenRouter models[/dim]")
            return
        
        console.print("[cyan]Syncing OpenRouter models...[/cyan]")
        
        # Run the sync command with update-only to preserve user settings
        config_path = Path("config/openrouter_models.yaml")
        
        try:
            # Run sync command in subprocess
            result = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "mind_swarm.cli.commands.sync_openrouter",
                "sync", "--update-only", "--output", str(config_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                # Parse output to show summary
                output = stdout.decode()
                if "Updated" in output:
                    # Extract numbers from output
                    import re
                    match = re.search(r"Updated (\d+) existing models", output)
                    if match:
                        count = match.group(1)
                        console.print(f"[green]✓ Updated {count} models with latest context lengths[/green]")
                    else:
                        console.print("[green]✓ Models synced successfully[/green]")
                else:
                    console.print("[green]✓ Models are up to date[/green]")
                    
                # Reload model pool to pick up changes
                from mind_swarm.ai.model_pool import model_pool
                model_pool.__init__()  # Reinitialize to reload configs
                console.print("[dim]Model pool reloaded with updated configurations[/dim]")
                
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                console.print(f"[red]✗ Sync failed: {error_msg}[/red]")
                
        except Exception as e:
            console.print(f"[red]✗ Failed to sync models: {e}[/red]")
    
    async def show_model_list(self):
        """Display full list of available models."""
        from mind_swarm.ai.model_pool import model_pool, Priority, CostType
        from datetime import datetime
        
        model_list = model_pool.list_models(include_paid=True)
        
        if not model_list:
            console.print("[yellow]No models available[/yellow]")
            return
        
        table = Table(title="Available Models")
        table.add_column("Model ID", style="cyan")
        table.add_column("Priority", style="magenta")
        table.add_column("Cost", style="green")
        table.add_column("Provider")
        table.add_column("Context", style="dim")
        table.add_column("Status")
        
        for model, promotion in model_list:
            # Determine status
            status = ""
            if promotion:
                if promotion.expires_at == datetime.max:
                    status = "Promoted (indefinite)"
                else:
                    remaining = promotion.expires_at - datetime.now()
                    hours = remaining.total_seconds() / 3600
                    status = f"Promoted ({hours:.1f}h left)"
            
            # Get effective priority
            effective_priority = promotion.new_priority if promotion else model.priority
            
            # Format priority with color
            priority = effective_priority.value
            if effective_priority == Priority.PRIMARY:
                priority = f"[bold green]{priority}[/bold green]"
            elif effective_priority == Priority.NORMAL:
                priority = f"[yellow]{priority}[/yellow]"
            else:
                priority = f"[dim]{priority}[/dim]"
            
            # Add indicator if promoted
            if promotion:
                priority = f"{priority} ⬆"
            
            # Format cost
            cost = "FREE" if model.cost_type == CostType.FREE else "PAID"
            if model.cost_type == CostType.PAID:
                cost = f"[red]{cost}[/red]"
            
            table.add_row(
                model.id,
                priority,
                cost,
                model.provider,
                str(model.context_length),
                status
            )
        
        console.print(table)
    
    def show_model_summary(self):
        """Display model pool summary."""
        from mind_swarm.ai.model_pool import model_pool, Priority
        
        model_list = model_pool.list_models(include_paid=True)
        
        # Count by effective priority (considering promotions)
        primary_count = 0
        normal_count = 0
        fallback_count = 0
        
        for model, promotion in model_list:
            effective_priority = promotion.new_priority if promotion else model.priority
            if effective_priority == Priority.PRIMARY:
                primary_count += 1
            elif effective_priority == Priority.NORMAL:
                normal_count += 1
            else:
                fallback_count += 1
        
        table = Table(title="Model Pool Summary")
        table.add_column("Priority", style="cyan")
        table.add_column("Count", style="green", justify="right")
        table.add_column("Description")
        
        table.add_row(
            "PRIMARY",
            str(primary_count),
            "Preferred models (selected first)"
        )
        table.add_row(
            "NORMAL",
            str(normal_count),
            "Standard models (selected if no primary)"
        )
        table.add_row(
            "FALLBACK",
            str(fallback_count),
            "Local models (used as last resort)"
        )
        
        console.print(table)
        console.print(f"\n[dim]Use 'mind-swarm models list' to see all models[/dim]")
    
    async def run_interactive(self):
        """Run interactive mode."""
        self._running = True
        
        console.print("[bold]Mind-Swarm Interactive Mode[/bold]")
        console.print("Commands:")
        console.print("  [cyan]status[/cyan] - Show Cyber status")
        console.print("  [cyan]create [--io] [name][/cyan] - Create a new AI Cyber")
        console.print("  [cyan]terminate <name>[/cyan] - Terminate an Cyber")
        console.print("  [cyan]command <name> <command> [params][/cyan] - Send command to Cyber")
        console.print("  [cyan]message <name> <text>[/cyan] - Send message to Cyber")
        console.print("  [cyan]question <text>[/cyan] - Create a shared question")
        console.print("  [cyan]announce <title> | <message>[/cyan] - Create system announcement")
        console.print("  [cyan]clear-announcements[/cyan] - Clear all system announcements")
        console.print("  [cyan]models[/cyan] - Show model pool summary")
        console.print("  [cyan]models list[/cyan] - Show all available models")
        console.print("  [cyan]models promote <id> <priority> [--duration <hours>][/cyan] - Promote model")
        console.print("  [cyan]models demote <id>[/cyan] - Demote model to original priority")
        console.print("  [cyan]models sync[/cyan] - Sync OpenRouter models from API (update context lengths)")
        console.print("  [cyan]dev register <name> [full_name] [email][/cyan] - Register developer")
        console.print("  [cyan]dev current [name][/cyan] - Show/set current developer")
        console.print("  [cyan]dev list[/cyan] - List registered developers")
        console.print("  [cyan]mailbox[/cyan] - Check developer mailbox")
        console.print("  [cyan]stop[/cyan] - Stop the server")
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
                
                elif cmd == "stop":
                    # Stop the server using the PID file approach
                    console.print("[yellow]Stopping the server...[/yellow]")
                    
                    import signal
                    import time
                    from pathlib import Path
                    
                    pid_file = Path("/tmp/mind-swarm-server.pid")
                    
                    if not pid_file.exists():
                        console.print("[yellow]Server not running (no PID file)[/yellow]")
                    else:
                        try:
                            pid = int(pid_file.read_text().strip())
                            import os
                            os.kill(pid, signal.SIGTERM)
                            console.print(f"[green]✓ Sent shutdown signal to server (PID: {pid})[/green]")
                            
                            # Wait for shutdown (up to 60 seconds)
                            console.print("[dim]Waiting for graceful shutdown...[/dim]")
                            for i in range(120):
                                await asyncio.sleep(0.5)
                                try:
                                    os.kill(pid, 0)
                                    # Show progress every 5 seconds
                                    if i > 0 and i % 10 == 0:
                                        console.print(f"[yellow]Still waiting... ({i//2}s)[/yellow]")
                                except ProcessLookupError:
                                    console.print("[green]✓ Server stopped gracefully[/green]")
                                    console.print("[dim]Exiting client...[/dim]")
                                    self._running = False
                                    break
                            else:
                                # If we're still here after 60s, force kill
                                console.print("[red]Server still running after 60s, sending SIGKILL[/red]")
                                os.kill(pid, signal.SIGKILL)
                                await asyncio.sleep(1)
                                console.print("[green]✓ Server force stopped[/green]")
                                self._running = False
                                
                        except (ValueError, ProcessLookupError) as e:
                            console.print("[yellow]Server not running (stale PID file)[/yellow]")
                            pid_file.unlink()
                        except Exception as e:
                            console.print(f"[red]✗ Failed to stop server: {e}[/red]")
                            console.print("[dim]You may need to stop the server manually using 'mind-swarm server stop'[/dim]")
                
                elif cmd == "status":
                    await self.show_status()
                
                elif cmd == "create":
                    # Parse create options: create [--io] [name]
                    is_io_agent = False
                    cyber_name = None
                    
                    for i, part in enumerate(parts[1:], 1):
                        if part == "--io":
                            is_io_agent = True
                        else:
                            cyber_name = part
                    
                    # Determine Cyber type
                    cyber_type = "io_gateway" if is_io_agent else "general"
                    
                    agent_name_result = await self.client.create_agent(
                        name=cyber_name,
                        cyber_type=cyber_type,
                    )
                    type_str = "I/O Gateway" if is_io_agent else "General"
                    console.print(f"Created {agent_name_result} [{type_str}]")
                
                elif cmd == "terminate" and len(parts) > 1:
                    cyber_name = parts[1]
                    await self.client.terminate_agent(cyber_name)
                    console.print(f"Terminated Cyber {cyber_name}")
                
                elif cmd == "command" and len(parts) >= 3:
                    # command <cyber_name> <command> [params]
                    cyber_name = parts[1]
                    command = parts[2]
                    params = {"input": " ".join(parts[3:])} if len(parts) > 3 else {}
                    
                    await self.client.send_command(cyber_name, command, params)
                    console.print(f"Command '{command}' sent to {cyber_name}")
                
                elif cmd == "message" and len(parts) >= 3:
                    # message <cyber_name> <text>
                    cyber_name = parts[1]
                    message_text = " ".join(parts[2:])
                    
                    await self.client.send_message(cyber_name, message_text)
                    console.print(f"Message sent to {cyber_name}")
                
                elif cmd == "question" and len(parts) > 1:
                    # Post a question to the Community
                    question_text = " ".join(parts[1:])
                    q_id = await self.client.create_community_question(question_text)
                    console.print(f"Posted to Community: {q_id}")
                
                elif cmd == "announce" and len(parts) > 1:
                    # Create system announcement
                    # Format: announce <title> | <message> [--priority HIGH] [--expires 2025-12-31]
                    announce_text = " ".join(parts[1:])
                    
                    # Parse title and message separated by |
                    if "|" in announce_text:
                        title, rest = announce_text.split("|", 1)
                        title = title.strip()
                        
                        # Parse message and optional flags
                        message_parts = rest.strip().split("--")
                        message = message_parts[0].strip()
                        
                        # Parse optional flags
                        priority = "HIGH"
                        expires = None
                        
                        for flag_part in message_parts[1:]:
                            flag_part = flag_part.strip()
                            if flag_part.startswith("priority "):
                                priority = flag_part[9:].strip().upper()
                            elif flag_part.startswith("expires "):
                                expires = flag_part[8:].strip()
                        
                        try:
                            success = await self.client.update_announcements(
                                title=title,
                                message=message,
                                priority=priority,
                                expires=expires
                            )
                            
                            if success:
                                console.print(f"[green]✓ Announcement created: {title}[/green]")
                                console.print(f"  Priority: {priority}")
                                if expires:
                                    console.print(f"  Expires: {expires}")
                            else:
                                console.print("[red]Failed to create announcement[/red]")
                        except Exception as e:
                            console.print(f"[red]Error creating announcement: {e}[/red]")
                    else:
                        console.print("[yellow]Format: announce <title> | <message> [--priority HIGH] [--expires 2025-12-31][/yellow]")
                
                elif cmd == "clear-announcements":
                    # Clear all system announcements
                    try:
                        success = await self.client.clear_announcements()
                        if success:
                            console.print("[green]✓ All announcements cleared[/green]")
                        else:
                            console.print("[red]Failed to clear announcements[/red]")
                    except Exception as e:
                        console.print(f"[red]Error clearing announcements: {e}[/red]")
                
                elif cmd == "models":
                    # Check for subcommand
                    if len(parts) > 1:
                        subcmd = parts[1].lower()
                        
                        if subcmd == "list":
                            # Show full model list
                            await self.show_model_list()
                        
                        elif subcmd == "promote" and len(parts) >= 4:
                            # models promote <model_id> <priority> [--duration <hours>]
                            model_id = parts[2]
                            priority = parts[3]
                            
                            # Check for duration flag
                            duration = None
                            if len(parts) > 4:
                                for i in range(4, len(parts)):
                                    if parts[i] == "--duration" and i + 1 < len(parts):
                                        try:
                                            duration = float(parts[i + 1])
                                        except ValueError:
                                            console.print(f"[red]Invalid duration: {parts[i + 1]}[/red]")
                                            continue
                            
                            # Promote the model
                            self.promote_model(model_id, priority, duration)
                        
                        elif subcmd == "demote" and len(parts) >= 3:
                            # models demote <model_id>
                            model_id = parts[2]
                            self.demote_model(model_id)
                        
                        elif subcmd == "sync":
                            # Sync OpenRouter models
                            await self.sync_openrouter_models()
                        
                        else:
                            console.print(f"[red]Unknown models command: {subcmd}[/red]")
                            console.print("[dim]Use 'models', 'models list', 'models promote', 'models demote', or 'models sync'[/dim]")
                    else:
                        # Show summary
                        self.show_model_summary()
                
                elif cmd == "dev" and len(parts) > 1:
                    # Developer commands
                    subcmd = parts[1].lower()
                    
                    if subcmd == "register" and len(parts) >= 3:
                        # dev register <name> [full_name] [email]
                        name = parts[2]
                        full_name = parts[3] if len(parts) > 3 else None
                        email = parts[4] if len(parts) > 4 else None
                        
                        try:
                            cyber_name = await self.client.register_developer(name, full_name, email)
                            console.print(f"[green]Registered developer {name} as {cyber_name}[/green]")
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
                                    console.print(f"Current developer: {dev['cyber_name']} ({dev.get('full_name', 'N/A')})")
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
                                table.add_column("Cyber Name", style="green")
                                table.add_column("Full Name")
                                table.add_column("Email")
                                table.add_column("Last Active")
                                
                                for name, info in developers.items():
                                    table.add_row(
                                        name,
                                        info["cyber_name"],
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
    create_agents: int = typer.Option(0, "--create", "-c", help="Number of Cybers to create on connect"),
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
            
            # Create initial Cybers if requested
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
                    console.print(f"  Cybers: {len(status.Cybers)}")
                    console.print(f"  Community questions: {status.community_questions}")
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
    console.print(f"Max Cybers: {settings.subspace.max_agents}")
    
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
def announce(
    title: str = typer.Argument(..., help="Announcement title"),
    message: str = typer.Argument(..., help="Announcement message"),
    priority: str = typer.Option("HIGH", "--priority", "-p", help="Priority: CRITICAL, HIGH, MEDIUM, LOW"),
    expires: Optional[str] = typer.Option(None, "--expires", "-e", help="Expiration date (ISO format: 2025-12-31)"),
):
    """Create a system announcement for all Cybers."""
    console.print(f"[bold]Creating System Announcement[/bold]")
    
    # Check if server is running
    client = MindSwarmClient()
    if not client.is_server_running():
        console.print("[red]Server is not running![/red]")
        console.print("Start with: [cyan]mind-swarm server start[/cyan]")
        return
    
    async def send_announcement():
        try:
            if await client.check_server():
                success = await client.update_announcements(
                    title=title,
                    message=message,
                    priority=priority.upper(),
                    expires=expires
                )
                
                if success:
                    console.print(f"[green]✓ Announcement created successfully![/green]")
                    console.print(f"  Title: {title}")
                    console.print(f"  Message: {message}")
                    console.print(f"  Priority: {priority.upper()}")
                    if expires:
                        console.print(f"  Expires: {expires}")
                else:
                    console.print("[red]Failed to create announcement[/red]")
            else:
                console.print("[red]Server not responding[/red]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            logger.error(f"Failed to create announcement: {e}", exc_info=True)
    
    asyncio.run(send_announcement())


@app.command()
def server(
    action: str = typer.Argument(..., help="Action: start, stop, restart, logs"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug logging"),
    llm_debug: bool = typer.Option(False, "--llm-debug", help="Enable LLM API call logging"),
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
        
        # Ensure log directory exists
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
        if llm_debug:
            cmd.append("--llm-debug")
        
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
        server("stop", debug=False, llm_debug=False, host=host, port=port)
        time.sleep(1)
        # Then start
        server("start", debug=debug, llm_debug=llm_debug, host=host, port=port)
    
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