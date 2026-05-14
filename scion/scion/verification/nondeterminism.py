"""V8_nondeterminism: same case + same seed must yield identical artifacts.

This check verifies that the solver path is deterministic. Adapter-backed
problems compare canonical solver artifacts; legacy/no-adapter problems keep
the older objective-only compatibility comparison.

Common sources of nondeterminism:
  - uuid.uuid4() or os.urandom() (use generate_vehicle_id(rng) instead)
  - list(set(...)) or iterating set/dict in order-dependent ways
  - importing random module directly (use the rng parameter)
  - reading system time, file system state, or other external entropy

This is distinct from V5_solution_consistency. A candidate can pass V5 but fail
V8 if it uses uuid or non-deterministic iteration patterns.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
import os
from pathlib import Path
import shutil
import time
from typing import TYPE_CHECKING, Any, Mapping
import uuid

from scion.config.problem import ProblemSpec
from scion.core.models import CheckResult
from scion.runtime.audit import format_runtime_audit_failure, runtime_audit_failure_from_raw
from scion.runtime.runner import Runner, run_solver_with_surface
from scion.verification.feasibility import _registry_path, resolve_problem_path
from scion.verification.requirements import (
    declared_objective_metric_names,
    requires_adapter_for_runtime,
    research_surface_target_files,
)

if TYPE_CHECKING:
    from scion.problem.contracts import ProblemAdapter, SolverArtifact


_CANARY_SEED = 77  # fixed seed used for both runs


def check_nondeterminism(
    problem_spec: ProblemSpec,
    runner: Runner,
    candidate_workspace: str,
    metrics_dir: str | None = None,
    *,
    selected_surface: str | None = None,
    adapter: ProblemAdapter | None = None,
    require_adapter_for_runtime: bool = False,
) -> CheckResult:
    """V8_nondeterminism: two same-seed runs must produce equivalent output."""
    t0 = time.monotonic_ns()

    canary = resolve_problem_path(problem_spec, problem_spec.canary_case_path)
    if not canary:
        return _cr(True, "skipped: no canary_case_path configured", t0)

    if not os.path.isfile(canary):
        return _cr(True, f"skipped: canary file not found: {canary}", t0)

    reg = _registry_path(candidate_workspace)

    def _run() -> tuple[dict | None, str]:
        """Returns (output_dict, stderr_snippet)."""
        try:
            r = run_solver_with_surface(
                runner,
                workdir=candidate_workspace,
                instance_path=canary,
                seed=_CANARY_SEED,
                time_limit_sec=30,
                registry_path=reg,
                selected_surface=selected_surface,
            )
        except Exception as exc:
            return None, str(exc)
        if not r.success or r.output_path is None:
            return None, r.stderr.strip() if r.stderr else ""
        try:
            with open(r.output_path, encoding="utf-8") as f:
                return json.load(f), ""
        except Exception as exc:
            return None, str(exc)

    raw1, err1 = _run()
    if raw1 is None:
        detail = f"first run failed: {err1}" if err1 else "first run failed"
        return _cr(False, detail, t0)
    audit_failure = runtime_audit_failure_from_raw(
        raw1,
        problem_spec=problem_spec,
        selected_surface=selected_surface,
    )
    if audit_failure is not None:
        return _cr(
            False,
            _failure_detail(
                comparison_mode="runtime_audit",
                selected_surface=selected_surface,
                error=(
                    "first run runtime audit failed: "
                    + format_runtime_audit_failure(audit_failure)
                ),
                run="first",
            ),
            t0,
        )

    raw2, err2 = _run()
    if raw2 is None:
        detail = f"second run failed: {err2}" if err2 else "second run failed"
        return _cr(False, detail, t0)
    audit_failure = runtime_audit_failure_from_raw(
        raw2,
        problem_spec=problem_spec,
        selected_surface=selected_surface,
    )
    if audit_failure is not None:
        return _cr(
            False,
            _failure_detail(
                comparison_mode="runtime_audit",
                selected_surface=selected_surface,
                error=(
                    "second run runtime audit failed: "
                    + format_runtime_audit_failure(audit_failure)
                ),
                run="second",
            ),
            t0,
        )

    # Save run outputs to metrics_dir if provided
    short_id = uuid.uuid4().hex[:8]
    run1_path: str | None = None
    run2_path: str | None = None
    if metrics_dir and os.path.isdir(metrics_dir):
        run1_path = os.path.join(metrics_dir, f"v8_run1_{short_id}.json")
        run2_path = os.path.join(metrics_dir, f"v8_run2_{short_id}.json")
        try:
            with open(run1_path, "w", encoding="utf-8") as f:
                json.dump(raw1, f, indent=2)
            with open(run2_path, "w", encoding="utf-8") as f:
                json.dump(raw2, f, indent=2)
        except OSError:
            run1_path = None
            run2_path = None

    if adapter is None and requires_adapter_for_runtime(
        problem_spec,
        explicit=require_adapter_for_runtime,
    ):
        return _cr(
            False,
            _failure_detail(
                comparison_mode="adapter_required_missing",
                selected_surface=selected_surface,
                error=(
                    "problem adapter is required for adapter-backed runtime "
                    "verification; legacy nondeterminism fallback disabled"
                ),
                run1_ref=run1_path,
                run2_ref=run2_path,
            ),
            t0,
        )

    if adapter is not None:
        return _check_via_adapter(
            adapter=adapter,
            raw1=raw1,
            raw2=raw2,
            canary=canary,
            problem_spec=problem_spec,
            candidate_workspace=candidate_workspace,
            metrics_dir=metrics_dir,
            short_id=short_id,
            run1_path=run1_path,
            run2_path=run2_path,
            selected_surface=selected_surface,
            t0=t0,
        )

    obj1 = {k: v for k, v in raw1.get("objective", {}).items() if k != "solve_time_ms"}
    obj2 = {k: v for k, v in raw2.get("objective", {}).items() if k != "solve_time_ms"}

    if obj1 == obj2:
        return _cr(
            True,
            "legacy objective comparison identical across two runs",
            t0,
            metadata={
                "comparison_mode": "legacy_objective",
                "selected_surface": selected_surface,
                "adapter_backed": False,
                "comparison_equal": True,
            },
        )

    # Archive candidate code on failure
    archive_ref: str | None = None
    if metrics_dir and os.path.isdir(metrics_dir):
        archive_ref = _archive_candidate_code(
            workspace=candidate_workspace,
            archive_dir=metrics_dir,
            tag=f"v8_archive_{short_id}",
            problem_spec=problem_spec,
            selected_surface=selected_surface,
        )

    detail = json.dumps({
        "comparison_mode": "legacy_objective",
        "selected_surface": selected_surface,
        "run1_objective": obj1,
        "run2_objective": obj2,
        "diff_keys": _diff_keys(obj1, obj2),
        "run1_ref": run1_path,
        "run2_ref": run2_path,
        "candidate_archive_ref": archive_ref,
    }, sort_keys=True)
    return _cr(False, detail, t0)


def _check_via_adapter(
    *,
    adapter: ProblemAdapter,
    raw1: dict,
    raw2: dict,
    canary: str,
    problem_spec: ProblemSpec,
    candidate_workspace: str,
    metrics_dir: str | None,
    short_id: str,
    run1_path: str | None,
    run2_path: str | None,
    selected_surface: str | None,
    t0: int,
) -> CheckResult:
    try:
        instance = adapter.load_instance(canary)
        artifact1 = adapter.deserialize_solver_output(raw1, instance)
        artifact2 = adapter.deserialize_solver_output(raw2, instance)
    except Exception as exc:
        return _cr(False, f"adapter deserialize error: {exc}", t0)

    try:
        sig1, mode = _canonical_signature(adapter, artifact1, instance, problem_spec)
        sig2, _ = _canonical_signature(adapter, artifact2, instance, problem_spec)
    except Exception as exc:
        return _cr(False, f"adapter canonical signature error: {exc}", t0)

    sig1_text = _stable_json(sig1)
    sig2_text = _stable_json(sig2)
    if sig1_text == sig2_text:
        return _cr(
            True,
            f"{mode} identical across two runs",
            t0,
            metadata={
                "comparison_mode": mode,
                "selected_surface": selected_surface,
                "adapter_backed": True,
                "comparison_equal": True,
            },
        )

    archive_ref: str | None = None
    if metrics_dir and os.path.isdir(metrics_dir):
        archive_ref = _archive_candidate_code(
            workspace=candidate_workspace,
            archive_dir=metrics_dir,
            tag=f"v8_archive_{short_id}",
            problem_spec=problem_spec,
            selected_surface=selected_surface,
        )

    detail = json.dumps(
        {
            "comparison_mode": mode,
            "selected_surface": selected_surface,
            "run1_signature": sig1,
            "run2_signature": sig2,
            "diff_keys": _diff_keys(sig1, sig2),
            "run1_ref": run1_path,
            "run2_ref": run2_path,
            "candidate_archive_ref": archive_ref,
        },
        sort_keys=True,
    )
    return _cr(False, detail, t0)


def _canonical_signature(
    adapter: ProblemAdapter,
    artifact: SolverArtifact,
    instance: Any,
    problem_spec: ProblemSpec,
) -> tuple[dict[str, Any], str]:
    fingerprint = getattr(adapter, "canonical_artifact_fingerprint", None)
    if callable(fingerprint):
        return (
            {"fingerprint": _stable_data(fingerprint(artifact, instance))},
            "adapter_declared_fingerprint",
        )

    return (
        {
            "feasible": bool(artifact.feasible),
            "objective": _stable_data(
                _objective_for_signature(artifact.objective, problem_spec)
            ),
            "normalized_solution": _stable_data(artifact.normalized_solution),
        },
        "adapter_canonical_signature",
    )


def _failure_detail(
    *,
    comparison_mode: str,
    selected_surface: str | None,
    error: str,
    **extra: Any,
) -> str:
    return json.dumps(
        {
            "comparison_mode": comparison_mode,
            "selected_surface": selected_surface,
            "error": error,
            **extra,
        },
        sort_keys=True,
    )


def _objective_for_signature(
    objective: Mapping[str, Any],
    problem_spec: ProblemSpec,
) -> dict[str, Any]:
    declared_names = declared_objective_metric_names(problem_spec)
    if declared_names:
        return {
            name: objective[name]
            for name in declared_names
            if name in objective
        }
    return {
        str(key): value
        for key, value in objective.items()
        if str(key) != "solve_time_ms"
    }


def _stable_data(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return _stable_data(asdict(value))
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _stable_data(model_dump())
    if isinstance(value, Mapping):
        return {
            str(key): _stable_data(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, (list, tuple)):
        return [_stable_data(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [_stable_data(item) for item in value]
        return sorted(items, key=_stable_json)
    return repr(value)


def _stable_json(value: Any) -> str:
    return json.dumps(
        _stable_data(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _diff_keys(left: Mapping[str, Any], right: Mapping[str, Any]) -> list[str]:
    keys = sorted(set(left) | set(right), key=str)
    return [str(key) for key in keys if left.get(key) != right.get(key)]


def _archive_candidate_code(
    workspace: str,
    archive_dir: str,
    tag: str,
    *,
    problem_spec: ProblemSpec | None = None,
    selected_surface: str | None = None,
) -> str | None:
    """Archive selected-surface target files, falling back to operators/."""

    workspace_path = Path(workspace)
    archive_path = Path(archive_dir) / tag
    try:
        copied = _archive_surface_targets(
            workspace_path=workspace_path,
            archive_path=archive_path,
            patterns=research_surface_target_files(problem_spec, selected_surface),
        )
        if copied:
            return str(archive_path)

        operators_src = workspace_path / "operators"
        if not operators_src.is_dir():
            return None
        shutil.copytree(
            operators_src,
            archive_path / "operators",
            symlinks=False,
            dirs_exist_ok=True,
        )
        return str(archive_path)
    except Exception:
        return None


def _archive_surface_targets(
    *,
    workspace_path: Path,
    archive_path: Path,
    patterns: tuple[str, ...],
) -> bool:
    copied = False
    if not patterns:
        return False

    workspace_root = workspace_path.resolve()
    for pattern in patterns:
        for source in _matching_workspace_paths(workspace_path, pattern):
            try:
                resolved = source.resolve()
                relative = resolved.relative_to(workspace_root)
            except (OSError, ValueError):
                continue
            target = archive_path / relative
            if resolved.is_dir():
                shutil.copytree(
                    resolved,
                    target,
                    symlinks=False,
                    dirs_exist_ok=True,
                )
            elif resolved.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(resolved, target)
            else:
                continue
            copied = True
    return copied


def _matching_workspace_paths(workspace_path: Path, pattern: str) -> list[Path]:
    if os.path.isabs(pattern):
        candidate = Path(pattern)
        return [candidate] if candidate.exists() else []
    return [path for path in workspace_path.glob(pattern) if path.exists()]


def _cr(
    passed: bool,
    detail: str,
    t0: int,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> CheckResult:
    elapsed = int((time.monotonic_ns() - t0) / 1_000_000)
    return CheckResult(
        name="V8_nondeterminism",
        passed=passed,
        severity="heavy",
        detail=detail,
        elapsed_ms=elapsed,
        metadata=dict(metadata or {}),
    )
