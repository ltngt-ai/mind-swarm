"""Logging configuration for Mind-Swarm."""

import logging
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

from mind_swarm.core.config import settings


def setup_logging(
    name: str = "mind_swarm",
    log_file: Optional[Path] = None,
    level: Optional[str] = None,
) -> logging.Logger:
    """Set up logging with Rich handler for better output.
    
    Args:
        name: Logger name
        log_file: Optional file path for logging
        level: Log level (defaults to settings.log_level)
    
    Returns:
        Configured logger instance
    """
    level = level or settings.log_level
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Console handler with Rich
    console = Console(stderr=True)
    console_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=settings.debug,
        rich_tracebacks=True,
        tracebacks_show_locals=settings.debug,
    )
    console_handler.setLevel(level)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


# Create default logger
logger = setup_logging()