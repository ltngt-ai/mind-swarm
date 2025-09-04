# Mind-Swarm Knowledge Sources Inventory Report

## Summary
Total knowledge volume identified for migration: ~252KB across 30 files
Excludes: cybers/*/.internal/memory/**, .env files, transient logs, Python code files

## Knowledge Sources Identified

### 1. subspace_template/initial_knowledge (ALREADY SUPPORTED)
- **Path**: `subspace_template/initial_knowledge/`
- **Volume**: 108KB, 15 files
- **Format**: YAML files
- **Content**: Core cyber knowledge including:
  - Guides (quick tips, summarizing, onboarding)
  - OODA loop stages (observation, decision, execution, reflection, cleanup)
  - Concepts (cyber basics, LLM usage, cognitive architecture)
  - Formats (message format, knowledge format guides)
  - Library guides (fiction collection)

### 2. grid/library/schemas
- **Path**: `subspace_template/grid/library/schemas/`
- **Volume**: 16KB, 3 files
- **Format**: JSON schema definitions
- **Content**:
  - `knowledge_format.json` - Schema for knowledge structure
  - `message_format.json` - Schema for message protocol
  - `.description.txt` - Directory metadata

### 3. grid/community (Curated Docs Only)
- **Path**: `subspace_template/grid/community/`
- **Volume**: 128KB total, 7 curated document files
- **Formats**: Markdown (.md) and JSON
- **Content**:
  - `cyber_directory.json` - Cyber registry
  - `BULLETIN_BOARD.md` - Community announcements
  - `announcements/system_announcements.json` - System messages
  - School/onboarding materials (3 README files)
  - Suggestions (memory management enhancement proposal)

### 4. grid/library/non-fiction (Documentation Only)
- **Path**: `subspace_template/grid/library/non-fiction/`
- **Volume**: ~35KB of documentation (from 29MB total including code)
- **Format**: Markdown files
- **Content**:
  - `mind_swarm_tech/base_code/CLAUDE.md` - Claude integration guide (12KB)
  - `mind_swarm_tech/base_code/README.md` - Base code overview
  - `SCRIPT_EXECUTOR_SUMMARY.md` - Script execution documentation (11KB)
  - Python modules documentation (11KB)

## Special Formats Detected

1. **YAML Knowledge Format**: Structured knowledge in initial_knowledge uses consistent YAML schema with metadata fields (title, type, context, content)
2. **JSON Schemas**: Formal schema definitions for message and knowledge formats
3. **JSON Registries**: cyber_directory.json uses structured JSON for cyber metadata
4. **Markdown Documentation**: Standard markdown with headers, code blocks, and lists

## Excluded from Migration

Per requirements, the following are excluded:
- `cybers/*/.internal/memory/**` - Transient cyber memories
- `.env` files - Environment variables and secrets
- API keys and credentials
- Log files (*.log)
- Python source code (*.py files in base_code)
- Binary/compiled files

## Recommendations

1. **Priority Order**: 
   - Start with initial_knowledge (already supported)
   - Then schemas (foundational for validation)
   - Community curated docs
   - Non-fiction documentation

2. **ID Scheme Considerations**:
   - Use path-based IDs to preserve hierarchy
   - Example: `knowledge:initial:guides:quick_tips`
   
3. **Special Handling**:
   - JSON schemas should be stored as reference documents
   - YAML files should preserve their structure for context
   - Markdown can be chunked at header boundaries

## Next Steps
- Define ID scheme based on path hierarchy
- Design sync scope for periodic updates
- Implement loaders for YAML, JSON, and Markdown formats