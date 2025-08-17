#!/usr/bin/env python3
"""
Intelligent sync system for subspace management.
Syncs changes from subspace_template to subspace while preserving Cyber contributions.
"""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

import yaml

from mind_swarm.utils.logging import logger


class SubspaceSync:
    """Manages intelligent syncing between subspace_template and subspace."""
    
    def __init__(
        self,
        subspace_path: Path,
        template_path: Path,
        config_path: Optional[Path] = None,
        dry_run: bool = False
    ):
        """Initialize the sync manager.
        
        Args:
            subspace_path: Path to the runtime subspace directory
            template_path: Path to the subspace_template directory
            config_path: Path to sync configuration file
            dry_run: If True, show what would be done without making changes
        """
        self.subspace_path = subspace_path
        self.template_path = template_path
        self.config_path = config_path
        self.dry_run = dry_run
        self.config = self._load_config()
        
    def _load_config(self) -> Dict:
        """Load sync configuration."""
        if self.config_path and self.config_path.exists():
            with open(self.config_path) as f:
                return yaml.safe_load(f)
        
        # Default configuration
        return {
            "template_owned": [
                "grid/library/mind_swarm_tech/base_code/base_code_template",
                "grid/library/mind_swarm_tech/base_code/io_cyber_template",
                "boot_rom",
                "initial_knowledge"
            ],
            "cyber_owned": [
                "cybers/*",
                "grid/community",
                "grid/library/knowledge/sections"
            ],
            "merge_required": [
                "grid/library/knowledge/schemas"
            ],
            "ignore_patterns": [
                "*.pyc",
                "__pycache__",
                ".git",
                "*.log",
                ".tmp_*"
            ]
        }
    
    def _run_git_command(self, cmd: List[str], cwd: Path) -> tuple[int, str, str]:
        """Run a git command and return the result.
        
        Args:
            cmd: Git command to run
            cwd: Working directory for the command
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would run: git {' '.join(cmd)} in {cwd}")
            return 0, "", ""
        
        try:
            result = subprocess.run(
                ["git"] + cmd,
                cwd=cwd,
                capture_output=True,
                text=True
            )
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            logger.error(f"Git command failed: {e}")
            return 1, "", str(e)
    
    def init_subspace_git(self) -> bool:
        """Initialize subspace as a git repository if needed.
        
        Returns:
            True if successful
        """
        git_dir = self.subspace_path / ".git"
        
        if git_dir.exists():
            logger.info("Subspace is already a git repository")
            return True
        
        logger.info("Initializing subspace as git repository...")
        
        # Initialize git repo
        returncode, _, stderr = self._run_git_command(["init"], self.subspace_path)
        if returncode != 0:
            logger.error(f"Failed to initialize git: {stderr}")
            return False
        
        # .gitignore will be copied from template if it exists
        
        # Make initial commit
        self._run_git_command(["add", "."], self.subspace_path)
        self._run_git_command(
            ["commit", "-m", "Initial subspace commit"],
            self.subspace_path
        )
        
        logger.info("Subspace git repository initialized")
        return True
    
    def _is_path_matched(self, path: Path, patterns: List[str]) -> bool:
        """Check if a path matches any of the given patterns.
        
        Args:
            path: Path to check (relative to subspace root)
            patterns: List of glob patterns
            
        Returns:
            True if path matches any pattern
        """
        path_str = str(path)
        for pattern in patterns:
            # Handle glob patterns
            if "*" in pattern:
                # Convert to Path for glob matching
                if Path(path_str).match(pattern):
                    return True
            # Handle exact matches
            elif path_str == pattern or path_str.startswith(pattern + "/"):
                return True
        return False
    
    def _get_sync_strategy(self, relative_path: Path) -> str:
        """Determine the sync strategy for a given path.
        
        Args:
            relative_path: Path relative to subspace root
            
        Returns:
            One of: 'template_owned', 'cyber_owned', 'merge', 'skip'
        """
        path_str = str(relative_path)
        
        # Check ignore patterns first
        if self._is_path_matched(relative_path, self.config["ignore_patterns"]):
            return "skip"
        
        # Check each strategy
        if self._is_path_matched(relative_path, self.config["template_owned"]):
            return "template_owned"
        elif self._is_path_matched(relative_path, self.config["cyber_owned"]):
            return "cyber_owned"
        elif self._is_path_matched(relative_path, self.config["merge_required"]):
            return "merge"
        
        # Default to merge for safety
        return "merge"
    
    def _sync_template_owned(self, relative_path: Path) -> bool:
        """Sync a template-owned path (always overwrite from template).
        
        Args:
            relative_path: Path relative to root directories
            
        Returns:
            True if successful
        """
        template_full = self.template_path / relative_path
        subspace_full = self.subspace_path / relative_path
        
        if not template_full.exists():
            logger.debug(f"Template path doesn't exist: {relative_path}")
            return True
        
        logger.info(f"Syncing template-owned: {relative_path}")
        
        if not self.dry_run:
            # Remove existing and copy from template
            if subspace_full.exists():
                if subspace_full.is_dir():
                    shutil.rmtree(subspace_full)
                else:
                    subspace_full.unlink()
            
            # Copy from template
            if template_full.is_dir():
                shutil.copytree(template_full, subspace_full)
            else:
                subspace_full.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(template_full, subspace_full)
        
        return True
    
    def _sync_with_merge(self, relative_path: Path) -> bool:
        """Sync a path that requires merging.
        
        Args:
            relative_path: Path relative to root directories
            
        Returns:
            True if successful
        """
        template_full = self.template_path / relative_path
        subspace_full = self.subspace_path / relative_path
        
        if not template_full.exists():
            logger.debug(f"Template path doesn't exist: {relative_path}")
            return True
        
        logger.info(f"Merging changes for: {relative_path}")
        
        if not self.dry_run:
            # If it doesn't exist in subspace, just copy
            if not subspace_full.exists():
                if template_full.is_dir():
                    shutil.copytree(template_full, subspace_full)
                else:
                    subspace_full.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(template_full, subspace_full)
                return True
            
            # For directories, merge contents
            if template_full.is_dir() and subspace_full.is_dir():
                # Recursively sync directory contents
                for item in template_full.iterdir():
                    item_relative = relative_path / item.name
                    strategy = self._get_sync_strategy(item_relative)
                    
                    if strategy == "template_owned":
                        self._sync_template_owned(item_relative)
                    elif strategy != "cyber_owned":
                        self._sync_with_merge(item_relative)
            
            # For files, check if they differ
            elif template_full.is_file() and subspace_full.is_file():
                template_content = template_full.read_bytes()
                subspace_content = subspace_full.read_bytes()
                
                if template_content != subspace_content:
                    # Create a conflict file for manual resolution
                    conflict_path = subspace_full.with_suffix(
                        subspace_full.suffix + ".template_conflict"
                    )
                    shutil.copy2(template_full, conflict_path)
                    logger.warning(
                        f"Merge conflict for {relative_path}. "
                        f"Template version saved to {conflict_path.name}"
                    )
        
        return True
    
    def _handle_initial_cyber_owned(self, relative_path: Path) -> bool:
        """Handle initial creation of cyber-owned directories that exist in template.
        
        This is needed for directories like new_cyber_introduction which are 
        cyber-owned but need to be initially copied from the template.
        
        Args:
            relative_path: Path relative to root directories
            
        Returns:
            True if successful
        """
        template_full = self.template_path / relative_path
        subspace_full = self.subspace_path / relative_path
        
        # Only copy if it exists in template but not in subspace
        if template_full.exists() and not subspace_full.exists():
            logger.info(f"Initial creation of cyber-owned path: {relative_path}")
            
            if not self.dry_run:
                if template_full.is_dir():
                    shutil.copytree(template_full, subspace_full)
                else:
                    subspace_full.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(template_full, subspace_full)
            
            return True
        
        return False
    
    def sync(self) -> bool:
        """Perform the sync operation.
        
        Returns:
            True if successful
        """
        logger.info("Starting subspace sync...")
        
        if self.dry_run:
            logger.info("Running in DRY RUN mode - no changes will be made")
        
        # Initialize git if needed
        if not self.init_subspace_git():
            return False
        
        # Create a commit before sync
        if not self.dry_run:
            self._run_git_command(["add", "."], self.subspace_path)
            self._run_git_command(
                ["commit", "-m", f"Pre-sync snapshot {datetime.now().isoformat()}"],
                self.subspace_path
            )
        
        # Track what we've processed
        processed_paths: Set[Path] = set()
        
        # Process template-owned paths
        for pattern in self.config["template_owned"]:
            # Find actual paths matching the pattern
            base_pattern = pattern.replace("/*", "")
            base_path = self.template_path / base_pattern
            
            if base_path.exists():
                relative = Path(base_pattern)
                if relative not in processed_paths:
                    self._sync_template_owned(relative)
                    processed_paths.add(relative)
        
        # Process merge-required paths
        for pattern in self.config["merge_required"]:
            base_pattern = pattern.replace("/*", "")
            base_path = self.template_path / base_pattern
            
            if base_path.exists():
                relative = Path(base_pattern)
                if relative not in processed_paths:
                    self._sync_with_merge(relative)
                    processed_paths.add(relative)
        
        # Handle initial creation of cyber-owned paths that exist in template
        # This is important for directories like new_cyber_introduction
        for pattern in self.config.get("cyber_owned", []):
            # Skip wildcard patterns for initial creation
            if "*" in pattern:
                continue
            
            base_path = self.template_path / pattern
            if base_path.exists():
                relative = Path(pattern)
                if relative not in processed_paths:
                    self._handle_initial_cyber_owned(relative)
                    processed_paths.add(relative)
        
        # Commit changes
        if not self.dry_run:
            self._run_git_command(["add", "."], self.subspace_path)
            self._run_git_command(
                ["commit", "-m", f"Sync from template {datetime.now().isoformat()}"],
                self.subspace_path
            )
        
        logger.info("Subspace sync completed successfully")
        return True
    
    def create_backup(self) -> Optional[Path]:
        """Create a backup of the current subspace.
        
        Returns:
            Path to backup directory if successful
        """
        if self.dry_run:
            logger.info("[DRY RUN] Would create backup")
            return None
        
        backup_root = self.subspace_path.parent / "subspace_backups"
        backup_root.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_root / f"backup_{timestamp}"
        
        logger.info(f"Creating backup at {backup_path}")
        shutil.copytree(self.subspace_path, backup_path)
        
        return backup_path


def main():
    """Main entry point for the sync script."""
    parser = argparse.ArgumentParser(
        description="Sync subspace with template while preserving Cyber contributions"
    )
    parser.add_argument(
        "--subspace",
        type=Path,
        help="Path to subspace directory (default: ./subspace)",
        default=Path.cwd() / "subspace"
    )
    parser.add_argument(
        "--template",
        type=Path,
        help="Path to template directory (default: ./subspace_template)",
        default=Path.cwd() / "subspace_template"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to sync configuration file",
        default=Path.cwd() / "config" / "subspace_sync.yaml"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create backup before syncing"
    )
    
    args = parser.parse_args()
    
    # Validate paths
    if not args.template.exists():
        print(f"Template directory not found: {args.template}")
        sys.exit(1)
    
    if not args.subspace.exists():
        print(f"Subspace directory not found: {args.subspace}")
        sys.exit(1)
    
    # Create sync manager
    sync_manager = SubspaceSync(
        subspace_path=args.subspace,
        template_path=args.template,
        config_path=args.config if args.config.exists() else None,
        dry_run=args.dry_run
    )
    
    # Create backup if requested
    if args.backup:
        backup_path = sync_manager.create_backup()
        if backup_path:
            print(f"Backup created at: {backup_path}")
    
    # Perform sync
    if sync_manager.sync():
        print("Sync completed successfully")
    else:
        print("Sync failed")
        sys.exit(1)


if __name__ == "__main__":
    main()