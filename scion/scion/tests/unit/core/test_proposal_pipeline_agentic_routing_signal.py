"""Focused agentic proposal-boundary routing signal tests."""

from scion.core.proposal_pipeline import _agentic_failure_routing_signal
from scion.core.proposal_pipeline.constants import FRAMEWORK_CONTROL_FAILURE
from scion.core.branch_repair_policy import RepairPolicyCheck

from .proposal_pipeline_test_support import *  # noqa: F401,F403


def _failed_output(
    *,
    termination_reason: AgenticTerminationReason,
    failure_detail: str,
    failure_category: AgenticFailureCategory | str | None = None,
    structured_rejection: dict[str, str] | None = None,
) -> AgenticProposalOutput:
    return AgenticProposalOutput(
        status=AgenticProposalStatus.FAILED,
        session_id="routing-session",
        campaign_id="camp-1",
        branch_id="branch-1",
        champion_version=1,
        champion_weight_revision=0,
        problem_id="toy",
        problem_spec_hash="spec-hash",
        termination_reason=termination_reason,
        failure_detail=failure_detail,
        failure_category=failure_category,
        structured_rejection=structured_rejection,
    )


def _assert_records_route(
    output: AgenticProposalOutput,
    *,
    expected_lifecycle_category: str,
    expected_circuit_failure: bool,
    expected_control_timeout: bool = False,
    expected_llm_transient: bool = False,
    expected_framework_boundary: bool = False,
) -> None:
    for record_path in ("hypothesis", "code"):
        pipeline, branch, _, circuit, failures, _ = _pipeline(
            use_agentic_proposal=True,
        )
        detail = pipeline._agentic_failure_detail(output)
        signal = _agentic_failure_routing_signal(output, detail)

        assert signal.origin == "agentic_proposal_output"
        assert signal.source == "typed_output"
        assert signal.lifecycle_category == expected_lifecycle_category
        assert signal.record_circuit_failure is expected_circuit_failure
        assert signal.control_timeout is expected_control_timeout
        assert signal.llm_transient_api_error is expected_llm_transient
        assert signal.framework_boundary is expected_framework_boundary

        if record_path == "hypothesis":
            assert pipeline._record_agentic_failure(branch, detail, output) == (
                None,
                None,
            )
        else:
            pipeline._record_agentic_code_failure(
                branch,
                detail=detail,
                output=output,
            )

        assert len(failures) == 1
        failed_branch, failure = failures[0]
        assert failed_branch is branch
        assert failure.category == expected_lifecycle_category
        assert failure.detail == detail
        assert circuit.failures == ([detail] if expected_circuit_failure else [])


def test_typed_output_session_timeout_text_stays_proposal_circuit_failure() -> None:
    output = _failed_output(
        termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
        failure_detail=(
            "draft failed; diagnostic text mentioned session_timeout and "
            "max_wall_time_sec, but typed termination did not time out"
        ),
    )

    _assert_records_route(
        output,
        expected_lifecycle_category="proposal",
        expected_circuit_failure=True,
    )


def test_typed_output_bad_gateway_text_stays_proposal_circuit_failure() -> None:
    output = _failed_output(
        termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
        failure_detail=(
            "draft failed while summarizing a prior HTTP 502 Bad Gateway note"
        ),
    )

    _assert_records_route(
        output,
        expected_lifecycle_category="proposal",
        expected_circuit_failure=True,
    )


def test_typed_session_timeout_routes_framework_control_without_circuit() -> None:
    output = _failed_output(
        termination_reason=AgenticTerminationReason.SESSION_TIMEOUT,
        failure_detail="agentic proposal session exceeded max_wall_time_sec=10",
    )

    _assert_records_route(
        output,
        expected_lifecycle_category=FRAMEWORK_CONTROL_FAILURE,
        expected_circuit_failure=False,
        expected_control_timeout=True,
    )


def test_typed_llm_transient_category_routes_infra_without_circuit() -> None:
    output = _failed_output(
        termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
        failure_detail="Tool call failed after HTTP 502 Bad Gateway",
        failure_category=AgenticFailureCategory.LLM_TRANSIENT_API_ERROR,
    )

    _assert_records_route(
        output,
        expected_lifecycle_category="infra",
        expected_circuit_failure=False,
        expected_llm_transient=True,
    )


def test_exception_detail_signal_keeps_legacy_source_marked() -> None:
    signal = _agentic_failure_routing_signal(
        None,
        "agentic_proposal:session_timeout: max_wall_time_sec=10",
    )

    assert signal.origin == "exception_detail"
    assert signal.source == "legacy_detail_compat"
    assert signal.lifecycle_category == FRAMEWORK_CONTROL_FAILURE
    assert signal.record_circuit_failure is False
    assert signal.control_timeout is True


def test_exact_repair_policy_signal_stays_outside_lifecycle_and_circuit() -> None:
    policy_detail = RepairPolicyCheck(
        allowed=False,
        reason="unrelated mechanism",
        protected_mechanism_ids=("bounded_probe",),
        proposed_mechanism_ids=("new_restart",),
    ).detail
    output = _failed_output(
        termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
        failure_detail=policy_detail,
    )

    for record_path in ("hypothesis", "code"):
        pipeline, branch, _, circuit, failures, _ = _pipeline(
            use_agentic_proposal=True,
        )
        detail = pipeline._agentic_failure_detail(output)
        signal = _agentic_failure_routing_signal(output, detail)

        assert signal.origin == "agentic_proposal_output"
        assert signal.source == "typed_output"
        assert signal.lifecycle_category is None
        assert signal.record_circuit_failure is False
        assert signal.repair_policy_violation is True
        assert signal.framework_boundary is True

        if record_path == "hypothesis":
            assert pipeline._record_agentic_failure(branch, detail, output) == (
                None,
                None,
            )
        else:
            pipeline._record_agentic_code_failure(
                branch,
                detail=detail,
                output=output,
            )

        assert failures == []
        assert circuit.failures == []


def test_typed_framework_boundary_text_stays_proposal_circuit_failure() -> None:
    output = _failed_output(
        termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
        failure_detail=(
            "forced_surface_constraint: keep surface solver_design and target "
            "policies/baseline_algorithm.py"
        ),
        failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
    )

    _assert_records_route(
        output,
        expected_lifecycle_category="proposal",
        expected_circuit_failure=True,
    )


def test_structured_framework_boundary_signal_records_lifecycle_without_circuit() -> None:
    output = _failed_output(
        termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
        failure_detail=(
            "forced_surface_constraint: keep surface solver_design and target "
            "policies/baseline_algorithm.py"
        ),
        failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
        structured_rejection={
            "source": "hypothesis_boundary_gate",
            "failure_code": "forced_surface_constraint",
            "failure_category": (
                AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE.value
            ),
        },
    )

    _assert_records_route(
        output,
        expected_lifecycle_category="proposal",
        expected_circuit_failure=False,
        expected_framework_boundary=True,
    )
