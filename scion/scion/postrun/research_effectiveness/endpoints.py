"""Pure M32 research-effectiveness endpoint calculation."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from .models import (
    BLOCK_UNSCORABLE,
    HISTORY_REPLAY_BASIS_UNAVAILABLE,
    INITIAL_CELL_DATA_UNAVAILABLE,
    SCIENTIFIC_DELEGATION_INCOMPLETE,
    InitialCell,
    LoadedHistoryAvailable,
    LoadedHistoryUnavailable,
    ResearchEffectivenessExpectation,
    _as_mapping,
    _fail,
    _h_key,
    _history_decision,
    _JoinedRow,
    _OriginQuality,
    _patch_key,
    _Physical,
)
from .validation import (
    _normalize_history,
    _parse_physical,
    _validate_terminal_twins,
)


def calculate_research_effectiveness(
    *,
    status: Mapping[str, Any],
    summary: Mapping[str, Any],
    current_history: Sequence[Mapping[str, Any]],
    loaded_history: LoadedHistoryAvailable | LoadedHistoryUnavailable,
    expectation: ResearchEffectivenessExpectation,
    initial_cells: Sequence[Sequence[InitialCell]] | None = None,
) -> dict[str, Any]:
    """Calculate one M32 arm report without external reads or side effects."""

    if not isinstance(expectation, ResearchEffectivenessExpectation):
        _fail("INVALID_EXPECTATION_TYPE")
    status_map = _as_mapping(status, "STATUS_NOT_A_MAPPING")
    summary_map = _as_mapping(summary, "SUMMARY_NOT_A_MAPPING")
    _validate_terminal_twins(status_map, summary_map, expectation)
    histories = _normalize_history(
        current_history,
        expectation=expectation,
        code="CURRENT_HISTORY_INVALID",
    )
    physical = _parse_physical(status_map, summary_map, histories, expectation)
    physical_output = _physical_output(physical, expectation)

    limitations: list[str] = []
    loaded: tuple[dict[str, Any], ...] | None
    if isinstance(loaded_history, LoadedHistoryUnavailable):
        loaded = None
        limitations.append(HISTORY_REPLAY_BASIS_UNAVAILABLE)
    elif isinstance(loaded_history, LoadedHistoryAvailable):
        loaded = _normalize_history(
            loaded_history.records,
            expectation=expectation,
            code="LOADED_HISTORY_INVALID",
        )
    else:
        _fail("INVALID_LOADED_HISTORY_TYPE")
    if physical.incomplete:
        limitations.insert(0, "RUN_INCOMPLETE")
    if limitations:
        return _report(
            incomplete=physical.incomplete,
            limitations=limitations,
            physical=physical_output,
            adjusted=_blank_adjusted(),
        )
    assert loaded is not None
    adjusted, limitation = _adjusted_output(
        physical,
        loaded,
        expectation,
        initial_cells,
    )
    if limitation is not None:
        limitations.append(limitation)
    return _report(
        incomplete=False,
        limitations=limitations,
        physical=physical_output,
        adjusted=adjusted,
    )


def _physical_output(
    physical: _Physical,
    expectation: ResearchEffectivenessExpectation,
) -> dict[str, Any]:
    h = sum(attempt.hypotheses_exported for attempt in physical.attempts)
    c_ready = sum(attempt.code_candidates_ready for attempt in physical.attempts)
    formal = len(physical.initial_rows)
    expand_progressions = sum(
        row.protocol is not None
        and row.protocol.gate_outcome == "expand"
        and _history_decision(row.history) == "expand_screening"
        for row in physical.initial_rows
    )
    quality = tuple(_origin_quality_by_round(physical.rows).values())
    within_h_replays, within_pair_replays, candidate_only = _current_guard_counts(
        physical.rows
    )
    return {
        "a_cap": expectation.a_cap,
        "a_used": len(physical.attempts),
        "p_cap": expectation.p_cap,
        "p_charged": physical.p_charged,
        "provider_calls_by_request_kind": dict(physical.aggregate_by_kind),
        "hypothesis_candidates_completed": sum(
            attempt.hypothesis_candidates_completed for attempt in physical.attempts
        ),
        "hypothesis_candidates_selected": sum(
            attempt.hypothesis_candidates_selected for attempt in physical.attempts
        ),
        "h": h,
        "patches_completed": sum(
            attempt.patches_completed for attempt in physical.attempts
        ),
        "c_ready": c_ready,
        "initial_protocol_dispatches": formal,
        "initial_expand_progressions": expand_progressions,
        "candidate_failure_candidates": sum(item.candidate_failure for item in quality),
        "champion_failure_candidates": sum(item.champion_failure for item in quality),
        "shared_failure_candidates": sum(item.shared_failure for item in quality),
        "bilateral_failure_candidates": sum(item.bilateral_failure for item in quality),
        "protected_regression_candidates": sum(
            item.protected_regression for item in quality
        ),
        "candidate_only_failure_candidates": candidate_only,
        "within_block_h_replays": within_h_replays,
        "within_block_pair_replays": within_pair_replays,
        "formal_per_used_attempt": _ratio(formal, len(physical.attempts)),
        "formal_per_charged_provider_call": _ratio(
            formal, physical.p_charged, zero_status="ZERO_PROVIDER_DENOMINATOR"
        ),
        "formal_per_a_cap": _ratio(formal, expectation.a_cap),
        "formal_per_p_cap": _ratio(formal, expectation.p_cap),
        "h_productivity": _ratio(
            h,
            physical.p_charged,
            zero_status="ZERO_PROVIDER_DENOMINATOR",
        ),
        "c_readiness": _ratio(c_ready, max(h, 1)),
        "initial_quality": _ratio(expand_progressions, formal),
        "within_block_h_replay_rate": _ratio(within_h_replays, expectation.a_cap),
        "within_block_pair_replay_rate": _ratio(within_pair_replays, expectation.a_cap),
        "candidate_only_failure_rate": _ratio(candidate_only, expectation.a_cap),
    }


def _adjusted_output(
    physical: _Physical,
    loaded: tuple[dict[str, Any], ...],
    expectation: ResearchEffectivenessExpectation,
    initial_cells: Sequence[Sequence[InitialCell]] | None,
) -> tuple[dict[str, Any], str | None]:
    loaded_h = {
        key for record in loaded if (key := _h_key(record["hypothesis"])) is not None
    }
    loaded_pairs = {
        (h_key, patch_key)
        for record in loaded
        if (h_key := _h_key(record["hypothesis"])) is not None
        and (patch_key := _patch_key(record["patch"])) is not None
    }
    seen_h: set[tuple[Any, ...]] = set()
    seen_pairs: set[tuple[tuple[Any, ...], tuple[tuple[str, str, str], ...]]] = set()
    h_novel_by_round: dict[int, bool] = {}
    pair_novel_by_round: dict[int, bool] = {}
    loaded_h_replays = 0
    within_h_replays = 0
    loaded_pair_replays = 0
    within_pair_replays = 0
    for row in physical.rows:
        if row.attempt is None:
            continue
        round_num = row.attempt.round_num
        if row.h_key is not None:
            loaded_hit = row.h_key in loaded_h
            within_hit = row.h_key in seen_h
            loaded_h_replays += loaded_hit
            within_h_replays += within_hit
            h_novel_by_round[round_num] = not loaded_hit and not within_hit
            seen_h.add(row.h_key)
        if row.h_key is not None and row.patch_key is not None:
            pair = (row.h_key, row.patch_key)
            loaded_hit = pair in loaded_pairs
            within_hit = pair in seen_pairs
            loaded_pair_replays += loaded_hit
            within_pair_replays += within_hit
            pair_novel_by_round[round_num] = not loaded_hit and not within_hit
            seen_pairs.add(pair)

    d_h = sum(h_novel_by_round.values())
    f_rows = tuple(
        row
        for row in physical.initial_rows
        if row.attempt is not None
        and h_novel_by_round.get(row.attempt.round_num, False)
        and pair_novel_by_round.get(row.attempt.round_num, False)
    )
    f = len(f_rows)
    quality_by_round = _origin_quality_by_round(physical.rows)
    g = sum(
        _is_g_candidate(
            row,
            expectation,
            quality_by_round[row.attempt.round_num],
        )
        for row in f_rows
        if row.attempt is not None
    )
    _physical_h_replays, _physical_pair_replays, candidate_only = _current_guard_counts(
        physical.rows
    )
    e_value, limitation = _effect_value(
        physical.initial_rows,
        f_rows,
        expectation,
        initial_cells,
        quality_by_round,
    )
    h = sum(attempt.hypotheses_exported for attempt in physical.attempts)
    c_ready = sum(attempt.code_candidates_ready for attempt in physical.attempts)
    adjusted = {
        "d_h": d_h,
        "f": f,
        "g": g,
        "t": _throughput_ratio(f, physical.p_charged),
        "f_per_p_cap": _ratio(f, expectation.p_cap),
        "f_per_a_cap": _ratio(f, expectation.a_cap),
        "h_productivity": _ratio(
            h,
            physical.p_charged,
            zero_status="ZERO_PROVIDER_DENOMINATOR",
        ),
        "d_h_per_a_cap": _ratio(d_h, expectation.a_cap),
        "c_readiness": _ratio(c_ready, max(h, 1)),
        "q": _ratio(g, max(f, 1)),
        "g_per_a_cap": _ratio(g, expectation.a_cap),
        "loaded_history_h_replay_rate": _ratio(loaded_h_replays, expectation.a_cap),
        "within_block_h_replay_rate": _ratio(within_h_replays, expectation.a_cap),
        "loaded_history_pair_replay_rate": _ratio(
            loaded_pair_replays, expectation.a_cap
        ),
        "within_block_pair_replay_rate": _ratio(within_pair_replays, expectation.a_cap),
        "candidate_only_failure_rate": _ratio(candidate_only, expectation.a_cap),
        "e": e_value,
    }
    return adjusted, limitation


def _effect_value(
    initial_rows: tuple[_JoinedRow, ...],
    f_rows: tuple[_JoinedRow, ...],
    expectation: ResearchEffectivenessExpectation,
    initial_cells: Sequence[Sequence[InitialCell]] | None,
    quality_by_round: Mapping[int, _OriginQuality],
) -> tuple[dict[str, Any], str | None]:
    if not f_rows:
        return _positive_infinity(), None
    outer = _initial_cell_outer(initial_cells)
    if initial_cells is not None and len(outer) != len(initial_rows):
        return _unavailable_effect(), INITIAL_CELL_DATA_UNAVAILABLE
    index_by_round = {
        row.attempt.round_num: index
        for index, row in enumerate(initial_rows)
        if row.attempt is not None
    }
    candidate_medians: list[float] = []
    for row in f_rows:
        assert row.protocol is not None and row.attempt is not None
        candidate_median, limitation = _candidate_effect_median(
            row,
            quality_by_round[row.attempt.round_num],
            expectation,
            outer[index_by_round[row.attempt.round_num]]
            if initial_cells is not None
            else None,
        )
        if limitation is not None:
            return _unavailable_effect(), limitation
        candidate_medians.append(candidate_median)
    effect = _median_with_infinity(candidate_medians)
    if math.isinf(effect):
        return _positive_infinity(), None
    if not math.isfinite(effect):
        return _unavailable_effect(), BLOCK_UNSCORABLE
    return {"status": "FINITE", "value": effect}, None


def _initial_cell_outer(
    initial_cells: Sequence[Sequence[InitialCell]] | None,
) -> Sequence[Sequence[InitialCell]]:
    if initial_cells is None:
        return ()
    if isinstance(initial_cells, (str, bytes, bytearray)) or not isinstance(
        initial_cells, Sequence
    ):
        _fail("INITIAL_CELL_DATA_INVALID")
    return initial_cells


def _candidate_effect_median(
    row: _JoinedRow,
    quality: _OriginQuality,
    expectation: ResearchEffectivenessExpectation,
    cells: Sequence[InitialCell] | None,
) -> tuple[float, str | None]:
    assert row.protocol is not None
    if quality.blocks_quality or not row.protocol.exact_initial_matrix(expectation):
        return math.inf, None
    if cells is None:
        return math.inf, INITIAL_CELL_DATA_UNAVAILABLE
    if isinstance(cells, (str, bytes, bytearray)) or not isinstance(cells, Sequence):
        _fail("INITIAL_CELL_DATA_INVALID")
    if len(cells) != expectation.expected_initial_pair_count:
        return math.inf, INITIAL_CELL_DATA_UNAVAILABLE
    effects: list[float] = []
    for cell in cells:
        effect = _initial_cell_effect(cell)
        if effect is None:
            return math.inf, BLOCK_UNSCORABLE
        effects.append(effect)
    candidate_median = _finite_median(effects)
    if candidate_median is None:
        return math.inf, BLOCK_UNSCORABLE
    return candidate_median, None


def _initial_cell_effect(cell: InitialCell) -> float | None:
    if type(cell) is not InitialCell:
        _fail("INITIAL_CELL_MUST_BE_NAMED")
    candidate = _cell_number(cell.candidate_total_distance)
    b0 = _cell_number(cell.b0_total_distance)
    if candidate is None or b0 is None or b0 <= 0:
        return None
    effect = (candidate - b0) / b0
    return effect if math.isfinite(effect) else None


def _is_g_candidate(
    row: _JoinedRow,
    expectation: ResearchEffectivenessExpectation,
    quality: _OriginQuality,
) -> bool:
    return bool(
        row.protocol is not None
        and row.protocol.exact_initial_matrix(expectation)
        and not quality.blocks_quality
        and row.protocol.gate_outcome == "expand"
        and _history_decision(row.history) == "expand_screening"
    )


def _candidate_only_canary(row: _JoinedRow) -> bool:
    canary = row.summary.get("canary_result")
    return bool(
        isinstance(canary, Mapping)
        and canary.get("passed") is False
        and canary.get("failure_category") == "candidate_failure"
    )


def _current_guard_counts(rows: tuple[_JoinedRow, ...]) -> tuple[int, int, int]:
    seen_h: set[tuple[Any, ...]] = set()
    seen_pairs: set[tuple[tuple[Any, ...], tuple[tuple[str, str, str], ...]]] = set()
    h_replays = 0
    pair_replays = 0
    candidate_only_rounds = _candidate_only_attempt_rounds(rows)
    for row in rows:
        if row.attempt is not None:
            if row.h_key is not None:
                h_replays += row.h_key in seen_h
                seen_h.add(row.h_key)
            if row.h_key is not None and row.patch_key is not None:
                pair = (row.h_key, row.patch_key)
                pair_replays += pair in seen_pairs
                seen_pairs.add(pair)
    return h_replays, pair_replays, len(candidate_only_rounds)


def _candidate_only_attempt_rounds(rows: tuple[_JoinedRow, ...]) -> set[int]:
    return {
        round_num
        for round_num, quality in _origin_quality_by_round(rows).items()
        if quality.candidate_only_failure
    }


def _origin_quality_by_round(
    rows: tuple[_JoinedRow, ...],
) -> dict[int, _OriginQuality]:
    flags_by_round: dict[int, set[str]] = {}
    origin_round: int | None = None
    for row in rows:
        if row.attempt is not None:
            origin_round = row.attempt.round_num
            flags_by_round.setdefault(origin_round, set())
        if origin_round is not None:
            flags_by_round[origin_round].update(_row_quality_flags(row))
    return {
        round_num: _OriginQuality(**{name: True for name in flags})
        for round_num, flags in flags_by_round.items()
    }


def _row_quality_flags(row: _JoinedRow) -> set[str]:
    flags: set[str] = set()
    if row.protocol is not None:
        for field, count in (
            ("candidate_failure", row.protocol.candidate_failed_pairs),
            ("champion_failure", row.protocol.champion_failed_pairs),
            ("shared_failure", row.protocol.shared_failed_pairs),
            ("bilateral_failure", row.protocol.bilateral_failed_pairs),
        ):
            if count:
                flags.add(field)
        if row.protocol.protected_regression:
            flags.add("protected_regression")
        if row.protocol.candidate_only_failure:
            flags.add("candidate_only_failure")
    if _candidate_only_canary(row):
        flags.update(("candidate_failure", "candidate_only_failure"))
    return flags


def _blank_adjusted() -> dict[str, None]:
    return {
        key: None
        for key in (
            "d_h",
            "f",
            "g",
            "t",
            "f_per_p_cap",
            "f_per_a_cap",
            "h_productivity",
            "d_h_per_a_cap",
            "c_readiness",
            "q",
            "g_per_a_cap",
            "loaded_history_h_replay_rate",
            "within_block_h_replay_rate",
            "loaded_history_pair_replay_rate",
            "within_block_pair_replay_rate",
            "candidate_only_failure_rate",
            "e",
        )
    }


def _report(
    *,
    incomplete: bool,
    limitations: Sequence[str],
    physical: dict[str, Any],
    adjusted: dict[str, Any],
) -> dict[str, Any]:
    limitations_tuple = tuple(limitations)
    return {
        "scientific_status": {
            "value": "incomplete" if incomplete else "complete",
            "reasons": ([SCIENTIFIC_DELEGATION_INCOMPLETE] if incomplete else []),
        },
        "endpoint_status": {
            "value": "unavailable" if limitations_tuple else "complete",
            "limitations": list(limitations_tuple),
        },
        "physical": physical,
        "adjusted": adjusted,
    }


def _ratio(
    numerator: int,
    denominator: int,
    *,
    zero_status: str = "ZERO_DENOMINATOR",
) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
        "status": "FINITE" if denominator else zero_status,
    }


def _throughput_ratio(numerator: int, denominator: int) -> dict[str, Any]:
    if denominator:
        return _ratio(numerator, denominator)
    return {
        "numerator": numerator,
        "denominator": 0,
        "value": 0.0,
        "status": "DEFINED_ZERO_PROVIDER_DENOMINATOR",
    }


def _positive_infinity() -> dict[str, Any]:
    return {"status": "POSITIVE_INFINITY", "value": None}


def _unavailable_effect() -> dict[str, Any]:
    return {"status": "UNAVAILABLE", "value": None}


def _cell_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("INITIAL_CELL_DISTANCE_INVALID")
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) else None


def _finite_median(values: Sequence[float]) -> float | None:
    ordered = sorted(values)
    size = len(ordered)
    if not size:
        return None
    middle = size // 2
    if size % 2:
        result = ordered[middle]
    else:
        left, right = ordered[middle - 1], ordered[middle]
        result = (
            (left + right) / 2.0
            if (left < 0.0) != (right < 0.0)
            else left / 2.0 + right / 2.0
        )
    return result if math.isfinite(result) else None


def _median_with_infinity(values: Sequence[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    left, right = ordered[middle - 1], ordered[middle]
    if math.isinf(right):
        return math.inf
    value = _finite_median((left, right))
    if value is None:
        raise RuntimeError("finite effect median became unavailable")
    return value


__all__ = ["calculate_research_effectiveness"]
