"""Private branch-inventory audit for initial-screening study artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .models import (
    _as_mapping,
    _fail,
    _JoinedRow,
    _Physical,
)
from .terminal_interrupts import _row_allows_next_attempt

_FORMAL_BRANCH_STATE = "parked_lineage"
_PREFORMAL_BRANCH_STATE = "explore"
_BLOCKED_BRANCH_STATE = "blocked_infra"
_BRANCH_FIELDS = frozenset(
    {
        "id",
        "state",
        "base_champion_id",
        "current_code_hash",
        "weight_revision",
        "direction",
        "failure_codes",
        "created_at",
        "updated_at",
    }
)


def _validate_branch_inventory(
    status: Mapping[str, Any],
    physical: _Physical,
    *,
    completed: bool,
) -> None:
    branches, ordered_ids = _parse_branches(status)
    rows_by_branch = _rows_by_branch(physical)
    terminal_gap = _terminal_branch_gap(status, physical, completed=completed)
    _validate_branch_id_join(
        branches,
        rows_by_branch,
        physical,
        completed=completed,
        terminal_gap=terminal_gap,
    )
    champion, weight_revision = _champion_projection(status)
    active_ids: list[str] = []
    for branch_id in ordered_ids:
        branch = branches[branch_id]
        rows = rows_by_branch.get(branch_id, [])
        _validate_one_branch(
            branch,
            rows,
            physical,
            completed=completed,
            champion=champion,
            weight_revision=weight_revision,
        )
        if branch.get("state") == _PREFORMAL_BRANCH_STATE:
            active_ids.append(branch_id)
    _validate_active_inventory(status, active_ids)


def _parse_branches(
    status: Mapping[str, Any],
) -> tuple[dict[str, Mapping[str, Any]], list[str]]:
    raw_branches = status.get("branches")
    if not isinstance(raw_branches, list):
        _fail("STUDY_BRANCH_INVENTORY_INVALID")
    assert isinstance(raw_branches, list)
    branches: dict[str, Mapping[str, Any]] = {}
    ordered_ids: list[str] = []
    for raw in raw_branches:
        branch = _as_mapping(raw, "STUDY_BRANCH_INVENTORY_INVALID")
        if set(branch) != _BRANCH_FIELDS:
            _fail("STUDY_BRANCH_INVENTORY_INVALID")
        branch_id = branch.get("id")
        if type(branch_id) is not str or not branch_id or branch_id in branches:
            _fail("STUDY_BRANCH_INVENTORY_INVALID")
        branches[branch_id] = branch
        ordered_ids.append(branch_id)
    return branches, ordered_ids


def _rows_by_branch(physical: _Physical) -> dict[str, list[_JoinedRow]]:
    rows_by_branch: dict[str, list[_JoinedRow]] = {}
    for row in physical.rows:
        branch_id = row.summary.get("branch_id")
        if type(branch_id) is not str or not branch_id:
            _fail("STUDY_SUMMARY_BRANCH_INVALID")
        rows_by_branch.setdefault(branch_id, []).append(row)
    return rows_by_branch


def _champion_projection(status: Mapping[str, Any]) -> tuple[int, int]:
    champion = status.get("champion_version")
    weight_revision = status.get("champion_weight_revision")
    if (
        type(champion) is not int
        or champion < 0
        or type(weight_revision) is not int
        or weight_revision < 0
    ):
        _fail("STUDY_CHAMPION_PROJECTION_INVALID")
    assert type(champion) is int and type(weight_revision) is int
    return champion, weight_revision


def _validate_one_branch(
    branch: Mapping[str, Any],
    rows: list[_JoinedRow],
    physical: _Physical,
    *,
    completed: bool,
    champion: int,
    weight_revision: int,
) -> None:
    retired = _validate_retirement_sequence(rows)
    state = branch.get("state")
    if not _branch_state_is_valid(
        state,
        rows,
        completed=completed,
        retired=retired,
    ):
        _fail("STUDY_BRANCH_RETIREMENT_INVALID")
    terminal_hold = bool(
        not completed and rows and not _row_allows_next_attempt(rows[-1])
    )
    reusable_rows = rows[:-1] if retired or terminal_hold else rows
    if any(
        row.history["outcome"]["outcome"] != "research_rejected"
        for row in reusable_rows
    ):
        _fail("STUDY_PREFORMAL_BRANCH_INVALID")
    _validate_branch_projection(branch, champion, weight_revision)
    if state == _PREFORMAL_BRANCH_STATE and branch["failure_codes"]:
        _fail("STUDY_EXPLORE_BRANCH_NOT_CLEAN")
    _validate_blocked_branch_evidence(branch, rows, physical)


def _validate_retirement_sequence(rows: list[_JoinedRow]) -> bool:
    retirement_positions = tuple(
        index for index, row in enumerate(rows) if _row_requires_retirement(row)
    )
    if len(retirement_positions) > 1 or (
        retirement_positions and retirement_positions[0] != len(rows) - 1
    ):
        _fail("STUDY_BRANCH_RETIREMENT_SEQUENCE_INVALID")
    return bool(retirement_positions)


def _branch_state_is_valid(
    state: Any,
    rows: list[_JoinedRow],
    *,
    completed: bool,
    retired: bool,
) -> bool:
    if completed:
        expected = _FORMAL_BRANCH_STATE if retired else _PREFORMAL_BRANCH_STATE
        return state == expected
    if retired:
        return state == _FORMAL_BRANCH_STATE
    return state in _stopped_unretired_states(rows)


def _validate_branch_projection(
    branch: Mapping[str, Any], champion: int, weight_revision: int
) -> None:
    if (
        branch.get("current_code_hash") is not None
        or branch.get("direction") is not None
    ):
        _fail("STUDY_BRANCH_AUTHORITY_REMAINS")
    if branch.get("base_champion_id") != champion or (
        branch.get("weight_revision") != weight_revision
    ):
        _fail("STUDY_BRANCH_BASE_MISMATCH")
    if (
        type(branch.get("base_champion_id")) is not int
        or type(branch.get("weight_revision")) is not int
        or type(branch.get("failure_codes")) is not list
        or any(type(code) is not str for code in branch["failure_codes"])
        or type(branch.get("created_at")) is not str
        or not branch["created_at"]
        or type(branch.get("updated_at")) is not str
        or not branch["updated_at"]
    ):
        _fail("STUDY_BRANCH_INVENTORY_INVALID")


def _validate_branch_id_join(
    branches: Mapping[str, Mapping[str, Any]],
    rows_by_branch: Mapping[str, list[_JoinedRow]],
    physical: _Physical,
    *,
    completed: bool,
    terminal_gap: int,
) -> None:
    visible_ids = set(branches)
    row_ids = set(rows_by_branch)
    extra_ids = visible_ids - row_ids
    missing_ids = row_ids - visible_ids
    if completed:
        if visible_ids != row_ids:
            _fail("STUDY_BRANCH_ROW_JOIN_INVALID")
        return
    if len(extra_ids) > terminal_gap:
        _fail("STUDY_BRANCH_ROW_JOIN_INVALID")
    expected_missing = _expected_missing_branch(physical)
    if missing_ids != expected_missing:
        _fail("STUDY_BRANCH_ROW_JOIN_INVALID")
    if expected_missing:
        hidden_rows = rows_by_branch[next(iter(expected_missing))]
        if any(
            _row_requires_retirement(row)
            or row.history["outcome"]["outcome"] != "research_rejected"
            for row in hidden_rows[:-1]
        ):
            _fail("STUDY_BRANCH_RETIREMENT_SEQUENCE_INVALID")


def _expected_missing_branch(physical: _Physical) -> set[str]:
    if not physical.rows:
        return set()
    last = physical.rows[-1]
    if (
        last.protocol is None
        and last.canary_classification in {"champion", "shared", "bilateral"}
        and _row_decision_is_abandon(last)
    ):
        return {str(last.summary["branch_id"])}
    return set()


def _terminal_branch_gap(
    status: Mapping[str, Any], physical: _Physical, *, completed: bool
) -> int:
    if completed:
        return 0
    run = _as_mapping(status.get("run_result"), "RUN_RESULT_INVALID")
    return int(
        len(physical.attempts) > len(physical.rows)
        or run.get("scheduled_calls") > len(physical.attempts)
    )


def _row_decision_is_abandon(row: _JoinedRow) -> bool:
    decision = row.history.get("decision")
    return bool(isinstance(decision, Mapping) and decision.get("value") == "abandon")


def _stopped_unretired_states(rows: list[_JoinedRow]) -> frozenset[str]:
    if not rows:
        return frozenset({_PREFORMAL_BRANCH_STATE})
    outcome = rows[-1].history["outcome"]["outcome"]
    if outcome in {
        "blocked_infra",
        "not_evaluated",
        "resource_exhausted",
        "interrupted",
    }:
        return frozenset({_BLOCKED_BRANCH_STATE})
    return frozenset({_PREFORMAL_BRANCH_STATE})


def _validate_blocked_branch_evidence(
    branch: Mapping[str, Any], rows: list[_JoinedRow], physical: _Physical
) -> None:
    if branch.get("state") != _BLOCKED_BRANCH_STATE:
        return
    failure_codes = branch.get("failure_codes")
    if not failure_codes:
        _fail("STUDY_BLOCKED_BRANCH_EVIDENCE_INVALID")
    assert isinstance(failure_codes, list)
    if rows:
        if rows[-1] is not physical.rows[-1] or (
            rows[-1].history["outcome"]["outcome"]
            not in {
                "not_evaluated",
                "blocked_infra",
                "resource_exhausted",
                "interrupted",
            }
        ):
            _fail("STUDY_BLOCKED_BRANCH_EVIDENCE_INVALID")
        reason = rows[-1].history["outcome"]["reason_code"]
        if reason not in failure_codes:
            _fail("STUDY_BLOCKED_BRANCH_EVIDENCE_INVALID")


def _row_requires_retirement(row: _JoinedRow) -> bool:
    return row.protocol is not None or row.canary_classification == "candidate"


def _validate_active_inventory(
    status: Mapping[str, Any], active_ids: list[str]
) -> None:
    active = _as_mapping(status.get("active_slots"), "STUDY_ACTIVE_INVENTORY_INVALID")
    if set(active) != {"used", "max", "available", "branch_ids"}:
        _fail("STUDY_ACTIVE_INVENTORY_INVALID")
    used = active.get("used")
    maximum = active.get("max")
    available = active.get("available")
    branch_ids = active.get("branch_ids")
    n_active = status.get("n_active_branches")
    if (
        type(used) is not int
        or type(maximum) is not int
        or type(available) is not int
        or type(n_active) is not int
        or _minimum_negative(used, maximum, available)
        or maximum == 0
        or n_active < 0
        or used > maximum
        or available != maximum - used
        or type(branch_ids) is not list
        or branch_ids != active_ids
        or used != len(active_ids)
        or n_active != used
    ):
        _fail("STUDY_ACTIVE_INVENTORY_INVALID")


def _minimum_negative(*values: int) -> bool:
    return min(values) < 0
