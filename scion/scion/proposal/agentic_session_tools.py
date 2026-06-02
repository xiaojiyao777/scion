"""Tool-selection helpers for Agentic Proposal Sessions."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from scion.core.models import HypothesisProposal
from scion.proposal.agentic_session_feedback import (
    _has_equivalent_feedback_observation,
    _observation_satisfies_compact_requirement,
)
from scion.proposal.agentic_utils import (
    _drop_empty_dict,
    _enum_value,
    _sanitize_agentic_value,
)
from scion.proposal.tools import ProposalObservation, ProposalToolContext
from scion.problem.providers import (
    active_subject_policy_matches_path,
    active_subject_policy_payload,
)

_HOLDOUT_SUMMARY_TOOL = "feedback.query_holdout_summary"
_PLANNER_HIDDEN_PREVIEW_TOOLS = frozenset(
    {
        "proposal.schema_preview",
        "proposal.target_permission_preview",
        "proposal.contract_preview",
        "proposal.algorithm_smoke",
    }
)
_ACTIVE_SOLVER_TOOL_ALLOWLIST = frozenset(
    {
        "context.read_active_solver_map",
        "context.read_operator_registry",
        "context.read_algorithm_slice",
        "context.read_active_solver_design",
        "context.read_solver_call_graph",
        "context.list_algorithm_files",
        "context.read_algorithm_file",
        "context.read_algorithm_symbol",
    }
)
_ACTIVE_SOLVER_FILE_READ_TOOLS = frozenset(
    {
        "context.read_algorithm_file",
        "context.read_algorithm_symbol",
    }
)
_CODE_PHASE_TOOL_ALLOWLIST = frozenset(
    {
        "context.list_surfaces",
        "context.read_problem",
        "context.read_surface",
        "context.read_objective_policy",
        "context.read_champion_summary",
        "context.read_branch_state",
        "memory.query",
        "feedback.query_screening",
        "feedback.query_runtime",
    }
) | _ACTIVE_SOLVER_TOOL_ALLOWLIST
_SINGLE_SUCCESS_OBSERVATION_TOOLS = (
    "context.list_surfaces",
    "context.read_problem",
    "context.read_branch_state",
    "memory.query",
    "context.read_active_solver_map",
    "context.read_active_solver_design",
    "context.read_solver_call_graph",
    "context.list_algorithm_files",
)
_ACTIVE_SOLVER_READ_DEFAULT_MAX_CHARS = 12000
_APS_SURFACE_READ_CODE_CHARS = 800
_APS_CODE_SURFACE_READ_CODE_CHARS = 12000
_APS_CODE_MODULE_SURFACE_READ_CODE_CHARS = 6000
_CODE_PHASE_SOLVER_DESIGN_FILE_READ_LIMIT = 5


def _filter_model_facing_tool_names(
    tool_names: tuple[str, ...] | list[str],
    context: ProposalToolContext,
) -> tuple[str, ...]:
    del context
    filtered: list[str] = []
    for raw_name in tool_names:
        name = str(raw_name or "").strip()
        if not name:
            continue
        if name == _HOLDOUT_SUMMARY_TOOL:
            # The direct tool remains available to deterministic callers, but
            # model-facing planner prompts cannot safely render a tool name
            # containing holdout terminology under strict sanitization.
            continue
        if name in _PLANNER_HIDDEN_PREVIEW_TOOLS:
            # Preview tools are deterministic gates over the approved
            # hypothesis/patch. Planner exploration must not generate preview
            # observations that can be mistaken for authoritative self-checks.
            continue
        filtered.append(name)
    return tuple(dict.fromkeys(filtered))


def _filter_code_phase_tool_names(
    tool_names: tuple[str, ...] | list[str],
    context: ProposalToolContext,
) -> tuple[str, ...]:
    allowed = set(_filter_model_facing_tool_names(tool_names, context))
    return tuple(sorted(allowed.intersection(_CODE_PHASE_TOOL_ALLOWLIST)))


def _budgeted_tool_args(
    name: str,
    args: Mapping[str, Any],
    *,
    selection_source: str,
    context: ProposalToolContext | None = None,
) -> Mapping[str, Any]:
    if name != "context.read_surface":
        return args
    budgeted = dict(args)
    if selection_source == "code_phase_required_compact":
        if budgeted.get("detail") != "compact":
            budgeted["detail"] = "compact"
        max_code_chars = budgeted.get("max_code_chars")
        if max_code_chars is None:
            budgeted["max_code_chars"] = _APS_SURFACE_READ_CODE_CHARS
            return budgeted
        try:
            requested = int(max_code_chars)
        except Exception:
            budgeted["max_code_chars"] = _APS_SURFACE_READ_CODE_CHARS
            return budgeted
        if requested > _APS_SURFACE_READ_CODE_CHARS or requested < 0:
            budgeted["max_code_chars"] = _APS_SURFACE_READ_CODE_CHARS
        return budgeted
    if selection_source.startswith("code_phase"):
        target_file = str(budgeted.get("target_file") or "").strip()
        surface = str(budgeted.get("surface") or "").strip()
        if _is_solver_design_algorithm_target(
            target_file,
            context=context,
            surface=surface,
        ):
            budgeted["section"] = "target_preview"
        if _is_solver_design_support_module_target(
            target_file,
            context=context,
            surface=surface,
        ):
            budgeted["max_code_chars"] = min(
                _APS_CODE_MODULE_SURFACE_READ_CODE_CHARS,
                _coerce_positive_int(
                    budgeted.get("max_code_chars"),
                    _APS_CODE_MODULE_SURFACE_READ_CODE_CHARS,
                ),
            )
            if budgeted.get("detail") != "full":
                budgeted["detail"] = "full"
            return budgeted
        if budgeted.get("detail") != "full":
            budgeted["detail"] = "full"
        max_code_chars = budgeted.get("max_code_chars")
        if max_code_chars is None:
            budgeted["max_code_chars"] = _APS_CODE_SURFACE_READ_CODE_CHARS
            return budgeted
        try:
            requested = int(max_code_chars)
        except Exception:
            budgeted["max_code_chars"] = _APS_CODE_SURFACE_READ_CODE_CHARS
            return budgeted
        if requested > _APS_CODE_SURFACE_READ_CODE_CHARS or requested < 0:
            budgeted["max_code_chars"] = _APS_CODE_SURFACE_READ_CODE_CHARS
        return budgeted
    if budgeted.get("detail") != "compact":
        budgeted["detail"] = "compact"
    max_code_chars = budgeted.get("max_code_chars")
    if max_code_chars is None:
        budgeted["max_code_chars"] = _APS_SURFACE_READ_CODE_CHARS
        return budgeted
    try:
        requested = int(max_code_chars)
    except Exception:
        return budgeted
    if requested > _APS_SURFACE_READ_CODE_CHARS:
        budgeted["max_code_chars"] = _APS_SURFACE_READ_CODE_CHARS
    elif selection_source == "selected_surface_required" and requested < 0:
        budgeted["max_code_chars"] = _APS_SURFACE_READ_CODE_CHARS
    return budgeted


def _observation_selection_payload(observation: ProposalObservation) -> dict[str, Any]:
    structured_payload = _sanitize_agentic_value(observation.structured_payload)
    digest_payload = {
        "tool_name": observation.tool_name,
        "observation_type": observation.observation_type,
        "summary": observation.summary,
        "structured_payload": structured_payload,
    }
    digest = hashlib.sha256(
        json.dumps(digest_payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "observation_id": observation.observation_id,
        "tool_name": observation.tool_name,
        "source": {
            "tool_call_id": observation.tool_call_id,
            "artifact_ref": observation.artifact_ref,
        },
        "phase": "agentic_tool_selection",
        "digest": digest,
        "observation_type": observation.observation_type,
        "summary": _sanitize_agentic_value(observation.summary),
        "is_error": observation.is_error,
        "failure_code": _enum_value(observation.failure_code),
        "exposure_level": _enum_value(observation.exposure_level),
    }


def _surface_names_from_observations(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> list[str]:
    names: list[str] = []
    for observation in observations:
        if observation.is_error or observation.tool_name != "context.list_surfaces":
            continue
        surfaces = observation.structured_payload.get("surfaces", ())
        if not isinstance(surfaces, (list, tuple)):
            continue
        for surface in surfaces:
            if not isinstance(surface, Mapping):
                continue
            for key in ("id", "name"):
                value = surface.get(key)
                if value:
                    names.append(str(value))
    return list(dict.fromkeys(names))


def _algorithm_file_path_guidance(
    context: ProposalToolContext,
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation] = (),
) -> dict[str, Any]:
    from scion.proposal.tools.active_solver import algorithm_file_path_guidance

    guidance = dict(algorithm_file_path_guidance(context))
    observed_allowed_paths = _algorithm_file_paths_from_observations(observations)
    if observed_allowed_paths:
        primary_path = str(guidance.get("primary_entrypoint_file_path") or "").strip()
        active_paths = _active_solver_design_paths_first(
            observed_allowed_paths,
            primary_path,
        )
        guidance["allowed_file_paths"] = active_paths
        guidance["allowed_file_count"] = len(observed_allowed_paths)
        guidance["allowed_paths_source"] = "existing_tool_observation"
        guidance["preferred_active_file_paths"] = active_paths
        if primary_path in observed_allowed_paths:
            guidance["primary_entrypoint_file_path"] = primary_path
        if active_paths:
            guidance["example_file_path"] = active_paths[0]
        else:
            guidance["example_file_path"] = observed_allowed_paths[0]
    guidance.setdefault(
        "sequence_rule",
        (
            "Call context.list_algorithm_files before context.read_algorithm_file "
            "or context.read_algorithm_symbol, then pass one returned file_path."
        ),
    )
    guidance.setdefault(
        "surface_id_rule",
        "solver_design is a research surface id; it is not a valid file_path.",
    )
    guidance.setdefault(
        "path_selection_rule",
        (
            "Use only provider-declared active solver files for solver_design "
            "optimization."
        ),
    )
    guidance.setdefault(
        "mechanism_owner_file_rule",
        (
            "Before drafting a solver_design hypothesis, read the active file "
            "that owns the mechanism you plan to change. Use active_algorithm_facts "
            "source_paths_or_symbols to choose the owner file when the fact packet "
            "already identifies one."
        ),
    )
    return guidance


def _active_solver_map_context(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    *,
    target_file: Any = None,
) -> dict[str, Any]:
    """Return planner-facing active-map ids from already collected observations."""

    payload = _latest_active_solver_map_payload(observations)
    if not payload:
        return {}
    target_path = _normalized_algorithm_read_path(target_file)
    registries = _active_solver_map_items(payload.get("operator_registries"))
    slices = _active_solver_map_items(payload.get("algorithm_slices"))
    recommended_registry = _recommended_registry_from_map(
        registries,
        target_path=target_path,
    )
    recommended_slice = _recommended_slice_from_map(
        slices,
        target_path=target_path,
    )
    return _drop_empty_dict(
        {
            "available": bool(payload.get("available", True)),
            "surface": payload.get("surface"),
            "subject_id": payload.get("subject_id"),
            "snapshot_digest": payload.get("snapshot_digest"),
            "read_receipt": payload.get("read_receipt"),
            "available_registry_ids": [
                item["registry_id"]
                for item in registries
                if item.get("registry_id")
            ],
            "recommended_registry_id": recommended_registry.get("registry_id"),
            "recommended_registry": recommended_registry,
            "available_slice_ids": [
                item["slice_id"]
                for item in slices
                if item.get("slice_id")
            ],
            "recommended_slice_id": recommended_slice.get("slice_id"),
            "recommended_slice": recommended_slice,
            "algorithm_slices": slices[:12],
            "operator_registries": registries[:12],
            "already_visible_source": _already_visible_solver_source(observations),
        }
    )


def _active_solver_map_followup_calls(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    *,
    target_file: Any = None,
    surface: Any = None,
    require_registry: bool = True,
    require_slice: bool = True,
) -> list[tuple[str, Mapping[str, Any]]]:
    """Return missing map-consumer calls that should precede broad source reads."""

    map_context = _active_solver_map_context(
        observations,
        target_file=target_file,
    )
    if not map_context.get("available"):
        return []
    effective_surface = str(surface or map_context.get("surface") or "").strip()
    calls: list[tuple[str, Mapping[str, Any]]] = []
    registry_id = str(map_context.get("recommended_registry_id") or "").strip()
    registry_args = _drop_empty_dict(
        {"surface": effective_surface, "registry_id": registry_id}
    )
    if (
        require_registry
        and registry_id
        and not _has_successful_reusable_observation(
            observations,
            "context.read_operator_registry",
            registry_args,
            forced_surface=effective_surface,
        )
        and not _has_attempted_active_map_target_read(
            observations,
            "context.read_operator_registry",
            registry_args,
            id_key="registry_id",
        )
    ):
        calls.append(
            (
                "context.read_operator_registry",
                registry_args,
            )
        )
    slice_id = str(map_context.get("recommended_slice_id") or "").strip()
    slice_args = _drop_empty_dict(
        {
            "surface": effective_surface,
            "slice_id": slice_id,
            "max_chars": _APS_CODE_MODULE_SURFACE_READ_CODE_CHARS,
        }
    )
    if (
        require_slice
        and slice_id
        and not _has_successful_reusable_observation(
            observations,
            "context.read_algorithm_slice",
            slice_args,
            forced_surface=effective_surface,
        )
        and not _has_attempted_active_map_target_read(
            observations,
            "context.read_algorithm_slice",
            slice_args,
            id_key="slice_id",
        )
    ):
        calls.append(
            (
                "context.read_algorithm_slice",
                slice_args,
            )
        )
    return calls


def _missing_active_solver_map_followups(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    *,
    target_file: Any = None,
    surface: Any = None,
) -> tuple[str, ...]:
    return tuple(
        name
        for name, _args in _active_solver_map_followup_calls(
            observations,
            target_file=target_file,
            surface=surface,
        )
    )


def _has_relevant_algorithm_slice_read(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    *,
    target_file: Any,
) -> bool:
    target_path = _normalized_algorithm_read_path(target_file)
    if not target_path:
        return False
    for observation in observations:
        if observation.is_error or observation.tool_name != "context.read_algorithm_slice":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        if not payload.get("available", True):
            continue
        if _normalized_algorithm_read_path(payload.get("file_path")) != target_path:
            continue
        content = str(payload.get("content") or "")
        if content or payload.get("content_digest"):
            return True
    return False


def _latest_active_solver_map_payload(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> Mapping[str, Any]:
    for observation in reversed(tuple(observations)):
        if observation.is_error or observation.tool_name != "context.read_active_solver_map":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        if payload.get("available") is False:
            continue
        return payload
    return {}


def _active_solver_map_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    items: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, Mapping):
            items.append(_sanitize_agentic_value(dict(item)))
    return items


def _recommended_registry_from_map(
    registries: list[Mapping[str, Any]],
    *,
    target_path: str,
) -> dict[str, Any]:
    if not registries:
        return {}
    ranked = sorted(
        registries,
        key=lambda item: _registry_target_score(item, target_path=target_path),
        reverse=True,
    )
    return dict(ranked[0])


def _registry_target_score(
    registry: Mapping[str, Any],
    *,
    target_path: str,
) -> tuple[int, int, int]:
    if not target_path:
        return (0, _count_mapping_items(registry.get("operators")), 0)
    owner = _normalized_algorithm_read_path(registry.get("owner_file"))
    operator_paths = {
        _normalized_algorithm_read_path(item.get("file_path"))
        for item in _active_solver_map_items(registry.get("operators"))
    }
    integration_paths = {
        _normalized_algorithm_read_path(item.get("file_path"))
        for item in _active_solver_map_items(registry.get("integration_points"))
    }
    score = 0
    if owner == target_path:
        score += 100
    if target_path in operator_paths:
        score += 80
    if target_path in integration_paths:
        score += 70
    target_leaf = target_path.rsplit("/", 1)[-1].removesuffix(".py")
    text = " ".join(
        str(registry.get(key) or "")
        for key in ("registry_id", "registry_kind", "owner_symbol")
    ).lower()
    if target_leaf and target_leaf in text:
        score += 20
    return (score, _count_mapping_items(registry.get("operators")), 0)


def _recommended_slice_from_map(
    slices: list[Mapping[str, Any]],
    *,
    target_path: str,
) -> dict[str, Any]:
    if not slices:
        return {}
    ranked = sorted(
        slices,
        key=lambda item: _slice_target_score(item, target_path=target_path),
        reverse=True,
    )
    return dict(ranked[0])


def _slice_target_score(
    slice_ref: Mapping[str, Any],
    *,
    target_path: str,
) -> tuple[int, int, int]:
    score = 0
    file_path = _normalized_algorithm_read_path(slice_ref.get("file_path"))
    if target_path and file_path == target_path:
        score += 100
    exposure = str(slice_ref.get("exposure_level") or slice_ref.get("slice_kind") or "")
    if exposure in {"body", "symbol_body"}:
        score += 20
    elif exposure in {"excerpt", "symbol_excerpt", "registry_block", "integration_block"}:
        score += 15
    elif exposure == "signature":
        score += 5
    purpose = str(slice_ref.get("purpose") or "").lower()
    if "integration" in purpose:
        score += 6
    if "registry" in purpose:
        score += 5
    token_estimate = _coerce_nonnegative_int(slice_ref.get("token_estimate")) or 0
    return (score, -token_estimate, 0)


def _already_visible_solver_source(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> list[dict[str, Any]]:
    visible: list[dict[str, Any]] = []
    for observation in observations:
        if observation.is_error:
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        if observation.tool_name == "context.read_algorithm_file":
            file_path = _normalized_algorithm_read_path(payload.get("file_path"))
            if not file_path:
                continue
            visible.append(
                _drop_empty_dict(
                    {
                        "tool_name": observation.tool_name,
                        "observation_id": observation.observation_id,
                        "file_path": file_path,
                        "coverage": "full"
                        if payload.get("truncated") is False
                        else "truncated",
                        "max_chars": payload.get("max_chars"),
                        "digest": payload.get("digest") or payload.get("sha256"),
                    }
                )
            )
        elif observation.tool_name == "context.read_algorithm_slice":
            file_path = _normalized_algorithm_read_path(payload.get("file_path"))
            slice_id = str(payload.get("slice_id") or "").strip()
            if not file_path and not slice_id:
                continue
            visible.append(
                _drop_empty_dict(
                    {
                        "tool_name": observation.tool_name,
                        "observation_id": observation.observation_id,
                        "slice_id": slice_id,
                        "file_path": file_path,
                        "symbols": payload.get("symbols"),
                        "line_start": payload.get("line_start"),
                        "line_end": payload.get("line_end"),
                        "content_digest": payload.get("content_digest"),
                        "truncated": payload.get("truncated"),
                    }
                )
            )
    return visible[-16:]


def _count_mapping_items(value: Any) -> int:
    if isinstance(value, (list, tuple)):
        return sum(1 for item in value if isinstance(item, Mapping))
    return 0


def _recommended_algorithm_file_path(
    guidance: Mapping[str, Any],
    preferred: Any = None,
) -> str:
    allowed_paths = [
        str(path)
        for path in guidance.get("allowed_file_paths", ())
        if str(path or "").strip()
    ]
    active_paths = [
        str(path)
        for path in guidance.get("preferred_active_file_paths", ())
        if str(path or "").strip()
    ]
    preferred_path = str(preferred or "").replace("\\", "/").strip()
    if preferred_path and preferred_path in set(allowed_paths):
        return preferred_path
    primary = str(guidance.get("primary_entrypoint_file_path") or "").strip()
    if primary and primary in set(allowed_paths):
        return primary
    if active_paths:
        return active_paths[0]
    if allowed_paths:
        return allowed_paths[0]
    return "<file_path returned by context.list_algorithm_files>"


def _solver_design_code_algorithm_file_read_budget_exhausted(
    context: ProposalToolContext,
    observations: list[ProposalObservation],
    *,
    hypothesis: HypothesisProposal,
    next_args: Mapping[str, Any],
) -> bool:
    from scion.proposal.agentic_grounding import _context_requires_solver_design_grounding

    is_solver_design_hypothesis = str(
        hypothesis.change_locus or ""
    ).strip() in {"solver_design", "solver_algorithm"}
    if (
        not is_solver_design_hypothesis
        and not _context_requires_solver_design_grounding(context)
    ):
        return False
    requested_path = _normalized_algorithm_read_path(next_args.get("file_path"))
    if not requested_path:
        return False
    target_path = _normalized_algorithm_read_path(hypothesis.target_file)
    if target_path and requested_path == target_path:
        return False
    if _has_successful_reusable_observation(
        observations,
        "context.read_algorithm_file",
        next_args,
        forced_surface=hypothesis.change_locus,
    ):
        return False
    current_paths = _successful_algorithm_file_read_paths(
        observations,
        count_already_observed=False,
    )
    if requested_path in set(current_paths):
        return False
    priority = _solver_design_algorithm_read_priority(
        context,
        requested_path,
        target_path=target_path,
    )
    hard_limit = _CODE_PHASE_SOLVER_DESIGN_FILE_READ_LIMIT + 4
    if priority in {
        "target",
        "primary_entrypoint",
        "integration_neighbor",
        "integration_role",
        "active_manifest",
    }:
        return False
    if priority == "manifest":
        return len(current_paths) >= hard_limit
    if len(current_paths) < _CODE_PHASE_SOLVER_DESIGN_FILE_READ_LIMIT:
        return False
    return True


def _algorithm_file_paths_from_observations(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> list[str]:
    for observation in reversed(tuple(observations)):
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        if observation.tool_name == "context.list_algorithm_files":
            paths = _file_paths_from_list_algorithm_files_payload(payload)
            if paths:
                return paths
        if observation.tool_name in _ACTIVE_SOLVER_FILE_READ_TOOLS:
            paths = _file_paths_from_algorithm_guidance_payload(payload)
            if paths:
                return paths
    return []


def _active_solver_design_paths_first(
    paths: list[str],
    primary_entrypoint_path: str = "",
) -> list[str]:
    active_paths = list(paths)
    if not primary_entrypoint_path or primary_entrypoint_path not in active_paths:
        return active_paths
    return [
        primary_entrypoint_path,
        *[
            path
            for path in active_paths
            if path != primary_entrypoint_path
        ],
    ]


def _successful_algorithm_file_read_paths(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    *,
    count_already_observed: bool = True,
) -> list[str]:
    paths: list[str] = []
    for observation in observations:
        if observation.is_error or observation.tool_name != "context.read_algorithm_file":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        if (
            not count_already_observed
            and (
                observation.observation_type == "already_observed"
                or payload.get("already_observed")
            )
        ):
            continue
        path = _normalized_algorithm_read_path(payload.get("file_path"))
        if path and path not in paths:
            paths.append(path)
    return paths


def _file_paths_from_list_algorithm_files_payload(
    payload: Mapping[str, Any],
) -> list[str]:
    files = payload.get("files")
    if not isinstance(files, (list, tuple)):
        return []
    paths: list[str] = []
    for item in files:
        if not isinstance(item, Mapping):
            continue
        path = str(item.get("file_path") or "").strip()
        if path:
            paths.append(path)
    return list(dict.fromkeys(paths))


def _file_paths_from_algorithm_guidance_payload(
    payload: Mapping[str, Any],
) -> list[str]:
    for key in ("allowed_file_paths", "allowed_files"):
        paths = payload.get(key)
        if not isinstance(paths, (list, tuple)):
            continue
        cleaned = [
            str(path).strip()
            for path in paths
            if str(path or "").strip()
        ]
        if cleaned:
            return list(dict.fromkeys(cleaned))
    return []


def _has_successful_surface_read(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    surface_name: str,
) -> bool:
    for observation in observations:
        if observation.is_error or observation.tool_name != "context.read_surface":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        surface = payload.get("surface")
        if isinstance(surface, Mapping) and surface.get("name") == surface_name:
            return True
    return False


def _has_successful_reusable_observation(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    tool_name: str,
    args: Mapping[str, Any],
    *,
    forced_surface: str | None = None,
) -> bool:
    if tool_name in {"feedback.query_screening", "feedback.query_runtime"}:
        return _has_equivalent_feedback_observation(
            observations,
            tool_name,
            args,
            default_surface=str(forced_surface or "").strip(),
        )
    if tool_name == "context.read_algorithm_file":
        return _has_successful_algorithm_file_read(observations, args)
    if tool_name == "context.read_algorithm_symbol":
        return _has_successful_algorithm_symbol_read(observations, args)
    if tool_name == "context.read_operator_registry":
        return _has_successful_active_map_target_read(
            observations,
            tool_name,
            args,
            id_key="registry_id",
        )
    if tool_name == "context.read_algorithm_slice":
        return _has_successful_active_map_target_read(
            observations,
            tool_name,
            args,
            id_key="slice_id",
        )
    if tool_name in _SINGLE_SUCCESS_OBSERVATION_TOOLS:
        return any(
            observation.tool_name == tool_name and not observation.is_error
            for observation in observations
        )
    if tool_name != "context.read_surface":
        return False
    requested_surface = str(args.get("surface") or forced_surface or "").strip()
    if not requested_surface:
        return False
    return _has_successful_surface_read(observations, requested_surface)


def _has_attempted_active_map_target_read(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    tool_name: str,
    args: Mapping[str, Any],
    *,
    id_key: str,
) -> bool:
    requested_id = str(args.get(id_key) or "").strip()
    if not requested_id:
        return False
    for observation in observations:
        if observation.tool_name != tool_name:
            continue
        payload = observation.structured_payload
        observed_id = ""
        if isinstance(payload, Mapping):
            observed_id = str(payload.get(id_key) or "").strip()
        if observed_id == requested_id:
            return True
        if observation.is_error and not observed_id:
            return True
    return False


def _has_successful_tool(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    tool_name: str,
) -> bool:
    return any(
        observation.tool_name == tool_name and not observation.is_error
        for observation in observations
    )


def _has_successful_code_phase_reusable_observation(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    tool_name: str,
    args: Mapping[str, Any],
    *,
    hypothesis: HypothesisProposal,
) -> bool:
    if tool_name == "memory.query":
        return False
    if tool_name in {"feedback.query_screening", "feedback.query_runtime"}:
        return _has_successful_reusable_observation(
            observations,
            tool_name,
            args,
            forced_surface=hypothesis.change_locus,
        )
    if tool_name == "context.read_surface":
        requested_surface = str(
            args.get("surface") or hypothesis.change_locus or ""
        ).strip()
        requested_target = str(
            args.get("target_file") or hypothesis.target_file or ""
        ).strip()
        return _has_code_phase_surface_read(
            observations,
            hypothesis,
            surface=requested_surface,
            target_file=requested_target or None,
        )
    reusable = _has_successful_reusable_observation(
        observations,
        tool_name,
        args,
        forced_surface=hypothesis.change_locus,
    )
    if reusable or tool_name in _ACTIVE_SOLVER_FILE_READ_TOOLS:
        return reusable
    return _has_successful_tool(observations, tool_name)


def _has_successful_algorithm_file_read(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    args: Mapping[str, Any],
) -> bool:
    requested_path = _normalized_algorithm_read_path(args.get("file_path"))
    if not requested_path:
        return False
    requested_max_chars = _requested_algorithm_read_max_chars(args)
    for observation in observations:
        if (
            observation.is_error
            or observation.tool_name != "context.read_algorithm_file"
        ):
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        observed_path = _normalized_algorithm_read_path(payload.get("file_path"))
        if observed_path != requested_path:
            continue
        if _algorithm_payload_satisfies_read_request(
            payload,
            requested_max_chars=requested_max_chars,
        ):
            return True
    return False


def _has_successful_algorithm_symbol_read(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    args: Mapping[str, Any],
) -> bool:
    requested_path = _normalized_algorithm_read_path(args.get("file_path"))
    requested_symbol = str(args.get("symbol") or "").strip()
    if not requested_path or not requested_symbol:
        return False
    requested_max_chars = _requested_algorithm_read_max_chars(args)
    for observation in observations:
        if (
            observation.is_error
            or observation.tool_name != "context.read_algorithm_symbol"
        ):
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        observed_path = _normalized_algorithm_read_path(payload.get("file_path"))
        observed_symbol = str(payload.get("symbol") or "").strip()
        if observed_path != requested_path or observed_symbol != requested_symbol:
            continue
        if _algorithm_payload_satisfies_read_request(
            payload,
            requested_max_chars=requested_max_chars,
        ):
            return True
    return False


def _has_successful_active_map_target_read(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    tool_name: str,
    args: Mapping[str, Any],
    *,
    id_key: str,
) -> bool:
    requested_id = str(args.get(id_key) or "").strip()
    if not requested_id:
        return False
    for observation in observations:
        if observation.is_error or observation.tool_name != tool_name:
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        if str(payload.get(id_key) or "").strip() == requested_id:
            return True
    return False


def _normalized_algorithm_read_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lstrip("/").strip()


def _requested_algorithm_read_max_chars(args: Mapping[str, Any]) -> int:
    parsed = _coerce_nonnegative_int(args.get("max_chars"))
    if parsed is None:
        return _ACTIVE_SOLVER_READ_DEFAULT_MAX_CHARS
    return parsed


def _algorithm_payload_satisfies_read_request(
    payload: Mapping[str, Any],
    *,
    requested_max_chars: int,
) -> bool:
    if payload.get("readable") is not True:
        return False
    if payload.get("already_observed"):
        coverage = payload.get("coverage")
        if isinstance(coverage, Mapping):
            observed_max = _coerce_nonnegative_int(coverage.get("max_chars"))
            preview_chars = _coerce_nonnegative_int(
                coverage.get("content_preview_chars")
            )
            size_chars = _coerce_nonnegative_int(coverage.get("size_chars"))
            truncated = bool(coverage.get("truncated"))
            if requested_max_chars <= 0:
                return True
            if (
                not truncated
                and size_chars is not None
                and preview_chars is not None
                and preview_chars >= min(size_chars, requested_max_chars)
            ):
                return True
            if observed_max is not None and requested_max_chars <= observed_max and not truncated:
                return True
        max_chars = _coerce_nonnegative_int(payload.get("max_chars"))
        return bool(max_chars is not None and requested_max_chars <= max_chars)
    if bool(payload.get("truncated")):
        return False
    observed_max_chars = _coerce_nonnegative_int(payload.get("max_chars"))
    if observed_max_chars is not None and requested_max_chars > observed_max_chars:
        return False
    content_preview = payload.get("content_preview")
    if content_preview is None:
        return requested_max_chars <= 0
    preview_chars = len(str(content_preview))
    size_chars = _coerce_nonnegative_int(payload.get("size_chars"))
    if size_chars is not None:
        required_preview_chars = min(size_chars, requested_max_chars)
        return preview_chars >= required_preview_chars
    if observed_max_chars is not None:
        required_preview_chars = min(observed_max_chars, requested_max_chars)
        return preview_chars >= required_preview_chars
    if not bool(payload.get("compacted_for_agentic_budget")):
        return True
    return preview_chars >= requested_max_chars


def _solver_design_algorithm_read_priority(
    context: ProposalToolContext,
    requested_path: str,
    *,
    target_path: str,
) -> str:
    if target_path and requested_path == target_path:
        return "target"
    rows = _solver_design_algorithm_file_rows(context)
    role = ""
    active = False
    for item in rows:
        if _normalized_algorithm_read_path(item.get("file_path")) != requested_path:
            continue
        role = str(item.get("role") or "").lower()
        active = bool(item.get("active"))
        break
    if "entrypoint" in role or "primary" in role:
        return "primary_entrypoint"
    if any(
        token in role
        for token in ("integration", "scheduler", "caller", "callee", "state", "config")
    ):
        return "integration_role"
    if target_path and _solver_design_call_graph_neighbors(
        context,
        requested_path,
        target_path,
    ):
        return "integration_neighbor"
    if active:
        return "active_manifest"
    if role:
        return "manifest"
    return ""


def _solver_design_algorithm_file_rows(
    context: ProposalToolContext,
) -> list[Mapping[str, Any]]:
    try:
        from scion.proposal.active_solver_snapshot import list_algorithm_files_payload

        return list(list_algorithm_files_payload(context, include_inactive=True))
    except Exception:
        return []


def _solver_design_call_graph_neighbors(
    context: ProposalToolContext,
    requested_path: str,
    target_path: str,
) -> bool:
    try:
        from scion.proposal.active_solver_snapshot import solver_call_graph_payload

        payload = solver_call_graph_payload(context)
    except Exception:
        return False
    edges = payload.get("edges") if isinstance(payload, Mapping) else None
    if not isinstance(edges, list):
        return False
    for edge in edges:
        if not isinstance(edge, Mapping):
            continue
        endpoints = " ".join(
            str(edge.get(key) or "")
            for key in ("from", "to", "caller", "callee")
        )
        if requested_path in endpoints and target_path in endpoints:
            return True
    return False


def _has_code_phase_surface_read(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    hypothesis: HypothesisProposal,
    *,
    surface: str | None = None,
    target_file: str | None = None,
) -> bool:
    expected_surface = str(surface or hypothesis.change_locus or "").strip()
    expected_target = str(target_file or hypothesis.target_file or "").strip()
    if not expected_surface:
        return False
    for observation in observations:
        if observation.is_error or observation.tool_name != "context.read_surface":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        observed_surface = payload.get("surface")
        if not (
            isinstance(observed_surface, Mapping)
            and observed_surface.get("name") == expected_surface
        ):
            continue
        if str(payload.get("detail") or "") != "full":
            continue
        observed_target = str(payload.get("target_file") or "").strip()
        if expected_target and observed_target and observed_target != expected_target:
            continue
        artifact = payload.get("current_artifact")
        if not isinstance(artifact, Mapping):
            return True
        if not bool(artifact.get("readable", True)):
            continue
        try:
            max_chars = int(artifact.get("max_chars") or 0)
        except (TypeError, ValueError):
            max_chars = 0
        required_chars = _APS_CODE_SURFACE_READ_CODE_CHARS
        if max_chars >= required_chars or not artifact.get("truncated"):
            return True
    return False


def _is_solver_design_support_module_target(
    target_file: Any,
    *,
    context: ProposalToolContext | None = None,
    surface: str | None = None,
) -> bool:
    policy = _active_subject_policy_for_context(context, surface=surface)
    return active_subject_policy_matches_path(
        policy,
        str(target_file or ""),
        include_entrypoints=False,
        include_support=True,
        include_compatibility=False,
    )


def _is_solver_design_algorithm_target(
    target_file: Any,
    *,
    context: ProposalToolContext | None = None,
    surface: str | None = None,
) -> bool:
    policy = _active_subject_policy_for_context(context, surface=surface)
    return active_subject_policy_matches_path(
        policy,
        str(target_file or ""),
        include_entrypoints=True,
        include_support=True,
        include_compatibility=True,
    )


def _active_subject_policy_for_context(
    context: ProposalToolContext | None,
    *,
    surface: str | None = None,
) -> dict[str, Any]:
    if context is None:
        return {}
    selected_surface = (
        str(surface or "").strip()
        or str(context.forced_surface or "").strip()
        or None
    )
    return active_subject_policy_payload(
        context=context,
        problem_spec=context.problem_spec,
        adapter=context.adapter,
        surface=selected_surface,
    )


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return parsed if parsed > 0 else default


def _coerce_nonnegative_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except Exception:
        return None
    return parsed if parsed >= 0 else None
