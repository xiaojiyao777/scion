from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from scion.core.campaign_loop import (
    CampaignLoop,
    _fresh_runtime_replay_drain_status,
    _proposal_attempt_limit,
)
from scion.core.models import Decision
from scion.core.step_result import StepResult


def _protocol_stage_result(
    *,
    action: str,
    branch_id: str,
    reason: str,
    stage: str,
    **kwargs: Any,
) -> StepResult:
    return StepResult(
        action=action,
        branch_id=branch_id,
        reason=reason,
        protocol_stage=stage,
        formal_protocol_evaluated=True,
        screened_experiment_effective=stage == "screening",
        **kwargs,
    )


def _screening_result(
    *,
    action: str = "explore",
    branch_id: str = "b1",
    reason: str = "screening complete",
    **kwargs: Any,
) -> StepResult:
    return _protocol_stage_result(
        action=action,
        branch_id=branch_id,
        reason=reason,
        stage="screening",
        **kwargs,
    )


def test_campaign_loop_default_proposal_attempt_limit_includes_repair_headroom() -> None:
    statuses: list[dict[str, Any]] = []

    loop = CampaignLoop(
        write_status=lambda **kwargs: statuses.append(kwargs),
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: None,
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=lambda: _screening_result(),
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
    )

    loop.run(max_rounds=4)

    first_loop_status = next(
        item["loop_status"] for item in statuses if "loop_status" in item
    )
    assert first_loop_status["proposal_attempt_limit"] == 12
    assert first_loop_status["requested_rounds"] == 4


def test_proposal_attempt_limit_prefers_explicit_config_over_default() -> None:
    assert _proposal_attempt_limit(8, configured=9) == 9


def test_campaign_loop_does_not_count_retry_attempt_against_max_rounds() -> None:
    results = [
        StepResult(
            action="explore",
            branch_id="b1",
            reason="retry code generation failed",
            counts_toward_max_rounds=False,
        ),
        StepResult(action="explore", branch_id="b1", reason="new round failed"),
    ]
    calls = 0
    stopped_reasons: list[str | None] = []

    def run_one_step() -> StepResult:
        nonlocal calls
        result = results[calls]
        calls += 1
        return result

    loop = CampaignLoop(
        write_status=lambda **kwargs: stopped_reasons.append(
            kwargs.get("stopped_reason")
        )
        if "stopped_reason" in kwargs
        else None,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_attempt_limit=2,
    )

    loop.run(max_rounds=1)

    assert calls == 2
    assert "max_rounds_exhausted" in stopped_reasons


def test_campaign_loop_does_not_count_active_slot_skip_against_max_rounds() -> None:
    results = [
        StepResult(
            action="skip",
            reason="max_active_branches reached",
            counts_toward_max_rounds=False,
            attempt_kind="scheduler_active_slot_blocked",
            scheduler_slot="capacity_blocked",
            scheduler_reason="active_branch_limit_reached",
        ),
        _screening_result(),
    ]
    calls = 0
    statuses: list[dict[str, Any]] = []
    stopped_reasons: list[str | None] = []

    def run_one_step() -> StepResult:
        nonlocal calls
        result = results[calls]
        calls += 1
        return result

    loop = CampaignLoop(
        write_status=lambda **kwargs: statuses.append(kwargs),
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_attempt_limit=2,
    )

    loop.run(max_rounds=1)

    final_status = statuses[-1]["loop_status"]
    assert calls == 2
    assert stopped_reasons == ["max_rounds_exhausted"]
    assert final_status["effective_rounds_completed"] == 1
    assert final_status["formal_screened_candidates"] == 1
    assert final_status["protocol_evaluated_candidates"] == 1
    assert final_status["active_slot_blocked_attempts"] == 1
    assert final_status["scheduler_active_slot_blocked_attempts"] == 1


def test_campaign_loop_drains_fresh_runtime_replay_after_max_rounds() -> None:
    main_calls = 0
    drain_calls = 0
    statuses: list[dict[str, Any]] = []
    stopped_reasons: list[str | None] = []
    last_results: list[StepResult] = []

    def run_one_step() -> StepResult:
        nonlocal main_calls
        main_calls += 1
        return _screening_result()

    def drain_step() -> StepResult:
        nonlocal drain_calls
        drain_calls += 1
        if drain_calls == 1:
            return StepResult(
                action="replay",
                branch_id="b1",
                reason="fresh runtime replay complete",
                counts_toward_max_rounds=False,
                attempt_kind="fresh_runtime_replay",
                scheduler_audit_metadata={
                    "scheduler_action": "replay_existing",
                    "fresh_runtime_replay": {
                        "schema_version": "fresh_runtime_replay.v1",
                        "closure_status": "fresh_evidence_recorded",
                        "counts_toward_max_rounds": False,
                        "decision_features_excluded": True,
                    },
                },
            )
        return StepResult(
            action="skip",
            reason="no pending replay",
            counts_toward_max_rounds=False,
            attempt_kind="other",
        )

    def write_status(**kwargs: Any) -> None:
        if "stopped_reason" in kwargs:
            stopped_reasons.append(kwargs.get("stopped_reason"))
        if "last_result" in kwargs:
            last_results.append(kwargs["last_result"])
        if "loop_status" in kwargs:
            statuses.append(dict(kwargs["loop_status"]))

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_fresh_runtime_replay_drain_step=drain_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_attempt_limit=1,
        fresh_runtime_replay_drain_limit=2,
    )

    loop.run(max_rounds=1)

    final_status = statuses[-1]
    assert main_calls == 1
    assert drain_calls == 2
    assert last_results[-1].attempt_kind == "fresh_runtime_replay"
    assert "max_rounds_exhausted" in stopped_reasons
    assert final_status["effective_rounds_completed"] == 1
    assert final_status["formal_screened_candidates"] == 1
    assert final_status["proposal_attempts_consumed"] == 1
    assert final_status["fresh_runtime_replay_drain_executed"] == 1
    assert final_status["fresh_runtime_replay_drain_skipped"] == 1
    assert final_status["fresh_runtime_replay_drain_status"] == "selected_succeeded"
    assert final_status["fresh_runtime_replay_drain"]["status"] == (
        "selected_succeeded"
    )
    assert final_status["fresh_runtime_replay_drain"][
        "accepted_replay_last_result"
    ]["accepted_for_drain"] is True
    assert final_status["fresh_runtime_replay_drain"][
        "final_attempt_last_result"
    ]["attempt_kind"] == "other"
    assert (
        final_status["fresh_runtime_replay_drain"]["last_result"][
            "accepted_for_drain"
        ]
        is False
    )


