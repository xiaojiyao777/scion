from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from src.parser import find_instances, parse_sol

FIELDNAMES = [
    "instance",
    "subset",
    "path",
    "dimension",
    "bks",
    "bks_routes",
    "cost",
    "gap_pct",
    "routes",
    "route_gap",
    "iterations",
    "time",
    "time_limit",
    "seed",
    "feasible",
    "benchmark_feasible",
    "mode",
    "status",
    "error",
    "wall_time",
]


def _reference_for(path: str) -> tuple[float | None, int | None]:
    sol_path = Path(path).with_suffix(".sol")
    if not sol_path.exists():
        return None, None
    routes, cost = parse_sol(str(sol_path))
    return (cost if cost > 0 else None), len(routes)


def _dimension_for(path: str) -> int:
    with open(path) as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("DIMENSION") and ":" in stripped:
                return int(stripped.split(":", 1)[1])
            if stripped.endswith("SECTION"):
                break
    raise ValueError("DIMENSION not found")


def _done_paths(output: Path) -> set[str]:
    if not output.exists():
        return set()
    with open(output, newline="") as f:
        return {
            row["path"]
            for row in csv.DictReader(f)
            if row.get("path") and row.get("status") == "ok"
        }


def _ensure_writer(output: Path, resume: bool) -> tuple[object, csv.DictWriter]:
    output.parent.mkdir(parents=True, exist_ok=True)
    append = resume and output.exists() and output.stat().st_size > 0
    f = open(output, "a" if append else "w", newline="")
    writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
    if not append:
        writer.writeheader()
    return f, writer


def _time_limit_for(dimension: int, bks: float | None, args: argparse.Namespace) -> float:
    if dimension >= args.large_dimension:
        return args.large_time_limit
    if bks is not None:
        return args.bks_time_limit
    return args.time_limit


def _empty_row(path: str, args: argparse.Namespace) -> dict[str, object]:
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
        "route_gap": "",
        "iterations": "",
        "time": "",
        "time_limit": "",
        "seed": args.seed,
        "feasible": "",
        "benchmark_feasible": "",
        "mode": "",
        "status": "ok",
        "error": "",
        "wall_time": "",
    }
    return row


def _time_limit_for_path(path: str, args: argparse.Namespace) -> tuple[float, int | None, float | None, int | None]:
    dimension = _dimension_for(path)
    bks, bks_routes = _reference_for(path)
    time_limit = _time_limit_for(dimension, bks, args)
    return time_limit, dimension, bks, bks_routes


