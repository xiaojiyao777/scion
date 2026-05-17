from __future__ import annotations

from pathlib import Path

from scion.contract.gate import ContractGate
from scion.core.models import (
    HypothesisProposal,
    PatchProposal,
)
from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.tests.unit.research_surface_helpers import (
    _CVRP_ROOT,
    _main_search_strategy_code,
)


def test_cvrp_construction_policy_contract_targets_and_required_functions() -> None:
    spec = load_problem_spec_v1_from_yaml(
        Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem-v1.yaml"
    )
    gate = ContractGate(legacy_problem_spec_from_v1(spec))

    remove_hypothesis = HypothesisProposal(
        hypothesis_text="Remove the construction policy.",
        change_locus="construction_policy",
        action="remove",
        target_file="policies/construction_policy.py",
    )
    remove_result = gate.validate_hypothesis(remove_hypothesis, [], [])
    c3 = next(check for check in remove_result.checks if check.name == "C3_action_target")
    assert not c3.passed
    assert "not allowed" in c3.detail

    wrong_target = HypothesisProposal(
        hypothesis_text="Modify construction through an operator file.",
        change_locus="construction_policy",
        action="modify",
        target_file="operators/not_construction.py",
    )
    wrong_target_result = gate.validate_hypothesis(wrong_target, [], [])
    c3 = next(
        check for check in wrong_target_result.checks if check.name == "C3_action_target"
    )
    assert not c3.passed
    assert "policies/construction_policy.py" in c3.detail

    missing_patch = PatchProposal(
        file_path="policies/construction_policy.py",
        action="modify",
        code_content=(
            "def construction_mode(instance, time_limit_sec):\n"
            "    return 'nearest_neighbor'\n"
        ),
    )
    missing_result = gate.validate_patch(missing_patch)
    c7 = next(check for check in missing_result.checks if check.name == "C7_interface")
    assert not c7.passed
    assert "missing required functions ['construction_bias']" in c7.detail

    valid_patch = PatchProposal(
        file_path="policies/construction_policy.py",
        action="modify",
        code_content=(
            "def construction_mode(instance, time_limit_sec):\n"
            "    return 'nearest_neighbor'\n\n"
            "def construction_bias(instance, time_limit_sec):\n"
            "    return 0.0\n"
        ),
    )
    valid_result = gate.validate_patch(valid_patch)
    c7 = next(check for check in valid_result.checks if check.name == "C7_interface")
    assert c7.passed


def test_cvrp_neighborhood_portfolio_contract_targets_and_required_functions() -> None:
    spec = load_problem_spec_v1_from_yaml(
        Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem-v1.yaml"
    )
    gate = ContractGate(legacy_problem_spec_from_v1(spec))

    create_hypothesis = HypothesisProposal(
        hypothesis_text="Create a second portfolio policy.",
        change_locus="neighborhood_portfolio",
        action="create_new",
        target_file="policies/other_portfolio.py",
    )
    create_result = gate.validate_hypothesis(create_hypothesis, [], [])
    c3 = next(check for check in create_result.checks if check.name == "C3_action_target")
    assert not c3.passed
    assert "not allowed" in c3.detail

    wrong_target = HypothesisProposal(
        hypothesis_text="Modify portfolio through an operator file.",
        change_locus="neighborhood_portfolio",
        action="modify",
        target_file="operators/not_portfolio.py",
    )
    wrong_target_result = gate.validate_hypothesis(wrong_target, [], [])
    c3 = next(
        check for check in wrong_target_result.checks if check.name == "C3_action_target"
    )
    assert not c3.passed
    assert "policies/neighborhood_portfolio.py" in c3.detail

    missing_patch = PatchProposal(
        file_path="policies/neighborhood_portfolio.py",
        action="modify",
        code_content=(
            "def enabled_components(instance, time_limit_sec):\n"
            "    return ['route_local']\n"
        ),
    )
    missing_result = gate.validate_patch(missing_patch)
    c7 = next(check for check in missing_result.checks if check.name == "C7_interface")
    assert not c7.passed
    assert "missing required functions ['component_weights', 'candidate_limits']" in c7.detail

    valid_patch = PatchProposal(
        file_path="policies/neighborhood_portfolio.py",
        action="modify",
        code_content=(
            "def enabled_components(instance, time_limit_sec):\n"
            "    return ['route_local']\n\n"
            "def component_weights(instance, time_limit_sec):\n"
            "    return {'route_local': 1.0}\n\n"
            "def candidate_limits(instance, time_limit_sec):\n"
            "    return {'top_k': 1}\n"
        ),
    )
    valid_result = gate.validate_patch(valid_patch)
    c7 = next(check for check in valid_result.checks if check.name == "C7_interface")
    assert c7.passed


