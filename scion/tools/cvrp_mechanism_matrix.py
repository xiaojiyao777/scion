#!/usr/bin/env python3
"""Run or plan a no-LLM CVRP family/slice/mechanism diagnostic matrix."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

_TOOL_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOL_PACKAGE_ROOT = _TOOL_REPO_ROOT / "scion"
if str(_TOOL_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_TOOL_PACKAGE_ROOT))

from scion.problems.cvrp.evidence.mechanism_matrix import (
    RESULTS_SCHEMA,
    CvrpMatrixJob,
    CvrpMechanismSpec,
    build_cvrp_mechanism_matrix_manifest,
    build_jobs,
    default_cvrp_mechanisms,
    load_case_entries,
    planned_result_for_job,
    summarize_solver_output_for_job,
)


DEFAULT_EXPERIMENTS_ROOT = Path("/home/clawd/research/scion-experiments")
DEFAULT_REPO_ROOT = _TOOL_REPO_ROOT
DEFAULT_CASE_MANIFEST = (
    DEFAULT_REPO_ROOT
    / "scion"
    / "scion"
    / "problems"
    / "cvrp"
    / "formal"
    / "manifests"
    / "screening.json"
)
DEFAULT_WORKSPACE = (
    DEFAULT_REPO_ROOT / "scion" / "scion" / "problems" / "cvrp"
)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(args.repo_root).expanduser().resolve(strict=False)
    workspace = Path(args.workspace).expanduser().resolve(strict=False)
    data_root = Path(args.data_root).expanduser().resolve(strict=False)
    output_dir = _resolve_output_dir(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    mechanisms = _selected_mechanisms(args.mechanism)
    cases = load_case_entries(
        args.case_manifest,
        case_limit=args.case_limit,
        family_filter=tuple(args.family),
        slice_filter=tuple(args.slice),
    )
    seeds = _resolve_seeds(args.seed)
    time_budget_sec = _positive_int(args.time_budget_sec, "--time-budget-sec")
    jobs = build_jobs(
        cases=cases,
        mechanisms=mechanisms,
        seeds=seeds,
        time_budget_sec=time_budget_sec,
        output_dir=output_dir,
    )

    manifest = build_cvrp_mechanism_matrix_manifest(
        cases=cases,
        mechanisms=mechanisms,
        seeds=seeds,
        time_budget_sec=time_budget_sec,
        output_dir=output_dir,
        repo_root=repo_root,
        workspace=workspace,
        data_root=data_root,
        python=args.python,
        selected_surface=args.selected_surface,
        dry_run=args.dry_run,
    )
    manifest_path = output_dir / "manifest.json"
    _write_json(manifest_path, manifest)

    if args.dry_run:
        results = [planned_result_for_job(job) for job in jobs]
    else:
        mechanism_workspaces = _prepare_mechanism_workspaces(
            mechanisms,
            workspace=workspace,
            output_dir=output_dir,
            reuse_workspaces=args.reuse_workspaces,
        )
        results = _run_jobs(
            jobs,
            mechanism_workspaces=mechanism_workspaces,
            repo_root=repo_root,
            data_root=data_root,
            python=args.python,
            selected_surface=args.selected_surface,
            timeout_padding_sec=args.timeout_padding_sec,
            resume=args.resume,
        )

    results_payload = {
        "schema_version": RESULTS_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": bool(args.dry_run),
        "manifest_path": str(manifest_path),
        "jobs": results,
    }
    results_path = output_dir / "results.json"
    _write_json(results_path, results_payload)
    _write_summary_csv(output_dir / "summary.csv", results)
    print(f"wrote {manifest_path}")
    print(f"wrote {results_path}")
    print(f"wrote {output_dir / 'summary.csv'}")
    return 0


def _run_jobs(
    jobs: Sequence[CvrpMatrixJob],
    *,
    mechanism_workspaces: Mapping[str, Path],
    repo_root: Path,
    data_root: Path,
    python: str,
    selected_surface: str,
    timeout_padding_sec: int,
    resume: bool,
) -> list[dict[str, Any]]:
    raw_by_job: dict[str, Mapping[str, Any]] = {}
    failures: dict[str, dict[str, Any]] = {}
    status_by_job: dict[str, dict[str, Any]] = {}

    for job in jobs:
        output_path = Path(job.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if resume and output_path.exists():
            raw_by_job[job.job_id] = _read_solver_json(output_path)
            status_by_job[job.job_id] = {"status": "resumed"}
            print(json.dumps({"job_id": job.job_id, "status": "resumed"}), flush=True)
            continue
        row = _run_solver_job(
            job,
            workspace=mechanism_workspaces[job.mechanism.mechanism_id],
            repo_root=repo_root,
            data_root=data_root,
            python=python,
            selected_surface=selected_surface,
            timeout_padding_sec=timeout_padding_sec,
        )
        print(json.dumps(row, sort_keys=True), flush=True)
        if row.get("status") == "solver_json_available":
            raw_by_job[job.job_id] = _read_solver_json(output_path)
            status_by_job[job.job_id] = row
        else:
            failures[job.job_id] = row

    first_pass: dict[str, dict[str, Any]] = {}
    reference_by_case_seed: dict[tuple[str, int], dict[str, Any]] = {}
    for job in jobs:
        raw = raw_by_job.get(job.job_id)
        if raw is None:
            continue
        summary = summarize_solver_output_for_job(raw, job=job)
        first_pass[job.job_id] = summary
        if job.mechanism.mechanism_id == "canonical_alns_vns":
            reference_by_case_seed[(job.case.case_id, job.seed)] = summary

    results: list[dict[str, Any]] = []
    for job in jobs:
        raw = raw_by_job.get(job.job_id)
        if raw is None:
            planned = planned_result_for_job(job)
            planned.update(failures.get(job.job_id, {"status": "failed"}))
            results.append(planned)
            continue
        reference = reference_by_case_seed.get((job.case.case_id, job.seed))
        summary = summarize_solver_output_for_job(raw, job=job, reference=reference)
        status_row = status_by_job.get(job.job_id, {})
        for key in ("returncode", "wall_elapsed_sec", "stdout_tail", "stderr_tail"):
            if key in status_row:
                summary[key] = status_row[key]
        results.append(summary)
    return results


def _run_solver_job(
    job: CvrpMatrixJob,
    *,
    workspace: Path,
    repo_root: Path,
    data_root: Path,
    python: str,
    selected_surface: str,
    timeout_padding_sec: int,
) -> dict[str, Any]:
    env = os.environ.copy()
    package_root = repo_root / "scion"
    env["PYTHONPATH"] = _prepend_path(str(package_root), env.get("PYTHONPATH", ""))
    env["SCION_PROBLEM_DATA_ROOT"] = str(data_root)
    if str(selected_surface or "").strip():
        env["SCION_SELECTED_SURFACE"] = str(selected_surface).strip()
    else:
        env.pop("SCION_SELECTED_SURFACE", None)

    cmd = [
        str(Path(python).expanduser()),
        "-m",
        "scion.problems.cvrp.solver",
        job.case.source_path,
        "--seed",
        str(job.seed),
        "--time-limit",
        str(job.time_budget_sec),
        "--output",
        job.output_path,
    ]
    started = time.perf_counter()
    row: dict[str, Any] = {
        "job_id": job.job_id,
        "mechanism_id": job.mechanism.mechanism_id,
        "case_id": job.case.case_id,
        "seed": job.seed,
        "time_budget_sec": job.time_budget_sec,
        "workspace": str(workspace),
        "output_path": job.output_path,
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
            timeout=max(1, int(job.time_budget_sec) + int(timeout_padding_sec)),
        )
    except subprocess.TimeoutExpired as exc:
        row.update(
            {
                "status": "timeout_expired",
                "timeout_after_sec": int(job.time_budget_sec)
                + int(timeout_padding_sec),
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
    if completed.returncode != 0 or not Path(job.output_path).exists():
        row["status"] = "failed"
        return row
    row["status"] = "solver_json_available"
    return row


def _prepare_mechanism_workspaces(
    mechanisms: Sequence[CvrpMechanismSpec],
    *,
    workspace: Path,
    output_dir: Path,
    reuse_workspaces: bool,
) -> dict[str, Path]:
    workspace_map: dict[str, Path] = {}
    for mechanism in mechanisms:
        if not mechanism.overlays:
            workspace_map[mechanism.mechanism_id] = workspace
            continue
        target = output_dir / "workspaces" / mechanism.mechanism_id
        if target.exists() and not reuse_workspaces:
            _safe_rmtree(target, root=output_dir)
        if not target.exists():
            shutil.copytree(
                workspace,
                target,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
            )
        _apply_mechanism_overlays(target, mechanism.overlays)
        workspace_map[mechanism.mechanism_id] = target
    return workspace_map


def _apply_mechanism_overlays(workspace: Path, overlays: Sequence[str]) -> None:
    for overlay in overlays:
        if overlay == "config_use_vns_false":
            _overlay_config_use_vns_false(workspace)
        elif overlay == "config_vns_threshold_70":
            _overlay_config_vns_threshold(workspace, threshold=70)
        elif overlay == "local_search_two_opt_only":
            _overlay_local_search_two_opt_only(workspace)
        else:
            raise ValueError(f"unknown CVRP mechanism overlay: {overlay}")


def _overlay_config_use_vns_false(workspace: Path) -> None:
    config_path = workspace / "policies" / "baseline_modules" / "config.py"
    text = config_path.read_text(encoding="utf-8")
    text = _replace_once(text, "USE_VNS = True", "USE_VNS = False")
    config_path.write_text(text, encoding="utf-8")


def _overlay_config_vns_threshold(workspace: Path, *, threshold: int) -> None:
    config_path = workspace / "policies" / "baseline_modules" / "config.py"
    text = config_path.read_text(encoding="utf-8")
    text = _replace_line_prefix(text, "VNS_THRESHOLD =", f"VNS_THRESHOLD = {threshold}")
    config_path.write_text(text, encoding="utf-8")


def _overlay_local_search_two_opt_only(workspace: Path) -> None:
    local_search_path = workspace / "policies" / "baseline_modules" / "local_search.py"
    text = local_search_path.read_text(encoding="utf-8")
    old = """def _default_vns_operators():
    return [
        _two_opt_intra,
        _relocate,
        _or_opt_1,
        _or_opt_2,
        _or_opt_3,
        _swap,
        _two_opt_star,
    ]
