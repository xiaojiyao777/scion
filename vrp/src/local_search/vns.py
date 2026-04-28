from __future__ import annotations

from typing import Callable

from ..models import Solution

NeighborhoodOperator = Callable[[Solution], bool]


def vns(solution: Solution, operators: list[NeighborhoodOperator],
        max_no_improve: int = 5000) -> bool:
    """
    Variable Neighborhood Search.
    Cycle through operators; on improvement restart from operator 0.
    Returns True if any improvement was made.
    """
    improved_overall = False
    k = 0
    no_improve_count = 0

    while k < len(operators) and no_improve_count < max_no_improve:
        if operators[k](solution):
            improved_overall = True
            k = 0
            no_improve_count = 0
        else:
            k += 1
            no_improve_count += 1

    return improved_overall
