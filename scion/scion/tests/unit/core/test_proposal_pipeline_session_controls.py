"""Focused tests split from test_proposal_pipeline.py."""

from .proposal_pipeline_test_support import *  # noqa: F401,F403

def test_generate_code_failure_routes_proposal_failure() -> None:
    creative = FakeCreative(code_error=LLMRetryExhaustedError("code failed"))
    pipeline, branch, _, circuit, failures, _ = _pipeline(creative=creative)

    patch = pipeline.generate_code(branch, creative.hypothesis, prior_failure="first")

    assert patch is None
    assert circuit.failures == ["code failed"]
    assert len(failures) == 1
    failed_branch, failure = failures[0]
    assert failed_branch is branch
    assert failure.category == "proposal"
    assert failure.detail == "code failed"


def test_default_agentic_session_has_registry_and_requests_get_tool_context() -> None:
    captured: list[AgenticProposalRequest] = []

    class CapturingSession:
        def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
            captured.append(request)
            return AgenticProposalOutput(
                status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
                session_id="session-1",
                campaign_id=request.campaign_id,
                branch_id=request.branch.branch_id,
                champion_version=request.champion.version if request.champion else None,
                problem_id=request.problem_id,
                problem_spec_hash=request.problem_spec_hash,
                hypothesis=FakeCreative().hypothesis,
                termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
            )

    pipeline, branch, _, _, _, _ = _pipeline(
        use_agentic_proposal=True,
        agentic_session=CapturingSession(),
    )

    default_session = _pipeline(use_agentic_proposal=True)[0]._get_agentic_session()
    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert isinstance(default_session, AgenticProposalSession)
    assert isinstance(default_session.tool_registry, ProposalToolRegistry)
    assert "context.list_surfaces" in default_session.tool_registry.list_tools()
    assert hypothesis is not None
    assert record is not None
    assert len(captured) == 1
    assert isinstance(captured[0].tool_context, ProposalToolContext)
    assert captured[0].tool_context.branch is branch
    assert captured[0].tool_context.problem_id == "toy"


def test_default_agentic_session_uses_configured_timeout() -> None:
    pipeline, _, _, _, _, _ = _pipeline(
        use_agentic_proposal=True,
        agentic_session_timeout_sec=7.5,
    )

    session = pipeline._get_agentic_session()

    assert isinstance(session, AgenticProposalSession)
    assert session._tool_loop_config.max_wall_time_sec == 7.5


def test_agentic_session_invalid_target_does_not_build_code_context_or_patch(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
    creative.hypothesis = HypothesisProposal(
        hypothesis_text="Try an invalid target.",
        change_locus="local_search",
        action="modify",
        target_file="secret/forbidden.py",
    )
    champion_root = tmp_path / "champion"
    target = champion_root / "secret" / "forbidden.py"
    target.parent.mkdir(parents=True)
    target.write_text("SECRET_TARGET_CONTENT = True\n", encoding="utf-8")
    build_calls = 0

    def build_code_context(_hypothesis):
        nonlocal build_calls
        build_calls += 1
        target.read_text(encoding="utf-8")
        raise AssertionError("code context must not be built before approval")

    session = AgenticProposalSession(creative)
    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=_branch(),
            champion=_champion(),
            hypothesis_context={"kind": "hypothesis"},
            build_code_context=build_code_context,
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=False,
                failure_reason="C3_action_target: invalid target_file",
            ),
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert (
        output.termination_reason
        == AgenticTerminationReason.HYPOTHESIS_APPROVAL_FAILED
    )
    assert output.hypothesis == creative.hypothesis
    assert output.patch is None
    assert build_calls == 0
    assert creative.code_calls == 0
    assert "SECRET_TARGET_CONTENT" not in str(output)


def test_agentic_pipeline_hypothesis_request_denies_custom_code_context_read(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
    target = tmp_path / "champion" / "operators" / "bounded.py"
    target.parent.mkdir(parents=True)
    target.write_text("SECRET_TARGET_CONTENT = True\n", encoding="utf-8")
    target_reads = 0

    class MaliciousSession:
        attempted = False

        def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
            self.attempted = True
            request.build_code_context(creative.hypothesis)
            raise AssertionError("unapproved code context was available")

    session = MaliciousSession()
    pipeline, branch, runtime, circuit, failures, _ = _pipeline(
        creative=creative,
        agentic_session=session,
    )

    def forbidden_build_code_context(**kwargs):
        nonlocal target_reads
        target_reads += 1
        target.read_text(encoding="utf-8")
        return {"kind": "code", **kwargs}

    runtime.build_code_context = forbidden_build_code_context

    hypothesis, record = pipeline.generate_hypothesis(branch)
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)

    assert hypothesis is None
    assert record is None
    assert session.attempted is True
    assert detail is not None
    assert "ContractGate-approved hypothesis" in detail
    assert runtime.code_kwargs is None
    assert target_reads == 0
    assert "SECRET_TARGET_CONTENT" not in str(pipeline.agentic_outputs)
    assert len(failures) == 1
    assert circuit.failures == []


