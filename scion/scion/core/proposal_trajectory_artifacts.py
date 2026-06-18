"""Report-only proposal trajectory manifest artifacts.

This module projects existing agentic proposal audit indexes into compact
fingerprints for posthoc governance trajectory analysis.  It never reads raw
trace payloads, materializes workspaces, replays LLM calls, or mutates campaign
state.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scion.core.explore_step.branch_lesson_usage import (
    BRANCH_LESSON_USAGE_REPORT_PROJECTION_SCHEMA,
    branch_lesson_usage_report_projection,
)

SCHEMA_VERSION = "scion.proposal_trajectory_manifest.v1"
COMPARISON_SCHEMA_VERSION = "scion.proposal_trajectory_comparison.v1"
BRANCH_LESSON_USAGE_ACCOUNTING_SCHEMA = "branch_lesson_usage_accounting.v1"
DEFAULT_MANIFEST_FILENAME = "proposal_trajectory_manifest.v1.json"
DEFAULT_COMPARISON_FILENAME = "proposal_trajectory_comparison.v1.json"
OBSERVED_CONTROL_ARMS = {"on", "record_only"}
_CONTROL_PAIR_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

_GUARDRAILS: dict[str, bool] = {
    "report_only": True,
    "decision_features_excluded": True,
    "comparison_is_decision_input": False,
    "campaign_state_mutated": False,
    "scheduler_state_mutated": False,
    "promotion_state_mutated": False,
    "raw_prompt_excluded": True,
    "raw_response_excluded": True,
    "patch_body_excluded": True,
}

_SESSION_INDEX_REF = "agentic_sessions/agentic_session_index.json"
_TRACE_INDEX_REF = "agentic_sessions/agentic_session_trace_index.json"
_FORMAL_CANDIDATE_INDEX_REF = "artifacts/formal_candidates/index.jsonl"


def build_proposal_trajectory_manifest(
    campaign_dir: str | Path,
    *,
    observed_control_arm: str,
    control_pair_key: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a compact report-only proposal trajectory manifest."""

    arm = str(observed_control_arm or "").strip()
    if arm not in OBSERVED_CONTROL_ARMS:
        raise ValueError(
            "observed_control_arm must be one of: "
            + ", ".join(sorted(OBSERVED_CONTROL_ARMS))
        )
    sanitized_control_pair_key = _sanitize_control_pair_key(control_pair_key)
    campaign_path = Path(campaign_dir).expanduser().resolve()
    agentic_dir = campaign_path / "agentic_sessions"
    session_index_path = agentic_dir / "agentic_session_index.json"
    trace_index_path = agentic_dir / "agentic_session_trace_index.json"
    formal_index_path = campaign_path / "artifacts" / "formal_candidates" / "index.jsonl"

    session_items, session_index_status = _read_session_index(session_index_path)
    trace_sessions, trace_index_status = _read_trace_index(trace_index_path)
    formal_rows, formal_index_status = _read_formal_candidate_index(formal_index_path)
    formal_join_index = _FormalCandidateJoinIndex(formal_rows)

    trace_by_session = {
        _clean_str(item.get("session_id")): item
        for item in trace_sessions
        if _clean_str(item.get("session_id"))
    }

    prompt_manifest_ref_count = 0
    prompt_manifest_loaded_count = 0
    sessions: list[dict[str, Any]] = []
    missing_joins: list[dict[str, str]] = []

    sorted_session_items = sorted(session_items, key=_session_sort_key)
    session_join_hints = _session_join_hints(
        sorted_session_items,
        trace_by_session=trace_by_session,
    )

    for item in sorted_session_items:
        session = _session_fingerprint(
            item,
            trace_by_session.get(_clean_str(item.get("session_id"))),
            formal_join_index=formal_join_index,
            campaign_dir=campaign_path,
            agentic_dir=agentic_dir,
            join_hints=session_join_hints.get(_clean_str(item.get("session_id")), {}),
        )
        prompt_manifest_ref_count += session.pop("_prompt_manifest_ref_count", 0)
        prompt_manifest_loaded_count += session.pop("_prompt_manifest_loaded_count", 0)
        if not session["proposal_fingerprint"].get("formal_candidate_ref"):
            missing_joins.append(
                {
                    "session_id": session["session_id"],
                    "branch_id": session["branch_id"],
                    "reason": session["replayability"]["formal_candidate_join_status"],
                }
            )
        sessions.append(session)

    trace_count = sum(len(session["trace_fingerprints"]) for session in sessions)
    formal_joined_count = sum(
        1
        for session in sessions
        if session["proposal_fingerprint"].get("formal_candidate_ref")
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "proposal_trajectory_manifest",
        "generated_at": generated_at or _utc_now_iso(),
        "campaign_dir": str(campaign_path),
        "observed_control_arm": arm,
        "control_pair_key": sanitized_control_pair_key,
        **_GUARDRAILS,
        "source_indexes": {
            "agentic_session_index_ref": (
                _SESSION_INDEX_REF if session_index_path.exists() else ""
            ),
            "agentic_session_index_status": session_index_status,
            "agentic_session_trace_index_ref": (
                _TRACE_INDEX_REF if trace_index_path.exists() else ""
            ),
            "agentic_session_trace_index_status": trace_index_status,
            "formal_candidate_index_ref": (
                _FORMAL_CANDIDATE_INDEX_REF if formal_index_path.exists() else ""
            ),
            "formal_candidate_index_status": formal_index_status,
        },
        "counts": {
            "session_count": len(sessions),
            "trace_count": trace_count,
            "formal_candidate_count": len(formal_rows),
            "formal_candidate_replayable_count": len(
                formal_join_index.replayable_rows
            ),
            "formal_candidate_joined_session_count": formal_joined_count,
            "prompt_manifest_ref_count": prompt_manifest_ref_count,
            "prompt_manifest_loaded_count": prompt_manifest_loaded_count,
        },
        "coverage": {
            "sessions_with_traces": sum(
                1 for session in sessions if session["trace_fingerprints"]
            ),
            "sessions_with_formal_candidate": formal_joined_count,
            "missing_joins": missing_joins,
            "missing_join_count": len(missing_joins),
            "formal_candidate_join_basis_counts": dict(
                sorted(formal_join_index.join_basis_counts.items())
            ),
        },
        "context_arm_fingerprint": _context_arm_fingerprint(sessions),
        "call_kind_counts": _call_kind_counts(sessions),
        "proposal_distributions": _proposal_distributions(sessions),
        "prompt_block_family_aggregate": _block_family_aggregate(sessions),
        "branch_lesson_usage_accounting": _branch_lesson_usage_accounting(sessions),
        "sessions": sessions,
    }
    return manifest