def test_campaign_loop_does_not_drain_arbitrary_non_counted_result_after_max_rounds() -> None:
    main_calls = 0
    drain_calls = 0
    statuses: list[dict[str, Any]] = []
    stopped_reasons: list[str | None] = []
    last_results: list[StepResult] = []

    def run_one_step() -> StepResult:
        nonlocal main_calls
        main_calls += 1
        return _screening_result()

    def drain_step() -> StepResult:
        nonlocal drain_calls
        drain_calls += 1
        return StepResult(
            action="explore",
            branch_id="b1",
            reason="ordinary proposal block",
            counts_toward_max_rounds=False,
            attempt_kind="proposal_block",
        )

    def write_status(**kwargs: Any) -> None:
        if "stopped_reason" in kwargs:
            stopped_reasons.append(kwargs.get("stopped_reason"))
        if "last_result" in kwargs:
            last_results.append(kwargs["last_result"])
        if "loop_status" in kwargs:
            statuses.append(dict(kwargs["loop_status"]))

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_fresh_runtime_replay_drain_step=drain_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_attempt_limit=1,
    )

    loop.run(max_rounds=1)

    final_status = statuses[-1]
    assert main_calls == 1
    assert drain_calls == 1
    assert [result.reason for result in last_results] == ["screening complete"]
    assert "max_rounds_exhausted" in stopped_reasons
    assert final_status["effective_rounds_completed"] == 1
    assert final_status["formal_screened_candidates"] == 1
    assert final_status["proposal_attempts_consumed"] == 1
    assert final_status["fresh_runtime_replay_drain_executed"] == 0
    assert final_status["fresh_runtime_replay_drain_skipped"] == 1
    assert final_status["fresh_runtime_replay_drain"]["last_result"][
        "attempt_kind"
    ] == "proposal_block"
    assert final_status["fresh_runtime_replay_drain_status"] == (
        "not_selected_no_pending"
    )


def test_campaign_loop_drains_final_round_queued_validation_without_new_proposal_round() -> None:
    main_calls = 0
    drain_calls = 0
    statuses: list[dict[str, Any]] = []
    stopped_reasons: list[str | None] = []
    last_results: list[StepResult] = []

    def run_one_step() -> StepResult:
        nonlocal main_calls
        main_calls += 1
        return _screening_result(
            branch_id="b1",
            reason="screening queued validation",
            decision=Decision.QUEUE_VALIDATE,
        )

    def stage_drain_step() -> StepResult:
        nonlocal drain_calls
        drain_calls += 1
        if drain_calls == 1:
            return _protocol_stage_result(
                action="validate",
                branch_id="b1",
                reason="validation drained",
                stage="validation",
                decision=Decision.QUEUE_FROZEN,
                counts_toward_max_rounds=False,
                attempt_kind="stage_transition_drain",
            )
        return StepResult(
            action="skip",
            branch_id="b1",
            reason="stage transition drain skipped: no pending validation",
            counts_toward_max_rounds=False,
            attempt_kind="stage_transition_drain",
        )

    def write_status(**kwargs: Any) -> None:
        if "stopped_reason" in kwargs:
            stopped_reasons.append(kwargs.get("stopped_reason"))
        if "last_result" in kwargs:
            last_results.append(kwargs["last_result"])
        if "loop_status" in kwargs:
            statuses.append(dict(kwargs["loop_status"]))

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stage_transition_drain_step=stage_drain_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_attempt_limit=1,
        stage_transition_drain_limit=2,
    )

    loop.run(max_rounds=1)

    final_status = statuses[-1]
    assert main_calls == 1
    assert drain_calls == 2
    assert last_results[-1].reason == "validation drained"
    assert "max_rounds_exhausted" in stopped_reasons
    assert final_status["effective_rounds_completed"] == 1
    assert final_status["proposal_attempts_consumed"] == 1
    assert final_status["formal_screened_candidates"] == 1
    assert final_status["protocol_stage_counts"] == {
        "screening": 1,
        "validation": 1,
        "frozen": 0,
    }
    assert final_status["stage_transition_drain_executed"] == 1
    assert final_status["stage_transition_drain_skipped"] == 1
    assert final_status["stage_transition_drain_status"] == "selected_executed"
    assert final_status["stage_transition_drain"]["counts_toward_max_rounds"] is False
    assert final_status["stage_transition_drain"]["generates_new_hypothesis"] is False


def test_campaign_loop_rejects_non_stage_transition_drain_result() -> None:
    main_calls = 0
    drain_calls = 0
    statuses: list[dict[str, Any]] = []

    def run_one_step() -> StepResult:
        nonlocal main_calls
        main_calls += 1
        return _screening_result()

    def stage_drain_step() -> StepResult:
        nonlocal drain_calls
        drain_calls += 1
        return StepResult(
            action="explore",
            branch_id="b1",
            reason="new proposal would be unsafe",
            counts_toward_max_rounds=False,
            attempt_kind="proposal_block",
        )

    def write_status(**kwargs: Any) -> None:
        if "loop_status" in kwargs:
            statuses.append(dict(kwargs["loop_status"]))

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: None,
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stage_transition_drain_step=stage_drain_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_attempt_limit=1,
    )

    loop.run(max_rounds=1)

    final_status = statuses[-1]
    assert main_calls == 1
    assert drain_calls == 1
    assert final_status["effective_rounds_completed"] == 1
    assert final_status["proposal_attempts_consumed"] == 1
    assert final_status["protocol_stage_counts"]["validation"] == 0
    assert final_status["stage_transition_drain_executed"] == 0
    assert final_status["stage_transition_drain_skipped"] == 1
    assert final_status["stage_transition_drain_status"] == "not_selected_no_pending"


