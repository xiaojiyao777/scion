from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

import pytest

from scion.core.code_research_limits import CodeResearchLimits
from scion.core.resource_envelope import (
    ProviderCallBudget,
    ProviderCallCapExhausted,
)
from scion.proposal.bounded_research import bounded_json
from scion.proposal.engine import (
    ProposalValidationError,
    build_prompt_turn_snapshot,
)
from scion.proposal.hypothesis_candidate_bank import HypothesisCandidateBank
from scion.proposal.hypothesis_research_session import (
    HypothesisResearchAbstain,
    HypothesisResearchContextError,
    HypothesisResearchFinalized,
)
from scion.tests.unit.proposal.test_hypothesis_research_session import (
    _basis,
    _context,
    _history_one_hypothesis,
    _hypothesis,
    _run,
    _snapshot,
)

_K1_WIRE_SHA256 = "04df346c822f784f355cf1a45ea3de62256177f8f50d8b575e5beaf573f035e1"


def _candidate(text: str) -> dict[str, Any]:
    value = _hypothesis()
    value["hypothesis_text"] = text
    return value


def _stage(
    slot: object,
    hypothesis: object,
    research_basis: object | None = None,
) -> dict[str, Any]:
    return {
        "action": "stage_hypothesis_candidate",
        "slot": slot,
        "hypothesis": hypothesis,
        "research_basis": (
            _basis("source-0001") if research_basis is None else research_basis
        ),
    }


def _select(slot: object) -> dict[str, Any]:
    return {"action": "select_hypothesis_candidate", "slot": slot}


def _action_names(call: dict[str, Any]) -> list[str]:
    return [
        branch["properties"]["action"]["enum"][0]
        for branch in call["tool"]["input_schema"]["oneOf"]
    ]


def _slot_enum(call: dict[str, Any], action: str) -> list[int]:
    branch = next(
        candidate
        for candidate in call["tool"]["input_schema"]["oneOf"]
        if candidate["properties"]["action"]["enum"] == [action]
    )
    return branch["properties"]["slot"]["enum"]


def _limits(*, max_turns: int, **overrides: Any) -> CodeResearchLimits:
    return CodeResearchLimits(
        max_turns=max_turns,
        max_hypothesis_candidates=2,
        **overrides,
    )


def test_default_and_explicit_k1_preserve_the_frozen_wire() -> None:
    wires: list[str] = []
    for limits in (
        CodeResearchLimits(max_turns=2),
        CodeResearchLimits(max_turns=2, max_hypothesis_candidates=1),
    ):
        session, client = _run(
            [
                {"action": "read_source", "ref": "source-0001"},
                {
                    "action": "finalize_hypothesis",
                    "hypothesis": _hypothesis(),
                    "research_basis": _basis("source-0001"),
                },
            ],
            limits=limits,
        )

        result = session.run(_snapshot(include_history=False))

        assert isinstance(result, HypothesisResearchFinalized)
        wires.append(
            json.dumps(
                client.calls,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            )
        )

    assert wires[0] == wires[1]
    assert hashlib.sha256(wires[0].encode()).hexdigest() == _K1_WIRE_SHA256


def test_k2_stages_two_ordinal_slots_then_provider_selects_one() -> None:
    loser_text = "K2_TRACE_ONLY_LOSER_MECHANISM"
    selected_text = "K2_SELECTED_MECHANISM"
    session, client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            _stage(1, _candidate(loser_text)),
            _stage(2, _candidate(selected_text)),
            _select(2),
        ],
        limits=_limits(max_turns=4),
    )

    result = session.run(_snapshot(include_history=False))

    assert isinstance(result, HypothesisResearchFinalized)
    assert result.hypothesis.hypothesis_text == selected_text
    assert session.provider_calls_used == 4
    assert "stage_hypothesis_candidate" not in _action_names(client.calls[0])
    assert _slot_enum(client.calls[1], "stage_hypothesis_candidate") == [1]
    assert _slot_enum(client.calls[2], "stage_hypothesis_candidate") == [2]
    assert "stage_hypothesis_candidate" not in _action_names(client.calls[3])
    assert _slot_enum(client.calls[3], "select_hypothesis_candidate") == [1, 2]
    assert all(
        "finalize_hypothesis" not in _action_names(call) for call in client.calls
    )
    assert loser_text in client.calls[2]["system_text"]
    assert selected_text in client.calls[3]["system_text"]
    safe_results = json.dumps(session._budget.results, sort_keys=True)
    assert loser_text not in safe_results
    assert selected_text not in safe_results


