"""EvidenceRecorder service shell."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, MutableSequence

from scion.core.models import StepRecord
from scion.core.research_history import ResearchHistoryWriter
from scion.core.status_reporter import StatusReporter

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
        model_id: str | None = None,
        protocol_version: str | None = None,
        family_taxonomy: Any | None = None,
        problem_id: str | None = None,
    ) -> None:
        self.campaign_id = campaign_id
        self.campaign_dir = Path(campaign_dir)
        self.status_reporter = status_reporter or StatusReporter(str(self.campaign_dir))
        self.registry = registry
        self.model_id = model_id
        self.protocol_version = protocol_version
        self.family_taxonomy = family_taxonomy
        self.final_evidence_refs: Dict[str, Any] = {}
        self._research_history_writer = (
            ResearchHistoryWriter(self.campaign_dir, problem_id=problem_id)
            if problem_id is not None
            else None
        )

    def record_step(
        self,
        step: StepRecord,
        step_history: MutableSequence[StepRecord],
    ) -> None:
        """Append a completed step to the durable campaign history."""
        if self._research_history_writer is not None:
            self._research_history_writer.append_step(step)
        step_history.append(step)

    def attach_final_evidence_refs(self, refs: Mapping[str, Any]) -> None:
        """Store future final quality harness refs without touching step schema."""
        self.final_evidence_refs.update(dict(refs))
