from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ParameterSearchSpace:
    operator_names: Tuple[str, ...]
    weight_bounds: Tuple[float, float] = (0.05, 5.0)
    n_initial_random: int = 8
    n_iterations: int = 8
    n_eval_seeds: int = 2
    eval_cases: Tuple[str, ...] = ()
