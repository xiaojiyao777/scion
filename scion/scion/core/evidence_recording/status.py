"""Status payload writer for campaign evidence recording."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Mapping

from scion.core.public_refs import redact_public_refs
from scion.core.run_validity import build_run_validity
from scion.core.status_reporter import normalize_status_payload, normalize_stopped_reason

from .artifact_refs import _in_flight_protocol_snapshot, _read_partial_metrics_snapshot

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
            }
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
        if self.current_status_progress is not None:
            payload["current_progress"] = self.current_status_progress
        if self.in_flight_protocol is not None:
            payload["in_flight_protocol"] = self.in_flight_protocol
            if self.last_status_result is not None:
                payload["last_completed_result"] = self.last_status_result
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
        ):
            if key not in payload and key in metrics_snapshot:
                progress[key] = metrics_snapshot[key]
        _normalize_child_process_fields(progress, payload)
        if "valid_pairs" not in progress and "completed_pairs" in progress:
            progress["valid_pairs"] = progress["completed_pairs"]
        if progress.get("raw_metrics_ref"):
            progress["raw_metrics_ref_scope"] = "public_artifact_ref"
            progress["raw_metrics_internal_only"] = True
        progress["last_progress_at"] = datetime.now().isoformat()
        progress = redact_public_refs(progress, base_dir=self.campaign_dir)
        self.current_status_progress = progress
        self.in_flight_protocol = _in_flight_protocol_snapshot(progress)
        self.write_status()
        return progress
