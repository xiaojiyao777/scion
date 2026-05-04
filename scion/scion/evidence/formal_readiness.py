"""Formal campaign readiness checks for final evidence refs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from scion.evidence.final_evidence_refs import (
    FINAL_QUALITY_ARTIFACT_KEYS,
    MANIFEST_METADATA_KEYS,
)


@dataclass(frozen=True)
class FormalReadinessReport:
    formal_ready: bool
    missing: tuple[str, ...]
    refs: Mapping[str, Any]


def validate_formal_readiness(
    final_evidence_refs: Mapping[str, Any] | None,
    *,
    label: str | None = None,
) -> FormalReadinessReport:
    """Validate that final evidence refs contain a complete artifact package.

    The check intentionally inspects only the summary refs structure. It does
    not open artifact files and does not mutate step schemas.
    """

    refs = dict(final_evidence_refs or {})
    if not refs:
        return FormalReadinessReport(
            formal_ready=False,
            missing=("final_evidence_refs",),
            refs=refs,
        )

    package_label = _select_package_label(refs, label=label)
    if package_label is None:
        return FormalReadinessReport(
            formal_ready=False,
            missing=("final_evidence_refs.package",),
            refs=refs,
        )

    package = refs.get(package_label)
    if not isinstance(package, Mapping):
        return FormalReadinessReport(
            formal_ready=False,
            missing=(f"{package_label}",),
            refs=refs,
        )

    missing: list[str] = []
    for key in MANIFEST_METADATA_KEYS:
        if not package.get(key):
            missing.append(f"{package_label}.{key}")

    artifacts = package.get("artifacts")
    if not isinstance(artifacts, Mapping):
        missing.append(f"{package_label}.artifacts")
    else:
        for key in FINAL_QUALITY_ARTIFACT_KEYS:
            if not artifacts.get(key):
                missing.append(f"{package_label}.artifacts.{key}")

    return FormalReadinessReport(
        formal_ready=not missing,
        missing=tuple(missing),
        refs=refs,
    )


def _select_package_label(
    refs: Mapping[str, Any],
    *,
    label: str | None,
) -> str | None:
    if label is not None:
        return label if label in refs else None
    if "final_quality" in refs:
        return "final_quality"
    for key, value in refs.items():
        if isinstance(value, Mapping):
            return str(key)
    return None

