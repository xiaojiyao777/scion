from __future__ import annotations

from pathlib import Path

from scion.config.problem import ProblemSpec
from scion.problem.bridge import bridge_problem_spec_v1, load_problem_spec_v1_from_yaml
from scion.problems.warehouse_delivery.adapter import WarehouseDeliveryAdapter
from scion.proposal.context.problem_adapter import _build_operator_interface_spec
from scion.proposal.tools import (
    ContextExposurePolicy,
    ProposalToolContext,
    ProposalToolRegistry,
)


_WAREHOUSE_PROBLEM = (
    Path(__file__).resolve().parents[3]
    / "problems"
    / "warehouse_delivery"
    / "problem.yaml"
)
_WAREHOUSE_PROBLEM_V1 = _WAREHOUSE_PROBLEM.with_name("problem-v1.yaml")


def test_warehouse_vehicle_level_surface_passes_target_preview() -> None:
    spec = ProblemSpec.from_yaml(str(_WAREHOUSE_PROBLEM))
    _assert_vehicle_level_preview_passes(spec)


def test_warehouse_v1_bridge_preserves_surfaces_for_target_preview() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    bridge = bridge_problem_spec_v1(spec_v1)

    assert [surface.name for surface in bridge.problem_spec.research_surfaces] == [
        "order_level",
        "vehicle_level",
    ]
    _assert_vehicle_level_preview_passes(bridge.problem_spec)


def test_warehouse_order_level_interface_renders_problem_owned_runtime_guidance() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_WAREHOUSE_PROBLEM_V1)
    bridge = bridge_problem_spec_v1(spec_v1)
    adapter = WarehouseDeliveryAdapter(spec_v1)

    order_interface = _build_operator_interface_spec(
        bridge.problem_spec,
        adapter=adapter,
        surface_name="order_level",
    )
    vehicle_interface = _build_operator_interface_spec(
        bridge.problem_spec,
        adapter=adapter,
        surface_name="vehicle_level",
    )

    assert "Active Surface Prompt Guidance: order_level" in order_interface
    assert "top-k, sampling, or early-exit cap" in order_interface
    assert "Avoid repeated full-solution feasibility/objective recomputation" in (
        order_interface
    )
    assert "O(n^2) trial evaluation" in order_interface
    assert "Active Surface Prompt Guidance: vehicle_level" not in vehicle_interface
    assert "O(n^2) trial evaluation" not in vehicle_interface


def _assert_vehicle_level_preview_passes(spec: ProblemSpec) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = ProposalToolContext(
        session_id="warehouse-preview-test",
        campaign_id="warehouse-preview-test",
        problem_spec=spec,
        policy=ContextExposurePolicy(allow_contract_preview=True),
    )

    observation = registry.call(
        "proposal.target_permission_preview",
        {
            "change_locus": "vehicle_level",
            "action": "modify",
            "target_file": "operators/merge_vehicles.py",
        },
        context,
    )

    assert observation.is_error is False
    assert observation.structured_payload["passed"] is True
    assert observation.structured_payload["issues"] == []
    assert observation.structured_payload["surface"]["name"] == "vehicle_level"
    assert observation.structured_payload["declared_targets"] == ["operators/*.py"]
