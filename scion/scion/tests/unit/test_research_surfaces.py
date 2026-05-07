from __future__ import annotations

import random
from pathlib import Path
from types import SimpleNamespace

import pytest

from scion.config.problem import ProblemSpec, SearchSpace
from scion.contract.gate import ContractGate
from scion.core.models import (
    Branch,
    BranchState,
    CaseAggregateFeedback,
    ChampionState,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    ProtocolResult,
    StepRecord,
)
from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.problem.spec import ProblemSpecV1
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.models import CvrpInstance, CvrpNode, CvrpSolution
from scion.problems.cvrp.solver import (
    _baseline_time_budget,
    _load_construction_policy,
    _load_neighborhood_portfolio,
    _load_search_policy,
    improve_with_registry_operators,
)
from scion.proposal.context_manager import ContextManager
from scion.proposal.engine import _split_code_context, _split_hypothesis_context
from scion.runtime.audit import (
    format_runtime_audit_failure,
    runtime_audit_failure_from_runtime,
)

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


def test_problem_spec_accepts_optional_research_surfaces_and_bridge_maps_loci(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "local",
            "kind": "operator",
            "description": "Local operators",
            "target_files": ["operators/*.py"],
        },
        {
            "name": "search_policy",
            "kind": "policy",
            "description": "Budget policy",
            "target_files": ["policies/search_policy.py"],
            "create_new_allowed": False,
            "remove_allowed": False,
        },
    ]

    spec = ProblemSpecV1(**payload)
    legacy = legacy_problem_spec_from_v1(spec)

    assert [surface.name for surface in spec.research_surfaces or []] == [
        "local",
        "search_policy",
    ]
    assert legacy.operator_categories == ["local", "search_policy"]
    assert [surface.name for surface in legacy.research_surfaces] == [
        "local",
        "search_policy",
    ]
    assert legacy.research_surfaces[1].required_functions == []
    assert legacy.research_surfaces[1].targets.files == [
        "policies/search_policy.py"
    ]
    assert legacy.research_surfaces[1].interface.required_functions == []


def test_problem_spec_accepts_v2_research_surface_and_exposes_legacy_fields(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["search_space"]["editable"] = ["operators/*.py", "policies/*.py"]
    payload["research_surfaces"] = [
        {
            "name": "search_policy",
            "kind": "policy",
            "description": "Budget policy",
            "algorithm": {
                "role": "search_budget_policy",
                "invocation_point": "before_main_search",
                "description": "Controls bounded search budget choices.",
            },
            "targets": {
                "files": ["policies/search_policy.py"],
                "create_new_allowed": False,
                "modify_allowed": True,
                "remove_allowed": False,
                "singleton": True,
            },
            "interface": {
                "required_functions": [
                    "baseline_time_fraction",
                    "max_operator_rounds",
                ],
                "function_signatures": {
                    "baseline_time_fraction": ["instance", "time_limit_sec"],
                    "max_operator_rounds": "max_operator_rounds(instance, time_limit_sec)",
                },
                "return_contract": "problem-defined scalar policy values",
            },
            "bounds": {
                "allowed_components": ["baseline_budget", "round_limit"],
                "numeric_ranges": {
                    "baseline_time_fraction": [0.05, 0.95],
                    "max_operator_rounds": [0, 50],
                },
                "complexity_scale_terms": ["problem_size", "time_limit_sec"],
            },
            "evidence": {
                "required_runtime_fields": [
                    "policy_loaded",
                    "policy_errors",
                ],
            },
            "novelty": {
                "strategy": "semantic_signature",
                "signature_fields": ["budget_pattern", "round_limit_pattern"],
            },
            "prompt": {
                "hypothesis_guidance": "Explain expected budget tradeoff.",
                "implementation_guidance": "Keep policy deterministic.",
                "anti_patterns": "Do not read external result files.",
            },
        },
    ]

    spec = ProblemSpecV1(**payload)
    surface = (spec.research_surfaces or [])[0]

    assert surface.algorithm is not None
    assert surface.algorithm.role == "search_budget_policy"
    assert surface.targets is not None
    assert surface.targets.files == ["policies/search_policy.py"]
    assert surface.targets.singleton is True
    assert surface.interface is not None
    assert surface.interface.required_functions == [
        "baseline_time_fraction",
        "max_operator_rounds",
    ]
    assert surface.interface.function_signatures == {
        "baseline_time_fraction": ["instance", "time_limit_sec"],
        "max_operator_rounds": ["instance", "time_limit_sec"],
    }
    assert surface.interface.return_contract == "problem-defined scalar policy values"
    assert surface.bounds is not None
    assert surface.bounds.allowed_components == ["baseline_budget", "round_limit"]
    assert surface.bounds.numeric_ranges["baseline_time_fraction"] == (0.05, 0.95)
    assert surface.evidence is not None
    assert surface.evidence.required_runtime_fields == [
        "policy_loaded",
        "policy_errors",
    ]
    assert surface.novelty is not None
    assert surface.novelty.strategy == "semantic_signature"
    assert surface.prompt is not None
    assert surface.prompt.anti_patterns == "Do not read external result files."

    assert surface.target_files == ["policies/search_policy.py"]
    assert surface.required_functions == [
        "baseline_time_fraction",
        "max_operator_rounds",
    ]
    assert surface.create_new_allowed is False
    assert surface.modify_allowed is True
    assert surface.remove_allowed is False

    legacy = legacy_problem_spec_from_v1(spec)
    legacy_surface = legacy.research_surfaces[0]
    assert legacy.operator_categories == ["search_policy"]
    assert legacy_surface.target_files == ["policies/search_policy.py"]
    assert legacy_surface.required_functions == [
        "baseline_time_fraction",
        "max_operator_rounds",
    ]
    assert legacy_surface.bounds.allowed_components == [
        "baseline_budget",
        "round_limit",
    ]


def test_v2_research_surface_metadata_is_problem_owned(tmp_path: Path) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "abstract_surface",
            "kind": "portfolio",
            "algorithm": {
                "role": "problem_defined_role",
                "invocation_point": "problem_defined_hook",
            },
            "targets": {"files": ["operators/*.py"]},
            "bounds": {
                "allowed_components": ["problem_component_a"],
                "numeric_ranges": {"problem_knob": [1, 3]},
                "complexity_scale_terms": ["problem_scale_term"],
            },
        },
    ]

    spec = ProblemSpecV1(**payload)
    surface = (spec.research_surfaces or [])[0]

    assert surface.kind == "portfolio"
    assert surface.bounds is not None
    assert surface.bounds.allowed_components == ["problem_component_a"]
    assert surface.bounds.complexity_scale_terms == ["problem_scale_term"]


def test_problem_spec_rejects_duplicate_research_surface_names(tmp_path: Path) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "search_policy",
            "kind": "policy",
            "description": "Budget policy",
            "target_files": ["policies/search_policy.py"],
        },
        {
            "name": "search_policy",
            "kind": "policy",
            "description": "Duplicate",
            "target_files": ["policies/other.py"],
        },
    ]

    with pytest.raises(ValueError, match="research surface names must be unique"):
        ProblemSpecV1(**payload)


def test_problem_spec_rejects_legacy_v2_surface_target_conflict(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "policy",
            "kind": "policy",
            "targets": {"files": ["policies/policy.py"]},
            "target_files": ["policies/other.py"],
        },
    ]

    with pytest.raises(ValueError, match="target_files conflicts"):
        ProblemSpecV1(**payload)


def test_problem_spec_rejects_legacy_v2_surface_action_conflict(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "policy",
            "kind": "policy",
            "targets": {
                "files": ["policies/policy.py"],
                "remove_allowed": False,
            },
            "target_files": ["policies/policy.py"],
            "remove_allowed": True,
        },
    ]

    with pytest.raises(ValueError, match="remove_allowed conflicts"):
        ProblemSpecV1(**payload)


def test_problem_spec_rejects_legacy_v2_surface_interface_conflict(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "policy",
            "kind": "policy",
            "targets": {"files": ["policies/policy.py"]},
            "interface": {"required_functions": ["choose_limit"]},
            "target_files": ["policies/policy.py"],
            "required_functions": ["choose_mode"],
        },
    ]

    with pytest.raises(ValueError, match="required_functions conflicts"):
        ProblemSpecV1(**payload)


def test_problem_spec_without_research_surfaces_keeps_legacy_categories(
    tmp_path: Path,
) -> None:
    spec = ProblemSpecV1(**_problem_payload(str(tmp_path)))
    legacy = legacy_problem_spec_from_v1(spec)

    assert spec.research_surfaces is None
    assert legacy.operator_categories == ["local"]
    assert legacy.research_surfaces == []