def test_campaign_loop_preserves_blocked_replay_and_final_skip_in_drain_status() -> None:
    main_calls = 0
    drain_calls = 0
    statuses: list[dict[str, Any]] = []

    def run_one_step() -> StepResult:
        nonlocal main_calls
        main_calls += 1
        return _screening_result()

    def drain_step() -> StepResult:
        nonlocal drain_calls
        drain_calls += 1
        if drain_calls == 1:
            return StepResult(
                action="replay",
                branch_id="b1",
                reason="fresh runtime replay missing workspace,hypothesis",
                counts_toward_max_rounds=False,
                attempt_kind="fresh_runtime_replay",
                failure_stage="fresh_runtime_replay",
                failure_detail="fresh runtime replay missing workspace,hypothesis",
                scheduler_audit_metadata={
                    "scheduler_action": "replay_existing",
                    "fresh_runtime_replay": {
                        "schema_version": "fresh_runtime_replay.v1",
                        "closure_status": "blocked_missing_candidate_state",
                        "detail": "fresh runtime replay missing workspace,hypothesis",
                        "counts_toward_max_rounds": False,
                        "decision_features_excluded": True,
                    },
                },
            )
        return StepResult(
            action="skip",
            reason="no pending replay",
            counts_toward_max_rounds=False,
            attempt_kind="other",
        )

    loop = CampaignLoop(
        write_status=lambda **kwargs: statuses.append(dict(kwargs["loop_status"]))
        if "loop_status" in kwargs
        else None,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: None,
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_fresh_runtime_replay_drain_step=drain_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_attempt_limit=1,
        fresh_runtime_replay_drain_limit=2,
    )

    loop.run(max_rounds=1)

    final_status = statuses[-1]
    drain = final_status["fresh_runtime_replay_drain"]
    accepted = drain["accepted_replay_last_result"]
    final_attempt = drain["final_attempt_last_result"]
    assert main_calls == 1
    assert drain_calls == 2
    assert final_status["fresh_runtime_replay_drain_status"] == "selected_blocked"
    assert drain["status"] == "selected_blocked"
    assert drain["attempts"] == 2
    assert drain["executed"] == 1
    assert drain["skipped"] == 1
    assert drain["blocked_count"] == 1
    assert drain["unresolved_closures"][0]["closure_status"] == (
        "blocked_missing_candidate_state"
    )
    assert accepted["accepted_for_drain"] is True
    assert accepted["fresh_runtime_replay"]["closure_status"] == (
        "blocked_missing_candidate_state"
    )
    assert final_attempt["accepted_for_drain"] is False
    assert final_attempt["attempt_kind"] == "other"
    assert drain["last_result"] == final_attempt


def test_fresh_runtime_replay_drain_status_distinguishes_failed_from_blocked() -> None:
    assert (
        _fresh_runtime_replay_drain_status(
            attempts=1,
            executed=1,
            skipped=0,
            stopped_reason="",
            accepted_replay_last_result={
                "attempt_kind": "fresh_runtime_replay",
                "failure_stage": "fresh_runtime_replay",
                "failure_detail": "runtime error",
                "fresh_runtime_replay": {"closure_status": "failed"},
            },
            final_attempt_last_result={},
            blocked_count=0,
        )
        == "selected_failed"
    )


def test_campaign_loop_reports_fresh_pressure_without_schedulable_replay_candidate() -> None:
    main_calls = 0
    drain_calls = 0
    statuses: list[dict[str, Any]] = []

    def run_one_step() -> StepResult:
        nonlocal main_calls
        main_calls += 1
        return _screening_result()

    def drain_step() -> StepResult:
        nonlocal drain_calls
        drain_calls += 1
        return StepResult(
            action="skip",
            branch_id="b1",
            reason=(
                "fresh runtime replay drain skipped: scheduler did not select "
                "replay_existing"
            ),
            counts_toward_max_rounds=False,
            attempt_kind="other",
            scheduler_audit_metadata={
                "scheduler_action": "create_new",
                "fresh_runtime_replay": {
                    "schema_version": "fresh_runtime_replay.v1",
                    "closure_status": "pressure_no_schedulable_replay_candidate",
                    "detail": (
                        "fresh champion runtime pressure exists but no "
                        "structured replay candidate is scheduler-eligible"
                    ),
                    "fresh_runtime_pressure_candidates": [
                        {
                            "branch_id": "b1",
                            "runtime_evidence_status": "fresh_champion_required",
                            "fresh_runtime_required": True,
                            "fresh_runtime_pending": False,
                            "runtime_evidence_pressure_count": 2,
                        }
                    ],
                    "counts_toward_max_rounds": False,
                    "decision_features_excluded": True,
                },
            },
        )

    loop = CampaignLoop(
        write_status=lambda **kwargs: statuses.append(dict(kwargs["loop_status"]))
        if "loop_status" in kwargs
        else None,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: None,
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_fresh_runtime_replay_drain_step=drain_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_attempt_limit=1,
        fresh_runtime_replay_drain_limit=2,
    )

    loop.run(max_rounds=1)

    final_status = statuses[-1]
    drain = final_status["fresh_runtime_replay_drain"]

    assert main_calls == 1
    assert drain_calls == 1
    assert final_status["fresh_runtime_replay_drain_status"] == (
        "pressure_no_schedulable_replay_candidate"
    )
    assert drain["status"] == "pressure_no_schedulable_replay_candidate"
    assert drain["executed"] == 0
    assert drain["skipped"] == 1
    assert drain["stopped_reason"] == "pressure_no_schedulable_replay_candidate"
    assert drain["blocked_count"] == 1
    assert drain["unresolved_closures"][0]["closure_status"] == (
        "pressure_no_schedulable_replay_candidate"
    )
    assert drain["final_attempt_last_result"]["fresh_runtime_replay"][
        "fresh_runtime_pressure_candidates"
    ][0]["branch_id"] == "b1"


