"""Weight optimizer: random initialization + local perturbation."""
from __future__ import annotations

import math
import random
import time
from typing import Callable, Dict, List, Optional, Tuple

from scion.core.models import WeightOptimizationResult
from scion.parameter.search_space import ParameterSearchSpace


class RandomLocalWeightOptimizer:
    """Bayesian-free optimizer: random init + local perturbation around best.

    Search in log-space for natural positivity constraint.
    """

    def __init__(
        self,
        search_space: ParameterSearchSpace,
        evaluator_fn: Callable[[Dict[str, float]], float],
        seed: int = 0,
    ) -> None:
        self._space = search_space
        self._eval_fn = evaluator_fn  # weights -> median_delta
        self._rng = random.Random(seed)

    def optimize(self) -> WeightOptimizationResult:
        """Run optimization. Returns result with best weights found."""
        t0 = time.time()
        names = list(self._space.operator_names)
        lo, hi = math.log(self._space.weight_bounds[0]), math.log(self._space.weight_bounds[1])

        observations: List[Tuple[Dict[str, float], float]] = []

        # Phase 1: evaluate baseline (current weights via eval_fn with no change)
        # The caller should have set up the evaluator to compare against baseline

        # Phase 2: random initialization
        for _ in range(self._space.n_initial_random):
            w = self._random_weights(names, lo, hi)
            score = self._eval_fn(w)
            observations.append((w, score))

        # Find best so far
        best_w, best_score = max(observations, key=lambda x: x[1])

        # Phase 3: local perturbation around best
        for i in range(self._space.n_iterations):
            sigma = 0.3 * (1.0 - i / max(self._space.n_iterations, 1))  # decay
            w = self._perturb(best_w, names, lo, hi, sigma)
            score = self._eval_fn(w)
            observations.append((w, score))
            if score > best_score:
                best_w, best_score = w, score

        elapsed = time.time() - t0

        # Baseline score is first observation (or 0 if no observations)
        baseline_score = observations[0][1] if observations else 0.0
        baseline_weights = observations[0][0] if observations else {}

        return WeightOptimizationResult(
            baseline_weights=baseline_weights,
            best_weights=best_w,
            baseline_score=baseline_score,
            best_score=best_score,
            improved=best_score > baseline_score,
            n_evaluations=len(observations),
            elapsed_seconds=round(elapsed, 1),
            observations_ref="",  # caller fills this if saving to disk
        )

    def _random_weights(self, names: List[str], lo: float, hi: float) -> Dict[str, float]:
        return {n: math.exp(self._rng.uniform(lo, hi)) for n in names}

    def _perturb(
        self, base: Dict[str, float], names: List[str],
        lo: float, hi: float, sigma: float,
    ) -> Dict[str, float]:
        result = {}
        for n in names:
            log_w = math.log(base[n]) + self._rng.gauss(0, sigma)
            log_w = max(lo, min(hi, log_w))  # clamp
            result[n] = math.exp(log_w)
        return result
