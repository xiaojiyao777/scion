from __future__ import annotations

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
            "primary_failure": {
                "stage": "agent_quality_blocked",
                "reason": "algorithm_smoke_failure",
                "category": "algorithm_smoke_failure",
                "code": "algorithm_smoke_failure",
                "detail": "runtime_smoke.telemetry_guard: zero move attempts",
            }
        },
    )

    rendered = _build_agent_quality_feedback([blocked], blocked.branch_id)

    assert "algorithm_smoke_failure" in rendered
    assert "runtime_smoke.telemetry_guard" in rendered
    assert "DecisionFeatures" in rendered
