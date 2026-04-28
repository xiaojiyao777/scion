from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

import yaml

REPO = Path('/home/clawd/research/or-autoresearch-agent')
SURROGATE = REPO / 'surrogate'
sys.path.insert(0, str(SURROGATE))

from milp_solver import solve_exact, _load_instance  # type: ignore
from oracle import check_feasibility, recompute_objective  # type: ignore
from solver import solve as surrogate_solve, Config as SolverConfig  # type: ignore


def load_manifest_paths(manifest_path: str) -> list[tuple[str, str]]:
    path = Path(manifest_path)
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    items: list[tuple[str, str]] = []
    for split in ['canary', 'screening', 'validation', 'frozen']:
        for raw in data.get(split, []) or []:
            raw_s = str(raw)
            if raw_s.startswith('/'):
                resolved = raw_s
            else:
                if raw_s.startswith('data/'):
                    resolved = str((REPO / 'surrogate' / raw_s).resolve())
                else:
                    resolved = str((path.parent / raw_s).resolve())
            items.append((split, resolved))
    return items


def estimate_budget(n_orders: int, family: str) -> int:
    if family == 'synthetic':
        if n_orders <= 25:
            return 600
        if n_orders <= 45:
            return 1800
        if n_orders <= 70:
            return 3600
        if n_orders <= 100:
            return 1800
        return 1200
    # production is much harder because subcat count explodes
    if n_orders <= 35:
        return 1200
    if n_orders <= 60:
        return 1800
    if n_orders <= 90:
        return 1200
    return 900


def classify_scale(n_orders: int) -> str:
    if n_orders <= 40:
        return 'small'
    if n_orders <= 100:
        return 'medium'
    if n_orders <= 300:
        return 'large'
    return 'xlarge'


def warmstart_for_instance(inst):
    cfg = SolverConfig(max_iterations=200, random_seed=42)
    champion = surrogate_solve(inst, cfg=cfg)
    if champion.objective is None:
        champion.objective = recompute_objective(champion, inst)
    return champion


