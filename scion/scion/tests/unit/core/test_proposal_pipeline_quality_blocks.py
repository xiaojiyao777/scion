"""Focused tests split from test_proposal_pipeline.py."""

from .proposal_pipeline_test_support import *  # noqa: F401,F403
from scion.core.explore_step_pipeline import ExploreStepPipeline
from scion.core.models import ContractResult, HypothesisRecord, MechanismChange
from scion.core.proposal_pipeline.classification import (
    _agentic_output_is_quality_blocked,
    _agentic_primary_secondary_failures,
)

def test_mechanism_premise_warning_is_not_quality_block_and_returns_patch() -> None:
    creative = FakeCreative()
    patch = creative.patch
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.COMPLETED,
        session_id="premise-session",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        hypothesis=creative.hypothesis,
        patch=patch,
        self_check=AgenticSelfCheck(
            schema_valid=True,
            contract_preview_passed=True,
        ),
        termination_reason=AgenticTerminationReason.COMPLETED,
        structured_rejection={
            "source": "mechanism_novelty_gate",
            "gate_name": "MechanismNoveltyGate",
            "mechanism": "cross_route_or_opt_2_3",
            "premise_check": "contradicted",
            "failure_category": "mechanism_premise_warning",
            "gate_action": "diagnostic",
            "result_kind": "mechanism_premise_warning",
            "diagnostic_kind": "mechanism_premise_warning",
            "screening_allowed": True,
            "quality_block": False,
            "reason": (
                "Hypothesis claims inter-route Or-opt is missing, but active "
                "solver evidence already shows cross-route Or-opt."
            ),
            "evidence": ["_or_opt_1", "_or_opt_2", "_or_opt_3", "_or_opt"],
            "fact_packet_digest": "facts-constraint",
            "fact_provenance": {"source": "unit_test_provider"},
            "variant_allowed": False,
            "contradicted_span": "inter-route Or-opt is missing",
            "matched_span": "inter-route Or-opt is missing",
            "allowed_variant_guidance": "Use a materially different mechanism.",
        },
    )
    failure_streak = {"proposal": 2}
    pipeline, branch, _, circuit, failures, _ = _pipeline(
        creative=creative,
        agentic_session=AgenticProposalSession(injected_output=output),
    )
    pipeline.failure_streak = failure_streak

    patch = pipeline.generate_code(branch, creative.hypothesis)
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)
    session_ref = pipeline.pop_agentic_session_ref(branch.branch_id)

    assert patch is creative.patch
    assert _agentic_output_is_quality_blocked(output) is False
    assert failures == []
    assert failure_streak == {"proposal": 2}
    assert detail is None
    assert circuit.failures == []
    assert session_ref is not None
    assert session_ref["failure_category"] == ""
    assert session_ref["failure_code"] == ""
    assert session_ref["agent_block_reason"] == ""
    assert session_ref["primary_failure"] == {}
    assert session_ref["secondary_observations"] == []
    assert session_ref["rejection_constraint"] is None


def test_mechanism_novelty_warning_is_not_quality_block() -> None:
    creative = FakeCreative()
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.COMPLETED,
        session_id="warning-session",
        campaign_id="camp-1",
        branch_id="branch-1",
        hypothesis=creative.hypothesis,
        patch=creative.patch,
        termination_reason=AgenticTerminationReason.COMPLETED,
        structured_rejection={
            "source": "mechanism_novelty_gate",
            "gate_action": "diagnostic",
            "result_kind": "duplicate_diagnostic",
            "diagnostic_kind": "duplicate_risk",
            "mechanism": "cross_route_or_opt_2_3",
            "premise_check": "duplicate",
            "failure_category": "duplicate_mechanism",
            "screening_allowed": True,
            "reason": "Existing near-field mechanism may overlap.",
        },
    )

    assert _agentic_output_is_quality_blocked(output) is False


