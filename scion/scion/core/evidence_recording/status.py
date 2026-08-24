"""Pure status projections for a fresh V3 campaign."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Mapping

from scion.core.execution_outcome import ExecutionOutcome
from scion.core.public_refs import redact_public_refs

logger = logging.getLogger(__name__)

_REDACTED_PROPOSAL_STAGES = frozenset(
    {"proposal_hypothesis", "proposal_code"}
)


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
        stage = primitive.get("provenance", {}).get("stage")
        failure_stage = getattr(result, "failure_stage", None)
        redacted_proposal_stage = (
            failure_stage
            if isinstance(failure_stage, str)
            and failure_stage in _REDACTED_PROPOSAL_STAGES
            else stage
            if isinstance(stage, str) and stage in _REDACTED_PROPOSAL_STAGES
            else None
        )
        outcome = {
            "outcome": primitive["outcome"],
            "reason_code": primitive["reason_code"],
        }
        public_stage = redacted_proposal_stage or stage
        if isinstance(public_stage, str) and public_stage.strip():
            outcome["stage"] = public_stage.strip()
        projected["execution_outcome"] = outcome
        if (
            execution_outcome.outcome is not ExecutionOutcome.EVALUATED
            and redacted_proposal_stage is not None
        ):
            projected["reason"] = primitive["reason_code"]
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