def run_one(split: str, path: str, family: str, out_dir: Path) -> dict[str, Any]:
    inst = _load_instance(path)
    n_orders = len(inst.orders)
    n_active = len({o.vehicle_subcategory for o in inst.orders.values()})
    locked = sum(1 for o in inst.orders.values() if o.locked_vehicle_id is not None)
    scale = classify_scale(n_orders)
    budget = estimate_budget(n_orders, family)
    instance_name = Path(path).name

    rec: dict[str, Any] = {
        'provider': 'milp',
        'family': family,
        'split': split,
        'instance_name': instance_name,
        'instance_path': path,
        'n_orders': n_orders,
        'n_active_subcats': n_active,
        'n_locked_orders': locked,
        'scale': scale,
        'time_limit_s': budget,
        'solver': 'HiGHS',
        'run_started': time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    t0 = time.monotonic()
    champion = warmstart_for_instance(inst)
    t_champ = time.monotonic() - t0
    champ_obj = champion.objective or recompute_objective(champion, inst)

    rec.update({
        'warm_start_strategy': 'surrogate_vns_200iters',
        'warm_start_time_s': round(t_champ, 2),
        'warm_start_f1': champ_obj.subcategory_splits,
        'warm_start_f2': champ_obj.total_cost,
    })

    t1 = time.monotonic()
    result = solve_exact(
        inst,
        time_limit_seconds=budget,
        verbose=False,
        solver_name='HiGHS',
        warm_start=champion,
    )
    elapsed = time.monotonic() - t1

    rec.update({
        'elapsed_s': round(elapsed, 2),
        'milp_status': result.status,
        'milp_verified': bool(result.solution_verified),
        'milp_f1': result.objective_f1,
        'milp_f2': result.objective_f2,
        'milp_lb_f1': result.lower_bound_f1,
        'milp_lb_f2': result.lower_bound_f2,
        'phase1_time_s': round(result.phase1_time, 2),
        'phase2_time_s': round(result.phase2_time, 2),
        'phase1_gap': result.phase1_gap,
        'phase2_gap': result.phase2_gap,
        'verification_issues': result.verification_issues or [],
        'milp_exact': bool(result.status == 'optimal' and result.phase1_gap == 0 and result.phase2_gap == 0),
    })

    if result.solution is not None:
        feas = check_feasibility(result.solution, inst, 1)
        obj = recompute_objective(result.solution, inst)
        rec.update({
            'oracle_feasible': bool(feas.is_feasible),
            'oracle_violations': list(feas.violations)[:5],
            'oracle_f1': obj.subcategory_splits,
            'oracle_f2': obj.total_cost,
            'oracle_consistent': bool(obj.subcategory_splits == result.objective_f1 and obj.total_cost == result.objective_f2),
            'n_orders_assigned': len(result.solution.assignment),
            'n_vehicles_used': len([v for v in result.solution.vehicles.values() if v.order_ids]),
        })
    else:
        rec.update({
            'oracle_feasible': None,
            'oracle_violations': [],
            'oracle_consistent': None,
            'no_solution': True,
        })

    if rec['milp_f1'] is not None and rec['warm_start_f1'] is not None:
        rec['champion_vs_milp_delta_f1'] = rec['warm_start_f1'] - rec['milp_f1']
    else:
        rec['champion_vs_milp_delta_f1'] = None
    if rec['milp_f2'] is not None and rec['warm_start_f2'] is not None:
        rec['champion_vs_milp_delta_f2'] = rec['warm_start_f2'] - rec['milp_f2']
    else:
        rec['champion_vs_milp_delta_f2'] = None

    if rec['milp_f1'] is not None and rec['milp_lb_f1'] not in (None, 0):
        rec['gap_f1_pct'] = round(max(rec['milp_f1'] - rec['milp_lb_f1'], 0) / rec['milp_lb_f1'] * 100, 4)
    else:
        rec['gap_f1_pct'] = None
    if rec['milp_f2'] is not None and rec['milp_lb_f2'] not in (None, 0):
        rec['gap_f2_pct'] = round(max(rec['milp_f2'] - rec['milp_lb_f2'], 0) / rec['milp_lb_f2'] * 100, 4)
    else:
        rec['gap_f2_pct'] = None

    out_path = out_dir / f"{instance_name.replace('.json','')}.json"
    out_path.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding='utf-8')
    print(
        f"[{family}:{split}] {instance_name} n={n_orders} status={rec['milp_status']} "
        f"exact={rec['milp_exact']} verified={rec['milp_verified']} "
        f"f1={rec['milp_f1']} f2={rec['milp_f2']} lb_f1={rec['milp_lb_f1']} elapsed={rec['elapsed_s']}s",
        flush=True,
    )
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', required=True)
    ap.add_argument('--family', required=True, choices=['synthetic', 'production'])
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_items = load_manifest_paths(args.manifest)

    # Deduplicate while preserving order
    seen = set()
    items: list[tuple[str, str]] = []
    for split, path in raw_items:
        if path in seen:
            continue
        seen.add(path)
        items.append((split, path))

    if args.limit > 0:
        items = items[: args.limit]

    summary: dict[str, Any] = {
        'provider': 'milp',
        'family': args.family,
        'manifest': args.manifest,
        'run_started': time.strftime('%Y-%m-%d %H:%M:%S'),
        'items_total': len(items),
        'results': [],
    }

    for idx, (split, path) in enumerate(items, start=1):
        print(f"\n===== [{idx}/{len(items)}] {split} :: {path} =====", flush=True)
        try:
            rec = run_one(split, path, args.family, out_dir)
        except Exception as e:
            rec = {
                'provider': 'milp',
                'family': args.family,
                'split': split,
                'instance_name': Path(path).name,
                'instance_path': path,
                'milp_status': 'error',
                'error': f'{type(e).__name__}: {e}',
            }
            err_path = out_dir / f"{Path(path).stem}.json"
            err_path.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding='utf-8')
            print(f"ERROR {Path(path).name}: {rec['error']}", flush=True)
        summary['results'].append(rec)
        (out_dir / 'summary.partial.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')

    summary['run_finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
    (out_dir / 'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\nDONE family={args.family} summary={out_dir / 'summary.json'}", flush=True)


if __name__ == '__main__':
    main()
