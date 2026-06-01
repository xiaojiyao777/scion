from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

from scion.core.branch import BranchController
from scion.core.branch_step_runner import BranchStepRunner
from scion.core.models import Branch, BranchState, ChampionState
from scion.core.scheduler import Scheduler, SchedulerAction, active_slot_inventory
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
        run_explore_step=lambda branch: selected_explore_result,
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
    assert result.branch_id == "new-branch"
    assert result.scheduler_slot == "explore_new"
    assert result.scheduler_reason == "clean_fork_required_for_new_mechanism"
    assert result.scheduler_audit_metadata == {
        "actual_branch_action": "explore_new_clean_fork",
        "clean_fork_reason": "clean_fork_required_for_new_mechanism",
        "clean_fork_selected": True,
        "same_branch_refinement_not_selected_reason": (
            "clean_fork_required_for_new_mechanism"
        ),
        "scheduler_action": "create_new",
        "scheduler_reason": "clean_fork_required_for_new_mechanism",
        "scheduler_slot": "explore_new",
    }
    assert "improve the same branch" not in result.reason
    assert recorded == [result]


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
    assert result.scheduler_audit_metadata == {
        "actual_branch_action": "continue_same_branch",
        "post_refine_decision_reason": "screening complete",
        "refined_branch_id": "existing-branch",
        "same_branch_refinement_selected": True,
        "scheduler_action": "run_existing",
        "scheduler_reason": "existing_branch_selected",
        "scheduler_slot": "refine_active",
    }
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
    assert result.scheduler_audit_metadata == {
        "actual_branch_action": "soft_abandon",
        "post_refine_abandon_reason": (
            "CONTINUE_EXPLORE: weak-positive screening signal; "
            "repair/refine the same branch"
        ),
        "refined_branch_id": "repair-branch",
        "same_branch_refinement_selected": True,
        "scheduler_action": "run_existing",
        "scheduler_reason": "effect_diagnostic_followup",
        "scheduler_slot": "repair_diagnostic",
    }
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
    assert recorded == [result]