def test_cvrp_main_search_strategy_contract_targets_and_required_functions() -> None:
    spec = load_problem_spec_v1_from_yaml(
        Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem-v1.yaml"
    )
    gate = ContractGate(legacy_problem_spec_from_v1(spec))

    create_hypothesis = HypothesisProposal(
        hypothesis_text="Create a second solver algorithm.",
        change_locus="solver_design",
        action="create_new",
        target_file="policies/other_solver_algorithm.py",
    )
    create_result = gate.validate_hypothesis(create_hypothesis, [], [])
    c3 = next(check for check in create_result.checks if check.name == "C3_action_target")
    assert not c3.passed
    assert "is not in target files" in c3.detail
    assert "policies/baseline_modules/*.py" in c3.detail

    create_module_hypothesis = HypothesisProposal(
        hypothesis_text="Add a focused solver-design construction helper.",
        change_locus="solver_design",
        action="create_new",
        target_file="policies/baseline_modules/construction_variant.py",
        predicted_direction="improve",
        target_objectives=("total_distance",),
        novelty_signature={
            "algorithm_family": "alns_vns_module_variant",
            "construction_strategy": "capacity_seeded_sweep",
            "improvement_strategy": "reuse_existing_vns",
            "acceptance_strategy": "reuse_existing_acceptance",
            "runtime_budget_strategy": "bounded_existing_scheduler",
        },
    )
    create_module_result = gate.validate_hypothesis(
        create_module_hypothesis,
        [],
        [],
    )
    c3 = next(
        check for check in create_module_result.checks if check.name == "C3_action_target"
    )
    assert c3.passed
    assert create_module_result.passed

    wrong_target = HypothesisProposal(
        hypothesis_text="Modify solver algorithm through an operator file.",
        change_locus="solver_design",
        action="modify",
        target_file="operators/not_strategy.py",
    )
    wrong_target_result = gate.validate_hypothesis(wrong_target, [], [])
    c3 = next(
        check for check in wrong_target_result.checks if check.name == "C3_action_target"
    )
    assert not c3.passed
    assert "policies/baseline_algorithm.py" in c3.detail
    assert "policies/solver_algorithm.py" in c3.detail
    assert "policies/baseline_modules/*.py" in c3.detail

    missing_patch = PatchProposal(
        file_path="policies/solver_algorithm.py",
        action="modify",
        code_content="def helper(instance, rng, time_limit_sec, context):\n    return None\n",
    )
    missing_result = gate.validate_patch(missing_patch)
    c7 = next(check for check in missing_result.checks if check.name == "C7_interface")
    assert not c7.passed
    assert "missing required functions ['solve']" in c7.detail

    valid_patch = PatchProposal(
        file_path="policies/solver_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    return context.nearest_neighbor()\n"
        ),
    )
    valid_result = gate.validate_patch(valid_patch)
    c7 = next(check for check in valid_result.checks if check.name == "C7_interface")
    assert c7.passed

    module_patch = PatchProposal(
        file_path="policies/baseline_modules/local_search.py",
        action="modify",
        code_content=(
            "from __future__ import annotations\n\n"
            "def helper():\n"
            "    return 'bounded local search helper'\n"
        ),
    )
    module_result = gate.validate_patch(module_patch)
    c7 = next(check for check in module_result.checks if check.name == "C7_interface")
    assert c7.passed
    assert "deferred to workspace smoke" in c7.detail

    delete_module_hypothesis = HypothesisProposal(
        hypothesis_text="Remove an unused solver-design helper module.",
        change_locus="solver_design",
        action="remove",
        target_file="policies/baseline_modules/obsolete_helper.py",
        predicted_direction="improve",
        target_objectives=("total_distance",),
        novelty_signature={
            "algorithm_family": "alns_vns_module_cleanup",
            "construction_strategy": "unchanged",
            "improvement_strategy": "remove_unused_helper",
            "acceptance_strategy": "unchanged",
            "runtime_budget_strategy": "reduce_import_surface",
        },
    )
    delete_module_patch = PatchProposal(
        file_path="policies/baseline_modules/obsolete_helper.py",
        action="delete",
        code_content="",
    )
    delete_module_result = gate.validate_patch(
        delete_module_patch,
        approved_hypothesis=delete_module_hypothesis,
    )
    c4b = next(
        check
        for check in delete_module_result.checks
        if check.name == "C4b_patch_action_target"
    )
    assert c4b.passed
    assert delete_module_result.passed


