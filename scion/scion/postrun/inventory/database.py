"""SQLite campaign inventory readers."""

from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from scion.core.execution_outcome import ExecutionOutcome
from scion.core.proposal_trajectory_artifacts import (
    read_proposal_attempt_transitions,
)
from scion.postrun.inventory.utils import (
    _branch_id,
    _string_list,
    _string_or_none,
)


def _read_db_inventory(db_path: Path) -> dict[str, Any]:
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            tables = _tables(conn)
            branches = _branches(conn) if "branches" in tables else []
            events = _events(conn) if "experiment_events" in tables else _empty_events()
            hypotheses = (
                _hypotheses(conn) if "hypotheses" in tables else _empty_hypotheses()
            )
            champions = (
                _champions(conn) if "champions" in tables else _empty_champions()
            )
    except sqlite3.DatabaseError as exc:
        empty = _empty_db_inventory()
        empty["read_error"] = f"{type(exc).__name__}: {exc}"
        return empty
    proposal_attempts = read_proposal_attempt_transitions(db_path)["stats"]
    return {
        "branches": branches,
        "events": events,
        "hypotheses": hypotheses,
        "champions": champions,
        "proposal_attempts": proposal_attempts,
    }


def _empty_db_inventory() -> dict[str, Any]:
    return {
        "branches": [],
        "events": _empty_events(),
        "hypotheses": _empty_hypotheses(),
        "champions": _empty_champions(),
        "proposal_attempts": _empty_proposal_attempts(),
        "read_error": None,
    }


def _empty_proposal_attempts() -> dict[str, Any]:
    return {
        "source_status": "missing",
        "row_count": 0,
        "valid_row_count": 0,
        "invalid_row_count": 0,
        "attempt_count": 0,
        "by_runtime_mode": {},
        "by_phase": {},
        "by_status": {},
        "by_failure_lane": {},
        "prompt_manifest_ref_count": 0,
        "invalid_by_reason": {},
    }


def _empty_events() -> dict[str, Any]:
    return {
        "by_kind": {},
        "by_decision": {},
        "by_stage": {},
        "execution_outcome_schema_available": False,
        "by_execution_outcome": {},
        "explicit_execution_outcome_count": 0,
        "invalid_execution_outcome_count": 0,
        "decision_rows_with_non_evaluated_outcome": 0,
        "decision_outcome_consistency_status": "unknown_historical",
    }


def _empty_hypotheses() -> dict[str, Any]:
    return {
        "count": 0,
        "by_status": {},
        "by_action": {},
        "by_change_locus": {},
    }


