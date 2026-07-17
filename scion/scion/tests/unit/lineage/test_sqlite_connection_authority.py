from __future__ import annotations

import contextvars
import os
import sqlite3
import threading
from pathlib import Path

import pytest

import scion.lineage.sqlite_connection as subject
from scion.lineage.sqlite_connection import (
    InactiveImmediateTransactionError,
    InvalidImmediateTransactionError,
    SQLiteConnectionPolicyError,
)


class _CloseTrackingConnection(sqlite3.Connection):
    closed = False

    def close(self) -> None:
        self.closed = True
        super().close()


def _authority(
    path: Path,
    *,
    execution_lock_is_held: object | None = None,
) -> subject.CampaignDatabaseAuthority:
    connection = subject._connect_sqlite(path)
    try:
        connection.execute(
            "CREATE TABLE values_under_test (value TEXT PRIMARY KEY)"
        )
    finally:
        connection.close()
    kwargs: dict[str, object] = {}
    if execution_lock_is_held is not None:
        kwargs["execution_lock_is_held"] = execution_lock_is_held
    return subject._issue_test_campaign_database_authority(path, **kwargs)


def _rollback_deactivate_close(
    session: subject._CoordinatedTransactionSession,
    authority: subject.CampaignDatabaseAuthority,
) -> None:
    state = subject._lookup_session_state(session)
    if state.phase is not subject._SessionPhase.DEACTIVATED:
        subject._deactivate_coordinated_transaction(session, authority)
    subject._settle_deactivated_original_connection(session, authority)


