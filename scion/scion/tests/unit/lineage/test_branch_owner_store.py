from __future__ import annotations

import ast
import inspect
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pytest

from scion.core.models import Branch, BranchState
from scion.lineage import branch_owner_store as subject
from scion.lineage import owner_transaction as owner
from scion.lineage import sqlite_connection as sqlite_boundary
from scion.lineage.durable_owner import (
    DurableOwnerIntegrityError,
    OwnerAlreadyExists,
    OwnerPayloadConflict,
    OwnerRevisionConflict,
    RevisionedBranchRecord,
)


@dataclass(frozen=True)
class _Harness:
    path: Path
    authority: sqlite_boundary.CampaignDatabaseAuthority
    store: subject.BranchStore
    expected: RevisionedBranchRecord


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
        failure_codes=["SCREENING_FAILED"],
        created_at=datetime(2026, 7, 16, 1, 2, 3),
        updated_at=datetime(2026, 7, 16, 1, 2, 4),
        direction="local-search",
        weight_revision=3,
        branch_code_status="candidate_committed",
        branch_evidence_summary={"complete": True, "score": 1.25},
        infra_block_count=0,
    )


def _target(
    expected: RevisionedBranchRecord,
    *,
    state: BranchState = BranchState.READY_VALIDATE,
) -> Branch:
    value = expected.value()
    value.state = state
    value.updated_at = datetime(2026, 7, 16, 2, 3, 4)
    value.failure_codes.append("TARGET_READY")
    value.branch_evidence_summary["target"] = state.value
    return value


