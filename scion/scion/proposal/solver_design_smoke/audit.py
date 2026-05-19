"""Runtime telemetry audit helpers for solver-design smoke."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from scion.problem.bridge import legacy_problem_spec_from_v1

from .utils import _attr

if TYPE_CHECKING:
    from scion.proposal.tools import ProposalToolContext
else:
    ProposalToolContext = Any


def _runtime_smoke_audit_failure(
    raw: Mapping[str, Any],
    *,
    context: ProposalToolContext,
    selected_surface: str,
) -> Mapping[str, Any] | None:
    from scion.runtime.audit import runtime_audit_failure_from_raw

    problem_spec = _problem_spec_for_runtime_audit(context.problem_spec)
    return runtime_audit_failure_from_raw(
        raw,
        problem_spec=problem_spec,
        selected_surface=selected_surface,
    )


def _problem_spec_for_runtime_audit(problem_spec: Any) -> Any:
    if (
        str(_attr(problem_spec, "spec_version", "") or "") == "problem-v1"
        and _attr(problem_spec, "id") is not None
    ):
        return legacy_problem_spec_from_v1(problem_spec)
    return problem_spec


def _compact_runtime_smoke_payload(runtime: Any) -> dict[str, Any]:
    if not isinstance(runtime, Mapping):
        return {}
    keys = (
        "solver_algorithm_path",
        "solver_algorithm_loaded",
        "solver_algorithm_active",
        "solver_algorithm_errors",
        "solver_algorithm_events",
        "solver_algorithm_elapsed_ms",
        "solver_algorithm_solution_valid",
        "solver_algorithm_total_distance",
        "solver_algorithm_fleet_violation",
        "solver_algorithm_baseline_calls",
        "solver_algorithm_baseline_errors",
        "solver_algorithm_search_iterations",
        "solver_algorithm_move_attempts",
        "solver_algorithm_accepted_moves",
        "solver_algorithm_improving_moves",
        "solver_algorithm_neutral_accepted_moves",
        "solver_algorithm_best_improving_moves",
        "solver_algorithm_best_delta",
        "solver_algorithm_phase_delta_sum",
        "solver_algorithm_phase_best_delta",
        "solver_algorithm_phase_improvement_counts",
        "solver_algorithm_stop_reason",
    )
    return {key: runtime.get(key) for key in keys if key in runtime}


def _compact_runtime_audit_failure(value: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "error_category",
        "detail",
        "failed_runtime_fields",
        "solver_algorithm_errors",
        "solver_algorithm_events",
    )
    return {key: value.get(key) for key in keys if key in value}
