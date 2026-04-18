"""
Two-phase epsilon-constraint MILP exact solver.

Usage:
  python -m surrogate.milp_solver <instance.json> [--time-limit 600] [--output result.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pulp

# Ensure surrogate/ on sys.path
_surrogate_dir = Path(__file__).parent
if str(_surrogate_dir) not in sys.path:
    sys.path.insert(0, str(_surrogate_dir))

from milp_model import build_milp, compute_K, build_locked_slot_map, extract_solution
from models import Instance, Solution, VEHICLE_TYPES
from oracle import check_feasibility, recompute_objective


@dataclass
class MILPResult:
    status: str                      # "optimal" | "feasible" | "infeasible" | "timeout" | "error"
    solution: Optional[Solution]     # None if infeasible/error
    objective_f1: Optional[int]      # subcategory_splits
    objective_f2: Optional[float]    # total_cost
    phase1_time: float               # seconds
    phase2_time: float               # seconds
    phase1_gap: float                # MIP gap at phase1 end (0 if optimal)
    phase2_gap: float
    lower_bound_f1: Optional[int]    # best lower bound if not optimal
    lower_bound_f2: Optional[float]


def _solve_phase(
    prob: pulp.LpProblem,
    time_limit: int,
    verbose: bool,
) -> tuple[int, float, float]:
    """Solve a single MIP phase. Returns (status_code, gap, elapsed_seconds)."""
    solver = pulp.PULP_CBC_CMD(
        msg=1 if verbose else 0,
        timeLimit=time_limit,
        gapRel=0,
    )
    t0 = time.time()
    prob.solve(solver)
    elapsed = time.time() - t0

    status = prob.status  # 1=Optimal, 0=Not Solved, -1=Infeasible, -2=Unbounded, -3=Undefined

    # Compute MIP gap
    gap = 0.0
    try:
        obj_val = pulp.value(prob.objective)
        best_bound = prob.bestBound if hasattr(prob, 'bestBound') else None
        if obj_val is not None and best_bound is not None and abs(obj_val) > 1e-9:
            gap = abs(obj_val - best_bound) / (abs(obj_val) + 1e-12)
    except Exception:
        pass

    return status, gap, elapsed


def _compute_sum_alpha(vars_dict: dict) -> int:
    """Read sum of alpha variables from a solved model."""
    S = vars_dict["S"]
    J = vars_dict["J"]
    alpha = vars_dict["alpha"]
    total = 0
    for s in S:
        for j in J:
            val = pulp.value(alpha[s, j])
            if val is not None and val > 0.5:
                total += 1
    return total


def _compute_cost(vars_dict: dict) -> int:
    """Read total cost from solved z variables."""
    J = vars_dict["J"]
    T = vars_dict["T"]
    z = vars_dict["z"]
    total = 0
    for j in J:
        for t in T:
            val = pulp.value(z[j, t])
            if val is not None and val > 0.5:
                total += VEHICLE_TYPES[t].cost
    return total


def solve_exact(
    instance: Instance,
    time_limit_seconds: int = 600,
    symmetry_breaking: bool = True,
    verbose: bool = False,
) -> MILPResult:
    """Two-phase epsilon-constraint MILP solver.

    Phase 1: minimize subcategory_splits (sum alpha)
    Phase 2: minimize total_cost subject to f1 == f1*
    """
    K = compute_K(instance)
    locked_slot_map = build_locked_slot_map(instance)

    # Count active subcategories for converting sum_alpha → splits
    active_subcats = {o.vehicle_subcategory for o in instance.orders.values()}
    n_active = len(active_subcats)

    # ---- Phase 1 ----
    try:
        prob1, vars1 = build_milp(
            instance, K, locked_slot_map,
            symmetry_breaking=symmetry_breaking,
            phase2_sum_alpha_star=None,
        )
    except Exception as e:
        return MILPResult(
            status="error", solution=None,
            objective_f1=None, objective_f2=None,
            phase1_time=0, phase2_time=0,
            phase1_gap=0, phase2_gap=0,
            lower_bound_f1=None, lower_bound_f2=None,
        )

    phase1_time_limit = max(time_limit_seconds // 2, 60)
    status1, gap1, elapsed1 = _solve_phase(prob1, phase1_time_limit, verbose)

    if status1 == -1:
        return MILPResult(
            status="infeasible", solution=None,
            objective_f1=None, objective_f2=None,
            phase1_time=elapsed1, phase2_time=0,
            phase1_gap=gap1, phase2_gap=0,
            lower_bound_f1=None, lower_bound_f2=None,
        )

    if status1 not in (1, 0):
        # -2=Unbounded, -3=Undefined, etc.
        # status 0 with a feasible solution from timeout is handled below
        # Check if we at least have a feasible solution
        obj_val = pulp.value(prob1.objective)
        if obj_val is None:
            return MILPResult(
                status="error", solution=None,
                objective_f1=None, objective_f2=None,
                phase1_time=elapsed1, phase2_time=0,
                phase1_gap=gap1, phase2_gap=0,
                lower_bound_f1=None, lower_bound_f2=None,
            )

    # Read Phase 1 result
    sum_alpha_star = _compute_sum_alpha(vars1)
    f1_star = sum_alpha_star - n_active  # splits = sum_alpha - |S_active|

    phase1_optimal = (status1 == 1)

    # If phase 1 timed out but has a feasible solution, proceed with best found
    remaining_time = max(time_limit_seconds - elapsed1, 30)

    # ---- Phase 2 ----
    try:
        prob2, vars2 = build_milp(
            instance, K, locked_slot_map,
            symmetry_breaking=symmetry_breaking,
            phase2_sum_alpha_star=sum_alpha_star,
        )
    except Exception as e:
        # Phase 2 build failed; return Phase 1 result
        sol1 = extract_solution(instance, vars1)
        sol1.objective = recompute_objective(sol1, instance)
        return MILPResult(
            status="feasible" if phase1_optimal else "timeout",
            solution=sol1,
            objective_f1=f1_star,
            objective_f2=None,
            phase1_time=elapsed1, phase2_time=0,
            phase1_gap=gap1, phase2_gap=0,
            lower_bound_f1=f1_star if phase1_optimal else None,
            lower_bound_f2=None,
        )

    phase2_time_limit = int(remaining_time)
    status2, gap2, elapsed2 = _solve_phase(prob2, phase2_time_limit, verbose)

    if status2 == -1:
        # Phase 2 infeasible means Phase 1 solution was boundary;
        # return phase 1 solution
        sol1 = extract_solution(instance, vars1)
        sol1.objective = recompute_objective(sol1, instance)
        return MILPResult(
            status="feasible",
            solution=sol1,
            objective_f1=f1_star,
            objective_f2=sol1.objective.total_cost if sol1.objective else None,
            phase1_time=elapsed1, phase2_time=elapsed2,
            phase1_gap=gap1, phase2_gap=0,
            lower_bound_f1=f1_star,
            lower_bound_f2=None,
        )

    if status2 not in (1, 0):
        obj_val = pulp.value(prob2.objective)
        if obj_val is None:
            sol1 = extract_solution(instance, vars1)
            sol1.objective = recompute_objective(sol1, instance)
            return MILPResult(
                status="feasible",
                solution=sol1,
                objective_f1=f1_star,
                objective_f2=sol1.objective.total_cost if sol1.objective else None,
                phase1_time=elapsed1, phase2_time=elapsed2,
                phase1_gap=gap1, phase2_gap=0,
                lower_bound_f1=f1_star,
                lower_bound_f2=None,
            )

    # Extract Phase 2 solution
    solution = extract_solution(instance, vars2)
    solution.objective = recompute_objective(solution, instance)

    f2_star = _compute_cost(vars2)

    # Determine overall status
    phase2_optimal = (status2 == 1)
    if phase1_optimal and phase2_optimal:
        overall_status = "optimal"
    elif gap1 > 0 or gap2 > 0:
        overall_status = "feasible"
    else:
        overall_status = "feasible"

    # Lower bounds
    lb_f1 = f1_star if phase1_optimal else None
    lb_f2 = None
    try:
        if hasattr(prob2, 'bestBound') and prob2.bestBound is not None:
            lb_f2 = prob2.bestBound
    except Exception:
        pass

    return MILPResult(
        status=overall_status,
        solution=solution,
        objective_f1=f1_star,
        objective_f2=f2_star,
        phase1_time=elapsed1,
        phase2_time=elapsed2,
        phase1_gap=gap1,
        phase2_gap=gap2,
        lower_bound_f1=lb_f1,
        lower_bound_f2=lb_f2,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _load_instance(path: str) -> Instance:
    """Load Instance from JSON (same as solver.load_instance)."""
    from models import Order, SPU
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    orders = {}
    for o in data["orders"]:
        spu_list = [SPU(packing_type=s["packing_type"], quantity=s["quantity"])
                    for s in o["spu_list"]]
        order = Order(
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

    return Instance(
        orders=orders,
        amount_limits=data.get("amount_limits", {}),
        phase=1,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="MILP Exact Solver")
    parser.add_argument("instance", help="Instance JSON path")
    parser.add_argument("--time-limit", type=int, default=600, help="Time limit in seconds")
    parser.add_argument("--output", default=None, help="Output result JSON path")
    parser.add_argument("--verbose", action="store_true", help="Show CBC output")
    parser.add_argument("--no-symmetry-breaking", action="store_true")
    args = parser.parse_args()

    instance = _load_instance(args.instance)

    result = solve_exact(
        instance,
        time_limit_seconds=args.time_limit,
        symmetry_breaking=not args.no_symmetry_breaking,
        verbose=args.verbose,
    )

    # Print summary
    print(f"Status:       {result.status}")
    print(f"f1 (splits):  {result.objective_f1}")
    print(f"f2 (cost):    {result.objective_f2}")
    print(f"Phase 1 time: {result.phase1_time:.1f}s  (gap: {result.phase1_gap:.4f})")
    print(f"Phase 2 time: {result.phase2_time:.1f}s  (gap: {result.phase2_gap:.4f})")
    print(f"LB f1:        {result.lower_bound_f1}")
    print(f"LB f2:        {result.lower_bound_f2}")

    if result.solution:
        feas = check_feasibility(result.solution, instance, 1)
        print(f"Feasible:     {feas.is_feasible}")
        if not feas.is_feasible:
            for v in feas.violations:
                print(f"  VIOLATION: {v}")
        obj = recompute_objective(result.solution, instance)
        print(f"Recomputed:   splits={obj.subcategory_splits}, cost={obj.total_cost}")
        print(f"Vehicles:     {len(result.solution.vehicles)}")

    # Output JSON
    if args.output and result.solution:
        out = {
            "status": result.status,
            "objective_f1": result.objective_f1,
            "objective_f2": result.objective_f2,
            "phase1_time": result.phase1_time,
            "phase2_time": result.phase2_time,
            "phase1_gap": result.phase1_gap,
            "phase2_gap": result.phase2_gap,
            "vehicles": {
                vid: {
                    "vehicle_id": v.vehicle_id,
                    "vehicle_type": v.vehicle_type,
                    "region": v.region,
                    "order_ids": v.order_ids,
                }
                for vid, v in result.solution.vehicles.items()
            },
            "assignment": result.solution.assignment,
        }
        Path(args.output).write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Result written to {args.output}")


if __name__ == "__main__":
    main()
