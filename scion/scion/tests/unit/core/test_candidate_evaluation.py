from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

from scion.core.branch import BranchController
from scion.core.branch_step_runner import BranchStepRunner
from scion.core.candidate_evaluation import (
    candidate_evaluation,
    candidate_evaluation_kind,
    candidate_evaluation_pending,
    mark_candidate_evaluation_completed,
    mark_candidate_evaluation_pending,
)
from scion.core.models import Branch, BranchState
from scion.core.scheduler import SchedulerAction
from scion.core.step_result import StepResult


def _branch() -> Branch:
    return Branch(
        branch_id="branch-1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-1",
    )


def test_pending_marker_preserves_kind_and_hypothesis_identity() -> None:
    branch = _branch()

    mark_candidate_evaluation_pending(
        branch,
        hypothesis_id="hypothesis-1",
        kind="reconcile",
    )

    assert candidate_evaluation_pending(branch) is True
    assert candidate_evaluation_kind(branch) == "reconcile"
    assert candidate_evaluation(branch) == {
        "status": "pending",
        "hypothesis_id": "hypothesis-1",
        "kind": "reconcile",
    }


def test_completed_marker_keeps_candidate_kind_for_evaluation_accounting() -> None:
    branch = _branch()
    mark_candidate_evaluation_pending(
        branch,
        hypothesis_id="hypothesis-1",
        kind="explore",
    )

    mark_candidate_evaluation_completed(branch)

    assert candidate_evaluation_pending(branch) is False
    assert candidate_evaluation_kind(branch) == "explore"
    assert candidate_evaluation(branch) == {
        "status": "completed",
        "hypothesis_id": "hypothesis-1",
        "kind": "explore",
    }


def test_runner_dispatches_plain_pending_reconcile_to_eval_callback() -> None:
    branch = _branch()
    mark_candidate_evaluation_pending(
        branch,
        hypothesis_id="hypothesis-1",
        kind="reconcile",
    )
    controller = BranchController()
    controller.restore_branch(branch)
    callbacks: list[str] = []
    runner = BranchStepRunner(
        branch_controller=controller,
        scheduler=SimpleNamespace(
            select_next=lambda _active: SchedulerAction(
                action="run_existing", branch=branch
            )
        ),
        champion_lock=nullcontext(),
        get_champion=lambda: SimpleNamespace(),
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
        evaluate=lambda *_args: None,
        apply_decision_and_finalize=lambda **_kwargs: StepResult(action="reconcile"),
        record_step=lambda _step: None,
        decision_reason_codes_for=lambda *_args: None,
        run_explore_step=lambda _branch: StepResult(action="explore"),
        run_eval_step_callback=lambda _branch: (
            callbacks.append("eval") or StepResult(action="reconcile")
        ),
        run_reconcile_step_callback=lambda _branch: StepResult(action="reconcile"),
        increment_round=lambda: 1,
        hypothesis_store=SimpleNamespace(),
    )

    result = runner.run_one_step()

    assert callbacks == ["eval"]
    assert result.action == "reconcile"
