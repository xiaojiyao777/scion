"""Proposal-pipeline boundary checks for hypothesis surface ownership."""
from __future__ import annotations

from typing import Any

from scion.core.models import HypothesisProposal

from .utils import _runtime_attr


def _active_problem_boundary_surfaces_for_runtime(runtime: Any) -> tuple[str, ...]:
    problem_spec = _runtime_attr(runtime, "spec")
    if problem_spec is None:
        problem_spec = _runtime_attr(runtime, "_spec")
    adapter = _runtime_attr(runtime, "adapter")
    if adapter is None:
        adapter = _runtime_attr(runtime, "_adapter")
    adapter_spec = _runtime_attr(adapter, "spec")
    if adapter_spec is None:
        adapter_spec = _runtime_attr(adapter, "_spec")
    names = _declared_solver_design_surface_names(problem_spec)
    if not names:
        names = _declared_solver_design_surface_names(adapter_spec)
    return tuple(names)


def _declared_solver_design_surface_names(problem_spec: Any) -> list[str]:
    if problem_spec is None:
        return []
    names: list[str] = []
    for surface in getattr(problem_spec, "research_surfaces", []) or []:
        name = str(getattr(surface, "name", "") or "").strip()
        if not name:
            continue
        kind = str(getattr(surface, "kind", "") or "").strip().lower()
        role = str(getattr(getattr(surface, "algorithm", None), "role", "") or "").lower()
        if (
            kind in {"solver_design", "solver_algorithm"}
            or "solver_design" in role
            or "solver_algorithm" in role
        ):
            names.append(name)
    return names


class BoundaryValidationMixin:
    @staticmethod
    def _forced_hypothesis_violation(
        hypothesis: HypothesisProposal,
        *,
        forced_surface: str | None,
        forced_action: str | None,
        forced_target_file: str | None,
    ) -> str | None:
        forced_surface = str(forced_surface or "").strip()
        if not forced_surface:
            return None
        if str(hypothesis.change_locus or "").strip() != forced_surface:
            return (
                "forced_surface_constraint: change_locus must be "
                f"{forced_surface!r}, got {hypothesis.change_locus!r}"
            )
        forced_action = str(forced_action or "").strip()
        if forced_action and str(hypothesis.action or "").strip() != forced_action:
            return (
                "forced_surface_constraint: action must be "
                f"{forced_action!r}, got {hypothesis.action!r}"
            )
        forced_target_file = str(forced_target_file or "").strip()
        if forced_target_file:
            target = str(hypothesis.target_file or "").strip()
            if target != forced_target_file:
                return (
                    "forced_surface_constraint: target_file must be "
                    f"{forced_target_file!r}, got {target!r}"
                )
        return None

    @staticmethod
    def _active_problem_boundary_violation(
        hypothesis: HypothesisProposal,
        *,
        active_problem_boundary_surfaces: tuple[str, ...],
        forced_surface: str | None = None,
    ) -> str | None:
        if str(forced_surface or "").strip():
            return None
        boundary = [
            str(surface or "").strip()
            for surface in active_problem_boundary_surfaces
            if str(surface or "").strip()
        ]
        if not boundary:
            return None
        actual = str(hypothesis.change_locus or "").strip()
        if actual in set(boundary):
            return None
        return (
            "active_problem_boundary_constraint: change_locus must stay within "
            f"{boundary!r}; got {actual!r}"
        )
