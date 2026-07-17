from __future__ import annotations

import contextvars
import os
import sqlite3
import threading
from pathlib import Path
from typing import Callable, Iterator

import pytest

import scion.lineage.sqlite_connection as sqlite_connection_module
from scion.lineage.sqlite_connection import (
    CampaignDatabaseAuthority,
    ImmediateResult,
    ImmediateTransaction,
    InactiveImmediateTransactionError,
    InvalidCampaignDatabaseAuthorityError,
    InvalidImmediateTransactionError,
    NestedImmediateTransactionError,
    ParticipantStatementError,
    SQLiteConnectionCleanupError,
    SQLiteConnectionPolicyError,
    TransactionControlError,
    immediate_transaction,
    require_active_immediate_transaction,
)


def _scalar(connection: sqlite3.Connection, pragma: str) -> object:
    row = connection.execute(f"PRAGMA {pragma}").fetchone()
    assert row is not None
    return row[0]


def _create_values_table(db_path: Path) -> CampaignDatabaseAuthority:
    connection = sqlite_connection_module._connect_sqlite(db_path)
    try:
        connection.execute(
            "CREATE TABLE values_under_test (value TEXT PRIMARY KEY)"
        )
    finally:
        connection.close()
    return sqlite_connection_module._issue_test_campaign_database_authority(db_path)


def _stored_values(db_path: Path) -> list[str]:
    connection = sqlite3.connect(db_path)
    try:
        return [
            str(row[0])
            for row in connection.execute(
                "SELECT value FROM values_under_test ORDER BY value"
            )
        ]
    finally:
        connection.close()


def _execute(
    transaction: ImmediateTransaction,
    sql: str,
    parameters: tuple[object, ...] = (),
) -> ImmediateResult:
    authority = sqlite_connection_module._lookup_capability_state(
        transaction
    ).authority
    return sqlite_connection_module._execute_participant(
        transaction,
        authority,
        sql,
        parameters,
    )


def _executemany(
    transaction: ImmediateTransaction,
    sql: str,
    rows: tuple[tuple[object, ...], ...],
) -> ImmediateResult:
    authority = sqlite_connection_module._lookup_capability_state(
        transaction
    ).authority
    return sqlite_connection_module._executemany_participant(
        transaction,
        authority,
        sql,
        rows,
    )


def _exception_contexts(error: BaseException) -> Iterator[BaseException]:
    seen = {id(error)}
    current = error.__context__
    while current is not None and id(current) not in seen:
        yield current
        seen.add(id(current))
        current = current.__context__


class _FaultConnection(sqlite3.Connection):
    fail_commit = False
    fail_after_commit = False
    fail_rollback = False
    fail_close = False

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.events: list[str] = []
        self.closed = False
        self.rollback_probe: Callable[[], None] | None = None

    def commit(self) -> None:
        self.events.append("commit")
        if self.fail_commit:
            raise RuntimeError("injected commit failure")
        super().commit()
        if self.fail_after_commit:
            raise RuntimeError("injected post-commit failure")

    def rollback(self) -> None:
        self.events.append("rollback")
        if self.rollback_probe is not None:
            self.rollback_probe()
        if self.fail_rollback:
            raise RuntimeError("injected rollback failure")
        super().rollback()

    def close(self) -> None:
        self.events.append("close")
        self.closed = True
        super().close()
        if self.fail_close:
            raise RuntimeError("injected close failure")


class _TrackingCursor(sqlite3.Cursor):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.closed = False

    def close(self) -> None:
        self.closed = True
        super().close()


class _TrackingConnection(sqlite3.Connection):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.last_cursor: _TrackingCursor | None = None

    def cursor(self, *args: object, **kwargs: object) -> _TrackingCursor:
        assert not args
        assert not kwargs
        cursor = super().cursor(factory=_TrackingCursor)
        assert isinstance(cursor, _TrackingCursor)
        self.last_cursor = cursor
        return cursor


