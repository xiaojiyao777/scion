"""One append-only event per direct V3 H/C provider call."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from scion.core.execution_outcome import ExecutionOutcomeRecord
from scion.proposal.engine import PromptCallReceipt


@dataclass(frozen=True)
class ProposalCallJournal:
    """Persist provider diagnostics without creating an attempt lifecycle."""

    lineage_registry: Any | None
    campaign_id: str

    def append(
        self,
        *,
        branch_id: str,
        phase: str,
        status: str,
        hypothesis_id: str | None,
        receipt: PromptCallReceipt | None,
        execution_outcome: ExecutionOutcomeRecord | None = None,
    ) -> Mapping[str, Any]:
        if phase not in {"hypothesis", "code"}:
            raise ValueError(f"unsupported proposal phase: {phase}")
        if status not in {"generated", "failed", "interrupted"}:
            raise ValueError(f"unsupported proposal call status: {status}")
        if not branch_id:
            raise ValueError("proposal call branch_id is required")

        payload: dict[str, Any] = {
            "schema_version": "proposal-call.v1",
            "phase": phase,
            "status": status,
            "hypothesis_id": hypothesis_id,
            "receipt": _receipt_payload(receipt),
            "execution_outcome": (
                execution_outcome.to_primitive()
                if execution_outcome is not None
                else None
            ),
        }
        lineage_event_id = None
        if self.lineage_registry is not None:
            lineage_event_id = self.lineage_registry.record_event(
                {
                    "campaign_id": self.campaign_id,
                    "branch_id": branch_id,
                    "hypothesis_id": hypothesis_id,
                    "event_kind": "proposal_call",
                    "stage": f"proposal_{phase}",
                    "audit_payload_json": json.dumps(
                        payload,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                }
            )

        ref: dict[str, Any] = {
            "schema_version": "proposal-call-ref.v1",
            "phase": phase,
            "status": status,
            "hypothesis_id": hypothesis_id,
        }
        if lineage_event_id:
            ref["lineage_event_id"] = str(lineage_event_id)
        if receipt is not None:
            if receipt.trace_ref:
                ref["artifact_ref"] = receipt.trace_ref
            if receipt.prompt_manifest_ref:
                ref["prompt_manifest_ref"] = receipt.prompt_manifest_ref
            if receipt.error_category:
                ref["failure_category"] = receipt.error_category
        if execution_outcome is not None:
            ref["failure_code"] = execution_outcome.reason_code
            ref["primary_failure"] = {
                "stage": f"proposal_{phase}",
                "code": execution_outcome.reason_code,
                "category": (
                    receipt.error_category if receipt is not None else None
                ),
                "detail": execution_outcome.detail,
            }
        return ref


def _receipt_payload(receipt: PromptCallReceipt | None) -> dict[str, Any] | None:
    if receipt is None:
        return None
    return {
        "request_kind": receipt.request_kind,
        "context_digest": receipt.context_digest,
        "prompt_hash": receipt.prompt_hash,
        "trace_ref": receipt.trace_ref,
        "prompt_manifest_ref": receipt.prompt_manifest_ref,
        "raw_response_ref": receipt.raw_response_ref,
        "provider_ok": receipt.provider_ok,
        "ok": receipt.ok,
        "error_category": receipt.error_category,
        "error_type": receipt.error_type,
        "trace_persistence_error": receipt.trace_persistence_error,
    }


__all__ = ["ProposalCallJournal"]