def test_campaign_loop_caps_fresh_runtime_replay_drain_after_max_rounds() -> None:
    main_calls = 0
    drain_calls = 0
    statuses: list[dict[str, Any]] = []
    stopped_reasons: list[str | None] = []

    def run_one_step() -> StepResult:
        nonlocal main_calls
        main_calls += 1
        return _screening_result()

    def drain_step() -> StepResult:
        nonlocal drain_calls
        drain_calls += 1
        return StepResult(
            action="replay",
            branch_id=f"b{drain_calls}",
            reason="fresh runtime replay still pending",
            counts_toward_max_rounds=False,
            attempt_kind="fresh_runtime_replay",
            scheduler_audit_metadata={"scheduler_action": "replay_existing"},
        )

    def write_status(**kwargs: Any) -> None:
        if "stopped_reason" in kwargs:
            stopped_reasons.append(kwargs.get("stopped_reason"))
        if "loop_status" in kwargs:
            statuses.append(dict(kwargs["loop_status"]))

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_fresh_runtime_replay_drain_step=drain_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_attempt_limit=1,
        fresh_runtime_replay_drain_limit=2,
    )

    loop.run(max_rounds=1)

    final_status = statuses[-1]
    assert main_calls == 1
    assert drain_calls == 2
    assert "max_rounds_exhausted" in stopped_reasons
    assert final_status["effective_rounds_completed"] == 1
    assert final_status["formal_screened_candidates"] == 1
    assert final_status["proposal_attempts_consumed"] == 1
    assert final_status["fresh_runtime_replay_drain_executed"] == 2
    assert final_status["fresh_runtime_replay_drain_stopped_reason"] == (
        "fresh_runtime_replay_drain_cap_exhausted"
    )
    assert final_status["fresh_runtime_replay_drain"]["last_result"][
        "cap_exhausted"
    ] is True


def test_campaign_loop_active_slot_skip_has_independent_stop_budget() -> None:
    calls = 0
    statuses: list[dict[str, Any]] = []
    stopped_reasons: list[str | None] = []

    def run_one_step() -> StepResult:
        nonlocal calls
        calls += 1
        return StepResult(
            action="skip",
            reason="max_active_branches reached",
            counts_toward_max_rounds=False,
            attempt_kind="scheduler_active_slot_blocked",
            scheduler_slot="capacity_blocked",
            scheduler_reason="active_branch_limit_reached",
        )

    loop = CampaignLoop(
        write_status=lambda **kwargs: statuses.append(kwargs),
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_attempt_limit=10,
    )

    loop.run(max_rounds=1)

    final_status = statuses[-1]["loop_status"]
    assert calls == 2
    assert stopped_reasons == ["scheduler_active_slot_blocked"]
    assert final_status["effective_rounds_completed"] == 0
    assert final_status["formal_screened_candidates"] == 0
    assert final_status["protocol_evaluated_candidates"] == 0
    assert final_status["active_slot_blocked_attempts"] == 2
    assert final_status["active_slot_blocked_attempt_limit"] == 2


def test_campaign_loop_does_not_count_proposal_only_blocks_against_max_rounds() -> None:
    results = [
        StepResult(
            action="explore",
            branch_id="b1",
            reason="agent_quality_blocked",
            counts_toward_max_rounds=False,
        ),
        StepResult(
            action="explore",
            branch_id="b1",
            reason="code generation failed",
            counts_toward_max_rounds=False,
        ),
        _screening_result(),
    ]
    calls = 0
    stopped_reasons: list[str | None] = []

    def run_one_step() -> StepResult:
        nonlocal calls
        result = results[calls]
        calls += 1
        return result

    loop = CampaignLoop(
        write_status=lambda **kwargs: stopped_reasons.append(
            kwargs.get("stopped_reason")
        )
        if "stopped_reason" in kwargs
        else None,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_attempt_limit=3,
    )

    loop.run(max_rounds=1)

    assert calls == 3
    assert "max_rounds_exhausted" in stopped_reasons


def test_campaign_loop_stops_agent_quality_blocks_with_explicit_reason() -> None:
    results = [
        StepResult(
            action="explore",
            branch_id="b1",
            reason="agent_quality_blocked",
            counts_toward_max_rounds=False,
            attempt_kind="proposal_block",
        ),
        StepResult(
            action="explore",
            branch_id="b1",
            reason="agent_quality_blocked",
            counts_toward_max_rounds=False,
            attempt_kind="proposal_block",
        ),
        _screening_result(),
    ]
    calls = 0
    stopped_reasons: list[str | None] = []
    last_results: list[StepResult] = []
    loop_statuses: list[dict[str, Any]] = []

    def run_one_step() -> StepResult:
        nonlocal calls
        result = results[calls]
        calls += 1
        return result

    def write_status(**kwargs: Any) -> None:
        if "stopped_reason" in kwargs:
            stopped_reasons.append(kwargs.get("stopped_reason"))
        if "last_result" in kwargs:
            last_results.append(kwargs["last_result"])
        if "loop_status" in kwargs:
            loop_statuses.append(dict(kwargs["loop_status"]))

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_quality_loop_limit=2,
    )

    loop.run(max_rounds=1)

    assert calls == 2
    assert last_results[-1].reason == "agent_quality_blocked"
    assert last_results[-1].stopped is True
    assert "proposal_quality_loop" in stopped_reasons
    ledger = loop_statuses[-1]["quality_block_ledger"]
    assert loop_statuses[-1]["quality_block_ledger_count"] == 2
    assert ledger[0]["sequence"] == 1
    assert ledger[0]["index"] == 0
    assert ledger[0]["branch_id"] == "b1"
    assert ledger[0]["attempt_kind"] == "proposal_block"
    assert ledger[0]["source_result_reason"] == "agent_quality_blocked"
    assert ledger[0]["counts_toward_max_rounds"] is False
    assert ledger[0]["pre_protocol"] is True
    assert ledger[0]["loop_step"] == 1


def test_campaign_loop_records_model_repair_failed_quality_block_ledger() -> None:
    results = [
        StepResult(
            action="explore",
            branch_id="b1",
            reason="model_repair_failed",
            counts_toward_max_rounds=False,
            attempt_kind="proposal_block",
            failure_stage="code_generation",
            failure_category="model_repair_failed",
            failure_detail="model_repair_failed: code repair exhausted",
        ),
        _screening_result(),
    ]
    calls = 0
    loop_statuses: list[dict[str, Any]] = []

    def run_one_step() -> StepResult:
        nonlocal calls
        result = results[calls]
        calls += 1
        return result

    loop = CampaignLoop(
        write_status=lambda **kwargs: loop_statuses.append(
            dict(kwargs["loop_status"])
        )
        if "loop_status" in kwargs
        else None,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: None,
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_attempt_limit=2,
    )

    loop.run(max_rounds=1)

    assert calls == 2
    ledger = loop_statuses[-1]["quality_block_ledger"]
    assert loop_statuses[-1]["quality_blocks"] == 1
    assert loop_statuses[-1]["quality_block_ledger_count"] == 1
    assert ledger[0]["failure_stage"] == "code_generation"
    assert ledger[0]["failure_category"] == "model_repair_failed"
    assert ledger[0]["failure_reason"] == (
        "model_repair_failed: code repair exhausted"
    )
    assert ledger[0]["source_result_reason"] == "model_repair_failed"


