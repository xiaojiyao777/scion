from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

from scion.core.branch_step_runner import BranchStepRunner
from scion.core.models import Branch, BranchState
from scion.core.scheduler import (
    PREPARED_SUCCESSOR_FOCUS_CLEAN_FORK_REASON,
    Scheduler,
)
from scion.core.step_result import StepResult


def _branch(branch_id: str) -> Branch:
    return Branch(
        branch_id=branch_id,
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
    )


def test_branch_step_runner_passes_launch_focus_to_scheduler_clean_fork():
    reviewed = _branch("reviewed-branch")
    reviewed.branch_code_status = "active_no_effect"
    reviewed.branch_mechanism_ids = ("reviewed_mechanism",)
    created = _branch("created-branch")
    saved: list[str] = []
    recorded: list[StepResult] = []

    branch_controller = SimpleNamespace(
        get_active_branches=lambda: [reviewed],
        create_branch=lambda champion: created,
        get_branch=lambda branch_id: created if branch_id == created.branch_id else reviewed,
        schedule_branch=lambda branch_id: None,
        apply_decision=lambda branch_id, decision: None,
    )
    runner = BranchStepRunner(
        branch_controller=branch_controller,
        scheduler=Scheduler(max_active_branches=3),
        champion_lock=nullcontext(),
        get_champion=lambda: SimpleNamespace(version=1),
        branch_store=SimpleNamespace(save=lambda branch: saved.append(branch.branch_id)),
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
        launch_research_focus_provider=lambda: {
            "required_mechanism_ids": [],
            "reviewed_mechanism_ids": ["reviewed_mechanism"],
            "successor_opportunity_families": ["successor_family"],
        },
    )

    result = runner.run_one_step()

    assert result.action == "create_branch"
    assert result.branch_id == "created-branch"
    assert result.scheduler_reason == PREPARED_SUCCESSOR_FOCUS_CLEAN_FORK_REASON
    assert result.scheduler_audit_metadata["clean_fork_selected"] is True
    assert saved == ["created-branch"]
    assert recorded[-1].scheduler_reason == PREPARED_SUCCESSOR_FOCUS_CLEAN_FORK_REASON


def test_branch_step_runner_blocks_capacity_without_reviewed_expand_eval():
    blocked_a = _branch("blocked-a")
    blocked_a.state = BranchState.BLOCKED_INFRA
    blocked_b = _branch("blocked-b")
    blocked_b.state = BranchState.BLOCKED_INFRA
    reviewed = _branch("reviewed-expand")
    reviewed.state = BranchState.EXPLORE_EXPAND
    reviewed.branch_code_status = "clean"
    reviewed.last_screening_feedback_tier = "marginal"
    reviewed.branch_mechanism_ids = ("reviewed_mechanism",)
    branches = {
        branch.branch_id: branch
        for branch in (blocked_a, blocked_b, reviewed)
    }
    recorded: list[StepResult] = []
    eval_calls: list[str] = []

    def active_branches() -> list[Branch]:
        return [
            branch
            for branch in branches.values()
            if branch.state
            not in {
                BranchState.ABANDONED,
                BranchState.PARKED_LINEAGE,
                BranchState.PROMOTED,
            }
        ]

    branch_controller = SimpleNamespace(
        get_active_branches=active_branches,
        create_branch=lambda champion: (_ for _ in ()).throw(
            AssertionError("capacity-blocked selection must not create a branch")
        ),
        get_branch=lambda branch_id: branches[branch_id],
        schedule_branch=lambda branch_id: None,
        apply_decision=lambda branch_id, decision: None,
    )
    runner = BranchStepRunner(
        branch_controller=branch_controller,
        scheduler=Scheduler(max_active_branches=3),
        champion_lock=nullcontext(),
        get_champion=lambda: SimpleNamespace(version=1),
        branch_store=SimpleNamespace(save=lambda branch: None),
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
        run_explore_step=lambda branch: StepResult(
            action="explore",
            branch_id=branch.branch_id,
            reason="screening complete",
        ),
        run_eval_step_callback=lambda branch: (
            eval_calls.append(branch.branch_id)
            or StepResult(action="validate", branch_id=branch.branch_id)
        ),
        run_reconcile_step_callback=lambda branch: StepResult(action="reconcile"),
        increment_round=lambda: 1,
        increment_rounds_since_last_promote=lambda: None,
        hypothesis_store=None,
        record_scheduler_result=recorded.append,
        launch_research_focus_provider=lambda: {
            "required_mechanism_ids": [],
            "reviewed_mechanism_ids": ["reviewed_mechanism"],
            "successor_opportunity_families": ["successor_family"],
        },
    )

    result = runner.run_one_step()

    assert result.action == "skip"
    assert result.reason == "max_active_branches reached"
    assert result.scheduler_reason == "active_branch_limit_reached"
    assert eval_calls == []
    focus_audit = result.scheduler_audit_metadata["prepared_successor_focus"]
    assert focus_audit["excluded_branch_ids"] == ["reviewed-expand"]
    assert result.scheduler_audit_metadata["active_slot_hard_cap"][
        "reason"
    ] == "active_slot_hard_cap_blocked"
    assert recorded[-1].scheduler_reason == "active_branch_limit_reached"
