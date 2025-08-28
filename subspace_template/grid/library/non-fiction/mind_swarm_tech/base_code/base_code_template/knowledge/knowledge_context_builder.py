"""Knowledge Context Builder

Utilities to assemble concise, stage-appropriate knowledge snippets from the
Knowledge API for inclusion in LLM prompts. Applies light budgets, deduping,
and optional tag filtering to avoid overwhelming working memory.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set
import json
from mind_swarm.core.config import KNOWLEDGE_QUERY_TRUNCATE_CHARS


logger = logging.getLogger("Cyber.knowledge.context_builder")


@dataclass
class KnowledgeSnippet:
    id: str
    content: str
    score: float
    source: str
    tags: str | None


class KnowledgeContextBuilder:
    """Builds concise knowledge context strings for stage prompts."""

    def __init__(self, knowledge_manager, memory_system, state_manager):
        self.knowledge_manager = knowledge_manager
        self.memory_system = memory_system
        self.state_manager = state_manager

    def build(
        self,
        stage: str,
        queries: Sequence[str],
        *,
        limit: int = 3,
        budget_chars: int = 1200,
        blacklist_tags: Optional[Set[str]] = None,
        min_score: float = 0.35,
    ) -> str:
        """Search and format knowledge for a stage.

        - Searches using provided queries (best effort; stops when budget is met)
        - Deduplicates by id
        - Filters by min_score and optional tag blacklist
        - Trims to a character budget for predictable token usage
        """
        blacklist_tags = blacklist_tags or set()

        # Build a prioritized list of queries:
        # 1) Current task summary/intention
        # 2) Stage-provided queries (e.g., new_information, decision context)
        # 3) Recent reflection
        # 4) Current location (lowest priority)
        q: List[str] = []

        task_summary = self._current_task_summary()
        if task_summary:
            q.append(task_summary)

        decision_intent = self._current_decision_intention()
        if decision_intent:
            q.append(decision_intent)

        # Add current TODO/active task summaries (if any)
        active_todos = self._active_task_summaries()
        if active_todos:
            q.append(active_todos)

        for s in queries:
            s = (s or "").strip()
            if s:
                if KNOWLEDGE_QUERY_TRUNCATE_CHARS and KNOWLEDGE_QUERY_TRUNCATE_CHARS > 0:
                    q.append(s[:KNOWLEDGE_QUERY_TRUNCATE_CHARS])  # basic guard
                else:
                    q.append(s)

        reflection = self._recent_reflection_summary()
        if reflection:
            q.append(reflection)

        current_loc = self._current_location()
        if current_loc:
            q.append(str(current_loc))

        if not q:
            return ""

        collected: dict[str, KnowledgeSnippet] = {}
        for query in q:
            try:
                results = self.knowledge_manager.search_knowledge(query=query, limit=limit)
            except Exception as e:
                logger.debug(f"Knowledge search failed for '{query[:60]}...': {e}")
                results = []

            for item in results or []:
                try:
                    kid = str(item.get("id", ""))
                    if not kid or kid in collected:
                        continue
                    score = float(item.get("score", 0.0))
                    if score < min_score:
                        continue
                    tags = item.get("metadata", {}).get("tags")
                    # tags are stored as comma-separated string
                    if tags and any(t.strip() in blacklist_tags for t in str(tags).split(",")):
                        continue
                    content = str(item.get("content", "")).strip()
                    if not content:
                        continue
                    collected[kid] = KnowledgeSnippet(
                        id=kid,
                        content=content,
                        score=score,
                        source=str(item.get("source", "shared")),
                        tags=str(tags) if tags else None,
                    )
                except Exception:
                    continue

        if not collected:
            return ""

        # Order by score desc, prefer personal over shared when equal
        ordered = sorted(
            collected.values(),
            key=lambda s: (s.score, 1 if s.source == "shared" else 2),
            reverse=True,
        )

        # Format with budget
        lines: List[str] = [f"## Helpful Knowledge ({stage})"]
        used = 0
        for i, snip in enumerate(ordered, 1):
            header = f"\n{i}. [Relevance {snip.score:.2f}] ({snip.source})\n"
            body_budget = max(0, budget_chars - used - len(header) - 32)
            if body_budget <= 0:
                break
            body = snip.content
            if len(body) > body_budget:
                body = body[: body_budget - 3] + "..."
            lines.append(header + body)
            used += len(header) + len(body)
            if used >= budget_chars:
                break

        return "\n".join(lines).strip()

    def _current_location(self) -> Optional[str]:
        try:
            from ..state.unified_state_manager import StateSection
            return self.state_manager.get_value(StateSection.LOCATION, "current_location")
        except Exception:
            return None

    def _current_task_summary(self) -> Optional[str]:
        try:
            from ..state.unified_state_manager import StateSection
            summary = self.state_manager.get_value(StateSection.TASK, "current_task_summary")
            if not summary:
                return None
            return (
                str(summary)[:KNOWLEDGE_QUERY_TRUNCATE_CHARS]
                if KNOWLEDGE_QUERY_TRUNCATE_CHARS and KNOWLEDGE_QUERY_TRUNCATE_CHARS > 0
                else str(summary)
            )
        except Exception:
            return None

    def _pipeline_dir(self) -> Optional[Path]:
        try:
            mem_dir: Path = getattr(self.state_manager, "memory_dir", None)
            if not mem_dir:
                return None
            p = Path(mem_dir) / "pipeline"
            return p if p.exists() else None
        except Exception:
            return None

    def _current_decision_intention(self) -> Optional[str]:
        try:
            pdir = self._pipeline_dir()
            if not pdir:
                return None
            decision_file = pdir / "decision_pipe_stage.json"
            if not decision_file.exists():
                return None
            data = json.loads(decision_file.read_text())
            intention = data.get("intention") or ""
            if not intention:
                return None
            return (
                str(intention)[:KNOWLEDGE_QUERY_TRUNCATE_CHARS]
                if KNOWLEDGE_QUERY_TRUNCATE_CHARS and KNOWLEDGE_QUERY_TRUNCATE_CHARS > 0
                else str(intention)
            )
        except Exception:
            return None

    def _recent_reflection_summary(self) -> Optional[str]:
        try:
            mem_dir: Path = getattr(self.state_manager, "memory_dir", None)
            if not mem_dir:
                return None
            reflection_file = Path(mem_dir) / "reflection_on_last_cycle.json"
            if not reflection_file.exists():
                return None
            data = json.loads(reflection_file.read_text())
            # Try a few common keys; fallback to truncated string of JSON
            for k in ("summary", "learnings", "reflection", "notes"):
                v = data.get(k)
                if isinstance(v, str) and v.strip():
                    text = v.strip()
                    return (
                        text[:KNOWLEDGE_QUERY_TRUNCATE_CHARS]
                        if KNOWLEDGE_QUERY_TRUNCATE_CHARS and KNOWLEDGE_QUERY_TRUNCATE_CHARS > 0
                        else text
                    )
            # Fallback: first 400 chars of the file
            text = reflection_file.read_text()
            return (
                text[:KNOWLEDGE_QUERY_TRUNCATE_CHARS]
                if KNOWLEDGE_QUERY_TRUNCATE_CHARS and KNOWLEDGE_QUERY_TRUNCATE_CHARS > 0
                else text
            )
        except Exception:
            return None

    def _active_task_summaries(self) -> Optional[str]:
        """Collect short summaries of active TODO items (from task files)."""
        try:
            mem_dir: Path = getattr(self.state_manager, "memory_dir", None)
            if not mem_dir:
                return None
            tasks_dir = Path(mem_dir).parent / "tasks" / "active"
            if not tasks_dir.exists():
                return None
            items: List[str] = []
            for f in sorted(tasks_dir.glob("task_*.json")):
                try:
                    data = json.loads(f.read_text())
                    title = str(data.get("title") or data.get("name") or data.get("summary") or "").strip()
                    if title:
                        items.append(title)
                    if len(items) >= 5:
                        break
                except Exception:
                    continue
            if not items:
                return None
            joined = "; ".join(items)
            return (
                "Active TODOs: " + joined[:KNOWLEDGE_QUERY_TRUNCATE_CHARS]
                if KNOWLEDGE_QUERY_TRUNCATE_CHARS and KNOWLEDGE_QUERY_TRUNCATE_CHARS > 0
                else "Active TODOs: " + joined
            )
        except Exception:
            return None
