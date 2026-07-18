"""Serial, no-retry runner for the sealed CVRP F1 ancestry matrix."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import time
from typing import Any, Mapping, Sequence

from scion.problems.cvrp.evidence import f1_contract as contract
from scion.problems.cvrp.evidence import f1_io as io
from scion.problems.cvrp.evidence import f1_preparation as preparation
from scion.problems.cvrp.evidence.f1_runtime import child_environment


def run_f1_root(root: str | Path) -> None:
    """Run the frozen jobs serially exactly once; never retry or resume."""

    plan = preparation.verify_f1_root(root)
    manifest = plan.manifest
    if manifest.get("dry_run") is not False:
        raise contract.CvrpF1Error("F1 dry root has no solver execution authority")
    design = io._object(manifest["design"], "design")
    if design.get("tracked_at_git_commit") is not True:
        raise contract.CvrpF1Error(
            "F1 formal execution requires committed design authority"
        )
    if any(
        row.get("tracked_at_git_commit") is not True
        for row in manifest["implementation_sources"]
    ):
        raise contract.CvrpF1Error(
            "F1 formal execution requires committed implementation authority"
        )
    terminal = plan.root / "terminal.json"
    if terminal.exists():
        raise contract.CvrpF1Error("F1 terminal root cannot be run again")
    for dirname in ("raw", "interchange", "streams"):
        path = plan.root / dirname
        if path.exists():
            raise contract.CvrpF1Error(
                f"F1 execution directory already exists: {dirname}"
            )
        path.mkdir()
    manifest_sha = plan.manifest_sha256
    arms = {str(row["arm"]): row for row in manifest["arms"]}
    python = str(manifest["python"]["executable_path"])
    dependency_paths = tuple(str(value) for value in manifest["dependency_paths"])
    completed_rows = 0
    failed_rows = 0
    for job in manifest["jobs"]:
        row = _run_job(
            root=plan.root,
            manifest_sha256=manifest_sha,
            job=io._object(job, "job"),
            arm=io._object(arms[str(job["arm"])], "arm"),
            python=python,
            dependency_paths=dependency_paths,
        )
        io._publish_json_no_replace(plan.root / str(job["row_path"]), row)
        completed_rows += 1
        if row["status"] != "validated_solver":
            failed_rows += 1
    if completed_rows != 256:
        raise contract.CvrpF1Error("F1 runner did not publish all declared rows")
    # The design requires a complete immutable-closure check before and after
    # formal execution.  Re-running full preflight between jobs would add a
    # second workload to the serial matrix and distort the experimental lane.
    preparation.verify_f1_root(plan.root)
    marker = {
        "schema_version": contract.F1_TERMINAL_SCHEMA,
        "manifest_sha256": manifest_sha,
        "declared_jobs": 256,
        "published_rows": completed_rows,
        "typed_solver_failures": failed_rows,
        "runner_complete": True,
        "retry": False,
        "resume": False,
        "automatic_rerun": False,
    }
    io._publish_json_no_replace(terminal, marker)


def _run_job(
    *,
    root: Path,
    manifest_sha256: str,
    job: Mapping[str, Any],
    arm: Mapping[str, Any],
    python: str,
    dependency_paths: Sequence[str],
) -> dict[str, Any]:
    workspace = root / str(arm["workspace"])
    package_root = root / str(arm["package_root"])
    interchange = root / str(job["interchange_path"])
    io._create_exclusive_empty(interchange)
    stdout_path = root / str(job["stdout_path"])
    stderr_path = root / str(job["stderr_path"])
    env = child_environment(
        package_root=package_root,
        dependency_paths=dependency_paths,
        data_root=root / "input_snapshot",
    )
    argv = [
        python,
        "-S",
        "-m",
        "scion.problems.cvrp.solver",
        str(job["case_path"]),
        "--seed",
        str(job["seed"]),
        "--time-limit",
        str(job["time_limit_sec"]),
        "--output",
        str(interchange),
    ]
    if argv != job["command"]:
        raise contract.CvrpF1Error(f"F1 frozen argv drift: {job['job_id']}")
    if env != job["environment"]:
        raise contract.CvrpF1Error(f"F1 frozen environment drift: {job['job_id']}")
    started_mono = time.monotonic_ns()
    started_wall = time.time_ns()
    completed = subprocess.run(
        argv,
        cwd=str(workspace),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    ended_mono = time.monotonic_ns()
    ended_wall = time.time_ns()
    io._publish_bytes_no_replace(stdout_path, completed.stdout)
    io._publish_bytes_no_replace(stderr_path, completed.stderr)
    base: dict[str, Any] = {
        "schema_version": contract.F1_ROW_SCHEMA,
        "manifest_sha256": manifest_sha256,
        "root_id": job["root_id"],
        "job_identity_sha256": job["job_identity_sha256"],
        "job_id": job["job_id"],
        "job_ordinal": job["job_ordinal"],
        "cell_ordinal": job["cell_ordinal"],
        "stage": job["stage"],
        "arm": job["arm"],
        "arm_symbol": job["arm_symbol"],
        "schedule_position": job["schedule_position"],
        "williams_sequence": job["williams_sequence"],
        "case_path": job["case_path"],
        "case_identity_sha256": job["case_identity_sha256"],
        "solution_identity_sha256": job["solution_identity_sha256"],
        "seed": job["seed"],
        "time_limit_sec": job["time_limit_sec"],
        "command": argv,
        "environment": env,
        "working_directory": str(workspace),
        "workspace_identity_sha256": arm["runtime_identity_sha256"],
        "returncode": completed.returncode,
        "exit_status": completed.returncode if completed.returncode >= 0 else None,
        "signal_status": -completed.returncode if completed.returncode < 0 else None,
        "started_monotonic_ns": started_mono,
        "ended_monotonic_ns": ended_mono,
        "started_wall_ns": started_wall,
        "ended_wall_ns": ended_wall,
        "interchange": io._file_evidence(interchange),
        "stdout": io._file_evidence(stdout_path),
        "stderr": io._file_evidence(stderr_path),
    }
    if completed.returncode != 0:
        return _solver_failure(base, "nonzero_exit_or_signal")
    try:
        raw = io._load_object(interchange, label=f"solver interchange {job['job_id']}")
        validation = _validate_solver_payload(
            python=python,
            package_root=package_root,
            workspace=workspace,
            data_root=root / "input_snapshot",
            case_path=str(job["case_path"]),
            interchange=interchange,
            dependency_paths=dependency_paths,
        )
        parsed = _parse_solver_evidence(raw, validation)
    except Exception as exc:
        return _solver_failure(
            base,
            "invalid_solver_evidence",
            detail=f"{type(exc).__name__}: {exc}",
        )
    base.update(
        {
            "status": "validated_solver",
            "failure": None,
            "parsed_payload": {
                "status": "present",
                "sha256": io._canonical_sha256(raw),
            },
            **parsed,
        }
    )
    return base


def _solver_failure(
    base: dict[str, Any], failure_type: str, *, detail: str | None = None
) -> dict[str, Any]:
    reason = detail or "solver process did not exit successfully"
    base.update(
        {
            "status": "solver_failure",
            "failure": {"type": failure_type, "reason": reason},
            "parsed_payload": io._missing(failure_type),
            "validity": io._missing(failure_type),
            "objective": io._missing(failure_type),
            "telemetry": io._missing(failure_type),
        }
    )
    return base


def _parse_solver_evidence(
    raw: Mapping[str, Any], validation: Mapping[str, Any]
) -> dict[str, Any]:
    runtime = io._object_or_empty(raw.get("runtime"))
    objective = io._object(validation.get("objective"), "validated objective")
    solution_progress = io._object_or_empty(
        runtime.get("solver_algorithm_solution_progress")
    )
    phase_runtime = io._object_or_empty(
        runtime.get("solver_algorithm_phase_runtime_ms")
    )
    phase_attempts = io._object_or_empty(
        runtime.get("solver_algorithm_phase_move_attempts")
    )
    phase_accepted = io._object_or_empty(
        runtime.get("solver_algorithm_phase_accepted_moves")
    )
    phase_delta = io._object_or_empty(runtime.get("solver_algorithm_phase_delta_sum"))
    actionability = io._object_or_empty(
        runtime.get("solver_algorithm_actionability_summary")
    )
    actionability_phases = io._object_or_empty(actionability.get("phases"))
    swap_star_actionability = io._object_or_empty(actionability_phases.get("swap_star"))
    trace = runtime.get("solver_algorithm_alns_iteration_trace")
    typed_trace = (
        trace if isinstance(trace, list) else io._missing("solver_did_not_emit")
    )
    best_update_trace = runtime.get("solver_algorithm_best_update_trace")
    typed_best_update_trace = (
        best_update_trace
        if isinstance(best_update_trace, list)
        else io._missing("solver_did_not_emit_best_update_trace")
    )
    best_update_summary = runtime.get("solver_algorithm_best_update_summary")
    typed_best_update_summary = (
        dict(best_update_summary)
        if isinstance(best_update_summary, Mapping)
        else io._missing("solver_did_not_emit_best_update_summary")
    )
    sa_temperature_trace = runtime.get("solver_algorithm_sa_temperature_trajectory")
    typed_sa_temperature_trace = (
        sa_temperature_trace
        if isinstance(sa_temperature_trace, list)
        else io._missing("solver_did_not_emit_sa_temperature_trajectory")
    )
    probes = runtime.get("solver_algorithm_objective_probes")
    typed_probes = (
        probes if isinstance(probes, list) else io._missing("solver_did_not_emit")
    )
    route_rows = (
        [
            row
            for row in trace
            if isinstance(row, dict) and row.get("destroy_operator") == "route"
        ]
        if isinstance(trace, list)
        else []
    )
    route_repair_rows = (
        [
            row
            for row in route_rows
            if isinstance(row, dict) and row.get("acceptance_reason") != "destroy_empty"
        ]
        if route_rows
        else []
    )
    trace_present = isinstance(trace, list)

    def trace_count(value: int) -> dict[str, Any]:
        return io._typed(value) if trace_present else io._missing("solver_did_not_emit")

    telemetry = {
        "initial_solution": {
            "identity": io._missing("solver_did_not_emit_initial_solution_identity"),
            "objective": io._typed(solution_progress.get("initial_total_distance")),
        },
        "phase_runtime_ms": {
            name: io._typed(phase_runtime.get(name))
            for name in (
                "vns_initial",
                "vns_embedded",
                "alns_core",
                "repair",
                "polish",
                "residual",
            )
        },
        "alns": {
            "iterations": io._typed(runtime.get("solver_algorithm_search_iterations")),
            "throughput": io._typed(runtime.get("solver_algorithm_search_throughput")),
            "best_updates": io._typed(
                runtime.get("solver_algorithm_best_improving_moves")
            ),
            "best_update_trace": typed_best_update_trace,
            "best_update_summary": typed_best_update_summary,
            "iteration_trace": typed_trace,
            # The frozen runtime records acceptance decisions in the complete
            # ALNS iteration trace.  Preserve those exact rows; do not infer a
            # separate trajectory or a temperature schedule.
            "acceptance_trajectory": typed_trace,
            "sa_temperature_trajectory": typed_sa_temperature_trace,
            "objective_probes": typed_probes,
            "stop_reason": io._typed(runtime.get("solver_algorithm_stop_reason")),
            "runtime_budget_hit": io._typed(
                runtime.get("solver_algorithm_runtime_budget_hit")
            ),
        },
        "swap_star": {
            "attempts": io._typed(phase_attempts.get("swap_star")),
            "accepted": io._typed(phase_accepted.get("swap_star")),
            "delta": io._typed(phase_delta.get("swap_star")),
            "elapsed_ms": io._typed(swap_star_actionability.get("runtime_ms")),
        },
        "route_elimination": {
            "selections": trace_count(len(route_rows)),
            "destroy_empty": trace_count(
                sum(
                    row.get("acceptance_reason") == "destroy_empty"
                    for row in route_rows
                )
            ),
            "repair_invocations": trace_count(len(route_repair_rows)),
            "acceptances": trace_count(
                sum(bool(row.get("accepted")) for row in route_rows)
            ),
            "best_updates": trace_count(
                sum(bool(row.get("best_improved")) for row in route_rows)
            ),
            "elapsed_ms": io._missing("solver_did_not_emit_route_elimination_elapsed"),
        },
    }
    return {
        "validity": {
            "status": "present",
            "solution_valid": validation["solution_valid"],
            "fleet_feasible": validation["fleet_feasible"],
            "reasons": validation["reasons"],
        },
        "objective": {
            "status": "present",
            "fleet_violation": objective["fleet_violation"],
            "total_distance": objective["total_distance"],
            "routes": objective["routes"],
            "bks": validation["bks"],
            "bks_routes": validation["bks_routes"],
            "bks_gap_pct": validation["bks_gap_pct"],
        },
        "telemetry": telemetry,
    }


def _validate_solver_payload(
    *,
    python: str,
    package_root: Path,
    workspace: Path,
    data_root: Path,
    case_path: str,
    interchange: Path,
    dependency_paths: Sequence[str],
) -> Mapping[str, Any]:
    script = r"""
