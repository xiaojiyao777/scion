from __future__ import annotations

from scion.tests.unit.agentic_session_test_support import *


class SequentialHypothesisCreative(FakeCreative):
    def __init__(self, hypotheses: list[HypothesisProposal]) -> None:
        super().__init__(hypothesis=hypotheses[-1])
        self.hypotheses = list(hypotheses)

    def generate_hypothesis(self, context):
        self.hypothesis_contexts.append(dict(context))
        if not self.hypotheses:
            return self.hypothesis
        return self.hypotheses.pop(0)


def _vns_hypothesis(expected_telemetry: dict) -> HypothesisProposal:
    return HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_modules/local_search.py",
            hypothesis_text=(
                "VNS local search uses fixed neighborhood ordering. Add a "
                "VNS-local adaptive neighborhood scheduler that learns from "
                "recent improvement success while preserving fleet_violation."
            ),
            target_weakness=(
                "The local-search phase does not adapt VNS neighborhood order "
                "from recent success."
            ),
            expected_effect=(
                "Improve total_distance by spending VNS effort on productive "
                "neighborhoods."
            ),
            no_op_condition=(
                "Fall back to fixed VNS ordering when the adaptive scheduler has "
                "no positive activation evidence."
            ),
            mechanism_changes=[
                {
                    "id": "adaptive_vns_operator_weights",
                    "change_type": "add",
                }
            ],
            novelty_signature={
                "algorithm_family": "adaptive_vns",
                "construction_strategy": "preserve_existing_construction",
                "improvement_strategy": "adaptive_vns_neighborhood_ordering",
                "acceptance_strategy": "preserve_existing_acceptance",
                "runtime_budget_strategy": "bounded_vns_segments",
            },
            expected_telemetry=expected_telemetry,
        )
    )


def _bad_vns_phase_telemetry() -> dict:
    return {
        "activity": ["solver_algorithm_search_iterations"],
        "activation": ["solver_algorithm_phase_runtime_ms.vns"],
        "effect": [
            "solver_algorithm_phase_improvement_counts."
            "adaptive_vns_operator_weights"
        ],
        "budget": [
            "solver_algorithm_phase_runtime_ms.adaptive_vns_operator_weights"
        ],
    }


def _good_vns_mechanism_telemetry() -> dict:
    return {
        "activity": ["solver_algorithm_search_iterations"],
        "activation": [
            "solver_algorithm_context_records."
            "adaptive_vns_operator_weights_iterations",
            "solver_algorithm_phase_runtime_ms.adaptive_vns_operator_weights",
        ],
        "effect": [
            "solver_algorithm_phase_improvement_counts."
            "adaptive_vns_operator_weights"
        ],
        "budget": [
            "solver_algorithm_phase_runtime_ms.adaptive_vns_operator_weights"
        ],
    }


def test_hypothesis_preview_c11_feedback_retries_to_corrected_hypothesis(
    tmp_path: Path,
) -> None:
    bad = _vns_hypothesis(_bad_vns_phase_telemetry())
    good = _vns_hypothesis(_good_vns_mechanism_telemetry())
    creative = SequentialHypothesisCreative([bad, good])
    context = _cvrp_context_with_champion(tmp_path)
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-hyp-preview-retry",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "preview-retry"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert (
        output.termination_reason
        == AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL
    )
    assert output.hypothesis == good
    assert output.self_check.schema_valid is True
    assert len(creative.hypothesis_contexts) == 2
    retry_context = creative.hypothesis_contexts[1]
    retry_feedback = retry_context["agentic_hypothesis_preview_rejections"][0]
    assert retry_feedback["failure_code"] == "C11_expected_telemetry"
    assert "solver_algorithm_phase_runtime_ms.vns" in json.dumps(retry_feedback)
    assert ".vns" in retry_feedback["retry_constraint"]
    assert "declared_mechanism_runtime_fields" in retry_feedback
    assert any(
        event.metadata.get("failure_code") == "C11_expected_telemetry"
        for event in output.transcript
    )


def test_hypothesis_preview_c11_retry_exhaustion_fails_with_clear_detail(
    tmp_path: Path,
) -> None:
    bad = _vns_hypothesis(_bad_vns_phase_telemetry())
    creative = SequentialHypothesisCreative([bad, bad])
    context = _cvrp_context_with_champion(tmp_path)
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-hyp-preview-exhausted",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "preview-retry-exhausted"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.FAILED
    assert output.patch is None
    assert creative.code_contexts == []
    assert len(creative.hypothesis_contexts) == 2
    assert output.failure_category == "contract_boundary_failure"
    assert output.failure_detail is not None
    assert "C11_expected_telemetry" in output.failure_detail
    assert "solver_algorithm_phase_runtime_ms.vns" in output.failure_detail
    assert output.self_check.schema_valid is False
    assert output.failure_ledger["latest_failure"] == "schema_output_failure"
    assert (
        output.failure_ledger["entries"][-1]["failure_code"]
        == "C11_expected_telemetry"
    )