def test_campaign_loop_does_not_count_mechanism_novelty_diagnostics_as_quality_blocks() -> None:
    results = [
        StepResult(
            action="explore",
            branch_id="b1",
            reason="duplicate_mechanism",
            counts_toward_max_rounds=False,
            attempt_kind="proposal_block",
        ),
        StepResult(
            action="explore",
            branch_id="b1",
            reason="mechanism_novelty_rejected",
            counts_toward_max_rounds=False,
            attempt_kind="proposal_block",
        ),
        _screening_result(),
    ]
    calls = 0
    stopped_reasons: list[str | None] = []
    last_results: list[StepResult] = []
    loop_statuses: list[dict[str, Any]] = []

    def run_one_step() -> StepResult:
        nonlocal calls
        result = results[calls]
        calls += 1
        return result

    def write_status(**kwargs: Any) -> None:
        if "stopped_reason" in kwargs:
            stopped_reasons.append(kwargs.get("stopped_reason"))
        if "last_result" in kwargs:
            last_results.append(kwargs["last_result"])
        if "loop_status" in kwargs:
            loop_statuses.append(kwargs["loop_status"])

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_quality_loop_limit=2,
    )

    loop.run(max_rounds=1)

    assert calls == 3
    assert last_results[-1].reason == "screening complete"
    assert last_results[-1].stopped is False
    assert "proposal_quality_loop" not in stopped_reasons
    assert loop_statuses[-1]["proposal_quality_blocks_consumed"] == 0
    assert loop_statuses[-1]["quality_blocks"] == 0


def test_campaign_loop_does_not_count_continue_explore_without_failure_as_quality_block() -> None:
    results = [
        StepResult(
            action="explore",
            branch_id="b1",
            decision=Decision.CONTINUE_EXPLORE,
            reason="CONTINUE_EXPLORE: weak-positive same-branch follow-up",
            counts_toward_max_rounds=False,
            attempt_kind="proposal_block",
        ),
        _screening_result(),
    ]
    calls = 0
    loop_statuses: list[dict[str, Any]] = []

    def run_one_step() -> StepResult:
        nonlocal calls
        result = results[calls]
        calls += 1
        return result

    loop = CampaignLoop(
        write_status=lambda **kwargs: loop_statuses.append(
            dict(kwargs["loop_status"])
        )
        if "loop_status" in kwargs
        else None,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: None,
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_quality_loop_limit=1,
    )

    loop.run(max_rounds=1)

    assert calls == 2
    assert loop_statuses[-1]["proposal_quality_blocks_consumed"] == 0
    assert loop_statuses[-1]["quality_blocks"] == 0
    assert loop_statuses[-1]["quality_block_ledger"] == []


def test_campaign_loop_classifies_stale_source_as_code_generation_not_quality_block() -> (
    None
):
    results = [
        StepResult(
            action="explore",
            branch_id="b1",
            reason="code generation failed: stale_source",
            counts_toward_max_rounds=False,
            attempt_kind="proposal_block",
            failure_stage="code_generation",
            failure_category="code_generation",
            failure_detail=(
                "patch.changes.0: stale_source for components/common.py: "
                "expected old digest"
            ),
        ),
        _screening_result(),
    ]
    calls = 0
    loop_statuses: list[dict[str, Any]] = []

    def run_one_step() -> StepResult:
        nonlocal calls
        result = results[calls]
        calls += 1
        return result

    loop = CampaignLoop(
        write_status=lambda **kwargs: loop_statuses.append(
            dict(kwargs["loop_status"])
        )
        if "loop_status" in kwargs
        else None,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: None,
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_quality_loop_limit=1,
    )

    loop.run(max_rounds=1)

    assert calls == 2
    assert loop_statuses[-1]["failure_categories"]["code_generation"] == 1
    assert loop_statuses[-1]["proposal_quality_blocks_consumed"] == 0
    assert loop_statuses[-1]["quality_blocks"] == 0
    assert loop_statuses[-1]["quality_block_ledger"] == []


def test_campaign_loop_counts_generic_proposal_blocks_in_quality_ceiling() -> None:
    results = [
        StepResult(
            action="explore",
            branch_id="b1",
            reason="hypothesis generation failed",
            counts_toward_max_rounds=False,
            attempt_kind="proposal_block",
        ),
        StepResult(
            action="explore",
            branch_id="b1",
            reason="code generation failed",
            counts_toward_max_rounds=False,
            attempt_kind="proposal_block",
        ),
        _screening_result(),
    ]
    calls = 0
    stopped_reasons: list[str | None] = []
    last_results: list[StepResult] = []

    def run_one_step() -> StepResult:
        nonlocal calls
        result = results[calls]
        calls += 1
        return result

    def write_status(**kwargs: Any) -> None:
        if "stopped_reason" in kwargs:
            stopped_reasons.append(kwargs.get("stopped_reason"))
        if "last_result" in kwargs:
            last_results.append(kwargs["last_result"])

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_quality_loop_limit=2,
    )

    loop.run(max_rounds=3)

    assert calls == 2
    assert last_results[-1].reason == "code generation failed"
    assert last_results[-1].stopped is True
    assert "proposal_quality_loop" in stopped_reasons


def test_campaign_loop_explicit_attempt_limit_allows_bounded_quality_overflow() -> None:
    results = [
        *[
            StepResult(
                action="explore",
                branch_id="b1",
                reason="agent_quality_blocked",
                counts_toward_max_rounds=False,
                attempt_kind="proposal_block",
            )
            for _ in range(5)
        ],
        _screening_result(reason="screening 1"),
        StepResult(action="explore", branch_id="b1", reason="screening 2"),
        StepResult(action="explore", branch_id="b1", reason="screening 3"),
    ]
    calls = 0
    stopped_reasons: list[str | None] = []
    loop_statuses: list[dict[str, Any]] = []

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

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_attempt_limit=8,
    )

    loop.run(max_rounds=3)

    assert calls == 8
    assert "proposal_quality_loop" not in stopped_reasons
    assert "max_rounds_exhausted" in stopped_reasons
    assert loop_statuses[-1]["attempt_limit"] == 8
    assert loop_statuses[-1]["proposal_quality_limit"] == 9
    assert loop_statuses[-1]["proposal_quality_blocks_consumed"] == 5


