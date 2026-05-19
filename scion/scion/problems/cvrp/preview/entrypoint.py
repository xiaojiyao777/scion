"""Synthetic execution preview for the active CVRP solver entrypoint."""
from __future__ import annotations

import random
import types
from typing import Any

from scion.problems.cvrp.preview.synthetic import _synthetic_preview_instance
from scion.problems.cvrp.preview.synthetic import (
    _PolicyPreviewTimeout,
    _PreviewSolverAlgorithmContext,
    _call_solver_algorithm_preview,
    _coerce_preview_solution,
    _preview_solution_is_valid,
    _solver_algorithm_preview_instances,
)

def _preview_solver_entrypoint(
    module: types.ModuleType,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    func = getattr(module, "solve", None)
    if not callable(func):
        issues.append("missing callable solve")
        checks.append({"name": "solve", "passed": False, "detail": "missing callable"})
        return
    for preview_instance in _solver_algorithm_preview_instances(
        _synthetic_preview_instance()
    ):
        _preview_solver_entrypoint_case(func, preview_instance, issues, checks)

def _preview_solver_entrypoint_case(
    func: Any,
    instance: CvrpInstance,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    rng = random.Random(0)
    context = _PreviewSolverAlgorithmContext(instance, rng)
    check_name = (
        "solve" if instance.name == "synthetic_preview" else f"solve:{instance.name}"
    )
    try:
        raw_solution = _call_solver_algorithm_preview(
            func,
            instance=instance,
            rng=rng,
            context=context,
        )
    except _PolicyPreviewTimeout:
        detail = (
            f"{instance.name}: solve timed out during synthetic preview; "
            "solver_design candidates "
            "must use explicit bounded loops and poll context.remaining_time()"
        )
        issues.append(detail)
        checks.append({"name": check_name, "passed": False, "detail": detail})
        return
    except Exception as exc:
        detail = f"{instance.name}: solve raised during synthetic preview: {exc}"
        issues.append(detail)
        checks.append({"name": check_name, "passed": False, "detail": detail})
        return
    if raw_solution is None:
        detail = f"{instance.name}: solve returned None; solver entrypoint would be inactive"
        issues.append(detail)
        checks.append({"name": check_name, "passed": False, "detail": detail})
        return
    solution = _coerce_preview_solution(raw_solution)
    if solution is None:
        detail = f"{instance.name}: solve returned non-solution value"
        issues.append(detail)
        checks.append(
            {
                "name": check_name,
                "passed": False,
                "detail": f"{detail}: returned {type(raw_solution).__name__}",
            }
        )
        return
    valid, reason = _preview_solution_is_valid(instance, solution)
    solution_distance = sum(instance.route_distance(route) for route in solution.routes)
    preview_baseline = context.nearest_neighbor()
    preview_baseline_distance = sum(
        instance.route_distance(route) for route in preview_baseline.routes
    )
    delta_vs_preview_baseline = preview_baseline_distance - solution_distance
    body_has_search = (
        context.move_attempts > 0
        or context.accepted_moves > 0
        or context.search_iterations > 0
    )
    if valid and not body_has_search:
        valid = False
        reason = (
            "solver_design preview saw no active search telemetry; algorithm "
            "candidates must record bounded search effort with "
            "context.record_iteration or context.record_move"
        )
    checks.append(
        {
            "name": check_name,
            "passed": valid,
            "detail": (
                f"{instance.name}: routes={len(solution.routes)} "
                f"distance={solution_distance} "
                f"preview_baseline_distance={preview_baseline_distance} "
                f"delta_vs_preview_baseline={delta_vs_preview_baseline} "
                f"search_iterations={context.search_iterations} "
                f"move_attempts={context.move_attempts} "
                f"accepted_moves={context.accepted_moves}"
                if valid
                else f"{instance.name}: {reason}"
            ),
        }
    )
    if not valid:
        issues.append(
            f"{instance.name}: solve returned invalid synthetic solution: {reason}"
        )
