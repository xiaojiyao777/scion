"""V5_solution_consistency: verify output solution is internally consistent.

Runs the candidate solver on a canary case and delegates problem-specific
output consistency to the selected adapter or optional problem oracle hook.

Semantic rename: was V5_solution_consistency in v0.2, now V5_solution_consistency (W11).
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Literal, Optional

from scion.config.problem import ProblemSpec
from scion.core.models import CheckResult
from scion.runtime.audit import (
    format_runtime_audit_failure,
    runtime_audit_failure_from_raw,
    runtime_audit_issue_blocks_execution,
)
from scion.runtime.runner import Runner, run_solver_with_surface
from scion.verification.candidate_canary import CandidateCanaryExecution
from scion.verification.feasibility import _registry_path, resolve_problem_path
from scion.verification.requirements import requires_adapter_for_runtime

if TYPE_CHECKING:
    from scion.problem.contracts import ProblemAdapter


_CANARY_SEED = 77


def check_state_mutation(
    problem_spec: ProblemSpec,
    runner: Runner,
    candidate_workspace: str,
    metrics_dir: str | None = None,
    *,
    adapter: Optional[ProblemAdapter] = None,
    selected_surface: str | None = None,
    require_adapter_for_runtime: bool = False,
    runtime_time_limit_sec: int | float = 30,
    canary_execution: CandidateCanaryExecution | None = None,
) -> CheckResult:
    """V5_solution_consistency: output must be internally consistent."""
    t0 = time.monotonic_ns()

    canary = (
        canary_execution.case_path
        if canary_execution is not None
        else resolve_problem_path(problem_spec, problem_spec.canary_case_path)
    )
    if not canary:
        return _cr(True, "skipped: no canary_case_path configured", t0)

    if not os.path.isfile(canary):
        return _cr(True, f"skipped: canary file not found: {canary}", t0)

    if canary_execution is not None:
        if canary_execution.raw_output is None:
            detail = canary_execution.error or "solver run failed or no output"
            return _cr(False, detail, t0, diagnosis="ENV")
        raw = dict(canary_execution.raw_output)
    else:
        reg = _registry_path(candidate_workspace)
        try:
            result = run_solver_with_surface(
                runner,
                workdir=candidate_workspace,
                instance_path=canary,
                seed=_CANARY_SEED,
                time_limit_sec=runtime_time_limit_sec,
                registry_path=reg,
                selected_surface=selected_surface,
            )
        except Exception as exc:
            return _cr(False, f"solver run failed: {exc}", t0, diagnosis="ENV")

        if not result.success or result.output is None:
            detail = "solver run failed or no output"
            if result.stderr:
                detail = f"solver run failed: {result.stderr.strip()}"
            return _cr(False, detail, t0, diagnosis="ENV")

        raw = result.output.to_raw_mapping()

    audit_failure = runtime_audit_failure_from_raw(
        raw,
        problem_spec=problem_spec,
        selected_surface=selected_surface,
    )
    if runtime_audit_issue_blocks_execution(audit_failure):
        return _cr(
            False,
            "solver runtime audit failed: " + format_runtime_audit_failure(audit_failure),
            t0,
            diagnosis="CANDIDATE",
            metadata=_runtime_failure_metadata(audit_failure),
        )

    if adapter is None and requires_adapter_for_runtime(
        problem_spec,
        explicit=require_adapter_for_runtime,
    ):
        return _cr(
            False,
            "problem adapter is required for adapter-backed runtime verification; "
            "legacy solution consistency fallback disabled",
            t0,
            diagnosis="ENV",
        )

    if adapter is not None:
        return _check_via_adapter(adapter, raw, canary, t0)

    return _check_via_oracle(problem_spec, raw, canary, t0)


def _check_via_adapter(
    adapter: "ProblemAdapter",
    raw: dict,
    canary: str,
    t0: int,
) -> CheckResult:
    try:
        instance = adapter.load_instance(canary)
        artifact = adapter.deserialize_solver_output(raw, instance)
    except Exception as exc:
        return _cr(False, f"adapter deserialize error: {exc}", t0, diagnosis="CANDIDATE")

    try:
        consistency = adapter.check_solution_consistency(artifact, instance)
    except Exception as exc:
        return _cr(False, f"adapter.check_solution_consistency error: {exc}", t0, diagnosis="UNKNOWN")

    if consistency.passed:
        return _cr(True, "adapter solution consistency ok", t0)

    return _cr(
        False,
        "adapter consistency failed: " + "; ".join(consistency.reasons),
        t0,
        diagnosis="CANDIDATE",
    )


def _check_via_oracle(
    problem_spec: ProblemSpec,
    raw: dict,
    canary: str,
    t0: int,
) -> CheckResult:
    oracle_path = _oracle_file_path(problem_spec)
    if not oracle_path or not os.path.isfile(oracle_path):
        return _cr(
            True,
            "skipped: no adapter or oracle.check_solver_output_consistency hook configured",
            t0,
        )

    try:
        oracle = _import_oracle_file(oracle_path)
    except Exception as exc:
        return _cr(False, f"cannot import legacy oracle: {exc}", t0, diagnosis="ENV")

    consistency_check = getattr(oracle, "check_solver_output_consistency", None)
    if consistency_check is None:
        return _cr(
            True,
            "skipped: no adapter or oracle.check_solver_output_consistency hook configured",
            t0,
        )

    try:
        consistency = consistency_check(raw, canary)
    except Exception as exc:
        return _cr(False, f"legacy consistency hook error: {exc}", t0, diagnosis="UNKNOWN")

    if _legacy_result_passed(consistency):
        return _cr(True, "oracle solution consistency ok", t0)

    diagnosis = _legacy_result_diagnosis(consistency)
    reasons = _legacy_result_reasons(consistency)
    detail = json.dumps(
        {
            "check": "solution_consistency",
            "diagnosis": diagnosis,
            "issues": reasons or ["legacy consistency hook failed"],
        }
    )
    return _cr(False, detail, t0, diagnosis=diagnosis)


def _oracle_file_path(problem_spec: ProblemSpec) -> str:
    oracle_path = getattr(problem_spec, "oracle_path", "") or ""
    if not oracle_path:
        return ""
    if os.path.isabs(oracle_path):
        return os.path.abspath(oracle_path)
    return os.path.abspath(os.path.join(problem_spec.root_dir, oracle_path))


def _import_oracle_file(oracle_path: str) -> object:
    oracle_dir = os.path.dirname(oracle_path)
    saved = list(sys.path)
    if oracle_dir not in sys.path:
        sys.path.insert(0, oracle_dir)
    try:
        spec = importlib.util.spec_from_file_location(
            "_scion_solution_consistency_oracle",
            oracle_path,
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"could not load oracle module from {oracle_path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_scion_solution_consistency_oracle"] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path[:] = saved


def _legacy_result_passed(value: object) -> bool:
    if isinstance(value, dict) and "passed" in value:
        return bool(value["passed"])
    return bool(getattr(value, "passed", value))


def _legacy_result_reasons(value: object) -> list[str]:
    if isinstance(value, dict):
        raw_reasons = (
            value.get("reasons")
            or value.get("violations")
            or value.get("issues")
            or ()
        )
    else:
        raw_reasons = (
            getattr(value, "reasons", None)
            or getattr(value, "violations", None)
            or getattr(value, "issues", None)
            or ()
        )
    return [str(reason) for reason in raw_reasons]


def _legacy_result_diagnosis(
    value: object,
) -> Literal["ENV", "CANDIDATE", "UNKNOWN"]:
    if isinstance(value, dict):
        raw = value.get("diagnosis")
    else:
        raw = getattr(value, "diagnosis", None)
    return raw if raw in {"ENV", "CANDIDATE", "UNKNOWN"} else "CANDIDATE"


def _cr(
    passed: bool,
    detail: str,
    t0: int,
    *,
    diagnosis: Literal["ENV", "CANDIDATE", "UNKNOWN"] | None = None,
    metadata: Mapping[str, Any] | None = None,
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
        metadata=dict(metadata or {}),
    )


def _runtime_failure_metadata(
    issue: Mapping[str, Any] | None,
) -> dict[str, str]:
    if not isinstance(issue, Mapping):
        return {}
    events = issue.get("runtime_events")
    if not isinstance(events, (list, tuple)):
        return {}
    event = next(
        (
            item
            for item in events
            if isinstance(item, Mapping)
            and str(item.get("status") or "").strip().lower() == "error"
            and any(item.get(key) for key in ("failing_symbol", "callsite"))
        ),
        None,
    )
    if event is None:
        return {}
    return {
        key: value
        for key in ("failing_symbol", "callsite")
        if (value := str(event.get(key) or "").strip())
    }
