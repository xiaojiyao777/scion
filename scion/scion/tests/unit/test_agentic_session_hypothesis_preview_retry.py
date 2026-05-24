from __future__ import annotations

from scion.core.models import (
    Decision,
    EvalStats,
    ExperimentStage,
    MechanismChange,
    ProtocolResult,
    StepRecord,
)
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


class SequentialHypothesisToolClient:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = list(payloads)
        self.tool_names: list[str] = []

    def call_with_tool(
        self,
        prompt,
        tool,
        model=None,
        system_blocks=None,
        request_kind=None,
    ):
        del prompt, model, system_blocks, request_kind
        self.tool_names.append(tool["name"])
        if tool["name"] == "plan_proposal_tool_call":
            return {"intent": "stop"}
        if tool["name"] == "generate_hypothesis":
            if not self.payloads:
                raise AssertionError("generate_hypothesis called too many times")
            return self.payloads.pop(0)
        raise AssertionError(f"unexpected tool request: {tool['name']}")


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
    creative = SequentialHypothesisCreative([bad, bad, good])
    context = _cvrp_context_with_champion(tmp_path)
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
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
    assert len(creative.hypothesis_contexts) == 3
    assert "agentic_hypothesis_grounding_rejections" in creative.hypothesis_contexts[1]
    retry_context = creative.hypothesis_contexts[2]
    retry_feedback = retry_context["agentic_hypothesis_preview_rejections"][0]
    assert retry_feedback["failure_code"] == "C11_expected_telemetry"
    assert "solver_algorithm_phase_runtime_ms.vns" in json.dumps(retry_feedback)
    assert "Repair only expected_telemetry/schema fields" in retry_feedback[
        "retry_constraint"
    ]
    assert "switch mechanisms or targets" in retry_feedback["retry_constraint"]
    assert "declared_runtime_fields" not in retry_feedback
    assert "declared_mechanism_runtime_fields" not in retry_feedback
    assert retry_feedback["allowed_expected_telemetry_template"][
        "expected_telemetry"
    ]["activation"] == [
        "solver_algorithm_context_records.adaptive_vns_operator_weights_iterations",
        "solver_algorithm_phase_runtime_ms.adaptive_vns_operator_weights",
    ]
    assert retry_feedback["preserve_hypothesis"]["target_file"] == (
        "policies/baseline_modules/local_search.py"
    )
    assert retry_feedback["preserve_hypothesis"]["mechanism_changes"] == [
        {"id": "adaptive_vns_operator_weights", "change_type": "add"}
    ]
    assert any(
        event.metadata.get("failure_code") == "C11_expected_telemetry"
        for event in output.transcript
    )
    manifests = [
        json.loads(Path(ref).read_text(encoding="utf-8"))
        for ref in output.tainted_artifact_refs
        if "api_visible_prompt_manifest" in ref
    ]
    retry_manifests = [
        manifest
        for manifest in manifests
        if manifest.get("call_kind") == "hypothesis_preview_retry"
    ]
    assert retry_manifests
    retry_manifest = retry_manifests[0]
    feedback_status = retry_manifest["section_statuses"][
        "hypothesis_schema_telemetry_retry_feedback"
    ]
    assert feedback_status["status"] == "included"
    assert "hypothesis_schema_telemetry_retry_feedback" not in retry_manifest[
        "truncated_sections"
    ]


def test_hypothesis_preview_c11_retry_allows_runtime_free_text_rewrite(
    tmp_path: Path,
) -> None:
    bad = _vns_hypothesis(_bad_vns_phase_telemetry())
    good = _vns_hypothesis(_good_vns_mechanism_telemetry())
    rewritten = replace(
        good,
        hypothesis_text=(
            good.hypothesis_text
            + " The schema retry restates the runtime expectation more compactly."
        ),
        expected_effect=(
            "Improve total_distance by using the same adaptive VNS mechanism "
            "with clearer telemetry declarations."
        ),
        target_runtime_effect=(
            "Shift VNS time toward recently productive existing neighborhoods "
            "within the same bounded local-search budget."
        ),
        novelty_signature={
            **dict(good.novelty_signature or {}),
            "algorithm_family": (
                "adaptive neighborhood policy for the same VNS operator set"
            ),
            "construction_strategy": (
                "leave construction unchanged while restating the schema repair"
            ),
            "improvement_strategy": (
                "sliding-window success-rate reordering of neighborhood "
                "operators per pass"
            ),
            "acceptance_strategy": (
                "keep the incumbent acceptance rule unchanged"
            ),
            "runtime_budget_strategy": (
                "bounded_existing_vns_operator_reordering_with_schema_valid_telemetry"
            ),
        },
    )
    creative = SequentialHypothesisCreative([bad, bad, rewritten])
    context = _cvrp_context_with_champion(tmp_path)
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-c11-free-text-allowed",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "preview-retry-free-text"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.hypothesis == rewritten
    assert output.self_check.schema_valid is True
    assert not any(
        event.metadata.get("failure_code") == "schema_retry_drift"
        for event in output.transcript
    )


