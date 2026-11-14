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

import hashlib
import json
import os
import time
from dataclasses import asdict, is_dataclass
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

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
from scion.verification.requirements import (
    declared_objective_metric_names,
    requires_adapter_for_runtime,
)

if TYPE_CHECKING:
    from scion.problem.contracts import ProblemAdapter, SolverArtifact


_CANARY_SEED = 77  # fixed seed used for both runs
_FAILURE_DETAIL_MAX_BYTES = 8 * 1024
_FAILURE_ERROR_MAX_CHARS = 1024
_FAILURE_VALUE_MAX_CHARS = 512
_MAX_DIFF_KEYS = 32
_MAX_DIFF_KEY_CHARS = 128


def check_nondeterminism(
    problem_spec: ProblemSpec,
    runner: Runner,
    candidate_workspace: str,
    metrics_dir: str | None = None,
    *,
    selected_surface: str | None = None,
    adapter: ProblemAdapter | None = None,
    require_adapter_for_runtime: bool = False,
    runtime_time_limit_sec: int | float = 30,
    first_execution: CandidateCanaryExecution | None = None,
) -> CheckResult:
    """V8_nondeterminism: two same-seed runs must produce equivalent output."""
    t0 = time.monotonic_ns()

    canary = (
        first_execution.case_path
        if first_execution is not None
        else resolve_problem_path(problem_spec, problem_spec.canary_case_path)
    )
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
                time_limit_sec=runtime_time_limit_sec,
                registry_path=reg,
                selected_surface=selected_surface,
            )
        except Exception as exc:
            return None, str(exc)
        if not r.success or r.output is None:
            return None, r.stderr.strip() if r.stderr else ""
        return r.output.to_raw_mapping(), ""

    if first_execution is None:
        raw1, err1 = _run()
    elif first_execution.raw_output is None:
        raw1, err1 = None, first_execution.error
    else:
        raw1, err1 = dict(first_execution.raw_output), ""
    if raw1 is None:
        return _failure_result(
            t0=t0,
            metrics_dir=metrics_dir,
            comparison_mode="solver_execution",
            selected_surface=selected_surface,
            error=f"first run failed: {err1}" if err1 else "first run failed",
            run="first",
        )
    audit_failure = runtime_audit_failure_from_raw(
        raw1,
        problem_spec=problem_spec,
        selected_surface=selected_surface,
    )
    if runtime_audit_issue_blocks_execution(audit_failure):
        return _failure_result(
            t0=t0,
            metrics_dir=metrics_dir,
            comparison_mode="runtime_audit",
            selected_surface=selected_surface,
            error=(
                "first run runtime audit failed: "
                + format_runtime_audit_failure(audit_failure)
            ),
            run="first",
        )

    raw2, err2 = _run()
    if raw2 is None:
        return _failure_result(
            t0=t0,
            metrics_dir=metrics_dir,
            comparison_mode="solver_execution",
            selected_surface=selected_surface,
            error=f"second run failed: {err2}" if err2 else "second run failed",
            run="second",
        )
    audit_failure = runtime_audit_failure_from_raw(
        raw2,
        problem_spec=problem_spec,
        selected_surface=selected_surface,
    )
    if runtime_audit_issue_blocks_execution(audit_failure):
        return _failure_result(
            t0=t0,
            metrics_dir=metrics_dir,
            comparison_mode="runtime_audit",
            selected_surface=selected_surface,
            error=(
                "second run runtime audit failed: "
                + format_runtime_audit_failure(audit_failure)
            ),
            run="second",
        )

    if adapter is None and requires_adapter_for_runtime(
        problem_spec,
        explicit=require_adapter_for_runtime,
    ):
        return _failure_result(
            t0=t0,
            metrics_dir=metrics_dir,
            comparison_mode="adapter_required_missing",
            selected_surface=selected_surface,
            error=(
                "problem adapter is required for adapter-backed runtime "
                "verification; legacy nondeterminism fallback disabled"
            ),
        )

    if adapter is not None:
        return _check_via_adapter(
            adapter=adapter,
            raw1=raw1,
            raw2=raw2,
            canary=canary,
            problem_spec=problem_spec,
            metrics_dir=metrics_dir,
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

    return _failure_result(
        t0=t0,
        metrics_dir=metrics_dir,
        comparison_mode="legacy_objective",
        selected_surface=selected_surface,
        error="legacy objectives differ across same-seed runs",
        run1_objective_digest=_metric_digest(obj1),
        run2_objective_digest=_metric_digest(obj2),
        diff_keys=_diff_keys(obj1, obj2),
    )


def _check_via_adapter(
    *,
    adapter: ProblemAdapter,
    raw1: dict,
    raw2: dict,
    canary: str,
    problem_spec: ProblemSpec,
    metrics_dir: str | None,
    selected_surface: str | None,
    t0: int,
) -> CheckResult:
    try:
        instance = adapter.load_instance(canary)
        artifact1 = adapter.deserialize_solver_output(raw1, instance)
        artifact2 = adapter.deserialize_solver_output(raw2, instance)
    except Exception as exc:
        return _failure_result(
            t0=t0,
            metrics_dir=metrics_dir,
            comparison_mode="adapter_deserialize",
            selected_surface=selected_surface,
            error=f"adapter deserialize error: {exc}",
        )

    try:
        sig1, mode = _canonical_signature(adapter, artifact1, instance, problem_spec)
        sig2, _ = _canonical_signature(adapter, artifact2, instance, problem_spec)
    except Exception as exc:
        return _failure_result(
            t0=t0,
            metrics_dir=metrics_dir,
            comparison_mode="adapter_canonical_signature",
            selected_surface=selected_surface,
            error=f"adapter canonical signature error: {exc}",
        )

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

    return _failure_result(
        t0=t0,
        metrics_dir=metrics_dir,
        comparison_mode=mode,
        selected_surface=selected_surface,
        error="canonical solver artifacts differ across same-seed runs",
        run1_signature_digest=_metric_digest(sig1),
        run2_signature_digest=_metric_digest(sig2),
        diff_keys=_diff_keys(sig1, sig2),
    )


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
    payload = {
        "comparison_mode": _bounded_detail_string(comparison_mode),
        "selected_surface": (
            _bounded_detail_string(selected_surface)
            if selected_surface is not None
            else None
        ),
        "error": _bounded_detail_string(error, maximum=_FAILURE_ERROR_MAX_CHARS),
        **{
            str(key)[:_MAX_DIFF_KEY_CHARS]: _bounded_detail_value(
                value,
                field_name=str(key),
            )
            for key, value in extra.items()
        },
    }
    detail = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if len(detail.encode("utf-8")) <= _FAILURE_DETAIL_MAX_BYTES:
        return detail
    return json.dumps(
        {
            "comparison_mode": payload["comparison_mode"],
            "selected_surface": payload["selected_surface"],
            "error": "failure detail exceeded fixed encoding limit",
            "detail_omitted": True,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _failure_result(
    *,
    t0: int,
    metrics_dir: str | None,
    comparison_mode: str,
    selected_surface: str | None,
    error: str,
    **extra: Any,
) -> CheckResult:
    """Return the Verification failure; persistence is diagnostic-only."""

    detail = _failure_detail(
        comparison_mode=comparison_mode,
        selected_surface=selected_surface,
        error=error,
        **extra,
    )
    diagnostic_ref, persistence_error = _persist_failure_diagnostic(
        detail=detail,
        metrics_dir=metrics_dir,
    )
    metadata: dict[str, Any] = {}
    if diagnostic_ref is not None:
        metadata["diagnostic_ref"] = diagnostic_ref
    if persistence_error is not None:
        metadata["diagnostic_persistence_error"] = persistence_error
    return _cr(False, detail, t0, metadata=metadata)


def _persist_failure_diagnostic(
    *,
    detail: str,
    metrics_dir: str | None,
) -> tuple[str | None, str | None]:
    """Best-effort atomic persistence of the one bounded failure diagnostic."""

    if not metrics_dir or not os.path.isdir(metrics_dir):
        return None, None

    target = Path(metrics_dir) / f"v8_failure_{time.monotonic_ns()}.json"
    temporary = target.with_suffix(".json.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write(detail)
        os.replace(temporary, target)
        return str(target), None
    except OSError as exc:
        return None, _bounded_detail_string(
            f"diagnostic persistence failed: {exc}",
            maximum=_FAILURE_ERROR_MAX_CHARS,
        )
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _metric_digest(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()[:16]


def _objective_for_signature(
    objective: Mapping[str, Any],
    problem_spec: ProblemSpec,
) -> dict[str, Any]:
    declared_names = declared_objective_metric_names(problem_spec)
    if declared_names:
        return {name: objective[name] for name in declared_names if name in objective}
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
    different: list[str] = []
    keys = chain(left, (key for key in right if key not in left))
    for key in keys:
        if left.get(key) == right.get(key):
            continue
        different.append(str(key)[:_MAX_DIFF_KEY_CHARS])
        if len(different) >= _MAX_DIFF_KEYS:
            break
    return sorted(different)


def _bounded_detail_value(value: Any, *, field_name: str) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        limit = (1 << 63) - 1
        return max(-limit, min(limit, value))
    if isinstance(value, float):
        return value if value == value and abs(value) != float("inf") else None
    if isinstance(value, str):
        return _bounded_detail_string(value)
    if field_name == "diff_keys" and isinstance(value, (list, tuple)):
        return [
            _bounded_detail_string(str(item), maximum=_MAX_DIFF_KEY_CHARS)
            for item in value[:_MAX_DIFF_KEYS]
        ]
    return {"omitted_value_type": type(value).__name__[:64]}


def _bounded_detail_string(
    value: str | None,
    *,
    maximum: int = _FAILURE_VALUE_MAX_CHARS,
) -> str:
    rendered = str(value or "")
    return rendered if len(rendered) <= maximum else rendered[:maximum]


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
