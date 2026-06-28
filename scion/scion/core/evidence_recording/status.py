"""Status payload writer for campaign evidence recording."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping

from scion.core.branch_cards import active_slot_inventory_from_branch_cards
from scion.core.branch_hygiene import campaign_remaining_branch_classification
from scion.core.public_refs import redact_public_refs
from scion.core.research_process_guidance_audit import (
    extract_research_process_guidance_audit,
)
from scion.core.run_validity import apply_run_completion_aliases, build_run_validity
from scion.core.screening_visibility import (
    observability_value_visibility_from_payload,
    runtime_gate_visibility_summary,
    runtime_evidence_policy_summary,
)
from scion.core.status_reporter import normalize_status_payload, normalize_stopped_reason

from .accounting import (
    accounting_reconciliation_fields,
    proposal_accounting_fields,
)
from .artifact_refs import _in_flight_protocol_snapshot, _read_partial_metrics_snapshot
from .common import reduced_measurement_readiness_payload
from .cross_branch_observability import build_cross_branch_research_observability
from .lineage import apply_lineage_integrity_to_run_validity

logger = logging.getLogger(__name__)

_BRANCH_LESSON_USAGE_STEP_COUNTER_FIELDS = (
    "branch_lesson_usage_present_count",
    "branch_lesson_usage_satisfied_count",
    "branch_lesson_usage_missing_block_count",
    "borrowed_lesson_count",
    "avoided_lesson_count",
    "contrasted_lesson_count",
    "preserved_same_branch_lesson_count",
    "clean_fork_contrast_satisfied_count",
    "weak_positive_transfer_count",
)

_PROTOCOL_STAGE_SCOPED_FIELDS = (
    "complete",
    "total_pairs",
    "attempted_pairs",
    "completed_pairs",
    "valid_pairs",
    "failed_pairs",
    "candidate_failed_pairs",
    "champion_failed_pairs",
    "raw_metrics_ref",
    "raw_metrics_ref_scope",
    "raw_metrics_internal_only",
    "child_pid",
    "child_exit_code",
    "child_elapsed_ms",
    "child_phase",
    "case",
    "seed",
    "selected_surface",
    "runtime_confidence",
    "runtime_evidence_status",
    "runtime_evidence_policy",
    "runtime_gate_visibility",
    "champion_cached_runtime_pairs",
    "runtime_budget_diagnostic",
    "runtime_budget_diagnostic_code",
    "observability_value_visibility",
)


def _normalize_child_process_fields(
    progress: Dict[str, Any], payload: Mapping[str, Any]
) -> None:
    """Keep child process lifecycle fields internally consistent.

    Progress updates are merged across long protocol stages. A subprocess start
    and completion can be separated by other stage updates, so stale child
    fields must not be allowed to survive that merge and make ``status.json``
    report a dead process as still running.
    """

    if payload.get("child_pid") is not None:
        progress.pop("child_exit_code", None)
        progress.pop("child_elapsed_ms", None)
        progress["child_phase"] = payload.get("child_phase") or "solver_subprocess"
        return

    if "child_pid" in payload:
        progress.pop("child_pid", None)

    has_terminal_child_update = (
        "child_exit_code" in payload
        or "child_elapsed_ms" in payload
        or progress.get("child_exit_code") is not None
        or progress.get("child_elapsed_ms") is not None
    )
    if has_terminal_child_update:
        progress.pop("child_pid", None)
        if not progress.get("child_phase") or progress.get("child_phase") == (
            "solver_subprocess"
        ):
            progress["child_phase"] = "solver_subprocess_complete"

    if progress.get("complete") is True:
        progress.pop("child_pid", None)
        if progress.get("child_phase") == "solver_subprocess":
            progress["child_phase"] = "solver_subprocess_complete"


def _ensure_running_protocol_fields(progress: Dict[str, Any]) -> None:
    """Expose in-flight protocol state without changing completed counters."""

    if progress.get("complete") is True:
        progress["protocol_state"] = "complete"
    elif progress.get("stage") or progress.get("phase") or progress.get("child_pid"):
        progress.setdefault("complete", False)
        progress["protocol_state"] = "running"
        progress.setdefault("attempted_pairs", 0)


def _sync_protocol_progress_aliases(progress: Dict[str, Any]) -> None:
    """Mirror redacted protocol fields under human-readable stable names."""

    if progress.get("case") is not None:
        progress["last_case"] = progress.get("case")
    if progress.get("seed") is not None:
        progress["last_seed"] = progress.get("seed")


def _merge_campaign_loop_observability(payload: Dict[str, Any]) -> None:
    """Mirror stable loop accounting fields at the status top level."""
    loop = payload.get("campaign_loop")
    if not isinstance(loop, Mapping):
        return

    aliases = {
        "requested_rounds": "requested_rounds",
        "total_rounds": "total_rounds",
        "proposal_attempts": "proposal_attempts",
        "proposal_attempts_consumed": "proposal_attempts_consumed",
        "proposal_attempts_total": "proposal_attempts_total",
        "proposal_attempts_total_semantics": "proposal_attempts_total_semantics",
        "effective_rounds_completed": "effective_rounds_completed",
        "effective_rounds_completed_semantics": (
            "effective_rounds_completed_semantics"
        ),
        "effective_protocol_rounds": "effective_protocol_rounds",
        "effective_protocol_rounds_semantics": (
            "effective_protocol_rounds_semantics"
        ),
        "formal_screened_candidates": "formal_screened_candidates",
        "protocol_evaluated_candidates": "protocol_evaluated_candidates",
        "protocol_metric_results": "protocol_metric_results",
        "screening_protocol_results": "screening_protocol_results",
        "fresh_runtime_replay_protocol_results": (
            "fresh_runtime_replay_protocol_results"
        ),
        "validation_protocol_results": "validation_protocol_results",
        "frozen_protocol_results": "frozen_protocol_results",
        "verification_consumed_candidates": "verification_consumed_candidates",
        "verification_failure_consumed_candidates": (
            "verification_failure_consumed_candidates"
        ),
        "proposal_quality_blocks": "proposal_quality_blocks",
        "protocol_metric_stage_counts": "protocol_metric_stage_counts",
        "protocol_stage_counts": "protocol_stage_counts",
        "max_rounds_budget_counter": "max_rounds_budget_counter",
        "max_rounds_semantics": "max_rounds_semantics",
        "telemetry_repair_attempts": "telemetry_repair_attempts",
        "telemetry_diagnostic_attempts": "telemetry_diagnostic_attempts",
        "branch_lifecycle_policy_blocks": "branch_lifecycle_policy_blocks",
        "reconcile_lifecycle_steps": "reconcile_lifecycle_steps",
        "non_counted_lifecycle_steps": "non_counted_lifecycle_steps",
        "scheduler_active_slot_blocked_attempts": (
            "scheduler_active_slot_blocked_attempts"
        ),
        "active_slot_blocked_attempts": "active_slot_blocked_attempts",
        "scheduler_active_slot_blocked_attempt_limit": (
            "scheduler_active_slot_blocked_attempt_limit"
        ),
        "active_slot_blocked_attempt_limit": "active_slot_blocked_attempt_limit",
        "fresh_runtime_replay_drain": "fresh_runtime_replay_drain",
        "fresh_runtime_replay_drain_status": "fresh_runtime_replay_drain_status",
        "fresh_runtime_replay_drain_attempts": "fresh_runtime_replay_drain_attempts",
        "fresh_runtime_replay_drain_executed": "fresh_runtime_replay_drain_executed",
        "fresh_runtime_replay_drain_skipped": "fresh_runtime_replay_drain_skipped",
        "fresh_runtime_replay_drain_limit": "fresh_runtime_replay_drain_limit",
        "fresh_runtime_replay_drain_stopped_reason": (
            "fresh_runtime_replay_drain_stopped_reason"
        ),
        "fresh_runtime_replay_drain_accepted_replay_last_result": (
            "fresh_runtime_replay_drain_accepted_replay_last_result"
        ),
        "fresh_runtime_replay_drain_final_attempt_last_result": (
            "fresh_runtime_replay_drain_final_attempt_last_result"
        ),
        "fresh_runtime_replay_drain_blocked_count": (
            "fresh_runtime_replay_drain_blocked_count"
        ),
        "fresh_runtime_replay_drain_unresolved_closures": (
            "fresh_runtime_replay_drain_unresolved_closures"
        ),
        "stage_transition_drain": "stage_transition_drain",
        "stage_transition_drain_status": "stage_transition_drain_status",
        "stage_transition_drain_attempts": "stage_transition_drain_attempts",
        "stage_transition_drain_executed": "stage_transition_drain_executed",
        "stage_transition_drain_skipped": "stage_transition_drain_skipped",
        "stage_transition_drain_limit": "stage_transition_drain_limit",
        "stage_transition_drain_stopped_reason": (
            "stage_transition_drain_stopped_reason"
        ),
        "stage_transition_drain_accepted_stage_last_result": (
            "stage_transition_drain_accepted_stage_last_result"
        ),
        "stage_transition_drain_final_attempt_last_result": (
            "stage_transition_drain_final_attempt_last_result"
        ),
        "quality_blocks": "quality_blocks",
        "quality_block_ledger": "quality_block_ledger",
        "quality_block_ledger_count": "quality_block_ledger_count",
        "research_accounting_breakdown": "research_accounting_breakdown",
        "unique_hypotheses": "unique_hypotheses",
        "unique_hypotheses_semantics": "unique_hypotheses_semantics",
        "formal_candidate_artifact_count": "formal_candidate_artifact_count",
        "formal_candidate_artifact_count_semantics": (
            "formal_candidate_artifact_count_semantics"
        ),
        "non_effective_screenings": "non_effective_screenings",
        "non_effective_screening_count": "non_effective_screening_count",
        "blocked_attempts": "blocked_attempts",
        "infra_failure_attempts": "infra_failure_attempts",
        "noninfra_failure_attempts": "noninfra_failure_attempts",
        "loop_steps": "loop_steps",
        "campaign_steps": "campaign_steps",
        "screened_rounds": "screened_rounds",
        "agentic_sessions": "agentic_sessions",
        "agentic_sessions_semantics": "agentic_sessions_semantics",
        "hypothesis_calls": "hypothesis_calls",
        "hypothesis_calls_semantics": "hypothesis_calls_semantics",
        "code_calls": "code_calls",
        "code_calls_semantics": "code_calls_semantics",
        "llm_request_kind_counts": "llm_request_kind_counts",
        "llm_request_kind_counts_semantics": (
            "llm_request_kind_counts_semantics"
        ),
        "llm_model_counts": "llm_model_counts",
        "llm_provider_counts": "llm_provider_counts",
        "llm_token_sums": "llm_token_sums",
        "llm_token_field_availability": "llm_token_field_availability",
        "llm_accounting": "llm_accounting",
        "formal_candidate_count_reconciliation": (
            "formal_candidate_count_reconciliation"
        ),
        "candidate_count_reconciliation": "candidate_count_reconciliation",
    }
    for top_key, loop_key in aliases.items():
        value = loop.get(loop_key)
        if value is None:
            continue
        payload[top_key] = value

    if payload.get("quality_blocks") is None:
        value = loop.get("proposal_quality_blocks_consumed")
        if value is not None:
            payload["quality_blocks"] = value
    if payload.get("blocked_attempts") is None:
        value = payload.get("quality_blocks")
        if value is not None:
            payload["blocked_attempts"] = value
    if isinstance(loop.get("failure_categories"), Mapping):
        payload["failure_categories"] = dict(loop["failure_categories"])


def _merge_runtime_budget_status(
    payload: Dict[str, Any],
    progress: Mapping[str, Any] | None,
) -> None:
    if not isinstance(progress, Mapping):
        return
    diagnostic = progress.get("runtime_budget_diagnostic")
    if isinstance(diagnostic, Mapping):
        payload["runtime_budget_diagnostic"] = dict(diagnostic)
        code = str(
            progress.get("runtime_budget_diagnostic_code")
            or diagnostic.get("code")
            or ""
        ).strip()
        if code:
            payload["runtime_budget_diagnostic_code"] = code


def _ensure_runtime_evidence_policy(progress: Dict[str, Any]) -> None:
    if not _progress_has_runtime_policy_source(progress):
        return
    if isinstance(progress.get("runtime_evidence_policy"), Mapping):
        return
    aggregate_excluded = progress.get("runtime_aggregate_excluded")
    if isinstance(aggregate_excluded, Mapping):
        aggregate_excluded = aggregate_excluded.get("excluded")
    progress["runtime_evidence_policy"] = runtime_evidence_policy_summary(
        runtime_confidence=progress.get("runtime_confidence", ""),
        runtime_evidence_status=progress.get("runtime_evidence_status", ""),
        runtime_pairs=progress.get("runtime_pairs", 0),
        champion_cached_runtime_pairs=progress.get(
            "champion_cached_runtime_pairs",
            0,
        ),
        runtime_aggregate_excluded=bool(aggregate_excluded),
        candidate_runtime_pair_evidence_count=progress.get(
            "candidate_runtime_pair_evidence_count",
            0,
        ),
    )


def _ensure_runtime_gate_visibility(progress: Dict[str, Any]) -> None:
    if not _progress_has_runtime_gate_visibility_source(progress):
        return
    if isinstance(progress.get("runtime_gate_visibility"), Mapping):
        return
    progress["runtime_gate_visibility"] = runtime_gate_visibility_summary(
        stage=progress.get("stage", ""),
        gate_outcome=progress.get("gate_outcome", ""),
        reason_codes=progress.get("reason_codes", ()),
        runtime_confidence=progress.get("runtime_confidence", ""),
        runtime_evidence_status=progress.get("runtime_evidence_status", ""),
        runtime_pairs=progress.get("runtime_pairs", 0),
        champion_cached_runtime_pairs=progress.get(
            "champion_cached_runtime_pairs",
            0,
        ),
        failed_pairs=progress.get("failed_pairs", 0),
        candidate_failed_pairs=progress.get("candidate_failed_pairs", 0),
        champion_failed_pairs=progress.get("champion_failed_pairs", 0),
        runtime_budget_diagnostic=progress.get("runtime_budget_diagnostic"),
    )


def _ensure_observability_value_visibility(progress: Dict[str, Any]) -> None:
    if not _progress_has_observability_value_source(progress):
        return
    visibility = observability_value_visibility_from_payload(progress)
    if visibility:
        progress["observability_value_visibility"] = visibility


def _progress_has_observability_value_source(progress: Mapping[str, Any]) -> bool:
    return any(
        key in progress
        for key in (
            "observability_value_visibility",
            "candidate_intent",
            "attempt_kind",
            "mechanism_evidence",
            "candidate_surface_runtime_summary",
            "candidate_phase_telemetry_summary",
            "telemetry_failure_details",
            "candidate_runtime_failure_categories",
            "candidate_first_runtime_failure",
        )
    )


def _progress_has_runtime_policy_source(progress: Mapping[str, Any]) -> bool:
    return any(
        key in progress
        for key in (
            "runtime_confidence",
            "runtime_evidence_status",
            "runtime_pairs",
            "champion_cached_runtime_pairs",
            "runtime_aggregate_excluded",
            "candidate_runtime_pair_evidence_count",
        )
    )


def _progress_has_runtime_gate_visibility_source(progress: Mapping[str, Any]) -> bool:
    return any(
        key in progress
        for key in (
            "runtime_gate_visibility",
            "gate_outcome",
            "reason_codes",
            "runtime_confidence",
            "runtime_evidence_status",
            "champion_cached_runtime_pairs",
            "runtime_budget_diagnostic",
        )
    )


def _branch_rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = payload.get("branches")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def _branch_cards_from_rows(rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    cards: list[Mapping[str, Any]] = []
    for row in rows:
        card = row.get("branch_card")
        if isinstance(card, Mapping):
            cards.append(card)
    return cards


def _status_scope_reconciliation(
    *,
    payload: Mapping[str, Any],
    branch_rows: list[Mapping[str, Any]],
    last_result: Mapping[str, Any] | None,
    current_progress: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Describe which evidence sources are visible in status.json."""

    last_counts = None
    if isinstance(last_result, Mapping):
        last_counts = bool(last_result.get("counts_toward_max_rounds", True))
    loop = payload.get("campaign_loop")
    loop_mapping = loop if isinstance(loop, Mapping) else {}
    return {
        "schema_version": "evidence_scope_reconciliation.v1",
        "payload": "status",
        "step_history_scope": "not_available",
        "branch_state_scope": "branch_rows_snapshot" if branch_rows else "none",
        "last_result_scope": (
            "last_completed_result_only" if last_result is not None else "none"
        ),
        "protocol_progress_scope": (
            "current_or_in_flight_protocol_progress"
            if current_progress is not None or payload.get("in_flight_protocol")
            else "none"
        ),
        "includes_failed_steps": bool(
            isinstance(last_result, Mapping) and last_result.get("failure_stage")
        ),
        "includes_non_counted_steps": bool(last_counts is False),
        "source_counts": {
            "step_history_total": 0,
            "branch_row_count": len(branch_rows),
            "last_result_count": 1 if last_result is not None else 0,
            "last_result_counts_toward_max_rounds": last_counts,
            "current_progress_count": 1 if current_progress is not None else 0,
            "in_flight_protocol_count": (
                1 if payload.get("in_flight_protocol") else 0
            ),
            "screened_experiments": payload.get(
                "screened_experiments",
                loop_mapping.get("screened_experiments"),
            ),
            "effective_rounds_completed": payload.get(
                "effective_rounds_completed",
                loop_mapping.get("effective_rounds_completed"),
            ),
        },
    }


