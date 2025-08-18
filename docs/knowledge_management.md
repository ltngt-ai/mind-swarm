# Knowledge Management Guide

This guide explains how to export, review, and import knowledge from the ChromaDB knowledge database.

## Overview

The Mind-Swarm knowledge system stores cyber-contributed knowledge in ChromaDB. When resetting a subspace or migrating knowledge, you can:

1. **Export** knowledge from ChromaDB to YAML files
2. **Review** and curate the exported knowledge
3. **Import** selected knowledge back into ChromaDB or add to the template

## Exporting Knowledge

### Export All Knowledge

Export all documents from the knowledge database:

```bash
./run.sh export-knowledge
```

This creates a timestamped export directory with:
- `all/` - All knowledge documents
- `by_category/` - Documents organized by category
- `by_tags/` - Documents organized by tags
- `by_cyber/` - Documents organized by contributing cyber
- `export_summary.yaml` - Export statistics
- `README.md` - Export documentation

### Export by Query

Export only knowledge matching a specific query:

```bash
./run.sh export-knowledge --query "memory management" --max-results 50
```

### Custom Export Directory

Specify where to export:

```bash
./run.sh export-knowledge --export-dir /path/to/exports
```

### Command Line Options

```bash
python scripts/export_knowledge.py --help

Options:
  --subspace-root PATH   Path to subspace root (default: ~/projects/subspace)
  --export-dir PATH      Export directory (default: ./knowledge_exports)
  --query TEXT          Export only matching knowledge
  --max-results N       Maximum results for query (default: 100)
```

## Reviewing Exported Knowledge

After export, review the knowledge in the export directory:

1. **Check `export_summary.yaml`** for statistics
2. **Browse by category** to understand knowledge organization
3. **Review by cyber** to see individual contributions
4. **Examine tags** to understand knowledge relationships

Each exported YAML file contains:
- Original knowledge content and metadata
- Export metadata (timestamp, source ID)
- ChromaDB metadata

## Importing Knowledge

### Import from Export

Import previously exported knowledge:

```bash
./run.sh import-knowledge --directory knowledge_exports/knowledge_export_20250117_120000
```

### Import Single File

Import a specific knowledge file:

```bash
./run.sh import-knowledge --file path/to/knowledge.yaml --knowledge-id "guides/my_guide"
```

### Import from Template

Import the initial knowledge from the template:

```bash
./run.sh import-knowledge --template
```

### Command Line Options

```bash
python scripts/import_knowledge.py --help

Options:
  --subspace-root PATH   Path to subspace root (default: ~/projects/subspace)
  --file PATH           Import single YAML file
  --directory PATH      Import all YAML files from directory
  --template            Import from subspace_template/initial_knowledge
  --recursive           Search subdirectories (default: True)
  --knowledge-id ID     Specific ID for single file import
```

## Adding Knowledge to Template

To include valuable knowledge in future subspace deployments:

1. **Export and review** the knowledge
2. **Select valuable content** to preserve
3. **Copy to template**:
   ```bash
   cp knowledge_exports/*/by_category/guides/useful_guide.yaml \
      subspace_template/initial_knowledge/guides/
   ```
4. **Clean up metadata** - Remove the `_export_metadata` section
5. **Update as needed** - Adjust title, tags, category
6. **Commit changes**:
   ```bash
   git add subspace_template/initial_knowledge/
   git commit -m "Add community-contributed knowledge to template"
   ```

## Workflow Examples

### Backup Before Reset

```bash
# 1. Export all knowledge
./run.sh export-knowledge

# 2. Note the export directory
# Example: knowledge_exports/knowledge_export_20250117_120000

# 3. Reset subspace (if needed)
rm -rf ~/projects/subspace

# 4. Restart server
./run.sh server

# 5. Import selected knowledge
./run.sh import-knowledge --directory knowledge_exports/knowledge_export_20250117_120000/by_category/guides
```

### Migrate Knowledge Between Systems

```bash
# On source system
./run.sh export-knowledge --export-dir /shared/knowledge_backup

# On target system
./run.sh import-knowledge --directory /shared/knowledge_backup/knowledge_export_*/all
```

### Curate Template Knowledge

```bash
# 1. Export current knowledge
./run.sh export-knowledge

# 2. Review and select best content
cd knowledge_exports/knowledge_export_*/by_category
ls -la

# 3. Copy selected files to template
cp guides/excellent_guide.yaml ../../../subspace_template/initial_knowledge/guides/

# 4. Edit to remove export metadata
vi ../../../subspace_template/initial_knowledge/guides/excellent_guide.yaml

# 5. Commit to repository
git add subspace_template/initial_knowledge/
git commit -m "Add curated community knowledge"
```

## File Format

Knowledge files use this YAML structure:

```yaml
title: Knowledge Title
tags: [tag1, tag2, tag3]
category: guides
source: Original source or cyber
content: |
  The actual knowledge content goes here.
  Can be multiple lines of markdown or text.
```

Export adds metadata:

```yaml
_export_metadata:
  id: original/knowledge/id
  exported_at: 2025-01-17T12:00:00
  chromadb_metadata:
    created_by: Alice
    created_at: 2025-01-01T10:00:00
```

## Best Practices

1. **Regular Exports** - Export knowledge periodically as backups
2. **Review Before Import** - Check exported content before importing
3. **Clean Metadata** - Remove `_export_metadata` when adding to template
4. **Organize by Category** - Use consistent categories for organization
5. **Tag Appropriately** - Use meaningful tags for discoverability
6. **Document Sources** - Keep track of knowledge origins
7. **Test Imports** - Verify imported knowledge is accessible

## Troubleshooting

### Export Issues

- **No knowledge found**: Ensure ChromaDB is initialized and contains data
- **Permission errors**: Check write permissions in export directory
- **ChromaDB connection**: Verify subspace root path is correct

### Import Issues

- **Invalid YAML**: Check file syntax with `yamllint`
- **Duplicate IDs**: Knowledge IDs must be unique
- **Missing metadata**: Ensure required fields (title, content) are present

### Performance

- Large exports may take time - use query filters for specific content
- Import in batches for very large knowledge bases
- Monitor ChromaDB storage usage

## Integration with Cybers

Cybers can access imported knowledge through:

1. **Knowledge search** - Query by content or tags
2. **Direct reference** - Access by knowledge ID
3. **Category browsing** - Explore by category
4. **Tag filtering** - Find related knowledge

Knowledge becomes immediately available to all cybers after import.