def test_campaign_loop_default_attempt_limit_allows_quality_block_headroom() -> None:
    results = [
        StepResult(
            action="explore",
            branch_id="b1",
            reason="agent_quality_blocked",
            counts_toward_max_rounds=False,
            attempt_kind="proposal_block",
        )
        for _ in range(11)
    ]
    calls = 0
    stopped_reasons: list[str | None] = []
    last_results: list[StepResult] = []
    loop_statuses: list[dict[str, Any]] = []

    def run_one_step() -> StepResult:
        nonlocal calls
        result = results[calls]
        calls += 1
        return result

    def write_status(**kwargs: Any) -> None:
        if "stopped_reason" in kwargs:
            stopped_reasons.append(kwargs.get("stopped_reason"))
        if "last_result" in kwargs:
            last_results.append(kwargs["last_result"])
        if "loop_status" in kwargs:
            loop_statuses.append(dict(kwargs["loop_status"]))

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
    )

    loop.run(max_rounds=3)

    assert calls == 9
    assert last_results[-1].stopped is True
    assert "proposal_quality_loop" in stopped_reasons
    assert "proposal_attempt_limit_exhausted" not in stopped_reasons
    assert loop_statuses[-1]["attempt_limit"] == 9
    assert loop_statuses[-1]["proposal_quality_limit"] == 9
    assert loop_statuses[-1]["proposal_quality_blocks_consumed"] == 9
    assert loop_statuses[-1]["quality_blocks"] == 9


def test_campaign_loop_schema_quality_block_does_not_consume_proposal_attempt() -> None:
    results = [
        StepResult(
            action="explore",
            branch_id="b1",
            reason=(
                "schema_quality_block: "
                "mechanism_changes_duplicate_id_conflict"
            ),
            counts_toward_max_rounds=False,
            attempt_kind="schema_quality_block",
        ),
        _screening_result(reason="screening 1"),
        StepResult(action="explore", branch_id="b1", reason="screening 2"),
    ]
    calls = 0
    stopped_reasons: list[str | None] = []
    loop_statuses: list[dict[str, Any]] = []

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

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_attempt_limit=2,
    )

    loop.run(max_rounds=2)

    assert calls == 3
    assert "max_rounds_exhausted" in stopped_reasons
    assert loop_statuses[-1]["proposal_attempts_consumed"] == 2
    assert loop_statuses[-1]["proposal_quality_blocks_consumed"] == 1
    assert loop_statuses[-1]["effective_rounds_completed"] == 2


def test_campaign_loop_does_not_start_step_when_proposal_attempts_are_exhausted() -> None:
    stopped_reasons: list[str | None] = []
    loop_statuses: list[dict[str, Any]] = []

    def write_status(**kwargs: Any) -> None:
        if "stopped_reason" in kwargs:
            stopped_reasons.append(kwargs.get("stopped_reason"))
        if "loop_status" in kwargs:
            loop_statuses.append(dict(kwargs["loop_status"]))

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=lambda: (_ for _ in ()).throw(
            AssertionError("proposal cap should stop before launching a new step")
        ),
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        get_proposal_attempts=lambda: 3,
        proposal_attempt_limit=3,
    )

    loop.run(max_rounds=3)

    assert "proposal_attempt_limit_exhausted" in stopped_reasons
    assert loop_statuses[-1]["requested_rounds"] == 3
    assert loop_statuses[-1]["attempt_limit"] == 3
    assert loop_statuses[-1]["proposal_attempts_consumed"] == 3
    assert loop_statuses[-1]["effective_rounds_completed"] == 0


def test_campaign_loop_continues_after_non_counting_and_telemetry_repairable_attempts() -> None:
    results = [
        StepResult(
            action="explore",
            branch_id="b1",
            reason="agent_quality_blocked",
            counts_toward_max_rounds=False,
            attempt_kind="proposal_block",
        ),
        StepResult(
            action="explore",
            branch_id="b1",
            decision=Decision.CONTINUE_EXPLORE,
            reason="TELEMETRY_VALIDATION_REPAIRABLE: repair declared telemetry",
            counts_toward_max_rounds=False,
            attempt_kind="telemetry_repairable",
            repair_mechanism_ids=("screening_probe",),
        ),
        StepResult(
            action="validate",
            branch_id="b1",
            decision=Decision.VALIDATION_REPAIR_REQUIRED,
            reason="VALIDATION_TELEMETRY_REPAIRABLE: repair declared telemetry",
            counts_toward_max_rounds=False,
            attempt_kind="validation_repair_required",
            repair_mechanism_ids=("validation_probe",),
        ),
        _screening_result(reason="screening 1"),
        StepResult(action="explore", branch_id="b1", reason="screening 2"),
    ]
    calls = 0
    stopped_reasons: list[str | None] = []
    last_results: list[StepResult] = []

    def run_one_step() -> StepResult:
        nonlocal calls
        result = results[calls]
        calls += 1
        return result

    def write_status(**kwargs: Any) -> None:
        if "stopped_reason" in kwargs:
            stopped_reasons.append(kwargs.get("stopped_reason"))
        if "last_result" in kwargs:
            last_results.append(kwargs["last_result"])

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_attempt_limit=5,
    )

    loop.run(max_rounds=2)

    assert calls == 5
    assert [result.attempt_kind for result in last_results[:3]] == [
        "proposal_block",
        "telemetry_repairable",
        "validation_repair_required",
    ]
    assert "max_rounds_exhausted" in stopped_reasons


