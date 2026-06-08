"""EvidenceRecorder service shell."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, MutableSequence

from scion.core.models import StepRecord
from scion.core.research_process_guidance_audit import (
    extract_research_process_guidance_audit,
)
from scion.core.status_reporter import StatusReporter

from .common import StateProvider
from .lineage import LineageRecorderMixin
from .status import StatusWriterMixin
from .summary import CampaignSummaryMixin


class EvidenceRecorder(StatusWriterMixin, LineageRecorderMixin, CampaignSummaryMixin):
    """Record campaign evidence while preserving existing artifact contracts."""

    def __init__(
        self,
        *,
        campaign_id: str,
        campaign_dir: str | Path,
        status_reporter: StatusReporter | None = None,
        registry: Any | None = None,
        state_provider: StateProvider | None = None,
        model_id: str | None = None,
        protocol_version: str | None = None,
        problem_spec_hash: str | None = None,
        split_manifest_hash: str | None = None,
        seed_ledger_hash: str | None = None,
        family_taxonomy: Any | None = None,
    ) -> None:
        self.campaign_id = campaign_id
        self.campaign_dir = Path(campaign_dir)
        self.status_reporter = status_reporter or StatusReporter(str(self.campaign_dir))
        self.registry = registry
        self.state_provider = state_provider
        self.model_id = model_id
        self.protocol_version = protocol_version
        self.problem_spec_hash = problem_spec_hash
        self.split_manifest_hash = split_manifest_hash
        self.seed_ledger_hash = seed_ledger_hash
        self.family_taxonomy = family_taxonomy
        self.current_status_progress: Dict[str, Any] | None = None
        self.in_flight_protocol: Dict[str, Any] | None = None
        self.last_status_result: Dict[str, Any] | None = None
        self.campaign_loop_status: Dict[str, Any] | None = None
        self.final_evidence_refs: Dict[str, Any] = {}
        self.lineage_recording_outcomes: list[Dict[str, Any]] = []

    def record_step(
        self,
        step: StepRecord,
        step_history: MutableSequence[StepRecord],
        *,
        search_memory: Any | None = None,
    ) -> None:
        """Append a completed step and update optional search memory."""
        step_history.append(step)
        if search_memory is not None:
            search_memory.update(step)

    def record_scheduler_result(
        self,
        result: Any,
        step_history: MutableSequence[StepRecord],
    ) -> None:
        """Persist scheduler metadata on the latest matching step and lineage."""
        slot = str(getattr(result, "scheduler_slot", "") or "")
        reason = str(getattr(result, "scheduler_reason", "") or "")
        audit_metadata = dict(getattr(result, "scheduler_audit_metadata", None) or {})
        if not (slot or reason):
            return
        step: StepRecord | None = None
        branch_id = str(getattr(result, "branch_id", "") or "")
        if branch_id:
            for candidate in reversed(step_history):
                if candidate.branch_id != branch_id:
                    continue
                step = candidate
                if getattr(candidate, "scheduler_slot", "") or getattr(
                    candidate,
                    "scheduler_reason",
                    "",
                ):
                    break
                candidate.scheduler_slot = slot
                candidate.scheduler_reason = reason
                if audit_metadata:
                    candidate.scheduler_audit_metadata = audit_metadata
                break
        guidance_audit = extract_research_process_guidance_audit(audit_metadata)
        if not guidance_audit and step is not None:
            guidance_audit = extract_research_process_guidance_audit(
                getattr(step, "proposal_session_ref", None)
            )
        if guidance_audit:
            audit_metadata["research_process_guidance_audit"] = guidance_audit
            result.scheduler_audit_metadata = audit_metadata
            if step is not None:
                step.scheduler_audit_metadata = audit_metadata
        self.record_scheduler_result_lineage(result=result, step=step)

    def attach_final_evidence_refs(self, refs: Mapping[str, Any]) -> None:
        """Store future final quality harness refs without touching step schema."""
        self.final_evidence_refs.update(dict(refs))
