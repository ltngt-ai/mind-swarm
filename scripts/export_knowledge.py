#!/usr/bin/env python3
"""Export knowledge from ChromaDB to YAML files for review and template inclusion.

This script exports all documents from the ChromaDB knowledge database,
organizing them by category and preserving their metadata.
"""

import argparse
import asyncio
import json
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


class KnowledgeExporter:
    """Export knowledge from ChromaDB to filesystem."""
    
    def __init__(self, subspace_root: Path, export_dir: Path):
        """Initialize the exporter.
        
        Args:
            subspace_root: Path to the subspace root directory
            export_dir: Directory to export knowledge to
        """
        self.subspace_root = Path(subspace_root)
        self.export_dir = Path(export_dir)
        self.knowledge_handler = None
        
    def initialize(self):
        """Initialize the knowledge handler."""
        self.knowledge_handler = KnowledgeHandler(
            subspace_root=self.subspace_root
        )
        logger.info("Knowledge handler initialized")
        
    async def export_all_knowledge(self) -> Dict[str, Any]:
        """Export all knowledge from ChromaDB.
        
        Returns:
            Dictionary with export statistics
        """
        if not self.knowledge_handler:
            self.initialize()
            
        # Create export directory structure
        self.export_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_subdir = self.export_dir / f"knowledge_export_{timestamp}"
        export_subdir.mkdir(exist_ok=True)
        
        # Create subdirectories for organization
        by_category = export_subdir / "by_category"
        by_tags = export_subdir / "by_tags"
        by_cyber = export_subdir / "by_cyber"
        all_knowledge = export_subdir / "all"
        
        for dir in [by_category, by_tags, by_cyber, all_knowledge]:
            dir.mkdir(exist_ok=True)
        
        # Get all knowledge with full content
        logger.info("Fetching all knowledge from ChromaDB...")
        all_docs = await self.knowledge_handler.export_all_knowledge(limit=10000)
        
        if not all_docs:
            logger.warning("No knowledge found in database")
            return {"total_exported": 0, "export_dir": str(export_subdir)}
        
        logger.info(f"Found {len(all_docs)} knowledge items")
        
        # Statistics
        stats = {
            "total_exported": len(all_docs),
            "by_category": {},
            "by_tags": {},
            "by_cyber": {},
            "export_dir": str(export_subdir)
        }
        
        # Export each document
        for i, doc in enumerate(all_docs, 1):
            doc_id = doc.get('id', f'unknown_{i}')
            metadata = doc.get('metadata', {})
            content = doc.get('content', '')
            
            # Clean up the ID for use as filename
            safe_id = doc_id.replace('/', '_').replace('\\', '_')
            if not safe_id.endswith('.yaml'):
                safe_id += '.yaml'
            
            # Try to parse content as YAML to get structured data
            try:
                # The content should be the full YAML document
                yaml_data = yaml.safe_load(content) if content else {}
                if not isinstance(yaml_data, dict):
                    yaml_data = {
                        "title": metadata.get('title', 'Untitled'),
                        "content": str(yaml_data)
                    }
            except:
                # If not valid YAML, create a structure
                yaml_data = {
                    "title": metadata.get('title', doc_id),
                    "tags": metadata.get('tags', []),
                    "category": metadata.get('category', 'uncategorized'),
                    "content": content
                }
            
            # Add metadata from ChromaDB
            yaml_data['_export_metadata'] = {
                "id": doc_id,
                "exported_at": datetime.now().isoformat(),
                "chromadb_metadata": metadata
            }
            
            # Save to all knowledge directory
            all_path = all_knowledge / safe_id
            with open(all_path, 'w') as f:
                yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False, width=80)
            
            # Save by category
            category = metadata.get('category', 'uncategorized')
            if category:
                cat_dir = by_category / category
                cat_dir.mkdir(exist_ok=True)
                cat_path = cat_dir / safe_id
                with open(cat_path, 'w') as f:
                    yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False, width=80)
                stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
            
            # Save by tags
            tags = metadata.get('tags', [])
            if isinstance(tags, str):
                tags = [tags]
            for tag in tags:
                tag_dir = by_tags / tag
                tag_dir.mkdir(exist_ok=True)
                tag_path = tag_dir / safe_id
                with open(tag_path, 'w') as f:
                    yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False, width=80)
                stats["by_tags"][tag] = stats["by_tags"].get(tag, 0) + 1
            
            # Save by cyber (who created/updated it)
            cyber = metadata.get('created_by') or metadata.get('updated_by', 'system')
            if cyber:
                cyber_dir = by_cyber / cyber
                cyber_dir.mkdir(exist_ok=True)
                cyber_path = cyber_dir / safe_id
                with open(cyber_path, 'w') as f:
                    yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False, width=80)
                stats["by_cyber"][cyber] = stats["by_cyber"].get(cyber, 0) + 1
            
            if i % 10 == 0:
                logger.info(f"Exported {i}/{len(all_docs)} documents...")
        
        # Write export summary
        summary_path = export_subdir / "export_summary.yaml"
        summary = {
            "export_timestamp": datetime.now().isoformat(),
            "total_documents": stats["total_exported"],
            "categories": stats["by_category"],
            "tags": stats["by_tags"],
            "cybers": stats["by_cyber"],
            "export_directory": str(export_subdir)
        }
        with open(summary_path, 'w') as f:
            yaml.dump(summary, f, default_flow_style=False, sort_keys=False)
        
        # Write README
        readme_path = export_subdir / "README.md"
        with open(readme_path, 'w') as f:
            f.write(f"""# Knowledge Export - {timestamp}

This directory contains an export of all knowledge from the ChromaDB database.

## Statistics
- **Total Documents**: {stats['total_exported']}
- **Categories**: {len(stats['by_category'])}
- **Unique Tags**: {len(stats['by_tags'])}
- **Contributing Cybers**: {len(stats['by_cyber'])}

## Directory Structure
- `all/` - All knowledge documents in one place
- `by_category/` - Documents organized by category
- `by_tags/` - Documents organized by tags (documents may appear in multiple tag directories)
- `by_cyber/` - Documents organized by the cyber who created/updated them
- `export_summary.yaml` - Detailed export statistics

## Usage
1. Review the exported knowledge in the various directories
2. Identify valuable content to add to the template
3. Copy selected files to `subspace_template/initial_knowledge/` or appropriate location
4. Update metadata as needed (remove `_export_metadata` section)
5. Commit changes to include in future subspace deployments

## Notes
- Documents are exported in YAML format for easy review and editing
- The `_export_metadata` section in each file contains export information and should be removed before adding to template
- Original ChromaDB metadata is preserved in the export for reference
""")
        
        logger.info(f"Export complete! {stats['total_exported']} documents exported to {export_subdir}")
        return stats
        
    async def export_by_query(self, query: str, n_results: int = 100) -> Dict[str, Any]:
        """Export knowledge matching a specific query.
        
        Args:
            query: Search query
            n_results: Maximum number of results to export
            
        Returns:
            Dictionary with export statistics
        """
        if not self.knowledge_handler:
            self.initialize()
            
        # Search for matching knowledge
        logger.info(f"Searching for knowledge matching: {query}")
        results = await self.knowledge_handler.search_shared_knowledge(query, limit=n_results)
        
        if not results:
            logger.warning(f"No knowledge found matching query: {query}")
            return {"total_exported": 0}
            
        # Create export directory
        self.export_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_query = query[:50].replace('/', '_').replace('\\', '_').replace(' ', '_')
        export_subdir = self.export_dir / f"knowledge_query_{safe_query}_{timestamp}"
        export_subdir.mkdir(exist_ok=True)
        
        # Export results
        for i, doc in enumerate(results, 1):
            doc_id = doc.get('id', f'result_{i}')
            safe_id = doc_id.replace('/', '_').replace('\\', '_')
            if not safe_id.endswith('.yaml'):
                safe_id += '.yaml'
                
            # Save document
            doc_path = export_subdir / safe_id
            with open(doc_path, 'w') as f:
                yaml.dump(doc, f, default_flow_style=False, sort_keys=False, width=80)
        
        logger.info(f"Exported {len(results)} documents to {export_subdir}")
        return {"total_exported": len(results), "export_dir": str(export_subdir)}
        
    async def cleanup(self):
        """Cleanup resources."""
        if self.knowledge_handler:
            # KnowledgeHandler doesn't have explicit cleanup, but we can clear the reference
            self.knowledge_handler = None


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Export knowledge from ChromaDB")
    parser.add_argument(
        "--subspace-root",
        type=Path,
        default=Path.home() / "projects" / "subspace",
        help="Path to subspace root directory (default: ~/projects/subspace)"
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path.cwd() / "knowledge_exports",
        help="Directory to export knowledge to (default: ./knowledge_exports)"
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Export only knowledge matching this query"
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=100,
        help="Maximum results for query export (default: 100)"
    )
    
    args = parser.parse_args()
    
    # Verify subspace root exists
    if not args.subspace_root.exists():
        logger.error(f"Subspace root does not exist: {args.subspace_root}")
        sys.exit(1)
    
    # Create exporter
    exporter = KnowledgeExporter(args.subspace_root, args.export_dir)
    
    try:
        # Run export
        if args.query:
            stats = await exporter.export_by_query(args.query, args.max_results)
        else:
            stats = await exporter.export_all_knowledge()
        
        # Print summary
        print("\n" + "="*60)
        print("EXPORT COMPLETE")
        print("="*60)
        print(f"Total documents exported: {stats['total_exported']}")
        if 'export_dir' in stats:
            print(f"Export directory: {stats['export_dir']}")
        
        if 'by_category' in stats:
            print(f"\nCategories: {len(stats['by_category'])}")
            for cat, count in sorted(stats['by_category'].items()):
                print(f"  - {cat}: {count} documents")
        
        if 'by_tags' in stats:
            print(f"\nTop tags: {len(stats['by_tags'])}")
            for tag, count in sorted(stats['by_tags'].items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  - {tag}: {count} documents")
                
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await exporter.cleanup()


if __name__ == "__main__":
    asyncio.run(main())