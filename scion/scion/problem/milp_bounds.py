"""MILP bounds integration — offline precomputed bounds for reporting.

MILP results are precomputed offline and stored as JSON files:
    <problem_root>/milp_bounds/<instance_stem>.json

Format:
    {
        "subcategory_splits": <int>,
        "total_cost": <int>,
        "status": "optimal" | "feasible",
        "gap": <float>,           # MIP gap (0.0 for optimal)
        "solver_time_sec": <float>
    }

The adapter's estimate_lower_bound() reads these files.
This module provides gap computation for reporting.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from scion.problem.contracts import LowerBoundEstimate


@dataclass(frozen=True)
class OptimumGapReport:
    metric_name: str
    champion_value: int | float
    bound_value: int | float
    gap: float
    bound_kind: str


def compute_optimum_gap(
    champion_objective: Mapping[str, int | float],
    bound: LowerBoundEstimate,
) -> OptimumGapReport:
    champ_val = champion_objective.get(bound.metric_name)
    if champ_val is None or bound.value == 0:
        gap = float("inf")
    else:
        gap = (float(champ_val) - float(bound.value)) / abs(float(bound.value))

    return OptimumGapReport(
        metric_name=bound.metric_name,
        champion_value=champ_val if champ_val is not None else 0,
        bound_value=bound.value,
        gap=gap,
        bound_kind=bound.kind,
    )