def _run_one_subprocess(path: str, args: argparse.Namespace) -> dict[str, object]:
    row = _empty_row(path, args)
    wall_start = time.perf_counter()
    try:
        time_limit, dimension, bks, bks_routes = _time_limit_for_path(path, args)
        row.update(
            {
                "dimension": dimension,
                "bks": "" if bks is None else bks,
                "bks_routes": "" if bks_routes is None else bks_routes,
                "time_limit": time_limit,
            }
        )
    except Exception as exc:
        row["status"] = "error"
        row["error"] = f"precheck {type(exc).__name__}: {exc}"
        row["wall_time"] = time.perf_counter() - wall_start
        return row

    cmd = [
        sys.executable,
        "solve_instance.py",
        path,
        "--seed",
        str(args.seed),
        "--time-limit",
        str(time_limit),
        "--vns-iterations",
        str(args.vns_iterations),
        "--cw-threshold",
        str(args.cw_threshold),
        "--vns-threshold",
        str(args.vns_threshold),
        "--alns-threshold",
        str(args.alns_threshold),
        "--max-destroy-customers",
        str(args.max_destroy_customers),
        "--memory-mb",
        str(args.memory_mb),
    ]
    if args.no_vns:
        cmd.append("--no-vns")
    if args.tracebacks:
        cmd.append("--tracebacks")

    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["MKL_NUM_THREADS"] = "1"
    env["NUMEXPR_NUM_THREADS"] = "1"

    timeout = max(args.instance_timeout, time_limit + args.timeout_slack)
    try:
        completed = subprocess.run(
            cmd,
            cwd=Path(__file__).parent,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        row["status"] = "timeout"
        row["error"] = f"timeout after {timeout:.1f}s"
        row["wall_time"] = time.perf_counter() - wall_start
        return row

    row["wall_time"] = time.perf_counter() - wall_start
    if completed.returncode != 0:
        row["status"] = "error"
        row["error"] = (completed.stderr or completed.stdout).strip()[:2000]
        return row

    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except Exception as exc:
        row["status"] = "error"
        row["error"] = f"bad child json: {type(exc).__name__}: {exc}; stderr={completed.stderr[:1000]}"
        return row

    row.update(payload)
    return row


def run(args: argparse.Namespace) -> None:
    paths = find_instances(args.data_dir, subsets=args.subsets, euc_2d_only=True)
    output = Path(args.output)
    completed = _done_paths(output) if args.resume else set()
    remaining = [path for path in paths if path not in completed]

    start_all = time.perf_counter()
    f, writer = _ensure_writer(output, args.resume)
    try:
        print(
            f"total={len(paths)} completed={len(completed)} remaining={len(remaining)} "
            f"workers={args.workers} output={output}",
            flush=True,
        )

        done_count = 0
        if args.workers <= 1:
            for path in remaining:
                row = _run_one_subprocess(path, args)
                done_count += 1
                writer.writerow(row)
                f.flush()
                if done_count % args.progress_every == 0 or row["status"] != "ok":
                    elapsed = time.perf_counter() - start_all
                    print(
                        f"progress={done_count}/{len(remaining)} elapsed={elapsed:.1f}s "
                        f"last={row['instance']} status={row['status']} mode={row['mode']} "
                        f"cost={row['cost']} gap={row['gap_pct']}",
                        flush=True,
                    )
            return

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            path_iter = iter(remaining)
            futures = {}
            for _ in range(args.workers):
                try:
                    path = next(path_iter)
                except StopIteration:
                    break
                futures[executor.submit(_run_one_subprocess, path, args)] = path

            while futures:
                for future in as_completed(list(futures)):
                    futures.pop(future)
                    break
                row = future.result()
                done_count += 1
                writer.writerow(row)
                f.flush()
                if done_count % args.progress_every == 0 or row["status"] != "ok":
                    elapsed = time.perf_counter() - start_all
                    print(
                        f"progress={done_count}/{len(remaining)} elapsed={elapsed:.1f}s "
                        f"last={row['instance']} status={row['status']} mode={row['mode']} "
                        f"cost={row['cost']} gap={row['gap_pct']}",
                        flush=True,
                    )
                try:
                    path = next(path_iter)
                except StopIteration:
                    continue
                futures[executor.submit(_run_one_subprocess, path, args)] = path
    finally:
        f.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a resumable full CVRPLIB experiment")
    parser.add_argument("data_dir", nargs="?", default="cvrplib")
    parser.add_argument("--subsets", nargs="*", default=None)
    parser.add_argument("--output", default="results/full_experiment.csv")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--time-limit", type=float, default=0.05, help="Default per-instance time limit")
    parser.add_argument("--bks-time-limit", type=float, default=0.5, help="Time limit when a .sol/BKS exists")
    parser.add_argument("--large-time-limit", type=float, default=0.0, help="Time limit for large instances")
    parser.add_argument("--large-dimension", type=int, default=2001)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--no-vns", action="store_true")
    parser.add_argument("--vns-iterations", type=int, default=300)
    parser.add_argument("--cw-threshold", type=int, default=1500)
    parser.add_argument("--vns-threshold", type=int, default=1200)
    parser.add_argument("--alns-threshold", type=int, default=2000)
    parser.add_argument("--max-destroy-customers", type=int, default=120)
    parser.add_argument("--progress-every", type=int, default=100)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--instance-timeout", type=float, default=30.0)
    parser.add_argument("--timeout-slack", type=float, default=5.0)
    parser.add_argument("--memory-mb", type=int, default=2048)
    parser.add_argument("--tracebacks", action="store_true")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