def test_contract_gate_rejects_main_search_strategy_read_only_open() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    gate = ContractGate(legacy_problem_spec_from_v1(spec))

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/main_search_strategy.py",
            action="modify",
            code_content=_main_search_strategy_code(
                "    data = open('/tmp/external_results.json', 'r').read()\n"
            ),
        )
    )

    c9 = next(check for check in result.checks if check.name == "C9_sensitive_api")
    assert not c9.passed
    assert "open" in c9.detail
    assert not result.passed


def test_contract_gate_rejects_main_search_strategy_path_read_text() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    gate = ContractGate(legacy_problem_spec_from_v1(spec))

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/main_search_strategy.py",
            action="modify",
            code_content=(
                "from pathlib import Path\n\n"
                + _main_search_strategy_code(
                    "    data = Path('/tmp/external_results.json').read_text()\n"
                )
            ),
        )
    )

    c9 = next(check for check in result.checks if check.name == "C9_sensitive_api")
    assert not c9.passed
    assert "read_text" in c9.detail
    assert not result.passed


def test_contract_gate_rejects_instance_name_on_main_search_strategy() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    gate = ContractGate(legacy_problem_spec_from_v1(spec))

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/main_search_strategy.py",
            action="modify",
            code_content=_main_search_strategy_code(
                "    if instance.name == 'X-n101-k25':\n"
                "        return {'enabled': False}\n"
            ),
        )
    )

    c9d = next(
        check for check in result.checks if check.name == "C9d_surface_instance_identity"
    )
    assert not c9d.passed
    assert "instance.name" in c9d.detail
    assert not result.passed


def test_contract_gate_rejects_instance_name_on_search_policy() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    gate = ContractGate(legacy_problem_spec_from_v1(spec))

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/search_policy.py",
            action="modify",
            code_content=(
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    if instance.name == 'X-n101-k25':\n"
                "        return 0.95\n"
                "    return 0.8\n\n"
                "def max_operator_rounds(instance, time_limit_sec):\n"
                "    return 20\n\n"
                "def enable_post_baseline_operators(instance, time_limit_sec):\n"
                "    return True\n"
            ),
        )
    )

    c9d = next(
        check for check in result.checks if check.name == "C9d_surface_instance_identity"
    )
    assert not c9d.passed
    assert "instance.name" in c9d.detail
    assert not result.passed


def test_contract_gate_rejects_getattr_instance_name_on_search_policy() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    gate = ContractGate(legacy_problem_spec_from_v1(spec))

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/search_policy.py",
            action="modify",
            code_content=(
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    return 0.95 if getattr(instance, 'name') == 'X-n101-k25' else 0.8\n\n"
                "def max_operator_rounds(instance, time_limit_sec):\n"
                "    return 20\n\n"
                "def enable_post_baseline_operators(instance, time_limit_sec):\n"
                "    return True\n"
            ),
        )
    )

    c9d = next(
        check for check in result.checks if check.name == "C9d_surface_instance_identity"
    )
    assert not c9d.passed
    assert "getattr(instance, 'name')" in c9d.detail
    assert not result.passed


