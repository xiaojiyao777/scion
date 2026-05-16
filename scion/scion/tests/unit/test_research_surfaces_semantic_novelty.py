from __future__ import annotations

from types import SimpleNamespace

from scion.config.problem import (
    ProblemSpec,
    SearchSpace,
)
from scion.contract.gate import ContractGate
from scion.core.models import (
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
)
from scion.tests.unit.research_surface_helpers import (
    _budget_policy_hypothesis,
    _overlapping_surface_gate,
    _semantic_objective_gate,
    _surface_gate,
)


def test_patch_interface_uses_approved_surface_on_overlapping_targets() -> None:
    gate = _overlapping_surface_gate()
    patch = PatchProposal(
        file_path="shared/policy.py",
        action="modify",
        code_content=(
            "class LooksLikeOperator:\n"
            "    def execute(self, solution, rng):\n"
            "        return solution\n"
        ),
    )

    result = gate.validate_patch(patch, approved_hypothesis=_budget_policy_hypothesis())
    c7 = next(check for check in result.checks if check.name == "C7_interface")

    assert not c7.passed
    assert "policy surface" in c7.detail


def test_instance_identity_uses_approved_surface_on_overlapping_targets() -> None:
    gate = _overlapping_surface_gate()
    patch = PatchProposal(
        file_path="shared/policy.py",
        action="modify",
        code_content=(
            "def choose_budget(instance):\n"
            "    if instance.name == 'case-a':\n"
            "        return 2\n"
            "    return 1\n"
        ),
    )

    result = gate.validate_patch(patch, approved_hypothesis=_budget_policy_hypothesis())
    c9d = next(
        check for check in result.checks if check.name == "C9d_surface_instance_identity"
    )

    assert not c9d.passed
    assert "budget_policy" in c9d.detail
    assert "instance.name" in c9d.detail


def test_complexity_bound_uses_approved_surface_on_overlapping_targets() -> None:
    gate = _overlapping_surface_gate()
    patch = PatchProposal(
        file_path="shared/policy.py",
        action="modify",
        code_content=(
            "def choose_budget(instance):\n"
            "    for a in item_count:\n"
            "        for b in item_count:\n"
            "            for c in item_count:\n"
            "                pass\n"
            "    return 1\n"
        ),
    )

    result = gate.validate_patch(patch, approved_hypothesis=_budget_policy_hypothesis())
    c9c = next(check for check in result.checks if check.name == "C9c_complexity_bound")

    assert not c9c.passed
    assert "three-level problem-scale nested loops" in c9c.detail


def test_singleton_semantic_surface_without_signature_fails_before_duplicate_scan() -> None:
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
    assert "requires usable structured novelty_signature identity" in result.detail
    assert "candidate missing or invalid novelty_signature fields: budget_pattern" in (
        result.detail
    )


def test_singleton_semantic_surface_valid_signature_ignores_legacy_empty_record() -> None:
    gate = _surface_gate()
    existing = HypothesisRecord(
        hypothesis_id="h1",
        branch_id="b1",
        change_locus="budget_policy",
        action="modify",
        status="rejected",
        target_file="policies/budget.py",
        hypothesis_text="Legacy rejected record without structured identity.",
        base_champion_version=1,
    )
    hyp = HypothesisProposal(
        hypothesis_text="Use a distinct structured budget policy.",
        change_locus="budget_policy",
        action="modify",
        target_file="policies/budget.py",
        novelty_signature={"budget_pattern": "repair_heavy"},
    )

    result = gate.validate_hypothesis(
        hyp,
        [],
        [],
        rejected_hypotheses=[existing],
        current_champion_version=1,
    )

    assert result.passed


def test_singleton_semantic_surface_identical_unstructured_hypothesis_fails_c10() -> None:
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
    assert "requires usable structured novelty_signature identity" in result.detail


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


def test_semantic_signature_uses_problem_owned_novelty_signature_fields() -> None:
    gate = _surface_gate()
    existing = HypothesisRecord(
        hypothesis_id="h1",
        branch_id="b1",
        change_locus="budget_policy",
        action="modify",
        status="active",
        target_file="policies/budget.py",
        hypothesis_text="Use a large-instance budget split.",
        novelty_signature={"budget_pattern": ["construction_heavy", "repair_light"]},
    )
    same_structured = HypothesisProposal(
        hypothesis_text="Same pattern with different rationale.",
        change_locus="budget_policy",
        action="modify",
        target_file="policies/budget.py",
        novelty_signature={"budget_pattern": ["construction_heavy", "repair_light"]},
    )
    different_structured = HypothesisProposal(
        hypothesis_text="Different problem-owned budget pattern.",
        change_locus="budget_policy",
        action="modify",
        target_file="policies/budget.py",
        novelty_signature={"budget_pattern": ["repair_heavy", "construction_light"]},
    )

    same_result = gate._c10_novelty(same_structured, [existing], [])
    different_result = gate._c10_novelty(different_structured, [existing], [])

    assert not same_result.passed
    assert different_result.passed


def test_invalid_predicted_direction_fails_semantic_identity() -> None:
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
    assert "requires usable structured novelty_signature identity" in c10.detail
    assert "predicted_direction" in c10.detail


def test_arbitrary_objective_names_fail_semantic_identity() -> None:
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
    assert "requires usable structured novelty_signature identity" in c10.detail
    assert "target_objectives" in c10.detail


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


def test_unavailable_signature_field_fails_semantic_identity() -> None:
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
        target_objectives=("time",),
        expected_effect="Different free-text expected effect.",
        no_op_condition="Different free-text no-op condition.",
        target_runtime_effect="Different unsupported string field.",
    )

    result = gate._c10_novelty(hyp, [existing], [])

    assert not result.passed
    assert "requires usable structured novelty_signature identity" in result.detail
    assert "hypothesis_text" in result.detail


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


def test_dummy_singleton_config_unextractable_signature_fails_closed() -> None:
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
