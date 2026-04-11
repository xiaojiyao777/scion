"""State-leak check: same case + same seed must yield identical objectives twice.

DEPRECATED: This module duplicates scion.verification.nondeterminism and will be
removed in v0.3. Use check_nondeterminism() from scion.verification.nondeterminism
instead. gate.py uses V8_nondeterminism (nondeterminism.py) as the authoritative
determinism check; this file is retained only for external callers that may still
import check_state_leak.
"""
import warnings as _warnings

_warnings.warn(
    "scion.verification.state_leak is deprecated and will be removed in v0.3. "
    "Use scion.verification.nondeterminism.check_nondeterminism instead.",
    DeprecationWarning,
    stacklevel=2,
)

from __future__ import annotations

import json
import os
import shutil
import time
import uuid

from scion.config.problem import ProblemSpec
from scion.core.models import CheckResult
from scion.runtime.runner import Runner
from scion.verification.feasibility import _registry_path


_CANARY_SEED = 77  # fixed seed used for both runs


def check_state_leak(
    problem_spec: ProblemSpec,
    runner: Runner,
    candidate_workspace: str,
    metrics_dir: str | None = None,
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

    # Save run outputs to metrics_dir if provided
    short_id = uuid.uuid4().hex[:8]
    run1_path: str | None = None
    run2_path: str | None = None
    if metrics_dir and os.path.isdir(metrics_dir):
        run1_path = os.path.join(metrics_dir, f"v5_run1_{short_id}.json")
        run2_path = os.path.join(metrics_dir, f"v5_run2_{short_id}.json")
        try:
            with open(run1_path, "w", encoding="utf-8") as f:
                json.dump(raw1, f, indent=2)
            with open(run2_path, "w", encoding="utf-8") as f:
                json.dump(raw2, f, indent=2)
        except OSError:
            run1_path = None
            run2_path = None

    obj1 = {k: v for k, v in raw1.get("objective", {}).items() if k != "solve_time_ms"}
    obj2 = {k: v for k, v in raw2.get("objective", {}).items() if k != "solve_time_ms"}

    if obj1 == obj2:
        return _cr(True, "heavy", "outputs identical across two runs", t0)

    # Archive candidate code on failure
    archive_ref: str | None = None
    if metrics_dir and os.path.isdir(metrics_dir):
        archive_ref = _archive_candidate_code(
            workspace=candidate_workspace,
            archive_dir=metrics_dir,
            tag=f"v5_archive_{short_id}",
        )

    detail = json.dumps({
        "run1_objective": obj1,
        "run2_objective": obj2,
        "diff_keys": [k for k in obj1 if obj1[k] != obj2.get(k)],
        "run1_ref": run1_path,
        "run2_ref": run2_path,
        "candidate_archive_ref": archive_ref,
    })
    return _cr(False, "heavy", detail, t0)


def _archive_candidate_code(workspace: str, archive_dir: str, tag: str) -> str | None:
    """Copy operators/ from workspace to archive_dir/tag/. Returns archive path or None."""
    ops_src = os.path.join(workspace, "operators")
    if not os.path.isdir(ops_src):
        return None
    dest = os.path.join(archive_dir, tag)
    try:
        shutil.copytree(ops_src, dest, symlinks=False)
        return dest
    except Exception:
        return None


def _cr(passed: bool, severity: str, detail: str, t0: int) -> CheckResult:
    elapsed = int((time.monotonic_ns() - t0) / 1_000_000)
    return CheckResult(
        name="V5_state_leak",
        passed=passed,
        severity=severity,  # type: ignore[arg-type]
        detail=detail,
        elapsed_ms=elapsed,
    )
