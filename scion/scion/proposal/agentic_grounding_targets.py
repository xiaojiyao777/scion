"""Solver-design target inference and grounding boundary helpers for APS."""

from __future__ import annotations

from typing import Any, Mapping

from scion.core.models import HypothesisProposal
from scion.proposal.agentic_session_tools import (
    _algorithm_file_path_guidance,
    _algorithm_file_paths_from_observations,
    _has_relevant_algorithm_slice_read,
    _has_successful_reusable_observation,
    _has_successful_tool,
    _is_solver_design_algorithm_target,
)
from scion.proposal.agentic_session_tools_config import (
    _ACTIVE_SOLVER_SOURCE_READ_HEADROOM_CHARS,
)
from scion.proposal.tools import ProposalObservation, ProposalToolContext

_SOLVER_DESIGN_SURFACE_NAMES = frozenset({"solver_design", "solver_algorithm"})
_SOLVER_DESIGN_GROUNDING_TOOLS = (
    "context.read_active_solver_design",
    "context.read_solver_call_graph",
)
_SOLVER_DESIGN_FILE_DISCOVERY_TOOLS = ("context.list_algorithm_files",)
_APS_TARGET_ALGORITHM_FILE_READ_CHARS = _ACTIVE_SOLVER_SOURCE_READ_HEADROOM_CHARS
_APS_EXISTING_TARGET_PREGROUNDING_READ_LIMIT = 3


def _context_requires_solver_design_grounding(
    context: ProposalToolContext | None,
) -> bool:
    if context is None:
        return False
    forced_surface = str(context.forced_surface or "").strip()
    if forced_surface in _SOLVER_DESIGN_SURFACE_NAMES:
        return True
    boundary = {
        str(surface or "").strip()
        for surface in context.active_problem_boundary_surfaces
        if str(surface or "").strip()
    }
    return bool(boundary) and boundary.issubset(_SOLVER_DESIGN_SURFACE_NAMES)


def _is_solver_design_hypothesis(hypothesis: HypothesisProposal) -> bool:
    return str(hypothesis.change_locus or "").strip() in _SOLVER_DESIGN_SURFACE_NAMES


def _missing_solver_design_grounding_error(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    *,
    hypothesis: HypothesisProposal,
    context: ProposalToolContext | None = None,
) -> str | None:
    if not _is_solver_design_hypothesis(hypothesis):
        return None
    boundary_error = _solver_design_target_boundary_error(
        hypothesis,
        context=context,
        observations=observations,
    )
    if boundary_error is not None:
        return boundary_error
    observed_ok = {
        observation.tool_name
        for observation in observations
        if not observation.is_error
    }
    if _has_active_solver_embedded_call_graph(observations):
        observed_ok.add("context.read_solver_call_graph")
    missing = [
        tool_name
        for tool_name in _SOLVER_DESIGN_FILE_DISCOVERY_TOOLS
        if tool_name not in observed_ok
    ]
    missing.extend(
        tool_name
        for tool_name in _SOLVER_DESIGN_GROUNDING_TOOLS
        if tool_name not in observed_ok
    )
    target_read_args = _solver_design_target_file_read_args(
        hypothesis,
        context=context,
        observations=observations,
    )
    if target_read_args is not None and not _has_successful_reusable_observation(
        observations,
        "context.read_algorithm_file",
        target_read_args,
        forced_surface=hypothesis.change_locus,
    ) and not _has_relevant_algorithm_slice_read(
        observations,
        target_file=target_read_args.get("file_path"),
    ):
        missing.append(
            "context.read_algorithm_file"
            f"({target_read_args.get('file_path')})"
        )
    if not missing:
        return None
    return (
        "missing required solver_design grounding tools before hypothesis approval: "
        + ", ".join(missing)
    )


def _solver_design_target_file_read_args(
    hypothesis: HypothesisProposal | None,
    *,
    context: ProposalToolContext | None = None,
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation] = (),
) -> dict[str, Any] | None:
    if hypothesis is None:
        return None
    target_file = _normalize_solver_design_target_file(hypothesis.target_file)
    if not _is_solver_design_algorithm_target(
        target_file,
        context=context,
        surface=hypothesis.change_locus,
    ):
        return None
    existing_paths = _existing_algorithm_file_paths(
        context=context,
        observations=observations,
    )
    if existing_paths and target_file not in set(existing_paths):
        return None
    if not existing_paths and _target_declared_for_solver_design_surface(
        context,
        target_file,
    ):
        return None
    return {
        "surface": "solver_design",
        "file_path": target_file,
        "max_chars": _APS_TARGET_ALGORITHM_FILE_READ_CHARS,
    }


