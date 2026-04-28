from __future__ import annotations

import argparse
import json
import os
import resource
import time
import traceback
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")


def _set_memory_limit(memory_mb: int) -> None:
    if memory_mb <= 0:
        return
    limit = memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def _reference_for(path: str) -> tuple[float | None, int | None]:
    from src.parser import parse_sol

    sol_path = Path(path).with_suffix(".sol")
    if not sol_path.exists():
        return None, None
    routes, cost = parse_sol(str(sol_path))
    return (cost if cost > 0 else None), len(routes)


def solve_one(args: argparse.Namespace) -> dict[str, object]:
    from src.parser import parse_vrp
    from src.solver import solve

    path = args.path
    row: dict[str, object] = {
        "instance": Path(path).stem,
        "subset": Path(path).parent.name,
        "path": path,
        "dimension": "",
        "bks": "",
        "bks_routes": "",
        "cost": "",
        "gap_pct": "",
        "routes": "",
        "iterations": "",
        "time": "",
        "time_limit": "",
        "seed": args.seed,
        "feasible": "",
        "mode": "",
        "status": "ok",
        "error": "",
    }

    try:
        instance = parse_vrp(path)
        bks, bks_routes = _reference_for(path)
        time_limit = args.time_limit
        result = solve(
            instance,
            time_limit=time_limit,
            seed=args.seed,
            use_vns=not args.no_vns,
            vns_max_no_improve=args.vns_iterations,
            cw_threshold=args.cw_threshold,
            vns_threshold=args.vns_threshold,
            alns_threshold=args.alns_threshold,
            max_destroy_customers=args.max_destroy_customers,
        )
        gap = None if not bks else (result.best_cost - bks) / bks * 100.0
        route_gap = "" if bks_routes is None else len(result.solution.routes) - bks_routes
        benchmark_feasible = (
            result.solution.is_feasible()
            and (bks_routes is None or len(result.solution.routes) <= bks_routes)
        )
        construction = "sweep" if instance.num_customers > args.cw_threshold else "clarke_wright"
        if result.iterations == 0:
            mode = f"{construction}_construction_only"
        else:
            mode = f"{construction}_{'alns' if args.no_vns else 'alns_vns'}"
        row.update(
            {
                "instance": instance.name,
                "dimension": instance.dimension,
                "bks": "" if bks is None else bks,
                "bks_routes": "" if bks_routes is None else bks_routes,
                "cost": result.best_cost,
                "gap_pct": "" if gap is None else gap,
                "routes": len(result.solution.routes),
                "route_gap": route_gap,
                "iterations": result.iterations,
                "time": result.elapsed,
                "time_limit": time_limit,
                "feasible": result.solution.is_feasible(),
                "benchmark_feasible": benchmark_feasible,
                "mode": mode,
            }
        )
    except Exception as exc:
        row["status"] = "error"
        row["error"] = f"{type(exc).__name__}: {exc}"
        if args.tracebacks:
            row["error"] = traceback.format_exc(limit=5)
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Solve one CVRP instance and emit one JSON row")
    parser.add_argument("path")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--time-limit", type=float, required=True)
    parser.add_argument("--no-vns", action="store_true")
    parser.add_argument("--vns-iterations", type=int, default=300)
    parser.add_argument("--cw-threshold", type=int, default=1500)
    parser.add_argument("--vns-threshold", type=int, default=1200)
    parser.add_argument("--alns-threshold", type=int, default=2000)
    parser.add_argument("--max-destroy-customers", type=int, default=120)
    parser.add_argument("--memory-mb", type=int, default=2048)
    parser.add_argument("--tracebacks", action="store_true")
    args = parser.parse_args()

    start = time.perf_counter()
    _set_memory_limit(args.memory_mb)
    row = solve_one(args)
    row["wall_time"] = time.perf_counter() - start
    print(json.dumps(row, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
