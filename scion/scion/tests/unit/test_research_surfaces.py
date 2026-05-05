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
    ChampionState,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
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
    _load_search_policy,
    improve_with_registry_operators,
)
from scion.proposal.context_manager import ContextManager
from scion.proposal.engine import _split_code_context, _split_hypothesis_context
from scion.runtime.audit import (
    format_runtime_audit_failure,
    runtime_audit_failure_from_runtime,
)


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


def test_problem_spec_without_research_surfaces_keeps_legacy_categories(
    tmp_path: Path,
) -> None:
    spec = ProblemSpecV1(**_problem_payload(str(tmp_path)))
    legacy = legacy_problem_spec_from_v1(spec)

    assert spec.research_surfaces is None
    assert legacy.operator_categories == ["local"]
    assert legacy.research_surfaces == []


def test_cvrp_problem_v1_exposes_search_policy_surface() -> None:
    spec = load_problem_spec_v1_from_yaml(
        Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem-v1.yaml"
    )
    legacy = legacy_problem_spec_from_v1(spec)

    assert legacy.operator_categories == [
        "route_local",
        "route_pair",
        "ruin_recreate",
        "search_policy",
    ]
    assert "policies/*.py" in legacy.search_space.editable
    assert "solver.py" in legacy.search_space.frozen


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
            ),
        ],
        search_space=SearchSpace(
            editable=["operators/*.py", "policies/*.py"],
            frozen=[],
            import_whitelist=["math"],
        ),
    )
    return ContractGate(spec)


def test_policy_modify_distinct_semantic_intents_pass_c10() -> None:
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
    )

    result = gate._c10_novelty(hyp, [existing], [])

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
    assert "policies/search_policy.py" in prompt_text
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


def test_contract_gate_validates_policy_surface_required_functions(
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
    assert not c7.passed
    assert "wrong policy function args" in c7.detail


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
