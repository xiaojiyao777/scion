"""Performance guard: candidate wall-clock time must not exceed champion * N times."""
from __future__ import annotations

import os
import time

from scion.config.problem import ProblemSpec
from scion.core.models import CheckResult
from scion.runtime.runner import Runner
from scion.verification.feasibility import _registry_path


_PERF_SEED = 55
_MAX_SLOWDOWN = 5  # candidate must not exceed champion × 5
_DEFAULT_PERF_TIMEOUT_SEC = 60


def check_perf(
    problem_spec: ProblemSpec,
    runner: Runner,
    candidate_workspace: str,
    champion_workspace: str,
) -> CheckResult:
    """V9_perf_guard: candidate solve time ≤ champion × 5."""
    t0 = time.monotonic_ns()

    perf_case = os.environ.get("SCION_PERF_GUARD_CASE") or problem_spec.canary_case_path
    if not perf_case:
        return _cr(True, "heavy", "skipped: no canary_case_path configured", t0)

    if not os.path.isfile(perf_case):
        return _cr(True, "heavy", f"skipped: perf case not found: {perf_case}", t0)

    if not champion_workspace or not os.path.isdir(champion_workspace):
        return _cr(True, "heavy", "skipped: champion workspace not available", t0)

    timeout_sec = int(os.environ.get("SCION_PERF_GUARD_TIMEOUT", str(_DEFAULT_PERF_TIMEOUT_SEC)))

    def _run(workdir: str) -> int | None:
        """Return elapsed_ms or None on failure."""
        try:
            r = runner.run_solver(
                workdir=workdir,
                instance_path=perf_case,
                seed=_PERF_SEED,
                time_limit_sec=timeout_sec,
                registry_path=_registry_path(workdir),
            )
        except Exception:
            return None
        if not r.success:
            return None
        return r.elapsed_ms

    cand_ms = _run(candidate_workspace)
    if cand_ms is None:
        return _cr(False, "heavy", "candidate solver run failed", t0)

    champ_ms = _run(champion_workspace)
    if champ_ms is None:
        return _cr(True, "heavy", "skipped: champion solver run failed", t0)

    if champ_ms == 0:
        return _cr(True, "heavy", "skipped: champion time=0ms (degenerate)", t0)

    ratio = cand_ms / champ_ms
    detail = (
        f"case={os.path.basename(perf_case)} candidate={cand_ms}ms "
        f"champion={champ_ms}ms ratio={ratio:.2f}x timeout={timeout_sec}s"
    )
    if ratio <= _MAX_SLOWDOWN:
        return _cr(True, "heavy", f"perf ok: {detail}", t0)
    return _cr(
        False, "heavy",
        f"too slow: {detail} (limit={_MAX_SLOWDOWN}x)",
        t0,
    )


def _cr(passed: bool, severity: str, detail: str, t0: int) -> CheckResult:
    elapsed = int((time.monotonic_ns() - t0) / 1_000_000)
    return CheckResult(
        name="V9_perf_guard",
        passed=passed,
        severity=severity,  # type: ignore[arg-type]
        detail=detail,
        elapsed_ms=elapsed,
    )