def test_cvrp_problem_v1_exposes_policy_surfaces() -> None:
    spec = load_problem_spec_v1_from_yaml(
        Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem-v1.yaml"
    )
    legacy = legacy_problem_spec_from_v1(spec)

    assert legacy.operator_categories == [
        "route_local",
        "route_pair",
        "ruin_recreate",
        "search_policy",
        "construction_policy",
        "neighborhood_portfolio",
        "algorithm_blueprint",
    ]
    assert "policies/*.py" in legacy.search_space.editable
    assert "solver.py" in legacy.search_space.frozen
    search_policy = next(
        surface
        for surface in spec.research_surfaces or []
        if surface.name == "search_policy"
    )
    assert search_policy.algorithm is not None
    assert search_policy.algorithm.role == "post_baseline_search_scheduling"
    assert search_policy.targets is not None
    assert search_policy.targets.singleton is True
    assert search_policy.interface is not None
    assert search_policy.interface.required_functions == [
        "baseline_time_fraction",
        "max_operator_rounds",
        "enable_post_baseline_operators",
    ]
    assert search_policy.interface.function_signatures == {
        "baseline_time_fraction": ["instance", "time_limit_sec"],
        "max_operator_rounds": ["instance", "time_limit_sec"],
        "enable_post_baseline_operators": ["instance", "time_limit_sec"],
    }
    assert search_policy.evidence is not None
    assert "policy_loaded" in search_policy.evidence.required_runtime_fields
    assert search_policy.novelty is not None
    assert search_policy.novelty.signature_fields == [
        "predicted_direction",
        "target_objectives",
    ]
    assert spec.runtime_failure_guidance
    no_accepted_guidance = spec.runtime_failure_guidance[0]
    assert no_accepted_guidance.failure_categories == ["no_accepted_moves"]
    assert no_accepted_guidance.applies_to_surface_kinds == ["operator"]
    assert no_accepted_guidance.recommended_surfaces == [
        "algorithm_blueprint",
        "construction_policy",
        "neighborhood_portfolio",
        "search_policy",
    ]
    assert "route_local" in no_accepted_guidance.discouraged_surfaces
    assert "accepted move rate" in no_accepted_guidance.guidance
    assert legacy.runtime_failure_guidance[0].failure_categories == [
        "no_accepted_moves"
    ]

    construction_policy = next(
        surface
        for surface in spec.research_surfaces or []
        if surface.name == "construction_policy"
    )
    assert construction_policy.kind == "construction"
    assert construction_policy.algorithm is not None
    assert construction_policy.algorithm.role == "initial_solution_construction"
    assert construction_policy.targets is not None
    assert construction_policy.targets.files == ["policies/construction_policy.py"]
    assert construction_policy.targets.singleton is True
    assert construction_policy.targets.create_new_allowed is False
    assert construction_policy.targets.remove_allowed is False
    assert construction_policy.interface is not None
    assert construction_policy.interface.required_functions == [
        "construction_mode",
        "construction_bias",
    ]
    assert construction_policy.interface.function_signatures == {
        "construction_mode": ["instance", "time_limit_sec"],
        "construction_bias": ["instance", "time_limit_sec"],
    }
    assert construction_policy.bounds is not None
    assert "nearest_neighbor" in construction_policy.bounds.allowed_components
    assert construction_policy.evidence is not None
    assert construction_policy.evidence.required_runtime_fields == [
        "construction_surface_loaded",
        "construction_errors",
        "construction_mode",
        "construction_elapsed_ms",
        "construction_routes",
        "construction_distance",
        "construction_feasible",
    ]
    assert construction_policy.novelty is not None
    assert construction_policy.novelty.signature_fields == [
        "predicted_direction",
        "target_objectives",
    ]

    neighborhood_portfolio = next(
        surface
        for surface in spec.research_surfaces or []
        if surface.name == "neighborhood_portfolio"
    )
    assert neighborhood_portfolio.kind == "portfolio"
    assert neighborhood_portfolio.algorithm is not None
    assert neighborhood_portfolio.algorithm.role == "post_baseline_neighborhood_portfolio"
    assert neighborhood_portfolio.targets is not None
    assert neighborhood_portfolio.targets.files == [
        "policies/neighborhood_portfolio.py"
    ]
    assert neighborhood_portfolio.targets.singleton is True
    assert neighborhood_portfolio.targets.create_new_allowed is False
    assert neighborhood_portfolio.targets.remove_allowed is False
    assert neighborhood_portfolio.interface is not None
    assert neighborhood_portfolio.interface.required_functions == [
        "enabled_components",
        "component_weights",
        "candidate_limits",
    ]
    assert neighborhood_portfolio.interface.function_signatures == {
        "enabled_components": ["instance", "time_limit_sec"],
        "component_weights": ["instance", "time_limit_sec"],
        "candidate_limits": ["instance", "time_limit_sec"],
    }
    assert neighborhood_portfolio.bounds is not None
    assert neighborhood_portfolio.bounds.numeric_ranges["max_rounds"] == (0, 6)
    assert neighborhood_portfolio.bounds.numeric_ranges["top_k"] == (0, 32)
    assert neighborhood_portfolio.bounds.allowed_components == [
        "route_local",
        "route_pair",
        "ruin_recreate",
        "registry_operator",
    ]
    assert neighborhood_portfolio.evidence is not None
    assert neighborhood_portfolio.evidence.required_runtime_fields == [
        "portfolio_surface_loaded",
        "portfolio_errors",
        "enabled_components",
        "component_weights",
        "candidate_limits",
        "component_attempts",
        "component_accepted",
        "component_runtime_ms",
        "portfolio_stop_reason",
    ]
    assert neighborhood_portfolio.novelty is not None
    assert neighborhood_portfolio.novelty.signature_fields == [
        "predicted_direction",
        "target_objectives",
    ]

    algorithm_blueprint = next(
        surface
        for surface in spec.research_surfaces or []
        if surface.name == "algorithm_blueprint"
    )
    assert algorithm_blueprint.kind == "config"
    assert algorithm_blueprint.algorithm is not None
    assert algorithm_blueprint.algorithm.role == "top_level_algorithm_lifecycle"
    assert algorithm_blueprint.targets is not None
    assert algorithm_blueprint.targets.files == ["policies/algorithm_blueprint.py"]
    assert algorithm_blueprint.targets.singleton is True
    assert algorithm_blueprint.targets.create_new_allowed is False
    assert algorithm_blueprint.targets.remove_allowed is False
    assert algorithm_blueprint.interface is not None
    assert algorithm_blueprint.interface.required_functions == ["algorithm_plan"]
    assert algorithm_blueprint.interface.function_signatures == {
        "algorithm_plan": ["instance", "time_limit_sec"],
    }
    assert algorithm_blueprint.bounds is not None
    assert "intra_route_2opt" in algorithm_blueprint.bounds.allowed_components
    assert "inter_route_relocate" in algorithm_blueprint.bounds.allowed_components
    assert algorithm_blueprint.evidence is not None
    assert "algorithm_blueprint_errors" in (
        algorithm_blueprint.evidence.required_runtime_fields
    )
    assert "algorithm_local_search_components" in (
        algorithm_blueprint.evidence.required_runtime_fields
    )
    assert algorithm_blueprint.novelty is not None
    assert algorithm_blueprint.novelty.signature_fields == [
        "predicted_direction",
        "target_objectives",
    ]


def test_cvrp_semantic_signature_fields_are_contract_supported() -> None:
    spec = load_problem_spec_v1_from_yaml(
        Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem-v1.yaml"
    )
    unsupported: dict[str, set[str]] = {}
    for surface in spec.research_surfaces or []:
        novelty = surface.novelty
        if novelty is None or novelty.strategy != "semantic_signature":
            continue
        unsupported_fields = set(novelty.signature_fields) - set(
            ContractGate.SUPPORTED_SEMANTIC_SIGNATURE_FIELDS
        )
        if unsupported_fields:
            unsupported[surface.name] = unsupported_fields

    assert unsupported == {}


def test_cvrp_search_policy_semantic_signature_distinguishes_objective_identity() -> None:
    spec = load_problem_spec_v1_from_yaml(
        Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem-v1.yaml"
    )
    gate = ContractGate(legacy_problem_spec_from_v1(spec))
    existing = HypothesisRecord(
        hypothesis_id="h1",
        branch_id="b1",
        change_locus="search_policy",
        action="modify",
        status="active",
        target_file="policies/search_policy.py",
        hypothesis_text="Spend more of the budget on operator rounds for distance.",
        predicted_direction="improve",
        target_objectives=("total_distance",),
    )
    different_identity = HypothesisProposal(
        hypothesis_text="Protect fleet comparability with a stricter policy.",
        change_locus="search_policy",
        action="modify",
        target_file="policies/search_policy.py",
        predicted_direction="improve",
        target_objectives=("fleet_violation",),
    )
    same_identity = HypothesisProposal(
        hypothesis_text="Use another distance-focused policy schedule.",
        change_locus="search_policy",
        action="modify",
        target_file="policies/search_policy.py",
        predicted_direction="improve",
        target_objectives=("total_distance",),
    )

    different_result = gate.validate_hypothesis(different_identity, [existing], [])
    same_result = gate.validate_hypothesis(same_identity, [existing], [])

    assert different_result.passed
    assert not same_result.passed
    assert "C10_novelty" in (same_result.failure_reason or "")


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


