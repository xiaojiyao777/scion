"""Pure Warehouse W3 validation over generic closed-process observations."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from random import Random
from typing import Any, Mapping, Sequence

from scion.runtime.execution import ClosedSpawnObservation, LeaderOutcome

from .w3_fixed_arm import (
    WarehouseW3Error,
    canonical_sha256,
    canonical_solution,
    process_spec_for_job,
    render_json,
    sha256_bytes,
    workspace_runtime,
)

RAW_SCHEMA = "scion.warehouse_w3_fixed_arm_raw_row.v2"
_RAW_FIELDS = {
    "schema",
    "manifest_sha256",
    "job_ordinal",
    "cell_ordinal",
    "stage_cell_ordinal",
    "stage",
    "case_identity",
    "seed",
    "arm",
    "arm_position",
    "arm_sha256",
    "workspace_tree_sha256",
    "phase",
    "scientific_time_limit_seconds",
    "max_iterations",
    "execution_observation",
    "solution",
    "solution_sha256",
    "oracle",
    "objective",
    "greedy_initial",
    "locked_groups",
    "merge_pair_counts",
    "operator_runtime_diagnostics",
}


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise WarehouseW3Error(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(data: bytes, *, label: str) -> Any:
    try:
        return json.loads(data, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WarehouseW3Error(f"invalid JSON for {label}: {exc}") from exc


def _finite_tree(value: Any) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _finite_tree(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return all(_finite_tree(item) for item in value)
    return value is None or isinstance(value, (str, int, bool))


def _entry(
    values: Sequence[Mapping[str, Any]], key: str, expected: str
) -> Mapping[str, Any]:
    matches = [value for value in values if value.get(key) == expected]
    if len(matches) != 1:
        raise WarehouseW3Error(f"W3 identity is not unique: {key}={expected}")
    return matches[0]


def _initial_fact(
    manifest: Mapping[str, Any], job: Mapping[str, Any]
) -> Mapping[str, Any]:
    matches = [
        fact
        for fact in manifest["greedy_preflight"]
        if fact["stable_case_id"] == job["stable_case_id"]
        and fact["seed"] == job["seed"]
    ]
    if len(matches) != 1:
        raise WarehouseW3Error(
            f"job has no unique greedy fact: {job['job_ordinal']}"
        )
    return matches[0]


def _solution_from_payload(runtime: Mapping[str, Any], payload: Mapping[str, Any]) -> Any:
    models = runtime["models"]
    raw_vehicles = payload.get("vehicles")
    assignment = payload.get("assignment")
    if not isinstance(raw_vehicles, (dict, list)) or not isinstance(assignment, dict):
        raise WarehouseW3Error("solver solution lacks vehicles or assignment")
    items: list[tuple[str, Any]] = []
    if isinstance(raw_vehicles, dict):
        items = [(str(key), value) for key, value in raw_vehicles.items()]
    else:
        for raw in raw_vehicles:
            if not isinstance(raw, dict) or "vehicle_id" not in raw:
                raise WarehouseW3Error("solver vehicle list item is malformed")
            items.append((str(raw["vehicle_id"]), raw))
    vehicles: dict[str, Any] = {}
    for map_id, raw in items:
        if not isinstance(raw, dict):
            raise WarehouseW3Error("solver vehicle is not a mapping")
        vehicle_id = str(raw.get("vehicle_id"))
        if vehicle_id != map_id:
            raise WarehouseW3Error("solver vehicle key differs from vehicle_id")
        if vehicle_id in vehicles:
            raise WarehouseW3Error(f"duplicate solver vehicle_id: {vehicle_id}")
        vehicles[vehicle_id] = models.Vehicle(
            vehicle_id=vehicle_id,
            vehicle_type=str(raw["vehicle_type"]),
            region=str(raw["region"]),
            order_ids=[str(value) for value in raw["order_ids"]],
        )
    return models.Solution(
        vehicles=vehicles,
        assignment={str(key): str(value) for key, value in assignment.items()},
    )


def _objective(payload: Mapping[str, Any]) -> tuple[int, int | float, Any]:
    raw = payload.get("objective")
    if not isinstance(raw, dict):
        raise WarehouseW3Error("solver output lacks objective")
    splits = raw.get("subcategory_splits")
    cost = raw.get("total_cost")
    if isinstance(splits, bool) or not isinstance(splits, int):
        raise WarehouseW3Error("subcategory_splits is not an integer")
    if (
        isinstance(cost, bool)
        or not isinstance(cost, (int, float))
        or not math.isfinite(cost)
    ):
        raise WarehouseW3Error("total_cost is not finite numeric")
    if float(cost).is_integer():
        cost = int(cost)
    return splits, cost, raw.get("solve_time_ms")


def _group_observations(
    instance: Any, solution: Any, initial_fact: Mapping[str, Any]
) -> dict[str, int]:
    groups: dict[str, list[str]] = defaultdict(list)
    for order_id, order in instance.orders.items():
        if order.locked_vehicle_id is not None:
            groups[str(order.locked_vehicle_id)].append(order_id)
    split = moved = intact = 0
    initial_map = initial_fact["initial_group_vehicle_map"]
    for group_id, order_ids in sorted(groups.items()):
        vehicles = {solution.assignment[order_id] for order_id in order_ids}
        if len(vehicles) != 1:
            split += 1
            continue
        intact += 1
        if next(iter(vehicles)) != initial_map[group_id]:
            moved += 1
    return {
        "final_intact_locked_group_count": intact,
        "whole_groups_moved_count": moved,
        "split_group_count": split,
    }


def _operator_diagnostics(payload: Mapping[str, Any]) -> dict[str, Any]:
    runtime = payload.get("runtime")
    diagnostics = runtime.get("operator_diagnostics") if isinstance(runtime, dict) else None
    return {
        "status": "available" if isinstance(diagnostics, dict) else "unavailable",
        "value": diagnostics if isinstance(diagnostics, dict) else None,
    }


def _validate_registry(payload: Mapping[str, Any], workspace: Mapping[str, Any]) -> None:
    runtime = payload.get("runtime")
    actual = runtime.get("operator_registry") if isinstance(runtime, dict) else None
    expected = [entry["name"] for entry in workspace["registry_semantics"]["operators"]]
    if actual != expected:
        raise WarehouseW3Error("solver did not report the exact manifest registry")


def _observation_value(observation: ClosedSpawnObservation) -> dict[str, Any]:
    return {
        "observation_sha256": observation.observation_sha256,
        "opaque_job_key": observation.opaque_job_key,
        "process_spec_sha256": observation.process_spec_sha256,
        "start_wall_ns": observation.start_wall_ns,
        "end_wall_ns": observation.end_wall_ns,
        "start_monotonic_ns": observation.start_monotonic_ns,
        "end_monotonic_ns": observation.end_monotonic_ns,
        "wall_time_ns": observation.end_monotonic_ns - observation.start_monotonic_ns,
        "process_identity": observation.process_identity.to_mapping(),
        "wait_fact": observation.wait_fact.to_mapping(),
        "leader_outcome": observation.leader_outcome.value,
        "stdout": {
            "sha256": observation.stdout.sha256,
            "byte_length": observation.stdout.byte_length,
        },
        "stderr": {
            "sha256": observation.stderr.sha256,
            "byte_length": observation.stderr.byte_length,
        },
        "cgroup_identity": observation.cgroup_identity.to_mapping(),
        "initial_cgroup_events_sha256": sha256_bytes(
            observation.initial_cgroup_events.raw
        ),
        "final_cgroup_events_sha256": sha256_bytes(
            observation.final_cgroup_events.raw
        ),
    }


def validate_closed_observation(
    root: Path,
    manifest: Mapping[str, Any],
    manifest_sha256: str,
    job: Mapping[str, Any],
    observation: ClosedSpawnObservation,
) -> bytes:
    """Return one canonical problem row without writing or publishing it."""

    if type(observation) is not ClosedSpawnObservation:
        raise TypeError("observation must be exact ClosedSpawnObservation")
    expected_spec = process_spec_for_job(root, manifest, job)
    if (
        observation.opaque_job_key != expected_spec.opaque_job_key
        or observation.process_spec_sha256 != expected_spec.spec_sha256
        or observation.executable_sha256 != expected_spec.executable_sha256
        or observation.argv_sha256 != expected_spec.argv_sha256
        or observation.environment_sha256 != expected_spec.environment_sha256
        or observation.cwd_sha256 != expected_spec.cwd_sha256
    ):
        raise WarehouseW3Error("closed observation differs from the manifest process spec")
    if observation.leader_outcome is not LeaderOutcome.ZERO:
        raise WarehouseW3Error("W3 solver leader did not exit zero")
    payload = _load_json(observation.stdout.data, label=observation.opaque_job_key)
    if not isinstance(payload, dict) or not _finite_tree(payload):
        raise WarehouseW3Error("solver stdout is not one finite JSON mapping")

    root = root.resolve(strict=True)
    workspace_entry = _entry(manifest["workspaces"], "arm", str(job["arm"]))
    case = _entry(manifest["cases"], "stable_case_id", str(job["stable_case_id"]))
    workspace = root / str(workspace_entry["relative_path"])
    case_path = root / str(case["sealed_relative_path"])
    initial_fact = _initial_fact(manifest, job)
    _validate_registry(payload, workspace_entry)
    reported_splits, reported_cost, reported_runtime = _objective(payload)
    with workspace_runtime(workspace) as runtime:
        instance = runtime["solver"].load_instance(case_path, phase=1)
        initial = runtime["greedy"].greedy_init(instance, Random(int(job["seed"])))
        initial.objective = runtime["oracle"].recompute_objective(initial, instance)
        reconstructed_initial_sha = canonical_sha256(
            {
                "domain": "scion.warehouse_w3_greedy_solution.v1",
                "solution": canonical_solution(initial),
            }
        )
        if reconstructed_initial_sha != initial_fact["initial_solution_sha256"]:
            raise WarehouseW3Error("job initial reconstruction differs from preflight")
        solution = _solution_from_payload(runtime, payload)
        feasibility = runtime["oracle"].check_feasibility(solution, instance, phase=1)
        objective = runtime["oracle"].recompute_objective(solution, instance)
        if (
            not feasibility.is_feasible
            or payload.get("feasible") is not True
            or objective.subcategory_splits != reported_splits
            or objective.total_cost != reported_cost
        ):
            raise WarehouseW3Error("job Oracle/objective mismatch")
        solution_value = canonical_solution(solution)
        locked_groups = _group_observations(instance, solution, initial_fact)
    if locked_groups["split_group_count"] != 0:
        raise WarehouseW3Error("job split a locked group")

    case_identity_keys = (
        "stable_case_id",
        "manifest_index",
        "lexical_path",
        "resolved_path",
        "size_bytes",
        "content_sha256",
        "sealed_relative_path",
    )
    row = {
        "schema": RAW_SCHEMA,
        "manifest_sha256": manifest_sha256,
        "job_ordinal": job["job_ordinal"],
        "cell_ordinal": job["cell_ordinal"],
        "stage_cell_ordinal": job["stage_cell_ordinal"],
        "stage": job["stage"],
        "case_identity": {key: case[key] for key in case_identity_keys},
        "seed": job["seed"],
        "arm": job["arm"],
        "arm_position": job["arm_position"],
        "arm_sha256": job["arm_sha256"],
        "workspace_tree_sha256": workspace_entry["tree"]["tree_sha256"],
        "phase": 1,
        "scientific_time_limit_seconds": 30,
        "max_iterations": 200,
        "execution_observation": _observation_value(observation),
        "solution": solution_value,
        "solution_sha256": canonical_sha256(
            {"domain": "scion.warehouse_w3_solution.v1", "solution": solution_value}
        ),
        "oracle": {"feasible": True, "issue_codes": []},
        "objective": {
            "subcategory_splits": reported_splits,
            "total_cost": reported_cost,
            "solver_reported_runtime_ms": reported_runtime,
            "runner_wall_time_ns": observation.end_monotonic_ns
            - observation.start_monotonic_ns,
        },
        "greedy_initial": {
            "preflight_sha256": initial_fact["initial_solution_sha256"],
            "job_reconstructed_sha256": reconstructed_initial_sha,
            "objective": initial_fact["initial_objective"],
        },
        "locked_groups": locked_groups,
        "merge_pair_counts": initial_fact["merge_pair_counts"],
        "operator_runtime_diagnostics": _operator_diagnostics(payload),
    }
    return render_json(row)


def decode_canonical_row(data: bytes) -> dict[str, Any]:
    value = _load_json(data, label="W3 canonical row")
    if not isinstance(value, dict) or render_json(value) != data:
        raise WarehouseW3Error("W3 row bytes are not canonical")
    return value


def validate_row_static(
    row: Mapping[str, Any],
    manifest: Mapping[str, Any],
    manifest_sha256: str,
    job: Mapping[str, Any],
) -> None:
    if set(row) != _RAW_FIELDS or row.get("schema") != RAW_SCHEMA:
        raise WarehouseW3Error("W3 raw row schema or fields differ")
    expected = {
        "manifest_sha256": manifest_sha256,
        "job_ordinal": job["job_ordinal"],
        "cell_ordinal": job["cell_ordinal"],
        "stage_cell_ordinal": job["stage_cell_ordinal"],
        "stage": job["stage"],
        "seed": job["seed"],
        "arm": job["arm"],
        "arm_position": job["arm_position"],
        "arm_sha256": job["arm_sha256"],
        "phase": 1,
        "scientific_time_limit_seconds": 30,
        "max_iterations": 200,
    }
    for key, value in expected.items():
        if row.get(key) != value:
            raise WarehouseW3Error(f"W3 row differs from job at {key}")
    case = _entry(manifest["cases"], "stable_case_id", str(job["stable_case_id"]))
    if row.get("case_identity", {}).get("content_sha256") != case["content_sha256"]:
        raise WarehouseW3Error("W3 row case identity differs")
    workspace = _entry(manifest["workspaces"], "arm", str(job["arm"]))
    if row.get("workspace_tree_sha256") != workspace["tree"]["tree_sha256"]:
        raise WarehouseW3Error("W3 row workspace identity differs")
    fact = _initial_fact(manifest, job)
    if row.get("merge_pair_counts") != fact["merge_pair_counts"]:
        raise WarehouseW3Error("W3 row counter facts differ")
    if row.get("oracle") != {"feasible": True, "issue_codes": []}:
        raise WarehouseW3Error("W3 row is not Oracle feasible")
    if row.get("locked_groups", {}).get("split_group_count") != 0:
        raise WarehouseW3Error("W3 row split a locked group")
    if not _finite_tree(row):
        raise WarehouseW3Error("W3 row contains a nonfinite value")


def validate_replay_rows(
    manifest: Mapping[str, Any],
    manifest_sha256: str,
    row_bytes: Sequence[bytes],
    publication_identities: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate the exact 172-row ordered bijection without filesystem authority."""

    jobs = manifest["jobs"]
    if len(row_bytes) != len(jobs) or len(publication_identities) != len(jobs):
        raise WarehouseW3Error("W3 replay does not contain the exact job count")
    rows: list[dict[str, Any]] = []
    identities: list[dict[str, Any]] = []
    for job, data, raw_identity in zip(
        jobs, row_bytes, publication_identities, strict=True
    ):
        if type(data) is not bytes or not isinstance(raw_identity, Mapping):
            raise TypeError("W3 replay inputs have wrong types")
        row = decode_canonical_row(data)
        validate_row_static(row, manifest, manifest_sha256, job)
        identity = dict(raw_identity)
        expected_identity = {
            "job_ordinal": job["job_ordinal"],
            "opaque_publication_key": f"warehouse-w3-row-{job['job_ordinal']:03d}",
            "sha256": sha256_bytes(data),
            "size_bytes": len(data),
        }
        if identity != expected_identity:
            raise WarehouseW3Error("W3 generic publication identity differs")
        rows.append(row)
        identities.append(identity)
    if tuple(row["arm"] for row in rows) != tuple(job["arm"] for job in jobs):
        raise WarehouseW3Error("W3 replay row order differs from the frozen schedule")
    return rows, identities


__all__ = [
    "RAW_SCHEMA",
    "decode_canonical_row",
    "validate_closed_observation",
    "validate_replay_rows",
    "validate_row_static",
]
