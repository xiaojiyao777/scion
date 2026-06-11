"""Performance guard: candidate wall-clock time must not exceed champion * N times."""
from __future__ import annotations

import os
import time

from scion.config.problem import ProblemSpec
from scion.core.models import CheckResult
from scion.runtime.audit import format_runtime_audit_failure, runtime_audit_failure_from_result
from scion.runtime.runner import Runner, run_solver_with_surface
from scion.verification.feasibility import _registry_path, resolve_problem_path


_PERF_SEED = 55
_DEFAULT_MAX_SLOWDOWN = 5.0
_DEFAULT_PERF_TIMEOUT_SEC = 60


def check_perf(
    problem_spec: ProblemSpec,
    runner: Runner,
    candidate_workspace: str,
    champion_workspace: str,
    *,
    max_slowdown: float = _DEFAULT_MAX_SLOWDOWN,
    selected_surface: str | None = None,
    timeout_sec: int | float | None = None,
    strict_runtime_checks: bool = False,
) -> CheckResult:
    """V9_perf_guard: runtime compliance for the problem's runtime model."""
    t0 = time.monotonic_ns()
    limit_ratio = float(max_slowdown)
    runtime_model = _runtime_model(problem_spec)

    perf_case = os.environ.get("SCION_PERF_GUARD_CASE") or problem_spec.canary_case_path
    perf_case = resolve_problem_path(problem_spec, perf_case)
    if not perf_case:
        return _invalid_comparison(
            strict_runtime_checks,
            "skipped: no canary_case_path configured",
            t0,
            metadata={"comparison_valid": False},
        )

    if not os.path.isfile(perf_case):
        return _invalid_comparison(
            strict_runtime_checks,
            f"skipped: perf case not found: {perf_case}",
            t0,
            metadata={"comparison_valid": False, "case_path": perf_case},
        )

    if not champion_workspace or not os.path.isdir(champion_workspace):
        return _invalid_comparison(
            strict_runtime_checks,
            "skipped: champion workspace not available",
            t0,
            metadata={
                "comparison_valid": False,
                "champion_error_category": "workspace_unavailable",
            },
        )

    timeout_sec = _timeout_sec(timeout_sec)

    def _run(workdir: str) -> dict[str, object]:
        """Return structured runtime facts for evidence."""
        try:
            r = run_solver_with_surface(
                runner,
                workdir=workdir,
                instance_path=perf_case,
                seed=_PERF_SEED,
                time_limit_sec=timeout_sec,
                registry_path=_registry_path(workdir),
                selected_surface=selected_surface,
            )
        except Exception:
            return {
                "success": False,
                "elapsed_ms": None,
                "timeout": False,
                "error_category": "exception",
            }
        if not r.success:
            return {
                "success": False,
                "elapsed_ms": r.elapsed_ms,
                "timeout": r.error_category == "timeout",
                "error_category": r.error_category,
            }
        audit_failure = runtime_audit_failure_from_result(
            r,
            problem_spec=problem_spec,
            selected_surface=selected_surface,
        )
        if audit_failure is not None:
            return {
                "success": False,
                "elapsed_ms": r.elapsed_ms,
                "timeout": False,
                "error_category": audit_failure["error_category"],
                "runtime_audit": audit_failure,
                "detail": format_runtime_audit_failure(audit_failure),
            }
        return {
            "success": True,
            "elapsed_ms": r.elapsed_ms,
            "timeout": False,
            "error_category": None,
        }

    cand = _run(candidate_workspace)
    case_id = os.path.basename(perf_case)
    if not cand["success"]:
        metadata = {
            "case_id": case_id,
            "timeout_sec": timeout_sec,
            "candidate_ms": cand["elapsed_ms"],
            "champion_ms": None,
            "ratio": None,
            "limit_ratio": limit_ratio,
            "comparison_valid": False,
            "candidate_timeout": bool(cand["timeout"]),
            "champion_timeout": False,
            "candidate_error_category": cand["error_category"],
            "champion_error_category": None,
            "candidate_runtime_audit": cand.get("runtime_audit"),
        }
        detail = (
            f"candidate solver run failed: case={case_id} "
            f"timeout={bool(cand['timeout'])} category={cand['error_category']} "
            f"timeout_limit={timeout_sec}s"
        )
        if cand.get("detail"):
            detail += f" detail={cand['detail']}"
        return _cr(False, "heavy", detail, t0, metadata=metadata)

    if runtime_model == "budget_exhausting":
        cand_ms = int(cand["elapsed_ms"] or 0)
        metadata = {
            "case_id": case_id,
            "timeout_sec": timeout_sec,
            "candidate_ms": cand_ms,
            "champion_ms": None,
            "ratio": None,
            "limit_ratio": None,
            "comparison_valid": False,
            "runtime_model": runtime_model,
            "budget_compliance_valid": True,
            "candidate_timeout": bool(cand["timeout"]),
            "champion_timeout": False,
            "candidate_error_category": cand["error_category"],
            "champion_error_category": None,
        }
        detail = (
            f"budget compliant: case={case_id} candidate={cand_ms}ms "
            f"timeout={timeout_sec}s runtime_model=budget_exhausting"
        )
        return _cr(True, "heavy", detail, t0, metadata=metadata)

    champ = _run(champion_workspace)
    if not champ["success"]:
        metadata = {
            "case_id": case_id,
            "timeout_sec": timeout_sec,
            "candidate_ms": cand["elapsed_ms"],
            "champion_ms": champ["elapsed_ms"],
            "ratio": None,
            "limit_ratio": limit_ratio,
            "comparison_valid": False,
            "candidate_timeout": bool(cand["timeout"]),
            "champion_timeout": bool(champ["timeout"]),
            "candidate_error_category": cand["error_category"],
            "champion_error_category": champ["error_category"],
        }
        detail = (
            "skipped: champion solver run failed"
            if not strict_runtime_checks
            else "champion solver run failed; performance comparison invalid"
        )
        return _cr(
            not strict_runtime_checks,
            "heavy",
            detail,
            t0,
            metadata=metadata,
        )

    cand_ms = int(cand["elapsed_ms"] or 0)
    champ_ms = int(champ["elapsed_ms"] or 0)
    if champ_ms == 0:
        return _invalid_comparison(
            strict_runtime_checks,
            (
                "skipped: champion time=0ms (degenerate)"
                if not strict_runtime_checks
                else "champion time=0ms; performance comparison invalid"
            ),
            t0,
            metadata={
                "case_id": case_id,
                "timeout_sec": timeout_sec,
                "candidate_ms": cand_ms,
                "champion_ms": champ_ms,
                "ratio": None,
                "limit_ratio": limit_ratio,
                "comparison_valid": False,
                "candidate_timeout": bool(cand["timeout"]),
                "champion_timeout": bool(champ["timeout"]),
                "candidate_error_category": cand["error_category"],
                "champion_error_category": "zero_runtime",
            },
        )

    ratio = cand_ms / champ_ms
    metadata = {
        "case_id": case_id,
        "timeout_sec": timeout_sec,
        "candidate_ms": cand_ms,
        "champion_ms": champ_ms,
        "ratio": ratio,
        "limit_ratio": limit_ratio,
        "comparison_valid": True,
        "runtime_model": runtime_model,
        "budget_compliance_valid": True,
        "candidate_timeout": bool(cand["timeout"]),
        "champion_timeout": bool(champ["timeout"]),
        "candidate_error_category": cand["error_category"],
        "champion_error_category": champ["error_category"],
    }
    detail = (
        f"case={case_id} candidate={cand_ms}ms "
        f"champion={champ_ms}ms ratio={ratio:.2f}x timeout={timeout_sec}s"
    )
    if ratio <= limit_ratio:
        return _cr(True, "heavy", f"perf ok: {detail}", t0, metadata=metadata)
    return _cr(
        False, "heavy",
        f"too slow: {detail} (limit={limit_ratio:g}x)",
        t0,
        metadata=metadata,
    )