def test_cvrp_default_policy_files_match_declared_signatures() -> None:
    root = Path(__file__).resolve().parents[2] / "problems" / "cvrp"
    spec = load_problem_spec_v1_from_yaml(root / "problem-v1.yaml")
    gate = ContractGate(legacy_problem_spec_from_v1(spec))

    for file_path in (
        "policies/search_policy.py",
        "policies/construction_policy.py",
        "policies/neighborhood_portfolio.py",
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


def test_policy_modify_free_text_changes_do_not_bypass_duplicate_c10() -> None:
    gate = _surface_gate()
    existing = HypothesisRecord(
        hypothesis_id="h1",
        branch_id="b1",
        change_locus="budget_policy",
        action="modify",
        status="active",
        target_file="policies/budget.py",
        hypothesis_text="Allocate more time to construction on large instances.",
    )
    hyp = HypothesisProposal(
        hypothesis_text="Reduce construction time and reserve budget for repair.",
        change_locus="budget_policy",
        action="modify",
        target_file="policies/budget.py",
        expected_effect="Different free-text expected effect.",
        no_op_condition="Different free-text no-op condition.",
    )

    result = gate._c10_novelty(hyp, [existing], [])

    assert not result.passed


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


def test_semantic_signature_uses_declared_structured_fields_only() -> None:
    gate = _semantic_objective_gate(["predicted_direction", "target_objectives"])
    existing = HypothesisRecord(
        hypothesis_id="h1",
        branch_id="b1",
        change_locus="budget_policy",
        action="modify",
        status="active",
        target_file="policies/budget.py",
        hypothesis_text="Original rationale.",
        predicted_direction="improve",
        target_objectives=("cost",),
    )
    same_structured = HypothesisProposal(
        hypothesis_text="Different rationale text.",
        change_locus="budget_policy",
        action="modify",
        target_file="policies/budget.py",
        predicted_direction="improve",
        target_objectives=("cost",),
        expected_effect="Different free-text expected effect.",
        no_op_condition="Different free-text no-op condition.",
    )
    different_structured = HypothesisProposal(
        hypothesis_text="Different objective set.",
        change_locus="budget_policy",
        action="modify",
        target_file="policies/budget.py",
        predicted_direction="improve",
        target_objectives=("time",),
        expected_effect="Different free-text expected effect.",
        no_op_condition="Different free-text no-op condition.",
    )

    same_result = gate._c10_novelty(same_structured, [existing], [])
    different_result = gate._c10_novelty(different_structured, [existing], [])

    assert not same_result.passed
    assert different_result.passed


def test_invalid_predicted_direction_fails_closed_without_semantic_bypass() -> None:
    gate = _semantic_objective_gate(["predicted_direction"])
    existing = HypothesisRecord(
        hypothesis_id="h1",
        branch_id="b1",
        change_locus="budget_policy",
        action="modify",
        status="active",
        target_file="policies/budget.py",
        hypothesis_text="Use a bounded budget policy.",
        predicted_direction="improve",
    )
    hyp = HypothesisProposal(
        hypothesis_text="Same policy with a free-form direction.",
        change_locus="budget_policy",
        action="modify",
        target_file="policies/budget.py",
        predicted_direction="cost-v2",  # type: ignore[arg-type]
    )

    result = gate.validate_hypothesis(hyp, [existing], [])
    c1 = next(check for check in result.checks if check.name == "C1_schema")
    c10 = next(check for check in result.checks if check.name == "C10_novelty")

    assert not result.passed
    assert not c1.passed
    assert not c10.passed


def test_arbitrary_objective_names_do_not_bypass_semantic_duplicate() -> None:
    gate = _semantic_objective_gate(["target_objectives", "protected_objectives"])
    existing = HypothesisRecord(
        hypothesis_id="h1",
        branch_id="b1",
        change_locus="budget_policy",
        action="modify",
        status="active",
        target_file="policies/budget.py",
        hypothesis_text="Improve cost while preserving reliability.",
        target_objectives=("cost",),
        protected_objectives=("reliability",),
    )
    hyp = HypothesisProposal(
        hypothesis_text="Try to rename the same objective identity.",
        change_locus="budget_policy",
        action="modify",
        target_file="policies/budget.py",
        target_objectives=("cost-v2",),
        protected_objectives=("reliability",),
    )

    result = gate.validate_hypothesis(hyp, [existing], [])
    c1 = next(check for check in result.checks if check.name == "C1_schema")
    c10 = next(check for check in result.checks if check.name == "C10_novelty")

    assert not result.passed
    assert not c1.passed
    assert not c10.passed


def test_semantic_signature_sorts_dedupes_objective_lists() -> None:
    gate = _semantic_objective_gate(["target_objectives", "protected_objectives"])
    existing = HypothesisRecord(
        hypothesis_id="h1",
        branch_id="b1",
        change_locus="budget_policy",
        action="modify",
        status="active",
        target_file="policies/budget.py",
        hypothesis_text="Improve both bounded objectives.",
        target_objectives=("cost", "time"),
        protected_objectives=("reliability",),
    )
    hyp = HypothesisProposal(
        hypothesis_text="Same objectives in a different order with duplicate text.",
        change_locus="budget_policy",
        action="modify",
        target_file="policies/budget.py",
        target_objectives=("time", "cost", "cost"),
        protected_objectives=("reliability",),
    )

    result = gate._c10_novelty(hyp, [existing], [])

    assert not result.passed


def test_free_text_signature_fields_fall_back_to_duplicate_identity() -> None:
    gate = _semantic_objective_gate(
        ["predicted_direction", "target_objectives", "hypothesis_text"],
    )
    existing = HypothesisRecord(
        hypothesis_id="h1",
        branch_id="b1",
        change_locus="budget_policy",
        action="modify",
        status="active",
        target_file="policies/budget.py",
        hypothesis_text="Original narrative.",
        predicted_direction="improve",
        target_objectives=("cost",),
    )
    hyp = HypothesisProposal(
        hypothesis_text="Different narrative text.",
        change_locus="budget_policy",
        action="modify",
        target_file="policies/budget.py",
        predicted_direction="improve",
        target_objectives=("cost",),
        expected_effect="Different free-text expected effect.",
        no_op_condition="Different free-text no-op condition.",
        target_runtime_effect="Different unsupported string field.",
    )

    result = gate._c10_novelty(hyp, [existing], [])

    assert not result.passed


def test_different_legal_bounded_semantic_identity_is_novel() -> None:
    gate = _semantic_objective_gate(["predicted_direction", "target_objectives"])
    existing = HypothesisRecord(
        hypothesis_id="h1",
        branch_id="b1",
        change_locus="budget_policy",
        action="modify",
        status="active",
        target_file="policies/budget.py",
        hypothesis_text="Improve cost.",
        predicted_direction="improve",
        target_objectives=("cost",),
    )
    hyp = HypothesisProposal(
        hypothesis_text="Legally target a different metric.",
        change_locus="budget_policy",
        action="modify",
        target_file="policies/budget.py",
        predicted_direction="improve",
        target_objectives=("time",),
    )

    result = gate.validate_hypothesis(hyp, [existing], [])

    assert result.passed


def test_policy_modify_identical_semantic_intent_fails_c10() -> None:
    gate = _surface_gate()
    text = "Allocate more time to construction on large instances."
    existing = HypothesisRecord(
        hypothesis_id="h1",
        branch_id="b1",
        change_locus="budget_policy",
        action="modify",
        status="active",
        target_file="policies/budget.py",
        hypothesis_text=text,
    )
    hyp = HypothesisProposal(
        hypothesis_text="  allocate MORE time to construction on large instances. ",
        change_locus="budget_policy",
        action="modify",
        target_file="policies/budget.py",
    )

    result = gate._c10_novelty(hyp, [existing], [])

    assert not result.passed


def test_operator_modify_remains_strict_by_locus_action_target_file() -> None:
    gate = _surface_gate()
    existing = HypothesisRecord(
        hypothesis_id="h1",
        branch_id="b1",
        change_locus="local",
        action="modify",
        status="active",
        target_file="operators/local.py",
        hypothesis_text="Try nearest-neighbor relocation.",
    )
    hyp = HypothesisProposal(
        hypothesis_text="Try regret-based relocation instead.",
        change_locus="local",
        action="modify",
        target_file="operators/local.py",
    )

    result = gate._c10_novelty(hyp, [existing], [])

    assert not result.passed


def test_dummy_singleton_config_unextractable_signature_falls_back_to_target_strict() -> None:
    spec = ProblemSpec(
        name="dummy",
        root_dir="/tmp/dummy",
        operator_categories=["dispatch_config"],
        research_surfaces=[
            SimpleNamespace(
                name="dispatch_config",
                kind="config",
                targets=SimpleNamespace(
                    files=["config/dispatch.py"],
                    create_new_allowed=False,
                    modify_allowed=True,
                    remove_allowed=False,
                    singleton=True,
                ),
                interface=SimpleNamespace(required_functions=["select_limit"]),
                novelty=SimpleNamespace(
                    strategy="semantic_signature",
                    signature_fields=["limit_pattern"],
                ),
            ),
        ],
        search_space=SearchSpace(
            editable=["config/*.py"],
            frozen=[],
            import_whitelist=["math"],
        ),
    )
    gate = ContractGate(spec)
    existing = HypothesisRecord(
        hypothesis_id="h1",
        branch_id="b1",
        change_locus="dispatch_config",
        action="modify",
        status="active",
        target_file="config/dispatch.py",
        hypothesis_text="Raise the dispatch limit for sparse queues.",
    )
    hyp = HypothesisProposal(
        hypothesis_text="Lower the dispatch limit when backlog is volatile.",
        change_locus="dispatch_config",
        action="modify",
        target_file="config/dispatch.py",
    )

    result = gate._c10_novelty(hyp, [existing], [])

    assert not result.passed
    for forbidden in ("cvrp", "warehouse", "customer", "vehicle", "route"):
        assert forbidden not in result.detail.lower()


def test_contract_gate_fails_closed_on_unknown_novelty_strategy() -> None:
    spec = ProblemSpec(
        name="dummy",
        root_dir="/tmp/dummy",
        operator_categories=["dispatch_config"],
        research_surfaces=[
            SimpleNamespace(
                name="dispatch_config",
                kind="config",
                targets=SimpleNamespace(
                    files=["config/dispatch.py"],
                    create_new_allowed=False,
                    modify_allowed=True,
                    remove_allowed=False,
                    singleton=True,
                ),
                novelty=SimpleNamespace(
                    strategy="problem_specific_magic",
                    signature_fields=["limit_pattern"],
                ),
            ),
        ],
        search_space=SearchSpace(
            editable=["config/*.py"],
            frozen=[],
            import_whitelist=["math"],
        ),
    )
    gate = ContractGate(spec)
    hyp = HypothesisProposal(
        hypothesis_text="Tune dispatch limits.",
        change_locus="dispatch_config",
        action="modify",
        target_file="config/dispatch.py",
    )

    result = gate.validate_hypothesis(hyp, [], [])
    c10 = next(check for check in result.checks if check.name == "C10_novelty")

    assert not c10.passed
    assert "unsupported novelty.strategy" in c10.detail


def test_problem_spec_rejects_unknown_research_surface_kind(tmp_path: Path) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "local",
            "kind": "oprator",
            "description": "Typo should not load.",
            "target_files": ["operators/*.py"],
        },
    ]

    with pytest.raises(ValueError, match="unsupported research surface kind"):
        ProblemSpecV1(**payload)


