"""Research-surface metadata and permission helpers."""

from __future__ import annotations

from typing import Any, Mapping

from scion.core.models import HypothesisProposal
from scion.core.path_match import normalize_relative_glob_pattern, segment_glob_match
from scion.proposal.context_manager import _get_adapter_problem_spec, _get_research_surfaces
from scion.proposal.tools.models import ProposalToolContext
from scion.proposal.tools.surface.compaction import (
    _coerce_compact_list,
    _compact_mapping_payload,
    _drop_empty_items,
)
from scion.proposal.tools.surface.constants import (
    _NONEMPTY_SEQUENCE_NOVELTY_FIELDS,
    _SEMANTIC_SIGNATURE_SCALAR_STRING_CHARS,
)
from scion.proposal.tools.utils import _attr, _normalize_rel_path


def _surface_allowed_actions(surface: Any | None) -> list[str]:
    if surface is None:
        return []
    targets = _attr(surface, "targets")
    allowed = []
    action_attrs = (
        ("create_new", "create_new_allowed"),
        ("modify", "modify_allowed"),
        ("remove", "remove_allowed"),
    )
    for action, attr in action_attrs:
        value = _attr(targets, attr, _attr(surface, attr, True))
        if value:
            allowed.append(action)
    return allowed
def _surface_permission_summary(
    surface: Any,
    *,
    allowed_actions: list[str],
    declared_targets: list[str],
) -> dict[str, Any]:
    return {
        "name": _attr(surface, "name"),
        "kind": _attr(surface, "kind"),
        "allowed_actions": list(allowed_actions),
        "declared_targets": list(declared_targets),
    }
def _surface_required_functions(surface: Any | None) -> list[str]:
    if surface is None:
        return []
    interface = _attr(surface, "interface")
    required = _attr(interface, "required_functions", None)
    if required is None:
        required = _attr(surface, "required_functions", [])
    return [str(name) for name in (required or [])]
