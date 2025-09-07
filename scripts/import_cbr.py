#!/usr/bin/env python3
"""Import CBR cases from YAML files into ChromaDB.

This script imports Case-Based Reasoning cases from YAML files (e.g., from exports)
into the ChromaDB CBR collections, supporting path-based IDs for deterministic imports.
"""

import argparse
import asyncio
import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.mind_swarm.subspace.cbr_handler import CBRHandler, CHROMADB_AVAILABLE

try:
    from chromadb.utils import embedding_functions
except ImportError:
    embedding_functions = None
from src.mind_swarm.utils.id_policy import normalize_cbr_case_id

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CBRImporter:
    """Import CBR cases from filesystem to ChromaDB."""
    
    def __init__(self, subspace_root: Path):
        """Initialize the importer.
        
        Args:
            subspace_root: Path to the subspace root directory
        """
        self.subspace_root = Path(subspace_root)
        self.cbr_handler = None
        self.stats = {
            "total_files": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "unchanged": 0,
            "updated": 0,
            "shared": 0,
            "personal": {}
        }
        
    def initialize(self):
        """Initialize the CBR handler."""
        if not CHROMADB_AVAILABLE:
            raise ImportError("ChromaDB is not installed. Please install it to use CBR import.")
        
        self.cbr_handler = CBRHandler(subspace_root=self.subspace_root)
        if not self.cbr_handler.enabled:
            raise RuntimeError("CBR handler could not be initialized")
        
        # Store references we need
        self.chroma_client = self.cbr_handler.chroma_client
        self.embedding_function = self.cbr_handler.embedding_fn
        
        logger.info("CBR handler initialized")
    
    def _sanitize_metadata_value(self, value: Any) -> Any:
        """Sanitize metadata value for ChromaDB.
        
        ChromaDB only accepts str, int, float, bool, None in metadata.
        
        Args:
            value: Value to sanitize
            
        Returns:
            Sanitized value or None if cannot be sanitized
        """
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (list, tuple)):
            # Convert lists to comma-separated strings
            str_items = []
            for item in value:
                sanitized = self._sanitize_metadata_value(item)
                if sanitized is not None:
                    str_items.append(str(sanitized))
            return ','.join(str_items) if str_items else None
        if isinstance(value, dict):
            # Convert dicts to JSON strings
            return json.dumps(value)
        # Convert everything else to string
        return str(value)
    
    def _prepare_case_metadata(self, metadata: Dict, cyber_name: Optional[str] = None) -> Dict:
        """Prepare and sanitize case metadata for ChromaDB.
        
        Args:
            metadata: Raw metadata dictionary
            cyber_name: Optional cyber name for personal collections
            
        Returns:
            Sanitized metadata dictionary
        """
        sanitized = {}
        
        # Copy and sanitize all metadata fields
        for key, value in metadata.items():
            sanitized_value = self._sanitize_metadata_value(value)
            if sanitized_value is not None:
                sanitized[key] = sanitized_value
        
        # Ensure required fields
        if 'timestamp' not in sanitized:
            sanitized['timestamp'] = datetime.now().isoformat()
        
        if 'imported_at' not in sanitized:
            sanitized['imported_at'] = datetime.now().isoformat()
        
        if 'imported_by' not in sanitized:
            sanitized['imported_by'] = 'import_cbr_tool'
        
        if cyber_name:
            sanitized['cyber_id'] = cyber_name
        
        # Set default success score if not present
        if 'success_score' not in sanitized:
            sanitized['success_score'] = 0.7
        
        return sanitized
    
    async def import_case(self, file_path: Path, target_collection: str = 'shared', 
                         cyber_name: Optional[str] = None) -> bool:
        """Import a single CBR case from YAML file.
        
        Args:
            file_path: Path to the YAML file to import
            target_collection: 'shared' or 'personal' (requires cyber_name if personal)
            cyber_name: Name of cyber for personal collections
            
        Returns:
            True if import was successful
        """
        if not self.cbr_handler:
            self.initialize()
            
        try:
            # Read and parse YAML file
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
            
            if not isinstance(data, dict):
                logger.error(f"Invalid YAML structure in {file_path}: expected dictionary")
                return False
            
            # Extract case ID from export metadata or case_path
            case_id = None
            case_path = None
            
            # Check for export metadata
            if '_export_metadata' in data:
                export_meta = data.pop('_export_metadata')
                case_id = export_meta.get('id')
                case_path = export_meta.get('case_path')
                
                # Add source metadata for traceability
                if 'chromadb_metadata' in export_meta:
                    orig_meta = export_meta['chromadb_metadata']
                    if 'cyber_id' in orig_meta and not cyber_name:
                        cyber_name = orig_meta['cyber_id']
            
            # Check for case_path in main metadata
            if not case_path and 'metadata' in data:
                case_path = data['metadata'].get('case_path')
            
            # Determine case ID using path-based normalization
            if case_path:
                case_id = normalize_cbr_case_id(case_path)
            elif case_id:
                # Normalize existing ID if it looks path-like
                case_id = normalize_cbr_case_id(case_id)
            else:
                # Generate ID from filename as fallback
                case_id = normalize_cbr_case_id(f"imported/{file_path.stem}")
            
            # Extract case content
            case_doc = {
                "problem_context": data.get('problem_context', ''),
                "solution": data.get('solution', ''),
                "outcome": data.get('outcome', '')
            }
            
            # Prepare metadata
            metadata = data.get('metadata', {})
            if case_path:
                metadata['case_path'] = case_path
            metadata = self._prepare_case_metadata(metadata, cyber_name)
            
            # Determine target collection
            if target_collection == 'personal' and cyber_name:
                collection_name = f"cbr_personal_{cyber_name}"
            else:
                collection_name = "cbr_shared"
            
            # Get or create collection
            try:
                collection = self.chroma_client.get_collection(
                    name=collection_name,
                    embedding_function=self.embedding_function
                )
            except:
                # Create collection if it doesn't exist
                collection = self.chroma_client.create_collection(
                    name=collection_name,
                    embedding_function=self.embedding_function
                )
                logger.info(f"Created collection: {collection_name}")
            
            # Check if case already exists (for upsert logic)
            try:
                existing = collection.get(ids=[case_id])
                if existing and existing.get('documents'):
                    # Update existing case
                    collection.update(
                        ids=[case_id],
                        documents=[json.dumps(case_doc)],
                        metadatas=[metadata]
                    )
                    logger.info(f"↻ Updated: {case_id} in {collection_name}")
                    self.stats["updated"] += 1
                else:
                    # Add new case
                    collection.add(
                        ids=[case_id],
                        documents=[json.dumps(case_doc)],
                        metadatas=[metadata]
                    )
                    logger.info(f"✓ Imported: {case_id} to {collection_name}")
            except Exception as e:
                # If get fails, try to add (backward compatibility)
                logger.debug(f"Could not check for existing case, attempting add: {e}")
                try:
                    collection.add(
                        ids=[case_id],
                        documents=[json.dumps(case_doc)],
                        metadatas=[metadata]
                    )
                    logger.info(f"✓ Imported: {case_id} to {collection_name}")
                except Exception as add_error:
                    logger.error(f"Failed to add case {case_id}: {add_error}")
                    raise
            
            # Update statistics
            if target_collection == 'shared':
                self.stats["shared"] += 1
            else:
                self.stats["personal"][cyber_name] = self.stats["personal"].get(cyber_name, 0) + 1
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to import {file_path}: {e}")
            return False
    
    async def import_directory(self, dir_path: Path, target_collection: str = 'shared',
                              recursive: bool = True) -> Dict[str, Any]:
        """Import all CBR case YAML files from a directory.
        
        Args:
            dir_path: Directory containing YAML files
            target_collection: 'shared' or 'personal' 
            recursive: Whether to search subdirectories
            
        Returns:
            Dictionary with import statistics
        """
        if not self.cbr_handler:
            self.initialize()
        
        # Find all YAML files
        pattern = "**/*.yaml" if recursive else "*.yaml"
        yaml_files = list(dir_path.glob(pattern))
        pattern = "**/*.yml" if recursive else "*.yml"
        yaml_files.extend(list(dir_path.glob(pattern)))
        
        self.stats["total_files"] = len(yaml_files)
        logger.info(f"Found {len(yaml_files)} YAML files to import")
        
        for i, file_path in enumerate(yaml_files, 1):
            # Skip summary and metadata files
            if file_path.name in ['export_summary.yaml', '.description.yaml', 'README.md']:
                self.stats["skipped"] += 1
                logger.debug(f"Skipped: {file_path.name}")
                continue
            
            # Detect cyber name from path structure (for personal collections)
            cyber_name = None
            if 'personal' in file_path.parts:
                # Look for pattern like cbr_cases/personal/cyber_name/file.yaml
                try:
                    personal_idx = file_path.parts.index('personal')
                    if personal_idx + 1 < len(file_path.parts):
                        cyber_name = file_path.parts[personal_idx + 1]
                        target_collection = 'personal'
                except:
                    pass
            
            # Import the file
            success = await self.import_case(file_path, target_collection, cyber_name)
            if success:
                self.stats["successful"] += 1
            else:
                self.stats["failed"] += 1
            
            if i % 10 == 0:
                logger.info(f"Progress: {i}/{len(yaml_files)} files processed...")
        
        return self.stats
    
    async def import_from_export(self, export_dir: Path) -> Dict[str, Any]:
        """Import CBR cases from a knowledge export directory.
        
        Args:
            export_dir: Path to export directory (e.g., knowledge_export_20250117_120000)
            
        Returns:
            Dictionary with import statistics
        """
        cbr_dir = export_dir / "cbr_cases"
        if not cbr_dir.exists():
            logger.warning(f"No CBR cases directory found in {export_dir}")
            return self.stats
        
        # Import shared CBR cases
        shared_dir = cbr_dir / "shared"
        if shared_dir.exists():
            logger.info("Importing shared CBR cases...")
            await self.import_directory(shared_dir, target_collection='shared')
        
        # Import personal CBR cases
        personal_dir = cbr_dir / "personal"
        if personal_dir.exists():
            logger.info("Importing personal CBR cases...")
            # Each subdirectory is a cyber's personal collection
            for cyber_dir in personal_dir.iterdir():
                if cyber_dir.is_dir():
                    cyber_name = cyber_dir.name
                    logger.info(f"Importing CBR cases for {cyber_name}...")
                    await self.import_directory(cyber_dir, target_collection='personal', 
                                              recursive=False)
        
        return self.stats
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.cbr_handler:
            self.cbr_handler = None


