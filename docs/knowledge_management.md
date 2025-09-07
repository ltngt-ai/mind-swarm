# Knowledge Management Guide

This guide explains how to sync, export, review, and import knowledge from the ChromaDB knowledge database, including Case-Based Reasoning (CBR) cases.

## Overview

The Mind-Swarm knowledge system stores cyber-contributed knowledge in ChromaDB with deterministic path-based IDs for reliable migration and synchronization. Key capabilities:

1. **Sync** knowledge from filesystem sources (templates, library, community) with configurable scopes
2. **Export** knowledge and CBR cases from ChromaDB to YAML files
3. **Review** and curate the exported knowledge with security filtering
4. **Import** selected knowledge back into ChromaDB using idempotent upserts
5. **Migrate** knowledge between systems preserving path-based IDs

## Knowledge Synchronization

### Sync from Filesystem Sources

Sync knowledge from configured filesystem sources to ChromaDB:

```bash
# Sync all configured sources
mind-swarm knowledge sync

# Sync specific scope
mind-swarm knowledge sync --scope library
mind-swarm knowledge sync --scope template  
mind-swarm knowledge sync --scope community
mind-swarm knowledge sync --scope all
```

### Sync Configuration

The sync process is controlled by `config/knowledge_sync.yaml` which defines:

- **Sync roots**: Source directories and their ID prefixes
- **Include/exclude patterns**: File patterns to sync or skip
- **Security filters**: Patterns to prevent sensitive data syncing
- **Content filters**: Additional validation rules

#### Path-Based IDs

Knowledge items use deterministic path-based IDs:
- Format: `{id_prefix}/{relative_path_from_root}`
- Example: `library/sections/security/authentication.md`
- Benefits: Idempotent syncs, predictable IDs, easy migration

#### Idempotency

Sync operations are idempotent:
- Same ID + same content = no update (skip)
- Same ID + different content = update with content hash check
- New ID = create new item
- Uses content hashing to detect actual changes

### Security and Filtering

The sync process includes multiple security layers:

1. **Path denylist**: Patterns like `**/.env`, `**/secrets/**`
2. **Content scanning**: Regex patterns to detect passwords, API keys, tokens
3. **File size limits**: Skip files over 10MB by default
4. **Binary detection**: Skip non-text files

Example patterns prevented:
```yaml
# Never synced:
- Files matching: **/.internal/**, **/private/**
- Content containing: password=, api_key=, -----BEGIN PRIVATE KEY-----
- File types: *.pem, *.key, *.cert
```

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

1. **Use Path-Based IDs** - Maintain consistent IDs across exports/imports
2. **Regular Syncs** - Keep knowledge up-to-date from filesystem sources
3. **Security First** - Review sync config to prevent sensitive data leakage
4. **Idempotent Operations** - Safe to run sync/import multiple times
5. **Content Hashing** - Detects actual changes, avoids unnecessary updates
6. **Scope Control** - Sync only what's needed (library, template, community)
7. **Regular Exports** - Export knowledge periodically as backups
8. **Review Before Import** - Check exported content before importing
9. **Clean Metadata** - Remove `_export_metadata` when adding to template
10. **Test Imports** - Verify imported knowledge is accessible

## Migration Guide

### Migrating Between Systems

Preserve knowledge and CBR cases when moving between systems:

```bash
# 1. On source system - Export everything
./run.sh export-knowledge --export-dir /shared/migration

# 2. Review exported content
ls -la /shared/migration/knowledge_export_*/
# Check: all/, by_category/, cbr_cases/

# 3. On target system - Import with path-based IDs
./run.sh import-knowledge --directory /shared/migration/knowledge_export_*/all
python scripts/import_cbr.py --export-dir /shared/migration/knowledge_export_*

# 4. Verify migration
mind-swarm knowledge sync --scope all
```

### Upgrading Knowledge Structure

When updating the knowledge organization:

```bash
# 1. Export current state
./run.sh export-knowledge --export-dir backups/pre-upgrade

# 2. Update sync configuration
vi config/knowledge_sync.yaml
# Modify sync_roots, id_prefixes as needed

# 3. Clear and re-sync
mind-swarm knowledge sync --scope all

# 4. Re-import any custom knowledge
./run.sh import-knowledge --directory backups/pre-upgrade/by_category/custom
```

### Merging Knowledge from Multiple Sources

```bash
# 1. Export from each source
# System A:
./run.sh export-knowledge --export-dir exports/system-a

# System B:
./run.sh export-knowledge --export-dir exports/system-b

# 2. On target system, import in priority order
# Higher priority overwrites lower on ID conflicts
./run.sh import-knowledge --directory exports/system-a/all
./run.sh import-knowledge --directory exports/system-b/all

# 3. Import CBR cases (path-based IDs prevent duplicates)
python scripts/import_cbr.py --export-dir exports/system-a
python scripts/import_cbr.py --export-dir exports/system-b
```

## Troubleshooting

### Sync Issues

- **No items synced**: Check sync roots exist and contain matching files
- **Security filter blocking**: Review `config/knowledge_sync.yaml` denylist
- **Path-based ID conflicts**: Higher priority roots override lower ones
- **Content not updating**: Content hash may be unchanged, force with `--force`

### Export Issues

- **No knowledge found**: Ensure ChromaDB is initialized and contains data
- **Permission errors**: Check write permissions in export directory
- **ChromaDB connection**: Verify subspace root path is correct
- **Missing CBR cases**: Ensure `--no-personal` flag if excluding personal cases

### Import Issues  

- **Invalid YAML**: Check file syntax with `yamllint`
- **Duplicate IDs**: Path-based IDs ensure idempotency (safe to re-import)
- **Missing metadata**: Ensure required fields (title, content) are present
- **CBR import fails**: Verify cyber name for personal collections

