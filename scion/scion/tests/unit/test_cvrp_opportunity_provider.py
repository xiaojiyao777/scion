from __future__ import annotations

import json
from pathlib import Path

from scion.problem.bridge import load_problem_spec_v1_from_yaml
from scion.opportunity import OpportunityContext
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.opportunity import CvrpOpportunityProvider


_CVRP_PROBLEM = (
    Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem-v1.yaml"
)


def test_cvrp_opportunity_provider_builds_proposal_only_summary() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_PROBLEM)
    adapter = CvrpAdapter(spec)

    payload = (
        CvrpOpportunityProvider(problem_spec=spec, adapter=adapter)
        .build_opportunity_summary()
        .to_payload()
    )

    assert payload["schema_version"] == "scion.problem_opportunity_summary.v1"
    assert payload["problem_family"] == "cvrp"
    assert payload["objective"] == "total_distance"
    assert payload["proposal_visibility_only"] is True
    assert payload["decision_features_excluded"] is True
    assert payload["measurement"]["runtime_model"] == "budget_exhausting"
    assert payload["measurement"]["effect_metric"] == "total_distance"
    assert payload["measurement"]["decision_features_excluded"] is True
    assert "calibration_ref" not in json.dumps(payload, sort_keys=True)
    assert "pair_evidence" not in json.dumps(payload, sort_keys=True)
    assert "bks" not in json.dumps(payload, sort_keys=True).lower()


def test_cvrp_opportunity_provider_preserves_problem_owned_signals() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_PROBLEM)
    adapter = CvrpAdapter(spec)

    payload = (
        CvrpOpportunityProvider(problem_spec=spec, adapter=adapter)
        .build_opportunity_summary()
        .to_payload()
    )

    mechanism_families = {
        item["mechanism_family"] for item in payload["mechanism_evidence"]
    }
    protected_cases = {item["case_id"] for item in payload["protected_cases"]}
    default_avoid = {
        item["mechanism_family"] for item in payload["default_avoid"]
    }
    reason_codes = {
        code
        for item in payload["mechanism_evidence"]
        for code in item.get("reason_codes", [])
    }

    assert "large_instance_intra_route_two_opt_seed" in mechanism_families
    assert {"CMT2", "CMT4"} <= protected_cases
    assert "broad_vns_removal" in default_avoid
    assert "CVRP_LARGE_TWOOPT_REVIEWED_NO_POSITIVE_AT_MDE" in reason_codes
    assert "SUCCESSOR_CAUSAL_PATH_REQUIRED" in reason_codes


def test_cvrp_opportunity_provider_projects_required_evidence_recipe() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_PROBLEM)
    adapter = CvrpAdapter(spec)

    payload = (
        CvrpOpportunityProvider(problem_spec=spec, adapter=adapter)
        .build_opportunity_summary()
        .to_payload()
    )

    requirements = {
        item["requirement_id"]: item
        for item in payload["evidence_requirements"]
    }
    pair_evidence = requirements[
        "large_instance_two_opt_objective_runtime_requirement"
    ]
    protected = requirements["cmt2_cmt4_case_protection"]
    successor = requirements["successor_bounded_local_search_direct_effect"]
    required_text = json.dumps(pair_evidence, sort_keys=True)

    assert successor["mechanism_family"] == "bounded_local_search_variant"
    assert successor["status"] == (
        "successor_required_after_large_twoopt_no_positive_at_mde"
    )
    assert "SUCCESSOR_CAUSAL_PATH_REQUIRED" in successor["reason_codes"]
    assert pair_evidence["mechanism_family"] == (
        "large_instance_intra_route_two_opt_seed"
    )
    assert pair_evidence["status"] == "current_run_required"
    assert "elapsed wall-clock" in required_text
    assert "same split" in required_text
    assert {"CMT2", "CMT4"} <= set(pair_evidence["protected_cases"])
    assert {"CMT2", "CMT4"} <= set(protected["protected_cases"])


def test_cvrp_opportunity_provider_uses_postrun_large_twoopt_status() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_PROBLEM)
    adapter = CvrpAdapter(spec)
    context = OpportunityContext(
        source_payload=adapter.render_problem_measurement_diagnostics(),
        postrun_reports=(
            {
                "schema_version": "scion.postrun_cvrp_large_twoopt_summary.v1",
                "current_run_evidence": True,
                "available": True,
                "interpretation": "protocol_evaluated_without_large_twoopt_signal",
                "evidence_gaps": ["missing_large_twoopt_mechanism_signal"],
                "evidence": {
                    "large_twoopt_mechanism": {
                        "mechanism_family_available": False,
                        "direct_evidence_ready": False,
                    }
                },
            },
        ),
    )

    payload = (
        CvrpOpportunityProvider(problem_spec=spec, adapter=adapter)
        .build_opportunity_summary(context)
        .to_payload()
    )

    requirements = {
        item["requirement_id"]: item
        for item in payload["evidence_requirements"]
    }
    pair_evidence = requirements[
        "large_instance_two_opt_objective_runtime_requirement"
    ]

    assert pair_evidence["status"] == "current_run_checklist_not_ready"
    assert "missing_large_twoopt_mechanism_signal" in (
        pair_evidence["reason_codes"]
    )


