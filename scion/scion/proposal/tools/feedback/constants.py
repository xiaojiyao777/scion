"""Constants for bounded feedback proposal-tool payloads."""

from __future__ import annotations




_COMPACT_FEEDBACK_PAYLOAD_CHARS = 24000
_COMPACT_FEEDBACK_TEXT_CHARS = 8000
_COMPACT_FEEDBACK_STRING_CHARS = 1200
_COMPACT_FEEDBACK_LIST_ITEMS = 8
_COMPACT_FEEDBACK_MAP_ITEMS = 32
_RUNTIME_ATTRIBUTION_SUFFIXES = (
    "_initial_distance",
    "_returned_distance",
    "_objective_delta",
    "_active",
    "_loaded",
    "_errors",
    "_attempts",
    "_accepted",
    "_skip_reasons",
    "_best_delta",
    "_improvement_counts",
    "_accepted_delta_sum",
    "_accepted_best_delta",
    "_accepted_positive_counts",
    "_recovery_delta_sum",
    "_recovery_best_delta",
    "_recovery_counts",
    "_phase_delta_sum",
    "_phase_best_delta",
    "_phase_improvement_counts",
    "_runtime_ms",
    "_objective_trace",
    "_delta_by_phase",
    "_stop_reason",
    "_coverage_status",
    "_quality_guard_applied",
    "_param_clamps",
)
_RUNTIME_ATTRIBUTION_PRIORITY_SUFFIXES = (
    "_objective_trace",
    "_objective_delta",
    "_delta_by_phase",
    "_phase_delta_sum",
    "_initial_distance",
    "_returned_distance",
    "_phase_best_delta",
    "_phase_improvement_counts",
    "_recovery_delta_sum",
    "_recovery_best_delta",
    "_recovery_counts",
    "_accepted_delta_sum",
    "_accepted_best_delta",
    "_accepted_positive_counts",
    "_accepted",
    "_attempts",
    "_skip_reasons",
    "_best_delta",
    "_improvement_counts",
    "_coverage_status",
    "_stop_reason",
    "_errors",
    "_active",
    "_loaded",
)

__all__ = [
    "_COMPACT_FEEDBACK_PAYLOAD_CHARS",
    "_COMPACT_FEEDBACK_TEXT_CHARS",
    "_COMPACT_FEEDBACK_STRING_CHARS",
    "_COMPACT_FEEDBACK_LIST_ITEMS",
    "_COMPACT_FEEDBACK_MAP_ITEMS",
    "_RUNTIME_ATTRIBUTION_SUFFIXES",
    "_RUNTIME_ATTRIBUTION_PRIORITY_SUFFIXES",
]
