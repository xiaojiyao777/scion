from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from scion.core.proposal_runtime_telemetry import ProposalRuntimeTelemetry
from scion.core.resource_envelope import (
    ProviderCallBudget,
    ProviderCallCapExhausted,
)

_KINDS = (
    "hypothesis",
    "hypothesis_research_turn",
    "code",
    "code_research_turn",
    "code_research_finalize",
    "other",
)


def _row(value: dict[str, Any], index: int = 0) -> dict[str, Any]:
    return value["attempts"][index]


def test_one_snapshot_attributes_active_and_closed_k1_counts() -> None:
    budget = ProviderCallBudget(None)
    runtime = ProposalRuntimeTelemetry(budget, max_hypothesis_candidates=1)

    with runtime.attempt_scope(1):
        budget.consume(request_kind="hypothesis_research_turn")
        runtime.record_hypothesis_candidate_completed()
        runtime.record_hypothesis_candidate_selected()
        runtime.record_hypothesis_exported()
        budget.consume(request_kind="code_research_turn")
        budget.consume(request_kind="code_research_finalize")
        runtime.record_patch_completed()
        runtime.record_code_candidate_ready()
        supplied = budget.snapshot()
        active_snapshot = runtime.snapshot(supplied, terminal=False)

        assert active_snapshot.provider_calls is supplied
        assert _row(active_snapshot.to_primitive()) == {
            "round_num": 1,
            "accounting_state": "active",
            "provider_calls": {
                "budget_admitted": 3,
                "by_request_kind": {
                    "hypothesis": 0,
                    "hypothesis_research_turn": 1,
                    "code": 0,
                    "code_research_turn": 1,
                    "code_research_finalize": 1,
                    "other": 0,
                },
            },
            "hypothesis_candidates_completed": 1,
            "hypothesis_candidates_selected": 1,
            "hypotheses_exported": 1,
            "patches_completed": 1,
            "code_candidates_ready": 1,
        }

    closed = runtime.snapshot(budget.snapshot(), terminal=True)
    assert closed.attempts[0].accounting_state == "closed"
    assert closed.attempts[0].budget_admitted == 3
    with pytest.raises(FrozenInstanceError):
        closed.attempts[0].round_num = 9  # type: ignore[misc]


def test_two_attempt_deltas_sum_all_kinds_and_cap_reject_is_zero() -> None:
    budget = ProviderCallBudget(6)
    runtime = ProposalRuntimeTelemetry(budget, max_hypothesis_candidates=2)

    with runtime.attempt_scope(1):
        for kind in _KINDS:
            budget.consume(request_kind=kind)
        runtime.record_hypothesis_candidate_completed()
        runtime.record_hypothesis_candidate_completed()
        runtime.record_hypothesis_candidate_selected()
        runtime.record_hypothesis_exported()

    with runtime.attempt_scope(2), pytest.raises(ProviderCallCapExhausted):
        budget.consume(request_kind="hypothesis_research_turn")

    projected = runtime.snapshot(budget.snapshot(), terminal=True).to_primitive()
    first, rejected = projected["attempts"]
    assert first["provider_calls"] == {
        "budget_admitted": 6,
        "by_request_kind": {kind: 1 for kind in _KINDS},
    }
    assert first["hypothesis_candidates_completed"] == 2
    assert first["hypothesis_candidates_selected"] == 1
    assert rejected["accounting_state"] == "closed"
    assert rejected["provider_calls"] == {
        "budget_admitted": 0,
        "by_request_kind": {kind: 0 for kind in _KINDS},
    }
    assert (
        sum(
            attempt["provider_calls"]["budget_admitted"]
            for attempt in projected["attempts"]
        )
        == projected["provider_calls"]["budget_admitted"]
    )


