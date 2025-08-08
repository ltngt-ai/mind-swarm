#!/usr/bin/env python3
"""Migration script to update Mind-Swarm source code terminology.

This script handles:
1. Renaming Cyber -> Cyber in all Python files
2. Renaming home -> personal in paths
3. Updating memory ID prefixes
4. Updating imports and module names
"""

import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Set
import argparse
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SourceCodeMigration:
    """Handles migration of Mind-Swarm source code."""
    
    # Mapping of old terms to new terms
    TERM_MAPPINGS = {
        # Class names
        r'\bAgentType\b': 'CyberType',
        r'\bAgentTypeConfig\b': 'CyberTypeConfig',
        r'\bAgentInfo\b': 'CyberInfo',
        r'\bAgentRegistry\b': 'CyberRegistry',
        r'\bAgentSpawner\b': 'CyberSpawner',
        r'\bAgentState\b': 'CyberState',
        r'\bAgentStateManager\b': 'CyberStateManager',
        r'\bget_agent_type_config\b': 'get_cyber_type_config',
        
        # Variable names (more specific patterns)
        r'\bagent_type\b': 'cyber_type',
        r'\bagent_name\b': 'cyber_name',
        r'\bagent_id\b': 'cyber_id',
        r'\bagent_config\b': 'cyber_config',
        r'\bagent_states\b': 'cyber_states',
        r'\bagent_info\b': 'cyber_info',
        r'\bagent_data\b': 'cyber_data',
        r'\bagent_dir\b': 'cyber_dir',
        r'\bagent_home\b': 'cyber_personal',
        r'\bself\.Cyber\b': 'self.cyber',
        r'\bself\.Cybers\b': 'self.cybers',
        r'\b_agents\b': '_cybers',
        r'\b_agent\b': '_cyber',
        
        # String literals and paths
        r'"/cybers/"': '"/cybers/"',
        r"'/cybers/'": "'/cybers/'",
        r'"/cyber_states/"': '"/cyber_states/"',
        r"'/cyber_states/'": "'/cyber_states/'",
        r'"cyber_states"': '"cyber_states"',
        r"'cyber_states'": "'cyber_states'",
        r'"cybers"': '"cybers"',
        r"'cybers'": "'cybers'",
        r'"cyber"': '"cyber"',
        r"'cyber'": "'cyber'",
        
        # Home -> Personal
        r'"/personal/"': '"/personal/"',
        r"'/personal/'": "'/personal/'",
        r'"/personal\b': '"/personal',
        r"'/personal\b": "'/personal",
        r'\bhome_dir\b': 'personal_dir',
        r'\bagent_home\b': 'cyber_personal',
        
        # Plaza -> Community
        r'"/community/"': '"/community/"',
        r"'/community/'": "'/community/'",
        r'"community"': '"community"',
        r"'community'": "'community'",
        r'\bplaza_dir\b': 'community_dir',
        
        # File references
        r'agent_directory\.json': 'cyber_directory.json',
        r'agent_types\.py': 'cyber_types.py',
        r'agent_spawner\.py': 'cyber_spawner.py',
        r'agent_registry\.py': 'cyber_registry.py',
        r'agent_state\.py': 'cyber_state.py',
        
        # IO Cyber -> IO Cyber
        r'\bio_agent\b': 'io_cyber',
        r'\bio_agents\b': 'io_cybers',
        r'io_cyber_template': 'io_cyber_template',
        r'IO_GATEWAY': 'IO_GATEWAY',  # Keep enum value for now
        
        # Comments and docstrings (case-insensitive for these)
        r'(?i)\b(an?\s+)?Cyber\b': r'\1Cyber',
        r'(?i)\bagents\b': 'Cybers',
    }
    
    # Files to rename
    FILE_RENAMES = {
        'cyber_types.py': 'cyber_types.py',
        'cyber_spawner.py': 'cyber_spawner.py',
        'cyber_registry.py': 'cyber_registry.py',
        'cyber_state.py': 'cyber_state.py',
        'test_agent_startup.py': 'test_cyber_startup.py',
        'test_agent_thinking.py': 'test_cyber_thinking.py',
        'test_agent_thinking_e2e.py': 'test_cyber_thinking_e2e.py',
    }
    
    # Directory renames
    DIR_RENAMES = {
        'io_cyber_template': 'io_cyber_template',
    }
    
    def __init__(self, project_root: Path, dry_run: bool = False):
        """Initialize migration.
        
        Args:
            project_root: Root directory of the project
            dry_run: If True, only show what would be done
        """
        self.project_root = project_root
        self.dry_run = dry_run
        self.changes = {
            "updated_files": [],
            "renamed_files": [],
            "renamed_dirs": [],
        }
    
    def update_python_files(self):
        """Update all Python files with new terminology."""
        logger.info("Updating Python source files...")
        
        # Process src directory
        src_dir = self.project_root / "src" / "mind_swarm"
        if src_dir.exists():
            self._process_directory(src_dir)
        
        # Process tests directory
        tests_dir = self.project_root / "tests"
        if tests_dir.exists():
            self._process_directory(tests_dir)
        
        # Process runtime templates
        for template_base in ["subspace_template", "subspace"]:
            template_dir = self.project_root / template_base / "grid" / "library" / "base_code"
            if template_dir.exists():
                self._process_directory(template_dir)
        
        # Process scripts
        scripts_dir = self.project_root / "scripts"
        if scripts_dir.exists():
            self._process_directory(scripts_dir)
    
    def _process_directory(self, directory: Path):
        """Process all Python files in a directory.
        
        Args:
            directory: Directory to process
        """
        for py_file in directory.rglob("*.py"):
            if self._update_file(py_file):
                self.changes["updated_files"].append(str(py_file))
    
    def _update_file(self, file_path: Path) -> bool:
        """Update a single Python file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file was updated
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Apply all term mappings
            for pattern, replacement in self.TERM_MAPPINGS.items():
                content = re.sub(pattern, replacement, content)
            
            # Special case: Update import statements
            content = self._update_imports(content)
            
            # Special case: Update memory ID creation
            content = self._update_memory_ids(content)
            
            if content != original_content:
                if self.dry_run:
                    logger.info(f"[DRY RUN] Would update {file_path}")
                else:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logger.info(f"Updated {file_path}")
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Could not update {file_path}: {e}")
            return False
    
    def _update_imports(self, content: str) -> str:
        """Update import statements.
        
        Args:
            content: File content
            
        Returns:
            Updated content
        """
        # Update module imports
        content = re.sub(
            r'from ([\w\.]+)\.agent_types import',
            r'from \1.cyber_types import',
            content
        )
        content = re.sub(
            r'from ([\w\.]+)\.agent_spawner import',
            r'from \1.cyber_spawner import',
            content
        )
        content = re.sub(
            r'from ([\w\.]+)\.agent_registry import',
            r'from \1.cyber_registry import',
            content
        )
        content = re.sub(
            r'from ([\w\.]+)\.agent_state import',
            r'from \1.cyber_state import',
            content
        )
        
        # Update relative imports in templates
        content = re.sub(
            r'from \.io_cyber_template',
            r'from .io_cyber_template',
            content
        )
        
        return content
    
    def _update_memory_ids(self, content: str) -> str:
        """Update memory ID creation to include prefixes.
        
        Args:
            content: File content
            
        Returns:
            Updated content
        """
        # This is complex and needs careful handling
        # We'll update the UnifiedMemoryID class specifically
        
        if 'class UnifiedMemoryID' in content:
            # Update the create method to add prefixes
            content = re.sub(
                r'def create\((.*?)\) -> str:(.*?)return f"\{type_str\}:\{namespace\}:\{semantic_path\}"',
                r'def create(\1) -> str:\2'
                r'        # Add prefix based on namespace\n'
                r'        if namespace in ["personal", "inbox", "outbox"]:\n'
                r'            prefix = "personal"\n'
                r'        else:\n'
                r'            prefix = "grid"\n'
                r'        return f"{prefix}:{type_str}:{namespace}:{semantic_path}"',
                content,
                flags=re.DOTALL
            )
        
        return content
    
    def rename_files_and_dirs(self):
        """Rename files and directories."""
        logger.info("Renaming files and directories...")
        
        # Rename directories first
        for old_name, new_name in self.DIR_RENAMES.items():
            self._rename_directory(old_name, new_name)
        
        # Then rename files
        for old_name, new_name in self.FILE_RENAMES.items():
            self._rename_file(old_name, new_name)
    
    def _rename_directory(self, old_name: str, new_name: str):
        """Rename a directory throughout the project.
        
        Args:
            old_name: Old directory name
            new_name: New directory name
        """
        for root, dirs, _ in os.walk(self.project_root):
            if old_name in dirs:
                old_path = Path(root) / old_name
                new_path = Path(root) / new_name
                
                if self.dry_run:
                    logger.info(f"[DRY RUN] Would rename {old_path} -> {new_path}")
                else:
                    old_path.rename(new_path)
                    logger.info(f"Renamed {old_path} -> {new_path}")
                
                self.changes["renamed_dirs"].append((str(old_path), str(new_path)))
    
    def _rename_file(self, old_name: str, new_name: str):
        """Rename a file throughout the project.
        
        Args:
            old_name: Old file name
            new_name: New file name
        """
        for root, _, files in os.walk(self.project_root):
            if old_name in files:
                old_path = Path(root) / old_name
                new_path = Path(root) / new_name
                
                if self.dry_run:
                    logger.info(f"[DRY RUN] Would rename {old_path} -> {new_path}")
                else:
                    old_path.rename(new_path)
                    logger.info(f"Renamed {old_path} -> {new_path}")
                
                self.changes["renamed_files"].append((str(old_path), str(new_path)))
    
    def update_yaml_files(self):
        """Update YAML configuration files."""
        logger.info("Updating YAML files...")
        
        yaml_files = [
            self.project_root / "ai_presets.yaml",
            self.project_root / "config" / "blacklist_models.yaml",
            self.project_root / "config" / "curated_models.yaml",
        ]
        
        # Add all YAML files in templates
        for template_base in ["subspace_template", "subspace"]:
            template_dir = self.project_root / template_base
            if template_dir.exists():
                yaml_files.extend(template_dir.rglob("*.yaml"))
                yaml_files.extend(template_dir.rglob("*.yml"))
        
        for yaml_file in yaml_files:
            if yaml_file.exists():
                self._update_yaml_file(yaml_file)
    
    def _update_yaml_file(self, file_path: Path):
        """Update a YAML file.
        
        Args:
            file_path: Path to YAML file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Apply replacements
            content = content.replace('cyber', 'cyber')
            content = content.replace('Cyber', 'Cyber')
            content = content.replace('Cyber', 'CYBER')
            content = content.replace('/personal/', '/personal/')
            content = content.replace('/community/', '/community/')
            content = content.replace('plaza:', 'community:')
            
            if content != original_content:
                if self.dry_run:
                    logger.info(f"[DRY RUN] Would update {file_path}")
                else:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logger.info(f"Updated {file_path}")
                self.changes["updated_files"].append(str(file_path))
                
        except Exception as e:
            logger.warning(f"Could not update {file_path}: {e}")
    
    def update_markdown_files(self):
        """Update markdown documentation files."""
        logger.info("Updating documentation files...")
        
        md_files = list(self.project_root.rglob("*.md"))
        
        for md_file in md_files:
            if '.git' not in str(md_file):
                self._update_markdown_file(md_file)
    
    def _update_markdown_file(self, file_path: Path):
        """Update a markdown file.
        
        Args:
            file_path: Path to markdown file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Apply replacements (be more careful with markdown)
            content = re.sub(r'\bagent\b', 'cyber', content, flags=re.IGNORECASE)
            content = re.sub(r'\bagents\b', 'cybers', content, flags=re.IGNORECASE)
            content = re.sub(r'\bAgent\b', 'Cyber', content)
            content = re.sub(r'\bAgents\b', 'Cybers', content)
            content = content.replace('/personal/', '/personal/')
            content = content.replace('/community/', '/community/')
            content = content.replace('cyber_states', 'cyber_states')
            
            if content != original_content:
                if self.dry_run:
                    logger.info(f"[DRY RUN] Would update {file_path}")
                else:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logger.info(f"Updated {file_path}")
                self.changes["updated_files"].append(str(file_path))
                
        except Exception as e:
            logger.warning(f"Could not update {file_path}: {e}")
    
    def print_summary(self):
        """Print summary of changes."""
        print("\n" + "="*60)
        print("SOURCE CODE MIGRATION SUMMARY")
        print("="*60)
        
        if self.dry_run:
            print("\n[DRY RUN MODE - No actual changes made]")
        
        print(f"\nUpdated files: {len(self.changes['updated_files'])}")
        for file_path in self.changes['updated_files'][:10]:
            print(f"  {Path(file_path).relative_to(self.project_root)}")
        if len(self.changes['updated_files']) > 10:
            print(f"  ... and {len(self.changes['updated_files']) - 10} more")
        
        print(f"\nRenamed files: {len(self.changes['renamed_files'])}")
        for old, new in self.changes['renamed_files']:
            print(f"  {Path(old).name} -> {Path(new).name}")
        
        print(f"\nRenamed directories: {len(self.changes['renamed_dirs'])}")
        for old, new in self.changes['renamed_dirs']:
            print(f"  {Path(old).name} -> {Path(new).name}")
        
        print("\n" + "="*60)
    
    def run(self):
        """Run the complete source code migration."""
        logger.info("Starting source code migration...")
        
        # First rename files and directories
        self.rename_files_and_dirs()
        
        # Then update file contents
        self.update_python_files()
        self.update_yaml_files()
        self.update_markdown_files()
        
        # Print summary
        self.print_summary()
        
        logger.info("Source code migration complete!")
        
        if not self.dry_run:
            print("\nNOTE: Next steps:")
            print("1. Run the tests to verify everything works")
            print("2. Update any remaining configuration")
            print("3. Commit the changes")


def main():
    parser = argparse.ArgumentParser(description="Migrate Mind-Swarm source code terminology")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--project-root", type=Path, default=Path.cwd(), help="Project root directory")
    
    args = parser.parse_args()
    
    migration = SourceCodeMigration(args.project_root, args.dry_run)
    migration.run()


if __name__ == "__main__":
    main()