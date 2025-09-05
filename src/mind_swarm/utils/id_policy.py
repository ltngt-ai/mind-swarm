"""ID normalization utilities for Knowledge and CBR.

Applies deterministic, path-based normalization rules:
- Lowercase
- Trim and replace spaces with '-'
- Remove leading slashes
- Use forward slashes

Knowledge IDs keep the provided relative path and file extensions, under a
namespace such as 'templates/', 'library/sections/', etc.

CBR case IDs normalize to 'cases/<...>' when a path-like value is provided.
If a non-path explicit ID is provided (e.g., 'cbr_auto_...'), it is returned
unchanged.
"""

from __future__ import annotations

from pathlib import Path


def _normalize_path_segments(path_str: str) -> str:
    """Normalize each segment: lowercase and replace spaces with hyphens.

    Keeps dots as-is (useful for knowledge filenames with extensions).
    Collapses empty segments caused by repeated slashes.
    """
    # Use POSIX separator to normalize across OSes
    posix = Path(path_str.replace("\\", "/").lstrip("/")).as_posix()
    parts = [p for p in posix.split("/") if p != ""]
    norm_parts = ["-".join(seg.strip().split()).lower() for seg in parts]
    return "/".join(norm_parts)


def normalize_knowledge_id(namespace: str, rel_path: str) -> str:
    """Normalize a knowledge ID under a namespace.

    Example: normalize_knowledge_id("templates", "Guides/Onboarding.md")
             -> "templates/guides/onboarding.md"
    """
    ns = _normalize_path_segments(namespace)
    rel = _normalize_path_segments(rel_path)
    if ns:
        return f"{ns}/{rel}" if rel else ns
    return rel


def normalize_cbr_case_id(path_or_id: str) -> str:
    """Normalize a CBR case identifier.

    - If it looks path-like (contains '/'), coerce to cases/<...>.
    - If it already starts with 'cases/', normalize after the prefix.
    - Otherwise, return unchanged (explicit non-path IDs preserved).
    """
    raw = str(path_or_id or "").strip()
    if not raw:
        return raw
    # If path-like or already namespaced
    looks_path = "/" in raw or raw.startswith("cases/")
    if looks_path:
        stripped = raw.lstrip("/")
        if stripped.startswith("cases/"):
            inner = stripped[len("cases/") :]
            return f"cases/{_normalize_path_segments(inner)}"
        return f"cases/{_normalize_path_segments(stripped)}"
    # Non-path explicit IDs: return as provided
    return raw
