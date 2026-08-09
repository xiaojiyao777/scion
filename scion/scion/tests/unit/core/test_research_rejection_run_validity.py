from __future__ import annotations

from scion.core.execution_outcome import ExecutionOutcome
from scion.core.run_validity import (
    RUN_VALIDITY_INVALID_RESEARCH_REJECTED_ONLY,
    RUN_VALIDITY_VALID,
    RUN_VALIDITY_VALID_BUT_INCOMPLETE,
    build_run_validity,
)


def _counts(*, evaluated: int, rejected: int) -> dict[str, int]:
    return {
        ExecutionOutcome.EVALUATED.value: evaluated,
        ExecutionOutcome.RESEARCH_REJECTED.value: rejected,
    }


def test_formal_target_with_prior_committed_rejection_is_valid_complete() -> None:
    validity = build_run_validity(
        requested_rounds=1,
        effective_rounds_completed=1,
        n_experiments=1,
        protocol_metric_results=1,
        proposal_attempts=2,
        execution_outcome_counts=_counts(evaluated=1, rejected=1),
        committed_research_rejections=1,
        stopped_reason="requested_rounds_completed",
    )

    assert validity["status"] == "valid"
    assert validity["reason"] == RUN_VALIDITY_VALID
    assert validity["complete"] is True
    assert validity["blocking_non_evaluated_count"] == 0


def test_formal_target_is_complete_despite_candidate_local_rejection() -> None:
    validity = build_run_validity(
        requested_rounds=12,
        effective_rounds_completed=12,
        n_experiments=12,
        protocol_metric_results=12,
        proposal_attempts=13,
        execution_outcome_counts=_counts(evaluated=12, rejected=1),
        stopped_reason="requested_rounds_completed",
    )

    assert validity["status"] == "valid"
    assert validity["reason"] == RUN_VALIDITY_VALID
    assert validity["complete"] is True
    assert validity["completeness_status"] == "complete"
    assert validity["blocking_non_evaluated_count"] == 1


def test_committed_rejection_without_evaluation_remains_invalid() -> None:
    validity = build_run_validity(
        requested_rounds=1,
        effective_rounds_completed=0,
        n_experiments=0,
        protocol_metric_results=0,
        proposal_attempts=1,
        execution_outcome_counts=_counts(evaluated=0, rejected=1),
        committed_research_rejections=1,
        stopped_reason="operator_requested",
    )

    assert validity["status"] == "invalid"
    assert validity["reason"] == RUN_VALIDITY_INVALID_RESEARCH_REJECTED_ONLY
    assert validity["complete"] is False


def test_operator_stop_after_evaluation_before_target_is_valid_incomplete() -> None:
    validity = build_run_validity(
        requested_rounds=2,
        effective_rounds_completed=1,
        n_experiments=1,
        protocol_metric_results=1,
        proposal_attempts=2,
        execution_outcome_counts=_counts(evaluated=1, rejected=1),
        committed_research_rejections=1,
        stopped_reason="operator_requested",
    )

    assert validity["status"] == "valid"
    assert validity["reason"] == RUN_VALIDITY_VALID_BUT_INCOMPLETE
    assert validity["complete"] is False
    assert validity["completeness_status"] == "incomplete"
