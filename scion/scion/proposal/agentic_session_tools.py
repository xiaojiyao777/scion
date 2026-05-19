"""Tool-selection helpers for Agentic Proposal Sessions."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from scion.core.models import HypothesisProposal
from scion.proposal.agentic_session_feedback import (
    _observation_satisfies_compact_requirement,
)
from scion.proposal.agentic_utils import _enum_value, _sanitize_agentic_value
from scion.proposal.tools import ProposalObservation, ProposalToolContext

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
    "context.read_active_solver_design",
    "context.read_solver_call_graph",
    "context.list_algorithm_files",
)
_ACTIVE_SOLVER_READ_DEFAULT_MAX_CHARS = 12000
_APS_SURFACE_READ_CODE_CHARS = 800
_APS_CODE_SURFACE_READ_CODE_CHARS = 12000
_APS_CODE_MODULE_SURFACE_READ_CODE_CHARS = 6000
_CODE_PHASE_SOLVER_DESIGN_FILE_READ_LIMIT = 3
_PRIMARY_SOLVER_DESIGN_ENTRYPOINT_PATH = "policies/baseline_algorithm.py"


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
        if _is_solver_design_algorithm_target(target_file):
            budgeted["section"] = "target_preview"
        if _is_solver_design_support_module_target(target_file):
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
        active_paths = _active_solver_design_paths_first(observed_allowed_paths)
        guidance["allowed_file_paths"] = active_paths
        guidance["allowed_file_count"] = len(observed_allowed_paths)
        guidance["allowed_paths_source"] = "existing_tool_observation"
        guidance["preferred_active_file_paths"] = active_paths
        guidance["primary_entrypoint_file_path"] = (
            _PRIMARY_SOLVER_DESIGN_ENTRYPOINT_PATH
            if _PRIMARY_SOLVER_DESIGN_ENTRYPOINT_PATH in observed_allowed_paths
            else guidance.get("primary_entrypoint_file_path", "")
        )
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
            "Use active solver files only for solver_design optimization: "
            "policies/baseline_algorithm.py and "
            "policies/baseline_modules/*.py."
        ),
    )
    return guidance


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
    current_paths = _successful_algorithm_file_read_paths(observations)
    if requested_path in set(current_paths):
        return False
    return len(current_paths) >= _CODE_PHASE_SOLVER_DESIGN_FILE_READ_LIMIT


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


def _active_solver_design_paths_first(paths: list[str]) -> list[str]:
    active_paths = list(paths)
    if _PRIMARY_SOLVER_DESIGN_ENTRYPOINT_PATH not in active_paths:
        return active_paths
    return [
        _PRIMARY_SOLVER_DESIGN_ENTRYPOINT_PATH,
        *[
            path
            for path in active_paths
            if path != _PRIMARY_SOLVER_DESIGN_ENTRYPOINT_PATH
        ],
    ]


def _successful_algorithm_file_read_paths(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> list[str]:
    paths: list[str] = []
    for observation in observations:
        if observation.is_error or observation.tool_name != "context.read_algorithm_file":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
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
        requested_surface = str(args.get("surface") or forced_surface or "").strip()
        requested_branch = str(args.get("branch_id") or "").strip()
        for observation in observations:
            if observation.tool_name != tool_name:
                continue
            if not _observation_satisfies_compact_requirement(None, observation):
                continue
            payload = observation.structured_payload
            if not isinstance(payload, Mapping):
                continue
            observed_surface = str(payload.get("surface") or "").strip()
            if (
                requested_surface
                and observed_surface
                and observed_surface != requested_surface
            ):
                continue
            observed_branch = str(payload.get("branch_id") or "").strip()
            if requested_branch and observed_branch != requested_branch:
                continue
            return True
        return False
    if tool_name == "context.read_algorithm_file":
        return _has_successful_algorithm_file_read(observations, args)
    if tool_name == "context.read_algorithm_symbol":
        return _has_successful_algorithm_symbol_read(observations, args)
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
    if tool_name in {
        "memory.query",
        "feedback.query_screening",
        "feedback.query_runtime",
    }:
        return False
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
        required_chars = (
            _APS_CODE_MODULE_SURFACE_READ_CODE_CHARS
            if _is_solver_design_support_module_target(expected_target)
            else _APS_CODE_SURFACE_READ_CODE_CHARS
        )
        if max_chars >= required_chars or not artifact.get("truncated"):
            return True
    return False


def _is_solver_design_support_module_target(target_file: Any) -> bool:
    normalized = str(target_file or "").replace("\\", "/").lstrip("/")
    return normalized.startswith("policies/baseline_modules/") and normalized.endswith(
        ".py"
    )


def _is_solver_design_algorithm_target(target_file: Any) -> bool:
    normalized = str(target_file or "").replace("\\", "/").lstrip("/")
    return normalized == "policies/baseline_algorithm.py" or (
        _is_solver_design_support_module_target(normalized)
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