def test_soft_novelty_detail_with_legacy_premise_code_is_not_quality_block() -> None:
    creative = FakeCreative()
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
        session_id="legacy-soft-warning-session",
        campaign_id="camp-1",
        branch_id="branch-1",
        hypothesis=creative.hypothesis,
        termination_reason=AgenticTerminationReason.PREMISE_CONTRADICTED,
        failure_category="agent_grounding_failure",
        failure_detail=(
            "proposal_premise_contradicted: mechanism_premise_warning; "
            "gate_action=diagnostic; screening_allowed=true; quality_block=false"
        ),
    )

    assert _agentic_output_is_quality_blocked(output) is False


def test_mechanism_change_type_enum_failure_is_schema_output_not_quality_block() -> None:
    detail = (
        "schema or target preview did not pass "
        "(mechanism_changes.1.change_type: Input should be "
        "'add', 'modify', 'replace', 'remove' or 'integrate'; got parameterize)"
    )
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.FAILED,
        session_id="schema-alias-session",
        campaign_id="camp-1",
        branch_id="branch-1",
        termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
        failure_detail=detail,
        failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
        self_check=AgenticSelfCheck(
            schema_valid=False,
            schema_preview_codes=(
                "mechanism_changes.1.change_type: Input should be one of "
                "add/modify/replace/remove/integrate; parameterize is an "
                "allowed_next_actions label",
            ),
        ),
    )

    primary, secondary = _agentic_primary_secondary_failures(output)

    assert _agentic_output_is_quality_blocked(output) is False
    assert primary["stage"] == "self_check"
    assert primary["category"] == "schema_output_failure"
    assert primary["category"] != "contract_boundary_failure"
    assert secondary == []


def test_agentic_quality_block_feedback_enters_next_hypothesis_context() -> None:
    creative = FakeCreative()
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
        session_id="premise-session",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        hypothesis=creative.hypothesis,
        termination_reason=AgenticTerminationReason.HYPOTHESIS_APPROVAL_FAILED,
        failure_detail="objective policy forbids worsening protected objective",
        failure_category="objective_policy_contradicted",
        structured_rejection={
            "source": "objective_policy_gate",
            "gate_name": "ObjectivePolicyGate",
            "mechanism": "objective_policy",
            "premise_check": "objective_policy_contradicted",
            "failure_category": "objective_policy_contradicted",
            "failure_code": "objective_policy_contradicted",
            "agent_block_reason": "agent_quality_blocked",
            "reason": "objective policy forbids worsening protected objective",
            "retry_constraint": "preserve protected objective policy",
        },
    )
    captured: list[AgenticProposalRequest] = []

    class CapturingSession:
        def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
            captured.append(request)
            return AgenticProposalOutput(
                status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
                session_id="next-session",
                campaign_id=request.campaign_id,
                branch_id=request.branch.branch_id,
                champion_version=request.champion.version if request.champion else None,
                problem_id=request.problem_id,
                problem_spec_hash=request.problem_spec_hash,
                hypothesis=creative.hypothesis,
                termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
            )

    pipeline, branch, _, circuit, failures, _ = _pipeline(
        creative=creative,
        agentic_session=AgenticProposalSession(injected_output=output),
    )

    patch = pipeline.generate_code(branch, creative.hypothesis)
    assert patch is None
    assert failures == []
    assert circuit.failures == []
    stored = pipeline.agentic_quality_feedback[branch.branch_id]
    assert stored[0]["failure_code"] == "objective_policy_contradicted"
    assert stored[0]["mechanism"] == "objective_policy"

    pipeline.agentic_session = CapturingSession()
    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis == creative.hypothesis
    assert record is not None
    context = captured[0].hypothesis_context
    assert context is not None
    rendered = json.dumps(context, sort_keys=True)
    assert "agentic_prior_quality_blocks" in context
    assert "objective_policy_contradicted" in rendered
    assert "objective_policy" in rendered
    assert "protected objective" in rendered
    assert "hard boundary, objective, contract" in context[
        "agentic_prior_quality_block_rule"
    ]
    assert branch.branch_id not in pipeline.agentic_quality_feedback