def _inject_connection(
    monkeypatch: pytest.MonkeyPatch,
    connection: sqlite3.Connection,
) -> None:
    def _connect(
        _authority: CampaignDatabaseAuthority,
        *,
        busy_timeout_ms: int,
    ) -> tuple[sqlite3.Connection, int, int]:
        assert busy_timeout_ms > 0
        database_path = sqlite_connection_module._lookup_authority_state(
            _authority
        ).database_path
        descriptor = os.open(
            database_path,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0),
        )
        return connection, descriptor, 1

    monkeypatch.setattr(
        sqlite_connection_module,
        "_connect_authority_sqlite",
        _connect,
    )
    monkeypatch.setattr(
        sqlite_connection_module,
        "_assert_sqlite_main_not_moved",
        lambda _handle: None,
    )


def test_raw_factory_is_private_and_applies_exact_policy(tmp_path: Path) -> None:
    assert "connect_sqlite" not in sqlite_connection_module.__all__
    assert not hasattr(sqlite_connection_module, "connect_sqlite")

    connection = sqlite_connection_module._connect_sqlite(
        tmp_path / "policy.db",
        busy_timeout_ms=1_237,
    )
    try:
        assert connection.isolation_level is None
        assert connection.row_factory is sqlite3.Row
        assert str(_scalar(connection, "journal_mode")).lower() == "wal"
        assert int(_scalar(connection, "synchronous")) == 2
        assert int(_scalar(connection, "foreign_keys")) == 1
        assert int(_scalar(connection, "recursive_triggers")) == 1
        assert int(_scalar(connection, "busy_timeout")) == 1_237
    finally:
        connection.close()


@pytest.mark.parametrize("value", (0, -1, True, 1.5, "5000"))
def test_raw_factory_rejects_invalid_busy_timeout(
    tmp_path: Path,
    value: object,
) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        sqlite_connection_module._connect_sqlite(  # type: ignore[arg-type]
            tmp_path / "invalid-timeout.db",
            busy_timeout_ms=value,
        )


def test_cached_statements_zero_rechecks_identical_sql(tmp_path: Path) -> None:
    connection = sqlite_connection_module._connect_sqlite(tmp_path / "cache.db")
    try:
        connection.execute("CREATE TABLE branches(branch_id TEXT PRIMARY KEY, x INT)")
        connection.execute("INSERT INTO branches VALUES('b', 0)")
        permit = {"open": True}
        calls: list[bool] = []

        def _authorizer(
            action: int,
            table: str | None,
            _column: str | None,
            _database: str | None,
            _source: str | None,
        ) -> int:
            if action == sqlite3.SQLITE_UPDATE and table == "branches":
                calls.append(permit["open"])
                return sqlite3.SQLITE_OK if permit["open"] else sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        connection.set_authorizer(_authorizer)
        sql = "UPDATE branches SET x=x+1 WHERE branch_id='b'"
        connection.execute(sql)
        permit["open"] = False
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            connection.execute(sql)
        assert calls == [True, False]
        assert connection.execute(
            "SELECT x FROM branches WHERE branch_id='b'"
        ).fetchone()[0] == 1
    finally:
        connection.close()


def test_authority_construction_subclass_and_forgery_fail(tmp_path: Path) -> None:
    with pytest.raises(InvalidCampaignDatabaseAuthorityError):
        CampaignDatabaseAuthority()

    with pytest.raises(TypeError, match="sealed"):

        class _ForbiddenAuthority(CampaignDatabaseAuthority):
            pass

    forged = object.__new__(CampaignDatabaseAuthority)
    with pytest.raises(InvalidCampaignDatabaseAuthorityError, match="not issued"):
        with immediate_transaction(forged):
            pytest.fail("forged authority unexpectedly opened")

    with pytest.raises(InvalidCampaignDatabaseAuthorityError):
        with immediate_transaction(tmp_path / "not-an-authority.db"):  # type: ignore[arg-type]
            pytest.fail("path unexpectedly acted as authority")


def test_authority_rechecks_execution_lock_and_file_identity(tmp_path: Path) -> None:
    db_path = tmp_path / "authority.db"
    _create_values_table(db_path)
    lock = {"held": True}
    authority = sqlite_connection_module._issue_test_campaign_database_authority(
        db_path,
        execution_lock_is_held=lambda: lock["held"],
    )

    lock["held"] = False
    with pytest.raises(SQLiteConnectionPolicyError, match="lock is not held"):
        with immediate_transaction(authority):
            pytest.fail("released lock unexpectedly opened")

    lock["held"] = True
    original = tmp_path / "authority-original.db"
    db_path.rename(original)
    replacement = sqlite3.connect(db_path)
    replacement.close()
    with pytest.raises(SQLiteConnectionPolicyError, match="identity changed"):
        with immediate_transaction(authority):
            pytest.fail("replacement database unexpectedly opened")