@pytest.mark.parametrize(
    ("error", "state"),
    (
        (RuntimeError("synthetic unresolved"), "unresolved"),
        (KeyboardInterrupt("synthetic interrupt"), "interrupted"),
        (SystemExit("synthetic exit"), "interrupted"),
    ),
)
def test_scope_classifies_base_exception_and_propagates(
    error: BaseException,
    state: str,
) -> None:
    budget = ProviderCallBudget(2)
    runtime = ProposalRuntimeTelemetry(budget, max_hypothesis_candidates=1)

    with pytest.raises(type(error), match="synthetic"), runtime.attempt_scope(7):
        budget.consume(request_kind="hypothesis_research_turn")
        raise error

    row = runtime.snapshot(budget.snapshot(), terminal=True).attempts[0]
    assert row.accounting_state == state
    assert row.budget_admitted == 1


def test_count_hooks_never_throw_and_faulted_attempt_is_unresolved() -> None:
    budget = ProviderCallBudget(None)
    runtime = ProposalRuntimeTelemetry(budget, max_hypothesis_candidates=1)

    runtime.record_hypothesis_candidate_completed()
    runtime.record_hypothesis_candidate_selected()
    runtime.record_hypothesis_exported()
    runtime.record_patch_completed()
    runtime.record_code_candidate_ready()
    with runtime.attempt_scope(1):
        runtime.record_hypothesis_candidate_selected()
        runtime.record_code_candidate_ready()

    row = runtime.snapshot(budget.snapshot(), terminal=True).attempts[0]
    assert row.accounting_state == "unresolved"
    assert row.hypothesis_candidates_completed == 0
    assert row.hypothesis_candidates_selected == 0
    assert row.hypotheses_exported == 0
    assert row.patches_completed == 0
    assert row.code_candidates_ready == 0


def test_terminal_snapshot_rejects_active_or_unattributed_provider_calls() -> None:
    budget = ProviderCallBudget(None)
    runtime = ProposalRuntimeTelemetry(budget, max_hypothesis_candidates=1)

    with runtime.attempt_scope(1), pytest.raises(RuntimeError, match="active attempt"):
        runtime.snapshot(budget.snapshot(), terminal=True)

    budget.consume(request_kind="code")
    with pytest.raises(RuntimeError, match="do not sum"):
        runtime.snapshot(budget.snapshot(), terminal=True)


def test_projection_has_only_the_frozen_public_schema() -> None:
    budget = ProviderCallBudget(3)
    runtime = ProposalRuntimeTelemetry(budget, max_hypothesis_candidates=2)

    with runtime.attempt_scope(4):
        budget.consume(request_kind="hypothesis_research_turn")

    projection = runtime.snapshot(budget.snapshot(), terminal=True).to_primitive()
    assert set(projection) == {"provider_calls", "attempts"}
    assert set(_row(projection)) == {
        "round_num",
        "accounting_state",
        "provider_calls",
        "hypothesis_candidates_completed",
        "hypothesis_candidates_selected",
        "hypotheses_exported",
        "patches_completed",
        "code_candidates_ready",
    }
    assert set(_row(projection)["provider_calls"]) == {
        "budget_admitted",
        "by_request_kind",
    }


def test_public_projection_mutation_cannot_change_runtime_truth() -> None:
    budget = ProviderCallBudget(2)
    runtime = ProposalRuntimeTelemetry(budget, max_hypothesis_candidates=1)

    with runtime.attempt_scope(1):
        budget.consume(request_kind="hypothesis_research_turn")

    projection = runtime.snapshot(budget.snapshot(), terminal=True).to_primitive()
    projection["provider_calls"]["budget_admitted"] = 99
    projection["provider_calls"]["by_request_kind"]["hypothesis"] = 99
    projection["attempts"][0]["accounting_state"] = "mutated"
    projection["attempts"].clear()

    fresh = runtime.snapshot(budget.snapshot(), terminal=True).to_primitive()
    assert fresh["provider_calls"]["budget_admitted"] == 1
    assert fresh["provider_calls"]["by_request_kind"]["hypothesis"] == 0
    assert _row(fresh)["accounting_state"] == "closed"
