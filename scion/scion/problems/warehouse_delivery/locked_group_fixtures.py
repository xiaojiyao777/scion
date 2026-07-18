"""Frozen directed fixture definitions for the Warehouse W2 probe."""

from __future__ import annotations

from typing import Any


FIXTURE_SCHEMA = "scion.warehouse_locked_group_fixtures.v1"


def _order(
    order_id: str,
    *,
    locked_vehicle_id: str | None = None,
    pallets: int = 1,
    category: int = 1,
    subcategory: int = 1,
    pickup: str = "DG-A",
    city: str = "Dongguan",
    hazard_quantity: int = 0,
    declaration_amount: float = 100.0,
    country: str = "DE",
    ship_method: str = "SEA",
) -> dict[str, Any]:
    return {
        "order_id": order_id,
        "vehicle_category": category,
        "vehicle_subcategory": subcategory,
        "urgent": False,
        "hazard_flag": hazard_quantity > 0,
        "hazard_quantity": hazard_quantity,
        "pickup_name": pickup,
        "pickup_province": "Guangdong",
        "pickup_city": city,
        "declaration_amount": declaration_amount,
        "lsp": "W2",
        "ship_method": ship_method,
        "destination_country": country,
        "spu_list": [{"packing_type": "FULL_PLT", "quantity": pallets}],
        "locked_vehicle_id": locked_vehicle_id,
    }


def _candidate(
    vehicles: list[tuple[str, str, list[str]]],
    *,
    assignment: dict[str, str] | None = None,
) -> dict[str, Any]:
    vehicle_map = {
        vid: {
            "vehicle_id": vid,
            "vehicle_type": vehicle_type,
            "region": "Dongguan",
            "order_ids": order_ids,
        }
        for vid, vehicle_type, order_ids in vehicles
    }
    if assignment is None:
        assignment = {
            oid: vid
            for vid, _vehicle_type, order_ids in vehicles
            for oid in order_ids
        }
    return {
        "vehicles": vehicle_map,
        "assignment": assignment,
        "objective": {"subcategory_splits": 0, "total_cost": 0},
        "feasible": False,
    }


def _fixture(
    fixture_id: str,
    orders: list[dict[str, Any]],
    candidate: dict[str, Any],
    *,
    expected_family: str,
    expected_feasible: bool,
    phase: int = 1,
    amount_limits: dict[str, float] | None = None,
    milp_applicable: bool = True,
    milp_reason: str | None = None,
    assert_phase2_empty_group_init: bool = False,
) -> dict[str, Any]:
    return {
        "fixture_id": fixture_id,
        "instance": {
            "orders": orders,
            "amount_limits": amount_limits or {},
            "phase": phase,
        },
        "candidate": candidate,
        "expected": {
            "feasible": expected_feasible,
            "constraint_family": expected_family,
        },
        "milp_contract": {
            "applicable": milp_applicable,
            "reason": milp_reason,
        },
        "assert_phase2_empty_group_init": assert_phase2_empty_group_init,
    }


