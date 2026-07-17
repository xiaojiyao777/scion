from __future__ import annotations

import contextvars
import copy
import gc
import pickle
import sqlite3
import threading
import weakref
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pytest

from scion.core.models import Branch, BranchState, HypothesisRecord
from scion.lineage import owner_transaction as subject
from scion.lineage import sqlite_connection as sqlite_boundary
from scion.lineage.durable_owner import (
    RevisionedBranchRecord,
    RevisionedHypothesisRecord,
)


@dataclass(frozen=True)
class _Harness:
    path: Path
    authority: sqlite_boundary.CampaignDatabaseAuthority
    branch_store: subject._OwnerStoreAuthority
    hypothesis_store: subject._OwnerStoreAuthority
    branch_authorizer: subject._OwnerCreationAuthorizerAuthority
    hypothesis_authorizer: subject._OwnerCreationAuthorizerAuthority
    branch: RevisionedBranchRecord
    hypothesis: RevisionedHypothesisRecord


def _branch(
    *,
    branch_id: str = "branch-1",
    state: BranchState = BranchState.EXPLORE,
) -> Branch:
    return Branch(
        branch_id=branch_id,
        state=state,
        base_champion_id=7,
        base_champion_hash="a" * 64,
        lineage_id=f"lineage-{branch_id}",
        current_code_hash="b" * 64,
        last_clean_code_hash="c" * 64,
        screening_expand_count=1,
        validation_expand_count=2,
        failure_codes=[],
        created_at=datetime(2026, 7, 16, 1, 2, 3),
        updated_at=datetime(2026, 7, 16, 1, 2, 4),
        direction="local-search",
        weight_revision=3,
        branch_code_status="candidate_committed",
        branch_evidence_summary={"complete": True},
        infra_block_count=0,
    )


def _hypothesis(
    *,
    hypothesis_id: str = "hypothesis-1",
    branch_id: str = "branch-1",
    status: str = "active",
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
        proposal_digest="d" * 64,
    )


def _harness(
    tmp_path: Path,
    *,
    two_branches: bool = False,
    owner_trigger: bool = False,
) -> _Harness:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "owner-transaction.db"
    branch = RevisionedBranchRecord.from_value(_branch(), owner_revision=0)
    hypothesis = RevisionedHypothesisRecord.from_value(
        _hypothesis(),
        owner_revision=0,
    )
    connection = sqlite_boundary._connect_sqlite(path)
    try:
        connection.executescript("""
            CREATE TABLE branches (
                branch_id TEXT PRIMARY KEY,
                owner_revision INTEGER NOT NULL,
                payload_sha256 TEXT NOT NULL,
                owner_protocol_generation TEXT NOT NULL
            );
            CREATE TABLE hypotheses (
                hypothesis_id TEXT PRIMARY KEY,
                branch_id TEXT NOT NULL,
                owner_revision INTEGER NOT NULL,
                payload_sha256 TEXT NOT NULL,
                owner_protocol_generation TEXT NOT NULL
            );
            CREATE TABLE participant_events (
                event_id TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """)
        connection.execute(
            "INSERT INTO branches VALUES (?, ?, ?, ?)",
            (
                branch.branch_id,
                branch.owner_revision,
                branch.payload_sha256,
                "durable-owner.v1",
            ),
        )
        connection.execute(
            "INSERT INTO hypotheses VALUES (?, ?, ?, ?, ?)",
            (
                hypothesis.hypothesis_id,
                hypothesis.value().branch_id,
                hypothesis.owner_revision,
                hypothesis.payload_sha256,
                "durable-owner.v1",
            ),
        )
        if two_branches:
            second = RevisionedBranchRecord.from_value(
                _branch(branch_id="branch-2"),
                owner_revision=0,
            )
            connection.execute(
                "INSERT INTO branches VALUES (?, ?, ?, ?)",
                (
                    second.branch_id,
                    second.owner_revision,
                    second.payload_sha256,
                    "durable-owner.v1",
                ),
            )
        if owner_trigger:
            connection.execute("""
                CREATE TRIGGER branch_writes_hypothesis
                AFTER UPDATE ON branches
                BEGIN
                    UPDATE hypotheses
                    SET owner_revision = owner_revision + 1
                    WHERE hypothesis_id = 'hypothesis-1';
                END
                """)
        connection.commit()
    finally:
        connection.close()

    authority = sqlite_boundary._issue_test_campaign_database_authority(path)
    return _Harness(
        path=path,
        authority=authority,
        branch_store=subject._issue_branch_store_authority(authority),
        hypothesis_store=subject._issue_hypothesis_store_authority(authority),
        branch_authorizer=(
            subject._issue_branch_creation_authorizer_authority(authority)
        ),
        hypothesis_authorizer=(
            subject._issue_hypothesis_creation_authorizer_authority(authority)
        ),
        branch=branch,
        hypothesis=hypothesis,
    )


def _branch_successor(
    expected: RevisionedBranchRecord,
    *,
    state: BranchState = BranchState.READY_VALIDATE,
) -> RevisionedBranchRecord:
    target = expected.value()
    target.state = state
    target.updated_at = datetime(2026, 7, 16, 2, 3, 4)
    return RevisionedBranchRecord.from_value(
        target,
        owner_revision=expected.owner_revision + 1,
    )


def _hypothesis_successor(
    expected: RevisionedHypothesisRecord,
    *,
    status: str = "advanced",
) -> RevisionedHypothesisRecord:
    target = expected.value()
    target.status = status
    return RevisionedHypothesisRecord.from_value(
        target,
        owner_revision=expected.owner_revision + 1,
    )


def _write_branch(
    harness: _Harness,
    ledger: subject._OwnerReceiptLedger,
    expected: RevisionedBranchRecord,
) -> tuple[subject.OwnerMutationReceipt, RevisionedBranchRecord]:
    committed = _branch_successor(expected)
    result, fact = subject._execute_branch_owner_update(
        harness.branch_store,
        ledger,
        expected,
        """
        UPDATE branches
        SET owner_revision = ?, payload_sha256 = ?
        WHERE branch_id = ? AND owner_revision = ?
        """,
        (
            committed.owner_revision,
            committed.payload_sha256,
            expected.branch_id,
            expected.owner_revision,
        ),
    )
    assert result.rowcount == 1
    ledger_state = subject._lookup_ledger(ledger)
    rows = sqlite_boundary._execute_participant(
        ledger_state.transaction,
        harness.authority,
        "SELECT owner_revision, payload_sha256 FROM branches WHERE branch_id = ?",
        (expected.branch_id,),
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        (committed.owner_revision, committed.payload_sha256)
    ]
    receipt = subject._issue_branch_mutation_receipt(
        harness.branch_store,
        ledger,
        fact,
        committed,
    )
    return receipt, committed


