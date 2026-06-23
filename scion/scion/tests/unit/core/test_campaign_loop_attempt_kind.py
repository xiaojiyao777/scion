from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from scion.core.campaign_loop import CampaignLoop, _attempt_kind
from scion.core.step_result import StepResult


def _screening_result(
    *,
    branch_id: str = "b1",
    reason: str = "screening complete",
) -> StepResult:
    return StepResult(
        action="explore",
        branch_id=branch_id,
        reason=reason,
        counts_toward_max_rounds=True,
    )


def _run_campaign_loop_results(
    results: list[StepResult],
    *,
    max_rounds: int,
    proposal_attempt_limit: int | None = None,
) -> SimpleNamespace:
    calls = 0
    stopped_reasons: list[str | None] = []
    loop_statuses: list[dict[str, Any]] = []
    last_results: list[StepResult] = []

    def run_one_step() -> StepResult:
        nonlocal calls
        result = results[calls]
        calls += 1
        return result

    def write_status(**kwargs: Any) -> None:
        if "stopped_reason" in kwargs:
            stopped_reasons.append(kwargs.get("stopped_reason"))
        if "loop_status" in kwargs:
            loop_statuses.append(dict(kwargs["loop_status"]))
        if "last_result" in kwargs:
            last_results.append(kwargs["last_result"])

    loop_kwargs: dict[str, Any] = {
        "write_status": write_status,
        "drain_weight_opt_events": lambda: None,
        "should_stop": lambda: False,
        "get_last_stop_reason": lambda: None,
        "set_last_stop_reason": lambda reason: stopped_reasons.append(reason),
        "get_circuit_breaker": lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        "circuit_breaker_threshold": 3,
        "run_one_step": run_one_step,
        "run_stagnation_check": lambda: None,
        "check_soft_stagnation": lambda: None,
        "write_campaign_summary": lambda: None,
        "terminalize_active_branches": lambda reason: None,
        "get_final_wait_timeout": lambda: 0.0,
        "wait_weight_opt_all": lambda timeout: None,
    }
    if proposal_attempt_limit is not None:
        loop_kwargs["proposal_attempt_limit"] = proposal_attempt_limit

    loop = CampaignLoop(**loop_kwargs)
    loop.run(max_rounds=max_rounds)

    return SimpleNamespace(
        calls=calls,
        stopped_reasons=stopped_reasons,
        loop_statuses=loop_statuses,
        last_results=last_results,
    )


def test_attempt_kind_does_not_infer_control_kinds_from_reason_text() -> None:
    reasons = [
        "branch_lifecycle_policy_violation: new_mechanism_requires_clean_fork",
        "repair_first_policy_violation: telemetry repair required",
        "TELEMETRY_VALIDATION_REPAIRABLE: repair declared telemetry",
        "VALIDATION_TELEMETRY_REPAIRABLE: repair declared telemetry",
        "same_family retry should repair the contradicted premise",
        "semantic retry should choose a different target",
        "schema_quality_block: mechanism_changes_duplicate_id_conflict",
    ]

    for reason in reasons:
        result = StepResult(
            action="explore",
            branch_id="b1",
            reason=reason,
            counts_toward_max_rounds=False,
        )

        assert _attempt_kind(result) == "proposal_block"


def test_schema_quality_text_without_attempt_kind_stays_proposal_block() -> None:
    outcome = _run_campaign_loop_results(
        [
            StepResult(
                action="explore",
                branch_id="b1",
                reason=(
                    "schema_quality_block: "
                    "mechanism_changes_duplicate_id_conflict"
                ),
                counts_toward_max_rounds=False,
            ),
            _screening_result(reason="screening 1"),
        ],
        max_rounds=1,
        proposal_attempt_limit=2,
    )

    assert outcome.calls == 2
    assert "max_rounds_exhausted" in outcome.stopped_reasons
    final_status = outcome.loop_statuses[-1]
    assert final_status["proposal_attempts_consumed"] == 2
    assert final_status["proposal_quality_blocks_consumed"] == 1
    assert final_status["effective_rounds_completed"] == 1
    ledger = final_status["quality_block_ledger"]
    assert [entry["attempt_kind"] for entry in ledger] == ["proposal_block"]
    assert "schema_quality_block" in ledger[0]["source_result_reason"]


def test_branch_lifecycle_text_without_attempt_kind_is_proposal_block() -> None:
    outcome = _run_campaign_loop_results(
        [
            StepResult(
                action="explore",
                branch_id="b1",
                reason=(
                    "branch_lifecycle_policy_violation: "
                    "new_mechanism_requires_clean_fork"
                ),
                counts_toward_max_rounds=False,
            ),
            _screening_result(branch_id="b2", reason="screening 1"),
        ],
        max_rounds=1,
        proposal_attempt_limit=2,
    )

    assert outcome.calls == 2
    assert "max_rounds_exhausted" in outcome.stopped_reasons
    final_status = outcome.loop_statuses[-1]
    assert final_status["branch_lifecycle_policy_blocks"] == 0
    assert final_status["non_counted_lifecycle_steps"] == 0
    assert final_status["proposal_attempts_consumed"] == 2
    assert final_status["proposal_quality_blocks_consumed"] == 1
    ledger = final_status["quality_block_ledger"]
    assert [entry["attempt_kind"] for entry in ledger] == ["proposal_block"]
    assert "branch_lifecycle_policy_violation" in ledger[0]["source_result_reason"]


def test_explicit_attempt_kind_still_controls_live_accounting() -> None:
    outcome = _run_campaign_loop_results(
        [
            StepResult(
                action="explore",
                branch_id="b1",
                reason="schema_quality_block: duplicate id",
                counts_toward_max_rounds=False,
                attempt_kind="schema_quality_block",
            ),
            StepResult(
                action="explore",
                branch_id="b2",
                reason="branch_lifecycle_policy_violation: clean fork",
                counts_toward_max_rounds=False,
                attempt_kind="branch_lifecycle_policy",
            ),
            _screening_result(branch_id="b3", reason="screening 1"),
        ],
        max_rounds=1,
        proposal_attempt_limit=2,
    )

    final_status = outcome.loop_statuses[-1]
    assert final_status["branch_lifecycle_policy_blocks"] == 1
    assert final_status["proposal_quality_blocks_consumed"] == 1
    assert final_status["quality_block_ledger"][0]["attempt_kind"] == (
        "schema_quality_block"
    )
