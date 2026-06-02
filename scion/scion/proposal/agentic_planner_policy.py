"""Planner policy helpers for bounded Agentic Proposal Sessions."""

from __future__ import annotations

from typing import Any, Mapping

from scion.proposal.agentic_grounding import (
    _context_requires_solver_design_grounding,
    _forced_solver_design_target_file_read_args,
    _required_context_tool_names,
)
from scion.proposal.agentic_session_feedback import (
    _has_feedback_screening_history,
    _observation_satisfies_compact_requirement,
)
from scion.proposal.tools import (
    ProposalObservation,
    ProposalToolContext,
    ProposalToolFailureCode,
)
from scion.proposal.agentic_session_tools import (
    _active_solver_map_followup_calls,
    _has_relevant_algorithm_slice_read,
    _has_successful_reusable_observation,
    _missing_active_solver_map_followups,
)

_SOLVER_DESIGN_PLANNER_ALGORITHM_FILE_READ_LIMIT = 5


def _missing_required_context_error(
    observations: list[ProposalObservation],
    *,
    context: ProposalToolContext | None = None,
) -> str | None:
    observed_ok = {
        observation.tool_name
        for observation in observations
        if not observation.is_error
    }
    missing = [
        name
        for name in _required_context_tool_names(context)
        if name not in observed_ok
    ]
    if missing:
        return f"missing required proposal context tools: {', '.join(missing)}"
    return None


def _planner_context_satisfied(
    tool_registry: Any,
    context: ProposalToolContext,
    observations: list[ProposalObservation],
) -> bool:
    return _missing_planner_context_error(tool_registry, context, observations) is None


def _missing_planner_context_error(
    tool_registry: Any,
    context: ProposalToolContext,
    observations: list[ProposalObservation],
) -> str | None:
    required_error = _missing_required_context_error(
        observations,
        context=context,
    )
    if required_error is not None:
        return required_error
    available_feedback = _available_compact_feedback_tools(tool_registry, context)
    observed_ok = {
        observation.tool_name
        for observation in observations
        if _observation_satisfies_compact_requirement(context, observation)
    }
    missing_feedback = [
        tool_name for tool_name in available_feedback if tool_name not in observed_ok
    ]
    if missing_feedback:
        return "missing compact proposal feedback tools: " + ", ".join(
            missing_feedback
        )
    if _context_requires_solver_design_grounding(context):
        missing_map_followups = _missing_active_solver_map_followups(
            observations,
            target_file=context.forced_target_file,
            surface="solver_design",
        )
        if missing_map_followups:
            return (
                "missing active solver map follow-up tools after "
                "context.read_active_solver_map: "
                + ", ".join(missing_map_followups)
            )
        missing_target = _missing_forced_solver_design_target_context(
            context,
            observations,
        )
        if missing_target is not None:
            return missing_target
    return None


