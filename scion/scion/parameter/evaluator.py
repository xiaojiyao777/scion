"""Weight evaluation function for parameter search."""
from __future__ import annotations

import os
import statistics
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence

from scion.runtime.pool_manager import update_weights
from scion.protocol.evaluation import compute_delta as legacy_compute_delta

if TYPE_CHECKING:
    from scion.problem.spec import ObjectiveMetricSpec


def collect_baseline(
    workspace: str,
    cases: List[str],
    seeds: List[int],
    runner,
    time_limit_sec: int,
) -> Dict[str, Dict[int, dict]]:
    """Run solver with current weights to collect baseline objectives.

    Returns {case_path: {seed: objective_dict}}.
    """
    registry_path = os.path.join(workspace, "registry.yaml")
    baseline: Dict[str, Dict[int, dict]] = {}
    for case in cases:
        baseline[case] = {}
        for seed in seeds:
            result = runner.run_solver(
                workdir=workspace,
                instance_path=case,
                seed=seed,
                time_limit_sec=time_limit_sec,
                registry_path=registry_path,
            )
            if result.success and result.output is not None:
                baseline[case][seed] = result.output.objective
    return baseline


def evaluate_weights(
    weights: Dict[str, float],
    workspace: str,
    cases: List[str],
    seeds: List[int],
    runner,
    time_limit_sec: int,
    baseline_objectives: Optional[Dict[str, Dict[int, dict]]] = None,
    *,
    metric_specs: Optional[Sequence[ObjectiveMetricSpec]] = None,
) -> float:
    """Evaluate a weight configuration. Returns median delta (positive = better than baseline).

    When metric_specs is provided, uses the generic comparator's scalar_delta
    instead of the legacy SCION_SPLITS_WEIGHT-based compute_delta.
    """
    registry_path = os.path.join(workspace, "registry.yaml")
    update_weights(registry_path, weights)

    if baseline_objectives is None:
        baseline_objectives = {}

    deltas = []
    for case in cases:
        for seed in seeds:
            result = runner.run_solver(
                workdir=workspace,
                instance_path=case,
                seed=seed,
                time_limit_sec=time_limit_sec,
                registry_path=registry_path,
            )
            if not result.success or result.output is None:
                continue

            cand_obj = result.output.objective
            champ_obj = (baseline_objectives.get(case) or {}).get(seed)
            if champ_obj is None:
                continue

            deltas.append(_compute_delta(cand_obj, champ_obj, metric_specs))

    if not deltas:
        return 0.0
    return statistics.median(deltas)


def _compute_delta(
    candidate: dict,
    champion: dict,
    metric_specs: Optional[Sequence[ObjectiveMetricSpec]],
) -> float:
    if metric_specs is not None:
        from scion.problem.objectives import compare_lexicographic
        result = compare_lexicographic(metric_specs, candidate, champion)
        # Use the decisive metric's delta for scoring, not scalar_delta (sum).
        # This respects lexicographic ordering: splits improvement dominates cost.
        for mc in result.metrics:
            if mc.decisive:
                return mc.signed_delta
        return 0.0  # tie
    return legacy_compute_delta(candidate, champion)
