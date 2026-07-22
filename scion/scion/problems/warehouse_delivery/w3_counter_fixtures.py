"""Independent directed fixtures for Warehouse W3 merge-pair counters.

The fixture oracle exercises the frozen operator classes themselves.  It does
not reuse the W3 counter predicates: champion eligibility is observed through
``execute`` with a directed RNG, R3 eligibility calls the frozen operator's
own profile/type/amount/consistency methods, and formal compatibility is
decided by a separately reconstructed solution passed to the frozen Oracle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

FIXTURE_SCHEMA = "scion.warehouse_w3_directed_counter_fixtures.v1"
FIXTURE_IDS = (
    "basic_unlocked",
    "multi_order_locked_group",
    "capacity_exceeded",
    "hazard_special_upgrade",
    "pickup_exceeded",
    "region_mixed",
    "category_mixed",
    "amount_limit_exceeded",
)


@dataclass(frozen=True)
class _DirectedRng:
    first: str
    second: str

    def sample(self, population: list[str], count: int) -> list[str]:
        if count != 2 or self.first not in population or self.second not in population:
            raise AssertionError("unexpected frozen champion RNG request")
        return [self.first, self.second]


def _order(models: Any, order_id: str, **overrides: Any) -> Any:
    values: dict[str, Any] = {
        "order_id": order_id,
        "vehicle_category": 1,
        "vehicle_subcategory": 1,
        "urgent": False,
        "hazard_flag": False,
        "hazard_quantity": 0,
        "pickup_name": f"pickup-{order_id}",
        "pickup_province": "Guangdong",
        "pickup_city": "Dongguan",
        "declaration_amount": 10.0,
        "lsp": "L",
        "ship_method": "sea",
        "destination_country": "DE",
        "spu_list": [models.SPU(packing_type="FULL_PLT", quantity=1)],
        "locked_vehicle_id": None,
    }
    values.update(overrides)
    return models.Order(**values)


def fixture(runtime: Mapping[str, Any], fixture_id: str) -> tuple[Any, Any]:
    if fixture_id not in FIXTURE_IDS:
        raise ValueError(f"unknown W3 counter fixture: {fixture_id}")
    models = runtime["models"]
    amount_limits: dict[str, float] = {}
    if fixture_id == "multi_order_locked_group":
        orders = {
            "a1": _order(
                models,
                "a1",
                locked_vehicle_id="origin-a",
                pickup_name="pickup-a",
            ),
            "a2": _order(
                models,
                "a2",
                locked_vehicle_id="origin-a",
                pickup_name="pickup-a",
            ),
            "b": _order(models, "b"),
        }
        vehicle_rows = (
            ("origin-a", "T3", "Dongguan", ["a1", "a2"]),
            ("b-vehicle", "T3", "Dongguan", ["b"]),
        )
    else:
        first: dict[str, Any] = {}
        second: dict[str, Any] = {}
        if fixture_id == "capacity_exceeded":
            first["spu_list"] = [models.SPU(packing_type="FULL_PLT", quantity=30)]
            second["spu_list"] = [models.SPU(packing_type="FULL_PLT", quantity=30)]
        elif fixture_id == "hazard_special_upgrade":
            first.update(hazard_flag=True, hazard_quantity=1000)
            second.update(hazard_flag=True, hazard_quantity=1000)
        elif fixture_id == "region_mixed":
            second["pickup_city"] = "Shenzhen"
        elif fixture_id == "category_mixed":
            second["vehicle_category"] = 2
        elif fixture_id == "amount_limit_exceeded":
            amount_limits = {"DE,sea": 15.0}
        orders = {"a": _order(models, "a", **first), "b": _order(models, "b", **second)}
        if fixture_id == "pickup_exceeded":
            orders["c"] = _order(models, "c", pickup_name="pickup-c")
        vehicle_rows = (
            ("a-vehicle", "HQ40", "Dongguan", ["a"]),
            (
                "b-vehicle",
                "HQ40",
                "Shenzhen" if fixture_id == "region_mixed" else "Dongguan",
                ["b", "c"] if fixture_id == "pickup_exceeded" else ["b"],
            ),
        )
    vehicles = {
        vehicle_id: models.Vehicle(vehicle_id, vehicle_type, region, order_ids)
        for vehicle_id, vehicle_type, region, order_ids in vehicle_rows
    }
    assignment = {
        order_id: vehicle_id
        for vehicle_id, vehicle in vehicles.items()
        for order_id in vehicle.order_ids
    }
    return (
        models.Instance(orders=orders, amount_limits=amount_limits, phase=1),
        models.Solution(vehicles=vehicles, assignment=assignment),
    )


def _changed_pair(before: Any, after: Any) -> tuple[str, str] | None:
    before_ids = {key for key, value in before.vehicles.items() if value.order_ids}
    after_ids = {key for key, value in after.vehicles.items() if value.order_ids}
    removed = before_ids - after_ids
    if len(removed) != 1 or len(after_ids) != len(before_ids) - 1:
        return None
    source = next(iter(removed))
    moved = set(before.vehicles[source].order_ids)
    destinations = {
        after.assignment[order_id]
        for order_id in moved
        if after.assignment.get(order_id) != source
    }
    if len(destinations) != 1:
        return None
    return source, next(iter(destinations))


def frozen_operator_executable_pairs(
    runtime: Mapping[str, Any], instance: Any, solution: Any
) -> set[tuple[str, str]]:
    operator = runtime["merge_operator"](instance, 1)
    vehicle_ids = sorted(solution.vehicles)
    realized: set[tuple[str, str]] = set()
    for first in vehicle_ids:
        for second in vehicle_ids:
            if first == second:
                continue
            result = operator.execute(solution, _DirectedRng(first, second))
            pair = _changed_pair(solution, result)
            if pair is not None:
                realized.add(pair)
    return realized


def champion_executable_pairs(
    runtime: Mapping[str, Any], instance: Any, solution: Any
) -> set[tuple[str, str]]:
    return frozen_operator_executable_pairs(runtime, instance, solution)


def _independent_merge(
    runtime: Mapping[str, Any],
    instance: Any,
    solution: Any,
    source: str,
    destination: str,
) -> Any | None:
    models = runtime["models"]
    candidate = solution.deep_copy()
    source_vehicle = candidate.vehicles[source]
    destination_vehicle = candidate.vehicles[destination]
    order_ids = list(destination_vehicle.order_ids) + list(source_vehicle.order_ids)
    pallets = sum(
        models.calc_pallets(instance.orders[item].spu_list) for item in order_ids
    )
    hazard = sum(
        instance.orders[item].hazard_quantity
        for item in order_ids
        if instance.orders[item].hazard_flag
    )
    vehicle_type = models.select_minimum_vehicle_type(pallets, hazard)
    if vehicle_type not in models.VEHICLE_TYPES:
        return None
    if models.VEHICLE_TYPES[vehicle_type].capacity < pallets:
        return None
    if hazard > 1800 and vehicle_type != "HQ40_DG":
        return None
    destination_vehicle.order_ids = order_ids
    destination_vehicle.vehicle_type = vehicle_type
    for order_id in source_vehicle.order_ids:
        candidate.assignment[order_id] = destination
    del candidate.vehicles[source]
    candidate.remove_empty_vehicles()
    return candidate


def formal_oracle_pairs(
    runtime: Mapping[str, Any], instance: Any, solution: Any
) -> set[tuple[str, str]]:
    realized: set[tuple[str, str]] = set()
    vehicle_ids = sorted(solution.vehicles)
    for source in vehicle_ids:
        for destination in vehicle_ids:
            if source == destination:
                continue
            candidate = _independent_merge(
                runtime, instance, solution, source, destination
            )
            if candidate is None:
                continue
            result = runtime["oracle"].check_feasibility(candidate, instance, phase=1)
            if result.is_feasible:
                realized.add((source, destination))
    return realized


def r3_frozen_predicate_pairs(
    runtime: Mapping[str, Any], instance: Any, solution: Any
) -> set[tuple[str, str]]:
    """Enumerate using the frozen R3 operator's own private predicate methods."""

    operator = runtime["merge_operator"](instance, 1)
    models = runtime["models"]
    vehicle_ids = sorted(solution.vehicles)
    profiles = {
        vehicle_id: operator._vehicle_profile(solution, vehicle_id)
        for vehicle_id in vehicle_ids
    }
    eligible: set[tuple[str, str]] = set()
    for source in vehicle_ids:
        source_profile = profiles[source]
        if source_profile is None or not source_profile[7]:
            continue
        for destination in vehicle_ids:
            if source == destination:
                continue
            destination_profile = profiles[destination]
            if destination_profile is None:
                continue
            if (
                source_profile[0] != destination_profile[0]
                or source_profile[1] != destination_profile[1]
            ):
                continue
            vehicle_type = operator._minimum_type(
                source_profile[2] + destination_profile[2],
                source_profile[3] + destination_profile[3],
            )
            if vehicle_type is None:
                continue
            if len(
                set(source_profile[4]).union(destination_profile[4])
            ) > models.get_max_pickups(source_profile[0]):
                continue
            if not operator._amounts_feasible(
                source_profile[5], destination_profile[5]
            ):
                continue
            candidate = _independent_merge(
                runtime, instance, solution, source, destination
            )
            if candidate is not None and operator._is_consistent(candidate):
                eligible.add((source, destination))
    return eligible


__all__ = [
    "FIXTURE_IDS",
    "FIXTURE_SCHEMA",
    "champion_executable_pairs",
    "fixture",
    "formal_oracle_pairs",
    "r3_frozen_predicate_pairs",
]
