from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any

import pytest

import scion.postrun.research_effectiveness.comparison as comparison_module
from scion.postrun.research_effectiveness import (
    BLOCK_UNSCORABLE,
    InitialCell,
    LoadedHistoryAvailable,
    MatchedResearchEffectivenessBlock,
    ResearchEffectivenessArmArtifacts,
    calculate_research_effectiveness,
    compare_five_block_research_effectiveness,
)
from scion.postrun.research_effectiveness.comparison import (
    _cross_arm,
    _cross_block_output,
    _EvaluatedBlock,
    _ratio_greater,
    _ratio_not_higher,
)
from scion.postrun.research_effectiveness.endpoints import _evaluate_arm
from scion.postrun.research_effectiveness.models import _ArmEvaluation, _ArmEvidence
from scion.tests.unit.postrun.test_m32_research_effectiveness import (
    _artifacts,
    _attempt,
    _canary_record,
    _expectation,
    _hypothesis,
    _patch,
    _protocol_failure,
    _screening_record,
    _set_canary_category,
)


def _arm(
    record: dict[str, Any],
    *,
    k: int,
    a_cap: int = 1,
    initial_cells: tuple[tuple[InitialCell, ...], ...] | None = None,
) -> ResearchEffectivenessArmArtifacts:
    return _arm_records(
        (record,),
        k=k,
        a_cap=a_cap,
        attempt_rounds=(1,),
        initial_cells=initial_cells,
    )


