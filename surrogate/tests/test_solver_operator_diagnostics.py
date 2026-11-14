from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import ObjectiveValue, Solution
from solver import _operator_runtime_diagnostics, solution_to_dict


class FillAndDownsize:
    def __init__(self) -> None:
        self.validation_transfer_diagnostics = {
            "operator_invocations": 3,
            "eligible_vehicle_or_order_groups_seen": 2,
            "accepted_moves": 1,
            "split_delta_sum": 1,
            "cost_delta_sum": 500,
            "improving_move_count": 1,
        }


class LockedAnchorRepack:
    def __init__(self) -> None:
        self.validation_transfer_diagnostics = {
            "operator_invocations": 5,
            "eligible_vehicle_or_order_groups_seen": 4,
            "accepted_moves": 0,
            "split_delta_sum": 0,
            "cost_delta_sum": 0,
            "improving_move_count": 0,
            "notes": "ignored",
        }


def test_operator_runtime_diagnostics_exports_snake_case_class_names() -> None:
    runtime = _operator_runtime_diagnostics(
        [FillAndDownsize(), LockedAnchorRepack()],
        ["FillAndDownsize", "LockedAnchorRepack"],
    )

    diagnostics = runtime["operator_diagnostics"]
    assert diagnostics["fill_and_downsize"]["operator_invocations"] == 3
    assert diagnostics["fill_and_downsize"]["cost_delta_sum"] == 500
    assert diagnostics["locked_anchor_repack"]["operator_invocations"] == 5
    assert "notes" not in diagnostics["locked_anchor_repack"]
    assert runtime["operator_registry"] == [
        "fill_and_downsize",
        "locked_anchor_repack",
    ]
    events = runtime["typed_telemetry_events"]
    assert len(events) == 1
    assert events[0]["lane"] == "state_transition"
    assert events[0]["mechanism_id"] == "warehouse_operator_registry"
    assert events[0]["attribution_confidence"] == 1.0
    assert events[0]["before_ref"] == "operator_registry:unresolved"
    assert events[0]["after_ref"] == (
        "operator_registry:active:fill_and_downsize,locked_anchor_repack"
    )
    assert events[0]["missing_refs"] == []
    assert all(event["lane"] != "direct_effect" for event in events)


def test_operator_registry_transition_does_not_invent_legacy_diagnostics() -> None:
    class MoveOrderWithoutDiagnostics:
        pass

    runtime = _operator_runtime_diagnostics(
        [MoveOrderWithoutDiagnostics()],
        ["MoveOrder"],
    )

    assert runtime["operator_registry"] == ["move_order"]
    assert "operator_diagnostics" not in runtime
    assert "validation_transfer_diagnostics" not in runtime
    event = runtime["typed_telemetry_events"][0]
    assert event["lane"] == "state_transition"
    assert event["mechanism_id"] == "warehouse_operator_registry"
    assert "accepted" not in event
    assert "direct_effect" not in str(event)


def test_solution_to_dict_exposes_operator_diagnostics_top_level() -> None:
    solution = Solution(vehicles={}, assignment={})
    solution.objective = ObjectiveValue(subcategory_splits=0, total_cost=0)
    solution._scion_runtime = _operator_runtime_diagnostics(
        [FillAndDownsize()],
        ["FillAndDownsize"],
    )

    payload = solution_to_dict(solution)

    assert payload["operator_diagnostics"]["fill_and_downsize"][
        "accepted_moves"
    ] == 1
    assert payload["runtime"]["operator_diagnostics"] == payload[
        "operator_diagnostics"
    ]
