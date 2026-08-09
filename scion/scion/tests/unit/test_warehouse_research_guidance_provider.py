from __future__ import annotations

import json
from pathlib import Path

from scion.problem.bridge import load_problem_spec_v1_from_yaml
from scion.problem.loader import load_problem_adapter
from scion.problems.warehouse_delivery.research_guidance import (
    WAREHOUSE_PRODUCTION_RESEARCH_PRIOR,
    WarehouseResearchGuidanceProvider,
    build_warehouse_legacy_research_focus,
    build_warehouse_research_guidance_contract,
)
from scion.research_guidance import (
    GuidanceContext,
    launch_research_guidance_payload,
    render_research_guidance_contract,
    research_guidance_contract_to_dict,
    validate_research_guidance_contract,
)


SCION_DIR = Path(__file__).resolve().parents[3]
PROBLEM_V1 = SCION_DIR / "scion" / "problems" / "warehouse_delivery" / "problem-v1.yaml"
FORBIDDEN_PROMPT_PHRASES = (
    "champion_v2",
    "post-v2",
    "validation",
    "frozen",
    "holdout",
    "top-k",
    "top_k",
    "candidate cap",
    "runtime budget",
    "quality-block",
    "retry",
)


def _assert_no_forbidden_prompt_controls(text: str) -> None:
    lowered = text.lower()
    assert not [phrase for phrase in FORBIDDEN_PROMPT_PHRASES if phrase in lowered]


def test_warehouse_provider_keeps_both_algorithm_surfaces_open() -> None:
    diagnostics = {
        "metric": "total_cost",
        "unit": "raw_delta",
        "runtime_model": "comparative",
        "pairing_validity": "trajectory_divergent",
        "practical_screen_delta": 0.001,
        "practical_validate_delta": 0.001,
        "screening_mde_at_power_80": 577.5,
        "summary": "Aggregate total_cost effects must be read against noise.",
    }
    contract = WarehouseResearchGuidanceProvider().build_guidance_contract(
        GuidanceContext(
            problem_family="warehouse_delivery",
            metadata={"measurement_opportunity_diagnostics": diagnostics},
        )
    )

    validate_research_guidance_contract(contract)
    rendered = render_research_guidance_contract(contract)

    assert contract.problem_family == "warehouse_delivery"
    assert contract.schema_version == "scion.warehouse_research_guidance_contract.v3"
    assert contract.required_mechanisms == ()
    assert contract.evidence_requirements
    assert contract.guidance_blocks
    assert "order_level" in rendered.text
    assert "vehicle_level" in rendered.text
    assert "Neither surface nor operator family is preferred" in rendered.text
    assert "telemetry" not in rendered.text.lower()
    assert "observability" not in rendered.text.lower()
    assert "excluded from DecisionFeatures" in rendered.text
    for line in WAREHOUSE_PRODUCTION_RESEARCH_PRIOR:
        assert rendered.text.count(line) == 1
    assert "5W/0L/0T cases and 14W/1L/0T pairs" in rendered.text
    assert "median total_cost improvement +13200" in rendered.text
    assert "candidate/champion ratio was 1.473" in rendered.text
    assert "seven tied cases, hence case win rate 0.5" in rendered.text
    assert "require neither continuing nor abandoning DestroyRebuild" in rendered.text
    assert "select no research surface, action, target file, or mechanism" in rendered.text
    rendered_without_prior = rendered.text
    for line in WAREHOUSE_PRODUCTION_RESEARCH_PRIOR:
        rendered_without_prior = rendered_without_prior.replace(line, "")
    _assert_no_forbidden_prompt_controls(rendered_without_prior)

    launch_payload = launch_research_guidance_payload(
        manifest_path="/tmp/prepared_run_manifest.v1.json",
        manifest={
            "problem_family": contract.problem_family,
            "research_guidance_contract": research_guidance_contract_to_dict(contract),
        },
    )
    assert launch_payload["required_mechanism_ids"] == []
    assert "warehouse_open_research_surfaces" in launch_payload["guidance_text"]


