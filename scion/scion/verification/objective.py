"""Objective check: solver-reported objective must match oracle.recompute_objective."""
from __future__ import annotations

import json
import os
import time
from typing import TYPE_CHECKING, Optional

from scion.config.problem import ProblemSpec
from scion.core.models import CheckResult
from scion.runtime.runner import Runner
from scion.verification.feasibility import (
    _import_oracle,
    _load_solution_and_instance,
    _registry_path,
)

if TYPE_CHECKING:
    from scion.problem.contracts import ProblemAdapter


def check_objective(
    problem_spec: ProblemSpec,
    runner: Runner,
    candidate_workspace: str,
    *,
    adapter: Optional[ProblemAdapter] = None,
) -> CheckResult:
    """V7_objective: oracle.recompute_objective must match solver-reported objective."""
    t0 = time.monotonic_ns()

    canary = problem_spec.canary_case_path
    if not canary:
        return _cr(True, "heavy", "skipped: no canary_case_path configured", t0)

    if not os.path.isfile(canary):
        return _cr(True, "heavy", f"skipped: canary file not found: {canary}", t0)

    try:
        result = runner.run_solver(
            workdir=candidate_workspace,
            instance_path=canary,
            seed=43,
            time_limit_sec=30,
            registry_path=_registry_path(candidate_workspace),
        )
    except Exception as exc:
        return _cr(False, "heavy", f"runner error: {exc}", t0)

    if not result.success or result.output_path is None:
        return _cr(
            False, "heavy",
            f"solver failed: exit={result.exit_code} "
            f"category={result.error_category}",
            t0,
        )

    try:
        with open(result.output_path, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as exc:
        return _cr(False, "heavy", f"cannot read solver output: {exc}", t0)

    # --- Adapter-based path (v0.3+) ---
    if adapter is not None:
        return _check_via_adapter(adapter, raw, canary, t0)

    # --- Legacy path (direct oracle import) ---
    obj_raw = raw.get("objective", {})
    solver_splits = obj_raw.get("subcategory_splits")
    solver_cost = obj_raw.get("total_cost")

    oracle_dir = os.path.dirname(os.path.abspath(
        os.path.join(problem_spec.root_dir, problem_spec.oracle_path)
    ))
    try:
        solution, instance = _load_solution_and_instance(raw, canary, oracle_dir)
        oracle_mod = _import_oracle(oracle_dir)
        oracle_obj = oracle_mod.recompute_objective(solution, instance, solve_time_ms=0)
    except Exception as exc:
        return _cr(False, "heavy", f"oracle error: {exc}", t0)

    mismatches = []
    if solver_splits is not None and oracle_obj.subcategory_splits != solver_splits:
        mismatches.append(
            f"splits: solver={solver_splits} oracle={oracle_obj.subcategory_splits}"
        )
    if solver_cost is not None and oracle_obj.total_cost != solver_cost:
        mismatches.append(
            f"cost: solver={solver_cost} oracle={oracle_obj.total_cost}"
        )

    if mismatches:
        return _cr(False, "heavy", "objective mismatch: " + "; ".join(mismatches), t0)
    return _cr(True, "heavy", "objective matches oracle", t0)


def _check_via_adapter(
    adapter: ProblemAdapter, raw: dict, canary: str, t0: int,
) -> CheckResult:
    try:
        instance = adapter.load_instance(canary)
        artifact = adapter.deserialize_solver_output(raw, instance)
    except Exception as exc:
        return _cr(False, "heavy", f"adapter deserialize error: {exc}", t0)

    try:
        recomputed = adapter.recompute_objective(artifact, instance)
    except Exception as exc:
        return _cr(False, "heavy", f"adapter.recompute_objective error: {exc}", t0)

    mismatches = []
    for key, oracle_val in recomputed.items():
        solver_val = artifact.objective.get(key)
        if solver_val is not None and solver_val != oracle_val:
            mismatches.append(f"{key}: solver={solver_val} oracle={oracle_val}")

    if mismatches:
        return _cr(False, "heavy", "objective mismatch: " + "; ".join(mismatches), t0)
    return _cr(True, "heavy", "objective matches oracle", t0)


def _cr(passed: bool, severity: str, detail: str, t0: int) -> CheckResult:
    elapsed = int((time.monotonic_ns() - t0) / 1_000_000)
    return CheckResult(
        name="V7_objective",
        passed=passed,
        severity=severity,  # type: ignore[arg-type]
        detail=detail,
        elapsed_ms=elapsed,
    )
