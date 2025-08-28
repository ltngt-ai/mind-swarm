"""Configuration management for Mind-Swarm."""

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class AIModelConfig(BaseModel):
    """Configuration for AI models."""
    
    openrouter_api_key: Optional[str] = Field(default=None, description="OpenRouter API key")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")


class SubspaceConfig(BaseModel):
    """Configuration for the subspace environment."""
    
    root_path: Path = Field(default=Path("./subspace"), description="Root path for subspace")
    max_agents: int = Field(default=5, description="Maximum number of concurrent Cybers")
    agent_memory_limit_mb: int = Field(default=512, description="Memory limit per Cyber in MB")
    agent_cpu_limit_percent: float = Field(default=20.0, description="CPU limit per Cyber as percentage")


class Settings(BaseModel):
    """Main configuration settings for Mind-Swarm."""
    
    # AI Model Configuration
    ai_models: AIModelConfig = Field(default_factory=AIModelConfig)
    
    # Subspace Configuration
    subspace: SubspaceConfig = Field(default_factory=SubspaceConfig)
    
    # Development Settings
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    
    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings from environment variables."""
        return cls(
            ai_models=AIModelConfig(
                openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
                openai_api_key=os.getenv("OPENAI_API_KEY"),
                anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            ),
            subspace=SubspaceConfig(
                # Default subspace is a folder inside the project
                root_path=Path(os.getenv("SUBSPACE_ROOT", "./subspace")),
                max_agents=int(os.getenv("MAX_AGENTS", "5")),
                agent_memory_limit_mb=int(os.getenv("AGENT_MEMORY_LIMIT_MB", "512")),
                agent_cpu_limit_percent=float(os.getenv("AGENT_CPU_LIMIT_PERCENT", "20.0")),
            ),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


# Global settings instance
settings = Settings.from_env()
import logging
logging.info(f"Settings initialized with subspace root: {settings.subspace.root_path}")

# Shared truncation limits (configurable via environment variables)
# 0 or negative disables truncation. Intended ONLY for queries/logging, not
# for mutating data stored in working memory.
KNOWLEDGE_QUERY_TRUNCATE_CHARS = int(os.getenv("KNOWLEDGE_QUERY_TRUNCATE_CHARS", "400"))
WORKING_MEMORY_TRUNCATE_CHARS = int(os.getenv("WORKING_MEMORY_TRUNCATE_CHARS", "300"))
OUTPUT_EXCERPT_TRUNCATE_CHARS = int(os.getenv("OUTPUT_EXCERPT_TRUNCATE_CHARS", "300"))
