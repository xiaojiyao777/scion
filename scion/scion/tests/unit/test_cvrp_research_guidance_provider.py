from __future__ import annotations

from scion.problems.cvrp.research_guidance import (
    CvrpResearchGuidanceProvider,
    build_cvrp_legacy_research_focus,
    build_cvrp_research_guidance_contract,
)
from scion.research_guidance import (
    GuidanceContext,
    ProblemResearchGuidanceProvider,
    launch_research_guidance_payload,
    render_research_guidance_contract,
    research_guidance_contract_to_dict,
    validate_research_guidance_contract,
)


def test_cvrp_research_guidance_contract_contains_required_blocks() -> None:
    provider: ProblemResearchGuidanceProvider = CvrpResearchGuidanceProvider()
    contract = provider.build_guidance_contract(
        GuidanceContext(
            problem_family="cvrp",
            metadata={
                "measurement_opportunity_diagnostics": {
                    "metric": "total_distance",
                    "screening_mde_at_power_80": 9.9,
                    "practical_screen_delta": 2.0,
                },
            },
        )
    )

    validate_research_guidance_contract(contract)
    rendered = render_research_guidance_contract(contract)

    assert contract.schema_version == "scion.cvrp_research_guidance_contract.v1"
    assert contract.problem_family == "cvrp"
    assert contract.proposal_visibility_only is True
    assert contract.decision_features_excluded is True
    assert contract.required_mechanisms == ()
    assert any(
        "total_distance delta by case and seed" in field
        for requirement in contract.evidence_requirements
        for field in requirement.required_fields
    )
    assert any(
        "CMT2" in item and "CMT4" in item
        for requirement in contract.evidence_requirements
        for item in (*requirement.required_fields, *requirement.protected_items)
    )
    assert any(
        "unbounded large-instance two-opt fallback" in rule.description
        for rule in contract.avoid_rules
    )
    assert any(
        "route-pressure acceptance/adaptive-weighting" in rule.description
        for rule in contract.avoid_rules
    )
    assert any(
        "zero branch cards" in requirement.description
        for requirement in contract.continuity_requirements
    )
    assert contract.measurement_summary is not None
    assert "screening MDE 9.9" in contract.measurement_summary.summary
    assert "successor_causal_path_direct_effect" in rendered.text
    assert "large_instance_intra_route_two_opt_seed" in rendered.text
    assert "bounded_2node_cross_exchange" in rendered.text
    assert "intra_route_or_opt_reinsert" in rendered.text
    assert "angular_sector_removal" in rendered.text
    assert "bounded_local_search_variant" in rendered.text
    assert "destroy_repair_selection" in rendered.text
    assert "measured_no_positive_at_mde" in rendered.text
    assert "no-positive-at-MDE" in rendered.text
    assert "CMT2/CMT4 case protection" in rendered.text
    assert "excluded from DecisionFeatures" in rendered.text

    launch_payload = launch_research_guidance_payload(
        manifest_path="/tmp/prepared_run_manifest.v1.json",
        manifest={
            "problem_family": contract.problem_family,
            "research_guidance_contract": research_guidance_contract_to_dict(contract),
        },
    )
    assert launch_payload["required_mechanism_ids"] == []


