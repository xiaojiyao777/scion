from __future__ import annotations
import os
from typing import Literal


def lexicographic_compare(
    candidate_objective: dict,
    champion_objective: dict,
) -> Literal["win", "loss", "tie"]:
    """
    Lexicographic multi-objective comparison.
    First minimize subcategory_splits, then minimize total_cost.
    Returns "win" if candidate is better than champion, "loss" if worse, "tie" if equal.
    """
    cand_splits = candidate_objective.get("subcategory_splits", 0)
    champ_splits = champion_objective.get("subcategory_splits", 0)

    if cand_splits < champ_splits:
        return "win"
    elif cand_splits > champ_splits:
        return "loss"

    cand_cost = candidate_objective.get("total_cost", float("inf"))
    champ_cost = champion_objective.get("total_cost", float("inf"))

    if cand_cost < champ_cost:
        return "win"
    elif cand_cost > champ_cost:
        return "loss"

    return "tie"


def compute_delta(candidate_objective: dict, champion_objective: dict) -> float:
    """
    Compute lexicographic delta aligned with the objective function.

    Since the objective is lexicographic (splits > cost > time),
    the delta must reflect the PRIMARY decisive dimension:
    - If splits differ: delta = (champ_splits - cand_splits) * SPLITS_WEIGHT
    - If splits equal:  delta = champ_cost - cand_cost

    SPLITS_WEIGHT is set large enough that any split improvement
    dominates any cost change, matching the lexicographic semantics.
    Positive value means candidate is better than champion.
    """
    cand_splits = candidate_objective.get("subcategory_splits", 0)
    champ_splits = champion_objective.get("subcategory_splits", 0)
    cand_cost = candidate_objective.get("total_cost", float("inf"))
    champ_cost = champion_objective.get("total_cost", float("inf"))

    if cand_splits != champ_splits:
        # DEPRECATED(v0.3): Use scion.problem.objectives.compare_lexicographic instead.
        # This env var will be removed when all callers migrate to the generic comparator.
        SPLITS_WEIGHT = int(os.environ.get("SCION_SPLITS_WEIGHT", "100000"))
        return (champ_splits - cand_splits) * SPLITS_WEIGHT
    else:
        # Same splits — cost is decisive
        return champ_cost - cand_cost
