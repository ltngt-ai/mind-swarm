# Knowledge and CBR ID Policy

Purpose: define a deterministic, path-based ID scheme for Knowledge and Case‑Based Reasoning (CBR) that is human‑meaningful, stable across sync/export, and minimizes collisions.

## Scope
- Knowledge items persisted in the shared store (e.g., ChromaDB) and synced from templates/library.
- CBR cases stored in personal or shared CBR collections.

## Core Principles
- Deterministic: the same source path yields the same ID.
- Relative: IDs use relative paths (no leading slash), scoped by a top‑level namespace.
- Normalized: lowercase; trim whitespace; replace spaces with `-`; use forward slashes.
- Minimal charset: `[a-z0-9-_/]` for path segments. Knowledge items may retain dots in filenames for extensions.
- Namespaced: avoid cross‑domain collisions and keep intent clear.

## Namespaces and Formats
- Knowledge
  - `templates/<rel_path>`: Content synced from `subspace_template/initial_knowledge`.
  - `library/sections/<rel_path>`: Curated library sections and imports.
  - `community/<area>/<slug>`: Community‑maintained notes (e.g., prompts, guides).
  - `personal/<cyber>/<category>/<slug>`: Personal notes/playbooks for a given cyber.
  - Notes:
    - Keep file extensions for knowledge paths when they originate from files (e.g., `.md`, `.yml`).
    - Use forward slashes; no leading slash; lowercase.

- CBR
  - Optional path‑based case IDs: `cases/<domain>/<topic>/<slug>`.
  - Otherwise, fall back to generated IDs (current format `cbr_<cyber>_<hash>_<epoch>`).
  - Case IDs should not include file extensions.

## Normalization Rules
- Lowercase all segments.
- Trim around separators; collapse internal whitespace to single hyphens per segment.
- Remove leading slashes; preserve a single forward slash as separator.
- Accept only `[a-z0-9-_/]` for CBR case IDs; knowledge IDs may include dots in the final filename when derived from files.

Examples (input → ID)
- Knowledge
  - `initial_knowledge/guides/Onboarding.md` → `templates/guides/onboarding.md`
  - `library/sections/Python/AsyncIO.md` → `library/sections/python/asyncio.md`
  - `community/Prompts/Summarization` → `community/prompts/summarization`
  - `personal/Cyber-42/Playbooks/Retry Strategies` → `personal/cyber-42/playbooks/retry-strategies`
- CBR
  - `DevOps/Deploy/Rollout Strategy v1` → `cases/devops/deploy/rollout-strategy-v1`

## Current Behavior vs. Target
- Today, the template sync uses the file path relative to `subspace_template/initial_knowledge` as the knowledge ID. Conceptually, this maps to the `templates/<rel_path>` namespace. Future config will make this explicit in exports and cross‑repo sync.
- CBR now supports optional path‑based IDs when provided (see API below). If not provided, it continues to generate unique IDs.

## Collision Handling
- Knowledge
  - Sync compares by ID. If a matching ID exists, the item is updated; otherwise, it is created.
  - Avoid duplicate items that differ only by letter case — IDs are treated as lowercase canonical forms.
  - Prefer meaningful reorganization via content moves (keeping IDs stable) instead of duplicating similar items.

- CBR
  - If you supply an explicit `case_id` or a `metadata.case_path` that normalizes to an existing ID in either personal or shared collection, the store operation returns an error and does not overwrite.
  - To update an existing case, use `update_score` or a future explicit update flow. To create variants, append a semantic suffix (e.g., `-v2`, `-2025-09-03`).
  - If you do not supply a path, the system generates a unique ID; collisions are not expected in that mode.

## API Usage
- Knowledge
  - CLI and server already support sync from template files. The ID is the relative file path in the template tree (conceptually `templates/<rel_path>`).

- CBR
  - Store with an explicit `case_id`:
    {
      "operation": "store",
      "request_id": "req-123",
      "case_id": "cases/devops/deploy/rollout-strategy-v1",
      "case": {
        "problem_context": "...",
        "solution": "...",
        "outcome": "...",
        "metadata": {"shared": false}
      }
    }

  - Store with a `metadata.case_path` (normalized automatically):
    {
      "operation": "store",
      "request_id": "req-124",
      "case": {
        "problem_context": "...",
        "solution": "...",
        "outcome": "...",
        "metadata": {
          "case_path": "DevOps/Deploy/Rollout Strategy v1",
          "shared": true
        }
      }
    }

  - Retrieve:
    {"operation": "retrieve", "request_id": "req-125", "context": "...", "options": {"limit": 3}}

  - Update score/usage:
    {"operation": "update_score", "case_id": "cases/devops/deploy/rollout-strategy-v1", "updates": {"increment_usage": true}}

## Reserved Prefixes
- Knowledge: `templates/`, `library/sections/`, `community/`, `personal/`.
- CBR: `cases/`.

## Recommendations
- Keep Knowledge filenames short and descriptive; avoid deep nesting where possible.
- Use hyphenated slugs for CBR case IDs to encourage reuse and readability.
- Prefer stable IDs; avoid renaming unless there is a clear taxonomy improvement.

## Notes on Storage Constraints
- ChromaDB stores IDs as strings; metadata values are sanitized to primitives. Lists are joined or JSON‑serialized where necessary.
- Maximum ID length is not strictly enforced, but keeping IDs under ~200 characters is recommended for portability.

## Alignment and Future Work
- Config alignment: `config/knowledge_sync.yaml` will formalize sync scopes that correspond to the namespaces above.
- Export/import: exporters should preserve these IDs; importers should normalize to the same rules.
- Body API: explicit IDs are now supported for CBR; future work may add explicit IDs for other body endpoints.