def test_contract_gate_rejects_instance_identity_reflection_on_search_policy() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    gate = ContractGate(legacy_problem_spec_from_v1(spec))

    cases = [
        ("return repr(instance)\n", "repr(instance)"),
        ("return str(instance)\n", "str(instance)"),
        ("return vars(instance).get('customer_count', 0)\n", "vars(instance)"),
        ("return instance.__dict__.get('customer_count', 0)\n", "instance.__dict__"),
        ("field = 'name'\n    return getattr(instance, field)\n", "getattr(instance"),
        (
            "import dataclasses\n    return dataclasses.asdict(instance).get('name')\n",
            "dataclasses.asdict",
        ),
    ]
    for body, expected in cases:
        result = gate.validate_patch(
            PatchProposal(
                file_path="policies/search_policy.py",
                action="modify",
                code_content=(
                    "def baseline_time_fraction(instance, time_limit_sec):\n"
                    f"    {body}\n"
                    "\n"
                    "def max_operator_rounds(instance, time_limit_sec):\n"
                    "    return 20\n\n"
                    "def enable_post_baseline_operators(instance, time_limit_sec):\n"
                    "    return True\n"
                ),
            )
        )

        c9d = next(
            check
            for check in result.checks
            if check.name == "C9d_surface_instance_identity"
        )
        assert not c9d.passed
        assert expected in c9d.detail
        assert not result.passed


def test_contract_gate_rejects_baseline_algorithm_context_baseline_call() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    gate = ContractGate(legacy_problem_spec_from_v1(spec))

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_algorithm.py",
            action="modify",
            code_content=(
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    return context.baseline(time_limit_sec=0.1)\n"
            ),
        ),
        selected_surface="solver_design",
    )

    c9 = next(check for check in result.checks if check.name == "C9_sensitive_api")
    assert not c9.passed
    assert "context.baseline" in c9.detail
    assert not result.passed


def test_contract_gate_allows_safe_policy_instance_api() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    gate = ContractGate(legacy_problem_spec_from_v1(spec))

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/search_policy.py",
            action="modify",
            code_content=(
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    scale = min(instance.customer_count, len(instance.customer_ids))\n"
                "    return 0.8 if scale >= 0 else 0.7\n\n"
                "def max_operator_rounds(instance, time_limit_sec):\n"
                "    first = instance.customer_ids[0]\n"
                "    demand = instance.demands[first] + instance.demand(first)\n"
                "    distance = instance.distance(instance.depot, first)\n"
                "    return 10 if demand + distance + instance.capacity >= 0 else 0\n\n"
                "def enable_post_baseline_operators(instance, time_limit_sec):\n"
                "    return True\n"
            ),
        )
    )

    c9 = next(check for check in result.checks if check.name == "C9_sensitive_api")
    c9d = next(
        check for check in result.checks if check.name == "C9d_surface_instance_identity"
    )
    assert c9.passed
    assert c9d.passed
    assert result.passed, result.failure_reason


def test_cvrp_default_policy_files_match_declared_signatures() -> None:
    root = Path(__file__).resolve().parents[2] / "problems" / "cvrp"
    spec = load_problem_spec_v1_from_yaml(root / "problem-v1.yaml")
    gate = ContractGate(legacy_problem_spec_from_v1(spec))

    for file_path in (
        "policies/search_policy.py",
        "policies/baseline_policy.py",
        "policies/construction_policy.py",
        "policies/neighborhood_portfolio.py",
        "policies/baseline_algorithm.py",
        "policies/solver_algorithm.py",
        "policies/baseline_modules/acceptance.py",
        "policies/baseline_modules/config.py",
        "policies/baseline_modules/construction.py",
        "policies/baseline_modules/destroy_repair.py",
        "policies/baseline_modules/local_search.py",
        "policies/baseline_modules/scheduler.py",
        "policies/baseline_modules/state.py",
        "policies/main_search_strategy.py",
        "policies/alns_vns_policy.py",
        "policies/destroy_repair_policy.py",
        "policies/route_pair_candidate_policy.py",
        "policies/acceptance_restart_policy.py",
    ):
        result = gate.validate_patch(
            PatchProposal(
                file_path=file_path,
                action="modify",
                code_content=(root / file_path).read_text(encoding="utf-8"),
            )
        )
        c7 = next(check for check in result.checks if check.name == "C7_interface")
        assert c7.passed, c7.detail


def test_cvrp_construction_policy_static_return_constraints_fail_bad_values() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    gate = ContractGate(legacy_problem_spec_from_v1(spec))

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/construction_policy.py",
            action="modify",
            code_content=(
                "def construction_mode(instance, time_limit_sec):\n"
                "    return 'savings'\n\n"
                "def construction_bias(instance, time_limit_sec):\n"
                "    return 2.5\n"
            ),
        )
    )

    c7 = next(check for check in result.checks if check.name == "C7_interface")
    assert not c7.passed
    assert "construction_mode" in c7.detail
