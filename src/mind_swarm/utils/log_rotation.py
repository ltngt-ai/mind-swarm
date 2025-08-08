"""Log rotation utilities for Cyber logs."""

import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from mind_swarm.utils.logging import logger


class AgentLogRotator:
    """Handles log rotation for Cyber logs.
    
    Each Cyber gets their own directory:
    /subspace/logs/Cybers/Alice/
        current.log          # Active log file
        2025-08-01_09-30-00.log  # Rotated logs with timestamps
        2025-08-01_08-15-22.log
    """
    
    def __init__(self, logs_base_dir: Path, max_size_mb: int = 10, max_files: int = 5):
        """Initialize log rotator.
        
        Args:
            logs_base_dir: Base directory for Cyber logs (e.g. /subspace/logs/Cybers)
            max_size_mb: Maximum size in MB before rotation
            max_files: Maximum number of rotated files to keep
        """
        self.logs_base_dir = logs_base_dir
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_files = max_files
        
    def get_agent_log_dir(self, cyber_name: str) -> Path:
        """Get the log directory for a specific Cyber."""
        return self.logs_base_dir / cyber_name
    
    def get_current_log_path(self, cyber_name: str) -> Path:
        """Get the path to the current log file for an Cyber."""
        cyber_dir = self.get_agent_log_dir(cyber_name)
        cyber_dir.mkdir(parents=True, exist_ok=True)
        return cyber_dir / "current.log"
        
    def should_rotate(self, cyber_name: str) -> bool:
        """Check if an Cyber's log file should be rotated."""
        log_file = self.get_current_log_path(cyber_name)
        if not log_file.exists():
            return False
        
        return log_file.stat().st_size >= self.max_size_bytes
    
    def rotate_log(self, cyber_name: str) -> Path:
        """Rotate log file for an Cyber.
        
        Args:
            cyber_name: Name of the Cyber
            
        Returns:
            Path to the new current.log file
        """
        current_log = self.get_current_log_path(cyber_name)
        
        if not current_log.exists():
            return current_log
        
        # Create timestamp for rotated file
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        cyber_dir = self.get_agent_log_dir(cyber_name)
        
        # Clean up old files if needed
        self._cleanup_old_logs(cyber_name)
        
        # Rename current log with timestamp
        rotated_path = cyber_dir / f"{timestamp}.log"
        shutil.move(str(current_log), str(rotated_path))
        
        logger.info(f"Rotated log for {cyber_name}: current.log -> {rotated_path.name}")
        
        return current_log
    
    def _cleanup_old_logs(self, cyber_name: str):
        """Remove old rotated logs if we exceed max_files."""
        cyber_dir = self.get_agent_log_dir(cyber_name)
        
        # Find all timestamped log files
        rotated_logs = self.get_rotated_logs(cyber_name)
        
        # Remove oldest files if we have too many
        while len(rotated_logs) >= self.max_files:
            oldest = rotated_logs.pop()  # List is sorted newest first, so last is oldest
            oldest.unlink()
            logger.info(f"Removed old log file: {oldest.name}")
    
    def get_latest_log(self, cyber_name: str) -> Optional[Path]:
        """Get the latest (current) log file for an Cyber."""
        log_file = self.get_current_log_path(cyber_name)
        return log_file if log_file.exists() else None
    
    def get_rotated_logs(self, cyber_name: str) -> List[Path]:
        """Get all rotated log files for an Cyber, sorted newest first."""
        cyber_dir = self.get_agent_log_dir(cyber_name)
        
        if not cyber_dir.exists():
            return []
        
        # Find all files matching timestamp pattern (YYYY-MM-DD_HH-MM-SS.log)
        rotated_files = [
            f for f in cyber_dir.glob("*.log")
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
    
    def get_all_logs(self, cyber_name: str) -> List[Path]:
        """Get all log files for an Cyber (current + rotated), newest first."""
        logs = []
        
        # Add current log if it exists
        current = self.get_latest_log(cyber_name)
        if current:
            logs.append(current)
        
        # Add rotated logs
        logs.extend(self.get_rotated_logs(cyber_name))
        
        return logs
    
    def clean_all_logs(self, cyber_name: str):
        """Remove all log files for an Cyber."""
        cyber_dir = self.get_agent_log_dir(cyber_name)
        
        if cyber_dir.exists():
            shutil.rmtree(cyber_dir)
            logger.info(f"Cleaned all logs for Cyber {cyber_name}")