def test_contract_gate_fails_closed_on_unknown_surface_kind() -> None:
    spec = ProblemSpec(
        name="dummy",
        root_dir="/tmp/dummy",
        operator_categories=["local"],
        research_surfaces=[
            SimpleNamespace(
                name="local",
                kind="oprator",
                target_files=["operators/*.py"],
            ),
        ],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=[],
            import_whitelist=["math"],
        ),
    )
    gate = ContractGate(spec)
    hyp = HypothesisProposal(
        hypothesis_text="Try a bounded local move.",
        change_locus="local",
        action="modify",
        target_file="operators/local.py",
    )

    result = gate.validate_hypothesis(hyp, [], [])

    assert not result.passed
    assert "unsupported research surface kind 'oprator'" in result.failure_reason


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


def test_cvrp_solver_loads_workspace_search_policy_and_applies_bounds(
    tmp_path: Path,
) -> None:
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "search_policy.py").write_text(
        "def baseline_time_fraction(instance, time_limit_sec):\n"
        "    return 0.5\n\n"
        "def max_operator_rounds(instance, time_limit_sec):\n"
        "    return 3\n\n"
        "def enable_post_baseline_operators(instance, time_limit_sec):\n"
        "    return False\n",
        encoding="utf-8",
    )

    policy = _load_search_policy(
        workspace_root=tmp_path,
        instance=_tiny_instance(),
        time_limit_sec=10.0,
    )
    assert policy["policy_loaded"] is True
    assert policy["policy_errors"] == 0
    assert policy["baseline_time_fraction"] == 0.5
    assert policy["operator_round_limit"] == 3
    assert policy["post_baseline_operators_enabled"] is False
    assert _baseline_time_budget(10.0, policy["baseline_time_fraction"]) == 5.0

    solution, audit = improve_with_registry_operators(
        CvrpSolution(routes=((1,),)),
        _tiny_instance(),
        adapter=CvrpAdapter(object()),  # type: ignore[arg-type]
        rng=random.Random(0),
        registry_path="",
        workspace_root=tmp_path,
        time_limit_sec=10.0,
        start_time=0.0,
        max_operator_rounds=policy["operator_round_limit"],
        post_baseline_operators_enabled=policy[
            "post_baseline_operators_enabled"
        ],
    )
    assert solution.routes == ((1,),)
    assert audit["operator_stop_reason"] == "disabled_by_policy"


def test_invalid_cvrp_search_policy_counts_policy_errors(tmp_path: Path) -> None:
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "search_policy.py").write_text(
        "def baseline_time_fraction(instance, time_limit_sec):\n"
        "    return 2.0\n\n"
        "def max_operator_rounds(instance, time_limit_sec):\n"
        "    return 'many'\n\n"
        "def enable_post_baseline_operators(instance, time_limit_sec):\n"
        "    return 1\n",
        encoding="utf-8",
    )

    policy = _load_search_policy(
        workspace_root=tmp_path,
        instance=_tiny_instance(),
        time_limit_sec=10.0,
    )

    assert policy["policy_loaded"] is True
    assert policy["policy_errors"] == 3
    assert policy["baseline_time_fraction"] == 0.95
    assert policy["operator_round_limit"] == 20
    assert policy["post_baseline_operators_enabled"] is True


def test_cvrp_solver_loads_workspace_construction_policy_and_applies_bounds(
    tmp_path: Path,
) -> None:
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "construction_policy.py").write_text(
        "def construction_mode(instance, time_limit_sec):\n"
        "    return 'nearest_neighbor_demand_bias'\n\n"
        "def construction_bias(instance, time_limit_sec):\n"
        "    return 0.4\n",
        encoding="utf-8",
    )

    policy = _load_construction_policy(
        workspace_root=tmp_path,
        instance=_tiny_instance(),
        time_limit_sec=10.0,
    )

    assert policy["construction_surface_loaded"] is True
    assert policy["construction_errors"] == 0
    assert policy["construction_mode"] == "nearest_neighbor_demand_bias"
    assert policy["construction_bias"] == 0.4


def test_invalid_cvrp_construction_policy_counts_construction_errors(
    tmp_path: Path,
) -> None:
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "construction_policy.py").write_text(
        "def construction_mode(instance, time_limit_sec):\n"
        "    return 'not_allowed'\n\n"
        "def construction_bias(instance, time_limit_sec):\n"
        "    return 2.0\n",
        encoding="utf-8",
    )

    policy = _load_construction_policy(
        workspace_root=tmp_path,
        instance=_tiny_instance(),
        time_limit_sec=10.0,
    )

    assert policy["construction_surface_loaded"] is True
    assert policy["construction_errors"] == 2
    assert policy["construction_mode"] == "nearest_neighbor"
    assert policy["construction_bias"] == 1.0


def test_cvrp_solver_loads_workspace_neighborhood_portfolio_and_applies_bounds(
    tmp_path: Path,
) -> None:
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "neighborhood_portfolio.py").write_text(
        "def enabled_components(instance, time_limit_sec):\n"
        "    return ['route_pair']\n\n"
        "def component_weights(instance, time_limit_sec):\n"
        "    return {'route_pair': 2.0}\n\n"
        "def candidate_limits(instance, time_limit_sec):\n"
        "    return {'max_rounds': 2, 'top_k': 1, 'route_pair': 3}\n",
        encoding="utf-8",
    )

    policy = _load_neighborhood_portfolio(
        workspace_root=tmp_path,
        instance=_tiny_instance(),
        time_limit_sec=10.0,
    )

    assert policy["portfolio_surface_loaded"] is True
    assert policy["portfolio_errors"] == 0
    assert policy["enabled_components"] == ["route_pair"]
    assert policy["component_weights"]["route_pair"] == 2.0
    assert policy["candidate_limits"]["max_rounds"] == 2
    assert policy["candidate_limits"]["top_k"] == 1
    assert policy["candidate_limits"]["route_pair"] == 3


def test_invalid_cvrp_neighborhood_portfolio_counts_portfolio_errors(
    tmp_path: Path,
) -> None:
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "neighborhood_portfolio.py").write_text(
        "def enabled_components(instance, time_limit_sec):\n"
        "    return ['not_a_component']\n\n"
        "def component_weights(instance, time_limit_sec):\n"
        "    return {'route_local': -1.0, 'ghost': 1.0}\n\n"
        "def candidate_limits(instance, time_limit_sec):\n"
        "    return {'top_k': -1, 'bad_limit': 2}\n",
        encoding="utf-8",
    )

    policy = _load_neighborhood_portfolio(
        workspace_root=tmp_path,
        instance=_tiny_instance(),
        time_limit_sec=10.0,
    )

    assert policy["portfolio_surface_loaded"] is True
    assert policy["portfolio_errors"] >= 5
    assert "registry_operator" in policy["enabled_components"]
    assert policy["component_weights"]["route_local"] == 0.0
    assert policy["candidate_limits"]["top_k"] == 0


def test_runtime_audit_fails_when_policy_errors_present() -> None:
    issue = runtime_audit_failure_from_runtime(
        {
            "policy_path": "policies/search_policy.py",
            "policy_loaded": True,
            "policy_errors": 1,
            "policy_events": [
                {
                    "policy": "policies/search_policy.py",
                    "status": "error",
                    "detail": "bad return",
                }
            ],
        }
    )

    assert issue is not None
    assert issue["error_category"] == "policy_runtime_error"
    assert "policy_errors=1" in issue["detail"]
    assert "bad return" in format_runtime_audit_failure(issue)


def test_runtime_audit_fails_when_construction_errors_present() -> None:
    issue = runtime_audit_failure_from_runtime(
        {
            "construction_policy_path": "policies/construction_policy.py",
            "construction_surface_loaded": True,
            "construction_errors": 1,
            "construction_mode": "nearest_neighbor",
            "construction_events": [
                {
                    "policy": "policies/construction_policy.py",
                    "status": "error",
                    "detail": "bad construction mode",
                }
            ],
        }
    )

    assert issue is not None
    assert issue["error_category"] == "construction_runtime_error"
    assert "construction_errors=1" in issue["detail"]
    assert "bad construction mode" in format_runtime_audit_failure(issue)


