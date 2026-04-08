"""V3_unit_tests and V4_regression_tests: run pytest in candidate workspace.

Both checks are *light* (LLM-fixable):
  V3_unit_tests     — run unit test file (tests/test_operators.py by default)
  V4_regression_tests — run regression test file (tests/test_solver.py by default)

Pytest is invoked as a subprocess with the candidate workspace on PYTHONPATH so
that operator imports resolve to the candidate code rather than the champion.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

from scion.config.problem import ProblemSpec
from scion.core.models import CheckResult


def check_unit_tests(
    problem_spec: ProblemSpec,
    runner: object,  # Runner (unused — kept for API symmetry with other checks)
    candidate_workspace: str,
) -> CheckResult:
    """V3_unit_tests: run unit tests inside candidate_workspace.

    The test file is resolved as:
      1. problem_spec.unit_test_path (if set and absolute, use directly)
      2. problem_spec.unit_test_path relative to problem_spec.root_dir
      3. Fallback: <root_dir>/tests/test_operators.py
    """
    t0 = time.monotonic_ns()
    test_path = _resolve_test_path(
        problem_spec.unit_test_path if hasattr(problem_spec, "unit_test_path") else "",
        problem_spec.root_dir,
        "tests/test_operators.py",
    )
    if test_path is None:
        return _cr(True, "V3_unit_tests", "skipped: no unit_test_path configured", t0)

    return _run_pytest(test_path, candidate_workspace, "V3_unit_tests", t0)


def check_regression_tests(
    problem_spec: ProblemSpec,
    runner: object,  # Runner (unused — kept for API symmetry)
    candidate_workspace: str,
) -> CheckResult:
    """V4_regression_tests: run regression/solver tests inside candidate_workspace.

    The test file is resolved the same way as unit tests, using
    regression_test_path / fallback tests/test_solver.py.
    """
    t0 = time.monotonic_ns()
    test_path = _resolve_test_path(
        problem_spec.regression_test_path if hasattr(problem_spec, "regression_test_path") else "",
        problem_spec.root_dir,
        "tests/test_solver.py",
    )
    if test_path is None:
        return _cr(True, "V4_regression_tests", "skipped: no regression_test_path configured", t0)

    return _run_pytest(test_path, candidate_workspace, "V4_regression_tests", t0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_test_path(
    configured: str,
    root_dir: str,
    fallback_rel: str,
) -> str | None:
    """Return an absolute path to the test file, or None if not found."""
    if configured:
        if os.path.isabs(configured):
            p = configured
        else:
            p = os.path.join(root_dir, configured)
        if os.path.isfile(p):
            return p
        # configured path doesn't exist — fall through to fallback
    fallback = os.path.join(root_dir, fallback_rel)
    if os.path.isfile(fallback):
        return fallback
    return None


def _run_pytest(test_path: str, workspace: str, check_name: str, t0: int) -> CheckResult:
    """Run pytest on test_path with workspace injected into PYTHONPATH.

    Uses a subprocess so the candidate workspace is isolated. The workspace is
    prepended to PYTHONPATH so that 'import operators' resolves from the candidate
    code rather than from the installed surrogate package.
    """
    env = dict(os.environ)
    # Prepend candidate_workspace so operator imports resolve there first.
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        workspace + os.pathsep + existing_pp if existing_pp else workspace
    )

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", test_path, "-q", "--tb=short", "--no-header"],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return _cr(False, check_name, "pytest timed out after 60 s", t0)
    except Exception as exc:
        return _cr(False, check_name, f"pytest invocation failed: {exc}", t0)

    if proc.returncode == 0:
        return _cr(True, check_name, "all tests passed", t0)

    # Collect a short excerpt from stdout/stderr for the failure detail.
    output = (proc.stdout or "") + (proc.stderr or "")
    snippet = output[-400:].strip().replace("\n", " | ")
    return _cr(False, check_name, f"pytest exit={proc.returncode}: {snippet}", t0)


def _cr(passed: bool, name: str, detail: str, t0: int) -> CheckResult:
    elapsed = int((time.monotonic_ns() - t0) / 1_000_000)
    return CheckResult(
        name=name,
        passed=passed,
        severity="light",
        detail=detail,
        elapsed_ms=elapsed,
    )
