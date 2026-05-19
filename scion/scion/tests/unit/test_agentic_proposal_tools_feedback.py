from __future__ import annotations

from scion.core.models import PairwiseCaseFeedback
from scion.proposal.context_manager import _build_agent_quality_feedback

from scion.tests.unit.test_agentic_proposal_tools_helpers import (
    Branch,
    BranchState,
    CaseAggregateFeedback,
    ContextExposurePolicy,
    ExperimentStage,
    HoldoutExposure,
    HypothesisProposal,
    NonCallableRenderMemory,
    Path,
    ProblemSpecV1,
    ProposalToolContext,
    ProposalToolFailureCode,
    ProposalToolRegistry,
    ProtocolResult,
    StepRecord,
    UnsafeDefaultOnlyMemory,
    _context,
    _cvrp_context,
    _hyp,
    _problem_spec,
    _stats,
    fields,
    json,
    replace,
)


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


def test_feedback_query_screening_distinguishes_pair_and_case_win_rates(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    pair_results = ["win"] * 2 + ["tie"] * 12 + ["loss"] * 2
    r2_like_step = replace(
        context.step_history[0],
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(n_cases=4, wins=0, losses=0, ties=4, win_rate=0.0),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="case-level gate failed",
            raw_metrics_ref="/SECRET/raw/r2-like.json",
            pair_feedback=tuple(
                PairwiseCaseFeedback(
                    case_id=f"case-{idx // 4}",
                    seed=idx,
                    comparison=result,
                    delta=(
                        1.0
                        if result == "win"
                        else -1.0
                        if result == "loss"
                        else 0.0
                    ),
                )
                for idx, result in enumerate(pair_results)
            ),
        ),
    )
    context = replace(context, step_history=(r2_like_step,))

    observation = registry.call("feedback.query_screening", {}, context)
    rendered = json.dumps(observation.structured_payload, sort_keys=True)
    row = observation.structured_payload["screening_steps"][0]

    assert row["screening_case_win_rate"] == 0.0
    assert row["screening_gate_win_rate"] == 0.0
    assert row["screening_win_rate_scope"] == "case_level_gate"
    assert row["screening_pair_wins"] == 2
    assert row["screening_pair_losses"] == 2
    assert row["screening_pair_ties"] == 12
    assert row["screening_pair_win_rate"] == 0.125
    assert "SECRET" not in rendered
    assert "raw_metrics_ref" not in rendered


def test_runtime_diagnosis_tags_unselected_declared_mechanism_surfaces(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    spec_payload = _problem_spec(tmp_path).model_dump()
    spec_payload["research_surfaces"].append(
        {
            "name": "deep_policy",
            "kind": "policy",
            "description": "Controlled mechanism surface.",
            "algorithm": {
                "role": "controlled_search_mechanism",
                "invocation_point": "during_search",
            },
            "targets": {
                "files": ["policies/deep_policy.py"],
                "create_new_allowed": False,
                "modify_allowed": True,
                "remove_allowed": False,
                "singleton": True,
            },
        }
    )
    context = replace(context, problem_spec=ProblemSpecV1(**spec_payload))
    runtime_step = replace(
        context.step_history[0],
        hypothesis=HypothesisProposal(
            hypothesis_text="Only revisit local moves.",
            change_locus="route_local",
            action="create_new",
            target_file="operators/local_new.py",
        ),
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(wins=0, losses=0, ties=2, win_rate=0.0),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="screening safe summary",
            raw_metrics_ref="/SECRET/raw/metrics/SECRET_RAW_REF.json",
        ),
    )
    context = replace(context, step_history=(runtime_step,))

    observation = registry.call("feedback.query_runtime", {}, context)
    diagnosis = observation.structured_payload["research_diagnosis"]

    assert "deep_surface_not_selected" in diagnosis["failure_mode_tags"]
    assert diagnosis["declared_mechanism_surfaces"] == ["deep_policy"]
    assert diagnosis["unselected_mechanism_surfaces"] == ["deep_policy"]
    assert "deep_policy" in " ".join(diagnosis["next_hypothesis_requirements"])


