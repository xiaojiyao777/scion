from __future__ import annotations

from scion.core.branch_hygiene import (
    branch_hygiene_context,
    campaign_branch_lifecycle_reroute_status,
    record_branch_lifecycle_policy_block,
)
from scion.core.branch_repair_policy import validate_branch_continuation_patch
from scion.core.explore_step.pipeline import ExploreStepPipeline
from scion.core.models import Branch, BranchState, HypothesisProposal, PatchProposal


def test_explore_status_progress_includes_suspect_branch_hygiene() -> None:
    branch = Branch(
        branch_id="suspect-1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        current_code_hash="candidate-hash",
        last_clean_code_hash="candidate-hash",
        branch_code_status="telemetry_wiring_suspect",
        last_screening_feedback_tier="inactive",
        last_telemetry_outcome="activation_missing_or_wiring_suspect",
        telemetry_repair_mechanism_ids=("probe",),
        telemetry_repair_attempts={"probe": 1},
    )
    updates: list[dict] = []
    pipeline = ExploreStepPipeline(
        branch_controller=None,
        contract_gate=None,
        verification_gate=None,
        hypothesis_store=None,
        registry=None,
        campaign_id="camp-1",
        get_champion=lambda: None,
        pending_hypotheses={},
        branch_hypotheses={},
        branch_patches={},
        branch_current_hypothesis={},
        branch_workspaces={},
        failure_streak={},
        increment_round=lambda: 1,
        increment_rounds_since_last_promote=lambda: None,
        generate_hypothesis=lambda _branch: (None, None),
        generate_code=lambda *_args, **_kwargs: None,
        attempt_fix=lambda *_args, **_kwargs: None,
        handle_failure=lambda *_args, **_kwargs: None,
        record_step=lambda _step: None,
        setup_workspace=lambda _branch: None,
        apply_patch=lambda *_args, **_kwargs: None,
        record_verification_pass=lambda *_args, **_kwargs: None,
        archive_failed_workspace=lambda *_args, **_kwargs: None,
        evaluate=lambda *_args, **_kwargs: (None, None, None),
        apply_decision_and_finalize=lambda *_args, **_kwargs: None,
        decision_reason_codes_for=lambda *_args, **_kwargs: None,
        update_status_progress=lambda payload: updates.append(payload),
    )

    pipeline._emit_status_progress(
        branch,
        phase="proposal_hypothesis",
        round_num=4,
    )

    assert updates
    payload = updates[0]
    assert payload["branch_code_status"] == "telemetry_wiring_suspect"
    assert payload["last_telemetry_outcome"] == (
        "activation_missing_or_wiring_suspect"
    )
    assert payload["repair_focus_required"] is True
    assert payload["repair_focus_reason"] == "wiring_suspect_requires_repair"
    assert payload["repair_policy"] == "repair_first_same_mechanism_or_clean_fork"
    assert payload["repair_mechanism_ids"] == ["probe"]
    assert payload["telemetry_repair_attempts"] == {"probe": 1}


def test_activation_missing_outcome_requires_repair_even_if_status_is_clean() -> None:
    branch = Branch(
        branch_id="suspect-by-outcome",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="clean",
        last_telemetry_outcome="activation_missing_or_wiring_suspect",
    )

    payload = branch_hygiene_context(branch)

    assert payload["repair_focus_required"] is True
    assert payload["baseline_policy"] == "champion_required_for_repair"


def test_active_no_effect_context_exposes_same_mechanism_followup_policy() -> None:
    branch = Branch(
        branch_id="active-no-effect",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="active_no_effect",
        last_screening_feedback_tier="no_effect",
        last_telemetry_outcome="no_objective_effect",
        branch_mechanism_ids=("bounded_probe",),
    )

    payload = branch_hygiene_context(branch)

    assert payload["repair_focus_required"] is False
    assert payload["hypothesis_generation_mode"] == "same_mechanism_only"
    assert payload["branch_followup_policy"] == "same_mechanism_followup_only"
    assert payload["clean_fork_policy"] == "clean_fork_required_for_new_mechanism"
    assert payload["branch_mechanism_ids"] == ["bounded_probe"]
    assert payload["allowed_mechanism_ids"] == ["bounded_probe"]
    assert payload["protected_mechanism_ids"] == ["bounded_probe"]
    assert payload["forbidden_mechanism_policy"] == "no_unrelated_mechanism_ids"
    assert payload["same_mechanism_allowed_actions"] == [
        "tune",
        "integrate",
        "repair",
        "parameterize",
        "telemetry_wiring",
    ]
    assert payload["diversity_reroute_guidance"]["policy"] == (
        "runtime_saturated_diversity_reroute"
    )
    assert "mechanism family" in payload["diversity_reroute_guidance"]["guidance"]
    assert payload["baseline_policy"] == (
        "branch_workspace_same_mechanism_followup_only"
    )


def test_lifecycle_policy_block_marks_branch_for_clean_fork_reroute() -> None:
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

    block = record_branch_lifecycle_policy_block(
        branch,
        (
            "branch_lifecycle_policy_violation: "
            "new_mechanism_requires_clean_fork; "
            "protected_mechanism_ids=bounded_probe; "
            "proposed_mechanism_ids=different_probe"
        ),
    )
    payload = branch_hygiene_context(branch)
    campaign_payload = campaign_branch_lifecycle_reroute_status([branch])

    assert block["reason"] == "new_mechanism_requires_clean_fork"
    assert payload["branch_lifecycle_policy_blocks"] == 1
    assert payload["branch_lifecycle_new_mechanism_ineligible"] is True
    assert payload["branch_lifecycle_reroute_reason"] == (
        "clean_fork_after_branch_lifecycle_policy_block"
    )
    assert payload["next_branch_selection_policy"] == (
        "clean_branch_or_clean_fork_for_new_mechanism"
    )
    assert campaign_payload["ineligible_branch_ids"] == [branch.branch_id]
    assert campaign_payload["last_policy_block"]["branch_id"] == branch.branch_id


def test_same_mechanism_followup_patch_blocks_unrelated_mechanism_ids() -> None:
    branch = Branch(
        branch_id="active-no-effect-followup",
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
    protected_patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content="",
        mechanism_changes=({"id": "bounded_probe", "change_type": "modify"},),
    )
    unrelated_patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content="",
        mechanism_changes=({"id": "new_restart", "change_type": "add"},),
    )

    allowed = validate_branch_continuation_patch(branch, hypothesis, protected_patch)
    blocked = validate_branch_continuation_patch(branch, hypothesis, unrelated_patch)

    assert allowed.allowed is True
    assert blocked.allowed is False
    assert blocked.reason == "new_mechanism_requires_clean_fork"
    assert blocked.protected_mechanism_ids == ("bounded_probe",)
    assert blocked.proposed_mechanism_ids == ("new_restart",)