def test_cvrp_opportunity_provider_uses_problem_owned_requirement_statuses() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_PROBLEM)
    adapter = CvrpAdapter(spec)
    context = OpportunityContext(
        source_payload=adapter.render_problem_measurement_diagnostics(),
        postrun_reports=(
            {
                "schema_version": "scion.postrun_cvrp_large_twoopt_summary.v1",
                "current_run_evidence": True,
                "available": True,
                "interpretation": (
                    "protocol_evaluated_without_large_twoopt_direct_evidence"
                ),
                "evidence": {
                    "large_twoopt_mechanism": {
                        "mechanism_family_available": True,
                        "direct_evidence_ready": False,
                    },
                    "evidence_requirement_statuses": {
                        "complete": True,
                        "status": "complete",
                        "requirements": {
                            "large_instance_two_opt_objective_runtime_requirement": {
                                "status": "observed",
                                "missing_fields": [],
                                "outcome_status": "measured_no_positive_at_mde",
                            },
                            "cmt2_cmt4_case_protection": {
                                "status": "observed",
                                "missing_fields": [],
                                "outcome_status": "not_outcome_requirement",
                            },
                        },
                    },
                },
            },
        ),
    )

    payload = (
        CvrpOpportunityProvider(problem_spec=spec, adapter=adapter)
        .build_opportunity_summary(context)
        .to_payload()
    )

    requirements = {
        item["requirement_id"]: item
        for item in payload["evidence_requirements"]
    }
    pair_evidence = requirements[
        "large_instance_two_opt_objective_runtime_requirement"
    ]
    protected = requirements["cmt2_cmt4_case_protection"]

    successor = requirements["successor_bounded_local_search_direct_effect"]

    assert successor["mechanism_family"] == "bounded_local_search_variant"
    assert successor["status"] == (
        "successor_required_after_large_twoopt_no_positive_at_mde"
    )
    assert "SUCCESSOR_CAUSAL_PATH_REQUIRED" in successor["reason_codes"]
    assert pair_evidence["status"] == "reviewed_no_positive_at_mde"
    assert protected["status"] == "current_run_required_evidence_observed"
    assert pair_evidence["reason_codes"] == ["measured_no_positive_at_mde"]
    assert protected["reason_codes"] == ["CVRP_PROTECTED_CASE_REVIEW_REQUIRED"]


def test_cvrp_opportunity_provider_projects_missing_cmt_as_actionable_requirement() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_PROBLEM)
    adapter = CvrpAdapter(spec)
    context = OpportunityContext(
        source_payload=adapter.render_problem_measurement_diagnostics(),
        postrun_reports=(
            {
                "schema_version": "scion.postrun_cvrp_large_twoopt_summary.v1",
                "current_run_evidence": True,
                "available": True,
                "interpretation": (
                    "protocol_evaluated_without_large_twoopt_direct_evidence"
                ),
                "evidence": {
                    "large_twoopt_mechanism": {
                        "mechanism_family_available": True,
                        "direct_evidence_ready": False,
                    },
                    "evidence_requirement_statuses": {
                        "complete": False,
                        "status": "incomplete",
                        "missing": ["missing_cmt_case_protection_evidence"],
                        "requirements": {
                            "large_instance_two_opt_objective_runtime_requirement": {
                                "status": "observed",
                                "missing_fields": [],
                                "outcome_status": "measured_no_positive_at_mde",
                            },
                            "cmt2_cmt4_case_protection": {
                                "status": "missing",
                                "missing_fields": [
                                    "missing_cmt_case_protection_evidence"
                                ],
                                "protected_cases_observed": [],
                                "required_protected_cases": ["CMT2", "CMT4"],
                                "outcome_status": "not_outcome_requirement",
                            },
                        },
                    },
                },
            },
        ),
    )

    payload = (
        CvrpOpportunityProvider(problem_spec=spec, adapter=adapter)
        .build_opportunity_summary(context)
        .to_payload()
    )

    requirements = {
        item["requirement_id"]: item
        for item in payload["evidence_requirements"]
    }
    pair_evidence = requirements[
        "large_instance_two_opt_objective_runtime_requirement"
    ]
    protected = requirements["cmt2_cmt4_case_protection"]
    protected_text = json.dumps(protected, sort_keys=True)

    assert "successor_bounded_local_search_direct_effect" not in requirements
    assert pair_evidence["status"] == "current_run_required_evidence_observed"
    assert pair_evidence["reason_codes"] == ["measured_no_positive_at_mde"]
    assert protected["status"] == "current_run_selected_but_required_evidence_missing"
    assert protected["reason_codes"] == ["missing_cmt_case_protection_evidence"]
    assert "case-level total_distance deltas for CMT2 and CMT4" in protected_text
    assert "current postrun missing: missing_cmt_case_protection_evidence" in (
        protected["required_observations"]
    )
    assert (
        "case-level total_distance deltas still required for protected cases: "
        "CMT2, CMT4"
    ) in protected["required_observations"]