def test_hypothesis_preview_c11_retry_blocks_mechanism_target_drift(
    tmp_path: Path,
) -> None:
    bad = _vns_hypothesis(_bad_vns_phase_telemetry())
    drifted = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_modules/scheduler.py",
            hypothesis_text=(
                "After schema retry, switch to a scheduler restart mechanism "
                "instead of repairing the prior VNS telemetry declaration."
            ),
            target_weakness="Scheduler restart cadence is fixed.",
            expected_effect="Improve total_distance through restart perturbations.",
            no_op_condition="Keep the existing scheduler when no restart evidence appears.",
            mechanism_changes=[
                {
                    "id": "adaptive_scheduler_restart",
                    "change_type": "add",
                }
            ],
            novelty_signature={
                "algorithm_family": "adaptive_scheduler_restart",
                "construction_strategy": "preserve_existing_construction",
                "improvement_strategy": "restart_after_stagnation",
                "acceptance_strategy": "preserve_existing_acceptance",
                "runtime_budget_strategy": "bounded_restart_checks",
            },
            expected_telemetry=_good_vns_mechanism_telemetry(),
        )
    )
    creative = SequentialHypothesisCreative([bad, bad, drifted])
    context = _cvrp_context_with_champion(tmp_path)
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-c11-drift-block",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "preview-retry-drift"},
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
    assert len(creative.hypothesis_contexts) == 4
    assert output.failure_category == "contract_boundary_failure"
    assert output.failure_detail is not None
    assert "schema_retry_drift" in output.failure_detail
    assert "target_file" in output.failure_detail
    assert "mechanism_changes" in output.failure_detail
    assert output.failure_ledger["entries"][-1]["failure_code"] == "schema_retry_drift"
    assert any(
        event.metadata.get("failure_code") == "schema_retry_drift"
        and event.metadata.get("corrective_retry") is True
        for event in output.transcript
    )


def test_hypothesis_preview_c11_retry_corrects_identity_drift(
    tmp_path: Path,
) -> None:
    bad = _vns_hypothesis(_bad_vns_phase_telemetry())
    drifted = replace(
        _vns_hypothesis(_good_vns_mechanism_telemetry()),
        target_file="policies/baseline_modules/scheduler.py",
        mechanism_changes=(
            MechanismChange(id="or_opt1_nn", change_type="add"),
        ),
    )
    restored = _vns_hypothesis(_good_vns_mechanism_telemetry())
    creative = SequentialHypothesisCreative([bad, bad, drifted, restored])
    context = _cvrp_context_with_champion(tmp_path)
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-c11-drift-corrective-retry",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "preview-retry-drift-corrective"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert output.hypothesis == restored
    assert len(creative.hypothesis_contexts) == 4
    corrective_context = creative.hypothesis_contexts[3]
    drift_feedback = corrective_context["agentic_hypothesis_preview_rejections"][-1]
    assert drift_feedback["failure_code"] == "schema_retry_drift"
    assert drift_feedback["corrective_retry"] is True
    assert drift_feedback["protected_identity"]["target_file"] == (
        "policies/baseline_modules/local_search.py"
    )
    assert drift_feedback["protected_identity"]["protected_mechanism_ids"] == [
        "adaptive_vns_operator_weights"
    ]
    assert output.failure_detail == "hypothesis awaits ContractGate approval"
    assert any(
        event.metadata.get("failure_code") == "schema_retry_drift"
        and event.metadata.get("corrective_retry") is True
        for event in output.transcript
    )