def directed_fixtures() -> list[dict[str, Any]]:
    group = [
        _order("L1", locked_vehicle_id="LOCK-A"),
        _order("L2", locked_vehicle_id="LOCK-A"),
    ]
    fixtures = [
        _fixture(
            "01_group_initial_vehicle",
            group,
            _candidate([("LOCK-A", "T3", ["L1", "L2"])]),
            expected_family="feasible",
            expected_feasible=True,
        ),
        _fixture(
            "02_multi_group_whole_move",
            group,
            _candidate([("MOVED", "T3", ["L1", "L2"])]),
            expected_family="feasible",
            expected_feasible=True,
        ),
        _fixture(
            "03_group_merge_free",
            [*group, _order("F1")],
            _candidate([("MERGED", "T3", ["L1", "L2", "F1"])]),
            expected_family="feasible",
            expected_feasible=True,
        ),
        _fixture(
            "04_two_groups_merge",
            [
                *group,
                _order("R1", locked_vehicle_id="LOCK-B"),
                _order("R2", locked_vehicle_id="LOCK-B"),
            ],
            _candidate([("MERGED", "T5", ["L1", "L2", "R1", "R2"])]),
            expected_family="feasible",
            expected_feasible=True,
        ),
        _fixture(
            "05_singleton_group_move",
            [_order("S1", locked_vehicle_id="LOCK-S")],
            _candidate([("OTHER", "T3", ["S1"])]),
            expected_family="feasible",
            expected_feasible=True,
        ),
        _fixture(
            "06_empty_string_group_phase2",
            [_order("E1", locked_vehicle_id=""), _order("E2", locked_vehicle_id="")],
            _candidate([("MOVED", "T3", ["E1", "E2"])]),
            expected_family="feasible",
            expected_feasible=True,
            phase=2,
            assert_phase2_empty_group_init=True,
        ),
        _fixture(
            "07_group_split",
            group,
            _candidate([("LEFT", "T3", ["L1"]), ("RIGHT", "T3", ["L2"])]),
            expected_family="H7",
            expected_feasible=False,
        ),
        _fixture(
            "08_group_partial_move",
            group,
            _candidate([("LOCK-A", "T3", ["L1"]), ("MOVED", "T3", ["L2"])]),
            expected_family="H7",
            expected_feasible=False,
        ),
        _fixture(
            "09_order_lost",
            group,
            _candidate([("ONLY", "T3", ["L1"])], assignment={"L1": "ONLY"}),
            expected_family="C0a",
            expected_feasible=False,
            milp_applicable=False,
            milp_reason="total_assignment_unrepresentable",
        ),
        _fixture(
            "10_order_duplicated",
            [_order("D1")],
            _candidate(
                [("A", "T3", ["D1"]), ("B", "T3", ["D1"])],
                assignment={"D1": "A"},
            ),
            expected_family="C0a",
            expected_feasible=False,
            milp_applicable=False,
            milp_reason="duplicate_membership_unrepresentable",
        ),
        _fixture(
            "11_assignment_disagrees",
            [_order("A1")],
            _candidate([("A", "T3", ["A1"])], assignment={"A1": "B"}),
            expected_family="C0a",
            expected_feasible=False,
            milp_applicable=False,
            milp_reason="dual_representation_disagreement_unrepresentable",
        ),
        _fixture(
            "12_capacity_exceeded",
            [
                _order("C1", locked_vehicle_id="CAP", pallets=2),
                _order("C2", locked_vehicle_id="CAP", pallets=2),
            ],
            _candidate([("MOVED", "T3", ["C1", "C2"])]),
            expected_family="H1",
            expected_feasible=False,
        ),
        _fixture(
            "13_region_mixed",
            [
                _order("G1", locked_vehicle_id="REGION", city="Dongguan"),
                _order("G2", locked_vehicle_id="REGION", city="Shenzhen"),
            ],
            _candidate([("MOVED", "T3", ["G1", "G2"])]),
            expected_family="H2",
            expected_feasible=False,
        ),
        _fixture(
            "14_pickup_limit",
            [
                _order("P1", locked_vehicle_id="PICK", pickup="DG-A"),
                _order("P2", locked_vehicle_id="PICK", pickup="DG-B"),
                _order("P3", locked_vehicle_id="PICK", pickup="DG-C"),
            ],
            _candidate([("MOVED", "T3", ["P1", "P2", "P3"])]),
            expected_family="H3",
            expected_feasible=False,
        ),
        _fixture(
            "15_phase1_category_mixed",
            [
                _order("K1", locked_vehicle_id="CAT", category=1),
                _order("K2", locked_vehicle_id="CAT", category=2),
            ],
            _candidate([("MOVED", "T3", ["K1", "K2"])]),
            expected_family="H4",
            expected_feasible=False,
        ),
        _fixture(
            "16_hazard_h5_h8_family",
            [
                _order("H1", locked_vehicle_id="HAZ", hazard_quantity=1000),
                _order("H2", locked_vehicle_id="HAZ", hazard_quantity=1001),
            ],
            _candidate([("MOVED", "HQ40", ["H1", "H2"])]),
            expected_family="H5/H8",
            expected_feasible=False,
        ),
        _fixture(
            "17_amount_limit_h6",
            [
                _order("M1", locked_vehicle_id="AMOUNT", declaration_amount=600.0),
                _order("M2", locked_vehicle_id="AMOUNT", declaration_amount=600.0),
            ],
            _candidate([("MOVED", "T3", ["M1", "M2"])]),
            expected_family="H6",
            expected_feasible=False,
            amount_limits={"DE,SEA": 1000.0},
        ),
    ]
    return sorted(fixtures, key=lambda item: item["fixture_id"])


__all__ = ["FIXTURE_SCHEMA", "directed_fixtures"]
