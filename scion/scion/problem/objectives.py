"""Generic lexicographic objective comparator.

Problem-agnostic: works with any set of named metrics with priority and direction.
Replaces the hardcoded warehouse-specific compare in protocol/evaluation.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

from scion.problem.spec import ObjectiveMetricSpec


@dataclass(frozen=True)
class MetricComparison:
    name: str
    candidate_value: int | float
    champion_value: int | float
    signed_delta: float
    relation: Literal["candidate", "champion", "tie"]
    decisive: bool = False


@dataclass(frozen=True)
class ObjectiveComparison:
    outcome: Literal["win", "loss", "tie"]
    decisive_metric: str | None
    scalar_delta: float
    metrics: tuple[MetricComparison, ...]


def compare_lexicographic(
    metric_specs: Sequence[ObjectiveMetricSpec],
    candidate: Mapping[str, int | float],
    champion: Mapping[str, int | float],
) -> ObjectiveComparison:
    """Lexicographic comparison driven by metric_specs priority order.

    Returns ObjectiveComparison with per-metric breakdown.
    """
    ordered = sorted(metric_specs, key=lambda s: s.priority)

    rows: list[MetricComparison] = []
    decisive_metric: str | None = None
    outcome: Literal["win", "loss", "tie"] = "tie"

    for spec in ordered:
        cand_val = candidate[spec.name]
        champ_val = champion[spec.name]

        if spec.direction == "minimize":
            signed_delta = float(champ_val) - float(cand_val)
        else:
            signed_delta = float(cand_val) - float(champ_val)

        tol = spec.tie_tolerance
        if signed_delta > tol:
            relation: Literal["candidate", "champion", "tie"] = "candidate"
        elif signed_delta < -tol:
            relation = "champion"
        else:
            relation = "tie"

        is_decisive = outcome == "tie" and relation != "tie"
        if is_decisive:
            decisive_metric = spec.name
            outcome = "win" if relation == "candidate" else "loss"

        rows.append(MetricComparison(
            name=spec.name,
            candidate_value=cand_val,
            champion_value=champ_val,
            signed_delta=signed_delta,
            relation=relation,
            decisive=is_decisive,
        ))

    total_delta = sum(r.signed_delta for r in rows)

    return ObjectiveComparison(
        outcome=outcome,
        decisive_metric=decisive_metric,
        scalar_delta=total_delta,
        metrics=tuple(rows),
    )
