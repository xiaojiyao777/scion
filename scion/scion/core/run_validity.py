"""Direct scientific-validity classification for one typed campaign result."""

from __future__ import annotations

from typing import Any, Mapping

from scion.core.execution_outcome import ExecutionOutcome

RUN_VALIDITY_VALID = "valid"
RUN_VALIDITY_VALID_INCOMPLETE = "valid_incomplete"
RUN_VALIDITY_INVALID_NO_EVALUATED_OUTCOME = "invalid_no_evaluated_outcome"
RUN_VALIDITY_PENDING = "running"


def classify_run_validity(
    *,
    terminal: bool,
    completed: bool,
    execution_outcome_counts: Mapping[str, Any],
) -> dict[str, Any]:
    """Classify only the typed outcomes owned by ``CampaignRunResult``.

    Fresh V3 runs do not reconstruct validity from step rows, registry state,
    failure prose, or historical aliases.  The loop's evaluated-outcome count
    and requested-round completion are the complete input to this projection.
    """

    evaluated = _count(execution_outcome_counts.get(ExecutionOutcome.EVALUATED.value))
    if not terminal:
        return {
            "status": "pending",
            "reason": RUN_VALIDITY_PENDING,
            "valid": None,
        }
    if evaluated > 0:
        return {
            "status": "valid",
            "reason": (
                RUN_VALIDITY_VALID if completed else RUN_VALIDITY_VALID_INCOMPLETE
            ),
            "valid": True,
        }
    return {
        "status": "invalid",
        "reason": RUN_VALIDITY_INVALID_NO_EVALUATED_OUTCOME,
        "valid": False,
    }


def _count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


__all__ = [
    "RUN_VALIDITY_INVALID_NO_EVALUATED_OUTCOME",
    "RUN_VALIDITY_PENDING",
    "RUN_VALIDITY_VALID",
    "RUN_VALIDITY_VALID_INCOMPLETE",
    "classify_run_validity",
]