def test_runtime_audit_fails_when_portfolio_errors_present() -> None:
    issue = runtime_audit_failure_from_runtime(
        {
            "portfolio_policy_path": "policies/neighborhood_portfolio.py",
            "portfolio_surface_loaded": True,
            "portfolio_errors": 1,
            "enabled_components": ["route_local"],
            "portfolio_events": [
                {
                    "policy": "policies/neighborhood_portfolio.py",
                    "status": "error",
                    "detail": "unknown component",
                }
            ],
        }
    )

    assert issue is not None
    assert issue["error_category"] == "portfolio_runtime_error"
    assert "portfolio_errors=1" in issue["detail"]
    assert "unknown component" in format_runtime_audit_failure(issue)


def test_context_exposes_search_policy_surface_and_modify_when_no_operator_pool(
    tmp_path: Path,
) -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(
        Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem-v1.yaml"
    )
    legacy = legacy_problem_spec_from_v1(spec_v1)
    (tmp_path / "policies").mkdir()
    (tmp_path / "policies" / "search_policy.py").write_text(
        "def baseline_time_fraction(instance, time_limit_sec):\n"
        "    return 0.8\n\n"
        "def max_operator_rounds(instance, time_limit_sec):\n"
        "    return 20\n\n"
        "def enable_post_baseline_operators(instance, time_limit_sec):\n"
        "    return True\n",
        encoding="utf-8",
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="h",
        code_snapshot_path=str(tmp_path),
        code_snapshot_hash="h",
    )
    branch = Branch(
        branch_id="b1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )
    manager = ContextManager(adapter=CvrpAdapter(spec_v1))

    ctx = manager.build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        active_hypotheses=[],
        blacklist=[],
    )
    system_blocks, user_prompt = _split_hypothesis_context(ctx)
    prompt_text = "\n".join(block["text"] for block in system_blocks) + user_prompt

    assert "## Research Surfaces" in prompt_text
    assert "search_policy [policy]" in prompt_text
    assert "construction_policy [construction]" in prompt_text
    assert "neighborhood_portfolio [portfolio]" in prompt_text
    assert "algorithm_blueprint [config]" in prompt_text
    assert "policies/search_policy.py" in prompt_text
    assert "policies/construction_policy.py" in prompt_text
    assert "policies/neighborhood_portfolio.py" in prompt_text
    assert "policies/algorithm_blueprint.py" in prompt_text
    assert "algorithm.role: post_baseline_search_scheduling" in prompt_text
    assert (
        "algorithm.invocation_point: "
        "before_and_during_post_baseline_operator_search"
    ) in prompt_text
    assert "targets.files: policies/search_policy.py" in prompt_text
    assert (
        "action permissions: create_new=false, modify=true, remove=false"
        in prompt_text
    )
    assert "singleton: true" in prompt_text
    assert (
        "interface.required_functions: baseline_time_fraction, "
        "max_operator_rounds, enable_post_baseline_operators"
    ) in prompt_text
    assert "interface.return_contract:" in prompt_text
    assert "bounds.allowed_components:" in prompt_text
    assert "baseline_time_fraction" in prompt_text
    assert "operator_round_limit" in prompt_text
    assert "bounds.numeric_ranges:" in prompt_text
    assert (
        "bounds.complexity_scale_terms: time_limit_sec, route_count, "
        "customer_count"
    ) in prompt_text
    assert (
        "evidence.required_runtime_fields: policy_loaded, policy_errors"
        in prompt_text
    )
    assert "novelty.strategy: semantic_signature" in prompt_text
    assert "novelty.signature_fields: predicted_direction, target_objectives" in prompt_text
    assert "construction_mode" in prompt_text
    assert "construction_elapsed_ms" in prompt_text
    assert "enabled_components" in prompt_text
    assert "component_weights" in prompt_text
    assert "candidate_limits" in prompt_text
    assert "portfolio_stop_reason" in prompt_text
    assert "algorithm_plan" in prompt_text
    assert "algorithm_blueprint_errors" in prompt_text
    assert "algorithm_local_search_components" in prompt_text
    assert "prompt.hypothesis_guidance:" in prompt_text
    assert "prompt.implementation_guidance:" in prompt_text
    assert "prompt.anti_patterns:" in prompt_text
    assert "instance.customer_ids, instance.customer_count" in prompt_text
    assert "instance.demands[customer_id]" in prompt_text
    assert "Never use instance.customers" in prompt_text
    assert ctx["available_actions"] == "create_new, modify"
    assert "remove" not in ctx["available_actions"]

    hypothesis = HypothesisProposal(
        hypothesis_text="Tune baseline/operator budget.",
        change_locus="search_policy",
        action="modify",
        target_file="policies/search_policy.py",
        target_weakness="baseline/operator scheduling",
        expected_effect="better budget allocation",
    )
    code_ctx = manager.build_code_context(
        branch=branch,
        hypothesis=hypothesis,
        champion=champion,
        problem_spec=legacy,
    )
    system_blocks, _ = _split_code_context(code_ctx)
    code_prompt_text = "\n".join(block["text"] for block in system_blocks)

    assert "Active surface: search_policy [policy]" in code_prompt_text
    assert "module-level policy file; no class is required" in code_prompt_text
    assert "def baseline_time_fraction" in code_prompt_text
    assert "`instance.customer_count`" in code_prompt_text
    assert "Never use `instance.customers`" in code_prompt_text

    construction_hypothesis = HypothesisProposal(
        hypothesis_text="Tune initial construction mode.",
        change_locus="construction_policy",
        action="modify",
        target_file="policies/construction_policy.py",
        target_weakness="initial route construction",
        expected_effect="better construction audit distance",
    )
    construction_code_ctx = manager.build_code_context(
        branch=branch,
        hypothesis=construction_hypothesis,
        champion=champion,
        problem_spec=legacy,
    )
    system_blocks, _ = _split_code_context(construction_code_ctx)
    construction_prompt_text = "\n".join(block["text"] for block in system_blocks)

    assert "Active surface: construction_policy [construction]" in construction_prompt_text
    assert "module-level construction policy file; no class is required" in construction_prompt_text
    assert "def construction_mode" in construction_prompt_text

    portfolio_hypothesis = HypothesisProposal(
        hypothesis_text="Tune neighborhood portfolio.",
        change_locus="neighborhood_portfolio",
        action="modify",
        target_file="policies/neighborhood_portfolio.py",
        target_weakness="component scheduling",
        expected_effect="better post-baseline neighborhood selection",
    )
    portfolio_code_ctx = manager.build_code_context(
        branch=branch,
        hypothesis=portfolio_hypothesis,
        champion=champion,
        problem_spec=legacy,
    )
    system_blocks, _ = _split_code_context(portfolio_code_ctx)
    portfolio_prompt_text = "\n".join(block["text"] for block in system_blocks)

    assert "Active surface: neighborhood_portfolio [portfolio]" in portfolio_prompt_text
    assert "module-level portfolio policy file; no class is required" in portfolio_prompt_text
    assert "def enabled_components" in portfolio_prompt_text

    blueprint_hypothesis = HypothesisProposal(
        hypothesis_text="Coordinate the top-level algorithm lifecycle.",
        change_locus="algorithm_blueprint",
        action="modify",
        target_file="policies/algorithm_blueprint.py",
        target_weakness="no accepted post-baseline moves",
        expected_effect="run bounded package-owned local search",
    )
    blueprint_code_ctx = manager.build_code_context(
        branch=branch,
        hypothesis=blueprint_hypothesis,
        champion=champion,
        problem_spec=legacy,
    )
    system_blocks, _ = _split_code_context(blueprint_code_ctx)
    blueprint_prompt_text = "\n".join(block["text"] for block in system_blocks)

    assert "Active surface: algorithm_blueprint [config]" in blueprint_prompt_text
    assert "top-level algorithm lifecycle config surface" in blueprint_prompt_text
    assert "def algorithm_plan" in blueprint_prompt_text
    assert "intra_route_2opt" in blueprint_prompt_text
    assert "Never use `instance.customers`" in blueprint_prompt_text


def test_context_still_renders_legacy_v1_surface_metadata(tmp_path: Path) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "legacy_surface",
            "kind": "operator",
            "description": "Legacy surface declaration",
            "target_files": ["operators/*.py"],
            "required_functions": ["execute"],
            "prompt_hint": "Keep moves bounded.",
            "create_new_allowed": True,
            "modify_allowed": True,
            "remove_allowed": False,
        },
    ]
    spec_v1 = ProblemSpecV1(**payload)
    legacy = legacy_problem_spec_from_v1(spec_v1)
    (tmp_path / "operators").mkdir()
    (tmp_path / "operators" / "old.py").write_text(
        "class Old:\n    pass\n",
        encoding="utf-8",
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="h",
        code_snapshot_path=str(tmp_path),
        code_snapshot_hash="h",
    )
    branch = Branch(
        branch_id="b1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )

    ctx = ContextManager().build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        active_hypotheses=[],
        blacklist=[],
    )

    assert (
        "legacy_surface [operator]: Legacy surface declaration"
        in ctx["research_surfaces"]
    )
    assert "targets.files: operators/*.py" in ctx["research_surfaces"]
    assert (
        "action permissions: create_new=true, modify=true, remove=false"
        in ctx["research_surfaces"]
    )
    assert "interface.required_functions: execute" in ctx["research_surfaces"]
    assert (
        "prompt.implementation_guidance: Keep moves bounded."
        in ctx["research_surfaces"]
    )