def _stopped_reason_preserves_partial_in_flight(reason: Any) -> bool:
    text = str(reason or "").strip().lower()
    return text.startswith("signal:") or text in {
        "external_stop_requested",
        "keyboard_interrupt",
    }


def _stopped_progress_is_complete(progress: Mapping[str, Any] | None) -> bool:
    return isinstance(progress, Mapping) and progress.get("complete") is True


def _reconcile_active_slots_from_branch_cards(
    payload: Dict[str, Any],
    branch_rows: list[Mapping[str, Any]],
) -> None:
    existing = payload.get("active_slots")
    existing_slots = dict(existing) if isinstance(existing, Mapping) else {}
    reconciled = active_slot_inventory_from_branch_cards(
        _branch_cards_from_rows(branch_rows),
        max_active_branches=existing_slots.get("max"),
    )
    if reconciled is None:
        return
    payload["active_slots"] = reconciled
    payload["n_active_branches"] = reconciled["used"]


def _sync_branch_progress_from_rows(
    progress: Mapping[str, Any],
    branch_rows: list[Mapping[str, Any]],
) -> Dict[str, Any]:
    branch_id = str(progress.get("branch_id") or "")
    merged = dict(progress)
    if not branch_id:
        return merged
    for row in branch_rows:
        if str(row.get("id") or row.get("branch_id") or "") != branch_id:
            continue
        card = row.get("branch_card")
        if not isinstance(card, Mapping):
            card = row
        merged["branch_card"] = dict(card)
        for key in _BRANCH_PROGRESS_FIELDS:
            if key in card:
                merged[key] = card[key]
        return merged
    return merged


