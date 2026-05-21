"""Focused tests split from test_proposal_pipeline.py."""

from .proposal_pipeline_test_support import *  # noqa: F401,F403
from scion.core.explore_step_pipeline import ExploreStepPipeline
from scion.core.models import ContractResult, HypothesisRecord, MechanismChange

def test_agentic_premise_contradiction_is_quality_block_not_infra_streak() -> None:
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
        termination_reason=AgenticTerminationReason.PREMISE_CONTRADICTED,
        failure_detail="active solver already contains the claimed missing move",
        failure_category="agent_grounding_failure",
        structured_rejection={
            "source": "mechanism_novelty_gate",
            "gate_name": "MechanismNoveltyGate",
            "mechanism": "cross_route_or_opt_2_3",
            "premise_check": "contradicted",
            "failure_category": "agent_grounding_failure",
            "failure_code": "proposal_premise_contradicted",
            "agent_block_reason": "agent_quality_blocked",
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

    assert patch is None
    assert failures == []
    assert failure_streak == {"proposal": 2}
    assert detail is not None
    assert "agent_quality_blocked" in detail
    assert "proposal_premise_contradicted" in detail
    assert "agent_grounding_failure" in detail
    assert circuit.failures == []
    assert session_ref is not None
    assert session_ref["failure_category"] == "agent_grounding_failure"
    assert session_ref["failure_code"] == "proposal_premise_contradicted"
    assert session_ref["agent_block_reason"] == "agent_quality_blocked"
    assert session_ref["primary_failure"] == {
        "stage": "agent_quality_blocked",
        "reason": "proposal_premise_contradicted",
        "category": "agent_grounding_failure",
        "code": "proposal_premise_contradicted",
        "detail": "active solver already contains the claimed missing move",
    }
    assert session_ref["secondary_observations"] == []
    assert session_ref["rejection_constraint"]["source"] == (
        "mechanism_novelty_gate"
    )
    assert session_ref["rejection_constraint"]["mechanism"] == (
        "cross_route_or_opt_2_3"
    )
    assert "active-solver evidence" in session_ref["rejection_constraint"][
        "retry_constraint"
    ]
    assert session_ref["rejection_constraint"]["fact_packet_digest"] == (
        "facts-constraint"
    )
    assert session_ref["rejection_constraint"]["fact_provenance"] == {
        "source": "unit_test_provider"
    }
    assert session_ref["rejection_constraint"]["variant_allowed"] is False
    assert session_ref["rejection_constraint"]["contradicted_span"] == (
        "inter-route Or-opt is missing"
    )
    assert session_ref["rejection_constraint"]["matched_span"] == (
        "inter-route Or-opt is missing"
    )
    assert session_ref["rejection_constraint"]["allowed_variant_guidance"] == (
        "Use a materially different mechanism."
    )


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
        termination_reason=AgenticTerminationReason.PREMISE_CONTRADICTED,
        failure_detail="active solver already contains the claimed missing move",
        failure_category="agent_grounding_failure",
        structured_rejection={
            "source": "mechanism_novelty_gate",
            "gate_name": "MechanismNoveltyGate",
            "mechanism": "cross_route_or_opt_2_3",
            "premise_check": "contradicted",
            "failure_category": "agent_grounding_failure",
            "failure_code": "proposal_premise_contradicted",
            "agent_block_reason": "agent_quality_blocked",
            "reason": "active solver already has the claimed mechanism",
            "retry_constraint": "do not repeat cross_route_or_opt_2_3",
            "fact_ids": ["cvrp.local_search.or_opt_cross_route"],
            "fact_packet_digest": "facts-123",
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
    assert stored[0]["failure_code"] == "proposal_premise_contradicted"
    assert stored[0]["mechanism"] == "cross_route_or_opt_2_3"

    pipeline.agentic_session = CapturingSession()
    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis == creative.hypothesis
    assert record is not None
    context = captured[0].hypothesis_context
    assert context is not None
    rendered = json.dumps(context, sort_keys=True)
    assert "agentic_prior_quality_blocks" in context
    assert "agentic_negative_fact_block" in context
    assert "fact_id=cvrp.local_search.or_opt_cross_route" in context[
        "agentic_negative_fact_block"
    ]
    assert "mechanism=cross_route_or_opt_2_3" in context[
        "agentic_negative_fact_block"
    ]
    assert "proposal_premise_contradicted" in rendered
    assert "cross_route_or_opt_2_3" in rendered
    assert "facts-123" in rendered
    assert "do not repeat the same premise" in context[
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


def test_agentic_premise_contradiction_enters_search_memory_as_primary_block() -> None:
    creative = FakeCreative()
    search_memory = CampaignSearchMemory()
    session_ref = {
        "failure_category": "agent_grounding_failure",
        "failure_code": "proposal_premise_contradicted",
        "agent_block_reason": "agent_quality_blocked",
        "primary_failure": {
            "stage": "agent_quality_blocked",
            "reason": "proposal_premise_contradicted",
            "category": "agent_grounding_failure",
            "code": "proposal_premise_contradicted",
            "detail": "premise_check=contradicted: active solver has evidence",
        },
        "rejection_constraint": {
            "source": "mechanism_novelty_gate",
            "mechanism": "cross_route_or_opt_2_3",
            "premise_check": "contradicted",
            "failure_code": "proposal_premise_contradicted",
            "agent_block_reason": "agent_quality_blocked",
            "reason": (
                "Hypothesis claims inter-route Or-opt is missing, but active "
                "solver already has the mechanism."
            ),
            "evidence": ["_or_opt_1", "_or_opt_2", "_or_opt_3", "_or_opt"],
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
            "agentic_proposal:premise_contradicted: "
            "agent_quality_blocked:proposal_premise_contradicted:"
            "agent_grounding_failure"
        ),
        proposal_session_ref=session_ref,
    )

    search_memory.update(step)
    rendered = search_memory.render(view="hypothesis")

    assert "Agentic Grounding Blocks" in rendered
    assert "do not repeat cross_route_or_opt_2_3" in rendered
    assert "premise_check=contradicted" in rendered
    assert "active solver already has" in rendered
    assert "_or_opt_2" in rendered
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
        "failure_category": "agent_grounding_failure",
        "failure_code": "proposal_premise_contradicted",
        "agent_block_reason": "agent_quality_blocked",
        "primary_failure": {
            "stage": "agent_quality_blocked",
            "reason": "proposal_premise_contradicted",
            "category": "agent_grounding_failure",
            "code": "proposal_premise_contradicted",
            "detail": "active solver already contains the claimed mechanism",
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
    assert "proposal_premise_contradicted" in (steps[0].failure_detail or "")
    assert steps[0].proposal_session_ref == session_ref
    assert branch.failure_codes == ["PROPOSAL_PREMISE_CONTRADICTED"]
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