def _create_schema(connection: sqlite3.Connection) -> None:
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
            owner_revision INTEGER NOT NULL CHECK (
                typeof(owner_revision) = 'integer' AND owner_revision >= 0
            ),
            owner_protocol_generation TEXT NOT NULL CHECK (
                owner_protocol_generation = 'durable-owner.v1'
            )
        );

        CREATE TRIGGER branches_no_delete
        BEFORE DELETE ON branches
        BEGIN
            SELECT RAISE(ABORT, 'durable owner deletion is forbidden');
        END;

        CREATE TRIGGER branches_owner_cas
        BEFORE UPDATE ON branches
        WHEN NEW.branch_id != OLD.branch_id
          OR NEW.owner_protocol_generation != OLD.owner_protocol_generation
          OR NEW.owner_revision != OLD.owner_revision + 1
        BEGIN
            SELECT RAISE(ABORT, 'durable owner CAS contract is required');
        END;
        """)


def _insert_seed(
    connection: sqlite3.Connection,
    token: RevisionedBranchRecord,
) -> None:
    connection.execute(
        subject._BRANCH_INSERT_SQL,
        (
            *subject._branch_storage_values(token),
            token.owner_revision,
            subject._OWNER_PROTOCOL_GENERATION,
        ),
    )


def _harness(tmp_path: Path) -> _Harness:
    path = tmp_path / "focused-branch-owner.db"
    expected = RevisionedBranchRecord.from_value(_branch(), owner_revision=0)
    connection = sqlite_boundary._connect_sqlite(path)
    try:
        _create_schema(connection)
        _insert_seed(connection, expected)
        connection.commit()
    finally:
        connection.close()
    authority = sqlite_boundary._issue_test_campaign_database_authority(path)
    return _Harness(
        path=path,
        authority=authority,
        store=subject.BranchStore(authority),
        expected=expected,
    )


def _load(
    harness: _Harness, branch_id: str = "branch-1"
) -> RevisionedBranchRecord | None:
    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        return harness.store.load_revisioned_in(transaction, branch_id)


def _authorize_branch_creation(
    harness: _Harness,
    transaction: sqlite_boundary.ImmediateTransaction,
    ledger: owner._OwnerReceiptLedger,
    target: RevisionedBranchRecord,
) -> tuple[
    owner._OwnerCreationAuthorizerAuthority,
    owner._OwnerCreationAuthorization,
]:
    authorizer = owner._issue_branch_creation_authorizer_authority(harness.authority)
    authorization = owner._register_branch_creation_authorization(
        authorizer,
        transaction,
        ledger,
        target.branch_id,
        target.payload_sha256,
    )
    return authorizer, authorization


def test_registry_snapshot_readers_return_single_and_complete_inventory(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    second = RevisionedBranchRecord.from_value(
        _branch(branch_id="branch-2", state=BranchState.VALIDATING),
        owner_revision=3,
    )
    connection = sqlite_boundary._connect_sqlite(harness.path)
    try:
        _insert_seed(connection, second)
        connection.commit()
    finally:
        connection.close()

    with sqlite_boundary._independent_authority_read_snapshot(
        harness.authority
    ) as snapshot:
        assert (
            harness.store._load_revisioned_branch_from_snapshot(
                snapshot,
                harness.expected.branch_id,
            )
            == harness.expected
        )
        assert (
            harness.store._load_revisioned_branch_from_snapshot(
                snapshot,
                "branch-missing",
            )
            is None
        )
        assert harness.store._load_all_revisioned_branches_from_snapshot(snapshot) == (
            harness.expected,
            second,
        )

    with pytest.raises(sqlite_boundary.InactiveImmediateTransactionError):
        harness.store._load_revisioned_branch_from_snapshot(
            snapshot,
            harness.expected.branch_id,
        )


def test_registry_snapshot_reader_reuses_strict_complete_decoder(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    connection = sqlite_boundary._connect_sqlite(harness.path)
    try:
        connection.execute("""
            UPDATE branches
            SET failure_codes = '{}', owner_revision = owner_revision + 1
            WHERE branch_id = 'branch-1'
            """)
        connection.commit()
    finally:
        connection.close()

    with sqlite_boundary._independent_authority_read_snapshot(
        harness.authority
    ) as snapshot:
        with pytest.raises(DurableOwnerIntegrityError, match="list of strings"):
            harness.store._load_revisioned_branch_from_snapshot(
                snapshot,
                harness.expected.branch_id,
            )


def test_complete_read_and_cas_round_trip_detach_caller_target(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    assert _load(harness) == harness.expected
    target = _target(harness.expected)
    target_token = RevisionedBranchRecord.from_value(target, owner_revision=1)

    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        ledger = owner._attach_owner_receipt_ledger(
            transaction,
            harness.authority,
        )
        receipt = harness.store.compare_and_swap_in(
            transaction,
            harness.expected,
            target,
        )
        target.state = BranchState.ABANDONED
        target.failure_codes.append("CALLER_MUTATION")
        target.branch_evidence_summary["target"] = "mutated"
        witness = owner._consume_branch_mutation_receipt(ledger, receipt)
        assert witness.expected_token == harness.expected
        assert witness.committed_token == target_token
        owner._seal_owner_receipt_ledger(ledger, (receipt,))

    assert _load(harness) == target_token


def test_insert_once_round_trip_issues_creation_receipt(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    target = _branch(branch_id="branch-new", state=BranchState.NEW)
    target_token = RevisionedBranchRecord.from_value(target, owner_revision=0)

    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        ledger = owner._attach_owner_receipt_ledger(
            transaction,
            harness.authority,
        )
        authorizer, authorization = _authorize_branch_creation(
            harness,
            transaction,
            ledger,
            target_token,
        )
        receipt = harness.store.insert_once_in(
            transaction,
            target,
            authorization,
        )
        outcome_witness = owner._issue_branch_semantic_creation_outcome_witness(
            authorizer,
            transaction,
            ledger,
            authorization,
        )
        owner._complete_branch_creation_authorization(
            authorizer,
            transaction,
            ledger,
            authorization,
            receipt,
            outcome_witness,
        )
        witness = owner._consume_branch_creation_receipt(ledger, receipt)
        assert witness.expected_token is None
        assert witness.committed_token == target_token
        owner._seal_owner_receipt_ledger(ledger, (receipt,))

    assert _load(harness, "branch-new") == target_token


def test_same_revision_payload_drift_is_authoritative_conflict(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    drifted_value = harness.expected.value()
    drifted_value.state = BranchState.VALIDATING
    drifted = RevisionedBranchRecord.from_value(drifted_value, owner_revision=0)

    with pytest.raises(OwnerPayloadConflict, match="same revision"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = owner._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            harness.store.compare_and_swap_in(
                transaction,
                drifted,
                _target(drifted),
            )
            assert ledger is not None

    assert _load(harness) == harness.expected


@pytest.mark.parametrize("post_state", ["payload", "owner-id"])
def test_post_row_mismatch_leaves_pending_and_denies_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    post_state: str,
) -> None:
    harness = _harness(tmp_path)
    target = _target(harness.expected)
    original_read = subject._read_branch_in
    read_count = 0

    def _read_with_bad_post(*args, **kwargs):
        nonlocal read_count
        read_count += 1
        if read_count == 1:
            return original_read(*args, **kwargs)
        if post_state == "payload":
            wrong = _target(
                harness.expected,
                state=BranchState.VALIDATING,
            )
        else:
            wrong = _branch(
                branch_id="branch-wrong",
                state=BranchState.READY_VALIDATE,
            )
        return RevisionedBranchRecord.from_value(wrong, owner_revision=1)

    monkeypatch.setattr(subject, "_read_branch_in", _read_with_bad_post)
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = owner._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            with pytest.raises(OwnerPayloadConflict, match="post-state"):
                harness.store.compare_and_swap_in(
                    transaction,
                    harness.expected,
                    target,
                )
            assert owner._lookup_ledger(ledger).pending_write is not None

    monkeypatch.setattr(subject, "_read_branch_in", original_read)
    assert _load(harness) == harness.expected


def test_post_row_rejects_noncanonical_json_storage_and_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    target = _target(harness.expected)
    monkeypatch.setattr(
        subject,
        "_BRANCH_CAS_SQL",
        subject._BRANCH_CAS_SQL.replace(
            "failure_codes = ?",
            "failure_codes = ' ' || ?",
            1,
        ),
    )

    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = owner._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            with pytest.raises(
                DurableOwnerIntegrityError,
                match="not canonical: failure_codes",
            ):
                harness.store.compare_and_swap_in(
                    transaction,
                    harness.expected,
                    target,
                )
            assert owner._lookup_ledger(ledger).pending_write is not None

    assert _load(harness) == harness.expected


def test_authoritative_reread_rejects_actual_sql_payload_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)
    target = _target(harness.expected)
    monkeypatch.setattr(
        subject,
        "_BRANCH_CAS_SQL",
        subject._BRANCH_CAS_SQL.replace(
            "state = ?",
            "state = CASE WHEN ? IS NULL THEN 'validating' ELSE 'validating' END",
            1,
        ),
    )

    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = owner._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            with pytest.raises(OwnerPayloadConflict, match="post-state"):
                harness.store.compare_and_swap_in(
                    transaction,
                    harness.expected,
                    target,
                )
            assert owner._lookup_ledger(ledger).pending_write is not None

    assert _load(harness) == harness.expected


def test_stale_expected_token_loses_after_exact_first_commit(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    first_target = _target(harness.expected)
    with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
        ledger = owner._attach_owner_receipt_ledger(
            transaction,
            harness.authority,
        )
        receipt = harness.store.compare_and_swap_in(
            transaction,
            harness.expected,
            first_target,
        )
        owner._consume_branch_mutation_receipt(ledger, receipt)
        owner._seal_owner_receipt_ledger(ledger, (receipt,))

    competing_target = _target(
        harness.expected,
        state=BranchState.VALIDATING,
    )
    competing_store = subject.BranchStore(harness.authority)
    with pytest.raises(OwnerRevisionConflict, match="revision changed"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = owner._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            competing_store.compare_and_swap_in(
                transaction,
                harness.expected,
                competing_target,
            )
            assert ledger is not None

    assert _load(harness) == RevisionedBranchRecord.from_value(first_target, 1)


def test_wrong_target_id_is_rejected_before_write(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    wrong_target = _branch(
        branch_id="branch-wrong",
        state=BranchState.READY_VALIDATE,
    )
    with pytest.raises(OwnerPayloadConflict, match="identity"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = owner._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            harness.store.compare_and_swap_in(
                transaction,
                harness.expected,
                wrong_target,
            )
            assert ledger is not None
    assert _load(harness) == harness.expected


def test_zero_row_cas_leaves_pending_and_rolls_back(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    connection = sqlite_boundary._connect_sqlite(harness.path)
    try:
        connection.execute("""
            CREATE TRIGGER ignore_focused_branch_update
            BEFORE UPDATE ON branches
            BEGIN
                SELECT RAISE(IGNORE);
            END
            """)
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(DurableOwnerIntegrityError, match="changed zero rows"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = owner._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            harness.store.compare_and_swap_in(
                transaction,
                harness.expected,
                _target(harness.expected),
            )
            assert ledger is not None
    assert _load(harness) == harness.expected


def test_duplicate_insert_is_typed_and_does_not_replace(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    duplicate = _target(harness.expected)
    with pytest.raises(OwnerAlreadyExists, match="already exists"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = owner._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            duplicate_token = RevisionedBranchRecord.from_value(
                duplicate,
                owner_revision=0,
            )
            _, authorization = _authorize_branch_creation(
                harness,
                transaction,
                ledger,
                duplicate_token,
            )
            harness.store.insert_once_in(
                transaction,
                duplicate,
                authorization,
            )
            assert ledger is not None
    assert _load(harness) == harness.expected


def test_malformed_complete_row_is_integrity_error(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    connection = sqlite_boundary._connect_sqlite(harness.path)
    try:
        connection.execute("""
            UPDATE branches
            SET failure_codes = '{}', owner_revision = owner_revision + 1
            WHERE branch_id = 'branch-1'
            """)
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(DurableOwnerIntegrityError, match="list of strings"):
        _load(harness)


def test_receipt_issue_failure_keeps_pending_and_forces_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness(tmp_path)

    def _fail_issue(*_args, **_kwargs):
        raise DurableOwnerIntegrityError("injected receipt issue failure")

    monkeypatch.setattr(owner, "_issue_branch_mutation_receipt", _fail_issue)
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = owner._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            with pytest.raises(DurableOwnerIntegrityError, match="injected"):
                harness.store.compare_and_swap_in(
                    transaction,
                    harness.expected,
                    _target(harness.expected),
                )
            assert owner._lookup_ledger(ledger).pending_write is not None

    assert _load(harness) == harness.expected


def test_valid_write_without_receipt_closure_cannot_commit(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        with sqlite_boundary.immediate_transaction(harness.authority) as transaction:
            ledger = owner._attach_owner_receipt_ledger(
                transaction,
                harness.authority,
            )
            harness.store.compare_and_swap_in(
                transaction,
                harness.expected,
                _target(harness.expected),
            )
            assert ledger is not None
    assert _load(harness) == harness.expected


def test_dormant_public_and_static_surface_is_exact() -> None:
    forbidden_parameters = {
        "sql",
        "parameters",
        "ledger",
        "write_fact",
        "committed_token",
    }
    for method_name in (
        "load_revisioned_in",
        "compare_and_swap_in",
        "insert_once_in",
    ):
        parameters = set(
            inspect.signature(getattr(subject.BranchStore, method_name)).parameters
        )
        assert not parameters & forbidden_parameters

    for statement in (
        subject._BRANCH_SELECT_SQL,
        subject._BRANCH_SELECT_ALL_SQL,
        subject._BRANCH_INSERT_SQL,
        subject._BRANCH_CAS_SQL,
    ):
        upper = statement.upper()
        assert "REPLACE" not in upper
        assert "INSERT OR" not in upper
        assert "UPDATE OR" not in upper
        assert "ON CONFLICT" not in upper
        assert "DELETE" not in upper
        assert "PAYLOAD_SHA256" not in upper

    assert tuple(
        inspect.signature(
            subject.BranchStore._load_revisioned_branch_from_snapshot
        ).parameters
    ) == ("self", "snapshot", "branch_id")
    assert tuple(
        inspect.signature(
            subject.BranchStore._load_all_revisioned_branches_from_snapshot
        ).parameters
    ) == ("self", "snapshot")
    for column in subject._BRANCH_COLUMNS:
        assert column in subject._BRANCH_SELECT_SQL
        assert column in subject._BRANCH_SELECT_ALL_SQL
    assert "ORDER BY branch_id ASC" in subject._BRANCH_SELECT_ALL_SQL

    source_path = Path(subject.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    execute_sql_names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {
            "_execute_branch_owner_update",
            "_execute_branch_owner_insert",
        }:
            continue
        assert len(node.args) >= 4
        sql_index = 4 if node.func.attr == "_execute_branch_owner_insert" else 3
        assert isinstance(node.args[sql_index], ast.Name)
        execute_sql_names.append(node.args[sql_index].id)
    assert sorted(execute_sql_names) == ["_BRANCH_CAS_SQL", "_BRANCH_INSERT_SQL"]
