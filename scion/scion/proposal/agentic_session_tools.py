"""Tool-selection helpers for Agentic Proposal Sessions."""

from __future__ import annotations

from typing import Any, Mapping

from scion.proposal.agentic_session_tools_active_solver import (
    _active_solver_map_context,
    _active_solver_map_followup_calls,
    _active_solver_design_paths_first,
    _active_solver_map_items,
    _already_visible_solver_source,
    _algorithm_file_path_guidance,
    _algorithm_file_paths_from_observations,
    _active_subject_policy_for_context,
    _count_mapping_items,
    _file_paths_from_algorithm_guidance_payload,
    _file_paths_from_list_algorithm_files_payload,
    _has_relevant_algorithm_slice_read,
    _is_solver_design_algorithm_target,
    _is_solver_design_support_module_target,
    _latest_active_solver_map_payload,
    _missing_active_solver_map_followups,
    _recommended_registry_from_map,
    _recommended_algorithm_file_path,
    _recommended_slice_from_map,
    _registry_target_score,
    _slice_target_score,
    _solver_design_code_algorithm_file_read_budget_exhausted,
    _solver_design_algorithm_file_rows,
    _solver_design_algorithm_read_priority,
    _solver_design_call_graph_neighbors,
)
from scion.proposal.agentic_session_tools_config import (
    _ACTIVE_SOLVER_FILE_READ_TOOLS,
    _ACTIVE_SOLVER_READ_DEFAULT_MAX_CHARS,
    _ACTIVE_SOLVER_TOOL_ALLOWLIST,
    _APS_CODE_MODULE_SURFACE_READ_CODE_CHARS,
    _APS_CODE_SURFACE_READ_CODE_CHARS,
    _APS_SURFACE_READ_CODE_CHARS,
    _CODE_PHASE_SOLVER_DESIGN_FILE_READ_LIMIT,
    _CODE_PHASE_TOOL_ALLOWLIST,
    _HOLDOUT_SUMMARY_TOOL,
    _PLANNER_HIDDEN_PREVIEW_TOOLS,
    _SINGLE_SUCCESS_OBSERVATION_TOOLS,
)
from scion.proposal.agentic_session_tools_observations import (
    _coerce_nonnegative_int,
    _algorithm_payload_satisfies_read_request,
    _has_attempted_active_map_target_read,
    _has_code_phase_surface_read,
    _has_successful_active_map_target_read,
    _has_successful_algorithm_file_read,
    _has_successful_algorithm_symbol_read,
    _has_successful_code_phase_reusable_observation,
    _has_successful_reusable_observation,
    _has_successful_surface_read,
    _has_successful_tool,
    _normalized_algorithm_read_path,
    _observation_selection_payload,
    _requested_algorithm_read_max_chars,
    _successful_algorithm_file_read_paths,
    _surface_names_from_observations,
)
from scion.proposal.tools import ProposalToolContext


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


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return parsed if parsed > 0 else default