def test_coordinated_lifecycle_supports_publish_before_close(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "coordinated.db"
    authority = _authority(db_path)
    session = subject._open_coordinated_transaction_session(authority)
    transaction = subject._coordinated_transaction(session, authority)

    subject._execute_participant(
        transaction,
        authority,
        "INSERT INTO values_under_test(value) VALUES (?)",
        ("committed",),
    )
    subject._commit_coordinated_transaction(session, authority)

    # Commit has returned, but the registry can still deactivate, publish its
    # immutable root, and only then close this original connection.
    assert subject._thread_owner() is transaction
    assert subject._ACTIVE_TRANSACTION.get() is transaction
    with pytest.raises(InactiveImmediateTransactionError):
        subject.require_active_immediate_transaction(transaction, authority)

    subject._deactivate_coordinated_transaction(session, authority)
    assert subject._thread_owner() is None
    assert subject._ACTIVE_TRANSACTION.get() is None
    assert subject._lookup_capability_state(transaction).connection is None

    published = True
    assert published
    state_before_close = subject._lookup_session_state(session)
    proof_fd = state_before_close.opened_main_fd
    subject._close_coordinated_transaction(session, authority)

    # Any independent classification starts only after the original
    # connection is settled and closed.
    with subject._independent_authority_read_snapshot(authority) as snapshot:
        rows = subject._execute_read_snapshot(
            snapshot,
            authority,
            "SELECT value FROM values_under_test",
        )
        assert [row[0] for row in rows] == ["committed"]

    state = subject._lookup_session_state(session)
    assert state.phase is subject._SessionPhase.CLOSED
    assert state.connection is None
    assert state.opened_main_fd == -1
    with pytest.raises(OSError):
        os.fstat(proof_fd)


def test_transaction_and_session_reject_a_different_authority(
    tmp_path: Path,
) -> None:
    authority_a = _authority(tmp_path / "a.db")
    authority_b = _authority(tmp_path / "b.db")
    session = subject._open_coordinated_transaction_session(authority_a)
    transaction = subject._coordinated_transaction(session, authority_a)
    try:
        with pytest.raises(InvalidImmediateTransactionError, match="another authority"):
            subject.require_active_immediate_transaction(transaction, authority_b)
        with pytest.raises(InvalidImmediateTransactionError, match="another authority"):
            subject._execute_participant(
                transaction,
                authority_b,
                "SELECT value FROM values_under_test",
            )
        with pytest.raises(InvalidImmediateTransactionError, match="another authority"):
            subject._coordinated_transaction(session, authority_b)
    finally:
        _rollback_deactivate_close(session, authority_a)


def test_generic_authorizer_is_bound_and_rechecks_each_statement(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path / "authorizer.db")
    other_authority = _authority(tmp_path / "other.db")
    session = subject._open_coordinated_transaction_session(authority)
    transaction = subject._coordinated_transaction(session, authority)
    permit = False
    decisions: list[tuple[int, str | None, str | None]] = []

    def _authorizer(
        action: int,
        object_name: str | None,
        _column: str | None,
        database_name: str | None,
        _trigger_source: str | None,
    ) -> int:
        nonlocal permit
        if action == sqlite3.SQLITE_INSERT and object_name == "values_under_test":
            decisions.append((action, object_name, database_name))
            return sqlite3.SQLITE_OK if permit else sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    handle = subject._install_transaction_authorizer(
        session,
        authority,
        _authorizer,
    )
    try:
        assert (
            subject._require_transaction_authorizer(handle, session, authority)
            is handle
        )
        with pytest.raises(
            InvalidImmediateTransactionError,
            match="another authority",
        ):
            subject._require_transaction_authorizer(
                handle,
                session,
                other_authority,
            )

        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            subject._execute_participant(
                transaction,
                authority,
                "INSERT INTO values_under_test(value) VALUES ('denied-1')",
            )
        permit = True
        subject._execute_participant(
            transaction,
            authority,
            "INSERT INTO values_under_test(value) VALUES ('allowed')",
        )
        permit = False
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            subject._execute_participant(
                transaction,
                authority,
                "INSERT INTO values_under_test(value) VALUES ('denied-2')",
            )

        assert decisions == [
            (sqlite3.SQLITE_INSERT, "values_under_test", "main"),
            (sqlite3.SQLITE_INSERT, "values_under_test", "main"),
            (sqlite3.SQLITE_INSERT, "values_under_test", "main"),
        ]
        subject._commit_coordinated_transaction(session, authority)
        with pytest.raises(InactiveImmediateTransactionError):
            subject._require_transaction_authorizer(handle, session, authority)
    finally:
        _rollback_deactivate_close(session, authority)


def test_authorizer_cannot_be_installed_after_participant_execution(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path / "late-authorizer.db")
    session = subject._open_coordinated_transaction_session(authority)
    transaction = subject._coordinated_transaction(session, authority)
    try:
        subject._execute_participant(
            transaction,
            authority,
            "SELECT value FROM values_under_test",
        )
        with pytest.raises(InvalidImmediateTransactionError, match="before participant"):
            subject._install_transaction_authorizer(
                session,
                authority,
                lambda *_args: sqlite3.SQLITE_OK,
            )
    finally:
        _rollback_deactivate_close(session, authority)


def test_opened_main_fd_proof_rejects_path_aba(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority_path = tmp_path / "authority.db"
    replacement_path = tmp_path / "replacement.db"
    parked_authority_path = tmp_path / "authority.parked"
    authority = _authority(authority_path)
    _authority(replacement_path)
    for path, marker in ((authority_path, 111), (replacement_path, 222)):
        connection = sqlite3.connect(path, isolation_level=None)
        try:
            connection.execute(f"PRAGMA user_version={marker}")
        finally:
            connection.close()
    authority_identity = os.stat(authority_path).st_dev, os.stat(authority_path).st_ino
    replacement_identity = (
        os.stat(replacement_path).st_dev,
        os.stat(replacement_path).st_ino,
    )
    assert replacement_identity != authority_identity

    real_connect = sqlite3.connect
    swapped = False
    opened_markers: list[int] = []

    def _connect_during_aba(*args: object, **kwargs: object) -> sqlite3.Connection:
        nonlocal swapped
        if swapped:
            return real_connect(*args, **kwargs)
        swapped = True
        os.replace(authority_path, parked_authority_path)
        os.replace(replacement_path, authority_path)
        try:
            connection = real_connect(*args, **kwargs)
            row = connection.execute("PRAGMA user_version").fetchone()
            assert row is not None
            opened_markers.append(int(row[0]))
        finally:
            os.replace(authority_path, replacement_path)
            os.replace(parked_authority_path, authority_path)
        return connection

    monkeypatch.setattr(subject.sqlite3, "connect", _connect_during_aba)
    with pytest.raises(SQLiteConnectionPolicyError, match="actual main"):
        subject._connect_authority_sqlite(
            authority,
            busy_timeout_ms=subject.DEFAULT_BUSY_TIMEOUT_MS,
        )

    assert swapped
    assert opened_markers == [222]
    assert (os.stat(authority_path).st_dev, os.stat(authority_path).st_ino) == (
        authority_identity
    )


def test_open_reservation_is_cleared_when_interrupted_after_assignment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority(tmp_path / "reservation.db")
    original_reserve = subject._reserve_thread_owner

    def _interrupt_after_reserve() -> None:
        original_reserve()
        raise RuntimeError("injected post-reservation interruption")

    monkeypatch.setattr(subject, "_reserve_thread_owner", _interrupt_after_reserve)
    with pytest.raises(RuntimeError, match="post-reservation"):
        subject._open_coordinated_transaction_session(authority)
    assert subject._thread_owner() is None
    assert subject._ACTIVE_TRANSACTION.get() is None

    monkeypatch.setattr(subject, "_reserve_thread_owner", original_reserve)
    with subject.immediate_transaction(authority):
        pass


def test_transaction_wrapper_cleans_if_interrupted_after_inner_enter(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path / "transaction-post-enter.db")
    manager = subject.immediate_transaction(authority)
    inner = manager._manager

    class _InterruptAfterEnter:
        transaction: subject.ImmediateTransaction | None = None

        def __enter__(self) -> subject.ImmediateTransaction:
            self.transaction = inner.__enter__()
            raise KeyboardInterrupt("injected transaction post-enter interruption")

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: object,
        ) -> bool | None:
            return inner.__exit__(exc_type, exc_value, traceback)  # type: ignore[arg-type]

    proxy = _InterruptAfterEnter()
    manager._manager = proxy  # type: ignore[assignment]
    with pytest.raises(KeyboardInterrupt, match="post-enter interruption"):
        manager.__enter__()

    assert proxy.transaction is not None
    capability_state = subject._lookup_capability_state(proxy.transaction)
    session = capability_state.session_ref()
    assert session is not None
    session_state = subject._lookup_session_state(session)
    assert capability_state.active is False
    assert capability_state.connection is None
    assert session_state.phase is subject._SessionPhase.CLOSED
    assert session_state.connection is None
    assert subject._thread_owner() is None
    assert subject._thread_session_owner() is None
    assert subject._ACTIVE_TRANSACTION.get() is None
    assert subject._ACTIVE_COORDINATED_SESSION.get() is None
    with subject.immediate_transaction(authority):
        pass


def test_snapshot_wrapper_cleans_if_interrupted_after_inner_enter(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path / "snapshot-post-enter.db")
    manager = subject._independent_authority_read_snapshot(authority)
    inner = manager._manager

    class _InterruptAfterEnter:
        snapshot: subject._IndependentReadSnapshot | None = None

        def __enter__(self) -> subject._IndependentReadSnapshot:
            self.snapshot = inner.__enter__()
            raise KeyboardInterrupt("injected snapshot post-enter interruption")

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: object,
        ) -> bool | None:
            return inner.__exit__(exc_type, exc_value, traceback)  # type: ignore[arg-type]

    proxy = _InterruptAfterEnter()
    manager._manager = proxy  # type: ignore[assignment]
    with pytest.raises(KeyboardInterrupt, match="post-enter interruption"):
        manager.__enter__()

    assert proxy.snapshot is not None
    snapshot_state = subject._lookup_read_snapshot_state(proxy.snapshot)
    assert snapshot_state.active is False
    assert snapshot_state.connection is None
    assert snapshot_state.opened_main_fd == -1
    assert subject._thread_owner() is None
    assert subject._ACTIVE_READ_SNAPSHOT.get() is None
    with subject.immediate_transaction(authority):
        pass