def _planner_required_context_status(
    tool_registry: Any,
    context: ProposalToolContext,
    observations: list[ProposalObservation],
) -> dict[str, Any]:
    """Model-facing stop constraints for mandatory generic context."""

    observed_ok = {
        observation.tool_name
        for observation in observations
        if not observation.is_error
    }
    required_missing = [
        name
        for name in _required_context_tool_names(context)
        if name not in observed_ok
    ]
    compact_feedback_missing = [
        name
        for name in _available_compact_feedback_tools(tool_registry, context)
        if name
        not in {
            observation.tool_name
            for observation in observations
            if _observation_satisfies_compact_requirement(context, observation)
        }
    ]
    map_followup_calls: list[tuple[str, Mapping[str, Any]]] = []
    target_source_call: tuple[str, Mapping[str, Any]] | None = None
    if _context_requires_solver_design_grounding(context):
        map_followup_calls = _active_solver_map_followup_calls(
            observations,
            target_file=context.forced_target_file,
            surface="solver_design",
        )
        target_args = _forced_solver_design_target_file_read_args(
            context,
            observations=observations,
        )
        if target_args is not None and not _forced_target_context_visible(
            context,
            observations,
            target_args,
        ):
            target_source_call = ("context.read_algorithm_file", target_args)

    missing_required_context: list[str] = []
    missing_required_context.extend(required_missing)
    missing_required_context.extend(compact_feedback_missing)
    missing_required_context.extend(name for name, _args in map_followup_calls)
    if target_source_call is not None:
        missing_required_context.append(
            f"context.read_algorithm_file({target_source_call[1].get('file_path')})"
        )
    next_required_tools = [
        {"tool_name": name, "args": dict(args)}
        for name, args in [
            *[(name, {}) for name in required_missing],
            *[(name, {}) for name in compact_feedback_missing],
            *map_followup_calls,
            *([target_source_call] if target_source_call is not None else []),
        ]
    ]
    missing_error = _missing_planner_context_error(
        tool_registry,
        context,
        observations,
    )
    if missing_error is None and missing_required_context:
        missing_error = (
            "missing required planner context before stop: "
            + ", ".join(list(dict.fromkeys(missing_required_context)))
        )
    return {
        "schema_version": "planner_required_context_status.v1",
        "stop_allowed": missing_error is None,
        "missing_required_context": list(dict.fromkeys(missing_required_context)),
        "next_required_tools": next_required_tools,
        "detail": missing_error,
        "rule": (
            "Do not return stop=true while stop_allowed=false. Call the next "
            "required tool first; framework completion is only a fail-closed "
            "fallback if the planner stops early."
        ),
    }


def _missing_forced_solver_design_target_context(
    context: ProposalToolContext,
    observations: list[ProposalObservation],
) -> str | None:
    target_args = _forced_solver_design_target_file_read_args(
        context,
        observations=observations,
    )
    if target_args is None:
        return None
    if _forced_target_context_visible(context, observations, target_args):
        return None
    target_file = str(target_args.get("file_path") or "").strip()
    return (
        "missing existing solver_design target source context before planner stop: "
        f"context.read_algorithm_file({target_file})"
    )


def _forced_target_context_visible(
    context: ProposalToolContext,
    observations: list[ProposalObservation],
    target_args: Mapping[str, Any],
) -> bool:
    if _has_relevant_algorithm_slice_read(
        observations,
        target_file=target_args.get("file_path"),
    ):
        return True
    return _has_successful_reusable_observation(
        observations,
        "context.read_algorithm_file",
        target_args,
        forced_surface=context.forced_surface or "solver_design",
    )


def _available_compact_feedback_tools(
    tool_registry: Any,
    context: ProposalToolContext,
) -> tuple[str, ...]:
    if tool_registry is None:
        return ()
    allowed = set(tool_registry.allowed_tools(context))
    available: list[str] = []
    if "memory.query" in allowed and (
        context.search_memory is not None or context.research_log is not None
    ):
        available.append("memory.query")
    has_screening_steps = _has_feedback_screening_history(context)
    if "feedback.query_screening" in allowed and has_screening_steps:
        available.append("feedback.query_screening")
    if "feedback.query_runtime" in allowed and has_screening_steps:
        available.append("feedback.query_runtime")
    return tuple(available)


def _planner_observation_requires_fallback(
    observation: ProposalObservation,
) -> bool:
    if not observation.is_error:
        return False
    if observation.tool_name in {"context.list_surfaces", "context.read_problem"}:
        return False
    return observation.failure_code in {
        ProposalToolFailureCode.SCHEMA_ERROR,
        ProposalToolFailureCode.PERMISSION_DENIED,
        ProposalToolFailureCode.NOT_FOUND,
        ProposalToolFailureCode.UNSUPPORTED,
    }


