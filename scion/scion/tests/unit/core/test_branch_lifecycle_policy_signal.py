"""Typed branch-lifecycle policy signal tests."""

from scion.core.branch_hygiene import record_branch_lifecycle_policy_block
from scion.core.branch_repair_policy import (
    branch_lifecycle_policy_block_signal_from_detail,
    repair_policy_check_violation_code_from_detail,
    validate_branch_continuation_patch,
)
from scion.core.models import Branch, BranchState, HypothesisProposal, PatchProposal


def test_policy_check_signal_marks_clean_fork_routing() -> None:
    branch = Branch(
        branch_id="blocked-no-effect",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="active_no_effect",
        last_screening_feedback_tier="no_effect",
        last_telemetry_outcome="no_objective_effect",
        branch_mechanism_ids=("bounded_probe",),
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Tune bounded_probe on the same branch.",
        target_weakness="The existing bounded_probe needs tuning.",
        expected_effect="Improve objective by tuning bounded_probe.",
        change_locus="solver_design",
        target_file="policies/baseline_algorithm.py",
        action="modify",
        mechanism_changes=({"id": "bounded_probe", "change_type": "modify"},),
    )
    unrelated_patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content="",
        mechanism_changes=({"id": "new_restart", "change_type": "add"},),
    )

    blocked = validate_branch_continuation_patch(branch, hypothesis, unrelated_patch)
    signal = blocked.lifecycle_block_signal
    parsed_signal = branch_lifecycle_policy_block_signal_from_detail(blocked.detail)
    wrapped_signal = branch_lifecycle_policy_block_signal_from_detail(
        f"agentic_proposal:anchor_validation_failed: {blocked.detail}"
    )
    text_only_signal = branch_lifecycle_policy_block_signal_from_detail(
        f"agentic_proposal:anchor_validation_failed: agent note says {blocked.detail}"
    )
    block = record_branch_lifecycle_policy_block(
        branch,
        blocked.detail,
        lifecycle_signal=signal,
    )

    assert blocked.allowed is False
    assert signal is not None
    assert parsed_signal == signal
    assert wrapped_signal == signal
    assert text_only_signal is None
    assert (
        repair_policy_check_violation_code_from_detail(blocked.detail)
        == "branch_lifecycle_policy_violation"
    )
    assert (
        repair_policy_check_violation_code_from_detail(
            f"agentic_proposal:anchor_validation_failed: {blocked.detail}"
        )
        == "branch_lifecycle_policy_violation"
    )
    assert signal.clean_fork_signal is True
    assert signal.candidate_routing == "new_mechanism_requires_clean_fork_signal"
    assert block["candidate_routing"] == "new_mechanism_requires_clean_fork_signal"
    assert block["clean_fork_signal"] is True
