"""Scheduler dispatch preserves direct branch execution behavior."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timedelta

from scion.core.branch import BranchController
from scion.core.branch_step_runner import BranchStepRunner
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import Branch, BranchState, ChampionState
from scion.core.scheduler import Scheduler, SchedulerAction
from scion.core.step_result import StepResult


class _FixedScheduler:
    max_active_branches = 1

    def __init__(self, action: SchedulerAction) -> None:
        self.action = action

    def select_next(self, _branches):
        return self.action


def _runner(action: SchedulerAction) -> BranchStepRunner:
    controller = BranchController()
    champion = ChampionState(
        version=1,
        operator_pool={},
        code_snapshot_path="/tmp/champion",
    )
    return BranchStepRunner(
        branch_controller=controller,
        scheduler=_FixedScheduler(action),  # type: ignore[arg-type]
        champion_lock=nullcontext(),
        get_champion=lambda: champion,
        branch_workspaces={},
        branch_patches={},
        experiment_protocol_provider=lambda: None,
        contract_gate=None,
        verification_gate=None,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        setup_workspace=lambda *_args, **_kwargs: None,
        evaluate=lambda *_args: None,  # type: ignore[arg-type]
        apply_decision_and_finalize=lambda **_kwargs: StepResult(action="explore"),
        record_step=lambda _step: None,
        run_explore_step=lambda branch: StepResult(
            action="explore",
            branch_id=branch.branch_id,
            execution_outcome=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.NOT_EVALUATED,
                reason_code="TEST",
            ),
        ),
        run_eval_step_callback=lambda branch: StepResult(
            action="evaluate", branch_id=branch.branch_id
        ),
        run_reconcile_step_callback=lambda branch: StepResult(
            action="reconcile", branch_id=branch.branch_id
        ),
        increment_round=lambda: 1,
    )


def test_create_new_returns_research_result_without_scheduler_projection() -> None:
    result = _runner(
        SchedulerAction(
            action="create_new",
            slot="explore_new",
            reason="active_slot_available",
        )
    ).run_one_step()
    assert result.action == "create_branch"


def test_capacity_returns_typed_non_evaluated_outcome() -> None:
    result = _runner(
        SchedulerAction(
            action="at_capacity",
            slot="capacity_blocked",
            reason="active_branch_limit_reached",
        )
    ).run_one_step()
    assert result.action == "skip"
    assert result.execution_outcome is not None
    assert result.execution_outcome.reason_code == "SCHEDULER_CAPACITY_BLOCKED"


def test_existing_explore_service_time_is_updated_before_research_call() -> None:
    branch = Branch(
        branch_id="served-explore",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )
    observed: list[datetime] = []
    runner = _runner(
        SchedulerAction(
            action="run_existing",
            branch=branch,
            reason="state_priority_explore_least_recently_served",
        )
    )
    runner.branch_controller._branches[branch.branch_id] = branch
    runner.run_explore_step = lambda selected: (
        observed.append(selected.updated_at)
        or StepResult(action="explore", branch_id=selected.branch_id)
    )

    runner.run_one_step()

    assert branch.updated_at > datetime(2026, 1, 1)
    assert observed == [branch.updated_at]


def test_three_explore_research_rejections_rotate_without_starvation() -> None:
    start = datetime(2026, 1, 1)
    branches = [
        Branch(
            branch_id=f"branch-{index}",
            state=BranchState.EXPLORE,
            base_champion_id=1,
            created_at=start + timedelta(seconds=index),
            updated_at=start + timedelta(seconds=index),
        )
        for index in range(3)
    ]
    served: list[str] = []
    runner = _runner(SchedulerAction(action="at_capacity"))
    runner.scheduler = Scheduler(max_active_branches=3)
    for branch in branches:
        runner.branch_controller._branches[branch.branch_id] = branch
    runner.run_explore_step = lambda selected: (
        served.append(selected.branch_id)
        or StepResult(
            action="research_rejected",
            branch_id=selected.branch_id,
            execution_outcome=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.RESEARCH_REJECTED,
                reason_code="TEST_RESEARCH_REJECTED",
            ),
        )
    )

    for _ in branches:
        runner.run_one_step()

    assert served == ["branch-0", "branch-1", "branch-2"]
