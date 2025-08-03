# Library - Shared Knowledge

The Library contains structured knowledge that agents can learn from.

## Structure

- `rom/` - Read-Only Memory (boot knowledge)
  - `general/` - Core knowledge for all agents
  - `{agent_type}/` - Type-specific knowledge
- `concepts/` - General concepts and definitions
- `procedures/` - How-to guides and procedures
- `facts/` - Factual knowledge base

All knowledge files use the JSON schema defined in KNOWLEDGE_SCHEMA.md