def _sync_in_flight_branch_fields(
    snapshot: Mapping[str, Any],
    progress: Mapping[str, Any] | None,
    branch_rows: list[Mapping[str, Any]],
) -> Dict[str, Any]:
    merged = dict(snapshot)
    source = progress if isinstance(progress, Mapping) else None
    if source is None and merged.get("branch_id"):
        source = _sync_branch_progress_from_rows(merged, branch_rows)
    if not isinstance(source, Mapping):
        return merged
    for key in ("branch_card", *_BRANCH_PROGRESS_FIELDS):
        if key in source:
            merged[key] = source[key]
    return merged


def _status_context_records(
    *values: Mapping[str, Any] | None,
) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    for value in values:
        if not isinstance(value, Mapping):
            continue
        ref = value.get("proposal_session_ref")
        if isinstance(ref, Mapping):
            records.append(ref)
        for key in (
            "branch_lesson_records",
            "branch_lessons",
            "branch_lesson_usage_requirement",
            "cross_branch_research_audit_records",
            "cross_branch_research_payload",
            "cross_branch_research_status",
            "material_difference_audit_records",
            "material_difference_requirement",
        ):
            if key in value:
                records.append(value)
                break
    return records


def _summary_grade_branch_lesson_usage_counters(
    *,
    campaign_dir: Path,
    campaign_id: str,
) -> dict[str, Any] | None:
    summary_path = campaign_dir / "campaign_summary.json"
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(summary, Mapping):
        return None
    if summary.get("campaign_id") not in (None, campaign_id):
        return None
    observability = summary.get("cross_branch_research_observability")
    if not isinstance(observability, Mapping):
        return None
    if observability.get("step_history_scope") in (None, "none"):
        return None
    source_counts = observability.get("source_counts")
    step_history_total = 0
    if isinstance(source_counts, Mapping):
        try:
            step_history_total = int(source_counts.get("step_history_total") or 0)
        except (TypeError, ValueError):
            step_history_total = 0
    if step_history_total <= 0:
        return None

    counters = {
        key: observability[key]
        for key in _BRANCH_LESSON_USAGE_STEP_COUNTER_FIELDS
        if key in observability
    }
    if not counters:
        return None
    counters["branch_lesson_usage_counter_scope"] = "summary_step_history"
    counters["branch_lesson_usage_counter_source"] = "campaign_summary_json"
    counters["branch_lesson_usage_counter_reason"] = (
        "status_step_history_not_available; copied_summary_grade_step_history_counters"
    )
    counters["branch_lesson_usage_step_history_scope"] = observability.get(
        "step_history_scope"
    )
    counters["branch_lesson_usage_summary_step_history_total"] = step_history_total
    return counters