def _arm_records(
    records: tuple[dict[str, Any], ...],
    *,
    k: int,
    a_cap: int,
    attempt_rounds: tuple[int, ...],
    initial_cells: tuple[tuple[InitialCell, ...], ...] | None = None,
) -> ResearchEffectivenessArmArtifacts:
    expectation = _expectation(a_cap=a_cap, p_cap=10, k=k)
    calls = (
        {"code_research_finalize": 1}
        if k == 1
        else {"hypothesis_research_turn": 3, "code_research_finalize": 1}
    )
    attempts = [
        _attempt(
            round_num,
            calls,
            completed=k,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
        for round_num in attempt_rounds
    ]
    status, summary = _artifacts(
        expectation=expectation,
        records=list(records),
        attempts=attempts,
    )
    return ResearchEffectivenessArmArtifacts(
        status=status,
        summary=summary,
        current_history=records,
        expectation=expectation,
        initial_cells=initial_cells,
    )


def _positive_block(ordinal: int) -> MatchedResearchEffectivenessBlock:
    k1_record = _screening_record(
        hypothesis=_hypothesis(f"k1 loaded hypothesis {ordinal}"),
        patch=_patch(f"def improve():\n    return {ordinal}\n"),
    )
    k2_record = _screening_record(
        hypothesis=_hypothesis(f"k2 novel hypothesis {ordinal}"),
        patch=_patch(f"def improve():\n    return {100 + ordinal}\n"),
    )
    return MatchedResearchEffectivenessBlock(
        k1=_arm(k1_record, k=1),
        k2=_arm(
            k2_record,
            k=2,
            initial_cells=((InitialCell(90.0, 100.0), InitialCell(80.0, 100.0)),),
        ),
        loaded_history=LoadedHistoryAvailable(records=(deepcopy(k1_record),)),
    )


def _positive_blocks() -> tuple[MatchedResearchEffectivenessBlock, ...]:
    return tuple(_positive_block(ordinal) for ordinal in range(1, 6))


def _replace_arm(
    arm: ResearchEffectivenessArmArtifacts,
    **changes: Any,
) -> ResearchEffectivenessArmArtifacts:
    return replace(arm, **changes)


def _replace_block(
    block: MatchedResearchEffectivenessBlock,
    **changes: Any,
) -> MatchedResearchEffectivenessBlock:
    return replace(block, **changes)


def _assert_no_published_conditions(result: dict[str, Any]) -> None:
    assert result["status"] == "inconclusive"
    for sign in result["block_signs"]:
        assert sign["endpoint_conditions_satisfied"] is None
        assert all(value is None for value in sign["conditions"].values())
    cross = result["cross_block"]
    assert cross["status"] == "UNAVAILABLE"
    assert cross["endpoint_conditions_satisfied"] is None
    assert all(value is None for value in cross["conditions"].values())
    for arm in (cross["k1"], cross["k2"]):
        assert all(value is None for value in arm.values())


def _private_evaluation(
    *,
    h_keys: tuple[tuple[Any, ...], ...] = (),
    pair_keys: tuple[tuple[Any, ...], ...] = (),
    f_pair_keys: tuple[tuple[Any, ...], ...] = (),
    a_cap: int = 1,
) -> _ArmEvaluation:
    return _ArmEvaluation(
        report={"physical": {"a_cap": a_cap}},
        evidence=_ArmEvidence(
            exported_h_keys=h_keys,
            pair_keys=pair_keys,
            f_pair_keys=f_pair_keys,
        ),
    )


def test_exact_five_block_positive_endpoint_conditions() -> None:
    result = compare_five_block_research_effectiveness(blocks=_positive_blocks())

    assert result["status"] == "endpoint_conditions_satisfied"
    assert result["counts"] == {
        "blocks_total": 5,
        "blocks_scoreable": 5,
        "blocks_inconclusive": 0,
        "blocks_unscorable": 0,
        "endpoint_conditions_satisfied": 5,
    }
    assert all(sign["endpoint_conditions_satisfied"] for sign in result["block_signs"])
    assert result["cross_block"]["status"] == "AVAILABLE"
    assert result["cross_block"]["k1"]["u_f"] == 0
    assert result["cross_block"]["k2"]["u_f"] == 5
    assert result["cross_block"]["endpoint_conditions_satisfied"] is True


def test_scoreable_k2_infeasibility_is_a_negative_not_inconclusive() -> None:
    blocks = list(_positive_blocks())
    block = blocks[0]
    summary = deepcopy(block.k2.summary)
    summary["steps"][0]["protocol_result"][
        "candidate_attributable_infeasible_pairs"
    ] = 1
    blocks[0] = MatchedResearchEffectivenessBlock(
        k1=block.k1,
        k2=ResearchEffectivenessArmArtifacts(
            status=block.k2.status,
            summary=summary,
            current_history=block.k2.current_history,
            expectation=block.k2.expectation,
            initial_cells=block.k2.initial_cells,
        ),
        loaded_history=block.loaded_history,
    )

    result = compare_five_block_research_effectiveness(blocks=tuple(blocks))

    assert result["status"] == "endpoint_conditions_not_satisfied"
    assert result["block_signs"][0]["status"] == "SCOREABLE"
    assert result["block_signs"][0]["conditions"]["k2_infeasibility_zero"] is False
    assert result["cross_block"]["status"] == "AVAILABLE"


@pytest.mark.parametrize(
    ("mutation", "error_code"),
    (
        ("list", "FIVE_BLOCK_INPUT_INVALID"),
        ("length", "FIVE_BLOCK_INPUT_INVALID"),
        ("k", "MATCHED_BLOCK_K_INVALID"),
        ("expectation", "MATCHED_BLOCK_EXPECTATION_MISMATCH"),
        ("problem", "FIVE_BLOCK_PROBLEM_MISMATCH"),
    ),
)
def test_comparator_rejects_nonexact_or_unmatched_inputs(
    mutation: str,
    error_code: str,
) -> None:
    blocks: Any = _positive_blocks()
    if mutation == "list":
        blocks = list(blocks)
    elif mutation == "length":
        blocks = blocks[:4]
    else:
        changed = list(blocks)
        block = changed[-1]
        if mutation == "k":
            expectation = replace(block.k1.expectation, max_hypothesis_candidates=2)
            changed[-1] = _replace_block(
                block,
                k1=_replace_arm(block.k1, expectation=expectation),
            )
        elif mutation == "expectation":
            expectation = replace(block.k2.expectation, a_cap=2)
            changed[-1] = _replace_block(
                block,
                k2=_replace_arm(block.k2, expectation=expectation),
            )
        else:
            k1_expectation = replace(block.k1.expectation, problem_id="other")
            k2_expectation = replace(block.k2.expectation, problem_id="other")
            changed[-1] = _replace_block(
                block,
                k1=_replace_arm(block.k1, expectation=k1_expectation),
                k2=_replace_arm(block.k2, expectation=k2_expectation),
            )
        blocks = tuple(changed)

    with pytest.raises(ValueError, match=f"^{error_code}$"):
        compare_five_block_research_effectiveness(blocks=blocks)


def test_public_carriers_and_private_evidence_have_body_free_repr() -> None:
    block = _positive_block(73)
    secret = "k2 novel hypothesis 73"

    assert repr(block.k2) == "ResearchEffectivenessArmArtifacts(<redacted>)"
    assert repr(block) == "MatchedResearchEffectivenessBlock(<redacted>)"
    private = _evaluate_arm(
        status=block.k2.status,
        summary=block.k2.summary,
        current_history=block.k2.current_history,
        loaded_history=block.loaded_history,
        expectation=block.k2.expectation,
        initial_cells=block.k2.initial_cells,
    )
    assert repr(private) == "_ArmEvaluation(<redacted>)"
    assert secret not in repr((block.k2, block, private))


def test_public_single_arm_wrapper_matches_private_oracle_and_f_evidence() -> None:
    block = _positive_block(1)
    public = calculate_research_effectiveness(
        status=block.k2.status,
        summary=block.k2.summary,
        current_history=block.k2.current_history,
        loaded_history=block.loaded_history,
        expectation=block.k2.expectation,
        initial_cells=block.k2.initial_cells,
    )
    private = _evaluate_arm(
        status=block.k2.status,
        summary=block.k2.summary,
        current_history=block.k2.current_history,
        loaded_history=block.loaded_history,
        expectation=block.k2.expectation,
        initial_cells=block.k2.initial_cells,
    )

    assert public == private.report
    assert private.evidence.f_pair_keys is not None
    assert len(private.evidence.f_pair_keys) == public["adjusted"]["f"]


def test_comparator_calls_the_single_arm_oracle_exactly_once_per_arm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    original = comparison_module._evaluate_arm

    def counted(**arguments: Any):
        nonlocal calls
        calls += 1
        return original(**arguments)

    monkeypatch.setattr(comparison_module, "_evaluate_arm", counted)

    compare_five_block_research_effectiveness(blocks=_positive_blocks())

    assert calls == 10


@pytest.mark.parametrize("mutation", ("feasibility", "effect", "incomplete"))
def test_any_partial_or_incomplete_arm_nulls_all_conditions_and_cross(
    mutation: str,
) -> None:
    blocks = list(_positive_blocks())
    block = blocks[0]
    if mutation == "feasibility":
        summary = deepcopy(block.k1.summary)
        del summary["steps"][0]["protocol_result"][
            "candidate_attributable_infeasible_pairs"
        ]
        k1 = _replace_arm(block.k1, summary=summary)
    elif mutation == "effect":
        k1 = _replace_arm(block.k2, initial_cells=None)
        block = _replace_block(block, k2=k1)
        blocks[0] = block
        result = compare_five_block_research_effectiveness(blocks=tuple(blocks))
        _assert_no_published_conditions(result)
        return
    else:
        status = deepcopy(block.k1.status)
        summary = deepcopy(block.k1.summary)
        status["proposal_runtime"]["attempts"][0]["accounting_state"] = "interrupted"
        summary["proposal_runtime"]["attempts"][0]["accounting_state"] = "interrupted"
        k1 = _replace_arm(block.k1, status=status, summary=summary)
    blocks[0] = _replace_block(block, k1=k1)

    result = compare_five_block_research_effectiveness(blocks=tuple(blocks))

    _assert_no_published_conditions(result)


def test_partial_early_arm_does_not_hide_later_malformed_arm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocks = list(_positive_blocks())
    first = blocks[0]
    first_summary = deepcopy(first.k1.summary)
    del first_summary["steps"][0]["protocol_result"][
        "candidate_attributable_infeasible_pairs"
    ]
    blocks[0] = _replace_block(
        first,
        k1=_replace_arm(first.k1, summary=first_summary),
    )
    last = blocks[-1]
    last_summary = deepcopy(last.k2.summary)
    last_summary["proposal_runtime"]["provider_calls"]["budget_admitted"] = (
        "sensitive malformed body"
    )
    blocks[-1] = _replace_block(
        last,
        k2=_replace_arm(last.k2, summary=last_summary),
    )
    calls = 0
    original = comparison_module._evaluate_arm

    def counted(**arguments: Any):
        nonlocal calls
        calls += 1
        return original(**arguments)

    monkeypatch.setattr(comparison_module, "_evaluate_arm", counted)

    with pytest.raises(ValueError) as error:
        compare_five_block_research_effectiveness(blocks=tuple(blocks))

    assert calls == 10
    assert "sensitive malformed body" not in str(error.value)


@pytest.mark.parametrize(
    ("candidate", "champion", "shared", "bilateral"),
    (
        (0, 1, 0, 0),
        (0, 1, 1, 0),
        (1, 1, 0, 1),
    ),
)
@pytest.mark.parametrize("feasibility_partial", (False, True))
def test_protocol_reference_failures_are_block_unscorable_even_if_partial(
    candidate: int,
    champion: int,
    shared: int,
    bilateral: int,
    feasibility_partial: bool,
) -> None:
    blocks = list(_positive_blocks())
    base = blocks[0]
    record = _protocol_failure(
        _screening_record(
            hypothesis=_hypothesis("protocol reference failure"),
            patch=_patch("def improve():\n    return -1\n"),
        ),
        candidate=candidate,
        champion=champion,
        shared=shared,
        bilateral=bilateral,
    )
    k1 = _arm(record, k=1)
    if feasibility_partial:
        summary = deepcopy(k1.summary)
        del summary["steps"][0]["protocol_result"][
            "candidate_attributable_infeasible_pairs"
        ]
        k1 = _replace_arm(k1, summary=summary)
    blocks[0] = _replace_block(
        base,
        k1=k1,
        loaded_history=LoadedHistoryAvailable(records=(deepcopy(record),)),
    )

    result = compare_five_block_research_effectiveness(blocks=tuple(blocks))

    assert result["block_signs"][0]["status"] == BLOCK_UNSCORABLE
    assert result["counts"]["blocks_unscorable"] == 1
    _assert_no_published_conditions(result)


@pytest.mark.parametrize(
    "canary_code",
    (
        "CANARY_CHAMPION_FAILURE",
        "CANARY_SHARED_FAILURE",
        "CANARY_BILATERAL_FAILURE",
    ),
)
@pytest.mark.parametrize("shape", ("initial", "expanded"))
def test_complete_pair_canary_reference_failures_are_block_unscorable(
    canary_code: str,
    shape: str,
) -> None:
    blocks = list(_positive_blocks())
    base = blocks[0]
    initial = _screening_record(
        hypothesis=_hypothesis("canary reference failure"),
        patch=_patch("def improve():\n    return -2\n"),
    )
    canary = _canary_record(
        hypothesis=initial["hypothesis"],
        patch=initial["patch"],
        canary_code=canary_code,
    )
    records = (canary,) if shape == "initial" else (initial, canary)
    k1 = _arm_records(records, k=1, a_cap=1, attempt_rounds=(1,))
    status = deepcopy(k1.status)
    summary = deepcopy(k1.summary)
    step_index = len(records) - 1
    if shape == "expanded":
        summary["steps"][step_index]["execution_outcome"]["provenance"]["stage"] = (
            "screening"
        )
        for artifact in (status, summary):
            artifact["run_result"]["last_execution_outcome"]["stage"] = "screening"
    _set_canary_category(
        status,
        summary,
        step_index=step_index,
        category="incomplete_evidence",
    )
    k1 = _replace_arm(k1, status=status, summary=summary)
    blocks[0] = _replace_block(base, k1=k1)

    result = compare_five_block_research_effectiveness(blocks=tuple(blocks))

    assert result["block_signs"][0]["status"] == BLOCK_UNSCORABLE
    _assert_no_published_conditions(result)


def test_candidate_failure_is_not_an_absolute_reference_guard() -> None:
    blocks = list(_positive_blocks())
    base = blocks[0]
    record = _protocol_failure(
        _screening_record(
            hypothesis=_hypothesis("candidate-only failure"),
            patch=_patch("def improve():\n    return -3\n"),
        ),
        candidate=1,
        champion=0,
    )
    blocks[0] = _replace_block(
        base,
        k1=_arm(record, k=1),
        loaded_history=LoadedHistoryAvailable(records=(deepcopy(record),)),
    )

    result = compare_five_block_research_effectiveness(blocks=tuple(blocks))

    assert result["block_signs"][0]["status"] == "SCOREABLE"
    assert (
        result["block_signs"][0]["conditions"]["reference_failure_classes_zero"] is True
    )


def test_k1_infeasibility_and_protected_regression_do_not_apply_k2_zero_guards() -> (
    None
):
    blocks = list(_positive_blocks())
    base = blocks[0]
    record = _protocol_failure(
        _screening_record(
            hypothesis=_hypothesis("k1 protected direction"),
            patch=_patch("def improve():\n    return -4\n"),
        ),
        candidate=0,
        champion=0,
        protected=True,
    )
    k1 = _arm(record, k=1)
    summary = deepcopy(k1.summary)
    summary["steps"][0]["protocol_result"][
        "candidate_attributable_infeasible_pairs"
    ] = 1
    blocks[0] = _replace_block(
        base,
        k1=_replace_arm(k1, summary=summary),
        loaded_history=LoadedHistoryAvailable(records=(deepcopy(record),)),
    )

    result = compare_five_block_research_effectiveness(blocks=tuple(blocks))

    assert result["status"] == "endpoint_conditions_satisfied"
    assert result["block_signs"][0]["conditions"]["k2_infeasibility_zero"] is True
    assert (
        result["block_signs"][0]["conditions"]["k2_protected_regression_zero"] is True
    )


def test_one_k2_protected_regression_is_a_scoreable_four_of_five_negative() -> None:
    blocks = list(_positive_blocks())
    base = blocks[0]
    record = _protocol_failure(
        _screening_record(
            hypothesis=_hypothesis("k2 protected direction"),
            patch=_patch("def improve():\n    return -5\n"),
        ),
        candidate=0,
        champion=0,
        protected=True,
    )
    blocks[0] = _replace_block(base, k2=_arm(record, k=2))

    result = compare_five_block_research_effectiveness(blocks=tuple(blocks))

    assert result["status"] == "endpoint_conditions_not_satisfied"
    assert result["counts"]["endpoint_conditions_satisfied"] == 4
    assert result["block_signs"][0]["status"] == "SCOREABLE"
    assert (
        result["block_signs"][0]["conditions"]["k2_protected_regression_zero"] is False
    )


def test_one_f_tie_is_not_pooled_away_by_four_positive_blocks() -> None:
    blocks = list(_positive_blocks())
    block = blocks[0]
    blocks[0] = _replace_block(
        block,
        loaded_history=LoadedHistoryAvailable(
            records=(
                deepcopy(block.k1.current_history[0]),
                deepcopy(block.k2.current_history[0]),
            )
        ),
    )

    result = compare_five_block_research_effectiveness(blocks=tuple(blocks))

    assert result["status"] == "endpoint_conditions_not_satisfied"
    assert result["counts"]["endpoint_conditions_satisfied"] == 4
    assert result["block_signs"][0]["conditions"]["f_higher"] is False
    assert all(
        sign["endpoint_conditions_satisfied"] for sign in result["block_signs"][1:]
    )


def test_rational_guards_ignore_supplied_float_values() -> None:
    one_third_with_false_float = {
        "numerator": 1,
        "denominator": 3,
        "value": 999.0,
        "status": "FINITE",
    }
    one_half_with_false_float = {
        "numerator": 1,
        "denominator": 2,
        "value": -999.0,
        "status": "FINITE",
    }
    frozen_zero = {
        "numerator": 0,
        "denominator": 0,
        "value": 123.0,
        "status": "DEFINED_ZERO_PROVIDER_DENOMINATOR",
    }

    assert not _ratio_greater(one_third_with_false_float, one_half_with_false_float)
    assert _ratio_not_higher(one_third_with_false_float, one_half_with_false_float)
    assert _ratio_greater(one_third_with_false_float, frozen_zero)


def test_cross_replay_updates_seen_only_after_the_current_block() -> None:
    h_key = ("exact-h",)
    pair_key = (h_key, (("private.py", "modify", "private source"),))
    evaluations = (
        _private_evaluation(
            h_keys=(h_key, h_key),
            pair_keys=(pair_key, pair_key),
            f_pair_keys=(pair_key,),
        ),
        _private_evaluation(
            h_keys=(h_key, h_key),
            pair_keys=(pair_key, pair_key),
            f_pair_keys=(pair_key,),
        ),
        _private_evaluation(),
        _private_evaluation(),
        _private_evaluation(),
    )

    result = _cross_arm(evaluations)

    assert result["h_replays"] == 2
    assert result["pair_replays"] == 2
    assert result["h_replay_rate"]["denominator"] == 5
    assert result["u_f"] == 1


def test_cross_u_f_uses_only_f_pairs_not_distinct_non_f_pairs() -> None:
    h_a = ("h-a",)
    h_b = ("h-b",)
    pair_a = (h_a, (("a.py", "modify", "source a"),))
    pair_b = (h_b, (("b.py", "modify", "source b"),))
    evaluations = (
        _private_evaluation(
            h_keys=(h_a, h_b),
            pair_keys=(pair_a, pair_b),
            f_pair_keys=(pair_a,),
        ),
        _private_evaluation(),
        _private_evaluation(),
        _private_evaluation(),
        _private_evaluation(),
    )

    result = _cross_arm(evaluations)

    assert result["u_f"] == 1


def test_cross_replay_sets_are_isolated_between_k1_and_k2() -> None:
    h_key = ("opposing-arm-h",)
    pair_key = (h_key, (("private.py", "modify", "private source"),))
    empty = _private_evaluation()
    k1_values = (
        _private_evaluation(h_keys=(h_key,), pair_keys=(pair_key,)),
        empty,
        empty,
        empty,
        empty,
    )
    k2_values = (
        empty,
        _private_evaluation(
            h_keys=(h_key,),
            pair_keys=(pair_key,),
            f_pair_keys=(pair_key,),
        ),
        empty,
        empty,
        empty,
    )
    evaluated = tuple(
        _EvaluatedBlock(source=source, k1=k1, k2=k2)
        for source, k1, k2 in zip(_positive_blocks(), k1_values, k2_values)
    )

    result = _cross_block_output(evaluated)

    assert result["k1"]["h_replays"] == 0
    assert result["k2"]["h_replays"] == 0
    assert result["k1"]["pair_replays"] == 0
    assert result["k2"]["pair_replays"] == 0
    assert result["k1"]["u_f"] == 0
    assert result["k2"]["u_f"] == 1


def test_global_cross_replay_failure_does_not_rewrite_positive_block_signs() -> None:
    blocks = list(_positive_blocks())
    blocks[1] = _replace_block(blocks[1], k2=blocks[0].k2)

    result = compare_five_block_research_effectiveness(blocks=tuple(blocks))

    assert all(sign["endpoint_conditions_satisfied"] for sign in result["block_signs"])
    assert result["cross_block"]["k1"]["h_replays"] == 0
    assert result["cross_block"]["k2"]["h_replays"] == 1
    assert result["cross_block"]["conditions"]["h_replay_not_higher"] is False
    assert result["status"] == "endpoint_conditions_not_satisfied"


def test_expanded_rows_do_not_duplicate_private_cross_evidence() -> None:
    initial = _screening_record(
        hypothesis=_hypothesis("one origin with expansion"),
        patch=_patch("def improve():\n    return 909\n"),
    )
    expanded = _screening_record(
        hypothesis=initial["hypothesis"],
        patch=initial["patch"],
        gate="fail",
        decision="continue_explore",
    )
    arm = _arm_records(
        (initial, expanded),
        k=2,
        a_cap=1,
        attempt_rounds=(1,),
        initial_cells=((InitialCell(90.0, 100.0), InitialCell(80.0, 100.0)),),
    )

    evaluation = _evaluate_arm(
        status=arm.status,
        summary=arm.summary,
        current_history=arm.current_history,
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=arm.expectation,
        initial_cells=arm.initial_cells,
    )

    assert len(evaluation.evidence.exported_h_keys) == 1
    assert len(evaluation.evidence.pair_keys) == 1
    assert evaluation.evidence.f_pair_keys is not None
    assert len(evaluation.evidence.f_pair_keys) == 1


def test_comparison_output_is_detached_and_recursively_identity_free() -> None:
    blocks = _positive_blocks()
    result = compare_five_block_research_effectiveness(blocks=blocks)
    frozen_result = deepcopy(result)
    secret_values = (
        "k2 novel hypothesis 1",
        "operators/local_search.py",
        "def improve():",
    )
    forbidden_key_parts = {
        "hypothesis",
        "patch",
        "path",
        "source",
        "case",
        "seed",
        "reason",
        "hash",
        "digest",
        "id",
        "label",
        "token",
        "go",
    }

    blocks[0].k2.summary["steps"][0]["hypothesis"]["text"] = "mutated"
    assert result == frozen_result
    assert set(result) == {
        "schema_version",
        "status",
        "block_signs",
        "counts",
        "cross_block",
    }

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                assert not (set(key.casefold().split("_")) & forbidden_key_parts)
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)
        elif isinstance(value, str):
            assert all(secret not in value for secret in secret_values)
            assert value.casefold() not in {"go", "qualified", "advance"}

    visit(result)


def test_public_carriers_reject_nonexact_tuple_shapes() -> None:
    block = _positive_block(1)

    with pytest.raises(ValueError, match="^ARM_CURRENT_HISTORY_MUST_BE_A_TUPLE$"):
        _replace_arm(block.k1, current_history=list(block.k1.current_history))
    with pytest.raises(ValueError, match="^ARM_INITIAL_CELLS_MUST_BE_TUPLES$"):
        _replace_arm(block.k2, initial_cells=list(block.k2.initial_cells or ()))
