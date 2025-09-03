"""Knowledge Context Builder

Utilities to assemble concise, stage-appropriate knowledge snippets from the
Knowledge API for inclusion in LLM prompts. Applies light budgets, deduping,
and optional tag filtering to avoid overwhelming working memory.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set
import json
import os
from .constants import (
    DEFAULT_MIN_SCORE,
    DEFAULT_BUDGET_CHARS,
    DEFAULT_QUERY_TRUNCATE_CHARS,
    MAX_ACTIVE_TODOS
)

# Allow environment override for truncation
KNOWLEDGE_QUERY_TRUNCATE_CHARS = int(
    os.environ.get("KNOWLEDGE_QUERY_TRUNCATE_CHARS", DEFAULT_QUERY_TRUNCATE_CHARS)
)


logger = logging.getLogger("Cyber.knowledge.context_builder")


@dataclass
class KnowledgeSnippet:
    """Represents a single knowledge snippet with metadata."""
    id: str
    content: str
    score: float
    source: str
    tags: Optional[str]


class KnowledgeContextBuilder:
    """Builds concise knowledge context strings for stage prompts."""

    def __init__(self, knowledge_manager: Any, memory_system: Any, state_manager: Any) -> None:
        """Initialize the context builder.
        
        Args:
            knowledge_manager: Knowledge manager instance
            memory_system: Memory system instance
            state_manager: State manager instance
        """
        self.knowledge_manager = knowledge_manager
        self.memory_system = memory_system
        self.state_manager = state_manager

    def build(
        self,
        stage: str,
        queries: Sequence[str],
        *,
        limit: int = 3,
        budget_chars: int = DEFAULT_BUDGET_CHARS,
        blacklist_tags: Optional[Set[str]] = None,
        min_score: float = DEFAULT_MIN_SCORE,
    ) -> str:
        """Search and format knowledge for a stage.

        - Searches using provided queries (best effort; stops when budget is met)
        - Deduplicates by id
        - Filters by min_score and optional tag blacklist
        - Trims to a character budget for predictable token usage
        """
        blacklist_tags = blacklist_tags or set()
        
        # Build prioritized query list
        q = self._build_query_list(queries)
        if not q:
            return ""
        
        # Collect relevant knowledge snippets
        collected = self._collect_knowledge_snippets(
            q, limit, min_score, blacklist_tags
        )
        if not collected:
            return ""
        
        # Order and format results
        return self._format_knowledge_results(
            collected, stage, budget_chars
        )
    
    def _build_query_list(self, queries: Sequence[str]) -> List[str]:
        """Build a prioritized list of queries."""
        q: List[str] = []
        
        # Priority 1: Current task context
        task_summary = self._current_task_summary()
        if task_summary:
            q.append(task_summary)
        
        decision_intent = self._current_decision_intention()
        if decision_intent:
            q.append(decision_intent)
        
        active_todos = self._active_task_summaries()
        if active_todos:
            q.append(active_todos)
        
        # Priority 2: Provided queries
        for s in queries:
            s = (s or "").strip()
            if s:
                q.append(self._truncate_query(s))
        
        # Priority 3: Historical context
        reflection = self._recent_reflection_summary()
        if reflection:
            q.append(reflection)
        
        # Priority 4: Location
        current_loc = self._current_location()
        if current_loc:
            q.append(str(current_loc))
        
        return q
    
    def _truncate_query(self, query: str) -> str:
        """Truncate query string if needed."""
        if KNOWLEDGE_QUERY_TRUNCATE_CHARS and KNOWLEDGE_QUERY_TRUNCATE_CHARS > 0:
            return query[:KNOWLEDGE_QUERY_TRUNCATE_CHARS]
        return query
    
    def _collect_knowledge_snippets(
        self,
        queries: List[str],
        limit: int,
        min_score: float,
        blacklist_tags: Set[str]
    ) -> Dict[str, KnowledgeSnippet]:
        """Collect relevant knowledge snippets from searches."""
        collected: Dict[str, KnowledgeSnippet] = {}
        
        for query in queries:
            try:
                results = self.knowledge_manager.search_knowledge(
                    query=query, limit=limit
                )
            except Exception as e:
                logger.debug(f"Knowledge search failed for '{query[:60]}...': {e}")
                results = []
            
            for item in results or []:
                snippet = self._process_search_result(
                    item, min_score, blacklist_tags
                )
                if snippet and snippet.id not in collected:
                    collected[snippet.id] = snippet
        
        return collected
    
    def _process_search_result(
        self,
        item: Dict[str, Any],
        min_score: float,
        blacklist_tags: Set[str]
    ) -> Optional[KnowledgeSnippet]:
        """Process a single search result into a snippet."""
        try:
            kid = str(item.get("id", ""))
            if not kid:
                return None
            
            score = float(item.get("score", 0.0))
            if score < min_score:
                return None
            
            # Check blacklisted tags
            tags = item.get("metadata", {}).get("tags")
            if tags and self._has_blacklisted_tag(tags, blacklist_tags):
                return None
            
            content = str(item.get("content", "")).strip()
            if not content:
                return None
            
            return KnowledgeSnippet(
                id=kid,
                content=content,
                score=score,
                source=str(item.get("source", "shared")),
                tags=str(tags) if tags else None,
            )
        except Exception:
            return None
    
    def _has_blacklisted_tag(self, tags: Any, blacklist: Set[str]) -> bool:
        """Check if tags contain any blacklisted tag."""
        # Tags are stored as comma-separated string
        tag_list = str(tags).split(",")
        return any(t.strip() in blacklist for t in tag_list)
    
    def _format_knowledge_results(
        self,
        collected: Dict[str, KnowledgeSnippet],
        stage: str,
        budget_chars: int
    ) -> str:
        """Format collected knowledge snippets within budget."""
        # Order by score desc, prefer personal over shared when equal
        ordered = sorted(
            collected.values(),
            key=lambda s: (s.score, 1 if s.source == "shared" else 2),
            reverse=True,
        )
        
        lines: List[str] = [f"## Helpful Knowledge ({stage})"]
        used = 0
        
        for i, snip in enumerate(ordered, 1):
            formatted = self._format_snippet(snip, i, budget_chars - used)
            if not formatted:
                break
            
            lines.append(formatted)
            used += len(formatted)
            
            if used >= budget_chars:
                break
        
        return "\n".join(lines).strip()
    
    def _format_snippet(
        self,
        snip: KnowledgeSnippet,
        index: int,
        remaining_budget: int
    ) -> Optional[str]:
        """Format a single knowledge snippet."""
        header = f"\n{index}. [Relevance {snip.score:.2f}] ({snip.source})\n"
        body_budget = remaining_budget - len(header) - 32
        
        if body_budget <= 0:
            return None
        
        body = snip.content
        if len(body) > body_budget:
            body = body[: body_budget - 3] + "..."
        
        return header + body

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
                    if len(items) >= MAX_ACTIVE_TODOS:
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
