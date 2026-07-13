"""Phase-4 evidence coverage inventory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from scion.postrun.inventory.constants import HANDOFF_DOC
from scion.postrun.inventory.lifecycle import _launch_root_without_current_run
from scion.postrun.inventory.prepared_ports import PreparedHandoffReviewPort
from scion.postrun.inventory.traces import (
    _prompt_manifest_ref_present,
)
from scion.postrun.inventory.utils import (
    _contains_key_fragment,
    _int_or_zero,
    _mapping_or_empty,
    _nested_int,
    _normalize_problem_family,
    _read_json,
)


def _phase4_evidence_coverage(
    *,
    run_root: Path,
    campaign_dir: Path,
    campaign_status: Any,
    summary: Any,
    llm_traces: dict[str, Any],
    proposal_attempts: Mapping[str, Any],
    proposal_runtime: Mapping[str, Any],
    lifecycle: Mapping[str, Any],
    prepared_manifest: Any = None,
    prepared_handoff_ports: Mapping[str, PreparedHandoffReviewPort] | None = None,
) -> dict[str, Any]:
    """Return report-only coverage flags for Phase 4 postrun analysis inputs."""

    proposal_runtime_mode = str(proposal_runtime.get("resolved_mode") or "")
    problem_specific_requirements = _problem_specific_phase4_requirements(
        prepared_manifest,
        prepared_handoff_ports=prepared_handoff_ports or {},
    )
    if _launch_root_without_current_run(lifecycle):
        return {
            "schema_version": "scion.postrun_phase4_evidence_coverage.v1",
            "report_only": True,
            "quality_judgment": False,
            "decision_features_excluded": True,
            "evidence_scope": lifecycle.get("evidence_scope") or "launch_root",
            "prepared_only": lifecycle.get("prepared_only") is True,
            "pre_campaign_completion_preflight_failed": (
                lifecycle.get("pre_campaign_completion_preflight_failed") is True
            ),
            "pre_campaign_infra_failed": (
                lifecycle.get("pre_campaign_infra_failed") is True
            ),
            "pre_campaign_infra_failure_keys": (
                lifecycle.get("pre_campaign_infra_failure_keys") or []
            ),
            "launcher_status_unavailable": (
                lifecycle.get("launcher_status_unavailable") is True
            ),
            "launcher_status_failure_key": lifecycle.get("launcher_status_failure_key"),
            "campaign_execution_artifacts_unavailable": (
                lifecycle.get("campaign_execution_artifacts_unavailable") is True
            ),
            "campaign_execution_failure_key": lifecycle.get(
                "campaign_execution_failure_key"
            ),
            "campaign_execution_artifacts": lifecycle.get(
                "campaign_execution_artifacts"
            )
            or {},
            "invalid_infra_only": lifecycle.get("invalid_infra_only") is True,
            "current_run_evidence": False,
            "requirements": _empty_phase4_requirements("not current-run evidence"),
            "proposal_runtime": dict(proposal_runtime),
            "problem_specific_requirements": problem_specific_requirements,
            "analysis_handoff": HANDOFF_DOC,
        }

    trace_coverage = _phase4_trace_coverage(
        campaign_dir=campaign_dir,
    )
    attempt_phase_counts = _mapping_or_empty(proposal_attempts.get("by_phase"))
    manifest_docs = _postrun_json_docs(run_root, "manifests")
    source_docs = [
        doc for doc in (summary, campaign_status, *manifest_docs) if doc
    ]
    formal_rows = _jsonl_row_count(
        campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    )
    prompt_manifest_loaded_count = sum(
        _nested_int(doc, ("prompt_manifest_loaded_count",)) or 0
        for doc in manifest_docs
    )
    prompt_signal_density_count = _prompt_signal_density_summary_count(manifest_docs)
    prompt_manifest_refs = max(
        trace_coverage.get("prompt_manifest_ref_count", 0),
        _int_or_zero(proposal_attempts.get("prompt_manifest_ref_count")),
    )
    measurement_readiness_count = sum(
        1
        for doc in (summary, campaign_status)
        if _contains_key_fragment(doc, ("measurement_readiness",))
    )
    runtime_feedback_count = sum(
        1
        for doc in source_docs
        if _contains_key_fragment(
            doc,
            (
                "runtime_feedback",
                "runtime_budget",
                "runtime_regression",
            ),
        )
    )
    source_visibility_count = sum(
        1
        for doc in source_docs
        if _contains_key_fragment(
            doc,
            ("source_visibility", "target_source_visibility", "visibility_ledger"),
        )
    )
    code_source_visibility_count = _code_source_visibility_summary_count(manifest_docs)
    return {
        "schema_version": "scion.postrun_phase4_evidence_coverage.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "evidence_scope": lifecycle.get("evidence_scope") or "postrun_campaign",
        "prepared_only": lifecycle.get("prepared_only") is True,
        "pre_campaign_completion_preflight_failed": (
            lifecycle.get("pre_campaign_completion_preflight_failed") is True
        ),
        "invalid_infra_only": lifecycle.get("invalid_infra_only") is True,
        "current_run_evidence": True,
        "proposal_runtime_mode": proposal_runtime_mode or None,
        "proposal_runtime": dict(proposal_runtime),
        "proposal_attempts": dict(proposal_attempts),
        "requirements": {
            "proposal_attempt_transition": _coverage_item(
                _int_or_zero(proposal_attempts.get("valid_row_count")),
                "campaign/scion.db proposal_attempt_transition",
            ),
            "proposal_attempt_hypothesis_phase": _coverage_item(
                _int_or_zero(attempt_phase_counts.get("hypothesis")),
                "campaign/scion.db proposal_attempt_transition",
            ),
            "proposal_attempt_code_phase": _coverage_item(
                _int_or_zero(attempt_phase_counts.get("code")),
                "campaign/scion.db proposal_attempt_transition",
            ),
            "hypothesis_trace": _coverage_item(
                max(
                    _int_or_zero(llm_traces.get("by_kind", {}).get("hypothesis")),
                    _int_or_zero(attempt_phase_counts.get("hypothesis")),
                ),
                "llm_traces or proposal attempt transitions",
            ),
            "code_trace": _coverage_item(
                max(
                    _int_or_zero(llm_traces.get("by_kind", {}).get("code")),
                    _int_or_zero(attempt_phase_counts.get("code")),
                ),
                "llm_traces or proposal attempt transitions",
            ),
            "formal_candidate_artifact": _coverage_item(
                formal_rows,
                "campaign/artifacts/formal_candidates/index.jsonl",
            ),
            "proposal_trajectory_manifest": _coverage_item(
                len(manifest_docs),
                "postrun_acceptance/manifests",
            ),
            "prompt_manifest_loaded": _coverage_item(
                prompt_manifest_loaded_count or prompt_manifest_refs,
                "proposal_trajectory_manifest or trace_index prompt_manifest refs",
            ),
            "prompt_signal_density": _coverage_item(
                prompt_signal_density_count,
                "proposal trajectory prompt block-family accounting",
            ),
            "measurement_readiness": _coverage_item(
                measurement_readiness_count,
                "campaign summary/status",
            ),
            "runtime_feedback": _coverage_item(
                runtime_feedback_count,
                "campaign summary/status runtime fields",
            ),
            "source_visibility": _coverage_item(
                source_visibility_count,
                "prompt manifests or trajectory visibility fingerprints",
            ),
            "code_source_visibility_guarantees": _coverage_item(
                code_source_visibility_count,
                "trajectory manifest code-phase source visibility guarantees",
            ),
        },
        "problem_specific_requirements": problem_specific_requirements,
        "analysis_handoff": HANDOFF_DOC,
    }


def _problem_specific_phase4_requirements(
    manifest: Any,
    *,
    prepared_handoff_ports: Mapping[str, PreparedHandoffReviewPort],
) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        return {}
    family = _normalize_problem_family(manifest.get("problem_family"))
    port = prepared_handoff_ports.get(family)
    if port is None:
        return {}
    return port.phase4_requirements(manifest, _coverage_item)


def _empty_phase4_requirements(reason: str) -> dict[str, dict[str, Any]]:
    sources = {
        "hypothesis_trace": "llm_traces",
        "code_trace": "llm_traces",
        "formal_candidate_artifact": "campaign/artifacts/formal_candidates/index.jsonl",
        "proposal_trajectory_manifest": "postrun_acceptance/manifests",
        "prompt_manifest_loaded": (
            "proposal_trajectory_manifest or trace_index prompt_manifest refs"
        ),
        "prompt_signal_density": ("proposal trajectory prompt block-family accounting"),
        "measurement_readiness": "campaign summary/status",
        "runtime_feedback": "campaign summary/status runtime fields",
        "source_visibility": "prompt manifests or trajectory visibility fingerprints",
        "code_source_visibility_guarantees": (
            "trajectory manifest code-phase source visibility guarantees"
        ),
    }
    return {
        key: _coverage_item(0, f"{source}; {reason}") for key, source in sources.items()
    }


def _prompt_signal_density_summary_count(docs: list[Any]) -> int:
    return sum(_prompt_signal_density_summary_count_in_doc(doc) for doc in docs)


def _prompt_signal_density_summary_count_in_doc(value: Any) -> int:
    if isinstance(value, dict):
        count = 1 if _has_prompt_signal_density_summary(value) else 0
        return count + sum(
            _prompt_signal_density_summary_count_in_doc(item) for item in value.values()
        )
    if isinstance(value, list):
        return sum(_prompt_signal_density_summary_count_in_doc(item) for item in value)
    return 0


def _has_prompt_signal_density_summary(value: dict[str, Any]) -> bool:
    block_summary = _mapping_or_empty(value.get("block_family_summary"))
    block_accounting = _mapping_or_empty(value.get("block_family_accounting"))
    return bool(
        _mapping_or_empty(block_summary.get("families"))
        or _mapping_or_empty(block_accounting.get("families"))
    )


def _code_source_visibility_summary_count(docs: list[Any]) -> int:
    return sum(_code_source_visibility_summary_count_in_doc(doc) for doc in docs)


def _code_source_visibility_summary_count_in_doc(value: Any) -> int:
    if isinstance(value, dict):
        count = 1 if _has_code_source_visibility_summary(value) else 0
        return count + sum(
            _code_source_visibility_summary_count_in_doc(item)
            for item in value.values()
        )
    if isinstance(value, list):
        return sum(_code_source_visibility_summary_count_in_doc(item) for item in value)
    return 0


def _has_code_source_visibility_summary(value: dict[str, Any]) -> bool:
    return bool(
        _mapping_or_empty(value.get("code_phase_guarantees"))
        or _mapping_or_empty(value.get("code_file_visibility"))
    )


def _phase4_trace_coverage(
    *,
    campaign_dir: Path,
) -> dict[str, int]:
    prompt_manifest_ref_count = 0
    for path in sorted((campaign_dir / "llm_traces").glob("*.json")):
        doc = _read_json(path)
        if _prompt_manifest_ref_present(doc):
            prompt_manifest_ref_count += 1
    return {
        "prompt_manifest_ref_count": prompt_manifest_ref_count,
    }


def _coverage_item(count: int | None, source: str) -> dict[str, Any]:
    safe_count = _int_or_zero(count)
    return {"available": safe_count > 0, "count": safe_count, "source": source}


def _postrun_json_docs(run_root: Path, family: str) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    subdir = run_root / "postrun_acceptance" / family
    if not subdir.exists():
        return docs
    for path in sorted(subdir.glob("*.json")):
        doc = _read_json(path)
        if isinstance(doc, dict):
            docs.append(doc)
    return docs


def _jsonl_row_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0
