from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from typing import Callable

from scion.core.branch import BranchController
from scion.core.branch_step_runner import BranchStepRunner
from scion.core.branch_lifecycle_policy import (
    BRANCH_LIFECYCLE_PARK_LINEAGE,
    BRANCH_LIFECYCLE_RETAIN_CHECKPOINT,
)
from scion.core.models import Branch, BranchState, ChampionState
from scion.core.scheduler import (
    ACTIVE_SLOT_RECLAIMED_FOR_NEW_BRANCH,
    Scheduler,
    SchedulerAction,
    active_slot_inventory,
)
from scion.core.step_result import StepResult


def _branch(
    branch_id: str = "branch-1",
    state: BranchState = BranchState.EXPLORE,
) -> Branch:
    return Branch(
        branch_id=branch_id,
        state=state,
        base_champion_id=1,
        base_champion_hash="champion-hash",
    )


def _champion() -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="solver",
        code_snapshot_path="/tmp/champion",
        code_snapshot_hash="champion-hash",
    )


def _runner(
    *,
    scheduler_action: SchedulerAction,
    branch: Branch | None = None,
    recorded_scheduler_results: list[StepResult] | None = None,
    explore_result: StepResult | None = None,
    run_explore_step: Callable[[Branch], StepResult] | None = None,
) -> BranchStepRunner:
    selected_branch = branch or _branch()
    recorded = (
        recorded_scheduler_results
        if recorded_scheduler_results is not None
        else []
    )
    branch_controller = SimpleNamespace(
        get_active_branches=lambda: [selected_branch] if branch is not None else [],
        create_branch=lambda champion: selected_branch,
        get_branch=lambda branch_id: selected_branch,
        schedule_branch=lambda branch_id: None,
        apply_decision=lambda branch_id, decision: None,
    )
    scheduler = SimpleNamespace(select_next=lambda active: scheduler_action)
    branch_store = SimpleNamespace(save=lambda branch: None)
    selected_explore_result = explore_result or StepResult(
        action="explore",
        branch_id=selected_branch.branch_id,
        reason="screening complete",
    )
    return BranchStepRunner(
        branch_controller=branch_controller,
        scheduler=scheduler,
        champion_lock=nullcontext(),
        get_champion=lambda: SimpleNamespace(version=1),
        branch_store=branch_store,
        branch_workspaces={},
        branch_hypotheses={},
        branch_patches={},
        branch_current_hypothesis={},
        experiment_protocol_provider=lambda: None,
        contract_gate=None,
        verification_gate=None,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        tick_blocked_branches=lambda: None,
        persist_branch_state=lambda branch_id: None,
        record_hard_abandon=lambda branch_id, reason: None,
        setup_workspace=lambda *args, **kwargs: None,
        apply_patch=lambda *args, **kwargs: None,
        record_verification_pass=lambda branch, code_hash: None,
        evaluate=lambda branch, workspace, hypothesis: None,
        apply_decision_and_finalize=lambda **kwargs: StepResult(action="explore"),
        record_step=lambda step: None,
        decision_reason_codes_for=lambda branch_id, protocol_result: None,
        run_explore_step=(
            run_explore_step
            if run_explore_step is not None
            else lambda branch: selected_explore_result
        ),
        run_eval_step_callback=lambda branch: StepResult(
            action="validate",
            branch_id=branch.branch_id,
            reason="evaluation complete",
        ),
        run_reconcile_step_callback=lambda branch: StepResult(
            action="reconcile",
            branch_id=branch.branch_id,
            reason="reconcile complete",
        ),
        increment_round=lambda: 1,
        increment_rounds_since_last_promote=lambda: None,
        hypothesis_store=None,
        record_scheduler_result=recorded.append,
    )


