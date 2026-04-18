#!/usr/bin/env python3
"""
MILP 大规模实例测试 — 独立运行脚本

测试实例:
  - s03       : instance_v4_scr_s03  (39 orders, 5 locked) — 必测
  - s04       : instance_scr_s04     (25 orders, 0 locked) — v1 schema sanity
  - m01       : instance_v3_scr_m01  (54 orders, 4 locked) — 规模挑战，超时也接受

时间预算:
  - s03: time_limit = 1200s (20 min)
  - s04: time_limit =  600s (10 min)
  - m01: time_limit = 1800s (30 min) — 预期可能超时

输出:
  - /tmp/milp-extended/<name>.json  : 求解结果 + solution
  - /tmp/milp-extended/summary.json : 汇总
  - 终端实时打印进度
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

# path setup — run from repo root
sys.path.insert(0, 'surrogate')

from milp_solver import solve_exact, MILPResult, _load_instance
from oracle import check_feasibility, recompute_objective


OUT_DIR = Path("/tmp/milp-extended")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TESTS = [
    # (short_name, instance_file, time_limit_seconds, note)
    ("s03",  "surrogate/data/instance_v4_scr_s03.json", 1200,
     "v4, 39 orders, 5 locked — 必测"),
    ("s04",  "surrogate/data/instance_scr_s04.json",     600,
     "v1, 25 orders, 0 locked — sanity"),
    ("m01",  "surrogate/data/instance_v3_scr_m01.json", 1800,
     "v3, 54 orders, 4 locked — 规模挑战，可能超时"),
]


def run_one(short: str, path: str, time_limit: int, note: str) -> dict:
    inst = _load_instance(path)
    n = len(inst.orders)
    print(f"\n{'='*70}", flush=True)
    print(f"[{short}] {path}", flush=True)
    print(f"  n={n}, note={note}", flush=True)
    print(f"  time_limit={time_limit}s", flush=True)
    print(f"  start: {time.strftime('%H:%M:%S')}", flush=True)

    t0 = time.monotonic()
    result = solve_exact(inst, time_limit_seconds=time_limit, verbose=True)
    elapsed = time.monotonic() - t0

    rec = {
        "name": short,
        "instance_path": path,
        "n_orders": n,
        "time_limit_s": time_limit,
        "elapsed_s": round(elapsed, 1),
        "status": result.status,
        "objective_f1": result.objective_f1,
        "objective_f2": result.objective_f2,
        "phase1_time_s": round(result.phase1_time, 1),
        "phase2_time_s": round(result.phase2_time, 1),
        "phase1_gap": result.phase1_gap,
        "phase2_gap": result.phase2_gap,
        "lower_bound_f1": result.lower_bound_f1,
        "lower_bound_f2": result.lower_bound_f2,
        "note": note,
    }

    # Oracle 独立验证
    if result.solution is not None:
        try:
            feas = check_feasibility(result.solution, inst, 1)
            rec["oracle_feasible"] = bool(feas.is_feasible)
            rec["oracle_violations"] = list(feas.violations)
            obj = recompute_objective(result.solution, inst)
            rec["oracle_f1"] = obj.subcategory_splits
            rec["oracle_f2"] = obj.total_cost
            rec["oracle_consistent"] = (
                obj.subcategory_splits == result.objective_f1
                and obj.total_cost == result.objective_f2
            )
        except Exception as e:
            rec["oracle_check_error"] = f"{type(e).__name__}: {e}"

    # 保存单实例结果
    out = OUT_DIR / f"{short}.json"
    with open(out, "w") as f:
        json.dump(rec, f, indent=2)
    print(f"\n  => status={rec['status']} elapsed={rec['elapsed_s']}s "
          f"f1={rec['objective_f1']} f2={rec['objective_f2']}", flush=True)
    print(f"     saved: {out}", flush=True)
    return rec


def main():
    print(f"MILP Extended Test Run", flush=True)
    print(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"Output dir: {OUT_DIR}", flush=True)

    all_results = []
    t_overall = time.monotonic()

    for short, path, tl, note in TESTS:
        try:
            rec = run_one(short, path, tl, note)
            all_results.append(rec)
        except Exception as e:
            err = {
                "name": short,
                "instance_path": path,
                "error": f"{type(e).__name__}: {e}",
            }
            print(f"\n  !! FAILED: {err['error']}", flush=True)
            all_results.append(err)

    # Summary
    overall_elapsed = time.monotonic() - t_overall
    summary = {
        "run_started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_elapsed_s": round(overall_elapsed, 1),
        "results": all_results,
    }
    summary_path = OUT_DIR / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'='*70}", flush=True)
    print(f"ALL DONE. total_elapsed={round(overall_elapsed, 1)}s", flush=True)
    print(f"Summary: {summary_path}", flush=True)
    for r in all_results:
        if "error" in r:
            print(f"  [{r['name']:4}] ERROR: {r['error']}", flush=True)
        else:
            print(f"  [{r['name']:4}] {r['status']:10} "
                  f"f1={r.get('objective_f1')} f2={r.get('objective_f2')} "
                  f"elapsed={r['elapsed_s']}s", flush=True)


if __name__ == "__main__":
    main()
