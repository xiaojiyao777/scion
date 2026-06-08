"""Generic dispatch for problem-owned surface-integration checks.

`solver_design` is a Scion v0.4 first-class surface contract. Problem packages
own the concrete algorithm API and integration rules behind this generic hook.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scion.contract.checks.problem_integration import (
    ProblemIntegrationCheckRequest,
    ProblemIntegrationProviderError,
    is_declared_solver_design_patch,
    resolve_contract_check_provider,
)
from scion.core.models import PatchProposal


@dataclass(frozen=True)
class SolverDesignIntegrationResult:
    passed: bool
    detail: str


def check_solver_design_integration(
    patch: PatchProposal,
    *,
    problem_spec: Any,
    adapter: Any = None,
    selected_surface: str | None,
    champion_file_content,
) -> SolverDesignIntegrationResult:
    """Dispatch C9e to a problem-owned provider when the surface declares it."""

    if not is_declared_solver_design_patch(
        problem_spec,
        patch,
        selected_surface=selected_surface,
    ):
        return SolverDesignIntegrationResult(True, "not a solver_design patch")

    try:
        provider = resolve_contract_check_provider(problem_spec, adapter=adapter)
    except ProblemIntegrationProviderError as exc:
        return SolverDesignIntegrationResult(False, str(exc))
    if provider is None:
        return SolverDesignIntegrationResult(
            False,
            "problem-owned surface integration check provider is required for "
            "solver_design patches",
        )

    check = getattr(provider, "check_solver_design_integration", None)
    if not callable(check):
        return SolverDesignIntegrationResult(
            False,
            "problem-owned contract check provider does not implement "
            "check_solver_design_integration",
        )

    request = ProblemIntegrationCheckRequest(
        problem_spec=problem_spec,
        patch=patch,
        selected_surface=selected_surface,
        champion_file_content=champion_file_content,
    )
    try:
        return _coerce_result(check(request))
    except Exception as exc:
        return SolverDesignIntegrationResult(
            False,
            f"problem-owned surface integration check failed: {exc}",
        )


def _coerce_result(result: Any) -> SolverDesignIntegrationResult:
    passed = getattr(result, "passed", None)
    detail = getattr(result, "detail", None)
    if passed is None:
        raise TypeError("provider result must expose a 'passed' field")
    if detail is None:
        reasons = getattr(result, "reasons", ())
        detail = "; ".join(str(reason) for reason in reasons) if reasons else ""
    detail_text = str(detail or "problem-owned surface integration check")
    return SolverDesignIntegrationResult(bool(passed), detail_text)
