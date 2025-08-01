"""CLI commands for viewing agent logs."""

import asyncio
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from mind_swarm.utils.log_rotation import AgentLogRotator
from mind_swarm.core.config import settings

console = Console()


def logs(
    agent_name: str = typer.Argument(..., help="Name of the agent"),
    tail: int = typer.Option(50, "--tail", "-t", help="Number of lines to show from end"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    history: bool = typer.Option(False, "--history", "-h", help="Show rotated logs"),
    subspace: Optional[str] = typer.Option(None, help="Path to subspace root")
):
    """View logs for a specific agent.
    
    Examples:
        mind-swarm logs Alice           # Show last 50 lines of Alice's log
        mind-swarm logs Alice -t 100    # Show last 100 lines
        mind-swarm logs Alice -f        # Follow Alice's log output
        mind-swarm logs Alice -h        # List Alice's rotated log files
    """
    # Determine subspace root
    if subspace:
        subspace_root = Path(subspace)
    else:
        # Use the configured subspace root from settings/environment
        subspace_root = settings.subspace.root_path
    
    # Initialize log rotator
    logs_base_dir = subspace_root / "logs" / "agents"
    log_rotator = AgentLogRotator(logs_base_dir)
    
    if history:
        # Show rotated logs
        console.print(f"[bold]Log files for agent {agent_name}:[/bold]")
        all_logs = log_rotator.get_all_logs(agent_name)
        
        if not all_logs:
            console.print(f"[yellow]No logs found for agent {agent_name}[/yellow]")
            return
        
        for log_file in all_logs:
            size_mb = log_file.stat().st_size / (1024 * 1024)
            console.print(f"  {log_file.name:<30} {size_mb:>8.2f} MB")
    
    elif follow:
        # Follow log output
        log_file = log_rotator.get_current_log_path(agent_name)
        if not log_file.exists():
            console.print(f"[yellow]No current log for agent {agent_name}[/yellow]")
            return
        
        console.print(f"[green]Following {log_file} (Ctrl+C to stop)...[/green]")
        
        try:
            asyncio.run(_follow_log(log_file))
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopped following log[/yellow]")
    
    else:
        # Show tail of current log
        log_file = log_rotator.get_current_log_path(agent_name)
        if not log_file.exists():
            console.print(f"[yellow]No current log for agent {agent_name}[/yellow]")
            return
        
        # Read last N lines
        lines = _tail_file(log_file, tail)
        for line in lines:
            console.print(line.rstrip())


def _tail_file(file_path: Path, n: int) -> list[str]:
    """Read last n lines from a file."""
    with open(file_path, 'rb') as f:
        # Start from end and work backwards
        f.seek(0, 2)  # Go to end
        file_size = f.tell()
        
        # Read chunks from end until we have enough lines
        lines = []
        chunk_size = 1024
        bytes_read = 0
        
        while len(lines) < n and bytes_read < file_size:
            # Calculate where to read from
            read_size = min(chunk_size, file_size - bytes_read)
            f.seek(file_size - bytes_read - read_size)
            
            # Read chunk
            chunk = f.read(read_size)
            bytes_read += read_size
            
            # Split into lines (prepend to existing partial line if any)
            chunk_lines = chunk.decode('utf-8', errors='replace').splitlines()
            if lines and not chunk.endswith(b'\n'):
                # Prepend first line of chunk to partial line
                chunk_lines[-1] = chunk_lines[-1] + lines[0]
                lines = chunk_lines + lines[1:]
            else:
                lines = chunk_lines + lines
    
    # Return last n lines
    return lines[-n:] if len(lines) > n else lines


async def _follow_log(log_file: Path):
    """Follow a log file, printing new lines as they appear."""
    # First print existing content
    with open(log_file, 'r') as f:
        for line in f:
            print(line.rstrip())
    
    # Then follow new content
    with open(log_file, 'r') as f:
        # Seek to end
        f.seek(0, 2)
        
        while True:
            line = f.readline()
            if line:
                print(line.rstrip())
            else:
                # No new content, wait a bit
                await asyncio.sleep(0.1)