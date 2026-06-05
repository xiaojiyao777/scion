"""Status payload writer for campaign evidence recording."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Mapping

from scion.core.branch_cards import active_slot_inventory_from_branch_cards
from scion.core.public_refs import redact_public_refs
from scion.core.research_process_guidance_audit import (
    extract_research_process_guidance_audit,
)
from scion.core.run_validity import build_run_validity
from scion.core.screening_visibility import (
    observability_value_visibility_from_payload,
    runtime_evidence_policy_summary,
)
from scion.core.status_reporter import normalize_status_payload, normalize_stopped_reason

from .accounting import (
    accounting_reconciliation_fields,
    proposal_accounting_fields,
)
from .artifact_refs import _in_flight_protocol_snapshot, _read_partial_metrics_snapshot
from .cross_branch_observability import build_cross_branch_research_observability

logger = logging.getLogger(__name__)

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
        "effective_rounds_completed": "effective_rounds_completed",
        "telemetry_repair_attempts": "telemetry_repair_attempts",
        "telemetry_diagnostic_attempts": "telemetry_diagnostic_attempts",
        "branch_lifecycle_policy_blocks": "branch_lifecycle_policy_blocks",
        "reconcile_lifecycle_steps": "reconcile_lifecycle_steps",
        "non_counted_lifecycle_steps": "non_counted_lifecycle_steps",
        "quality_blocks": "quality_blocks",
        "blocked_attempts": "blocked_attempts",
        "infra_failure_attempts": "infra_failure_attempts",
        "noninfra_failure_attempts": "noninfra_failure_attempts",
        "loop_steps": "loop_steps",
        "campaign_steps": "campaign_steps",
        "screened_rounds": "screened_rounds",
        "agentic_sessions": "agentic_sessions",
        "hypothesis_calls": "hypothesis_calls",
        "code_calls": "code_calls",
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


_BRANCH_PROGRESS_FIELDS = (
    "lineage_status",
    "current_head_status",
    "best_checkpoint_status",
    "best_quality_checkpoint_id",
    "last_valid_checkpoint_id",
    "rollback_count",
    "lineage_retained_checkpoint",
    "latest_head_failed",
    "allowed_next_actions",
    "forbidden_next_actions",
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
                "repair_mechanism_ids": list(
                    getattr(last_result, "repair_mechanism_ids", ()) or ()
                ),
                "repair_policy_reason": getattr(
                    last_result,
                    "repair_policy_reason",
                    "",
                ),
                "scheduler_slot": getattr(last_result, "scheduler_slot", ""),
                "scheduler_reason": getattr(last_result, "scheduler_reason", ""),
                "scheduler_audit_metadata": dict(
                    getattr(last_result, "scheduler_audit_metadata", None) or {}
                ),
            }
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
        if self.last_status_result is not None:
            payload["last_result"] = self.last_status_result
        if stopped_reason is not None:
            payload["stopped_reason"] = normalize_stopped_reason(
                stopped_reason,
                balance_exhausted=bool(payload.get("balance_exhausted")),
                circuit_breaker_tripped=bool(payload.get("circuit_breaker_tripped")),
            )
        branch_rows = _branch_rows(payload)
        _reconcile_active_slots_from_branch_cards(payload, branch_rows)
        current_progress = self.current_status_progress
        if current_progress is not None:
            current_progress = _sync_branch_progress_from_rows(
                current_progress,
                branch_rows,
            )
            self.current_status_progress = current_progress
            payload["current_progress"] = current_progress
            _merge_runtime_budget_status(payload, current_progress)
        if self.in_flight_protocol is not None:
            payload["in_flight_protocol"] = _sync_in_flight_branch_fields(
                self.in_flight_protocol,
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
                    scheduler_records=scheduler_records,
                )
            )
            _merge_status_cross_branch_map_coverage(payload)
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
        payload = normalize_status_payload(payload)
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
                stopped_reason=payload.get("stopped_reason"),
                failure_categories=failure_categories,
                stopped=True,
                partial_in_flight=bool(payload.get("in_flight_protocol")),
            )
            payload["run_validity_status"] = payload["run_validity"]["reason"]
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
        _ensure_observability_value_visibility(progress)
        if progress.get("raw_metrics_ref"):
            progress["raw_metrics_ref_scope"] = "public_artifact_ref"
            progress["raw_metrics_internal_only"] = True
        progress["last_progress_at"] = datetime.now().isoformat()
        progress = redact_public_refs(progress, base_dir=self.campaign_dir)
        self.current_status_progress = progress
        self.in_flight_protocol = _in_flight_protocol_snapshot(progress)
        self.write_status()
        return progress


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
