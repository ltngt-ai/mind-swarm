"""Knowledge system CLI commands.

Provides commands to interact with the server knowledge APIs.

Example usage:
  - Sync all knowledge sources:
      mind-swarm knowledge sync
  - Sync only library sources:
      mind-swarm knowledge sync --scope library
  - Sync template or community scopes:
      mind-swarm knowledge sync --scope template
      mind-swarm knowledge sync --scope community
  - Explicitly sync all scopes:
      mind-swarm knowledge sync --scope all
"""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from mind_swarm.client import MindSwarmClient

app = typer.Typer(help="Knowledge system commands")
console = Console()


@app.command("sync")
def sync(
    scope: Optional[str] = typer.Option(
        None,
        "--scope",
        "-s",
        help="Scope to sync: library | template | community | all (default: all)",
        case_sensitive=False,
    )
):
    """Trigger a server-side knowledge sync and show a summary.

    Contacts the server's /knowledge/sync endpoint with an optional scope
    filter and displays counts for added, updated, unchanged, and errors.
    """
    # Normalize scope to lowercase if provided
    if scope is not None:
        scope = scope.lower()
    
    valid_scopes = {"library", "template", "community", "all"}
    if scope is not None and scope not in valid_scopes:
        console.print(
            f"[red]Invalid scope: {scope}. Valid options: library, template, community, all[/red]"
        )
        raise typer.Exit(code=2)

    async def _run():
        client = MindSwarmClient()
        try:
            # Perform sync; let server default handle None scope as "all"
            result = await client.sync_knowledge(scope=scope)
        except Exception as e:
            console.print(
                f"[red]Failed to contact server for knowledge sync: {e}[/red]"
            )
            console.print(
                "[dim]Ensure the server is running: mind-swarm server start or ./run.sh server[/dim]"
            )
            raise typer.Exit(code=1)

        status = result.get("status", "unknown")
        message = result.get("message", "")

        if status != "success":
            console.print(f"[red]Sync failed: {message or 'Unknown error'}[/red]")
            warnings = result.get("warnings") or []
            for w in warnings:
                console.print(f"[yellow]- {w}[/yellow]")
            raise typer.Exit(code=1)

        # Success output
        config = result.get("config", {})
        effective_scope = config.get("scope") or scope or "all"
        roots = config.get("roots_processed", [])

        console.print("[green]✓ Knowledge sync completed successfully[/green]")
        if message:
            console.print(f"[dim]{message}[/dim]")

        # Summary table
        stats = result.get("stats", {})
        table = Table(title="Knowledge Sync Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right", style="green")
        table.add_row("Added", str(stats.get("added", 0)))
        table.add_row("Updated", str(stats.get("updated", 0)))
        table.add_row("Unchanged", str(stats.get("unchanged", 0)))
        table.add_row("Errors", str(stats.get("errors", 0)))
        console.print(table)

        # Details
        console.print(
            f"Scope: [bold]{effective_scope}[/bold]  •  Roots processed: {', '.join(roots) if roots else 'none'}"
        )

        # Show warnings if any
        warnings = result.get("warnings") or []
        if warnings:
            console.print("\n[yellow]Warnings:[/yellow]")
            for w in warnings:
                console.print(f"  - {w}")

    asyncio.run(_run())

