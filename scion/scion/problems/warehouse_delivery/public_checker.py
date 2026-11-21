"""Frozen Warehouse checks; no candidate models, operators or solver imports."""
from pathlib import Path
import sys

from scion.observation.wire import emit, read_request

# Frozen model/oracle are copied beside this checker, never from /subject.
sys.path.insert(0, str(Path(__file__).parent))
from models import Instance, Order, SPU, Solution, Vehicle, VEHICLE_TYPES
from oracle import check_feasibility, recompute_objective


def check(data, value):
    invalid = {"schema_version": 1, "consistency": "fail", "feasibility": "not_evaluated",
               "recomputed_objective": None, "reason_codes": ["SOLUTION_INVALID"]}
    if type(value) is not dict or set(value) != {"vehicles", "assignment"}:
        return invalid
    vehicles, assignment = value["vehicles"], value["assignment"]
    if type(vehicles) is not dict or type(assignment) is not dict:
        return invalid
    instance = Instance(
        orders={o["order_id"]: Order(**{**o, "spu_list": [SPU(**s) for s in o["spu_list"]]}) for o in data["orders"]},
        amount_limits=data["amount_limits"], phase=1,
    )
    seen = set()
    for key, vehicle in vehicles.items():
        if type(vehicle) is not dict or set(vehicle) != {"vehicle_id", "vehicle_type", "region", "order_ids"}:
            return invalid
        if any(type(vehicle[field]) is not str for field in ("vehicle_id", "vehicle_type", "region")):
            return invalid
        if vehicle["vehicle_id"] != key or vehicle["vehicle_type"] not in VEHICLE_TYPES or type(vehicle["order_ids"]) is not list:
            return invalid
        for oid in vehicle["order_ids"]:
            if type(oid) is not str or oid not in instance.orders or oid in seen or assignment.get(oid) != key:
                return invalid
            seen.add(oid)
    if seen != set(instance.orders) or set(assignment) != seen:
        return invalid
    solution = Solution({k: Vehicle(**v) for k, v in vehicles.items()}, assignment)
    feasibility = check_feasibility(solution, instance, 1)
    objective = recompute_objective(solution, instance)
    return {"schema_version": 1, "consistency": "pass", "feasibility": "pass" if feasibility.is_feasible else "fail",
            "recomputed_objective": {"subcategory_splits": objective.subcategory_splits, "total_cost": objective.total_cost},
            "reason_codes": [] if feasibility.is_feasible else ["FEASIBILITY_VIOLATION"]}


if __name__ == "__main__":
    request = read_request()
    emit(check(request["instance"], request["solution"]))
