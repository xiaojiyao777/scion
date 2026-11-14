from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass
class CaseLevelResult:
    """Aggregated result for a single case across all seeds."""
    case_id: str
    comparison: str   # preregistered case direction: "win" / "loss" / "tie"
    delta: float      # preregistered case-level effect
    metric_deltas: dict[str, float] | None = None


@dataclass(frozen=True)
class PairedExecutionSpec:
    candidate_ordinal: int
    block_id: str
    block_ordinal: int
    case_ordinals: Mapping[str, int]
    seed_ordinals: Mapping[int, int]

    def __post_init__(self) -> None:
        for name in ("case_ordinals", "seed_ordinals"):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))

__all__ = ["CaseLevelResult", "PairedExecutionSpec"]
