# Knowledge File Schema

Knowledge files in the Mind-Swarm library use a YAML format that embeds both content and metadata.

## Schema

```yaml
knowledge_version: "1.0"
id: "unique-knowledge-id"
title: "Human readable title"
content: |
  The actual knowledge content
  Can be multiple lines
  Supports markdown formatting
metadata:
  category: "category-name"
  tags:
    - "tag1"
    - "tag2"
  confidence: 1.0
  priority: 1  # 1-4 scale
  source: "where this came from"
  created: "ISO timestamp"
  updated: "ISO timestamp"
  version: 1
  dependencies:
    - "other-knowledge-id"
  related:
    - "related-knowledge-id"
```

## Fields

- `knowledge_version`: Schema version (currently "1.0")
- `title`: Human-readable title
- `content`: The actual knowledge text (use `|` for multiline content)
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

## Example Knowledge File

```yaml
knowledge_version: 1.0
title: Example Knowledge
content: |
  # Title  
  ## Sub header 1
  Use the outbox to send messages to other Cybers:
  
  ```python
  memory.personal.notes.example = "Example Code Text"
  /```
  ## Sub header 2
  More details about the topic.

metadata:
  category: "procedures"
  tags:
    - "communication"
    - "messaging"
    - "tutorial"
  confidence: 1.0
  priority: 2
  source: "boot_rom"
  created: "2025-08-14T00:00:00Z"
  updated: "2025-08-14T00:00:00Z"
  version: 1
  dependencies: []
```

## Creating New Knowledge Files

When creating new knowledge files:

1. **Use YAML format** with `.yaml` extension
2. **Use the pipe (`|`) for multiline content** to preserve formatting
3. **Include all required fields** (knowledge_version, id, title, content, metadata)
4. **Choose appropriate metadata** based on the knowledge type
5. **Use proper YAML indentation** (2 spaces recommended)
6. **Validate YAML syntax** before saving
