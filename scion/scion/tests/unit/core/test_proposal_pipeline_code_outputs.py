"""Focused tests split from test_proposal_pipeline.py."""

from .proposal_pipeline_test_support import *  # noqa: F401,F403

def test_agentic_approved_continuation_can_build_code_context_and_patch() -> None:
    creative = FakeCreative()
    events: list[str] = []

    class ContinuationSession:
        def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
            if request.approved_hypothesis is None:
                events.append("hypothesis")
                return AgenticProposalOutput(
                    status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
                    session_id="session-hyp",
                    campaign_id=request.campaign_id,
                    branch_id=request.branch.branch_id,
                    champion_version=(
                        request.champion.version if request.champion else None
                    ),
                    problem_id=request.problem_id,
                    problem_spec_hash=request.problem_spec_hash,
                    hypothesis=creative.hypothesis,
                    termination_reason=(
                        AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL
                    ),
                )

            events.append("continuation")
            code_context = request.build_code_context(request.approved_hypothesis)
            assert code_context["kind"] == "code"
            events.append("code_context")
            return AgenticProposalOutput(
                status=AgenticProposalStatus.COMPLETED,
                session_id="session-code",
                campaign_id=request.campaign_id,
                branch_id=request.branch.branch_id,
                champion_version=request.champion.version if request.champion else None,
                problem_id=request.problem_id,
                problem_spec_hash=request.problem_spec_hash,
                hypothesis=request.approved_hypothesis,
                patch=creative.patch,
                termination_reason=AgenticTerminationReason.COMPLETED,
            )

    pipeline, branch, runtime, _, failures, _ = _pipeline(
        creative=creative,
        agentic_session=ContinuationSession(),
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)
    patch = pipeline.generate_code(branch, hypothesis)

    assert hypothesis == creative.hypothesis
    assert record is not None
    assert patch == creative.patch
    assert events == ["hypothesis", "continuation", "code_context"]
    assert runtime.code_kwargs["hypothesis"] == creative.hypothesis
    assert failures == []


def test_agentic_completed_output_failed_self_check_rejected_before_patch_use() -> None:
    creative = FakeCreative()
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.COMPLETED,
        session_id="session-code",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        champion_weight_revision=0,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        hypothesis=creative.hypothesis,
        patch=creative.patch,
        transcript=(
            AgenticTranscriptEvent(
                phase="self_check",
                message="preview failed",
                metadata={"tool_name": "proposal.contract_preview"},
            ),
        ),
        self_check=AgenticSelfCheck(
            schema_valid=False,
            contract_preview_passed=False,
            contract_preview_codes=("result_too_large", "tool_skipped"),
        ),
        tool_budget_used={"tool_calls": 8, "tool_steps": 8},
        termination_reason=AgenticTerminationReason.COMPLETED,
    )
    pipeline, branch, _, circuit, failures, _ = _pipeline(
        creative=creative,
        agentic_session=AgenticProposalSession(injected_output=output),
    )

    patch = pipeline.generate_code(branch, creative.hypothesis)

    assert patch is None
    assert len(failures) == 1
    assert "agentic_self_check_failed" in failures[0][1].detail
    assert circuit.failures == [failures[0][1].detail]


def test_agentic_completed_output_produces_existing_hypothesis_and_patch_shapes(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
    artifact_dir = tmp_path / "artifacts" / "agentic_proposal_sessions"
    pipeline, branch, runtime, circuit, failures, _ = _pipeline(
        creative=creative,
        use_agentic_proposal=True,
        agentic_artifact_dir=str(artifact_dir),
        branch_workspace=str(tmp_path / "candidate-workspace"),
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)
    patch = pipeline.generate_code(branch, hypothesis)

    assert hypothesis == creative.hypothesis
    assert record is not None
    assert patch == creative.patch
    assert creative.hypothesis_calls == 1
    assert creative.code_calls == 1
    assert circuit.successes == 2
    assert failures == []
    assert runtime.code_kwargs["hypothesis"] == creative.hypothesis
    assert not (tmp_path / "candidate-workspace").exists()

    artifact_refs = sorted(
        str(p)
        for p in artifact_dir.rglob("*.json")
        if p.name in {"output.json", "transcript.json"}
    )
    assert len(artifact_refs) == 4
    for ref in artifact_refs:
        path = Path(ref).resolve()
        assert artifact_dir.resolve() in path.parents


def test_agentic_partial_session_returns_no_patch_and_routes_proposal_failure() -> None:
    creative = FakeCreative(code_error=LLMRetryExhaustedError("code failed"))
    pipeline, branch, _, circuit, failures, _ = _pipeline(
        creative=creative,
        use_agentic_proposal=True,
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis == creative.hypothesis
    assert record is not None
    output = pipeline.agentic_outputs[branch.branch_id]
    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert (
        output.termination_reason
        == AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL
    )
    assert output.patch is None
    assert creative.code_calls == 0

    patch = pipeline.generate_code(branch, hypothesis)

    assert patch is None
    assert len(failures) == 1
    assert failures[0][1].category == "proposal"
    assert "agentic_proposal:code_generation_failed" in failures[0][1].detail
    assert circuit.failures == [failures[0][1].detail]
