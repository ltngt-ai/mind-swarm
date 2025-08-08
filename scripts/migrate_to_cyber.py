#!/usr/bin/env python3
"""Migration script to refactor Mind-Swarm terminology and structure.

This script handles:
1. Renaming Cybers -> cybers
2. Renaming home -> personal  
3. Reorganizing grid library knowledge
4. Renaming plaza -> community
5. Moving logs to personal folders
6. Removing cyber_states directory
"""

import os
import shutil
import json
import yaml
from pathlib import Path
from typing import Dict, List, Any
import argparse
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MindSwarmMigration:
    """Handles migration of Mind-Swarm structure and terminology."""
    
    def __init__(self, project_root: Path, dry_run: bool = False):
        """Initialize migration.
        
        Args:
            project_root: Root directory of the project
            dry_run: If True, only show what would be done
        """
        self.project_root = project_root
        self.dry_run = dry_run
        self.subspace_dir = project_root / "subspace"
        self.template_dir = project_root / "subspace_template"
        
        # Track changes for reporting
        self.changes = {
            "renamed_dirs": [],
            "moved_files": [],
            "updated_files": [],
            "removed": []
        }
    
    def migrate_filesystem(self):
        """Migrate the filesystem structure."""
        logger.info("Starting filesystem migration...")
        
        # 1. Rename Cybers -> cybers
        self._rename_agents_to_cybers()
        
        # 2. Reorganize grid library
        self._reorganize_grid_library()
        
        # 3. Rename plaza -> community and integrate bulletin
        self._rename_plaza_to_community()
        
        # 4. Move logs to personal folders
        self._move_logs_to_personal()
        
        # 5. Remove cyber_states directory
        self._remove_agent_states()
        
        logger.info("Filesystem migration complete")
    
    def _rename_agents_to_cybers(self):
        """Rename Cybers directory to cybers."""
        for base_dir in [self.subspace_dir, self.template_dir]:
            agents_dir = base_dir / "cybers"
            cybers_dir = base_dir / "cybers"
            
            if agents_dir.exists():
                if self.dry_run:
                    logger.info(f"[DRY RUN] Would rename {agents_dir} -> {cybers_dir}")
                else:
                    shutil.move(str(agents_dir), str(cybers_dir))
                    logger.info(f"Renamed {agents_dir} -> {cybers_dir}")
                self.changes["renamed_dirs"].append((str(agents_dir), str(cybers_dir)))
    
    def _reorganize_grid_library(self):
        """Reorganize grid library to have knowledge section."""
        for base_dir in [self.subspace_dir, self.template_dir]:
            library_dir = base_dir / "grid" / "library"
            if not library_dir.exists():
                continue
                
            knowledge_dir = library_dir / "knowledge"
            
            # Create knowledge structure
            if self.dry_run:
                logger.info(f"[DRY RUN] Would create {knowledge_dir}")
            else:
                knowledge_dir.mkdir(parents=True, exist_ok=True)
                
            # Move actions, rom, models to knowledge/sections
            sections_dir = knowledge_dir / "sections"
            if not self.dry_run:
                sections_dir.mkdir(parents=True, exist_ok=True)
            
            for subdir in ["actions", "rom", "models"]:
                src = library_dir / subdir
                dst = sections_dir / subdir
                
                if src.exists():
                    if self.dry_run:
                        logger.info(f"[DRY RUN] Would move {src} -> {dst}")
                    else:
                        shutil.move(str(src), str(dst))
                        logger.info(f"Moved {src} -> {dst}")
                    self.changes["moved_files"].append((str(src), str(dst)))
            
            # Move schema files to knowledge/schemas
            schemas_dir = knowledge_dir / "schemas"
            if not self.dry_run:
                schemas_dir.mkdir(parents=True, exist_ok=True)
                
            for schema_file in ["KNOWLEDGE_SCHEMA.md", "action_execution.md"]:
                src = library_dir / schema_file
                if src.exists():
                    dst = schemas_dir / schema_file
                    if self.dry_run:
                        logger.info(f"[DRY RUN] Would move {src} -> {dst}")
                    else:
                        shutil.move(str(src), str(dst))
                        logger.info(f"Moved {src} -> {dst}")
                    self.changes["moved_files"].append((str(src), str(dst)))
    
    def _rename_plaza_to_community(self):
        """Rename plaza to community and integrate bulletin."""
        for base_dir in [self.subspace_dir, self.template_dir]:
            grid_dir = base_dir / "grid"
            if not grid_dir.exists():
                continue
                
            community_dir = grid_dir / "community"
            community_dir = grid_dir / "community"
            bulletin_dir = grid_dir / "bulletin"
            
            # Rename plaza -> community
            if community_dir.exists():
                if self.dry_run:
                    logger.info(f"[DRY RUN] Would rename {community_dir} -> {community_dir}")
                else:
                    shutil.move(str(community_dir), str(community_dir))
                    logger.info(f"Renamed {community_dir} -> {community_dir}")
                self.changes["renamed_dirs"].append((str(community_dir), str(community_dir)))
            
            # Move bulletin into community
            if bulletin_dir.exists():
                dst = community_dir / "bulletin"
                if self.dry_run:
                    logger.info(f"[DRY RUN] Would move {bulletin_dir} -> {dst}")
                else:
                    if not community_dir.exists():
                        community_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(bulletin_dir), str(dst))
                    logger.info(f"Moved {bulletin_dir} -> {dst}")
                self.changes["moved_files"].append((str(bulletin_dir), str(dst)))
            
            # Rename cyber_directory.json -> cyber_directory.json
            if community_dir.exists():
                agent_dir_file = community_dir / "cyber_directory.json"
                cyber_dir_file = community_dir / "cyber_directory.json"
                
                if agent_dir_file.exists():
                    if self.dry_run:
                        logger.info(f"[DRY RUN] Would rename {agent_dir_file} -> {cyber_dir_file}")
                    else:
                        agent_dir_file.rename(cyber_dir_file)
                        logger.info(f"Renamed {agent_dir_file} -> {cyber_dir_file}")
                    self.changes["renamed_dirs"].append((str(agent_dir_file), str(cyber_dir_file)))
    
    def _move_logs_to_personal(self):
        """Move logs from central location to personal folders."""
        logs_dir = self.subspace_dir / "logs" / "cybers"
        cybers_dir = self.subspace_dir / "cybers"
        
        if logs_dir.exists():
            for agent_log_dir in logs_dir.iterdir():
                if agent_log_dir.is_dir():
                    cyber_name = agent_log_dir.name
                    cyber_dir = cybers_dir / cyber_name
                    
                    if cyber_dir.exists():
                        dst = cyber_dir / "logs"
                        if self.dry_run:
                            logger.info(f"[DRY RUN] Would move {agent_log_dir} -> {dst}")
                        else:
                            shutil.move(str(agent_log_dir), str(dst))
                            logger.info(f"Moved {agent_log_dir} -> {dst}")
                        self.changes["moved_files"].append((str(agent_log_dir), str(dst)))
            
            # Remove empty logs directory structure
            if not self.dry_run:
                try:
                    (self.subspace_dir / "logs" / "cybers").rmdir()
                    (self.subspace_dir / "logs").rmdir()
                    logger.info("Removed empty logs directory")
                except OSError:
                    pass  # Directory not empty or doesn't exist
    
    def _remove_agent_states(self):
        """Remove the cyber_states directory."""
        agent_states_dir = self.subspace_dir / "cyber_states"
        
        if agent_states_dir.exists():
            if self.dry_run:
                logger.info(f"[DRY RUN] Would remove {agent_states_dir}")
            else:
                shutil.rmtree(agent_states_dir)
                logger.info(f"Removed {agent_states_dir}")
            self.changes["removed"].append(str(agent_states_dir))
    
    def update_knowledge_files(self):
        """Update knowledge files to remove IDs and use memory IDs."""
        for base_dir in [self.subspace_dir, self.template_dir]:
            knowledge_dir = base_dir / "grid" / "library" / "knowledge" / "sections"
            
            if not knowledge_dir.exists():
                continue
            
            # Process all YAML files in knowledge sections
            for yaml_file in knowledge_dir.rglob("*.yaml"):
                if self._update_knowledge_file(yaml_file):
                    self.changes["updated_files"].append(str(yaml_file))
    
    def _update_knowledge_file(self, file_path: Path) -> bool:
        """Update a single knowledge file.
        
        Args:
            file_path: Path to the knowledge file
            
        Returns:
            True if file was updated
        """
        try:
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
            
            if not isinstance(data, dict):
                return False
            
            # Remove 'id' field if present
            updated = False
            if 'id' in data:
                if self.dry_run:
                    logger.info(f"[DRY RUN] Would remove 'id' field from {file_path}")
                else:
                    del data['id']
                    updated = True
            
            # Update 'knowledge_id' to 'memory_id' if present
            if 'knowledge_id' in data:
                if self.dry_run:
                    logger.info(f"[DRY RUN] Would rename 'knowledge_id' to 'memory_id' in {file_path}")
                else:
                    data['memory_id'] = data.pop('knowledge_id')
                    updated = True
            
            if updated and not self.dry_run:
                with open(file_path, 'w') as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
                logger.info(f"Updated {file_path}")
            
            return updated
            
        except Exception as e:
            logger.warning(f"Could not update {file_path}: {e}")
            return False
    
    def print_summary(self):
        """Print summary of changes."""
        print("\n" + "="*60)
        print("MIGRATION SUMMARY")
        print("="*60)
        
        if self.dry_run:
            print("\n[DRY RUN MODE - No actual changes made]")
        
        print(f"\nRenamed directories: {len(self.changes['renamed_dirs'])}")
        for src, dst in self.changes['renamed_dirs'][:5]:
            print(f"  {Path(src).name} -> {Path(dst).name}")
        
        print(f"\nMoved files/directories: {len(self.changes['moved_files'])}")
        for src, dst in self.changes['moved_files'][:5]:
            print(f"  {Path(src).relative_to(self.project_root)} -> {Path(dst).relative_to(self.project_root)}")
        
        print(f"\nUpdated files: {len(self.changes['updated_files'])}")
        for file_path in self.changes['updated_files'][:5]:
            print(f"  {Path(file_path).relative_to(self.project_root)}")
        
        print(f"\nRemoved: {len(self.changes['removed'])}")
        for path in self.changes['removed']:
            print(f"  {Path(path).relative_to(self.project_root)}")
        
        print("\n" + "="*60)
    
    def run(self):
        """Run the complete migration."""
        logger.info("Starting Mind-Swarm migration...")
        
        # Filesystem changes
        self.migrate_filesystem()
        
        # Update knowledge files
        self.update_knowledge_files()
        
        # Print summary
        self.print_summary()
        
        logger.info("Migration complete!")
        
        if not self.dry_run:
            print("\nNOTE: You still need to:")
            print("1. Update Python source files (use migrate_source_code.py)")
            print("2. Update configuration files")
            print("3. Run tests to verify everything works")


def main():
    parser = argparse.ArgumentParser(description="Migrate Mind-Swarm structure and terminology")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--project-root", type=Path, default=Path.cwd(), help="Project root directory")
    
    args = parser.parse_args()
    
    migration = MindSwarmMigration(args.project_root, args.dry_run)
    migration.run()


if __name__ == "__main__":
    main()