def test_context_token_is_recoverable_after_set_then_interrupts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority(tmp_path / "context-renewal-interruption.db")
    manager = subject.immediate_transaction(authority)
    transaction = manager.__enter__()
    real_context = subject._ACTIVE_COORDINATED_SESSION

    class _InterruptAfterSet:
        set_calls = 0

        def get(self) -> subject._CoordinatedTransactionSession | None:
            return real_context.get()

        def set(
            self,
            value: subject._CoordinatedTransactionSession | None,
        ) -> contextvars.Token[subject._CoordinatedTransactionSession | None]:
            self.set_calls += 1
            token = real_context.set(value)
            if self.set_calls == 1:
                raise KeyboardInterrupt("injected context renewal interruption")
            return token

        def reset(
            self,
            token: contextvars.Token[
                subject._CoordinatedTransactionSession | None
            ],
        ) -> None:
            real_context.reset(token)

    interrupting_context = _InterruptAfterSet()
    monkeypatch.setattr(
        subject,
        "_ACTIVE_COORDINATED_SESSION",
        interrupting_context,
    )
    with pytest.raises(KeyboardInterrupt, match="context renewal interruption"):
        subject.require_active_immediate_transaction(transaction, authority)
    assert interrupting_context.set_calls == 3

    monkeypatch.setattr(subject, "_ACTIVE_COORDINATED_SESSION", real_context)
    assert subject.require_active_immediate_transaction(
        transaction,
        authority,
    ) is transaction
    manager.__exit__(None, None, None)
    assert subject._ACTIVE_COORDINATED_SESSION.get() is None
    with subject.immediate_transaction(authority):
        pass


