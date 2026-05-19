"""Focused tests split from test_proposal_pipeline.py."""

from .proposal_pipeline_test_support import *  # noqa: F401,F403

def test_agentic_failed_session_returns_typed_hypothesis_failure() -> None:
    failed_output = AgenticProposalOutput(
        status=AgenticProposalStatus.FAILED,
        session_id="",
        campaign_id="",
        branch_id="",
        termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
        failure_detail="no valid surface",
    )
    pipeline, branch, _, circuit, failures, _ = _pipeline(
        use_agentic_proposal=True,
        agentic_session=AgenticProposalSession(injected_output=failed_output),
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is None
    assert record is None
    assert (
        pipeline.agentic_outputs[branch.branch_id].status
        == AgenticProposalStatus.FAILED
    )
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)
    assert detail == "agentic_proposal:hypothesis_generation_failed: no valid surface"
    assert len(failures) == 1
    assert circuit.failures == [detail]


def test_agentic_session_timeout_routes_framework_control_without_llm_breaker() -> None:
    failed_output = AgenticProposalOutput(
        status=AgenticProposalStatus.FAILED,
        session_id="session-timeout",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        champion_weight_revision=0,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        termination_reason=AgenticTerminationReason.SESSION_TIMEOUT,
        failure_detail="agentic proposal session exceeded max_wall_time_sec=10",
        failure_category=AgenticFailureCategory.TOOL_BUDGET_EXHAUSTED,
    )
    pipeline, branch, _, circuit, failures, _ = _pipeline(
        use_agentic_proposal=True,
        agentic_session=AgenticProposalSession(injected_output=failed_output),
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is None
    assert record is None
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)
    assert detail == (
        "agentic_proposal:session_timeout: "
        "agentic proposal session exceeded max_wall_time_sec=10"
    )
    assert len(failures) == 1
    failed_branch, failure = failures[0]
    assert failed_branch is branch
    assert failure.category == "framework_control"
    assert "session_timeout" in failure.detail
    assert circuit.failures == []


@pytest.mark.parametrize(
    ("override", "expected_field"),
    [
        ({"branch_id": "wrong-branch"}, "branch_id"),
        ({"champion_version": 99}, "champion_version"),
        ({"problem_spec_hash": "wrong-spec"}, "problem_spec_hash"),
    ],
)
def test_agentic_completed_output_with_mismatched_anchor_is_rejected(
    override,
    expected_field: str,
) -> None:
    creative = FakeCreative()
    output_kwargs = {
        "status": AgenticProposalStatus.COMPLETED,
        "session_id": "session-1",
        "campaign_id": "camp-1",
        "branch_id": "branch-1",
        "champion_version": 1,
        "champion_weight_revision": 0,
        "problem_id": "toy",
        "problem_spec_hash": "spec-hash",
        "hypothesis": creative.hypothesis,
        "patch": creative.patch,
        "termination_reason": AgenticTerminationReason.COMPLETED,
    }
    output_kwargs.update(override)
    output = AgenticProposalOutput(**output_kwargs)
    pipeline, branch, _, circuit, failures, _ = _pipeline(
        use_agentic_proposal=True,
        agentic_session=AgenticProposalSession(injected_output=output),
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)

    assert hypothesis is None
    assert record is None
    detail = pipeline.pop_hypothesis_failure_detail(branch.branch_id)
    assert detail is not None
    assert "agentic_proposal:anchor_validation_failed" in detail
    assert expected_field in detail
    assert pipeline.agentic_outputs[branch.branch_id].patch is None
    assert len(failures) == 1
    assert circuit.failures == [detail]


def test_agentic_artifact_dir_without_agentic_proposal_does_not_create_files(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "agentic"
    pipeline, branch, _, _, _, _ = _pipeline(
        use_agentic_proposal=False,
        agentic_artifact_dir=str(artifact_dir),
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)
    patch = pipeline.generate_code(branch, hypothesis)

    assert hypothesis is not None
    assert record is not None
    assert patch is not None
    assert not artifact_dir.exists()
    assert pipeline.agentic_outputs == {}


def test_unsafe_agentic_session_and_scratch_path_segments_raise_without_write(
    tmp_path: Path,
) -> None:
    root = tmp_path / "artifacts"
    store = FileAgenticSessionArtifactStore(root)
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.FAILED,
        session_id="../escape",
        campaign_id="camp-1",
        branch_id="branch-1",
    )

    with pytest.raises(ValueError, match="unsafe session artifact path segment"):
        store.write_output(output)
    with pytest.raises(ValueError, match="unsafe session artifact path segment"):
        store.write_scratch("session-1", "bad/name", {"x": 1})

    assert not root.exists()


def test_partial_patch_unchecked_with_patch_does_not_return_usable_patch() -> None:
    creative = FakeCreative()
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.PARTIAL_PATCH_UNCHECKED,
        session_id="session-1",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        champion_weight_revision=0,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        hypothesis=creative.hypothesis,
        patch=creative.patch,
    )
    pipeline, branch, _, circuit, failures, _ = _pipeline(
        use_agentic_proposal=True,
        agentic_session=AgenticProposalSession(injected_output=output),
    )

    hypothesis, record = pipeline.generate_hypothesis(branch)
    stored = pipeline.agentic_outputs[branch.branch_id]
    patch = pipeline.generate_code(branch, hypothesis)

    assert hypothesis == creative.hypothesis
    assert record is not None
    assert stored.patch is None
    assert patch is None
    assert len(failures) == 1
    assert "non-completed output included unchecked patch" in failures[0][1].detail
    assert circuit.failures == [failures[0][1].detail]