def test_candidate_bank_copies_on_stage_projection_and_selection() -> None:
    original_text = "K2_IMMUTABLE_STORED_H"
    session, _client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": _candidate(original_text),
                "research_basis": _basis("source-0001"),
            },
        ],
        limits=CodeResearchLimits(max_turns=2),
    )
    first = session.run(_snapshot(include_history=False))
    assert isinstance(first, HypothesisResearchFinalized)
    second = deepcopy(first)
    second.hypothesis.hypothesis_text = "K2_IMMUTABLE_SECOND_H"
    bank = HypothesisCandidateBank()

    assert bank.stage_validated(1, first) is None
    assert bank.stage_validated(2, second) is None
    first.hypothesis.hypothesis_text = "K2_MUTATED_AFTER_STAGE"
    projection = bank.to_research_projection()
    selected = bank.select(1)

    assert isinstance(selected, HypothesisResearchFinalized)
    assert projection["staged_candidates"][0]["hypothesis"]["hypothesis_text"] == (
        original_text
    )
    selected.hypothesis.hypothesis_text = "K2_MUTATED_AFTER_SELECTION"
    assert (
        bank.to_research_projection()["staged_candidates"][0]["hypothesis"][
            "hypothesis_text"
        ]
        == original_text
    )


def test_k2_nearest_history_audit_keeps_the_same_unstaged_ordinal() -> None:
    first = _history_one_hypothesis()
    second = deepcopy(first)
    second["expected_effect"] = "K2_HISTORY_GROUNDED_SECOND_SLOT"
    grounded_basis = _basis(
        "source-0001",
        "history-0001",
        nearest_prior_refs=("history-0001",),
    )
    session, client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            _stage(1, first, _basis("source-0001")),
            {"action": "read_history", "ref": "history-0001"},
            _stage(1, first, grounded_basis),
            _stage(2, second, grounded_basis),
            _select(2),
        ],
        limits=_limits(max_turns=6),
    )

    result = session.run(_snapshot())

    assert isinstance(result, HypothesisResearchFinalized)
    assert result.hypothesis.expected_effect == second["expected_effect"]
    audit = session._budget.results[1]
    assert audit == {
        "action": "stage_hypothesis_candidate",
        "ok": False,
        "reason": "nearest_history_audit_required",
        "required_history_ref": "history-0001",
    }
    assert _slot_enum(client.calls[2], "stage_hypothesis_candidate") == [1]
    assert _slot_enum(client.calls[3], "stage_hypothesis_candidate") == [1]


def test_k2_rejects_ordinal_overwrite_and_same_h_duplicate() -> None:
    original_text = "K2_ORIGINAL_SLOT_ONE"
    out_of_order_sentinel = "K2_OUT_OF_ORDER_BODY_MUST_NOT_REPLAY"
    overwrite_sentinel = "K2_OVERWRITE_BODY_MUST_NOT_REPLAY"
    duplicate_basis_sentinel = "K2_DUPLICATE_BASIS_MUST_NOT_REPLAY"
    original = _candidate(original_text)
    duplicate_basis = _basis("source-0001")
    duplicate_basis["material_delta"] = duplicate_basis_sentinel
    out_of_order = _stage(2, _candidate(out_of_order_sentinel))
    del out_of_order["research_basis"]
    overwrite = _stage(1, overwrite_sentinel, "K2_OVERWRITE_BASIS_MUST_NOT_PARSE")
    overwrite["unexpected_body_field"] = "K2_OVERWRITE_EXTRA_MUST_NOT_PARSE"
    session, client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            out_of_order,
            _stage(1, original),
            overwrite,
            _stage(2, deepcopy(original), duplicate_basis),
            _stage(2, _candidate("K2_DISTINCT_SLOT_TWO")),
            _select(1),
        ],
        limits=_limits(max_turns=7),
    )

    result = session.run(_snapshot(include_history=False))

    assert isinstance(result, HypothesisResearchFinalized)
    assert result.hypothesis.hypothesis_text == original_text
    reasons = [
        item.get("reason") for item in session._budget.results if not item.get("ok")
    ]
    assert reasons == [
        "candidate_slot_out_of_order",
        "candidate_slot_already_staged",
        "candidate_hypothesis_duplicate",
    ]
    assert out_of_order_sentinel not in client.calls[2]["system_text"]
    assert overwrite_sentinel not in client.calls[4]["system_text"]
    assert duplicate_basis_sentinel not in client.calls[5]["system_text"]
    assert _slot_enum(client.calls[2], "stage_hypothesis_candidate") == [1]
    assert _slot_enum(client.calls[4], "stage_hypothesis_candidate") == [2]
    assert _slot_enum(client.calls[5], "stage_hypothesis_candidate") == [2]


