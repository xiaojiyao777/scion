"""Deterministic APS tool prefetch helpers."""
from __future__ import annotations

from typing import Any, Mapping

from scion.proposal.agentic_models import (
    AgenticProposalPhase,
    AgenticProposalSessionState,
)
from scion.proposal.agentic_planner_policy import _available_compact_feedback_tools
from scion.proposal.agentic_session_feedback import (
    _feedback_query_args,
    _has_equivalent_feedback_observation,
)
from scion.proposal.agentic_session_tools import _has_successful_reusable_observation
from scion.proposal.agentic_tool_selection_ledger import (
    record_tool_selection_ledger_entry,
    update_tool_selection_ledger_result,
)
from scion.proposal.prompt_manifest import stable_digest
from scion.proposal.tools import ProposalObservation, ProposalToolContext

_DEFAULT_COMPACT_PREFETCH_TOOLS = (
    "memory.query",
    "feedback.query_screening",
    "feedback.query_runtime",
)


def run_deterministic_compact_feedback_prefetch(
    runner: Any,
    context: ProposalToolContext,
    state: AgenticProposalSessionState,
    observations: list[ProposalObservation],
    *,
    phase: AgenticProposalPhase,
    source: str = "deterministic_prefetch",
    preserve_observation_chars: int = 0,
) -> list[ProposalObservation]:
    """Prefetch default compact feedback without asking the LLM planner."""

    if runner.tool_registry is None:
        return []
    available = set(_available_compact_feedback_tools(runner.tool_registry, context))
    calls = [
        (name, _deterministic_prefetch_args(name, context))
        for name in _DEFAULT_COMPACT_PREFETCH_TOOLS
        if name in available
    ]
    if not calls:
        return []

    plan_id = _ensure_deterministic_prefetch_plan_id(
        state,
        session_id=context.session_id,
        source=source,
    )
    prefetched: list[ProposalObservation] = []
    for name, args in calls:
        current = [*observations, *prefetched]
        if _has_equivalent_successful_prefetch_observation(
            current,
            name,
            args,
            context=context,
        ):
            continue
        if runner._tool_loop_limit_reached(state):
            runner._record_loop_stop(state, runner._current_loop_stop_reason(state))
            break
        ledger_index = record_tool_selection_ledger_entry(
            state,
            phase=phase.value,
            source=source,
            status="executed",
            tool_name=name,
            args=args,
        )
        observation = runner._call_tool(
            context,
            state,
            phase,
            name,
            args,
            selection_source=source,
            preserve_observation_chars=preserve_observation_chars,
        )
        update_tool_selection_ledger_result(
            state,
            ledger_index,
            observation,
            status="executed",
        )
        _attach_entry_prefetch_plan_id(state, ledger_index, plan_id)
        prefetched.append(observation)
        if state.loop_stop_reason in {"session_timeout", "repeated_tool_call"}:
            break
    if prefetched:
        state.note(
            phase,
            "Collected deterministic compact feedback prefetch observations.",
            metadata={
                "selection_source": source,
                "deterministic_prefetch_plan_id": plan_id,
                "tool_names": [observation.tool_name for observation in prefetched],
                "error_count": sum(
                    1 for observation in prefetched if observation.is_error
                ),
            },
        )
    return prefetched


def _deterministic_prefetch_args(
    tool_name: str,
    context: ProposalToolContext,
) -> Mapping[str, Any]:
    if tool_name == "memory.query":
        return {}
    if tool_name in {"feedback.query_screening", "feedback.query_runtime"}:
        return _feedback_query_args(context)
    return {}


def _has_equivalent_successful_prefetch_observation(
    observations: list[ProposalObservation],
    tool_name: str,
    args: Mapping[str, Any],
    *,
    context: ProposalToolContext,
) -> bool:
    if tool_name in {"feedback.query_screening", "feedback.query_runtime"}:
        return _has_equivalent_feedback_observation(
            observations,
            tool_name,
            args,
            default_surface=str(context.forced_surface or "").strip(),
        )
    return _has_successful_reusable_observation(
        observations,
        tool_name,
        args,
        forced_surface=context.forced_surface,
    )


def _ensure_deterministic_prefetch_plan_id(
    state: AgenticProposalSessionState,
    *,
    session_id: str,
    source: str,
) -> str:
    current = str(getattr(state, "deterministic_prefetch_plan_id", "") or "").strip()
    if current and current != "none":
        return current
    plan_id = stable_digest(
        {
            "session_id": session_id or state.session_id,
            "state_session_id": state.session_id,
            "source": source,
            "tools": _DEFAULT_COMPACT_PREFETCH_TOOLS,
        },
        length=16,
    )
    setattr(state, "deterministic_prefetch_plan_id", plan_id)
    return plan_id


def _attach_entry_prefetch_plan_id(
    state: AgenticProposalSessionState,
    entry_index: int | None,
    plan_id: str,
) -> None:
    if entry_index is None:
        return
    entries = getattr(state, "tool_selection_ledger", None)
    if not isinstance(entries, list):
        return
    for offset, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            continue
        if int(entry.get("index") or 0) != int(entry_index):
            continue
        updated = dict(entry)
        updated["deterministic_prefetch_plan_id"] = plan_id
        entries[offset] = updated
        return

