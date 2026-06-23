from __future__ import annotations

from scion.problems.cvrp.research_guidance import (
    CvrpResearchGuidanceProvider,
    build_cvrp_legacy_research_focus,
    build_cvrp_research_guidance_contract,
)
from scion.research_guidance import (
    GuidanceContext,
    ProblemResearchGuidanceProvider,
    render_research_guidance_contract,
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
    assert [item.mechanism_id for item in contract.required_mechanisms] == [
        "large_instance_intra_route_two_opt_seed"
    ]
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
    assert "large_instance_intra_route_two_opt_seed" in rendered.text
    assert "CMT2/CMT4 case protection" in rendered.text
    assert "excluded from DecisionFeatures" in rendered.text


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
    assert focus["required_mechanism_ids"] == [
        "large_instance_intra_route_two_opt_seed"
    ]
    assert "large-instance intra-route two-opt seed" in focus["current_question"]
    assert "First attempt" in focus["next_required_direction"]
    assert focus["measurement_opportunity_diagnostics"] == measurement
    assert focus["measurement_opportunity_diagnostics"] is not measurement
    assert any(
        "current-run pair-level total_distance" in item
        for item in focus["required_evidence"]
    )
    assert any(
        "route-merge absorption" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "ec052599-style" in item
        for item in focus["default_avoid_directions"]
    )

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


def test_cvrp_contract_rejects_non_cvrp_context() -> None:
    try:
        build_cvrp_research_guidance_contract(GuidanceContext(problem_family="warehouse"))
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
