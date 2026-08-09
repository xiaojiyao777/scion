from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CaseLevelResult:
    """Aggregated result for a single case across all seeds."""
    case_id: str
    comparison: str   # preregistered case direction: "win" / "loss" / "tie"
    delta: float      # preregistered case-level effect
    metric_deltas: dict[str, float] | None = None

__all__ = ["CaseLevelResult"]
