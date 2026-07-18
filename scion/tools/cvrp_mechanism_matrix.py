#!/usr/bin/env python3
"""Run or plan a no-LLM CVRP family/slice/mechanism diagnostic matrix."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
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
    available_cvrp_mechanisms,
    build_cvrp_mechanism_matrix_manifest,
    build_jobs,
    default_cvrp_mechanisms,
    load_case_entries,
    planned_result_for_job,
    summarize_solver_output_for_job,
)
from scion.problems.cvrp.evidence.b0_runner_contract import (
    B0_CONTRACT,
    B0_OUTER_TIMEOUT_PADDING_SEC,
    B0_SELECTED_SURFACE,
    B0LaunchPlan,
    B0PlannedJob,
    prepare_b0_launch_plan,
    verify_b0_launch_plan,
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
DEFAULT_PROTOCOL_CONFIG = (
    DEFAULT_REPO_ROOT
    / "scion"
    / "scion"
    / "problems"
    / "cvrp"
    / "formal"
    / "protocol.yaml"
)
DEFAULT_WORKSPACE = (
    DEFAULT_REPO_ROOT / "scion" / "scion" / "problems" / "cvrp"
)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    matrix_contract = _resolve_matrix_contract(args)
    repo_root = Path(args.repo_root).expanduser().resolve(strict=False)
    workspace = Path(args.workspace).expanduser().resolve(strict=False)
    data_root = Path(args.data_root).expanduser().resolve(strict=False)
    output_dir = _resolve_output_dir(args.output_dir)
    b0_plan: B0LaunchPlan | None = None
    if matrix_contract == "b0":
        _validate_b0_cli_scope(args)
        source_package_root = repo_root / "scion" / "scion"
        expected_workspace = source_package_root / "problems" / "cvrp"
        if workspace != expected_workspace.resolve(strict=False):
            raise SystemExit(
                "CVRP B0 workspace must be the canonical package workspace: "
                f"{expected_workspace}"
            )
        b0_plan = prepare_b0_launch_plan(
            source_package_root=source_package_root,
            source_data_root=data_root,
            protocol_path=args.protocol_config,
            case_manifest_path=args.case_manifest,
            output_root=output_dir,
            python=args.python,
            selected_surface=args.selected_surface,
            outer_timeout_padding_sec=args.timeout_padding_sec,
            dry_run=args.dry_run,
        )
        jobs = tuple(planned.job for planned in b0_plan.execution_jobs)
        mechanisms = tuple(
            runtime.profile.mechanism_spec() for runtime in b0_plan.profiles
        )
        manifest = b0_plan.manifest_payload()
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        mechanisms = _selected_mechanisms(args.mechanism)
        cases = load_case_entries(
            args.case_manifest,
            case_id_filter=tuple(args.case_id),
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
        manifest["matrix_contract"] = "legacy_uniform_time.v1"
    manifest_path = output_dir / "manifest.json"
    _write_json(manifest_path, manifest, require_absent=b0_plan is not None)

    if args.dry_run:
        if b0_plan is None:
            results = [planned_result_for_job(job) for job in jobs]
        else:
            results = [
                _decorate_b0_result(planned_result_for_job(planned.job), planned)
                for planned in b0_plan.summary_jobs
            ]
    else:
        if b0_plan is None:
            mechanism_workspaces = _prepare_mechanism_workspaces(
                mechanisms,
                workspace=workspace,
                output_dir=output_dir,
                reuse_workspaces=args.reuse_workspaces,
            )
            b0_by_job = None
            effective_data_root = data_root
        else:
            verify_b0_launch_plan(b0_plan)
            mechanism_workspaces = b0_plan.profile_workspaces
            b0_by_job = b0_plan.planned_by_job_id
            effective_data_root = b0_plan.input_root
        results = _run_jobs(
            jobs,
            mechanism_workspaces=mechanism_workspaces,
            repo_root=repo_root,
            data_root=effective_data_root,
            python=(b0_plan.python if b0_plan is not None else args.python),
            selected_surface=args.selected_surface,
            timeout_padding_sec=args.timeout_padding_sec,
            resume=args.resume,
            b0_by_job=b0_by_job,
        )
        if b0_plan is not None:
            by_job_id = {str(row.get("job_id")): row for row in results}
            results = [by_job_id[planned.job.job_id] for planned in b0_plan.summary_jobs]

    snapshot_verification = {"status": "not_applicable"}
    if b0_plan is not None:
        try:
            verify_b0_launch_plan(b0_plan)
            snapshot_verification = {"status": "passed"}
        except Exception as exc:
            snapshot_verification = {"status": "failed", "error": str(exc)}
    results_payload = {
        "schema_version": RESULTS_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": bool(args.dry_run),
        "manifest_path": str(manifest_path),
        "matrix_contract": (
            B0_CONTRACT if b0_plan is not None else "legacy_uniform_time.v1"
        ),
        "snapshot_verification": snapshot_verification,
        "jobs": results,
    }
    results_path = output_dir / "results.json"
    _write_json(results_path, results_payload, require_absent=b0_plan is not None)
    _write_summary_csv(output_dir / "summary.csv", results)
    exit_status = 0
    if b0_plan is not None and not args.dry_run:
        complete = (
            snapshot_verification["status"] == "passed"
            and len(results) == 256
            and all(row.get("status") == "completed" for row in results)
        )
        if complete:
            _publish_b0_closed_receipt(
                plan=b0_plan,
                manifest_path=manifest_path,
                results_path=results_path,
                results=results,
            )
        else:
            exit_status = 1
    print(f"wrote {manifest_path}")
    print(f"wrote {results_path}")
    print(f"wrote {output_dir / 'summary.csv'}")
    return exit_status


def _resolve_matrix_contract(args: argparse.Namespace) -> str:
    requested = str(args.matrix_contract or "").strip()
    if not requested:
        if args.time_budget_sec is not None:
            return "legacy-uniform"
        raise SystemExit(
            "select --matrix-contract b0 explicitly, or provide "
            "--time-budget-sec for the legacy uniform-time contract"
        )
    if requested == "b0" and args.time_budget_sec is not None:
        raise SystemExit(
            "--time-budget-sec is legacy-only and cannot be used with "
            "--matrix-contract b0"
        )
    if requested == "legacy-uniform" and args.time_budget_sec is None:
        raise SystemExit(
            "--matrix-contract legacy-uniform requires --time-budget-sec"
        )
    return requested


def _validate_b0_cli_scope(args: argparse.Namespace) -> None:
    if str(args.stage or "").strip() != "screening":
        raise SystemExit(
            f"CVRP B0 accepts only --stage screening; got {args.stage!r}"
        )
    forbidden = {
        "--mechanism": args.mechanism,
        "--family": args.family,
        "--slice": args.slice,
        "--case-id": args.case_id,
        "--seed": args.seed,
    }
    selected = [flag for flag, values in forbidden.items() if values]
    if selected:
        raise SystemExit(
            "CVRP B0 freezes the complete Protocol population, four profiles, "
            "and seeds 11/29/43/59; selectors are forbidden: "
            + ", ".join(selected)
        )
    if args.resume:
        raise SystemExit("CVRP B0 forbids --resume; use one fresh output root")
    if args.reuse_workspaces:
        raise SystemExit(
            "CVRP B0 forbids --reuse-workspaces; profile runtimes are immutable"
        )
    if int(args.timeout_padding_sec) != B0_OUTER_TIMEOUT_PADDING_SEC:
        raise SystemExit(
            "CVRP B0 outer timeout padding is frozen at "
            f"{B0_OUTER_TIMEOUT_PADDING_SEC}s"
        )
    if str(args.selected_surface or "").strip() != B0_SELECTED_SURFACE:
        raise SystemExit(
            "CVRP B0 selected surface is frozen at "
            f"{B0_SELECTED_SURFACE!r}"
        )


def _decorate_b0_result(
    row: Mapping[str, Any],
    planned: B0PlannedJob,
) -> dict[str, Any]:
    return {**dict(row), **planned.contract_payload()}


def _publish_b0_closed_receipt(
    *,
    plan: B0LaunchPlan,
    manifest_path: Path,
    results_path: Path,
    results: Sequence[Mapping[str, Any]],
) -> None:
    if len(results) != 256:
        raise ValueError("CVRP B0 closed receipt requires exactly 256 results")
    raw_identities: list[dict[str, str]] = []
    planned_by_job = plan.planned_by_job_id
    for row in results:
        if row.get("status") != "completed":
            raise ValueError("CVRP B0 closed receipt requires all jobs completed")
        job_id = str(row.get("job_id") or "")
        planned = planned_by_job.get(job_id)
        if planned is None:
            raise ValueError(f"CVRP B0 result has unknown job: {job_id}")
        if row.get("job_identity_sha256") != planned.job_identity_sha256:
            raise ValueError(f"CVRP B0 result identity drift: {job_id}")
        raw_path = Path(str(row.get("output_path") or ""))
        if raw_path != Path(planned.job.output_path):
            raise ValueError(f"CVRP B0 raw path drift: {job_id}")
        raw = _read_solver_json(raw_path)
        if raw.get("job_identity_sha256") != planned.job_identity_sha256:
            raise ValueError(f"CVRP B0 raw identity drift: {job_id}")
        if raw.get("matrix_contract") != B0_CONTRACT:
            raise ValueError(f"CVRP B0 raw contract drift: {job_id}")
        if raw.get("b0_job") != planned.contract_payload():
            raise ValueError(f"CVRP B0 raw job contract drift: {job_id}")
        raw_identities.append(
            {
                "job_id": job_id,
                "job_identity_sha256": planned.job_identity_sha256,
                "raw_sha256": _sha256_file(raw_path),
            }
        )
    receipt = {
        "schema": "scion.cvrp_b0_matrix_receipt.v1",
        "status": "closed",
        "matrix_contract": B0_CONTRACT,
        "job_count": 256,
        "manifest_sha256": _sha256_file(manifest_path),
        "results_sha256": _sha256_file(results_path),
        "protocol_identity_sha256": plan.protocol_identity_sha256,
        "case_manifest_identity_sha256": plan.case_manifest_identity_sha256,
        "authority_snapshot_identity_sha256": (
            plan.authority_snapshot_identity_sha256
        ),
        "input_snapshot_identity_sha256": plan.input_snapshot_identity_sha256,
        "python_runtime_identity_sha256": (
            plan.python_runtime.runtime_identity_sha256
        ),
        "dependency_identities": {
            runtime.profile.profile_id: runtime.dependency_identity_sha256
            for runtime in plan.profiles
        },
        "raw_results": raw_identities,
    }
    _write_json(
        plan.output_root / "matrix.closed.receipt.json",
        receipt,
        require_absent=True,
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    b0_by_job: Mapping[str, B0PlannedJob] | None = None,
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
        try:
            row = _run_solver_job(
                job,
                workspace=mechanism_workspaces[job.mechanism.mechanism_id],
                repo_root=repo_root,
                data_root=data_root,
                python=python,
                selected_surface=selected_surface,
                timeout_padding_sec=timeout_padding_sec,
                b0_planned=(b0_by_job or {}).get(job.job_id),
            )
        except Exception as exc:
            if b0_by_job is None:
                raise
            row = {
                "job_id": job.job_id,
                "status": "runner_exception",
                "error": f"{type(exc).__name__}: {exc}",
            }
            b0_planned = (b0_by_job or {}).get(job.job_id)
            if b0_planned is not None:
                row = _decorate_b0_result(row, b0_planned)
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
        planned = (b0_by_job or {}).get(job.job_id)
        if planned is not None:
            summary = _decorate_b0_result(summary, planned)
        first_pass[job.job_id] = summary
        if job.mechanism.mechanism_id == "canonical_alns_vns":
            reference_by_case_seed[(job.case.case_id, job.seed)] = summary

    results: list[dict[str, Any]] = []
    for job in jobs:
        raw = raw_by_job.get(job.job_id)
        if raw is None:
            planned = planned_result_for_job(job)
            b0_planned = (b0_by_job or {}).get(job.job_id)
            if b0_planned is not None:
                planned = _decorate_b0_result(planned, b0_planned)
            planned.update(failures.get(job.job_id, {"status": "failed"}))
            results.append(planned)
            continue
        reference = reference_by_case_seed.get((job.case.case_id, job.seed))
        summary = summarize_solver_output_for_job(raw, job=job, reference=reference)
        b0_planned = (b0_by_job or {}).get(job.job_id)
        if b0_planned is not None:
            summary = _decorate_b0_result(summary, b0_planned)
        status_row = status_by_job.get(job.job_id, {})
        for key in ("returncode", "wall_elapsed_sec", "stdout", "stderr"):
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
    b0_planned: B0PlannedJob | None = None,
) -> dict[str, Any]:
    env = os.environ.copy()
    if b0_planned is None:
        package_root = repo_root / "scion"
        env["PYTHONPATH"] = _prepend_path(
            str(package_root), env.get("PYTHONPATH", "")
        )
        solver_output_path = Path(job.output_path)
    else:
        package_root = b0_planned.runtime.package_root
        python = str(b0_planned.python_executable_path)
        selected_surface = B0_SELECTED_SURFACE
        env["PYTHONPATH"] = os.pathsep.join(
            b0_planned.runtime.pythonpath_entries
        )
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        final_output_path = Path(job.output_path)
        if final_output_path.exists():
            raise ValueError(f"CVRP B0 raw output already exists: {final_output_path}")
        final_output_path.parent.mkdir(parents=True, exist_ok=True)
        solver_output_path = final_output_path.parent / (
            f".{final_output_path.name}.{uuid.uuid4().hex}.partial"
        )
    env["SCION_PROBLEM_DATA_ROOT"] = str(data_root)
    if str(selected_surface or "").strip():
        env["SCION_SELECTED_SURFACE"] = str(selected_surface).strip()
    else:
        env.pop("SCION_SELECTED_SURFACE", None)

    cmd = [str(Path(python).expanduser())]
    if b0_planned is not None:
        cmd.append("-S")
    cmd.extend(
        [
            "-m",
            "scion.problems.cvrp.solver",
            job.case.source_path,
            "--seed",
            str(job.seed),
            "--time-limit",
            str(job.time_budget_sec),
            "--output",
            str(solver_output_path),
        ]
    )
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
    if b0_planned is not None:
        row.update(b0_planned.contract_payload())
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
        _unlink_if_exists(solver_output_path)
        row.update(
            {
                "status": "timeout_expired",
                "timeout_after_sec": int(job.time_budget_sec)
                + int(timeout_padding_sec),
                "wall_elapsed_sec": time.perf_counter() - started,
                "stdout": _full_text(exc.stdout),
                "stderr": _full_text(exc.stderr),
            }
        )
        return row
    except BaseException:
        _unlink_if_exists(solver_output_path)
        raise

    row.update(
        {
            "returncode": completed.returncode,
            "wall_elapsed_sec": time.perf_counter() - started,
            "stdout": _full_text(completed.stdout),
            "stderr": _full_text(completed.stderr),
        }
    )
    if completed.returncode != 0 or not solver_output_path.exists():
        _unlink_if_exists(solver_output_path)
        row["status"] = "failed"
        return row
    if b0_planned is not None:
        try:
            raw = dict(_read_solver_json(solver_output_path))
        except Exception as exc:
            _unlink_if_exists(solver_output_path)
            row.update({"status": "invalid_solver_json", "error": str(exc)})
            return row
        try:
            raw.update(
                {
                    "matrix_contract": B0_CONTRACT,
                    "job_identity_sha256": b0_planned.job_identity_sha256,
                    "b0_job": b0_planned.contract_payload(),
                }
            )
            _write_json(Path(job.output_path), raw, require_absent=True)
        finally:
            _unlink_if_exists(solver_output_path)
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
        elif overlay == "config_disable_initial_vns":
            _overlay_config_bool(workspace, "ENABLE_INITIAL_VNS", False)
        elif overlay == "config_disable_embedded_vns":
            _overlay_config_bool(workspace, "ENABLE_EMBEDDED_VNS", False)
        elif overlay == "config_adaptive_embedded_vns_cadence4":
            _overlay_config_int(workspace, "EMBEDDED_VNS_CADENCE", 4)
            _overlay_config_bool(
                workspace,
                "EMBEDDED_VNS_RUN_ON_REPAIR_IMPROVEMENT",
                True,
            )
        elif overlay == "config_adaptive_embedded_vns_cadence2":
            _overlay_config_int(workspace, "EMBEDDED_VNS_CADENCE", 2)
            _overlay_config_bool(
                workspace,
                "EMBEDDED_VNS_RUN_ON_REPAIR_IMPROVEMENT",
                True,
            )
        elif overlay == "config_adaptive_embedded_vns_early8_cadence2":
            _overlay_config_int(workspace, "EMBEDDED_VNS_CADENCE", 2)
            _overlay_config_int(workspace, "EMBEDDED_VNS_EARLY_ALWAYS_ITERATIONS", 8)
            _overlay_config_bool(
                workspace,
                "EMBEDDED_VNS_RUN_ON_REPAIR_IMPROVEMENT",
                True,
            )
        elif overlay == "config_adaptive_embedded_vns_share60_cadence2":
            _overlay_config_int(workspace, "EMBEDDED_VNS_CADENCE", 2)
            _overlay_config_float(workspace, "EMBEDDED_VNS_MIN_RUNTIME_SHARE", 0.60)
            _overlay_config_bool(
                workspace,
                "EMBEDDED_VNS_RUN_ON_REPAIR_IMPROVEMENT",
                True,
            )
        elif overlay == "config_adaptive_embedded_vns_share70_cadence2":
            _overlay_config_int(workspace, "EMBEDDED_VNS_CADENCE", 2)
            _overlay_config_float(workspace, "EMBEDDED_VNS_MIN_RUNTIME_SHARE", 0.70)
            _overlay_config_bool(
                workspace,
                "EMBEDDED_VNS_RUN_ON_REPAIR_IMPROVEMENT",
                True,
            )
        elif overlay == "config_adaptive_embedded_vns_share70_hardcap_cadence2":
            _overlay_config_int(workspace, "EMBEDDED_VNS_CADENCE", 2)
            _overlay_config_float(workspace, "EMBEDDED_VNS_MIN_RUNTIME_SHARE", 0.70)
            _overlay_config_float(workspace, "EMBEDDED_VNS_MAX_RUNTIME_SHARE", 0.70)
            _overlay_config_bool(
                workspace,
                "EMBEDDED_VNS_CAP_REPAIR_IMPROVEMENT_RESCUE",
                False,
            )
            _overlay_config_bool(
                workspace,
                "EMBEDDED_VNS_RUN_ON_REPAIR_IMPROVEMENT",
                True,
            )
            _overlay_config_string(
                workspace,
                "EMBEDDED_VNS_DIAGNOSTIC_PHASE",
                "adaptive_embedded_vns_share70_trigger",
            )
        elif overlay == "config_adaptive_embedded_vns_share70_softrescue_cadence2":
            _overlay_config_int(workspace, "EMBEDDED_VNS_CADENCE", 2)
            _overlay_config_float(workspace, "EMBEDDED_VNS_MIN_RUNTIME_SHARE", 0.70)
            _overlay_config_float(workspace, "EMBEDDED_VNS_MAX_RUNTIME_SHARE", 0.70)
            _overlay_config_bool(
                workspace,
                "EMBEDDED_VNS_CAP_REPAIR_IMPROVEMENT_RESCUE",
                True,
            )
            _overlay_config_bool(
                workspace,
                "EMBEDDED_VNS_RUN_ON_REPAIR_IMPROVEMENT",
                True,
            )
            _overlay_config_string(
                workspace,
                "EMBEDDED_VNS_DIAGNOSTIC_PHASE",
                "adaptive_embedded_vns_share70_trigger",
            )
        elif overlay == "config_adaptive_embedded_vns_share70_tail6_cadence2":
            _overlay_config_int(workspace, "EMBEDDED_VNS_CADENCE", 2)
            _overlay_config_float(workspace, "EMBEDDED_VNS_MIN_RUNTIME_SHARE", 0.70)
            _overlay_config_float(workspace, "EMBEDDED_VNS_MAX_RUNTIME_SHARE", 0.70)
            _overlay_config_bool(
                workspace,
                "EMBEDDED_VNS_CAP_REPAIR_IMPROVEMENT_RESCUE",
                True,
            )
            _overlay_config_int(workspace, "EMBEDDED_VNS_CAP_RESCUE_CADENCE", 6)
            _overlay_config_bool(
                workspace,
                "EMBEDDED_VNS_RUN_ON_REPAIR_IMPROVEMENT",
                True,
            )
            _overlay_config_string(
                workspace,
                "EMBEDDED_VNS_DIAGNOSTIC_PHASE",
                "adaptive_embedded_vns_share70_trigger",
            )
        elif overlay == "config_adaptive_embedded_vns_improve_only":
            _overlay_config_int(workspace, "EMBEDDED_VNS_CADENCE", 0)
            _overlay_config_bool(
                workspace,
                "EMBEDDED_VNS_RUN_ON_REPAIR_IMPROVEMENT",
                True,
            )
        elif overlay == "config_disable_size70_two_opt":
            _overlay_config_bool(workspace, "ENABLE_SIZE70_TWO_OPT_FALLBACK", False)
        elif overlay == "config_vns_threshold_70":
            _overlay_config_vns_threshold(workspace, threshold=70)
        elif overlay == "local_search_two_opt_only":
            _overlay_local_search_two_opt_only(workspace)
        else:
            raise ValueError(f"unknown CVRP mechanism overlay: {overlay}")


def _overlay_config_use_vns_false(workspace: Path) -> None:
    _overlay_config_bool(workspace, "USE_VNS", False)


def _overlay_config_bool(workspace: Path, name: str, value: bool) -> None:
    replacement = "True" if value else "False"
    config_path = workspace / "policies" / "baseline_modules" / "config.py"
    text = config_path.read_text(encoding="utf-8")
    text = _replace_line_prefix(text, f"{name} =", f"{name} = {replacement}")
    config_path.write_text(text, encoding="utf-8")


def _overlay_config_int(workspace: Path, name: str, value: int) -> None:
    config_path = workspace / "policies" / "baseline_modules" / "config.py"
    text = config_path.read_text(encoding="utf-8")
    text = _replace_line_prefix(text, f"{name} =", f"{name} = {int(value)}")
    config_path.write_text(text, encoding="utf-8")


def _overlay_config_float(workspace: Path, name: str, value: float) -> None:
    config_path = workspace / "policies" / "baseline_modules" / "config.py"
    text = config_path.read_text(encoding="utf-8")
    text = _replace_line_prefix(text, f"{name} =", f"{name} = {float(value):.2f}")
    config_path.write_text(text, encoding="utf-8")


def _overlay_config_string(workspace: Path, name: str, value: str) -> None:
    config_path = workspace / "policies" / "baseline_modules" / "config.py"
    text = config_path.read_text(encoding="utf-8")
    text = _replace_line_prefix(text, f"{name} =", f'{name} = "{value}"')
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
        mechanism.mechanism_id: mechanism for mechanism in available_cvrp_mechanisms()
    }
    if not selected:
        return default_cvrp_mechanisms()
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


def _write_json(
    path: Path,
    payload: Mapping[str, Any],
    *,
    require_absent: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    encoded = (
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")
    try:
        with temp.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        parsed = json.loads(temp.read_text(encoding="utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError(f"atomic JSON artifact must be an object: {path}")
        if require_absent:
            os.link(temp, path)
            temp.unlink()
        else:
            os.replace(temp, path)
        _fsync_directory(path.parent)
    finally:
        _unlink_if_exists(temp)


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
        "alns_iterations",
        "alns_iteration_trace_count",
        "alns_core_runtime_ms",
        "vns_initial_runtime_ms",
        "vns_embedded_runtime_ms",
        "vns_embedded_runtime_fraction",
        "solver_algorithm_elapsed_ms",
        "solver_algorithm_stop_reason",
        "solver_algorithm_runtime_budget_hit",
        "output_path",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        with temp.open("x", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(_csv_row(row, fieldnames))
            handle.flush()
            os.fsync(handle.fileno())
        with temp.open(encoding="utf-8", newline="") as handle:
            if sum(1 for _ in csv.DictReader(handle)) != len(rows):
                raise ValueError("summary CSV validation count mismatch")
        os.replace(temp, path)
        _fsync_directory(path.parent)
    finally:
        _unlink_if_exists(temp)


def _csv_row(row: Mapping[str, Any], fieldnames: Sequence[str]) -> dict[str, Any]:
    case = _dict_or_empty(row.get("case"))
    quality = _dict_or_empty(row.get("quality"))
    flags = _dict_or_empty(row.get("route_fleet_regression_flags"))
    moves = _dict_or_empty(row.get("accepted_moves"))
    best = _dict_or_empty(row.get("best_update_telemetry"))
    phase = _dict_or_empty(row.get("phase_telemetry"))
    runtime = _dict_or_empty(row.get("runtime_phase_split"))
    phase_runtime = _dict_or_empty(runtime.get("phase_runtime_ms"))
    phase_fraction = _dict_or_empty(runtime.get("phase_runtime_fraction"))
    actionability = _dict_or_empty(phase.get("actionability_summary"))
    actionability_phases = _dict_or_empty(actionability.get("phases"))
    alns_actionability = _dict_or_empty(actionability_phases.get("alns"))
    alns_trace = phase.get("alns_iteration_trace")
    alns_trace_count = len(alns_trace) if isinstance(alns_trace, list) else 0
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
        "alns_iterations": alns_actionability.get("iterations"),
        "alns_iteration_trace_count": alns_trace_count,
        "alns_core_runtime_ms": phase_runtime.get("alns_core"),
        "vns_initial_runtime_ms": phase_runtime.get("vns_initial"),
        "vns_embedded_runtime_ms": phase_runtime.get("vns_embedded"),
        "vns_embedded_runtime_fraction": phase_fraction.get("vns_embedded"),
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


def _unlink_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


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


def _full_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(value)


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
    parser.add_argument("--protocol-config", default=str(DEFAULT_PROTOCOL_CONFIG))
    parser.add_argument("--stage", default="screening")
    parser.add_argument(
        "--matrix-contract",
        choices=("b0", "legacy-uniform"),
        default=None,
        help=(
            "B0 must be selected explicitly; --time-budget-sec without this "
            "option selects the legacy uniform-time diagnostic contract."
        ),
    )
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
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help=(
            "Case id to include exactly, e.g. P-n76-k4. Repeatable; combines "
            "with --family and --slice filters."
        ),
    )
    parser.add_argument("--seed", action="append", default=[])
    parser.add_argument(
        "--time-budget-sec",
        default=None,
        help=(
            "Legacy uniform-time diagnostic only; forbidden by the CVRP B0 "
            "Protocol-resolved contract."
        ),
    )
    parser.add_argument("--timeout-padding-sec", type=int, default=60)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--reuse-workspaces", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.timeout_padding_sec < 0:
        raise SystemExit("--timeout-padding-sec must be non-negative")
    return args


if __name__ == "__main__":
    raise SystemExit(main())