def test_authority_identity_validator_runs_before_begin(tmp_path: Path) -> None:
    db_path = tmp_path / "identity-validator.db"
    _create_values_table(db_path)
    calls: list[tuple[str, str, bool]] = []

    def _validate(
        connection: sqlite3.Connection,
        campaign_id: str,
        schema_generation: str,
    ) -> None:
        calls.append((campaign_id, schema_generation, connection.in_transaction))

    authority = sqlite_connection_module._issue_test_campaign_database_authority(
        db_path,
        campaign_id="campaign-1",
        schema_generation="durable-owner.v1",
        validate_database_identity=_validate,
    )
    with immediate_transaction(authority):
        pass
    assert calls == [("campaign-1", "durable-owner.v1", False)]


def test_immediate_transaction_commits_and_ends_capability(tmp_path: Path) -> None:
    db_path = tmp_path / "commit.db"
    authority = _create_values_table(db_path)

    leaked: ImmediateTransaction
    result: ImmediateResult
    with immediate_transaction(authority) as transaction:
        leaked = transaction
        assert (
            require_active_immediate_transaction(transaction, authority)
            is transaction
        )
        assert not hasattr(transaction, "execute")
        assert not hasattr(transaction, "executemany")
        assert not hasattr(transaction, "commit")
        result = _execute(
            transaction,
            "INSERT INTO values_under_test(value) VALUES (?)",
            ("committed",),
        )
        assert result.rowcount == 1

    assert _stored_values(db_path) == ["committed"]
    with pytest.raises(InactiveImmediateTransactionError):
        require_active_immediate_transaction(leaked, authority)
    with pytest.raises(InactiveImmediateTransactionError):
        result.rowcount


def test_immediate_transaction_rolls_back_and_ends_capability(tmp_path: Path) -> None:
    db_path = tmp_path / "rollback.db"
    authority = _create_values_table(db_path)
    leaked: ImmediateTransaction | None = None

    with pytest.raises(RuntimeError, match="injected participant failure"):
        with immediate_transaction(authority) as transaction:
            leaked = transaction
            _execute(
                transaction,
                "INSERT INTO values_under_test(value) VALUES (?)",
                ("rolled-back",),
            )
            raise RuntimeError("injected participant failure")

    assert _stored_values(db_path) == []
    assert leaked is not None
    with pytest.raises(InactiveImmediateTransactionError):
        require_active_immediate_transaction(leaked, authority)


def test_capability_construction_subclass_and_forgery_fail(tmp_path: Path) -> None:
    with pytest.raises(InvalidImmediateTransactionError):
        ImmediateTransaction()

    with pytest.raises(TypeError, match="sealed"):

        class _ForbiddenTransaction(ImmediateTransaction):
            pass

    forged = object.__new__(ImmediateTransaction)
    authority = _create_values_table(tmp_path / "forged.db")
    with pytest.raises(InvalidImmediateTransactionError, match="not issued"):
        require_active_immediate_transaction(forged, authority)


def test_nested_and_fresh_context_transactions_fail_without_damaging_outer(
    tmp_path: Path,
) -> None:
    outer_path = tmp_path / "outer.db"
    nested_path = tmp_path / "nested.db"
    outer_authority = _create_values_table(outer_path)
    nested_authority = _create_values_table(nested_path)

    with immediate_transaction(outer_authority) as outer:
        _execute(
            outer,
            "INSERT INTO values_under_test(value) VALUES (?)",
            ("before-nested",),
        )
        with pytest.raises(NestedImmediateTransactionError):
            with immediate_transaction(nested_authority):
                pytest.fail("ordinary nested transaction unexpectedly opened")

        def _open_in_fresh_context() -> None:
            with immediate_transaction(nested_authority):
                pytest.fail("fresh-Context nested transaction unexpectedly opened")

        with pytest.raises(NestedImmediateTransactionError):
            contextvars.Context().run(_open_in_fresh_context)
        with pytest.raises(InactiveImmediateTransactionError, match="Context"):
            contextvars.Context().run(
                require_active_immediate_transaction,
                outer,
                outer_authority,
            )
        require_active_immediate_transaction(outer, outer_authority)
        _execute(
            outer,
            "INSERT INTO values_under_test(value) VALUES (?)",
            ("after-nested",),
        )

    assert _stored_values(outer_path) == ["after-nested", "before-nested"]
    assert _stored_values(nested_path) == []