### Performance

- Large syncs use batching and parallel processing (see sync_behavior config)
- Content hashing avoids unnecessary updates
- Use scoped syncs to reduce processing (`--scope library`)
- Import in batches for very large knowledge bases
- Monitor ChromaDB storage usage

## CBR Case Management

### Exporting CBR Cases

CBR (Case-Based Reasoning) cases are automatically exported alongside knowledge when using the export scripts:

```bash
./run.sh export-knowledge --no-personal  # Exclude personal CBR cases
```

Exported CBR cases are organized in:
- `cbr_cases/shared/` - Shared CBR cases accessible to all cybers
- `cbr_cases/personal/{cyber_name}/` - Personal CBR cases per cyber

### Importing CBR Cases

Import CBR cases from YAML files using the dedicated import script:

#### Import from Export Directory

```bash
python scripts/import_cbr.py --export-dir knowledge_exports/knowledge_export_20250117_120000
```

#### Import Single CBR Case

```bash
python scripts/import_cbr.py --file case.yaml --target shared
```

#### Import to Personal Collection

```bash
python scripts/import_cbr.py --directory cases/ --target personal --cyber Alice
```

#### Command Line Options

```bash
python scripts/import_cbr.py --help

Options:
  --subspace-root PATH   Path to subspace root (default: $SUBSPACE_ROOT or ../subspace)
  --file PATH           Import single YAML file
  --directory PATH      Import all YAML files from directory
  --export-dir PATH     Import from knowledge export directory
  --target {shared,personal}  Target collection (default: shared)
  --cyber NAME          Cyber name for personal collections
  --recursive           Search subdirectories (default: True)
```

### CBR Case Format

CBR cases use this YAML structure:

```yaml
problem_context: Description of the problem encountered
solution: The solution that was applied
outcome: The result of applying the solution
metadata:
  case_path: cases/category/specific-case  # Optional path-based ID
  success_score: 0.85
  tags: [tag1, tag2]
  cyber_id: Alice
  timestamp: 2025-01-17T12:00:00
```

With export metadata:

```yaml
_export_metadata:
  id: cases/debugging/memory-leak-fix  # Path-based ID used for import
  case_path: cases/debugging/memory-leak-fix  # Preserved for round-trip
  collection: cbr_shared
  exported_at: 2025-01-17T12:00:00
```

### Path-Based IDs for CBR

The CBR import tool supports deterministic, path-based IDs:

1. **Priority order**: `case_id` parameter > `case_path` metadata > filename
2. **Normalization**: Path-like IDs are normalized to `cases/...` format
3. **Upsert logic**: Existing cases with same ID are updated, not duplicated
4. **Round-trip support**: Export preserves `case_path` for re-import

Example workflow:

```bash
# Export CBR cases
./run.sh export-knowledge

# Cases have path-based IDs like:
# - cases/debugging/memory-leak
# - cases/optimization/query-performance

# Re-import preserves the same IDs
python scripts/import_cbr.py --export-dir knowledge_exports/latest

# Cases maintain their original IDs for consistency
```

## Integration with Cybers

Cybers can access imported knowledge and CBR cases through:

1. **Knowledge search** - Query by content or tags
2. **Direct reference** - Access by knowledge ID
3. **Category browsing** - Explore by category
4. **Tag filtering** - Find related knowledge
5. **CBR retrieval** - Find similar past cases and solutions
6. **CBR storage** - Store new cases with deterministic IDs

Knowledge and CBR cases become immediately available to all cybers after import.

## CLI Reference

### Knowledge Sync

```bash
mind-swarm knowledge sync [--scope {all,library,template,community}]
```

Triggers server-side sync from filesystem sources to ChromaDB.

### Export Scripts

```bash
# Export knowledge
python scripts/export_knowledge.py \
  --subspace-root PATH \
  --export-dir PATH \
  --query TEXT \
  --max-results N \
  --no-personal  # Exclude personal CBR cases

# Exported structure:
knowledge_export_TIMESTAMP/
├── all/                    # All knowledge documents
├── by_category/           # Organized by category
├── by_tags/              # Organized by tags  
├── by_cyber/             # Organized by contributor
├── cbr_cases/            # CBR cases
│   ├── shared/          # Shared cases
│   └── personal/        # Personal cases by cyber
├── export_summary.yaml   # Statistics
└── README.md            # Documentation
```

### Import Scripts

```bash
# Import knowledge
python scripts/import_knowledge.py \
  --subspace-root PATH \
  --file PATH \
  --directory PATH \
  --template \
  --knowledge-id ID  # Explicit ID for single file

# Import CBR cases
python scripts/import_cbr.py \
  --subspace-root PATH \
  --file PATH \
  --directory PATH \
  --export-dir PATH \
  --target {shared,personal} \
  --cyber NAME \
  --case-id ID  # Explicit ID for single case
```

## Configuration Reference

### knowledge_sync.yaml Structure

```yaml
version: "1.0"

sync_roots:
  - name: "root_name"
    source_path: "path/relative/to/project"
    id_prefix: "namespace/"
    enabled: true
    priority: 100  # Higher wins on conflicts
    runtime: false  # true for runtime paths

include_patterns:
  - "*.md"
  - "*.yaml"
  - "*.knowledge"

exclude_patterns:
  - "**/__pycache__/**"
  - "*.pyc"

security_denylist:
  - "**/.env"
  - "**/secrets/**"
  - "*api_key*"

content_filters:
  max_file_size: 10485760  # 10MB
  skip_binary: true
  content_denylist:
    - pattern: "password\\s*[:=]"
      description: "Password assignments"

sync_behavior:
  on_conflict: "update"  # skip, update, error
  use_content_hash: true
  batch_size: 100
  parallel: true
```