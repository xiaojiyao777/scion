from __future__ import annotations
import os
from collections.abc import Iterable
from typing import Literal


DEFAULT_LEXICOGRAPHIC_DELTA_WEIGHT = 100000


def metric_order_from_objectives(
    candidate_objective: dict,
    champion_objective: dict,
    metric_order: Iterable[str] | None = None,
) -> list[str]:
    """Return explicit metric order or merged objective key order."""
    if metric_order is not None:
        return [str(name) for name in metric_order]
    ordered: list[str] = []
    for objective in (candidate_objective, champion_objective):
        for name in objective:
            if name not in ordered:
                ordered.append(name)
    return ordered


def lexicographic_compare(
    candidate_objective: dict,
    champion_objective: dict,
    metric_order: Iterable[str] | None = None,
) -> Literal["win", "loss", "tie"]:
    """
    Generic lexicographic multi-objective comparison.

    All metrics are treated as minimization objectives in this legacy fallback.
    Returns "win" if candidate is better than champion, "loss" if worse, "tie" if equal.
    """
    for name in metric_order_from_objectives(
        candidate_objective,
        champion_objective,
        metric_order,
    ):
        cand_value = candidate_objective.get(name, 0)
        champ_value = champion_objective.get(name, 0)
        if cand_value < champ_value:
            return "win"
        if cand_value > champ_value:
            return "loss"

    return "tie"


def compute_delta(
    candidate_objective: dict,
    champion_objective: dict,
    metric_order: Iterable[str] | None = None,
) -> float:
    """
    Compute a generic lexicographic-minimize legacy delta.

    Single-metric fallback returns champion minus candidate. Multi-metric
    fallback returns the first differing metric delta, with a large weight for
    non-final decisive dimensions to preserve legacy lexicographic dominance.
    Positive value means candidate is better than champion.
    """
    order = metric_order_from_objectives(
        candidate_objective,
        champion_objective,
        metric_order,
    )
    if not order:
        return 0.0

    # DEPRECATED(v0.3): Use scion.problem.objectives.compare_lexicographic instead.
    # This legacy fallback remains for compatibility with callers without metric specs.
    weight = int(
        os.environ.get(
            "SCION_LEXICOGRAPHIC_DELTA_WEIGHT",
            str(DEFAULT_LEXICOGRAPHIC_DELTA_WEIGHT),
        )
    )
    for idx, name in enumerate(order):
        cand_value = candidate_objective.get(name, 0)
        champ_value = champion_objective.get(name, 0)
        signed_delta = float(champ_value) - float(cand_value)
        if signed_delta == 0:
            continue
        if len(order) > 1 and idx < len(order) - 1:
            return signed_delta * weight
        return signed_delta
    return 0.0
