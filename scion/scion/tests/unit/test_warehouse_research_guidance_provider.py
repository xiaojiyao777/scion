from __future__ import annotations

import json
from pathlib import Path

from scion.problems.warehouse_delivery.research_guidance import (
    WarehouseResearchGuidanceProvider,
    build_warehouse_legacy_research_focus,
    build_warehouse_research_guidance_contract,
)
from scion.research_guidance import (
    GuidanceContext,
    render_research_guidance_contract,
    validate_research_guidance_contract,
)


SCION_DIR = Path(__file__).resolve().parents[3]
PROBLEM_V1 = SCION_DIR / "scion" / "problems" / "warehouse_delivery" / "problem-v1.yaml"


def test_warehouse_provider_contract_has_guidance_sections() -> None:
    diagnostics = {
        "metric": "total_cost",
        "runtime_model": "comparative",
        "pairing_validity": "trajectory_divergent",
        "screening_mde_at_power_80": 577.5,
        "summary": "Warehouse screening is low-power for raw total_cost effects.",
        "reason_codes": [
            "WAREHOUSE_MDE_EXCEEDS_PRACTICAL_DELTA",
            "TRAJECTORY_DIVERGENT_LOW_SNR",
        ],
    }
    provider = WarehouseResearchGuidanceProvider()
    contract = provider.build_guidance_contract(
        GuidanceContext(
            problem_family="warehouse_delivery",
            metadata={"measurement_opportunity_diagnostics": diagnostics},
        )
    )

    validate_research_guidance_contract(contract)
    rendered = render_research_guidance_contract(contract)

    assert contract.problem_family == "warehouse_delivery"
    assert contract.required_mechanisms
    assert contract.evidence_requirements
    assert contract.avoid_rules
    assert contract.guidance_blocks
    assert contract.measurement_summary is not None
    assert any(
        "cost_delta_sum" in requirement.required_fields
        for requirement in contract.evidence_requirements
    )
    assert any("split_delta_sum==0" in rule.description for rule in contract.avoid_rules)
    assert "warehouse_champion_v2_checkpoint" in rendered.text
    assert "warehouse_measurement_runtime_handoff" in rendered.text
    assert "excluded from DecisionFeatures" in rendered.text


def test_warehouse_contract_rejects_non_warehouse_context() -> None:
    try:
        build_warehouse_research_guidance_contract(
            GuidanceContext(problem_family="cvrp")
        )
    except ValueError as exc:
        assert "warehouse_delivery" in str(exc)
    else:
        raise AssertionError("warehouse contract accepted a non-warehouse context")


def test_warehouse_legacy_research_focus_preserves_manifest_fields() -> None:
    focus = build_warehouse_legacy_research_focus(SCION_DIR, PROBLEM_V1)

    assert focus["schema_version"] == "scion.warehouse_research_focus.v1"
    assert focus["scope"] == "report_only_prepared_handoff"
    assert "Champion v2" in focus["accepted_checkpoint"]
    assert "post-v2 plateau" in focus["current_question"]
    assert len(focus["required_evidence"]) >= 5
    assert any(
        "cost_delta" in item and "split_delta" in item
        for item in focus["required_evidence"]
    )
    assert any(
        "split_delta_sum==0" in item
        for item in focus["default_avoid_directions"]
    )
    assert "DecisionFeatures" in focus["decision_boundary"]

    measurement = focus["measurement_opportunity_diagnostics"]
    assert measurement["schema_version"] == "warehouse_measurement_runtime_handoff.v1"
    assert measurement["source"] == "problem_v1.measurement.calibration_ref"
    assert measurement["proposal_visibility_only"] is True
    assert measurement["decision_features_excluded"] is True
    assert measurement["metric"] == "total_cost"
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
        "warehouse_validation_transfer_diagnostic.v1"
    )
    assert "transfer_risk" in measurement
    assert "required_diagnostics" in measurement
    assert "measurable_opportunity_classes" in measurement
    assert "opportunity_diagnostics" in measurement

    rendered = json.dumps(focus, sort_keys=True)
    assert "validation_case" not in rendered
    assert "frozen_case" not in rendered
    assert "pair_evidence" not in rendered
