from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class CaseLevelResult:
    """Aggregated result for a single case across all seeds."""
    case_id: str
    comparison: str   # majority vote: "win" / "loss" / "tie"
    delta: float      # median delta across seeds
    metric_deltas: Dict[str, float] | None = None

__all__ = ["CaseLevelResult"]
