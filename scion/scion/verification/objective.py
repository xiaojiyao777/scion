"""Objective check: solver-reported objective must match adapter recomputation."""
from __future__ import annotations

import json
import os
import time
from typing import TYPE_CHECKING, Optional

from scion.config.problem import ProblemSpec
from scion.core.models import CheckResult
from scion.runtime.audit import format_runtime_audit_failure, runtime_audit_failure_from_raw
from scion.runtime.runner import Runner
from scion.verification.feasibility import (
    _import_oracle,
    _registry_path,
    resolve_problem_path,
)

if TYPE_CHECKING:
    from scion.problem.contracts import ProblemAdapter


def check_objective(
    problem_spec: ProblemSpec,
    runner: Runner,
    candidate_workspace: str,
    *,
    adapter: Optional[ProblemAdapter] = None,
    selected_surface: str | None = None,
) -> CheckResult:
    """V7_objective: oracle.recompute_objective must match solver-reported objective."""
    t0 = time.monotonic_ns()

    canary = resolve_problem_path(problem_spec, problem_spec.canary_case_path)
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

    audit_failure = runtime_audit_failure_from_raw(
        raw,
        problem_spec=problem_spec,
        selected_surface=selected_surface,
    )
    if audit_failure is not None:
        return _cr(
            False,
            "heavy",
            "solver runtime audit failed: " + format_runtime_audit_failure(audit_failure),
            t0,
        )

    # --- Adapter-based path (v0.3+) ---
    if adapter is not None:
        return _check_via_adapter(adapter, raw, canary, t0)

    # --- Legacy path (direct oracle import) ---
    # Legacy problems that do not use ProblemAdapter must provide a generic
    # solver-output objective hook. Scion framework does not reconstruct
    # problem-native data models.
    oracle_dir = os.path.dirname(os.path.abspath(
        os.path.join(problem_spec.root_dir, problem_spec.oracle_path)
    ))
    try:
        oracle_mod = _import_oracle(oracle_dir)
    except Exception as exc:
        return _cr(False, "heavy", f"cannot import legacy oracle: {exc}", t0)

    legacy_recompute = getattr(oracle_mod, "recompute_solver_output_objective", None)
    if legacy_recompute is None:
        return _cr(
            False,
            "heavy",
            "problem adapter or oracle.recompute_solver_output_objective hook is required",
            t0,
        )

    try:
        oracle_obj = legacy_recompute(raw, canary)
    except Exception as exc:
        return _cr(False, "heavy", f"legacy objective hook error: {exc}", t0)

    mismatches = []
    reported = raw.get("objective", {})
    recomputed = _objective_mapping(oracle_obj)
    for key, oracle_val in recomputed.items():
        solver_val = reported.get(key) if isinstance(reported, dict) else None
        if solver_val is not None and solver_val != oracle_val:
            mismatches.append(f"{key}: solver={solver_val} oracle={oracle_val}")

    if mismatches:
        return _cr(False, "heavy", "objective mismatch: " + "; ".join(mismatches), t0)
    return _cr(True, "heavy", "objective matches oracle", t0)


def _objective_mapping(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if hasattr(value, "_asdict"):
        return dict(value._asdict())
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    raise TypeError("legacy objective hook must return a mapping-like object")


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