def test_create_new_scheduler_metadata_reaches_result_and_callback() -> None:
    branch = _branch("new-branch")
    recorded: list[StepResult] = []
    runner = _runner(
        scheduler_action=SchedulerAction(
            action="create_new",
            slot="explore_new",
            reason="clean_fork_required_for_new_mechanism",
        ),
        branch=branch,
        recorded_scheduler_results=recorded,
    )

    result = runner.run_one_step()

    assert result.action == "create_branch"
    assert result.decision is None
    assert result.branch_id == "new-branch"
    assert result.scheduler_slot == "explore_new"
    assert result.scheduler_reason == "clean_fork_required_for_new_mechanism"
    metadata = result.scheduler_audit_metadata
    assert metadata["scheduler_action"] == "create_new"
    assert metadata["pre_finalizer_scheduler_action"] == "create_new"
    assert metadata["pre_finalizer_scheduler_slot"] == "explore_new"
    assert metadata["scheduler_slot_semantics"] == (
        "pre_finalizer_scheduler_preference"
    )
    assert metadata["actual_branch_action"] == "explore_new_clean_fork"
    assert metadata["post_finalizer_actual_branch_action"] == (
        "explore_new_clean_fork"
    )
    assert metadata["post_finalizer_next_proposal_policy"] == "clean_fork_selected"
    assert metadata["clean_fork_selected"] is True
    assert metadata["same_branch_refinement_not_selected_reason"] == (
        "clean_fork_required_for_new_mechanism"
    )
    justification = metadata["same_mechanism_clean_fork_justification"]
    assert justification == {
        "reason": "new_mechanism_requires_clean_fork",
        "selected_policy": "clean_fork_selected",
        "clean_fork_reason": "clean_fork_required_for_new_mechanism",
        "same_branch_refinement_not_selected_reason": (
            "clean_fork_required_for_new_mechanism"
        ),
        "active_branch_cap_context": {
            "scheduler_slot": "explore_new",
            "scheduler_reason": "clean_fork_required_for_new_mechanism",
            "pre_finalizer_scheduler_action": "create_new",
        },
    }
    assert "improve the same branch" not in result.reason
    assert recorded == [result]


def test_clean_fork_selected_instead_of_same_branch_has_explicit_justification() -> None:
    branch = _branch("sibling-branch")
    runner = _runner(
        scheduler_action=SchedulerAction(
            action="create_new",
            slot="explore_new",
            reason="new_exploration_slot_available",
        ),
        branch=branch,
    )

    result = runner.run_one_step()

    justification = result.scheduler_audit_metadata[
        "same_mechanism_clean_fork_justification"
    ]
    assert result.action == "create_branch"
    assert result.decision is None
    assert justification["reason"] == "clean_fork_selected_instead_of_same_branch"
    assert justification["selected_policy"] == "clean_fork_selected"
    assert justification["clean_fork_reason"] == "new_exploration_slot_available"
    assert justification["same_branch_refinement_not_selected_reason"] == (
        "new_exploration_slot_available"
    )


def test_scheduler_action_audit_metadata_reaches_result() -> None:
    branch = _branch("weak-positive-branch")
    runner = _runner(
        scheduler_action=SchedulerAction(
            action="run_existing",
            branch=branch,
            slot="exploit_weak_positive",
            reason="weak_positive_signal_followup",
            audit_metadata={
                "runtime_evidence_clean_fork_suppression": (
                    "weak_positive_exception"
                ),
                "runtime_evidence_clean_fork_reason": (
                    "runtime_evidence_completeness_clean_fork"
                ),
                "runtime_evidence_pressure_count": 2,
                "case_wins": 1,
                "case_losses": 0,
            },
        ),
        branch=branch,
    )

    result = runner.run_one_step()

    metadata = result.scheduler_audit_metadata
    assert metadata["runtime_evidence_clean_fork_suppression"] == (
        "weak_positive_exception"
    )
    assert metadata["runtime_evidence_clean_fork_reason"] == (
        "runtime_evidence_completeness_clean_fork"
    )
    assert metadata["runtime_evidence_pressure_count"] == 2
    assert metadata["case_wins"] == 1
    assert metadata["case_losses"] == 0
    assert metadata["scheduler_action"] == "run_existing"