def _empty_champions() -> dict[str, Any]:
    return {
        "table_present": False,
        "count": 0,
        "max_version": None,
        "max_weight_revision": None,
        "versions": [],
        "promotion_experiment_count": 0,
        "promotion_dossier_count": 0,
        "promoted_at_count": 0,
        "latest_promotion_experiment_id": None,
        "latest_promotion_dossier_ref": None,
    }


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {str(row[0]) for row in rows}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _branches(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    columns = _columns(conn, "branches")
    wanted = (
        "branch_id",
        "state",
        "lineage_id",
        "base_champion_hash",
        "current_code_hash",
        "best_quality_checkpoint_id",
        "last_valid_checkpoint_id",
        "rollback_count",
        "failure_codes",
    )
    select_cols = [col for col in wanted if col in columns]
    rows = conn.execute(
        f"SELECT {', '.join(select_cols)} FROM branches ORDER BY branch_id"
    ).fetchall()
    branches: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        branch_id = str(data.get("branch_id") or "")
        branches.append(
            {
                "branch_id": branch_id,
                "state": data.get("state"),
                "lineage_id": data.get("lineage_id") or branch_id,
                "base_champion_hash": data.get("base_champion_hash"),
                "current_code_hash": data.get("current_code_hash"),
                "best_quality_checkpoint_id": data.get("best_quality_checkpoint_id"),
                "last_valid_checkpoint_id": data.get("last_valid_checkpoint_id"),
                "rollback_count": int(data.get("rollback_count") or 0),
                "failure_codes": _string_list(data.get("failure_codes")),
                "hypothesis_count": _count_where(
                    conn, "hypotheses", "branch_id", branch_id
                ),
                "event_count": _count_where(
                    conn, "experiment_events", "branch_id", branch_id
                ),
                "session_count": 0,
                "trace_count": 0,
            }
        )
    return branches


def _events(conn: sqlite3.Connection) -> dict[str, Any]:
    columns = _columns(conn, "experiment_events")
    outcome_schema = "execution_outcome" in columns
    by_outcome = (
        _group_counts(conn, "experiment_events", "execution_outcome")
        if outcome_schema
        else {}
    )
    allowed = {outcome.value for outcome in ExecutionOutcome}
    explicit_count = sum(by_outcome.values())
    invalid_count = sum(
        count for value, count in by_outcome.items() if value not in allowed
    )
    inconsistent_decisions = 0
    decision_count = 0
    if "decision" in columns:
        decision_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM experiment_events "
                "WHERE decision IS NOT NULL AND decision != ''"
            ).fetchone()[0]
            or 0
        )
        if outcome_schema and explicit_count > 0:
            identity_columns = {"campaign_id", "branch_id", "hypothesis_id"}
            if identity_columns.issubset(columns):
                inconsistent_decisions = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM experiment_events AS decision_row "
                        "WHERE decision_row.decision IS NOT NULL "
                        "AND decision_row.decision != '' "
                        "AND COALESCE(decision_row.execution_outcome, '') != ? "
                        "AND NOT EXISTS ("
                        "SELECT 1 FROM experiment_events AS outcome_row "
                        "WHERE outcome_row.execution_outcome = ? "
                        "AND outcome_row.campaign_id = decision_row.campaign_id "
                        "AND outcome_row.branch_id = decision_row.branch_id "
                        "AND (outcome_row.hypothesis_id = decision_row.hypothesis_id "
                        "OR decision_row.hypothesis_id IS NULL))",
                        (
                            ExecutionOutcome.EVALUATED.value,
                            ExecutionOutcome.EVALUATED.value,
                        ),
                    ).fetchone()[0]
                    or 0
                )
            else:
                inconsistent_decisions = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM experiment_events "
                        "WHERE decision IS NOT NULL AND decision != '' "
                        "AND execution_outcome IS NOT NULL "
                        "AND execution_outcome != '' "
                        "AND execution_outcome != ?",
                        (ExecutionOutcome.EVALUATED.value,),
                    ).fetchone()[0]
                    or 0
                )
    if invalid_count or inconsistent_decisions:
        consistency_status = "invalid"
    elif explicit_count > 0:
        consistency_status = "consistent"
    else:
        consistency_status = "unknown_historical"
    return {
        "by_kind": _group_counts(conn, "experiment_events", "event_kind"),
        "by_decision": _group_counts(conn, "experiment_events", "decision"),
        "by_stage": _group_counts(conn, "experiment_events", "stage"),
        "execution_outcome_schema_available": outcome_schema,
        "by_execution_outcome": by_outcome,
        "explicit_execution_outcome_count": explicit_count,
        "invalid_execution_outcome_count": invalid_count,
        "decision_row_count": decision_count,
        "decision_rows_with_non_evaluated_outcome": inconsistent_decisions,
        "decision_outcome_consistency_status": consistency_status,
    }


def _hypotheses(conn: sqlite3.Connection) -> dict[str, Any]:
    count = conn.execute("SELECT COUNT(*) FROM hypotheses").fetchone()[0]
    return {
        "count": int(count or 0),
        "by_status": _group_counts(conn, "hypotheses", "status"),
        "by_action": _group_counts(conn, "hypotheses", "action"),
        "by_change_locus": _group_counts(conn, "hypotheses", "change_locus"),
    }


