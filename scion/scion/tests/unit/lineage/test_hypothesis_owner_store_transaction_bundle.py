from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scion.core.models import HypothesisRecord
from scion.lineage import hypothesis_owner_store as subject
from scion.lineage import sqlite_connection
from scion.lineage.durable_owner import (
    DurableOwnerIntegrityError,
    RevisionedHypothesisRecord,
)


_CREATE_HYPOTHESES_SQL = """
CREATE TABLE hypotheses (
    hypothesis_id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL,
    change_locus TEXT NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    target_file TEXT,
    parent_hypothesis_id TEXT,
    suggested_weight REAL,
    hypothesis_text TEXT,
    created_at TEXT NOT NULL,
    base_champion_version INTEGER NOT NULL,
    family_id TEXT,
    family_source TEXT,
    taxonomy_version TEXT,
    predicted_direction TEXT NOT NULL,
    proposal_digest TEXT,
    owner_revision INTEGER NOT NULL,
    owner_protocol_generation TEXT NOT NULL
)
"""


def _hypothesis(hypothesis_id: str, branch_id: str) -> HypothesisRecord:
    return HypothesisRecord(
        hypothesis_id=hypothesis_id,
        branch_id=branch_id,
        change_locus="local_search",
        action="modify",
        status="active",
        target_file="operators/local_search.py",
        parent_hypothesis_id=None,
        suggested_weight=0.5,
        hypothesis_text="Use a bounded neighborhood.",
        created_at=datetime(2026, 7, 17, 1, 2, 3, tzinfo=timezone.utc),
        base_champion_version=7,
        family_id="local-search",
        family_source="manual",
        taxonomy_version="v1",
        predicted_direction="improve",
        proposal_digest="d" * 64,
    )


def _database(
    path: Path,
    hypotheses: tuple[tuple[HypothesisRecord, int], ...] = (),
) -> tuple[
    sqlite_connection.CampaignDatabaseAuthority,
    subject.HypothesisStore,
]:
    connection = sqlite_connection._connect_sqlite(path)
    try:
        connection.execute(_CREATE_HYPOTHESES_SQL)
        for hypothesis, revision in hypotheses:
            token = RevisionedHypothesisRecord.from_value(hypothesis, revision)
            connection.execute(
                subject._HYPOTHESIS_INSERT_SQL,
                subject._write_parameters(token),
            )
        connection.commit()
    finally:
        connection.close()
    authority = sqlite_connection._issue_test_campaign_database_authority(path)
    return authority, subject.HypothesisStore(authority)


def test_transaction_reader_returns_complete_sorted_branch_bundle(
    tmp_path: Path,
) -> None:
    first = _hypothesis("hypothesis-a", "branch-1")
    second = dataclasses.replace(
        _hypothesis("hypothesis-b", "branch-1"),
        status="validated",
        proposal_digest="e" * 64,
    )
    other = _hypothesis("hypothesis-c", "branch-2")
    authority, store = _database(
        tmp_path / "bundle.db",
        ((second, 2), (other, 4), (first, 0)),
    )

    with sqlite_connection.immediate_transaction(authority) as transaction:
        assert store._load_branch_hypotheses_in(transaction, "branch-1") == (
            RevisionedHypothesisRecord.from_value(first, 0),
            RevisionedHypothesisRecord.from_value(second, 2),
        )


def test_transaction_reader_returns_empty_complete_bundle(tmp_path: Path) -> None:
    authority, store = _database(
        tmp_path / "empty.db",
        ((_hypothesis("hypothesis-a", "branch-1"), 0),),
    )

    with sqlite_connection.immediate_transaction(authority) as transaction:
        assert store._load_branch_hypotheses_in(transaction, "branch-empty") == ()


def test_transaction_reader_rejects_noncanonical_owner_row(tmp_path: Path) -> None:
    path = tmp_path / "malformed.db"
    authority, store = _database(
        path,
        ((_hypothesis("hypothesis-a", "branch-1"), 0),),
    )
    connection = sqlite_connection._connect_sqlite(path)
    try:
        connection.execute(
            "UPDATE hypotheses SET proposal_digest = ? WHERE hypothesis_id = ?",
            ("not-a-digest", "hypothesis-a"),
        )
        connection.commit()
    finally:
        connection.close()

    with sqlite_connection.immediate_transaction(authority) as transaction:
        with pytest.raises(DurableOwnerIntegrityError, match="malformed semantic"):
            store._load_branch_hypotheses_in(transaction, "branch-1")


def test_transaction_reader_rejects_wrong_authority_and_inactive_transaction(
    tmp_path: Path,
) -> None:
    authority, store = _database(tmp_path / "owner.db")
    other_authority, _ = _database(tmp_path / "other.db")

    with sqlite_connection.immediate_transaction(other_authority) as wrong:
        with pytest.raises(
            sqlite_connection.InvalidImmediateTransactionError,
            match="another authority",
        ):
            store._load_branch_hypotheses_in(wrong, "branch-1")

    with sqlite_connection.immediate_transaction(authority) as transaction:
        assert store._load_branch_hypotheses_in(transaction, "branch-1") == ()

    with pytest.raises(sqlite_connection.InactiveImmediateTransactionError):
        store._load_branch_hypotheses_in(transaction, "branch-1")


def test_transaction_reader_rejects_cross_branch_and_duplicate_query_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority, store = _database(
        tmp_path / "integrity.db",
        (
            (_hypothesis("hypothesis-a", "branch-1"), 0),
            (_hypothesis("hypothesis-b", "branch-2"), 0),
        ),
    )

    monkeypatch.setattr(
        subject,
        "_HYPOTHESIS_SELECT_BRANCH_SQL",
        subject._HYPOTHESIS_SELECT_ALL_SQL,
    )
    with sqlite_connection.immediate_transaction(authority) as transaction:
        with pytest.raises(DurableOwnerIntegrityError, match="another Branch"):
            store._load_branch_hypotheses_in(transaction, "branch-1")

    monkeypatch.setattr(
        subject,
        "_HYPOTHESIS_SELECT_BRANCH_SQL",
        subject._HYPOTHESIS_SELECT_ALL_SQL.replace(
            "ORDER BY hypothesis_id ASC",
            "UNION ALL "
            + subject._HYPOTHESIS_SELECT_ALL_SQL.split("FROM hypotheses", 1)[0]
            + "FROM hypotheses ORDER BY hypothesis_id ASC",
        ),
    )
    with sqlite_connection.immediate_transaction(authority) as transaction:
        with pytest.raises(DurableOwnerIntegrityError, match="duplicate"):
            store._load_branch_hypotheses_in(transaction, "branch-1")
