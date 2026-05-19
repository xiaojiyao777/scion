"""Target, interface, and forced-boundary preview tools."""

from __future__ import annotations

from typing import Any

from scion.core.models import HypothesisProposal
from scion.proposal.tools.base import _BaseReadOnlyTool
from scion.proposal.tools.models import (
    InterfacePreviewInput,
    ProposalExposureLevel,
    ProposalObservation,
    ProposalToolContext,
    ProposalToolPermission,
    TargetPermissionPreviewInput,
)
from scion.proposal.tools.previews.common import (
    _contract_gate,
    _module_classes,
    _module_level_functions,
    _patch_path_error,
    _problem_surface_preview,
)
from scion.proposal.tools.previews.contract import _checks_payload
from scion.proposal.tools.surface import (
    _drop_empty_items,
    _find_surface,
    _surface_allowed_actions,
    _surface_for_selected_or_patch_path,
    _surface_function_signatures,
    _surface_novelty_signature_requirement,
    _surface_payload,
    _surface_permission_summary,
    _surface_required_functions,
    _surface_return_values,
    _surface_target_files,
    _target_declared,
)
from scion.proposal.tools.utils import _normalize_rel_path

class TargetPermissionPreviewTool(_BaseReadOnlyTool):
    name = "proposal.target_permission_preview"
    input_schema = TargetPermissionPreviewInput
    permission = ProposalToolPermission.CONTRACT_PREVIEW
    max_result_chars = 24000

    def call(
        self,
        args: TargetPermissionPreviewInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        surface = _find_surface(context, args.change_locus)
        declared_targets = _surface_target_files(surface) if surface is not None else []
        allowed_actions = _surface_allowed_actions(surface)
        target_error = None
        if args.target_file:
            target_error = _patch_path_error(args.target_file)

        passed = surface is not None
        issues: list[str] = []
        if surface is None:
            issues.append(f"unknown research surface: {args.change_locus}")
        if args.action not in {"modify", "create_new", "remove"}:
            passed = False
            issues.append(f"invalid hypothesis action: {args.action}")
        elif surface is not None and args.action not in allowed_actions:
            passed = False
            issues.append(
                f"action '{args.action}' is not allowed for surface "
                f"'{args.change_locus}'"
            )
        if args.action in {"modify", "remove"} and not args.target_file:
            passed = False
            issues.append(f"action '{args.action}' requires target_file")
        if target_error is not None:
            passed = False
            issues.append(target_error)
        elif args.target_file and surface is not None:
            if not _target_declared(args.target_file, declared_targets):
                passed = False
                issues.append(
                    f"target_file '{args.target_file}' is not declared for surface "
                    f"'{args.change_locus}'"
                )
        forced_violation = _forced_action_target_violation(
            context,
            change_locus=args.change_locus,
            action=args.action,
            target_file=args.target_file,
        )
        if forced_violation is not None:
            passed = False
            issues.append(forced_violation)
        boundary_violation = _active_problem_boundary_violation(
            context,
            change_locus=args.change_locus,
        )
        if boundary_violation is not None:
            passed = False
            issues.append(boundary_violation)

        payload = {
            "passed": passed,
            "surface": (
                _surface_permission_summary(
                    surface,
                    allowed_actions=allowed_actions,
                    declared_targets=declared_targets,
                )
                if surface is not None
                else None
            ),
            "requested": {
                "change_locus": args.change_locus,
                "action": args.action,
                "target_file": args.target_file,
            },
            "allowed_actions": allowed_actions,
            "declared_targets": declared_targets,
            "forced_surface_constraint": _forced_surface_constraint_payload(context),
            "active_problem_boundary_constraint": (
                _active_problem_boundary_constraint_payload(context)
            ),
            "permission": {
                "surface_known": surface is not None,
                "action_allowed": bool(
                    surface is not None and args.action in allowed_actions
                ),
                "target_required": args.action in {"modify", "remove"},
                "target_path_safe": target_error is None,
                "target_declared": bool(
                    args.target_file
                    and surface is not None
                    and _target_declared(args.target_file, declared_targets)
                ),
            },
            "issues": issues,
            "workspace_materialized": False,
        }
        return self._observation(
            context,
            observation_type="target_permission_preview",
            summary=(
                "Target/action permission preview passed."
                if passed
                else "Target/action permission preview found issues."
            ),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )

class InterfacePreviewTool(_BaseReadOnlyTool):
    name = "proposal.interface_preview"
    input_schema = InterfacePreviewInput
    permission = ProposalToolPermission.CONTRACT_PREVIEW
    max_result_chars = 36000

    def call(
        self,
        args: InterfacePreviewInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        patch_payload = {
            "file_path": args.file_path,
            "action": args.action,
            "code_content": args.code_content,
        }
        from scion.proposal.tools.previews.schema import _schema_preview_patch_payload

        patch_preview = _schema_preview_patch_payload(patch_payload)
        if not patch_preview["passed"]:
            payload = {
                "passed": False,
                "patch_schema": patch_preview,
                "workspace_materialized": False,
            }
            return self._observation(
                context,
                observation_type="interface_preview",
                summary="Interface preview found schema issues.",
                structured_payload=payload,
                exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
            )

        patch = patch_preview["patch_object"]
        gate = _contract_gate(context)
        result = gate.validate_patch(
            patch,
            selected_surface=args.selected_surface,
        )
        interface_checks = [
            check for check in result.checks if check.name == "C7_interface"
        ]
        surface = _surface_for_selected_or_patch_path(
            context,
            patch.file_path,
            args.selected_surface,
        )
        interface_passed = bool(
            interface_checks and all(check.passed for check in interface_checks)
        )
        passed = interface_passed and result.passed
        if not interface_checks:
            passed = False
        problem_preview = None
        if passed:
            problem_preview = _problem_surface_preview(context, patch, surface)
            if problem_preview is not None:
                passed = passed and bool(problem_preview.get("passed"))
        payload = {
            "passed": passed,
            "surface": _surface_payload(surface) if surface is not None else None,
            "required_functions": _surface_required_functions(surface),
            "declared_function_signatures": _surface_function_signatures(surface),
            "declared_return_values": _surface_return_values(surface),
            "present_functions": _module_level_functions(args.code_content),
            "present_classes": _module_classes(args.code_content),
            "checks": _checks_payload(result.checks),
            "problem_preview": problem_preview,
            "workspace_materialized": False,
        }
        return self._observation(
            context,
            observation_type="interface_preview",
            summary=(
                "Interface preview passed."
                if passed
                else "Interface preview found issues."
            ),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )

def _forced_surface_constraint_payload(
    context: ProposalToolContext,
) -> dict[str, Any] | None:
    surface = str(context.forced_surface or "").strip()
    if not surface:
        return None
    return _drop_empty_items(
        {
            "surface": surface,
            "action": str(context.forced_action or "").strip() or None,
            "target_file": str(context.forced_target_file or "").strip() or None,
            "rule": (
                "Hypothesis outputs and proposal previews must use exactly this "
                "research surface"
                + (", action" if context.forced_action else "")
                + (", and target_file" if context.forced_target_file else "")
                + ". Off-surface hypotheses fail closed before code generation."
            ),
        }
    )

def _active_problem_boundary_constraint_payload(
    context: ProposalToolContext,
) -> dict[str, Any] | None:
    surfaces = [
        str(surface or "").strip()
        for surface in context.active_problem_boundary_surfaces
        if str(surface or "").strip()
    ]
    if not surfaces:
        return None
    novelty_requirements = _active_boundary_novelty_requirements(context, surfaces)
    return {
        "surfaces": surfaces,
        "rule": (
            "Hypothesis outputs must keep change_locus on the active "
            "problem-object boundary. Component policies may appear only as "
            "implementation hooks or attribution evidence, not replacement "
            "research goals."
        ),
        "novelty_signature_requirements": novelty_requirements,
    }

def _active_boundary_novelty_requirements(
    context: ProposalToolContext,
    surfaces: list[str],
) -> dict[str, Any]:
    requirements: dict[str, Any] = {}
    for surface_name in surfaces:
        surface = _find_surface(context, surface_name)
        requirement = _surface_novelty_signature_requirement(surface)
        if requirement:
            requirements[surface_name] = requirement
    return requirements

def _forced_hypothesis_violation(
    context: ProposalToolContext,
    hypothesis: HypothesisProposal,
) -> str | None:
    forced = _forced_action_target_violation(
        context,
        change_locus=hypothesis.change_locus,
        action=hypothesis.action,
        target_file=hypothesis.target_file,
    )
    if forced is not None:
        return forced
    return _active_problem_boundary_violation(
        context,
        change_locus=hypothesis.change_locus,
    )

def _active_problem_boundary_violation(
    context: ProposalToolContext,
    *,
    change_locus: str | None,
) -> str | None:
    if context.forced_surface:
        return None
    boundary = [
        str(surface or "").strip()
        for surface in context.active_problem_boundary_surfaces
        if str(surface or "").strip()
    ]
    if not boundary:
        return None
    actual = str(change_locus or "").strip()
    if actual in set(boundary):
        return None
    return (
        "active_problem_boundary_constraint: change_locus must stay within "
        f"{boundary!r}; got {actual!r}. Component policies are implementation "
        "hooks or attribution evidence, not replacement research goals."
    )

def _forced_action_target_violation(
    context: ProposalToolContext,
    *,
    change_locus: str | None,
    action: str | None,
    target_file: str | None,
) -> str | None:
    forced_surface = str(context.forced_surface or "").strip()
    if not forced_surface:
        return None
    actual_surface = str(change_locus or "").strip()
    if actual_surface != forced_surface:
        return (
            "forced_surface_constraint: change_locus must be "
            f"{forced_surface!r}, got {actual_surface!r}"
        )
    forced_action = str(context.forced_action or "").strip()
    if forced_action and str(action or "").strip() != forced_action:
        return (
            "forced_surface_constraint: action must be "
            f"{forced_action!r}, got {str(action or '').strip()!r}"
        )
    forced_target = str(context.forced_target_file or "").strip()
    if forced_target:
        actual_target = str(target_file or "").strip()
        if _normalize_rel_path(actual_target) != _normalize_rel_path(forced_target):
            return (
                "forced_surface_constraint: target_file must be "
                f"{forced_target!r}, got {actual_target!r}"
            )
    return None


__all__ = [
    "InterfacePreviewTool",
    "TargetPermissionPreviewTool",
    "_active_boundary_novelty_requirements",
    "_active_problem_boundary_constraint_payload",
    "_active_problem_boundary_violation",
    "_forced_action_target_violation",
    "_forced_hypothesis_violation",
    "_forced_surface_constraint_payload",
]