def _forced_solver_design_target_file_read_args(
    context: ProposalToolContext | None,
    *,
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation] = (),
) -> dict[str, Any] | None:
    if context is None or not _context_requires_solver_design_grounding(context):
        return None
    target_file = _inferred_solver_design_target_file(
        context,
        observations=observations,
    )
    if not _is_solver_design_algorithm_target(
        target_file,
        context=context,
        surface=context.forced_surface,
    ):
        return None
    existing_paths = _existing_algorithm_file_paths(
        context=context,
        observations=observations,
    )
    if existing_paths and target_file not in set(existing_paths):
        return None
    if not existing_paths and not _target_declared_for_solver_design_surface(
        context,
        target_file,
    ):
        return None
    return {
        "surface": "solver_design",
        "file_path": target_file,
        "max_chars": _APS_TARGET_ALGORITHM_FILE_READ_CHARS,
    }


def _pre_hypothesis_solver_design_target_file_read_args(
    context: ProposalToolContext | None,
    *,
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation] = (),
    limit: int = _APS_EXISTING_TARGET_PREGROUNDING_READ_LIMIT,
) -> list[dict[str, Any]]:
    if context is None or not _context_requires_solver_design_grounding(context):
        return []

    existing_paths = set(
        _existing_algorithm_file_paths(context=context, observations=observations)
    )
    forced_action = str(context.forced_action or "").strip()
    forced_target = _normalize_solver_design_target_file(context.forced_target_file)
    branch_current_paths = {
        _normalize_solver_design_target_file(path)
        for path in getattr(context, "branch_current_file_sources", {}) or {}
        if _normalize_solver_design_target_file(path)
    }
    non_map_observation_candidates = _solver_design_target_candidates_from_observations(
        tuple(
            observation
            for observation in observations
            if observation.tool_name != "context.read_active_solver_map"
        )
    )
    if (
        not forced_target
        and forced_action in {"modify", "remove"}
        and not branch_current_paths
        and not non_map_observation_candidates
        and not tuple(getattr(context, "step_history", ()) or ())
    ):
        return []
    target_candidates = (
        [forced_target]
        if forced_target
        else _solver_design_target_candidates(context, observations=observations)
    )
    read_args: list[dict[str, Any]] = []
    for target_file in target_candidates:
        if not _is_solver_design_algorithm_target(
            target_file,
            context=context,
            surface=context.forced_surface or "solver_design",
        ):
            continue
        if existing_paths and target_file not in existing_paths:
            continue
        if not existing_paths and not _target_declared_for_solver_design_surface(
            context,
            target_file,
        ):
            continue
        read_args.append(
            {
                "surface": "solver_design",
                "file_path": target_file,
                "max_chars": _APS_TARGET_ALGORITHM_FILE_READ_CHARS,
            }
        )
        if len(read_args) >= max(1, int(limit)):
            break
    return read_args


def _inferred_solver_design_target_file(
    context: ProposalToolContext | None,
    *,
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation] = (),
) -> str:
    """Return a generic existing solver-design target candidate, if one exists."""

    if context is None or not _context_requires_solver_design_grounding(context):
        return ""
    candidates = _solver_design_target_candidates(context, observations=observations)
    if not candidates:
        return ""
    existing_paths = set(
        _existing_algorithm_file_paths(context=context, observations=observations)
    )
    branch_current_paths = {
        _normalize_solver_design_target_file(path)
        for path in getattr(context, "branch_current_file_sources", {}) or {}
        if _normalize_solver_design_target_file(path)
    }
    for candidate in candidates:
        target_file = _normalize_solver_design_target_file(candidate)
        if not target_file:
            continue
        if not _is_solver_design_algorithm_target(
            target_file,
            context=context,
            surface=context.forced_surface,
        ):
            continue
        if (
            target_file in existing_paths
            or target_file in branch_current_paths
            or _target_declared_for_solver_design_surface(context, target_file)
        ):
            return target_file
    return ""


