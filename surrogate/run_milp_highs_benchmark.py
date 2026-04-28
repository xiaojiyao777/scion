"""HiGHS benchmark for MILP solver — full extended + unit test validation.

Runs:
1. Extended instances (s03, s04, m01) with HiGHS, same time budgets as v2
2. v4_s01/s02/s03 phase1+phase2 with HiGHS (to cross-validate compare results)

Output: /home/clawd/research/scion-experiments/milp-highs-benchmark/
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, '/home/clawd/research/or-autoresearch-agent/surrogate')

from milp_solver import solve_exact, _load_instance
from oracle import check_feasibility, recompute_objective


OUT_DIR = Path("/home/clawd/research/scion-experiments/milp-highs-benchmark")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Instance → time_limit (seconds). Keep budgets consistent with v2 run.
EXTENDED = [
    ("s03",      "surrogate/data/instance_v4_scr_s03.json", 1200,
     "v4, 39 orders, 5 locked - HiGHS vs CBC baseline"),
    ("s04",      "surrogate/data/instance_scr_s04.json",     600,
     "v1, 25 orders, sanity"),
    ("m01",      "surrogate/data/instance_v3_scr_m01.json", 1800,
     "v3, 54 orders, 4 locked - scale challenge"),
]

# Unit-test-style small instances, same time limit as _milp_result (600s)
SMALL = [
    ("v4_s01", "surrogate/data/instance_v4_scr_s01.json", 600),
    ("v4_s02", "surrogate/data/instance_v4_scr_s02.json", 600),
    ("v4_s03", "surrogate/data/instance_v4_scr_s03.json", 600),
]


def load_baseline_champion(instance):
    """Run the surrogate solver for a short budget to get a baseline champion."""
    from config import Config
    from greedy_init import greedy_init
    from operators import (
        ChangeVehicleType, DestroyRebuild, MergeVehicles,
        MoveOrder, SplitVehicle, SwapOrders,
    )
    from vns import run_vns
    from random import Random

    cfg = Config()
    cfg.max_iterations = 50
    rng = Random(42)
    init_sol = greedy_init(instance, rng)
    init_sol.objective = recompute_objective(init_sol, instance)
    ops = [
        SwapOrders(instance, 1),
        MoveOrder(instance, 1),
        MergeVehicles(instance, 1),
        ChangeVehicleType(instance, 1),
        DestroyRebuild(instance, 1),
        SplitVehicle(instance, 1),
    ]
    weights = [3, 3, 2, 2, 2, 1]
    champion = run_vns(instance, [init_sol], ops, weights, cfg)
    champion.objective = recompute_objective(champion, instance)
    return champion


def run_one(short, path, time_limit, note=""):
    inst = _load_instance(path)
    n = len(inst.orders)
    n_active = len({o.vehicle_subcategory for o in inst.orders.values()})

    print(f"\n{'='*70}", flush=True)
    print(f"[{short}] n={n} n_active_subcats={n_active}  time_limit={time_limit}s", flush=True)
    print(f"  start: {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

    champion = load_baseline_champion(inst)
    champ_obj = recompute_objective(champion, inst)

    t0 = time.monotonic()
    r = solve_exact(
        inst,
        time_limit_seconds=time_limit,
        verbose=False,
        solver_name="HiGHS",
        warm_start=champion,
    )
    elapsed = time.monotonic() - t0

    rec = {
        "name": short,
        "instance_path": str(path),
        "solver": "HiGHS",
        "n_orders": n,
        "n_active_subcats": n_active,
        "time_limit_s": time_limit,
        "elapsed_s": round(elapsed, 1),
        "status": r.status,
        "solution_verified": r.solution_verified,
        "verification_issues_count": len(r.verification_issues) if r.verification_issues else 0,
        "verification_issues_sample": r.verification_issues[:3] if r.verification_issues else [],
        "objective_f1": r.objective_f1,
        "objective_f2": r.objective_f2,
        "phase1_time_s": round(r.phase1_time, 1),
        "phase2_time_s": round(r.phase2_time, 1),
        "phase1_gap": r.phase1_gap,
        "phase2_gap": r.phase2_gap,
        "lower_bound_f1": r.lower_bound_f1,
        "lower_bound_f2": r.lower_bound_f2,
        "warmstart_f1": champ_obj.subcategory_splits,
        "warmstart_f2": champ_obj.total_cost,
        "note": note,
    }

    if r.solution is not None:
        feas = check_feasibility(r.solution, inst, 1)
        rec["oracle_feasible"] = bool(feas.is_feasible)
        rec["oracle_violations"] = list(feas.violations)[:5]
        obj = recompute_objective(r.solution, inst)
        rec["oracle_f1"] = obj.subcategory_splits
        rec["oracle_f2"] = obj.total_cost
        rec["oracle_consistent"] = (
            obj.subcategory_splits == r.objective_f1
            and obj.total_cost == r.objective_f2
        )
        rec["n_orders_assigned"] = len(r.solution.assignment)
        rec["n_vehicles_used"] = len([v for v in r.solution.vehicles.values() if v.order_ids])
    else:
        rec["oracle_feasible"] = None
        rec["no_solution"] = True

    out = OUT_DIR / f"{short}.json"
    out.write_text(json.dumps(rec, indent=2))
    print(
        f"  DONE status={r.status} verified={r.solution_verified} "
        f"f1={r.objective_f1} f2={r.objective_f2} lb_f1={r.lower_bound_f1} "
        f"elapsed={elapsed:.1f}s (warmstart f1={champ_obj.subcategory_splits})",
        flush=True,
    )
    return rec


def main():
    print(f"\n{'#'*70}", flush=True)
    print(f"# HiGHS MILP Benchmark", flush=True)
    print(f"# Started: {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"# Output : {OUT_DIR}", flush=True)
    print(f"{'#'*70}", flush=True)

    all_results = []
    t_all = time.monotonic()

    for short, path, tl, *rest in EXTENDED:
        note = rest[0] if rest else ""
        try:
            all_results.append(run_one(short, path, tl, note))
        except Exception as e:
            err = {"name": short, "error": f"{type(e).__name__}: {e}"}
            print(f"  !! FAILED: {err['error']}", flush=True)
            all_results.append(err)

    for short, path, tl in SMALL:
        try:
            all_results.append(run_one(short, path, tl, "unit-test-style 600s budget"))
        except Exception as e:
            err = {"name": short, "error": f"{type(e).__name__}: {e}"}
            print(f"  !! FAILED: {err['error']}", flush=True)
            all_results.append(err)

    total = time.monotonic() - t_all

    summary = {
        "solver": "HiGHS (highspy 1.14.0)",
        "run_started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_elapsed_s": round(total, 1),
        "results": all_results,
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\n{'='*70}", flush=True)
    print(f"ALL DONE. total={total:.1f}s ({total/60:.1f} min)", flush=True)
    print(f"Summary: {OUT_DIR}/summary.json", flush=True)
    for r in all_results:
        if "error" in r:
            print(f"  [{r['name']:8}] ERROR: {r['error']}", flush=True)
        else:
            print(
                f"  [{r['name']:8}] {r['status']:12} verified={r['solution_verified']} "
                f"f1={r['objective_f1']} f2={r['objective_f2']} "
                f"elapsed={r['elapsed_s']}s",
                flush=True,
            )


if __name__ == "__main__":
    main()

