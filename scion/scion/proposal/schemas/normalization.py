"""Schema-level normalization helpers for patch outputs."""

from __future__ import annotations

from typing import Any, Mapping


def normalize_patch_output_with_repair_attribution(
    raw: Mapping[str, Any],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Preserve provider output exactly; typed validation owns all failures."""

    return dict(raw), ()


__all__ = [
    "normalize_patch_output_with_repair_attribution",
]
