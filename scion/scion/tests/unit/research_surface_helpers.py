from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scion.config.problem import ProblemSpec, SearchSpace
from scion.contract.gate import ContractGate
from scion.core.models import HypothesisProposal
from scion.problems.cvrp.models import CvrpInstance, CvrpNode


_SCION_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_CVRP_ROOT = _SCION_PACKAGE_ROOT / "problems" / "cvrp"


def _problem_payload(root_dir: str) -> dict:
    return {
        "spec_version": "problem-v1",
        "id": "demo",
        "display_name": "Demo",
        "root_dir": root_dir,
        "search_space": {
            "editable": ["operators/*.py"],
            "frozen": ["solver.py"],
            "import_whitelist": ["math"],
        },
        "operator_interface": {
            "base_class_import": "scion.problems.demo.operators.base:DemoOperator",
            "execute_signature": "execute(self, solution, rng) -> Solution",
            "categories": [{"name": "local", "description": "local ops"}],
        },
        "objectives": [
            {
                "name": "cost",
                "direction": "minimize",
                "priority": 1,
                "tie_tolerance": 0.0,
            }
        ],
        "adapter": {
            "import_path": "scion.problems.demo.adapter:DemoAdapter",
            "api_version": "v1",
        },
    }


def _tiny_instance() -> CvrpInstance:
    return CvrpInstance(
        name="tiny",
        capacity=10,
        depot=0,
        nodes=(
            CvrpNode(id=0, x=0, y=0, demand=0),
            CvrpNode(id=1, x=1, y=0, demand=1),
        ),
    )


def _main_search_strategy_code(extra_body: str = "") -> str:
    return (
        "def main_search_plan(instance, time_limit_sec):\n"
        f"{extra_body}"
        "    return {\n"
        "        'enabled': False,\n"
        "        'problem_adaptation': {'strategy_family': 'balanced_lifecycle', 'instance_profile': {}, 'phase_objective': 'phase_best_distance', 'component_roles': {}, 'fallback_order': [], 'evidence_targets': ['main_search_component_phase_delta_sum']},\n"
        "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},\n"
        "        'construction': {'methods': ['nearest_neighbor'], 'keep_top_k': 1, 'bias': 0.0},\n"
        "        'baseline': {'time_fraction': 0.8, 'params': {}},\n"
        "        'improvement': {'enabled_components': [], 'rounds': 0, 'top_k': 16},\n"
        "        'acceptance': {'min_distance_improvement': 0.0},\n"
        "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},\n"
        "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},\n"
        "        'post_baseline_operators_enabled': False,\n"
        "        'operator_round_limit': 0,\n"
        "    }\n"
    )


def _surface_gate() -> ContractGate:
    spec = ProblemSpec(
        name="surface-demo",
        root_dir="/tmp/surface-demo",
        operator_categories=["local", "budget_policy"],
        research_surfaces=[
            SimpleNamespace(
                name="local",
                kind="operator",
                target_files=["operators/*.py"],
            ),
            SimpleNamespace(
                name="budget_policy",
                kind="policy",
                target_files=["policies/budget.py"],
                targets=SimpleNamespace(
                    files=["policies/budget.py"],
                    create_new_allowed=False,
                    modify_allowed=True,
                    remove_allowed=False,
                    singleton=True,
                ),
                novelty=SimpleNamespace(
                    strategy="semantic_signature",
                    signature_fields=["budget_pattern"],
                ),
            ),
        ],
        search_space=SearchSpace(
            editable=["operators/*.py", "policies/*.py"],
            frozen=[],
            import_whitelist=["math"],
        ),
    )
    return ContractGate(spec)


def _overlapping_surface_gate() -> ContractGate:
    spec = ProblemSpec(
        name="overlap-demo",
        root_dir="/tmp/overlap-demo",
        operator_categories=["local", "budget_policy"],
        research_surfaces=[
            SimpleNamespace(
                name="local",
                kind="operator",
                targets=SimpleNamespace(
                    files=["shared/*.py"],
                    create_new_allowed=True,
                    modify_allowed=True,
                    remove_allowed=False,
                    singleton=False,
                ),
            ),
            SimpleNamespace(
                name="budget_policy",
                kind="policy",
                targets=SimpleNamespace(
                    files=["shared/policy.py"],
                    create_new_allowed=False,
                    modify_allowed=True,
                    remove_allowed=False,
                    singleton=True,
                ),
                interface=SimpleNamespace(
                    required_functions=["choose_budget"],
                    function_signatures={"choose_budget": ["instance"]},
                ),
                bounds=SimpleNamespace(complexity_scale_terms=["item_count"]),
            ),
        ],
        search_space=SearchSpace(
            editable=["shared/*.py"],
            frozen=[],
            import_whitelist=["math"],
        ),
    )
    return ContractGate(spec)


def _budget_policy_hypothesis() -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text="Tune the budget policy.",
        change_locus="budget_policy",
        action="modify",
        target_file="shared/policy.py",
    )


def _semantic_objective_gate(signature_fields: list[str]) -> ContractGate:
    spec = ProblemSpec(
        name="surface-demo",
        root_dir="/tmp/surface-demo",
        operator_categories=["budget_policy"],
        research_surfaces=[
            SimpleNamespace(
                name="budget_policy",
                kind="policy",
                targets=SimpleNamespace(
                    files=["policies/budget.py"],
                    create_new_allowed=False,
                    modify_allowed=True,
                    remove_allowed=False,
                    singleton=True,
                ),
                novelty=SimpleNamespace(
                    strategy="semantic_signature",
                    signature_fields=signature_fields,
                ),
            ),
        ],
        search_space=SearchSpace(
            editable=["policies/*.py"],
            frozen=[],
            import_whitelist=["math"],
        ),
    )
    object.__setattr__(
        spec,
        "objectives",
        (
            SimpleNamespace(name="cost"),
            SimpleNamespace(name="time"),
            SimpleNamespace(name="reliability"),
        ),
    )
    return ContractGate(spec)
