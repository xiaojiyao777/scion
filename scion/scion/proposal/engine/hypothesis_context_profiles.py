"""Lossless prompt-context handoff for direct V3 hypothesis generation."""

from __future__ import annotations

from typing import Any, Mapping


def filter_hypothesis_context_for_prompt(
    context: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the complete context; direct V3 has no ablation or compact profile."""

    return dict(context)


__all__ = ["filter_hypothesis_context_for_prompt"]
