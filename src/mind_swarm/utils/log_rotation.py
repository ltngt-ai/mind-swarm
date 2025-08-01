"""Log rotation utilities for agent logs."""

import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from mind_swarm.utils.logging import logger


class AgentLogRotator:
    """Handles log rotation for agent logs.
    
    Each agent gets their own directory:
    /subspace/logs/agents/Alice/
        current.log          # Active log file
        2025-08-01_09-30-00.log  # Rotated logs with timestamps
        2025-08-01_08-15-22.log
    """
    
    def __init__(self, logs_base_dir: Path, max_size_mb: int = 10, max_files: int = 5):
        """Initialize log rotator.
        
        Args:
            logs_base_dir: Base directory for agent logs (e.g. /subspace/logs/agents)
            max_size_mb: Maximum size in MB before rotation
            max_files: Maximum number of rotated files to keep
        """
        self.logs_base_dir = logs_base_dir
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_files = max_files
        
    def get_agent_log_dir(self, agent_name: str) -> Path:
        """Get the log directory for a specific agent."""
        return self.logs_base_dir / agent_name
    
    def get_current_log_path(self, agent_name: str) -> Path:
        """Get the path to the current log file for an agent."""
        agent_dir = self.get_agent_log_dir(agent_name)
        agent_dir.mkdir(parents=True, exist_ok=True)
        return agent_dir / "current.log"
        
    def should_rotate(self, agent_name: str) -> bool:
        """Check if an agent's log file should be rotated."""
        log_file = self.get_current_log_path(agent_name)
        if not log_file.exists():
            return False
        
        return log_file.stat().st_size >= self.max_size_bytes
    
    def rotate_log(self, agent_name: str) -> Path:
        """Rotate log file for an agent.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Path to the new current.log file
        """
        current_log = self.get_current_log_path(agent_name)
        
        if not current_log.exists():
            return current_log
        
        # Create timestamp for rotated file
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        agent_dir = self.get_agent_log_dir(agent_name)
        
        # Clean up old files if needed
        self._cleanup_old_logs(agent_name)
        
        # Rename current log with timestamp
        rotated_path = agent_dir / f"{timestamp}.log"
        shutil.move(str(current_log), str(rotated_path))
        
        logger.info(f"Rotated log for {agent_name}: current.log -> {rotated_path.name}")
        
        return current_log
    
    def _cleanup_old_logs(self, agent_name: str):
        """Remove old rotated logs if we exceed max_files."""
        agent_dir = self.get_agent_log_dir(agent_name)
        
        # Find all timestamped log files
        rotated_logs = self.get_rotated_logs(agent_name)
        
        # Remove oldest files if we have too many
        while len(rotated_logs) >= self.max_files:
            oldest = rotated_logs.pop()  # List is sorted newest first, so last is oldest
            oldest.unlink()
            logger.info(f"Removed old log file: {oldest.name}")
    
    def get_latest_log(self, agent_name: str) -> Optional[Path]:
        """Get the latest (current) log file for an agent."""
        log_file = self.get_current_log_path(agent_name)
        return log_file if log_file.exists() else None
    
    def get_rotated_logs(self, agent_name: str) -> List[Path]:
        """Get all rotated log files for an agent, sorted newest first."""
        agent_dir = self.get_agent_log_dir(agent_name)
        
        if not agent_dir.exists():
            return []
        
        # Find all files matching timestamp pattern (YYYY-MM-DD_HH-MM-SS.log)
        rotated_files = [
            f for f in agent_dir.glob("*.log")
            if f.name != "current.log" and self._is_timestamp_log(f.name)
        ]
        
        # Sort by modification time, newest first
        return sorted(rotated_files, key=lambda f: f.stat().st_mtime, reverse=True)
    
    def _is_timestamp_log(self, filename: str) -> bool:
        """Check if filename matches timestamp pattern."""
        # Pattern: YYYY-MM-DD_HH-MM-SS.log
        parts = filename.split('.')
        if len(parts) != 2 or parts[1] != 'log':
            return False
        
        try:
            datetime.strptime(parts[0], "%Y-%m-%d_%H-%M-%S")
            return True
        except ValueError:
            return False
    
    def get_all_logs(self, agent_name: str) -> List[Path]:
        """Get all log files for an agent (current + rotated), newest first."""
        logs = []
        
        # Add current log if it exists
        current = self.get_latest_log(agent_name)
        if current:
            logs.append(current)
        
        # Add rotated logs
        logs.extend(self.get_rotated_logs(agent_name))
        
        return logs
    
    def clean_all_logs(self, agent_name: str):
        """Remove all log files for an agent."""
        agent_dir = self.get_agent_log_dir(agent_name)
        
        if agent_dir.exists():
            shutil.rmtree(agent_dir)
            logger.info(f"Cleaned all logs for agent {agent_name}")