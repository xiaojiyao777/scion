from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from scion.core.campaign_loop import CampaignLoop
from scion.core.models import Decision
from scion.core.step_result import StepResult


def test_campaign_loop_default_proposal_attempt_limit_matches_requested_rounds() -> None:
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
        run_one_step=lambda: StepResult(
            action="explore",
            branch_id="b1",
            reason="screening complete",
        ),
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
    assert first_loop_status["proposal_attempt_limit"] == 4
    assert first_loop_status["requested_rounds"] == 4


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
        StepResult(action="explore", branch_id="b1", reason="screening complete"),
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
        StepResult(action="explore", branch_id="b1", reason="screening complete"),
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
    assert last_results[-1].reason == "agent_quality_blocked"
    assert last_results[-1].stopped is True
    assert "proposal_quality_loop" in stopped_reasons


def test_campaign_loop_stops_broader_pre_screen_quality_blocks() -> None:
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
        StepResult(action="explore", branch_id="b1", reason="screening complete"),
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
    assert last_results[-1].reason == "mechanism_novelty_rejected"
    assert last_results[-1].stopped is True
    assert "proposal_quality_loop" in stopped_reasons


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
        StepResult(action="explore", branch_id="b1", reason="screening complete"),
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
        StepResult(action="explore", branch_id="b1", reason="screening 1"),
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


def test_campaign_loop_default_attempt_limit_caps_quality_blocks_at_rounds() -> None:
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

    assert calls == 3
    assert last_results[-1].stopped is False
    assert "proposal_attempt_limit_exhausted" in stopped_reasons
    assert loop_statuses[-1]["attempt_limit"] == 3
    assert loop_statuses[-1]["proposal_quality_limit"] == 9
    assert loop_statuses[-1]["proposal_quality_blocks_consumed"] == 3
    assert loop_statuses[-1]["quality_blocks"] == 3


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
        StepResult(action="explore", branch_id="b1", reason="screening 1"),
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
        StepResult(action="explore", branch_id="b1", reason="screening 1"),
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
        StepResult(action="explore", branch_id="b1", reason="screening 1"),
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
        ),
        StepResult(action="explore", branch_id="b2", reason="screening 1"),
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
    assert loop_statuses[-1]["quality_blocks"] == 0


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
        StepResult(action="explore", branch_id="clean-1", reason="screening 1"),
        StepResult(action="explore", branch_id="clean-2", reason="screening 2"),
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
