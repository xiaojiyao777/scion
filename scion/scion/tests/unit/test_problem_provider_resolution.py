from __future__ import annotations

from types import SimpleNamespace

import pytest

from scion.problem.providers import (
    ProblemProviderError,
    _active_subject_code_constraint_providers,
    resolve_solver_design_prompt_provider,
)


class _ConstraintProvider:
    def __init__(self, version: str = "v1") -> None:
        self.version = version

    def active_subject_code_constraints(self, *args, **kwargs):
        return {"constraints": ("preserve the public solver interface",)}


class _AliasOwner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def active_subject_code_constraints_provider(self):
        self.calls.append("constraints")
        return _ConstraintProvider()

    def active_subject_policy_provider(self):
        self.calls.append("policy")
        return _ConstraintProvider()

    def solver_design_prompt_provider(self):
        self.calls.append("prompt")
        return _ConstraintProvider()


def test_each_owner_uses_one_explicit_factory_priority() -> None:
    owner = _AliasOwner()

    providers = _active_subject_code_constraint_providers(adapter=owner)

    assert len(providers) == 1
    assert providers[0].version == "v1"
    assert owner.calls == ["constraints"]


def test_adapter_and_spec_each_contribute_at_most_one_provider() -> None:
    adapter = SimpleNamespace(
        active_subject_code_constraints_provider=lambda: _ConstraintProvider("adapter"),
    )
    problem_spec = SimpleNamespace(
        active_subject_code_constraints_provider=lambda: _ConstraintProvider("spec"),
        adapter_import_path="",
    )

    providers = _active_subject_code_constraint_providers(
        adapter=adapter,
        problem_spec=problem_spec,
    )

    assert [provider.version for provider in providers] == ["adapter", "spec"]


def test_adapter_and_problem_spec_ids_must_be_consistent() -> None:
    adapter = SimpleNamespace(
        spec=SimpleNamespace(id="adapter-problem"),
        solver_design_prompt_provider=lambda: _ConstraintProvider(),
    )
    problem_spec = SimpleNamespace(
        id="declared-problem",
        adapter_import_path="",
    )

    with pytest.raises(ProblemProviderError, match="adapter id does not match"):
        resolve_solver_design_prompt_provider(
            adapter=adapter,
            problem_spec=problem_spec,
        )
