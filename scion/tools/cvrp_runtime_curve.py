#!/usr/bin/env python3
"""Run no-LLM CVRP solver runtime-budget curves for selected cases."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_EXPERIMENTS_ROOT = Path("/home/clawd/research/scion-experiments")
DEFAULT_DATA_ROOT = Path("/home/clawd/research/or-autoresearch-agent/vrp")


@dataclass(frozen=True)
class CaseBudget:
    case: str
    base_time_limit_sec: int


@dataclass(frozen=True)
class RuntimeCurveJob:
    case: str
    seed: int
    multiplier: float
    time_limit_sec: int
    output_path: Path


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(args.repo_root).expanduser().resolve(strict=False)
    workspace = Path(args.workspace).expanduser().resolve(strict=False)
    data_root = Path(args.data_root).expanduser().resolve(strict=False)
    output_dir = _resolve_output_dir(args.output_dir)
    case_budgets = [parse_case_budget(value) for value in args.case_budget]
    multipliers = [_positive_float(value, "--multiplier") for value in args.multiplier]
    seeds = [_positive_int(value, "--seed") for value in args.seed]
    jobs = build_jobs(
        case_budgets=case_budgets,
        seeds=seeds,
        multipliers=multipliers,
        output_dir=output_dir,
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {
        "schema_version": "cvrp_runtime_curve.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "workspace": str(workspace),
        "data_root": str(data_root),
        "python": str(Path(args.python).expanduser()),
        "selected_surface": _clean_str(args.selected_surface),
        "parallelism": int(args.parallelism),
        "dry_run": bool(args.dry_run),
        "jobs": [],
    }
    if args.dry_run or int(args.parallelism) <= 1:
        for job in jobs:
            row = (
                summarize_planned_job(job, data_root=data_root)
                if args.dry_run
                else run_job(
                    job,
                    repo_root=repo_root,
                    workspace=workspace,
                    data_root=data_root,
                    python=args.python,
                    selected_surface=args.selected_surface,
                    timeout_padding_sec=args.timeout_padding_sec,
                    resume=args.resume,
                )
            )
            payload["jobs"].append(row)
            print(json.dumps(row, sort_keys=True), flush=True)
    else:
        payload["jobs"] = [None] * len(jobs)
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=int(args.parallelism)
        ) as executor:
            futures = {
                executor.submit(
                    run_job,
                    job,
                    repo_root=repo_root,
                    workspace=workspace,
                    data_root=data_root,
                    python=args.python,
                    selected_surface=args.selected_surface,
                    timeout_padding_sec=args.timeout_padding_sec,
                    resume=args.resume,
                ): index
                for index, job in enumerate(jobs)
            }
            for future in concurrent.futures.as_completed(futures):
                index = futures[future]
                try:
                    row = future.result()
                except Exception as exc:  # pragma: no cover - defensive guard.
                    job = jobs[index]
                    row = {
                        "case": job.case,
                        "seed": job.seed,
                        "multiplier": job.multiplier,
                        "time_limit_sec": job.time_limit_sec,
                        "output_path": str(job.output_path),
                        "status": "runner_error",
                        "error": str(exc),
                    }
                payload["jobs"][index] = row
                print(json.dumps(row, sort_keys=True), flush=True)
    payload["jobs"] = [row for row in payload["jobs"] if isinstance(row, dict)]

    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_summary_csv(output_dir / "summary.csv", payload["jobs"])
    print(f"wrote {summary_path}")
    return 0


def parse_case_budget(value: str) -> CaseBudget:
    raw = str(value or "").strip()
    if "=" not in raw:
        raise argparse.ArgumentTypeError(
            "--case-budget must have the form CASE=SECONDS"
        )
    case, limit = raw.rsplit("=", 1)
    case = case.strip()
    if not case:
        raise argparse.ArgumentTypeError("--case-budget case path is empty")
    return CaseBudget(case=case, base_time_limit_sec=_positive_int(limit, "CASE=SECONDS"))


def build_jobs(
    *,
    case_budgets: list[CaseBudget],
    seeds: list[int],
    multipliers: list[float],
    output_dir: Path,
) -> list[RuntimeCurveJob]:
    jobs: list[RuntimeCurveJob] = []
    for case_budget in case_budgets:
        for seed in seeds:
            for multiplier in multipliers:
                time_limit = max(
                    1,
                    int(round(case_budget.base_time_limit_sec * multiplier)),
                )
                jobs.append(
                    RuntimeCurveJob(
                        case=case_budget.case,
                        seed=seed,
                        multiplier=multiplier,
                        time_limit_sec=time_limit,
                        output_path=output_dir / _job_filename(
                            case_budget.case,
                            seed=seed,
                            multiplier=multiplier,
                            time_limit_sec=time_limit,
                        ),
                    )
                )
    return jobs


def summarize_planned_job(job: RuntimeCurveJob, *, data_root: Path) -> dict[str, Any]:
    return {
        "case": job.case,
        "seed": job.seed,
        "multiplier": job.multiplier,
        "time_limit_sec": job.time_limit_sec,
        "output_path": str(job.output_path),
        "status": "planned",
        "bks": _bks_for_case(job.case, data_root=data_root),
    }


def run_job(
    job: RuntimeCurveJob,
    *,
    repo_root: Path,
    workspace: Path,
    data_root: Path,
    python: str,
    selected_surface: str | None,
    timeout_padding_sec: int,
    resume: bool,
) -> dict[str, Any]:
    if resume and job.output_path.exists():
        row = summarize_solver_output(job, data_root=data_root)
        row["status"] = "resumed"
        return row

    env = os.environ.copy()
    package_root = repo_root / "scion"
    env["PYTHONPATH"] = _prepend_path(str(package_root), env.get("PYTHONPATH", ""))
    env["SCION_PROBLEM_DATA_ROOT"] = str(data_root)
    surface = _clean_str(selected_surface)
    if surface:
        env["SCION_SELECTED_SURFACE"] = surface
    else:
        env.pop("SCION_SELECTED_SURFACE", None)

    cmd = [
        str(Path(python).expanduser()),
        "-m",
        "scion.problems.cvrp.solver",
        job.case,
        "--seed",
        str(job.seed),
        "--time-limit",
        str(job.time_limit_sec),
        "--output",
        str(job.output_path),
    ]
    started = time.perf_counter()
    row: dict[str, Any] = {
        "case": job.case,
        "seed": job.seed,
        "multiplier": job.multiplier,
        "time_limit_sec": job.time_limit_sec,
        "output_path": str(job.output_path),
        "command": cmd,
    }
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(workspace),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=max(1, int(job.time_limit_sec) + int(timeout_padding_sec)),
        )
    except subprocess.TimeoutExpired as exc:
        row.update(
            {
                "status": "timeout_expired",
                "timeout_after_sec": int(job.time_limit_sec) + int(timeout_padding_sec),
                "wall_elapsed_sec": time.perf_counter() - started,
                "stdout_tail": _tail_text(exc.stdout),
                "stderr_tail": _tail_text(exc.stderr),
            }
        )
        return row

    row.update(
        {
            "returncode": completed.returncode,
            "wall_elapsed_sec": time.perf_counter() - started,
            "stdout_tail": _tail_text(completed.stdout),
            "stderr_tail": _tail_text(completed.stderr),
        }
    )
    if completed.returncode != 0 or not job.output_path.exists():
        row["status"] = "failed"
        return row
    row.update(summarize_solver_output(job, data_root=data_root))
    row["status"] = "completed"
    return row


def summarize_solver_output(
    job: RuntimeCurveJob,
    *,
    data_root: Path,
) -> dict[str, Any]:
    raw = json.loads(job.output_path.read_text(encoding="utf-8"))
    objective = raw.get("objective") if isinstance(raw, dict) else {}
    runtime = raw.get("runtime") if isinstance(raw, dict) else {}
    if not isinstance(objective, dict):
        objective = {}
    if not isinstance(runtime, dict):
        runtime = {}
    total_distance = _float_or_none(
        runtime.get("solver_algorithm_total_distance")
        or objective.get("total_distance")
    )
    best_update_summary = runtime.get("solver_algorithm_best_update_summary")
    if not isinstance(best_update_summary, dict):
        best_update_summary = None
    bks = _bks_for_case(job.case, data_root=data_root)
    return {
        "case": job.case,
        "seed": job.seed,
        "multiplier": job.multiplier,
        "time_limit_sec": job.time_limit_sec,
        "output_path": str(job.output_path),
        "objective": objective,
        "runtime_elapsed_sec": runtime.get("elapsed_s"),
        "solver_algorithm_elapsed_ms": runtime.get("solver_algorithm_elapsed_ms"),
        "solver_algorithm_stop_reason": runtime.get("solver_algorithm_stop_reason"),
        "solver_algorithm_runtime_budget_hit": runtime.get(
            "solver_algorithm_runtime_budget_hit"
        ),
        "solver_algorithm_total_distance": total_distance,
        "solver_algorithm_solution_routes": runtime.get(
            "solver_algorithm_solution_routes"
        ),
        "solver_algorithm_search_iterations": runtime.get(
            "solver_algorithm_search_iterations"
        ),
        "solver_algorithm_best_delta": runtime.get("solver_algorithm_best_delta"),
        "solver_algorithm_best_update_count": (
            best_update_summary.get("best_update_count")
            if best_update_summary
            else runtime.get("solver_algorithm_best_update_count")
        ),
        "solver_algorithm_best_update_summary": best_update_summary,
        "solver_algorithm_best_update_trace": runtime.get(
            "solver_algorithm_best_update_trace"
        ),
        "bks": bks,
        "bks_gap_pct": _gap_pct(total_distance, bks),
    }


def write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "status",
        "case",
        "seed",
        "multiplier",
        "time_limit_sec",
        "wall_elapsed_sec",
        "runtime_elapsed_sec",
        "solver_algorithm_elapsed_ms",
        "solver_algorithm_stop_reason",
        "solver_algorithm_runtime_budget_hit",
        "solver_algorithm_total_distance",
        "bks",
        "bks_gap_pct",
        "solver_algorithm_solution_routes",
        "solver_algorithm_search_iterations",
        "solver_algorithm_best_delta",
        "solver_algorithm_best_update_count",
        "output_path",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})


def _job_filename(
    case: str,
    *,
    seed: int,
    multiplier: float,
    time_limit_sec: int,
) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(case).stem).strip(".-_")
    mult = ("%g" % multiplier).replace(".", "p")
    return f"{stem}_seed{seed}_m{mult}_tl{time_limit_sec}.json"


def _resolve_output_dir(value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve(strict=False)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_EXPERIMENTS_ROOT / f"cvrp-runtime-curve-{stamp}"


def _bks_for_case(case: str, *, data_root: Path) -> float | None:
    sol_path = data_root / Path(case).with_suffix(".sol")
    if not sol_path.exists():
        return None
    match = re.search(
        r"^\s*Cost\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*$",
        sol_path.read_text(encoding="utf-8", errors="replace"),
        re.IGNORECASE | re.MULTILINE,
    )
    if not match:
        return None
    return float(match.group(1))


def _gap_pct(distance: float | None, bks: float | None) -> float | None:
    if distance is None or bks is None or bks <= 0:
        return None
    return 100.0 * (float(distance) - float(bks)) / float(bks)


def _prepend_path(value: str, existing: str) -> str:
    if not existing:
        return value
    return value + os.pathsep + existing


def _positive_int(value: object, label: str) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"{label} must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError(f"{label} must be positive")
    return parsed


def _positive_float(value: object, label: str) -> float:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"{label} must be a number") from exc
    if parsed <= 0.0:
        raise argparse.ArgumentTypeError(f"{label} must be positive")
    return parsed


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _tail_text(value: Any, limit: int = 2000) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    text = str(value)
    return text[-limit:]


def _clean_str(value: object) -> str:
    return str(value or "").strip()


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True)
    return value


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, help="CVRP solver workspace")
    parser.add_argument(
        "--case-budget",
        action="append",
        required=True,
        help="Case path plus current nominal protocol budget, e.g. cvrplib/X/X-n573-k30.vrp=120",
    )
    parser.add_argument(
        "--seed",
        action="append",
        required=True,
        help="Seed to replay. Repeat for multiple seeds.",
    )
    parser.add_argument(
        "--multiplier",
        action="append",
        default=[],
        help="Budget multiplier. Repeat; defaults to 1,2,4.",
    )
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--selected-surface", default=None)
    parser.add_argument(
        "--parallelism",
        type=int,
        default=1,
        help="Number of solver subprocesses to run concurrently.",
    )
    parser.add_argument(
        "--timeout-padding-sec",
        type=int,
        default=300,
        help="Extra wall-clock padding above each nominal solver time limit.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse an existing output JSON if the job output already exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write the planned job matrix without running solvers.",
    )
    args = parser.parse_args(argv)
    if not args.multiplier:
        args.multiplier = ["1", "2", "4"]
    if args.timeout_padding_sec < 0:
        raise SystemExit("--timeout-padding-sec must be non-negative")
    if args.parallelism <= 0:
        raise SystemExit("--parallelism must be positive")
    return args


if __name__ == "__main__":
    raise SystemExit(main())
