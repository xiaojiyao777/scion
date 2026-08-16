"""Pure status projections for a fresh V3 campaign."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Mapping

from scion.core.public_refs import redact_public_refs

logger = logging.getLogger(__name__)


def project_last_result(result: Any) -> dict[str, Any]:
    """Return the compact operator view of the latest completed step."""

    projected: dict[str, Any] = {
        "action": result.action,
        "branch_id": result.branch_id,
        "decision": (
            result.decision.value
            if getattr(result, "decision", None) is not None
            else None
        ),
        "stopped": bool(result.stopped),
        "reason": result.reason,
    }
    execution_outcome = getattr(result, "execution_outcome", None)
    if execution_outcome is not None:
        primitive = execution_outcome.to_primitive()
        outcome = {
            "outcome": primitive["outcome"],
            "reason_code": primitive["reason_code"],
        }
        stage = primitive.get("provenance", {}).get("stage")
        if isinstance(stage, str) and stage.strip():
            outcome["stage"] = stage.strip()
        projected["execution_outcome"] = outcome
    return projected


class StatusWriterMixin:
    def write_status(
        self,
        *,
        state: Mapping[str, Any],
        run_result: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """Write the supplied ordinary state without rebuilding run semantics."""

        payload = dict(state)
        payload["run_result"] = dict(run_result)
        public_payload = redact_public_refs(payload, base_dir=self.campaign_dir)
        try:
            self.status_reporter.write(public_payload)
        except Exception as exc:  # pragma: no cover - observational best effort
            logger.debug("Failed to write status.json: %s", exc)
        return public_payload

    def record_protocol_progress(
        self,
        *,
        current_progress: Mapping[str, Any] | None = None,
        **payload: Any,
    ) -> Dict[str, Any]:
        """Return the caller-supplied progress merge without derived aliases."""

        progress = dict(current_progress or {})
        progress.update(payload)
        progress["last_progress_at"] = datetime.now().isoformat()
        return redact_public_refs(progress, base_dir=self.campaign_dir)
