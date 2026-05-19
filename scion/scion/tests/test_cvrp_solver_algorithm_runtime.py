from __future__ import annotations

from scion.tests.cvrp_solver_runtime_support import *
from scion.runtime.audit import (
    format_runtime_audit_failure,
    runtime_audit_failure_from_runtime,
)


def test_solver_design_surface_declares_active_algorithm_runtime_fields(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        selected_surface="solver_design",
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    surface = next(
        surface
        for surface in spec_v1.research_surfaces or []
        if surface.name == "solver_design"
    )
    required_fields = tuple(surface.evidence.required_runtime_fields)

    assert "solver_algorithm_loaded" in required_fields
    assert "solver_algorithm_active" in required_fields
    assert "solver_algorithm_phase_runtime_ms" in required_fields
    assert set(required_fields).issubset(runtime)
    assert runtime["solver_algorithm_path"] == "policies/baseline_algorithm.py"
    assert runtime["solver_algorithm_loaded"] is True
    assert runtime["solver_algorithm_active"] is True
    assert runtime["solver_algorithm_errors"] == 0
    assert runtime["solver_algorithm_solution_valid"] is True
    assert runtime["solver_algorithm_solution_routes"] >= 1
    assert runtime["solver_algorithm_total_distance"] > 0
    assert runtime["solver_algorithm_stop_reason"] != "inactive"
    assert raw["feasible"] is True
    assert runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="solver_design",
    ) is None


def test_solver_design_baseline_algorithm_exception_fails_selected_surface(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "baseline_algorithm.py").write_text(
        "\n".join(
            [
                "def solve(instance, rng, time_limit_sec, context):",
                "    raise RuntimeError('baseline body failed')",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        selected_surface="solver_design",
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    issue = runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="solver_design",
    )

    assert runtime["solver_algorithm_path"] == "policies/baseline_algorithm.py"
    assert runtime["solver_algorithm_loaded"] is True
    assert runtime["solver_algorithm_active"] is False
    assert runtime["solver_algorithm_errors"] == 1
    assert runtime["solver_algorithm_stop_reason"] == "exception"
    assert "baseline body failed" in json.dumps(runtime["solver_algorithm_events"])
    assert issue is not None
    assert issue["error_category"] == "solver_algorithm_runtime_error"
    assert issue["solver_algorithm_errors"] == 1
    assert "baseline body failed" in format_runtime_audit_failure(issue)


def test_solver_design_runtime_audit_rejects_inconsistent_phase_runtime() -> None:
    issue = runtime_audit_failure_from_runtime(
        {
            "solver_algorithm_errors": 0,
            "solver_algorithm_elapsed_ms": 1000,
            "solver_algorithm_phase_runtime_ms": {
                "search": 500,
                "bad_phase": 100000,
            },
        },
    )

    assert issue is not None
    assert issue["error_category"] == "solver_algorithm_runtime_telemetry_error"
    assert issue["solver_algorithm_phase"] == "bad_phase"
    assert "record_phase expects per-phase elapsed delta" in (
        format_runtime_audit_failure(issue)
    )


def test_active_baseline_algorithm_ignores_deleted_legacy_policy_hooks(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "baseline_algorithm.py").write_text(
        "\n".join(
            [
                "def solve(instance, rng, time_limit_sec, context):",
                "    solution = context.nearest_neighbor()",
                "    context.record_phase('candidate_construct', 1)",
                "    context.record_iteration('candidate_probe', 1)",
                "    context.record_move('candidate_probe', attempted=1, accepted=0)",
                "    context.set_stop_reason('candidate_completed')",
                "    return solution",
                "",
            ]
        ),
        encoding="utf-8",
    )
    legacy_files = {
        "solver_algorithm.py": "def solve(*args, **kwargs):\n    raise RuntimeError('legacy solver hook should not run')\n",
        "search_policy.py": "def baseline_time_fraction(*args, **kwargs):\n    raise RuntimeError('legacy search policy should not run')\n",
        "construction_policy.py": "def construction_mode(*args, **kwargs):\n    raise RuntimeError('legacy construction policy should not run')\n",
        "main_search_strategy.py": "def main_search_plan(*args, **kwargs):\n    raise RuntimeError('legacy main search should not run')\n",
    }
    for name, body in legacy_files.items():
        (workspace / "policies" / name).write_text(body, encoding="utf-8")

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        selected_surface="solver_design",
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)

    assert runtime["solver_algorithm_path"] == "policies/baseline_algorithm.py"
    assert runtime["solver_algorithm_loaded"] is True
    assert runtime["solver_algorithm_active"] is True
    assert runtime["solver_algorithm_errors"] == 0
    assert runtime["solver_algorithm_stop_reason"] == "candidate_completed"
    assert runtime["solver_algorithm_search_iterations"] == 1
    assert runtime["solver_algorithm_move_attempts"] == 1
    assert runtime["solver_algorithm_solution_valid"] is True
    assert "candidate_construct" in runtime["solver_algorithm_phase_runtime_ms"]
    rendered_runtime = json.dumps(runtime)
    assert "legacy solver hook should not run" not in rendered_runtime
    assert "legacy search policy should not run" not in rendered_runtime
    assert "legacy construction policy should not run" not in rendered_runtime
    assert "legacy main search should not run" not in rendered_runtime
    assert runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="solver_design",
    ) is None


def test_solver_design_context_exposes_objective_and_budget_helpers(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "baseline_algorithm.py").write_text(
        "\n".join(
            [
                "def solve(instance, rng, time_limit_sec, context):",
                "    solution = context.nearest_neighbor()",
                "    objective = context.objective(solution)",
                "    assert context.objective_key(solution) == (objective[0], objective[1])",
                "    assert context.is_valid(solution)",
                "    assert context.remaining_time() >= 0.0",
                "    assert context.remaining_time_ms() >= 0",
                "    context.record_iteration('objective_probe', 1)",
                "    context.record_move('objective_probe', attempted=1, accepted=0)",
                "    return context.make_solution(solution.routes)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        selected_surface="solver_design",
    )
    runtime = raw["runtime"]

    assert runtime["solver_algorithm_active"] is True
    assert runtime["solver_algorithm_errors"] == 0
    assert runtime["solver_algorithm_search_iterations"] == 1
    assert runtime["solver_algorithm_move_attempts"] == 1
    assert runtime["solver_algorithm_accepted_moves"] == 0
    assert runtime["solver_algorithm_neutral_accepted_moves"] == 0
    assert runtime["solver_algorithm_improving_moves"] == 0
    assert runtime["solver_algorithm_phase_improvement_counts"]["objective_probe"] == 0
    assert runtime["solver_algorithm_solution_valid"] is True
