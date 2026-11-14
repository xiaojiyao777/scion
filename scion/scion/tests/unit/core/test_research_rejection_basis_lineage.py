from __future__ import annotations

import json

import pytest

from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import Branch, BranchState, HypothesisProposal, PatchProposal
from scion.core.research_rejection_finalizer import ResearchRejectionFinalizer
from scion.core.workspace_service import CandidateWorkspace
from scion.lineage.registry import LineageRegistry


class _WorkspaceService:
    def __init__(self) -> None:
        self.rejected: list[CandidateWorkspace] = []

    def reject_candidate(self, candidate: CandidateWorkspace) -> None:
        self.rejected.append(candidate)


class _FailingWorkspaceService:
    def reject_candidate(self, _candidate: CandidateWorkspace) -> None:
        raise OSError("candidate cleanup unavailable")


@pytest.mark.parametrize(
    "phase",
    ("hypothesis_contract", "proposal_code", "patch_contract", "verification"),
)
def test_every_research_rejection_event_carries_attempt_local_selected_basis(
    tmp_path,
    phase: str,
) -> None:
    registry = LineageRegistry(str(tmp_path / "lineage.db"))
    workspace_service = _WorkspaceService()
    finalizer = ResearchRejectionFinalizer(
        campaign_id="campaign-1",
        registry=registry,
        workspace_service=workspace_service,
        branch_patches={},
    )
    branch = Branch(
        branch_id="branch-1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
    )
    basis = {
        "read_refs": ["source-0001", "history-0002"],
        "nearest_prior_refs": ["history-0002"],
        "material_delta": "Change the selected mechanism.",
        "alternatives_considered": ["Keep the current mechanism."],
        "observable_prediction": "Screening should improve.",
        "falsification_condition": "Reject if screening does not improve.",
        "history_review": [
            {
                "ref": "history-0003",
                "disposition": "rejected",
                "reason": "Its failure mechanism does not apply.",
            }
        ],
    }
    patch = PatchProposal(
        file_path="operators/local_search.py",
        action="modify",
        code_content="def improve(solution):\n    return solution\n",
    )
    candidate = CandidateWorkspace("/tmp/candidate", "candidate-digest")
    outcome = ExecutionOutcomeRecord(
        outcome=ExecutionOutcome.RESEARCH_REJECTED,
        reason_code="TEST_RESEARCH_REJECTED",
        provenance={"stage": phase},
    )

    finalizer.finalize(
        branch=branch,
        rejection_phase=phase,
        outcome=outcome,
        patch=patch if phase in {"patch_contract", "verification"} else None,
        candidate=candidate if phase == "verification" else None,
        selected_hypothesis_research_basis=basis,
    )

    row = registry.query_by_branch(branch.branch_id)[0]
    assert row["event_kind"] == "research_rejection"
    assert json.loads(row["selected_hypothesis_research_basis_json"]) == basis
    assert workspace_service.rejected == (
        [candidate] if phase == "verification" else []
    )


def test_verification_cleanup_failure_records_infra_and_retains_rejection_fact(
    tmp_path,
) -> None:
    registry = LineageRegistry(str(tmp_path / "lineage.db"))
    patch = PatchProposal(
        file_path="operators/local_search.py",
        action="modify",
        code_content="def improve(solution):\n    return solution\n",
    )
    finalizer = ResearchRejectionFinalizer(
        campaign_id="campaign-1",
        registry=registry,
        workspace_service=_FailingWorkspaceService(),
        branch_patches={"branch-1": patch},
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Exercise the selected mechanism.",
        change_locus="local_search",
        action="modify",
        target_file="operators/local_search.py",
    )
    basis = {
        "read_refs": ["source-0001"],
        "nearest_prior_refs": [],
        "material_delta": "Change the selected mechanism.",
        "alternatives_considered": ["Keep the current mechanism."],
        "observable_prediction": "Verification should pass.",
        "falsification_condition": "Reject if verification fails.",
    }
    branch = Branch(
        branch_id="branch-1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        hypothesis=hypothesis,
        selected_hypothesis_research_basis=basis,
    )
    rejection = ExecutionOutcomeRecord(
        outcome=ExecutionOutcome.RESEARCH_REJECTED,
        reason_code="VERIFICATION_LIGHT_REJECTED",
        detail="synthetic verification failure",
        provenance={"stage": "verification", "severity": "light"},
    )

    result = finalizer.finalize(
        branch=branch,
        rejection_phase="verification",
        outcome=rejection,
        patch=patch,
        candidate=CandidateWorkspace("/tmp/candidate", "candidate-digest"),
        selected_hypothesis_research_basis=basis,
    )

    assert result.outcome is ExecutionOutcome.BLOCKED_INFRA
    assert result.reason_code == "CANDIDATE_REJECT_FAILED"
    assert result.provenance["interrupted_outcome"] == rejection.to_primitive()
    assert branch.state is BranchState.BLOCKED_INFRA
    assert branch.hypothesis is hypothesis
    assert branch.selected_hypothesis_research_basis == basis
    rows = registry.query_by_branch(branch.branch_id)
    assert len(rows) == 1
    assert rows[0]["event_kind"] == "candidate_disposition_execution_outcome"
    assert json.loads(rows[0]["selected_hypothesis_research_basis_json"]) == basis
    assert json.loads(rows[0]["execution_outcome_provenance_json"])[
        "interrupted_outcome"
    ] == rejection.to_primitive()
