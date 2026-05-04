"""Helpers for attaching final evidence package refs to campaign summaries."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


__all__ = [
    "attach_final_evidence_package",
    "build_final_evidence_refs",
    "FINAL_QUALITY_ARTIFACT_KEYS",
    "MANIFEST_METADATA_KEYS",
]

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


def build_final_evidence_refs(
    package_result: Any,
    label: str = "final_quality",
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
    payload["artifacts"] = _artifact_refs(artifacts)
    return {label: payload}


def attach_final_evidence_package(
    recorder: Any,
    package_result: Any,
    label: str = "final_quality",
) -> dict[str, dict[str, Any]]:
    """Attach package refs through ``EvidenceRecorder`` and return the payload."""

    payload = build_final_evidence_refs(package_result, label=label)
    recorder.attach_final_evidence_refs(payload)
    return payload


def _artifact_refs(artifacts: Mapping[str, Any]) -> dict[str, str | None]:
    refs = {
        key: _string_ref(artifacts.get(key))
        for key in FINAL_QUALITY_ARTIFACT_KEYS
    }
    for key, value in artifacts.items():
        if key not in refs:
            refs[key] = _string_ref(value)
    return refs


def _string_ref(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Path):
        return str(value)
    return str(value)
