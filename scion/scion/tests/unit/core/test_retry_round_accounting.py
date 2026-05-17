from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from scion.core.campaign_loop import CampaignLoop
from scion.core.explore_step_pipeline import ExploreStepPipeline
from scion.core.models import (
    Branch,
    BranchState,
    CheckResult,
    ContractResult,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    StepRecord,
)
from scion.core.step_result import StepResult


def _hypothesis() -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text="Try a bounded local search variant.",
        change_locus="local_search",
        action="modify",
        target_file="operators/local_search.py",
    )


def _hypothesis_record(branch_id: str) -> HypothesisRecord:
    return HypothesisRecord(
        hypothesis_id="hyp-1",
        branch_id=branch_id,
        change_locus="local_search",
        action="modify",
        status="active",
        target_file="operators/local_search.py",
        hypothesis_text="Try a bounded local search variant.",
    )


class _ContractGate:
    def validate_hypothesis(self, *args: Any, **kwargs: Any) -> ContractResult:
        return ContractResult(
            passed=True,
            checks=(CheckResult("C", True, "light", "ok", 0),),
        )

    def validate_patch(self, *args: Any, **kwargs: Any) -> ContractResult:
        return ContractResult(
            passed=True,
            checks=(CheckResult("P", True, "light", "ok", 0),),
        )


class _HypothesisStore:
    def __init__(self) -> None:
        self.saved: list[HypothesisRecord] = []
        self.statuses: list[tuple[str, str]] = []

    def get_by_status(self, status: str) -> list[HypothesisRecord]:
        return []

    def save(self, record: HypothesisRecord) -> None:
        self.saved.append(record)

    def mark_status(self, hypothesis_id: str, status: str) -> None:
        self.statuses.append((hypothesis_id, status))


def _pipeline(
    *,
    pending: dict[str, tuple[HypothesisProposal, HypothesisRecord, str]] | None = None,
    increment_round,
    increment_rounds_since_last_promote,
    get_current_round=lambda: 0,
    generate_hypothesis,
    generate_code,
    record_step,
) -> ExploreStepPipeline:
    store = _HypothesisStore()
    pipeline = ExploreStepPipeline(
        branch_controller=SimpleNamespace(),
        contract_gate=_ContractGate(),
        verification_gate=None,
        hypothesis_store=store,
        registry=SimpleNamespace(),
        campaign_id="campaign",
        get_champion=lambda: None,
        pending_hypotheses=pending if pending is not None else {},
        branch_hypotheses={},
        branch_patches={},
        branch_current_hypothesis={},
        branch_workspaces={},
        failure_streak={},
        increment_round=increment_round,
        increment_rounds_since_last_promote=increment_rounds_since_last_promote,
        generate_hypothesis=generate_hypothesis,
        generate_code=generate_code,
        attempt_fix=lambda branch, patch, vresult: None,
        handle_failure=lambda *args, **kwargs: None,
        record_step=record_step,
        setup_workspace=lambda branch: None,
        apply_patch=lambda *args, **kwargs: None,
        record_verification_pass=lambda branch, code_hash: None,
        archive_failed_workspace=lambda workspace, branch_id, round_num: None,
        evaluate=lambda branch, workspace, hypothesis: None,
        apply_decision_and_finalize=lambda **kwargs: None,
        decision_reason_codes_for=lambda branch_id, protocol_result: None,
        proposal_failure_detail_for=lambda branch_id: "forced code failure",
        proposal_session_ref_for=lambda branch_id: {"session_id": "s1"},
        get_current_round=get_current_round,
    )
    pipeline._test_store = store
    return pipeline


def test_pending_code_retry_does_not_increment_exploration_round() -> None:
    branch = Branch("b1", BranchState.EXPLORE, 1, "champ")
    hypothesis = _hypothesis()
    record = _hypothesis_record(branch.branch_id)
    pending = {
        branch.branch_id: (hypothesis, record, "initial code generation failed"),
    }
    steps: list[StepRecord] = []
    round_calls = 0
    idle_calls = 0

    def increment_round() -> int:
        nonlocal round_calls
        round_calls += 1
        return 99

    def increment_rounds_since_last_promote() -> None:
        nonlocal idle_calls
        idle_calls += 1

    pipeline = _pipeline(
        pending=pending,
        increment_round=increment_round,
        increment_rounds_since_last_promote=increment_rounds_since_last_promote,
        get_current_round=lambda: 7,
        generate_hypothesis=lambda branch: (_ for _ in ()).throw(
            AssertionError("pending retry must not generate a new hypothesis")
        ),
        generate_code=lambda branch, hypothesis, prior_failure=None: None,
        record_step=steps.append,
    )

    pipeline.run(branch)

    assert round_calls == 0
    assert idle_calls == 0
    assert pending == {}
    assert steps[0].round_num == 7
    assert steps[0].failure_stage == "code_generation"
    assert steps[0].proposal_session_ref == {
        "session_id": "s1",
        "retry_attempt": True,
        "retry_prior_failure": "initial code generation failed",
    }
    assert steps[0].proposal_session_ref["retry_attempt"] is True
    assert pipeline._test_store.statuses == [("hyp-1", "rejected")]


def test_new_hypothesis_attempt_increments_exploration_round() -> None:
    branch = Branch("b1", BranchState.EXPLORE, 1, "champ")
    hypothesis = _hypothesis()
    record = _hypothesis_record(branch.branch_id)
    pending: dict[str, tuple[HypothesisProposal, HypothesisRecord, str]] = {}
    steps: list[StepRecord] = []
    round_calls = 0
    idle_calls = 0

    def increment_round() -> int:
        nonlocal round_calls
        round_calls += 1
        return round_calls

    def increment_rounds_since_last_promote() -> None:
        nonlocal idle_calls
        idle_calls += 1

    pipeline = _pipeline(
        pending=pending,
        increment_round=increment_round,
        increment_rounds_since_last_promote=increment_rounds_since_last_promote,
        generate_hypothesis=lambda branch: (hypothesis, record),
        generate_code=lambda branch, hypothesis, prior_failure=None: None,
        record_step=steps.append,
    )

    pipeline.run(branch)

    assert round_calls == 1
    assert idle_calls == 1
    assert steps[0].round_num == 1
    assert steps[0].proposal_session_ref == {"session_id": "s1"}
    assert pending[branch.branch_id] == (
        hypothesis,
        record,
        "forced code failure",
    )
    assert pipeline._test_store.statuses == [("hyp-1", "code_failed")]


def test_campaign_loop_does_not_count_retry_attempt_against_max_rounds() -> None:
    results = [
        StepResult(
            action="explore",
            branch_id="b1",
            reason="retry code generation failed",
            counts_toward_max_rounds=False,
        ),
        StepResult(action="explore", branch_id="b1", reason="new round failed"),
    ]
    calls = 0
    stopped_reasons: list[str | None] = []

    def run_one_step() -> StepResult:
        nonlocal calls
        result = results[calls]
        calls += 1
        return result

    loop = CampaignLoop(
        write_status=lambda **kwargs: stopped_reasons.append(
            kwargs.get("stopped_reason")
        )
        if "stopped_reason" in kwargs
        else None,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
    )

    loop.run(max_rounds=1)

    assert calls == 2
    assert "max_rounds_exhausted" in stopped_reasons
