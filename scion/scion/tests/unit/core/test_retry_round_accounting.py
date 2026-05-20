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
    Decision,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    VerificationResult,
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
    branch_controller=SimpleNamespace(),
    verification_gate=None,
    setup_workspace=lambda branch: None,
    apply_patch=lambda *args, **kwargs: None,
    record_verification_pass=lambda branch, code_hash: None,
    evaluate=lambda branch, workspace, hypothesis: None,
    apply_decision_and_finalize=lambda **kwargs: None,
    persist_branch_state=lambda branch_id: None,
) -> ExploreStepPipeline:
    store = _HypothesisStore()
    pipeline = ExploreStepPipeline(
        branch_controller=branch_controller,
        contract_gate=_ContractGate(),
        verification_gate=verification_gate,
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
        setup_workspace=setup_workspace,
        apply_patch=apply_patch,
        record_verification_pass=record_verification_pass,
        archive_failed_workspace=lambda workspace, branch_id, round_num: None,
        evaluate=evaluate,
        apply_decision_and_finalize=apply_decision_and_finalize,
        decision_reason_codes_for=lambda branch_id, protocol_result: None,
        proposal_failure_detail_for=lambda branch_id: "forced code failure",
        proposal_session_ref_for=lambda branch_id: {"session_id": "s1"},
        get_current_round=get_current_round,
        persist_branch_state=persist_branch_state,
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


def test_pending_code_retry_success_clears_retry_and_code_failed_status() -> None:
    branch = Branch("b1", BranchState.EXPLORE, 1, "champ", pending_retry=True)
    branch.consecutive_llm_retries = 1
    hypothesis = _hypothesis()
    record = _hypothesis_record(branch.branch_id)
    record.status = "code_failed"
    pending = {
        branch.branch_id: (hypothesis, record, "initial code generation failed"),
    }
    steps: list[StepRecord] = []
    persisted: list[str] = []
    verification_passes: list[tuple[str, str]] = []
    patch = PatchProposal(
        file_path="operators/local_search.py",
        action="modify",
        code_content="def solve():\n    return None\n",
    )

    class BranchController:
        def get_branch(self, branch_id: str) -> Branch:
            assert branch_id == branch.branch_id
            return branch

        def next_stage(self, branch_id: str) -> None:
            assert branch_id == branch.branch_id

    class VerificationGate:
        def run(self, *_args, **_kwargs) -> VerificationResult:
            return VerificationResult(
                passed=True,
                checks=(CheckResult("V", True, "light", "ok", 0),),
            )

    pipeline = _pipeline(
        pending=pending,
        increment_round=lambda: (_ for _ in ()).throw(
            AssertionError("pending retry must not increment the round")
        ),
        increment_rounds_since_last_promote=lambda: (_ for _ in ()).throw(
            AssertionError("pending retry must not increment idle rounds")
        ),
        get_current_round=lambda: 7,
        generate_hypothesis=lambda branch: (_ for _ in ()).throw(
            AssertionError("pending retry must not generate a new hypothesis")
        ),
        generate_code=lambda branch, hypothesis, prior_failure=None: patch,
        record_step=steps.append,
        branch_controller=BranchController(),
        verification_gate=VerificationGate(),
        setup_workspace=lambda branch: "/tmp/workspace",
        apply_patch=lambda *args, **kwargs: SimpleNamespace(code_hash="code-hash"),
        record_verification_pass=lambda branch, code_hash: verification_passes.append(
            (branch.branch_id, code_hash)
        ),
        evaluate=lambda branch, workspace, hypothesis: (Decision.ABANDON, None, None),
        apply_decision_and_finalize=lambda **kwargs: StepResult(
            action="explore",
            branch_id=kwargs["branch"].branch_id,
            decision=kwargs["decision"],
            reason="screening complete",
        ),
        persist_branch_state=persisted.append,
    )

    result = pipeline.run(branch)

    assert result.reason == "screening complete"
    assert result.counts_toward_max_rounds is False
    assert branch.pending_retry is False
    assert branch.consecutive_llm_retries == 0
    assert record.status == "active"
    assert persisted == [branch.branch_id]
    assert pipeline._test_store.statuses == [("hyp-1", "active")]
    assert pending == {}
    assert verification_passes == [(branch.branch_id, "code-hash")]
    assert steps[0].failure_stage is None
    assert steps[0].patch == patch


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

    result = pipeline.run(branch)

    assert round_calls == 1
    assert idle_calls == 1
    assert result.counts_toward_max_rounds is False
    assert steps[0].round_num == 1
    assert steps[0].proposal_session_ref == {"session_id": "s1"}
    assert pending[branch.branch_id] == (
        hypothesis,
        record,
        "forced code failure",
    )
    assert pipeline._test_store.statuses == [("hyp-1", "code_failed")]


def test_agent_quality_blocked_code_failure_rejects_without_pending_retry() -> None:
    branch = Branch("b1", BranchState.EXPLORE, 1, "champ")
    hypothesis = _hypothesis()
    record = _hypothesis_record(branch.branch_id)
    pending: dict[str, tuple[HypothesisProposal, HypothesisRecord, str]] = {}
    steps: list[StepRecord] = []
    detail = (
        "agentic_proposal:premise_contradicted: "
        "agent_quality_blocked:proposal_premise_contradicted:"
        "agent_grounding_failure: active solver already has this move"
    )

    pipeline = _pipeline(
        pending=pending,
        increment_round=lambda: 1,
        increment_rounds_since_last_promote=lambda: None,
        generate_hypothesis=lambda branch: (hypothesis, record),
        generate_code=lambda branch, hypothesis, prior_failure=None: None,
        record_step=steps.append,
    )
    pipeline.proposal_failure_detail_for = lambda branch_id: detail

    result = pipeline.run(branch)

    assert result.reason == "agent_quality_blocked"
    assert result.counts_toward_max_rounds is False
    assert branch.pending_retry is False
    assert pending == {}
    assert steps[0].failure_stage == "agent_quality_blocked"
    assert steps[0].failure_detail == detail
    assert steps[0].contract_passed is False
    assert pipeline._test_store.statuses == [("hyp-1", "rejected")]


def test_agentic_session_timeout_hypothesis_failure_stops_campaign() -> None:
    branch = Branch("b1", BranchState.EXPLORE, 1, "champ")
    steps: list[StepRecord] = []
    detail = (
        "agentic_proposal:session_timeout: agentic proposal session exceeded "
        "max_wall_time_sec=10"
    )
    pending: dict[str, tuple[HypothesisProposal, HypothesisRecord, str]] = {}

    pipeline = _pipeline(
        pending=pending,
        increment_round=lambda: 1,
        increment_rounds_since_last_promote=lambda: None,
        generate_hypothesis=lambda branch: (None, None),
        generate_code=lambda branch, hypothesis, prior_failure=None: None,
        record_step=steps.append,
    )
    pipeline.proposal_failure_detail_for = lambda branch_id: detail

    result = pipeline.run(branch)

    assert result.stopped is True
    assert result.reason == "agentic_session_timeout"
    assert result.counts_toward_max_rounds is False
    assert pending == {}
    assert steps[0].failure_stage == "agentic_budget_control"
    assert steps[0].failure_detail == detail


def test_agentic_session_timeout_code_failure_stops_without_pending_retry() -> None:
    branch = Branch("b1", BranchState.EXPLORE, 1, "champ")
    hypothesis = _hypothesis()
    record = _hypothesis_record(branch.branch_id)
    pending: dict[str, tuple[HypothesisProposal, HypothesisRecord, str]] = {}
    steps: list[StepRecord] = []
    detail = (
        "agentic_proposal:session_timeout: contract preview skipped by agentic "
        "session_timeout/budget control"
    )

    pipeline = _pipeline(
        pending=pending,
        increment_round=lambda: 1,
        increment_rounds_since_last_promote=lambda: None,
        generate_hypothesis=lambda branch: (hypothesis, record),
        generate_code=lambda branch, hypothesis, prior_failure=None: None,
        record_step=steps.append,
    )
    pipeline.proposal_failure_detail_for = lambda branch_id: detail

    result = pipeline.run(branch)

    assert result.stopped is True
    assert result.reason == "agentic_session_timeout"
    assert result.counts_toward_max_rounds is False
    assert pending == {}
    assert branch.pending_retry is False
    assert steps[0].failure_stage == "agentic_budget_control"
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


def test_campaign_loop_does_not_count_proposal_only_blocks_against_max_rounds() -> None:
    results = [
        StepResult(
            action="explore",
            branch_id="b1",
            reason="agent_quality_blocked",
            counts_toward_max_rounds=False,
        ),
        StepResult(
            action="explore",
            branch_id="b1",
            reason="code generation failed",
            counts_toward_max_rounds=False,
        ),
        StepResult(action="explore", branch_id="b1", reason="screening complete"),
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

    assert calls == 3
    assert "max_rounds_exhausted" in stopped_reasons


def test_campaign_loop_writes_status_heartbeat_before_step_execution() -> None:
    status_calls: list[str] = []
    calls = 0

    def write_status(**kwargs: Any) -> None:
        status_calls.append("stopped" if "stopped_reason" in kwargs else "heartbeat")

    def run_one_step() -> StepResult:
        nonlocal calls
        calls += 1
        assert status_calls[:2] == ["heartbeat", "heartbeat"]
        return StepResult(action="explore", branch_id="b1", stopped=True, reason="done")

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: status_calls.append(f"final:{reason}"),
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

    assert calls == 1
    assert status_calls[0:2] == ["heartbeat", "heartbeat"]
    assert "final:done" in status_calls
