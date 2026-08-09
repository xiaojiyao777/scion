"""Scheduler metadata stays observational at the branch-step boundary."""
from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timedelta
from types import SimpleNamespace

from scion.core.branch import BranchController
from scion.core.branch_step_runner import BranchStepRunner
from scion.core.execution_outcome import ExecutionOutcome
from scion.core.models import Branch, BranchState, ChampionState
from scion.core.scheduler import Scheduler, SchedulerAction
from scion.core.step_result import StepResult


class _FixedScheduler:
    max_active_branches = 1

    def __init__(self, action: SchedulerAction) -> None:
        self.action = action

    def select_next(self, _branches):
        return self.action


def _runner(action: SchedulerAction, recorded: list[StepResult]) -> BranchStepRunner:
    controller = BranchController()
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="solver",
        code_snapshot_path="/tmp/champion",
        code_snapshot_hash="champion",
    )
    return BranchStepRunner(
        branch_controller=controller,
        scheduler=_FixedScheduler(action),  # type: ignore[arg-type]
        champion_lock=nullcontext(),
        get_champion=lambda: champion,
        branch_store=SimpleNamespace(save=lambda _branch: None),
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
        persist_branch_state=lambda _branch_id: None,
        setup_workspace=lambda *_args, **_kwargs: None,
        apply_patch=lambda *_args, **_kwargs: None,
        evaluate=lambda *_args: None,  # type: ignore[arg-type]
        apply_decision_and_finalize=lambda **_kwargs: StepResult(action="explore"),
        record_step=lambda _step: None,
        decision_reason_codes_for=lambda *_args: None,
        run_explore_step=lambda branch: StepResult(
            action="explore",
            branch_id=branch.branch_id,
            attempt_kind="other",
            execution_outcome=ExecutionOutcome.NOT_EVALUATED,
            execution_outcome_reason_code="TEST",
        ),
        run_eval_step_callback=lambda branch: StepResult(
            action="evaluate", branch_id=branch.branch_id
        ),
        run_reconcile_step_callback=lambda branch: StepResult(
            action="reconcile", branch_id=branch.branch_id
        ),
        increment_round=lambda: 1,
        hypothesis_store=None,
        record_scheduler_result=recorded.append,
    )


def test_create_new_metadata_has_only_scheduler_facts() -> None:
    recorded: list[StepResult] = []
    result = _runner(
        SchedulerAction(
            action="create_new",
            slot="explore_new",
            reason="active_slot_available",
        ),
        recorded,
    ).run_one_step()
    assert result.action == "create_branch"
    assert result.scheduler_slot == "explore_new"
    assert result.scheduler_reason == "active_slot_available"
    assert result.scheduler_audit_metadata == {
        "scheduler_action": "create_new",
        "pre_finalizer_scheduler_action": "create_new",
        "scheduler_slot": "explore_new",
        "pre_finalizer_scheduler_slot": "explore_new",
        "scheduler_reason": "active_slot_available",
        "pre_finalizer_scheduler_reason": "active_slot_available",
        "scheduler_semantics": "state_priority_fifo_explore_least_recently_served",
    }
    assert recorded == [result]


def test_capacity_metadata_does_not_mutate_or_advise() -> None:
    recorded: list[StepResult] = []
    result = _runner(
        SchedulerAction(
            action="at_capacity",
            slot="capacity_blocked",
            reason="active_branch_limit_reached",
        ),
        recorded,
    ).run_one_step()
    assert result.action == "skip"
    assert not hasattr(result, "counts_toward_max_rounds")
    assert result.scheduler_audit_metadata["scheduler_semantics"] == (
        "state_priority_fifo_explore_least_recently_served"
    )
    assert "clean_fork" not in str(result.scheduler_audit_metadata)
    assert "repair" not in str(result.scheduler_audit_metadata)


def test_existing_explore_service_time_is_persisted_before_research_call() -> None:
    branch = Branch(
        branch_id="served-explore",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )
    observed: list[tuple[datetime, list[str]]] = []
    persisted: list[str] = []
    runner = _runner(
        SchedulerAction(
            action="run_existing",
            branch=branch,
            reason="state_priority_explore_least_recently_served",
        ),
        [],
    )
    runner.branch_controller.restore_branch(branch)
    runner.persist_branch_state = persisted.append
    runner.run_explore_step = lambda selected: (
        observed.append((selected.updated_at, list(persisted)))
        or StepResult(action="explore", branch_id=selected.branch_id)
    )

    runner.run_one_step()

    assert branch.updated_at > datetime(2026, 1, 1)
    assert observed == [(branch.updated_at, [branch.branch_id])]


def test_three_explore_research_rejections_rotate_without_starvation() -> None:
    start = datetime(2026, 1, 1)
    branches = [
        Branch(
            branch_id=f"branch-{index}",
            state=BranchState.EXPLORE,
            base_champion_id=1,
            base_champion_hash="champion",
            created_at=start + timedelta(seconds=index),
            updated_at=start + timedelta(seconds=index),
        )
        for index in range(3)
    ]
    served: list[str] = []
    runner = _runner(SchedulerAction(action="at_capacity"), [])
    runner.scheduler = Scheduler(max_active_branches=3)
    for branch in branches:
        runner.branch_controller.restore_branch(branch)
    runner.run_explore_step = lambda selected: (
        served.append(selected.branch_id)
        or StepResult(
            action="research_rejected",
            branch_id=selected.branch_id,
            execution_outcome=ExecutionOutcome.RESEARCH_REJECTED,
            execution_outcome_reason_code="TEST_RESEARCH_REJECTED",
        )
    )

    for _ in branches:
        runner.run_one_step()

    assert served == ["branch-0", "branch-1", "branch-2"]