def _write_hypothesis(
    harness: _Harness,
    ledger: subject._OwnerReceiptLedger,
    expected: RevisionedHypothesisRecord,
) -> tuple[subject.OwnerMutationReceipt, RevisionedHypothesisRecord]:
    committed = _hypothesis_successor(expected)
    result, fact = subject._execute_hypothesis_owner_update(
        harness.hypothesis_store,
        ledger,
        expected,
        """
        UPDATE hypotheses
        SET owner_revision = ?, payload_sha256 = ?
        WHERE hypothesis_id = ? AND owner_revision = ?
        """,
        (
            committed.owner_revision,
            committed.payload_sha256,
            expected.hypothesis_id,
            expected.owner_revision,
        ),
    )
    assert result.rowcount == 1
    ledger_state = subject._lookup_ledger(ledger)
    rows = sqlite_boundary._execute_participant(
        ledger_state.transaction,
        harness.authority,
        """
        SELECT branch_id, owner_revision, payload_sha256
        FROM hypotheses
        WHERE hypothesis_id = ?
        """,
        (expected.hypothesis_id,),
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        (
            committed.value().branch_id,
            committed.owner_revision,
            committed.payload_sha256,
        )
    ]
    receipt = subject._issue_hypothesis_mutation_receipt(
        harness.hypothesis_store,
        ledger,
        fact,
        committed,
    )
    return receipt, committed


def _prepare_branch_creation(
    harness: _Harness,
    transaction: sqlite_boundary.ImmediateTransaction,
    ledger: subject._OwnerReceiptLedger,
    initial: RevisionedBranchRecord,
) -> tuple[
    subject._OwnerCreationAuthorization,
    subject._OwnerWriteFact,
    subject.OwnerCreationReceipt,
]:
    authorization = subject._register_branch_creation_authorization(
        harness.branch_authorizer,
        transaction,
        ledger,
        initial.branch_id,
        initial.payload_sha256,
    )
    result, write_fact = subject._execute_branch_owner_insert(
        harness.branch_store,
        ledger,
        authorization,
        initial.branch_id,
        "INSERT INTO branches VALUES (?, ?, ?, ?)",
        (
            initial.branch_id,
            initial.owner_revision,
            initial.payload_sha256,
            "durable-owner.v1",
        ),
    )
    assert result.rowcount == 1
    receipt = subject._issue_branch_creation_receipt(
        harness.branch_store,
        ledger,
        write_fact,
        initial,
    )
    return authorization, write_fact, receipt


def _complete_branch_creation(
    harness: _Harness,
    transaction: sqlite_boundary.ImmediateTransaction,
    ledger: subject._OwnerReceiptLedger,
    authorization: subject._OwnerCreationAuthorization,
    receipt: subject.OwnerCreationReceipt,
) -> subject.SemanticCreationOutcomeWitness:
    outcome_witness = subject._issue_branch_semantic_creation_outcome_witness(
        harness.branch_authorizer,
        transaction,
        ledger,
        authorization,
    )
    subject._complete_branch_creation_authorization(
        harness.branch_authorizer,
        transaction,
        ledger,
        authorization,
        receipt,
        outcome_witness,
    )
    return outcome_witness


def _database_owner(
    harness: _Harness,
    table: str,
    owner_id: str,
) -> tuple[int, str]:
    connection = sqlite_boundary._connect_sqlite(harness.path)
    try:
        id_column = "branch_id" if table == "branches" else "hypothesis_id"
        row = connection.execute(
            f"SELECT owner_revision, payload_sha256 FROM {table} "
            f"WHERE {id_column} = ?",
            (owner_id,),
        ).fetchone()
        assert row is not None
        return int(row[0]), str(row[1])
    finally:
        connection.close()


@pytest.mark.parametrize(
    "receipt_type",
    [subject.OwnerMutationReceipt, subject.OwnerCreationReceipt],
)
def test_receipt_types_are_sealed_and_copies_are_not_issued(
    receipt_type: type[object],
) -> None:
    with pytest.raises(subject.InvalidOwnerReceiptError):
        receipt_type()
    with pytest.raises(TypeError):
        type("Subclass", (receipt_type,), {})

    forged = object.__new__(receipt_type)
    with pytest.raises(subject.InvalidOwnerReceiptError):
        subject._lookup_receipt(forged)
    with pytest.raises(subject.InvalidOwnerReceiptError):
        copy.copy(forged)
    with pytest.raises((TypeError, pickle.PicklingError)):
        pickle.dumps(forged)


@pytest.mark.parametrize(
    ("capability_type", "lookup"),
    [
        (
            subject._OwnerCreationAuthorizerAuthority,
            subject._lookup_creation_authorizer_authority,
        ),
        (
            subject._OwnerCreationAuthorization,
            subject._lookup_creation_authorization,
        ),
        (
            subject.SemanticCreationOutcomeWitness,
            subject._lookup_semantic_creation_outcome_witness,
        ),
    ],
)
def test_creation_authority_types_are_sealed_and_forged_values_fail(
    capability_type: type[object],
    lookup,
) -> None:
    with pytest.raises(subject.InvalidOwnerReceiptError):
        capability_type()
    with pytest.raises(TypeError):
        type("Subclass", (capability_type,), {})

    forged = object.__new__(capability_type)
    with pytest.raises(subject.InvalidOwnerReceiptError):
        lookup(forged)
    with pytest.raises(subject.InvalidOwnerReceiptError):
        copy.copy(forged)
    with pytest.raises(subject.InvalidOwnerReceiptError):
        copy.deepcopy(forged)
    with pytest.raises((TypeError, pickle.PicklingError)):
        pickle.dumps(forged)