def test_campaign_loop_caps_repeated_telemetry_repair_by_branch_mechanism() -> None:
    results = [
        StepResult(
            action="explore",
            branch_id="b1",
            decision=Decision.CONTINUE_EXPLORE,
            reason="TELEMETRY_VALIDATION_REPAIRABLE: repair declared telemetry",
            counts_toward_max_rounds=False,
            attempt_kind="telemetry_repairable",
            repair_mechanism_ids=("probe",),
        )
        for _ in range(5)
    ]
    calls = 0
    stopped_reasons: list[str | None] = []
    loop_statuses: list[dict[str, Any]] = []

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

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
    )

    loop.run(max_rounds=4)

    assert calls == 2
    assert "telemetry_repair_attempt_budget_exhausted" in stopped_reasons
    assert loop_statuses[-1]["requested_rounds"] == 4
    assert loop_statuses[-1]["proposal_attempts_consumed"] == 0
    assert loop_statuses[-1]["effective_rounds_completed"] == 0
    assert loop_statuses[-1]["telemetry_diagnostic_attempts"] == 2
    assert loop_statuses[-1]["telemetry_repair_attempts"] == 2
    assert loop_statuses[-1]["telemetry_repair_attempts_by_branch_mechanism"] == {
        "b1:probe": 2
    }


def test_campaign_loop_telemetry_repairable_does_not_consume_proposal_attempts() -> None:
    results = [
        StepResult(
            action="explore",
            branch_id="b1",
            decision=Decision.CONTINUE_EXPLORE,
            reason="TELEMETRY_VALIDATION_REPAIRABLE: repair declared telemetry",
            counts_toward_max_rounds=False,
            attempt_kind="telemetry_repairable",
            repair_mechanism_ids=("probe",),
        ),
        StepResult(
            action="explore",
            branch_id="b1",
            decision=Decision.CONTINUE_EXPLORE,
            reason="TELEMETRY_VALIDATION_REPAIRABLE: repair declared telemetry",
            counts_toward_max_rounds=False,
            attempt_kind="telemetry_repairable",
            repair_mechanism_ids=("other_probe",),
        ),
        _screening_result(reason="screening 1"),
        StepResult(action="explore", branch_id="b1", reason="screening 2"),
    ]
    calls = 0
    stopped_reasons: list[str | None] = []
    loop_statuses: list[dict[str, Any]] = []

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

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_attempt_limit=2,
    )

    loop.run(max_rounds=2)

    assert calls == 4
    assert "max_rounds_exhausted" in stopped_reasons
    assert loop_statuses[-1]["proposal_attempts_consumed"] == 2
    assert loop_statuses[-1]["telemetry_repair_attempts"] == 2
    assert loop_statuses[-1]["effective_rounds_completed"] == 2


def test_campaign_loop_branch_lifecycle_policy_block_does_not_consume_proposal_attempt() -> None:
    results = [
        StepResult(
            action="explore",
            branch_id="b1",
            reason=(
                "branch_lifecycle_policy_violation: "
                "new_mechanism_requires_clean_fork"
            ),
            counts_toward_max_rounds=False,
            attempt_kind="branch_lifecycle_policy",
            repair_mechanism_ids=("bounded_probe",),
            failure_stage="proposal",
            failure_detail=(
                "branch_lifecycle_policy_violation: "
                "new_mechanism_requires_clean_fork"
            ),
            failure_category="contract_boundary_failure",
        ),
        _screening_result(branch_id="b2", reason="screening 1"),
    ]
    calls = 0
    stopped_reasons: list[str | None] = []
    loop_statuses: list[dict[str, Any]] = []

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

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_attempt_limit=1,
    )

    loop.run(max_rounds=1)

    assert calls == 2
    assert "max_rounds_exhausted" in stopped_reasons
    assert loop_statuses[-1]["proposal_attempts_consumed"] == 1
    assert loop_statuses[-1]["effective_rounds_completed"] == 1
    assert loop_statuses[-1]["branch_lifecycle_policy_blocks"] == 1
    assert loop_statuses[-1]["reconcile_lifecycle_steps"] == 0
    assert loop_statuses[-1]["non_counted_lifecycle_steps"] == 1
    assert loop_statuses[-1]["quality_blocks"] == 0
    assert loop_statuses[-1]["failure_categories"] == {}
    assert loop_statuses[-1]["noninfra_failure_attempts"] == 0


def test_campaign_loop_reconcile_lifecycle_step_does_not_count_effective_round() -> None:
    results = [
        StepResult(
            action="reconcile",
            branch_id="stale-1",
            reason="missing hypothesis metadata for reconcile",
            counts_toward_max_rounds=False,
            attempt_kind="reconcile_lifecycle",
        ),
        _screening_result(reason="screening 1"),
        StepResult(action="explore", branch_id="b2", reason="screening 2"),
    ]
    calls = 0
    stopped_reasons: list[str | None] = []
    loop_statuses: list[dict[str, Any]] = []

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

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_attempt_limit=2,
    )

    loop.run(max_rounds=2)

    assert calls == 3
    assert "max_rounds_exhausted" in stopped_reasons
    assert loop_statuses[-1]["effective_rounds_completed"] == 2
    assert loop_statuses[-1]["proposal_attempts_consumed"] == 2
    assert loop_statuses[-1]["reconcile_lifecycle_steps"] == 1
    assert loop_statuses[-1]["non_counted_lifecycle_steps"] == 1
    assert loop_statuses[-1]["branch_lifecycle_policy_blocks"] == 0


def test_campaign_loop_exposes_candidate_accounting_without_counting_holdouts_as_screening() -> None:
    results = [
        StepResult(
            action="explore",
            branch_id="b1",
            reason="agent_quality_blocked",
            counts_toward_max_rounds=False,
            attempt_kind="proposal_block",
        ),
        _screening_result(reason="screening 1"),
        StepResult(
            action="validate",
            branch_id="b1",
            reason="validation complete",
            protocol_stage="validation",
            formal_protocol_evaluated=True,
        ),
        StepResult(
            action="frozen",
            branch_id="b1",
            reason="frozen complete",
            protocol_stage="frozen",
            formal_protocol_evaluated=True,
        ),
    ]
    calls = 0
    stopped_reasons: list[str | None] = []
    loop_statuses: list[dict[str, Any]] = []

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

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
    )

    loop.run(max_rounds=3)

    assert calls == 4
    assert "max_rounds_exhausted" in stopped_reasons
    final_status = loop_statuses[-1]
    assert final_status["proposal_attempts_total"] == 4
    assert final_status["effective_rounds_completed"] == 3
    assert final_status["formal_screened_candidates"] == 1
    assert final_status["protocol_evaluated_candidates"] == 3
    assert final_status["protocol_stage_counts"] == {
        "screening": 1,
        "validation": 1,
        "frozen": 1,
    }
    assert final_status["quality_blocks"] == 1


