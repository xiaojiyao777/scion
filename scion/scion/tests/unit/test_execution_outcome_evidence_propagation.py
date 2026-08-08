from __future__ import annotations

import pytest

from scion.core.execution_outcome import (
    ExecutionOutcome,
    execution_outcome_evidence,
)
from scion.core.run_validity import (
    RUN_VALIDITY_INVALID_INTERRUPTED_ONLY,
    RUN_VALIDITY_INVALID_RESOURCE_EXHAUSTED_ONLY,
    RUN_VALIDITY_UNKNOWN_HISTORICAL,
    build_run_validity,
)


def _all_outcome_counts(**overrides: int) -> dict[str, int]:
    counts = {outcome.value: 0 for outcome in ExecutionOutcome}
    counts.update(overrides)
    return counts


def test_six_state_projection_is_lossless_and_safe() -> None:
    rows = [
        {
            "outcome": outcome.value,
            "reason_code": f"REASON_{index}",
            "provenance": {
                "stage": "evaluation",
                "artifact_ref": f"artifact-{index}",
                "raw_prompt": "must-not-leak",
            },
        }
        for index, outcome in enumerate(ExecutionOutcome)
    ]

    evidence = execution_outcome_evidence(rows)

    assert evidence["execution_outcome_counts"] == _all_outcome_counts(
        evaluated=1,
        research_rejected=1,
        not_evaluated=1,
        blocked_infra=1,
        resource_exhausted=1,
        interrupted=1,
    )
    assert evidence["evaluated_count"] == 1
    assert evidence["non_evaluated_count"] == 5
    assert evidence["research_conclusion_eligibility"]["status"] == "partial_evaluated"
    assert evidence["last_execution_outcome"] == {
        "outcome": "interrupted",
        "reason_code": "REASON_5",
        "provenance_refs": {
            "stage": "evaluation",
            "artifact_ref": "artifact-5",
        },
    }


def test_partial_evaluated_plus_blocked_remains_eligible_with_exclusion() -> None:
    counts = _all_outcome_counts(evaluated=2, blocked_infra=1)
    validity = build_run_validity(
        requested_rounds=3,
        effective_rounds_completed=2,
        n_experiments=2,
        execution_outcome_counts=counts,
        stopped_reason="provider error text must not reclassify typed outcomes",
    )

    assert validity["valid"] is True
    assert validity["research_conclusion_eligibility"] == {
        "status": "partial_evaluated",
        "eligible": True,
        "algorithm_conclusions_allowed": True,
        "partial": True,
        "excluded_outcome_counts": {"blocked_infra": 1},
        "unknown_excluded_count": 0,
    }


@pytest.mark.parametrize(
    ("outcome", "expected_reason"),
    [
        ("resource_exhausted", RUN_VALIDITY_INVALID_RESOURCE_EXHAUSTED_ONLY),
        ("interrupted", RUN_VALIDITY_INVALID_INTERRUPTED_ONLY),
    ],
)
def test_zero_evaluated_preserves_non_evaluated_taxonomy(
    outcome: str,
    expected_reason: str,
) -> None:
    validity = build_run_validity(
        requested_rounds=1,
        effective_rounds_completed=0,
        n_experiments=0,
        proposal_attempts=1,
        failure_categories={"infra": 99},
        stopped_reason="HTTP 503 provider error",
        execution_outcome_counts=_all_outcome_counts(**{outcome: 1}),
    )

    assert validity["reason"] == expected_reason
    assert validity["research_conclusion_eligibility"][
        "algorithm_conclusions_allowed"
    ] is False


def test_historical_missing_outcome_stays_unknown_not_negative() -> None:
    evidence = execution_outcome_evidence([{"decision": "rollback"}])
    validity = build_run_validity(
        requested_rounds=1,
        effective_rounds_completed=0,
        n_experiments=0,
        execution_outcome_counts=evidence["execution_outcome_counts"],
        unknown_outcome_count=evidence["unknown_outcome_count"],
        stopped_reason="provider error",
    )

    assert evidence["research_conclusion_eligibility"]["eligible"] is None
    assert validity["reason"] == RUN_VALIDITY_UNKNOWN_HISTORICAL
    assert validity["valid"] is None
