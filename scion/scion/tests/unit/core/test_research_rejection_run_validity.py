from scion.core.execution_outcome import ExecutionOutcome
from scion.core.run_validity import (
    RUN_VALIDITY_INVALID_NO_EVALUATED_OUTCOME,
    RUN_VALIDITY_PENDING,
    RUN_VALIDITY_VALID,
    RUN_VALIDITY_VALID_INCOMPLETE,
    classify_run_validity,
)


def _counts(**overrides: int) -> dict[str, int]:
    counts = {outcome.value: 0 for outcome in ExecutionOutcome}
    counts.update(overrides)
    return counts


def test_running_result_is_pending() -> None:
    assert classify_run_validity(
        terminal=False,
        completed=False,
        execution_outcome_counts=_counts(),
    ) == {"status": "pending", "reason": RUN_VALIDITY_PENDING, "valid": None}


def test_completed_evaluated_result_is_valid() -> None:
    assert classify_run_validity(
        terminal=True,
        completed=True,
        execution_outcome_counts=_counts(evaluated=2),
    ) == {"status": "valid", "reason": RUN_VALIDITY_VALID, "valid": True}


def test_partial_evaluated_result_is_valid_incomplete() -> None:
    assert classify_run_validity(
        terminal=True,
        completed=False,
        execution_outcome_counts=_counts(evaluated=1, interrupted=1),
    ) == {
        "status": "valid",
        "reason": RUN_VALIDITY_VALID_INCOMPLETE,
        "valid": True,
    }


def test_non_evaluated_outcomes_are_not_reclassified_from_reason_text() -> None:
    assert classify_run_validity(
        terminal=True,
        completed=False,
        execution_outcome_counts=_counts(research_rejected=3),
    ) == {
        "status": "invalid",
        "reason": RUN_VALIDITY_INVALID_NO_EVALUATED_OUTCOME,
        "valid": False,
    }