"""
    new = """def _default_vns_operators():
    return [_two_opt_intra]
"""
    text = _replace_once(text, old, new)
    local_search_path.write_text(text, encoding="utf-8")


def _selected_mechanisms(selected: Sequence[str]) -> tuple[CvrpMechanismSpec, ...]:
    mechanisms_by_id = {
        mechanism.mechanism_id: mechanism for mechanism in default_cvrp_mechanisms()
    }
    if not selected:
        return tuple(mechanisms_by_id.values())
    mechanisms: list[CvrpMechanismSpec] = []
    for value in selected:
        mechanism_id = str(value or "").strip()
        if mechanism_id not in mechanisms_by_id:
            known = ", ".join(sorted(mechanisms_by_id))
            raise SystemExit(f"unknown --mechanism {mechanism_id!r}; expected one of {known}")
        mechanisms.append(mechanisms_by_id[mechanism_id])
    return tuple(mechanisms)


def _resolve_seeds(values: Sequence[str]) -> tuple[int, ...]:
    if not values:
        return (11,)
    return tuple(_positive_int(value, "--seed") for value in values)


def _resolve_output_dir(value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve(strict=False)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_EXPERIMENTS_ROOT / f"cvrp-mechanism-matrix-{stamp}"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_summary_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fieldnames = [
        "status",
        "job_id",
        "case_id",
        "case_family",
        "case_slice",
        "seed",
        "time_budget_sec",
        "mechanism_id",
        "mechanism_family",
        "mechanism_slice",
        "total_distance",
        "bks",
        "bks_gap_pct",
        "quality_delta_total_distance_vs_reference",
        "route_count",
        "bks_routes",
        "route_count_exceeds_bks_routes",
        "route_count_regressed_vs_reference",
        "fleet_violation",
        "fleet_violation_positive",
        "fleet_regressed_vs_reference",
        "accepted_moves",
        "move_attempts",
        "improving_moves",
        "best_delta",
        "best_update_count",
        "solver_algorithm_elapsed_ms",
        "solver_algorithm_stop_reason",
        "solver_algorithm_runtime_budget_hit",
        "output_path",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(_csv_row(row, fieldnames))


def _csv_row(row: Mapping[str, Any], fieldnames: Sequence[str]) -> dict[str, Any]:
    case = _dict_or_empty(row.get("case"))
    quality = _dict_or_empty(row.get("quality"))
    flags = _dict_or_empty(row.get("route_fleet_regression_flags"))
    moves = _dict_or_empty(row.get("accepted_moves"))
    best = _dict_or_empty(row.get("best_update_telemetry"))
    runtime = _dict_or_empty(row.get("runtime_phase_split"))
    values = {
        "status": row.get("status"),
        "job_id": row.get("job_id"),
        "case_id": case.get("case_id"),
        "case_family": case.get("case_family"),
        "case_slice": case.get("case_slice"),
        "seed": row.get("seed"),
        "time_budget_sec": row.get("time_budget_sec"),
        "mechanism_id": row.get("mechanism_id"),
        "mechanism_family": row.get("mechanism_family"),
        "mechanism_slice": row.get("mechanism_slice"),
        "total_distance": quality.get("total_distance"),
        "bks": quality.get("bks"),
        "bks_gap_pct": quality.get("bks_gap_pct"),
        "quality_delta_total_distance_vs_reference": quality.get(
            "quality_delta_total_distance_vs_reference"
        ),
        "route_count": quality.get("route_count"),
        "bks_routes": quality.get("bks_routes"),
        "route_count_exceeds_bks_routes": flags.get(
            "route_count_exceeds_bks_routes"
        ),
        "route_count_regressed_vs_reference": flags.get(
            "route_count_regressed_vs_reference"
        ),
        "fleet_violation": quality.get("fleet_violation"),
        "fleet_violation_positive": flags.get("fleet_violation_positive"),
        "fleet_regressed_vs_reference": flags.get("fleet_regressed_vs_reference"),
        "accepted_moves": moves.get("total"),
        "move_attempts": moves.get("move_attempts"),
        "improving_moves": moves.get("improving_moves"),
        "best_delta": best.get("best_delta"),
        "best_update_count": best.get("best_update_count"),
        "solver_algorithm_elapsed_ms": runtime.get("solver_algorithm_elapsed_ms"),
        "solver_algorithm_stop_reason": runtime.get("solver_algorithm_stop_reason"),
        "solver_algorithm_runtime_budget_hit": runtime.get(
            "solver_algorithm_runtime_budget_hit"
        ),
        "output_path": row.get("output_path"),
    }
    return {key: _csv_value(values.get(key)) for key in fieldnames}


def _read_solver_json(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"solver output must be a JSON object: {path}")
    return payload


def _prepend_path(value: str, existing: str) -> str:
    if not existing:
        return value
    return value + os.pathsep + existing


def _replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"expected exactly one overlay target; found {count}")
    return text.replace(old, new, 1)


def _replace_line_prefix(text: str, prefix: str, new_line: str) -> str:
    lines = text.splitlines()
    matches = [index for index, line in enumerate(lines) if line.startswith(prefix)]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one line starting with {prefix!r}")
    lines[matches[0]] = new_line
    return "\n".join(lines) + "\n"


def _safe_rmtree(path: Path, *, root: Path) -> None:
    resolved = path.resolve(strict=False)
    root_resolved = root.resolve(strict=False)
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"refusing to remove path outside output dir: {path}") from exc
    shutil.rmtree(resolved)


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _tail_text(value: Any, limit: int = 2000) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(value)[-limit:]


def _positive_int(value: object, label: str) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"{label} must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError(f"{label} must be positive")
    return parsed


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True)
    return value


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    parser.add_argument("--data-root", default=str(DEFAULT_REPO_ROOT / "vrp"))
    parser.add_argument("--case-manifest", default=str(DEFAULT_CASE_MANIFEST))
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--selected-surface", default="solver_design")
    parser.add_argument(
        "--mechanism",
        action="append",
        default=[],
        help=(
            "Mechanism id to include. Repeatable; defaults to canonical_alns_vns, "
            "alns_only, and size70_two_opt_candidate."
        ),
    )
    parser.add_argument("--family", action="append", default=[])
    parser.add_argument("--slice", action="append", default=[])
    parser.add_argument("--case-limit", type=int, default=1)
    parser.add_argument("--seed", action="append", default=[])
    parser.add_argument("--time-budget-sec", default="1")
    parser.add_argument("--timeout-padding-sec", type=int, default=60)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--reuse-workspaces", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.case_limit is not None and args.case_limit <= 0:
        raise SystemExit("--case-limit must be positive")
    if args.timeout_padding_sec < 0:
        raise SystemExit("--timeout-padding-sec must be non-negative")
    return args


if __name__ == "__main__":
    raise SystemExit(main())
