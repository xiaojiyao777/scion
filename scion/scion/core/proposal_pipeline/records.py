"""Champion snapshots and hypothesis records."""
from __future__ import annotations

import uuid

from scion.core.models import Branch, ChampionState, HypothesisProposal, HypothesisRecord


class ProposalRecordMixin:
    def _champion_snapshot(self) -> ChampionState:
        with self.champion_lock:
            return self.get_champion()

    def _hypothesis_record(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
        *,
        champion: ChampionState | None = None,
        proposal_digest: str | None = None,
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
            base_champion_version=(champion.version if champion is not None else 0),
            target_file=hypothesis.target_file,
            suggested_weight=hypothesis.suggested_weight,
            hypothesis_text=hypothesis.hypothesis_text,
            family_id=cls_result.family_id,
            family_source=cls_result.source,
            taxonomy_version=cls_result.taxonomy_version,
            predicted_direction=hypothesis.predicted_direction,
            proposal_digest=proposal_digest,
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