def test_capability_cannot_cross_thread(tmp_path: Path) -> None:
    authority = _create_values_table(tmp_path / "cross-thread.db")
    errors: list[BaseException] = []

    with immediate_transaction(authority) as transaction:
        def _worker() -> None:
            try:
                require_active_immediate_transaction(transaction, authority)
            except BaseException as error:
                errors.append(error)

        thread = threading.Thread(target=_worker)
        thread.start()
        thread.join()
        assert len(errors) == 1
        assert isinstance(errors[0], InactiveImmediateTransactionError)
        assert "issuing thread" in str(errors[0])
        require_active_immediate_transaction(transaction, authority)


def test_transaction_acquires_immediate_write_reservation(tmp_path: Path) -> None:
    db_path = tmp_path / "immediate-reservation.db"
    authority = _create_values_table(db_path)

    with immediate_transaction(authority):
        competitor = sqlite_connection_module._connect_sqlite(
            db_path,
            busy_timeout_ms=1,
        )
        try:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                competitor.execute("BEGIN IMMEDIATE")
        finally:
            if competitor.in_transaction:
                competitor.rollback()
            competitor.close()


@pytest.mark.parametrize(
    "sql",
    (
        "BEGIN",
        "COMMIT",
        "END TRANSACTION",
        "ROLLBACK",
        "SAVEPOINT nested",
        "RELEASE nested",
        "-- participant comment\nCOMMIT",
        "/* participant comment */ ROLLBACK",
        "; COMMIT",
        "; -- empty statement\n/* participant comment */ ROLLBACK",
    ),
)
def test_participant_cannot_take_over_transaction_control(
    tmp_path: Path,
    sql: str,
) -> None:
    authority = _create_values_table(tmp_path / "transaction-control.db")
    with immediate_transaction(authority) as transaction:
        with pytest.raises(TransactionControlError):
            _execute(transaction, sql)
        require_active_immediate_transaction(transaction, authority)


@pytest.mark.parametrize(
    "sql, keyword",
    (
        ("PRAGMA ignore_check_constraints=ON", "PRAGMA"),
        ("ATTACH DATABASE ':memory:' AS other", "ATTACH"),
        ("DETACH DATABASE other", "DETACH"),
        ("VACUUM", "VACUUM"),
        ("CREATE TABLE forbidden(x)", "CREATE"),
        ("DROP TABLE values_under_test", "DROP"),
    ),
)
def test_participant_statement_allowlist_rejects_connection_and_schema_sql(
    tmp_path: Path,
    sql: str,
    keyword: str,
) -> None:
    db_path = tmp_path / f"forbidden-{keyword}.db"
    authority = _create_values_table(db_path)
    with immediate_transaction(authority) as transaction:
        with pytest.raises(ParticipantStatementError, match=keyword):
            _execute(transaction, sql)

    connection = sqlite3.connect(db_path)
    try:
        connection.execute("INSERT INTO values_under_test(value) VALUES ('ok')")
        assert connection.execute(
            "SELECT value FROM values_under_test"
        ).fetchone()[0] == "ok"
    finally:
        connection.close()


def test_rejected_pragma_cannot_weaken_check_constraint(tmp_path: Path) -> None:
    db_path = tmp_path / "check-policy.db"
    connection = sqlite_connection_module._connect_sqlite(db_path)
    try:
        connection.execute(
            "CREATE TABLE checked_values(value INTEGER CHECK(value > 0))"
        )
    finally:
        connection.close()
    authority = sqlite_connection_module._issue_test_campaign_database_authority(
        db_path
    )

    with immediate_transaction(authority) as transaction:
        with pytest.raises(ParticipantStatementError, match="PRAGMA"):
            _execute(transaction, "PRAGMA ignore_check_constraints=ON")
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint"):
            _execute(transaction, "INSERT INTO checked_values VALUES (-1)")


