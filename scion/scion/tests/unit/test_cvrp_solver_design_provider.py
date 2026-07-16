from __future__ import annotations

from scion.problem.bridge import load_problem_spec_v1_from_yaml
from scion.problem.providers import resolve_solver_design_prompt_provider
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.solver_design.manifest import (
    SOLVER_DESIGN_API_MANIFEST_FILES,
)
from scion.tests.unit.research_surface_helpers import _CVRP_ROOT


def _provider():
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    adapter = CvrpAdapter(spec)
    return resolve_solver_design_prompt_provider(problem_spec=spec, adapter=adapter)


def test_cvrp_adapter_registers_direct_solver_design_guidance() -> None:
    provider = _provider()

    assert provider is not None
    assert tuple(provider.solver_design_api_manifest_files()) == (
        SOLVER_DESIGN_API_MANIFEST_FILES
    )


def test_cvrp_hypothesis_guidance_is_open_and_algorithm_owned() -> None:
    rendered = "\n".join(_provider().solver_design_hypothesis_guidance({}))

    assert "No prepared file or mechanism is mandatory" in rendered
    assert "CVRP-owned causal path" in rendered
    assert "paired and case-level total_distance" in rendered
    assert "confidence interval, and MDE" in rendered
    assert "generic Scion core" in rendered
    assert "nearest reviewed mechanism" not in rendered
    assert "CMT2/CMT4" not in rendered
    assert "target-intent" not in rendered
    assert "read_active_solver_map" not in rendered


def test_cvrp_code_constraints_expose_real_source_and_object_model() -> None:
    constraints = _provider().active_subject_code_constraints(surface="solver_design")
    assert constraints is not None
    rendered = repr(constraints)

    assert "policies/baseline_algorithm.py::solve" in rendered
    assert "source ledger" in rendered
    assert "_Solution.routes" in rendered
    assert "_Route" in rendered
    assert "record_move" not in rendered
    assert "solver-provided time limit" in rendered
    assert "agentic_code_scope_control" not in rendered


def test_cvrp_target_module_guidance_matches_mechanism_ownership() -> None:
    provider = _provider()

    destroy_repair_guidance = provider.solver_design_target_api_guidance(
        "policies/baseline_modules/destroy_repair.py"
    )
    assert "destroy and repair operators" in destroy_repair_guidance
    assert "monotonic deadline context" in destroy_repair_guidance
    assert "remaining_time" in destroy_repair_guidance
    assert "recursive searches" in destroy_repair_guidance
    assert "partial repair" in destroy_repair_guidance
    assert "_default_vns_operators" in provider.solver_design_target_api_guidance(
        "policies/baseline_modules/local_search.py"
    )
    assert "Scheduler owns" in provider.solver_design_target_api_guidance(
        "policies/baseline_modules/scheduler.py"
    )


def test_cvrp_code_guidance_has_no_scope_caps_or_smoke_repair_path() -> None:
    provider = _provider()
    rendered = "\n".join(
        (
            *provider.solver_design_code_rules({}),
            *provider.solver_design_scope_guidance(
                {}, mode="direct_v3", broad_terms=("alns", "vns")
            ),
            *provider.solver_design_user_constraints({}),
        )
    )

    assert "one coherent executable causal path" in rendered
    assert "line" not in rendered.lower() or "entrypoint" in rendered.lower()
    assert "agentic_code_scope_control" not in rendered
    assert "smoke" not in rendered.lower()
    assert "retry" not in rendered.lower()
    assert "top-n" not in rendered.lower()
