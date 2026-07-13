from __future__ import annotations

from types import SimpleNamespace

from scion.config.problem import ProblemSpec, SearchSpace
from scion.contract.gate import ContractGate
from scion.core.models import HypothesisProposal, PatchProposal
from scion.tests.unit.research_surface_helpers import (
    _budget_policy_hypothesis,
    _overlapping_surface_gate,
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

    result = gate.validate_patch(
        patch,
        approved_hypothesis=_budget_policy_hypothesis(),
    )
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

    result = gate.validate_patch(
        patch,
        approved_hypothesis=_budget_policy_hypothesis(),
    )
    c9d = next(
        check
        for check in result.checks
        if check.name == "C9d_surface_instance_identity"
    )

    assert not c9d.passed
    assert "budget_policy" in c9d.detail
    assert "instance.name" in c9d.detail


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
    hypothesis = HypothesisProposal(
        hypothesis_text="Try a bounded local move.",
        change_locus="local",
        action="modify",
        target_file="operators/local.py",
    )

    result = gate.validate_hypothesis(hypothesis)

    assert not result.passed
    assert "unsupported research surface kind 'oprator'" in result.failure_reason
