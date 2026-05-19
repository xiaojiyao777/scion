from __future__ import annotations

from scion.problems.cvrp.preview import synthetic as cvrp_preview_synthetic
from scion.tests.cvrp_adapter_test_support import *

def test_cvrp_solver_algorithm_preview_accepts_valid_solution(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    solution = context.nearest_neighbor()\n"
            "    context.record_phase('construct', 1)\n"
            "    context.record_iteration('construct_probe', 1)\n"
            "    context.record_move('construct_probe', attempted=1, accepted=0)\n"
            "    return solution\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="solver_design"),
    )

    assert preview["passed"] is True
    assert preview["surface"] == "solver_design"
    assert preview["issues"] == []
    check = next(
        check
        for check in preview["checks"]
        if check["name"] == "solve"
    )
    assert check["passed"] is True
    assert "routes=" in check["detail"]


def test_cvrp_solver_algorithm_preview_accepts_objective_helpers(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    seed = context.nearest_neighbor()\n"
            "    seed_obj = context.objective(seed)\n"
            "    best = seed\n"
            "    best_key = context.objective_key(best)\n"
            "    for route_index, route in enumerate(best.routes):\n"
            "        route = list(route)\n"
            "        for left in range(max(0, len(route) - 1)):\n"
            "            for right in range(left + 2, len(route) + 1):\n"
            "                context.record_iteration('two_opt_probe', 1)\n"
            "                new_route = route[:left] + list(reversed(route[left:right])) + route[right:]\n"
            "                routes = [list(candidate_route) for candidate_route in best.routes]\n"
            "                routes[route_index] = new_route\n"
            "                candidate = context.make_solution(routes)\n"
            "                if context.is_valid(candidate) and context.objective_key(candidate) < best_key:\n"
            "                    context.record_move('two_opt_probe', attempted=1, accepted=1, delta=1.0, best_improved=True)\n"
            "                    return candidate\n"
            "                context.record_move('two_opt_probe', attempted=1, accepted=0)\n"
            "    return best\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="solver_design"),
    )

    assert preview["passed"] is True
    assert preview["issues"] == []


def test_cvrp_solver_algorithm_preview_rejects_no_search_telemetry(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    return context.nearest_neighbor()\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="solver_design"),
    )

    assert preview["passed"] is False
    rendered = json.dumps(preview["issues"])
    assert "active search telemetry" in rendered


def test_cvrp_solver_design_preview_rejects_dynamic_private_state_attrs(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/baseline_modules/local_search.py",
        action="modify",
        code_content=(
            "def _vns(solution, operators, max_no_improve, context, reserve):\n"
            "    solution._nn_lists = {}\n"
            "    context.record_iteration('probe', 1)\n"
            "    context.record_move('probe', attempted=1, accepted=0)\n"
            "    return False\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="solver_design"),
    )

    assert preview["passed"] is False
    rendered = json.dumps(preview["issues"])
    assert "__slots__" in rendered
    assert "solution._nn_lists" not in rendered
    assert any(
        check["name"] == "solver_design_no_dynamic_state_private_attrs"
        and check["passed"] is False
        for check in preview["checks"]
    )


def test_cvrp_solver_design_preview_rejects_cumulative_record_phase_elapsed(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/baseline_modules/destroy_repair.py",
        action="modify",
        code_content=(
            "def _probe(solution, context):\n"
            "    context.record_phase('probe', context.elapsed_ms())\n"
            "    context.record_iteration('probe', 1)\n"
            "    context.record_move('probe', attempted=1, accepted=0)\n"
            "    return solution\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="solver_design"),
    )

    assert preview["passed"] is False
    rendered = json.dumps(preview["issues"])
    assert "record_phase expects a phase-duration delta" in rendered
    assert any(
        check["name"] == "solver_design_record_phase_uses_elapsed_delta"
        and check["passed"] is False
        for check in preview["checks"]
    )


def test_cvrp_solver_algorithm_preview_runs_canary_shaped_instance(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    if instance.customer_count > 3:\n"
            "        raise IndexError('split-only solver bug')\n"
            "    solution = context.nearest_neighbor()\n"
            "    context.record_phase('construct', 1)\n"
            "    context.record_iteration('construct_probe', 1)\n"
            "    context.record_move('construct_probe', attempted=1, accepted=0)\n"
            "    return solution\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="solver_design"),
    )

    assert preview["passed"] is False
    issues = json.dumps(preview["issues"])
    assert "synthetic_preview_canary_5" in issues
    assert "split-only solver bug" in issues
    assert any(
        check["name"] == "solve:synthetic_preview_canary_5"
        and check["passed"] is False
        for check in preview["checks"]
    )


def test_cvrp_solver_algorithm_preview_rejects_deleted_baseline_context_hook(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    return context.baseline(time_limit_sec=0.1)\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="solver_design"),
    )

    assert preview["passed"] is False
    assert "must not call context.baseline" in json.dumps(preview["issues"])


def test_cvrp_solver_algorithm_preview_bounds_remaining_time_guarded_loop(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    solution = context.nearest_neighbor()\n"
            "    iterations = 0\n"
            "    while context.remaining_time() > 0.5:\n"
            "        iterations += 1\n"
            "        context.record_iteration('guarded_loop', 1)\n"
            "    context.record_phase('guarded_loop', iterations)\n"
            "    context.record_move('guarded_loop', attempted=1, accepted=0)\n"
            "    return solution\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="solver_design"),
    )

    assert preview["passed"] is True
    assert preview["issues"] == []


def test_cvrp_baseline_algorithm_preview_rejects_remaining_time_ms_mixup(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    solution = context.nearest_neighbor()\n"
            "    budget_ms = float(time_limit_sec) * 1000.0\n"
            "    reserve = max(50.0, budget_ms * 0.03)\n"
            "    while context.remaining_time() > reserve:\n"
            "        break\n"
            "    return solution\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="solver_design"),
    )

    assert preview["passed"] is False
    rendered = json.dumps(preview["issues"])
    assert "context.remaining_time() returns seconds" in rendered
    assert "remaining_time_ms" in rendered
    assert any(
        check["name"] == "baseline_algorithm_remaining_time_units"
        and check["passed"] is False
        for check in preview["checks"]
    )


def test_cvrp_solver_algorithm_preview_exposes_remaining_time_ms_helper(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    solution = context.nearest_neighbor()\n"
            "    if context.remaining_time_ms() <= 0:\n"
            "        context.set_stop_reason('time_limit')\n"
            "    context.record_iteration('budget_probe', 1)\n"
            "    context.record_move('budget_probe', attempted=1, accepted=0)\n"
            "    return solution\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="solver_design"),
    )

    assert preview["passed"] is True
    assert preview["issues"] == []


def test_cvrp_solver_algorithm_preview_times_out_unbounded_solve(
    cvrp_adapter: ProblemAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert not issubclass(cvrp_preview_synthetic._PolicyPreviewTimeout, Exception)
    monkeypatch.setattr(cvrp_adapter_module, "_POLICY_PREVIEW_EXEC_TIMEOUT_SEC", 0.05)
    patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    while True:\n"
            "        pass\n"
            "    return context.nearest_neighbor()\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="solver_design"),
    )

    assert preview["passed"] is False
    assert "timed out during synthetic preview" in json.dumps(preview["issues"])


def test_cvrp_solver_algorithm_preview_rejects_infeasible_solution(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    return {'routes': [[1], [1]]}\n"
        ),
    )

    preview = cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=SimpleNamespace(name="solver_design"),
    )

    assert preview["passed"] is False
    assert "invalid synthetic solution" in json.dumps(preview["issues"])
