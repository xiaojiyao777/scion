"""Weight optimizer: random initialization + local perturbation, and Bayesian."""
from __future__ import annotations

import json
import math
import os
import random
import time
from typing import Callable, Dict, List, Optional, Tuple

from scion.core.models import WeightOptimizationResult
from scion.parameter.search_space import ParameterSearchSpace


def _save_observations(
    observations: List[Tuple[Dict[str, float], float]],
    artifacts_dir: str,
) -> str:
    """Save observations list to a JSON file and return its path."""
    os.makedirs(artifacts_dir, exist_ok=True)
    ts = int(time.time())
    path = os.path.join(artifacts_dir, f"weight_opt_{ts}.json")
    data = [
        {"weights": w, "score": s, "timestamp": ts}
        for w, s in observations
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


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

    def optimize(
        self,
        current_weights: Dict[str, float],
        artifacts_dir: Optional[str] = None,
    ) -> WeightOptimizationResult:
        """Run optimization. Returns result with best weights found.

        Args:
            current_weights: Current champion weights — evaluated first as true baseline.
            artifacts_dir: If given, observations are saved to a JSON file here.
        """
        t0 = time.time()
        names = list(self._space.operator_names)
        lo, hi = math.log(self._space.weight_bounds[0]), math.log(self._space.weight_bounds[1])

        # T1: Evaluate true baseline (current champion weights) FIRST
        true_baseline_score = self._eval_fn(current_weights)
        observations: List[Tuple[Dict[str, float], float]] = [
            (current_weights, true_baseline_score)
        ]

        # Phase 2: random initialization
        for _ in range(self._space.n_initial_random):
            w = self._random_weights(names, lo, hi)
            score = self._eval_fn(w)
            observations.append((w, score))

        # Find best so far (including baseline)
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

        # T2: Save observations to JSON
        observations_ref = ""
        if artifacts_dir is not None:
            try:
                observations_ref = _save_observations(observations, artifacts_dir)
            except Exception:
                pass

        return WeightOptimizationResult(
            baseline_weights=current_weights,
            best_weights=best_w,
            baseline_score=true_baseline_score,
            best_score=best_score,
            improved=best_score > true_baseline_score,
            n_evaluations=len(observations),
            elapsed_seconds=round(elapsed, 1),
            observations_ref=observations_ref,
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


class BayesianWeightOptimizer:
    """Gaussian Process-based Bayesian optimization for operator weights.

    Tries skopt.gp_minimize → scipy L-BFGS-B → pure-Python UCB fallback.
    The fallback uses a UCB acquisition over a random candidate grid,
    approximating the GP posterior mean/variance with exponential
    distance-weighted statistics (no external deps required).
    """

    def __init__(
        self,
        search_space: ParameterSearchSpace,
        evaluator_fn: Callable[[Dict[str, float]], float],
        seed: int = 42,
    ) -> None:
        self._space = search_space
        self._eval_fn = evaluator_fn
        self._seed = seed

    def optimize(
        self,
        current_weights: Dict[str, float],
        artifacts_dir: Optional[str] = None,
    ) -> WeightOptimizationResult:
        """Run Bayesian optimization. Returns best weights found.

        Args:
            current_weights: Current champion weights — evaluated first as true baseline.
            artifacts_dir: If given, observations are saved to a JSON file here.
        """
        try:
            return self._optimize_skopt(current_weights, artifacts_dir)
        except ImportError:
            pass
        try:
            return self._optimize_scipy(current_weights, artifacts_dir)
        except ImportError:
            pass
        return self._optimize_pure_python(current_weights, artifacts_dir)

    # ------------------------------------------------------------------
    # skopt backend
    # ------------------------------------------------------------------

    def _optimize_skopt(
        self,
        current_weights: Dict[str, float],
        artifacts_dir: Optional[str] = None,
    ) -> WeightOptimizationResult:
        from skopt import gp_minimize  # type: ignore
        from skopt.space import Real  # type: ignore

        t0 = time.time()
        names = list(self._space.operator_names)
        lb, ub = self._space.weight_bounds
        dimensions = [Real(lb, ub, name=n, prior="log-uniform") for n in names]

        # T1: Evaluate true baseline first
        true_baseline_score = self._eval_fn(current_weights)
        observations: List[Tuple[Dict[str, float], float]] = [
            (current_weights, true_baseline_score)
        ]

        def objective(x):
            w = dict(zip(names, x))
            score = self._eval_fn(w)
            observations.append((w, score))
            return -score

        result = gp_minimize(
            objective, dimensions,
            n_calls=self._space.n_initial_random + self._space.n_iterations,
            n_initial_points=self._space.n_initial_random,
            random_state=self._seed,
        )

        best_weights = dict(zip(names, result.x))
        best_score = -result.fun

        observations_ref = ""
        if artifacts_dir is not None:
            try:
                observations_ref = _save_observations(observations, artifacts_dir)
            except Exception:
                pass

        return WeightOptimizationResult(
            baseline_weights=current_weights,
            best_weights=best_weights,
            baseline_score=true_baseline_score,
            best_score=best_score,
            improved=best_score > true_baseline_score,
            n_evaluations=len(observations),
            elapsed_seconds=round(time.time() - t0, 1),
            observations_ref=observations_ref,
        )

    # ------------------------------------------------------------------
    # scipy backend (L-BFGS-B with multiple random restarts)
    # ------------------------------------------------------------------

    def _optimize_scipy(
        self,
        current_weights: Dict[str, float],
        artifacts_dir: Optional[str] = None,
    ) -> WeightOptimizationResult:
        import numpy as np  # type: ignore
        from scipy.optimize import minimize  # type: ignore

        t0 = time.time()
        names = list(self._space.operator_names)
        lb, ub = self._space.weight_bounds
        log_lb, log_ub = math.log(lb), math.log(ub)
        bounds = [(log_lb, log_ub)] * len(names)
        rng = np.random.RandomState(self._seed)

        # T1: Evaluate true baseline first
        true_baseline_score = self._eval_fn(current_weights)
        observations: List[Tuple[Dict[str, float], float]] = [
            (current_weights, true_baseline_score)
        ]

        best_score = float('-inf')
        best_weights: Dict[str, float] = {}

        n_restarts = self._space.n_initial_random
        max_iter_per_restart = max(1, self._space.n_iterations // max(n_restarts, 1))

        for _ in range(n_restarts):
            x0 = rng.uniform(log_lb, log_ub, size=len(names))

            def neg_score(x, _names=names, _obs=observations):
                w = dict(zip(_names, [math.exp(v) for v in x]))
                score = self._eval_fn(w)
                _obs.append((w, score))
                return -score

            res = minimize(
                neg_score, x0, method='L-BFGS-B', bounds=bounds,
                options={'maxiter': max_iter_per_restart},
            )

            score = -res.fun
            if score > best_score:
                best_score = score
                best_weights = dict(zip(names, [math.exp(v) for v in res.x]))

        observations_ref = ""
        if artifacts_dir is not None:
            try:
                observations_ref = _save_observations(observations, artifacts_dir)
            except Exception:
                pass

        return WeightOptimizationResult(
            baseline_weights=current_weights,
            best_weights=best_weights,
            baseline_score=true_baseline_score,
            best_score=best_score,
            improved=best_score > true_baseline_score,
            n_evaluations=len(observations),
            elapsed_seconds=round(time.time() - t0, 1),
            observations_ref=observations_ref,
        )

    # ------------------------------------------------------------------
    # Pure-Python UCB fallback (no external deps)
    # ------------------------------------------------------------------

    def _optimize_pure_python(
        self,
        current_weights: Dict[str, float],
        artifacts_dir: Optional[str] = None,
    ) -> WeightOptimizationResult:
        """UCB acquisition over random candidate grid — pure Python, no deps."""
        t0 = time.time()
        names = list(self._space.operator_names)
        lo = math.log(self._space.weight_bounds[0])
        hi = math.log(self._space.weight_bounds[1])
        rng = random.Random(self._seed)

        # Observations: list of (log_x_vector, score)
        obs_x: List[List[float]] = []
        obs_y: List[float] = []
        obs_weights: List[Dict[str, float]] = []

        def _random_log_x() -> List[float]:
            return [rng.uniform(lo, hi) for _ in names]

        def _to_weights(log_x: List[float]) -> Dict[str, float]:
            return {n: math.exp(v) for n, v in zip(names, log_x)}

        def _to_log_x(weights: Dict[str, float]) -> List[float]:
            return [math.log(max(weights.get(n, math.exp(lo)), math.exp(lo))) for n in names]

        def _sq_dist(a: List[float], b: List[float]) -> float:
            return sum((ai - bi) ** 2 for ai, bi in zip(a, b))

        def _ucb(log_x: List[float], kappa: float = 2.0) -> float:
            """UCB acquisition: mean + kappa * std, estimated from observations."""
            if not obs_x:
                return float('inf')
            # Kernel bandwidth ~ (hi - lo) / 2
            h2 = ((hi - lo) / 2.0) ** 2
            total_w = 0.0
            mean = 0.0
            for xi, yi in zip(obs_x, obs_y):
                d2 = _sq_dist(log_x, xi)
                w = math.exp(-d2 / (2.0 * h2 + 1e-12))
                total_w += w
                mean += w * yi
            if total_w < 1e-12:
                mean_est = sum(obs_y) / len(obs_y)
                var_est = sum((y - mean_est) ** 2 for y in obs_y) / len(obs_y)
            else:
                mean_est = mean / total_w
                # Variance estimate
                var_num = sum(
                    math.exp(-_sq_dist(log_x, xi) / (2.0 * h2 + 1e-12)) * (yi - mean_est) ** 2
                    for xi, yi in zip(obs_x, obs_y)
                )
                var_est = var_num / (total_w + 1e-12)
            return mean_est + kappa * math.sqrt(max(var_est, 0.0))

        # T1: Evaluate true baseline (current_weights) first
        true_baseline_score = self._eval_fn(current_weights)
        baseline_log_x = _to_log_x(current_weights)
        obs_x.append(baseline_log_x)
        obs_y.append(true_baseline_score)
        obs_weights.append(current_weights)

        # Phase 1: random initialization
        for _ in range(self._space.n_initial_random):
            lx = _random_log_x()
            w = _to_weights(lx)
            score = self._eval_fn(w)
            obs_x.append(lx)
            obs_y.append(score)
            obs_weights.append(w)

        best_idx = max(range(len(obs_y)), key=lambda i: obs_y[i])
        best_score = obs_y[best_idx]
        best_weights = obs_weights[best_idx]

        # Phase 2: UCB-guided search
        n_candidates = 16  # candidates per iteration
        for _ in range(self._space.n_iterations):
            # Generate random candidates and pick the one with max UCB
            candidates = [_random_log_x() for _ in range(n_candidates)]
            best_cand = max(candidates, key=_ucb)
            w = _to_weights(best_cand)
            score = self._eval_fn(w)
            obs_x.append(best_cand)
            obs_y.append(score)
            obs_weights.append(w)
            if score > best_score:
                best_score = score
                best_weights = w

        observations: List[Tuple[Dict[str, float], float]] = list(zip(obs_weights, obs_y))

        observations_ref = ""
        if artifacts_dir is not None:
            try:
                observations_ref = _save_observations(observations, artifacts_dir)
            except Exception:
                pass

        return WeightOptimizationResult(
            baseline_weights=current_weights,
            best_weights=best_weights,
            baseline_score=true_baseline_score,
            best_score=best_score,
            improved=best_score > true_baseline_score,
            n_evaluations=len(obs_y),
            elapsed_seconds=round(time.time() - t0, 1),
            observations_ref=observations_ref,
        )
