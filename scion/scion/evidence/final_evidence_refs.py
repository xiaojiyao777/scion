"""Helpers for attaching final evidence package refs to campaign summaries."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from scion.core.public_refs import public_artifact_ref


__all__ = [
    "attach_final_evidence_package",
    "build_final_evidence_closure_refs",
    "build_final_evidence_refs",
    "FINAL_QUALITY_ARTIFACT_KEYS",
    "FINAL_EVIDENCE_CLOSURE_SCHEMA",
    "FINAL_EVIDENCE_REASON_NORMAL_COMPLETION",
    "FINAL_EVIDENCE_REASON_PENDING_EXTERNAL",
    "FINAL_EVIDENCE_STATUS_NON_FORMAL_CLOSED",
    "FINAL_EVIDENCE_STATUS_PENDING_EXTERNAL",
    "MANIFEST_METADATA_KEYS",
]

FINAL_EVIDENCE_CLOSURE_SCHEMA = "scion.final_evidence_refs.closure.v1"
FINAL_EVIDENCE_STATUS_NON_FORMAL_CLOSED = "non_formal_final_evidence_closed"
FINAL_EVIDENCE_STATUS_PENDING_EXTERNAL = "pending_external_final_evidence"
FINAL_EVIDENCE_REASON_NORMAL_COMPLETION = (
    "normal_campaign_completed_without_formal_final_evidence"
)
FINAL_EVIDENCE_REASON_PENDING_EXTERNAL = "external_final_evidence_pending"

FINAL_QUALITY_ARTIFACT_KEYS = (
    "manifest",
    "final_quality_json",
    "final_quality_csv",
    "per_case_quality_csv",
    "runtime_summary",
    "failure_summary",
)

MANIFEST_METADATA_KEYS = (
    "schema",
    "package_type",
    "problem_id",
    "campaign_id",
    "baseline_label",
    "candidate_label",
    "n_cases",
)


def build_final_evidence_closure_refs(
    *,
    reason: str,
    reason_code: str = FINAL_EVIDENCE_REASON_NORMAL_COMPLETION,
    status: str = FINAL_EVIDENCE_STATUS_NON_FORMAL_CLOSED,
    required_for_formal_readiness: bool = False,
) -> dict[str, Any]:
    """Build a public closure index when no final evidence package is attached."""

    return {
        "schema": FINAL_EVIDENCE_CLOSURE_SCHEMA,
        "status": status,
        "reason_code": reason_code,
        "reason": reason,
        "required_for_formal_readiness": required_for_formal_readiness,
    }


def build_final_evidence_refs(
    package_result: Any,
    label: str = "final_quality",
    *,
    base_dir: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Build a stable summary payload from an already-written evidence package.

    The helper intentionally reads only in-memory package/result metadata. It
    does not open artifact paths or inspect artifact contents.
    """

    package = getattr(package_result, "package", None)
    artifacts = getattr(package_result, "artifacts", None)
    if package is None or artifacts is None:
        raise ValueError("package_result must expose package and artifacts attributes")
    if not isinstance(artifacts, Mapping):
        raise TypeError("package_result.artifacts must be a mapping")

    manifest = getattr(package, "manifest", {}) or {}
    if not isinstance(manifest, Mapping):
        raise TypeError("package_result.package.manifest must be a mapping")

    payload: dict[str, Any] = {
        key: manifest.get(key) for key in MANIFEST_METADATA_KEYS
    }
    payload["artifacts"] = _artifact_refs(artifacts, base_dir=base_dir)
    return {label: payload}


def attach_final_evidence_package(
    recorder: Any,
    package_result: Any,
    label: str = "final_quality",
) -> dict[str, dict[str, Any]]:
    """Attach package refs through ``EvidenceRecorder`` and return the payload."""

    payload = build_final_evidence_refs(
        package_result,
        label=label,
        base_dir=getattr(recorder, "campaign_dir", None),
    )
    recorder.attach_final_evidence_refs(payload)
    return payload


def _artifact_refs(
    artifacts: Mapping[str, Any],
    *,
    base_dir: str | Path | None = None,
) -> dict[str, str | None]:
    refs = {
        key: _string_ref(artifacts.get(key), base_dir=base_dir)
        for key in FINAL_QUALITY_ARTIFACT_KEYS
    }
    for key, value in artifacts.items():
        if key not in refs:
            refs[key] = _string_ref(value, base_dir=base_dir)
    return refs


def _string_ref(
    value: Any,
    *,
    base_dir: str | Path | None = None,
) -> str | None:
    if value is None:
        return None
    return public_artifact_ref(value, base_dir=base_dir, kind="artifact")
