from __future__ import annotations

from types import SimpleNamespace

from scion.core.models import (
    Branch,
    BranchState,
    CheckResult,
    ContractResult,
    Decision,
    HypothesisProposal,
    HypothesisRecord,
    MechanismChange,
    PatchProposal,
    VerificationResult,
    StepRecord,
)
from scion.core.repeated_contract_failures import (
    REPEATED_CONTRACT_FAILURE_CODE,
    REPEATED_CONTRACT_REROUTE_REASON,
)
from scion.core.step_result import StepResult
from scion.tests.unit.core.retry_round_accounting_support import (
    hypothesis as _hypothesis,
    hypothesis_record as _hypothesis_record,
    pipeline as _pipeline,
)


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


def test_repeated_contract_code_failure_reroutes_without_pending_retry() -> None:
    branch = Branch("b1", BranchState.EXPLORE, 1, "champ")
    hypothesis = _hypothesis()
    hypothesis.change_locus = "algorithm_design"
    hypothesis.target_file = "policies/state.py"
    hypothesis.mechanism_changes = (
        MechanismChange("state_delta_cache", "modify"),
    )
    record = _hypothesis_record(branch.branch_id)
    pending: dict[str, tuple[HypothesisProposal, HypothesisRecord, str]] = {}
    steps: list[StepRecord] = []
    detail = (
        "Contract preview failed: object_model_no_dynamic_private_attrs; "
        "state.py prose says the private cache keeps mutable branch state"
    )
    session_ref = {
        "session_id": "session-contract",
        "failure_category": "contract_boundary_failure",
        "failure_code": "object_model_no_dynamic_private_attrs",
        "contract_preview_codes": [
            "object_model_no_dynamic_private_attrs",
        ],
        "primary_failure": {
            "stage": "self_check",
            "reason": "contract_preview_failed",
            "category": "contract_boundary_failure",
            "code": "object_model_no_dynamic_private_attrs",
        },
    }

    pipeline = _pipeline(
        pending=pending,
        increment_round=lambda: 1,
        increment_rounds_since_last_promote=lambda: None,
        get_current_round=lambda: 1,
        generate_hypothesis=lambda branch: (hypothesis, record),
        generate_code=lambda branch, hypothesis, prior_failure=None: None,
        record_step=steps.append,
    )
    pipeline.proposal_failure_detail_for = lambda branch_id: detail
    pipeline.proposal_session_ref_for = lambda branch_id: dict(session_ref)

    first = pipeline.run(branch)
    second = pipeline.run(branch)

    assert first.reason == "code generation failed"
    assert second.reason == REPEATED_CONTRACT_REROUTE_REASON
    assert pending == {}
    assert branch.pending_retry is False
    assert branch.failure_codes == [REPEATED_CONTRACT_FAILURE_CODE]
    assert branch.last_branch_lifecycle_policy_block["failure_code"] == (
        REPEATED_CONTRACT_FAILURE_CODE
    )
    assert branch.last_branch_lifecycle_policy_block["same_hypothesis_retry"] == (
        "blocked"
    )
    assert steps[1].attempt_kind == "branch_lifecycle_policy"
    assert pipeline._test_store.statuses == [
        ("hyp-1", "code_failed"),
        ("hyp-1", "rejected"),
    ]


def test_explore_pipeline_emits_pre_protocol_status_progress() -> None:
    branch = Branch("b1", BranchState.EXPLORE, 1, "champ")
    hypothesis = _hypothesis()
    record = _hypothesis_record(branch.branch_id)
    patch = PatchProposal(
        file_path="operators/local_search.py",
        action="modify",
        code_content="def solve():\n    return None\n",
    )
    progress_events: list[dict[str, object] | None] = []
    steps: list[StepRecord] = []
    verification_passes: list[tuple[str, str]] = []

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
        pending={},
        increment_round=lambda: 3,
        increment_rounds_since_last_promote=lambda: None,
        generate_hypothesis=lambda branch: (hypothesis, record),
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
        update_status_progress=progress_events.append,
    )

    result = pipeline.run(branch)

    assert result.reason == "screening complete"
    phases = [event["phase"] for event in progress_events if event]
    assert phases[:3] == [
        "proposal_hypothesis",
        "hypothesis_contract",
        "proposal_code",
    ]
    assert "patch_contract" in phases
    assert "verification" in phases
    assert "evaluation_dispatch" in phases
    code_event = next(
        event
        for event in progress_events
        if event and event["phase"] == "proposal_code"
    )
    assert code_event["target_file"] == hypothesis.target_file
    assert code_event["hypothesis_action"] == hypothesis.action
    assert progress_events[-1] is None


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