def test_list_surfaces_exposes_deep_surface_priority_tag_after_screening_history(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    spec_payload = _problem_spec(tmp_path).model_dump()
    spec_payload["research_surfaces"].append(
        {
            "name": "deep_policy",
            "kind": "policy",
            "description": "Controlled mechanism surface.",
            "algorithm": {
                "role": "controlled_search_mechanism",
                "invocation_point": "during_search",
            },
            "targets": {
                "files": ["policies/deep_policy.py"],
                "create_new_allowed": False,
                "modify_allowed": True,
                "remove_allowed": False,
                "singleton": True,
            },
        }
    )
    context = replace(context, problem_spec=ProblemSpecV1(**spec_payload))

    observation = registry.call("context.list_surfaces", {}, context)
    priorities = observation.structured_payload["diagnostic_surface_priorities"]

    assert "deep_surface_not_selected" in priorities["failure_mode_tags"]
    assert priorities["unselected_mechanism_surfaces"] == ["deep_policy"]
    assert "deep_policy" in " ".join(priorities["next_requirements"])


def test_cvrp_prioritizes_solver_design_over_component_policy_diagnostics(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)
    screening_step = StepRecord(
        round_num=1,
        branch_id="branch-cvrp",
        hypothesis=HypothesisProposal(
            hypothesis_text="Tune a component policy.",
            change_locus="destroy_repair_policy",
            action="modify",
            target_file="policies/destroy_repair_policy.py",
        ),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(wins=0, losses=1, ties=1, win_rate=0.0),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="screening safe summary",
            raw_metrics_ref="/SECRET/raw/metrics/SECRET_RAW_REF.json",
        ),
        decision=None,
        failure_stage=None,
        failure_detail=None,
    )
    context = replace(context, step_history=(screening_step,))

    listed = registry.call("context.list_surfaces", {}, context)
    priorities = listed.structured_payload["diagnostic_surface_priorities"]
    runtime = registry.call("feedback.query_runtime", {}, context)
    diagnosis = runtime.structured_payload["research_diagnosis"]

    assert priorities["solver_design_surfaces"] == ["solver_design"]
    assert priorities["unselected_solver_design_surfaces"] == ["solver_design"]
    assert priorities["failure_mode_tags"] == ["solver_design_not_selected"]
    assert "component policies are attribution hooks" in priorities["recommendation"]
    assert "unselected_mechanism_surfaces" not in priorities
    assert diagnosis["declared_solver_design_surfaces"] == ["solver_design"]
    assert diagnosis["declared_mechanism_surfaces"] == []
    assert "solver_design_not_selected" in diagnosis["failure_mode_tags"]
    assert "deep_surface_not_selected" not in diagnosis["failure_mode_tags"]
    assert "solver_design" in " ".join(diagnosis["next_hypothesis_requirements"])