import json, os
from pathlib import Path
from scion.problems.cvrp.adapter import CvrpAdapter
class Spec:
    pass
adapter = CvrpAdapter(Spec())
case = Path(os.environ["F1_DATA_ROOT"]) / os.environ["F1_CASE_PATH"]
raw = json.loads(Path(os.environ["F1_INTERCHANGE"]).read_text(encoding="utf-8"))
instance = adapter.load_instance(str(case))
artifact = adapter.deserialize_solver_output(raw, instance)
consistency = adapter.check_solution_consistency(artifact, instance)
feasibility = adapter.check_feasibility(artifact, instance)
objective = dict(adapter.recompute_objective(artifact, instance))
reported = raw.get("objective", {})
if not isinstance(reported, dict):
    reported = {}
reasons = list(consistency.reasons) + [
    reason for reason in feasibility.reasons if reason not in consistency.reasons
]
for key in ("fleet_violation", "total_distance", "routes"):
    if key not in reported or float(reported[key]) != float(objective[key]):
        reasons.append(f"reported objective mismatch: {key}")
bks = instance.bks
gap = None if bks in (None, 0) else (float(objective["total_distance"]) - float(bks)) / float(bks) * 100.0
print(json.dumps({
    "solution_valid": not reasons and consistency.passed and feasibility.passed,
    "fleet_feasible": feasibility.passed and int(objective["fleet_violation"]) == 0,
    "reasons": reasons,
    "objective": objective,
    "bks": bks,
    "bks_routes": instance.bks_routes,
    "bks_gap_pct": gap,
}, sort_keys=True, separators=(",", ":"), allow_nan=False))
"""
    env = child_environment(
        package_root=package_root,
        dependency_paths=dependency_paths,
        data_root=data_root,
    )
    env.update(
        {
            "F1_DATA_ROOT": str(data_root),
            "F1_CASE_PATH": case_path,
            "F1_INTERCHANGE": str(interchange),
        }
    )
    completed = subprocess.run(
        [python, "-S", "-c", script],
        cwd=str(workspace),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise contract.CvrpF1Error(
            "sealed solution validation failed: "
            + completed.stderr.decode("utf-8", errors="replace")
        )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise contract.CvrpF1Error("sealed solution validation returned non-object")
    return payload


__all__ = ["run_f1_root"]