def _mark_branch_lesson_usage_counters_unavailable(
    observability: Dict[str, Any],
) -> None:
    if observability.get("step_history_scope") != "none":
        return
    for key in _BRANCH_LESSON_USAGE_STEP_COUNTER_FIELDS:
        if key in observability:
            observability[key] = None
    observability["branch_lesson_usage_counter_scope"] = "not_available"
    observability["branch_lesson_usage_counter_source"] = "requires_step_history"
    observability["branch_lesson_usage_counter_reason"] = (
        "status_json_does_not_have_step_history; use_campaign_summary_json_when_available"
    )


def _canary_result_payload(
    canary_result: Any,
    *,
    base_dir: str | Path | None,
) -> dict[str, Any]:
    if canary_result is None:
        return {}
    details = getattr(canary_result, "details", None)
    payload: dict[str, Any] = {
        "passed": bool(getattr(canary_result, "passed", False)),
        "reason": getattr(canary_result, "reason", None),
    }
    failure_category = str(getattr(canary_result, "failure_category", "") or "")
    if failure_category:
        payload["failure_category"] = failure_category
    reason_codes = tuple(getattr(canary_result, "reason_codes", ()) or ())
    if reason_codes:
        payload["reason_codes"] = list(reason_codes)
    if isinstance(details, Mapping):
        payload.update(dict(details))
    payload.setdefault("schema_version", "scion.canary_result.v1")
    if not payload.get("raw_metrics_ref"):
        payload["raw_metrics_ref"] = None
        payload.setdefault(
            "raw_metrics_unavailable_reason",
            "canary_veto_before_formal_protocol",
        )
    return redact_public_refs(payload, base_dir=base_dir)


