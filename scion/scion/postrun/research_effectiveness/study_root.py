"""Private decoded-artifact adapter for the M32 initial-screening boundary.

Canonical root path and non-alias identity authority are intentionally deferred
to the future safe loader. This module audits only supplied projections and
their declared campaign identifiers.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from scion.core.public_refs import public_case_ref

from .comparison import compare_five_block_research_effectiveness
from .endpoints import calculate_research_effectiveness
from .models import (
    InitialCell,
    LoadedHistoryAvailable,
    LoadedHistoryUnavailable,
    MatchedResearchEffectivenessBlock,
    ResearchEffectivenessArmArtifacts,
    ResearchEffectivenessExpectation,
    _as_mapping,
    _fail,
    _is_incomplete_reason,
    _JoinedRow,
    _Physical,
)
from .study_root_branches import _validate_branch_inventory
from .study_root_progress import (
    _validate_completed_last_result,
    _validate_stopped_current_progress,
    _validate_stopped_last_result,
)
from .study_root_schema import (
    _validate_status_summary_snapshot,
    _validate_study_run_schema,
)
from .terminal_interrupts import (
    _TERMINAL_CLOSED,
    _TERMINAL_PRE_RESERVATION,
    _row_allows_next_attempt,
    _stopped_projection_kind,
)
from .validation import (
    _normalize_history,
    _parse_physical,
    _validate_terminal_twins,
)

_DEVELOPMENT_BOUNDARY_MODE = "initial_screening_only_v1"
_QUALIFICATION_STOP = "qualification_not_reached"
_PAIRED_EFFECT_CELLS_SCHEMA = "scion.paired_effect_cells.v1"
_PAIRED_EFFECT_METRIC = "total_distance"
_ORDINARY_OUTCOMES = frozenset({"evaluated", "research_rejected"})


@dataclass(frozen=True, repr=False)
class _InitialScreeningStudyExpectation:
    """Frozen identity-bearing ordinal controls for one study arm."""

    effectiveness: ResearchEffectivenessExpectation
    case_refs: tuple[str, ...]
    seeds: tuple[int, ...]
    equivalence_band: float

    def __post_init__(self) -> None:
        if type(self.effectiveness) is not ResearchEffectivenessExpectation:
            raise ValueError("STUDY_EFFECTIVENESS_EXPECTATION_INVALID")
        if type(self.case_refs) is not tuple or any(
            type(ref) is not str or not ref or public_case_ref(ref) != ref
            for ref in self.case_refs
        ):
            raise ValueError("STUDY_CASE_REFS_INVALID")
        if len(set(self.case_refs)) != len(self.case_refs) or len(self.case_refs) != (
            self.effectiveness.expected_initial_case_count
        ):
            raise ValueError("STUDY_CASE_REFS_INVALID")
        basenames = tuple(PurePosixPath(ref).name for ref in self.case_refs)
        if len(set(basenames)) != len(basenames):
            raise ValueError("STUDY_CASE_BASENAMES_INVALID")
        if type(self.seeds) is not tuple or any(
            type(seed) is not int for seed in self.seeds
        ):
            raise ValueError("STUDY_SEEDS_INVALID")
        if (
            not self.seeds
            or len(set(self.seeds)) != len(self.seeds)
            or (
                len(self.case_refs) * len(self.seeds)
                != self.effectiveness.expected_initial_pair_count
            )
        ):
            raise ValueError("STUDY_SEEDS_INVALID")
        if type(self.equivalence_band) is not float or self.equivalence_band < 0.0:
            raise ValueError("STUDY_EQUIVALENCE_BAND_INVALID")
        _finite_study_number(
            self.equivalence_band, code="STUDY_EQUIVALENCE_BAND_INVALID"
        )

    def __repr__(self) -> str:
        return "_InitialScreeningStudyExpectation(<redacted>)"


@dataclass(frozen=True, repr=False)
class _InitialScreeningStudyRootArtifacts:
    """Decoded public artifacts for one identity-bearing study root."""

    status: Mapping[str, Any]
    summary: Mapping[str, Any]
    current_history: tuple[Mapping[str, Any], ...]
    expectation: _InitialScreeningStudyExpectation

    def __post_init__(self) -> None:
        if not isinstance(self.status, Mapping) or not isinstance(
            self.summary, Mapping
        ):
            raise TypeError("STUDY_ROOT_ARTIFACT_MAPPING_INVALID")
        if type(self.current_history) is not tuple or any(
            not isinstance(record, Mapping) for record in self.current_history
        ):
            raise ValueError("STUDY_ROOT_HISTORY_MUST_BE_A_TUPLE")
        if type(self.expectation) is not _InitialScreeningStudyExpectation:
            raise ValueError("STUDY_ROOT_EXPECTATION_INVALID")

    def __repr__(self) -> str:
        return "_InitialScreeningStudyRootArtifacts(<redacted>)"


@dataclass(frozen=True, repr=False)
class _MatchedInitialScreeningStudyBlock:
    """One private K=1/K=2 root pair sharing a loaded-history basis."""

    k1: _InitialScreeningStudyRootArtifacts
    k2: _InitialScreeningStudyRootArtifacts
    loaded_history: LoadedHistoryAvailable | LoadedHistoryUnavailable

    def __post_init__(self) -> None:
        if (
            type(self.k1) is not _InitialScreeningStudyRootArtifacts
            or type(self.k2) is not _InitialScreeningStudyRootArtifacts
        ):
            raise ValueError("STUDY_MATCHED_BLOCK_ARM_INVALID")
        if type(self.loaded_history) not in {
            LoadedHistoryAvailable,
            LoadedHistoryUnavailable,
        }:
            raise ValueError("STUDY_MATCHED_BLOCK_HISTORY_INVALID")

    def __repr__(self) -> str:
        return "_MatchedInitialScreeningStudyBlock(<redacted>)"


def _calculate_initial_screening_study_root_effectiveness(
    *,
    artifacts: _InitialScreeningStudyRootArtifacts,
    loaded_history: LoadedHistoryAvailable | LoadedHistoryUnavailable,
) -> dict[str, Any]:
    """Audit and score one already-decoded public study root."""

    if type(artifacts) is not _InitialScreeningStudyRootArtifacts:
        _fail("STUDY_ROOT_ARTIFACTS_INVALID")
    if type(loaded_history) not in {
        LoadedHistoryAvailable,
        LoadedHistoryUnavailable,
    }:
        _fail("STUDY_ROOT_LOADED_HISTORY_INVALID")
    arm = _decode_study_root(artifacts)
    return calculate_research_effectiveness(
        status=arm.status,
        summary=arm.summary,
        current_history=arm.current_history,
        loaded_history=loaded_history,
        expectation=arm.expectation,
        initial_cells=arm.initial_cells,
    )


def _compare_five_block_initial_screening_study_roots(
    *,
    blocks: tuple[_MatchedInitialScreeningStudyBlock, ...],
) -> dict[str, Any]:
    """Audit ten projections before delegating to the exact-five oracle.

    Declared campaign identifiers are checked for uniqueness. Canonical root
    path and non-alias authority remain the responsibility of the future loader.
    """

    if type(blocks) is not tuple or len(blocks) != 5:
        _fail("STUDY_FIVE_BLOCK_INPUT_INVALID")
    for block in blocks:
        if type(block) is not _MatchedInitialScreeningStudyBlock:
            _fail("STUDY_MATCHED_BLOCK_INPUT_INVALID")
    decoded = tuple(
        (
            _decode_study_root(block.k1),
            _decode_study_root(block.k2),
            block.loaded_history,
        )
        for block in blocks
    )
    _validate_matched_study_controls(blocks)
    _validate_distinct_declared_campaign_ids(decoded)
    return compare_five_block_research_effectiveness(
        blocks=tuple(
            MatchedResearchEffectivenessBlock(
                k1=k1,
                k2=k2,
                loaded_history=loaded_history,
            )
            for k1, k2, loaded_history in decoded
        )
    )


def _validate_matched_study_controls(
    blocks: tuple[_MatchedInitialScreeningStudyBlock, ...],
) -> None:
    for block in blocks:
        k1 = block.k1.expectation
        k2 = block.k2.expectation
        if (
            k1.effectiveness.max_hypothesis_candidates != 1
            or k2.effectiveness.max_hypothesis_candidates != 2
            or k1.case_refs != k2.case_refs
            or k1.seeds != k2.seeds
            or k1.equivalence_band != k2.equivalence_band
            or _effectiveness_match_key(k1.effectiveness)
            != _effectiveness_match_key(k2.effectiveness)
            or _visible_root_control_key(block.k1.status)
            != _visible_root_control_key(block.k2.status)
        ):
            _fail("STUDY_MATCHED_CONTROL_MISMATCH")


def _effectiveness_match_key(
    expectation: ResearchEffectivenessExpectation,
) -> tuple[Any, ...]:
    return (
        expectation.problem_id,
        expectation.expected_initial_case_count,
        expectation.expected_initial_pair_count,
        expectation.a_cap,
        expectation.p_cap,
    )


def _visible_root_control_key(status: Mapping[str, Any]) -> tuple[Any, ...]:
    active = _as_mapping(status.get("active_slots"), "STUDY_ACTIVE_INVENTORY_INVALID")
    readiness = _as_mapping(
        status.get("measurement_readiness"),
        "STUDY_MEASUREMENT_READINESS_INVALID",
    )
    values = (
        status.get("champion_version"),
        status.get("champion_weight_revision"),
        active.get("max"),
    )
    if any(type(value) is not int for value in values):
        _fail("STUDY_MATCHED_VISIBLE_CONTROL_INVALID")
    return (*values, dict(readiness))


def _validate_distinct_declared_campaign_ids(
    decoded: tuple[
        tuple[
            ResearchEffectivenessArmArtifacts,
            ResearchEffectivenessArmArtifacts,
            LoadedHistoryAvailable | LoadedHistoryUnavailable,
        ],
        ...,
    ],
) -> None:
    campaign_ids = tuple(
        _campaign_id(arm.status)
        for k1, k2, _loaded_history in decoded
        for arm in (k1, k2)
    )
    if len(set(campaign_ids)) != 10:
        _fail("STUDY_CAMPAIGN_REUSE_INVALID")


def _campaign_id(status: Mapping[str, Any]) -> str:
    value = status.get("campaign_id")
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or len(value) > 256
        or not value.isprintable()
    ):
        _fail("STUDY_CAMPAIGN_ID_INVALID")
    assert isinstance(value, str)
    return value


def _decode_study_root(
    artifacts: _InitialScreeningStudyRootArtifacts,
) -> ResearchEffectivenessArmArtifacts:
    status = _as_mapping(artifacts.status, "STATUS_NOT_A_MAPPING")
    summary = _as_mapping(artifacts.summary, "SUMMARY_NOT_A_MAPPING")
    study_expectation = artifacts.expectation
    expectation = study_expectation.effectiveness
    _validate_terminal_twins(status, summary, expectation)
    _validate_study_run_schema(status)
    histories = _normalize_history(
        artifacts.current_history,
        expectation=expectation,
        code="CURRENT_HISTORY_INVALID",
    )
    physical = _parse_physical(status, summary, histories, expectation)
    _validate_status_summary_snapshot(status, summary)
    _campaign_id(status)
    completed = _validate_initial_only_projection(
        status,
        physical,
        histories,
        expectation,
    )
    _validate_initial_only_rows(
        physical,
        study_expectation,
        completed=completed,
    )
    _validate_branch_inventory(status, physical, completed=completed)
    initial_cells = _decode_initial_cells(physical, expectation)
    return ResearchEffectivenessArmArtifacts(
        status=artifacts.status,
        summary=artifacts.summary,
        current_history=artifacts.current_history,
        expectation=expectation,
        initial_cells=initial_cells,
    )


def _validate_initial_only_projection(
    status: Mapping[str, Any],
    physical: _Physical,
    histories: tuple[dict[str, Any], ...],
    expectation: ResearchEffectivenessExpectation,
) -> bool:
    run = _as_mapping(status["run_result"], "RUN_RESULT_INVALID")
    qualification = _as_mapping(
        run.get("qualification"), "QUALIFICATION_PROJECTION_INVALID"
    )
    limits = _as_mapping(qualification.get("limits"), "QUALIFICATION_LIMITS_INVALID")
    if qualification.get("development_boundary_mode") != _DEVELOPMENT_BOUNDARY_MODE:
        _fail("STUDY_DEVELOPMENT_BOUNDARY_MODE_INVALID")
    if set(limits) != {
        "max_proposal_attempts",
        "max_verified_candidate_chains",
        "max_formal_screening_stages",
    } or any(value != expectation.a_cap for value in limits.values()):
        _fail("STUDY_QUALIFICATION_CAP_MISMATCH")
    if run.get("requested_rounds") != expectation.a_cap:
        _fail("STUDY_REQUESTED_ROUNDS_MISMATCH")
    stage_counts = _as_mapping(
        run.get("protocol_stage_counts"), "PROTOCOL_STAGE_COUNTS_INVALID"
    )
    if stage_counts.get("validation") != 0 or stage_counts.get("frozen") != 0:
        _fail("STUDY_HELDOUT_STAGE_OBSERVED")
    if qualification.get("expanded_screening_stages") != 0:
        _fail("STUDY_EXPANDED_SCREENING_OBSERVED")

    completed = run.get("status") == "completed"
    if completed:
        if run.get("run_validity") != {
            "valid": True,
            "status": "valid",
            "reason": "valid",
        }:
            _fail("STUDY_COMPLETED_RUN_INVALID")
        if run.get("stop_reason") != _QUALIFICATION_STOP or (
            qualification.get("disposition") != _QUALIFICATION_STOP
        ):
            _fail("STUDY_COMPLETED_TERMINAL_INVALID")
        _validate_completed_inventory(
            status,
            run,
            physical,
            histories,
            expectation,
        )
        _validate_completed_scientific_accounting(run, physical)
    else:
        _validate_stopped_prefix(status, run, physical, histories, expectation)
    return completed


def _validate_completed_inventory(
    status: Mapping[str, Any],
    run: Mapping[str, Any],
    physical: _Physical,
    histories: tuple[dict[str, Any], ...],
    expectation: ResearchEffectivenessExpectation,
) -> None:
    attempts = physical.attempts
    rows = physical.rows
    expected = expectation.a_cap
    if status.get("balance_exhausted") is not False:
        _fail("STUDY_COMPLETED_BALANCE_EXHAUSTED")
    if not (
        len(attempts)
        == len(rows)
        == len(histories)
        == run.get("scheduled_calls")
        == status.get("n_steps")
        == expected
    ):
        _fail("STUDY_COMPLETED_ATTEMPT_INVENTORY_INVALID")
    if tuple(attempt.round_num for attempt in attempts) != tuple(
        range(1, expected + 1)
    ):
        _fail("STUDY_COMPLETED_ATTEMPT_ORDINAL_INVALID")
    if any(attempt.accounting_state != "closed" for attempt in attempts):
        _fail("STUDY_COMPLETED_ATTEMPT_STATE_INVALID")
    if any(row.attempt is None or row.expanded for row in rows):
        _fail("STUDY_COMPLETED_ROW_JOIN_INVALID")
    if any(row.history["outcome"]["outcome"] not in _ORDINARY_OUTCOMES for row in rows):
        _fail("STUDY_COMPLETED_OUTCOME_INVALID")
    _validate_completed_last_result(status, rows)


def _validate_stopped_prefix(
    status: Mapping[str, Any],
    run: Mapping[str, Any],
    physical: _Physical,
    histories: tuple[dict[str, Any], ...],
    expectation: ResearchEffectivenessExpectation,
) -> None:
    if run.get("status") != "stopped":
        _fail("STUDY_RUN_TERMINAL_INVALID")
    attempts = physical.attempts
    rows = physical.rows
    row_count = len(rows)
    if len(attempts) > expectation.a_cap:
        _fail("STUDY_STOPPED_PREFIX_INVALID")
    if tuple(attempt.round_num for attempt in attempts) != tuple(
        range(1, len(attempts) + 1)
    ):
        _fail("STUDY_STOPPED_ATTEMPT_ORDINAL_INVALID")
    if tuple(int(row.summary["round"]) for row in rows) != tuple(
        range(1, row_count + 1)
    ) or any(row.attempt is None or row.expanded for row in rows):
        _fail("STUDY_STOPPED_ROW_ORDINAL_INVALID")
    terminal_kind = _stopped_projection_kind(status, rows, attempts)
    if terminal_kind is None:
        _fail("STUDY_STOPPED_TERMINAL_PROJECTION_INVALID")
    assert terminal_kind is not None
    _validate_stopped_current_progress(status, physical, terminal_kind)
    _validate_stopped_last_result(status, physical, terminal_kind)
    has_terminal_gap = terminal_kind != _TERMINAL_CLOSED
    continuable_rows = rows if has_terminal_gap else rows[:-1]
    if any(not _row_allows_next_attempt(row) for row in continuable_rows):
        _fail("STUDY_STOPPED_PREFIX_SEQUENCE_INVALID")
    if not row_count == len(histories) == status.get("n_steps"):
        _fail("STUDY_STOPPED_ROW_INVENTORY_INVALID")
    if terminal_kind == _TERMINAL_PRE_RESERVATION and (
        len(attempts) >= expectation.a_cap
    ):
        _fail("STUDY_PRE_RESERVATION_INTERRUPT_INVALID")


def _validate_initial_only_rows(
    physical: _Physical,
    study_expectation: _InitialScreeningStudyExpectation,
    *,
    completed: bool,
) -> None:
    for row in physical.initial_rows:
        _validate_candidate_composition(row)
        _validate_ordinal_controls(row, study_expectation)
        assert row.protocol is not None
        if (
            row.protocol.n_cases
            != study_expectation.effectiveness.expected_initial_case_count
            or row.protocol.total_pairs
            != study_expectation.effectiveness.expected_initial_pair_count
        ):
            _fail("STUDY_DECLARED_MATRIX_SHAPE_MISMATCH")
    if completed and physical.incomplete:
        _fail("STUDY_COMPLETED_RUN_INCOMPLETE")


def _validate_completed_scientific_accounting(
    run: Mapping[str, Any], physical: _Physical
) -> None:
    rows = physical.rows
    observed = Counter(str(row.history["outcome"]["outcome"]) for row in rows)
    raw_outcomes = _as_mapping(
        run.get("execution_outcome_counts"), "RUN_OUTCOME_COUNTS_INVALID"
    )
    if any(raw_outcomes.get(name) != count for name, count in observed.items()) or any(
        count and observed.get(name, 0) != count for name, count in raw_outcomes.items()
    ):
        _fail("STUDY_COMPLETED_OUTCOME_HISTOGRAM_INVALID")
    if (
        run.get("unknown_outcome_count") != 0
        or run.get("terminal_exception") is not None
        or run.get("evaluated_rounds") != len(physical.initial_rows)
        or any(
            row.history["outcome"]["stage"] == "canary"
            and row.canary_classification
            not in {"candidate", "champion", "shared", "bilateral"}
            for row in rows
        )
        or any(
            _is_incomplete_reason(str(row.history["outcome"]["reason_code"]))
            for row in rows
        )
    ):
        _fail("STUDY_COMPLETED_SCIENTIFIC_ACCOUNTING_INVALID")


def _validate_candidate_composition(row: _JoinedRow) -> None:
    protocol = _as_mapping(row.history.get("protocol"), "HISTORY_PROTOCOL_INVALID")
    composition = _as_mapping(
        protocol.get("candidate_composition"),
        "STUDY_CANDIDATE_COMPOSITION_INVALID",
    )
    if row.patch_key is None:
        _fail("STUDY_CANDIDATE_COMPOSITION_INVALID")
    target_files = sorted({change[0] for change in row.patch_key})
    expected = {
        "attribution_scope": "current_step_candidate",
        "protocol_comparison_scope": "candidate_vs_champion",
        "evaluation_candidate": "branch_state_after_current_step_patch",
        "current_step_change_scope": "incremental_patch",
        "incremental_effect_isolated": True,
        "current_step": {"target_files": target_files},
    }
    if dict(composition) != expected:
        _fail("STUDY_CANDIDATE_COMPOSITION_INVALID")


def _validate_ordinal_controls(
    row: _JoinedRow,
    expectation: _InitialScreeningStudyExpectation,
) -> None:
    summary = _as_mapping(
        row.summary.get("protocol_result"), "SUMMARY_PROTOCOL_INVALID"
    )
    if (
        type(summary.get("case_ids")) is not list
        or any(type(value) is not str for value in summary["case_ids"])
        or summary["case_ids"] != list(expectation.case_refs)
    ):
        _fail("STUDY_CASE_REFS_MISMATCH")
    if (
        type(summary.get("seed_set")) is not list
        or any(type(value) is not int for value in summary["seed_set"])
        or summary["seed_set"] != list(expectation.seeds)
    ):
        _fail("STUDY_SEEDS_MISMATCH")
    aggregation = _as_mapping(
        summary.get("case_aggregation"), "STUDY_CASE_AGGREGATION_INVALID"
    )
    if set(aggregation) != {"method", "effect_metric", "equivalence_band"} or (
        aggregation.get("method") != "paired_effect_median"
        or aggregation.get("effect_metric") != _PAIRED_EFFECT_METRIC
        or type(aggregation.get("equivalence_band")) is not float
        or aggregation.get("equivalence_band") != expectation.equivalence_band
    ):
        _fail("STUDY_CASE_AGGREGATION_INVALID")


def _decode_initial_cells(
    physical: _Physical,
    expectation: ResearchEffectivenessExpectation,
) -> tuple[tuple[InitialCell, ...], ...]:
    outer: list[tuple[InitialCell, ...]] = []
    for row in physical.initial_rows:
        protocol = _as_mapping(
            row.summary.get("protocol_result"), "SUMMARY_PROTOCOL_INVALID"
        )
        if "paired_effect_cells" not in protocol:
            outer.append(())
            continue
        raw = protocol["paired_effect_cells"]
        if row.protocol is None or not row.protocol.exact_initial_matrix(expectation):
            _fail("STUDY_PAIRED_EFFECT_CELLS_UNEXPECTED")
        payload = _as_mapping(raw, "STUDY_PAIRED_EFFECT_CELLS_INVALID")
        if set(payload) != {"schema_version", "metric_name", "cells"} or (
            payload.get("schema_version") != _PAIRED_EFFECT_CELLS_SCHEMA
            or payload.get("metric_name") != _PAIRED_EFFECT_METRIC
        ):
            _fail("STUDY_PAIRED_EFFECT_CELLS_INVALID")
        raw_cells = payload.get("cells")
        if type(raw_cells) is not list or len(raw_cells) != (
            expectation.expected_initial_pair_count
        ):
            _fail("STUDY_PAIRED_EFFECT_CELLS_INVALID")
        cells: list[InitialCell] = []
        for raw_cell in raw_cells:
            cell = _as_mapping(raw_cell, "STUDY_PAIRED_EFFECT_CELL_INVALID")
            if set(cell) != {"candidate_value", "reference_value"}:
                _fail("STUDY_PAIRED_EFFECT_CELL_INVALID")
            candidate = _finite_cell_number(cell.get("candidate_value"))
            reference = _finite_cell_number(cell.get("reference_value"))
            if candidate < 0:
                _fail("STUDY_PAIRED_EFFECT_CELL_INVALID")
            cells.append(
                InitialCell(
                    candidate_total_distance=candidate,
                    b0_total_distance=reference,
                )
            )
        outer.append(tuple(cells))
    return tuple(outer)


def _finite_cell_number(value: Any) -> int | float:
    return _finite_study_number(value, code="STUDY_PAIRED_EFFECT_CELL_INVALID")


def _finite_study_number(value: Any, *, code: str) -> int | float:
    if type(value) not in {int, float}:
        _fail(code)
    try:
        finite = math.isfinite(float(value))
    except (OverflowError, TypeError, ValueError):
        finite = False
    if not finite:
        _fail(code)
    assert type(value) in {int, float}
    return value