@pytest.mark.parametrize("sql", ("", "   ; ;  ", "-- only a comment", "/* open"))
def test_participant_rejects_empty_or_malformed_statement(
    tmp_path: Path,
    sql: str,
) -> None:
    authority = _create_values_table(tmp_path / "empty.db")
    with immediate_transaction(authority) as transaction:
        with pytest.raises(ParticipantStatementError):
            _execute(transaction, sql)


def test_allowed_statement_scanner_handles_comments_semicolons_and_with(
    tmp_path: Path,
) -> None:
    authority = _create_values_table(tmp_path / "scanner.db")
    with immediate_transaction(authority) as transaction:
        result = _execute(
            transaction,
            "; ; -- leading\r\n/* comment */ WITH answer(value) AS (SELECT 42) "
            "SELECT value FROM answer",
        )
        row = result.fetchone()
        assert row is not None
        assert row["value"] == 42


def test_multiple_executable_statements_fail_and_roll_back(tmp_path: Path) -> None:
    db_path = tmp_path / "multiple.db"
    authority = _create_values_table(db_path)
    with pytest.raises(sqlite3.ProgrammingError, match="one statement"):
        with immediate_transaction(authority) as transaction:
            _execute(
                transaction,
                "INSERT INTO values_under_test VALUES ('first'); "
                "INSERT INTO values_under_test VALUES ('second')",
            )
    assert _stored_values(db_path) == []


def test_extension_loading_remains_disabled(tmp_path: Path) -> None:
    authority = _create_values_table(tmp_path / "extension.db")
    with immediate_transaction(authority) as transaction:
        with pytest.raises(sqlite3.OperationalError, match="not authorized"):
            _execute(transaction, "SELECT load_extension(?)", ("missing-extension",))


def test_materialized_results_cover_dml_returning_and_cursor_ergonomics(
    tmp_path: Path,
) -> None:
    authority = _create_values_table(tmp_path / "materialized.db")
    leaked: list[ImmediateResult] = []

    with immediate_transaction(authority) as transaction:
        batch = _executemany(
            transaction,
            "INSERT INTO values_under_test(value) VALUES (?)",
            (("b",), ("a",)),
        )
        assert batch.rowcount == 2
        assert batch.fetchall() == []
        returning = _execute(
            transaction,
            "INSERT INTO values_under_test(value) VALUES (?) RETURNING value",
            ("c",),
        )
        assert returning.rowcount == 1
        assert returning.lastrowid is not None
        assert returning.description is not None
        returned = returning.fetchone()
        assert returned is not None and returned["value"] == "c"
        assert returning.fetchone() is None

        selected = _execute(
            transaction,
            "SELECT value FROM values_under_test ORDER BY value",
        )
        first = selected.fetchmany(1)
        assert [row["value"] for row in first] == ["a"]
        assert [row["value"] for row in selected] == ["b", "c"]
        empty = _execute(
            transaction,
            "SELECT value FROM values_under_test WHERE 0",
        )
        assert empty.fetchone() is None
        leaked.extend((batch, returning, selected, empty))

    for result in leaked:
        with pytest.raises(InactiveImmediateTransactionError):
            result.fetchall()


def test_materialized_result_object_graph_retains_no_cursor_or_connection(
    tmp_path: Path,
) -> None:
    authority = _create_values_table(tmp_path / "object-graph.db")

    with immediate_transaction(authority) as transaction:
        result = _execute(transaction, "SELECT 1 AS value")
        assert not hasattr(result, "_cursor")
        assert not hasattr(result, "connection")

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
            if type(value).__module__ != sqlite_connection_module.__name__:
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

        _walk(result)


def test_executemany_mid_batch_failure_closes_cursor_and_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "executemany-failure.db"
    authority = _create_values_table(db_path)
    connection = sqlite3.connect(
        db_path,
        isolation_level=None,
        cached_statements=0,
        factory=_TrackingConnection,
    )
    assert isinstance(connection, _TrackingConnection)
    connection.row_factory = sqlite3.Row
    _inject_connection(monkeypatch, connection)

    with pytest.raises(sqlite3.IntegrityError):
        with immediate_transaction(authority) as transaction:
            _executemany(
                transaction,
                "INSERT INTO values_under_test(value) VALUES (?)",
                (("duplicate",), ("duplicate",)),
            )

    assert connection.last_cursor is not None
    assert connection.last_cursor.closed is True
    assert _stored_values(db_path) == []


