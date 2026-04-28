"""WarehouseDeliveryAdapter — ProblemAdapter for the warehouse delivery problem.

Wraps surrogate/oracle.py and surrogate/models.py. All warehouse-specific logic
(Vehicle/Solution/Instance reconstruction, feasibility checks, objective
recomputation) is encapsulated here so Scion core never imports surrogate directly.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from collections import defaultdict
from typing import Any, Mapping, Sequence

from scion.problem.contracts import CheckReport, LowerBoundEstimate, SolverArtifact
from scion.problem.spec import ProblemSpecV1


class WarehouseDeliveryAdapter:
    def __init__(self, spec: ProblemSpecV1) -> None:
        self._spec = spec
        self._root = spec.root_dir
        self._oracle_mod: Any = None
        self._models_mod: Any = None

    @property
    def spec(self) -> ProblemSpecV1:
        return self._spec

    # --- lazy import of surrogate modules ---

    def _ensure_modules(self) -> None:
        if self._oracle_mod is not None:
            return
        oracle_dir = os.path.dirname(
            os.path.abspath(os.path.join(self._root, self._spec.oracle_path))
        )
        self._oracle_mod = _import_module(oracle_dir, "oracle.py", "_wd_oracle")
        self._models_mod = _import_module(oracle_dir, "models.py", "_wd_models")

    # --- Prompt / context ---

    def render_problem_summary(self) -> str:
        cats = ", ".join(
            c.name for c in self._spec.operator_interface.categories
        ) if self._spec.operator_interface else "vehicle_level, order_level"
        editable = ", ".join(self._spec.search_space.editable)
        frozen = ", ".join(self._spec.search_space.frozen)
        objective_policy = _render_objective_policy(self._spec)
        objective_implication = _render_objective_implication(self._spec)

        return f"""\
Name: {self._spec.display_name}
Description: {self._spec.description or 'Warehouse Delivery Assignment'}

### Objective Function
{objective_policy}

Metric definitions:
- subcategory_splits: For each unique `vehicle_subcategory` value across all orders,
  count how many distinct vehicles contain orders of that subcategory, subtract 1,
  then sum. Formula: sum(len(vehicles_containing_subcat) - 1 for each subcategory)
- total_cost: sum(VEHICLE_TYPES[v.vehicle_type].cost for all non-empty vehicles)
  Vehicle costs: T3=800, T5=1200, T10=1800, HQ40=3300, HQ40_DG=6600

{objective_implication}

### How the Initial Solution is Built (greedy_init)
Orders are grouped by (vehicle_category, vehicle_subcategory, pickup_city).
Within each group, orders are packed sequentially into vehicles using first-fit.
When a vehicle reaches capacity (pallet limit), a new vehicle is opened for the same group.
Subcategory splits occur when a subcategory group's total pallets exceed one vehicle's capacity.
Example: if subcategory 3 has 50 pallets and HQ40 capacity is 40, it needs 2 vehicles -> 1 split.

To reduce splits, an operator typically consolidates orders so a subcategory fits in
fewer vehicles: merging partially-filled vehicles of the SAME vehicle_subcategory,
or moving orders between vehicles to free up space for same-subcategory consolidation.
To reduce cost while preserving splits, an operator typically downsizes, merges
under-filled compatible vehicles, or removes vehicles without spreading a subcategory
across more vehicles. Random order moves between arbitrary vehicles are unlikely to
improve either metric reliably.

### Worked Example (Small Instance)
Instance: 6 orders, 2 subcategories, all Shenzhen region
  Orders: A1(subcat=1,8plt), A2(subcat=1,6plt), A3(subcat=1,10plt),
          A4(subcat=1,12plt), B1(subcat=2,5plt), B2(subcat=2,4plt)
  Vehicle types: T10(cap=14,cost=1800), HQ40(cap=40,cost=3300)