def test_default_authorizer_denies_direct_owner_dml_and_executemany(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    with pytest.raises(RuntimeError, match="rollback authorizer test"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            subject._attach_owner_receipt_ledger(transaction, harness.authority)
            for sql in (
                "UPDATE branches SET owner_revision = owner_revision + 1",
                "INSERT INTO branches VALUES "
                "('branch-x', 0, 'x', 'durable-owner.v1')",
                "DELETE FROM hypotheses WHERE hypothesis_id = 'hypothesis-1'",
            ):
                with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
                    sqlite_boundary._execute_participant(
                        transaction,
                        harness.authority,
                        sql,
                    )
            with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
                sqlite_boundary._executemany_participant(
                    transaction,
                    harness.authority,
                    "UPDATE branches SET owner_revision = ? WHERE branch_id = ?",
                    [(1, "branch-1")],
                )
            raise RuntimeError("rollback authorizer test")


def test_non_owner_participant_dml_remains_available(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        ledger = subject._attach_owner_receipt_ledger(
            transaction,
            harness.authority,
        )
        result = sqlite_boundary._execute_participant(
            transaction,
            harness.authority,
            "INSERT INTO participant_events VALUES (?, ?)",
            ("event-1", "complete"),
        )
        assert result.rowcount == 1
        receipt, _ = _write_branch(harness, ledger, harness.branch)
        subject._consume_branch_mutation_receipt(ledger, receipt)
        subject._seal_owner_receipt_ledger(ledger, (receipt,))


def test_branch_receipt_consumption_and_closure_commit_exact_successor(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        ledger = subject._attach_owner_receipt_ledger(
            transaction,
            harness.authority,
        )
        receipt, committed = _write_branch(harness, ledger, harness.branch)
        with pytest.raises(subject.InvalidOwnerReceiptError):
            copy.copy(receipt)
        with pytest.raises(subject.InvalidOwnerReceiptError):
            copy.deepcopy(receipt)
        with pytest.raises(subject.InvalidOwnerReceiptError):
            pickle.dumps(receipt)
        witness = subject._consume_branch_mutation_receipt(ledger, receipt)
        assert witness.owner_id == harness.branch.branch_id
        assert witness.expected_token is harness.branch
        assert witness.committed_token is committed
        assert subject._seal_owner_receipt_ledger(ledger, (receipt,)) == (witness,)

    assert _database_owner(harness, "branches", harness.branch.branch_id) == (
        committed.owner_revision,
        committed.payload_sha256,
    )
    with pytest.raises(subject.InactiveOwnerTransactionError):
        subject._consume_branch_mutation_receipt(ledger, receipt)


def test_owner_receipt_object_graph_retains_no_cursor_or_connection(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        ledger = subject._attach_owner_receipt_ledger(
            transaction,
            harness.authority,
        )
        receipt, _ = _write_branch(harness, ledger, harness.branch)
        witness = subject._consume_branch_mutation_receipt(ledger, receipt)

        seen: set[int] = set()

        def _walk(value: object) -> None:
            if id(value) in seen:
                return
            seen.add(id(value))
            assert not isinstance(value, (sqlite3.Cursor, sqlite3.Connection))
            if isinstance(value, dict):
                for key, item in value.items():
                    _walk(key)
                    _walk(item)
                return
            if isinstance(value, (list, tuple, set, frozenset)):
                for item in value:
                    _walk(item)
                return
            if type(value).__module__ != subject.__name__:
                return
            for cls in type(value).__mro__:
                slots = cls.__dict__.get("__slots__", ())
                if isinstance(slots, str):
                    slots = (slots,)
                for slot in slots:
                    if slot == "__weakref__":
                        continue
                    mangled = slot
                    if slot.startswith("__") and not slot.endswith("__"):
                        mangled = f"_{cls.__name__.lstrip('_')}{slot}"
                    if hasattr(value, mangled):
                        _walk(getattr(value, mangled))

        _walk(ledger)
        _walk(receipt)
        _walk(witness)
        subject._seal_owner_receipt_ledger(ledger, (receipt,))


def test_mixed_branch_hypothesis_receipts_close_by_exact_identity(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        ledger = subject._attach_owner_receipt_ledger(
            transaction,
            harness.authority,
        )
        branch_receipt, branch_committed = _write_branch(
            harness,
            ledger,
            harness.branch,
        )
        hypothesis_receipt, hypothesis_committed = _write_hypothesis(
            harness,
            ledger,
            harness.hypothesis,
        )
        branch_witness = subject._consume_branch_mutation_receipt(
            ledger,
            branch_receipt,
        )
        hypothesis_witness = subject._consume_hypothesis_mutation_receipt(
            ledger,
            hypothesis_receipt,
        )
        assert subject._seal_owner_receipt_ledger(
            ledger,
            (branch_receipt, hypothesis_receipt),
        ) == (branch_witness, hypothesis_witness)

    assert _database_owner(harness, "branches", harness.branch.branch_id)[0] == 1
    assert (
        _database_owner(
            harness,
            "hypotheses",
            harness.hypothesis.hypothesis_id,
        )[0]
        == 1
    )
    assert branch_committed.owner_revision == hypothesis_committed.owner_revision == 1


def test_missing_receipt_closure_rolls_back_permitted_write(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    with pytest.raises(subject.OwnerReceiptClosureError, match="empty"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            subject._execute_branch_owner_update(
                harness.branch_store,
                ledger,
                harness.branch,
                "UPDATE branches SET owner_revision = 1 WHERE branch_id = 'branch-1'",
            )
            subject._seal_owner_receipt_ledger(ledger, ())

    assert _database_owner(harness, "branches", harness.branch.branch_id) == (
        harness.branch.owner_revision,
        harness.branch.payload_sha256,
    )


def test_unsealed_owner_ledger_cannot_commit(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            subject._execute_branch_owner_update(
                harness.branch_store,
                ledger,
                harness.branch,
                "UPDATE branches SET owner_revision = 1 "
                "WHERE branch_id = 'branch-1'",
            )

    assert _database_owner(harness, "branches", harness.branch.branch_id)[0] == 0


def test_transaction_has_one_exact_attached_owner_ledger(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        ledger = subject._attach_owner_receipt_ledger(
            transaction,
            harness.authority,
        )
        assert (
            subject._require_branch_store_ledger(
                transaction,
                harness.branch_store,
            )
            is ledger
        )
        with pytest.raises(subject.OwnerWriteProtocolError, match="already attached"):
            subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
        receipt, _ = _write_branch(harness, ledger, harness.branch)
        subject._consume_branch_mutation_receipt(ledger, receipt)
        subject._seal_owner_receipt_ledger(ledger, (receipt,))


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE branches SET owner_revision = 1 WHERE branch_id = 'missing'",
        "UPDATE branches SET owner_revision = owner_revision + 1",
    ],
)
def test_zero_or_multi_row_write_cannot_issue_receipt(
    tmp_path: Path,
    sql: str,
) -> None:
    harness = _harness(tmp_path, two_branches=True)
    with pytest.raises(subject.OwnerWriteProtocolError, match="single-row"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            _, fact = subject._execute_branch_owner_update(
                harness.branch_store,
                ledger,
                harness.branch,
                sql,
            )
            subject._issue_branch_mutation_receipt(
                harness.branch_store,
                ledger,
                fact,
                _branch_successor(harness.branch),
            )

    assert _database_owner(harness, "branches", harness.branch.branch_id)[0] == 0


@pytest.mark.parametrize(
    ("sql", "match"),
    [
        (
            "UPDATE hypotheses SET owner_revision = 1 "
            "WHERE hypothesis_id = 'hypothesis-1'",
            "not authorized",
        ),
        (
            "INSERT INTO branches VALUES " "('branch-x', 0, 'x', 'durable-owner.v1')",
            "not authorized",
        ),
    ],
)
def test_branch_update_permit_rejects_wrong_table_or_action(
    tmp_path: Path,
    sql: str,
    match: str,
) -> None:
    harness = _harness(tmp_path)
    with pytest.raises(sqlite3.DatabaseError, match=match):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            subject._execute_branch_owner_update(
                harness.branch_store,
                ledger,
                harness.branch,
                sql,
            )


def test_owner_trigger_write_is_denied_and_rolls_back_top_level_write(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path, owner_trigger=True)
    committed = _branch_successor(harness.branch)
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            subject._execute_branch_owner_update(
                harness.branch_store,
                ledger,
                harness.branch,
                "UPDATE branches SET owner_revision = ?, payload_sha256 = ? "
                "WHERE branch_id = ?",
                (committed.owner_revision, committed.payload_sha256, "branch-1"),
            )

    assert _database_owner(harness, "branches", harness.branch.branch_id)[0] == 0
    assert (
        _database_owner(
            harness,
            "hypotheses",
            harness.hypothesis.hypothesis_id,
        )[0]
        == 0
    )


def test_authorizer_permit_rejects_non_main_trigger_and_delete_events(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    with pytest.raises(RuntimeError, match="rollback authorizer matrix"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            state = subject._lookup_ledger(ledger)
            permit = subject._PermitState(
                owner_kind=subject._OwnerKind.BRANCH,
                action=subject._OwnerAction.UPDATE,
                executing=True,
            )
            state.active_permit = permit
            ledger_ref = weakref.ref(ledger)
            assert (
                subject._authorize_owner_table_action(
                    ledger_ref,
                    sqlite3.SQLITE_UPDATE,
                    "branches",
                    "owner_revision",
                    "main",
                    None,
                )
                == sqlite3.SQLITE_OK
            )
            assert (
                subject._authorize_owner_table_action(
                    ledger_ref,
                    sqlite3.SQLITE_UPDATE,
                    "branches",
                    "owner_revision",
                    "aux",
                    None,
                )
                == sqlite3.SQLITE_DENY
            )
            assert (
                subject._authorize_owner_table_action(
                    ledger_ref,
                    sqlite3.SQLITE_UPDATE,
                    "branches",
                    "owner_revision",
                    "main",
                    "owner_trigger",
                )
                == sqlite3.SQLITE_DENY
            )
            assert (
                subject._authorize_owner_table_action(
                    ledger_ref,
                    sqlite3.SQLITE_DELETE,
                    "branches",
                    None,
                    "main",
                    None,
                )
                == sqlite3.SQLITE_DENY
            )
            permit.executing = False
            state.active_permit = None
            raise RuntimeError("rollback authorizer matrix")


def test_pending_write_blocks_second_permit_and_replay_is_default_denied(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    with pytest.raises(subject.OwnerWriteProtocolError, match="prior owner write"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            subject._execute_branch_owner_update(
                harness.branch_store,
                ledger,
                harness.branch,
                "UPDATE branches SET owner_revision = 1 WHERE branch_id = 'branch-1'",
            )
            with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
                sqlite_boundary._execute_participant(
                    transaction,
                    harness.authority,
                    "UPDATE branches SET owner_revision = 2 "
                    "WHERE branch_id = 'branch-1'",
                )
            subject._execute_hypothesis_owner_update(
                harness.hypothesis_store,
                ledger,
                harness.hypothesis,
                "UPDATE hypotheses SET owner_revision = 1 "
                "WHERE hypothesis_id = 'hypothesis-1'",
            )

    assert _database_owner(harness, "branches", harness.branch.branch_id)[0] == 0


def test_interruption_after_execute_return_leaves_pending_and_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    original_execute = sqlite_boundary._execute_participant
    interrupt = True

    def _execute_then_interrupt(*args, **kwargs):
        nonlocal interrupt
        result = original_execute(*args, **kwargs)
        sql = args[2] if len(args) > 2 else kwargs.get("sql", "")
        if interrupt and str(sql).lstrip().upper().startswith("UPDATE"):
            interrupt = False
            raise KeyboardInterrupt("after owner execute")
        return result

    with pytest.raises(subject.OwnerReceiptClosureError, match="not completed"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            monkeypatch.setattr(
                sqlite_boundary,
                "_execute_participant",
                _execute_then_interrupt,
            )
            with pytest.raises(KeyboardInterrupt, match="after owner execute"):
                subject._execute_branch_owner_update(
                    harness.branch_store,
                    ledger,
                    harness.branch,
                    "UPDATE branches SET owner_revision = 1 "
                    "WHERE branch_id = 'branch-1'",
                )
            assert subject._lookup_ledger(ledger).active_permit is None
            subject._seal_owner_receipt_ledger(ledger, (object(),))  # type: ignore[arg-type]

    assert _database_owner(harness, "branches", harness.branch.branch_id)[0] == 0


def test_same_owner_cannot_receive_two_writes_in_one_ledger(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    with pytest.raises(
        subject.OwnerWriteProtocolError, match="cannot be written twice"
    ):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            receipt, committed = _write_branch(harness, ledger, harness.branch)
            subject._consume_branch_mutation_receipt(ledger, receipt)
            subject._execute_branch_owner_update(
                harness.branch_store,
                ledger,
                committed,
                "UPDATE branches SET owner_revision = 2 WHERE branch_id = 'branch-1'",
            )

    assert _database_owner(harness, "branches", harness.branch.branch_id)[0] == 0


def test_receipt_is_single_use_and_wrong_kind_does_not_consume_it(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        ledger = subject._attach_owner_receipt_ledger(
            transaction,
            harness.authority,
        )
        receipt, _ = _write_branch(harness, ledger, harness.branch)
        with pytest.raises(subject.OwnerWriteProtocolError, match="another owner kind"):
            subject._consume_hypothesis_mutation_receipt(ledger, receipt)
        witness = subject._consume_branch_mutation_receipt(ledger, receipt)
        with pytest.raises(subject.OwnerWriteProtocolError, match="only once"):
            subject._consume_branch_mutation_receipt(ledger, receipt)
        subject._seal_owner_receipt_ledger(ledger, (receipt,))
        assert witness.owner_kind is subject._OwnerKind.BRANCH


def test_receipt_from_another_transaction_is_rejected(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    captured: list[subject.OwnerMutationReceipt] = []
    with pytest.raises(RuntimeError, match="rollback first transaction"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            receipt, _ = _write_branch(harness, ledger, harness.branch)
            captured.append(receipt)
            raise RuntimeError("rollback first transaction")

    with pytest.raises(RuntimeError, match="rollback second transaction"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            other_ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            with pytest.raises(
                subject.InvalidOwnerReceiptError,
                match="another transaction",
            ):
                subject._consume_branch_mutation_receipt(
                    other_ledger,
                    captured[0],
                )
            raise RuntimeError("rollback second transaction")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda token: RevisionedBranchRecord.from_value(
            token.value(),
            owner_revision=token.owner_revision,
        ),
        lambda token: RevisionedBranchRecord.from_value(
            token.value(),
            owner_revision=token.owner_revision + 2,
        ),
        lambda token: RevisionedBranchRecord.from_value(
            _branch(branch_id="branch-other", state=BranchState.READY_VALIDATE),
            owner_revision=token.owner_revision + 1,
        ),
    ],
)
def test_invalid_mutation_successor_cannot_issue_receipt(
    tmp_path: Path,
    mutate,
) -> None:
    harness = _harness(tmp_path)
    with pytest.raises(subject.OwnerWriteProtocolError):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            _, fact = subject._execute_branch_owner_update(
                harness.branch_store,
                ledger,
                harness.branch,
                "UPDATE branches SET owner_revision = 1 WHERE branch_id = 'branch-1'",
            )
            subject._issue_branch_mutation_receipt(
                harness.branch_store,
                ledger,
                fact,
                mutate(harness.branch),
            )


def test_hypothesis_cannot_move_between_branches_in_receipt(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    moved = harness.hypothesis.value()
    moved.branch_id = "branch-other"
    committed = RevisionedHypothesisRecord.from_value(moved, owner_revision=1)
    with pytest.raises(subject.OwnerWriteProtocolError, match="between Branches"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            _, fact = subject._execute_hypothesis_owner_update(
                harness.hypothesis_store,
                ledger,
                harness.hypothesis,
                "UPDATE hypotheses SET owner_revision = 1 "
                "WHERE hypothesis_id = 'hypothesis-1'",
            )
            subject._issue_hypothesis_mutation_receipt(
                harness.hypothesis_store,
                ledger,
                fact,
                committed,
            )


def test_creation_receipt_requires_revision_zero_and_fixed_kind(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    initial = RevisionedBranchRecord.from_value(
        _branch(branch_id="branch-new"),
        owner_revision=0,
    )
    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        ledger = subject._attach_owner_receipt_ledger(
            transaction,
            harness.authority,
        )
        authorization = subject._register_branch_creation_authorization(
            harness.branch_authorizer,
            transaction,
            ledger,
            initial.branch_id,
            initial.payload_sha256,
        )
        result, fact = subject._execute_branch_owner_insert(
            harness.branch_store,
            ledger,
            authorization,
            initial.branch_id,
            "INSERT INTO branches VALUES (?, ?, ?, ?)",
            (
                initial.branch_id,
                0,
                initial.payload_sha256,
                "durable-owner.v1",
            ),
        )
        assert result.rowcount == 1
        with pytest.raises(subject.OwnerWriteProtocolError, match="revision zero"):
            subject._issue_branch_creation_receipt(
                harness.branch_store,
                ledger,
                fact,
                RevisionedBranchRecord.from_value(initial.value(), owner_revision=1),
            )
        receipt = subject._issue_branch_creation_receipt(
            harness.branch_store,
            ledger,
            fact,
            initial,
        )
        outcome_witness = _complete_branch_creation(
            harness,
            transaction,
            ledger,
            authorization,
            receipt,
        )
        with pytest.raises(subject.OwnerWriteProtocolError, match="interchanged"):
            subject._consume_receipt_as(
                ledger,
                receipt,
                owner_kind=subject._OwnerKind.BRANCH,
                creation=False,
            )
        witness = subject._consume_branch_creation_receipt(ledger, receipt)
        subject._require_branch_semantic_creation_outcome_witness(
            harness.branch_authorizer,
            transaction,
            ledger,
            authorization,
            outcome_witness,
        )
        subject._seal_owner_receipt_ledger(ledger, (receipt,))
        assert witness.expected_token is None
        assert witness.creation_authorization is authorization


def test_hypothesis_creation_receipt_binds_actual_branch_and_revision(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    initial = RevisionedHypothesisRecord.from_value(
        _hypothesis(hypothesis_id="hypothesis-new"),
        owner_revision=0,
    )
    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        ledger = subject._attach_owner_receipt_ledger(
            transaction,
            harness.authority,
        )
        authorization = subject._register_hypothesis_creation_authorization(
            harness.hypothesis_authorizer,
            transaction,
            ledger,
            initial.hypothesis_id,
            initial.payload_sha256,
        )
        _, fact = subject._execute_hypothesis_owner_insert(
            harness.hypothesis_store,
            ledger,
            authorization,
            initial.hypothesis_id,
            "INSERT INTO hypotheses VALUES (?, ?, ?, ?, ?)",
            (
                initial.hypothesis_id,
                initial.value().branch_id,
                0,
                initial.payload_sha256,
                "durable-owner.v1",
            ),
        )
        receipt = subject._issue_hypothesis_creation_receipt(
            harness.hypothesis_store,
            ledger,
            fact,
            initial,
        )
        outcome_witness = subject._issue_hypothesis_semantic_creation_outcome_witness(
            harness.hypothesis_authorizer,
            transaction,
            ledger,
            authorization,
        )
        subject._complete_hypothesis_creation_authorization(
            harness.hypothesis_authorizer,
            transaction,
            ledger,
            authorization,
            receipt,
            outcome_witness,
        )
        witness = subject._consume_hypothesis_creation_receipt(ledger, receipt)
        subject._seal_owner_receipt_ledger(ledger, (receipt,))
        assert witness.owner_id == "hypothesis-new"
        assert witness.expected_token is None
        assert witness.creation_authorization is authorization

    assert _database_owner(harness, "hypotheses", "hypothesis-new") == (
        0,
        initial.payload_sha256,
    )


def test_creation_authorization_requires_completion_before_consumption(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    initial = RevisionedBranchRecord.from_value(
        _branch(branch_id="branch-new"),
        owner_revision=0,
    )
    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        ledger = subject._attach_owner_receipt_ledger(
            transaction,
            harness.authority,
        )
        authorization, write_fact, receipt = _prepare_branch_creation(
            harness,
            transaction,
            ledger,
            initial,
        )
        authorization_state = subject._lookup_creation_authorization(authorization)
        assert (
            authorization_state.phase is subject._CreationAuthorizationPhase.WRITE_BOUND
        )
        assert authorization_state.write_fact is write_fact
        with pytest.raises(subject.OwnerWriteProtocolError, match="not completed"):
            subject._consume_branch_creation_receipt(ledger, receipt)
        outcome_witness = subject._issue_branch_semantic_creation_outcome_witness(
            harness.branch_authorizer,
            transaction,
            ledger,
            authorization,
        )
        with pytest.raises(
            subject.InvalidOwnerReceiptError,
            match="another semantic authorizer",
        ):
            subject._complete_branch_creation_authorization(
                subject._issue_branch_creation_authorizer_authority(harness.authority),
                transaction,
                ledger,
                authorization,
                receipt,
                outcome_witness,
            )
        subject._complete_branch_creation_authorization(
            harness.branch_authorizer,
            transaction,
            ledger,
            authorization,
            receipt,
            outcome_witness,
        )
        assert (
            authorization_state.phase is subject._CreationAuthorizationPhase.COMPLETED
        )
        with pytest.raises(subject.OwnerWriteProtocolError, match="WRITE_BOUND"):
            subject._complete_branch_creation_authorization(
                harness.branch_authorizer,
                transaction,
                ledger,
                authorization,
                receipt,
                outcome_witness,
            )
        witness = subject._consume_branch_creation_receipt(ledger, receipt)
        assert witness.creation_authorization is authorization
        subject._seal_owner_receipt_ledger(ledger, (receipt,))


def test_creation_authorization_rejects_wrong_kind_database_and_digest(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path / "a")
    other = _harness(tmp_path / "b")
    with pytest.raises(RuntimeError, match="rollback authorization validation"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            forged_transaction = object.__new__(sqlite_boundary.ImmediateTransaction)
            with pytest.raises(
                subject.InvalidOwnerReceiptError,
                match="another transaction",
            ):
                subject._register_branch_creation_authorization(
                    harness.branch_authorizer,
                    forged_transaction,
                    ledger,
                    "branch-new",
                    "a" * 64,
                )
            with pytest.raises(subject.InvalidOwnerReceiptError, match="owner kind"):
                subject._register_hypothesis_creation_authorization(
                    harness.branch_authorizer,
                    transaction,
                    ledger,
                    "hypothesis-new",
                    "a" * 64,
                )
            with pytest.raises(
                subject.InvalidOwnerReceiptError,
                match="another database",
            ):
                subject._register_branch_creation_authorization(
                    other.branch_authorizer,
                    transaction,
                    ledger,
                    "branch-new",
                    "a" * 64,
                )
            for malformed_owner_id in ("", " ", " branch-new", "branch-new "):
                with pytest.raises(
                    subject.OwnerWriteProtocolError,
                    match="nonempty exact str",
                ):
                    subject._register_branch_creation_authorization(
                        harness.branch_authorizer,
                        transaction,
                        ledger,
                        malformed_owner_id,
                        "a" * 64,
                    )
            for malformed in ("", "A" * 64, "g" * 64, "a" * 63):
                with pytest.raises(
                    subject.OwnerWriteProtocolError,
                    match="SHA-256",
                ):
                    subject._register_branch_creation_authorization(
                        harness.branch_authorizer,
                        transaction,
                        ledger,
                        "branch-new",
                        malformed,
                    )
            raise RuntimeError("rollback authorization validation")


def test_owner_insert_rejects_forged_and_wrong_id_authorization(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    initial = RevisionedBranchRecord.from_value(
        _branch(branch_id="branch-new"),
        owner_revision=0,
    )
    with pytest.raises(RuntimeError, match="rollback insert authorization"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            forged = object.__new__(subject._OwnerCreationAuthorization)
            with pytest.raises(subject.InvalidOwnerReceiptError, match="not issued"):
                subject._execute_branch_owner_insert(
                    harness.branch_store,
                    ledger,
                    forged,
                    initial.branch_id,
                    "INSERT INTO branches VALUES (?, ?, ?, ?)",
                    (
                        initial.branch_id,
                        0,
                        initial.payload_sha256,
                        "durable-owner.v1",
                    ),
                )
            authorization = subject._register_branch_creation_authorization(
                harness.branch_authorizer,
                transaction,
                ledger,
                initial.branch_id,
                initial.payload_sha256,
            )
            with pytest.raises(subject.OwnerWriteProtocolError, match="ID differs"):
                subject._execute_branch_owner_insert(
                    harness.branch_store,
                    ledger,
                    authorization,
                    "branch-other",
                    "INSERT INTO branches VALUES (?, ?, ?, ?)",
                    ("branch-other", 0, initial.payload_sha256, "durable-owner.v1"),
                )
            raise RuntimeError("rollback insert authorization")


def test_creation_receipt_rejects_authorization_target_digest_drift(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    initial = RevisionedBranchRecord.from_value(
        _branch(branch_id="branch-new"),
        owner_revision=0,
    )
    with pytest.raises(RuntimeError, match="rollback digest drift"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            authorization = subject._register_branch_creation_authorization(
                harness.branch_authorizer,
                transaction,
                ledger,
                initial.branch_id,
                "e" * 64,
            )
            _, write_fact = subject._execute_branch_owner_insert(
                harness.branch_store,
                ledger,
                authorization,
                initial.branch_id,
                "INSERT INTO branches VALUES (?, ?, ?, ?)",
                (
                    initial.branch_id,
                    0,
                    initial.payload_sha256,
                    "durable-owner.v1",
                ),
            )
            with pytest.raises(subject.OwnerWriteProtocolError, match="digest"):
                subject._issue_branch_creation_receipt(
                    harness.branch_store,
                    ledger,
                    write_fact,
                    initial,
                )
            raise RuntimeError("rollback digest drift")


def test_semantic_creation_outcome_witness_is_exact_and_one_shot(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    initial = RevisionedBranchRecord.from_value(
        _branch(branch_id="branch-new"),
        owner_revision=0,
    )
    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        ledger = subject._attach_owner_receipt_ledger(
            transaction,
            harness.authority,
        )
        authorization = subject._register_branch_creation_authorization(
            harness.branch_authorizer,
            transaction,
            ledger,
            initial.branch_id,
            initial.payload_sha256,
        )
        _, write_fact = subject._execute_branch_owner_insert(
            harness.branch_store,
            ledger,
            authorization,
            initial.branch_id,
            "INSERT INTO branches VALUES (?, ?, ?, ?)",
            (
                initial.branch_id,
                0,
                initial.payload_sha256,
                "durable-owner.v1",
            ),
        )
        with pytest.raises(subject.OwnerWriteProtocolError, match="exact issued"):
            subject._issue_branch_semantic_creation_outcome_witness(
                harness.branch_authorizer,
                transaction,
                ledger,
                authorization,
            )
        receipt = subject._issue_branch_creation_receipt(
            harness.branch_store,
            ledger,
            write_fact,
            initial,
        )
        outcome_witness = subject._issue_branch_semantic_creation_outcome_witness(
            harness.branch_authorizer,
            transaction,
            ledger,
            authorization,
        )
        with pytest.raises(subject.OwnerWriteProtocolError, match="only once"):
            subject._issue_branch_semantic_creation_outcome_witness(
                harness.branch_authorizer,
                transaction,
                ledger,
                authorization,
            )
        forged = object.__new__(subject.SemanticCreationOutcomeWitness)
        with pytest.raises(subject.InvalidOwnerReceiptError, match="not issued"):
            subject._require_branch_semantic_creation_outcome_witness(
                harness.branch_authorizer,
                transaction,
                ledger,
                authorization,
                forged,
            )
        with pytest.raises(subject.InvalidOwnerReceiptError, match="transaction"):
            subject._require_branch_semantic_creation_outcome_witness(
                harness.branch_authorizer,
                object.__new__(sqlite_boundary.ImmediateTransaction),
                ledger,
                authorization,
                outcome_witness,
            )
        subject._complete_branch_creation_authorization(
            harness.branch_authorizer,
            transaction,
            ledger,
            authorization,
            receipt,
            outcome_witness,
        )
        subject._consume_branch_creation_receipt(ledger, receipt)
        subject._seal_owner_receipt_ledger(ledger, (receipt,))


def test_creation_completion_rejects_swapped_receipt(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    first = RevisionedBranchRecord.from_value(
        _branch(branch_id="branch-new-1"),
        owner_revision=0,
    )
    second = RevisionedBranchRecord.from_value(
        _branch(branch_id="branch-new-2"),
        owner_revision=0,
    )
    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        ledger = subject._attach_owner_receipt_ledger(
            transaction,
            harness.authority,
        )
        first_authorization, first_fact, first_receipt = _prepare_branch_creation(
            harness,
            transaction,
            ledger,
            first,
        )
        second_authorization, second_fact, second_receipt = _prepare_branch_creation(
            harness,
            transaction,
            ledger,
            second,
        )
        first_outcome = subject._issue_branch_semantic_creation_outcome_witness(
            harness.branch_authorizer,
            transaction,
            ledger,
            first_authorization,
        )
        second_outcome = subject._issue_branch_semantic_creation_outcome_witness(
            harness.branch_authorizer,
            transaction,
            ledger,
            second_authorization,
        )
        with pytest.raises(
            subject.InvalidOwnerReceiptError,
            match="completion facts",
        ):
            subject._complete_branch_creation_authorization(
                harness.branch_authorizer,
                transaction,
                ledger,
                first_authorization,
                second_receipt,
                first_outcome,
            )
        assert (
            subject._lookup_creation_authorization(first_authorization).write_fact
            is first_fact
        )
        assert (
            subject._lookup_creation_authorization(second_authorization).write_fact
            is second_fact
        )
        for authorization, receipt, outcome_witness in (
            (first_authorization, first_receipt, first_outcome),
            (second_authorization, second_receipt, second_outcome),
        ):
            subject._complete_branch_creation_authorization(
                harness.branch_authorizer,
                transaction,
                ledger,
                authorization,
                receipt,
                outcome_witness,
            )
            subject._consume_branch_creation_receipt(ledger, receipt)
        subject._seal_owner_receipt_ledger(
            ledger,
            (first_receipt, second_receipt),
        )


def test_extra_issued_creation_authorization_prevents_mutation_only_closure(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    with pytest.raises(
        subject.OwnerReceiptClosureError,
        match="creation authorization identities differ",
    ):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            subject._register_branch_creation_authorization(
                harness.branch_authorizer,
                transaction,
                ledger,
                "branch-never-written",
                "a" * 64,
            )
            receipt, _ = _write_branch(harness, ledger, harness.branch)
            witness = subject._consume_branch_mutation_receipt(ledger, receipt)
            assert witness.creation_authorization is None
            subject._seal_owner_receipt_ledger(ledger, (receipt,))


def test_failed_creation_insert_stays_write_bound_and_pending(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            authorization = subject._register_branch_creation_authorization(
                harness.branch_authorizer,
                transaction,
                ledger,
                harness.branch.branch_id,
                harness.branch.payload_sha256,
            )
            with pytest.raises(sqlite3.IntegrityError):
                subject._execute_branch_owner_insert(
                    harness.branch_store,
                    ledger,
                    authorization,
                    harness.branch.branch_id,
                    "INSERT INTO branches VALUES (?, ?, ?, ?)",
                    (
                        harness.branch.branch_id,
                        0,
                        harness.branch.payload_sha256,
                        "durable-owner.v1",
                    ),
                )
            authorization_state = subject._lookup_creation_authorization(authorization)
            assert (
                authorization_state.phase
                is subject._CreationAuthorizationPhase.WRITE_BOUND
            )
            assert authorization_state.write_fact is not None
            assert subject._lookup_ledger(ledger).pending_write is (
                authorization_state.write_fact
            )


@pytest.mark.parametrize("staged", [(), "duplicate", "missing"])
def test_receipt_closure_rejects_empty_duplicate_and_missing_sets(
    tmp_path: Path,
    staged: object,
) -> None:
    harness = _harness(tmp_path)
    with pytest.raises(subject.OwnerReceiptClosureError):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            receipt, _ = _write_branch(harness, ledger, harness.branch)
            if staged == "missing":
                subject._seal_owner_receipt_ledger(ledger, ())
            elif staged == "duplicate":
                subject._consume_branch_mutation_receipt(ledger, receipt)
                subject._seal_owner_receipt_ledger(ledger, (receipt, receipt))
            else:
                subject._seal_owner_receipt_ledger(ledger, ())


def test_sealed_or_closed_ledger_denies_every_later_operation(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        ledger = subject._attach_owner_receipt_ledger(
            transaction,
            harness.authority,
        )
        receipt, _ = _write_branch(harness, ledger, harness.branch)
        subject._consume_branch_mutation_receipt(ledger, receipt)
        subject._seal_owner_receipt_ledger(ledger, (receipt,))
        with pytest.raises(subject.InactiveOwnerTransactionError):
            subject._execute_hypothesis_owner_update(
                harness.hypothesis_store,
                ledger,
                harness.hypothesis,
                "UPDATE hypotheses SET owner_revision = 1",
            )
    subject._close_owner_receipt_ledger(ledger, harness.authority)
    with pytest.raises(subject.InactiveOwnerTransactionError):
        subject._consume_branch_mutation_receipt(ledger, receipt)


def test_wrong_store_authority_and_database_authority_are_rejected(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path / "a")
    other = _harness(tmp_path / "b")
    with pytest.raises(RuntimeError, match="rollback binding test"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            with pytest.raises(subject.InvalidOwnerReceiptError):
                subject._execute_branch_owner_update(
                    harness.hypothesis_store,
                    ledger,
                    harness.branch,
                    "UPDATE branches SET owner_revision = 1",
                )
            with pytest.raises(
                subject.InvalidOwnerReceiptError,
                match="another database",
            ):
                subject._execute_branch_owner_update(
                    other.branch_store,
                    ledger,
                    harness.branch,
                    "UPDATE branches SET owner_revision = 1",
                )
            raise RuntimeError("rollback binding test")


def test_copied_context_and_cross_thread_cannot_use_owner_ledger(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    manager = sqlite_boundary.immediate_transaction(harness.authority)
    transaction = manager.__enter__()
    ledger = subject._attach_owner_receipt_ledger(
        transaction,
        harness.authority,
    )
    copied = contextvars.copy_context()
    with pytest.raises(
        sqlite_boundary.InactiveImmediateTransactionError,
        match="another Context",
    ):
        copied.run(
            subject._execute_branch_owner_update,
            harness.branch_store,
            ledger,
            harness.branch,
            "UPDATE branches SET owner_revision = 1",
        )

    errors: list[BaseException] = []

    def _cross_thread() -> None:
        try:
            subject._execute_branch_owner_update(
                harness.branch_store,
                ledger,
                harness.branch,
                "UPDATE branches SET owner_revision = 1",
            )
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=_cross_thread)
    thread.start()
    thread.join()
    assert len(errors) == 1
    assert isinstance(errors[0], subject.InactiveOwnerTransactionError)
    error = RuntimeError("rollback context test")
    assert manager.__exit__(RuntimeError, error, None) is False


def test_close_ledger_rejects_cross_thread_and_copied_context(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    manager = sqlite_boundary.immediate_transaction(harness.authority)
    transaction = manager.__enter__()
    ledger = subject._attach_owner_receipt_ledger(
        transaction,
        harness.authority,
    )
    errors: list[BaseException] = []

    def _close_cross_thread() -> None:
        try:
            subject._close_owner_receipt_ledger(ledger, harness.authority)
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=_close_cross_thread)
    thread.start()
    thread.join()
    assert len(errors) == 1
    assert isinstance(errors[0], subject.InactiveOwnerTransactionError)
    with pytest.raises(subject.InactiveOwnerTransactionError, match="Context"):
        contextvars.copy_context().run(
            subject._close_owner_receipt_ledger,
            ledger,
            harness.authority,
        )
    assert subject._lookup_ledger(ledger).phase is subject._LedgerPhase.OPEN
    subject._close_owner_receipt_ledger(ledger, harness.authority)
    error = RuntimeError("rollback closed ledger")
    assert manager.__exit__(RuntimeError, error, None) is False


def test_owner_ledger_must_attach_before_any_participant_statement(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        sqlite_boundary._execute_participant(
            transaction,
            harness.authority,
            "SELECT 1",
        )
        with pytest.raises(
            sqlite_boundary.InvalidImmediateTransactionError,
            match="before participant",
        ):
            subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )


def test_abandoned_ledger_gc_keeps_commit_fail_closed(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    gc.collect()
    initial_ledgers = len(subject._LEDGER_STATES)
    initial_transactions = len(subject._TRANSACTION_LEDGERS)

    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            ledger_ref = weakref.ref(ledger)
            del ledger
            gc.collect()
            assert ledger_ref() is None

    del transaction
    gc.collect()
    assert len(subject._LEDGER_STATES) == initial_ledgers
    assert len(subject._TRANSACTION_LEDGERS) == initial_transactions


def test_receipt_registry_does_not_keep_completed_receipts_alive(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    gc.collect()
    initial_receipts = len(subject._RECEIPT_STATES)

    def _commit_once() -> tuple[
        weakref.ReferenceType[subject.OwnerMutationReceipt],
        weakref.ReferenceType[subject._OwnerReceiptLedger],
    ]:
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            receipt, _ = _write_branch(harness, ledger, harness.branch)
            subject._consume_branch_mutation_receipt(ledger, receipt)
            subject._seal_owner_receipt_ledger(ledger, (receipt,))
            return weakref.ref(receipt), weakref.ref(ledger)

    receipt_ref, ledger_ref = _commit_once()
    gc.collect()
    assert receipt_ref() is None
    assert ledger_ref() is None
    assert len(subject._RECEIPT_STATES) == initial_receipts


def test_creation_authorization_registry_retains_no_completed_capabilities(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    initial = RevisionedBranchRecord.from_value(
        _branch(branch_id="branch-new"),
        owner_revision=0,
    )
    gc.collect()
    initial_authorizations = len(subject._CREATION_AUTHORIZATION_STATES)

    def _commit_once() -> tuple[
        weakref.ReferenceType[subject._OwnerCreationAuthorization],
        weakref.ReferenceType[subject.OwnerCreationReceipt],
        weakref.ReferenceType[subject._OwnerReceiptLedger],
    ]:
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = subject._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            authorization, _, receipt = _prepare_branch_creation(
                harness,
                transaction,
                ledger,
                initial,
            )
            _complete_branch_creation(
                harness,
                transaction,
                ledger,
                authorization,
                receipt,
            )
            subject._consume_branch_creation_receipt(ledger, receipt)
            subject._seal_owner_receipt_ledger(ledger, (receipt,))
            return weakref.ref(authorization), weakref.ref(receipt), weakref.ref(ledger)

    authorization_ref, receipt_ref, ledger_ref = _commit_once()
    gc.collect()
    assert authorization_ref() is None
    assert receipt_ref() is None
    assert ledger_ref() is None
    assert len(subject._CREATION_AUTHORIZATION_STATES) == initial_authorizations
