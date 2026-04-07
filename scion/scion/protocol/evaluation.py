from __future__ import annotations
from typing import Literal, Tuple
from scion.core.models import SolverOutput, ObjectiveBreakdown


def compare_with_breakdown(
    candidate_objective: dict,
    champion_objective: dict,
) -> Tuple[Literal["win", "loss", "tie"], ObjectiveBreakdown]:
    """Lexicographic compare with full per-objective breakdown.

    Returns (comparison, breakdown) where breakdown records raw values,
    deltas, and which objective level was decisive.
    """
    cand_splits = candidate_objective.get("subcategory_splits", 0)
    champ_splits = champion_objective.get("subcategory_splits", 0)
    cand_cost = candidate_objective.get("total_cost", float("inf"))
    champ_cost = champion_objective.get("total_cost", float("inf"))

    delta_splits = champ_splits - cand_splits  # positive = candidate better
    delta_cost = champ_cost - cand_cost        # positive = candidate better

    if cand_splits < champ_splits:
        comparison = "win"
        decisive = "business_aggregation"
    elif cand_splits > champ_splits:
        comparison = "loss"
        decisive = "business_aggregation"
    elif cand_cost < champ_cost:
        comparison = "win"
        decisive = "cost"
    elif cand_cost > champ_cost:
        comparison = "loss"
        decisive = "cost"
    else:
        comparison = "tie"
        decisive = "tie"

    breakdown = ObjectiveBreakdown(
        candidate_subcategory_splits=cand_splits,
        champion_subcategory_splits=champ_splits,
        candidate_total_cost=cand_cost,
        champion_total_cost=champ_cost,
        delta_subcategory_splits=delta_splits,
        delta_total_cost=delta_cost,
        decisive_objective=decisive,
    )
    return comparison, breakdown


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
    Compute primary objective delta: champion_cost - candidate_cost.
    Positive value means candidate improved over champion.
    """
    cand_cost = candidate_objective.get("total_cost", float("inf"))
    champ_cost = champion_objective.get("total_cost", float("inf"))
    return champ_cost - cand_cost