def test_agentic_algorithm_smoke_failure_is_quality_block_not_proposal_streak() -> None:
    creative = FakeCreative()
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.FAILED,
        session_id="smoke-session",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        champion_weight_revision=0,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        hypothesis=creative.hypothesis,
        termination_reason=AgenticTerminationReason.CODE_GENERATION_FAILED,
        failure_detail=(
            "algorithm smoke did not pass "
            "(runtime_smoke.telemetry_guard: TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED)"
        ),
        failure_category=AgenticFailureCategory.ALGORITHM_SMOKE_FAILURE,
    )
    failure_streak = {"proposal": 2}
    pipeline, branch, _, circuit, failures, _ = _pipeline(
        creative=creative,
        agentic_session=AgenticProposalSession(injected_output=output),
    )
    pipeline.failure_streak = failure_streak

    patch = pipeline.generate_code(branch, creative.hypothesis)
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)
    session_ref = pipeline.pop_agentic_session_ref(branch.branch_id)

    assert patch is None
    assert failures == []
    assert failure_streak == {"proposal": 2}
    assert detail is not None
    assert "agent_quality_blocked" in detail
    assert "algorithm_smoke_failure" in detail
    assert circuit.failures == []
    assert session_ref is not None
    assert session_ref["primary_failure"]["stage"] == "agent_quality_blocked"
    assert session_ref["primary_failure"]["category"] == "algorithm_smoke_failure"


def test_agentic_activation_diagnostic_is_quality_block_not_proposal_streak() -> None:
    creative = FakeCreative()
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.FAILED,
        session_id="activation-session",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        champion_weight_revision=0,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        hypothesis=creative.hypothesis,
        termination_reason=AgenticTerminationReason.CODE_GENERATION_FAILED,
        failure_detail=(
            "algorithm smoke did not pass: proposal activation diagnostic: "
            "code=proposal_activation_diagnostic; "
            "activation_diagnostic_kind=instrumentation_missing"
        ),
        failure_category="proposal_activation_diagnostic",
    )
    failure_streak = {"proposal": 2}
    pipeline, branch, _, circuit, failures, _ = _pipeline(
        creative=creative,
        agentic_session=AgenticProposalSession(injected_output=output),
    )
    pipeline.failure_streak = failure_streak

    patch = pipeline.generate_code(branch, creative.hypothesis)
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)
    session_ref = pipeline.pop_agentic_session_ref(branch.branch_id)

    assert patch is None
    assert failures == []
    assert failure_streak == {"proposal": 2}
    assert detail is not None
    assert "agent_quality_blocked" in detail
    assert "proposal_activation_diagnostic" in detail
    assert "activation_diagnostic_kind=instrumentation_missing" in detail
    assert circuit.failures == []
    assert session_ref is not None
    assert session_ref["failure_category"] == "proposal_activation_diagnostic"
    assert session_ref["failure_code"] == "proposal_activation_diagnostic"
    assert session_ref["agent_block_reason"] == "agent_quality_blocked"
    assert session_ref["primary_failure"]["stage"] == "agent_quality_blocked"
    assert session_ref["primary_failure"]["category"] == (
        "proposal_activation_diagnostic"
    )
    assert session_ref["primary_failure"]["code"] == (
        "proposal_activation_diagnostic"
    )
    assert "activation_diagnostic_kind=instrumentation_missing" in session_ref[
        "primary_failure"
    ]["detail"]


def test_agentic_activation_not_observed_diagnostic_is_not_quality_block() -> None:
    creative = FakeCreative()
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.FAILED,
        session_id="activation-diagnostic-session",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        champion_weight_revision=0,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        hypothesis=creative.hypothesis,
        termination_reason=AgenticTerminationReason.CODE_GENERATION_FAILED,
        failure_detail=(
            "activation_not_observed_diagnostic: proposal_activation_diagnostic; "
            "activation_diagnostic_kind=path_not_reached"
        ),
        failure_category="activation_not_observed_diagnostic",
        self_check=AgenticSelfCheck(
            schema_valid=True,
            contract_preview_passed=True,
        ),
    )
    pipeline, branch, _, circuit, failures, _ = _pipeline(
        creative=creative,
        agentic_session=AgenticProposalSession(injected_output=output),
    )

    patch = pipeline.generate_code(branch, creative.hypothesis)
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)
    session_ref = pipeline.pop_agentic_session_ref(branch.branch_id)

    assert patch is None
    assert detail is not None
    assert "agent_quality_blocked" not in detail
    assert failures and failures[-1][1].category == "proposal"
    assert circuit.failures
    assert session_ref is not None
    assert session_ref["agent_block_reason"] == ""
    assert session_ref["primary_failure"]["category"] == (
        "activation_not_observed_diagnostic"
    )


