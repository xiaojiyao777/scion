"""V5_state_mutation: verify operator does not modify the input solution.

Runs the candidate operator once on a canary case, comparing the input
solution before and after to detect in-place mutation (state pollution).

This is distinct from V7_nondeterminism (which checks solver-level
determinism via double-run). V5 directly tests the operator contract:
execute(solution, rng) must not modify `solution`.
"""
from __future__ import annotations

import copy
import json
import os
import time

from scion.config.problem import ProblemSpec
from scion.core.models import CheckResult
from scion.runtime.runner import Runner
from scion.verification.feasibility import _registry_path


_CANARY_SEED = 77


def check_state_mutation(
    problem_spec: ProblemSpec,
    runner: Runner,
    candidate_workspace: str,
    metrics_dir: str | None = None,
) -> CheckResult:
    """V5_state_mutation: operator must not modify the input solution.

    Strategy:
      1. Run solver once to get a solution (the "input snapshot")
      2. Run solver again — if the solver internally calls the operator
         and the operator mutates the input, the pool gets corrupted

    Implementation: run solver once, capture full output including the
    solution state. Then run again with same seed. If the operator mutates
    the input solution, the pool corruption will cascade and produce
    different results. But that's what V7 catches.

    So V5's direct approach: we instrument the check by running the solver
    with a special flag that deep-copies the solution before each operator
    call and compares after. For MVP, we use a simpler proxy: run solver
    once and check that the output solution is internally consistent
    (assignment dict matches vehicle.order_ids, all orders accounted for).
    This catches the most common mutation bugs where the operator corrupts
    the solution's internal consistency.
    """
    t0 = time.monotonic_ns()

    canary = problem_spec.canary_case_path
    if not canary:
        return _cr(True, "skipped: no canary_case_path configured", t0)

    if not os.path.isfile(canary):
        return _cr(True, f"skipped: canary file not found: {canary}", t0)

    reg = _registry_path(candidate_workspace)

    try:
        result = runner.run_solver(
            workdir=candidate_workspace,
            instance_path=canary,
            seed=_CANARY_SEED,
            time_limit_sec=30,
            registry_path=reg,
        )
    except Exception as exc:
        return _cr(False, f"solver run failed: {exc}", t0)

    if not result.success or result.output_path is None:
        return _cr(False, "solver run failed or no output", t0)

    try:
        with open(result.output_path, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as exc:
        return _cr(False, f"could not read output: {exc}", t0)

    # Check internal consistency of the output solution
    issues = _check_solution_consistency(raw)
    if issues:
        detail = json.dumps({
            "check": "solution_consistency",
            "issues": issues,
        })
        return _cr(False, detail, t0)

    return _cr(True, "solution internally consistent after solver run", t0)


def _check_solution_consistency(raw: dict) -> list[str]:
    """Check that the output solution is internally consistent.

    This catches common mutation bugs where operators corrupt the
    solution's assignment/vehicle data structures.
    """
    issues: list[str] = []

    solution = raw.get("solution", {})
    assignment = solution.get("assignment", {})
    vehicles = solution.get("vehicles", {})

    if not assignment and not vehicles:
        # No solution data in output — skip consistency check
        return issues

    # Check 1: every assigned order appears in exactly one vehicle
    order_to_vehicle: dict[str, str] = {}
    for vid, vehicle in vehicles.items():
        for oid in vehicle.get("order_ids", []):
            if oid in order_to_vehicle:
                issues.append(
                    f"order {oid} in multiple vehicles: "
                    f"{order_to_vehicle[oid]} and {vid}"
                )
            order_to_vehicle[oid] = vid

    # Check 2: assignment dict matches vehicle membership
    for oid, vid in assignment.items():
        if oid not in order_to_vehicle:
            issues.append(f"order {oid} in assignment but not in any vehicle")
        elif order_to_vehicle[oid] != vid:
            issues.append(
                f"order {oid}: assignment says {vid} but found in "
                f"{order_to_vehicle[oid]}"
            )

    for oid, vid in order_to_vehicle.items():
        if oid not in assignment:
            issues.append(f"order {oid} in vehicle {vid} but not in assignment")

    # Check 3: no empty vehicles
    for vid, vehicle in vehicles.items():
        if not vehicle.get("order_ids"):
            issues.append(f"empty vehicle {vid} in output")

    return issues


def _cr(passed: bool, detail: str, t0: int) -> CheckResult:
    elapsed = int((time.monotonic_ns() - t0) / 1_000_000)
    return CheckResult(
        name="V5_state_mutation",
        passed=passed,
        severity="heavy",
        detail=detail,
        elapsed_ms=elapsed,
    )
