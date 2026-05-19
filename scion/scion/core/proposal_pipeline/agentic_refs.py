"""Agentic session recovery, lineage, and public session references."""
from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Mapping

from scion.core.public_refs import contains_absolute_path, public_artifact_ref
from scion.proposal.agentic_session import (
    AgenticProposalOutput,
    AgenticProposalRequest,
    AgenticProposalStatus,
    AgenticSessionStore,
    AgenticTerminationReason,
    compute_agentic_idempotency_key,
    resume_from_artifact,
)

from .classification import (
    _agentic_primary_secondary_failures,
    _agentic_quality_block_classification,
    _agentic_rejection_constraint,
)
from .constants import AGENT_QUALITY_BLOCKED
from .utils import _agentic_value, _json_dumps, _now_iso

logger = logging.getLogger(__name__)


class AgenticRefsMixin:
    def _with_agentic_resume_context(
        self,
        request: AgenticProposalRequest,
    ) -> AgenticProposalRequest:
        resume_context = self._lookup_agentic_resume_context(request)
        if resume_context is None:
            return request
        return replace(request, resume_context=resume_context)

    def _lookup_agentic_resume_context(
        self,
        request: AgenticProposalRequest,
    ) -> Mapping[str, Any] | None:
        if not self.agentic_artifact_dir:
            return None
        idempotency_key = self._agentic_idempotency_key_for_request(request)
        stored = AgenticSessionStore(self.agentic_artifact_dir).find_by_idempotency_key(
            idempotency_key
        )
        if stored is None:
            return None

        report = {
            "session_id": stored.entry.session_id,
            "idempotency_key": idempotency_key,
            "artifact_ref": stored.entry.artifact_ref,
            "status": stored.entry.status,
            "termination_reason": stored.entry.termination_reason,
            "validation_ok": stored.validation.ok,
            "validation_errors": list(stored.validation.errors),
        }
        self.agentic_recovery_reports[request.branch.branch_id] = report
        if not stored.validation.ok or stored.artifact is None:
            logger.warning(
                "Branch %s: agentic recovery artifact invalid; starting fresh: %s",
                request.branch.branch_id,
                "; ".join(stored.validation.errors),
            )
            return None
        try:
            context = resume_from_artifact(stored.artifact)
        except Exception as exc:
            self.agentic_recovery_reports[request.branch.branch_id] = {
                **report,
                "validation_ok": False,
                "validation_errors": [str(exc)],
            }
            logger.warning(
                "Branch %s: agentic recovery summary failed; starting fresh: %s",
                request.branch.branch_id,
                exc,
            )
            return None
        return {
            "source": "agentic_session_store",
            "recovery_mode": "sanitized_resume_context_only",
            "artifact_ref": stored.entry.artifact_ref,
            "status": stored.entry.status,
            "termination_reason": stored.entry.termination_reason,
            "validation": {"ok": True, "errors": []},
            "resume": context,
        }

    def _agentic_idempotency_key_for_request(
        self,
        request: AgenticProposalRequest,
    ) -> str:
        key_for_request = getattr(self.agentic_session, "idempotency_key_for_request", None)
        if callable(key_for_request):
            try:
                return str(key_for_request(request))
            except Exception:
                logger.debug("agentic session idempotency hook failed", exc_info=True)
        return compute_agentic_idempotency_key(
            request,
            self._agentic_tool_loop_config(),
        )

    def _agentic_failure_detail(self, output: AgenticProposalOutput) -> str:
        reason = output.termination_reason
        reason_value = (
            reason.value
            if isinstance(reason, AgenticTerminationReason)
            else str(reason)
        )
        quality = _agentic_quality_block_classification(output)
        if quality is not None:
            prefix = (
                f"agentic_proposal:{reason_value}: "
                f"{AGENT_QUALITY_BLOCKED}:"
                f"{quality['failure_code']}:"
                f"{quality['failure_class']}"
            )
            if output.failure_detail:
                return f"{prefix}: {output.failure_detail}"
            return prefix
        if output.failure_detail:
            return f"agentic_proposal:{reason_value}: {output.failure_detail}"
        return f"agentic_proposal:{reason_value}"

    def _record_agentic_lineage_event(self, output: AgenticProposalOutput) -> None:
        if self.lineage_registry is None:
            return
        tainted_artifact_refs = list(output.tainted_artifact_refs)
        public_tainted_artifact_refs = [
            public_artifact_ref(ref) for ref in tainted_artifact_refs
        ]
        tainted_refs_internal_only = contains_absolute_path(tainted_artifact_refs)
        primary_failure, secondary_observations = (
            _agentic_primary_secondary_failures(output)
        )
        payload = {
            "schema_version": output.schema_version,
            "session_id": output.session_id,
            "request_id": output.request_id,
            "idempotency_key": output.idempotency_key,
            "transcript_digest": output.transcript_digest,
            "status": output.status.value
            if isinstance(output.status, AgenticProposalStatus)
            else str(output.status),
            "termination_reason": output.termination_reason.value
            if isinstance(output.termination_reason, AgenticTerminationReason)
            else str(output.termination_reason),
            "tainted_artifact_refs": public_tainted_artifact_refs,
            "tainted_artifact_ref_scope": "public_relative",
            "tainted_artifact_refs_internal_only": tainted_refs_internal_only,
            "internal_only": tainted_refs_internal_only,
            "contract_preview_passed": output.self_check.contract_preview_passed,
            "contract_preview_codes": list(output.self_check.contract_preview_codes),
        }
        if primary_failure:
            payload["primary_failure"] = primary_failure
        if secondary_observations:
            payload["secondary_observations"] = secondary_observations
        event = {
            "campaign_id": output.campaign_id or self.campaign_id,
            "branch_id": output.branch_id,
            "timestamp": _now_iso(),
            "event_kind": "agentic_proposal_session",
            "stage": "agentic_proposal",
            "contract_result": (
                "passed"
                if output.self_check.contract_preview_passed is True
                else "failed"
                if output.self_check.contract_preview_passed is False
                else "not_run"
            ),
            "verification_result": "not_run",
            "canary_result": "not_run",
            "raw_metrics_ref": "",
            "decision_features_json": "",
            "audit_payload_json": _json_dumps(payload),
        }
        try:
            self.lineage_registry.record_event(event)
        except Exception:
            logger.debug("agentic lineage event write failed", exc_info=True)

    def _record_agentic_session_ref(self, output: AgenticProposalOutput) -> None:
        self.agentic_session_refs[output.branch_id] = self._agentic_session_ref(output)

    def pop_agentic_session_ref(self, branch_id: str) -> Mapping[str, Any] | None:
        return self.agentic_session_refs.pop(branch_id, None)

    @staticmethod
    def _agentic_session_ref(output: AgenticProposalOutput) -> dict[str, Any]:
        artifact_ref = next(
            (
                ref
                for ref in reversed(output.tainted_artifact_refs)
                if str(ref).endswith("output.json")
            ),
            output.tainted_artifact_refs[-1] if output.tainted_artifact_refs else None,
        )
        structured = (
            output.structured_rejection
            if isinstance(output.structured_rejection, Mapping)
            else {}
        )
        quality = _agentic_quality_block_classification(output)
        primary_failure, secondary_observations = (
            _agentic_primary_secondary_failures(output)
        )
        rejection_constraint = _agentic_rejection_constraint(output)
        return {
            "schema_version": output.schema_version,
            "session_id": output.session_id,
            "request_id": output.request_id,
            "idempotency_key": output.idempotency_key,
            "artifact_ref": artifact_ref,
            "transcript_digest": output.transcript_digest,
            "termination_reason": output.termination_reason.value
            if isinstance(output.termination_reason, AgenticTerminationReason)
            else str(output.termination_reason),
            "status": output.status.value
            if isinstance(output.status, AgenticProposalStatus)
            else str(output.status),
            "failure_category": _agentic_value(output.failure_category),
            "failure_code": str(structured.get("failure_code") or ""),
            "agent_block_reason": (
                quality["block_reason"] if quality is not None else ""
            ),
            "primary_failure": primary_failure,
            "secondary_observations": secondary_observations,
            "rejection_constraint": rejection_constraint,
        }
