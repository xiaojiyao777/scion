from __future__ import annotations

import argparse
import csv
from pathlib import Path

from src.parser import find_instances, parse_sol, parse_vrp
from src.solver import solve


def _reference_for(instance_path: str) -> tuple[float | None, int | None]:
    sol_path = Path(instance_path).with_suffix(".sol")
    if not sol_path.exists():
        return None, None
    routes, cost = parse_sol(str(sol_path))
    return (cost if cost > 0 else None), len(routes)


def run_benchmark(
    data_dir: str,
    subsets: list[str] | None = None,
    time_limit: float = 30.0,
    seed: int = 0,
    output_csv: str = "results.csv",
    use_vns: bool = True,
    vns_iterations: int = 5000,
    cw_threshold: int = 1500,
    vns_threshold: int = 1200,
    alns_threshold: int = 2000,
    max_destroy_customers: int = 200,
    verbose: bool = False,
) -> list[dict[str, float | int | str | None]]:
    paths = find_instances(data_dir, subsets=subsets, euc_2d_only=True)
    rows: list[dict[str, float | int | str | None]] = []

    for idx, path in enumerate(paths, start=1):
        instance = parse_vrp(path)
        bks, bks_routes = _reference_for(path)
        result = solve(
            instance,
            time_limit=time_limit,
            seed=seed,
            use_vns=use_vns,
            vns_max_no_improve=vns_iterations,
            cw_threshold=cw_threshold,
            vns_threshold=vns_threshold,
            alns_threshold=alns_threshold,
            max_destroy_customers=max_destroy_customers,
            verbose=verbose,
        )
        gap = None if not bks else (result.best_cost - bks) / bks * 100.0
        row: dict[str, float | int | str | None] = {
            "instance": instance.name,
            "subset": Path(path).parent.name,
            "path": path,
            "dimension": instance.dimension,
            "bks": bks,
            "bks_routes": bks_routes,
            "cost": result.best_cost,
            "gap_pct": gap,
            "routes": len(result.solution.routes),
            "iterations": result.iterations,
            "time": result.elapsed,
            "time_limit": time_limit,
            "seed": seed,
            "feasible": result.solution.is_feasible(),
        }
        rows.append(row)
        if verbose:
            gap_text = "" if gap is None else f" gap={gap:.2f}%"
            print(f"[{idx}/{len(paths)}] {instance.name} cost={result.best_cost:.3f}{gap_text}")

    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "instance",
                "subset",
                "path",
                "dimension",
                "bks",
                "bks_routes",
                "cost",
                "gap_pct",
                "routes",
                "iterations",
                "time",
                "time_limit",
                "seed",
                "feasible",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CVRP benchmark")
    parser.add_argument("data_dir")
    parser.add_argument("--subsets", nargs="*", default=None)
    parser.add_argument("-t", "--time-limit", type=float, default=30.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", default="results.csv")
    parser.add_argument("--no-vns", action="store_true")
    parser.add_argument("--vns-iterations", type=int, default=5000)
    parser.add_argument("--cw-threshold", type=int, default=1500)
    parser.add_argument("--vns-threshold", type=int, default=1200)
    parser.add_argument("--alns-threshold", type=int, default=2000)
    parser.add_argument("--max-destroy-customers", type=int, default=200)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    run_benchmark(
        data_dir=args.data_dir,
        subsets=args.subsets,
        time_limit=args.time_limit,
        seed=args.seed,
        output_csv=args.output,
        use_vns=not args.no_vns,
        vns_iterations=args.vns_iterations,
        cw_threshold=args.cw_threshold,
        vns_threshold=args.vns_threshold,
        alns_threshold=args.alns_threshold,
        max_destroy_customers=args.max_destroy_customers,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
