"""context.read_surface facade tool."""

from __future__ import annotations

from typing import Any

from scion.proposal.tools.base import _BaseReadOnlyTool
from scion.proposal.tools.models import (
    ProposalExposureLevel,
    ProposalObservation,
    ProposalToolContext,
    ProposalToolFailureCode,
    ProposalToolPermission,
    ReadSurfaceInput,
)
from scion.proposal.tools.surface.constants import (
    _COMPACT_SURFACE_CODE_CHARS,
    _FULL_SURFACE_CODE_CHARS,
)
from scion.proposal.tools.surface.metadata import (
    _allowed_surface_names_for_context,
    _find_surface,
    _first_concrete_target,
    _surface_list_for_context,
    _surface_name,
    _surface_read_boundary_violation,
    _surface_target_files,
    _surfaces,
    _target_declared,
)
from scion.proposal.tools.surface.payloads import (
    _surface_contract_metadata,
    _surface_interface_summary,
    _surface_read_payload,
)
from scion.proposal.tools.surface.readers import (
    _read_code_file_from_root,
    _surface_code_read_root,
)
from scion.proposal.tools.surface.support_artifacts import _read_solver_design_support_artifacts
from scion.proposal.tools.utils import _attr


class ContextReadSurfaceTool(_BaseReadOnlyTool):
    name = "context.read_surface"
    input_schema = ReadSurfaceInput
    permission = ProposalToolPermission.READ_CHAMPION_ARTIFACT

    def call(
        self,
        args: ReadSurfaceInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        surface = _find_surface(context, args.surface)
        if surface is None:
            available_surfaces = [
                str(_attr(candidate, "name") or _attr(candidate, "id") or "")
                for candidate in _surface_list_for_context(context, _surfaces(context))
            ]
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.NOT_FOUND,
                summary=f"Research surface not found: {args.surface}",
                structured_payload={
                    "requested_surface": args.surface,
                    "available_surfaces": [
                        surface_name
                        for surface_name in available_surfaces
                        if surface_name
                    ],
                },
                repair_hint="Use context.list_surfaces and select a declared surface.",
            )
        boundary_violation = _surface_read_boundary_violation(context, args.surface)
        if boundary_violation is not None:
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.PERMISSION_DENIED,
                summary=boundary_violation,
                structured_payload={
                    "requested_surface": args.surface,
                    "surface_state": "inactive_legacy",
                    "active_problem_boundary_surfaces": (
                        _allowed_surface_names_for_context(context)
                    ),
                    "rule": (
                        "Read active solver_design for hypothesis grounding. "
                        "Legacy/component surfaces are available only when "
                        "explicitly forced for diagnostics."
                    ),
                },
                repair_hint=(
                    "Use context.read_surface with surface='solver_design' or "
                    "the active forced surface."
                ),
            )
        target_files = _surface_target_files(surface)
        target_file = args.target_file or _first_concrete_target(target_files)
        if target_file is not None and not _target_declared(target_file, target_files):
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.PERMISSION_DENIED,
                summary=(
                    f"Target file {target_file!r} is not declared for surface "
                    f"{args.surface!r}."
                ),
                structured_payload={
                    "surface": args.surface,
                    "declared_targets": target_files,
                    "requested_target": target_file,
                },
                repair_hint="Read only files declared by the selected research surface.",
            )

        detail = args.detail
        code_char_limit = _surface_code_char_limit(
            detail=detail,
            requested_max=args.max_code_chars,
        )
        code_payload: dict[str, Any] | None = None
        support_artifacts: list[dict[str, Any]] = []
        if args.include_code and target_file:
            if context.champion is None:
                return self._error(
                    context,
                    failure_code=ProposalToolFailureCode.NOT_FOUND,
                    summary="No champion snapshot is available for surface read.",
                )
            source_root, source_kind = _surface_code_read_root(context)
            code_payload = _read_code_file_from_root(
                source_root,
                target_file,
                max_chars=code_char_limit,
                source_kind=source_kind,
            )
            if _surface_name(surface) == "solver_design" and args.section in {
                "all",
                "target_preview",
            }:
                support_artifacts = _read_solver_design_support_artifacts(
                    source_root,
                    target_files,
                    primary_target=target_file,
                    detail=detail,
                    primary_code_char_limit=code_char_limit,
                    source_kind=source_kind,
                )

        payload = {
            "surface": _surface_read_payload(
                surface,
                detail=detail,
                section=args.section,
            ),
            "surface_contract": _surface_contract_metadata(
                surface,
                detail=detail,
                section=args.section,
                current_artifact=code_payload,
            ),
            "interface_summary": _surface_interface_summary(
                surface,
                detail=detail,
                section=args.section,
            ),
            "detail": detail,
            "section": args.section,
            "declared_targets": target_files,
            "target_file": target_file,
            "current_artifact": code_payload,
            "support_artifacts": support_artifacts,
        }
        return self._observation(
            context,
            observation_type="surface_interface",
            summary=f"Returned declared interface for surface {args.surface}.",
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.CHAMPION_CODE,
        )
def _surface_code_char_limit(
    *,
    detail: str,
    requested_max: int | None,
) -> int:
    if requested_max is not None:
        return requested_max
    if detail == "full":
        return _FULL_SURFACE_CODE_CHARS
    return _COMPACT_SURFACE_CODE_CHARS

__all__ = [
    "ContextReadSurfaceTool",
    "_surface_code_char_limit",
]
