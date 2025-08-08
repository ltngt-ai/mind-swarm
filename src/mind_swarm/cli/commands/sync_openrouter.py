"""Sync OpenRouter models from their API."""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, List

import typer
import httpx
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from mind_swarm.utils.logging import logger

app = typer.Typer()
console = Console()


def fetch_openrouter_models(api_key: str) -> List[Dict[str, Any]]:
    """Fetch available models from OpenRouter API.
    
    Args:
        api_key: OpenRouter API key
        
    Returns:
        List of model data from OpenRouter
    """
    url = "https://openrouter.ai/api/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    response = httpx.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    return data.get("data", [])


def load_existing_config(path: Path) -> Dict[str, Any]:
    """Load existing configuration to preserve user settings.
    
    Args:
        path: Path to existing config file
        
    Returns:
        Dictionary mapping model IDs to their existing config
    """
    if not path.exists():
        return {}
    
    try:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        
        existing = {}
        for model in data.get('models', []):
            model_id = model.get('id')
            if model_id:
                existing[model_id] = {
                    'priority': model.get('priority', 'normal'),
                    'custom_name': model.get('name') if 'name' in model else None,
                    'temperature': model.get('temperature', 0.7),
                    'custom_settings': model.get('api_settings', {})
                }
        return existing
    except Exception as e:
        logger.warning(f"Could not load existing config: {e}")
        return {}


