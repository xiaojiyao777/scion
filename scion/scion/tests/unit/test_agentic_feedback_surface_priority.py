from __future__ import annotations

from scion.tests.unit.agentic_feedback_test_support import *

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