def test_k2_early_nonexistent_and_bool_selection_are_safe_corrections() -> None:
    selected_text = "K2_SELECTION_RECOVERY"
    session, _client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            _stage(1, _candidate("K2_FIRST_FOR_SELECTION_ERRORS")),
            _select(2),
            _select(1),
            _stage(2, _candidate(selected_text)),
            _select(3),
            _select(True),
            _select(2),
        ],
        limits=_limits(max_turns=8),
    )

    result = session.run(_snapshot(include_history=False))

    assert isinstance(result, HypothesisResearchFinalized)
    assert result.hypothesis.hypothesis_text == selected_text
    reasons = [
        item.get("reason") for item in session._budget.results if not item.get("ok")
    ]
    assert reasons == [
        "candidate_slot_not_staged",
        "candidate_slots_incomplete",
        "candidate_slot_not_staged",
        "candidate_selection_invalid",
    ]


def test_k2_invalid_candidate_payloads_do_not_replay_rejected_bodies() -> None:
    bool_slot_sentinel = "K2_BOOL_SLOT_BODY_MUST_NOT_REPLAY"
    invalid_body_sentinel = "K2_INVALID_BODY_MUST_NOT_REPLAY"
    missing_basis = _stage(1, _candidate("unused"))
    del missing_basis["research_basis"]
    session, client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            _stage(True, _candidate(bool_slot_sentinel)),
            missing_basis,
            _stage(
                1,
                {"hypothesis_text": invalid_body_sentinel},
                _basis("source-0001"),
            ),
            _stage(1, _candidate("K2_VALID_AFTER_INVALID")),
            _stage(2, _candidate("K2_SECOND_AFTER_INVALID")),
            _select(1),
        ],
        limits=_limits(max_turns=7),
    )

    result = session.run(_snapshot(include_history=False))

    assert isinstance(result, HypothesisResearchFinalized)
    reasons = [
        item.get("reason") for item in session._budget.results if not item.get("ok")
    ]
    assert reasons == [
        "candidate_payload_invalid",
        "candidate_payload_invalid",
        "hypothesis_invalid",
    ]
    assert bool_slot_sentinel not in client.calls[2]["system_text"]
    assert invalid_body_sentinel not in client.calls[4]["system_text"]
    assert bool_slot_sentinel not in json.dumps(session._budget.results)
    assert invalid_body_sentinel not in json.dumps(session._budget.results)


def test_k2_read_search_turn_and_transcript_accounting_never_reset_per_slot() -> None:
    session, client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            {"action": "search_source", "query": "return value"},
            _stage(1, _candidate("K2_SHARED_BUDGET_ONE")),
            {"action": "read_source", "ref": "source-0001"},
            {"action": "search_source", "query": "return value"},
            _stage(2, _candidate("K2_SHARED_BUDGET_TWO")),
            _select(2),
        ],
        limits=_limits(
            max_turns=7,
            max_read_calls=1,
            max_search_calls=1,
        ),
    )

    result = session.run(_snapshot(include_history=False))

    assert isinstance(result, HypothesisResearchFinalized)
    assert session.provider_calls_used == 7
    assert session._budget.read_calls == 1
    assert session._budget.search_calls == 1
    assert [
        item.get("reason") for item in session._budget.results if not item.get("ok")
    ] == ["read_call_cap_exhausted", "search_call_cap_exhausted"]
    prompt_chars = sum(
        len(
            bounded_json(
                {
                    "system_blocks": call["system_blocks"],
                    "user_prompt": call["prompt"],
                    "provider_tool": call["tool"],
                }
            )
        )
        for call in client.calls
    )
    assert session._budget.transcript_chars > prompt_chars