async def main():
    """Main entry point."""
    import os
    parser = argparse.ArgumentParser(
        description="Import CBR cases from YAML files into ChromaDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import from export directory
  %(prog)s --export-dir knowledge_exports/knowledge_export_20250117_120000
  
  # Import single file to shared collection
  %(prog)s --file case.yaml --target shared
  
  # Import directory to personal collection
  %(prog)s --directory cases/ --target personal --cyber Alice
  
  # Import with custom subspace root
  %(prog)s --subspace-root /custom/path --export-dir exports/
        """
    )
    
    # Use SUBSPACE_ROOT env var if set, otherwise use current directory parent
    default_subspace = Path(os.environ.get("SUBSPACE_ROOT", "../subspace"))
    
    parser.add_argument(
        "--subspace-root",
        type=Path,
        default=default_subspace,
        help=f"Path to subspace root directory (default: {default_subspace})"
    )
    
    # Input source options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--file",
        type=Path,
        help="Import single YAML file"
    )
    input_group.add_argument(
        "--directory",
        type=Path,
        help="Import all YAML files from directory"
    )
    input_group.add_argument(
        "--export-dir",
        type=Path,
        help="Import from knowledge export directory (e.g., knowledge_export_20250117_120000)"
    )
    
    # Target options
    parser.add_argument(
        "--target",
        choices=['shared', 'personal'],
        default='shared',
        help="Target collection: shared or personal (default: shared)"
    )
    parser.add_argument(
        "--cyber",
        type=str,
        help="Cyber name for personal collections (required if --target personal)"
    )
    parser.add_argument(
        "--recursive",
        action='store_true',
        default=True,
        help="Search subdirectories recursively (default: True)"
    )
    parser.add_argument(
        "--no-recursive",
        dest='recursive',
        action='store_false',
        help="Don't search subdirectories"
    )
    
    args = parser.parse_args()
    
    # Validation
    if args.target == 'personal' and not args.cyber and not args.export_dir:
        parser.error("--cyber is required when --target is personal (unless using --export-dir)")
    
    # Verify subspace root exists
    if not args.subspace_root.exists():
        logger.error(f"Subspace root does not exist: {args.subspace_root}")
        sys.exit(1)
    
    # Create importer
    importer = CBRImporter(args.subspace_root)
    
    try:
        # Run import based on input type
        if args.file:
            success = await importer.import_case(args.file, args.target, args.cyber)
            stats = importer.stats
            stats["successful"] = 1 if success else 0
            stats["failed"] = 0 if success else 1
            stats["total_files"] = 1
        elif args.directory:
            stats = await importer.import_directory(args.directory, args.target, args.recursive)
        else:  # export_dir
            stats = await importer.import_from_export(args.export_dir)
        
        # Print summary
        print("\n" + "="*60)
        print("CBR IMPORT COMPLETE")
        print("="*60)
        print(f"Total files processed: {stats['total_files']}")
        print(f"Successfully imported: {stats['successful']}")
        if stats['updated'] > 0:
            print(f"Updated existing: {stats['updated']}")
        if stats['failed'] > 0:
            print(f"Failed: {stats['failed']}")
        if stats['skipped'] > 0:
            print(f"Skipped: {stats['skipped']}")
        
        print(f"\nBy collection:")
        if stats['shared'] > 0:
            print(f"  Shared: {stats['shared']} cases")
        if stats['personal']:
            print(f"  Personal collections:")
            for cyber, count in stats['personal'].items():
                print(f"    - {cyber}: {count} cases")
        
        # Exit with error if any imports failed
        if stats['failed'] > 0:
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await importer.cleanup()


if __name__ == "__main__":
    asyncio.run(main())