def _champions(conn: sqlite3.Connection) -> dict[str, Any]:
    columns = _columns(conn, "champions")
    if "version" not in columns:
        payload = _empty_champions()
        payload["table_present"] = True
        return payload

    count = int(conn.execute("SELECT COUNT(*) FROM champions").fetchone()[0] or 0)
    max_version = conn.execute("SELECT MAX(version) FROM champions").fetchone()[0]
    version_rows = conn.execute(
        "SELECT DISTINCT version FROM champions ORDER BY version"
    ).fetchall()
    versions = [int(row[0]) for row in version_rows if row[0] is not None]
    max_weight_revision = None
    if "weight_revision" in columns and max_version is not None:
        max_weight_revision = conn.execute(
            "SELECT MAX(weight_revision) FROM champions WHERE version = ?",
            (max_version,),
        ).fetchone()[0]

    promotion_experiment_count = 0
    latest_promotion_experiment_id = None
    if "promotion_experiment_id" in columns:
        promotion_experiment_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM champions "
                "WHERE promotion_experiment_id IS NOT NULL "
                "AND promotion_experiment_id != ''"
            ).fetchone()[0]
            or 0
        )
        latest_promotion_experiment_id = _latest_champion_field(
            conn,
            "promotion_experiment_id",
            columns=columns,
        )

    promotion_dossier_count = 0
    latest_promotion_dossier_ref = None
    if "promotion_dossier_ref" in columns:
        promotion_dossier_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM champions "
                "WHERE promotion_dossier_ref IS NOT NULL "
                "AND promotion_dossier_ref != ''"
            ).fetchone()[0]
            or 0
        )
        latest_promotion_dossier_ref = _latest_champion_field(
            conn,
            "promotion_dossier_ref",
            columns=columns,
        )

    promoted_at_count = 0
    if "promoted_at" in columns:
        promoted_at_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM champions "
                "WHERE promoted_at IS NOT NULL AND promoted_at != ''"
            ).fetchone()[0]
            or 0
        )

    return {
        "table_present": True,
        "count": count,
        "max_version": int(max_version) if max_version is not None else None,
        "max_weight_revision": (
            int(max_weight_revision) if max_weight_revision is not None else None
        ),
        "versions": versions,
        "promotion_experiment_count": promotion_experiment_count,
        "promotion_dossier_count": promotion_dossier_count,
        "promoted_at_count": promoted_at_count,
        "latest_promotion_experiment_id": _string_or_none(
            latest_promotion_experiment_id
        ),
        "latest_promotion_dossier_ref": _string_or_none(latest_promotion_dossier_ref),
    }


def _latest_champion_field(
    conn: sqlite3.Connection,
    field: str,
    *,
    columns: set[str],
) -> Any:
    order = "version DESC"
    if "weight_revision" in columns:
        order += ", weight_revision DESC"
    row = conn.execute(
        f"SELECT {field} FROM champions "
        f"WHERE {field} IS NOT NULL AND {field} != '' "
        f"ORDER BY {order} LIMIT 1"
    ).fetchone()
    return row[0] if row else None


def _group_counts(
    conn: sqlite3.Connection,
    table: str,
    column: str,
) -> dict[str, int]:
    if column not in _columns(conn, table):
        return {}
    rows = conn.execute(
        f"SELECT {column}, COUNT(*) FROM {table} "
        f"WHERE {column} IS NOT NULL AND {column} != '' GROUP BY {column}"
    ).fetchall()
    return {str(key): int(count) for key, count in rows}


def _count_where(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    value: str,
) -> int:
    if table not in _tables(conn) or column not in _columns(conn, table):
        return 0
    return int(
        conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {column} = ?",
            (value,),
        ).fetchone()[0]
        or 0
    )


def _merge_branch_counts(
    branches: list[dict[str, Any]],
    *,
    session_counts: Counter[str],
    trace_counts: Counter[str],
) -> list[dict[str, Any]]:
    by_id = {branch["branch_id"]: dict(branch) for branch in branches}
    for branch_id in set(session_counts) | set(trace_counts):
        if branch_id not in by_id:
            by_id[branch_id] = {
                "branch_id": branch_id,
                "state": None,
                "lineage_id": branch_id,
                "base_champion_hash": None,
                "current_code_hash": None,
                "best_quality_checkpoint_id": None,
                "last_valid_checkpoint_id": None,
                "rollback_count": 0,
                "failure_codes": [],
                "hypothesis_count": 0,
                "event_count": 0,
                "session_count": 0,
                "trace_count": 0,
            }
        by_id[branch_id]["session_count"] = int(session_counts.get(branch_id, 0))
        by_id[branch_id]["trace_count"] = int(trace_counts.get(branch_id, 0))
    return [by_id[key] for key in sorted(by_id)]
