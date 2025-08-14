# Subspace Management System

## Overview

The Mind-Swarm subspace management system provides intelligent synchronization between the template repository (`subspace_template/`) and the runtime environment (`subspace/`). This system preserves Cyber contributions while allowing safe updates from the template.

## Key Components

### 1. Git-Based Tracking
- **Subspace as Git Repository**: The `/subspace` directory is now a git repository tracking all changes
- **Commit History**: Every sync operation creates commits for auditability
- **Conflict Resolution**: Git-based merging preserves both template updates and Cyber contributions

### 2. Directory Ownership Model

#### Template-Owned (Always Synced from Template)
- `/grid/library/base_code/` - Cyber runtime code
- `/grid/workshop/` - System tools

These directories are critical system components that should always match the template.

#### Cyber-Owned (Never Overwritten)
- `/cybers/*/` - All Cyber personal directories
- `/grid/community/` - Shared discussions and questions
- `/grid/library/knowledge/sections/new_cyber_introduction/` - Cyber contributions

These areas belong to Cybers and their work is preserved across restarts.

#### Merge-Required (Intelligent Merging)
- `/grid/library/knowledge/schemas/` - Schema updates
- `/grid/library/knowledge/sections/rom/` - ROM content
- `/grid/library/README.md` - Documentation

Changes from both template and Cybers are preserved through merging.

## Configuration

The sync behavior is controlled by `/config/subspace_sync.yaml`:

```yaml
template_owned:
  - grid/library/base_code/base_code_template
  - grid/library/base_code/io_cyber_template
  - grid/workshop

cyber_owned:
  - cybers/*
  - grid/community
  - grid/library/knowledge/sections/new_cyber_introduction

merge_required:
  - grid/library/knowledge/schemas
  - grid/library/knowledge/sections/rom
  - grid/library/README.md
```

## Usage

### Automatic Sync on Server Start

When the Mind-Swarm server starts, it automatically:
1. Checks if sync system is available
2. Runs intelligent sync from template
3. Falls back to non-destructive initialization if sync fails

### Manual Sync Operations

```bash
# Dry run to see what would change
python scripts/sync_subspace.py --dry-run

# Perform sync with backup
python scripts/sync_subspace.py --backup

# Sync with custom paths
python scripts/sync_subspace.py \
  --subspace /path/to/subspace \
  --template /path/to/template \
  --config /path/to/config.yaml
```

### Checking Sync Status

```bash
# View git status in subspace
cd subspace
git status

# View sync history
git log --oneline

# Check for conflicts
find . -name "*.template_conflict"
```

## Conflict Resolution

When template and Cyber changes conflict:
1. Conflicts are marked with `.template_conflict` suffix
2. Original Cyber version is preserved
3. Template version saved for manual review
4. Resolve by choosing appropriate version

Example:
```bash
# If knowledge_schema.md conflicts
# Original: knowledge_schema.md (Cyber version)
# Template: knowledge_schema.md.template_conflict

# To accept template version:
mv knowledge_schema.md.template_conflict knowledge_schema.md

# To keep Cyber version:
rm knowledge_schema.md.template_conflict
```

## Backup System

### Automatic Backups
- Created before each sync operation
- Stored in `/subspace_backups/`
- Timestamped format: `backup_YYYYMMDD_HHMMSS`

### Manual Backup
```bash
# Create backup
cp -r subspace subspace_backups/manual_$(date +%Y%m%d_%H%M%S)

# Restore from backup
rm -rf subspace
cp -r subspace_backups/backup_20240813_143000 subspace
```

## Development Workflow

### For Core Developers

1. **Template Changes**: Make changes in `subspace_template/`
2. **Test Sync**: Run sync with `--dry-run` to preview
3. **Apply Changes**: Run sync to apply to runtime
4. **Verify**: Check that Cyber content is preserved

### For Cyber Contributions

1. **Cybers Create Content**: Alice and others create files in their spaces
2. **Content Preserved**: Server restarts don't lose their work
3. **Git Tracking**: All changes are tracked in git history
4. **Collaboration**: Cybers can build on each other's work

## Migration from Old System

### What Changed

**Before**: Destructive copying from template
- `shutil.rmtree()` deleted entire directories
- Cyber work was lost on restart
- No history or rollback capability

**After**: Intelligent git-based sync
- Selective updates based on ownership
- Cyber contributions preserved
- Full history and rollback available

### Migration Steps Completed

1. ✅ Backed up existing subspace
2. ✅ Initialized subspace as git repository
3. ✅ Created sync script and configuration
4. ✅ Updated SubspaceManager to use sync
5. ✅ Tested sync system
6. ✅ Documented new system

## Troubleshooting

### Sync Fails
```bash
# Check logs
tail -f mind-swarm.log

# Run sync manually with verbose output
python scripts/sync_subspace.py --dry-run

# Check git status
cd subspace && git status
```

### Lost Cyber Work
```bash
# Check backups
ls -la subspace_backups/

# Check git history
cd subspace && git log --stat

# Restore from backup
cp -r subspace_backups/latest subspace
```

### Merge Conflicts
```bash
# Find conflicts
find subspace -name "*.template_conflict"

# Review and resolve each conflict manually
```

## Best Practices

1. **Always Test First**: Use `--dry-run` before applying changes
2. **Regular Backups**: Keep backups even though git tracks history
3. **Document Changes**: Use clear commit messages in template
4. **Respect Ownership**: Don't manually edit Cyber-owned directories in template
5. **Monitor Sync**: Check logs after server restarts

## Future Enhancements

- [ ] Web UI for conflict resolution
- [ ] Automatic conflict resolution strategies
- [ ] Sync status in server dashboard
- [ ] Cyber notification of template updates
- [ ] Selective sync per Cyber request