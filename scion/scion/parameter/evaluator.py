"""Weight evaluation function for parameter search."""
from __future__ import annotations

import os
import statistics
from typing import Dict, List, Optional

from scion.runtime.pool_manager import update_weights
from scion.protocol.evaluation import compute_delta


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
) -> float:
    """Evaluate a weight configuration. Returns median delta (positive = better than baseline).

    Steps:
    1. Write weights to workspace's registry.yaml.
    2. For each (case, seed), run solver with new weights.
    3. Compute delta vs baseline using compute_delta().
    4. Return median delta; 0.0 if no successful runs.

    Note: modifies the workspace's registry.yaml in-place. The caller is
    responsible for using a dedicated evaluation workspace, not the champion
    snapshot directly.
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

            deltas.append(compute_delta(cand_obj, champ_obj))

    if not deltas:
        return 0.0
    return statistics.median(deltas)