def write_proposal_trajectory_manifest(
    campaign_dir: str | Path,
    *,
    observed_control_arm: str,
    control_pair_key: str | None = None,
    output_path: str | Path,
) -> Path:
    """Build and write a proposal trajectory manifest JSON artifact."""

    destination = Path(output_path).expanduser().resolve()
    manifest = build_proposal_trajectory_manifest(
        campaign_dir,
        observed_control_arm=observed_control_arm,
        control_pair_key=control_pair_key,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_stable_json(manifest), encoding="utf-8")
    return destination


def build_proposal_trajectory_comparison(
    left: str | Path | Mapping[str, Any],
    right: str | Path | Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Compare two report-only proposal trajectory manifests."""

    left_manifest = _load_manifest(left)
    right_manifest = _load_manifest(right)
    _validate_manifest(left_manifest, side="left")
    _validate_manifest(right_manifest, side="right")

    left_key = _manifest_control_pair_key(left_manifest, side="left")
    right_key = _manifest_control_pair_key(right_manifest, side="right")
    paired_control_key = left_key if left_key and left_key == right_key else ""
    observational_only = not bool(paired_control_key)

    comparison = {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "artifact_kind": "proposal_trajectory_comparison",
        "generated_at": generated_at or _utc_now_iso(),
        **_GUARDRAILS,
        "observational_only": observational_only,
        "llm_deterministic_replay": False,
        "control_pair_key": paired_control_key,
        "causal_replay_label": (
            "observational_only_not_causal_llm_trajectory_replay"
            if observational_only
            else "control_pair_key_matched_not_deterministic_llm_replay"
        ),
        "summary": {
            "left": _manifest_count_summary(left_manifest),
            "right": _manifest_count_summary(right_manifest),
            "delta": _count_delta(left_manifest, right_manifest),
        },
        "context_arm_fingerprints": {
            "left": _mapping(left_manifest.get("context_arm_fingerprint")),
            "right": _mapping(right_manifest.get("context_arm_fingerprint")),
        },
        "call_kind_counts": _paired_counter_summary(
            left_manifest.get("call_kind_counts"),
            right_manifest.get("call_kind_counts"),
        ),
        "proposal_distributions": {
            key: _paired_counter_summary(
                _mapping_at(left_manifest, "proposal_distributions", key),
                _mapping_at(right_manifest, "proposal_distributions", key),
            )
            for key in (
                "selected_surface",
                "action",
                "target_file",
                "mechanism_id",
            )
        },
        "prompt_block_family_aggregate_shares": _paired_family_share_summary(
            left_manifest.get("prompt_block_family_aggregate"),
            right_manifest.get("prompt_block_family_aggregate"),
        ),
        "branch_lesson_usage_accounting": _paired_counter_summary(
            _branch_lesson_usage_numeric_summary(left_manifest),
            _branch_lesson_usage_numeric_summary(right_manifest),
        ),
        "coverage": {
            "left": _coverage_summary(left_manifest),
            "right": _coverage_summary(right_manifest),
        },
        "missing_joins": {
            "left": _missing_joins(left_manifest),
            "right": _missing_joins(right_manifest),
        },
    }
    return comparison


def write_proposal_trajectory_comparison(
    left: str | Path,
    right: str | Path,
    *,
    output_path: str | Path,
) -> Path:
    """Build and write a proposal trajectory comparison JSON artifact."""

    destination = Path(output_path).expanduser().resolve()
    comparison = build_proposal_trajectory_comparison(left, right)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_stable_json(comparison), encoding="utf-8")
    return destination


def _session_fingerprint(
    item: Mapping[str, Any],
    trace_session: Mapping[str, Any] | None,
    *,
    formal_join_index: "_FormalCandidateJoinIndex",
    campaign_dir: Path,
    agentic_dir: Path,
    join_hints: Mapping[str, Any],
) -> dict[str, Any]:
    session_id = _clean_str(item.get("session_id"))
    request_id = _clean_str(item.get("request_id")) or session_id
    branch_id = _clean_str(item.get("branch_id"))
    hypothesis_summary = _mapping(item.get("hypothesis_summary"))
    mechanism_ids = _string_list(
        item.get("mechanism_ids") or hypothesis_summary.get("mechanism_ids")
    )
    selected_surface = _clean_str(
        item.get("selected_surface") or hypothesis_summary.get("selected_surface")
    )
    action = _clean_str(item.get("action") or hypothesis_summary.get("action"))
    target_file = _clean_str(
        item.get("target_file") or hypothesis_summary.get("target_file")
    )
    formal_candidate = formal_join_index.match_session(
        {
            "session_id": session_id,
            "request_id": request_id,
            "branch_id": branch_id,
            "hypothesis_id": _clean_str(
                item.get("hypothesis_id") or hypothesis_summary.get("hypothesis_id")
            ),
            "has_code_trace": _clean_str(join_hints.get("has_code_trace")),
            "branch_code_ordinal": _clean_str(
                join_hints.get("branch_code_ordinal")
            ),
            "branch_code_session_count": _clean_str(
                join_hints.get("branch_code_session_count")
            ),
        }
    )
    trace_fingerprints, prompt_ref_count, prompt_loaded_count = _trace_fingerprints(
        trace_session,
        session_prompt_refs=_prompt_manifest_refs(item),
        campaign_dir=campaign_dir,
        agentic_dir=agentic_dir,
    )
    branch_lesson_usage = _branch_lesson_usage_fingerprint(
        item,
        campaign_dir=campaign_dir,
        agentic_dir=agentic_dir,
    )
    proposal = {
        "selected_surface": selected_surface,
        "action": action,
        "target_file": target_file,
        "mechanism_ids": mechanism_ids,
        "hypothesis_digest": _text_digest(hypothesis_summary.get("hypothesis_text")),
        "patch_digest": formal_candidate.get("patch_digest", ""),
        "formal_candidate_ref": formal_candidate.get("artifact_ref", ""),
        "formal_candidate_id": formal_candidate.get("candidate_id", ""),
        "formal_candidate_join_basis": formal_candidate.get("join_basis", ""),
    }
    return {
        "session_id": session_id,
        "request_id": request_id,
        "branch_id": branch_id,
        "status": _clean_str(item.get("status")),
        "termination_reason": _clean_str(item.get("termination_reason")),
        "context_profile": _clean_str(
            item.get("context_profile") or trace_session and trace_session.get("context_profile")
        ),
        "problem_fingerprint": {
            "problem_id": _clean_str(
                item.get("problem_id") or trace_session and trace_session.get("problem_id")
            ),
            "problem_spec_hash": _clean_str(
                item.get("problem_spec_hash")
                or trace_session
                and trace_session.get("problem_spec_hash")
            ),
            "split_manifest_hash": _clean_str(
                item.get("split_manifest_hash")
                or trace_session
                and trace_session.get("split_manifest_hash")
            ),
            "seed_ledger_hash": _clean_str(
                item.get("seed_ledger_hash")
                or trace_session
                and trace_session.get("seed_ledger_hash")
            ),
        },
        "proposal_fingerprint": _drop_empty(proposal),
        "branch_lesson_usage_fingerprint": branch_lesson_usage,
        "trace_fingerprints": trace_fingerprints,
        "replayability": {
            "summary": "posthoc_audit_fingerprints_only_no_llm_replay",
            "prompt_manifest_required": bool(item.get("prompt_manifest_required")),
            "prompt_manifest_available": prompt_loaded_count > 0,
            "trace_count": len(trace_fingerprints),
            "formal_candidate_joined": bool(formal_candidate.get("artifact_ref")),
            "formal_candidate_join_status": (
                "joined"
                if formal_candidate.get("artifact_ref")
                else formal_candidate.get("join_status", "missing")
            ),
        },
        "_prompt_manifest_ref_count": prompt_ref_count,
        "_prompt_manifest_loaded_count": prompt_loaded_count,
    }


def _branch_lesson_usage_fingerprint(
    item: Mapping[str, Any],
    *,
    campaign_dir: Path,
    agentic_dir: Path,
) -> dict[str, Any]:
    hypothesis_summary = _mapping(item.get("hypothesis_summary"))
    from_summary = _coerce_branch_lesson_usage_projection(
        hypothesis_summary.get("branch_lesson_usage")
    )
    if from_summary:
        return from_summary
    artifact = _load_session_output_artifact(
        item,
        campaign_dir=campaign_dir,
        agentic_dir=agentic_dir,
    )
    hypothesis = _mapping(artifact.get("hypothesis"))
    return _coerce_branch_lesson_usage_projection(
        hypothesis.get("branch_lesson_usage")
    )


def _coerce_branch_lesson_usage_projection(value: Any) -> dict[str, Any]:
    payload = _mapping(value)
    if not payload:
        return {}
    if (
        _clean_str(payload.get("schema_version"))
        == BRANCH_LESSON_USAGE_REPORT_PROJECTION_SCHEMA
    ):
        return _sanitize_branch_lesson_usage_projection(payload)
    return _sanitize_branch_lesson_usage_projection(
        branch_lesson_usage_report_projection(payload)
    )


def _sanitize_branch_lesson_usage_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    if not value:
        return {}
    field_counts = {
        str(key): _int_or_zero(count)
        for key, count in _mapping(value.get("field_counts")).items()
        if _int_or_zero(count)
    }
    projection_digest = _clean_str(value.get("projection_digest"))[:32]
    return _drop_empty(
        {
            "schema_version": BRANCH_LESSON_USAGE_REPORT_PROJECTION_SCHEMA,
            "present": bool(value.get("present")),
            "semantic_projection_present": bool(
                value.get("semantic_projection_present")
            ),
            "unrecognized_usage_present": bool(
                value.get("unrecognized_usage_present")
            ),
            "projection_digest": projection_digest,
            "field_counts": field_counts,
            "item_count": _int_or_zero(value.get("item_count")),
            "clean_fork_diversity_claim_present": bool(
                value.get("clean_fork_diversity_claim_present")
            ),
            "report_only": True,
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
        }
    )


def _load_session_output_artifact(
    item: Mapping[str, Any],
    *,
    campaign_dir: Path,
    agentic_dir: Path,
) -> Mapping[str, Any]:
    refs = _string_list(
        (
            item.get("output_artifact_ref"),
            item.get("artifact_ref"),
            item.get("artifact_path"),
        )
    )
    session_id = _clean_str(item.get("session_id"))
    if session_id:
        refs.append(f"{session_id}/output.json")
    for ref in refs:
        path = _resolve_artifact_ref(
            ref,
            campaign_dir=campaign_dir,
            agentic_dir=agentic_dir,
        )
        if path is None or not path.exists():
            continue
        try:
            raw = _read_json(path)
        except (OSError, ValueError):
            continue
        if isinstance(raw, Mapping):
            return raw
    return {}


def _trace_fingerprints(
    trace_session: Mapping[str, Any] | None,
    *,
    session_prompt_refs: list[str],
    campaign_dir: Path,
    agentic_dir: Path,
) -> tuple[list[dict[str, Any]], int, int]:
    traces = []
    if isinstance(trace_session, Mapping):
        traces = [
            trace
            for trace in trace_session.get("traces", []) or []
            if isinstance(trace, Mapping)
        ]
    fingerprints: list[dict[str, Any]] = []
    prompt_ref_count = 0
    prompt_loaded_count = 0
    for index, trace in enumerate(traces):
        prompt_ref = _clean_str(
            trace.get("prompt_manifest_artifact_ref")
            or trace.get("prompt_manifest_ref")
            or trace.get("prompt_manifest")
        )
        if not prompt_ref and len(session_prompt_refs) == len(traces):
            prompt_ref = session_prompt_refs[index]
        elif not prompt_ref and len(session_prompt_refs) == 1:
            prompt_ref = session_prompt_refs[0]
        if prompt_ref:
            prompt_ref_count += 1
        prompt_manifest = _load_prompt_manifest(
            prompt_ref,
            campaign_dir=campaign_dir,
            agentic_dir=agentic_dir,
        )
        if prompt_manifest:
            prompt_loaded_count += 1
        prompt_hash = _clean_str(
            trace.get("prompt_hash") or prompt_manifest.get("prompt_hash")
        )
        visibility_digest = _clean_str(
            trace.get("prompt_visibility_ledger_digest")
            or trace.get("visibility_ledger_digest")
            or _mapping(prompt_manifest.get("visibility_ledger_summary")).get(
                "ledger_digest"
            )
        )
        fingerprints.append(
            _drop_empty(
                {
                    "trace_id": _clean_str(trace.get("trace_id")),
                    "call_kind": _clean_str(
                        trace.get("call_kind") or trace.get("request_kind")
                    ),
                    "phase": _clean_str(trace.get("phase")),
                    "prompt_hash": prompt_hash,
                    "prompt_manifest_ref": prompt_ref,
                    "proposal_context_ablation": _prompt_manifest_ablation(
                        prompt_manifest
                    ),
                    "visibility_ledger_digest": visibility_digest,
                    "block_family_summary": _prompt_block_family_summary(
                        prompt_manifest
                    ),
                    "source_visibility_summary": _prompt_source_visibility_summary(
                        prompt_manifest
                    ),
                    "omitted_sections": _string_list(
                        prompt_manifest.get("omitted_sections")
                    ),
                    "truncated_sections": _string_list(
                        prompt_manifest.get("truncated_sections")
                    ),
                }
            )
        )
    return fingerprints, prompt_ref_count, prompt_loaded_count


def _prompt_manifest_ablation(prompt_manifest: Mapping[str, Any]) -> str:
    metadata = _mapping(prompt_manifest.get("context_profile_metadata"))
    return _clean_str(metadata.get("proposal_context_ablation"))


def _prompt_block_family_summary(prompt_manifest: Mapping[str, Any]) -> dict[str, Any]:
    if not prompt_manifest:
        return {}
    accounting = _mapping(prompt_manifest.get("block_family_accounting"))
    char_budget = _mapping(prompt_manifest.get("char_budget"))
    token_accounting = _mapping(prompt_manifest.get("token_accounting"))
    families = _mapping(accounting.get("families") or char_budget.get("block_families"))
    compact_families: dict[str, dict[str, Any]] = {}
    for family, raw in sorted(families.items()):
        if not isinstance(raw, Mapping):
            continue
        compact_families[str(family)] = _drop_empty(
            {
                "char_count": _int_or_none(raw.get("char_count")),
                "token_estimate": _int_or_none(raw.get("token_estimate")),
                "token_share": _float_or_none(raw.get("token_share")),
            }
        )
    return _drop_empty(
        {
            "total_chars": _int_or_none(
                accounting.get("total_chars") or char_budget.get("total_chars")
            ),
            "total_token_estimate": _int_or_none(
                accounting.get("total_token_estimate")
                or token_accounting.get("provider_visible_token_estimate")
            ),
            "families": compact_families,
        }
    )


def _prompt_source_visibility_summary(
    prompt_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    if not prompt_manifest:
        return {}
    code_guarantees = _mapping(
        prompt_manifest.get("code_phase_source_guarantees")
    )
    if not code_guarantees:
        code_guarantees = _mapping(
            _mapping(prompt_manifest.get("code_file_visibility_ledger")).get(
                "source_visibility_guarantees"
            )
        )
    code_ledger = _mapping(prompt_manifest.get("code_file_visibility_ledger"))
    hypothesis_ledger = _mapping(
        prompt_manifest.get("hypothesis_target_source_visibility_ledger")
    )
    return _drop_empty(
        {
            "schema_version": "scion.prompt_source_visibility_fingerprint.v1",
            "code_phase_guarantees": _compact_code_phase_guarantees(
                code_guarantees
            ),
            "code_file_visibility": _compact_code_file_visibility(code_ledger),
            "hypothesis_target_source_visibility": (
                _compact_hypothesis_target_source_visibility(hypothesis_ledger)
            ),
        }
    )


def _compact_code_phase_guarantees(
    guarantees: Mapping[str, Any],
) -> dict[str, Any]:
    if not guarantees:
        return {}
    return _drop_empty(
        {
            "schema_version": guarantees.get("schema_version"),
            "target_source_visible": _bool_or_none(
                guarantees.get("target_source_visible")
            ),
            "required_integration_source_visible": _bool_or_none(
                guarantees.get("required_integration_source_visible")
            ),
            "algorithm_file_read_source_visible": _bool_or_none(
                guarantees.get("algorithm_file_read_source_visible")
            ),
            "protected_source_visible": _bool_or_none(
                guarantees.get("protected_source_visible")
            ),
            "target_file_create_mode": _bool_or_none(
                guarantees.get("target_file_create_mode")
            ),
            "required_integration_source_count": _int_or_none(
                guarantees.get("required_integration_source_count")
            ),
            "algorithm_file_read_source_count": _int_or_none(
                guarantees.get("algorithm_file_read_source_count")
            ),
            "missing_required_source_paths": _string_list(
                guarantees.get("missing_required_source_paths")
            ),
            "duplicate_target_paths_satisfied_by_target_source": _string_list(
                guarantees.get("duplicate_target_paths_satisfied_by_target_source")
            ),
        }
    )


def _compact_code_file_visibility(
    ledger: Mapping[str, Any],
) -> dict[str, Any]:
    if not ledger:
        return {}
    target = _mapping(ledger.get("target_file"))
    integration_files = [
        item
        for item in ledger.get("integration_files") or []
        if isinstance(item, Mapping)
    ]
    algorithm_reads = [
        item
        for item in ledger.get("algorithm_file_reads") or []
        if isinstance(item, Mapping)
    ]
    visible_integration = sum(
        1
        for item in integration_files
        if item.get("full_content_visible_in_rendered_prompt") is True
    )
    visible_algorithm_reads = sum(
        1
        for item in algorithm_reads
        if item.get("full_content_visible_in_rendered_prompt") is True
    )
    return _drop_empty(
        {
            "schema_version": ledger.get("schema_version"),
            "target_visibility_status": target.get("visibility_status"),
            "target_prompt_visibility_status": target.get(
                "prompt_visibility_status"
            ),
            "target_source_status": target.get("source_status"),
            "target_source_provenance": target.get("source_provenance"),
            "target_full_content_visible": _bool_or_none(
                target.get("full_content_visible_in_rendered_prompt")
            ),
            "integration_file_count": len(integration_files),
            "integration_files_full_content_visible_count": visible_integration,
            "algorithm_file_read_count": len(algorithm_reads),
            "algorithm_file_reads_full_content_visible_count": (
                visible_algorithm_reads
            ),
        }
    )


def _compact_hypothesis_target_source_visibility(
    ledger: Mapping[str, Any],
) -> dict[str, Any]:
    if not ledger:
        return {}
    owner_source = _mapping(ledger.get("owner_source"))
    placeholder = _mapping(ledger.get("placeholder"))
    return _drop_empty(
        {
            "schema_version": ledger.get("schema_version"),
            "target_source_required": _bool_or_none(
                ledger.get("target_source_required")
            ),
            "visibility_status": ledger.get("visibility_status"),
            "preflight_section_status": ledger.get("preflight_section_status"),
            "owner_source_visible": _bool_or_none(
                owner_source.get("full_content_visible_in_dedicated_source_section")
                or owner_source.get("content_preview_visible_in_rendered_prompt")
                or owner_source.get("full_content_visible_in_rendered_prompt")
            ),
            "placeholder_visible": _bool_or_none(placeholder.get("visible")),
        }
    )


def _session_join_hints(
    items: list[Mapping[str, Any]],
    *,
    trace_by_session: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    has_code_by_session: dict[str, bool] = {}
    branch_code_totals: Counter[str] = Counter()
    for item in items:
        session_id = _clean_str(item.get("session_id"))
        branch_id = _clean_str(item.get("branch_id"))
        trace_session = trace_by_session.get(session_id)
        has_code = _trace_session_has_code(trace_session)
        has_code_by_session[session_id] = has_code
        if session_id and branch_id and has_code:
            branch_code_totals[branch_id] += 1

    branch_code_seen: Counter[str] = Counter()
    hints: dict[str, dict[str, Any]] = {}
    for item in items:
        session_id = _clean_str(item.get("session_id"))
        branch_id = _clean_str(item.get("branch_id"))
        if not session_id:
            continue
        has_code = bool(has_code_by_session.get(session_id))
        payload: dict[str, Any] = {"has_code_trace": has_code}
        if branch_id and has_code:
            branch_code_seen[branch_id] += 1
            payload["branch_code_ordinal"] = branch_code_seen[branch_id]
            payload["branch_code_session_count"] = branch_code_totals[branch_id]
        hints[session_id] = payload
    return hints


def _trace_session_has_code(trace_session: Mapping[str, Any] | None) -> bool:
    if not isinstance(trace_session, Mapping):
        return False
    for trace in trace_session.get("traces", []) or []:
        if not isinstance(trace, Mapping):
            continue
        if _clean_str(trace.get("call_kind") or trace.get("request_kind")) == "code":
            return True
    return False


class _FormalCandidateJoinIndex:
    def __init__(self, rows: list[Mapping[str, Any]]) -> None:
        self.rows = rows
        self.replayable_rows = [
            row for row in rows if _is_replayable_formal_candidate_row(row)
        ]
        self.logical_rows = _logical_formal_candidate_rows(self.replayable_rows)
        self.join_basis_counts: Counter[str] = Counter()
        self._by_session = _index_unique(self.logical_rows, "session_id")
        self._by_request = _index_unique(self.logical_rows, "request_id")
        self._by_branch_hypothesis = _index_unique_composite(
            self.logical_rows,
            ("branch_id", "hypothesis_id"),
        )
        self._by_branch_order = _index_ordered(self.logical_rows, "branch_id")

    def match_session(self, session: Mapping[str, str]) -> dict[str, str]:
        match: Mapping[str, Any] | None = None
        basis = ""
        for candidate_basis, key, index in (
            ("session_id", session.get("session_id"), self._by_session),
            ("request_id", session.get("request_id"), self._by_request),
            (
                "branch_id+hypothesis_id",
                _composite_key(
                    (session.get("branch_id"), session.get("hypothesis_id"))
                ),
                self._by_branch_hypothesis,
            ),
        ):
            if not key:
                continue
            match = index.get(str(key))
            if match is not None:
                basis = candidate_basis
                break
        if match is None:
            branch_id = _clean_str(session.get("branch_id"))
            branch_rows = self._by_branch_order.get(branch_id, [])
            code_ordinal = _int_or_zero(session.get("branch_code_ordinal"))
            code_session_count = _int_or_zero(session.get("branch_code_session_count"))
            if (
                _bool_str(session.get("has_code_trace"))
                and branch_rows
                and code_ordinal
                and code_session_count == len(branch_rows)
                and code_ordinal <= len(branch_rows)
            ):
                match = branch_rows[code_ordinal - 1]
                basis = "branch_code_sequence"
        if not match:
            return {"join_status": "missing_formal_candidate_join"}
        self.join_basis_counts[basis] += 1
        return {
            "candidate_id": _clean_str(match.get("candidate_id")),
            "artifact_ref": _clean_str(match.get("artifact_ref")),
            "patch_digest": _clean_str(
                match.get("patch_digest") or match.get("patch_hash")
            ),
            "join_basis": basis,
        }


def _is_replayable_formal_candidate_row(row: Mapping[str, Any]) -> bool:
    missing = row.get("missing_replay_identity_keys")
    if isinstance(missing, list) and missing:
        return False
    return (
        _clean_str(row.get("artifact_status")) == "recorded"
        and _clean_str(row.get("replay_identity_status")) == "complete"
    )


def _logical_formal_candidate_rows(
    rows: list[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    grouped: dict[str, tuple[Mapping[str, Any], int]] = {}
    order: list[str] = []
    for row_index, row in enumerate(rows):
        key = _formal_candidate_logical_key(row, row_index)
        if not key:
            continue
        existing = grouped.get(key)
        if existing is None:
            order.append(key)
            grouped[key] = (row, row_index)
            continue
        if _formal_candidate_preference_key(
            row,
            row_index,
        ) > _formal_candidate_preference_key(*existing):
            grouped[key] = (row, row_index)
    return [grouped[key][0] for key in order]


def _formal_candidate_logical_key(row: Mapping[str, Any], row_index: int) -> str:
    branch_id = _clean_str(row.get("branch_id"))
    if not branch_id:
        return ""
    for key in ("session_id", "request_id", "hypothesis_id", "candidate_id"):
        value = _clean_str(row.get(key))
        if value:
            return _composite_key((branch_id, key, value))
    return _composite_key((branch_id, "row", str(row_index)))


def _formal_candidate_preference_key(
    row: Mapping[str, Any],
    row_index: int,
) -> tuple[int, int, int, int]:
    return (
        1 if _string_list(row.get("activation_files")) else 0,
        len(_string_list(row.get("target_files"))),
        len(_string_list(row.get("proposal_target_files"))),
        -row_index,
    )


def _read_session_index(index_path: Path) -> tuple[list[Mapping[str, Any]], str]:
    if not index_path.exists():
        return [], "missing"
    raw = _read_json(index_path)
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, Mapping)], "available"
    if isinstance(raw, Mapping):
        for key in ("sessions", "entries"):
            values = raw.get(key)
            if isinstance(values, list):
                return [item for item in values if isinstance(item, Mapping)], "available"
    raise ValueError(f"agentic session index has unsupported shape: {index_path}")


def _read_trace_index(index_path: Path) -> tuple[list[Mapping[str, Any]], str]:
    if not index_path.exists():
        return [], "missing"
    raw = _read_json(index_path)
    if isinstance(raw, Mapping):
        sessions = raw.get("sessions")
        if isinstance(sessions, list):
            return [item for item in sessions if isinstance(item, Mapping)], "available"
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, Mapping)], "available"
    raise ValueError(f"agentic session trace index has unsupported shape: {index_path}")


def _read_formal_candidate_index(
    index_path: Path,
) -> tuple[list[Mapping[str, Any]], str]:
    if not index_path.exists():
        return [], "missing"
    rows: list[Mapping[str, Any]] = []
    with index_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSON in formal candidate index line {line_number}"
                ) from exc
            if not isinstance(row, Mapping):
                raise ValueError(
                    f"formal candidate index line {line_number} is not an object"
                )
            rows.append(row)
    return rows, "available"


def _load_prompt_manifest(
    ref: str,
    *,
    campaign_dir: Path,
    agentic_dir: Path,
) -> Mapping[str, Any]:
    path = _resolve_artifact_ref(ref, campaign_dir=campaign_dir, agentic_dir=agentic_dir)
    if path is None or not path.exists():
        return {}
    raw = _read_json(path)
    return raw if isinstance(raw, Mapping) else {}


def _resolve_artifact_ref(
    ref: str,
    *,
    campaign_dir: Path,
    agentic_dir: Path,
) -> Path | None:
    text = _clean_str(ref)
    if not text:
        return None
    path_text = text.split("#", 1)[0]
    raw_path = Path(path_text)
    candidates = [raw_path] if raw_path.is_absolute() else [
        campaign_dir / raw_path,
        agentic_dir / raw_path,
    ]
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if _is_relative_to(resolved, campaign_dir) and resolved.exists():
            return resolved
    return None


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON artifact: {path}") from exc


def _load_manifest(value: str | Path | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    raw = _read_json(Path(value).expanduser().resolve())
    if not isinstance(raw, Mapping):
        raise ValueError(f"manifest must be a JSON object: {value}")
    return raw


def _validate_manifest(manifest: Mapping[str, Any], *, side: str) -> None:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"{side} manifest schema_version must be {SCHEMA_VERSION}")
    for key, expected in _GUARDRAILS.items():
        if manifest.get(key) is not expected:
            raise ValueError(f"{side} manifest guardrail mismatch: {key}")
    _manifest_control_pair_key(manifest, side=side)


def _call_kind_counts(sessions: list[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for session in sessions:
        for trace in session.get("trace_fingerprints", []) or []:
            if isinstance(trace, Mapping):
                key = _clean_str(trace.get("call_kind")) or "unknown"
                counts[key] += 1
    return dict(sorted(counts.items()))


def _proposal_distributions(sessions: list[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    selected_surface: Counter[str] = Counter()
    action: Counter[str] = Counter()
    target_file: Counter[str] = Counter()
    mechanism_id: Counter[str] = Counter()
    for session in sessions:
        proposal = _mapping(session.get("proposal_fingerprint"))
        selected_surface[_clean_str(proposal.get("selected_surface")) or "unknown"] += 1
        action[_clean_str(proposal.get("action")) or "unknown"] += 1
        target_file[_clean_str(proposal.get("target_file")) or "unknown"] += 1
        for mechanism in _string_list(proposal.get("mechanism_ids")):
            mechanism_id[mechanism] += 1
    return {
        "selected_surface": dict(sorted(selected_surface.items())),
        "action": dict(sorted(action.items())),
        "target_file": dict(sorted(target_file.items())),
        "mechanism_id": dict(sorted(mechanism_id.items())),
    }


def _context_arm_fingerprint(sessions: list[Mapping[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    unknown_trace_count = 0
    for session in sessions:
        for trace in session.get("trace_fingerprints", []) or []:
            if not isinstance(trace, Mapping):
                continue
            arm = _clean_str(trace.get("proposal_context_ablation"))
            if arm:
                counts[arm] += 1
            else:
                unknown_trace_count += 1
    known_trace_count = sum(counts.values())
    dominant = ""
    mixed = len(counts) > 1
    if len(counts) == 1:
        dominant = next(iter(counts))
    elif mixed:
        dominant = "mixed"
    elif unknown_trace_count:
        dominant = "unknown"
    return {
        "source": "prompt_manifest.context_profile_metadata.proposal_context_ablation",
        "proposal_context_ablation": dominant,
        "proposal_context_ablation_counts": dict(sorted(counts.items())),
        "known_trace_count": known_trace_count,
        "unknown_trace_count": unknown_trace_count,
        "mixed": mixed,
    }


def _block_family_aggregate(sessions: list[Mapping[str, Any]]) -> dict[str, Any]:
    family_chars: Counter[str] = Counter()
    family_tokens: Counter[str] = Counter()
    total_chars = 0
    total_tokens = 0
    for session in sessions:
        for trace in session.get("trace_fingerprints", []) or []:
            if not isinstance(trace, Mapping):
                continue
            summary = _mapping(trace.get("block_family_summary"))
            total_chars += _int_or_zero(summary.get("total_chars"))
            total_tokens += _int_or_zero(summary.get("total_token_estimate"))
            families = _mapping(summary.get("families"))
            for family, raw in families.items():
                if not isinstance(raw, Mapping):
                    continue
                family_chars[str(family)] += _int_or_zero(raw.get("char_count"))
                family_tokens[str(family)] += _int_or_zero(raw.get("token_estimate"))
    family_payload: dict[str, dict[str, Any]] = {}
    for family in sorted(set(family_chars) | set(family_tokens)):
        token_estimate = family_tokens[family]
        char_count = family_chars[family]
        family_payload[family] = {
            "char_count": char_count,
            "token_estimate": token_estimate,
            "token_share": (
                round(token_estimate / total_tokens, 6) if total_tokens else 0.0
            ),
        }
    return {
        "total_chars": total_chars,
        "total_token_estimate": total_tokens,
        "families": family_payload,
    }


def _branch_lesson_usage_accounting(
    sessions: list[Mapping[str, Any]],
) -> dict[str, Any]:
    field_counts: Counter[str] = Counter()
    projection_digest_counts: Counter[str] = Counter()
    prompt_visibility_counts: Counter[str] = Counter()
    usage_present_count = 0
    semantic_projection_present_count = 0
    unrecognized_usage_present_count = 0
    clean_fork_diversity_claim_present_count = 0
    item_count = 0

    for session in sessions:
        usage = _mapping(session.get("branch_lesson_usage_fingerprint"))
        if usage:
            usage_present_count += 1
            semantic_projection_present_count += int(
                bool(usage.get("semantic_projection_present"))
            )
            unrecognized_usage_present_count += int(
                bool(usage.get("unrecognized_usage_present"))
            )
            clean_fork_diversity_claim_present_count += int(
                bool(usage.get("clean_fork_diversity_claim_present"))
            )
            item_count += _int_or_zero(usage.get("item_count"))
            digest = _clean_str(usage.get("projection_digest"))
            if digest:
                projection_digest_counts[digest] += 1
            for field, count in _mapping(usage.get("field_counts")).items():
                field_counts[str(field)] += _int_or_zero(count)

        for trace in session.get("trace_fingerprints", []) or []:
            if not isinstance(trace, Mapping):
                continue
            truncated = _branch_lesson_prompt_sections(
                trace.get("truncated_sections")
            )
            omitted = _branch_lesson_prompt_sections(trace.get("omitted_sections"))
            if truncated:
                prompt_visibility_counts[
                    "branch_lesson_context_truncated_trace_count"
                ] += 1
                prompt_visibility_counts[
                    "branch_lesson_context_truncated_section_count"
                ] += len(truncated)
            if omitted:
                prompt_visibility_counts[
                    "branch_lesson_context_omitted_trace_count"
                ] += 1
                prompt_visibility_counts[
                    "branch_lesson_context_omitted_section_count"
                ] += len(omitted)

    return {
        "schema_version": BRANCH_LESSON_USAGE_ACCOUNTING_SCHEMA,
        "report_only": True,
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "session_count": len(sessions),
        "usage_present_count": usage_present_count,
        "usage_missing_count": len(sessions) - usage_present_count,
        "semantic_projection_present_count": semantic_projection_present_count,
        "unrecognized_usage_present_count": unrecognized_usage_present_count,
        "clean_fork_diversity_claim_present_count": (
            clean_fork_diversity_claim_present_count
        ),
        "item_count": item_count,
        "field_counts": dict(sorted(field_counts.items())),
        "projection_digest_counts": dict(sorted(projection_digest_counts.items())),
        "prompt_visibility_counts": dict(sorted(prompt_visibility_counts.items())),
    }


def _branch_lesson_prompt_sections(value: Any) -> list[str]:
    return [
        section
        for section in _string_list(value)
        if _is_branch_lesson_prompt_section(section)
    ]


def _is_branch_lesson_prompt_section(value: Any) -> bool:
    lowered = _clean_str(value).lower()
    return "branch_lesson" in lowered or "branch lesson" in lowered


def _branch_lesson_usage_numeric_summary(
    manifest: Mapping[str, Any],
) -> dict[str, int]:
    accounting = _mapping(manifest.get("branch_lesson_usage_accounting"))
    prompt_counts = _mapping(accounting.get("prompt_visibility_counts"))
    field_counts = _mapping(accounting.get("field_counts"))
    numeric: dict[str, int] = {
        key: _int_or_zero(accounting.get(key))
        for key in (
            "session_count",
            "usage_present_count",
            "usage_missing_count",
            "semantic_projection_present_count",
            "unrecognized_usage_present_count",
            "clean_fork_diversity_claim_present_count",
            "item_count",
        )
    }
    for key, value in prompt_counts.items():
        numeric[str(key)] = _int_or_zero(value)
    for key, value in field_counts.items():
        numeric[f"{key}_count"] = _int_or_zero(value)
    return numeric


def _manifest_count_summary(manifest: Mapping[str, Any]) -> dict[str, int]:
    counts = _mapping(manifest.get("counts"))
    return {
        "session_count": _int_or_zero(counts.get("session_count")),
        "trace_count": _int_or_zero(counts.get("trace_count")),
        "formal_candidate_count": _int_or_zero(counts.get("formal_candidate_count")),
    }


def _count_delta(
    left_manifest: Mapping[str, Any],
    right_manifest: Mapping[str, Any],
) -> dict[str, int]:
    left = _manifest_count_summary(left_manifest)
    right = _manifest_count_summary(right_manifest)
    return {key: right[key] - left[key] for key in sorted(left)}


def _paired_counter_summary(left: Any, right: Any) -> dict[str, dict[str, int]]:
    left_counts = {str(key): _int_or_zero(value) for key, value in _mapping(left).items()}
    right_counts = {
        str(key): _int_or_zero(value) for key, value in _mapping(right).items()
    }
    keys = sorted(set(left_counts) | set(right_counts))
    return {
        "left": {key: left_counts.get(key, 0) for key in keys},
        "right": {key: right_counts.get(key, 0) for key in keys},
        "delta": {
            key: right_counts.get(key, 0) - left_counts.get(key, 0) for key in keys
        },
    }


def _paired_family_share_summary(left: Any, right: Any) -> dict[str, Any]:
    left_families = _mapping(_mapping(left).get("families"))
    right_families = _mapping(_mapping(right).get("families"))
    keys = sorted(set(left_families) | set(right_families))
    by_family: dict[str, dict[str, float]] = {}
    for family in keys:
        left_share = _float_or_zero(_mapping(left_families.get(family)).get("token_share"))
        right_share = _float_or_zero(
            _mapping(right_families.get(family)).get("token_share")
        )
        by_family[family] = {
            "left": left_share,
            "right": right_share,
            "delta": round(right_share - left_share, 6),
        }
    return {
        "left_total_token_estimate": _int_or_zero(
            _mapping(left).get("total_token_estimate")
        ),
        "right_total_token_estimate": _int_or_zero(
            _mapping(right).get("total_token_estimate")
        ),
        "families": by_family,
    }


def _coverage_summary(manifest: Mapping[str, Any]) -> dict[str, int]:
    coverage = _mapping(manifest.get("coverage"))
    return {
        "sessions_with_traces": _int_or_zero(coverage.get("sessions_with_traces")),
        "sessions_with_formal_candidate": _int_or_zero(
            coverage.get("sessions_with_formal_candidate")
        ),
        "missing_join_count": _int_or_zero(coverage.get("missing_join_count")),
    }


def _missing_joins(manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    coverage = _mapping(manifest.get("coverage"))
    joins = coverage.get("missing_joins")
    if not isinstance(joins, list):
        return []
    return [item for item in joins if isinstance(item, Mapping)]


def _mapping_at(manifest: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    current: Any = manifest
    for key in keys:
        current = _mapping(current).get(key)
    return _mapping(current)


def _index_unique(
    rows: list[Mapping[str, Any]],
    key: str,
) -> dict[str, Mapping[str, Any]]:
    values: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        row_key = _clean_str(row.get(key))
        if not row_key:
            continue
        values.setdefault(row_key, []).append(row)
    return {row_key: items[0] for row_key, items in values.items() if len(items) == 1}


def _index_ordered(
    rows: list[Mapping[str, Any]],
    key: str,
) -> dict[str, list[Mapping[str, Any]]]:
    values: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        row_key = _clean_str(row.get(key))
        if row_key:
            values.setdefault(row_key, []).append(row)
    return values


def _index_unique_composite(
    rows: list[Mapping[str, Any]],
    keys: tuple[str, ...],
) -> dict[str, Mapping[str, Any]]:
    values: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        row_key = _composite_key(tuple(row.get(key) for key in keys))
        if not row_key:
            continue
        values.setdefault(row_key, []).append(row)
    return {row_key: items[0] for row_key, items in values.items() if len(items) == 1}


def _composite_key(values: Iterable[Any]) -> str:
    parts = [_clean_str(value) for value in values]
    if not all(parts):
        return ""
    return "\x1f".join(parts)


def _prompt_manifest_refs(item: Mapping[str, Any]) -> list[str]:
    refs = _string_list(
        item.get("prompt_manifest_artifact_refs") or item.get("prompt_manifest_refs")
    )
    single = _clean_str(item.get("prompt_manifest_artifact_ref"))
    if single and single not in refs:
        refs.append(single)
    return refs


def _session_sort_key(item: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        _clean_str(item.get("created_at") or item.get("updated_at")),
        _clean_str(item.get("branch_id")),
        _clean_str(item.get("session_id")),
    )


def _stable_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _text_digest(value: Any) -> str:
    text = _clean_str(value)
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _manifest_control_pair_key(manifest: Mapping[str, Any], *, side: str) -> str:
    if "control_pair_key" not in manifest or manifest.get("control_pair_key") == "":
        return ""
    try:
        return _sanitize_control_pair_key(manifest.get("control_pair_key"))
    except ValueError as exc:
        raise ValueError(f"{side} manifest {exc}") from exc


def _sanitize_control_pair_key(value: Any) -> str:
    if value is None:
        return ""
    key = str(value).strip()
    if not key:
        raise ValueError("control_pair_key must be non-empty after trimming")
    if len(key) > 128:
        raise ValueError("control_pair_key must be at most 128 characters")
    if not _CONTROL_PAIR_KEY_RE.fullmatch(key):
        raise ValueError(
            "control_pair_key must contain only [A-Za-z0-9._:-] characters"
        )
    return key


def _clean_str(value: Any) -> str:
    return str(value or "").strip()


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        values: Iterable[Any] = [value]
    elif isinstance(value, Iterable) and not isinstance(value, Mapping):
        values = value
    else:
        values = []
    compact: list[str] = []
    for item in values:
        text = _clean_str(item)
        if text and text not in compact:
            compact.append(text)
    return compact


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _drop_empty(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in payload.items()
        if value not in (None, "", (), [], {})
    }


def _int_or_none(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: Any) -> int:
    result = _int_or_none(value)
    return result if result is not None else 0


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _float_or_none(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def _float_or_zero(value: Any) -> float:
    result = _float_or_none(value)
    return result if result is not None else 0.0


def _bool_str(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _clean_str(value).lower() in {"1", "true", "yes", "on"}


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "COMPARISON_SCHEMA_VERSION",
    "DEFAULT_COMPARISON_FILENAME",
    "DEFAULT_MANIFEST_FILENAME",
    "SCHEMA_VERSION",
    "build_proposal_trajectory_comparison",
    "build_proposal_trajectory_manifest",
    "write_proposal_trajectory_comparison",
    "write_proposal_trajectory_manifest",
]
