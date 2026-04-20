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
        return self._spec.description or (
            "Warehouse Delivery Assignment: assign B2B orders to vehicle slots. "
            "Objective (lexicographic): minimize subcategory_splits, then total_cost."
        )

    def render_operator_interface(self) -> str:
        return (
            "from operators.base import Operator\n"
            "\n"
            "class MyOperator(Operator):\n"
            '    name = "my_operator"\n'
            '    category = "order_level"  # or "vehicle_level"\n'
            "\n"
            "    def execute(self, solution, rng):\n"
            "        # solution.vehicles: dict[str, Vehicle]\n"
            "        # solution.assignment: dict[order_id, vehicle_id]\n"
            "        # Must return a new Solution (do not mutate input)\n"
            "        ..."
        )

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
        containing {"subcategory_splits": ..., "total_cost": ..., "status": "optimal"|"bound"}.
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