def test_warehouse_adapter_hypothesis_context_has_no_hidden_outcomes_or_controls() -> None:
    spec = load_problem_spec_v1_from_yaml(PROBLEM_V1)
    adapter = load_problem_adapter(spec)

    summary = adapter.render_problem_summary()
    operator_interface = adapter.render_operator_interface()
    order_context = adapter.render_research_surface_interface("order_level")
    vehicle_context = adapter.render_research_surface_interface("vehicle_level")

    assert "Both order-level and vehicle-level research remain open" in summary
    assert 'f"{order.destination_country},{order.ship_method}"' in summary
    assert "country first, comma separator" in summary
    assert 'f"{order.destination_country},{order.ship_method}"' in operator_interface
    assert "country first, comma separator" in operator_interface
    assert "order-level idea" in order_context
    assert "vehicle-level idea" in vehicle_context
    assert "telemetry" not in order_context.lower()
    assert "observability" not in order_context.lower()
    assert "telemetry" not in vehicle_context.lower()
    assert "observability" not in vehicle_context.lower()
    _assert_no_forbidden_prompt_controls(summary)
    _assert_no_forbidden_prompt_controls(order_context)
    _assert_no_forbidden_prompt_controls(vehicle_context)


def test_warehouse_contract_rejects_non_warehouse_context() -> None:
    try:
        build_warehouse_research_guidance_contract(
            GuidanceContext(problem_family="cvrp")
        )
    except ValueError as exc:
        assert "warehouse_delivery" in str(exc)
    else:
        raise AssertionError("warehouse contract accepted a non-warehouse context")


def test_warehouse_focus_preserves_safe_complete_aggregate_measurement() -> None:
    focus = build_warehouse_legacy_research_focus(SCION_DIR, PROBLEM_V1)

    assert focus["schema_version"] == "scion.warehouse_research_focus.v1"
    assert focus["scope"] == "report_only_prepared_handoff"
    assert "current champion source" in focus["accepted_checkpoint"].lower()
    assert "order-level or vehicle-level" in focus["current_question"]
    assert len(focus["required_evidence"]) == 4
    assert "DecisionFeatures" in focus["decision_boundary"]

    measurement = focus["measurement_opportunity_diagnostics"]
    assert measurement["schema_version"] == "warehouse_measurement_opportunity.v2"
    assert measurement["source"] == "problem_v1.measurement.calibration_ref"
    assert measurement["proposal_visibility_only"] is True
    assert measurement["decision_features_excluded"] is True
    assert measurement["metric"] == "total_cost"
    assert measurement["unit"] == "raw_delta"
    assert measurement["runtime_model"] == "comparative"
    assert measurement["pairing_validity"] == "trajectory_divergent"
    assert measurement["screening_mde_at_power_80"] == 577.5
    assert measurement["measurement_readiness"]["status"] == "ready"
    assert measurement["calibration"]["source_artifact"]["sha256"] == (
        "5e34c863356bc74a9d2254dbde1d0a0945c88d56ca7201a4e033344b9718146f"
    )
    assert "WAREHOUSE_MDE_EXCEEDS_PRACTICAL_DELTA" in measurement["reason_codes"]
    assert "TRAJECTORY_DIVERGENT_LOW_SNR" in measurement["reason_codes"]
    assert measurement["adapter_payload_schema"] == (
        "warehouse_research_opportunity_diagnostic.v2"
    )
    assert set(measurement["measurable_opportunity_classes"][0]) == {
        "surface",
        "research_question",
    }
    assert {
        item["surface"] for item in measurement["measurable_opportunity_classes"]
    } == {"order_level", "vehicle_level"}
    assert "optional_observability" not in measurement
    assert "runtime_policy" not in measurement["calibration"]
    assert "calibration_run" not in measurement["calibration"]

    rendered = json.dumps(focus, sort_keys=True)
    _assert_no_forbidden_prompt_controls(rendered)
    assert "pair_evidence" not in rendered
