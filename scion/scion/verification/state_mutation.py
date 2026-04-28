"""V5_solution_consistency: verify output solution is internally consistent.

Runs the candidate solver on a canary case and checks that the output
solution has correct internal structure (assignment ↔ vehicle membership).
Classifies failures as ENV / CANDIDATE / UNKNOWN for diagnosis.

Semantic rename: was V5_solution_consistency in v0.2, now V5_solution_consistency (W11).
"""
from __future__ import annotations

import json
import os
import time
from typing import Literal

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
    """V5_solution_consistency: output must be internally consistent."""
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
        return _cr(False, f"solver run failed: {exc}", t0, diagnosis="ENV")

    if not result.success or result.output_path is None:
        detail = "solver run failed or no output"
        if result.stderr:
            detail = f"solver run failed: {result.stderr.strip()}"
        return _cr(False, detail, t0, diagnosis="ENV")

    try:
        with open(result.output_path, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as exc:
        return _cr(False, f"could not read output: {exc}", t0, diagnosis="ENV")

    issues = _check_solution_consistency(raw)
    if issues:
        diag = _classify_consistency_failure(issues)
        detail = json.dumps({
            "check": "solution_consistency",
            "diagnosis": diag,
            "issues": issues,
        })
        return _cr(False, detail, t0, diagnosis=diag)

    return _cr(True, "solution internally consistent after solver run", t0)


def _classify_consistency_failure(
    issues: list[str],
) -> Literal["ENV", "CANDIDATE", "UNKNOWN"]:
    """Classify consistency failure into ENV / CANDIDATE / UNKNOWN.

    - ENV: infrastructure issue (empty output, file read error)
    - CANDIDATE: operator-induced corruption (duplicate orders, assignment mismatch)
    - UNKNOWN: can't determine root cause
    """
    candidate_patterns = ["multiple vehicles", "assignment says", "not in assignment", "not in any vehicle"]
    for issue in issues:
        if any(p in issue for p in candidate_patterns):
            return "CANDIDATE"
    env_patterns = ["empty vehicle"]
    for issue in issues:
        if any(p in issue for p in env_patterns):
            return "ENV"
    return "UNKNOWN"


def _check_solution_consistency(raw: dict) -> list[str]:
    """Check that the output solution is internally consistent."""
    issues: list[str] = []

    solution = raw.get("solution")
    if not isinstance(solution, dict) or not (
        "assignment" in solution or "vehicles" in solution
    ):
        solution = raw
    assignment = solution.get("assignment", {})
    vehicles = solution.get("vehicles", {})

    if not assignment and not vehicles:
        return issues

    order_to_vehicle: dict[str, str] = {}
    for vid, vehicle in vehicles.items():
        for oid in vehicle.get("order_ids", []):
            if oid in order_to_vehicle:
                issues.append(
                    f"order {oid} in multiple vehicles: "
                    f"{order_to_vehicle[oid]} and {vid}"
                )
            order_to_vehicle[oid] = vid

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

    for vid, vehicle in vehicles.items():
        if not vehicle.get("order_ids"):
            issues.append(f"empty vehicle {vid} in output")

    return issues


def _cr(
    passed: bool, detail: str, t0: int,
    diagnosis: Literal["ENV", "CANDIDATE", "UNKNOWN"] | None = None,
) -> CheckResult:
    elapsed = int((time.monotonic_ns() - t0) / 1_000_000)
    name = "V5_solution_consistency"
    if diagnosis and not passed:
        detail = f"[{diagnosis}] {detail}"
    return CheckResult(
        name=name,
        passed=passed,
        severity="heavy",
        detail=detail,
        elapsed_ms=elapsed,
    )
