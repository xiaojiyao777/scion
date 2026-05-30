from __future__ import annotations

import inspect

from scion.core.models import (
    Branch,
    BranchState,
    HypothesisProposal,
    MechanismChange,
    PatchFileChange,
    PatchProposal,
    StepRecord,
)
from scion.proposal.context import branch_followup as branch_followup_module
from scion.proposal.context.branch_followup import (
    BRANCH_FOLLOWUP_POLICY_VIOLATION,
    branch_created_files,
    branch_current_file_sources,
    build_branch_followup_policy,
    render_branch_followup_policy,
    validate_weak_positive_followup_hypothesis,
)
from scion.proposal.engine import _split_hypothesis_context


def _weak_branch() -> Branch:
    return Branch(
        branch_id="branch-alpha",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="hash",
        branch_code_status="active_weak_positive",
        last_screening_feedback_tier="weak_positive",
        branch_mechanism_ids=("alpha_refinement",),
    )


def _hypothesis(
    *,
    target_file: str,
    mechanism_id: str,
    text: str = "Try a different scoring family.",
) -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=text,
        change_locus="assignment_policy",
        action="modify",
        target_file=target_file,
        target_weakness="The current policy leaves a generic gap.",
        expected_effect="Improve the declared objective without changing boundaries.",
        mechanism_changes=(MechanismChange(id=mechanism_id, change_type="add"),),
    )


def _prior_step() -> StepRecord:
    return StepRecord(
        round_num=1,
        branch_id="branch-alpha",
        hypothesis=_hypothesis(
            target_file="policies/main_policy.py",
            mechanism_id="alpha_refinement",
            text="Refine alpha_refinement inside the main policy.",
        ),
        patch=PatchProposal(
            file_path="policies/main_policy.py",
            action="modify",
            code_content="def main_policy():\n    return None\n",
            additional_changes=(
                PatchFileChange(
                    file_path="policies/helpers/alpha_helper.py",
                    action="create",
                    code_content="def alpha_helper():\n    return 1\n",
                ),
            ),
        ),
        contract_passed=True,
        verification_passed=True,
        protocol_result=None,
        decision=None,
        failure_stage=None,
        failure_detail=None,
    )


def test_weak_positive_followup_without_lineage_or_bridge_is_repairable_block() -> None:
    check = validate_weak_positive_followup_hypothesis(
        _weak_branch(),
        _hypothesis(
            target_file="policies/other_policy.py",
            mechanism_id="beta_probe",
        ),
        step_history=[_prior_step()],
    )

    assert check.allowed is False
    assert BRANCH_FOLLOWUP_POLICY_VIOLATION in check.detail
    rejection = check.structured_rejection()
    assert rejection["agent_block_reason"] == "agent_quality_blocked"
    assert "rewrite" in rejection["retry_constraint"]
    assert rejection["prior_mechanism_ids"] == ["alpha_refinement"]
    assert "policies/main_policy.py" in rejection["prior_touched_files"]
    assert rejection["branch_created_files"] == ["policies/helpers/alpha_helper.py"]


def test_weak_positive_followup_allows_bridge_or_prior_lineage_reference() -> None:
    bridge = validate_weak_positive_followup_hypothesis(
        _weak_branch(),
        _hypothesis(
            target_file="policies/other_policy.py",
            mechanism_id="beta_probe",
            text=(
                "Bridge from the prior weak signal on the same branch: this "
                "tests a branch-local failure because alpha_refinement cannot "
                "directly be refined without moving the activation point."
            ),
        ),
        step_history=[_prior_step()],
    )
    prior_file = validate_weak_positive_followup_hypothesis(
        _weak_branch(),
        _hypothesis(
            target_file="policies/main_policy.py",
            mechanism_id="beta_probe",
        ),
        step_history=[_prior_step()],
    )
    prior_mechanism = validate_weak_positive_followup_hypothesis(
        _weak_branch(),
        _hypothesis(
            target_file="policies/other_policy.py",
            mechanism_id="alpha_refinement",
        ),
        step_history=[_prior_step()],
    )

    assert bridge.allowed is True
    assert prior_file.allowed is True
    assert prior_mechanism.allowed is True


def test_branch_followup_policy_receipt_is_in_hypothesis_prompt() -> None:
    branch = _weak_branch()
    steps = [_prior_step()]
    policy = build_branch_followup_policy(branch, steps)
    rendered_policy = render_branch_followup_policy(policy)
    system_blocks, user_prompt = _split_hypothesis_context(
        {
            "problem_summary": "Generic combinatorial optimisation problem.",
            "research_surfaces": "assignment_policy",
            "champion_operators_code": "",
            "champion_stats": "",
            "branch_followup_policy": rendered_policy,
        }
    )
    rendered_prompt = "\n".join(block["text"] for block in system_blocks)

    assert "## Branch Follow-up Policy" in rendered_prompt
    assert "excluded_from_decision_features" in rendered_prompt
    assert "alpha_refinement" in rendered_prompt
    assert "policies/helpers/alpha_helper.py" in rendered_prompt
    assert "## Experiment History" not in user_prompt
    assert branch_created_files(branch, steps) == ("policies/helpers/alpha_helper.py",)


def test_branch_current_file_sources_replay_latest_same_branch_patch_content() -> None:
    branch = _weak_branch()
    first = _prior_step()
    second = StepRecord(
        round_num=2,
        branch_id="branch-alpha",
        hypothesis=_hypothesis(
            target_file="policies/helpers/alpha_helper.py",
            mechanism_id="alpha_refinement",
            text="Refine the helper source.",
        ),
        patch=PatchProposal(
            file_path="policies/helpers/alpha_helper.py",
            action="modify",
            code_content="def alpha_helper():\n    return 2\n",
        ),
        contract_passed=True,
        verification_passed=True,
        protocol_result=None,
        decision=None,
        failure_stage=None,
        failure_detail=None,
    )

    sources = branch_current_file_sources(branch, [first, second])

    assert sources["policies/main_policy.py"] == (
        "def main_policy():\n    return None\n"
    )
    assert sources["policies/helpers/alpha_helper.py"] == (
        "def alpha_helper():\n    return 2\n"
    )


def test_branch_followup_module_has_no_problem_specific_control_terms() -> None:
    source = inspect.getsource(branch_followup_module).lower()

    for term in ("cvrp", "route", "alns", "vns", "capacity", "demand", "fleet"):
        assert term not in source