def test_agentic_activation_diagnostic_enters_next_hypothesis_context_with_facts() -> None:
    creative = FakeCreative()
    creative.hypothesis = HypothesisProposal(
        hypothesis_text="Add multi-start VNS seed with explicit activation telemetry.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/construction.py",
        target_weakness="Construction seed lacks diversification.",
        expected_effect="Improve distance while preserving feasibility.",
        mechanism_changes=(
            MechanismChange(id="multi_start_vns_seed", change_type="add"),
        ),
    )
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.FAILED,
        session_id="activation-session",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        champion_weight_revision=0,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        hypothesis=creative.hypothesis,
        termination_reason=AgenticTerminationReason.CODE_GENERATION_FAILED,
        failure_detail=(
            "algorithm smoke did not pass: proposal activation diagnostic: "
            "code=proposal_activation_diagnostic; "
            "activation_diagnostic_kind=instrumentation_missing"
        ),
        failure_category="proposal_activation_diagnostic",
        structured_rejection={
            "source": "proposal.algorithm_smoke",
            "gate_name": "AlgorithmSmokeActivationDiagnostic",
            "mechanism": "multi_start_vns_seed",
            "failure_code": "proposal_activation_diagnostic",
            "agent_block_reason": "agent_quality_blocked",
            "reason": "declared mechanism telemetry did not activate",
            "fact_packet_digest": "facts-activation",
            "fact_provenance": {
                "provenance": {
                    "source": "champion_snapshot",
                    "branch_id": "branch-1",
                }
            },
        },
    )
    captured: list[AgenticProposalRequest] = []

    class CapturingSession:
        def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
            captured.append(request)
            return AgenticProposalOutput(
                status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
                session_id="next-session",
                campaign_id=request.campaign_id,
                branch_id=request.branch.branch_id,
                champion_version=request.champion.version if request.champion else None,
                problem_id=request.problem_id,
                problem_spec_hash=request.problem_spec_hash,
                hypothesis=creative.hypothesis,
                termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
            )

    pipeline, branch, _, circuit, failures, _ = _pipeline(
        creative=creative,
        agentic_session=AgenticProposalSession(injected_output=output),
    )

    patch = pipeline.generate_code(branch, creative.hypothesis)
    assert patch is None
    assert failures == []
    assert circuit.failures == []
    stored = pipeline.agentic_quality_feedback[branch.branch_id]
    assert stored[0]["failure_code"] == "proposal_activation_diagnostic"
    assert stored[0]["mechanism"] == "multi_start_vns_seed"
    assert stored[0]["fact_packet_digest"] == "facts-activation"
    assert stored[0]["fact_provenance"]["provenance"]["source"] == (
        "champion_snapshot"
    )

    pipeline.agentic_session = CapturingSession()
    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis == creative.hypothesis
    assert record is not None
    context = captured[0].hypothesis_context
    assert context is not None
    rendered = json.dumps(context, sort_keys=True)
    assert "agentic_prior_quality_blocks" in context
    assert "proposal_activation_diagnostic" in rendered
    assert "activation-session" in rendered
    assert "multi_start_vns_seed" in rendered
    assert "facts-activation" in rendered
    assert "champion_snapshot" in rendered
    assert "infra_suspected" not in rendered.lower()