def test_campaign_loop_counts_clean_fork_screening_as_formal_candidate() -> None:
    results = [
        _screening_result(
            action="create_branch",
            branch_id="clean-1",
            reason="clean fork screening complete",
            attempt_kind="screening",
            counts_toward_max_rounds=True,
        ),
    ]
    calls = 0
    stopped_reasons: list[str | None] = []
    loop_statuses: list[dict[str, Any]] = []

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

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
    )

    loop.run(max_rounds=1)

    assert calls == 1
    assert "max_rounds_exhausted" in stopped_reasons
    final_status = loop_statuses[-1]
    assert final_status["effective_rounds_completed"] == 1
    assert final_status["formal_screened_candidates"] == 1
    assert final_status["protocol_evaluated_candidates"] == 1
    assert final_status["protocol_stage_counts"] == {
        "screening": 1,
        "validation": 0,
        "frozen": 0,
    }


def test_campaign_loop_counts_completed_screening_hidden_by_lifecycle_result() -> None:
    results = [
        StepResult(
            action="soft_abandon",
            branch_id="branch-1",
            decision=Decision.ABANDON,
            reason="soft_abandon: screening abandon lifecycle policy",
            attempt_kind="branch_lifecycle_policy",
            protocol_stage="screening",
            formal_protocol_evaluated=True,
            screened_experiment_effective=True,
        ),
    ]
    calls = 0
    stopped_reasons: list[str | None] = []
    loop_statuses: list[dict[str, Any]] = []

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

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
    )

    loop.run(max_rounds=1)

    assert calls == 1
    assert "max_rounds_exhausted" in stopped_reasons
    final_status = loop_statuses[-1]
    assert final_status["effective_rounds_completed"] == 1
    assert final_status["formal_screened_candidates"] == 1
    assert final_status["protocol_evaluated_candidates"] == 1
    assert final_status["protocol_stage_counts"] == {
        "screening": 1,
        "validation": 0,
        "frozen": 0,
    }


def test_campaign_loop_clean_fork_screening_mixes_with_holdout_stages() -> None:
    results = [
        _screening_result(
            action="create_branch",
            branch_id="clean-1",
            reason="clean fork screening complete",
            attempt_kind="screening",
            counts_toward_max_rounds=True,
        ),
        StepResult(
            action="validate",
            branch_id="clean-1",
            reason="validation complete",
            protocol_stage="validation",
            formal_protocol_evaluated=True,
        ),
        StepResult(
            action="frozen",
            branch_id="clean-1",
            reason="frozen complete",
            protocol_stage="frozen",
            formal_protocol_evaluated=True,
        ),
    ]
    calls = 0
    stopped_reasons: list[str | None] = []
    loop_statuses: list[dict[str, Any]] = []

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

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
    )

    loop.run(max_rounds=3)

    assert calls == 3
    assert "max_rounds_exhausted" in stopped_reasons
    final_status = loop_statuses[-1]
    assert final_status["effective_rounds_completed"] == 3
    assert final_status["formal_screened_candidates"] == 1
    assert final_status["protocol_evaluated_candidates"] == 3
    assert final_status["protocol_stage_counts"] == {
        "screening": 1,
        "validation": 1,
        "frozen": 1,
    }


def test_campaign_loop_repeated_lifecycle_blocks_do_not_stop_before_effective_rounds() -> None:
    results = [
        StepResult(
            action="explore",
            branch_id="b1",
            reason=(
                "branch_lifecycle_policy_violation: "
                "new_mechanism_requires_clean_fork"
            ),
            counts_toward_max_rounds=False,
            attempt_kind="branch_lifecycle_policy",
            repair_mechanism_ids=("bounded_probe",),
        ),
        StepResult(
            action="explore",
            branch_id="b2",
            reason=(
                "branch_lifecycle_policy_violation: "
                "new_mechanism_requires_clean_fork"
            ),
            counts_toward_max_rounds=False,
            attempt_kind="branch_lifecycle_policy",
            repair_mechanism_ids=("other_probe",),
        ),
        _screening_result(branch_id="clean-1", reason="screening 1"),
        _screening_result(branch_id="clean-2", reason="screening 2"),
    ]
    calls = 0
    stopped_reasons: list[str | None] = []
    loop_statuses: list[dict[str, Any]] = []

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

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: stopped_reasons.append(reason),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
        proposal_attempt_limit=2,
    )

    loop.run(max_rounds=2)

    assert calls == 4
    assert "circuit_breaker" not in stopped_reasons
    assert "max_rounds_exhausted" in stopped_reasons
    assert loop_statuses[-1]["branch_lifecycle_policy_blocks"] == 2
    assert loop_statuses[-1]["reconcile_lifecycle_steps"] == 0
    assert loop_statuses[-1]["non_counted_lifecycle_steps"] == 2
    assert loop_statuses[-1]["proposal_attempts_consumed"] == 2
    assert loop_statuses[-1]["effective_rounds_completed"] == 2


def test_campaign_loop_writes_status_heartbeat_before_step_execution() -> None:
    status_calls: list[str] = []
    calls = 0

    def write_status(**kwargs: Any) -> None:
        status_calls.append("stopped" if "stopped_reason" in kwargs else "heartbeat")

    def run_one_step() -> StepResult:
        nonlocal calls
        calls += 1
        assert status_calls[:2] == ["heartbeat", "heartbeat"]
        return StepResult(action="explore", branch_id="b1", stopped=True, reason="done")

    loop = CampaignLoop(
        write_status=write_status,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        set_last_stop_reason=lambda reason: status_calls.append(f"final:{reason}"),
        get_circuit_breaker=lambda: SimpleNamespace(
            is_tripped=False,
            last_failure_detail=None,
        ),
        circuit_breaker_threshold=3,
        run_one_step=run_one_step,
        run_stagnation_check=lambda: None,
        check_soft_stagnation=lambda: None,
        write_campaign_summary=lambda: None,
        terminalize_active_branches=lambda reason: None,
        get_final_wait_timeout=lambda: 0.0,
        wait_weight_opt_all=lambda timeout: None,
    )

    loop.run(max_rounds=1)

    assert calls == 1
    assert status_calls[0:2] == ["heartbeat", "heartbeat"]
    assert "final:done" in status_calls