def _solver_design_planner_algorithm_file_read_budget_exhausted(
    context: ProposalToolContext,
    observations: list[ProposalObservation],
    *,
    next_tool_name: str,
    next_args: Mapping[str, Any] | None = None,
) -> bool:
    if not _context_requires_solver_design_grounding(context):
        return False
    if next_tool_name != "context.read_algorithm_file":
        return False
    args = dict(next_args or {})
    requested_path = _normalized_algorithm_read_path(args.get("file_path"))
    if not requested_path:
        return False
    if _planner_has_reusable_algorithm_read(observations, requested_path):
        return False
    target_path = _normalized_algorithm_read_path(context.forced_target_file)
    if target_path and requested_path == target_path:
        return False
    priority = _planner_algorithm_read_priority(
        context,
        requested_path,
        target_path=target_path,
    )
    if priority in {
        "primary_entrypoint",
        "integration_role",
        "integration_neighbor",
        "active_manifest",
    }:
        return False
    read_count = _successful_planner_algorithm_file_read_count(observations)
    hard_limit = _SOLVER_DESIGN_PLANNER_ALGORITHM_FILE_READ_LIMIT + 4
    if priority == "manifest":
        return read_count >= hard_limit
    if read_count < _SOLVER_DESIGN_PLANNER_ALGORITHM_FILE_READ_LIMIT:
        return False
    return True


def _successful_planner_algorithm_file_read_count(
    observations: list[ProposalObservation],
) -> int:
    file_paths: set[str] = set()
    for observation in observations:
        if observation.is_error or observation.tool_name != "context.read_algorithm_file":
            continue
        payload = observation.structured_payload
        file_path = ""
        if isinstance(payload, Mapping):
            if (
                observation.observation_type == "already_observed"
                or payload.get("already_observed")
            ):
                continue
            file_path = str(payload.get("file_path") or "").strip()
        file_paths.add(file_path or observation.observation_id)
    return len(file_paths)


def _planner_has_reusable_algorithm_read(
    observations: list[ProposalObservation],
    requested_path: str,
) -> bool:
    for observation in observations:
        if observation.is_error or observation.tool_name != "context.read_algorithm_file":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        path = _normalized_algorithm_read_path(payload.get("file_path"))
        if path == requested_path:
            return True
    return False


def _planner_algorithm_read_priority(
    context: ProposalToolContext,
    requested_path: str,
    *,
    target_path: str,
) -> str:
    role = ""
    active = False
    try:
        from scion.proposal.active_solver_snapshot import (
            list_algorithm_files_payload,
            solver_call_graph_payload,
        )

        rows = list_algorithm_files_payload(context, include_inactive=True)
        for item in rows:
            if _normalized_algorithm_read_path(item.get("file_path")) != requested_path:
                continue
            role = str(item.get("role") or "").lower()
            active = bool(item.get("active"))
            break
        if target_path:
            graph = solver_call_graph_payload(context)
            edges = graph.get("edges") if isinstance(graph, Mapping) else None
            if isinstance(edges, list):
                for edge in edges:
                    if not isinstance(edge, Mapping):
                        continue
                    endpoints = " ".join(
                        str(edge.get(key) or "")
                        for key in ("from", "to", "caller", "callee")
                    )
                    if requested_path in endpoints and target_path in endpoints:
                        return "integration_neighbor"
    except Exception:
        pass
    if "entrypoint" in role or "primary" in role:
        return "primary_entrypoint"
    if any(
        token in role
        for token in ("integration", "scheduler", "caller", "callee", "state", "config")
    ):
        return "integration_role"
    if active:
        return "active_manifest"
    if role:
        return "manifest"
    return ""


def _normalized_algorithm_read_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lstrip("/").strip()


def _should_defer_diagnosis_tool_to_code_phase(
    context: ProposalToolContext,
    name: str,
    args: Mapping[str, Any],
) -> bool:
    if name != "context.read_surface":
        return False
    if not _context_requires_solver_design_grounding(context):
        return False
    if str(args.get("detail") or "").strip() != "full":
        return False
    return bool(str(args.get("target_file") or "").strip())


def _push_deferred_code_phase_tool_call(
    state: Any,
    name: str,
    args: Mapping[str, Any],
) -> None:
    calls = getattr(state, "_deferred_code_phase_tool_calls", None)
    if not isinstance(calls, list):
        calls = []
        setattr(state, "_deferred_code_phase_tool_calls", calls)
    calls.append((name, dict(args)))


def _pop_deferred_code_phase_tool_call(
    state: Any,
) -> tuple[str, Mapping[str, Any]] | None:
    calls = getattr(state, "_deferred_code_phase_tool_calls", None)
    if not isinstance(calls, list) or not calls:
        return None
    name, args = calls.pop(0)
    return str(name), dict(args)