def test_duplicate_mechanism_diagnostic_does_not_become_quality_block() -> None:
    branch = Branch("b1", BranchState.EXPLORE, 1, "champ")
    hypothesis = _hypothesis()
    record = _hypothesis_record(branch.branch_id)
    pending: dict[str, tuple[HypothesisProposal, HypothesisRecord, str]] = {}
    steps: list[StepRecord] = []
    detail = (
        "agentic_proposal:duplicate_mechanism: premise_check=duplicate: "
        "candidate repeats an existing mechanism"
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

    assert result.reason == "code generation failed"
    assert result.counts_toward_max_rounds is False
    assert branch.pending_retry is False
    assert branch.branch_id in pending
    assert steps[0].failure_stage == "code_generation"
    assert steps[0].failure_detail == detail
    assert "duplicate_mechanism" in steps[0].failure_detail
    assert pipeline._test_store.statuses == [("hyp-1", "code_failed")]


def test_schema_quality_block_does_not_create_pending_code_retry() -> None:
    branch = Branch("b1", BranchState.EXPLORE, 1, "champ")
    pending: dict[str, tuple[HypothesisProposal, HypothesisRecord, str]] = {}
    steps: list[StepRecord] = []
    detail = (
        "schema_quality_block: mechanism_changes_duplicate_id_conflict: "
        "mechanism_changes repeats id values"
    )

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

    assert result.reason == "agent_quality_blocked"
    assert result.attempt_kind == "schema_quality_block"
    assert result.counts_toward_max_rounds is False
    assert pending == {}
    assert steps[0].failure_stage == "agent_quality_blocked"
    assert steps[0].attempt_kind == "schema_quality_block"
    assert "mechanism_changes_duplicate_id_conflict" in (steps[0].failure_detail or "")


def test_patch_contract_failure_marks_contract_failed_status() -> None:
    branch = Branch("b1", BranchState.EXPLORE, 1, "champ")
    hypothesis = _hypothesis()
    record = _hypothesis_record(branch.branch_id)
    patch = PatchProposal(
        file_path="operators/local_search.py",
        action="modify",
        code_content="def solve():\n    return None\n",
    )
    steps: list[StepRecord] = []

    class FailingPatchContractGate:
        def validate_hypothesis(self, *args, **kwargs) -> ContractResult:
            return ContractResult(
                passed=True,
                checks=(CheckResult("C", True, "light", "ok", 0),),
            )

        def validate_patch(self, *args, **kwargs) -> ContractResult:
            return ContractResult(
                passed=False,
                checks=(CheckResult("P", False, "light", "bad", 0),),
                failure_reason="C9_security failed",
            )

    pipeline = _pipeline(
        pending={},
        increment_round=lambda: 1,
        increment_rounds_since_last_promote=lambda: None,
        generate_hypothesis=lambda branch: (hypothesis, record),
        generate_code=lambda branch, hypothesis, prior_failure=None: patch,
        record_step=steps.append,
    )
    pipeline.contract_gate = FailingPatchContractGate()

    result = pipeline.run(branch)

    assert result.reason == "patch contract failed"
    assert pipeline._test_store.statuses == [("hyp-1", "contract_failed")]
    assert steps[0].failure_stage == "patch_contract"


def test_algorithm_smoke_quality_block_marks_smoke_failed_status() -> None:
    branch = Branch("b1", BranchState.EXPLORE, 1, "champ")
    hypothesis = _hypothesis()
    record = _hypothesis_record(branch.branch_id)
    pending: dict[str, tuple[HypothesisProposal, HypothesisRecord, str]] = {}
    steps: list[StepRecord] = []
    detail = (
        "agentic_proposal:code_generation_failed: agent_quality_blocked:"
        "algorithm_smoke_failure:algorithm_smoke_failure: "
        "algorithm smoke did not pass"
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
    assert pipeline._test_store.statuses == [("hyp-1", "smoke_failed")]
    assert steps[0].failure_stage == "agent_quality_blocked"


def test_agentic_session_timeout_hypothesis_failure_does_not_stop_campaign() -> None:
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

    assert result.stopped is False
    assert result.reason == "agentic_session_timeout"
    assert result.counts_toward_max_rounds is False
    assert pending == {}
    assert steps[0].failure_stage == "agentic_budget_control"
    assert steps[0].failure_detail == detail


def test_agentic_session_timeout_code_failure_does_not_stop_campaign() -> None:
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

    assert result.stopped is False
    assert result.reason == "agentic_session_timeout"
    assert result.counts_toward_max_rounds is False
    assert pending == {}
    assert branch.pending_retry is False
    assert steps[0].failure_stage == "agentic_budget_control"
    assert pipeline._test_store.statuses == [("hyp-1", "code_failed")]