_BRANCH_PROGRESS_FIELDS = (
    "lineage_status",
    "branch_code_status",
    "current_head_status",
    "active_slot_status",
    "counts_toward_active_slots",
    "current_head_active_slot_release_reason",
    "best_checkpoint_status",
    "best_quality_checkpoint_id",
    "last_valid_checkpoint_id",
    "rollback_count",
    "lineage_retained_checkpoint",
    "latest_head_failed",
    "allowed_next_actions",
    "forbidden_next_actions",
    "final_branch_classification",
    "branch_final_classification",
    "branch_next_action",
    "branch_classification_reason",
)


class StatusWriterMixin:
    def write_status(
        self,
        *,
        last_result: Any | None = None,
        stopped_reason: str | None = None,
        loop_status: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Write ``status.json`` using the existing CampaignManager payload shape."""
        payload: Dict[str, Any] = (
            dict(self.state_provider()) if self.state_provider is not None else {}
        )
        if loop_status is not None:
            self.campaign_loop_status = dict(loop_status)
        if self.campaign_loop_status is not None:
            payload["campaign_loop"] = dict(self.campaign_loop_status)
            _merge_campaign_loop_observability(payload)
            accounting = proposal_accounting_fields(
                campaign_dir=self.campaign_dir,
                loop_status=self.campaign_loop_status,
                state=payload,
                screened_rounds=payload.get("screened_experiments"),
            )
            accounting_reconciliation = accounting_reconciliation_fields(
                loop_status=self.campaign_loop_status,
                state=payload,
                screened_rounds=payload.get("screened_experiments"),
                effective_rounds_completed=payload.get(
                    "effective_rounds_completed"
                ),
                campaign_dir=self.campaign_dir,
            )
            payload.update(accounting)
            payload["accounting_reconciliation"] = accounting_reconciliation
            payload["proposal_accounting"] = {
                "proposal_attempts": payload.get("proposal_attempts"),
                "proposal_attempts_consumed": payload.get(
                    "proposal_attempts_consumed"
                ),
                **accounting,
                "accounting_reconciliation": accounting_reconciliation,
            }
        if last_result is not None:
            self.last_status_result = {
                "action": last_result.action,
                "branch_id": last_result.branch_id,
                "decision": (
                    last_result.decision.value
                    if getattr(last_result, "decision", None) is not None
                    else None
                ),
                "stopped": last_result.stopped,
                "reason": last_result.reason,
                "counts_toward_max_rounds": getattr(
                    last_result,
                    "counts_toward_max_rounds",
                    True,
                ),
                "attempt_kind": getattr(last_result, "attempt_kind", "screening"),
                "protocol_stage": getattr(last_result, "protocol_stage", None),
                "formal_protocol_evaluated": bool(
                    getattr(last_result, "formal_protocol_evaluated", False)
                ),
                "screened_experiment_effective": bool(
                    getattr(last_result, "screened_experiment_effective", False)
                ),
                "repair_mechanism_ids": list(
                    getattr(last_result, "repair_mechanism_ids", ()) or ()
                ),
                "repair_policy_reason": getattr(
                    last_result,
                    "repair_policy_reason",
                    "",
                ),
                "decision_layer_source": getattr(
                    last_result,
                    "decision_layer_source",
                    None,
                ),
                "decision_engine_reason_codes": list(
                    getattr(last_result, "decision_engine_reason_codes", ()) or ()
                ),
                "diagnostic_reason_codes": list(
                    getattr(last_result, "diagnostic_reason_codes", ()) or ()
                ),
                "bypass_reason_codes": list(
                    getattr(last_result, "bypass_reason_codes", ()) or ()
                ),
                "lifecycle_reason_codes": list(
                    getattr(last_result, "lifecycle_reason_codes", ()) or ()
                ),
                "lifecycle_bookkeeping": dict(
                    getattr(last_result, "lifecycle_bookkeeping", None) or {}
                ),
                "scheduler_slot": getattr(last_result, "scheduler_slot", ""),
                "scheduler_reason": getattr(last_result, "scheduler_reason", ""),
                "scheduler_audit_metadata": dict(
                    getattr(last_result, "scheduler_audit_metadata", None) or {}
                ),
            }
            proposal_session_ref = getattr(last_result, "proposal_session_ref", None)
            if isinstance(proposal_session_ref, Mapping):
                self.last_status_result["proposal_session_ref"] = dict(
                    proposal_session_ref
                )
            guidance_audit = extract_research_process_guidance_audit(
                getattr(last_result, "scheduler_audit_metadata", None) or {}
            )
            if guidance_audit:
                self.last_status_result["research_process_guidance_audit"] = (
                    guidance_audit
                )
            failure_stage = getattr(last_result, "failure_stage", None)
            failure_category = getattr(last_result, "failure_category", None)
            failure_detail = getattr(last_result, "failure_detail", None)
            if failure_stage:
                self.last_status_result["failure_stage"] = failure_stage
            if failure_category:
                self.last_status_result["failure_category"] = failure_category
            if failure_detail:
                self.last_status_result["failure_detail"] = str(failure_detail)[:1000]
            canary_payload = _canary_result_payload(
                getattr(last_result, "canary_result", None),
                base_dir=self.campaign_dir,
            )
            if canary_payload:
                self.last_status_result["canary_result"] = canary_payload
        if self.last_status_result is not None:
            payload["last_result"] = self.last_status_result
        if stopped_reason is not None:
            payload["stopped_reason"] = normalize_stopped_reason(
                stopped_reason,
                balance_exhausted=bool(payload.get("balance_exhausted")),
                circuit_breaker_tripped=bool(payload.get("circuit_breaker_tripped")),
            )
        state_current_progress = payload.pop("current_progress", None)
        state_in_flight_protocol = payload.pop("in_flight_protocol", None)
        readiness_payload = reduced_measurement_readiness_payload(
            payload.get("measurement_readiness")
        )
        if readiness_payload is None:
            payload.pop("measurement_readiness", None)
        else:
            payload["measurement_readiness"] = readiness_payload
        payload = normalize_status_payload(payload)
        terminal_stopped = payload.get("stopped") is True
        terminal_stopped_reason = payload.get("stopped_reason")
        branch_rows = _branch_rows(payload)
        _reconcile_active_slots_from_branch_cards(payload, branch_rows)
        if _is_max_rounds_stop(terminal_stopped_reason):
            payload["remaining_branch_classification"] = (
                campaign_remaining_branch_classification(branch_rows)
            )
        current_progress = self.current_status_progress
        if current_progress is None and isinstance(state_current_progress, Mapping):
            current_progress = dict(state_current_progress)
        if terminal_stopped and not _stopped_progress_is_complete(current_progress):
            current_progress = None
            self.current_status_progress = None
        if current_progress is not None:
            current_progress = _sync_branch_progress_from_rows(
                current_progress,
                branch_rows,
            )
            self.current_status_progress = current_progress
            payload["current_progress"] = current_progress
            _merge_runtime_budget_status(payload, current_progress)
        in_flight_protocol = self.in_flight_protocol
        if in_flight_protocol is None and isinstance(state_in_flight_protocol, Mapping):
            in_flight_protocol = dict(state_in_flight_protocol)
        if terminal_stopped and not _stopped_reason_preserves_partial_in_flight(
            terminal_stopped_reason
        ):
            in_flight_protocol = None
            self.in_flight_protocol = None
        if in_flight_protocol is not None:
            self.in_flight_protocol = dict(in_flight_protocol)
            payload["in_flight_protocol"] = _sync_in_flight_branch_fields(
                in_flight_protocol,
                current_progress,
                branch_rows,
            )
            if self.last_status_result is not None:
                payload["last_completed_result"] = self.last_status_result
        try:
            scheduler_records = (
                [self.last_status_result]
                if isinstance(self.last_status_result, Mapping)
                else []
            )
            payload["cross_branch_research_observability"] = (
                build_cross_branch_research_observability(
                    branch_rows=branch_rows,
                    branch_history_cards=payload.get("branch_history_cards") or (),
                    scheduler_records=scheduler_records,
                    context_records=_status_context_records(
                        self.last_status_result
                        if isinstance(self.last_status_result, Mapping)
                        else None,
                        current_progress
                        if isinstance(current_progress, Mapping)
                        else None,
                        payload.get("in_flight_protocol")
                        if isinstance(payload.get("in_flight_protocol"), Mapping)
                        else None,
                    ),
                )
            )
            _merge_status_cross_branch_map_coverage(payload)
            observability = payload.get("cross_branch_research_observability")
            if isinstance(observability, dict):
                summary_counters = (
                    _summary_grade_branch_lesson_usage_counters(
                        campaign_dir=self.campaign_dir,
                        campaign_id=self.campaign_id,
                    )
                    if terminal_stopped
                    else None
                )
                if summary_counters is not None:
                    observability.update(summary_counters)
                else:
                    _mark_branch_lesson_usage_counters_unavailable(observability)
        except Exception as exc:  # pragma: no cover - status is best-effort
            logger.debug("cross-branch observability status failed: %s", exc)
        payload["evidence_scope_reconciliation"] = _status_scope_reconciliation(
            payload=payload,
            branch_rows=branch_rows,
            last_result=(
                self.last_status_result
                if isinstance(self.last_status_result, Mapping)
                else None
            ),
            current_progress=(
                current_progress if isinstance(current_progress, Mapping) else None
            ),
        )
        lineage_integrity = self.lineage_integrity_snapshot(
            source="status_recorder_accumulator"
        )
        payload["lineage_integrity"] = lineage_integrity
        payload["evidence_integrity"] = {
            "schema_version": "scion.evidence_integrity.v1",
            "status": lineage_integrity["status"],
            "lineage_status": lineage_integrity["status"],
            "warnings": (
                [lineage_integrity["warning"]]
                if lineage_integrity.get("warning")
                else []
            ),
        }
        if payload.get("stopped_reason") is not None or payload.get("stopped") is True:
            loop = payload.get("campaign_loop")
            loop_mapping = loop if isinstance(loop, Mapping) else {}
            failure_categories = payload.get("failure_categories")
            if not isinstance(failure_categories, Mapping):
                failure_categories = loop_mapping.get("failure_categories")
            payload["run_validity"] = build_run_validity(
                requested_rounds=payload.get(
                    "requested_rounds",
                    loop_mapping.get("requested_rounds"),
                ),
                effective_rounds_completed=payload.get(
                    "effective_rounds_completed",
                    loop_mapping.get("effective_rounds_completed"),
                ),
                n_experiments=payload.get(
                    "n_experiments",
                    payload.get("screened_experiments"),
                ),
                proposal_attempts=payload.get(
                    "proposal_attempts_consumed",
                    payload.get("proposal_attempts"),
                ),
                protocol_metric_results=payload.get(
                    "protocol_metric_results",
                    loop_mapping.get("protocol_metric_results"),
                ),
                effective_protocol_rounds=payload.get(
                    "effective_protocol_rounds",
                    loop_mapping.get("effective_protocol_rounds"),
                ),
                stopped_reason=payload.get("stopped_reason"),
                failure_categories=failure_categories,
                stopped=True,
                partial_in_flight=bool(payload.get("in_flight_protocol")),
            )
            payload["run_validity_status"] = payload["run_validity"]["reason"]
            apply_lineage_integrity_to_run_validity(payload, lineage_integrity)
            payload = apply_run_completion_aliases(payload)
        public_payload = redact_public_refs(payload, base_dir=self.campaign_dir)
        try:
            self.status_reporter.write(public_payload)
        except Exception as exc:  # pragma: no cover - mirrors campaign best-effort behavior
            logger.debug("Failed to write status.json: %s", exc)
        return public_payload

    def record_protocol_progress(self, **payload: Any) -> Dict[str, Any]:
        """Merge a protocol progress update and refresh ``status.json``."""
        metrics_snapshot = _read_partial_metrics_snapshot(payload.get("raw_metrics_ref"))
        progress = dict(self.current_status_progress or {})
        previous_stage = str(progress.get("stage") or "").strip()
        incoming_stage = str(payload.get("stage") or "").strip()
        if incoming_stage and previous_stage and incoming_stage != previous_stage:
            for key in _PROTOCOL_STAGE_SCOPED_FIELDS:
                if key not in payload:
                    progress.pop(key, None)
        progress.update(payload)
        _normalize_child_process_fields(progress, payload)
        if "phase" not in payload:
            stage = str(progress.get("stage") or "").strip()
            if stage:
                progress["phase"] = f"formal_{stage}"
        for key in (
            "stage",
            "complete",
            "total_pairs",
            "attempted_pairs",
            "valid_pairs",
            "failed_pairs",
            "candidate_failed_pairs",
            "champion_failed_pairs",
            "runtime_confidence",
            "runtime_evidence_status",
            "runtime_evidence_policy",
            "runtime_gate_visibility",
            "champion_cached_runtime_pairs",
            "runtime_budget_diagnostic",
            "runtime_budget_diagnostic_code",
            "observability_value_visibility",
        ):
            if key not in payload and key in metrics_snapshot:
                progress[key] = metrics_snapshot[key]
        _normalize_child_process_fields(progress, payload)
        if "valid_pairs" not in progress and "completed_pairs" in progress:
            progress["valid_pairs"] = progress["completed_pairs"]
        _ensure_runtime_evidence_policy(progress)
        _ensure_runtime_gate_visibility(progress)
        _ensure_observability_value_visibility(progress)
        _ensure_running_protocol_fields(progress)
        if progress.get("raw_metrics_ref"):
            progress["raw_metrics_ref_scope"] = "public_artifact_ref"
            progress["raw_metrics_internal_only"] = True
        progress["last_progress_at"] = datetime.now().isoformat()
        progress = redact_public_refs(progress, base_dir=self.campaign_dir)
        _sync_protocol_progress_aliases(progress)
        self.current_status_progress = progress
        self.in_flight_protocol = _in_flight_protocol_snapshot(progress)
        self.write_status()
        return progress


def _is_max_rounds_stop(reason: Any) -> bool:
    text = str(reason or "").strip()
    return text in {"max_rounds", "max_rounds_exhausted"}


def _merge_status_cross_branch_map_coverage(payload: Dict[str, Any]) -> None:
    """Infer status-level map coverage from stable loop counters when needed."""
    observability = payload.get("cross_branch_research_observability")
    if not isinstance(observability, dict):
        return
    if observability.get("observable_step_count"):
        return
    completed = payload.get("effective_rounds_completed") or payload.get(
        "screened_experiments"
    )
    try:
        count = max(0, int(completed))
    except (TypeError, ValueError):
        return
    if count <= 0:
        return
    observability["observable_step_count"] = count
    observability["cross_branch_map_seen_count"] = max(
        int(observability.get("cross_branch_map_seen_count") or 0),
        count,
    )
    source_counts = observability.get("source_counts")
    if isinstance(source_counts, dict):
        source_counts["observable_step_count"] = observability["observable_step_count"]
        source_counts["status_loop_accounting_inferred_count"] = count
    observability["status_scope"] = "loop_accounting_inferred"