@pytest.mark.parametrize(
    ("include_history", "clear_sources", "max_turns"),
    (
        (False, True, 2),
        (False, False, 3),
        (True, False, 4),
    ),
)
def test_k2_minimum_turns_fail_before_provider(
    include_history: bool,
    clear_sources: bool,
    max_turns: int,
) -> None:
    context = _context(include_history=include_history)
    if clear_sources:
        context["champion_operators_code"] = ""
        context["existing_target_files"] = []
    session, client = _run([], limits=_limits(max_turns=max_turns))

    with pytest.raises(HypothesisResearchContextError, match="max_turns"):
        session.run(build_prompt_turn_snapshot("hypothesis", context))

    assert session.provider_calls_used == 0
    assert client.calls == []


def test_k2_global_provider_cap_rejects_without_export_or_extra_count() -> None:
    budget = ProviderCallBudget(2)
    session, client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            _stage(1, _candidate("K2_CAP_SLOT_ONE")),
            _stage(2, _candidate("K2_CAP_SLOT_TWO")),
        ],
        limits=_limits(max_turns=4),
        budget=budget,
    )

    with pytest.raises(ProviderCallCapExhausted):
        session.run(_snapshot(include_history=False))

    assert session.provider_calls_used == 2
    assert len(client.calls) == 2
    assert budget.snapshot().budget_admitted == 2


def test_k2_interrupt_after_staging_exports_nothing_and_counts_dispatch() -> None:
    budget = ProviderCallBudget(8)
    session, client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            _stage(1, _candidate("K2_INTERRUPT_SLOT_ONE")),
            KeyboardInterrupt("synthetic K2 interrupt"),
        ],
        limits=_limits(max_turns=4),
        budget=budget,
    )

    with pytest.raises(KeyboardInterrupt, match="synthetic K2 interrupt"):
        session.run(_snapshot(include_history=False))

    assert session.provider_calls_used == 3
    assert len(client.calls) == 3
    assert budget.snapshot().budget_admitted == 3


def test_k2_turn_exhaustion_without_selection_exports_nothing() -> None:
    session, _client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            _stage(1, _candidate("K2_UNSELECTED_ONE")),
            _stage(2, _candidate("K2_UNSELECTED_TWO")),
            {"action": "search_source", "query": "no such text"},
        ],
        limits=_limits(max_turns=4),
    )

    with pytest.raises(ProposalValidationError, match="turn cap exhausted"):
        session.run(_snapshot(include_history=False))

    assert session.provider_calls_used == 4


def test_k2_rejects_legacy_finalize_without_export() -> None:
    session, _client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            {
                "action": "finalize_hypothesis",
                "hypothesis": _candidate("K2_FINALIZE_BYPASS_MUST_NOT_EXPORT"),
                "research_basis": _basis("source-0001"),
            },
        ],
        limits=_limits(max_turns=4),
    )

    with pytest.raises(ProposalValidationError, match="action must be"):
        session.run(_snapshot(include_history=False))

    assert session.provider_calls_used == 2


def test_k2_abstain_after_two_slots_returns_no_hypothesis() -> None:
    session, _client = _run(
        [
            {"action": "read_source", "ref": "source-0001"},
            _stage(1, _candidate("K2_ABSTAIN_ONE")),
            _stage(2, _candidate("K2_ABSTAIN_TWO")),
            {"action": "abstain", "reason": "Neither candidate is adequate."},
        ],
        limits=_limits(max_turns=4),
    )

    result = session.run(_snapshot(include_history=False))

    assert result == HypothesisResearchAbstain(reason="Neither candidate is adequate.")
