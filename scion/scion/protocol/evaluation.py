from __future__ import annotations
from typing import Literal
from scion.core.models import SolverOutput


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
