"""Run lifecycle and launcher artifact state for postrun inventory."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from scion.postrun.inventory.constants import (
    CAMPAIGN_EXECUTION_ARTIFACTS,
    PRE_CAMPAIGN_INFRA_FAILURE_KEYS,
)
from scion.postrun.inventory.prepared_contract import PREPARED_RUN_MANIFEST_SCHEMA
from scion.postrun.inventory.utils import (
    _first_int,
    _first_string,
    _string_or_none,
)


def _validity(*docs: Any) -> dict[str, Any]:
    run_validity_status = _first_string(
        *docs, keys=("run_validity_status", "validity_status")
    )
    run_completeness_status = _first_string(
        *docs, keys=("run_completeness_status", "completeness_status")
    )
    last_stop_reason = _first_string(
        *docs,
        keys=(
            "last_stop_reason",
            "stopped_reason",
            "stop_reason",
            "termination_reason",
            "failure_reason",
        ),
    )
    invalid_infra_only = any(_doc_says_invalid_infra_only(doc) for doc in docs)
    return {
        "run_validity_status": run_validity_status,
        "run_completeness_status": run_completeness_status,
        "last_stop_reason": last_stop_reason,
        "invalid_infra_only": invalid_infra_only,
    }


def _doc_says_invalid_infra_only(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    if doc.get("invalid_infra_only") is True:
        return True
    if doc.get("pre_campaign_completion_preflight") == "failed":
        return True
    if _pre_campaign_infra_failure_keys(doc):
        return True
    values: list[str] = []
    for key in (
        "run_validity_status",
        "validity_status",
        "run_completeness_status",
        "status",
        "last_stop_reason",
        "stopped_reason",
        "stop_reason",
        "termination_reason",
        "failure_category",
        "error_category",
    ):
        value = doc.get(key)
        if value is not None:
            values.append(str(value).strip().lower())
    provider_error = doc.get("provider_error")
    if isinstance(provider_error, dict):
        values.extend(str(value).strip().lower() for value in provider_error.values())
    if "invalid_infra_only" in values:
        return True
    joined = " ".join(values)
    return "infra" in joined and ("invalid" in joined or "failed_infra" in joined)


def _pre_campaign_infra_failure_keys(
    doc: Mapping[str, Any],
    keys: Sequence[str] = PRE_CAMPAIGN_INFRA_FAILURE_KEYS,
) -> list[str]:
    return [key for key in keys if doc.get(key) not in (None, False, "", 0)]


def _counters(*docs: Any) -> dict[str, int | None]:
    fields = {
        "requested_rounds": ("requested_rounds", "total_rounds", "max_rounds"),
        "effective_rounds_completed": (
            "effective_rounds_completed",
            "effective_rounds",
            "completed_rounds",
            "n_steps",
        ),
        "formal_screened_candidates": (
            "formal_screened_candidates",
            "screened_candidates",
            "screened_experiments",
        ),
        "protocol_evaluated_candidates": (
            "protocol_evaluated_candidates",
            "protocol_evaluations",
            "n_experiments",
        ),
        "screened_experiments": ("screened_experiments", "n_experiments"),
        "proposal_attempts_total": (
            "proposal_attempts_total",
            "proposal_attempts",
            "attempts",
        ),
    }
    return {name: _first_int(*docs, keys=keys) for name, keys in fields.items()}


def _lifecycle_inventory(
    run_status: Any,
    prepared_manifest: Any,
    *campaign_docs: Any,
    run_status_present: bool = True,
    run_status_valid: bool = True,
    campaign_execution_artifacts: Mapping[str, Any] | None = None,
    pre_campaign_infra_failure_keys: Sequence[str] = (),
) -> dict[str, Any]:
    status_doc = run_status if isinstance(run_status, dict) else {}
    manifest = prepared_manifest if isinstance(prepared_manifest, dict) else {}
    artifact_state = (
        campaign_execution_artifacts
        if isinstance(campaign_execution_artifacts, Mapping)
        else _empty_campaign_execution_artifact_state()
    )
    manifest_is_prepared = (
        manifest.get("schema_version") == PREPARED_RUN_MANIFEST_SCHEMA
    )
    launcher_status_unavailable = not run_status_present or not run_status_valid
    launcher_status_failure_key = (
        "root_run_status_missing"
        if not run_status_present
        else "root_run_status_invalid" if not run_status_valid else None
    )
    prepared_only = status_doc.get("prepared_only") is True or (
        status_doc.get("schema") == "scion.launcher_prepare.v1"
        and status_doc.get("status") == "prepared"
    )
    preflight_failed = (
        status_doc.get("pre_campaign_completion_preflight") == "failed"
        and manifest_is_prepared
    )
    pre_campaign_infra_failure_keys = (
        _pre_campaign_infra_failure_keys(
            status_doc,
            pre_campaign_infra_failure_keys,
        )
        if manifest_is_prepared
        else []
    )
    pre_campaign_infra_failed = bool(pre_campaign_infra_failure_keys)
    invalid_infra_only_from_docs = (
        any(_doc_says_invalid_infra_only(doc) for doc in (status_doc, *campaign_docs))
        or launcher_status_unavailable
    )
    campaign_execution_artifacts_available = artifact_state.get("available") is True
    campaign_execution_artifacts_unavailable = (
        not prepared_only
        and not launcher_status_unavailable
        and not preflight_failed
        and not pre_campaign_infra_failed
        and not invalid_infra_only_from_docs
        and not campaign_execution_artifacts_available
    )
    campaign_execution_failure_key = (
        artifact_state.get("failure_key")
        if campaign_execution_artifacts_unavailable
        else None
    )
    invalid_infra_only = (
        invalid_infra_only_from_docs or campaign_execution_artifacts_unavailable
    )
    resume_from = status_doc.get("resume_from_campaign")
    if resume_from is None:
        resume_from = manifest.get("resume_from_campaign")
    resume_snapshot_ref = status_doc.get("resume_snapshot_ref")
    if resume_snapshot_ref is None:
        resume_snapshot_ref = manifest.get("resume_snapshot_ref")
    if prepared_only:
        evidence_scope = "prepared_launch_root_with_resume_snapshot"
    elif launcher_status_unavailable:
        evidence_scope = "launcher_status_unavailable_with_resume_snapshot"
    elif preflight_failed:
        evidence_scope = "pre_campaign_preflight_failed_with_resume_snapshot"
    elif pre_campaign_infra_failed:
        evidence_scope = "pre_campaign_infra_failed_with_resume_snapshot"
    elif campaign_execution_artifacts_unavailable:
        evidence_scope = "campaign_execution_artifacts_unavailable_with_resume_snapshot"
    elif invalid_infra_only:
        evidence_scope = "invalid_infra_only_with_resume_snapshot"
    else:
        evidence_scope = "postrun_campaign"
    return {
        "schema_version": "scion.launcher_lifecycle.v1",
        "prepared_only": bool(prepared_only),
        "pre_campaign_completion_preflight_failed": bool(preflight_failed),
        "pre_campaign_infra_failed": pre_campaign_infra_failed,
        "pre_campaign_infra_failure_keys": pre_campaign_infra_failure_keys,
        "invalid_infra_only": bool(invalid_infra_only),
        "current_run_evidence": not (
            prepared_only
            or launcher_status_unavailable
            or preflight_failed
            or pre_campaign_infra_failed
            or campaign_execution_artifacts_unavailable
            or invalid_infra_only
        ),
        "launcher_status_unavailable": launcher_status_unavailable,
        "launcher_status_failure_key": launcher_status_failure_key,
        "root_run_status_present": run_status_present,
        "root_run_status_valid": run_status_valid,
        "campaign_execution_artifacts_available": (
            campaign_execution_artifacts_available
        ),
        "campaign_execution_artifacts_unavailable": (
            campaign_execution_artifacts_unavailable
        ),
        "campaign_execution_failure_key": campaign_execution_failure_key,
        "campaign_execution_artifacts": artifact_state.get("artifacts", {}),
        "status": _string_or_none(status_doc.get("status")),
        "prepared_status_schema": _string_or_none(status_doc.get("schema")),
        "resume_from_campaign": _string_or_none(resume_from),
        "resume_snapshot_ref": _string_or_none(resume_snapshot_ref),
        "copied_campaign_status_present": status_doc.get(
            "copied_campaign_status_present"
        ),
        "copied_campaign_summary_present": status_doc.get(
            "copied_campaign_summary_present"
        ),
        "evidence_scope": evidence_scope,
    }


def _launch_root_without_current_run(lifecycle: Mapping[str, Any]) -> bool:
    return (
        lifecycle.get("prepared_only") is True
        or lifecycle.get("launcher_status_unavailable") is True
        or lifecycle.get("pre_campaign_completion_preflight_failed") is True
        or lifecycle.get("pre_campaign_infra_failed") is True
        or lifecycle.get("campaign_execution_artifacts_unavailable") is True
        or lifecycle.get("invalid_infra_only") is True
    )


def _prepared_only_validity(lifecycle: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "run_validity_status": "prepared_only",
        "run_completeness_status": "not_started",
        "last_stop_reason": "prepared_only_not_launched",
        "invalid_infra_only": False,
    }


def _pre_campaign_failure_validity(lifecycle: Mapping[str, Any]) -> dict[str, Any]:
    last_stop_reason = "pre_campaign_completion_preflight_failed"
    launcher_status_failure_key = lifecycle.get("launcher_status_failure_key")
    if isinstance(launcher_status_failure_key, str) and launcher_status_failure_key:
        last_stop_reason = launcher_status_failure_key
    campaign_execution_failure_key = lifecycle.get("campaign_execution_failure_key")
    if (
        isinstance(campaign_execution_failure_key, str)
        and campaign_execution_failure_key
    ):
        last_stop_reason = campaign_execution_failure_key
    keys = lifecycle.get("pre_campaign_infra_failure_keys")
    if isinstance(keys, list) and keys:
        last_stop_reason = f"pre_campaign_{keys[0]}"
    return {
        "run_validity_status": "invalid_infra_only",
        "run_completeness_status": "incomplete",
        "last_stop_reason": last_stop_reason,
        "invalid_infra_only": True,
    }


def _prepared_only_counters(prepared_manifest: Any) -> dict[str, int | None]:
    manifest = prepared_manifest if isinstance(prepared_manifest, dict) else {}
    execution = manifest.get("execution")
    if not isinstance(execution, dict):
        execution = {}
    return {
        "requested_rounds": _first_int(execution, keys=("rounds",)),
        "effective_rounds_completed": 0,
        "formal_screened_candidates": 0,
        "protocol_evaluated_candidates": 0,
        "screened_experiments": 0,
        "proposal_attempts_total": 0,
    }


def _campaign_execution_artifact_state(
    *,
    campaign_dir: Path,
    marker_path: Path,
    marker: Any,
    docs: Mapping[str, Any],
) -> dict[str, Any]:
    artifacts: dict[str, dict[str, Any]] = {}
    marker_state = _campaign_execution_marker_state(marker_path, marker)
    for key, filename in CAMPAIGN_EXECUTION_ARTIFACTS:
        path = campaign_dir / filename
        doc = docs.get(key)
        valid = isinstance(doc, dict)
        fresh = (
            _campaign_execution_doc_is_fresh(
                key=key,
                path=path,
                doc=doc,
                marker_state=marker_state,
            )
            if valid
            else False
        )
        artifacts[key] = {
            "path": str(path),
            "present": path.exists(),
            "valid": valid,
            "fresh": fresh,
        }
    present_any = any(item["present"] for item in artifacts.values())
    valid_any = any(item["valid"] for item in artifacts.values())
    marker_enforced = marker_state["valid"]
    fresh_any = any(item["fresh"] for item in artifacts.values())
    available = fresh_any if marker_enforced else valid_any
    if available:
        failure_key = None
    elif marker_enforced and valid_any:
        failure_key = "campaign_execution_artifacts_stale_resume_snapshot"
    elif present_any:
        failure_key = "campaign_execution_artifacts_unreadable"
    else:
        failure_key = "campaign_execution_artifacts_missing"
    return {
        "available": available,
        "present_any": present_any,
        "valid_any": valid_any,
        "fresh_any": fresh_any,
        "freshness_marker": marker_state,
        "failure_key": failure_key,
        "artifacts": artifacts,
    }


def _empty_campaign_execution_artifact_state() -> dict[str, Any]:
    return {
        "available": False,
        "present_any": False,
        "valid_any": False,
        "fresh_any": False,
        "freshness_marker": {
            "path": "",
            "present": False,
            "valid": False,
            "started_at": None,
        },
        "failure_key": "campaign_execution_artifacts_missing",
        "artifacts": {},
    }


def _campaign_execution_marker_state(path: Path, marker: Any) -> dict[str, Any]:
    marker_doc = marker if isinstance(marker, dict) else {}
    started_at = _parse_iso_timestamp(marker_doc.get("started_at"))
    valid = (
        path.exists()
        and marker_doc.get("schema") == "scion.launcher_campaign_execution_marker.v1"
        and started_at is not None
    )
    return {
        "path": str(path),
        "present": path.exists(),
        "valid": valid,
        "schema": marker_doc.get("schema"),
        "started_at": marker_doc.get("started_at"),
        "started_at_epoch": started_at.timestamp() if started_at else None,
        "mtime": _mtime(path),
    }


def _campaign_execution_doc_is_fresh(
    *,
    key: str,
    path: Path,
    doc: Any,
    marker_state: Mapping[str, Any],
) -> bool:
    if marker_state.get("valid") is not True:
        return isinstance(doc, dict)
    marker_started = _float_or_none(marker_state.get("started_at_epoch"))
    if marker_started is None:
        return False
    if key == "campaign_run_status" and isinstance(doc, dict):
        doc_started = _parse_iso_timestamp(doc.get("started_at"))
        if doc_started is not None:
            return doc_started.timestamp() >= marker_started
    marker_mtime = _float_or_none(marker_state.get("mtime"))
    doc_mtime = _mtime(path)
    if marker_mtime is None or doc_mtime is None:
        return False
    return doc_mtime + 1e-6 >= marker_mtime


def _parse_iso_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