def test_cvrp_legacy_research_focus_keeps_prepared_manifest_keys() -> None:
    measurement = {
        "metric": "total_distance",
        "screening_mde_at_power_80": 9.9,
        "practical_screen_delta": 2.0,
        "reason_codes": ["CVRP_MDE_EXCEEDS_PRACTICAL_DELTA"],
    }

    focus = build_cvrp_legacy_research_focus(
        measurement_opportunity_diagnostics=measurement
    )

    assert focus["schema_version"] == "scion.cvrp_research_focus.v1"
    assert focus["scope"] == "report_only_prepared_handoff"
    assert focus["required_mechanism_ids"] == []
    assert focus["reviewed_mechanism_ids"] == [
        "large_instance_intra_route_two_opt_seed",
        "bounded_2node_cross_exchange",
        "intra_route_or_opt_reinsert",
        "angular_sector_removal",
    ]
    assert focus["successor_opportunity_families"] == [
        "destroy_repair_selection",
        "construction_seed_portfolio",
        "bounded_local_search_variant",
    ]
    assert "positive-at-MDE" in focus["current_question"]
    assert "bounded_2node_cross_exchange" in focus["next_required_direction"]
    assert "intra_route_or_opt_reinsert" in focus["next_required_direction"]
    assert "angular_sector_removal" in focus["next_required_direction"]
    assert (
        "Rotate the next CVRP solver-design attempt to construction"
        in focus["next_required_direction"]
    )
    assert "distinct from cross-exchange, intra-route Or-opt reinsertion" in (
        focus["next_required_direction"]
    )
    assert focus["measurement_opportunity_diagnostics"] == measurement
    assert focus["measurement_opportunity_diagnostics"] is not measurement
    assert any(
        "current-run pair-level total_distance" in item
        for item in focus["required_evidence"]
    )
    assert any(
        "route-merge absorption" in item for item in focus["default_avoid_directions"]
    )
    assert any("ec052599-style" in item for item in focus["default_avoid_directions"])
    assert any(
        "bounded_2node_cross_exchange" in item and "measured_no_positive_at_mde" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "intra_route_or_opt_reinsert" in item and "measured_no_positive_at_mde" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "angular_sector_removal" in item and "measured_no_positive_at_mde" in item
        for item in focus["default_avoid_directions"]
    )
    assert not any(
        item.strip().lower() == "avoid bounded_local_search_variant"
        for item in focus["default_avoid_directions"]
    )

    successor_evidence = focus["reviewed_successor_evidence"]
    assert successor_evidence["source_summary"] == "cvrp_successor_summary"
    assert successor_evidence["decision_features_excluded"] is True
    assert successor_evidence["mechanisms"] == [
        {
            "mechanism_id": "bounded_2node_cross_exchange",
            "mechanism_family": "bounded_local_search_variant",
            "checklist_status": "proven",
            "outcome_status": "measured_no_positive_at_mde",
            "next_use_rule": (
                "Do not spend the next CVRP branch on the same cross-exchange "
                "successor path unless the hypothesis names a materially new "
                "bounded-local-search causal path and direct per-case "
                "objective-effect evidence."
            ),
        },
        {
            "mechanism_id": "intra_route_or_opt_reinsert",
            "mechanism_family": "bounded_local_search_variant",
            "checklist_status": "proven",
            "outcome_status": "measured_no_positive_at_mde",
            "next_use_rule": (
                "Do not spend the next CVRP branch on the same intra-route "
                "Or-opt reinsertion path unless the hypothesis names a "
                "materially new bounded-local-search causal path and direct "
                "per-case objective-effect evidence."
            ),
        },
        {
            "mechanism_id": "angular_sector_removal",
            "mechanism_family": "destroy_repair_selection",
            "checklist_status": "proven",
            "outcome_status": "measured_no_positive_at_mde",
            "next_use_rule": (
                "Do not spend the next CVRP branch on the same angular-sector "
                "removal path unless the hypothesis names a materially new "
                "destroy/repair selection causal path and direct per-case "
                "objective-effect evidence."
            ),
        },
    ]

    large_twoopt = focus["large_instance_two_opt_constraints"]
    assert large_twoopt["schema_version"] == (
        "scion.cvrp_large_instance_two_opt_constraints.v1"
    )
    assert large_twoopt["proposal_visibility_only"] is True
    assert large_twoopt["decision_features_excluded"] is True
    assert "v04-vrp-large-instance-two-opt-seed-evidence-20260618.md" in (
        large_twoopt["seed_report"]
    )
    assert any(
        "two_opt_intra" in item and "unbounded" in item
        for item in large_twoopt["implementation_constraints"]
    )

    case_protection = focus["case_protection_requirements"]
    assert case_protection["protected_cases"] == ["CMT2", "CMT4"]
    assert any("CMT2/CMT4" in item for item in case_protection["rules"])

    resume_continuity = focus["resume_continuity_requirements"]
    assert "prepared_research_focus" in resume_continuity["fallback_sources"]
    assert any("zero branch cards" in item for item in resume_continuity["rules"])
    assert "DecisionFeatures" in focus["decision_boundary"]

    launch_payload = launch_research_guidance_payload(
        manifest_path="/tmp/prepared_run_manifest.v1.json",
        manifest={
            "problem_family": "cvrp",
            "research_guidance_contract": research_guidance_contract_to_dict(
                build_cvrp_research_guidance_contract(
                    measurement_opportunity_diagnostics=measurement
                )
            ),
            "research_focus": focus,
        },
    )
    assert launch_payload["reviewed_mechanism_ids"] == [
        "large_instance_intra_route_two_opt_seed",
        "bounded_2node_cross_exchange",
        "intra_route_or_opt_reinsert",
        "angular_sector_removal",
    ]
    assert launch_payload["successor_opportunity_families"] == [
        "destroy_repair_selection",
        "construction_seed_portfolio",
        "bounded_local_search_variant",
    ]
    assert launch_payload["legacy_research_focus_schema_version"] == (
        "scion.cvrp_research_focus.v1"
    )


def test_cvrp_contract_rejects_non_cvrp_context() -> None:
    try:
        build_cvrp_research_guidance_contract(
            GuidanceContext(problem_family="warehouse")
        )
    except ValueError as exc:
        assert "cvrp" in str(exc)
    else:
        raise AssertionError("CVRP contract accepted a non-CVRP context")


def test_cvrp_contract_function_accepts_explicit_measurement() -> None:
    contract = build_cvrp_research_guidance_contract(
        measurement_opportunity_diagnostics={
            "metric": "total_distance",
            "screening_mde_at_power_80": 9.9,
            "practical_screen_delta": 2.0,
        }
    )

    assert contract.measurement_summary is not None
    assert contract.measurement_summary.metric_names == ("total_distance",)
    assert "not promotion" in " ".join(contract.measurement_summary.limitations)