def test_agentic_session_builds_code_context_only_after_hypothesis_contract_pass() -> None:
    creative = FakeCreative()
    events: list[str] = []

    def approve_hypothesis(_hypothesis):
        events.append("approve")
        return SimpleNamespace(passed=True, failure_reason=None)

    def build_code_context(hypothesis):
        events.append("build_code_context")
        assert hypothesis == creative.hypothesis
        return {"kind": "code"}

    session = AgenticProposalSession(creative)
    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=_branch(),
            champion=_champion(),
            hypothesis_context={"kind": "hypothesis"},
            build_code_context=build_code_context,
            approve_hypothesis=approve_hypothesis,
        )
    )

    assert events == ["approve", "build_code_context"]
    assert output.is_completed
    assert isinstance(output.hypothesis, HypothesisProposal)
    assert isinstance(output.patch, PatchProposal)


def test_agentic_completed_patch_before_approval_is_downgraded_and_cleared() -> None:
    creative = FakeCreative()
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.COMPLETED,
        session_id="session-1",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        champion_weight_revision=0,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        hypothesis=creative.hypothesis,
        patch=creative.patch,
        termination_reason=AgenticTerminationReason.COMPLETED,
    )
    pipeline, branch, runtime, _, failures, _ = _pipeline(
        creative=creative,
        agentic_session=AgenticProposalSession(injected_output=output),
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)
    stored = pipeline.agentic_outputs[branch.branch_id]

    assert hypothesis == creative.hypothesis
    assert record is not None
    assert stored.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert (
        stored.termination_reason
        == AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL
    )
    assert stored.patch is None
    assert "before ContractGate-approved hypothesis" in (stored.failure_detail or "")
    assert runtime.code_kwargs is None
    assert creative.code_calls == 0
    assert failures == []


def test_agentic_forced_surface_rejects_off_surface_hypothesis_before_code() -> None:
    creative = FakeCreative()
    off_surface = HypothesisProposal(
        hypothesis_text="Try route-local work despite a forced policy surface.",
        change_locus="route_local",
        action="create_new",
        target_file="operators/local_new.py",
    )
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
        session_id="session-1",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        champion_weight_revision=0,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        hypothesis=off_surface,
        termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
    )
    pipeline, branch, runtime, circuit, failures, _ = _pipeline(
        creative=creative,
        agentic_session=AgenticProposalSession(injected_output=output),
        forced_locus=None,
        persistent_forced_locus="solver_design",
        forced_surface_action="modify",
        forced_surface_target_file="policies/baseline_algorithm.py",
        forced_surface_diagnostic=True,
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is None
    assert record is None
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)
    assert detail is not None
    assert "forced_surface_constraint" in detail
    assert "solver_design" in detail
    assert len(failures) == 1
    assert circuit.failures == []
    assert runtime.code_kwargs is None
    assert creative.code_calls == 0


def test_agentic_active_problem_boundary_rejects_component_hypothesis() -> None:
    creative = FakeCreative()
    component = HypothesisProposal(
        hypothesis_text="Tune a component policy outside the active boundary.",
        change_locus="baseline_policy",
        action="modify",
        target_file="policies/baseline_policy.py",
    )
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
        session_id="session-1",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        champion_weight_revision=0,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        hypothesis=component,
        termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
    )
    solver_design_spec = SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="solver_design",
                kind="solver_design",
                algorithm=SimpleNamespace(role="problem_object_solver_algorithm"),
            ),
            SimpleNamespace(
                name="baseline_policy",
                kind="policy",
                algorithm=SimpleNamespace(role="component_policy"),
            ),
        ]
    )
    pipeline, branch, runtime, circuit, failures, _ = _pipeline(
        creative=creative,
        agentic_session=AgenticProposalSession(injected_output=output),
        forced_locus=None,
        problem_spec=solver_design_spec,
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is None
    assert record is None
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)
    assert detail is not None
    assert "active_problem_boundary_constraint" in detail
    assert "solver_design" in detail
    assert len(failures) == 1
    assert circuit.failures == [detail]
    assert runtime.code_kwargs is None
    assert creative.code_calls == 0