def test_feedback_defaults_to_active_boundary_and_excludes_legacy_surfaces(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = replace(
        _cvrp_context(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )
    solver_step = StepRecord(
        round_num=1,
        branch_id="branch-cvrp",
        hypothesis=HypothesisProposal(
            hypothesis_text="Change the active solver lifecycle.",
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_algorithm.py",
        ),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(wins=1, losses=0, ties=1, win_rate=0.5),
            gate_outcome="continue",
            reason_codes=("SCREENING_SIGNAL",),
            exposed_summary="active solver-design summary",
            raw_metrics_ref="/SECRET/raw/active.json",
            selected_surface="solver_design",
            candidate_surface_runtime_summary={
                "fields": {
                    "solver_algorithm_active": {
                        "present": 1,
                        "missing": 0,
                        "empty": 0,
                        "failed": 0,
                    }
                }
            },
        ),
        decision=None,
        failure_stage=None,
        failure_detail=None,
    )
    legacy_step = StepRecord(
        round_num=2,
        branch_id="branch-cvrp",
        hypothesis=HypothesisProposal(
            hypothesis_text="Legacy component policy evidence.",
            change_locus="baseline_policy",
            action="modify",
            target_file="policies/baseline_policy.py",
        ),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(wins=0, losses=1, ties=1, win_rate=0.0),
            gate_outcome="fail",
            reason_codes=("LEGACY_FAIL",),
            exposed_summary="legacy inactive summary",
            raw_metrics_ref="/SECRET/raw/legacy.json",
            selected_surface="baseline_policy",
            candidate_surface_runtime_summary={
                "fields": {
                    "baseline_policy_active": {
                        "present": 1,
                        "missing": 0,
                        "empty": 0,
                        "failed": 0,
                    }
                }
            },
        ),
        decision=None,
        failure_stage=None,
        failure_detail=None,
    )
    context = replace(context, step_history=(solver_step, legacy_step))

    screening = registry.call("feedback.query_screening", {}, context).structured_payload
    runtime = registry.call("feedback.query_runtime", {}, context).structured_payload
    rendered_default = json.dumps([screening, runtime], sort_keys=True)

    assert screening["active_boundary_filter"]["status"] == "enforced"
    assert [row["surface"] for row in screening["screening_steps"]] == [
        "solver_design"
    ]
    assert screening["inactive_reference_steps"] == []
    assert screening["excluded_inactive_reference_count"] == 1
    assert screening["screening_steps"][0]["provenance"]["evidence_role"] == (
        "active_boundary_evidence"
    )
    assert runtime["research_diagnosis"]["surface_counts"] == {"solver_design": 1}
    assert runtime["inactive_reference_runtime_attribution"] == []
    assert "legacy inactive summary" not in rendered_default


