"""Thin orchestration facade for pre-Protocol research rejection completion."""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from scion.core.durable_owner_codec import (
    branch_from_payload,
    branch_to_payload,
)
from scion.core.evidence_recording.replay_identity import stable_patch_digest
from scion.core.execution_outcome import (
    AttemptDisposition,
    ExecutionOutcomeRecord,
    ResearchRejectionDisposition,
)
from scion.core.models import Branch, HypothesisRecord, PatchProposal
from scion.core.research_rejection_completion import (
    ResearchRejectionCompletionIntent,
    ResearchRejectionCompletionStore,
)


@dataclass(frozen=True)
class ResearchRejectionFinalization:
    marker: ResearchRejectionDisposition
    archive_ref: str | None


@dataclass
class ResearchRejectionFinalizer:
    campaign_id: str
    campaign_dir: str
    store: ResearchRejectionCompletionStore
    branch_store: Any
    materializer: Any
    workspace_lifecycle: Any
    branch_hypotheses: MutableMapping[str, Any]
    branch_patches: MutableMapping[str, Any]
    branch_current_hypothesis: MutableMapping[str, Any]
    discard_approved_hypothesis_binding: Any

    def finalize(
        self,
        *,
        branch: Branch,
        hypothesis_record: HypothesisRecord,
        proposal_attempt_ref: Mapping[str, Any],
        rejection_phase: str,
        outcome: ExecutionOutcomeRecord,
        checks: tuple[Mapping[str, Any], ...],
        rejected_candidate_workspace: str | None = None,
        patch: PatchProposal | None = None,
    ) -> ResearchRejectionFinalization:
        source_branch = self.branch_store.load(branch.branch_id)
        if source_branch is None:
            raise RuntimeError("research rejection source branch is unavailable")
        clean_parent = self._clean_parent_identity(source_branch)
        failed = next(
            (item for item in checks if item.get("passed") is False),
            None,
        )
        failed_check = str((failed or {}).get("name") or rejection_phase)
        diagnostic_metadata = {
            "checks": [dict(item) for item in checks],
            "failure_detail": outcome.detail,
            "outcome_provenance": dict(outcome.provenance),
            "proposal": {
                "hypothesis_text": hypothesis_record.hypothesis_text or "",
                "action": (
                    patch.action if patch is not None else hypothesis_record.action
                ),
                "target_file": (
                    patch.file_path
                    if patch is not None
                    else hypothesis_record.target_file
                ),
            },
        }
        candidate = None
        if rejection_phase == "verification":
            if rejected_candidate_workspace is None or patch is None:
                raise ValueError(
                    "verification rejection requires candidate and patch identity"
                )
            candidate = self._candidate_identity(
                branch_id=branch.branch_id,
                hypothesis_id=hypothesis_record.hypothesis_id,
                workspace=rejected_candidate_workspace,
                patch=patch,
            )
        elif rejected_candidate_workspace is not None:
            raise ValueError("contract rejection cannot own candidate cleanup")
        elif rejection_phase == "hypothesis_contract" and patch is not None:
            raise ValueError("hypothesis Contract rejection cannot own a patch")
        elif rejection_phase == "patch_contract" and patch is None:
            raise ValueError("patch Contract rejection requires patch identity")
        rejected_patch_digest = (
            stable_patch_digest(patch.iter_file_changes())
            if rejection_phase == "patch_contract" and patch is not None
            else None
        )
        self._validate_live_branch_owner(
            branch,
            source_branch=source_branch,
            rejection_phase=rejection_phase,
            candidate=candidate,
        )

        intent = self.store.prepare(
            campaign_id=self.campaign_id,
            proposal_attempt_ref=proposal_attempt_ref,
            branch_id=branch.branch_id,
            hypothesis_id=hypothesis_record.hypothesis_id,
            rejection_phase=rejection_phase,
            reason_code=outcome.reason_code,
            failed_check=failed_check,
            diagnostic_metadata=diagnostic_metadata,
            clean_code_parent=clean_parent,
            rejected_candidate=candidate,
            rejected_patch_digest=rejected_patch_digest,
            execution_outcome=outcome,
            identity_validator=lambda clean, rejected: (
                self.materializer.validate_research_rejection_sources(
                    branch_id=branch.branch_id,
                    clean_parent=dict(clean),
                    candidate=(dict(rejected) if rejected is not None else None),
                )
            ),
        )
        committed = self.store.complete(
            intent,
            cleanup=self._cleanup,
            ownership_validator=self._validate_ownership,
        )
        self._install_target_branch(branch, committed)
        if rejected_candidate_workspace is not None:
            self.workspace_lifecycle.release_rejected_candidate_binding(
                branch,
                rejected_candidate_workspace,
            )
        self.branch_hypotheses.pop(branch.branch_id, None)
        self.branch_patches.pop(branch.branch_id, None)
        self.branch_current_hypothesis.pop(branch.branch_id, None)
        self.discard_approved_hypothesis_binding(branch.branch_id)
        provider = committed.payload["provider_attempt"]
        marker = ResearchRejectionDisposition(
            disposition=AttemptDisposition.ATTEMPT_REJECT_TO_BASE,
            completion_id=committed.completion_id,
            campaign_id=committed.campaign_id,
            provider_attempt_id=str(provider["attempt_id"]),
            rejection_phase=committed.rejection_phase,
        )
        if not self.store.verify_committed(
            marker,
            ownership_validator=self._validate_ownership,
        ):
            raise RuntimeError("research rejection committed marker is unavailable")
        return ResearchRejectionFinalization(
            marker=marker,
            archive_ref=(
                str(committed.payload["archive_ref"])
                if committed.payload.get("archive_ref")
                else None
            ),
        )

    def _clean_parent_identity(self, source_branch: Branch) -> dict[str, str]:
        campaign = Path(self.campaign_dir).resolve()
        if source_branch.last_clean_code_hash or source_branch.current_code_hash:
            path = campaign / "workspaces" / source_branch.branch_id
            kind = "branch_workspace"
        else:
            path = (
                campaign / "champions" / (f"champion_v{source_branch.base_champion_id}")
            )
            kind = "champion_snapshot"
        path = path.resolve()
        if not path.is_dir():
            raise RuntimeError("research rejection clean parent is unavailable")
        return {
            "kind": kind,
            "ref": path.relative_to(campaign).as_posix(),
            "code_hash": self.materializer.compute_code_hash(str(path)),
            "snapshot_hash": self.materializer.compute_snapshot_hash(str(path)),
        }

    def _candidate_identity(
        self,
        *,
        branch_id: str,
        hypothesis_id: str,
        workspace: str,
        patch: PatchProposal,
    ) -> dict[str, str]:
        campaign = Path(self.campaign_dir).resolve()
        path = Path(workspace).resolve()
        try:
            relative = path.relative_to(campaign).as_posix()
        except ValueError as exc:
            raise RuntimeError("rejected candidate escapes campaign") from exc
        expected_parent = campaign / "candidate_workspaces" / branch_id
        if path.parent != expected_parent.resolve():
            raise RuntimeError("rejected candidate workspace ownership mismatch")
        return {
            "workspace_ref": relative,
            "code_hash": self.materializer.compute_code_hash(str(path)),
            "snapshot_hash": self.materializer.compute_snapshot_hash(str(path)),
            "patch_digest": stable_patch_digest(patch.iter_file_changes()),
            "hypothesis_id": hypothesis_id,
        }

    @staticmethod
    def _validate_live_branch_owner(
        branch: Branch,
        *,
        source_branch: Branch,
        rejection_phase: str,
        candidate: Mapping[str, str] | None,
    ) -> None:
        source = branch_to_payload(source_branch)
        live = branch_to_payload(branch)
        if rejection_phase in {"hypothesis_contract", "patch_contract"}:
            expected = dict(source)
            expected["screening_expand_count"] = 0
            expected["validation_expand_count"] = 0
            if live != expected:
                raise RuntimeError(
                    "research rejection live Branch drifted from its clean owner"
                )
            return
        stable_fields = (
            "branch_id",
            "state",
            "base_champion_id",
            "base_champion_hash",
            "lineage_id",
            "last_clean_code_hash",
            "failure_codes",
            "created_at",
            "direction",
            "weight_revision",
            "branch_code_status",
            "branch_evidence_summary",
            "infra_block_count",
        )
        if any(live[key] != source[key] for key in stable_fields):
            raise RuntimeError(
                "verification rejection Branch owner changed before completion"
            )
        if live["screening_expand_count"] != 0 or live["validation_expand_count"] != 0:
            raise RuntimeError("verification rejection expansion owner changed")
        if candidate is None or live["current_code_hash"] != candidate["code_hash"]:
            raise RuntimeError(
                "verification rejection candidate Branch binding changed"
            )

    def _cleanup(self, intent: ResearchRejectionCompletionIntent) -> None:
        if intent.workspace_disposition == "archive_cleanup":
            self.materializer.archive_research_rejection_candidate(dict(intent.payload))

    def _validate_ownership(
        self,
        intent: ResearchRejectionCompletionIntent,
        require_cleanup_receipt: bool,
    ) -> None:
        self.materializer.validate_research_rejection_ownership(
            dict(intent.payload),
            require_cleanup_receipt=require_cleanup_receipt,
        )

    @staticmethod
    def _install_target_branch(
        branch: Branch,
        intent: ResearchRejectionCompletionIntent,
    ) -> None:
        target = branch_from_payload(intent.payload["target_branch"])
        for item in fields(Branch):
            setattr(branch, item.name, getattr(target, item.name))


__all__ = [
    "ResearchRejectionFinalization",
    "ResearchRejectionFinalizer",
]
