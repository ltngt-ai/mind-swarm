"""Command-line interface for Mind-Swarm."""

import os
from pathlib import Path

# Load environment variables from .env file before anything else
try:
    from dotenv import load_dotenv
    
    # Try to find .env file in multiple locations
    env_locations = [
        Path.cwd() / ".env",  # Current directory
        Path(__file__).parent.parent.parent.parent / ".env",  # Project root
        Path("/opt/mind-swarm/.env"),  # Absolute path for server installation
    ]
    
    for env_path in env_locations:
        if env_path.exists():
            load_dotenv(env_path, override=True)
            break
except ImportError:
    pass  # dotenv not installed

from mind_swarm.cli.main import app

__all__ = ["app"]