from __future__ import annotations

from types import SimpleNamespace

from scion.config.problem import (
    ProblemSpec,
    SearchSpace,
)
from scion.contract.gate import ContractGate
from scion.core.models import PatchProposal
from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.tests.unit.research_surface_helpers import _CVRP_ROOT


def test_c9c_uses_v2_surface_complexity_scale_terms_for_dummy_problem() -> None:
    spec = ProblemSpec(
        name="dummy",
        root_dir="/tmp/dummy",
        operator_categories=["dispatch_policy"],
        research_surfaces=[
            SimpleNamespace(
                name="dispatch_policy",
                kind="policy",
                targets=SimpleNamespace(
                    files=["policies/dispatch.py"],
                    create_new_allowed=False,
                    modify_allowed=True,
                    remove_allowed=False,
                    singleton=True,
                ),
                bounds=SimpleNamespace(complexity_scale_terms=["item_count"]),
            ),
        ],
        search_space=SearchSpace(
            editable=["policies/*.py"],
            frozen=[],
            import_whitelist=["itertools"],
        ),
    )
    gate = ContractGate(spec)
    uses_declared_scale = PatchProposal(
        file_path="policies/dispatch.py",
        action="modify",
        code_content=(
            "def select_limit(instance, time_limit_sec):\n"
            "    for a in item_count:\n"
            "        for b in item_count:\n"
            "            for c in item_count:\n"
            "                pass\n"
            "    return 1\n"
        ),
    )
    uses_unrelated_legacy_word = PatchProposal(
        file_path="policies/dispatch.py",
        action="modify",
        code_content=(
            "def select_limit(instance, time_limit_sec):\n"
            "    for a in customers:\n"
            "        for b in customers:\n"
            "            for c in customers:\n"
            "                pass\n"
            "    return 1\n"
        ),
    )

    declared = gate._c9c_complexity_bound(uses_declared_scale)
    unrelated = gate._c9c_complexity_bound(uses_unrelated_legacy_word)

    assert not declared.passed
    assert "three-level problem-scale nested loops" in declared.detail
    assert unrelated.passed


def test_cvrp_solver_algorithm_complexity_allows_bounded_algorithm_while_patterns() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    legacy = legacy_problem_spec_from_v1(spec_v1)
    gate = ContractGate(legacy)
    patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    unvisited = set(instance.customer_ids)\n"
            "    routes = []\n"
            "    while unvisited:\n"
            "        route = []\n"
            "        load = 0\n"
            "        while unvisited:\n"
            "            best = None\n"
            "            for customer in sorted(unvisited):\n"
            "                if load + instance.demands[customer] <= instance.capacity:\n"
            "                    best = customer\n"
            "                    break\n"
            "            if best is None:\n"
            "                break\n"
            "            unvisited.remove(best)\n"
            "            route.append(best)\n"
            "            load += instance.demands[best]\n"
            "        if route:\n"
            "            routes.append(route)\n"
            "    max_rounds = min(20, instance.customer_count)\n"
            "    round_idx = 0\n"
            "    while round_idx < max_rounds:\n"
            "        round_idx += 1\n"
            "    improved = True\n"
            "    pass_count = 0\n"
            "    while improved:\n"
            "        pass_count += 1\n"
            "        improved = False\n"
            "        if pass_count > 30:\n"
            "            break\n"
            "    return context.make_solution(routes)\n"
        ),
    )

    c9c = gate._c9c_complexity_bound(patch, selected_surface="solver_design")

    assert c9c.passed


def test_cvrp_solver_algorithm_complexity_allows_prior_capped_collection_growth() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    legacy = legacy_problem_spec_from_v1(spec_v1)
    gate = ContractGate(legacy)
    patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    routes = [list(instance.customer_ids)]\n"
            "    customers = list(instance.customer_ids)\n"
            "    q = max(0, min(q, len(customers)))\n"
            "    removed = []\n"
            "    while len(removed) < q:\n"
            "        if not customers:\n"
            "            break\n"
            "        removed.append(customers.pop())\n"
            "    return context.make_solution(routes)\n"
        ),
    )

    c9c = gate._c9c_complexity_bound(patch, selected_surface="solver_design")

    assert c9c.passed


def test_cvrp_solver_algorithm_complexity_allows_local_runtime_guard_helper() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    legacy = legacy_problem_spec_from_v1(spec_v1)
    gate = ContractGate(legacy)
    patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    routes = [list(instance.customer_ids)]\n"
            "    iteration = 0\n"
            "    while _within_budget(context):\n"
            "        iteration += 1\n"
            "        context.record_iteration('search', 1)\n"
            "        if iteration >= 10:\n"
            "            return context.make_solution(routes)\n"
            "    return context.make_solution(routes)\n"
            "\n"
            "def _within_budget(context):\n"
            "    return context.remaining_time() > 0.05\n"
        ),
    )

    c9c = gate._c9c_complexity_bound(patch, selected_surface="solver_design")

    assert c9c.passed


def test_cvrp_solver_algorithm_complexity_rejects_unbounded_improvement_flag_loop() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    legacy = legacy_problem_spec_from_v1(spec_v1)
    gate = ContractGate(legacy)
    patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    routes = [list(instance.customer_ids)]\n"
            "    improved = True\n"
            "    while improved:\n"
            "        improved = False\n"
            "        for route in routes:\n"
            "            if len(route) > 3:\n"
            "                improved = True\n"
            "    return context.make_solution(routes)\n"
        ),
    )

    c9c = gate._c9c_complexity_bound(patch, selected_surface="solver_design")

    assert not c9c.passed
    assert "uncapped while loop" in c9c.detail
    assert "condition='improved'" in c9c.detail
    assert "iteration cap" in c9c.detail


def test_cvrp_solver_algorithm_complexity_rejects_fake_runtime_guard_helper() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    legacy = legacy_problem_spec_from_v1(spec_v1)
    gate = ContractGate(legacy)
    patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    routes = [list(instance.customer_ids)]\n"
            "    while always(context):\n"
            "        pass\n"
            "    return context.make_solution(routes)\n"
            "\n"
            "def always(context):\n"
            "    context.remaining_time()\n"
            "    return True\n"
        ),
    )

    c9c = gate._c9c_complexity_bound(patch, selected_surface="solver_design")

    assert not c9c.passed
    assert "uncapped while loop" in c9c.detail
    assert "condition='always(context)'" in c9c.detail
    assert "runtime guard" in c9c.detail