@app.command()
def sync(
    api_key: str = typer.Option(None, "--api-key", "-k", help="OpenRouter API key (or use OPENROUTER_API_KEY env)"),
    output: Path = typer.Option(
        Path("config/openrouter_models_auto.yaml"),
        "--output", "-o",
        help="Output file path"
    ),
    filter_free: bool = typer.Option(False, "--free-only", help="Only include free models"),
    filter_paid: bool = typer.Option(False, "--paid-only", help="Only include paid models"),
    min_context: int = typer.Option(0, "--min-context", help="Minimum context length"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive model selection"),
    update_only: bool = typer.Option(False, "--update-only", "-u", help="Only update existing models, don't add new ones"),
):
    """Sync OpenRouter models from their API and generate configuration."""
    
    # Get API key
    if not api_key:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            console.print("[red]Error: No OpenRouter API key provided[/red]")
            console.print("Set OPENROUTER_API_KEY env var or use --api-key option")
            raise typer.Exit(1)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Fetch models
        task = progress.add_task("Fetching models from OpenRouter...", total=None)
        
        try:
            models_data = fetch_openrouter_models(api_key)
            progress.update(task, completed=True)
            console.print(f"[green]✓ Fetched {len(models_data)} models from OpenRouter[/green]")
        except Exception as e:
            console.print(f"[red]✗ Failed to fetch models: {e}[/red]")
            raise typer.Exit(1)
    
    # Filter models
    filtered_models = []
    for model in models_data:
        # Skip if no ID
        if not model.get("id"):
            continue
            
        # Get pricing info
        pricing = model.get("pricing", {})
        prompt_price = float(pricing.get("prompt", "0").replace("$", ""))
        completion_price = float(pricing.get("completion", "0").replace("$", ""))
        is_free = prompt_price == 0 and completion_price == 0
        
        # Apply filters
        if filter_free and not is_free:
            continue
        if filter_paid and is_free:
            continue
            
        context_length = model.get("context_length", 8192)
        if context_length < min_context:
            continue
            
        filtered_models.append(model)
    
    console.print(f"[cyan]Filtered to {len(filtered_models)} models[/cyan]")
    
    # Interactive selection if requested
    if interactive:
        selected_models = []
        table = Table(title="Available OpenRouter Models")
        table.add_column("#", style="cyan", width=4)
        table.add_column("Model ID", style="green")
        table.add_column("Context", style="yellow", justify="right")
        table.add_column("Cost", style="magenta")
        
        for i, model in enumerate(filtered_models):
            pricing = model.get("pricing", {})
            prompt_price = float(pricing.get("prompt", "0").replace("$", ""))
            cost = "FREE" if prompt_price == 0 else f"${prompt_price}/1K"
            
            table.add_row(
                str(i + 1),
                model["id"],
                f"{model.get('context_length', 0):,}",
                cost
            )
        
        console.print(table)
        console.print("\n[bold]Select models to include:[/bold]")
        console.print("Enter numbers separated by commas (e.g., 1,3,5-10) or 'all':")
        
        selection = console.input("> ").strip()
        
        if selection.lower() == "all":
            selected_models = filtered_models
        else:
            indices = set()
            for part in selection.split(","):
                part = part.strip()
                if "-" in part:
                    start, end = part.split("-")
                    indices.update(range(int(start) - 1, int(end)))
                else:
                    indices.add(int(part) - 1)
            
            selected_models = [filtered_models[i] for i in sorted(indices) if i < len(filtered_models)]
    else:
        selected_models = filtered_models
    
    # Load existing configuration to preserve user settings
    existing_config = load_existing_config(output)
    
    # In update-only mode, check if we have an existing config
    if update_only and not existing_config:
        console.print(f"[red]Error: --update-only requires existing config at {output}[/red]")
        raise typer.Exit(1)
    
    # Build a map of API models for quick lookup
    api_models_map = {m["id"]: m for m in selected_models}
    
    # Convert to our format
    output_models = []
    new_models = []
    updated_models = []
    skipped_models = []
    
    if update_only:
        # Only process models that exist in the current config
        for model_id, existing in existing_config.items():
            if model_id in api_models_map:
                model = api_models_map[model_id]
                
                # Get updated info from API
                context_length = model.get("context_length", 8192)
                max_output = model.get("max_output", 4096)
                pricing = model.get("pricing", {})
                prompt_price = float(pricing.get("prompt", "0").replace("$", ""))
                
                # Determine cost type
                cost_type = "free" if prompt_price == 0 else "paid"
                
                # Preserve all user settings
                model_config = {
                    "id": model_id,
                    "name": existing.get('custom_name') or model.get("name", model_id),
                    "provider": "openrouter",
                    "priority": existing.get('priority', 'normal'),
                    "cost_type": cost_type,
                    "context_length": context_length,  # Updated from API
                    "max_tokens": max_output or 4096,   # Updated from API
                    "temperature": existing.get('temperature', 0.7),
                }
                
                # Preserve any custom API settings
                if existing.get('custom_settings'):
                    model_config["api_settings"] = existing['custom_settings']
                
                # Add pricing info as comment
                if cost_type == "paid":
                    model_config["_pricing"] = {
                        "prompt": pricing.get("prompt"),
                        "completion": pricing.get("completion")
                    }
                
                output_models.append(model_config)
                updated_models.append(model_id)
            else:
                # Model exists in config but not in API response
                skipped_models.append(model_id)
        
        # Count new models that were skipped
        for model in selected_models:
            if model["id"] not in existing_config:
                new_models.append(model["id"])
    else:
        # Normal mode - process all selected models
        for model in selected_models:
            model_id = model["id"]
            
            # Get model info from API
            context_length = model.get("context_length", 8192)
            max_output = model.get("max_output", 4096)
            pricing = model.get("pricing", {})
            prompt_price = float(pricing.get("prompt", "0").replace("$", ""))
            
            # Determine cost type
            cost_type = "free" if prompt_price == 0 else "paid"
            
            # Check if model exists in current config
            existing = existing_config.get(model_id, {})
            
            # Use existing priority or default to 'normal' for new models
            priority = existing.get('priority', 'normal')
            
            # Use custom name if set, otherwise use API name
            name = existing.get('custom_name') or model.get("name", model_id)
            
            # Use existing temperature or default
            temperature = existing.get('temperature', 0.7)
            
            # Create model entry
            model_config = {
                "id": model_id,
                "name": name,
                "provider": "openrouter",
                "priority": priority,
                "cost_type": cost_type,
                "context_length": context_length,
                "max_tokens": max_output or 4096,
                "temperature": temperature,
            }
            
            # Preserve any custom API settings
            if existing.get('custom_settings'):
                model_config["api_settings"] = existing['custom_settings']
            
            # Add pricing info as comment
            if cost_type == "paid":
                model_config["_pricing"] = {
                    "prompt": pricing.get("prompt"),
                    "completion": pricing.get("completion")
                }
            
            output_models.append(model_config)
            
            # Track new vs updated
            if model_id in existing_config:
                updated_models.append(model_id)
            else:
                new_models.append(model_id)
    
    # Sort by priority and name
    priority_order = {"primary": 0, "normal": 1, "fallback": 2}
    output_models.sort(key=lambda x: (priority_order[x["priority"]], x["name"]))
    
    # Create output structure
    output_data = {
        "models": output_models,
        "provider_settings": {
            "openrouter": {
                "site_url": "http://mind-swarm:8000",
                "app_name": "Mind-Swarm"
            }
        }
    }
    
    # Write to file
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'w') as f:
        yaml.dump(output_data, f, default_flow_style=False, sort_keys=False)
    
    console.print(f"[green]✓ Wrote {len(output_models)} models to {output}[/green]")
    
    # Show what was done
    if update_only:
        if updated_models:
            console.print(f"[green]✓ Updated {len(updated_models)} existing models (preserved all settings)[/green]")
        if skipped_models:
            console.print(f"[yellow]⚠ {len(skipped_models)} models in config not found in API[/yellow]")
            if len(skipped_models) <= 5:
                for model_id in skipped_models:
                    console.print(f"  - {model_id}")
        if new_models:
            console.print(f"[cyan]ℹ Skipped {len(new_models)} new models from API (use without --update-only to add)[/cyan]")
            if len(new_models) <= 5:
                for model_id in new_models[:5]:
                    console.print(f"  - {model_id}")
    else:
        if updated_models:
            console.print(f"[yellow]Updated {len(updated_models)} existing models (preserved priorities)[/yellow]")
        if new_models:
            console.print(f"[cyan]Added {len(new_models)} new models (default priority: normal)[/cyan]")
            if len(new_models) <= 10:
                for model_id in new_models[:10]:
                    console.print(f"  - {model_id}")
            else:
                console.print(f"  (showing first 5)")
                for model_id in new_models[:5]:
                    console.print(f"  - {model_id}")
    
    # Show summary
    table = Table(title="Model Summary by Priority")
    table.add_column("Priority", style="cyan")
    table.add_column("Count", style="green", justify="right")
    table.add_column("Status")
    
    for priority in ["primary", "normal", "fallback"]:
        count = sum(1 for m in output_models if m["priority"] == priority)
        status = ""
        if priority == "normal" and new_models and not update_only:
            status = f"(includes {len(new_models)} new)"
        table.add_row(priority.upper(), str(count), status)
    
    console.print(table)
    
    if new_models and not update_only:
        console.print("\n[dim]Tip: Edit the file to set priorities for new models[/dim]")


@app.command()
def check():
    """Check current OpenRouter API key and available models."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    
    if not api_key:
        console.print("[yellow]No OPENROUTER_API_KEY found in environment[/yellow]")
        return
    
    console.print(f"[green]✓ OPENROUTER_API_KEY found: {api_key[:10]}...[/green]")
    
    try:
        models = fetch_openrouter_models(api_key)
        console.print(f"[green]✓ Successfully fetched {len(models)} models[/green]")
        
        # Show some stats
        free_count = sum(
            1 for m in models 
            if float(m.get("pricing", {}).get("prompt", "1").replace("$", "")) == 0
        )
        
        console.print(f"  - Free models: {free_count}")
        console.print(f"  - Paid models: {len(models) - free_count}")
        
        # Show a few examples
        console.print("\n[bold]Sample models:[/bold]")
        for model in models[:5]:
            console.print(f"  - {model['id']}: {model.get('context_length', 0):,} tokens")
            
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch models: {e}[/red]")


if __name__ == "__main__":
    app()