def test_hypothesis_preview_c11_retry_blocks_activation_mechanism_drift(
    tmp_path: Path,
) -> None:
    bad = _vns_hypothesis(_bad_vns_phase_telemetry())
    drifted_telemetry = _good_vns_mechanism_telemetry()
    drifted_telemetry["activation"] = [
        "solver_algorithm_context_records.nn_relocate_iterations",
        "solver_algorithm_phase_runtime_ms.nn_relocate",
    ]
    drifted = replace(
        _vns_hypothesis(drifted_telemetry),
        target_runtime_effect=(
            "Keep the same prose, but incorrectly point activation telemetry "
            "at a different mechanism."
        ),
    )
    creative = SequentialHypothesisCreative([bad, bad, drifted])
    context = _cvrp_context_with_champion(tmp_path)
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-c11-activation-drift",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "preview-retry-activation-drift"},
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
    assert len(creative.hypothesis_contexts) == 4
    assert output.failure_category == "contract_boundary_failure"
    assert output.failure_detail is not None
    assert "schema_retry_drift" in output.failure_detail
    assert "expected_telemetry.activation" in output.failure_detail
    assert output.failure_ledger["entries"][-1]["failure_code"] == "schema_retry_drift"


def test_hypothesis_text_survives_preview_failure_artifact_serialization(
    tmp_path: Path,
) -> None:
    hypothesis_text = (
        "The current simulated annealing acceptance cools monotonically, and "
        "the search can become trapped behind a frozen SA temperature after "
        "early improvements. Add a bounded stagnation-triggered reheat so the "
        "acceptance probability can recover without changing feasibility "
        "checks or the operator portfolio."
    )
    bad_payload = _valid_hypothesis_payload(
        change_locus="solver_design",
        target_file="policies/baseline_modules/acceptance.py",
        hypothesis_text=hypothesis_text,
        target_weakness=(
            "The acceptance temperature can freeze before late search "
            "diversification is useful."
        ),
        expected_effect="Improve total_distance by escaping late local optima.",
        mechanism_changes=[{"id": "sa_reheat", "change_type": "add"}],
        novelty_signature={
            "algorithm_family": "alns_with_sa_reheat",
            "construction_strategy": "preserve_existing_construction",
            "improvement_strategy": "preserve_existing_vns_portfolio",
            "acceptance_strategy": "stagnation_triggered_sa_reheat",
            "runtime_budget_strategy": "bounded_reheat_checks",
        },
        expected_telemetry={
            "activity": ["solver_algorithm_search_iterations"],
            "activation": {
                "sa_reheat": [
                    "solver_algorithm_accepted_moves",
                    "solver_algorithm_neutral_accepted_moves",
                ]
            },
            "effect": ["solver_algorithm_best_delta"],
            "budget": ["solver_algorithm_elapsed_ms"],
        },
    )
    client = SequentialHypothesisToolClient(
        [bad_payload, dict(bad_payload), dict(bad_payload)]
    )
    creative = CreativeLayer(client, model="test-model")
    context = _cvrp_context_with_champion(tmp_path)
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-hyp-text-handoff",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "hypothesis-text-handoff"},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=None,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    output_ref = next(
        ref for ref in output.tainted_artifact_refs if ref.endswith("output.json")
    )
    artifact = json.loads(Path(output_ref).read_text(encoding="utf-8"))
    rendered_codes = json.dumps(output.self_check.schema_preview_codes)
    ledger_entry = artifact["failure_ledger"]["entries"][0]

    assert output.status == AgenticProposalStatus.FAILED
    assert output.hypothesis is not None
    assert output.hypothesis.hypothesis_text == hypothesis_text
    assert artifact["hypothesis"]["hypothesis_text"] == hypothesis_text
    assert "frozen SA temperature" in artifact["hypothesis"]["hypothesis_text"]
    assert "C11_expected_telemetry" in (output.failure_detail or "")
    assert "hypothesis_text" not in rendered_codes
    assert ledger_entry["category"] == "schema_output_failure"
    assert "C11_expected_telemetry" in ledger_entry["detail"]
    assert "hypothesis_text" not in ledger_entry["detail"]


def test_semantic_retry_then_self_check_c11_retry_reaches_approval(
    tmp_path: Path,
) -> None:
    duplicate = _duplicate_or_opt_hypothesis()
    bad = _vns_hypothesis(_bad_vns_phase_telemetry())
    good = _vns_hypothesis(_good_vns_mechanism_telemetry())
    creative = SequentialHypothesisCreative([duplicate, duplicate, bad, good])
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
    assert len(creative.hypothesis_contexts) == 4
    assert (
        creative.hypothesis_contexts[2]["agentic_hypothesis_semantic_rejections"][0][
            "mechanism"
        ]
        == "cross_route_or_opt_2_3"
    )
    preview_feedback = creative.hypothesis_contexts[3][
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
    creative = SequentialHypothesisCreative([repeat, repeat, good])
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
    assert len(creative.hypothesis_contexts) == 3
    retry_feedback = creative.hypothesis_contexts[2][
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
    assert len(creative.hypothesis_contexts) == 3
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
