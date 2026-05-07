"""Interface check: confirm operator code exposes the configured execute signature.

This check intentionally uses AST only. Candidate operator code is tainted LLM
output, so verification must not import it in the orchestrator process just to
inspect a method signature.
"""
from __future__ import annotations

from typing import Any

from scion.core.models import CheckResult, PatchProposal
from scion.contract.surface_interface import check_surface_interface


def check_interface(
    patch: PatchProposal,
    candidate_workspace: str,
    *,
    problem_spec: Any | None = None,
    selected_surface: str | None = None,
    hypothesis: object | None = None,
    operator_execute_signature: str | None = None,
) -> CheckResult:
    """V2_interface: operator module has the configured execute signature."""
    surface_name = _selected_surface_name(
        selected_surface=selected_surface,
        hypothesis=hypothesis,
    )
    return check_surface_interface(
        patch,
        problem_spec=problem_spec,
        selected_surface=surface_name,
        operator_execute_signature=operator_execute_signature,
        check_name="V2_interface",
        severity="light",
        detail_suffix=" (AST)",
    )


def _selected_surface_name(
    *,
    selected_surface: str | None,
    hypothesis: object | None,
) -> str | None:
    if selected_surface is not None:
        surface = selected_surface.strip()
        return surface or None
    if hypothesis is None:
        return None
    surface = getattr(hypothesis, "change_locus", None)
    if not isinstance(surface, str):
        return None
    surface = surface.strip()
    return surface or None