def test_returning_materialization_failure_closes_cursor_and_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "returning-failure.db"
    authority = _create_values_table(db_path)
    connection = sqlite3.connect(
        db_path,
        isolation_level=None,
        cached_statements=0,
        factory=_TrackingConnection,
    )
    assert isinstance(connection, _TrackingConnection)

    def _raise_while_materializing(
        _cursor: sqlite3.Cursor,
        _row: tuple[object, ...],
    ) -> sqlite3.Row:
        raise RuntimeError("injected materialization failure")

    connection.row_factory = _raise_while_materializing
    _inject_connection(monkeypatch, connection)

    with pytest.raises(RuntimeError, match="materialization failure"):
        with immediate_transaction(authority) as transaction:
            _execute(
                transaction,
                "INSERT INTO values_under_test(value) VALUES (?) RETURNING value",
                ("rolled-back",),
            )

    assert connection.last_cursor is not None
    assert connection.last_cursor.closed is True
    assert _stored_values(db_path) == []


def test_commit_failure_is_primary_and_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "commit-failure.db"
    authority = _create_values_table(db_path)
    connection = sqlite3.connect(
        db_path,
        isolation_level=None,
        factory=_FaultConnection,
    )
    assert isinstance(connection, _FaultConnection)
    connection.row_factory = sqlite3.Row
    connection.fail_commit = True
    _inject_connection(monkeypatch, connection)

    with pytest.raises(RuntimeError, match="commit failure"):
        with immediate_transaction(authority) as transaction:
            _execute(
                transaction,
                "INSERT INTO values_under_test(value) VALUES (?)",
                ("rolled-back",),
            )

    assert connection.events == ["commit", "rollback", "close"]
    assert connection.closed is True
    assert _stored_values(db_path) == []