def test_feedback_explicit_inactive_surface_returns_reference_provenance(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = replace(
        _cvrp_context(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )
    legacy_step = StepRecord(
        round_num=1,
        branch_id="branch-cvrp",
        hypothesis=HypothesisProposal(
            hypothesis_text="Request old component reference.",
            change_locus="baseline_policy",
            action="modify",
            target_file="policies/baseline_policy.py",
        ),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(wins=0, losses=1, ties=1, win_rate=0.0),
            gate_outcome="fail",
            reason_codes=("LEGACY_FAIL",),
            exposed_summary="legacy inactive summary",
            raw_metrics_ref="/SECRET/raw/legacy.json",
            selected_surface="baseline_policy",
        ),
        decision=None,
        failure_stage=None,
        failure_detail=None,
    )
    context = replace(context, step_history=(legacy_step,))

    observation = registry.call(
        "feedback.query_screening",
        {"surface": "baseline_policy"},
        context,
    )
    payload = observation.structured_payload

    assert payload["screening_steps"] == []
    assert payload["active_boundary_filter"]["requested_surface_status"] == (
        "inactive_reference"
    )
    assert [row["surface"] for row in payload["inactive_reference_steps"]] == [
        "baseline_policy"
    ]
    assert payload["inactive_reference_steps"][0]["provenance"]["evidence_role"] == (
        "inactive_reference"
    )


def test_cvrp_solver_design_preprotocol_failure_requests_boundary_retry(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    failed_solver_design = StepRecord(
        round_num=1,
        branch_id="branch-cvrp",
        hypothesis=HypothesisProposal(
            hypothesis_text="Try the top-level solver design.",
            change_locus="solver_design",
            action="modify",
            target_file="policies/solver_algorithm.py",
        ),
        patch=None,
        contract_passed=True,
        verification_passed=False,
        protocol_result=None,
        decision=None,
        failure_stage="verification",
        failure_detail="V5_solution_consistency",
        verification_detail="V5_solution_consistency: invalid candidate output",
    )
    component_screening = StepRecord(
        round_num=2,
        branch_id="branch-cvrp-2",
        hypothesis=HypothesisProposal(
            hypothesis_text="Tune a component policy.",
            change_locus="destroy_repair_policy",
            action="modify",
            target_file="policies/destroy_repair_policy.py",
        ),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(wins=0, losses=1, ties=1, win_rate=0.0),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="screening safe summary",
            raw_metrics_ref="/SECRET/raw/metrics/SECRET_RAW_REF.json",
        ),
        decision=None,
        failure_stage=None,
        failure_detail=None,
    )
    context = replace(
        _cvrp_context(tmp_path),
        step_history=(failed_solver_design, component_screening),
    )

    listed = registry.call("context.list_surfaces", {}, context)
    priorities = listed.structured_payload["diagnostic_surface_priorities"]
    runtime = registry.call("feedback.query_runtime", {}, context)
    diagnosis = runtime.structured_payload["research_diagnosis"]

    assert priorities["failed_solver_design_surfaces"] == ["solver_design"]
    assert "solver_design_pre_protocol_failure" in priorities["failure_mode_tags"]
    assert "candidate failure" in priorities["recommendation"]
    assert "component policies remain attribution hooks" in priorities["recommendation"]
    assert diagnosis["failed_solver_design_surfaces"] == ["solver_design"]
    assert "solver_design_pre_protocol_failure" in diagnosis["failure_mode_tags"]
    assert "pre-screening candidate failure" in " ".join(
        diagnosis["next_hypothesis_requirements"]
    )


def test_cvrp_solver_design_screening_failure_keeps_boundary_priority(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    solver_design_screening = StepRecord(
        round_num=1,
        branch_id="branch-cvrp",
        hypothesis=HypothesisProposal(
            hypothesis_text="Try the top-level solver design.",
            change_locus="solver_design",
            action="modify",
            target_file="policies/solver_algorithm.py",
        ),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(wins=0, losses=2, ties=0, win_rate=0.0),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="screening safe summary",
            raw_metrics_ref="/SECRET/raw/metrics/SECRET_RAW_REF.json",
            selected_surface="solver_design",
        ),
        decision=None,
        failure_stage=None,
        failure_detail=None,
    )
    context = replace(
        _cvrp_context(tmp_path),
        step_history=(solver_design_screening,),
    )

    listed = registry.call("context.list_surfaces", {}, context)
    priorities = listed.structured_payload["diagnostic_surface_priorities"]
    runtime = registry.call("feedback.query_runtime", {}, context)
    diagnosis = runtime.structured_payload["research_diagnosis"]

    assert priorities["screening_failed_solver_design_surfaces"] == ["solver_design"]
    assert "solver_design_screening_failure" in priorities["failure_mode_tags"]
    assert "component policies" in priorities["recommendation"]
    assert diagnosis["screening_failed_solver_design_surfaces"] == ["solver_design"]
    assert "solver_design_screening_failure" in diagnosis["failure_mode_tags"]
    assert "replacement research goals" in " ".join(
        diagnosis["next_hypothesis_requirements"]
    )


def test_runtime_diagnosis_tags_zero_phase_and_recovery_only_patterns(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    runtime_step = replace(
        context.step_history[0],
        hypothesis=HypothesisProposal(
            hypothesis_text="Accepted moves do not refresh phase best.",
            change_locus="solver_design",
            action="modify",
            target_file="policies/solver_algorithm.py",
        ),
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(wins=0, losses=0, ties=2, win_rate=0.0),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="screening safe summary",
            raw_metrics_ref="/SECRET/raw/metrics/SECRET_RAW_REF.json",
            selected_surface="solver_design",
            candidate_surface_runtime_summary={
                "selected_surface": "solver_design",
                "required_runtime_fields": [
                    "main_search_component_accepted_delta_sum",
                    "main_search_component_recovery_delta_sum",
                    "main_search_component_phase_delta_sum",
                ],
                "fields": {
                    "main_search_component_accepted_delta_sum": {
                        "present": 2,
                        "missing": 0,
                        "empty": 0,
                        "failed": 0,
                        "numeric_summary": {
                            "mapping": {
                                "route_pair_swap": {
                                    "observed_count": 2,
                                    "weighted_sum": 12.0,
                                    "nonzero_count": 2,
                                }
                            }
                        },
                    },
                    "main_search_component_recovery_delta_sum": {
                        "present": 2,
                        "missing": 0,
                        "empty": 0,
                        "failed": 0,
                        "numeric_summary": {
                            "mapping": {
                                "route_pair_swap": {
                                    "observed_count": 2,
                                    "weighted_sum": 12.0,
                                    "nonzero_count": 2,
                                }
                            }
                        },
                    },
                    "main_search_component_phase_delta_sum": {
                        "present": 2,
                        "missing": 0,
                        "empty": 0,
                        "failed": 0,
                        "numeric_summary": {
                            "mapping": {
                                "route_pair_swap": {
                                    "observed_count": 2,
                                    "weighted_sum": 0.0,
                                    "nonzero_count": 0,
                                }
                            }
                        },
                    },
                },
            },
        ),
    )
    context = replace(context, step_history=(runtime_step,))

    observation = registry.call("feedback.query_runtime", {}, context)
    diagnosis = observation.structured_payload["research_diagnosis"]

    assert "zero_phase_delta" in diagnosis["failure_mode_tags"]
    assert "accepted_signal_without_phase_delta" in diagnosis["failure_mode_tags"]
    assert "recovery_only_accepted_moves" in diagnosis["failure_mode_tags"]
    assert diagnosis["runtime_signal_rows"][0]["zero_phase_delta_fields"] == [
        "main_search_component_phase_delta_sum"
    ]


def test_forced_runtime_feedback_omits_conflicting_surface_guidance(
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
            raw_metrics_ref="/safe/screening.json",
            candidate_runtime_failure_categories={"no_accepted_moves": 2},
            candidate_operator_attempts=24,
            candidate_operator_accepted=0,
        ),
    )
    context = replace(
        context,
        forced_surface="route_local",
        forced_action="create_new",
        step_history=(runtime_step,),
    )

    observation = registry.call(
        "feedback.query_runtime",
        {"surface": "route_local"},
        context,
    )
    guidance = observation.structured_payload["runtime_failure_guidance"]

    assert "forced_surface_constraint: keep surface route_local" in guidance
    assert "recommended_surfaces: search_policy" not in guidance
    assert "discouraged_surfaces: route_local" not in guidance
    assert "declared budget surface" not in guidance