def test_generic_v2_surface_prompt_has_no_cvrp_or_warehouse_core_terms(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["description"] = "Generic scheduling benchmark."
    payload["search_space"]["editable"] = ["policies/*.py"]
    payload["research_surfaces"] = [
        {
            "name": "dispatch_policy",
            "kind": "policy",
            "description": "Dispatch timing policy.",
            "algorithm": {
                "role": "dispatch_timing",
                "invocation_point": "before_candidate_selection",
                "description": "Controls generic timing choices.",
            },
            "targets": {
                "files": ["policies/dispatch_policy.py"],
                "create_new_allowed": False,
                "modify_allowed": True,
                "remove_allowed": False,
                "singleton": True,
            },
            "interface": {
                "required_functions": ["select_limit"],
                "function_signatures": {
                    "select_limit": ["instance", "time_limit_sec"]
                },
                "return_contract": "problem-defined scalar values",
            },
            "bounds": {
                "allowed_components": ["limit_selector"],
                "numeric_ranges": {"select_limit": [1, 10]},
                "complexity_scale_terms": ["item_count"],
            },
            "evidence": {"required_runtime_fields": ["policy_loaded"]},
            "novelty": {
                "strategy": "semantic_signature",
                "signature_fields": ["limit_pattern"],
            },
            "prompt": {
                "hypothesis_guidance": "Describe the timing change.",
                "implementation_guidance": "Keep selection bounded.",
                "anti_patterns": "Do not read external files.",
            },
        },
    ]
    spec_v1 = ProblemSpecV1(**payload)
    legacy = legacy_problem_spec_from_v1(spec_v1)
    (tmp_path / "policies").mkdir()
    (tmp_path / "policies" / "dispatch_policy.py").write_text(
        "def select_limit(instance, time_limit_sec):\n    return 5\n",
        encoding="utf-8",
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="h",
        code_snapshot_path=str(tmp_path),
        code_snapshot_hash="h",
    )
    branch = Branch(
        branch_id="b1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )
    manager = ContextManager()

    ctx = manager.build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        active_hypotheses=[],
        blacklist=[],
    )
    system_blocks, user_prompt = _split_hypothesis_context(ctx)
    prompt_text = "\n".join(block["text"] for block in system_blocks) + user_prompt

    assert "algorithm.role: dispatch_timing" in prompt_text
    assert (
        "interface.function_signatures: select_limit(instance, time_limit_sec)"
        in prompt_text
    )
    assert "bounds.complexity_scale_terms: item_count" in prompt_text
    for forbidden in (
        "cvrp",
        "warehouse",
        "customer",
        "vehicle",
        "depot",
        "cvrplib",
    ):
        assert forbidden not in prompt_text.lower()

    hypothesis = HypothesisProposal(
        hypothesis_text="Tune the dispatch limit.",
        change_locus="dispatch_policy",
        action="modify",
        target_file="policies/dispatch_policy.py",
    )
    code_ctx = manager.build_code_context(
        branch=branch,
        hypothesis=hypothesis,
        champion=champion,
        problem_spec=legacy,
    )

    assert "select_limit" in code_ctx["operator_interface_spec"]
    assert (
        "interface.function_signatures: select_limit(instance, time_limit_sec)"
        in code_ctx["operator_interface_spec"]
    )
    assert "problem-defined scalar values" in code_ctx["operator_interface_spec"]


def test_forced_singleton_config_surface_context_derives_modify_target(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["search_space"]["editable"] = ["policies/*.py"]
    payload["research_surfaces"] = [
        {
            "name": "algorithm_blueprint",
            "kind": "config",
            "description": "Top-level algorithm plan.",
            "targets": {
                "files": ["policies/algorithm_blueprint.py"],
                "create_new_allowed": False,
                "modify_allowed": True,
                "remove_allowed": False,
                "singleton": True,
            },
            "interface": {
                "required_functions": ["algorithm_plan"],
                "function_signatures": {
                    "algorithm_plan": ["instance", "time_limit_sec"]
                },
                "return_contract": "bounded plan dict",
            },
        },
    ]
    spec_v1 = ProblemSpecV1(**payload)
    legacy = legacy_problem_spec_from_v1(spec_v1)
    (tmp_path / "policies").mkdir()
    (tmp_path / "policies" / "algorithm_blueprint.py").write_text(
        "def algorithm_plan(instance, time_limit_sec):\n"
        "    return {'enabled': False}\n",
        encoding="utf-8",
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="h",
        code_snapshot_path=str(tmp_path),
        code_snapshot_hash="h",
    )
    branch = Branch(
        branch_id="b1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )

    ctx = ContextManager().build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        active_hypotheses=[],
        blacklist=[],
        forced_locus="algorithm_blueprint",
        forced_surface_diagnostic=True,
    )
    system_blocks, user_prompt = _split_hypothesis_context(ctx)
    prompt_text = "\n".join(block["text"] for block in system_blocks) + user_prompt

    assert ctx["forced_surface"] == "algorithm_blueprint"
    assert ctx["forced_action"] == "modify"
    assert ctx["forced_target_file"] == "policies/algorithm_blueprint.py"
    assert "policies/algorithm_blueprint.py" in ctx["targetable_files"]
    assert "algorithm_plan" in ctx["champion_operators_code"]
    assert "diagnostic experiment-control hook" in prompt_text
    assert "Set `change_locus` to `algorithm_blueprint`." in prompt_text
    assert "Set `action` to `modify`." in prompt_text
    assert "Set `target_file` to `policies/algorithm_blueprint.py`." in prompt_text


def test_forced_surface_context_rejects_unknown_surface(tmp_path: Path) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "dispatch_policy",
            "kind": "policy",
            "description": "Dispatch policy.",
            "target_files": ["policies/dispatch_policy.py"],
        },
    ]
    spec_v1 = ProblemSpecV1(**payload)
    legacy = legacy_problem_spec_from_v1(spec_v1)
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="h",
        code_snapshot_path=str(tmp_path),
        code_snapshot_hash="h",
    )
    branch = Branch(
        branch_id="b1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )

    with pytest.raises(ValueError, match="unknown research surface 'missing'"):
        ContextManager().build_hypothesis_context(
            branch=branch,
            champion=champion,
            problem_spec=legacy,
            active_hypotheses=[],
            blacklist=[],
            forced_locus="missing",
        )


def test_validation_and_frozen_raw_metric_refs_stay_out_of_context(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "local",
            "kind": "operator",
            "description": "Local surface",
            "target_files": ["operators/*.py"],
        },
    ]
    spec_v1 = ProblemSpecV1(**payload)
    legacy = legacy_problem_spec_from_v1(spec_v1)
    (tmp_path / "operators").mkdir()
    (tmp_path / "operators" / "old.py").write_text(
        "class Old:\n    pass\n",
        encoding="utf-8",
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="h",
        code_snapshot_path=str(tmp_path),
        code_snapshot_hash="h",
    )
    branch = Branch(
        branch_id="b1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )
    screening_hypothesis = HypothesisProposal(
        hypothesis_text="Bounded local move.",
        change_locus="local",
        action="modify",
        target_file="operators/old.py",
    )
    validation_hypothesis = HypothesisProposal(
        hypothesis_text="VALIDATION_ONLY_HYPOTHESIS_TEXT",
        change_locus="validation_only_locus",
        action="modify",
        target_file="operators/validation_only.py",
    )
    frozen_hypothesis = HypothesisProposal(
        hypothesis_text="FROZEN_ONLY_HYPOTHESIS_TEXT",
        change_locus="frozen_only_locus",
        action="modify",
        target_file="operators/frozen_only.py",
    )
    screening_stats = EvalStats(
        n_cases=6,
        wins=5,
        losses=1,
        ties=0,
        win_rate=0.83,
        median_delta=0.1234,
        ci_low=0.01,
        ci_high=0.20,
    )
    holdout_stats = EvalStats(
        n_cases=17,
        wins=7,
        losses=10,
        ties=0,
        win_rate=0.42,
        median_delta=0.4242,
        ci_low=-0.42,
        ci_high=0.43,
    )
    frozen_stats = EvalStats(
        n_cases=19,
        wins=18,
        losses=1,
        ties=0,
        win_rate=0.95,
        median_delta=9.1919,
        ci_low=0.91,
        ci_high=0.99,
    )
    holdout_case_feedback = (
        CaseAggregateFeedback(
            case_id="holdout-case-feedback-secret",
            n_pairs=3,
            wins=1,
            losses=2,
            ties=0,
            win_rate=0.33,
            dominant_result="loss",
            decisive_metric="holdout_secret_metric",
            median_deltas={"holdout_secret_metric": -123.0},
            seed_consistency=1.0,
            case_features={"path_stem": "holdout-secret-stem"},
        ),
    )
    step_history = [
        StepRecord(
            round_num=1,
            branch_id="b1",
            hypothesis=screening_hypothesis,
            patch=None,
            contract_passed=True,
            verification_passed=True,
            protocol_result=ProtocolResult(
                stage=ExperimentStage.SCREENING,
                stats=screening_stats,
                gate_outcome="expand",
                reason_codes=("screening_expand",),
                exposed_summary="screening summary may be copied",
                raw_metrics_ref="/tmp/screening-metrics.json",
            ),
            decision=Decision.EXPAND_SCREENING,
            failure_stage=None,
            failure_detail=None,
        ),
        StepRecord(
            round_num=2,
            branch_id="b1",
            hypothesis=validation_hypothesis,
            patch=None,
            contract_passed=True,
            verification_passed=True,
            protocol_result=ProtocolResult(
                stage=ExperimentStage.VALIDATION,
                stats=holdout_stats,
                gate_outcome="pass",
                reason_codes=("validation_positive",),
                exposed_summary="validation secret should not be copied",
                raw_metrics_ref="/tmp/private-validation-metrics.json",
                case_ids=("validation-secret-case",),
                seed_set=(11,),
                case_feedback=holdout_case_feedback,
            ),
            decision=Decision.QUEUE_FROZEN,
            failure_stage=None,
            failure_detail=None,
        ),
        StepRecord(
            round_num=3,
            branch_id="b1",
            hypothesis=frozen_hypothesis,
            patch=None,
            contract_passed=True,
            verification_passed=True,
            protocol_result=ProtocolResult(
                stage=ExperimentStage.FROZEN,
                stats=frozen_stats,
                gate_outcome="fail",
                reason_codes=("frozen_positive",),
                exposed_summary="frozen secret should not be copied",
                raw_metrics_ref="/tmp/private-frozen-metrics.json",
                case_ids=("frozen-secret-case",),
                seed_set=(13,),
                case_feedback=holdout_case_feedback,
            ),
            decision=Decision.ABANDON,
            failure_stage=None,
            failure_detail=None,
        ),
        StepRecord(
            round_num=4,
            branch_id="b1",
            hypothesis=frozen_hypothesis,
            patch=None,
            contract_passed=True,
            verification_passed=True,
            protocol_result=ProtocolResult(
                stage=ExperimentStage.FROZEN,
                stats=frozen_stats,
                gate_outcome="pass",
                reason_codes=("frozen_positive_promote",),
                exposed_summary="frozen promote secret should not be copied",
                raw_metrics_ref="/tmp/private-frozen-promote-metrics.json",
                case_ids=("frozen-promote-secret-case",),
                seed_set=(17,),
                case_feedback=holdout_case_feedback,
            ),
            decision=Decision.PROMOTE,
            failure_stage=None,
            failure_detail=None,
        ),
    ]

    ctx = ContextManager().build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        active_hypotheses=[],
        blacklist=[],
        step_history=step_history,
    )
    system_blocks, user_prompt = _split_hypothesis_context(ctx)
    prompt_text = "\n".join(block["text"] for block in system_blocks) + user_prompt

    assert "private-validation-metrics" not in prompt_text
    assert "private-frozen-metrics" not in prompt_text
    assert "private-frozen-promote-metrics" not in prompt_text
    assert "raw_metrics_ref" not in prompt_text
    assert "validation-secret-case" not in prompt_text
    assert "frozen-secret-case" not in prompt_text
    assert "frozen-promote-secret-case" not in prompt_text
    assert "secret should not be copied" not in prompt_text
    assert "VALIDATION_ONLY_HYPOTHESIS_TEXT" not in prompt_text
    assert "FROZEN_ONLY_HYPOTHESIS_TEXT" not in prompt_text
    assert "validation_only_locus" not in prompt_text
    assert "frozen_only_locus" not in prompt_text
    assert "holdout-case-feedback-secret" not in prompt_text
    assert "holdout_secret_metric" not in prompt_text
    assert "holdout-secret-stem" not in prompt_text
    assert "QUEUE_FROZEN" not in prompt_text
    assert "PROMOTE" not in prompt_text
    assert "ABANDON" not in prompt_text
    assert "promoted=" not in prompt_text
    assert "failed_validation" not in prompt_text
    assert "failed_frozen" not in prompt_text
    assert "screening: win_rate=0.83" in prompt_text
    assert "median_delta=0.1234" in prompt_text
    assert "outcome=expand" in prompt_text
    assert "screening_expand=1" in prompt_text
    assert "n=1" in prompt_text
    assert "win_rate=0.42" not in prompt_text
    assert "median_delta=0.4242" not in prompt_text
    assert "win_rate=0.95" not in prompt_text
    assert "median_delta=9.1919" not in prompt_text
    assert "n=17" not in prompt_text
    assert "n=19" not in prompt_text
    assert "outcome=pass" not in prompt_text
    assert "outcome=fail" not in prompt_text