def test_commit_failure_deactivates_before_rollback_and_close(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "commit-settlement-order.db"
    authority = _create_values_table(db_path)
    connection = sqlite3.connect(
        db_path,
        isolation_level=None,
        factory=_FaultConnection,
    )
    assert isinstance(connection, _FaultConnection)
    connection.row_factory = sqlite3.Row
    connection.fail_commit = True
    _inject_connection(monkeypatch, connection)
    original_deactivate = (
        sqlite_connection_module._deactivate_coordinated_transaction
    )
    leaked: ImmediateTransaction | None = None

    def _record_deactivate(
        session: sqlite_connection_module._CoordinatedTransactionSession,
        exact_authority: CampaignDatabaseAuthority,
    ) -> None:
        original_deactivate(session, exact_authority)
        connection.events.append("deactivate")

    def _assert_deactivated_before_rollback() -> None:
        assert leaked is not None
        capability_state = sqlite_connection_module._lookup_capability_state(leaked)
        session = capability_state.session_ref()
        assert session is not None
        assert capability_state.active is False
        assert capability_state.connection is None
        assert sqlite_connection_module._lookup_session_state(
            session
        ).phase is sqlite_connection_module._SessionPhase.DEACTIVATED
        assert sqlite_connection_module._ACTIVE_TRANSACTION.get() is None
        assert sqlite_connection_module._thread_owner() is None

    connection.rollback_probe = _assert_deactivated_before_rollback
    monkeypatch.setattr(
        sqlite_connection_module,
        "_deactivate_coordinated_transaction",
        _record_deactivate,
    )

    with pytest.raises(RuntimeError, match="commit failure"):
        with immediate_transaction(authority) as transaction:
            leaked = transaction
            _execute(
                transaction,
                "INSERT INTO values_under_test(value) VALUES (?)",
                ("rolled-back",),
            )

    assert connection.events == ["commit", "deactivate", "rollback", "close"]
    assert connection.closed is True
    assert _stored_values(db_path) == []


def test_commit_then_raise_closes_before_independent_classification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "commit-then-raise.db"
    authority = _create_values_table(db_path)
    connection = sqlite3.connect(
        db_path,
        isolation_level=None,
        factory=_FaultConnection,
    )
    assert isinstance(connection, _FaultConnection)
    connection.row_factory = sqlite3.Row
    connection.fail_after_commit = True
    original_connect = sqlite_connection_module._connect_authority_sqlite
    _inject_connection(monkeypatch, connection)
    original_deactivate = (
        sqlite_connection_module._deactivate_coordinated_transaction
    )
    leaked_session: sqlite_connection_module._CoordinatedTransactionSession | None = None

    def _record_deactivate(
        session: sqlite_connection_module._CoordinatedTransactionSession,
        exact_authority: CampaignDatabaseAuthority,
    ) -> None:
        original_deactivate(session, exact_authority)
        connection.events.append("deactivate")

    monkeypatch.setattr(
        sqlite_connection_module,
        "_deactivate_coordinated_transaction",
        _record_deactivate,
    )

    with pytest.raises(RuntimeError, match="post-commit failure"):
        with immediate_transaction(authority) as transaction:
            leaked_session = sqlite_connection_module._lookup_capability_state(
                transaction
            ).session_ref()
            _execute(
                transaction,
                "INSERT INTO values_under_test(value) VALUES (?)",
                ("durable",),
            )

    assert leaked_session is not None
    assert connection.events == ["commit", "deactivate", "close"]
    assert connection.closed is True
    assert sqlite_connection_module._lookup_session_state(
        leaked_session
    ).phase is sqlite_connection_module._SessionPhase.CLOSED
    monkeypatch.setattr(
        sqlite_connection_module,
        "_connect_authority_sqlite",
        original_connect,
    )
    with sqlite_connection_module._independent_authority_read_snapshot(
        authority
    ) as snapshot:
        rows = sqlite_connection_module._execute_read_snapshot(
            snapshot,
            authority,
            "SELECT value FROM values_under_test",
        )
    assert [row[0] for row in rows] == ["durable"]


def test_handle_invalidation_error_still_settles_the_deactivated_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "deactivation-invalidation-error.db"
    authority = _create_values_table(db_path)
    connection = sqlite3.connect(
        db_path,
        isolation_level=None,
        factory=_FaultConnection,
    )
    assert isinstance(connection, _FaultConnection)
    connection.row_factory = sqlite3.Row
    _inject_connection(monkeypatch, connection)
    original_invalidate = sqlite_connection_module._invalidate_session_handles
    invalidate_calls = 0
    leaked: ImmediateTransaction | None = None
    leaked_session: sqlite_connection_module._CoordinatedTransactionSession | None = None

    def _fail_first_invalidation(
        state: sqlite_connection_module._SessionState,
    ) -> None:
        nonlocal invalidate_calls
        invalidate_calls += 1
        if invalidate_calls == 1:
            raise RuntimeError("injected handle invalidation failure")
        original_invalidate(state)

    monkeypatch.setattr(
        sqlite_connection_module,
        "_invalidate_session_handles",
        _fail_first_invalidation,
    )
    body_error = RuntimeError("body remains primary")

    with pytest.raises(RuntimeError, match="body remains primary") as caught:
        with immediate_transaction(authority) as transaction:
            leaked = transaction
            leaked_session = sqlite_connection_module._lookup_capability_state(
                transaction
            ).session_ref()
            _execute(
                transaction,
                "INSERT INTO values_under_test(value) VALUES (?)",
                ("must-roll-back",),
            )
            raise body_error

    assert caught.value is body_error
    assert [str(error) for error in _exception_contexts(caught.value)] == [
        "injected handle invalidation failure"
    ]
    assert invalidate_calls == 2
    assert leaked is not None
    assert leaked_session is not None
    capability_state = sqlite_connection_module._lookup_capability_state(leaked)
    session_state = sqlite_connection_module._lookup_session_state(leaked_session)
    assert capability_state.active is False
    assert capability_state.connection is None
    assert session_state.phase is sqlite_connection_module._SessionPhase.CLOSED
    assert session_state.connection is None
    assert connection.events == ["rollback", "close"]
    assert connection.closed is True
    assert sqlite_connection_module._ACTIVE_TRANSACTION.get() is None
    assert sqlite_connection_module._ACTIVE_COORDINATED_SESSION.get() is None
    assert sqlite_connection_module._thread_owner() is None
    assert sqlite_connection_module._thread_session_owner() is None
    assert _stored_values(db_path) == []


def test_body_error_remains_primary_over_rollback_and_close_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "cleanup-order.db"
    authority = _create_values_table(db_path)
    connection = sqlite3.connect(
        db_path,
        isolation_level=None,
        factory=_FaultConnection,
    )
    assert isinstance(connection, _FaultConnection)
    connection.row_factory = sqlite3.Row
    connection.fail_rollback = True
    connection.fail_close = True
    _inject_connection(monkeypatch, connection)
    body_error = RuntimeError("body is primary")

    with pytest.raises(RuntimeError, match="body is primary") as caught:
        with immediate_transaction(authority) as transaction:
            _execute(
                transaction,
                "INSERT INTO values_under_test(value) VALUES (?)",
                ("rolled-back-on-close",),
            )
            raise body_error

    assert caught.value is body_error
    assert [str(error) for error in _exception_contexts(caught.value)] == [
        "injected rollback failure",
    ]
    rollback_error = caught.value.__context__
    assert rollback_error is not None
    assert str(rollback_error.__cause__) == "injected close failure"
    assert connection.events == ["rollback", "close"]
    assert connection.closed is True
    assert _stored_values(db_path) == []


def test_commit_error_remains_primary_over_rollback_and_close_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "commit-cleanup-order.db"
    authority = _create_values_table(db_path)
    connection = sqlite3.connect(
        db_path,
        isolation_level=None,
        factory=_FaultConnection,
    )
    assert isinstance(connection, _FaultConnection)
    connection.row_factory = sqlite3.Row
    connection.fail_commit = True
    connection.fail_rollback = True
    connection.fail_close = True
    _inject_connection(monkeypatch, connection)

    with pytest.raises(RuntimeError, match="commit failure") as caught:
        with immediate_transaction(authority) as transaction:
            _execute(
                transaction,
                "INSERT INTO values_under_test(value) VALUES (?)",
                ("rolled-back-on-close",),
            )

    assert [str(error) for error in _exception_contexts(caught.value)] == [
        "injected rollback failure",
    ]
    rollback_error = caught.value.__context__
    assert rollback_error is not None
    assert str(rollback_error.__cause__) == "injected close failure"
    assert connection.events == ["commit", "rollback", "close"]
    assert connection.closed is True
    assert _stored_values(db_path) == []


def test_close_failure_after_commit_is_typed_and_capability_is_inactive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "post-commit-close.db"
    authority = _create_values_table(db_path)
    connection = sqlite3.connect(
        db_path,
        isolation_level=None,
        factory=_FaultConnection,
    )
    assert isinstance(connection, _FaultConnection)
    connection.row_factory = sqlite3.Row
    connection.fail_close = True
    _inject_connection(monkeypatch, connection)
    leaked: ImmediateTransaction | None = None

    with pytest.raises(SQLiteConnectionCleanupError) as caught:
        with immediate_transaction(authority) as transaction:
            leaked = transaction
            _execute(
                transaction,
                "INSERT INTO values_under_test(value) VALUES (?)",
                ("committed",),
            )

    assert isinstance(caught.value.__cause__, RuntimeError)
    assert str(caught.value.__cause__) == "injected close failure"
    assert connection.events == ["commit", "close"]
    assert _stored_values(db_path) == ["committed"]
    assert leaked is not None
    with pytest.raises(InactiveImmediateTransactionError):
        require_active_immediate_transaction(leaked, authority)
    assert sqlite_connection_module._ACTIVE_TRANSACTION.get() is None
    assert sqlite_connection_module._thread_owner() is None


def test_body_error_remains_primary_when_close_alone_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "body-close.db"
    authority = _create_values_table(db_path)
    connection = sqlite3.connect(
        db_path,
        isolation_level=None,
        factory=_FaultConnection,
    )
    assert isinstance(connection, _FaultConnection)
    connection.row_factory = sqlite3.Row
    connection.fail_close = True
    _inject_connection(monkeypatch, connection)
    body_error = RuntimeError("body failure")

    with pytest.raises(RuntimeError, match="body failure") as caught:
        with immediate_transaction(authority):
            raise body_error

    assert caught.value is body_error
    assert [str(error) for error in _exception_contexts(caught.value)] == [
        "injected close failure"
    ]
    assert connection.events == ["rollback", "close"]
    assert sqlite_connection_module._ACTIVE_TRANSACTION.get() is None
    assert sqlite_connection_module._thread_owner() is None
