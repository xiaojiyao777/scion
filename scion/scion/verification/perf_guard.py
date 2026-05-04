"""Performance guard: candidate wall-clock time must not exceed champion * N times."""
from __future__ import annotations

import os
import time

from scion.config.problem import ProblemSpec
from scion.core.models import CheckResult
from scion.runtime.audit import format_runtime_audit_failure, runtime_audit_failure_from_result
from scion.runtime.runner import Runner
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
) -> CheckResult:
    """V9_perf_guard: candidate solve time must stay within configured slowdown."""
    t0 = time.monotonic_ns()
    limit_ratio = float(max_slowdown)

    perf_case = os.environ.get("SCION_PERF_GUARD_CASE") or problem_spec.canary_case_path
    perf_case = resolve_problem_path(problem_spec, perf_case)
    if not perf_case:
        return _cr(True, "heavy", "skipped: no canary_case_path configured", t0)

    if not os.path.isfile(perf_case):
        return _cr(True, "heavy", f"skipped: perf case not found: {perf_case}", t0)

    if not champion_workspace or not os.path.isdir(champion_workspace):
        return _cr(True, "heavy", "skipped: champion workspace not available", t0)

    timeout_sec = int(os.environ.get("SCION_PERF_GUARD_TIMEOUT", str(_DEFAULT_PERF_TIMEOUT_SEC)))

    def _run(workdir: str) -> dict[str, object]:
        """Return structured runtime facts for evidence."""
        try:
            r = runner.run_solver(
                workdir=workdir,
                instance_path=perf_case,
                seed=_PERF_SEED,
                time_limit_sec=timeout_sec,
                registry_path=_registry_path(workdir),
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
        audit_failure = runtime_audit_failure_from_result(r)
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

    champ = _run(champion_workspace)
    if not champ["success"]:
        metadata = {
            "case_id": case_id,
            "timeout_sec": timeout_sec,
            "candidate_ms": cand["elapsed_ms"],
            "champion_ms": champ["elapsed_ms"],
            "ratio": None,
            "limit_ratio": limit_ratio,
            "candidate_timeout": bool(cand["timeout"]),
            "champion_timeout": bool(champ["timeout"]),
            "candidate_error_category": cand["error_category"],
            "champion_error_category": champ["error_category"],
        }
        return _cr(True, "heavy", "skipped: champion solver run failed", t0, metadata=metadata)

    cand_ms = int(cand["elapsed_ms"] or 0)
    champ_ms = int(champ["elapsed_ms"] or 0)
    if champ_ms == 0:
        return _cr(True, "heavy", "skipped: champion time=0ms (degenerate)", t0)

    ratio = cand_ms / champ_ms
    metadata = {
        "case_id": case_id,
        "timeout_sec": timeout_sec,
        "candidate_ms": cand_ms,
        "champion_ms": champ_ms,
        "ratio": ratio,
        "limit_ratio": limit_ratio,
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