def test_contract_gate_validates_policy_surface_required_function_presence(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["search_space"]["editable"] = ["operators/*.py", "policies/*.py"]
    payload["research_surfaces"] = [
        {
            "name": "local",
            "kind": "operator",
            "description": "Local operators",
            "target_files": ["operators/*.py"],
        },
        {
            "name": "search_policy",
            "kind": "policy",
            "description": "Budget policy",
            "target_files": ["policies/search_policy.py"],
            "required_functions": [
                "baseline_time_fraction",
                "max_operator_rounds",
                "enable_post_baseline_operators",
            ],
            "create_new_allowed": False,
            "remove_allowed": False,
        },
    ]
    legacy = legacy_problem_spec_from_v1(ProblemSpecV1(**payload))
    gate = ContractGate(legacy)

    valid_patch = PatchProposal(
        file_path="policies/search_policy.py",
        action="modify",
        code_content=(
            "def baseline_time_fraction(instance, time_limit_sec):\n"
            "    return 0.8\n\n"
            "def max_operator_rounds(instance, time_limit_sec):\n"
            "    return 20\n\n"
            "def enable_post_baseline_operators(instance, time_limit_sec):\n"
            "    return True\n"
        ),
    )
    result = gate.validate_patch(valid_patch)
    c7 = next(check for check in result.checks if check.name == "C7_interface")
    assert c7.passed

    missing_patch = PatchProposal(
        file_path="policies/search_policy.py",
        action="modify",
        code_content=(
            "def baseline_time_fraction(instance, time_limit_sec):\n"
            "    return 0.8\n"
        ),
    )
    result = gate.validate_patch(missing_patch)
    c7 = next(check for check in result.checks if check.name == "C7_interface")
    assert not c7.passed
    assert "missing required functions" in c7.detail

    wrong_args_patch = PatchProposal(
        file_path="policies/search_policy.py",
        action="modify",
        code_content=(
            "def baseline_time_fraction(instance):\n"
            "    return 0.8\n\n"
            "def max_operator_rounds(instance, time_limit_sec):\n"
            "    return 20\n\n"
            "def enable_post_baseline_operators(instance, time_limit_sec):\n"
            "    return True\n"
        ),
    )
    result = gate.validate_patch(wrong_args_patch)
    c7 = next(check for check in result.checks if check.name == "C7_interface")
    assert c7.passed


def test_contract_gate_validates_declared_module_function_signatures(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["search_space"]["editable"] = ["policies/*.py"]
    payload["research_surfaces"] = [
        {
            "name": "dispatch_policy",
            "kind": "policy",
            "targets": {"files": ["policies/dispatch.py"]},
            "interface": {
                "required_functions": ["select_limit"],
                "function_signatures": {
                    "select_limit": ["instance", "time_limit_sec"]
                },
            },
        },
    ]
    gate = ContractGate(legacy_problem_spec_from_v1(ProblemSpecV1(**payload)))

    missing = gate.validate_patch(
        PatchProposal(
            file_path="policies/dispatch.py",
            action="modify",
            code_content="def other(instance, time_limit_sec):\n    return 1\n",
        )
    )
    c7 = next(check for check in missing.checks if check.name == "C7_interface")
    assert not c7.passed
    assert "missing required functions ['select_limit']" in c7.detail

    wrong_name = gate.validate_patch(
        PatchProposal(
            file_path="policies/dispatch.py",
            action="modify",
            code_content="def select_limit(problem, time_limit_sec):\n    return 1\n",
        )
    )
    c7 = next(check for check in wrong_name.checks if check.name == "C7_interface")
    assert not c7.passed
    assert "do not match declared prefix" in c7.detail

    extra_required = gate.validate_patch(
        PatchProposal(
            file_path="policies/dispatch.py",
            action="modify",
            code_content=(
                "def select_limit(instance, time_limit_sec, extra):\n"
                "    return 1\n"
            ),
        )
    )
    c7 = next(check for check in extra_required.checks if check.name == "C7_interface")
    assert not c7.passed
    assert "extra required positional parameters ['extra']" in c7.detail

    optional_extra = gate.validate_patch(
        PatchProposal(
            file_path="policies/dispatch.py",
            action="modify",
            code_content=(
                "def select_limit(instance, time_limit_sec, extra=None):\n"
                "    return 1\n"
            ),
        )
    )
    c7 = next(check for check in optional_extra.checks if check.name == "C7_interface")
    assert c7.passed


def test_contract_gate_validates_declared_static_return_values(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["search_space"]["editable"] = ["policies/*.py"]
    payload["research_surfaces"] = [
        {
            "name": "dispatch_policy",
            "kind": "policy",
            "targets": {"files": ["policies/dispatch.py"]},
            "interface": {
                "required_functions": ["select_mode", "select_limit"],
                "function_signatures": {
                    "select_mode": ["instance", "time_limit_sec"],
                    "select_limit": ["instance", "time_limit_sec"],
                },
                "return_values": {
                    "select_mode": {
                        "value_type": "str",
                        "allowed_literals": ["small", "large"],
                    },
                    "select_limit": {
                        "value_type": "int",
                        "numeric_range": [1, 10],
                    },
                },
            },
        },
    ]
    gate = ContractGate(legacy_problem_spec_from_v1(ProblemSpecV1(**payload)))

    good = gate.validate_patch(
        PatchProposal(
            file_path="policies/dispatch.py",
            action="modify",
            code_content=(
                "def select_mode(instance, time_limit_sec):\n"
                "    return 'small'\n\n"
                "def select_limit(instance, time_limit_sec):\n"
                "    return 5\n"
            ),
        )
    )
    c7 = next(check for check in good.checks if check.name == "C7_interface")
    assert c7.passed

    bad_literal = gate.validate_patch(
        PatchProposal(
            file_path="policies/dispatch.py",
            action="modify",
            code_content=(
                "def select_mode(instance, time_limit_sec):\n"
                "    return 'unknown'\n\n"
                "def select_limit(instance, time_limit_sec):\n"
                "    return 5\n"
            ),
        )
    )
    c7 = next(check for check in bad_literal.checks if check.name == "C7_interface")
    assert not c7.passed
    assert "expected one of" in c7.detail

    bad_range = gate.validate_patch(
        PatchProposal(
            file_path="policies/dispatch.py",
            action="modify",
            code_content=(
                "def select_mode(instance, time_limit_sec):\n"
                "    return 'small'\n\n"
                "def select_limit(instance, time_limit_sec):\n"
                "    return 99\n"
            ),
        )
    )
    c7 = next(check for check in bad_range.checks if check.name == "C7_interface")
    assert not c7.passed
    assert "outside declared range" in c7.detail


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


def test_contract_gate_uses_v2_targets_actions_and_interface(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["search_space"]["editable"] = ["operators/*.py", "policies/*.py"]
    payload["research_surfaces"] = [
        {
            "name": "dispatch_policy",
            "kind": "policy",
            "targets": {
                "files": ["policies/dispatch.py"],
                "create_new_allowed": False,
                "modify_allowed": True,
                "remove_allowed": False,
                "singleton": True,
            },
            "interface": {
                "required_functions": ["select_limit"],
                "return_contract": "problem-defined scalar value",
            },
        },
    ]
    legacy = legacy_problem_spec_from_v1(ProblemSpecV1(**payload))
    gate = ContractGate(legacy)

    remove_hypothesis = HypothesisProposal(
        hypothesis_text="Remove the dispatch policy.",
        change_locus="dispatch_policy",
        action="remove",
        target_file="policies/dispatch.py",
    )
    result = gate.validate_hypothesis(remove_hypothesis, [], [])
    c3 = next(check for check in result.checks if check.name == "C3_action_target")
    assert not c3.passed
    assert "not allowed" in c3.detail

    wrong_target = HypothesisProposal(
        hypothesis_text="Modify a policy through the wrong file.",
        change_locus="dispatch_policy",
        action="modify",
        target_file="operators/not_dispatch.py",
    )
    result = gate.validate_hypothesis(wrong_target, [], [])
    c3 = next(check for check in result.checks if check.name == "C3_action_target")
    assert not c3.passed
    assert "policies/dispatch.py" in c3.detail

    missing_patch = PatchProposal(
        file_path="policies/dispatch.py",
        action="modify",
        code_content="def other_function(instance):\n    return 1\n",
    )
    result = gate.validate_patch(missing_patch)
    c7 = next(check for check in result.checks if check.name == "C7_interface")
    assert not c7.passed
    assert "missing required functions ['select_limit']" in c7.detail

    valid_patch = PatchProposal(
        file_path="policies/dispatch.py",
        action="modify",
        code_content="def select_limit(instance):\n    return 1\n",
    )
    result = gate.validate_patch(valid_patch)
    c7 = next(check for check in result.checks if check.name == "C7_interface")
    assert c7.passed


def test_contract_gate_enforces_surface_action_and_target_rules(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["search_space"]["editable"] = ["operators/*.py", "policies/*.py"]
    payload["research_surfaces"] = [
        {
            "name": "search_policy",
            "kind": "policy",
            "description": "Budget policy",
            "target_files": ["policies/search_policy.py"],
            "create_new_allowed": False,
            "modify_allowed": True,
            "remove_allowed": False,
        },
    ]
    legacy = legacy_problem_spec_from_v1(ProblemSpecV1(**payload))
    gate = ContractGate(legacy)

    remove_hypothesis = HypothesisProposal(
        hypothesis_text="Remove the singleton policy.",
        change_locus="search_policy",
        action="remove",
        target_file="policies/search_policy.py",
    )
    result = gate.validate_hypothesis(remove_hypothesis, [], [])
    c3 = next(check for check in result.checks if check.name == "C3_action_target")
    assert not c3.passed
    assert "not allowed" in c3.detail

    wrong_target = HypothesisProposal(
        hypothesis_text="Modify a policy via the wrong file.",
        change_locus="search_policy",
        action="modify",
        target_file="operators/not_policy.py",
    )
    result = gate.validate_hypothesis(wrong_target, [], [])
    c3 = next(check for check in result.checks if check.name == "C3_action_target")
    assert not c3.passed
    assert "not in target files" in c3.detail


def test_contract_gate_validate_patch_enforces_hypothesis_action_and_surface_permissions(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["search_space"]["editable"] = ["operators/*.py", "policies/*.py"]
    payload["research_surfaces"] = [
        {
            "name": "search_policy",
            "kind": "policy",
            "description": "Budget policy",
            "target_files": ["policies/search_policy.py"],
            "create_new_allowed": False,
            "modify_allowed": True,
            "remove_allowed": False,
        },
        {
            "name": "scratch_policy",
            "kind": "policy",
            "description": "Scratch policy modules",
            "target_files": ["policies/*.py"],
            "create_new_allowed": True,
            "modify_allowed": False,
            "remove_allowed": True,
        },
    ]
    legacy = legacy_problem_spec_from_v1(ProblemSpecV1(**payload))
    gate = ContractGate(legacy)
    policy_code = "def choose_budget(instance):\n    return 1\n"

    modify_hypothesis = HypothesisProposal(
        hypothesis_text="Tune search policy.",
        change_locus="search_policy",
        action="modify",
        target_file="policies/search_policy.py",
    )
    legal_modify = PatchProposal(
        file_path="policies/search_policy.py",
        action="modify",
        code_content=policy_code,
    )
    delete_patch = PatchProposal(
        file_path="policies/search_policy.py",
        action="delete",
        code_content="",
    )
    create_disallowed = PatchProposal(
        file_path="policies/search_policy.py",
        action="create",
        code_content=policy_code,
    )
    scratch_create_hypothesis = HypothesisProposal(
        hypothesis_text="Create scratch policy.",
        change_locus="scratch_policy",
        action="create_new",
        target_file="policies/scratch.py",
    )
    scratch_remove_hypothesis = HypothesisProposal(
        hypothesis_text="Remove scratch policy.",
        change_locus="scratch_policy",
        action="remove",
        target_file="policies/scratch.py",
    )

    result = gate.validate_patch(legal_modify, approved_hypothesis=modify_hypothesis)
    c4b = next(check for check in result.checks if check.name == "C4b_patch_action_target")
    assert c4b.passed
    assert result.passed

    result = gate.validate_patch(delete_patch, approved_hypothesis=modify_hypothesis)
    c4b = next(check for check in result.checks if check.name == "C4b_patch_action_target")
    assert not c4b.passed
    assert "does not match approved hypothesis action" in c4b.detail

    result = gate.validate_patch(delete_patch)
    c4b = next(check for check in result.checks if check.name == "C4b_patch_action_target")
    assert not c4b.passed
    assert "not allowed" in c4b.detail

    result = gate.validate_patch(create_disallowed)
    c4b = next(check for check in result.checks if check.name == "C4b_patch_action_target")
    assert not c4b.passed
    assert "not allowed" in c4b.detail

    scratch_create = PatchProposal(
        file_path="policies/scratch.py",
        action="create",
        code_content=policy_code,
    )
    result = gate.validate_patch(
        scratch_create,
        approved_hypothesis=scratch_create_hypothesis,
    )
    c4b = next(check for check in result.checks if check.name == "C4b_patch_action_target")
    assert c4b.passed

    scratch_delete = PatchProposal(
        file_path="policies/scratch.py",
        action="delete",
        code_content="",
    )
    result = gate.validate_patch(
        scratch_delete,
        approved_hypothesis=scratch_remove_hypothesis,
    )
    c4b = next(check for check in result.checks if check.name == "C4b_patch_action_target")
    assert c4b.passed
    assert result.passed


def test_contract_gate_surface_wildcard_is_segment_aware(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "local",
            "kind": "operator",
            "description": "Local operators",
            "target_files": ["operators/*.py"],
        },
    ]
    legacy = legacy_problem_spec_from_v1(ProblemSpecV1(**payload))
    gate = ContractGate(legacy)
    direct = HypothesisProposal(
        hypothesis_text="Modify direct operator.",
        change_locus="local",
        action="modify",
        target_file="operators/local_a.py",
    )
    nested = HypothesisProposal(
        hypothesis_text="Modify nested operator.",
        change_locus="local",
        action="modify",
        target_file="operators/archive/evil.py",
    )

    direct_result = gate.validate_hypothesis(direct, [], [])
    nested_result = gate.validate_hypothesis(nested, [], [])
    direct_c3 = next(
        check for check in direct_result.checks if check.name == "C3_action_target"
    )
    nested_c3 = next(
        check for check in nested_result.checks if check.name == "C3_action_target"
    )

    assert direct_c3.passed
    assert nested_c3.passed is False
    assert "not in target files" in nested_c3.detail


def test_contract_gate_requires_operator_class_for_declared_operator_surface(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "local",
            "kind": "operator",
            "description": "Local operators",
            "target_files": ["operators/*.py"],
        },
    ]
    legacy = legacy_problem_spec_from_v1(ProblemSpecV1(**payload))
    gate = ContractGate(legacy)

    patch = PatchProposal(
        file_path="operators/op.py",
        action="create",
        code_content="WEIGHT = 0.5\n",
    )
    result = gate.validate_patch(patch)
    c7 = next(check for check in result.checks if check.name == "C7_interface")
    assert not c7.passed
    assert "operator class" in c7.detail
