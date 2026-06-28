"""Problem prompt bridge specs for prepared prompt-context readiness."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


SourceMarker = tuple[str, str]
ACTIVE_SUBJECT_CODE_CONSTRAINT_PROVIDER_SUMMARY_SCHEMA = (
    "scion.active_subject_code_constraints_provider_payload_summary.v1"
)


@dataclass(frozen=True)
class ProblemPromptBridgeSpec:
    """Problem-owned prompt bridge metadata consumed by generic readiness tools."""

    problem_family: str
    problem_v1_candidates: tuple[str, ...]
    measurement_signal_name: str
    measurement_failure_prefix: str
    measurement_source_markers: Mapping[str, SourceMarker]
    measurement_bridge_scope: str
    active_subject_signal_name: str
    active_subject_failure_prefix: str
    active_subject_surface: str
    active_subject_provider_markers: Mapping[str, SourceMarker]

    @property
    def measurement_marker_group_name(self) -> str:
        return f"{self.problem_family}_problem_measurement_diagnostics_source_markers"

    @property
    def active_subject_marker_group_name(self) -> str:
        if self.problem_family == "cvrp":
            return "cvrp_active_subject_code_constraint_source_markers"
        if self.problem_family == "warehouse_delivery":
            return "warehouse_active_subject_code_constraint_source_markers"
        return f"{self.problem_family}_active_subject_code_constraint_source_markers"


def resolve_problem_v1_path(
    *,
    root: Path,
    manifest: Mapping[str, Any],
    repo_dir: Path,
    spec: ProblemPromptBridgeSpec,
) -> Path | None:
    config = _mapping_or_empty(manifest.get("config"))
    candidates: list[Path] = []
    configured = str(config.get("problem_v1") or "").strip()
    if configured:
        path = Path(configured).expanduser()
        if path.is_absolute():
            candidates.append(path)
        else:
            candidates.extend((root / path, repo_dir / path))
    for rel in spec.problem_v1_candidates:
        candidates.append(repo_dir / rel)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def active_subject_code_constraints_provider_payload_summary(
    *,
    root: Path,
    manifest: Mapping[str, Any],
    repo_dir: Path,
    spec: ProblemPromptBridgeSpec,
) -> dict[str, Any]:
    problem_v1 = resolve_problem_v1_path(
        root=root,
        manifest=manifest,
        repo_dir=repo_dir,
        spec=spec,
    )
    base = {
        "schema_version": ACTIVE_SUBJECT_CODE_CONSTRAINT_PROVIDER_SUMMARY_SCHEMA,
        "problem_family": spec.problem_family,
        "surface": spec.active_subject_surface,
        "problem_v1_path": str(problem_v1) if problem_v1 else "",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_payload_excluded": True,
    }
    if not problem_v1:
        return {**base, "available": False, "reason": "problem_v1_not_found"}
    try:
        from scion.problem.bridge import load_problem_spec_v1_from_yaml
        from scion.problem.loader import load_problem_adapter
        from scion.problem.providers import active_subject_code_constraints_payload

        problem_spec = load_problem_spec_v1_from_yaml(problem_v1)
        adapter = load_problem_adapter(problem_spec)
        payload = active_subject_code_constraints_payload(
            problem_spec=problem_spec,
            adapter=adapter,
            surface=spec.active_subject_surface,
        )
    except Exception as exc:  # pragma: no cover - surfaced as readiness detail.
        return {
            **base,
            "available": False,
            "reason": "provider_payload_error",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

    counts = {
        "constraint_count": _sequence_count(payload.get("constraints")),
        "object_model_hint_count": _sequence_count(payload.get("object_model_hints")),
        "api_contract_count": _sequence_count(payload.get("api_contracts")),
        "forbidden_pattern_count": _sequence_count(payload.get("forbidden_patterns")),
    }
    total = sum(counts.values())
    version = str(payload.get("version") or "").strip()
    available = bool(payload) and bool(version) and total > 0
    return {
        **base,
        "available": available,
        "reason": "ok" if available else "empty_payload",
        "version": version,
        "subject_id": str(payload.get("subject_id") or "").strip(),
        **counts,
        "total_guidance_item_count": total,
    }


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _sequence_count(value: Any) -> int:
    if isinstance(value, (list, tuple)):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    return 0
