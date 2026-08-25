"""Strict parsing for D1 proposal-runtime telemetry artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from itertools import pairwise
from typing import Any

from .models import (
    _ATTEMPT_COUNTERS,
    _REQUEST_KINDS,
    ResearchEffectivenessExpectation,
    _as_mapping,
    _Attempt,
    _fail,
    _JoinedRow,
    _nonnegative_int,
    _positive_int,
)


def _parse_runtime(
    runtime: Mapping[str, Any],
    expectation: ResearchEffectivenessExpectation,
) -> tuple[dict[str, int], tuple[_Attempt, ...]]:
    aggregate = _parse_provider_calls(
        runtime["provider_calls"], cap=expectation.p_cap, aggregate=True
    )
    raw_attempts = runtime["attempts"]
    if not isinstance(raw_attempts, list):
        _fail("PROPOSAL_ATTEMPTS_INVALID")
    attempts = tuple(
        _parse_attempt(raw, expectation.max_hypothesis_candidates)
        for raw in raw_attempts
    )
    rounds = tuple(item.round_num for item in attempts)
    if any(left >= right for left, right in pairwise(rounds)):
        _fail("PROPOSAL_ATTEMPT_ROUNDS_INVALID")
    if len(attempts) > expectation.a_cap:
        _fail("PROPOSAL_ATTEMPT_CAP_EXCEEDED")
    _validate_attempt_provider_totals(attempts, aggregate)
    return aggregate, attempts


def _validate_attempt_provider_totals(
    attempts: tuple[_Attempt, ...], aggregate: Mapping[str, int]
) -> None:
    if sum(item.budget_admitted for item in attempts) != aggregate["budget_admitted"]:
        _fail("PROVIDER_ATTEMPT_TOTAL_MISMATCH")
    for kind in _REQUEST_KINDS:
        if sum(item.by_request_kind[kind] for item in attempts) != aggregate[kind]:
            _fail("PROVIDER_ATTEMPT_KIND_MISMATCH")


def _validate_provider_cap_exhaustion(
    rows: tuple[_JoinedRow, ...],
    aggregate: Mapping[str, int],
    expectation: ResearchEffectivenessExpectation,
) -> None:
    exhausted = any(
        row.history["outcome"]["reason_code"] == "PROVIDER_CALL_CAP_EXHAUSTED"
        for row in rows
    )
    if exhausted and aggregate["budget_admitted"] != expectation.p_cap:
        _fail("PROVIDER_CAP_EXHAUSTION_ACCOUNTING_MISMATCH")


def _parse_provider_calls(value: Any, *, cap: int, aggregate: bool) -> dict[str, int]:
    item = _as_mapping(value, "PROVIDER_CALLS_INVALID")
    expected = (
        {"budget_admitted", "cap", "remaining", "by_request_kind"}
        if aggregate
        else {"budget_admitted", "by_request_kind"}
    )
    if set(item) != expected:
        _fail("PROVIDER_CALLS_INVALID")
    admitted = _nonnegative_int(item["budget_admitted"], "PROVIDER_CALLS_INVALID")
    kinds = _as_mapping(item["by_request_kind"], "PROVIDER_REQUEST_KINDS_INVALID")
    if tuple(kinds) != _REQUEST_KINDS:
        _fail("PROVIDER_REQUEST_KINDS_INVALID")
    parsed = {
        kind: _nonnegative_int(kinds[kind], "PROVIDER_REQUEST_KIND_COUNT_INVALID")
        for kind in _REQUEST_KINDS
    }
    if sum(parsed.values()) != admitted:
        _fail("PROVIDER_REQUEST_KIND_SUM_MISMATCH")
    if aggregate:
        if item["cap"] != cap or type(item["cap"]) is not int:
            _fail("PROVIDER_CAP_MISMATCH")
        if item["remaining"] != cap - admitted:
            _fail("PROVIDER_REMAINING_MISMATCH")
        if admitted > cap:
            _fail("PROVIDER_CAP_EXCEEDED")
    return {"budget_admitted": admitted, **parsed}


def _parse_attempt(value: Any, k: int) -> _Attempt:
    item = _as_mapping(value, "PROPOSAL_ATTEMPT_INVALID")
    if set(item) != {
        "round_num",
        "accounting_state",
        "provider_calls",
        *_ATTEMPT_COUNTERS,
    }:
        _fail("PROPOSAL_ATTEMPT_INVALID")
    round_num = _positive_int(item["round_num"], "PROPOSAL_ATTEMPT_ROUND_INVALID")
    state = item["accounting_state"]
    if state not in {"active", "closed", "interrupted", "unresolved"}:
        _fail("PROPOSAL_ATTEMPT_STATE_INVALID")
    provider = _parse_provider_calls(item["provider_calls"], cap=0, aggregate=False)
    counters = {
        field: _nonnegative_int(item[field], "PROPOSAL_ATTEMPT_COUNTER_INVALID")
        for field in _ATTEMPT_COUNTERS
    }
    completed = counters["hypothesis_candidates_completed"]
    selected = counters["hypothesis_candidates_selected"]
    exported = counters["hypotheses_exported"]
    patches = counters["patches_completed"]
    ready = counters["code_candidates_ready"]
    if not (0 <= ready <= patches <= exported <= selected <= completed <= k):
        _fail("PROPOSAL_ATTEMPT_LIFECYCLE_INVALID")
    if any(counters[name] > 1 for name in _ATTEMPT_COUNTERS[1:]):
        _fail("PROPOSAL_ATTEMPT_LIFECYCLE_INVALID")
    if selected == 1 and completed != k:
        _fail("PROPOSAL_ATTEMPT_SELECTION_INVALID")
    if provider["budget_admitted"] == 0 and any(counters.values()):
        _fail("ZERO_CALL_ATTEMPT_PROGRESS_INVALID")
    return _Attempt(
        round_num=round_num,
        accounting_state=state,
        budget_admitted=provider["budget_admitted"],
        by_request_kind={kind: provider[kind] for kind in _REQUEST_KINDS},
        **counters,
    )
