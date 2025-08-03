# Knowledge File Schema

Knowledge files in the Mind-Swarm library use a JSON format that embeds both content and metadata.

## Schema

```json
{
  "knowledge_version": "1.0",
  "id": "unique-knowledge-id",
  "title": "Human readable title",
  "content": "The actual knowledge content",
  "metadata": {
    "category": "category-name",
    "tags": ["tag1", "tag2"],
    "confidence": 1.0,
    "priority": 1-4,
    "source": "where this came from",
    "created": "ISO timestamp",
    "updated": "ISO timestamp",
    "version": 1,
    "dependencies": ["other-knowledge-id"],
    "related": ["related-knowledge-id"]
  }
}
```

## Fields

- `knowledge_version`: Schema version (currently "1.0")
- `id`: Unique identifier for this knowledge
- `title`: Human-readable title
- `content`: The actual knowledge text
- `metadata`:
  - `category`: Main category (e.g., "arithmetic", "concepts", "procedures")
  - `tags`: List of tags for organization
  - `confidence`: 0.0-1.0 confidence score
  - `priority`: 1 (critical), 2 (high), 3 (medium), 4 (low)
  - `source`: Origin of knowledge (e.g., "boot_rom", "learned", "user")
  - `created`/`updated`: ISO timestamps
  - `version`: Integer version number
  - `dependencies`: IDs of required prerequisite knowledge
  - `related`: IDs of related knowledge

## ROM Files

ROM files are special knowledge files that:
1. Always have `priority: 1` (critical)
2. Always have `confidence: 1.0`
3. Have `source: "boot_rom"`
4. Are automatically loaded at agent startup

## Directory Structure

```
/grid/library/
├── rom/
│   ├── general/        # ROMs for all agents
│   │   └── core.json
│   └── {agent_type}/   # Type-specific ROMs
│       └── core.json
├── concepts/           # General concepts
├── procedures/         # How-to knowledge
└── facts/             # Factual knowledge
```