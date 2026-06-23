from __future__ import annotations

from scion.core.explore_step.branch_lesson_usage import (
    branch_lesson_usage_requirement_from_records,
)
from scion.core.models import (
    Branch,
    BranchState,
    HypothesisProposal,
    MechanismChange,
    StepRecord,
)
from scion.proposal.context.cross_branch_research import (
    build_cross_branch_research_map,
)


def _branch(branch_id: str) -> Branch:
    return Branch(
        branch_id=branch_id,
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="hash",
        branch_mechanism_ids=("bounded_probe",),
    )


def _patch_contract_failure_step(branch_id: str) -> StepRecord:
    return StepRecord(
        round_num=1,
        branch_id=branch_id,
        hypothesis=HypothesisProposal(
            hypothesis_text="Whitelist failure is structural feedback.",
            change_locus="algorithm_design",
            action="modify",
            target_file="policies/base.py",
            mechanism_changes=(
                MechanismChange(id="bounded_probe", change_type="modify"),
            ),
        ),
        patch=None,
        contract_passed=False,
        verification_passed=False,
        protocol_result=None,
        decision=None,
        failure_stage="patch_contract",
        failure_detail="C4_file_whitelist",
    )


def test_patch_contract_failure_is_visible_but_not_hard_branch_lesson() -> None:
    current = _branch("branch-a")
    payload = build_cross_branch_research_map(
        current,
        [current],
        [_patch_contract_failure_step("branch-a")],
    )

    assert payload["branches"][0]["outcome_summary"]["outcome_pattern"] == (
        "pre_protocol_failure"
    )
    assert "branch_lesson_records" not in payload
    assert branch_lesson_usage_requirement_from_records(
        payload.get("branch_lesson_records")
    ) == {}