def test_clean_fork_reclaims_low_value_slot_before_create_new() -> None:
    champion = _champion()
    controller = BranchController()
    stale_low_signal = controller.create_branch(champion)
    stale_low_signal.direction = "solver: no-effect follow-up"
    stale_low_signal.branch_code_status = "active_no_effect"
    stale_low_signal.last_screening_feedback_tier = "no_effect"
    stale_low_signal.branch_mechanism_ids = ("probe",)
    recorded: list[StepResult] = []
    saved: list[tuple[str, BranchState]] = []

    def save_branch(branch: Branch) -> None:
        saved.append((branch.branch_id, branch.state))

    runner = BranchStepRunner(
        branch_controller=controller,
        scheduler=Scheduler(max_active_branches=1),
        champion_lock=nullcontext(),
        get_champion=lambda: champion,
        branch_store=SimpleNamespace(save=save_branch),
        branch_workspaces={},
        branch_hypotheses={},
        branch_patches={},
        branch_current_hypothesis={},
        experiment_protocol_provider=lambda: None,
        contract_gate=None,
        verification_gate=None,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        tick_blocked_branches=lambda: None,
        persist_branch_state=lambda branch_id: save_branch(
            controller.get_branch(branch_id)
        ),
        record_hard_abandon=lambda branch_id, reason: None,
        setup_workspace=lambda *args, **kwargs: None,
        apply_patch=lambda *args, **kwargs: None,
        record_verification_pass=lambda branch, code_hash: None,
        evaluate=lambda branch, workspace, hypothesis: None,
        apply_decision_and_finalize=lambda **kwargs: StepResult(action="explore"),
        record_step=lambda step: None,
        decision_reason_codes_for=lambda branch_id, protocol_result: None,
        run_explore_step=lambda branch: StepResult(
            action="explore",
            branch_id=branch.branch_id,
            reason="screening complete",
        ),
        run_eval_step_callback=lambda branch: StepResult(action="validate"),
        run_reconcile_step_callback=lambda branch: StepResult(action="reconcile"),
        increment_round=lambda: 1,
        increment_rounds_since_last_promote=lambda: None,
        hypothesis_store=None,
        record_scheduler_result=recorded.append,
    )

    result = runner.run_one_step()
    inventory = active_slot_inventory(
        controller.get_reportable_branches(),
        max_active_branches=1,
    )

    assert result.action == "create_branch"
    assert result.branch_id != stale_low_signal.branch_id
    assert stale_low_signal.state == BranchState.PARKED_LINEAGE
    assert inventory["used"] == 1
    assert inventory["parked_lineage_ids"] == [stale_low_signal.branch_id]
    assert len(controller.get_reportable_branches()) == 2
    assert saved[0] == (stale_low_signal.branch_id, BranchState.PARKED_LINEAGE)
    lifecycle_codes = stale_low_signal.last_branch_lifecycle_policy_block[
        "lifecycle_action_reason_codes"
    ]
    assert lifecycle_codes == [BRANCH_LIFECYCLE_PARK_LINEAGE]
    assert ACTIVE_SLOT_RECLAIMED_FOR_NEW_BRANCH not in lifecycle_codes
    assert result.scheduler_audit_metadata["active_slot_reconciliation"][
        "mode"
    ] == "new_branch_reclaim"
    assert recorded == [result]


def test_run_existing_scheduler_metadata_reaches_result_and_callback() -> None:
    branch = _branch("existing-branch")
    recorded: list[StepResult] = []
    runner = _runner(
        scheduler_action=SchedulerAction(
            action="run_existing",
            branch=branch,
            slot="refine_active",
            reason="existing_branch_selected",
        ),
        branch=branch,
        recorded_scheduler_results=recorded,
    )

    result = runner.run_one_step()

    assert result.action == "explore"
    assert result.branch_id == "existing-branch"
    assert result.scheduler_slot == "refine_active"
    assert result.scheduler_reason == "existing_branch_selected"
    metadata = result.scheduler_audit_metadata
    assert metadata["scheduler_action"] == "run_existing"
    assert metadata["pre_finalizer_scheduler_action"] == "run_existing"
    assert metadata["pre_finalizer_scheduler_slot"] == "refine_active"
    assert metadata["pre_finalizer_selected_branch_id"] == "existing-branch"
    assert metadata["scheduler_slot_semantics"] == (
        "pre_finalizer_scheduler_preference"
    )
    assert metadata["actual_branch_action"] == "continue_same_branch"
    assert metadata["post_finalizer_actual_branch_action"] == "continue_same_branch"
    assert metadata["post_finalizer_next_proposal_policy"] == (
        "same_branch_eligible"
    )
    assert metadata["post_finalizer_branch_id"] == "existing-branch"
    assert metadata["post_finalizer_branch_state"] == "explore"
    assert metadata["post_finalizer_counts_toward_active_slots"] is True
    assert metadata["same_branch_refinement_selected"] is True
    assert metadata["pre_finalizer_same_branch_refinement_selected"] is True
    assert metadata["same_mechanism_clean_fork_justification"] == {
        "reason": "not_applicable",
        "selected_policy": "same_branch_eligible",
        "clean_fork_reason": "",
        "same_branch_refinement_not_selected_reason": "",
        "active_branch_cap_context": {
            "scheduler_slot": "refine_active",
            "scheduler_reason": "existing_branch_selected",
            "pre_finalizer_scheduler_action": "run_existing",
        },
    }
    assert metadata["post_refine_decision_reason"] == "screening complete"
    assert recorded == [result]


