from __future__ import annotations

from scion.core.models import Decision, EvalStats, ExperimentStage, ProtocolResult, StepRecord
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


def _duplicate_or_opt_hypothesis() -> HypothesisProposal:
    return HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_modules/local_search.py",
            hypothesis_text=(
                "The active solver lacks inter-route Or-opt segment relocation; "
                "add an NN-filtered cross-route segment relocation neighborhood."
            ),
            target_weakness=(
                "The active solver lacks inter-route Or-opt segment relocation."
            ),
            expected_effect="Improve total_distance with a new cross-route Or-opt move.",
            mechanism_changes=[
                {"id": "cross_route_oropt", "change_type": "add"},
            ],
            novelty_signature={
                "algorithm_family": "vns_local_search",
                "construction_strategy": "preserve_existing_construction",
                "improvement_strategy": "new_cross_route_oropt",
                "acceptance_strategy": "preserve_existing_acceptance",
                "runtime_budget_strategy": "bounded_neighbor_pairs",
            },
            expected_telemetry=_good_vns_mechanism_telemetry(),
        )
    )


def _targeted_multi_relocate_hypothesis() -> HypothesisProposal:
    return HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_modules/local_search.py",
            hypothesis_text=(
                "Add targeted_multi_relocate as a new local-search mechanism "
                "for high-cost customers."
            ),
            target_weakness="The active local search misses targeted multi relocate.",
            expected_effect="Improve total_distance with targeted relocations.",
            mechanism_changes=[
                {"id": "targeted_multi_relocate", "change_type": "add"},
            ],
            novelty_signature={
                "algorithm_family": "targeted_multi_relocate",
                "construction_strategy": "preserve_existing_construction",
                "improvement_strategy": "targeted_multi_relocate",
                "acceptance_strategy": "preserve_existing_acceptance",
                "runtime_budget_strategy": "bounded_relocation_pairs",
            },
            expected_telemetry=_good_vns_mechanism_telemetry(),
        )
    )


def _failed_screening_step(hypothesis: HypothesisProposal) -> StepRecord:
    return StepRecord(
        round_num=4,
        branch_id="branch-cvrp",
        hypothesis=hypothesis,
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=EvalStats(
                n_cases=16,
                wins=0,
                losses=0,
                ties=16,
                win_rate=0.0,
                median_delta=0.0,
                ci_low=0.0,
                ci_high=0.0,
            ),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="screening failed",
            raw_metrics_ref="/tmp/screening.json",
        ),
        decision=Decision.CONTINUE_EXPLORE,
        failure_stage=None,
        failure_detail=None,
        decision_reason_codes=("SCREENING_FAIL_WIN_RATE",),
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


def test_semantic_retry_then_self_check_c11_retry_reaches_approval(
    tmp_path: Path,
) -> None:
    duplicate = _duplicate_or_opt_hypothesis()
    bad = _vns_hypothesis(_bad_vns_phase_telemetry())
    good = _vns_hypothesis(_good_vns_mechanism_telemetry())
    creative = SequentialHypothesisCreative([duplicate, bad, good])
    context = _cvrp_context_with_champion(tmp_path)
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-semantic-then-c11-retry",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "semantic-then-preview"},
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
    assert len(creative.hypothesis_contexts) == 3
    assert (
        creative.hypothesis_contexts[1]["agentic_hypothesis_semantic_rejections"][0][
            "mechanism"
        ]
        == "cross_route_or_opt_2_3"
    )
    preview_feedback = creative.hypothesis_contexts[2][
        "agentic_hypothesis_preview_rejections"
    ][0]
    assert preview_feedback["failure_code"] == "C11_expected_telemetry"
    assert "solver_algorithm_phase_runtime_ms.vns" in json.dumps(preview_feedback)

    transcript = output.transcript
    assert any(
        "Mechanism novelty gate rejected hypothesis" in event.message
        for event in transcript
    )
    assert any(
        event.metadata.get("tool_name") == "proposal.schema_preview"
        and "solver_algorithm_phase_runtime_ms.vns"
        in event.metadata.get("result_summary", "")
        for event in transcript
    )
    assert any(
        "Hypothesis preview gate rejected hypothesis" in event.message
        and event.metadata.get("failure_code") == "C11_expected_telemetry"
        for event in transcript
    )


def test_repeated_mechanism_semantic_retry_feedback_enters_hypothesis_context(
    tmp_path: Path,
) -> None:
    repeat = _targeted_multi_relocate_hypothesis()
    good = _vns_hypothesis(_good_vns_mechanism_telemetry())
    creative = SequentialHypothesisCreative([repeat, good])
    context = _cvrp_context_with_champion(tmp_path)
    context = replace(
        context,
        step_history=(_failed_screening_step(repeat),),
    )
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-repeated-mechanism-retry",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "repeated-mechanism"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.hypothesis == good
    assert len(creative.hypothesis_contexts) == 2
    retry_feedback = creative.hypothesis_contexts[1][
        "agentic_hypothesis_semantic_rejections"
    ][0]
    assert retry_feedback["failure_category"] == "repeated_mechanism"
    assert retry_feedback["mechanism"] == "targeted_multi_relocate"
    assert "SCREENING_FAIL_WIN_RATE" in retry_feedback["reason"]


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


def test_non_repairable_target_preview_failure_fails_closed(
    tmp_path: Path,
) -> None:
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            target_file="policies/not_declared.py",
        )
    )
    creative = SequentialHypothesisCreative([hypothesis])
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-target-fail-closed",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "target-fail-closed"},
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
    assert len(creative.hypothesis_contexts) == 1
    assert output.failure_category == "contract_boundary_failure"
    assert output.failure_detail is not None
    assert "schema or target preview did not pass" in output.failure_detail
    assert "C11_expected_telemetry" not in output.failure_detail
