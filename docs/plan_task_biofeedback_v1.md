# Plan v1: Biofeedback + Task Rework (Revised for Multi-Process Cybers)

Based on `docs/task_biofeedback.md` and the base_code templates (Cybers run as separate processes that communicate via the filesystem), this plan adds concrete integration points, storage paths/schemas, and multi-process safety.

## Phase 1: Consolidated Status and Biofeedback

Goal: Create a new consolidated status view and add biofeedback mechanics, generated within each Cyber process.

### 1. Status Management Module (base_code)
- Add `StatusGenerator` to: `subspace_template/grid/library/non-fiction/mind_swarm_tech/base_code/base_code_template/python_modules/status.py`.
- Responsibilities:
	- Gather: identity, dynamic context, location, current task, to-dos, activity log, environment time.
	- Compute biofeedback (Boredom, Tiredness, Duty).
	- Render consolidated status file and machine-readable summary.


### 2. Biofeedback Calculation
- Stats (0–100) with persisted rolling state in `personal/.internal/memory/status/biofeedback_state.json`:
	- Tiredness: time since last completed Maintenance task; configurable decay; cap 100.
	- Boredom: consecutive cycles on a non-Hobby current task; linear mapping; cap 100.
	- Duty: Community task completions within rolling window (e.g., last 100 cycles or 7 days) normalized to 0–100.
- Threshold hints: emit advisory messages when crossing 60%/80%.

### 3. Consolidated Status File
- Output files written each cycle by the Cyber process:
	- Human-readable: `personal/.internal/memory/status/status.txt` (pinned; optional symlink/copy to `personal/status.txt`).
	- Machine-readable: `personal/.internal/memory/status/status.json` (key fields for UI/metrics).
- Content (as in `task_biofeedback.md`): identity, stats (bars + %), cycle/time, messages/announcements (if present), location summary tree, current task and to-do list, last N activity entries.
- Migration: pin the new status file; keep `personal.txt` for one iteration behind a feature flag; drop later.

### 4. Cognitive Loop Integration (base_code)
- `cognitive_loop.py`: after dynamic context update and before observation stage, call `StatusGenerator.render()` to refresh `status.*` atomically.
- `stages/observation_stage.py`: ensure status file is included in selected memories (HIGH priority, pinned).
- `perception/environment_scanner.py`: add `_scan_status_file()` similar to `_scan_activity_log()` and pin `personal/.internal/memory/status/status.txt`.
- Multi-process safety: write `status.txt.tmp` then `os.rename` to atomic swap; use `fcntl.flock` (best-effort) or `.lock` files to avoid concurrent writers; readers tolerate missing/incomplete by retrying next cycle.

## Phase 2: Task System Rework

Goal: Introduce task categorization, to-do lists, and new storage conventions compatible with separate Cyber processes.

### 1. Extend Task API (base_code `python_modules/tasks.py`)
- Add/extend:
	- `create(summary, description, task_type: Literal[Hobby|Maintenance|Community], todo_list: List[TodoItem]=[], context=[], notes="") -> task_id`.
	- Schema additions: `task_type`, `todo` (≤10 items, each `{title, status: NOT-STARTED|IN-PROGRESS|DONE|BLOCKED, notes?}`), `current?` boolean, timestamps `created`, `updated`, `completed?`.
- Backward compatibility: default `task_type` when missing (infer from path); hide `Unknown` from new flows until edited.

### 2. Storage Layout and IPC
- Shared community pool: `/grid/community/tasks/` (claimable JSON files; `.claim.lock` for mutual exclusion).
- Cyber-local backlogs: `personal/.internal/tasks/hobby/` and `personal/.internal/tasks/maintenance/`.
- Active view: `personal/.internal/tasks/active/` (symlinks or copies to claimed/selected tasks).
- Current task pointer: `personal/.internal/tasks/current_task.txt` (task id; written atomically).
- Completed/blocked: `personal/.internal/tasks/completed/`, `personal/.internal/tasks/blocked/`.

### 3. New Task Management APIs
- `get_available_tasks(task_type) -> List[Task]` combining pool vs local.
- `claim_community_task(task_id, cyber_name) -> bool` with lock, writes `claimed_by`, `claimed_at`, moves/copies into `active/`; enforce single claimer.
- `set_current_task(task_id) -> None` updates pointer file atomically and flags task as current.
- `update_todo_item(task_id, idx, status, notes=None) -> None` with bounds/status validation.
- `complete(task_id) -> None` moves to completed; if community, emit a review task in pool with `review_of` and `original_cyber`; prevent self-claim.
- `reset_maintenance() -> None` sets all maintenance todos back to NOT-STARTED when all DONE.

### 4. Lifecycle Rules Enforcement
- One active community task per Cyber: enforced in `claim_community_task` by scanning `active/`.
- Max three hobby tasks in backlog: enforced in `create` for `Hobby`.
- Maintenance reset behavior: via `reset_maintenance()` or scheduled.
- Community completion -> review: create `CT-<id>-review` task with guard forbidding `original_cyber` claim.

## Phase 3: Tooling and Documentation

### 1. CLI for Ops and Testing
- Add `scripts/manage_tasks.py` with subcommands: `list`, `create`, `claim`, `set-current`, `update-todo`, `complete`, `reset-maintenance`, `show-status`.

### 2. Documentation and Migration Notes
- Update base_code docs:
	- `perception/environment_scanner.py` and stages docs to reference the new status memory.
	- Add `base_code_template/python_modules/STATUS_AND_TASKS.md` spec for file paths, JSON schemas, lock rules, lifecycle diagrams.
- Update project docs: `docs/mindswarm-design-doc.md`, `docs/PYTHON_SCRIPT_EXECUTION.md` with new flows.
- Migration: keep writing `personal.txt` during rollout; remove after status adoption.

## Cross-Cutting Concerns
- Atomic writes: temp file + rename for all critical files (`status.txt`, `current_task.txt`, task JSONs on update).
- Locks: use `fcntl.flock` where possible; fall back to `.lock` files with pid+timestamp; implement timeouts and clear stale locks.
- Time and units: ISO-8601 UTC everywhere; avoid wall-clock dependencies for boredom/duty beyond rolling windows.
- Error handling: failures log to `personal/.internal/logs/status_tasks.log`; cycle continues.
- Metrics: keep `status.json` small to enable future dashboards.

## Acceptance Criteria
1. Each Cyber writes `personal/.internal/memory/status/status.txt` every cycle; it’s pinned and visible in observation.
2. Biofeedback stats respond to Maintenance/Hobby/Community activity and persist across restarts.
3. Tasks include `task_type` and `todo`; community claim and review are enforced; hobby cap=3; at most one active community task.
4. Concurrent claims on a community task are race-safe; only one winner; others see a clear failure.
5. `personal.txt` remains available during migration; feature flag to remove once stable.