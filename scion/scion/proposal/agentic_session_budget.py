"""Budget helpers for bounded Agentic Proposal Sessions."""

from __future__ import annotations

from scion.proposal.agentic_models import (
    AgenticProposalSessionState,
    AgenticToolLoopConfig,
)

_MIN_BUDGETED_OBSERVATION_CHARS = 512
_OPTIONAL_SURFACE_READ_BUDGET_FLOOR_CHARS = 3000
_APS_FEEDBACK_CALL_RESERVE_CHARS = 3000
_SELF_CHECK_TOOL_CALL_RESERVE = 4
_SELF_CHECK_OBSERVATION_RESERVE_CHARS = 16000
_IMPLEMENTATION_FINAL_PREVIEW_TOOL_RESERVE = 2
_IMPLEMENTATION_OBSERVATION_RESERVE_CHARS = 16000


def _remaining_observation_chars(
    config: AgenticToolLoopConfig,
    state: AgenticProposalSessionState,
) -> int:
    return max(
        0,
        int(config.max_observation_chars) - int(state.observation_chars_used),
    )


def _remaining_tool_calls(
    config: AgenticToolLoopConfig,
    state: AgenticProposalSessionState,
) -> int:
    return max(0, int(config.max_tool_calls) - int(state.tool_call_count))


def _remaining_tool_steps(
    config: AgenticToolLoopConfig,
    state: AgenticProposalSessionState,
) -> int:
    return max(0, int(config.max_steps) - int(state.tool_step_count))


def _self_check_tool_call_reserve(config: AgenticToolLoopConfig) -> int:
    max_calls = max(0, int(config.max_tool_calls))
    if max_calls < 8:
        return 0
    return min(_SELF_CHECK_TOOL_CALL_RESERVE, max_calls // 4)


def _self_check_step_reserve(config: AgenticToolLoopConfig) -> int:
    max_steps = max(0, int(config.max_steps))
    if max_steps < 8:
        return 0
    return min(_SELF_CHECK_TOOL_CALL_RESERVE, max_steps // 4)


def _self_check_observation_reserve_chars(config: AgenticToolLoopConfig) -> int:
    max_chars = max(0, int(config.max_observation_chars))
    if max_chars < _SELF_CHECK_OBSERVATION_RESERVE_CHARS * 2:
        return 0
    return min(_SELF_CHECK_OBSERVATION_RESERVE_CHARS, max_chars // 3)


def _diagnosis_budget_reserved(
    config: AgenticToolLoopConfig,
    state: AgenticProposalSessionState,
) -> bool:
    call_reserve = _self_check_tool_call_reserve(config)
    if call_reserve and _remaining_tool_calls(config, state) <= call_reserve:
        return True
    step_reserve = _self_check_step_reserve(config)
    if step_reserve and _remaining_tool_steps(config, state) <= step_reserve:
        return True
    observation_reserve = _self_check_observation_reserve_chars(config)
    if (
        observation_reserve
        and _remaining_observation_chars(config, state) <= observation_reserve
    ):
        return True
    return False


def _diagnosis_feedback_budget_reserved(
    config: AgenticToolLoopConfig,
    state: AgenticProposalSessionState,
) -> bool:
    observation_reserve = _self_check_observation_reserve_chars(config)
    if not observation_reserve:
        return False
    return _remaining_observation_chars(config, state) <= (
        observation_reserve + _APS_FEEDBACK_CALL_RESERVE_CHARS
    )


def _minimum_budgeted_observation_chars() -> int:
    return _MIN_BUDGETED_OBSERVATION_CHARS


def _observation_budget_exhausted(
    config: AgenticToolLoopConfig,
    state: AgenticProposalSessionState,
) -> bool:
    remaining = _remaining_observation_chars(config, state)
    if remaining <= 0:
        return True
    return remaining < _minimum_budgeted_observation_chars()


def _optional_surface_read_budget_floor(config: AgenticToolLoopConfig) -> int:
    self_check_reserve = _self_check_observation_reserve_chars(config)
    minimum = _minimum_budgeted_observation_chars()
    optional_floor = min(
        _OPTIONAL_SURFACE_READ_BUDGET_FLOOR_CHARS,
        max(0, int(config.max_observation_chars) // 8),
    )
    if self_check_reserve:
        return max(minimum, optional_floor, self_check_reserve + minimum)
    return max(minimum, optional_floor)


def _should_deny_optional_tool_for_budget(
    name: str,
    *,
    selection_source: str,
    config: AgenticToolLoopConfig,
    state: AgenticProposalSessionState,
) -> bool:
    if name != "context.read_surface":
        return False
    if selection_source == "selected_surface_required" or selection_source.startswith(
        "code_phase_required"
    ):
        return False
    return (
        _remaining_observation_chars(config, state)
        < _optional_surface_read_budget_floor(config)
    )


def _code_phase_budget_reserved(
    config: AgenticToolLoopConfig,
    state: AgenticProposalSessionState,
) -> bool:
    if (
        _remaining_tool_calls(config, state)
        <= _IMPLEMENTATION_FINAL_PREVIEW_TOOL_RESERVE
    ):
        return True
    if (
        _remaining_tool_steps(config, state)
        <= _IMPLEMENTATION_FINAL_PREVIEW_TOOL_RESERVE
    ):
        return True
    reserve = max(
        _minimum_budgeted_observation_chars(),
        min(
            _IMPLEMENTATION_OBSERVATION_RESERVE_CHARS,
            max(0, int(config.max_observation_chars) // 6),
        ),
        _self_check_observation_reserve_chars(config) // 2,
    )
    return _remaining_observation_chars(config, state) <= reserve
