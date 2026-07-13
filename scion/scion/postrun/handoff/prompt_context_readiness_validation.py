"""Direct-only validation for prepared prompt/context readiness artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from scion.postrun.handoff.prepared_prompt_context import (
    RESEARCH_FOCUS_PROJECTION_SUMMARY_SCHEMA,
    research_focus_projection_summary,
)
from scion.postrun.handoff.prompt_context_readiness import (
    PROMPT_CONTEXT_READINESS_SCHEMA,
)
from scion.postrun.inventory.prepared_contract import (
    prepared_execution_runtime_mode,
)


def check_prepared_prompt_context_readiness(
    root: Path | str,
    *,
    repo_dir: Path | str | None = None,
    ports_by_family: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Validate typed prepared context without reconstructing provider prompts."""

    del repo_dir, ports_by_family
    run_root = Path(root).expanduser().resolve()
    readiness_dir = run_root / "prepared_handoff" / "prompt_context_readiness"
    paths = sorted(readiness_dir.glob("*.json"))
    manifest_path = run_root / "prepared_run_manifest.v1.json"
    manifest = _mapping(_read_json(manifest_path))
    failures: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    if not paths:
        failures.append({"artifact": None, "reason": "missing_prompt_context_readiness"})

    for path in paths:
        payload = _read_json(path)
        summaries.append(_artifact_summary(payload, artifact=path.name))
        failures.extend(
            {"artifact": path.name, **failure}
            for failure in _artifact_failures(
                payload,
                root=run_root,
                manifest_path=manifest_path,
                manifest=manifest,
            )
        )

    detail = {
        "directory": str(readiness_dir),
        "artifacts": [path.name for path in paths],
        "artifact_summaries": summaries,
        "provider_prompt_scope": "typed_projection_no_live_provider_prompt",
        "raw_provider_prompt_rendered": False,
        "failures": failures,
    }
    return ("ok" if not failures else "failed"), detail


def _artifact_summary(payload: Any, *, artifact: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"artifact": artifact, "valid_payload": False}
    readiness = _mapping(payload.get("readiness"))
    projection = _mapping(
        _mapping(payload.get("signals")).get("prepared_research_focus_projection")
    )
    projection_detail = _mapping(projection.get("detail"))
    return {
        "artifact": artifact,
        "valid_payload": True,
        "problem_family": payload.get("problem_family"),
        "ready_for_launch_prompt_audit": readiness.get(
            "ready_for_launch_prompt_audit"
        ),
        "missing_required": readiness.get("missing_required"),
        "raw_provider_prompt_rendered": payload.get("raw_provider_prompt_rendered"),
        "prepared_focus_projection": {
            "available": projection_detail.get("available"),
            "schema_version": projection_detail.get("schema_version"),
            "contract_present": projection_detail.get("contract_present"),
            "schema_valid": projection_detail.get("schema_valid"),
            "proposal_visibility_only": projection_detail.get(
                "proposal_visibility_only"
            ),
            "missing_rendered_paths": projection_detail.get(
                "missing_rendered_paths"
            ),
        },
    }


def _artifact_failures(
    payload: Any,
    *,
    root: Path,
    manifest_path: Path,
    manifest: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return [{"reason": "invalid_json_payload"}]

    failures: list[dict[str, Any]] = []
    if payload.get("schema_version") != PROMPT_CONTEXT_READINESS_SCHEMA:
        failures.append(
            {
                "reason": "schema_mismatch",
                "schema_version": payload.get("schema_version"),
            }
        )

    execution = _mapping(manifest.get("execution"))
    try:
        expected_runtime = prepared_execution_runtime_mode(execution)
    except ValueError as exc:
        expected_runtime = None
        failures.append(
            {
                "reason": "proposal_runtime_mode_unknown_or_conflicting",
                "detail": str(exc),
            }
        )
    runtime = _mapping(payload.get("proposal_runtime"))
    if not (
        expected_runtime == "direct_v3"
        and runtime.get("status") == "resolved"
        and runtime.get("resolved_mode") == "direct_v3"
    ):
        failures.append(
            {
                "reason": "proposal_runtime_mode_mismatch",
                "expected": expected_runtime,
                "actual": dict(runtime),
            }
        )

    expected_identity = {
        "run_root": str(root),
        "prepared_manifest_path": str(manifest_path),
        "prepared_manifest_commit": _manifest_commit(manifest),
        "problem_family": manifest.get("problem_family"),
        "model": _mapping(manifest.get("model")).get("name"),
    }
    for field, expected in expected_identity.items():
        if payload.get(field) != expected:
            failures.append(
                {
                    "reason": "artifact_identity_mismatch",
                    "field": field,
                    "expected": expected,
                    "actual": payload.get(field),
                }
            )

    for field, expected in {
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "raw_provider_prompt_rendered": False,
    }.items():
        if payload.get(field) is not expected:
            failures.append(
                {
                    "reason": "boundary_flag_mismatch",
                    "field": field,
                    "expected": expected,
                    "actual": payload.get(field),
                }
            )

    readiness = _mapping(payload.get("readiness"))
    if readiness.get("ready_for_launch_prompt_audit") is not True:
        failures.append(
            {
                "reason": "prompt_audit_not_ready",
                "status": readiness.get("status"),
            }
        )
    if readiness.get("missing_required") != []:
        failures.append(
            {
                "reason": "prompt_audit_missing_required",
                "missing_required": readiness.get("missing_required"),
            }
        )

    signals = _mapping(payload.get("signals"))
    removed_signals = sorted(
        name
        for name in signals
        if "prompt_bridge" in str(name) or str(name).startswith("agentic_")
    )
    if removed_signals:
        failures.append(
            {
                "reason": "unsupported_historical_prompt_context_signals",
                "signals": removed_signals,
            }
        )

    runtime_signal = _mapping(signals.get("proposal_runtime_mode"))
    if not (
        runtime_signal.get("required") is True
        and runtime_signal.get("available") is True
        and _mapping(runtime_signal.get("detail")).get("resolved_mode") == "direct_v3"
    ):
        failures.append({"reason": "direct_runtime_signal_missing"})

    research_focus_required = bool(_mapping(manifest.get("research_focus")))
    projection = _mapping(signals.get("prepared_research_focus_projection"))
    if research_focus_required:
        if projection.get("required") is not True:
            failures.append({"reason": "prepared_focus_projection_not_required"})
        if projection.get("available") is not True:
            failures.append({"reason": "prepared_focus_projection_unavailable"})
        expected_projection = research_focus_projection_summary(
            manifest_path=manifest_path,
            manifest=dict(manifest),
        )
        actual_projection = _mapping(projection.get("detail"))
        if actual_projection != expected_projection:
            failures.append(
                {
                    "reason": "prepared_focus_projection_mismatch",
                    "expected_schema": RESEARCH_FOCUS_PROJECTION_SUMMARY_SCHEMA,
                }
            )
    return failures


def _manifest_commit(manifest: Mapping[str, Any]) -> Any:
    git = _mapping(manifest.get("git"))
    return git.get("commit") or manifest.get("git_commit")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _read_json(path: Path) -> Any:
    try:
        import json

        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