def test_agentic_transient_api_failure_routes_as_infra_not_structured_output() -> None:
    creative = FakeCreative()
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
        session_id="transient-session",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        champion_weight_revision=0,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        hypothesis=creative.hypothesis,
        termination_reason=AgenticTerminationReason.CODE_GENERATION_FAILED,
        failure_detail=(
            "Tool call failed after 2 transient API attempt(s). Last error: "
            "Transient provider error: HTTP 502 Bad Gateway <html>"
        ),
        failure_category=AgenticFailureCategory.LLM_TRANSIENT_API_ERROR,
        self_check=AgenticSelfCheck(schema_valid=True),
    )
    pipeline, branch, _, circuit, failures, _ = _pipeline(
        creative=creative,
        agentic_session=AgenticProposalSession(injected_output=output),
    )

    patch = pipeline.generate_code(branch, creative.hypothesis)
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)
    session_ref = pipeline.pop_agentic_session_ref(branch.branch_id)

    assert patch is None
    assert len(failures) == 1
    assert failures[0][1].category == "infra"
    assert detail is not None
    assert "502 Bad Gateway" in detail
    assert circuit.failures == []
    assert session_ref is not None
    assert session_ref["failure_category"] == "llm_transient_api_error"
    assert session_ref["primary_failure"]["category"] == "llm_transient_api_error"
    assert session_ref["primary_failure"]["stage"] == "code_generation_failed"


def test_agentic_hypothesis_api_failure_category_overrides_default_self_check() -> None:
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.FAILED,
        session_id="hyp-api-session",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
        failure_detail=(
            "Tool call failed after 2 transient API attempt(s). Last error: "
            "Transient provider error: HTTP 502 Bad Gateway"
        ),
        failure_category=AgenticFailureCategory.LLM_TRANSIENT_API_ERROR,
        self_check=AgenticSelfCheck(schema_valid=False),
    )
    pipeline, branch, _, circuit, failures, _ = _pipeline(
        agentic_session=AgenticProposalSession(injected_output=output),
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)
    session_ref = pipeline.pop_agentic_session_ref(branch.branch_id)

    assert hypothesis is None
    assert record is None
    assert len(failures) == 1
    assert failures[0][1].category == "infra"
    assert circuit.failures == []
    assert session_ref is not None
    assert session_ref["failure_category"] == "llm_transient_api_error"
    assert session_ref["primary_failure"]["category"] == "llm_transient_api_error"
    assert session_ref["primary_failure"]["stage"] == "hypothesis_generation_failed"


def test_hard_objective_contradiction_enters_search_memory_as_primary_block() -> None:
    creative = FakeCreative()
    search_memory = CampaignSearchMemory()
    session_ref = {
        "failure_category": "objective_policy_contradicted",
        "failure_code": "objective_policy_contradicted",
        "agent_block_reason": "agent_quality_blocked",
        "primary_failure": {
            "stage": "agent_quality_blocked",
            "reason": "objective_policy_contradicted",
            "category": "objective_policy_contradicted",
            "code": "objective_policy_contradicted",
            "detail": "objective policy forbids worsening protected objective",
        },
        "rejection_constraint": {
            "source": "objective_policy_gate",
            "mechanism": "objective_policy",
            "premise_check": "objective_policy_contradicted",
            "failure_code": "objective_policy_contradicted",
            "agent_block_reason": "agent_quality_blocked",
            "reason": (
                "Hypothesis would worsen a protected objective beyond policy."
            ),
            "evidence": ["protected objective policy"],
        },
    }
    step = StepRecord(
        round_num=1,
        branch_id="branch-1",
        hypothesis=creative.hypothesis,
        patch=None,
        contract_passed=False,
        verification_passed=False,
        protocol_result=None,
        decision=None,
        failure_stage="agent_quality_blocked",
        failure_detail=(
            "agentic_proposal:hypothesis_approval_failed: "
            "agent_quality_blocked:objective_policy_contradicted:"
            "objective_policy_contradicted"
        ),
        proposal_session_ref=session_ref,
    )

    search_memory.update(step)
    rendered = search_memory.render(view="hypothesis")

    assert "Agentic Grounding Blocks" in rendered
    assert "do not repeat objective_policy" in rendered
    assert "premise_check=objective_policy_contradicted" in rendered
    assert "protected objective" in rendered
    assert "C11" not in rendered


