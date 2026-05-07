"""Feasibility check: run solver on canary case and verify adapter feasibility."""
from __future__ import annotations

import json
import os
import sys
import time
from typing import TYPE_CHECKING, Any, Optional

from scion.config.problem import ProblemSpec
from scion.core.models import CheckResult
from scion.runtime.audit import format_runtime_audit_failure, runtime_audit_failure_from_raw
from scion.runtime.runner import Runner
from scion.verification.requirements import requires_adapter_for_runtime

if TYPE_CHECKING:
    from scion.problem.contracts import ProblemAdapter


def check_feasibility(
    problem_spec: ProblemSpec,
    runner: Runner,
    candidate_workspace: str,
    *,
    adapter: Optional[ProblemAdapter] = None,
    selected_surface: str | None = None,
    require_adapter_for_runtime: bool = False,
) -> CheckResult:
    """V6_feasibility: solver output must pass oracle.check_feasibility on the canary case."""
    t0 = time.monotonic_ns()

    canary = resolve_problem_path(problem_spec, problem_spec.canary_case_path)
    if not canary:
        return _cr(True, "heavy", "skipped: no canary_case_path configured", t0)

    if not os.path.isfile(canary):
        return _cr(True, "heavy", f"skipped: canary file not found: {canary}", t0)

    # Run solver in candidate workspace with canary case.
    try:
        result = runner.run_solver(
            workdir=candidate_workspace,
            instance_path=canary,
            seed=42,
            time_limit_sec=30,
            registry_path=_registry_path(candidate_workspace),
        )
    except Exception as exc:
        return _cr(False, "heavy", f"runner error: {exc}", t0)

    if not result.success:
        return _cr(
            False, "heavy",
            f"solver failed (exit={result.exit_code}, "
            f"category={result.error_category}): {result.stderr[:200]}",
            t0,
        )

    if result.output_path is None:
        return _cr(False, "heavy", "solver produced no output file", t0)

    # Load output JSON.
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

    if adapter is None and requires_adapter_for_runtime(
        problem_spec,
        explicit=require_adapter_for_runtime,
    ):
        return _cr(
            False,
            "heavy",
            "problem adapter is required for adapter-backed runtime verification; "
            "legacy feasibility fallback disabled",
            t0,
        )

    # --- Adapter-based path (v0.3+) ---
    if adapter is not None:
        return _check_via_adapter(adapter, raw, canary, t0)

    # --- Legacy path (direct oracle import) ---
    # The framework does not know how to reconstruct problem-native objects.
    # Legacy problems that do not use ProblemAdapter must provide a generic
    # oracle hook instead of relying on framework-owned problem data models.
    oracle_dir = os.path.dirname(os.path.abspath(
        os.path.join(problem_spec.root_dir, problem_spec.oracle_path)
    ))
    try:
        oracle = _import_oracle(oracle_dir)
    except Exception as exc:
        return _cr(False, "heavy", f"cannot import legacy oracle: {exc}", t0)

    legacy_check = getattr(oracle, "check_solver_output_feasibility", None)
    if legacy_check is None:
        return _cr(
            False,
            "heavy",
            "problem adapter or oracle.check_solver_output_feasibility hook is required",
            t0,
        )

    try:
        legacy_result = legacy_check(raw, canary)
    except Exception as exc:
        return _cr(False, "heavy", f"legacy feasibility hook error: {exc}", t0)
    passed = bool(getattr(legacy_result, "passed", legacy_result))
    if passed:
        return _cr(True, "heavy", "feasibility ok", t0)
    reasons = getattr(legacy_result, "reasons", None) or getattr(legacy_result, "violations", None) or ()
    detail = "; ".join(str(reason) for reason in list(reasons)[:3]) or "legacy feasibility hook failed"
    return _cr(False, "heavy", f"infeasible: {detail}", t0)


def _check_via_adapter(
    adapter: ProblemAdapter, raw: dict, canary: str, t0: int,
) -> CheckResult:
    try:
        instance = adapter.load_instance(canary)
        artifact = adapter.deserialize_solver_output(raw, instance)
    except Exception as exc:
        return _cr(False, "heavy", f"adapter deserialize error: {exc}", t0)

    try:
        consistency = adapter.check_solution_consistency(artifact, instance)
        if not consistency.passed:
            return _cr(
                False, "heavy",
                f"consistency failed: {'; '.join(consistency.reasons[:3])}",
                t0,
            )
    except Exception as exc:
        return _cr(False, "heavy", f"consistency check error: {exc}", t0)

    try:
        feas = adapter.check_feasibility(artifact, instance)
    except Exception as exc:
        return _cr(False, "heavy", f"adapter.check_feasibility error: {exc}", t0)

    if feas.passed:
        return _cr(True, "heavy", "feasibility ok", t0)
    return _cr(
        False, "heavy",
        f"infeasible: {'; '.join(feas.reasons[:3])}",
        t0,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _registry_path(workspace: str) -> str:
    """Return registry path if it exists, else an empty string (solver uses defaults)."""
    rp = os.path.join(workspace, "registry.yaml")
    return rp if os.path.isfile(rp) else ""


def resolve_problem_path(problem_spec: ProblemSpec, path: str) -> str:
    """Resolve problem-relative runtime paths for in-process verification."""
    if not path:
        return path
    if os.path.isabs(path):
        return path

    candidates: list[str] = []
    root_dir = getattr(problem_spec, "root_dir", "") or ""
    if root_dir:
        candidates.append(os.path.join(root_dir, path))
    candidates.append(path)

    for data_root in _problem_data_roots_from_env():
        candidates.append(os.path.join(data_root, path))

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return candidates[0] if candidates else path


def _problem_data_roots_from_env() -> list[str]:
    """Return adapter/runtime data roots without naming a research object here."""
    roots: list[str] = []
    for key, value in sorted(os.environ.items()):
        if not key.startswith("SCION_") or not key.endswith("_DATA_ROOT"):
            continue
        root = value.strip()
        if root:
            roots.append(root)
    return roots


def _import_oracle(oracle_dir: str) -> Any:
    """Import oracle module from oracle_dir, temporarily adjusting sys.path."""
    import importlib.util
    oracle_path = os.path.join(oracle_dir, "oracle.py")
    if not os.path.isfile(oracle_path):
        raise FileNotFoundError(f"oracle.py not found at {oracle_path}")

    saved = list(sys.path)
    if oracle_dir not in sys.path:
        sys.path.insert(0, oracle_dir)
    try:
        spec = importlib.util.spec_from_file_location("_scion_oracle", oracle_path)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        sys.modules["_scion_oracle"] = mod  # Required for dataclass introspection
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    finally:
        sys.path[:] = saved


def _cr(passed: bool, severity: str, detail: str, t0: int) -> CheckResult:
    elapsed = int((time.monotonic_ns() - t0) / 1_000_000)
    return CheckResult(
        name="V6_feasibility",
        passed=passed,
        severity=severity,  # type: ignore[arg-type]
        detail=detail,
        elapsed_ms=elapsed,
    )