Greedy init (groups by subcategory, first-fit):
  V1[T10]: A1(8)+A2(6)=14plt -> full
  V2[T10]: A3(10) -> 10plt (A4 won't fit: 10+12=22 > 14)
  V3[T10]: A4(12) -> 12plt
  V4[T10]: B1(5)+B2(4)=9plt
  Objective: splits=2 (subcat 1 in V1,V2,V3 -> split=2; subcat 2 in V4 -> split=0)
             cost=4*1800=7200

Improved (merge subcat-1 vehicles into HQ40):
  V1[HQ40]: A1+A2+A3+A4=36plt
  V4[T10]: B1+B2=9plt
  Objective: splits=0, cost=3300+1800=5100 -> BETTER on both objectives

The key move: merging V2+V3 orders into V1 (upgrading to HQ40).
This is what a good subcategory-consolidation operator should do.

Operator categories: {cats}
Editable files: {editable}
Frozen files (do not modify): {frozen}"""

    def render_operator_interface(self) -> str:
        base_py_path = os.path.join(self._root, "operators", "base.py")
        try:
            with open(base_py_path, encoding="utf-8") as fh:
                base_class_src = fh.read()
        except OSError:
            base_class_src = (
                "class Operator(ABC):\n"
                "    @abstractmethod\n"
                "    def execute(self, solution: Solution, rng: Random) -> Solution:\n"
                "        ..."
            )

        return f"""\
### Operator Base Class (from operators/base.py)
```python
{base_class_src}
```

### Key Data Structures (from models.py)
- `Solution`: contains `vehicles: dict[str, Vehicle]` and `assignment: dict[str, str]` (order_id → vehicle_id)
  - Call `solution.deep_copy()` to get a deep copy before modifying
  - `solution.remove_empty_vehicles()` to clean up empty vehicles in-place
- `Vehicle`: `vehicle_id`, `vehicle_type` (HQ40_DG|HQ40|T10|T5|T3), `region`, `order_ids: list[str]`
- `Order` (complete field list — use these EXACT attribute names):
  - `order_id: str` — unique identifier
  - `vehicle_category: int` — large category (feasibility H4: same vehicle must have same category)
  - `vehicle_subcategory: int` — sub-category used by the priority-1 split metric
  - `urgent: bool` — urgency flag
  - `hazard_flag: bool` — True if order contains hazardous goods
  - `hazard_quantity: int` — hazardous goods quantity in pcs (>1800 requires HQ40_DG)
  - `pickup_name: str` — pickup point name (constraint H3: max pickups per vehicle per region)
  - `pickup_city: str` — "Dongguan" or "Shenzhen" (constraint H2: same region per vehicle)
  - `declaration_amount: float` — customs declaration amount (constraint H6)
  - `lsp: str` — logistics service provider
  - `ship_method: str` — shipping method (H6 grouping key with destination_country)
  - `destination_country: str` — destination country (H6 grouping key with ship_method)
  - `spu_list: list[SPU]` — packing units; use `calc_pallets(order.spu_list)` from models.py
  - `locked_vehicle_id: Optional[str]` — None = freely assignable; non-None = MUST stay in that vehicle
- `Instance`: accessed via `self.instance` (set in __init__); contains `orders: dict[str, Order]`, `amount_limits: dict[str, float]`
- Helper: `select_minimum_vehicle_type(total_pallets, total_hazard) -> str` from models.py
- Helper: `get_max_pickups(region) -> int` from models.py (Dongguan=2, Shenzhen=3)

### Critical Constraints
1. **Deep copy first**: always call `new_sol = solution.deep_copy()` before any modification
2. **Locked orders**: never move orders where `order.locked_vehicle_id is not None`
3. **rng**: use `rng` (a `random.Random` instance) for all randomness — do NOT import `random` directly
4. **Determinism**: NEVER use `uuid.uuid4()` or any system entropy source. Generate vehicle IDs with `generate_vehicle_id(rng)` from `operators.base`. NEVER use `list(set(...))` or iterate over `set`/`dict` in an order-dependent way. Use `sorted()` when you need a stable order from sets or dict keys/values. The solver runs twice with the same seed to verify determinism — any non-deterministic output causes rejection.
5. **Return value**: return the modified solution (or the original if no valid move was found)
6. **Imports**: only use modules from the import whitelist; no external packages

### Feasibility Constraints (MUST NOT violate — will cause immediate rejection)
7. **Every order assigned**: every order in the instance MUST appear in exactly one vehicle's order_ids AND in the assignment dict. Never drop or duplicate orders.
8. **Consistency**: `solution.assignment[order_id] == vehicle_id` must match `order_id in vehicle.order_ids` for ALL orders. After any modification, update BOTH.
9. **Vehicle capacity**: total pallets in a vehicle must not exceed its type's capacity
10. **Hazardous goods**: orders with `hazard_flag=True` and total hazard_quantity > 1800 MUST be in HQ40_DG
11. **No empty vehicles**: after modifications, call `new_sol.remove_empty_vehicles()` to clean up
12. **Same region**: all orders in a vehicle must have the same `pickup_city` region
13. **Same category**: all orders in a vehicle must have the same `vehicle_category`
14. **Pickup limit**: number of distinct `pickup_name` values in a vehicle must not exceed `get_max_pickups(region)`"""

    # --- Instance / output ---

    def load_instance(self, instance_path: str) -> Any:
        self._ensure_modules()
        models = self._models_mod
        with open(instance_path, encoding="utf-8") as f:
            idata = json.load(f)
        orders = {}
        for o in idata["orders"]:
            spu_list = [
                models.SPU(packing_type=s["packing_type"], quantity=s["quantity"])
                for s in o["spu_list"]
            ]
            order = models.Order(
                order_id=o["order_id"],
                vehicle_category=o["vehicle_category"],
                vehicle_subcategory=o["vehicle_subcategory"],
                urgent=o["urgent"],
                hazard_flag=o["hazard_flag"],
                hazard_quantity=o["hazard_quantity"],
                pickup_name=o["pickup_name"],
                pickup_province=o["pickup_province"],
                pickup_city=o["pickup_city"],
                declaration_amount=o["declaration_amount"],
                lsp=o["lsp"],
                ship_method=o["ship_method"],
                destination_country=o["destination_country"],
                spu_list=spu_list,
                locked_vehicle_id=o.get("locked_vehicle_id"),
            )
            orders[order.order_id] = order
        amount_limits = idata.get("amount_limits", {})
        instance = models.Instance(
            orders=orders,
            amount_limits=amount_limits,
            phase=1,
        )
        return instance

    def deserialize_solver_output(
        self,
        raw_output: Mapping[str, Any],
        instance: Any,
    ) -> SolverArtifact:
        self._ensure_modules()
        models = self._models_mod

        vehicles = {}
        for vid, vdata in raw_output.get("vehicles", {}).items():
            vehicles[vid] = models.Vehicle(
                vehicle_id=vdata["vehicle_id"],
                vehicle_type=vdata["vehicle_type"],
                region=vdata["region"],
                order_ids=list(vdata["order_ids"]),
            )
        solution = models.Solution(
            vehicles=vehicles,
            assignment=dict(raw_output.get("assignment", {})),
        )

        objective_raw = raw_output.get("objective", {})
        feasible_raw = raw_output.get("feasible", False)

        return SolverArtifact(
            raw_output=dict(raw_output),
            objective={
                "subcategory_splits": objective_raw.get("subcategory_splits", 0),
                "total_cost": objective_raw.get("total_cost", 0),
            },
            feasible=feasible_raw,
            normalized_solution=solution,
        )

    # --- Verification ---

    def check_solution_consistency(
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> CheckReport:
        """C0a structural completeness check — every order assigned exactly once."""
        solution = artifact.normalized_solution
        if solution is None:
            return CheckReport(passed=False, reasons=("no normalized_solution",))

        reasons: list[str] = []
        all_order_ids = set(instance.orders.keys())
        placed: dict[str, str] = {}
        for vid, vehicle in solution.vehicles.items():
            for oid in vehicle.order_ids:
                if oid not in all_order_ids:
                    reasons.append(f"vehicle {vid} contains unknown order {oid}")
                elif oid in placed:
                    reasons.append(f"order {oid} in both {placed[oid]} and {vid}")
                else:
                    placed[oid] = vid

        missing = all_order_ids - set(placed.keys())
        if missing:
            reasons.append(f"{len(missing)} orders not assigned: {sorted(missing)[:5]}")

        return CheckReport(passed=len(reasons) == 0, reasons=tuple(reasons))

    def check_feasibility(
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> CheckReport:
        self._ensure_modules()
        solution = artifact.normalized_solution
        if solution is None:
            return CheckReport(passed=False, reasons=("no normalized_solution",))

        feas = self._oracle_mod.check_feasibility(solution, instance, phase=1)
        return CheckReport(
            passed=feas.is_feasible,
            reasons=tuple(feas.violations[:10]),
        )

    def recompute_objective(
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> Mapping[str, int | float]:
        self._ensure_modules()
        solution = artifact.normalized_solution
        obj = self._oracle_mod.recompute_objective(solution, instance, solve_time_ms=0)
        return {
            "subcategory_splits": obj.subcategory_splits,
            "total_cost": obj.total_cost,
        }

    # --- Lower bound ---

    def estimate_lower_bound(
        self,
        metric_name: str,
        instance_paths: Sequence[str],
    ) -> LowerBoundEstimate | None:
        """Load precomputed MILP bounds if available.

        Looks for a JSON file at <root_dir>/milp_bounds/<instance_stem>.json
        containing {"subcategory_splits": ..., "total_cost": ..., "status": ...}.
        CPLEX-generated non-optimal incumbents are report-only references and
        therefore return kind="instance" rather than kind="exact".
        """
        bounds_dir = os.path.join(self._root, "milp_bounds")
        if not os.path.isdir(bounds_dir):
            return None

        values: list[float] = []
        kind = "exact"
        for path in instance_paths:
            stem = os.path.splitext(os.path.basename(path))[0]
            bound_file = os.path.join(bounds_dir, f"{stem}.json")
            if not os.path.isfile(bound_file):
                continue
            with open(bound_file) as f:
                data = json.load(f)
            if metric_name in data:
                values.append(data[metric_name])
                if data.get("status") != "optimal":
                    kind = "instance"

        if not values:
            return None

        return LowerBoundEstimate(
            metric_name=metric_name,
            value=sum(values) / len(values),
            kind=kind,
            note=f"MILP {kind} from {len(values)} instances",
        )


def _render_objective_policy(spec: ProblemSpecV1) -> str:
    ordered = sorted(spec.objectives, key=lambda obj: obj.priority)
    if spec.objective_policy.mode == "weighted_sum":
        lines = [
            "Policy: weighted_sum. The decision objective is one weighted scalar; "
            "any positive weighted aggregate improvement is valuable."
        ]
        if spec.objective_policy.expose_weights_to_llm:
            for obj in ordered:
                lines.append(
                    f"- {obj.name}: direction={obj.direction}, "
                    f"weight={obj.weight}, tie_tolerance={obj.tie_tolerance}"
                )
        else:
            for obj in ordered:
                lines.append(
                    f"- {obj.name}: direction={obj.direction}, "
                    f"tie_tolerance={obj.tie_tolerance}"
                )
        return "\n".join(lines)

    if spec.objective_policy.mode == "single":
        obj = ordered[0]
        return (
            f"Policy: single objective. Decision metric is `{obj.name}` "
            f"({obj.direction}, tie_tolerance={obj.tie_tolerance})."
        )

    lines = [
        "Policy: lexicographic. Compare objectives in priority order; a lower-priority "
        "objective matters only when all higher-priority objectives tie within tolerance."
    ]
    for obj in ordered:
        lines.append(
            f"- priority {obj.priority}: {obj.name} "
            f"({obj.direction}, tie_tolerance={obj.tie_tolerance})"
        )
    return "\n".join(lines)


def _render_objective_implication(spec: ProblemSpecV1) -> str:
    if spec.objective_policy.mode == "weighted_sum":
        return (
            "Key implication for weighted-sum specs: an operator may improve any "
            "component if the weighted aggregate improves. Higher-weight components "
            "have larger marginal value, but feasibility constraints remain hard."
        )
    if spec.objective_policy.mode == "single":
        return (
            "Key implication for single-objective specs: an operator is useful when "
            "it measurably improves the decision metric without violating hard constraints."
        )
    return (
        "Key implication for lexicographic specs: an operator may improve any metric, "
        "but lower-priority gains are only decision-relevant when all higher-priority "
        "metrics are preserved within tolerance. Lower-priority moves should include "
        "a guard that returns the original solution if they would harm a protected metric."
    )


# ---------------------------------------------------------------------------
# Module import helper (extracted from verification/feasibility.py)
# ---------------------------------------------------------------------------

def _import_module(directory: str, filename: str, sys_key: str) -> Any:
    path = os.path.join(directory, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"{filename} not found at {path}")

    saved = list(sys.path)
    if directory not in sys.path:
        sys.path.insert(0, directory)
    try:
        spec = importlib.util.spec_from_file_location(sys_key, path)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        sys.modules[sys_key] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    finally:
        sys.path[:] = saved