def test_explore_pipeline_persists_agent_quality_instead_of_contract() -> None:
    creative = FakeCreative()
    branch = _branch()
    record = HypothesisRecord(
        hypothesis_id="hyp-1",
        branch_id=branch.branch_id,
        change_locus=creative.hypothesis.change_locus,
        action=creative.hypothesis.action,
        status="active",
        target_file=creative.hypothesis.target_file,
        hypothesis_text=creative.hypothesis.hypothesis_text,
    )
    steps: list[StepRecord] = []
    failures: list[tuple[Branch, FailureEvent]] = []
    marked_status: list[tuple[str, str]] = []

    class Store:
        def get_by_status(self, _status: str):
            return []

        def save(self, _record):
            return None

        def mark_status(self, hypothesis_id: str, status: str) -> None:
            marked_status.append((hypothesis_id, status))

    class ContractGate:
        def validate_hypothesis(self, *_args, **_kwargs):
            return ContractResult(
                passed=False,
                checks=(),
                failure_reason=(
                    "C11_expected_telemetry: expected telemetry is malformed"
                ),
            )

    session_ref = {
        "session_id": "premise-session",
        "failure_category": "objective_policy_contradicted",
        "failure_code": "objective_policy_contradicted",
        "agent_block_reason": "agent_quality_blocked",
        "primary_failure": {
            "stage": "agent_quality_blocked",
            "reason": "objective_policy_contradicted",
            "category": "objective_policy_contradicted",
            "code": "objective_policy_contradicted",
            "detail": "objective policy forbids worsening protected objective",
        },
    }

    pipeline = ExploreStepPipeline(
        branch_controller=None,
        contract_gate=ContractGate(),
        verification_gate=None,
        hypothesis_store=Store(),
        registry=None,
        campaign_id="camp-1",
        get_champion=_champion,
        pending_hypotheses={},
        branch_hypotheses={},
        branch_patches={},
        branch_current_hypothesis={},
        branch_workspaces={},
        failure_streak={},
        increment_round=lambda: 1,
        increment_rounds_since_last_promote=lambda: None,
        generate_hypothesis=lambda _branch: (creative.hypothesis, record),
        generate_code=lambda *_args, **_kwargs: None,
        attempt_fix=lambda *_args, **_kwargs: None,
        handle_failure=lambda b, f, **_kwargs: failures.append((b, f)),
        record_step=steps.append,
        setup_workspace=lambda _branch: None,
        apply_patch=lambda *_args, **_kwargs: None,
        record_verification_pass=lambda *_args, **_kwargs: None,
        archive_failed_workspace=lambda *_args, **_kwargs: None,
        evaluate=lambda *_args, **_kwargs: (None, None, None),
        apply_decision_and_finalize=lambda *_args, **_kwargs: None,
        decision_reason_codes_for=lambda *_args, **_kwargs: None,
        proposal_session_ref_for=lambda _branch_id: dict(session_ref),
        persist_branch_state=lambda _branch_id: None,
    )

    result = pipeline.run(branch)

    assert result.counts_toward_max_rounds is False
    assert result.reason == "agent_quality_blocked"
    assert failures == []
    assert marked_status == []
    assert len(steps) == 1
    assert steps[0].failure_stage == "agent_quality_blocked"
    assert "objective_policy_contradicted" in (steps[0].failure_detail or "")
    assert steps[0].proposal_session_ref == session_ref
    assert branch.failure_codes == ["OBJECTIVE_POLICY_CONTRADICTED"]
    assert "CONTRACT" not in branch.failure_codes


def test_agentic_provider_balance_failure_marks_balance_exhausted() -> None:
    detail = (
        "Tool call failed after 3 attempt(s). Last error: Transient provider error: "
        "Error code: 403 - {'error': {'type': 'Aihubmix_api_error', "
        "'message': 'Your account balance is insufficient. Please recharge your "
        "account to continue using the API.'}}"
    )
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.FAILED,
        session_id="balance-session",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
        failure_detail=detail,
    )
    pipeline, branch, _, circuit, failures, balance = _pipeline(
        agentic_session=AgenticProposalSession(injected_output=output),
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)
    recorded_detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)

    assert hypothesis is None
    assert record is None
    assert balance["value"] is True
    assert failures == []
    assert recorded_detail is not None
    assert "balance is insufficient" in recorded_detail
    assert circuit.failures == [recorded_detail]


