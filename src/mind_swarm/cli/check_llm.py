"""CLI command to check local LLM server status."""

import asyncio
import typer
from rich.console import Console
from rich.table import Table

from mind_swarm.ai.providers.local_llm_check import (
    check_local_llm_server, 
    get_model_capabilities,
    format_server_status
)
from mind_swarm.ai.model_pool import model_pool

app = typer.Typer()
console = Console()


@app.command()
def check(
    url: str = typer.Option(None, "--url", "-u", help="LLM server URL to check"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed model info"),
):
    """Check local LLM server status and available models."""
    
    async def run_check(check_url, show_detailed):
        # Get URLs from model pool if not provided
        if not check_url:
            urls_to_check = []
            
            # Check all models in pool for local providers (OpenAI with custom host)
            for model, promotion in model_pool.list_models(include_paid=True):
                if model.provider == "openai" and model.api_settings and "host" in model.api_settings:
                    # This is a local OpenAI-compatible server
                    model_url = model.api_settings["host"]
                    
                    if model_url:
                        urls_to_check.append((model.id, model_url))
            
            if not urls_to_check:
                console.print("[yellow]No local LLM configurations found in model pool[/yellow]")
                return
        else:
            urls_to_check = [("custom", check_url)]
        
        # Check each URL
        for model_id, check_url in urls_to_check:
            console.print(f"\n[bold]Checking {model_id}: {check_url}[/bold]")
            
            is_healthy, model_info = await check_local_llm_server(check_url)
            status = format_server_status(is_healthy, model_info)
            console.print(status)
            
            if is_healthy and model_info and show_detailed:
                models = model_info.get("models", [])
                if models:
                    table = Table(title="Available Models")
                    table.add_column("Model ID", style="cyan")
                    table.add_column("Created", style="green")
                    table.add_column("Owned By", style="yellow")
                    
                    for model in models:
                        table.add_row(
                            model.get("id", "unknown"),
                            str(model.get("created", "unknown")),
                            model.get("owned_by", "unknown")
                        )
                    
                    console.print(table)
                    
                    # Test primary model if requested
                    primary = model_info.get("primary_model")
                    if primary:
                        console.print(f"\n[dim]Testing model {primary}...[/dim]")
                        capabilities = await get_model_capabilities(check_url, primary)
                        if capabilities:
                            if capabilities.get("completion_capable"):
                                console.print(f"[green]✓ Model {primary} is responding correctly[/green]")
                            else:
                                console.print(f"[red]✗ Model {primary} test failed[/red]")
    
    asyncio.run(run_check(url, detailed))


if __name__ == "__main__":
    app()