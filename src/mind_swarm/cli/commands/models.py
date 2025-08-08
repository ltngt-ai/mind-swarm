"""Model management CLI commands."""

import asyncio
from typing import Optional
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table

from mind_swarm.ai.model_pool import model_pool, Priority, CostType
from mind_swarm.utils.logging import logger

app = typer.Typer(help="Manage AI models", invoke_without_command=True)
console = Console()


@app.callback(invoke_without_command=True)
def models_default(ctx: typer.Context):
    """Default action when no subcommand is provided - show list."""
    if ctx.invoked_subcommand is None:
        list_models(include_paid=True)


@app.command("list")
def list_models(
    include_paid: bool = typer.Option(True, "--include-paid/--free-only", help="Include paid models in list")
):
    """List all available models with their priorities."""
    models = model_pool.list_models(include_paid=include_paid)
    
    if not models:
        console.print("[yellow]No models available[/yellow]")
        return
    
    table = Table(title="Available Models")
    table.add_column("Model ID", style="cyan")
    table.add_column("Priority", style="magenta")
    table.add_column("Cost", style="green")
    table.add_column("Provider")
    table.add_column("Context", style="dim")
    table.add_column("Status")
    
    for model in models:
        # Determine status
        status = ""
        if model.is_promoted():
            remaining = model.promoted_until - datetime.now()
            hours = remaining.total_seconds() / 3600
            status = f"Promoted ({hours:.1f}h left)"
        
        # Format priority with color
        priority = model.priority.value
        if model.priority == Priority.PRIMARY:
            priority = f"[bold green]{priority}[/bold green]"
        elif model.priority == Priority.NORMAL:
            priority = f"[yellow]{priority}[/yellow]"
        else:
            priority = f"[dim]{priority}[/dim]"
        
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


@app.command("promote")
def promote_model(
    model_id: str = typer.Argument(..., help="Model ID to promote"),
    priority: str = typer.Argument(..., help="Priority level: primary, normal, or fallback"),
    duration: Optional[float] = typer.Option(None, "--duration", "-d", help="Duration in hours (permanent if not specified)")
):
    """Promote a model to a different priority tier."""
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


@app.command("demote")
def demote_model(
    model_id: str = typer.Argument(..., help="Model ID to demote")
):
    """Remove promotion from a model, restoring its original priority."""
    try:
        model_pool.demote_model(model_id)
        console.print(f"[green]✓ Model {model_id} demoted to original priority[/green]")
    except ValueError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
    except Exception as e:
        console.print(f"[red]✗ Failed to demote model: {e}[/red]")


@app.command("add-local")
def add_local_model(
    host: str = typer.Argument(..., help="Host URL (e.g., http://192.168.1.147:1234)"),
    model_name: str = typer.Argument(..., help="Model name/identifier"),
    priority: str = typer.Option("fallback", "--priority", "-p", help="Priority: primary, normal, or fallback"),
    context_length: int = typer.Option(8192, "--context", "-c", help="Context length"),
    max_tokens: int = typer.Option(4096, "--max-tokens", "-m", help="Max output tokens")
):
    """Add a local OpenAI-compatible model to the pool."""
    try:
        from mind_swarm.ai.model_pool import ModelConfig
        
        # Parse priority
        priority_enum = Priority(priority.lower())
        
        # Create model config
        model_id = f"local/{model_name.replace('/', '-')}"
        model = ModelConfig(
            id=model_id,
            name=f"{model_name} (Local)",
            provider="openai",
            priority=priority_enum,
            cost_type=CostType.FREE,
            context_length=context_length,
            max_tokens=max_tokens,
            api_settings={"host": host}
        )
        
        # Add to pool
        model_pool.add_model(model)
        
        console.print(f"[green]✓ Added local model {model_id} with priority {priority}[/green]")
        console.print(f"  Host: {host}")
        console.print(f"  Context: {context_length} tokens")
        
    except ValueError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
    except Exception as e:
        console.print(f"[red]✗ Failed to add model: {e}[/red]")


@app.command("remove")
def remove_model(
    model_id: str = typer.Argument(..., help="Model ID to remove")
):
    """Remove a model from the pool."""
    try:
        model_pool.remove_model(model_id)
        console.print(f"[green]✓ Model {model_id} removed from pool[/green]")
    except Exception as e:
        console.print(f"[red]✗ Failed to remove model: {e}[/red]")


@app.command("info")
def model_info(
    model_id: str = typer.Argument(..., help="Model ID to show info for")
):
    """Show detailed information about a specific model."""
    model = model_pool.get_model(model_id)
    
    if not model:
        console.print(f"[red]Model {model_id} not found[/red]")
        return
    
    console.print(f"\n[bold]Model Information[/bold]")
    console.print(f"ID: [cyan]{model.id}[/cyan]")
    console.print(f"Name: {model.name}")
    console.print(f"Provider: {model.provider}")
    console.print(f"Priority: [magenta]{model.priority.value}[/magenta]")
    console.print(f"Cost Type: {'[green]FREE[/green]' if model.cost_type == CostType.FREE else '[red]PAID[/red]'}")
    console.print(f"Context Length: {model.context_length:,} tokens")
    console.print(f"Max Output: {model.max_tokens:,} tokens")
    console.print(f"Temperature: {model.temperature}")
    
    if model.api_settings:
        console.print(f"\n[bold]API Settings:[/bold]")
        for key, value in model.api_settings.items():
            console.print(f"  {key}: {value}")
    
    if model.is_promoted():
        remaining = model.promoted_until - datetime.now()
        hours = remaining.total_seconds() / 3600
        console.print(f"\n[yellow]Promoted until: {model.promoted_until.strftime('%Y-%m-%d %H:%M')} ({hours:.1f} hours remaining)[/yellow]")
        if model.original_priority:
            console.print(f"Original priority: {model.original_priority.value}")


if __name__ == "__main__":
    app()