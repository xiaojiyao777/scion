from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from scion.lineage import champion_store as subject
from scion.lineage import branch_owner_store
from scion.lineage import owner_transaction as owner
from scion.lineage import sqlite_connection as sqlite_boundary
from scion.core.models import Branch, BranchState
from scion.lineage.durable_owner import (
    DurableOwnerIntegrityError,
    RevisionedBranchRecord,
)

_CREATE_SCHEMA = """
CREATE TABLE champions (
    version INTEGER NOT NULL,
    weight_revision INTEGER NOT NULL,
    operator_pool_json TEXT NOT NULL,
    solver_config_hash TEXT NOT NULL,
    code_snapshot_path TEXT NOT NULL,
    code_snapshot_hash TEXT NOT NULL,
    promotion_experiment_id TEXT,
    promotion_dossier_ref TEXT,
    promoted_at TEXT,
    PRIMARY KEY (version, weight_revision)
)
"""


def _operator_json(*, weight: object = 1.25) -> str:
    return json.dumps(
        {
            "relocate": {
                "name": "relocate",
                "file_path": "operators/relocate.py",
                "category": "local_search",
                "weight": weight,
                "class_name": "RelocateOperator",
            }
        },
        separators=(",", ":"),
    )


def _insert(
    connection: sqlite3.Connection,
    *,
    version: object = 7,
    weight_revision: object = 2,
    operator_pool_json: object | None = None,
    solver_config_hash: object = "legacy-short-config-hash",
) -> None:
    connection.execute(
        """
        INSERT INTO champions (
            version, weight_revision, operator_pool_json, solver_config_hash,
            code_snapshot_path, code_snapshot_hash,
            promotion_experiment_id, promotion_dossier_ref, promoted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            version,
            weight_revision,
            _operator_json() if operator_pool_json is None else operator_pool_json,
            solver_config_hash,
            "/snapshots/v7",
            "legacy-short-code-hash",
            "experiment-7",
            "dossier-7",
            "2026-07-16T01:02:03",
        ),
    )


def _harness(tmp_path: Path) -> tuple[
    Path,
    sqlite_boundary.CampaignDatabaseAuthority,
    subject.ConnectionScopedChampionStore,
]:
    path = tmp_path / "champion.db"
    connection = sqlite_boundary._connect_sqlite(path)
    try:
        connection.execute(_CREATE_SCHEMA)
        _insert(connection)
        connection.commit()
    finally:
        connection.close()
    authority = sqlite_boundary._issue_test_campaign_database_authority(path)
    return path, authority, subject.ConnectionScopedChampionStore(authority)


def _create_branch_schema(path: Path) -> None:
    connection = sqlite_boundary._connect_sqlite(path)
    try:
        connection.executescript("""
            CREATE TABLE branches (
                branch_id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                base_champion_id INTEGER NOT NULL,
                base_champion_hash TEXT NOT NULL,
                lineage_id TEXT NOT NULL,
                current_code_hash TEXT,
                last_clean_code_hash TEXT,
                screening_expand_count INTEGER NOT NULL,
                validation_expand_count INTEGER NOT NULL,
                failure_codes TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                direction TEXT,
                weight_revision INTEGER NOT NULL,
                branch_code_status TEXT NOT NULL,
                branch_evidence_summary_json TEXT NOT NULL,
                infra_block_count INTEGER NOT NULL,
                owner_revision INTEGER NOT NULL,
                owner_protocol_generation TEXT NOT NULL
            )
            """)
        connection.commit()
    finally:
        connection.close()


def _branch(*, branch_id: str = "branch-created") -> Branch:
    return Branch(
        branch_id=branch_id,
        state=BranchState.NEW,
        base_champion_id=7,
        base_champion_hash="legacy-short-code-hash",
        lineage_id=branch_id,
        current_code_hash=None,
        last_clean_code_hash=None,
        screening_expand_count=0,
        validation_expand_count=0,
        failure_codes=[],
        created_at=datetime(2026, 7, 16, 1, 2, 3),
        updated_at=datetime(2026, 7, 16, 1, 2, 3),
        direction=None,
        weight_revision=2,
        branch_code_status="clean",
        branch_evidence_summary={},
        infra_block_count=0,
    )


def _load(
    authority: sqlite_boundary.CampaignDatabaseAuthority,
    store: subject.ConnectionScopedChampionStore,
) -> subject.StoredChampionRecord | None:
    with sqlite_boundary.immediate_transaction(authority) as transaction:
        return store.load_current_in(transaction)


def _load_exact(
    authority: sqlite_boundary.CampaignDatabaseAuthority,
    store: subject.ConnectionScopedChampionStore,
    version: int,
    weight_revision: int,
) -> subject.StoredChampionRecord | None:
    with sqlite_boundary._independent_authority_read_snapshot(authority) as snapshot:
        return store._load_exact_from_snapshot(
            snapshot,
            version,
            weight_revision,
        )


def test_strict_current_load_returns_exact_storage_token_and_detached_values(
    tmp_path: Path,
) -> None:
    path, authority, store = _harness(tmp_path)
    connection = sqlite_boundary._connect_sqlite(path)
    try:
        _insert(connection, version=7, weight_revision=3)
        _insert(connection, version=8, weight_revision=0)
        connection.commit()
    finally:
        connection.close()

    token = _load(authority, store)
    assert token is not None
    assert (token.version, token.weight_revision) == (8, 0)
    assert (
        token.storage_sha256
        == hashlib.sha256(token.canonical_storage_payload_json).hexdigest()
    )
    first = token.value()
    second = token.value()
    assert first == second
    assert first is not second
    assert first.operator_pool is not second.operator_pool
    assert first.operator_pool["relocate"] is not second.operator_pool["relocate"]

    first.operator_pool["relocate"].weight = 99.0
    first.operator_pool["new"] = first.operator_pool["relocate"]
    assert token.value().operator_pool["relocate"].weight == 1.25
    assert "new" not in token.value().operator_pool


def test_storage_digest_preserves_semantically_equivalent_raw_operator_json(
    tmp_path: Path,
) -> None:
    _, authority, store = _harness(tmp_path)
    compact = _load(authority, store)
    assert compact is not None

    path = tmp_path / "spaced.db"
    connection = sqlite_boundary._connect_sqlite(path)
    try:
        connection.execute(_CREATE_SCHEMA)
        parsed = json.loads(_operator_json())
        _insert(connection, operator_pool_json=json.dumps(parsed, indent=2))
        connection.commit()
    finally:
        connection.close()
    spaced_authority = sqlite_boundary._issue_test_campaign_database_authority(path)
    spaced = _load(
        spaced_authority,
        subject.ConnectionScopedChampionStore(spaced_authority),
    )
    assert spaced is not None
    assert compact.value() == spaced.value()
    assert (
        compact.canonical_storage_payload_json != spaced.canonical_storage_payload_json
    )
    assert compact.storage_sha256 != spaced.storage_sha256


def test_snapshot_reader_uses_same_strict_token_and_expires_with_snapshot(
    tmp_path: Path,
) -> None:
    _, authority, store = _harness(tmp_path)
    expected = _load(authority, store)
    with sqlite_boundary._independent_authority_read_snapshot(authority) as snapshot:
        assert store._load_current_from_snapshot(snapshot) == expected

    with pytest.raises(sqlite_boundary.InactiveImmediateTransactionError):
        store._load_current_from_snapshot(snapshot)


def test_exact_snapshot_reader_loads_captured_historical_revision_not_current(
    tmp_path: Path,
) -> None:
    path, authority, store = _harness(tmp_path)
    connection = sqlite_boundary._connect_sqlite(path)
    try:
        _insert(connection, version=7, weight_revision=3)
        _insert(connection, version=8, weight_revision=0)
        connection.commit()
    finally:
        connection.close()

    exact = _load_exact(authority, store, 7, 2)
    current = _load(authority, store)

    assert exact is not None
    assert current is not None
    assert (exact.version, exact.weight_revision) == (7, 2)
    assert (current.version, current.weight_revision) == (8, 0)
    assert exact == _load_exact(authority, store, 7, 2)
    assert _load_exact(authority, store, 99, 0) is None


@pytest.mark.parametrize(
    ("version", "weight_revision", "message"),
    [
        (True, 0, "SQLite integer"),
        (-1, 0, "non-negative"),
        (7, True, "SQLite integer"),
        (7, -1, "non-negative"),
    ],
)
def test_exact_snapshot_reader_rejects_non_exact_identity_parameters(
    tmp_path: Path,
    version: object,
    weight_revision: object,
    message: str,
) -> None:
    _, authority, store = _harness(tmp_path)
    with sqlite_boundary._independent_authority_read_snapshot(authority) as snapshot:
        with pytest.raises(DurableOwnerIntegrityError, match=message):
            store._load_exact_from_snapshot(  # type: ignore[arg-type]
                snapshot,
                version,
                weight_revision,
            )


def test_exact_snapshot_reader_rejects_duplicate_storage_facts(
    tmp_path: Path,
) -> None:
    path = tmp_path / "duplicate-champion.db"
    connection = sqlite_boundary._connect_sqlite(path)
    try:
        connection.execute(
            _CREATE_SCHEMA.replace(
                ",\n    PRIMARY KEY (version, weight_revision)",
                "",
            )
        )
        _insert(connection)
        _insert(connection)
        connection.commit()
    finally:
        connection.close()
    authority = sqlite_boundary._issue_test_campaign_database_authority(path)
    store = subject.ConnectionScopedChampionStore(authority)

    with pytest.raises(DurableOwnerIntegrityError, match="more than one"):
        _load_exact(authority, store, 7, 2)


@pytest.mark.parametrize(
    ("operator_pool_json", "message"),
    [
        (
            '{"relocate":{"name":"a","name":"b","file_path":"x",'
            '"category":"c","weight":1,"class_name":"C"}}',
            "duplicate object key",
        ),
        (
            '{"relocate":{"name":"a","file_path":"x","category":"c",'
            '"weight":NaN,"class_name":"C"}}',
            "non-finite constant",
        ),
        (
            '{"relocate":{"name":"a","file_path":"x","category":"c",'
            '"weight":true,"class_name":"C"}}',
            "finite number",
        ),
        (
            '{"relocate":{"name":"a","file_path":"x","category":"c",'
            '"weight":' + str(10**400) + ',"class_name":"C"}}',
            "finite number",
        ),
        (
            '{"relocate":{"name":"a","file_path":"x","category":"c",'
            '"weight":1,"class_name":"C","extra":1}}',
            "unexpected fields",
        ),
        ("[]", "must contain an object"),
    ],
)
def test_strict_decoder_rejects_invalid_operator_storage(
    tmp_path: Path,
    operator_pool_json: str,
    message: str,
) -> None:
    path, authority, store = _harness(tmp_path)
    connection = sqlite_boundary._connect_sqlite(path)
    try:
        connection.execute(
            "UPDATE champions SET operator_pool_json = ?",
            (operator_pool_json,),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(DurableOwnerIntegrityError, match=message):
        _load(authority, store)


def test_strict_decoder_rejects_sqlite_type_drift(tmp_path: Path) -> None:
    path, authority, store = _harness(tmp_path)
    connection = sqlite_boundary._connect_sqlite(path)
    try:
        connection.execute("UPDATE champions SET version = 'type-drift'")
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(DurableOwnerIntegrityError, match="SQLite integer"):
        _load(authority, store)


def test_token_value_rejects_digest_and_identity_tampering(tmp_path: Path) -> None:
    _, authority, store = _harness(tmp_path)
    token = _load(authority, store)
    assert token is not None

    with pytest.raises(DurableOwnerIntegrityError, match="digest"):
        dataclasses.replace(token, storage_sha256="0" * 64).value()
    with pytest.raises(DurableOwnerIntegrityError, match="identity"):
        dataclasses.replace(token, version=token.version + 1).value()


def test_branch_authorization_binds_champion_transaction_and_outcome_witness(
    tmp_path: Path,
) -> None:
    path, authority, champion_store = _harness(tmp_path)
    _create_branch_schema(path)
    branches = branch_owner_store.BranchStore(authority)
    target = _branch()
    target_token = RevisionedBranchRecord.from_value(target, owner_revision=0)

    with sqlite_boundary.immediate_transaction(authority) as transaction:
        ledger = owner._attach_owner_receipt_ledger(transaction, authority)
        champion = champion_store.load_current_in(transaction)
        assert champion is not None
        authorization = champion_store._authorize_branch_creation_in(
            transaction,
            ledger,
            champion,
            target_token,
        )
        receipt = branches.insert_once_in(transaction, target, authorization)
        outcome_witness = champion_store._complete_branch_creation_in(
            transaction,
            ledger,
            authorization,
            receipt,
        )
        champion_store._require_branch_creation_outcome(
            outcome_witness,
            authorization,
        )
        receipt_witness = owner._consume_branch_creation_receipt(ledger, receipt)
        assert receipt_witness.creation_authorization is authorization
        assert receipt_witness.committed_token == target_token
        owner._seal_owner_receipt_ledger(ledger, (receipt,))

    # The participant's projection remains strongly available for the later
    # post-commit classifier even though the transaction is inactive.
    champion_store._require_branch_creation_outcome(
        outcome_witness,
        authorization,
    )
    champion_store._settle_branch_creation_outcome(
        outcome_witness,
        authorization,
    )
    with pytest.raises(DurableOwnerIntegrityError, match="another authorization"):
        champion_store._require_branch_creation_outcome(
            outcome_witness,
            authorization,
        )
    with pytest.raises(DurableOwnerIntegrityError, match="another authorization"):
        champion_store._settle_branch_creation_outcome(
            outcome_witness,
            authorization,
        )


def test_branch_authorization_rejects_anchor_mismatch_before_registration(
    tmp_path: Path,
) -> None:
    path, authority, champion_store = _harness(tmp_path)
    _create_branch_schema(path)
    target = _branch()
    target.base_champion_hash = "another-hash"
    target_token = RevisionedBranchRecord.from_value(target, owner_revision=0)

    with pytest.raises(DurableOwnerIntegrityError, match="exact champion anchor"):
        with sqlite_boundary.immediate_transaction(authority) as transaction:
            ledger = owner._attach_owner_receipt_ledger(transaction, authority)
            champion = champion_store.load_current_in(transaction)
            assert champion is not None
            champion_store._authorize_branch_creation_in(
                transaction,
                ledger,
                champion,
                target_token,
            )


def test_branch_completion_rejects_non_anchor_champion_drift_and_rolls_back(
    tmp_path: Path,
) -> None:
    path, authority, champion_store = _harness(tmp_path)
    _create_branch_schema(path)
    branches = branch_owner_store.BranchStore(authority)
    target = _branch()
    target_token = RevisionedBranchRecord.from_value(target, owner_revision=0)

    with pytest.raises(DurableOwnerIntegrityError, match="changed before"):
        with sqlite_boundary.immediate_transaction(authority) as transaction:
            ledger = owner._attach_owner_receipt_ledger(transaction, authority)
            champion = champion_store.load_current_in(transaction)
            assert champion is not None
            authorization = champion_store._authorize_branch_creation_in(
                transaction,
                ledger,
                champion,
                target_token,
            )
            receipt = branches.insert_once_in(transaction, target, authorization)
            sqlite_boundary._execute_participant(
                transaction,
                authority,
                "UPDATE champions SET solver_config_hash = ?",
                ("drifted-config-hash",),
            )
            champion_store._complete_branch_creation_in(
                transaction,
                ledger,
                authorization,
                receipt,
            )

    connection = sqlite_boundary._connect_sqlite(path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM branches").fetchone()[0] == 0
        assert (
            connection.execute("SELECT solver_config_hash FROM champions").fetchone()[0]
            == "legacy-short-config-hash"
        )
    finally:
        connection.close()


def test_branch_authorization_rejects_inactive_foreign_ledger(
    tmp_path: Path,
) -> None:
    path, authority, champion_store = _harness(tmp_path)
    _create_branch_schema(path)
    old_ledger: owner._OwnerReceiptLedger
    with pytest.raises(RuntimeError, match="abort old ledger"):
        with sqlite_boundary.immediate_transaction(authority) as first_transaction:
            old_ledger = owner._attach_owner_receipt_ledger(
                first_transaction,
                authority,
            )
            raise RuntimeError("abort old ledger")

    target_token = RevisionedBranchRecord.from_value(_branch(), owner_revision=0)
    with sqlite_boundary.immediate_transaction(authority) as transaction:
        champion = champion_store.load_current_in(transaction)
        assert champion is not None
        with pytest.raises(sqlite_boundary.InactiveImmediateTransactionError):
            champion_store._authorize_branch_creation_in(
                transaction,
                old_ledger,
                champion,
                target_token,
            )


def test_branch_completion_and_outcome_identity_are_one_shot_and_exact(
    tmp_path: Path,
) -> None:
    path, authority, champion_store = _harness(tmp_path)
    _create_branch_schema(path)
    branches = branch_owner_store.BranchStore(authority)
    target = _branch()
    target_token = RevisionedBranchRecord.from_value(target, owner_revision=0)

    with sqlite_boundary.immediate_transaction(authority) as transaction:
        ledger = owner._attach_owner_receipt_ledger(transaction, authority)
        champion = champion_store.load_current_in(transaction)
        assert champion is not None
        authorization = champion_store._authorize_branch_creation_in(
            transaction,
            ledger,
            champion,
            target_token,
        )
        receipt = branches.insert_once_in(transaction, target, authorization)
        outcome_witness = champion_store._complete_branch_creation_in(
            transaction,
            ledger,
            authorization,
            receipt,
        )
        with pytest.raises(DurableOwnerIntegrityError, match="no captured"):
            champion_store._complete_branch_creation_in(
                transaction,
                ledger,
                authorization,
                receipt,
            )
        forged_authorization = object.__new__(owner._OwnerCreationAuthorization)
        with pytest.raises(DurableOwnerIntegrityError, match="another authorization"):
            champion_store._require_branch_creation_outcome(
                outcome_witness,
                forged_authorization,
            )
        owner._consume_branch_creation_receipt(ledger, receipt)
        owner._seal_owner_receipt_ledger(ledger, (receipt,))

    champion_store._discard_branch_creation_outcome(authorization)
    with pytest.raises(DurableOwnerIntegrityError, match="another authorization"):
        champion_store._require_branch_creation_outcome(
            outcome_witness,
            authorization,
        )
    with pytest.raises(DurableOwnerIntegrityError, match="no exact unsettled"):
        champion_store._discard_branch_creation_outcome(authorization)


def test_dormant_participant_contains_no_schema_or_connection_lifecycle() -> None:
    tree = ast.parse(inspect.getsource(subject.ConnectionScopedChampionStore))
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not called_attributes.intersection(
        {"connect", "commit", "rollback", "close", "executescript"}
    )
    source = inspect.getsource(subject.ConnectionScopedChampionStore).upper()
    assert "CREATE TABLE" not in source
    assert "ALTER TABLE" not in source
    assert "DROP TABLE" not in source
