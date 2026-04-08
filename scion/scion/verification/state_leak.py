"""State-leak check: same case + same seed must yield identical objectives twice."""
from __future__ import annotations

import json
import os
import time

from scion.config.problem import ProblemSpec
from scion.core.models import CheckResult
from scion.runtime.runner import Runner
from scion.verification.feasibility import _registry_path


_CANARY_SEED = 77  # fixed seed used for both runs


def check_state_leak(
    problem_spec: ProblemSpec,
    runner: Runner,
    candidate_workspace: str,
) -> CheckResult:
    """V5_state_leak: two runs with identical seed must produce identical objectives."""
    t0 = time.monotonic_ns()

    canary = problem_spec.canary_case_path
    if not canary:
        return _cr(True, "heavy", "skipped: no canary_case_path configured", t0)

    if not os.path.isfile(canary):
        return _cr(True, "heavy", f"skipped: canary file not found: {canary}", t0)

    reg = _registry_path(candidate_workspace)

    def _run() -> dict | None:
        try:
            r = runner.run_solver(
                workdir=candidate_workspace,
                instance_path=canary,
                seed=_CANARY_SEED,
                time_limit_sec=30,
                registry_path=reg,
            )
        except Exception:
            return None
        if not r.success or r.output_path is None:
            return None
        try:
            with open(r.output_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    raw1 = _run()
    if raw1 is None:
        return _cr(False, "heavy", "first run failed", t0)

    raw2 = _run()
    if raw2 is None:
        return _cr(False, "heavy", "second run failed", t0)

    obj1 = raw1.get("objective", {})
    obj2 = raw2.get("objective", {})

    if obj1 == obj2:
        return _cr(True, "heavy", "outputs identical across two runs", t0)

    return _cr(
        False, "heavy",
        f"non-deterministic output: run1={obj1} run2={obj2}",
        t0,
    )


def _cr(passed: bool, severity: str, detail: str, t0: int) -> CheckResult:
    elapsed = int((time.monotonic_ns() - t0) / 1_000_000)
    return CheckResult(
        name="V5_state_leak",
        passed=passed,
        severity=severity,  # type: ignore[arg-type]
        detail=detail,
        elapsed_ms=elapsed,
    )
