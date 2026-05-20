from __future__ import annotations

from scion.core.models import MechanismChange
from scion.core.telemetry_validation import TELEMETRY_VALIDATION_REPAIRABLE
from scion.tests.unit.agentic_feedback_test_support import *

def test_validation_and_frozen_raw_metric_refs_are_not_exposed_by_read_only_tools(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(
        tmp_path,
        policy=ContextExposurePolicy(
            validation_exposure=HoldoutExposure.AGGREGATE,
            frozen_exposure=HoldoutExposure.AGGREGATE,
        ),
    )

    observations = [
        registry.call("context.list_surfaces", {}, context),
        registry.call("context.read_problem", {}, context),
        registry.call("context.read_objective_policy", {}, context),
        registry.call("context.read_champion_summary", {}, context),
        registry.call("context.read_surface", {"surface": "search_policy"}, context),
        registry.call("memory.query", {}, context),
        registry.call("feedback.query_screening", {}, context),
        registry.call("feedback.query_holdout_summary", {}, context),
        registry.call("feedback.query_runtime", {}, context),
    ]
    rendered = json.dumps(
        [obs.structured_payload for obs in observations],
        sort_keys=True,
        default=str,
    )

    assert "raw_metrics_ref" not in rendered
    assert "SECRET_VALIDATION" not in rendered
    assert "SECRET_FROZEN" not in rendered
    assert "validation raw" not in rendered
    assert "frozen raw" not in rendered


def test_feedback_query_runtime_includes_problem_declared_failure_guidance(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    runtime_step = replace(
        context.step_history[0],
        hypothesis=HypothesisProposal(
            hypothesis_text="Local move surface produced no accepted moves.",
            change_locus="route_local",
            action="create_new",
            target_file="operators/local_new.py",
        ),
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(wins=0, losses=0, ties=2, win_rate=0.0),
            gate_outcome="continue",
            reason_codes=("tie_dominated",),
            exposed_summary="screening safe summary",
            raw_metrics_ref="/SECRET/raw/metrics/SECRET_RAW_REF.json",
            candidate_runtime_failure_categories={"no_accepted_moves": 2},
            candidate_operator_attempts=24,
            candidate_operator_accepted=0,
        ),
    )
    context = replace(context, step_history=(runtime_step,))

    observation = registry.call("feedback.query_runtime", {}, context)
    payload = observation.structured_payload
    rendered = json.dumps(payload, sort_keys=True)

    assert "runtime_failure_guidance" in payload
    assert payload["research_diagnosis"]["schema_version"] == "research-diagnosis.v1"
    assert payload["research_diagnosis"]["screening_only"] is True
    assert payload["research_diagnosis"]["reason_code_counts"] == {"tie_dominated": 1}
    assert "zero_case_win_rate" in payload["research_diagnosis"]["failure_mode_tags"]
    assert "recommended_surfaces: search_policy" in payload["runtime_failure_guidance"]
    assert "discouraged_surfaces: route_local" in payload["runtime_failure_guidance"]
    assert "declared budget surface" in payload["runtime_failure_guidance"]
    assert "raw_metrics_ref" not in rendered
    assert "SECRET_RAW_REF" not in rendered


def test_agent_quality_feedback_surfaces_algorithm_smoke_failure_detail(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    blocked = replace(
        context.step_history[0],
        protocol_result=None,
        failure_stage="agent_quality_blocked",
        failure_detail=(
            "agentic_proposal:patch_generation_failed: "
            "agent_quality_blocked:algorithm_smoke_failure: "
            "runtime_smoke.telemetry_guard: zero move attempts"
        ),
        proposal_session_ref={
            "session_id": "session-smoke-blocked",
            "failure_code": "algorithm_smoke_failure",
            "primary_failure": {
                "stage": "agent_quality_blocked",
                "reason": "algorithm_smoke_failure",
                "category": "algorithm_smoke_failure",
                "code": "algorithm_smoke_failure",
                "detail": "runtime_smoke.telemetry_guard: zero move attempts",
            },
            "rejection_constraint": {
                "mechanism": "zero_move_probe",
                "fact_packet_digest": "facts-digest-smoke",
                "fact_provenance": {
                    "source": "active_algorithm_facts_provider",
                },
            },
        },
    )

    rendered = _build_agent_quality_feedback([blocked], blocked.branch_id)

    assert "attempt=round 1" in rendered
    assert "session=session-smoke-blocked" in rendered
    assert "mechanism=zero_move_probe" in rendered
    assert "stage=agent_quality_blocked" in rendered
    assert "algorithm_smoke_failure" in rendered
    assert "runtime_smoke.telemetry_guard" in rendered
    assert "fact_packet_digest=facts-digest-smoke" in rendered
    assert "infra_suspected" not in rendered.lower()
    assert "DecisionFeatures" in rendered


def test_agent_quality_feedback_surfaces_activation_diagnostic_kind(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    blocked = replace(
        context.step_history[0],
        protocol_result=None,
        failure_stage="agent_quality_blocked",
        failure_detail=(
            "agentic_proposal:code_generation_failed: "
            "agent_quality_blocked:proposal_activation_diagnostic: "
            "proposal activation diagnostic: code=proposal_activation_diagnostic; "
            "activation_diagnostic_kind=expected_telemetry_mismatch"
        ),
        proposal_session_ref={
            "primary_failure": {
                "stage": "agent_quality_blocked",
                "reason": "proposal_activation_diagnostic",
                "category": "proposal_activation_diagnostic",
                "code": "proposal_activation_diagnostic",
                "detail": (
                    "proposal activation diagnostic: "
                    "activation_diagnostic_kind=expected_telemetry_mismatch"
                ),
            }
        },
    )

    rendered = _build_agent_quality_feedback([blocked], blocked.branch_id)

    assert "proposal_activation_diagnostic" in rendered
    assert "activation_diagnostic_kind=expected_telemetry_mismatch" in rendered
    assert "DecisionFeatures" in rendered


def test_agent_quality_feedback_surfaces_code_generation_negative_memory(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    blocked = replace(
        context.step_history[0],
        protocol_result=None,
        failure_stage="code_generation_failed",
        failure_detail=(
            "agentic_proposal:code_generation_failed: "
            "algorithm_smoke_failure: expected telemetry never activated"
        ),
        proposal_session_ref={
            "session_id": "session-code-failed",
            "failure_code": "algorithm_smoke_failure",
            "primary_failure": {
                "stage": "code_generation_failed",
                "reason": "agent_quality_blocked",
                "category": "algorithm_smoke_failure",
                "code": "algorithm_smoke_failure",
                "detail": "expected telemetry never activated",
            },
            "rejection_constraint": {
                "mechanism": "stagnation_kick",
                "fact_packet_digest": "facts-digest-code",
                "fact_provenance": {
                    "provenance": {
                        "source": "champion_snapshot",
                        "branch_id": "branch-1",
                    }
                },
                "variant_allowed": False,
                "contradicted_span": "baseline lacks activation telemetry",
                "allowed_variant_guidance": "Declare telemetry that the patch updates.",
            },
        },
    )

    rendered = _build_agent_quality_feedback([blocked], blocked.branch_id)

    assert "attempt=round 1" in rendered
    assert "session=session-code-failed" in rendered
    assert "mechanism=stagnation_kick" in rendered
    assert "stage=code_generation_failed" in rendered
    assert "failure_code=algorithm_smoke_failure" in rendered
    assert "summary=expected telemetry never activated" in rendered
    assert "fact_packet_digest=facts-digest-code" in rendered
    assert "provenance=source=champion_snapshot,branch_id=branch-1" in rendered
    assert "variant_allowed=False" in rendered
    assert "infra_suspected" not in rendered.lower()


def test_agent_quality_feedback_surfaces_hypothesis_contract_negative_memory(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    blocked = replace(
        context.step_history[0],
        protocol_result=None,
        failure_stage="hypothesis_contract",
        failure_detail="hypothesis contract failed: missing expected_telemetry",
        proposal_session_ref={
            "session_id": "session-contract-failed",
            "failure_code": "hypothesis_contract_failed",
            "primary_failure": {
                "stage": "hypothesis_contract",
                "reason": "contract_failed",
                "category": "hypothesis_contract",
                "code": "hypothesis_contract_failed",
                "detail": "missing expected_telemetry.activation counter",
            },
            "rejection_constraint": {
                "mechanism": "adaptive_repair_gate",
                "fact_packet_digest": "facts-digest-contract",
                "fact_provenance": {
                    "source": "active_algorithm_facts_provider",
                },
            },
        },
    )

    rendered = _build_agent_quality_feedback([blocked], blocked.branch_id)

    assert "attempt=round 1" in rendered
    assert "session=session-contract-failed" in rendered
    assert "mechanism=adaptive_repair_gate" in rendered
    assert "stage=hypothesis_contract" in rendered
    assert "failure_code=hypothesis_contract_failed" in rendered
    assert "missing expected_telemetry.activation counter" in rendered
    assert "fact_packet_digest=facts-digest-contract" in rendered
    assert "provenance=source=active_algorithm_facts_provider" in rendered
    assert "infra_suspected" not in rendered.lower()


def test_agent_quality_feedback_surfaces_repairable_telemetry_negative_memory(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    telemetry_step = replace(
        context.step_history[0],
        hypothesis=HypothesisProposal(
            hypothesis_text="Add route-local kick with explicit activation telemetry.",
            change_locus="solver_design",
            action="modify",
            target_file="policies/search_policy.py",
            mechanism_changes=(
                MechanismChange(id="route_local_kick", change_type="add"),
            ),
        ),
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(wins=0, losses=0, ties=2, win_rate=0.0),
            gate_outcome="continue",
            reason_codes=(
                TELEMETRY_VALIDATION_REPAIRABLE,
                "TELEMETRY_ACTIVATION_NOT_OBSERVED",
            ),
            exposed_summary="screening summary",
            raw_metrics_ref="/SECRET/raw/metrics.json",
            candidate_surface_runtime_summary={
                "telemetry_guard": {
                    "passed": False,
                    "candidate_runs": 4,
                    "failures": [
                        {
                            "code": "TELEMETRY_ACTIVATION_NOT_OBSERVED",
                            "severity": "fail",
                            "category": "activation",
                            "field": "solver_algorithm_phase_runtime_ms.route_local_kick",
                            "mechanism": "route_local_kick",
                            "candidate_missing": 4,
                        }
                    ],
                    "mechanism_diagnostics": [
                        {
                            "mechanism": "route_local_kick",
                            "repair_guidance": [
                                "Record activation when the mechanism executes."
                            ],
                        }
                    ],
                }
            },
        ),
        decision_reason_codes=(
            TELEMETRY_VALIDATION_REPAIRABLE,
            "TELEMETRY_ACTIVATION_NOT_OBSERVED",
        ),
    )

    rendered = _build_agent_quality_feedback([telemetry_step], telemetry_step.branch_id)

    assert TELEMETRY_VALIDATION_REPAIRABLE in rendered
    assert "mechanism=route_local_kick" in rendered
    assert "candidate_missing=4" in rendered
    assert "candidate_runs=4" in rendered
    assert "repair_guidance=Record activation when the mechanism executes." in rendered
    assert "raw_metrics_ref" not in rendered
    assert "infra_suspected" not in rendered.lower()
