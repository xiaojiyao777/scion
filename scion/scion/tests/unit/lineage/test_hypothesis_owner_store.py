from __future__ import annotations

import ast
import dataclasses
import inspect
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from scion.core.models import HypothesisRecord
from scion.lineage import hypothesis_owner_store as subject
from scion.lineage import owner_transaction as owner
from scion.lineage import sqlite_connection as sqlite_boundary
from scion.lineage.durable_owner import (
    DurableOwnerIntegrityError,
    OwnerAlreadyExists,
    OwnerPayloadConflict,
    OwnerRevisionConflict,
    RevisionedHypothesisRecord,
    hypothesis_storage_payload,
)


@dataclass(frozen=True)
class _Harness:
    path: Path
    authority: sqlite_boundary.CampaignDatabaseAuthority
    store: subject.HypothesisStore
    initial: HypothesisRecord
    token: RevisionedHypothesisRecord


def _hypothesis(
    *,
    hypothesis_id: str = "hypothesis-1",
    branch_id: str = "branch-1",
    status: str = "active",
    proposal_digest: str = "d" * 64,
) -> HypothesisRecord:
    return HypothesisRecord(
        hypothesis_id=hypothesis_id,
        branch_id=branch_id,
        change_locus="local_search",
        action="modify",
        status=status,
        target_file="operators/local_search.py",
        parent_hypothesis_id=None,
        suggested_weight=0.5,
        hypothesis_text="Use a bounded neighborhood.",
        created_at=datetime(2026, 7, 16, 1, 2, 5),
        base_champion_version=7,
        family_id="local-search",
        family_source="manual",
        taxonomy_version="v1",
        predicted_direction="improve",
        proposal_digest=proposal_digest,
    )