def test_local_exit_preflight_fault_still_settles_and_preserves_body_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority(tmp_path / "exit-preflight-fault.db")
    manager = subject.immediate_transaction(authority)
    transaction = manager.__enter__()
    session = subject._lookup_capability_state(transaction).session_ref()
    assert session is not None
    original_preflight = subject._assert_session_thread_binding
    calls = 0

    def _fail_once(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("injected exit preflight fault")
        original_preflight(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(subject, "_assert_session_thread_binding", _fail_once)
    body_error = ValueError("body remains primary")
    assert (
        manager.__exit__(type(body_error), body_error, body_error.__traceback__)
        is False
    )

    assert str(body_error.__context__) == "injected exit preflight fault"
    capability_state = subject._lookup_capability_state(transaction)
    session_state = subject._lookup_session_state(session)
    assert capability_state.active is False
    assert capability_state.connection is None
    assert session_state.phase is subject._SessionPhase.CLOSED
    assert session_state.connection is None
    assert subject._thread_owner() is None
    assert subject._thread_session_owner() is None
    assert subject._ACTIVE_TRANSACTION.get() is None
    assert subject._ACTIVE_COORDINATED_SESSION.get() is None


def test_transaction_finalizer_dispatch_fault_is_reconciled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority(tmp_path / "transaction-finalizer-dispatch.db")
    manager = subject.immediate_transaction(authority)
    transaction = manager.__enter__()
    session = subject._lookup_capability_state(transaction).session_ref()
    assert session is not None
    original_finalize = subject._finalize_context_session
    calls = 0

    def _interrupt_first_dispatch(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise KeyboardInterrupt("injected transaction finalizer dispatch fault")
        original_finalize(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(subject, "_finalize_context_session", _interrupt_first_dispatch)
    body_error = ValueError("body remains primary")
    assert (
        manager.__exit__(type(body_error), body_error, body_error.__traceback__)
        is False
    )

    assert calls == 2
    assert str(body_error.__context__) == "injected transaction finalizer dispatch fault"
    capability_state = subject._lookup_capability_state(transaction)
    session_state = subject._lookup_session_state(session)
    assert capability_state.active is False
    assert capability_state.connection is None
    assert session_state.phase is subject._SessionPhase.CLOSED
    assert session_state.connection is None
    assert subject._thread_owner() is None
    assert subject._thread_session_owner() is None
    assert subject._ACTIVE_TRANSACTION.get() is None
    assert subject._ACTIVE_COORDINATED_SESSION.get() is None
    with subject.immediate_transaction(authority):
        pass


def test_partial_deactivation_is_reconciled_by_resource_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority(tmp_path / "partial-deactivation.db")
    manager = subject.immediate_transaction(authority)
    transaction = manager.__enter__()
    session = subject._lookup_capability_state(transaction).session_ref()
    assert session is not None
    original_deactivate = subject._deactivate_coordinated_transaction
    calls = 0

    def _interrupt_after_phase(
        exact_session: subject._CoordinatedTransactionSession,
        exact_authority: subject.CampaignDatabaseAuthority,
    ) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            state = subject._require_session_authority(
                exact_session,
                exact_authority,
            )
            state.phase = subject._SessionPhase.DEACTIVATED
            raise KeyboardInterrupt("injected partial deactivation fault")
        original_deactivate(exact_session, exact_authority)

    monkeypatch.setattr(
        subject,
        "_deactivate_coordinated_transaction",
        _interrupt_after_phase,
    )
    body_error = ValueError("body remains primary")
    assert (
        manager.__exit__(type(body_error), body_error, body_error.__traceback__)
        is False
    )

    state = subject._lookup_session_state(session)
    capability_state = subject._lookup_capability_state(transaction)
    assert calls == 2
    assert str(body_error.__context__) == "injected partial deactivation fault"
    assert state.phase is subject._SessionPhase.CLOSED
    assert subject._session_resources_closed(session, state)
    assert capability_state.active is False
    assert capability_state.connection is None
    assert subject._ACTIVE_TRANSACTION.get() is None
    assert subject._thread_owner() is None
    with subject.immediate_transaction(authority):
        pass


def test_partial_close_is_reconciled_by_resource_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority(tmp_path / "partial-close.db")
    manager = subject.immediate_transaction(authority)
    transaction = manager.__enter__()
    session = subject._lookup_capability_state(transaction).session_ref()
    assert session is not None
    state = subject._lookup_session_state(session)
    proof_fd = state.opened_main_fd
    original_close = subject._close_coordinated_transaction
    calls = 0

    def _interrupt_after_connection_close(
        exact_session: subject._CoordinatedTransactionSession,
        exact_authority: subject.CampaignDatabaseAuthority,
    ) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            exact_state = subject._require_session_authority(
                exact_session,
                exact_authority,
            )
            connection = exact_state.connection
            assert connection is not None
            connection.close()
            exact_state.connection = None
            exact_state.sqlite_handle = None
            raise KeyboardInterrupt("injected partial close fault")
        original_close(exact_session, exact_authority)

    monkeypatch.setattr(
        subject,
        "_close_coordinated_transaction",
        _interrupt_after_connection_close,
    )
    body_error = ValueError("body remains primary")
    assert (
        manager.__exit__(type(body_error), body_error, body_error.__traceback__)
        is False
    )

    assert calls == 2
    assert str(body_error.__context__) == "injected partial close fault"
    assert state.phase is subject._SessionPhase.CLOSED
    assert subject._session_resources_closed(session, state)
    assert state.connection is None
    assert state.opened_main_fd == -1
    with pytest.raises(OSError):
        os.fstat(proof_fd)
    assert subject._ACTIVE_COORDINATED_SESSION.get() is None
    assert subject._thread_session_owner() is None
    with subject.immediate_transaction(authority):
        pass


def test_snapshot_finalizer_dispatch_fault_is_reconciled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority(tmp_path / "snapshot-finalizer-dispatch.db")
    manager = subject._independent_authority_read_snapshot(authority)
    snapshot = manager.__enter__()
    state = subject._lookup_read_snapshot_state(snapshot)
    proof_fd = state.opened_main_fd
    original_finalize = subject._finalize_read_snapshot_state
    calls = 0

    def _interrupt_first_dispatch(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise KeyboardInterrupt("injected snapshot finalizer dispatch fault")
        original_finalize(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        subject,
        "_finalize_read_snapshot_state",
        _interrupt_first_dispatch,
    )
    with pytest.raises(
        subject.SQLiteConnectionCleanupError,
    ) as caught:
        manager.__exit__(None, None, None)

    assert isinstance(caught.value.__cause__, KeyboardInterrupt)
    assert calls == 2
    assert state.active is False
    assert state.context_cleared is True
    assert state.connection is None
    assert state.opened_main_fd == -1
    with pytest.raises(OSError):
        os.fstat(proof_fd)
    assert subject._thread_owner() is None
    assert subject._ACTIVE_READ_SNAPSHOT.get() is None
    with subject.immediate_transaction(authority):
        pass


def test_descriptor_dup_failure_closes_the_new_sqlite_connection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority(tmp_path / "dup-failure.db")
    real_connect = sqlite3.connect
    created: list[_CloseTrackingConnection] = []

    def _tracking_connect(*args: object, **kwargs: object) -> sqlite3.Connection:
        connection = real_connect(
            *args,
            **kwargs,
            factory=_CloseTrackingConnection,
        )
        assert isinstance(connection, _CloseTrackingConnection)
        created.append(connection)
        return connection

    monkeypatch.setattr(subject.sqlite3, "connect", _tracking_connect)
    monkeypatch.setattr(
        subject.os,
        "dup",
        lambda _descriptor: (_ for _ in ()).throw(OSError("injected dup failure")),
    )
    with pytest.raises(OSError, match="dup failure"):
        subject._connect_authority_sqlite(
            authority,
            busy_timeout_ms=subject.DEFAULT_BUSY_TIMEOUT_MS,
        )
    assert len(created) == 1
    assert created[0].closed is True


@pytest.mark.parametrize("fault", ("register", "cancel"))
def test_native_handle_capture_fault_clears_callback_and_tls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    authority = _authority(tmp_path / f"native-handle-{fault}.db")
    real_library = subject._sqlite_c_library()

    class _InterruptingLibrary:
        register_calls = 0
        cancel_calls = 0

        def __getattr__(self, name: str) -> object:
            return getattr(real_library, name)

        def sqlite3_auto_extension(self, pointer: object) -> int:
            self.register_calls += 1
            result = int(real_library.sqlite3_auto_extension(pointer))
            if fault == "register" and self.register_calls == 1:
                raise KeyboardInterrupt("injected native register interruption")
            return result

        def sqlite3_cancel_auto_extension(self, pointer: object) -> int:
            self.cancel_calls += 1
            result = int(real_library.sqlite3_cancel_auto_extension(pointer))
            if fault == "cancel" and self.cancel_calls == 1:
                raise KeyboardInterrupt("injected native cancel interruption")
            return result

    proxy = _InterruptingLibrary()
    monkeypatch.setattr(subject, "_sqlite_c_library", lambda: proxy)
    with pytest.raises(KeyboardInterrupt, match=f"native {fault} interruption"):
        subject._connect_authority_sqlite(
            authority,
            busy_timeout_ms=subject.DEFAULT_BUSY_TIMEOUT_MS,
        )

    assert not hasattr(subject._SQLITE_HANDLE_CAPTURE_LOCAL, "captures")
    assert not hasattr(subject._SQLITE_HANDLE_CAPTURE_LOCAL, "failed")
    assert proxy.cancel_calls >= 1

    monkeypatch.setattr(subject, "_sqlite_c_library", lambda: real_library)
    connection, proof_fd, _handle = subject._connect_authority_sqlite(
        authority,
        busy_timeout_ms=subject.DEFAULT_BUSY_TIMEOUT_MS,
    )
    connection.close()
    os.close(proof_fd)


def test_lost_context_token_is_cleared_after_set_interruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority(tmp_path / "context-token.db")
    real_context = subject._ACTIVE_TRANSACTION

    class _InterruptingContext:
        def __init__(self) -> None:
            self.set_calls = 0

        def get(self) -> subject.ImmediateTransaction | None:
            return real_context.get()

        def set(
            self,
            value: subject.ImmediateTransaction | None,
        ) -> contextvars.Token[subject.ImmediateTransaction | None]:
            self.set_calls += 1
            token = real_context.set(value)
            if self.set_calls == 1:
                raise RuntimeError("injected context-set interruption")
            return token

        def reset(
            self,
            token: contextvars.Token[subject.ImmediateTransaction | None],
        ) -> None:
            real_context.reset(token)

    interrupting_context = _InterruptingContext()
    monkeypatch.setattr(subject, "_ACTIVE_TRANSACTION", interrupting_context)
    with pytest.raises(RuntimeError, match="context-set interruption"):
        subject._open_coordinated_transaction_session(authority)
    assert interrupting_context.set_calls == 2
    assert subject._thread_owner() is None
    assert real_context.get() is None


def test_cross_thread_lifecycle_calls_do_not_mutate_session_state(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path / "cross-thread-session.db")
    session = subject._open_coordinated_transaction_session(authority)
    transaction = subject._coordinated_transaction(session, authority)
    errors: list[BaseException] = []

    def _run(callable_: object) -> None:
        try:
            assert callable(callable_)
            callable_(session, authority)  # type: ignore[operator]
        except BaseException as error:
            errors.append(error)

    for operation in (
        subject._deactivate_coordinated_transaction,
        subject._close_coordinated_transaction,
        subject._settle_deactivated_original_connection,
    ):
        thread = threading.Thread(target=_run, args=(operation,))
        thread.start()
        thread.join()

    state = subject._lookup_session_state(session)
    assert len(errors) == 3
    assert state.phase is subject._SessionPhase.ACTIVE
    assert state.connection is not None and state.connection.in_transaction
    assert subject._lookup_capability_state(transaction).active is True
    assert subject._thread_owner() is transaction
    assert subject._ACTIVE_TRANSACTION.get() is transaction

    subject._commit_coordinated_transaction(session, authority)
    thread = threading.Thread(
        target=_run,
        args=(subject._deactivate_coordinated_transaction,),
    )
    thread.start()
    thread.join()
    assert state.phase is subject._SessionPhase.COMMITTED

    subject._deactivate_coordinated_transaction(session, authority)
    thread = threading.Thread(
        target=_run,
        args=(subject._close_coordinated_transaction,),
    )
    thread.start()
    thread.join()
    assert state.phase is subject._SessionPhase.DEACTIVATED
    assert state.connection is not None
    subject._close_coordinated_transaction(session, authority)


def test_copied_context_cannot_use_or_consume_transaction_context(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path / "copied-transaction-context.db")
    manager = subject.immediate_transaction(authority)
    transaction = manager.__enter__()
    state = subject._lookup_capability_state(transaction)
    session = state.session_ref()
    assert session is not None
    copied = contextvars.copy_context()

    with pytest.raises(InactiveImmediateTransactionError, match="another Context"):
        copied.run(
            subject.require_active_immediate_transaction,
            transaction,
            authority,
        )
    with pytest.raises(InactiveImmediateTransactionError, match="another Context"):
        copied.run(manager.__exit__, None, None, None)

    assert subject.require_active_immediate_transaction(transaction, authority) is transaction
    assert subject._lookup_session_state(session).phase is subject._SessionPhase.ACTIVE
    assert subject._thread_owner() is transaction
    assert subject._ACTIVE_TRANSACTION.get() is transaction
    manager.__exit__(None, None, None)

    assert subject._lookup_session_state(session).phase is subject._SessionPhase.CLOSED
    with subject.immediate_transaction(authority):
        pass


def test_copied_context_cannot_use_or_consume_snapshot_context(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path / "copied-snapshot-context.db")
    manager = subject._independent_authority_read_snapshot(authority)
    snapshot = manager.__enter__()
    copied = contextvars.copy_context()

    with pytest.raises(InactiveImmediateTransactionError, match="another Context"):
        copied.run(
            subject._execute_read_snapshot,
            snapshot,
            authority,
            "SELECT value FROM values_under_test",
        )
    with pytest.raises(InactiveImmediateTransactionError, match="another Context"):
        copied.run(manager.__exit__, None, None, None)

    rows = subject._execute_read_snapshot(
        snapshot,
        authority,
        "SELECT value FROM values_under_test",
    )
    assert rows == ()
    assert subject._lookup_read_snapshot_state(snapshot).active is True
    assert subject._thread_owner() is snapshot
    assert subject._ACTIVE_READ_SNAPSHOT.get() is snapshot
    manager.__exit__(None, None, None)

    snapshot_state = subject._lookup_read_snapshot_state(snapshot)
    assert snapshot_state.active is False
    assert snapshot_state.connection is None
    with subject.immediate_transaction(authority):
        pass


def test_independent_snapshot_is_consistent_read_only_and_clears_raw_state(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "snapshot.db"
    authority = _authority(db_path)
    with subject.immediate_transaction(authority) as transaction:
        subject._execute_participant(
            transaction,
            authority,
            "INSERT INTO values_under_test(value) VALUES ('initial')",
        )

    leaked_snapshot: subject._IndependentReadSnapshot
    proof_fd: int
    with subject._independent_authority_read_snapshot(authority) as snapshot:
        leaked_snapshot = snapshot
        proof_fd = subject._lookup_read_snapshot_state(snapshot).opened_main_fd
        first = subject._execute_read_snapshot(
            snapshot,
            authority,
            "SELECT value FROM values_under_test ORDER BY value",
        )
        assert [row[0] for row in first] == ["initial"]

        competitor = sqlite3.connect(db_path, isolation_level=None)
        try:
            competitor.execute(
                "INSERT INTO values_under_test(value) VALUES ('later')"
            )
        finally:
            competitor.close()

        second = subject._execute_read_snapshot(
            snapshot,
            authority,
            "SELECT value FROM values_under_test ORDER BY value",
        )
        assert [row[0] for row in second] == ["initial"]
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            subject._execute_read_snapshot(
                snapshot,
                authority,
                "WITH proposed(value) AS (VALUES ('forbidden')) "
                "INSERT INTO values_under_test SELECT value FROM proposed",
            )

    leaked_state = subject._lookup_read_snapshot_state(leaked_snapshot)
    assert leaked_state.active is False
    assert leaked_state.connection is None
    assert leaked_state.opened_main_fd == -1
    with pytest.raises(OSError):
        os.fstat(proof_fd)
    with pytest.raises(InactiveImmediateTransactionError):
        subject._execute_read_snapshot(
            leaked_snapshot,
            authority,
            "SELECT value FROM values_under_test",
        )

    connection = sqlite3.connect(db_path)
    try:
        assert [
            row[0]
            for row in connection.execute(
                "SELECT value FROM values_under_test ORDER BY value"
            )
        ] == ["initial", "later"]
    finally:
        connection.close()


def test_read_snapshot_blocks_write_nesting_even_before_first_caller_read(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path / "snapshot-nesting.db")
    with subject._independent_authority_read_snapshot(authority):
        with pytest.raises(subject.NestedImmediateTransactionError):
            with subject.immediate_transaction(authority):
                pytest.fail("write transaction nested inside classification snapshot")

        def _fresh_context_write() -> None:
            with subject.immediate_transaction(authority):
                pytest.fail("fresh Context bypassed snapshot ownership")

        with pytest.raises(subject.NestedImmediateTransactionError):
            contextvars.Context().run(_fresh_context_write)


def test_read_snapshot_is_rejected_inside_an_active_write_transaction(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path / "write-before-snapshot.db")
    with subject.immediate_transaction(authority):
        with pytest.raises(subject.NestedImmediateTransactionError):
            with subject._independent_authority_read_snapshot(authority):
                pytest.fail("classification snapshot nested inside write transaction")


def test_read_snapshot_rejects_a_different_authority(
    tmp_path: Path,
) -> None:
    authority_a = _authority(tmp_path / "snapshot-a.db")
    authority_b = _authority(tmp_path / "snapshot-b.db")
    with subject._independent_authority_read_snapshot(authority_a) as snapshot:
        with pytest.raises(InvalidImmediateTransactionError, match="another authority"):
            subject._execute_read_snapshot(
                snapshot,
                authority_b,
                "SELECT value FROM values_under_test",
            )


def test_read_snapshot_revalidates_execution_lock_on_each_read(
    tmp_path: Path,
) -> None:
    lock_held = True

    def _lock_probe() -> bool:
        return lock_held

    authority = _authority(
        tmp_path / "snapshot-live-read.db",
        execution_lock_is_held=_lock_probe,
    )
    with pytest.raises(SQLiteConnectionPolicyError, match="lock is not held"):
        with subject._independent_authority_read_snapshot(authority) as snapshot:
            subject._execute_read_snapshot(
                snapshot,
                authority,
                "SELECT value FROM values_under_test",
            )
            lock_held = False
            subject._execute_read_snapshot(
                snapshot,
                authority,
                "SELECT value FROM values_under_test",
            )


def test_read_snapshot_revalidates_execution_lock_before_successful_exit(
    tmp_path: Path,
) -> None:
    lock_held = True

    def _lock_probe() -> bool:
        return lock_held

    authority = _authority(
        tmp_path / "snapshot-live-exit.db",
        execution_lock_is_held=_lock_probe,
    )
    with pytest.raises(SQLiteConnectionPolicyError, match="lock is not held"):
        with subject._independent_authority_read_snapshot(authority):
            lock_held = False
