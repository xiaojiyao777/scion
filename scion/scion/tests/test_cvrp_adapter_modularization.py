from __future__ import annotations

from scion.tests.cvrp_adapter_test_support import *

from scion.problems.cvrp import solution_checks, surface_rendering
from scion.problems.cvrp import adapter as cvrp_adapter_module
from scion.problems.cvrp.preview import common as preview_common
from scion.problems.cvrp.preview import dispatch as preview_dispatch
from scion.problems.cvrp.preview import synthetic as preview_synthetic


def test_cvrp_adapter_rendering_facade_delegates_to_surface_module(
    cvrp_adapter: ProblemAdapter,
) -> None:
    assert cvrp_adapter.render_problem_summary() == surface_rendering.render_problem_summary()
    assert cvrp_adapter.render_problem_object() == surface_rendering.render_problem_object()
    assert cvrp_adapter.render_solver_mechanics() == surface_rendering.render_solver_mechanics()
    assert (
        cvrp_adapter.render_operator_interface()
        == surface_rendering.render_operator_interface()
    )
    for surface_name in ("solver_design", "main_search_strategy", "unknown"):
        assert cvrp_adapter.render_research_surface_interface(
            surface_name
        ) == surface_rendering.render_research_surface_interface(surface_name)


def test_cvrp_adapter_solution_checks_facade_delegates_to_solution_module(
    cvrp_adapter: ProblemAdapter,
) -> None:
    inst = cvrp_adapter.load_instance(str(TINY_5))
    raw = _raw([[0, 1, 2, 0], [0, 3, 4, 0]])

    facade_artifact = cvrp_adapter.deserialize_solver_output(raw, inst)
    direct_artifact = solution_checks.deserialize_solver_output(raw, inst)

    assert facade_artifact.normalized_solution == direct_artifact.normalized_solution
    assert cvrp_adapter.check_solution_consistency(
        facade_artifact,
        inst,
    ) == solution_checks.check_solution_consistency(direct_artifact, inst)
    assert cvrp_adapter.check_feasibility(
        facade_artifact,
        inst,
    ) == solution_checks.check_feasibility(direct_artifact, inst)
    assert cvrp_adapter.recompute_objective(
        facade_artifact,
        inst,
    ) == solution_checks.recompute_objective(direct_artifact, inst)


def test_cvrp_adapter_keeps_legacy_private_solution_helper_imports() -> None:
    assert cvrp_adapter_module._normalize_route([0, 1, 2, 0], 0) == (1, 2)
    assert cvrp_adapter_module._extract_reported_objective(
        {"cost": 7.5, "fleet_violation": 1, "total_distance": 8.0}
    ) == {"fleet_violation": 1, "total_distance": 8.0}


def test_cvrp_adapter_preview_facade_delegates_to_preview_package(
    cvrp_adapter: ProblemAdapter,
) -> None:
    patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    solution = context.nearest_neighbor()\n"
            "    context.record_iteration('preview_probe', 1)\n"
            "    context.record_move('preview_probe', attempted=1, accepted=0)\n"
            "    return solution\n"
        ),
    )
    surface = SimpleNamespace(name="solver_design")

    assert cvrp_adapter.preview_research_surface_patch(
        patch=patch,
        surface=surface,
    ) == preview_dispatch.preview_research_surface_patch(
        patch=patch,
        surface=surface,
    )


def test_cvrp_adapter_preview_facade_preserves_timeout_monkeypatch_compatibility(
    cvrp_adapter: ProblemAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cvrp_adapter_module, "_POLICY_PREVIEW_TIME_LIMIT_SEC", 1.25)
    monkeypatch.setattr(cvrp_adapter_module, "_POLICY_PREVIEW_EXEC_TIMEOUT_SEC", 0.75)

    cvrp_adapter.preview_research_surface_patch(
        patch=PatchProposal(
            file_path="policies/baseline_modules/config.py",
            action="modify",
            code_content="VALUE = 1\n",
        ),
    )

    assert preview_common._POLICY_PREVIEW_TIME_LIMIT_SEC == 1.25
    assert preview_synthetic._POLICY_PREVIEW_TIME_LIMIT_SEC == 1.25
    assert preview_synthetic._POLICY_PREVIEW_EXEC_TIMEOUT_SEC == 0.75


def test_cvrp_adapter_preview_rejects_removed_legacy_surfaces(
    cvrp_adapter: ProblemAdapter,
) -> None:
    preview = cvrp_adapter.preview_research_surface_patch(
        patch=PatchProposal(
            file_path="policies/baseline_policy.py",
            action="modify",
            code_content="def baseline_params(instance, time_limit_sec):\n    return {}\n",
        ),
        surface=SimpleNamespace(name="baseline_policy"),
    )

    assert preview["passed"] is False
    assert preview["active_research_surface"] is False
    assert preview["legacy_surface"] is False
    assert "not an active CVRP research surface" in json.dumps(preview["issues"])