def _harness(
    tmp_path: Path,
    *,
    include_initial: bool = True,
    row_overrides: dict[str, Any] | None = None,
) -> _Harness:
    path = tmp_path / "hypothesis-owner-store.db"
    connection = sqlite_boundary._connect_sqlite(path)
    initial = _hypothesis()
    token = RevisionedHypothesisRecord.from_value(initial, owner_revision=0)
    try:
        connection.execute(
            """
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
        )
        if include_initial:
            values = hypothesis_storage_payload(initial)
            values["owner_revision"] = 0
            values["owner_protocol_generation"] = "durable-owner.v1"
            values.update(row_overrides or {})
            connection.execute(
                """
                INSERT INTO hypotheses (
                    hypothesis_id, branch_id, change_locus, action, status,
                    target_file, parent_hypothesis_id, suggested_weight,
                    hypothesis_text, created_at, base_champion_version,
                    family_id, family_source, taxonomy_version,
                    predicted_direction, proposal_digest, owner_revision,
                    owner_protocol_generation
                ) VALUES (
                    :hypothesis_id, :branch_id, :change_locus, :action, :status,
                    :target_file, :parent_hypothesis_id, :suggested_weight,
                    :hypothesis_text, :created_at, :base_champion_version,
                    :family_id, :family_source, :taxonomy_version,
                    :predicted_direction, :proposal_digest, :owner_revision,
                    :owner_protocol_generation
                )
                """,
                values,
            )
        connection.commit()
    finally:
        connection.close()
    authority = sqlite_boundary._issue_test_campaign_database_authority(path)
    return _Harness(
        path=path,
        authority=authority,
        store=subject.HypothesisStore(authority),
        initial=initial,
        token=token,
    )


def _raw_row(harness: _Harness) -> sqlite3.Row | None:
    connection = sqlite_boundary._connect_sqlite(harness.path)
    try:
        return connection.execute(
            "SELECT * FROM hypotheses WHERE hypothesis_id = ?",
            (harness.initial.hypothesis_id,),
        ).fetchone()
    finally:
        connection.close()


def _attach(
    transaction: sqlite_boundary.ImmediateTransaction,
    harness: _Harness,
) -> object:
    return owner._attach_owner_receipt_ledger(transaction, harness.authority)


def _insert_hypothesis(
    harness: _Harness,
    hypothesis: HypothesisRecord,
    *,
    owner_revision: int,
) -> RevisionedHypothesisRecord:
    token = RevisionedHypothesisRecord.from_value(hypothesis, owner_revision)
    connection = sqlite_boundary._connect_sqlite(harness.path)
    try:
        connection.execute(
            subject._HYPOTHESIS_INSERT_SQL,
            subject._write_parameters(token),
        )
        connection.commit()
    finally:
        connection.close()
    return token


def _commit_mutation(
    ledger: object,
    receipt: owner.OwnerMutationReceipt,
) -> None:
    owner._consume_hypothesis_mutation_receipt(ledger, receipt)  # type: ignore[arg-type]
    owner._seal_owner_receipt_ledger(ledger, (receipt,))  # type: ignore[arg-type]


def _commit_creation(
    ledger: object,
    receipt: owner.OwnerCreationReceipt,
) -> None:
    owner._consume_hypothesis_creation_receipt(ledger, receipt)  # type: ignore[arg-type]
    owner._seal_owner_receipt_ledger(ledger, (receipt,))  # type: ignore[arg-type]


def test_registry_snapshot_readers_return_single_inventory_and_branch_bundle(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    second_value = dataclasses.replace(
        _hypothesis(hypothesis_id="hypothesis-2"),
        created_at=datetime(2026, 7, 16, 1, 3, 5),
        status="validated",
    )
    third_value = dataclasses.replace(
        _hypothesis(hypothesis_id="hypothesis-3", branch_id="branch-2"),
        created_at=datetime(2026, 7, 16, 1, 4, 5),
    )
    second = _insert_hypothesis(harness, second_value, owner_revision=2)
    third = _insert_hypothesis(harness, third_value, owner_revision=4)

    with sqlite_boundary._independent_authority_read_snapshot(
        harness.authority
    ) as snapshot:
        assert harness.store._load_revisioned_hypothesis_from_snapshot(
            snapshot,
            harness.token.hypothesis_id,
        ) == harness.token
        assert (
            harness.store._load_revisioned_hypothesis_from_snapshot(
                snapshot,
                "hypothesis-missing",
            )
            is None
        )
        assert harness.store._load_all_revisioned_hypotheses_from_snapshot(
            snapshot
        ) == (harness.token, second, third)
        assert harness.store._load_branch_hypotheses_from_snapshot(
            snapshot,
            "branch-1",
        ) == (harness.token, second)
        assert harness.store._load_branch_hypotheses_from_snapshot(
            snapshot,
            "branch-empty",
        ) == ()

    with pytest.raises(sqlite_boundary.InactiveImmediateTransactionError):
        harness.store._load_revisioned_hypothesis_from_snapshot(
            snapshot,
            harness.token.hypothesis_id,
        )


def test_registry_snapshot_reader_reuses_strict_complete_decoder(
    tmp_path: Path,
) -> None:
    harness = _harness(
        tmp_path,
        row_overrides={"proposal_digest": "not-a-digest"},
    )
    with sqlite_boundary._independent_authority_read_snapshot(
        harness.authority
    ) as snapshot:
        with pytest.raises(DurableOwnerIntegrityError):
            harness.store._load_all_revisioned_hypotheses_from_snapshot(snapshot)


def test_complete_read_and_cas_round_trip_binds_proposal_digest(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        ledger = _attach(transaction, harness)
        loaded = harness.store.load_revisioned_in(
            transaction,
            harness.token.hypothesis_id,
        )
        assert loaded == harness.token
        assert loaded is not None
        target = dataclasses.replace(
            loaded.value(),
            status="validated",
            proposal_digest="e" * 64,
        )
        receipt = harness.store.compare_and_swap_in(transaction, loaded, target)
        committed = harness.store.load_revisioned_in(
            transaction,
            harness.token.hypothesis_id,
        )
        assert committed == RevisionedHypothesisRecord.from_value(target, 1)
        _commit_mutation(ledger, receipt)

    row = _raw_row(harness)
    assert row is not None
    assert row["status"] == "validated"
    assert row["proposal_digest"] == "e" * 64
    assert row["owner_revision"] == 1
    assert row["owner_protocol_generation"] == "durable-owner.v1"


def test_insert_once_round_trip_writes_complete_revision_zero_owner(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path, include_initial=False)
    hypothesis = _hypothesis(hypothesis_id="hypothesis-created")
    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        ledger = _attach(transaction, harness)
        assert (
            harness.store.load_revisioned_in(transaction, hypothesis.hypothesis_id)
            is None
        )
        receipt = harness.store.insert_once_in(transaction, hypothesis)
        committed = harness.store.load_revisioned_in(
            transaction,
            hypothesis.hypothesis_id,
        )
        assert committed == RevisionedHypothesisRecord.from_value(hypothesis, 0)
        _commit_creation(ledger, receipt)

    connection = sqlite_boundary._connect_sqlite(harness.path)
    try:
        row = connection.execute(
            "SELECT * FROM hypotheses WHERE hypothesis_id = ?",
            (hypothesis.hypothesis_id,),
        ).fetchone()
    finally:
        connection.close()
    assert row is not None
    assert tuple(row.keys()) == subject._HYPOTHESIS_COLUMNS
    assert row["proposal_digest"] == hypothesis.proposal_digest
    assert row["owner_revision"] == 0


def test_same_revision_semantic_drift_rejects_before_write(tmp_path: Path) -> None:
    harness = _harness(tmp_path, row_overrides={"proposal_digest": "e" * 64})
    target = dataclasses.replace(harness.initial, status="validated")
    with pytest.raises(OwnerPayloadConflict, match="payload differs"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = _attach(transaction, harness)
            harness.store.compare_and_swap_in(transaction, harness.token, target)

    row = _raw_row(harness)
    assert row is not None
    assert row["owner_revision"] == 0
    assert row["status"] == "active"
    assert row["proposal_digest"] == "e" * 64


def test_stale_revision_is_distinct_from_same_revision_payload_drift(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path, row_overrides={"owner_revision": 1})
    target = dataclasses.replace(harness.initial, status="validated")
    with pytest.raises(OwnerRevisionConflict):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = _attach(transaction, harness)
            harness.store.compare_and_swap_in(transaction, harness.token, target)


def test_target_cannot_move_hypothesis_between_branches(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    target = dataclasses.replace(
        harness.initial,
        branch_id="branch-2",
        status="validated",
    )
    with pytest.raises(OwnerPayloadConflict, match="move between Branches"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = _attach(transaction, harness)
            harness.store.compare_and_swap_in(transaction, harness.token, target)
    row = _raw_row(harness)
    assert row is not None
    assert row["branch_id"] == "branch-1"
    assert row["owner_revision"] == 0


def test_authoritative_reread_rejects_actual_sql_branch_movement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    target = dataclasses.replace(harness.initial, status="validated")
    monkeypatch.setattr(
        subject,
        "_HYPOTHESIS_CAS_SQL",
        """
        UPDATE hypotheses
        SET branch_id = 'branch-2',
            status = :status,
            owner_revision = :target_revision
        WHERE hypothesis_id = :hypothesis_id
          AND owner_revision = :expected_revision
        """,
    )
    with pytest.raises(DurableOwnerIntegrityError, match="post-write token"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = _attach(transaction, harness)
            harness.store.compare_and_swap_in(transaction, harness.token, target)

    row = _raw_row(harness)
    assert row is not None
    assert row["branch_id"] == "branch-1"
    assert row["owner_revision"] == 0


def test_authoritative_reread_rejects_post_write_payload_digest_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    target = dataclasses.replace(harness.initial, status="validated")
    monkeypatch.setattr(
        subject,
        "_HYPOTHESIS_CAS_SQL",
        """
        UPDATE hypotheses
        SET status = :status,
            proposal_digest = 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
            owner_revision = :target_revision
        WHERE hypothesis_id = :hypothesis_id
          AND branch_id = :branch_id
          AND owner_revision = :expected_revision
        """,
    )
    with pytest.raises(DurableOwnerIntegrityError, match="post-write token"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = _attach(transaction, harness)
            harness.store.compare_and_swap_in(transaction, harness.token, target)

    row = _raw_row(harness)
    assert row is not None
    assert row["proposal_digest"] == "d" * 64
    assert row["owner_revision"] == 0


def test_target_mutation_after_token_construction_cannot_change_committed_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    target = dataclasses.replace(harness.initial, status="validated")
    original_execute = owner._execute_hypothesis_owner_update

    def _mutating_execute(*args: Any, **kwargs: Any) -> Any:
        target.status = "caller-mutated"
        return original_execute(*args, **kwargs)

    monkeypatch.setattr(owner, "_execute_hypothesis_owner_update", _mutating_execute)
    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        ledger = _attach(transaction, harness)
        receipt = harness.store.compare_and_swap_in(
            transaction,
            harness.token,
            target,
        )
        committed = harness.store.load_revisioned_in(
            transaction,
            harness.token.hypothesis_id,
        )
        assert committed is not None
        assert committed.value().status == "validated"
        assert target.status == "caller-mutated"
        _commit_mutation(ledger, receipt)


def test_zero_row_cas_is_integrity_failure_and_rolls_back(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    target = dataclasses.replace(harness.initial, status="validated")
    original = subject._HYPOTHESIS_CAS_SQL
    subject._HYPOTHESIS_CAS_SQL = original + " AND owner_revision = -1"
    try:
        with pytest.raises(DurableOwnerIntegrityError, match="changed zero rows"):
            with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
                ledger = _attach(transaction, harness)
                harness.store.compare_and_swap_in(transaction, harness.token, target)
    finally:
        subject._HYPOTHESIS_CAS_SQL = original
    row = _raw_row(harness)
    assert row is not None
    assert row["status"] == "active"
    assert row["owner_revision"] == 0


@pytest.mark.parametrize("status", ["active", "different"])
def test_duplicate_insert_never_replaces_equal_or_drifted_owner(
    tmp_path: Path,
    status: str,
) -> None:
    harness = _harness(tmp_path)
    duplicate = dataclasses.replace(harness.initial, status=status)
    with pytest.raises(OwnerAlreadyExists):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = _attach(transaction, harness)
            harness.store.insert_once_in(transaction, duplicate)
    row = _raw_row(harness)
    assert row is not None
    assert row["status"] == "active"
    assert row["owner_revision"] == 0


@pytest.mark.parametrize(
    "row_overrides",
    [
        {"owner_protocol_generation": "durable-owner.v2"},
        {"owner_revision": "not-an-integer"},
        {"created_at": "2026-07-16 01:02:05"},
        {"proposal_digest": "not-a-digest"},
        {"branch_id": " branch-1"},
    ],
)
def test_complete_row_decoder_rejects_malformed_storage(
    tmp_path: Path,
    row_overrides: dict[str, Any],
) -> None:
    harness = _harness(tmp_path, row_overrides=row_overrides)
    with pytest.raises(DurableOwnerIntegrityError):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = _attach(transaction, harness)
            harness.store.load_revisioned_in(
                transaction,
                harness.token.hypothesis_id,
            )


def test_successful_write_without_sealed_receipt_rolls_back(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    target = dataclasses.replace(harness.initial, status="validated")
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = _attach(transaction, harness)
            harness.store.compare_and_swap_in(transaction, harness.token, target)

    row = _raw_row(harness)
    assert row is not None
    assert row["status"] == "active"
    assert row["owner_revision"] == 0


def test_public_api_hides_ledger_sql_parameters_facts_and_committed_tokens() -> None:
    signatures = {
        name: tuple(inspect.signature(getattr(subject.HypothesisStore, name)).parameters)
        for name in ("load_revisioned_in", "compare_and_swap_in", "insert_once_in")
    }
    assert signatures == {
        "load_revisioned_in": ("self", "transaction", "hypothesis_id"),
        "compare_and_swap_in": ("self", "transaction", "expected", "target"),
        "insert_once_in": ("self", "transaction", "hypothesis"),
    }
    forbidden = {"ledger", "sql", "parameters", "write_fact", "committed_token"}
    assert all(forbidden.isdisjoint(parameters) for parameters in signatures.values())
    assert tuple(
        inspect.signature(
            subject.HypothesisStore._load_revisioned_hypothesis_from_snapshot
        ).parameters
    ) == ("self", "snapshot", "hypothesis_id")
    assert tuple(
        inspect.signature(
            subject.HypothesisStore._load_all_revisioned_hypotheses_from_snapshot
        ).parameters
    ) == ("self", "snapshot")
    assert tuple(
        inspect.signature(
            subject.HypothesisStore._load_branch_hypotheses_from_snapshot
        ).parameters
    ) == ("self", "snapshot", "branch_id")


def test_store_sql_is_fixed_complete_and_avoids_replace_surfaces() -> None:
    source_path = Path(subject.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    constants: dict[str, str] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            constants[node.target.id] = node.value.value
    sql = {
        name: constants[name]
        for name in (
            "_HYPOTHESIS_SELECT_SQL",
            "_HYPOTHESIS_SELECT_ALL_SQL",
            "_HYPOTHESIS_SELECT_BRANCH_SQL",
            "_HYPOTHESIS_INSERT_SQL",
            "_HYPOTHESIS_CAS_SQL",
        )
    }
    for statement in sql.values():
        upper = statement.upper()
        assert "REPLACE" not in upper
        assert "INSERT OR" not in upper
        assert "UPDATE OR" not in upper
        assert "ON CONFLICT" not in upper
        assert "DELETE" not in upper
    assert "payload_sha256" not in "\n".join(sql.values())
    assert "branch_id =" not in sql["_HYPOTHESIS_CAS_SQL"].split("WHERE", 1)[0]
    for column in subject._HYPOTHESIS_COLUMNS:
        assert column in sql["_HYPOTHESIS_SELECT_SQL"]
        assert column in sql["_HYPOTHESIS_SELECT_ALL_SQL"]
        assert column in sql["_HYPOTHESIS_SELECT_BRANCH_SQL"]
        assert column in sql["_HYPOTHESIS_INSERT_SQL"]
    assert "ORDER BY hypothesis_id ASC" in sql["_HYPOTHESIS_SELECT_ALL_SQL"]
    assert "ORDER BY hypothesis_id ASC" in sql["_HYPOTHESIS_SELECT_BRANCH_SQL"]

    expected_sql_arguments = {
        "_execute_hypothesis_owner_update": "_HYPOTHESIS_CAS_SQL",
        "_execute_hypothesis_owner_insert": "_HYPOTHESIS_INSERT_SQL",
    }
    found: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        name = node.func.attr
        if name in expected_sql_arguments:
            argument = node.args[3]
            assert isinstance(argument, ast.Name)
            found[name] = argument.id
    assert found == expected_sql_arguments
    assert not any(
        isinstance(node, (ast.JoinedStr, ast.BinOp))
        for node in ast.walk(tree)
        if isinstance(node, (ast.JoinedStr, ast.BinOp))
        and any(
            isinstance(parent, ast.AnnAssign) and parent.value is node
            for parent in tree.body
        )
    )
    assert "executemany" not in source_path.read_text(encoding="utf-8")
