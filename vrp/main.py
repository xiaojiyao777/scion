from __future__ import annotations

import argparse
from pathlib import Path

from src.parser import parse_sol, parse_vrp
from src.solver import solve
from src.visualization import plot_convergence, plot_routes


def _try_bks(instance_path: Path) -> float | None:
    sol_path = instance_path.with_suffix(".sol")
    if not sol_path.exists():
        return None
    _, cost = parse_sol(str(sol_path))
    return cost if cost > 0 else None


def _print_solution(result, bks: float | None) -> None:
    gap = ""
    if bks:
        gap = f" gap={(result.best_cost - bks) / bks * 100:.2f}%"
    print(
        f"cost={result.best_cost:.3f}{gap} "
        f"routes={len(result.solution.routes)} "
        f"iterations={result.iterations} "
        f"time={result.elapsed:.2f}s"
    )
    for idx, route in enumerate(result.solution.routes, start=1):
        customers = " ".join(str(c) for c in route.customers)
        print(f"Route #{idx}: {customers}")


def main() -> None:
    parser = argparse.ArgumentParser(description="CVRP solver using ALNS + VNS")
    parser.add_argument("path", help=".vrp instance file, or data directory with --batch")
    parser.add_argument("-t", "--time-limit", type=float, default=60.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--batch", action="store_true", help="Run all matching instances under a directory")
    parser.add_argument("--subsets", nargs="*", default=None, help="Subset directories for batch mode, e.g. A B")
    parser.add_argument("--output", default="results.csv", help="CSV output path in batch mode")
    parser.add_argument("--output-dir", default="outputs", help="Directory for plots")
    parser.add_argument("--plot", action="store_true", help="Save route plot for single-instance mode")
    parser.add_argument("--convergence", action="store_true", help="Save convergence plot for single-instance mode")
    parser.add_argument("--no-vns", action="store_true", help="Disable VNS local search")
    parser.add_argument("--vns-iterations", type=int, default=5000)
    parser.add_argument("--cw-threshold", type=int, default=1500)
    parser.add_argument("--vns-threshold", type=int, default=1200)
    parser.add_argument("--alns-threshold", type=int, default=2000)
    parser.add_argument("--max-destroy-customers", type=int, default=200)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.batch:
        from benchmark import run_benchmark

        run_benchmark(
            data_dir=args.path,
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
        return

    instance_path = Path(args.path)
    instance = parse_vrp(str(instance_path))
    bks = _try_bks(instance_path)
    result = solve(
        instance,
        time_limit=args.time_limit,
        seed=args.seed,
        use_vns=not args.no_vns,
        vns_max_no_improve=args.vns_iterations,
        cw_threshold=args.cw_threshold,
        vns_threshold=args.vns_threshold,
        alns_threshold=args.alns_threshold,
        max_destroy_customers=args.max_destroy_customers,
        verbose=args.verbose,
    )
    _print_solution(result, bks)

    output_dir = Path(args.output_dir)
    if args.plot:
        plot_routes(result.solution, str(output_dir / f"{instance.name}_routes.png"), show=False)
    if args.convergence:
        plot_convergence(result.history, bks, str(output_dir / f"{instance.name}_convergence.png"), show=False)


if __name__ == "__main__":
    main()
