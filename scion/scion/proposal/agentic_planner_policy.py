"""Planner policy helpers for bounded Agentic Proposal Sessions."""

from __future__ import annotations

from typing import Any, Mapping

from scion.proposal.agentic_grounding import (
    _context_requires_solver_design_grounding,
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
    if not available_feedback:
        return None
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
    return None


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
) -> bool:
    if not _context_requires_solver_design_grounding(context):
        return False
    if next_tool_name != "context.read_algorithm_file":
        return False
    return (
        _successful_planner_algorithm_file_read_count(observations)
        >= _SOLVER_DESIGN_PLANNER_ALGORITHM_FILE_READ_LIMIT
    )


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
            file_path = str(payload.get("file_path") or "").strip()
        file_paths.add(file_path or observation.observation_id)
    return len(file_paths)


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
