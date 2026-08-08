"""Scheduler metadata stays observational at the branch-step boundary."""
from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

from scion.core.branch import BranchController
from scion.core.branch_step_runner import BranchStepRunner
from scion.core.execution_outcome import ExecutionOutcome
from scion.core.models import ChampionState
from scion.core.scheduler import SchedulerAction
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
        "scheduler_semantics": "state_priority_fifo",
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
    assert result.scheduler_audit_metadata["scheduler_semantics"] == "state_priority_fifo"
    assert "clean_fork" not in str(result.scheduler_audit_metadata)
    assert "repair" not in str(result.scheduler_audit_metadata)
