from __future__ import annotations

import pytest

from scion.problems.cvrp.research_guidance import (
    CvrpResearchGuidanceProvider,
    build_cvrp_research_focus,
    build_cvrp_research_guidance_contract,
)
from scion.research_guidance import (
    GuidanceContext,
    render_research_guidance_contract,
    validate_research_guidance_contract,
)


def _measurement() -> dict[str, object]:
    return {
        "measurement_context": {
            "metric": "total_distance",
            "screening_mde_at_power_80": 9.9,
            "practical_screen_delta": 2.0,
        }
    }


def test_cvrp_direct_guidance_is_open_and_source_grounded() -> None:
    contract = CvrpResearchGuidanceProvider().build_guidance_contract(
        GuidanceContext(
            problem_family="cvrp",
            metadata={"measurement_opportunity_diagnostics": _measurement()},
        )
    )
    validate_research_guidance_contract(contract)
    rendered = render_research_guidance_contract(contract).text

    assert contract.schema_version == "scion.cvrp_research_guidance_contract.v3"
    assert contract.required_mechanisms == ()
    assert contract.avoid_rules == ()
    assert contract.continuity_requirements == ()
    assert "policies/baseline_algorithm.py" in rendered
    assert "policies/baseline_modules" in rendered
    assert "SourceLedger" in rendered
    assert "solve(instance, rng, time_limit_sec, context)" in rendered
    assert "accepted route-state transitions" in rendered
    assert "final total_distance" in rendered
    assert "feasibility" in rendered


def test_cvrp_guidance_does_not_compile_history_or_target_steering() -> None:
    contract = build_cvrp_research_guidance_contract(
        measurement_opportunity_diagnostics=_measurement()
    )
    rendered = render_research_guidance_contract(contract).text.lower()
    focus = build_cvrp_research_focus(
        measurement_opportunity_diagnostics=_measurement()
    )
    focus_text = str(focus).lower()

    for forbidden in (
        "successor",
        "nearest reviewed",
        "cmt2",
        "cmt4",
        "denylist",
        "default_avoid",
        "required_mechanism_ids",
        "target_file",
        "next_required_direction",
        "required evidence",
    ):
        assert forbidden not in rendered
        assert forbidden not in focus_text


def test_cvrp_contract_rejects_non_cvrp_context() -> None:
    with pytest.raises(ValueError, match="requires problem_family='cvrp'"):
        build_cvrp_research_guidance_contract(
            GuidanceContext(problem_family="warehouse_delivery")
        )


def test_cvrp_contract_preserves_declared_measurement_scale() -> None:
    contract = build_cvrp_research_guidance_contract(
        measurement_opportunity_diagnostics=_measurement()
    )

    assert contract.measurement_summary is not None
    assert "MDE=9.9" in contract.measurement_summary.summary
    assert "practical screening delta=2.0" in contract.measurement_summary.summary
