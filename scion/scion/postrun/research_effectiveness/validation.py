"""Strict cross-view validation and durable-row joins for M32 postrun scoring."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from scion.core.research_history import normalize_research_history_record

from .models import (
    _FORBIDDEN_DECISIONS,
    _OUTCOMES,
    _REQUEST_KINDS,
    _SCIENTIFIC_OUTCOMES,
    _SCREENING_DECISIONS,
    _SCREENING_GATES,
    _SHARED_TERMINAL_FIELDS,
    ResearchEffectivenessExpectation,
    _as_mapping,
    _Attempt,
    _fail,
    _h_key,
    _history_decision,
    _is_incomplete_reason,
    _JoinedRow,
    _nonnegative_int,
    _patch_key,
    _Physical,
    _positive_int,
    _ProtocolFacts,
    _reject_forbidden_stage,
)
from .telemetry import _parse_runtime, _validate_provider_cap_exhaustion


def _validate_terminal_twins(
    status: Mapping[str, Any],
    summary: Mapping[str, Any],
    expectation: ResearchEffectivenessExpectation,
) -> None:
    for field in _SHARED_TERMINAL_FIELDS:
        if (
            field not in status
            or field not in summary
            or status[field] != summary[field]
        ):
            _fail("TERMINAL_PROJECTION_MISMATCH")
    if status["campaign_mode"] != "qualification_only":
        _fail("CAMPAIGN_MODE_NOT_QUALIFICATION_ONLY")
    if status["proposal_runtime_mode"] != expectation.proposal_runtime_mode:
        _fail("PROPOSAL_RUNTIME_MODE_MISMATCH")
    for field in ("n_steps", "total_rounds", "n_experiments", "screened_experiments"):
        _nonnegative_int(status[field], "TERMINAL_COUNTER_INVALID")


def _normalize_history(
    records: Sequence[Mapping[str, Any]],
    *,
    expectation: ResearchEffectivenessExpectation,
    code: str,
) -> tuple[dict[str, Any], ...]:
    if isinstance(records, (str, bytes, bytearray)) or not isinstance(
        records, Sequence
    ):
        _fail(code)
    normalized: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping):
            _fail(code)
        try:
            item = normalize_research_history_record(
                record,
                expected_problem_id=expectation.problem_id,
            )
        except (TypeError, ValueError, RecursionError):
            _fail(code)
        if dict(record) != item:
            _fail("RESEARCH_HISTORY_NOT_CANONICAL")
        _h_key(item.get("hypothesis"))
        _patch_key(item.get("patch"))
        normalized.append(item)
    return tuple(normalized)


def _parse_physical(
    status: Mapping[str, Any],
    summary: Mapping[str, Any],
    histories: tuple[dict[str, Any], ...],
    expectation: ResearchEffectivenessExpectation,
) -> _Physical:
    runtime = _as_mapping(status["proposal_runtime"], "PROPOSAL_RUNTIME_INVALID")
    if set(runtime) != {"provider_calls", "attempts"}:
        _fail("PROPOSAL_RUNTIME_INVALID")
    aggregate, attempts = _parse_runtime(runtime, expectation)
    steps = summary.get("steps")
    if not isinstance(steps, list) or len(steps) != len(histories):
        _fail("SUMMARY_HISTORY_CARDINALITY_MISMATCH")
    if status["n_steps"] != len(steps):
        _fail("TERMINAL_STEP_COUNT_MISMATCH")
    rows, join_incomplete = _join_rows(steps, histories, attempts, expectation)
    _validate_provider_cap_exhaustion(rows, aggregate, expectation)
    run_incomplete = _validate_run_result(status["run_result"], rows, attempts)
    _validate_terminal_counts(status, rows, attempts, expectation)
    incomplete = (
        join_incomplete
        or run_incomplete
        or any(attempt.accounting_state != "closed" for attempt in attempts)
    )
    initial_rows = tuple(
        row for row in rows if row.attempt is not None and row.protocol
    )
    return _Physical(
        attempts=attempts,
        rows=rows,
        p_charged=aggregate["budget_admitted"],
        aggregate_by_kind={kind: aggregate[kind] for kind in _REQUEST_KINDS},
        initial_rows=initial_rows,
        incomplete=incomplete,
    )


def _join_rows(
    steps: list[Any],
    histories: tuple[dict[str, Any], ...],
    attempts: tuple[_Attempt, ...],
    expectation: ResearchEffectivenessExpectation,
) -> tuple[tuple[_JoinedRow, ...], bool]:
    attempt_by_round = {attempt.round_num: attempt for attempt in attempts}
    rows: list[_JoinedRow] = []
    previous_round = 0
    matched_attempt_rounds: set[int] = set()
    for raw_step, history in zip(steps, histories):
        step = _as_mapping(raw_step, "SUMMARY_STEP_INVALID")
        round_num = _positive_int(step.get("round"), "SUMMARY_STEP_ROUND_INVALID")
        if round_num <= previous_round:
            _fail("SUMMARY_STEP_ROUNDS_INVALID")
        previous_round = round_num
        _reject_forbidden_stage(step.get("failure_stage"))
        _reject_forbidden_stage(step.get("stop_stage"))
        outcome = _as_mapping(history["outcome"], "HISTORY_OUTCOME_INVALID")
        _reject_forbidden_stage(outcome.get("stage"))
        h_key = _h_key(history["hypothesis"])
        patch_key = _patch_key(history["patch"])
        _validate_summary_hypothesis(step.get("hypothesis"), history["hypothesis"])
        _validate_summary_outcome(step.get("execution_outcome"), outcome)
        _validate_canary_row(step, history)
        _validate_reason_evidence(step, history)
        decision = _history_decision(history)
        if step.get("decision") != decision:
            _fail("SUMMARY_HISTORY_DECISION_MISMATCH")
        if decision in _FORBIDDEN_DECISIONS:
            _fail("FORBIDDEN_M32_DECISION")
        protocol = _protocol_facts(step.get("protocol_result"), history["protocol"])
        if protocol is not None:
            _validate_screening_decision(protocol, decision)
        attempt = attempt_by_round.get(round_num)
        if (
            _summary_outcome_stage(step) == "screening"
            and outcome.get("stage") == "canary"
            and attempt is not None
        ):
            _fail("SUMMARY_HISTORY_OUTCOME_STAGE_MISMATCH")
        if attempt is not None:
            matched_attempt_rounds.add(round_num)
            _validate_attempt_row(attempt, step, h_key, patch_key, protocol)
        expanded = attempt is None
        if expanded:
            _validate_expanded_continuation(
                rows,
                step,
                history,
                h_key=h_key,
                patch_key=patch_key,
                protocol=protocol,
            )
        rows.append(
            _JoinedRow(
                summary=step,
                history=history,
                attempt=attempt,
                h_key=h_key,
                patch_key=patch_key,
                protocol=protocol,
                expanded=expanded,
            )
        )
    return tuple(rows), matched_attempt_rounds != set(attempt_by_round)


def _validate_expanded_continuation(
    rows: list[_JoinedRow],
    step: Mapping[str, Any],
    history: Mapping[str, Any],
    *,
    h_key: tuple[Any, ...] | None,
    patch_key: tuple[tuple[str, str, str], ...] | None,
    protocol: _ProtocolFacts | None,
) -> None:
    if not rows:
        _fail("UNATTRIBUTED_SUMMARY_STEP")
    previous = rows[-1]
    formal = (
        protocol is not None
        and h_key == previous.h_key
        and patch_key == previous.patch_key
    )
    canary = _is_expanded_canary_negative(
        step,
        history,
        h_key=h_key,
        patch_key=patch_key,
        previous=previous,
    )
    valid_trigger = (
        previous.protocol is not None
        and previous.protocol.gate_outcome == "expand"
        and _history_decision(previous.history) == "expand_screening"
    )
    if not valid_trigger or not (formal or canary):
        _fail("EXPANDED_SCREENING_JOIN_INVALID")


def _validate_summary_hypothesis(value: Any, history_h: Any) -> None:
    if history_h is None:
        if value is not None:
            _fail("SUMMARY_HISTORY_HYPOTHESIS_MISMATCH")
        return
    item = _as_mapping(value, "SUMMARY_HYPOTHESIS_INVALID")
    expected = {
        "text": history_h["text"],
        "action": history_h["action"],
        "change_locus": history_h["change_locus"],
        "target_file": history_h["target_file"],
    }
    if dict(item) != expected:
        _fail("SUMMARY_HISTORY_HYPOTHESIS_MISMATCH")


def _validate_summary_outcome(value: Any, history_outcome: Mapping[str, Any]) -> None:
    item = _as_mapping(value, "SUMMARY_EXECUTION_OUTCOME_INVALID")
    if (
        item.get("outcome") != history_outcome["outcome"]
        or item.get("reason_code") != history_outcome["reason_code"]
    ):
        _fail("SUMMARY_HISTORY_OUTCOME_MISMATCH")
    provenance = _as_mapping(
        item.get("provenance"), "SUMMARY_EXECUTION_OUTCOME_PROVENANCE_INVALID"
    )
    summary_stage = provenance.get("stage")
    history_stage = history_outcome["stage"]
    if summary_stage != history_stage and not (
        summary_stage == "screening" and history_stage == "canary"
    ):
        _fail("SUMMARY_HISTORY_OUTCOME_STAGE_MISMATCH")


def _summary_outcome_stage(step: Mapping[str, Any]) -> str | None:
    outcome = step.get("execution_outcome")
    if not isinstance(outcome, Mapping):
        return None
    provenance = outcome.get("provenance")
    if not isinstance(provenance, Mapping):
        return None
    stage = provenance.get("stage")
    return stage if isinstance(stage, str) else None


def _validate_attempt_row(
    attempt: _Attempt,
    step: Mapping[str, Any],
    h_key: tuple[Any, ...] | None,
    patch_key: tuple[tuple[str, str, str], ...] | None,
    protocol: _ProtocolFacts | None,
) -> None:
    if (h_key is not None) != (attempt.hypotheses_exported == 1):
        _fail("ATTEMPT_HYPOTHESIS_JOIN_MISMATCH")
    if (patch_key is not None) != (attempt.patches_completed == 1):
        _fail("ATTEMPT_PATCH_JOIN_MISMATCH")
    for field in ("contract_passed", "verification_passed"):
        if step.get(field) not in {None, True, False}:
            _fail("SUMMARY_FORMAL_GATE_INVALID")
    if attempt.code_candidates_ready == 1 and step.get("contract_passed") is not True:
        _fail("CODE_READY_CONTRACT_JOIN_MISMATCH")
    if step.get("canary_result") is not None and (
        attempt.code_candidates_ready != 1
        or step.get("contract_passed") is not True
        or step.get("verification_passed") is not True
    ):
        _fail("CANARY_ATTEMPT_LIFECYCLE_MISMATCH")
    if protocol is None:
        return
    canary = _as_mapping(step.get("canary_result"), "SUMMARY_CANARY_INVALID")
    if (
        attempt.code_candidates_ready != 1
        or step.get("contract_passed") is not True
        or step.get("verification_passed") is not True
        or canary.get("passed") is not True
    ):
        _fail("FORMAL_PROTOCOL_GATE_JOIN_MISMATCH")


def _validate_screening_decision(
    protocol: _ProtocolFacts,
    decision: str | None,
) -> None:
    if decision not in _SCREENING_DECISIONS:
        _fail("SCREENING_DECISION_INVALID")
    if protocol.candidate_only_failure:
        expected = "abandon"
    elif protocol.champion_failed_pairs > 0:
        expected = "continue_explore"
    else:
        expected = {
            "pass": "queue_validate",
            "expand": "expand_screening",
            "fail": "continue_explore",
            "unclear": "continue_explore",
            "continue": "continue_explore",
        }[protocol.gate_outcome]
    if decision != expected:
        _fail("SCREENING_GATE_DECISION_MISMATCH")


def _is_expanded_canary_negative(
    step: Mapping[str, Any],
    history: Mapping[str, Any],
    *,
    h_key: tuple[Any, ...] | None,
    patch_key: tuple[tuple[str, str, str], ...] | None,
    previous: _JoinedRow,
) -> bool:
    outcome = history["outcome"]
    canary = step.get("canary_result")
    return bool(
        history["protocol"] is None
        and _history_decision(history) == "abandon"
        and outcome["outcome"] == "evaluated"
        and outcome["stage"] == "canary"
        and h_key == previous.h_key
        and patch_key == previous.patch_key
        and step.get("contract_passed") is True
        and step.get("verification_passed") is True
        and isinstance(canary, Mapping)
        and canary.get("passed") is False
        and isinstance(canary.get("failure_category"), str)
        and bool(canary.get("failure_category"))
    )


def _validate_canary_row(step: Mapping[str, Any], history: Mapping[str, Any]) -> None:
    outcome = history["outcome"]
    raw_canary = step.get("canary_result")
    if raw_canary is None:
        if outcome["stage"] == "canary":
            _fail("CANARY_ABANDONMENT_SHAPE_INVALID")
        return
    canary = _as_mapping(raw_canary, "SUMMARY_CANARY_INVALID")
    if not isinstance(canary.get("passed"), bool):
        _fail("SUMMARY_CANARY_INVALID")
    if canary["passed"] is True:
        if outcome["stage"] == "canary":
            _fail("CANARY_ABANDONMENT_SHAPE_INVALID")
        return
    if (
        outcome["stage"] != "canary"
        or history["protocol"] is not None
        or _history_decision(history) != "abandon"
        or outcome["outcome"] != "evaluated"
        or history["hypothesis"] is None
        or history["patch"] is None
        or step.get("contract_passed") is not True
        or step.get("verification_passed") is not True
        or canary.get("passed") is not False
        or not isinstance(canary.get("failure_category"), str)
        or not canary.get("failure_category")
    ):
        _fail("CANARY_ABANDONMENT_SHAPE_INVALID")


def _validate_reason_evidence(
    step: Mapping[str, Any], history: Mapping[str, Any]
) -> None:
    decision = history.get("decision")
    expected = (
        _as_mapping(decision, "HISTORY_DECISION_INVALID")
        if decision is not None
        else None
    )
    for summary_field, history_field in (
        ("decision_reason_codes", "reason_codes"),
        ("diagnostic_reason_codes", "diagnostic_reason_codes"),
        ("bypass_reason_codes", "bypass_reason_codes"),
    ):
        actual = step.get(summary_field)
        if not isinstance(actual, list):
            _fail("SUMMARY_REASON_CODES_INVALID")
        expected_value = expected[history_field] if expected is not None else []
        if actual != expected_value:
            _fail("SUMMARY_HISTORY_REASON_CODES_MISMATCH")
    protocol = history.get("protocol")
    if protocol is None:
        return
    protocol_map = _as_mapping(protocol, "HISTORY_PROTOCOL_INVALID")
    evidence = _as_mapping(protocol_map.get("evidence"), "HISTORY_PROTOCOL_INVALID")
    protocol_outcome = _as_mapping(
        evidence.get("protocol_outcome"), "HISTORY_PROTOCOL_OUTCOME_INVALID"
    )
    summary_protocol = _as_mapping(
        step.get("protocol_result"), "SUMMARY_PROTOCOL_INVALID"
    )
    if summary_protocol.get("reason_codes") != protocol_outcome.get("reason_codes"):
        _fail("SUMMARY_HISTORY_PROTOCOL_REASON_CODES_MISMATCH")


def _protocol_facts(summary_value: Any, history_value: Any) -> _ProtocolFacts | None:
    if history_value is None:
        if summary_value is not None:
            _fail("SUMMARY_HISTORY_PROTOCOL_MISMATCH")
        return None
    summary = _as_mapping(summary_value, "SUMMARY_PROTOCOL_INVALID")
    history = _as_mapping(history_value, "HISTORY_PROTOCOL_INVALID")
    evidence = _as_mapping(history.get("evidence"), "HISTORY_PROTOCOL_INVALID")
    if evidence.get("stage") != "screening" or summary.get("stage") != "screening":
        _fail("NON_SCREENING_PROTOCOL_STAGE")
    objective = _as_mapping(
        evidence.get("objective_outcome"), "HISTORY_PROTOCOL_OBJECTIVE_INVALID"
    )
    aggregate = _as_mapping(
        objective.get("aggregate"), "HISTORY_PROTOCOL_AGGREGATE_INVALID"
    )
    values = _protocol_counts(aggregate)
    _validate_protocol_failure_accounting(values)
    _validate_protocol_summary_counts(summary, values)
    _validate_protocol_case_outcomes(aggregate, summary, values["n_cases"])
    _validate_protocol_pair_outcomes(aggregate, summary, values["valid_pairs"])
    gate = _protocol_gate(evidence, summary)
    regressions = aggregate.get("protected_objective_regressions", ())
    if not isinstance(regressions, (list, tuple)):
        _fail("PROTECTED_REGRESSION_EVIDENCE_INVALID")
    return _ProtocolFacts(
        **values,
        protected_regression=bool(regressions),
        gate_outcome=gate,
    )


def _protocol_counts(aggregate: Mapping[str, Any]) -> dict[str, int]:
    return {
        name: _nonnegative_int(aggregate.get(name), "PROTOCOL_COUNT_INVALID")
        for name in (
            "n_cases",
            "total_pairs",
            "attempted_pairs",
            "valid_pairs",
            "failed_pairs",
            "candidate_failed_pairs",
            "champion_failed_pairs",
            "shared_failed_pairs",
            "bilateral_failed_pairs",
        )
    }


def _validate_protocol_failure_accounting(values: Mapping[str, int]) -> None:
    if values["attempted_pairs"] > values["total_pairs"]:
        _fail("PROTOCOL_PAIR_ACCOUNTING_INVALID")
    if values["valid_pairs"] + values["failed_pairs"] != values["attempted_pairs"]:
        _fail("PROTOCOL_PAIR_ACCOUNTING_INVALID")
    expected_failures = (
        values["candidate_failed_pairs"]
        + values["champion_failed_pairs"]
        - values["bilateral_failed_pairs"]
    )
    if values["failed_pairs"] != expected_failures:
        _fail("PROTOCOL_FAILURE_ACCOUNTING_INVALID")
    if values["bilateral_failed_pairs"] > min(
        values["candidate_failed_pairs"], values["champion_failed_pairs"]
    ):
        _fail("PROTOCOL_FAILURE_ACCOUNTING_INVALID")
    if values["shared_failed_pairs"] > values["champion_failed_pairs"]:
        _fail("PROTOCOL_FAILURE_ACCOUNTING_INVALID")
    if (
        values["shared_failed_pairs"] + values["bilateral_failed_pairs"]
        > values["failed_pairs"]
    ):
        _fail("PROTOCOL_FAILURE_ACCOUNTING_INVALID")


def _validate_protocol_summary_counts(
    summary: Mapping[str, Any], values: Mapping[str, int]
) -> None:
    for name, number in values.items():
        if name == "n_cases":
            continue
        observed = _nonnegative_int(summary.get(name), "SUMMARY_PROTOCOL_COUNT_INVALID")
        if observed != number:
            _fail("SUMMARY_HISTORY_PROTOCOL_COUNT_MISMATCH")


def _validate_protocol_case_outcomes(
    aggregate: Mapping[str, Any], summary: Mapping[str, Any], expected: int
) -> None:
    total = _validate_protocol_outcome_fields(
        aggregate,
        summary,
        (
            ("wins", "screening_case_wins"),
            ("losses", "screening_case_losses"),
            ("ties", "screening_case_ties"),
        ),
        history_code="PROTOCOL_CASE_ACCOUNTING_INVALID",
        summary_code="SUMMARY_PROTOCOL_CASE_ACCOUNTING_INVALID",
        mismatch_code="SUMMARY_HISTORY_PROTOCOL_CASE_MISMATCH",
    )
    if total != expected or summary.get("screening_case_total") != total:
        _fail("PROTOCOL_CASE_ACCOUNTING_INVALID")


def _validate_protocol_pair_outcomes(
    aggregate: Mapping[str, Any], summary: Mapping[str, Any], expected: int
) -> None:
    total = _validate_protocol_outcome_fields(
        aggregate,
        summary,
        (
            ("pair_wins", "screening_pair_wins"),
            ("pair_losses", "screening_pair_losses"),
            ("pair_ties", "screening_pair_ties"),
        ),
        history_code="PROTOCOL_PAIR_OUTCOME_ACCOUNTING_INVALID",
        summary_code="SUMMARY_PROTOCOL_PAIR_ACCOUNTING_INVALID",
        mismatch_code="SUMMARY_HISTORY_PROTOCOL_PAIR_MISMATCH",
    )
    if total != expected or summary.get("screening_pair_total") != total:
        _fail("PROTOCOL_PAIR_OUTCOME_ACCOUNTING_INVALID")


def _validate_protocol_outcome_fields(
    aggregate: Mapping[str, Any],
    summary: Mapping[str, Any],
    names: tuple[tuple[str, str], ...],
    *,
    history_code: str,
    summary_code: str,
    mismatch_code: str,
) -> int:
    total = 0
    for history_name, summary_name in names:
        history_count = _nonnegative_int(aggregate.get(history_name), history_code)
        summary_count = _nonnegative_int(summary.get(summary_name), summary_code)
        if summary_count != history_count:
            _fail(mismatch_code)
        total += history_count
    return total


def _protocol_gate(evidence: Mapping[str, Any], summary: Mapping[str, Any]) -> str:
    protocol_outcome = _as_mapping(
        evidence.get("protocol_outcome"), "HISTORY_PROTOCOL_OUTCOME_INVALID"
    )
    gate = protocol_outcome.get("gate_outcome")
    if gate not in _SCREENING_GATES or summary.get("gate_outcome") != gate:
        _fail("SUMMARY_HISTORY_PROTOCOL_GATE_MISMATCH")
    assert isinstance(gate, str)
    return gate


def _validate_run_result(
    value: Any,
    rows: tuple[_JoinedRow, ...],
    attempts: tuple[_Attempt, ...],
) -> bool:
    run = _as_mapping(value, "RUN_RESULT_INVALID")
    status, stop_reason = _validate_run_header(run)
    protocol_rows = _validate_run_protocol_projection(run, rows)
    outcomes, histogram_mismatch, outcome_incomplete = _run_outcome_facts(run, rows)
    missing_durable_row = run["scheduled_calls"] != len(rows)
    last_mismatch = _validate_run_durable_projection(
        run,
        rows,
        missing_durable_row=missing_durable_row,
    )
    exact_validity = _run_validity_is_exact(run["run_validity"])
    qualification_incomplete = _run_qualification_incomplete(
        run["qualification"], stop_reason
    )
    return any(
        (
            histogram_mismatch,
            _rows_have_incomplete_reason(rows),
            outcome_incomplete,
            missing_durable_row,
            last_mismatch,
            _has_incomplete_canary(rows),
            run["unknown_outcome_count"] != 0,
            run.get("terminal_exception") is not None,
            _is_incomplete_reason(stop_reason),
            any(attempt.accounting_state != "closed" for attempt in attempts),
            not exact_validity,
            status != "completed",
            run["evaluated_rounds"] != protocol_rows,
            sum(outcomes.values()) != run["scheduled_calls"],
            qualification_incomplete,
        )
    )


def _validate_run_header(run: Mapping[str, Any]) -> tuple[str, str]:
    required = {
        "status",
        "requested_rounds",
        "evaluated_rounds",
        "scheduled_calls",
        "formal_screened_candidates",
        "protocol_stage_counts",
        "failure_categories",
        "execution_outcome_counts",
        "unknown_outcome_count",
        "last_execution_outcome",
        "run_validity",
        "qualification",
        "stop_reason",
    }
    if not required <= set(run):
        _fail("RUN_RESULT_INVALID")
    status = run["status"]
    if status not in {"completed", "stopped"}:
        _fail("RUN_RESULT_NOT_TERMINAL")
    stop_reason = run["stop_reason"]
    if not isinstance(stop_reason, str) or not stop_reason:
        _fail("RUN_RESULT_NOT_TERMINAL")
    for field in (
        "requested_rounds",
        "evaluated_rounds",
        "scheduled_calls",
        "formal_screened_candidates",
        "unknown_outcome_count",
    ):
        _nonnegative_int(run[field], "RUN_RESULT_COUNTER_INVALID")
    assert isinstance(status, str) and isinstance(stop_reason, str)
    return status, stop_reason


def _validate_run_protocol_projection(
    run: Mapping[str, Any], rows: tuple[_JoinedRow, ...]
) -> int:
    stage_counts = _as_mapping(
        run["protocol_stage_counts"], "PROTOCOL_STAGE_COUNTS_INVALID"
    )
    if set(stage_counts) != {"screening", "validation", "frozen"}:
        _fail("PROTOCOL_STAGE_COUNTS_INVALID")
    for count in stage_counts.values():
        _nonnegative_int(count, "PROTOCOL_STAGE_COUNTS_INVALID")
    if stage_counts["validation"] != 0 or stage_counts["frozen"] != 0:
        _fail("FORBIDDEN_PROTOCOL_STAGE_COUNT")
    protocol_rows = sum(row.protocol is not None for row in rows)
    if stage_counts["screening"] != protocol_rows:
        _fail("PROTOCOL_STAGE_COUNT_MISMATCH")
    if run["formal_screened_candidates"] != protocol_rows:
        _fail("FORMAL_SCREENING_COUNT_MISMATCH")
    return protocol_rows


def _run_outcome_facts(
    run: Mapping[str, Any], rows: tuple[_JoinedRow, ...]
) -> tuple[dict[str, int], bool, bool]:
    outcomes = _as_mapping(
        run["execution_outcome_counts"], "RUN_OUTCOME_COUNTS_INVALID"
    )
    if tuple(outcomes) != _OUTCOMES:
        _fail("RUN_OUTCOME_COUNTS_INVALID")
    parsed_outcomes = {
        name: _nonnegative_int(outcomes[name], "RUN_OUTCOME_COUNTS_INVALID")
        for name in _OUTCOMES
    }
    observed = Counter(str(row.history["outcome"]["outcome"]) for row in rows)
    histogram_mismatch = any(
        observed[name] != parsed_outcomes[name] for name in _OUTCOMES
    )
    outcome_incomplete = any(
        parsed_outcomes[name] for name in _OUTCOMES if name not in _SCIENTIFIC_OUTCOMES
    )
    return parsed_outcomes, histogram_mismatch, outcome_incomplete


def _validate_run_durable_projection(
    run: Mapping[str, Any],
    rows: tuple[_JoinedRow, ...],
    *,
    missing_durable_row: bool,
) -> bool:
    last_mismatch = _last_execution_outcome(run.get("last_execution_outcome")) != (
        _expected_last_execution_outcome(rows[-1]) if rows else None
    )
    failure_categories = _as_mapping(
        run["failure_categories"], "RUN_FAILURE_CATEGORIES_INVALID"
    )
    parsed_failure_categories = {
        key: _nonnegative_int(value, "RUN_FAILURE_CATEGORIES_INVALID")
        for key, value in failure_categories.items()
    }
    expected_failure_categories = _expected_failure_categories(rows)
    if missing_durable_row:
        if any(
            parsed_failure_categories.get(key, 0) < count
            for key, count in expected_failure_categories.items()
        ):
            _fail("RUN_FAILURE_CATEGORY_COUNT_MISMATCH")
    elif parsed_failure_categories != expected_failure_categories:
        _fail("RUN_FAILURE_CATEGORY_COUNT_MISMATCH")
    if last_mismatch and not missing_durable_row:
        _fail("RUN_LAST_EXECUTION_OUTCOME_MISMATCH")
    return last_mismatch


def _run_validity_is_exact(value: Any) -> bool:
    validity = _as_mapping(value, "RUN_VALIDITY_INVALID")
    if set(validity) != {"valid", "status", "reason"} or (
        (validity["valid"] is not None and type(validity["valid"]) is not bool)
        or not isinstance(validity["status"], str)
        or not isinstance(validity["reason"], str)
    ):
        _fail("RUN_VALIDITY_INVALID")
    exact_validity = validity == {
        "valid": True,
        "status": "valid",
        "reason": "valid",
    }
    known_validities = (
        exact_validity,
        validity
        == {
            "valid": True,
            "status": "valid",
            "reason": "valid_incomplete",
        },
        validity
        == {
            "valid": False,
            "status": "invalid",
            "reason": "invalid_no_evaluated_outcome",
        },
        validity == {"valid": None, "status": "pending", "reason": "running"},
    )
    if not any(known_validities):
        _fail("RUN_VALIDITY_INCONSISTENT")
    return exact_validity


def _run_qualification_incomplete(value: Any, stop_reason: str) -> bool:
    qualification = _as_mapping(value, "QUALIFICATION_PROJECTION_INVALID")
    disposition = qualification.get("disposition")
    if disposition not in {
        "ready_for_postrun_qualification_audit",
        "qualification_not_reached",
        "pending",
        "incomplete",
    }:
        _fail("QUALIFICATION_DISPOSITION_INVALID")
    expected_disposition = {
        "qualification_not_reached": "qualification_not_reached",
        "qualification_boundary_reached": "ready_for_postrun_qualification_audit",
    }.get(stop_reason)
    if expected_disposition is not None and disposition != expected_disposition:
        _fail("QUALIFICATION_TERMINAL_DISPOSITION_MISMATCH")
    return disposition in {"pending", "incomplete"} or expected_disposition is None


def _rows_have_incomplete_reason(rows: tuple[_JoinedRow, ...]) -> bool:
    return any(
        _is_incomplete_reason(str(row.history["outcome"]["reason_code"]))
        for row in rows
    )


def _has_incomplete_canary(rows: tuple[_JoinedRow, ...]) -> bool:
    return any(
        row.history["outcome"]["stage"] == "canary"
        and isinstance(row.summary.get("canary_result"), Mapping)
        and row.summary["canary_result"].get("failure_category") != "candidate_failure"
        for row in rows
    )


def _last_execution_outcome(value: Any) -> dict[str, str] | None:
    if value is None:
        return None
    item = _as_mapping(value, "RUN_LAST_EXECUTION_OUTCOME_INVALID")
    if set(item) != {"outcome", "reason_code", "stage"} or any(
        not isinstance(item[field], str) or not item[field]
        for field in ("outcome", "reason_code", "stage")
    ):
        _fail("RUN_LAST_EXECUTION_OUTCOME_INVALID")
    return {field: item[field] for field in ("outcome", "reason_code", "stage")}


def _expected_last_execution_outcome(row: _JoinedRow) -> dict[str, str]:
    outcome = row.history["outcome"]
    stage = _summary_outcome_stage(row.summary)
    if stage is None:
        _fail("SUMMARY_EXECUTION_OUTCOME_PROVENANCE_INVALID")
    return {
        "outcome": outcome["outcome"],
        "reason_code": outcome["reason_code"],
        "stage": stage,
    }


def _expected_failure_categories(
    rows: tuple[_JoinedRow, ...],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        stage = row.summary.get("failure_stage")
        detail = row.summary.get("failure_detail")
        if not stage and not detail:
            continue
        outcome = row.history["outcome"]["outcome"]
        canary = row.summary.get("canary_result")
        if outcome not in _SCIENTIFIC_OUTCOMES:
            category = outcome
        elif isinstance(canary, Mapping) and canary.get("passed") is False:
            category = canary.get("failure_category")
        else:
            category = stage
        if not isinstance(category, str) or not category:
            _fail("SUMMARY_FAILURE_CATEGORY_UNRECOVERABLE")
        counts[category] += 1
    return dict(counts)


def _validate_terminal_counts(
    status: Mapping[str, Any],
    rows: tuple[_JoinedRow, ...],
    attempts: tuple[_Attempt, ...],
    expectation: ResearchEffectivenessExpectation,
) -> None:
    protocol_rows = tuple(row for row in rows if row.protocol is not None)
    initial_rows = tuple(row for row in protocol_rows if row.attempt is not None)
    expanded_rows = tuple(row for row in protocol_rows if row.expanded)
    _validate_terminal_inventory(status, rows, attempts, protocol_rows)
    run = _as_mapping(status["run_result"], "RUN_RESULT_INVALID")
    qualification = _as_mapping(
        run["qualification"], "QUALIFICATION_PROJECTION_INVALID"
    )
    limits = _validate_qualification_limits(qualification, expectation)
    _validate_qualification_counters(
        qualification,
        limits,
        rows=rows,
        attempts=attempts,
        protocol_rows=protocol_rows,
        initial_rows=initial_rows,
        expanded_rows=expanded_rows,
    )


def _validate_terminal_inventory(
    status: Mapping[str, Any],
    rows: tuple[_JoinedRow, ...],
    attempts: tuple[_Attempt, ...],
    protocol_rows: tuple[_JoinedRow, ...],
) -> None:
    if status["n_experiments"] != len(protocol_rows) or (
        status["screened_experiments"] != len(protocol_rows)
    ):
        _fail("TERMINAL_EXPERIMENT_COUNT_MISMATCH")
    observed_rounds = [int(row.summary["round"]) for row in rows]
    observed_rounds.extend(attempt.round_num for attempt in attempts)
    expected_total_rounds = max(observed_rounds, default=0)
    if status["total_rounds"] != expected_total_rounds:
        _fail("TERMINAL_ROUND_COUNT_MISMATCH")


def _validate_qualification_limits(
    qualification: Mapping[str, Any],
    expectation: ResearchEffectivenessExpectation,
) -> Mapping[str, Any]:
    if qualification.get("mode") != "qualification_only":
        _fail("QUALIFICATION_MODE_INVALID")
    limits = _as_mapping(qualification.get("limits"), "QUALIFICATION_LIMITS_INVALID")
    if set(limits) != {
        "max_proposal_attempts",
        "max_verified_candidate_chains",
        "max_formal_screening_stages",
    }:
        _fail("QUALIFICATION_LIMITS_INVALID")
    for value in limits.values():
        _positive_int(value, "QUALIFICATION_LIMITS_INVALID")
    if limits["max_proposal_attempts"] != expectation.a_cap:
        _fail("QUALIFICATION_ATTEMPT_CAP_MISMATCH")
    return limits


def _validate_qualification_counters(
    qualification: Mapping[str, Any],
    limits: Mapping[str, Any],
    *,
    rows: tuple[_JoinedRow, ...],
    attempts: tuple[_Attempt, ...],
    protocol_rows: tuple[_JoinedRow, ...],
    initial_rows: tuple[_JoinedRow, ...],
    expanded_rows: tuple[_JoinedRow, ...],
) -> None:
    for field in (
        "proposal_attempts",
        "verified_candidate_chains",
        "formal_screening_stages",
        "initial_screening_stages",
        "expanded_screening_stages",
    ):
        _nonnegative_int(qualification.get(field), "QUALIFICATION_COUNTER_INVALID")
    if qualification["proposal_attempts"] != len(attempts):
        _fail("QUALIFICATION_ATTEMPT_COUNT_MISMATCH")
    if qualification["formal_screening_stages"] != len(protocol_rows):
        _fail("QUALIFICATION_FORMAL_COUNT_MISMATCH")
    if qualification["initial_screening_stages"] != len(initial_rows) or (
        qualification["expanded_screening_stages"] != len(expanded_rows)
    ):
        _fail("QUALIFICATION_SCREENING_COUNT_MISMATCH")
    if (
        qualification["verified_candidate_chains"]
        > limits["max_verified_candidate_chains"]
        or qualification["formal_screening_stages"]
        > limits["max_formal_screening_stages"]
    ):
        _fail("QUALIFICATION_LIMIT_EXCEEDED")
    verified_attempts = sum(
        row.attempt is not None and row.summary.get("verification_passed") is True
        for row in rows
    )
    if qualification["verified_candidate_chains"] != verified_attempts:
        _fail("QUALIFICATION_VERIFIED_CHAIN_COUNT_MISMATCH")
