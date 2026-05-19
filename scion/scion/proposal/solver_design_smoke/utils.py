"""Small shared helpers for solver-design runtime smoke."""

from __future__ import annotations

import os
from pathlib import PurePosixPath
from typing import Any, Mapping


def _attr(value: Any, name: str, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _normalize_solver_design_surface(value: Any) -> str:
    surface = str(value or "").strip()
    if surface == "solver_algorithm":
        return "solver_design"
    return surface


def _normalize_rel_path(path: str) -> str | None:
    raw_path = str(path).replace(os.sep, "/")
    if raw_path.startswith("/"):
        return None
    raw = raw_path
    if not raw or raw in {".", ".."}:
        return None
    parts = PurePosixPath(raw).parts
    if any(part in {"..", ""} for part in parts):
        return None
    return "/".join(parts)


def _limit_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    suffix = "\n[truncated by proposal tool result budget]"
    return text[: max(0, max_chars - len(suffix))] + suffix


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
