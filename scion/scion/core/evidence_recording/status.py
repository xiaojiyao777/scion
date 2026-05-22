"""Status payload writer for campaign evidence recording."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Mapping

from scion.core.public_refs import redact_public_refs
from scion.core.status_reporter import normalize_status_payload, normalize_stopped_reason

from .artifact_refs import _in_flight_protocol_snapshot, _read_partial_metrics_snapshot

logger = logging.getLogger(__name__)


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
            }
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
        progress.update(payload)
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
            if key not in progress and key in metrics_snapshot:
                progress[key] = metrics_snapshot[key]
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
