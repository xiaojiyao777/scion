"""Ordinary problem reference used across the V3 pipeline."""

from __future__ import annotations

from typing import Any


def problem_reference(problem_spec: Any) -> str | None:
    """Return the declared problem id/name."""

    for attr in ("id", "problem_id", "name"):
        text = str(getattr(problem_spec, attr, None) or "").strip()
        if text:
            return text
    return None


__all__ = ["problem_reference"]
