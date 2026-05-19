"""Active-boundary feedback scope and provenance helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from scion.core.models import StepRecord
from scion.proposal.tools.models import ProposalToolContext
from scion.proposal.tools.surface.compaction import _drop_empty_items


@dataclass(frozen=True)
class _FeedbackBoundaryScope:
    active_steps: list[StepRecord]
    inactive_reference_steps: list[StepRecord]
    boundary_surfaces: tuple[str, ...]
    requested_surface: str | None
    enforced: bool
    excluded_count: int

    def payload(self) -> dict[str, Any]:
        status = "not_configured"
        requested_status = "not_requested"
        if self.enforced:
            status = "enforced"
            if self.requested_surface:
                requested_status = (
                    "active_boundary"
                    if self.requested_surface in self.boundary_surfaces
                    else "inactive_reference"
                )
        elif self.requested_surface:
            requested_status = "unrestricted"
        return _drop_empty_items(
            {
                "status": status,
                "active_boundary_surfaces": list(self.boundary_surfaces),
                "requested_surface": self.requested_surface,
                "requested_surface_status": requested_status,
                "default_excludes_inactive_references": self.enforced,
                "inactive_references_require_explicit_surface": self.enforced,
                "excluded_inactive_reference_count": self.excluded_count,
            }
        )
def _feedback_boundary_scope(
    steps: list[StepRecord],
    *,
    context: ProposalToolContext,
    requested_surface: str | None,
) -> _FeedbackBoundaryScope:
    boundary = tuple(
        surface
        for surface in (
            str(item or "").strip()
            for item in (context.active_problem_boundary_surfaces or ())
        )
        if surface
    )
    requested = str(requested_surface or "").strip() or None
    if not boundary:
        return _FeedbackBoundaryScope(
            active_steps=list(steps),
            inactive_reference_steps=[],
            boundary_surfaces=(),
            requested_surface=requested,
            enforced=False,
            excluded_count=0,
        )

    boundary_set = set(boundary)
    active_steps: list[StepRecord] = []
    inactive_steps: list[StepRecord] = []
    excluded_count = 0
    for step in steps:
        surface = str(step.hypothesis.change_locus or "").strip()
        if surface in boundary_set:
            active_steps.append(step)
            continue
        excluded_count += 1
        if requested and surface == requested:
            inactive_steps.append(step)
    return _FeedbackBoundaryScope(
        active_steps=active_steps,
        inactive_reference_steps=inactive_steps,
        boundary_surfaces=boundary,
        requested_surface=requested,
        enforced=True,
        excluded_count=excluded_count,
    )
def _feedback_payload_provenance(
    *,
    source: str,
    feedback_scope: _FeedbackBoundaryScope,
) -> dict[str, Any]:
    role = (
        "active_boundary_evidence"
        if feedback_scope.enforced
        else "screening_evidence"
    )
    return _drop_empty_items(
        {
            "source": source,
            "evidence_role": role,
            "active_boundary_filter_applied": feedback_scope.enforced,
            "active_boundary_surfaces": list(feedback_scope.boundary_surfaces),
            "inactive_reference_policy": (
                "Boundary-external surfaces are excluded from active evidence by "
                "default and are returned only as inactive_reference rows when "
                "that surface is explicitly requested."
                if feedback_scope.enforced
                else None
            ),
        }
    )
def _feedback_step_provenance(
    step: StepRecord,
    *,
    boundary_surfaces: tuple[str, ...],
    role: str,
) -> dict[str, Any]:
    protocol = step.protocol_result
    return _drop_empty_items(
        {
            "source": "screening_protocol_result",
            "evidence_role": role,
            "surface": step.hypothesis.change_locus,
            "selected_surface": (
                protocol.selected_surface if protocol is not None else None
            ),
            "active_boundary_surfaces": list(boundary_surfaces),
        }
    )
def _with_feedback_provenance(
    payload: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    result = dict(payload)
    result["provenance"] = dict(provenance)
    return result

__all__ = [
    "_FeedbackBoundaryScope",
    "_feedback_boundary_scope",
    "_feedback_payload_provenance",
    "_feedback_step_provenance",
    "_with_feedback_provenance",
]