def _timeout_sec(value: int | float | None) -> int:
    if isinstance(value, bool) or value is None:
        value = os.environ.get("SCION_PERF_GUARD_TIMEOUT", _DEFAULT_PERF_TIMEOUT_SEC)
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = _DEFAULT_PERF_TIMEOUT_SEC
    if numeric <= 0:
        numeric = _DEFAULT_PERF_TIMEOUT_SEC
    return max(1, int(numeric))


def _runtime_model(problem_spec: object) -> str:
    measurement = getattr(problem_spec, "measurement", None)
    if measurement is None:
        spec_v1 = getattr(problem_spec, "spec_v1", None)
        measurement = getattr(spec_v1, "measurement", None)
    value = str(getattr(measurement, "runtime_model", "") or "").strip()
    return value if value in {"comparative", "budget_exhausting"} else "comparative"


def _invalid_comparison(
    strict_runtime_checks: bool,
    detail: str,
    t0: int,
    *,
    metadata: dict[str, object] | None = None,
) -> CheckResult:
    return _cr(
        not strict_runtime_checks,
        "heavy",
        detail,
        t0,
        metadata=metadata,
    )


def _cr(
    passed: bool,
    severity: str,
    detail: str,
    t0: int,
    *,
    metadata: dict[str, object] | None = None,
) -> CheckResult:
    elapsed = int((time.monotonic_ns() - t0) / 1_000_000)
    return CheckResult(
        name="V9_perf_guard",
        passed=passed,
        severity=severity,  # type: ignore[arg-type]
        detail=detail,
        elapsed_ms=elapsed,
        metadata=dict(metadata or {}),
    )
