"""Phase-4 evidence coverage inventory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from scion.postrun.inventory.constants import HANDOFF_DOC
from scion.postrun.inventory.lifecycle import _launch_root_without_current_run
from scion.postrun.inventory.prepared_ports import PreparedHandoffReviewPort
from scion.postrun.inventory.traces import (
    _is_target_intent_trace,
    _prompt_manifest_ref_present,
    _session_index_entries,
    _trace_index_entries,
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
    trace_index: Any,
    session_index: Any,
    llm_traces: dict[str, Any],
    lifecycle: Mapping[str, Any],
    prepared_manifest: Any = None,
    prepared_handoff_ports: Mapping[str, PreparedHandoffReviewPort] | None = None,
) -> dict[str, Any]:
    """Return report-only coverage flags for Phase 4 postrun analysis inputs."""

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
            "problem_specific_requirements": problem_specific_requirements,
            "analysis_handoff": HANDOFF_DOC,
        }

    trace_coverage = _phase4_trace_coverage(
        campaign_dir=campaign_dir,
        trace_index=trace_index,
        session_index=session_index,
    )
    research_docs = _postrun_json_docs(run_root, "research_efficiency")
    manifest_docs = _postrun_json_docs(run_root, "manifests")
    source_docs = [
        doc for doc in (summary, campaign_status, *research_docs, *manifest_docs) if doc
    ]
    formal_rows = _jsonl_row_count(
        campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    )
    prompt_manifest_loaded_count = sum(
        _nested_int(doc, ("prompt_manifest_loaded_count",)) or 0
        for doc in manifest_docs
    )
    prompt_signal_density_count = _prompt_signal_density_summary_count(manifest_docs)
    prompt_manifest_refs = trace_coverage.get("prompt_manifest_ref_count", 0)
    measurement_readiness_count = sum(
        1
        for doc in (summary, campaign_status, *research_docs)
        if _contains_key_fragment(doc, ("measurement_readiness",))
    )
    effect_vs_mde_count = sum(
        1
        for doc in research_docs
        if _contains_key_fragment(doc, ("protocol_effects_vs_mde", "mde_source"))
    )
    protocol_accounting_count = _protocol_accounting_summary_count(research_docs)
    validation_frozen_stage_count = _validation_frozen_stage_accounting_count(
        research_docs
    )
    branch_lesson_count = sum(
        1
        for doc in source_docs
        if _contains_key_fragment(doc, ("branch_lesson", "cross_branch"))
    )
    research_continuity_count = sum(
        1
        for doc in research_docs
        if _contains_key_fragment(
            doc,
            (
                "research_continuity",
                "same_mechanism_followup",
                "weak_positive_transfer",
            ),
        )
    )
    same_mechanism_followup_count = _research_continuity_field_count(
        research_docs,
        "same_mechanism_followup",
    )
    branch_lesson_usage_count = _research_continuity_field_count(
        research_docs,
        "branch_lesson_usage",
    )
    weak_positive_transfer_count = _research_continuity_field_count(
        research_docs,
        "weak_positive_transfer",
    )
    branch_research_shape_count = _research_continuity_field_count(
        research_docs,
        "research_shape_summary",
    )
    runtime_feedback_count = sum(
        1
        for doc in source_docs
        if _contains_key_fragment(
            doc,
            (
                "runtime_feedback",
                "runtime_budget",
                "fresh_runtime_replay",
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
        "requirements": {
            "target_intent_trace": _coverage_item(
                trace_coverage.get("target_intent_trace_count", 0),
                "llm_traces or trace_index",
            ),
            "hypothesis_trace": _coverage_item(
                _int_or_zero(llm_traces.get("by_kind", {}).get("hypothesis")),
                "llm_traces",
            ),
            "code_trace": _coverage_item(
                _int_or_zero(llm_traces.get("by_kind", {}).get("code")),
                "llm_traces",
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
            "research_efficiency_report": _coverage_item(
                len(research_docs),
                "postrun_acceptance/research_efficiency",
            ),
            "measurement_readiness": _coverage_item(
                measurement_readiness_count,
                "campaign summary/status or research-efficiency report",
            ),
            "protocol_effect_vs_mde": _coverage_item(
                effect_vs_mde_count,
                "research-efficiency protocol_effects_vs_mde",
            ),
            "protocol_accounting": _coverage_item(
                protocol_accounting_count,
                "research-efficiency protocol_rows/formal_candidates/stage_rows",
            ),
            "validation_frozen_stage_accounting": _coverage_item(
                validation_frozen_stage_count,
                "research-efficiency validation/frozen stage accounting",
            ),
            "branch_lesson_transfer": _coverage_item(
                branch_lesson_count,
                "summary/status, research-efficiency, or trajectory manifest",
            ),
            "research_continuity": _coverage_item(
                research_continuity_count,
                "research-efficiency research_continuity",
            ),
            "same_mechanism_followup": _coverage_item(
                same_mechanism_followup_count,
                "research-efficiency research_continuity.same_mechanism_followup",
            ),
            "branch_lesson_usage": _coverage_item(
                branch_lesson_usage_count,
                "research-efficiency research_continuity.branch_lesson_usage",
            ),
            "weak_positive_transfer": _coverage_item(
                weak_positive_transfer_count,
                "research-efficiency research_continuity.weak_positive_transfer",
            ),
            "branch_research_shape": _coverage_item(
                branch_research_shape_count,
                "research-efficiency research_continuity.research_shape_summary",
            ),
            "runtime_feedback": _coverage_item(
                runtime_feedback_count,
                "summary/status or research-efficiency runtime fields",
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
        "target_intent_trace": "llm_traces or trace_index",
        "hypothesis_trace": "llm_traces",
        "code_trace": "llm_traces",
        "formal_candidate_artifact": "campaign/artifacts/formal_candidates/index.jsonl",
        "proposal_trajectory_manifest": "postrun_acceptance/manifests",
        "prompt_manifest_loaded": (
            "proposal_trajectory_manifest or trace_index prompt_manifest refs"
        ),
        "prompt_signal_density": ("proposal trajectory prompt block-family accounting"),
        "research_efficiency_report": "postrun_acceptance/research_efficiency",
        "measurement_readiness": (
            "campaign summary/status or research-efficiency report"
        ),
        "protocol_effect_vs_mde": "research-efficiency protocol_effects_vs_mde",
        "protocol_accounting": (
            "research-efficiency protocol_rows/formal_candidates/stage_rows"
        ),
        "validation_frozen_stage_accounting": (
            "research-efficiency validation/frozen stage accounting"
        ),
        "branch_lesson_transfer": (
            "summary/status, research-efficiency, or trajectory manifest"
        ),
        "research_continuity": "research-efficiency research_continuity",
        "same_mechanism_followup": (
            "research-efficiency research_continuity.same_mechanism_followup"
        ),
        "branch_lesson_usage": (
            "research-efficiency research_continuity.branch_lesson_usage"
        ),
        "weak_positive_transfer": (
            "research-efficiency research_continuity.weak_positive_transfer"
        ),
        "branch_research_shape": (
            "research-efficiency research_continuity.research_shape_summary"
        ),
        "runtime_feedback": "summary/status or research-efficiency runtime fields",
        "source_visibility": "prompt manifests or trajectory visibility fingerprints",
        "code_source_visibility_guarantees": (
            "trajectory manifest code-phase source visibility guarantees"
        ),
    }
    return {
        key: _coverage_item(0, f"{source}; {reason}") for key, source in sources.items()
    }


def _protocol_accounting_summary_count(docs: list[Any]) -> int:
    return sum(
        1
        for doc in docs
        if isinstance(doc, dict) and _has_protocol_accounting_summary(doc)
    )


def _has_protocol_accounting_summary(doc: dict[str, Any]) -> bool:
    return any(
        isinstance(doc.get(key), dict) and bool(doc.get(key))
        for key in (
            "effective_budget",
            "protocol_rows",
            "formal_candidates",
            "formal_candidate_artifacts",
            "stage_rows",
        )
    )


def _validation_frozen_stage_accounting_count(docs: list[Any]) -> int:
    return sum(
        1
        for doc in docs
        if isinstance(doc, dict) and _has_validation_frozen_stage_accounting(doc)
    )


def _has_validation_frozen_stage_accounting(doc: dict[str, Any]) -> bool:
    stage_rows = _mapping_or_empty(doc.get("stage_rows"))
    if "validation" in stage_rows or "frozen" in stage_rows:
        return True
    protocol_rows = _mapping_or_empty(doc.get("protocol_rows"))
    stage_counts = _mapping_or_empty(protocol_rows.get("stage_counts"))
    return "validation" in stage_counts or "frozen" in stage_counts


def _research_continuity_field_count(docs: list[Any], field: str) -> int:
    count = 0
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        continuity = doc.get("research_continuity")
        if not isinstance(continuity, dict):
            continue
        value = continuity.get(field)
        if isinstance(value, dict) and value:
            count += 1
    return count


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
    trace_index: Any,
    session_index: Any,
) -> dict[str, int]:
    file_target_intent_count = 0
    index_target_intent_count = 0
    prompt_manifest_ref_count = 0
    for path in sorted((campaign_dir / "llm_traces").glob("*.json")):
        doc = _read_json(path)
        if _is_target_intent_trace(doc, path):
            file_target_intent_count += 1
        if _prompt_manifest_ref_present(doc):
            prompt_manifest_ref_count += 1
    for entry in _trace_index_entries(trace_index):
        if _is_target_intent_trace(entry, None):
            index_target_intent_count += 1
        if _prompt_manifest_ref_present(entry):
            prompt_manifest_ref_count += 1
    for entry in _session_index_entries(session_index):
        if _prompt_manifest_ref_present(entry):
            prompt_manifest_ref_count += 1
    return {
        "target_intent_trace_count": max(
            file_target_intent_count,
            index_target_intent_count,
        ),
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