def _solver_design_target_candidates(
    context: ProposalToolContext,
    *,
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation] = (),
) -> list[str]:
    candidates: list[str] = []

    forced_action = str(context.forced_action or "").strip()
    forced_target = _normalize_solver_design_target_file(context.forced_target_file)
    if forced_target and (not forced_action or forced_action in {"modify", "remove"}):
        candidates.append(forced_target)

    candidates.extend(_solver_design_target_candidates_from_observations(observations))

    branch_id = str(getattr(context, "branch_id", None) or "").strip()
    for step in reversed(tuple(getattr(context, "step_history", ()) or ())):
        if branch_id and str(getattr(step, "branch_id", "") or "") != branch_id:
            continue
        hypothesis = getattr(step, "hypothesis", None)
        if hypothesis is not None and str(
            getattr(hypothesis, "action", "") or ""
        ) in {"modify", "remove"}:
            candidates.append(
                _normalize_solver_design_target_file(
                    getattr(hypothesis, "target_file", "")
                )
            )
        patch = getattr(step, "patch", None)
        for change in _patch_changes_for_target_candidates(patch):
            action = str(getattr(change, "action", "") or "")
            if action in {"modify", "delete"}:
                candidates.append(
                    _normalize_solver_design_target_file(
                        getattr(change, "file_path", "")
                    )
                )

    candidates.extend(
        _normalize_solver_design_target_file(path)
        for path in getattr(context, "branch_current_file_sources", {}) or {}
    )
    candidates.extend(_active_map_owner_file_candidates(observations))
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def _solver_design_target_candidates_from_observations(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> list[str]:
    candidates: list[str] = []
    for observation in reversed(tuple(observations)):
        if observation.is_error:
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        if observation.tool_name == "context.read_active_solver_map":
            candidates.extend(_active_map_owner_file_candidates([observation]))
            continue
        if observation.tool_name == "context.read_surface":
            candidates.extend(_surface_target_candidates(payload))
            continue
        candidates.extend(_target_file_values_from_payload(payload))
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def _surface_target_candidates(payload: Mapping[str, Any]) -> list[str]:
    candidates: list[str] = []
    for value in (
        payload.get("target_file"),
        _mapping_path(payload.get("current_artifact"), "file_path"),
        _mapping_path(payload.get("surface_contract"), "target_file"),
    ):
        target = _normalize_solver_design_target_file(value)
        if target:
            candidates.append(target)
    return list(dict.fromkeys(candidates))


def _target_file_values_from_payload(payload: Mapping[str, Any]) -> list[str]:
    candidates: list[str] = []
    stack: list[Any] = [payload]
    visited = 0
    while stack and visited < 256:
        visited += 1
        current = stack.pop()
        if isinstance(current, Mapping):
            action = str(current.get("action") or "").strip()
            if action in {"create", "create_new"}:
                continue
            for key in ("target_file", "hypothesis_target_file", "primary_target_file"):
                target = _normalize_solver_design_target_file(current.get(key))
                if target:
                    candidates.append(target)
            for value in current.values():
                if isinstance(value, (Mapping, list, tuple)):
                    stack.append(value)
        elif isinstance(current, (list, tuple)):
            stack.extend(current)
    return list(dict.fromkeys(candidates))


def _active_map_owner_file_candidates(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> list[str]:
    payload: Mapping[str, Any] = {}
    for observation in reversed(tuple(observations)):
        if observation.is_error or observation.tool_name != "context.read_active_solver_map":
            continue
        if isinstance(observation.structured_payload, Mapping):
            payload = observation.structured_payload
            break
    if not payload or payload.get("available") is False:
        return []
    weighted: list[tuple[tuple[int, int], str]] = []
    order = 0
    entrypoint_paths = {
        _normalize_solver_design_target_file(entrypoint.get("file_path"))
        for entrypoint in _mapping_items(payload.get("entrypoints"))
        if _normalize_solver_design_target_file(entrypoint.get("file_path"))
    }
    operator_file_counts: dict[str, int] = {}
    for registry in _mapping_items(payload.get("operator_registries")):
        for item in _mapping_items(registry.get("operators")):
            target = _normalize_solver_design_target_file(item.get("file_path"))
            if target:
                operator_file_counts[target] = operator_file_counts.get(target, 0) + 1
    registry_owner_counts: dict[str, int] = {}
    for registry in _mapping_items(payload.get("operator_registries")):
        target = _normalize_solver_design_target_file(registry.get("owner_file"))
        if target:
            registry_owner_counts[target] = registry_owner_counts.get(target, 0) + len(
                _mapping_items(registry.get("operators"))
            )
    for registry in _mapping_items(payload.get("operator_registries")):
        target = _normalize_solver_design_target_file(registry.get("owner_file"))
        if target:
            weighted.append(
                (
                    (
                        90 + registry_owner_counts.get(target, 0),
                        -order,
                    ),
                    target,
                )
            )
            order += 1
        for item in _mapping_items(registry.get("operators")):
            target = _normalize_solver_design_target_file(item.get("file_path"))
            if target:
                weighted.append(
                    ((100 + operator_file_counts.get(target, 0), -order), target)
                )
                order += 1
    for slice_ref in _mapping_items(payload.get("algorithm_slices")):
        target = _normalize_solver_design_target_file(slice_ref.get("file_path"))
        if target:
            base_score = 20 if target in entrypoint_paths else 70
            weighted.append(
                ((base_score + _slice_visibility_score(slice_ref), -order), target)
            )
            order += 1
    for integration in _mapping_items(payload.get("scheduler_integrations")):
        target = _normalize_solver_design_target_file(integration.get("file_path"))
        if target:
            weighted.append(((60, -order), target))
            order += 1
    for entrypoint in _mapping_items(payload.get("entrypoints")):
        target = _normalize_solver_design_target_file(entrypoint.get("file_path"))
        if target:
            weighted.append(((50, -order), target))
            order += 1
    for editable in _mapping_items(payload.get("editable_files")):
        target = _normalize_solver_design_target_file(editable.get("file_path"))
        if target:
            weighted.append(((40, -order), target))
            order += 1
    ordered = [target for _score, target in sorted(weighted, reverse=True)]
    return list(dict.fromkeys(ordered))


def _slice_visibility_score(slice_ref: Mapping[str, Any]) -> int:
    exposure = str(
        slice_ref.get("exposure_level") or slice_ref.get("slice_kind") or ""
    ).strip()
    if exposure in {"body", "symbol_body"}:
        return 20
    if exposure in {"excerpt", "symbol_excerpt", "registry_block", "integration_block"}:
        return 12
    if exposure == "signature":
        return 4
    return 0


def _mapping_items(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _mapping_path(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    return None


def _patch_changes_for_target_candidates(patch: Any) -> tuple[Any, ...]:
    if patch is None:
        return ()
    try:
        from scion.core.models import patch_file_changes

        return tuple(patch_file_changes(patch))
    except Exception:
        changes = [patch]
        extra = getattr(patch, "additional_changes", ()) or ()
        if isinstance(extra, (list, tuple)):
            changes.extend(extra)
        return tuple(changes)


def _solver_design_target_boundary_error(
    hypothesis: HypothesisProposal,
    *,
    context: ProposalToolContext | None,
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> str | None:
    target_file = _normalize_solver_design_target_file(hypothesis.target_file)
    if not target_file or context is None:
        return None
    existing_paths = _existing_algorithm_file_paths(
        context=context,
        observations=observations,
    )
    if target_file in set(existing_paths):
        return None
    if _target_declared_for_solver_design_surface(context, target_file):
        return None
    return (
        "solver_design target_file is outside declared patch paths: "
        f"{target_file}"
    )


def _normalize_solver_design_target_file(target_file: Any) -> str:
    return str(target_file or "").replace("\\", "/").lstrip("/").strip()


def _existing_algorithm_file_paths(
    *,
    context: ProposalToolContext | None,
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> list[str]:
    paths = _algorithm_file_paths_from_observations(observations)
    if paths:
        return paths
    if context is None:
        return []
    guidance = _algorithm_file_path_guidance(context, observations)
    allowed = guidance.get("allowed_file_paths", ())
    if not isinstance(allowed, (list, tuple)):
        return []
    return list(
        dict.fromkeys(
            _normalize_solver_design_target_file(path)
            for path in allowed
            if _normalize_solver_design_target_file(path)
        )
    )


def _target_declared_for_solver_design_surface(
    context: ProposalToolContext | None,
    target_file: str,
) -> bool:
    if context is None or not target_file:
        return False
    from scion.proposal.tools.surface import (
        _find_surface,
        _surface_target_files,
        _target_declared,
    )

    surface = _find_surface(context, "solver_design")
    if surface is None:
        return False
    return _target_declared(target_file, _surface_target_files(surface))


def _has_successful_solver_call_graph_grounding(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> bool:
    return _has_successful_tool(
        observations,
        "context.read_solver_call_graph",
    ) or _has_active_solver_embedded_call_graph(observations)


def _has_active_solver_embedded_call_graph(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> bool:
    for observation in reversed(tuple(observations)):
        if observation.is_error:
            continue
        if observation.tool_name != "context.read_active_solver_design":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        call_graph = payload.get("call_graph")
        if not isinstance(call_graph, Mapping):
            continue
        if any(
            key in call_graph
            for key in (
                "edges",
                "edge_count",
                "nodes",
                "node_count",
                "source_digest",
                "provenance",
            )
        ):
            return True
    return False