def _surface_function_signatures(surface: Any | None) -> dict[str, list[str]]:
    if surface is None:
        return {}
    interface = _attr(surface, "interface")
    signatures = _attr(interface, "function_signatures", None)
    if not isinstance(signatures, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for raw_name, raw_args in signatures.items():
        name = str(raw_name).strip()
        if not name:
            continue
        if isinstance(raw_args, str):
            args = [arg.strip() for arg in raw_args.split(",") if arg.strip()]
        else:
            try:
                args = [str(arg).strip() for arg in raw_args if str(arg).strip()]
            except TypeError:
                args = []
        normalized[name] = args
    return normalized
def _surface_return_values(surface: Any | None) -> dict[str, Any]:
    if surface is None:
        return {}
    interface = _attr(surface, "interface")
    values = _attr(interface, "return_values", None) if interface is not None else None
    if not isinstance(values, Mapping):
        return {}
    return _compact_mapping_payload(values)
def _surface_for_patch_path(
    context: ProposalToolContext,
    file_path: str,
) -> Any | None:
    normalized = _normalize_rel_path(file_path)
    if normalized is None:
        return None
    for surface in _surfaces(context):
        if _target_declared(normalized, _surface_target_files(surface)):
            return surface
    return None
def _allowed_surface_names_for_context(context: ProposalToolContext) -> list[str]:
    forced_surface = str(context.forced_surface or "").strip()
    if forced_surface:
        return [forced_surface]
    return [
        str(surface or "").strip()
        for surface in context.active_problem_boundary_surfaces
        if str(surface or "").strip()
    ]
def _surface_read_boundary_violation(
    context: ProposalToolContext,
    requested_surface: str,
) -> str | None:
    allowed = _allowed_surface_names_for_context(context)
    if not allowed:
        return None
    requested = str(requested_surface or "").strip()
    if requested in set(allowed):
        return None
    return (
        "active_problem_boundary_constraint: context.read_surface may only "
        f"read active surface(s) {allowed!r}; got {requested!r}."
    )
def _surface_for_hypothesis(
    context: ProposalToolContext,
    hypothesis: HypothesisProposal,
) -> Any | None:
    surface = _find_surface(context, hypothesis.change_locus)
    if surface is not None:
        return surface
    if hypothesis.target_file:
        return _surface_for_patch_path(context, hypothesis.target_file)
    return None
def _surface_novelty_signature_requirement(surface: Any | None) -> dict[str, Any]:
    if surface is None:
        return {}
    novelty = _attr(surface, "novelty")
    strategy = str(_attr(novelty, "strategy", "") or "")
    fields = _coerce_compact_list(_attr(novelty, "signature_fields", []))
    if strategy != "semantic_signature" or not fields:
        return {}
    return _drop_empty_items(
        {
            "strategy": strategy,
            "required_fields": fields,
            "nonempty_sequence_fields": [
                field for field in fields if field in _NONEMPTY_SEQUENCE_NOVELTY_FIELDS
            ],
            "rule": (
                "Provide every required novelty_signature field. Fields listed "
                "under nonempty_sequence_fields must be non-empty arrays of "
                "component names, not null, false, empty strings, or empty arrays. "
                "Scalar string values must be at most "
                f"{_SEMANTIC_SIGNATURE_SCALAR_STRING_CHARS} characters."
            ),
        }
    )
def _surface_for_selected_or_patch_path(
    context: ProposalToolContext,
    file_path: str,
    selected_surface: str | None,
) -> Any | None:
    selected = str(selected_surface or "").strip()
    if selected:
        surface = _find_surface(context, selected)
        if surface is not None:
            return surface
    return _surface_for_patch_path(context, file_path)
def _surfaces(context: ProposalToolContext) -> list[Any]:
    adapter_spec = _get_adapter_problem_spec(context.adapter)
    return _get_research_surfaces(context.problem_spec, adapter_spec)
def _surface_list_for_context(
    context: ProposalToolContext,
    surfaces: list[Any],
) -> list[Any]:
    forced_surface = str(context.forced_surface or "").strip()
    if forced_surface:
        constrained = [
            surface
            for surface in surfaces
            if str(_attr(surface, "name") or "").strip() == forced_surface
        ]
        return constrained or surfaces
    boundary = {
        str(surface or "").strip()
        for surface in context.active_problem_boundary_surfaces
        if str(surface or "").strip()
    }
    if not boundary:
        return surfaces
    constrained = [
        surface
        for surface in surfaces
        if str(_attr(surface, "name") or "").strip() in boundary
    ]
    return constrained or surfaces
def _find_surface(context: ProposalToolContext, name: str) -> Any | None:
    for surface in _surfaces(context):
        if _attr(surface, "name") == name:
            return surface
    return None
def _surface_name(surface: Any) -> str:
    return str(_attr(surface, "name") or "").strip()
def _surface_target_files(surface: Any) -> list[str]:
    targets = _attr(surface, "targets")
    files = _attr(targets, "files", None) if targets is not None else None
    if files is None:
        files = _attr(surface, "target_files", [])
    return [str(path) for path in (files or []) if str(path)]
def _first_concrete_target(target_files: list[str]) -> str | None:
    for target in target_files:
        if not any(ch in target for ch in "*?["):
            return target
    return None
def _target_declared(target_file: str, declared_targets: list[str]) -> bool:
    normalized = _normalize_rel_path(target_file)
    if normalized is None:
        return False
    for pattern in declared_targets:
        try:
            pattern = normalize_relative_glob_pattern(pattern)
        except ValueError:
            continue
        if pattern == normalized:
            return True
        if segment_glob_match(normalized, pattern):
            return True
    return False

__all__ = [
    "_surface_allowed_actions",
    "_surface_permission_summary",
    "_surface_required_functions",
    "_surface_function_signatures",
    "_surface_return_values",
    "_surface_for_patch_path",
    "_allowed_surface_names_for_context",
    "_surface_read_boundary_violation",
    "_surface_for_hypothesis",
    "_surface_novelty_signature_requirement",
    "_surface_for_selected_or_patch_path",
    "_surfaces",
    "_surface_list_for_context",
    "_find_surface",
    "_surface_name",
    "_surface_target_files",
    "_first_concrete_target",
    "_target_declared",
]
