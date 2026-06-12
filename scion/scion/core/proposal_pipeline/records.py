"""Champion snapshots, saturation signals, and hypothesis records."""
from __future__ import annotations

import uuid
from typing import Any

from scion.core.models import Branch, ChampionState, HypothesisProposal, HypothesisRecord


class ProposalRecordMixin:
    def _champion_snapshot(self) -> ChampionState:
        with self.champion_lock:
            return self.get_champion()

    def _compute_saturation_signals(self) -> Any:
        analyzer = self.get_saturation_analyzer()
        if analyzer is None:
            return None

        from scion.proposal.saturation import extract_candidate_metrics_from_step

        current_metrics = self.get_baseline_metrics()
        for step in reversed(self.step_history):
            if step.decision is not None and step.decision.value == "promote":
                metrics = extract_candidate_metrics_from_step(step)
                if metrics:
                    current_metrics = metrics
                    break
        if current_metrics:
            return analyzer.analyze(current_metrics)
        return None

    def _hypothesis_record(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
    ) -> HypothesisRecord:
        cls_result = self.classifier.classify(hypothesis.hypothesis_text or "")
        hypothesis_id = str(uuid.uuid4())
        parent_hypothesis_id = self._parent_hypothesis_id(
            branch.branch_id,
            hypothesis_id=hypothesis_id,
        )
        return HypothesisRecord(
            hypothesis_id=hypothesis_id,
            branch_id=branch.branch_id,
            parent_hypothesis_id=parent_hypothesis_id,
            change_locus=hypothesis.change_locus,
            action=hypothesis.action,
            status="active",
            target_file=hypothesis.target_file,
            suggested_weight=hypothesis.suggested_weight,
            hypothesis_text=hypothesis.hypothesis_text,
            family_id=cls_result.family_id,
            family_source=cls_result.source,
            taxonomy_version=cls_result.taxonomy_version,
            predicted_direction=hypothesis.predicted_direction,
            target_objectives=hypothesis.target_objectives,
            protected_objectives=hypothesis.protected_objectives,
            novelty_signature=dict(hypothesis.novelty_signature or {}),
            mechanism_changes=tuple(hypothesis.mechanism_changes or ()),
        )

    def _parent_hypothesis_id(
        self,
        branch_id: str,
        *,
        hypothesis_id: str,
    ) -> str | None:
        """Return the prior durable hypothesis on this branch, if any."""

        for record in reversed(self.hypothesis_store.get_by_branch(branch_id)):
            if record.hypothesis_id != hypothesis_id:
                return record.hypothesis_id
        return None
