# Repository Guidelines

## Project Structure & Module Organization
- `src/mind_swarm/`: Core Python package (CLI, server, AI providers, subspace runtime).
  - `cli/commands/`: CLI subcommands. Add new commands here.
  - `server/`: API, daemon, monitoring.
  - `ai/` and `ai/providers/`: Model selection and provider integrations.
  - `subspace/`: Agent coordination, knowledge/CBR, runtime utilities.
- `tests/`: Pytest suite (unit/integration). Name files `test_*.py`.
- `scripts/`: Import/export helpers for knowledge, etc.
- `docs/`, `config/`, `.env.example`: Documentation, configuration, and environment template.
- Top-level helpers: `run.sh` (dev workflow), `setup.sh`, ChromaDB scripts.

## Build, Test, and Development Commands
- Create venv and install: `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- Quick start server: `./run.sh server --debug` (status/logs: `./run.sh status` / `./run.sh logs`).
- CLI entry points: `mind-swarm ...` (e.g., `mind-swarm server start`, `mind-swarm connect`).
- Run tests: `pytest -q` or `pytest --cov=src/mind_swarm -q`.
- Lint/format/type-check: `ruff check .`, `black .`, `mypy src`.

## Coding Style & Naming Conventions
- Python 3.10+. PEP 8 with `black` (line length 100) and `ruff` rules; keep imports sorted.
- Type hints required for public functions (`mypy` enabled; avoid `Any`).
- Naming: `snake_case` for modules/functions, `PascalCase` for classes, `UPPER_SNAKE` for constants.
- CLI commands: place in `src/mind_swarm/cli/commands/`, file name `verb_noun.py`, function names `do_verb_noun`.

## Testing Guidelines
- Use `pytest` (with `pytest-asyncio` where needed). Name tests `test_<area>.py`; functions `test_<behavior>()`.
- Prefer fast unit tests in package submodules; mark slow/integration with `@pytest.mark.slow`.
- Aim for meaningful coverage on new/changed code; run `pytest --cov=src/mind_swarm` before PRs.

## Commit & Pull Request Guidelines
- Commits: present-tense imperative (“Add …”, “Refactor …”), small and focused; reference issues (e.g., `Fix #123`).
- PRs: include summary, motivation, screenshots/log snippets if UX/CLI output changes, and testing notes.
- CI hygiene: ensure `ruff`, `black`, `mypy`, and `pytest` pass locally.

## Configuration & Security
- Copy `.env.example` to `.env` and fill provider keys (OpenAI/Anthropic/OpenRouter, ChromaDB, etc.). Never commit secrets.
- Use the ChromaDB helper scripts and `scripts/` tools for knowledge import/export; verify outputs before sharing.

## Truncation Policy
- Purpose: Keep LLM search queries concise and logs readable without hiding information from Cyborgs.
- Scope: Truncation applies only to search queries and log/preview snippets.
- Never truncate: Working memory contents, pipeline buffers, or any persisted stage outputs.
- Env controls (0 disables):
  - `KNOWLEDGE_QUERY_TRUNCATE_CHARS` — max chars for knowledge search queries (default 400).
  - `WORKING_MEMORY_TRUNCATE_CHARS` — max chars when using working memory as a query seed (default 300).
  - `OUTPUT_EXCERPT_TRUNCATE_CHARS` — max chars for execution output excerpts in notes/logs (default 300).
- Rationale: Truncating what Cyborgs read creates confusion; only trim what the model searches or what we preview in logs.
