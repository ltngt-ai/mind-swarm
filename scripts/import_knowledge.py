#!/usr/bin/env python3
"""Import knowledge from YAML files into ChromaDB.

This script imports knowledge from YAML files (e.g., from template or exports)
into the ChromaDB knowledge database.
"""

import argparse
import asyncio
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

# Add parent directory to path for imports
import sys
sys.path.append(str(Path(__file__).parent.parent))

from src.mind_swarm.subspace.knowledge_handler import KnowledgeHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class KnowledgeImporter:
    """Import knowledge from filesystem to ChromaDB."""
    
    def __init__(self, subspace_root: Path):
        """Initialize the importer.
        
        Args:
            subspace_root: Path to the subspace root directory
        """
        self.subspace_root = Path(subspace_root)
        self.knowledge_handler = None
        
    def initialize(self):
        """Initialize the knowledge handler."""
        self.knowledge_handler = KnowledgeHandler(
            subspace_root=self.subspace_root
        )
        logger.info("Knowledge handler initialized")
        
    async def import_file(self, file_path: Path, knowledge_id: Optional[str] = None) -> bool:
        """Import a single YAML knowledge file.
        
        Args:
            file_path: Path to the YAML file to import
            knowledge_id: Optional ID to use for the knowledge (defaults to filename)
            
        Returns:
            True if import was successful
        """
        if not self.knowledge_handler:
            self.initialize()
            
        try:
            # Read and parse YAML file
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
            
            if not isinstance(data, dict):
                logger.error(f"Invalid YAML structure in {file_path}: expected dictionary")
                return False
            
            # Remove export metadata if present
            if '_export_metadata' in data:
                export_meta = data.pop('_export_metadata')
                if not knowledge_id and 'id' in export_meta:
                    knowledge_id = export_meta['id']
            
            # Use filename as ID if not specified
            if not knowledge_id:
                knowledge_id = file_path.stem
                if file_path.parent.name not in ['all', 'by_category', 'by_tags', 'by_cyber']:
                    # Include parent directory in ID for better organization
                    knowledge_id = f"{file_path.parent.name}/{knowledge_id}"
            
            # Extract metadata
            metadata = {
                "title": data.get('title', knowledge_id),
                "tags": data.get('tags', []),
                "category": data.get('category', 'imported'),
                "source": data.get('source', str(file_path)),
                "imported_at": datetime.now().isoformat(),
                "imported_by": "import_tool"
            }
            
            # The content should be the full YAML document
            content = yaml.dump(data, default_flow_style=False, sort_keys=False)
            
            # Store in ChromaDB
            success, message = await self.knowledge_handler.add_shared_knowledge_with_id(
                knowledge_id=knowledge_id,
                content=content,
                metadata=metadata
            )
            
            if success:
                logger.info(f"✓ Imported: {knowledge_id}")
                return True
            else:
                logger.error(f"Failed to import {knowledge_id}: {message}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to import {file_path}: {e}")
            return False
    
    async def import_directory(self, dir_path: Path, recursive: bool = True) -> Dict[str, Any]:
        """Import all YAML files from a directory.
        
        Args:
            dir_path: Directory containing YAML files
            recursive: Whether to search subdirectories
            
        Returns:
            Dictionary with import statistics
        """
        if not self.knowledge_handler:
            self.initialize()
            
        stats = {
            "total_files": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0
        }
        
        # Find all YAML files
        pattern = "**/*.yaml" if recursive else "*.yaml"
        yaml_files = list(dir_path.glob(pattern))
        pattern = "**/*.yml" if recursive else "*.yml"
        yaml_files.extend(list(dir_path.glob(pattern)))
        
        stats["total_files"] = len(yaml_files)
        logger.info(f"Found {len(yaml_files)} YAML files to import")
        
        for i, file_path in enumerate(yaml_files, 1):
            # Skip certain files
            if file_path.name in ['export_summary.yaml', '.description.yaml']:
                stats["skipped"] += 1
                logger.debug(f"Skipped: {file_path.name}")
                continue
            
            # Generate knowledge ID based on relative path
            try:
                rel_path = file_path.relative_to(dir_path)
                # Remove common export directory names
                parts = rel_path.parts
                if parts[0] in ['all', 'by_category', 'by_tags', 'by_cyber']:
                    parts = parts[1:]
                knowledge_id = '/'.join(parts).replace('.yaml', '').replace('.yml', '')
            except:
                knowledge_id = None
            
            # Import the file
            success = await self.import_file(file_path, knowledge_id)
            if success:
                stats["successful"] += 1
            else:
                stats["failed"] += 1
            
            if i % 10 == 0:
                logger.info(f"Progress: {i}/{len(yaml_files)} files processed...")
        
        return stats
    
    async def import_template_knowledge(self) -> Dict[str, Any]:
        """Import knowledge from the subspace template initial_knowledge directory.
        
        Returns:
            Dictionary with import statistics
        """
        # Find template knowledge directory
        template_dir = Path(__file__).parent.parent / "subspace_template" / "initial_knowledge"
        
        if not template_dir.exists():
            logger.error(f"Template knowledge directory not found: {template_dir}")
            return {"error": "Template directory not found"}
        
        logger.info(f"Importing knowledge from template: {template_dir}")
        return await self.import_directory(template_dir, recursive=True)
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.knowledge_handler:
            self.knowledge_handler = None


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Import knowledge into ChromaDB")
    import os
    # Use SUBSPACE_ROOT env var if set, otherwise use /home/mind/subspace
    default_subspace = Path(os.environ.get("SUBSPACE_ROOT", "/home/mind/subspace"))
    
    parser.add_argument(
        "--subspace-root",
        type=Path,
        default=default_subspace,
        help=f"Path to subspace root directory (default: {default_subspace})"
    )
    
    # Import source - mutually exclusive group
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--file",
        type=Path,
        help="Import a single YAML file"
    )
    source_group.add_argument(
        "--directory",
        type=Path,
        help="Import all YAML files from a directory"
    )
    source_group.add_argument(
        "--template",
        action="store_true",
        help="Import knowledge from subspace_template/initial_knowledge"
    )
    
    parser.add_argument(
        "--recursive",
        action="store_true",
        default=True,
        help="Search subdirectories when importing from directory (default: True)"
    )
    parser.add_argument(
        "--knowledge-id",
        type=str,
        help="Specific knowledge ID to use (only for single file import)"
    )
    
    args = parser.parse_args()
    
    # Verify subspace root exists
    if not args.subspace_root.exists():
        logger.error(f"Subspace root does not exist: {args.subspace_root}")
        sys.exit(1)
    
    # Create importer
    importer = KnowledgeImporter(args.subspace_root)
    
    try:
        # Run import based on source
        if args.file:
            if not args.file.exists():
                logger.error(f"File does not exist: {args.file}")
                sys.exit(1)
            success = await importer.import_file(args.file, args.knowledge_id)
            stats = {"successful": 1 if success else 0, "failed": 0 if success else 1}
            
        elif args.directory:
            if not args.directory.exists():
                logger.error(f"Directory does not exist: {args.directory}")
                sys.exit(1)
            stats = await importer.import_directory(args.directory, args.recursive)
            
        elif args.template:
            stats = await importer.import_template_knowledge()
        
        # Print summary
        print("\n" + "="*60)
        print("IMPORT COMPLETE")
        print("="*60)
        
        if "error" in stats:
            print(f"Error: {stats['error']}")
        else:
            if "total_files" in stats:
                print(f"Total files found: {stats.get('total_files', 0)}")
            print(f"Successfully imported: {stats.get('successful', 0)}")
            print(f"Failed: {stats.get('failed', 0)}")
            if stats.get('skipped', 0) > 0:
                print(f"Skipped: {stats['skipped']}")
            
            if stats.get('failed', 0) > 0:
                print("\n⚠️  Some imports failed. Check the logs for details.")
            elif stats.get('successful', 0) > 0:
                print("\n✅ All imports successful!")
                
    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await importer.cleanup()


if __name__ == "__main__":
    asyncio.run(main())