def test_agentic_pipeline_passes_compact_resume_context_from_failed_artifact(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "agentic"
    captured: list[AgenticProposalRequest] = []
    creative = FakeCreative()

    class CapturingSession:
        def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
            captured.append(request)
            return AgenticProposalOutput(
                status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
                session_id="next-session",
                campaign_id=request.campaign_id,
                branch_id=request.branch.branch_id,
                champion_version=request.champion.version if request.champion else None,
                problem_id=request.problem_id,
                problem_spec_hash=request.problem_spec_hash,
                hypothesis=creative.hypothesis,
                termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
            )

    pipeline, branch, _, _, _, _ = _pipeline(
        creative=creative,
        agentic_session=CapturingSession(),
        agentic_artifact_dir=str(artifact_dir),
    )
    previous = AgenticProposalSession(
        injected_output=AgenticProposalOutput(
            status=AgenticProposalStatus.FAILED,
            session_id="previous-failed",
            campaign_id="camp-1",
            branch_id="branch-1",
            termination_reason=AgenticTerminationReason.SESSION_TIMEOUT,
            failure_detail="safe timeout detail\nraw_metrics_ref should be removed",
        ),
        artifact_store=FileAgenticSessionArtifactStore(artifact_dir),
    )
    previous.run(
        pipeline._build_agentic_request(
            branch=branch,
            champion=_champion(),
            hypothesis_context={},
        )
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis == creative.hypothesis
    assert record is not None
    assert captured[0].resume_context is not None
    rendered = json.dumps(captured[0].resume_context, sort_keys=True)
    assert "previous-failed" in rendered
    assert "sanitized_resume_context_only" in rendered
    assert "raw_metrics_ref" not in rendered
    assert "SECRET" not in rendered


def test_agentic_pipeline_does_not_reuse_invalid_recovery_artifact(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "agentic"
    captured: list[AgenticProposalRequest] = []
    creative = FakeCreative()

    class CapturingSession:
        def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
            captured.append(request)
            return AgenticProposalOutput(
                status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
                session_id="fresh-session",
                campaign_id=request.campaign_id,
                branch_id=request.branch.branch_id,
                champion_version=request.champion.version if request.champion else None,
                problem_id=request.problem_id,
                problem_spec_hash=request.problem_spec_hash,
                hypothesis=creative.hypothesis,
                termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
            )

    pipeline, branch, _, _, _, _ = _pipeline(
        creative=creative,
        agentic_session=CapturingSession(),
        agentic_artifact_dir=str(artifact_dir),
    )
    previous = AgenticProposalSession(
        injected_output=AgenticProposalOutput(
            status=AgenticProposalStatus.FAILED,
            session_id="previous-invalid",
            campaign_id="camp-1",
            branch_id="branch-1",
            termination_reason=AgenticTerminationReason.SESSION_TIMEOUT,
            failure_detail="timeout",
        ),
        artifact_store=FileAgenticSessionArtifactStore(artifact_dir),
    )
    output = previous.run(
        pipeline._build_agentic_request(
            branch=branch,
            champion=_champion(),
            hypothesis_context={},
        )
    )
    output_ref = next(ref for ref in output.tainted_artifact_refs if ref.endswith("output.json"))
    artifact = json.loads(Path(output_ref).read_text(encoding="utf-8"))
    artifact["compact_transcript"] = [
        {
            "phase": "diagnose",
            "metadata": {
                "step_id": "tool-0001",
                "tool_name": "context.read_problem",
                "status": "ok",
                "result_summary": "raw_metrics_ref=/secret/raw.json",
            },
        }
    ]
    Path(output_ref).write_text(json.dumps(artifact), encoding="utf-8")
    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis == creative.hypothesis
    assert record is not None
    assert captured[0].resume_context is None
    report = pipeline.agentic_recovery_reports[branch.branch_id]
    assert report["validation_ok"] is False
    assert any("raw ref marker" in error for error in report["validation_errors"])
