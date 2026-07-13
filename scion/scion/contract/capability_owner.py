"""Single owner for problem capabilities consumed during one Contract run."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from scion.contract.checks.problem_integration import (
    ProblemIntegrationProviderError,
    is_declared_solver_design_patch,
    resolve_contract_check_provider,
)
from scion.core.models import PatchProposal
from scion.problem.providers import (
    ProblemProviderError,
    active_subject_policy_payload_from_provider,
)


@dataclass(frozen=True)
class ContractProblemCapabilities:
    """Immutable provider/policy snapshot for one patch validation."""

    solver_design_patch: bool
    selected_surface: str | None
    contract_check_provider: Any | None
    active_subject_policy: Mapping[str, Any]
    contract_provider_error: str | None = None
    active_subject_policy_error: str | None = None

    @classmethod
    def empty(cls, *, selected_surface: str | None) -> "ContractProblemCapabilities":
        return cls(
            solver_design_patch=False,
            selected_surface=selected_surface,
            contract_check_provider=None,
            active_subject_policy=MappingProxyType({}),
        )


def resolve_contract_problem_capabilities(
    *,
    problem_spec: Any,
    adapter: Any,
    patch: PatchProposal,
    selected_surface: str | None,
) -> ContractProblemCapabilities:
    """Resolve one provider and materialize one policy for this patch run."""

    if not is_declared_solver_design_patch(
        problem_spec,
        patch,
        selected_surface=selected_surface,
    ):
        return ContractProblemCapabilities.empty(selected_surface=selected_surface)

    try:
        provider = resolve_contract_check_provider(problem_spec, adapter=adapter)
    except ProblemIntegrationProviderError as exc:
        return ContractProblemCapabilities(
            solver_design_patch=True,
            selected_surface=selected_surface,
            contract_check_provider=None,
            active_subject_policy=MappingProxyType({}),
            contract_provider_error=str(exc),
            active_subject_policy_error=str(exc),
        )

    try:
        policy = active_subject_policy_payload_from_provider(
            provider,
            surface=selected_surface,
            strict=True,
        )
        policy_error = None
    except ProblemProviderError as exc:
        policy = {}
        policy_error = str(exc)

    return ContractProblemCapabilities(
        solver_design_patch=True,
        selected_surface=selected_surface,
        contract_check_provider=provider,
        active_subject_policy=MappingProxyType(dict(policy)),
        active_subject_policy_error=policy_error,
    )
