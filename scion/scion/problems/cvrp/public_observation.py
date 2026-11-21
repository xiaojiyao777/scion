"""CVRP-owned public inputs and execution declaration (no solver import)."""
from __future__ import annotations

from copy import deepcopy

from scion.problem.public_input import (
    PublicInputError, array, boolean, integer, number, object_fields, text,
)
from scion.problem.public_observation import JsonObject, PublicObservationSpec


class CvrpPublicObservationProvider:
    def source_config(self, available_files, *, initial):
        return {}

    def describe(self) -> PublicObservationSpec:
        # Entry modules are implemented in P1b; this is not an execution probe.
        return PublicObservationSpec(
            schema_version=1,
            fixture_paths=("data/tiny_development.json",),
            subject_workspace_paths=("policies",),
            subject_optional_workspace_paths=(),
            subject_package_paths=(
                "models.py", "adapter.py", "solution_checks.py", "cvrplib.py",
                "surface_policy.py", "surface_rendering.py", "surface_schema.py",
                "solver_runtime",
            ),
            checker_package_paths=("models.py", "solution_checks.py"),
            neutral_support_paths=(
                "problem/contracts.py", "problem/spec.py",
                "core/operator_interface.py", "runtime/telemetry_events.py",
            ),
            runner_module="scion.problems.cvrp.public_runner",
            checker_neutral_support_paths=("problem/contracts.py",),
            checker_module="scion.problems.cvrp.public_checker",
            input_description=(
                "Geometric JSON: name, capacity, depot, allowed_routes (int/null), "
                "use_integer_cost, nodes [{id,x,y,demand}]. No BKS or file paths."
            ),
            args_description="Exactly {time_limit_sec: positive finite number}.",
            subject_dependencies=("pydantic", "pydantic_core", "annotated_types", "typing_extensions.py", "typing_inspection"),
        )

    def validate_input(self, value: JsonObject) -> JsonObject:
        data = object_fields(value, {
            "name", "capacity", "depot", "allowed_routes", "use_integer_cost", "nodes",
        })
        text(data["name"], "$.name")
        capacity = integer(data["capacity"], "$.capacity", minimum=1)
        depot = integer(data["depot"], "$.depot")
        if data["allowed_routes"] is not None:
            integer(data["allowed_routes"], "$.allowed_routes", minimum=1)
        boolean(data["use_integer_cost"], "$.use_integer_cost")
        nodes = array(data["nodes"], "$.nodes")
        if len(nodes) < 2:
            raise PublicInputError("NODES_REQUIRED", "$.nodes")
        seen: set[int] = set()
        for index, node in enumerate(nodes):
            path = f"$.nodes[{index}]"
            object_fields(node, {"id", "x", "y", "demand"}, path)
            node_id = integer(node["id"], path + ".id")
            if node_id in seen:
                raise PublicInputError("DUPLICATE_NODE", path + ".id")
            seen.add(node_id)
            number(node["x"], path + ".x")
            number(node["y"], path + ".y")
            demand = integer(node["demand"], path + ".demand", minimum=0)
            if demand > capacity or (node_id == depot and demand != 0):
                raise PublicInputError("DEMAND_INVALID", path + ".demand")
        if depot not in seen:
            raise PublicInputError("DEPOT_MISSING", "$.depot")
        return deepcopy(data)

    def validate_args(self, value: JsonObject) -> JsonObject:
        data = object_fields(value, {"time_limit_sec"})
        number(data["time_limit_sec"], "$.time_limit_sec", positive=True)
        return deepcopy(data)

    def validate_source_config(self, value: JsonObject, available_files: tuple[str, ...]) -> JsonObject:
        return deepcopy(object_fields(value, set()))
