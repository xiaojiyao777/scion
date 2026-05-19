"""Solver subprocess adapter for solver-design runtime smoke."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .cases import _runtime_smoke_case_public_payload
from .constants import _ALGORITHM_SMOKE_TIMEOUT_SEC, _ALGORITHM_SMOKE_TIME_LIMIT_SEC
from .models import _RuntimeSmokeCase
from .utils import _limit_text


def _run_solver_design_smoke(
    *,
    workspace: Path,
    smoke_case: _RuntimeSmokeCase,
    registry_path: Path,
    selected_surface: str,
) -> tuple[Mapping[str, Any] | None, dict[str, Any]]:
    from scion.runtime.runner import ResourceLimits
    from scion.runtime.subprocess_runner import LocalSubprocessRunner

    runner = LocalSubprocessRunner(
        ResourceLimits(timeout_sec=_ALGORITHM_SMOKE_TIMEOUT_SEC, memory_mb=2048)
    )
    result = runner.run_solver(
        workdir=str(workspace),
        instance_path=str(smoke_case.path),
        seed=smoke_case.seed,
        time_limit_sec=_ALGORITHM_SMOKE_TIME_LIMIT_SEC,
        registry_path=str(registry_path),
        selected_surface=selected_surface,
    )
    run_payload = {
        **_runtime_smoke_case_public_payload(smoke_case),
        "seed": smoke_case.seed,
        "label": smoke_case.label,
        "success": result.success,
        "exit_code": result.exit_code,
        "elapsed_ms": result.elapsed_ms,
        "error_category": result.error_category,
        "stdout": _redact_runtime_smoke_paths(
            _limit_text(result.stdout or "", 800),
            workspace,
            smoke_case.path,
        ),
        "stderr": _redact_runtime_smoke_paths(
            _limit_text(result.stderr or "", 800),
            workspace,
            smoke_case.path,
        ),
    }
    if not result.success or result.output_path is None:
        detail = _redact_runtime_smoke_paths(
            _solver_run_failure_detail(result),
            workspace,
            smoke_case.path,
        )
        run_payload["detail"] = detail
        return None, run_payload
    try:
        with open(result.output_path, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as exc:
        run_payload["detail"] = f"could not read solver output: {exc}"
        return None, run_payload
    run_payload["detail"] = "solver smoke completed"
    return raw, run_payload


def _solver_run_failure_detail(result: Any) -> str:
    parts = [
        "solver run failed",
        f"exit_code={getattr(result, 'exit_code', None)}",
    ]
    error_category = getattr(result, "error_category", None)
    if error_category:
        parts.append(f"error_category={error_category}")
    elapsed_ms = getattr(result, "elapsed_ms", None)
    if elapsed_ms is not None:
        parts.append(f"elapsed_ms={elapsed_ms}")
    stderr = str(getattr(result, "stderr", "") or "").strip()
    stdout = str(getattr(result, "stdout", "") or "").strip()
    if stderr:
        parts.append("stderr=" + _limit_text(stderr, 1200))
    if stdout:
        parts.append("stdout=" + _limit_text(stdout, 1200))
    return "; ".join(parts)


def _redact_runtime_smoke_paths(text: str, *paths: Path) -> str:
    redacted = str(text or "")
    replacements = {
        str(path.expanduser().resolve(strict=False)): "<runtime_smoke_path>"
        for path in paths
        if path is not None
    }
    for raw, marker in sorted(replacements.items(), key=lambda item: -len(item[0])):
        if raw:
            redacted = redacted.replace(raw, marker)
    return redacted