def test_feedback_query_screening_bounds_large_compact_payload_without_error(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    protocol = context.step_history[0].protocol_result
    assert protocol is not None
    large_runtime_summary = {
        f"component_{idx}": "accepted route-pair evidence " * 200 for idx in range(60)
    }
    large_step = replace(
        context.step_history[0],
        protocol_result=replace(
            protocol,
            candidate_surface_runtime_summary=large_runtime_summary,
        ),
    )
    context = replace(context, step_history=(large_step,))

    observation = registry.call("feedback.query_screening", {}, context)
    rendered = json.dumps(observation.structured_payload, sort_keys=True, default=str)

    assert observation.is_error is False
    assert observation.failure_code is None
    assert observation.structured_payload["payload_truncated"] is True
    assert len(rendered) <= registry.get("feedback.query_screening").max_result_chars
    assert "raw_metrics_ref" not in rendered


def test_feedback_query_defaults_to_campaign_scope_across_branches(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    current_branch = Branch(
        branch_id="branch-current",
        state=BranchState.EXPLORE,
        base_champion_id=7,
        base_champion_hash="code-hash",
    )
    older_step = replace(context.step_history[0], branch_id="branch-older")
    context = replace(
        context,
        branch=current_branch,
        step_history=(older_step,),
    )

    observation = registry.call("feedback.query_screening", {}, context)
    branch_scoped = registry.call(
        "feedback.query_screening",
        {"branch_id": "branch-current"},
        context,
    )

    assert observation.structured_payload["available_screening_step_count"] == 1
    assert observation.structured_payload["matched_screening_step_count"] == 1
    assert (
        observation.structured_payload["screening_steps"][0]["branch_id"]
        == "branch-older"
    )
    assert branch_scoped.structured_payload["matched_screening_step_count"] == 0
    assert branch_scoped.structured_payload["screening_steps"] == []


def test_runtime_feedback_exposes_compact_surface_attribution(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    protocol = context.step_history[0].protocol_result
    assert protocol is not None
    main_search_hypothesis = replace(
        _hyp("solver_design"),
        target_file="policies/solver_algorithm.py",
    )
    attributed_step = replace(
        context.step_history[0],
        hypothesis=main_search_hypothesis,
        protocol_result=replace(
            protocol,
            candidate_surface_runtime_summary={
                "selected_surface": "solver_design",
                "fields": {
                    "main_search_component_accepted": {
                        "present": 2,
                        "missing": 0,
                        "empty": 0,
                        "failed": 0,
                        "numeric_summary": {
                            "mapping": {
                                "route_pair_swap": {
                                    "observed_count": 2,
                                    "weighted_sum": 43.0,
                                    "nonzero_count": 1,
                                    "positive_count": 1,
                                    "zero_count": 1,
                                }
                            }
                        },
                        "values": [
                            {
                                "value": "{'route_pair_swap': 43, 'bounded_destroy_repair': 11}",
                                "count": 1,
                            }
                        ],
                    },
                    "main_search_objective_delta_by_phase": {
                        "present": 2,
                        "missing": 0,
                        "empty": 0,
                        "failed": 0,
                        "values": [{"value": "{'improvement_loop': 0.0}", "count": 2}],
                    },
                },
            },
        ),
    )
    context = replace(context, step_history=(attributed_step,))

    screening = registry.call("feedback.query_screening", {}, context)
    runtime = registry.call("feedback.query_runtime", {}, context)
    rendered = json.dumps(
        [screening.structured_payload, runtime.structured_payload],
        sort_keys=True,
        default=str,
    )

    assert "candidate_surface_runtime_attribution" in rendered
    assert "screening_runtime_attribution" in runtime.structured_payload
    assert "main_search_component_accepted" in rendered
    assert "numeric_summary" in rendered
    assert "nonzero_count" in rendered
    assert "main_search_objective_delta_by_phase" in rendered
    assert "raw_metrics_ref" not in rendered


def test_runtime_feedback_prioritizes_phase_attribution_over_modal_fields(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    protocol = context.step_history[0].protocol_result
    assert protocol is not None
    low_priority_fields = {
        f"main_search_low_priority_{index}_active": {
            "present": 2,
            "missing": 0,
            "empty": 0,
            "failed": 0,
            "values": [{"value": "true", "count": 2}],
        }
        for index in range(20)
    }
    fields = {
        **low_priority_fields,
        "main_search_component_accepted_delta_sum": {
            "present": 2,
            "missing": 0,
            "empty": 0,
            "failed": 0,
            "numeric_summary": {
                "mapping": {
                    "route_pair_swap": {
                        "observed_count": 2,
                        "weighted_sum": 507.0,
                        "positive_count": 2,
                    }
                }
            },
            "values": [{"value": "{'route_pair_swap': 507.0}", "count": 1}],
        },
        "main_search_component_phase_delta_sum": {
            "present": 2,
            "missing": 0,
            "empty": 0,
            "failed": 0,
            "numeric_summary": {
                "mapping": {
                    "route_pair_swap": {
                        "observed_count": 2,
                        "weighted_sum": 0.0,
                        "zero_count": 2,
                    }
                }
            },
            "values": [{"value": "{'route_pair_swap': 0.0}", "count": 2}],
        },
        "main_search_component_recovery_delta_sum": {
            "present": 2,
            "missing": 0,
            "empty": 0,
            "failed": 0,
            "numeric_summary": {
                "mapping": {
                    "route_pair_swap": {
                        "observed_count": 2,
                        "weighted_sum": 507.0,
                        "positive_count": 2,
                    }
                }
            },
            "values": [{"value": "{'route_pair_swap': 507.0}", "count": 1}],
        },
        "main_search_objective_delta_by_phase": {
            "present": 2,
            "missing": 0,
            "empty": 0,
            "failed": 0,
            "numeric_summary": {
                "mapping": {
                    "improvement_loop": {
                        "observed_count": 2,
                        "weighted_sum": 0.0,
                        "zero_count": 2,
                    }
                }
            },
            "values": [{"value": "{'improvement_loop': 0.0}", "count": 2}],
        },
    }
    attributed_step = replace(
        context.step_history[0],
        hypothesis=replace(
            _hyp("solver_design"),
            target_file="policies/solver_algorithm.py",
        ),
        protocol_result=replace(
            protocol,
            candidate_surface_runtime_summary={
                "selected_surface": "solver_design",
                "fields": fields,
            },
        ),
    )
    context = replace(context, step_history=(attributed_step,))

    runtime = registry.call("feedback.query_runtime", {}, context)
    rendered = json.dumps(runtime.structured_payload, sort_keys=True, default=str)

    assert "main_search_component_accepted_delta_sum" in rendered
    assert "main_search_component_phase_delta_sum" in rendered
    assert "main_search_component_recovery_delta_sum" in rendered
    assert "main_search_objective_delta_by_phase" in rendered
    assert "weighted_sum" in rendered
    assert rendered.index("main_search_objective_delta_by_phase") < rendered.index(
        "main_search_low_priority_0_active"
    )


def test_runtime_feedback_surfaces_solver_algorithm_noop_motion(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    protocol = context.step_history[0].protocol_result
    assert protocol is not None
    fields = {
        "solver_algorithm_move_attempts": {
            "present": 16,
            "missing": 0,
            "empty": 0,
            "failed": 0,
            "numeric_summary": {
                "scalar": {
                    "observed_count": 16,
                    "weighted_sum": 7194.0,
                    "positive_count": 16,
                    "zero_count": 0,
                }
            },
            "values": [{"value": "125", "count": 2}],
        },
        "solver_algorithm_accepted_moves": {
            "present": 16,
            "missing": 0,
            "empty": 0,
            "failed": 0,
            "numeric_summary": {
                "scalar": {
                    "observed_count": 16,
                    "weighted_sum": 1.0,
                    "positive_count": 1,
                    "zero_count": 15,
                }
            },
            "values": [{"value": "0", "count": 15}],
        },
        "solver_algorithm_best_delta": {
            "present": 16,
            "missing": 0,
            "empty": 0,
            "failed": 0,
            "numeric_summary": {
                "scalar": {
                    "observed_count": 16,
                    "weighted_sum": 1.0,
                    "positive_count": 1,
                    "zero_count": 15,
                }
            },
            "values": [{"value": "0.0", "count": 15}],
        },
        "solver_algorithm_search_iterations": {
            "present": 16,
            "missing": 0,
            "empty": 0,
            "failed": 0,
            "numeric_summary": {
                "scalar": {
                    "observed_count": 16,
                    "weighted_sum": 0.0,
                    "positive_count": 0,
                    "zero_count": 16,
                }
            },
            "values": [{"value": "0", "count": 16}],
        },
    }
    attributed_step = replace(
        context.step_history[0],
        hypothesis=replace(
            _hyp("solver_design"),
            target_file="policies/solver_algorithm.py",
        ),
        protocol_result=replace(
            protocol,
            candidate_surface_runtime_summary={
                "selected_surface": "solver_design",
                "fields": fields,
            },
        ),
    )
    context = replace(context, step_history=(attributed_step,))

    runtime = registry.call("feedback.query_runtime", {}, context)
    rendered = json.dumps(runtime.structured_payload, sort_keys=True, default=str)

    assert "solver_algorithm_move_attempts" in rendered
    assert "solver_algorithm_accepted_moves" in rendered
    assert "solver_algorithm_best_delta" in rendered
    assert "solver_algorithm_search_iterations" in rendered
    assert "zero_count" in rendered


def test_default_holdout_summary_exposes_no_validation_or_frozen_rows(
    tmp_path: Path,
) -> None:
    observation = ProposalToolRegistry.default_read_only().call(
        "feedback.query_holdout_summary",
        {},
        _context(tmp_path),
    )

    assert observation.structured_payload["holdout_steps"] == []
    assert observation.structured_payload["validation_exposure"] == "none"
    assert observation.structured_payload["frozen_exposure"] == "none"


def test_memory_query_hides_promotion_and_holdout_signals(tmp_path: Path) -> None:
    observation = ProposalToolRegistry.default_read_only().call(
        "memory.query",
        {},
        _context(tmp_path),
    )

    text = observation.structured_payload["text"].lower()
    assert "safe screening idea" in text
    assert "champion_evolution" not in text
    assert "promoted" not in text
    assert "promotion" not in text
    assert "validation" not in text
    assert "frozen" not in text
    assert "holdout" not in text


def test_memory_query_rejects_default_render_without_safe_view(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context = ProposalToolContext(
        session_id=context.session_id,
        campaign_id=context.campaign_id,
        branch=context.branch,
        champion=context.champion,
        problem_spec=context.problem_spec,
        adapter=context.adapter,
        step_history=context.step_history,
        search_memory=UnsafeDefaultOnlyMemory(),
        research_log=context.research_log,
        policy=context.policy,
        problem_id=context.problem_id,
        problem_spec_hash=context.problem_spec_hash,
    )

    observation = ProposalToolRegistry.default_read_only().call(
        "memory.query", {}, context
    )
    rendered = json.dumps(observation.structured_payload, sort_keys=True)

    assert observation.is_error is True
    assert observation.failure_code == ProposalToolFailureCode.UNSUPPORTED
    assert "SECRET_HOLDOUT_SIGNAL" not in rendered
    assert "promotion path" not in rendered


def test_memory_query_rejects_non_callable_render(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context = ProposalToolContext(
        session_id=context.session_id,
        campaign_id=context.campaign_id,
        branch=context.branch,
        champion=context.champion,
        problem_spec=context.problem_spec,
        adapter=context.adapter,
        step_history=context.step_history,
        search_memory=NonCallableRenderMemory(),
        research_log=context.research_log,
        policy=context.policy,
        problem_id=context.problem_id,
        problem_spec_hash=context.problem_spec_hash,
    )

    observation = ProposalToolRegistry.default_read_only().call(
        "memory.query", {}, context
    )

    assert observation.is_error is True
    assert observation.failure_code == ProposalToolFailureCode.UNSUPPORTED


def test_champion_summary_hides_version_and_promotion_fields(tmp_path: Path) -> None:
    observation = ProposalToolRegistry.default_read_only().call(
        "context.read_champion_summary",
        {},
        _context(tmp_path),
    )
    rendered = json.dumps(observation.structured_payload, sort_keys=True)

    assert "version" not in rendered
    assert "promotion" not in rendered
    assert "promoted_at" not in rendered
    assert "promotion-secret" not in rendered


def test_holdout_aggregate_does_not_expose_malicious_raw_refs_or_case_ids(
    tmp_path: Path,
) -> None:
    context = _context(
        tmp_path,
        policy=ContextExposurePolicy(
            validation_exposure=HoldoutExposure.AGGREGATE,
            frozen_exposure=HoldoutExposure.AGGREGATE,
        ),
    )
    malicious_step = StepRecord(
        round_num=4,
        branch_id="branch-1",
        hypothesis=_hyp(),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.VALIDATION,
            stats=_stats(),
            gate_outcome="fail",
            reason_codes=("VALIDATION_REASON",),
            exposed_summary="validation safe summary",
            raw_metrics_ref="/SECRET/raw/metrics/SECRET_RAW_REF.json",
            case_ids=("SECRET_CASE_ID",),
            seed_set=(999,),
            case_feedback=(
                CaseAggregateFeedback(
                    case_id="SECRET_CASE_ID",
                    n_pairs=2,
                    wins=2,
                    losses=0,
                    ties=0,
                    win_rate=1.0,
                    dominant_result="win",
                    decisive_metric="distance",
                    median_deltas={"distance": -5.0},
                ),
            ),
        ),
        decision=None,
        failure_stage=None,
        failure_detail=None,
    )
    context = ProposalToolContext(
        session_id=context.session_id,
        campaign_id=context.campaign_id,
        branch=context.branch,
        champion=context.champion,
        problem_spec=context.problem_spec,
        adapter=context.adapter,
        step_history=(malicious_step,),
        search_memory=context.search_memory,
        research_log=context.research_log,
        policy=context.policy,
        problem_id=context.problem_id,
        problem_spec_hash=context.problem_spec_hash,
    )

    observation = ProposalToolRegistry.default_read_only().call(
        "feedback.query_holdout_summary",
        {},
        context,
    )
    rendered = json.dumps(observation.structured_payload, sort_keys=True)

    assert observation.is_error is False
    assert "SECRET_RAW_REF" not in rendered
    assert "SECRET_CASE_ID" not in rendered
    assert "case_feedback" not in rendered
    assert "raw_metrics_ref" not in rendered
