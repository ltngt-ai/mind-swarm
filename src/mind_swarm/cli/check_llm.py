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
from mind_swarm.ai.presets import preset_manager

app = typer.Typer()
console = Console()


@app.command()
def check(
    url: str = typer.Option(None, "--url", "-u", help="LLM server URL to check"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed model info"),
):
    """Check local LLM server status and available models."""
    
    async def run_check(check_url, show_detailed):
        # Get URL from presets if not provided
        if not check_url:
            urls_to_check = []
            
            # Check all presets for local models
            for preset_name in preset_manager.list_presets():
                preset = preset_manager.get_preset(preset_name)
                if preset and preset.provider in ["openai_compatible", "local", "ollama"]:
                    # Get URL from api_settings
                    preset_url = None
                    if preset.api_settings and "host" in preset.api_settings:
                        preset_url = preset.api_settings["host"]
                    
                    if preset_url:
                        urls_to_check.append((preset_name, preset_url))
            
            if not urls_to_check:
                console.print("[yellow]No local LLM configurations found in presets[/yellow]")
                return
        else:
            urls_to_check = [("custom", check_url)]
        
        # Check each URL
        for preset_name, check_url in urls_to_check:
            console.print(f"\n[bold]Checking {preset_name}: {check_url}[/bold]")
            
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