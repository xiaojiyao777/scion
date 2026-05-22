"""Telemetry summary helpers for formal protocol artifacts."""
from __future__ import annotations

from typing import Any, Dict, Iterable

from scion.core.models import ProtocolResult, StepRecord
from scion.core.telemetry_validation import (
    formal_telemetry_guard_failed,
    telemetry_decision_details,
    telemetry_failure_categories,
)


def _telemetry_failed_experiment_category_counts(
    protocol_results: Iterable[ProtocolResult | None],
) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for protocol_result in protocol_results:
        if not formal_telemetry_guard_failed(protocol_result):
            continue
        categories = telemetry_failure_categories(protocol_result) or ("unknown",)
        for category in categories:
            counts[category] = counts.get(category, 0) + 1
    return counts


def _telemetry_failed_experiment_details(
    steps: Iterable[StepRecord],
) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for step in steps:
        if not formal_telemetry_guard_failed(step.protocol_result):
            continue
        for detail in telemetry_decision_details(step.protocol_result):
            details.append(
                {
                    **detail,
                    "round": step.round_num,
                    "branch_id": step.branch_id,
                }
            )
    return details