def test_parked_lineage_records_post_finalizer_release_not_continue_same_branch() -> None:
    branch = _branch("parked-after-refine")
    branch.best_quality_checkpoint_id = "checkpoint-best"
    branch.last_valid_checkpoint_id = "checkpoint-best"
    recorded: list[StepResult] = []

    def park_lineage(selected: Branch) -> StepResult:
        selected.state = BranchState.PARKED_LINEAGE
        selected.branch_code_status = "parked_lineage"
        selected.last_branch_lifecycle_policy_block = {
            "lifecycle_action_reason_codes": [
                BRANCH_LIFECYCLE_PARK_LINEAGE,
                BRANCH_LIFECYCLE_RETAIN_CHECKPOINT,
            ],
        }
        return StepResult(
            action="explore",
            branch_id=selected.branch_id,
            reason="CONTINUE_EXPLORE: park_lineage; improve the same branch",
        )

    runner = _runner(
        scheduler_action=SchedulerAction(
            action="run_existing",
            branch=branch,
            slot="refine_active",
            reason="active_branch_refinement",
        ),
        branch=branch,
        recorded_scheduler_results=recorded,
        run_explore_step=park_lineage,
    )

    result = runner.run_one_step()
    metadata = result.scheduler_audit_metadata
    next_selection = Scheduler(max_active_branches=3).select_next([branch])

    assert metadata["pre_finalizer_scheduler_slot"] == "refine_active"
    assert metadata["pre_finalizer_selected_branch_id"] == "parked-after-refine"
    assert metadata["scheduler_slot_semantics"] == (
        "pre_finalizer_scheduler_preference"
    )
    assert metadata["actual_branch_action"] == "parked_lineage_released"
    assert metadata["post_finalizer_actual_branch_action"] == (
        "parked_lineage_released"
    )
    assert metadata["post_finalizer_actual_branch_action"] != (
        "continue_same_branch"
    )
    assert metadata["same_branch_refinement_selected"] is False
    assert metadata["pre_finalizer_same_branch_refinement_selected"] is True
    assert metadata["post_finalizer_lifecycle_action"] == "park_lineage"
    assert metadata["post_finalizer_active_slot_release_reason"] == "parked_lineage"
    assert metadata["post_finalizer_counts_toward_active_slots"] is False
    assert metadata["post_finalizer_next_proposal_policy"] == (
        "clean_fork_or_other_branch_required"
    )
    assert "release the branch slot" in result.reason
    assert next_selection.action == "create_new"
    assert next_selection.branch is None
    assert recorded == [result]


def test_same_branch_repair_soft_abandon_metadata_and_reason_are_aligned() -> None:
    branch = _branch("repair-branch")
    recorded: list[StepResult] = []
    runner = _runner(
        scheduler_action=SchedulerAction(
            action="run_existing",
            branch=branch,
            slot="repair_diagnostic",
            reason="effect_diagnostic_followup",
        ),
        branch=branch,
        recorded_scheduler_results=recorded,
        explore_result=StepResult(
            action="soft_abandon",
            branch_id="repair-branch",
            reason=(
                "CONTINUE_EXPLORE: weak-positive screening signal; "
                "improve the same branch"
            ),
        ),
    )

    result = runner.run_one_step()

    assert result.action == "soft_abandon"
    assert result.branch_id == "repair-branch"
    assert "repair/refine the same branch" in result.reason
    assert "improve the same branch" not in result.reason
    metadata = result.scheduler_audit_metadata
    assert metadata["scheduler_action"] == "run_existing"
    assert metadata["pre_finalizer_scheduler_slot"] == "repair_diagnostic"
    assert metadata["actual_branch_action"] == "soft_abandon"
    assert metadata["post_finalizer_actual_branch_action"] == "soft_abandon"
    assert metadata["post_finalizer_next_proposal_policy"] == (
        "same_branch_not_selected"
    )
    assert metadata["same_branch_refinement_selected"] is False
    assert metadata["pre_finalizer_same_branch_refinement_selected"] is True
    assert metadata["post_refine_abandon_reason"] == (
        "CONTINUE_EXPLORE: weak-positive screening signal; "
        "repair/refine the same branch"
    )
    assert recorded == [result]


def test_at_capacity_scheduler_metadata_reaches_result_and_callback() -> None:
    recorded: list[StepResult] = []
    runner = _runner(
        scheduler_action=SchedulerAction(
            action="at_capacity",
            slot="capacity_blocked",
            reason="active_branch_limit_reached",
        ),
        recorded_scheduler_results=recorded,
    )

    result = runner.run_one_step()

    assert result.action == "skip"
    assert result.branch_id is None
    assert result.scheduler_slot == "capacity_blocked"
    assert result.scheduler_reason == "active_branch_limit_reached"
    assert result.scheduler_audit_metadata[
        "same_mechanism_clean_fork_justification"
    ] == {
        "reason": "not_applicable",
        "selected_policy": "at_capacity",
        "clean_fork_reason": "",
        "same_branch_refinement_not_selected_reason": "",
        "active_branch_cap_context": {
            "scheduler_slot": "capacity_blocked",
            "scheduler_reason": "active_branch_limit_reached",
            "pre_finalizer_scheduler_action": "at_capacity",
        },
    }
    assert recorded == [result]
