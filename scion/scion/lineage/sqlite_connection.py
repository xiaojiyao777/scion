"""Sealed SQLite authority, coordinated transaction, and snapshot foundation.

Raw SQLite connections live only in module-owned state registries.  Callers get
opaque authority, transaction-session, capability, authorizer, and read-snapshot
handles; none of those objects retains a cursor or connection.  Branch/H table
policy and durable mutation receipts intentionally belong to later modules.
"""

from __future__ import annotations

import contextvars
import ctypes
import ctypes.util
import enum
import errno
import os
import re
import sqlite3
import stat
import threading
import weakref
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, Callable, Final, Iterable, Iterator, Mapping, Sequence

__all__ = [
    "CampaignDatabaseAuthority",
    "DEFAULT_BUSY_TIMEOUT_MS",
    "ImmediateResult",
    "ImmediateTransaction",
    "ImmediateTransactionError",
    "InactiveImmediateTransactionError",
    "InvalidCampaignDatabaseAuthorityError",
    "InvalidImmediateTransactionError",
    "NestedImmediateTransactionError",
    "ParticipantStatementError",
    "SQLiteConnectionCleanupError",
    "SQLiteConnectionPolicyError",
    "TransactionControlError",
    "immediate_transaction",
    "require_active_immediate_transaction",
]


DEFAULT_BUSY_TIMEOUT_MS: Final[int] = 5_000

_SqlParameters = Sequence[Any] | Mapping[str, Any]
_SqlParameterRows = Iterable[Sequence[Any] | Mapping[str, Any]]
_DatabaseIdentityValidator = Callable[[sqlite3.Connection, str, str], None]
_ExecutionLockProbe = Callable[[], bool]
_SQLiteAuthorizer = Callable[
    [int, str | None, str | None, str | None, str | None], int
]

_ALLOWED_STATEMENT_KEYWORDS: Final[frozenset[str]] = frozenset(
    {"SELECT", "INSERT", "UPDATE", "DELETE", "WITH"}
)
_READ_STATEMENT_KEYWORDS: Final[frozenset[str]] = frozenset({"SELECT", "WITH"})
_TRANSACTION_KEYWORDS: Final[frozenset[str]] = frozenset(
    {"BEGIN", "COMMIT", "END", "ROLLBACK", "SAVEPOINT", "RELEASE"}
)
_SQL_KEYWORD = re.compile(r"[A-Za-z]+")
_OPENING_TRANSACTION: Final[object] = object()
_OPENING_READ_SNAPSHOT: Final[object] = object()
_SQLITE_OK: Final[int] = 0
_SQLITE_FCNTL_HAS_MOVED: Final[int] = 20


class SQLiteConnectionPolicyError(RuntimeError):
    """A connection or database authority violates the frozen SQLite policy."""


class SQLiteConnectionCleanupError(RuntimeError):
    """Cleanup failed after the transaction's primary outcome was established."""


class InvalidCampaignDatabaseAuthorityError(TypeError):
    """A value is not a sealed authority issued by this module."""


class ImmediateTransactionError(RuntimeError):
    """Base class for invalid immediate-transaction lifecycle operations."""


class InvalidImmediateTransactionError(TypeError, ImmediateTransactionError):
    """A transaction/session/handle is forged, mismatched, or in a wrong phase."""


class InactiveImmediateTransactionError(ImmediateTransactionError):
    """An issued capability is ended or does not own the current context."""


class _ForeignLifecycleContextError(InactiveImmediateTransactionError):
    """A lifecycle handle was used outside its exact entering Context."""


class NestedImmediateTransactionError(ImmediateTransactionError):
    """The current thread or Context already owns a write transaction."""


class ParticipantStatementError(ImmediateTransactionError):
    """A participant statement is outside the narrow SQL surface."""


class TransactionControlError(ParticipantStatementError):
    """A participant attempted to take over transaction control."""


class _SessionPhase(enum.Enum):
    ACTIVE = enum.auto()
    COMMIT_ATTEMPTED = enum.auto()
    COMMITTED = enum.auto()
    DEACTIVATED = enum.auto()
    CLOSED = enum.auto()


class _OriginalConnectionSettlement(enum.Enum):
    ROLLED_BACK = enum.auto()
    NO_ACTIVE_TRANSACTION = enum.auto()


@dataclass(frozen=True)
class _AuthorityState:
    database_path: Path
    device: int
    inode: int
    held_database_fd: int
    campaign_id: str
    schema_generation: str
    execution_lock_identity: object
    execution_lock_is_held: _ExecutionLockProbe
    validate_database_identity: _DatabaseIdentityValidator


@dataclass
class _SessionState:
    connection: sqlite3.Connection | None
    opened_main_fd: int
    sqlite_handle: int | None
    authority: "CampaignDatabaseAuthority"
    capability: "ImmediateTransaction"
    context_token: contextvars.Token["ImmediateTransaction | None"]
    session_context_token: contextvars.Token[
        "_CoordinatedTransactionSession | None"
    ]
    phase: _SessionPhase = _SessionPhase.ACTIVE
    participant_statement_count: int = 0
    authorizer_handle: "_TransactionAuthorizerHandle | None" = None
    transaction_context_cleared: bool = False
    session_context_cleared: bool = False


@dataclass
class _CapabilityState:
    connection: sqlite3.Connection | None
    authority: "CampaignDatabaseAuthority"
    session_ref: weakref.ReferenceType["_CoordinatedTransactionSession"]
    thread_id: int
    active: bool = True


@dataclass
class _AuthorizerState:
    session_ref: weakref.ReferenceType["_CoordinatedTransactionSession"]
    authority: "CampaignDatabaseAuthority"
    active: bool = True


@dataclass
class _ReadSnapshotState:
    connection: sqlite3.Connection | None
    opened_main_fd: int
    sqlite_handle: int | None
    authority: "CampaignDatabaseAuthority"
    thread_id: int
    context_token: contextvars.Token["_IndependentReadSnapshot | None"]
    active: bool = True
    context_cleared: bool = False


_AUTHORITY_STATES: weakref.WeakKeyDictionary[
    "CampaignDatabaseAuthority", _AuthorityState
] = weakref.WeakKeyDictionary()
_AUTHORITY_STATES_LOCK = threading.RLock()
_SESSION_STATES: weakref.WeakKeyDictionary[
    "_CoordinatedTransactionSession", _SessionState
] = weakref.WeakKeyDictionary()
_SESSION_STATES_LOCK = threading.RLock()
_CAPABILITY_STATES: weakref.WeakKeyDictionary[
    "ImmediateTransaction", _CapabilityState
] = weakref.WeakKeyDictionary()
_CAPABILITY_STATES_LOCK = threading.RLock()
_AUTHORIZER_STATES: weakref.WeakKeyDictionary[
    "_TransactionAuthorizerHandle", _AuthorizerState
] = weakref.WeakKeyDictionary()
_AUTHORIZER_STATES_LOCK = threading.RLock()
_READ_SNAPSHOT_STATES: weakref.WeakKeyDictionary[
    "_IndependentReadSnapshot", _ReadSnapshotState
] = weakref.WeakKeyDictionary()
_READ_SNAPSHOT_STATES_LOCK = threading.RLock()
_SQLITE_HANDLE_CAPTURE_LOCK = threading.RLock()
_SQLITE_HANDLE_CAPTURE_LOCAL = threading.local()
_SQLITE_C_LIBRARY: ctypes.CDLL | None = None

_SQLiteAutoExtension = ctypes.CFUNCTYPE(
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_char_p),
    ctypes.c_void_p,
)


def _capture_sqlite_handle(
    db_handle: int | None,
    _error_message: ctypes.POINTER(ctypes.c_char_p),
    _api: int | None,
) -> int:
    captures = getattr(_SQLITE_HANDLE_CAPTURE_LOCAL, "captures", None)
    if captures is not None:
        try:
            captures.append(0 if db_handle is None else int(db_handle))
        except BaseException:
            _SQLITE_HANDLE_CAPTURE_LOCAL.failed = True
    return _SQLITE_OK


_SQLITE_HANDLE_CAPTURE_CALLBACK = _SQLiteAutoExtension(_capture_sqlite_handle)

_ACTIVE_TRANSACTION: contextvars.ContextVar["ImmediateTransaction | None"] = (
    contextvars.ContextVar("scion_active_immediate_transaction", default=None)
)
_ACTIVE_COORDINATED_SESSION: contextvars.ContextVar[
    "_CoordinatedTransactionSession | None"
] = contextvars.ContextVar("scion_active_coordinated_session", default=None)
_ACTIVE_READ_SNAPSHOT: contextvars.ContextVar[
    "_IndependentReadSnapshot | None"
] = contextvars.ContextVar("scion_active_independent_read_snapshot", default=None)
_THREAD_OWNER = threading.local()


class CampaignDatabaseAuthority:
    """Sealed identity of one verified Campaign database and execution lock."""

    __slots__ = ("__weakref__",)

    def __new__(
        cls, *_args: object, **_kwargs: object
    ) -> "CampaignDatabaseAuthority":
        raise InvalidCampaignDatabaseAuthorityError(
            "CampaignDatabaseAuthority is issued only after schema bootstrap"
        )

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("CampaignDatabaseAuthority is sealed and cannot be subclassed")


class ImmediateTransaction:
    """Sealed authority for one active ``BEGIN IMMEDIATE`` transaction."""

    __slots__ = ("__weakref__",)

    def __new__(cls, *_args: object, **_kwargs: object) -> "ImmediateTransaction":
        raise InvalidImmediateTransactionError(
            "ImmediateTransaction is issued only by a coordinated session"
        )

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("ImmediateTransaction is sealed and cannot be subclassed")


class _CoordinatedTransactionSession:
    """Opaque authority-owned handle for split transaction lifecycle steps."""

    __slots__ = ("__weakref__",)

    def __new__(
        cls, *_args: object, **_kwargs: object
    ) -> "_CoordinatedTransactionSession":
        raise InvalidImmediateTransactionError(
            "coordinated sessions are issued only by the private opener"
        )

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("coordinated transaction session is sealed")


class _TransactionAuthorizerHandle:
    """Opaque proof that a generic SQLite authorizer is installed on a session."""

    __slots__ = ("__weakref__",)

    def __new__(
        cls, *_args: object, **_kwargs: object
    ) -> "_TransactionAuthorizerHandle":
        raise InvalidImmediateTransactionError(
            "transaction authorizer handles are issued only by this module"
        )


class _IndependentReadSnapshot:
    """Opaque handle for one authority-verified, consistent read snapshot."""

    __slots__ = ("__weakref__",)

    def __new__(cls, *_args: object, **_kwargs: object) -> "_IndependentReadSnapshot":
        raise InvalidImmediateTransactionError(
            "read snapshots are issued only by the private context manager"
        )


class ImmediateResult:
    """Cursor-free materialized participant result bound to one capability."""

    __slots__ = (
        "__capability",
        "__description",
        "__index",
        "__lastrowid",
        "__rowcount",
        "__rows",
    )

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("ImmediateResult is created only by participant execution")

    @classmethod
    def _create(
        cls,
        capability: ImmediateTransaction,
        *,
        rows: tuple[sqlite3.Row, ...],
        rowcount: int,
        lastrowid: int | None,
        description: tuple[tuple[Any, ...], ...] | None,
    ) -> "ImmediateResult":
        result = object.__new__(cls)
        result.__capability = capability
        result.__rows = rows
        result.__index = 0
        result.__rowcount = rowcount
        result.__lastrowid = lastrowid
        result.__description = description
        return result

    def _require_active(self) -> None:
        state = _lookup_capability_state(self.__capability)
        require_active_immediate_transaction(self.__capability, state.authority)

    def fetchone(self) -> sqlite3.Row | None:
        self._require_active()
        if self.__index >= len(self.__rows):
            return None
        row = self.__rows[self.__index]
        self.__index += 1
        return row

    def fetchmany(self, size: int | None = None) -> list[sqlite3.Row]:
        self._require_active()
        fetch_size = 1 if size is None else size
        if isinstance(fetch_size, bool) or not isinstance(fetch_size, int):
            raise TypeError("fetchmany size must be an integer")
        if fetch_size < 0:
            fetch_size = len(self.__rows) - self.__index
        end = min(len(self.__rows), self.__index + fetch_size)
        rows = list(self.__rows[self.__index : end])
        self.__index = end
        return rows

    def fetchall(self) -> list[sqlite3.Row]:
        self._require_active()
        rows = list(self.__rows[self.__index :])
        self.__index = len(self.__rows)
        return rows

    @property
    def rowcount(self) -> int:
        self._require_active()
        return self.__rowcount

    @property
    def lastrowid(self) -> int | None:
        self._require_active()
        return self.__lastrowid

    @property
    def description(self) -> tuple[tuple[Any, ...], ...] | None:
        self._require_active()
        return self.__description

    def __iter__(self) -> "ImmediateResult":
        self._require_active()
        return self

    def __next__(self) -> sqlite3.Row:
        row = self.fetchone()
        if row is None:
            raise StopIteration
        return row


def _validate_nonempty_exact_string(value: str, *, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{field} must be a nonempty exact str")
    return value


def _validate_busy_timeout_ms(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("busy_timeout_ms must be a positive integer")
    return value


def _stat_regular_file(path: Path) -> os.stat_result:
    try:
        value = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise SQLiteConnectionPolicyError(
            f"Campaign database path is unavailable: {path}"
        ) from exc
    if not stat.S_ISREG(value.st_mode):
        raise SQLiteConnectionPolicyError(
            f"Campaign database path is not a regular file: {path}"
        )
    return value


def _assert_same_file(
    actual: os.stat_result,
    *,
    device: int,
    inode: int,
    description: str,
) -> None:
    if (actual.st_dev, actual.st_ino) != (device, inode):
        raise SQLiteConnectionPolicyError(
            f"Campaign database {description} identity changed"
        )


def _append_exception_context(primary: BaseException, secondary: BaseException) -> None:
    secondary_cursor = secondary
    secondary_seen = {id(secondary_cursor)}
    while secondary_cursor.__context__ is not None:
        if secondary_cursor.__context__ is primary:
            secondary_cursor.__context__ = None
            break
        if id(secondary_cursor.__context__) in secondary_seen:
            break
        secondary_cursor = secondary_cursor.__context__
        secondary_seen.add(id(secondary_cursor))

    cursor = primary
    seen = {id(cursor)}
    while cursor.__context__ is not None and id(cursor.__context__) not in seen:
        cursor = cursor.__context__
        seen.add(id(cursor))
    if id(secondary) not in seen:
        cursor.__context__ = secondary


def _raise_primary_with_cleanup(
    primary: BaseException,
    traceback: TracebackType | None,
    cleanup_errors: Sequence[BaseException],
) -> None:
    for cleanup_error in cleanup_errors:
        _append_exception_context(primary, cleanup_error)
    raise primary.with_traceback(traceback)


def _close_descriptor(descriptor: int, errors: list[BaseException]) -> None:
    try:
        os.close(descriptor)
    except BaseException as error:
        errors.append(error)


def _sqlite_c_library() -> ctypes.CDLL:
    """Load the exact SQLite C library backing Python's sqlite3 module."""

    global _SQLITE_C_LIBRARY
    with _SQLITE_HANDLE_CAPTURE_LOCK:
        if _SQLITE_C_LIBRARY is not None:
            return _SQLITE_C_LIBRARY
        library_name = ctypes.util.find_library("sqlite3")
        if library_name is None:
            raise SQLiteConnectionPolicyError(
                "the SQLite C library is unavailable for actual-main verification"
            )
        library = ctypes.CDLL(library_name)
        library.sqlite3_libversion.argtypes = []
        library.sqlite3_libversion.restype = ctypes.c_char_p
        raw_version = library.sqlite3_libversion()
        loaded_version = "" if raw_version is None else raw_version.decode("ascii")
        if loaded_version != sqlite3.sqlite_version:
            raise SQLiteConnectionPolicyError(
                "Python sqlite3 and the verification C library have different versions"
            )
        library.sqlite3_auto_extension.argtypes = [ctypes.c_void_p]
        library.sqlite3_auto_extension.restype = ctypes.c_int
        library.sqlite3_cancel_auto_extension.argtypes = [ctypes.c_void_p]
        library.sqlite3_cancel_auto_extension.restype = ctypes.c_int
        library.sqlite3_file_control.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_void_p,
        ]
        library.sqlite3_file_control.restype = ctypes.c_int
        _SQLITE_C_LIBRARY = library
        return library


def _assert_sqlite_main_not_moved(sqlite_handle: int) -> None:
    if isinstance(sqlite_handle, bool) or not isinstance(sqlite_handle, int):
        raise SQLiteConnectionPolicyError("SQLite handle proof is malformed")
    moved = ctypes.c_int(-1)
    result = _sqlite_c_library().sqlite3_file_control(
        ctypes.c_void_p(sqlite_handle),
        b"main",
        _SQLITE_FCNTL_HAS_MOVED,
        ctypes.byref(moved),
    )
    if result != _SQLITE_OK:
        raise SQLiteConnectionPolicyError(
            "SQLite VFS cannot verify whether the actual main handle moved"
        )
    if moved.value != 0:
        raise SQLiteConnectionPolicyError(
            "SQLite actual main handle differs from the authoritative path"
        )


def _connect_with_captured_sqlite_handle(
    db_path: Path,
    *,
    timeout_ms: int,
) -> tuple[sqlite3.Connection, int]:
    """Open one connection and capture its exact ``sqlite3*`` handle."""

    library = _sqlite_c_library()
    callback_pointer = ctypes.cast(
        _SQLITE_HANDLE_CAPTURE_CALLBACK,
        ctypes.c_void_p,
    )
    connection: sqlite3.Connection | None = None
    primary: BaseException | None = None
    traceback: TracebackType | None = None
    cleanup_errors: list[BaseException] = []
    captures: list[int] = []
    cancel_results: list[int] = []
    capture_failed = False
    registration_returned_ok = False
    with _SQLITE_HANDLE_CAPTURE_LOCK:
        if getattr(_SQLITE_HANDLE_CAPTURE_LOCAL, "captures", None) is not None:
            raise SQLiteConnectionPolicyError(
                "nested SQLite handle capture is forbidden"
            )
        _SQLITE_HANDLE_CAPTURE_LOCAL.captures = captures
        _SQLITE_HANDLE_CAPTURE_LOCAL.failed = False
        try:
            register_result = library.sqlite3_auto_extension(callback_pointer)
            if register_result != _SQLITE_OK:
                raise SQLiteConnectionPolicyError(
                    "SQLite handle-capture registration failed"
                )
            registration_returned_ok = True
            connection = sqlite3.connect(
                str(db_path),
                timeout=timeout_ms / 1_000,
                isolation_level=None,
                cached_statements=0,
            )
        except BaseException as error:
            primary = error
            traceback = error.__traceback__
        finally:
            # Cancel unconditionally: registration may have reached native
            # SQLite even if a proxy/trace interrupted before Python observed
            # its return.  A one-time cancellation fault gets one cleanup
            # attempt before TLS is released.
            try:
                try:
                    cancel_results.append(
                        library.sqlite3_cancel_auto_extension(callback_pointer)
                    )
                except BaseException as cancel_error:
                    cleanup_errors.append(cancel_error)
                    try:
                        cancel_results.append(
                            library.sqlite3_cancel_auto_extension(callback_pointer)
                        )
                    except BaseException as recovery_error:
                        cleanup_errors.append(recovery_error)
            finally:
                capture_failed = bool(
                    getattr(_SQLITE_HANDLE_CAPTURE_LOCAL, "failed", False)
                )
                try:
                    del _SQLITE_HANDLE_CAPTURE_LOCAL.captures
                except AttributeError:
                    pass
                try:
                    del _SQLITE_HANDLE_CAPTURE_LOCAL.failed
                except AttributeError:
                    pass

    if primary is None and cleanup_errors:
        primary = cleanup_errors.pop(0)
        traceback = primary.__traceback__
    if (
        primary is None
        and registration_returned_ok
        and cancel_results != [1]
    ):
        primary = SQLiteConnectionPolicyError(
            "SQLite handle-capture callback was not removed exactly once"
        )
        traceback = primary.__traceback__
    if primary is None and (capture_failed or len(captures) != 1 or captures[0] == 0):
        primary = SQLiteConnectionPolicyError(
            "SQLite connection did not yield one exact native handle"
        )
        traceback = primary.__traceback__
    if primary is not None:
        if connection is not None:
            try:
                connection.close()
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
        _raise_primary_with_cleanup(primary, traceback, cleanup_errors)
    assert connection is not None
    return connection, captures[0]


def _issue_campaign_database_authority(
    db_path: str | Path,
    *,
    held_database_fd: int,
    campaign_id: str,
    schema_generation: str,
    execution_lock_identity: object,
    execution_lock_is_held: _ExecutionLockProbe,
    validate_database_identity: _DatabaseIdentityValidator,
) -> CampaignDatabaseAuthority:
    """Private production issuer reserved for the exact schema-bootstrap adapter."""

    campaign = _validate_nonempty_exact_string(campaign_id, field="campaign_id")
    generation = _validate_nonempty_exact_string(
        schema_generation, field="schema_generation"
    )
    if not isinstance(held_database_fd, int) or isinstance(held_database_fd, bool):
        raise TypeError("held_database_fd must be an open integer file descriptor")
    if not callable(execution_lock_is_held):
        raise TypeError("execution_lock_is_held must be callable")
    if not callable(validate_database_identity):
        raise TypeError("validate_database_identity must be callable")

    canonical_path = Path(db_path).expanduser().resolve(strict=True)
    path_stat = _stat_regular_file(canonical_path)
    try:
        descriptor_stat = os.fstat(held_database_fd)
    except OSError as exc:
        raise SQLiteConnectionPolicyError(
            "held Campaign database descriptor is not open"
        ) from exc
    _assert_same_file(
        descriptor_stat,
        device=path_stat.st_dev,
        inode=path_stat.st_ino,
        description="held descriptor",
    )

    owned_fd = os.dup(held_database_fd)
    os.set_inheritable(owned_fd, False)
    authority = object.__new__(CampaignDatabaseAuthority)
    state = _AuthorityState(
        database_path=canonical_path,
        device=path_stat.st_dev,
        inode=path_stat.st_ino,
        held_database_fd=owned_fd,
        campaign_id=campaign,
        schema_generation=generation,
        execution_lock_identity=execution_lock_identity,
        execution_lock_is_held=execution_lock_is_held,
        validate_database_identity=validate_database_identity,
    )
    with _AUTHORITY_STATES_LOCK:
        _AUTHORITY_STATES[authority] = state
    weakref.finalize(authority, os.close, owned_fd)
    return authority


def _issue_test_campaign_database_authority(
    db_path: str | Path,
    *,
    campaign_id: str = "test-campaign",
    schema_generation: str = "durable-owner.test",
    execution_lock_is_held: _ExecutionLockProbe | None = None,
    validate_database_identity: _DatabaseIdentityValidator | None = None,
) -> CampaignDatabaseAuthority:
    """Explicit test-only authority issuer; never a production bootstrap path."""

    path = Path(db_path).expanduser().resolve(strict=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        return _issue_campaign_database_authority(
            path,
            held_database_fd=descriptor,
            campaign_id=campaign_id,
            schema_generation=schema_generation,
            execution_lock_identity=object(),
            execution_lock_is_held=execution_lock_is_held or (lambda: True),
            validate_database_identity=(
                validate_database_identity
                or (lambda _connection, _campaign_id, _schema_generation: None)
            ),
        )
    finally:
        os.close(descriptor)


def _lookup_authority_state(value: object) -> _AuthorityState:
    if type(value) is not CampaignDatabaseAuthority:
        raise InvalidCampaignDatabaseAuthorityError(
            "operation requires an issued CampaignDatabaseAuthority"
        )
    with _AUTHORITY_STATES_LOCK:
        state = _AUTHORITY_STATES.get(value)
    if state is None:
        raise InvalidCampaignDatabaseAuthorityError(
            "CampaignDatabaseAuthority was not issued by this module"
        )
    return state


def _assert_authority_live(state: _AuthorityState) -> None:
    try:
        lock_is_held = state.execution_lock_is_held()
    except BaseException as exc:
        raise SQLiteConnectionPolicyError(
            "Campaign execution-lock liveness check failed"
        ) from exc
    if lock_is_held is not True:
        raise SQLiteConnectionPolicyError("Campaign execution lock is not held")
    try:
        descriptor_stat = os.fstat(state.held_database_fd)
    except OSError as exc:
        raise SQLiteConnectionPolicyError(
            "held Campaign database descriptor is no longer open"
        ) from exc
    _assert_same_file(
        descriptor_stat,
        device=state.device,
        inode=state.inode,
        description="held descriptor",
    )
    _assert_same_file(
        _stat_regular_file(state.database_path),
        device=state.device,
        inode=state.inode,
        description="path",
    )


def _read_pragma_scalar(connection: sqlite3.Connection, name: str) -> Any:
    row = connection.execute(f"PRAGMA {name}").fetchone()
    if row is None:
        raise SQLiteConnectionPolicyError(f"PRAGMA {name} returned no value")
    return row[0]


def _validate_connection_policy(
    connection: sqlite3.Connection,
    *,
    busy_timeout_ms: int,
) -> None:
    actual = {
        "journal_mode": str(_read_pragma_scalar(connection, "journal_mode")).lower(),
        "synchronous": int(_read_pragma_scalar(connection, "synchronous")),
        "foreign_keys": int(_read_pragma_scalar(connection, "foreign_keys")),
        "recursive_triggers": int(
            _read_pragma_scalar(connection, "recursive_triggers")
        ),
        "busy_timeout": int(_read_pragma_scalar(connection, "busy_timeout")),
    }
    expected = {
        "journal_mode": "wal",
        "synchronous": 2,
        "foreign_keys": 1,
        "recursive_triggers": 1,
        "busy_timeout": busy_timeout_ms,
    }
    if actual != expected:
        raise SQLiteConnectionPolicyError(
            f"SQLite connection policy mismatch: expected {expected!r}, got {actual!r}"
        )
    if connection.isolation_level is not None:
        raise SQLiteConnectionPolicyError(
            "SQLite owner connections must use explicit transaction control"
        )


def _open_raw_sqlite_from_descriptor(
    db_path: Path,
    database_fd: int,
    *,
    timeout_ms: int,
) -> tuple[sqlite3.Connection, int, int]:
    """Open and prove SQLite's actual ``main`` against one held descriptor."""

    try:
        descriptor_stat = os.fstat(database_fd)
    except OSError as exc:
        raise SQLiteConnectionPolicyError(
            "held SQLite source descriptor is not open"
        ) from exc
    if not stat.S_ISREG(descriptor_stat.st_mode):
        raise SQLiteConnectionPolicyError(
            "held SQLite source descriptor is not a regular file"
        )
    _assert_same_file(
        _stat_regular_file(db_path),
        device=descriptor_stat.st_dev,
        inode=descriptor_stat.st_ino,
        description="source descriptor",
    )

    connection: sqlite3.Connection | None = None
    proof_fd: int | None = None
    sqlite_handle: int | None = None
    try:
        connection, sqlite_handle = _connect_with_captured_sqlite_handle(
            db_path,
            timeout_ms=timeout_ms,
        )
        # HAS_MOVED is implemented by the active VFS against its real
        # sqlite3_file, not against a guessed process FD or database-list path.
        _assert_sqlite_main_not_moved(sqlite_handle)
        _assert_same_file(
            _stat_regular_file(db_path),
            device=descriptor_stat.st_dev,
            inode=descriptor_stat.st_ino,
            description="path after descriptor-addressed open",
        )
        proof_fd = os.dup(database_fd)
        os.set_inheritable(proof_fd, False)
        return connection, proof_fd, sqlite_handle
    except BaseException as primary:
        traceback = primary.__traceback__
        cleanup_errors: list[BaseException] = []
        if proof_fd is not None:
            _close_descriptor(proof_fd, cleanup_errors)
        if connection is not None:
            try:
                connection.close()
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
        _raise_primary_with_cleanup(primary, traceback, cleanup_errors)


def _configure_sqlite_connection(
    connection: sqlite3.Connection,
    *,
    busy_timeout_ms: int,
) -> None:
    connection.row_factory = sqlite3.Row
    connection.enable_load_extension(False)
    connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA recursive_triggers=ON")
    journal_mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()
    if journal_mode is None or str(journal_mode[0]).lower() != "wal":
        actual = None if journal_mode is None else journal_mode[0]
        raise SQLiteConnectionPolicyError(f"SQLite WAL activation failed: got {actual!r}")
    connection.execute("PRAGMA synchronous=FULL")
    _validate_connection_policy(connection, busy_timeout_ms=busy_timeout_ms)


def _connect_sqlite(
    db_path: str | Path,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
) -> sqlite3.Connection:
    """Private raw factory for transaction contexts and schema bootstrap only."""

    timeout_ms = _validate_busy_timeout_ms(busy_timeout_ms)
    path = Path(db_path).expanduser().resolve(strict=False)
    connection: sqlite3.Connection | None = None
    opened_main_fd: int | None = None
    sqlite_handle: int | None = None
    source_fd: int | None = None
    try:
        flags = os.O_RDWR | os.O_CREAT
        flags |= getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        source_fd = os.open(path, flags, 0o600)
        os.set_inheritable(source_fd, False)
        connection, opened_main_fd, sqlite_handle = _open_raw_sqlite_from_descriptor(
            path,
            source_fd,
            timeout_ms=timeout_ms,
        )
        _configure_sqlite_connection(connection, busy_timeout_ms=timeout_ms)
        _assert_sqlite_main_not_moved(sqlite_handle)
        opened_path = _opened_main_path(connection)
        if opened_path != path:
            raise SQLiteConnectionPolicyError(
                "opened SQLite main path differs from requested path"
            )
        os.close(opened_main_fd)
        opened_main_fd = None
        os.close(source_fd)
        source_fd = None
        return connection
    except BaseException as primary:
        traceback = primary.__traceback__
        cleanup_errors: list[BaseException] = []
        if connection is not None:
            try:
                connection.close()
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
        if opened_main_fd is not None:
            _close_descriptor(opened_main_fd, cleanup_errors)
        if source_fd is not None:
            _close_descriptor(source_fd, cleanup_errors)
        _raise_primary_with_cleanup(primary, traceback, cleanup_errors)


def _opened_main_path(connection: sqlite3.Connection) -> Path:
    rows = connection.execute("PRAGMA database_list").fetchall()
    for row in rows:
        if str(row[1]) == "main":
            raw_path = str(row[2])
            if raw_path:
                return Path(raw_path).expanduser().resolve(strict=True)
    raise SQLiteConnectionPolicyError("opened SQLite connection has no file-backed main")


def _connect_authority_sqlite(
    authority: CampaignDatabaseAuthority,
    *,
    busy_timeout_ms: int,
) -> tuple[sqlite3.Connection, int, int]:
    state = _lookup_authority_state(authority)
    _assert_authority_live(state)
    connection: sqlite3.Connection | None = None
    opened_main_fd: int | None = None
    sqlite_handle: int | None = None
    try:
        connection, opened_main_fd, sqlite_handle = _open_raw_sqlite_from_descriptor(
            state.database_path,
            state.held_database_fd,
            timeout_ms=busy_timeout_ms,
        )
        _assert_same_file(
            os.fstat(opened_main_fd),
            device=state.device,
            inode=state.inode,
            description="descriptor-addressed SQLite main proof FD",
        )
        _configure_sqlite_connection(connection, busy_timeout_ms=busy_timeout_ms)
        _assert_sqlite_main_not_moved(sqlite_handle)
        opened_path = _opened_main_path(connection)
        if opened_path != state.database_path:
            raise SQLiteConnectionPolicyError(
                "opened SQLite main path differs from Campaign authority"
            )
        _assert_same_file(
            os.fstat(opened_main_fd),
            device=state.device,
            inode=state.inode,
            description="descriptor-addressed SQLite main proof FD",
        )
        _assert_authority_live(state)
        state.validate_database_identity(
            connection,
            state.campaign_id,
            state.schema_generation,
        )
        return connection, opened_main_fd, sqlite_handle
    except BaseException as primary:
        traceback = primary.__traceback__
        cleanup_errors: list[BaseException] = []
        if connection is not None:
            try:
                connection.close()
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
        if opened_main_fd is not None:
            _close_descriptor(opened_main_fd, cleanup_errors)
        _raise_primary_with_cleanup(primary, traceback, cleanup_errors)


def _thread_owner() -> object | None:
    return getattr(_THREAD_OWNER, "active", None)


def _thread_session_owner() -> object | None:
    return getattr(_THREAD_OWNER, "session", None)


def _reserve_thread_owner() -> None:
    if (
        _thread_owner() is not None
        or _thread_session_owner() is not None
        or _ACTIVE_TRANSACTION.get() is not None
        or _ACTIVE_COORDINATED_SESSION.get() is not None
        or _ACTIVE_READ_SNAPSHOT.get() is not None
    ):
        raise NestedImmediateTransactionError("nested immediate transactions are forbidden")
    _THREAD_OWNER.active = _OPENING_TRANSACTION


def _clear_thread_owner() -> None:
    _THREAD_OWNER.active = None


def _clear_thread_session_owner() -> None:
    _THREAD_OWNER.session = None


def _renew_context_binding(
    variable: contextvars.ContextVar[Any],
    token: contextvars.Token[Any],
    expected: object,
    *,
    install_token: Callable[[contextvars.Token[Any]], None],
    description: str,
) -> None:
    if variable.get() is not expected:
        raise _ForeignLifecycleContextError(
            f"{description} does not own the current Context"
        )
    reset_completed = False
    try:
        variable.reset(token)
        reset_completed = True
    except (RuntimeError, ValueError) as exc:
        if variable.get() is expected:
            raise _ForeignLifecycleContextError(
                f"{description} was entered in another Context"
            ) from exc
        recovery_token = variable.set(expected)
        install_token(recovery_token)
        raise
    except BaseException:
        if variable.get() is not expected:
            recovery_token = variable.set(expected)
            install_token(recovery_token)
        raise
    try:
        replacement_token = variable.set(expected)
        install_token(replacement_token)
    except BaseException:
        # A proxy, trace, or signal can fire after ``set`` changed the value
        # but before its token reached Python.  Rebuild and install the token
        # here, inside the same fault boundary, before propagating the error.
        if not reset_completed:
            raise
        variable.set(None)
        recovery_token = variable.set(expected)
        install_token(recovery_token)
        raise


def _lookup_session_state(value: object) -> _SessionState:
    if type(value) is not _CoordinatedTransactionSession:
        raise InvalidImmediateTransactionError(
            "operation requires an issued coordinated transaction session"
        )
    with _SESSION_STATES_LOCK:
        state = _SESSION_STATES.get(value)
    if state is None:
        raise InvalidImmediateTransactionError(
            "coordinated transaction session was not issued by this module"
        )
    return state


def _require_session_authority(
    session: _CoordinatedTransactionSession,
    authority: CampaignDatabaseAuthority,
) -> _SessionState:
    _lookup_authority_state(authority)
    state = _lookup_session_state(session)
    if state.authority is not authority:
        raise InvalidImmediateTransactionError(
            "coordinated transaction session is bound to another authority"
        )
    return state


def _assert_session_main_identity(state: _SessionState) -> None:
    authority_state = _lookup_authority_state(state.authority)
    _assert_same_file(
        os.fstat(state.opened_main_fd),
        device=authority_state.device,
        inode=authority_state.inode,
        description="session SQLite main FD",
    )
    if state.sqlite_handle is None:
        raise InactiveImmediateTransactionError(
            "coordinated SQLite handle is no longer available"
        )
    _assert_sqlite_main_not_moved(state.sqlite_handle)


def _assert_session_thread_binding(
    session: _CoordinatedTransactionSession,
    state: _SessionState,
    *,
    require_active_context: bool,
) -> None:
    capability_state = _lookup_capability_state(state.capability)
    if capability_state.thread_id != threading.get_ident():
        raise _ForeignLifecycleContextError(
            "coordinated session cannot cross its issuing thread"
        )
    _renew_context_binding(
        _ACTIVE_COORDINATED_SESSION,
        state.session_context_token,
        session,
        install_token=lambda token: setattr(
            state,
            "session_context_token",
            token,
        ),
        description="coordinated session",
    )
    if _thread_session_owner() is not session:
        raise InactiveImmediateTransactionError(
            "coordinated session does not own the current thread"
        )
    if require_active_context and (
        _thread_owner() is not state.capability
        or _ACTIVE_TRANSACTION.get() is not state.capability
    ):
        raise InactiveImmediateTransactionError(
            "coordinated session does not own the current thread and Context"
        )
    if require_active_context:
        _renew_context_binding(
            _ACTIVE_TRANSACTION,
            state.context_token,
            state.capability,
            install_token=lambda token: setattr(state, "context_token", token),
            description="ImmediateTransaction",
        )


def _issue_capability(
    connection: sqlite3.Connection,
    authority: CampaignDatabaseAuthority,
    session: _CoordinatedTransactionSession,
) -> ImmediateTransaction:
    capability = object.__new__(ImmediateTransaction)
    state = _CapabilityState(
        connection=connection,
        authority=authority,
        session_ref=weakref.ref(session),
        thread_id=threading.get_ident(),
    )
    with _CAPABILITY_STATES_LOCK:
        _CAPABILITY_STATES[capability] = state
    return capability


def _lookup_capability_state(value: object) -> _CapabilityState:
    if type(value) is not ImmediateTransaction:
        raise InvalidImmediateTransactionError(
            "participant requires an issued ImmediateTransaction"
        )
    with _CAPABILITY_STATES_LOCK:
        state = _CAPABILITY_STATES.get(value)
    if state is None:
        raise InvalidImmediateTransactionError(
            "ImmediateTransaction was not issued by this module"
        )
    return state


def _require_active_state(
    value: object,
    authority: CampaignDatabaseAuthority,
    *,
    session: _CoordinatedTransactionSession | None = None,
) -> _CapabilityState:
    _lookup_authority_state(authority)
    state = _lookup_capability_state(value)
    if state.authority is not authority:
        raise InvalidImmediateTransactionError(
            "ImmediateTransaction is bound to another authority"
        )
    issued_session = state.session_ref()
    if issued_session is None:
        raise InactiveImmediateTransactionError(
            "ImmediateTransaction session is no longer available"
        )
    if session is not None and issued_session is not session:
        raise InvalidImmediateTransactionError(
            "ImmediateTransaction is bound to another coordinated session"
        )
    session_state = _require_session_authority(issued_session, authority)
    _assert_session_thread_binding(
        issued_session,
        session_state,
        require_active_context=True,
    )
    if session_state.phase is not _SessionPhase.ACTIVE:
        raise InactiveImmediateTransactionError(
            "ImmediateTransaction session is no longer active"
        )
    if state.thread_id != threading.get_ident():
        raise InactiveImmediateTransactionError(
            "ImmediateTransaction cannot cross its issuing thread"
        )
    if not state.active:
        raise InactiveImmediateTransactionError("ImmediateTransaction is no longer active")
    if _thread_owner() is not value:
        raise InactiveImmediateTransactionError(
            "ImmediateTransaction does not own the current thread"
        )
    if _ACTIVE_TRANSACTION.get() is not value:
        raise InactiveImmediateTransactionError(
            "ImmediateTransaction does not own the current Context"
        )
    connection = state.connection
    if connection is None or not connection.in_transaction:
        raise InactiveImmediateTransactionError(
            "ImmediateTransaction no longer owns an SQLite transaction"
        )
    _assert_session_main_identity(session_state)
    return state


def require_active_immediate_transaction(
    value: object,
    authority: CampaignDatabaseAuthority,
) -> ImmediateTransaction:
    """Validate one active capability against its exact database authority."""

    _require_active_state(value, authority)
    return value  # type: ignore[return-value]


def _require_transaction_session(
    transaction: ImmediateTransaction,
    authority: CampaignDatabaseAuthority,
    session: _CoordinatedTransactionSession,
) -> ImmediateTransaction:
    """Private exact binding used by the future owner-transaction module."""

    _require_active_state(transaction, authority, session=session)
    return transaction


def _deactivate_capability(capability: ImmediateTransaction) -> None:
    with _CAPABILITY_STATES_LOCK:
        state = _CAPABILITY_STATES.get(capability)
        if state is not None:
            state.active = False
            state.connection = None


def _invalidate_session_handles(state: _SessionState) -> None:
    """Make participant handles unusable without touching the raw session owner."""

    cleanup_errors: list[BaseException] = []
    try:
        with _CAPABILITY_STATES_LOCK:
            capability_state = _CAPABILITY_STATES.get(state.capability)
            if capability_state is not None:
                capability_state.active = False
                capability_state.connection = None
    except BaseException as error:
        cleanup_errors.append(error)
    try:
        with _AUTHORIZER_STATES_LOCK:
            if state.authorizer_handle is not None:
                authorizer_state = _AUTHORIZER_STATES.get(state.authorizer_handle)
                if authorizer_state is not None:
                    authorizer_state.active = False
    except BaseException as error:
        cleanup_errors.append(error)
    if cleanup_errors:
        primary = cleanup_errors[0]
        _raise_primary_with_cleanup(primary, primary.__traceback__, cleanup_errors[1:])


def _open_coordinated_transaction_session(
    authority: CampaignDatabaseAuthority,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
) -> _CoordinatedTransactionSession:
    """Open and begin one private authority-owned coordinated session."""

    _lookup_authority_state(authority)
    timeout_ms = _validate_busy_timeout_ms(busy_timeout_ms)
    connection: sqlite3.Connection | None = None
    opened_main_fd: int | None = None
    sqlite_handle: int | None = None
    session: _CoordinatedTransactionSession | None = None
    capability: ImmediateTransaction | None = None
    context_token: contextvars.Token[ImmediateTransaction | None] | None = None
    session_context_token: contextvars.Token[
        _CoordinatedTransactionSession | None
    ] | None = None
    try:
        # Reservation is inside the cleanup boundary so an injected trace or
        # signal immediately after the thread-local write cannot strand the
        # sentinel and block every later transaction on this thread.
        _reserve_thread_owner()
        connection, opened_main_fd, sqlite_handle = _connect_authority_sqlite(
            authority,
            busy_timeout_ms=timeout_ms,
        )
        connection.execute("BEGIN IMMEDIATE")
        session = object.__new__(_CoordinatedTransactionSession)
        _THREAD_OWNER.session = session
        session_context_token = _ACTIVE_COORDINATED_SESSION.set(session)
        capability = _issue_capability(connection, authority, session)
        _THREAD_OWNER.active = capability
        context_token = _ACTIVE_TRANSACTION.set(capability)
        state = _SessionState(
            connection=connection,
            opened_main_fd=opened_main_fd,
            sqlite_handle=sqlite_handle,
            authority=authority,
            capability=capability,
            context_token=context_token,
            session_context_token=session_context_token,
        )
        with _SESSION_STATES_LOCK:
            _SESSION_STATES[session] = state
        return session
    except BaseException as primary:
        traceback = primary.__traceback__
        cleanup_errors: list[BaseException] = []
        if capability is not None:
            _deactivate_capability(capability)
        if context_token is not None:
            try:
                _ACTIVE_TRANSACTION.reset(context_token)
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
        elif capability is not None and _ACTIVE_TRANSACTION.get() is capability:
            try:
                _ACTIVE_TRANSACTION.set(None)
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
        if session_context_token is not None:
            try:
                _ACTIVE_COORDINATED_SESSION.reset(session_context_token)
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
        elif (
            session is not None
            and _ACTIVE_COORDINATED_SESSION.get() is session
        ):
            try:
                _ACTIVE_COORDINATED_SESSION.set(None)
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
        if _thread_owner() is _OPENING_TRANSACTION or _thread_owner() is capability:
            _clear_thread_owner()
        if _thread_session_owner() is session:
            _clear_thread_session_owner()
        if connection is not None and connection.in_transaction:
            try:
                connection.rollback()
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
        if connection is not None:
            try:
                connection.close()
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
        if opened_main_fd is not None:
            _close_descriptor(opened_main_fd, cleanup_errors)
        _raise_primary_with_cleanup(primary, traceback, cleanup_errors)


def _coordinated_transaction(
    session: _CoordinatedTransactionSession,
    authority: CampaignDatabaseAuthority,
) -> ImmediateTransaction:
    state = _require_session_authority(session, authority)
    if state.phase is not _SessionPhase.ACTIVE:
        raise InactiveImmediateTransactionError("coordinated session is not active")
    _require_active_state(state.capability, authority, session=session)
    return state.capability


def _commit_coordinated_transaction(
    session: _CoordinatedTransactionSession,
    authority: CampaignDatabaseAuthority,
) -> None:
    state = _require_session_authority(session, authority)
    if state.phase is not _SessionPhase.ACTIVE:
        raise InvalidImmediateTransactionError(
            "commit requires an active coordinated session"
        )
    _require_active_state(state.capability, authority, session=session)
    authority_state = _lookup_authority_state(authority)
    _assert_authority_live(authority_state)
    _assert_session_main_identity(state)
    state.phase = _SessionPhase.COMMIT_ATTEMPTED
    connection = state.connection
    if connection is None:
        raise InactiveImmediateTransactionError("coordinated connection is unavailable")
    connection.commit()
    state.phase = _SessionPhase.COMMITTED


def _deactivate_coordinated_transaction(
    session: _CoordinatedTransactionSession,
    authority: CampaignDatabaseAuthority,
) -> None:
    state = _require_session_authority(session, authority)
    capability_state = _lookup_capability_state(state.capability)
    if capability_state.thread_id != threading.get_ident():
        raise _ForeignLifecycleContextError(
            "coordinated session cannot cross its issuing thread"
        )
    if state.phase not in {_SessionPhase.DEACTIVATED, _SessionPhase.CLOSED}:
        _assert_session_thread_binding(session, state, require_active_context=True)
        # Phase changes first.  Every participant check now fails closed even
        # when a later staged cleanup boundary is interrupted.
        state.phase = _SessionPhase.DEACTIVATED
    cleanup_errors: list[BaseException] = []
    try:
        _invalidate_session_handles(state)
    except BaseException as error:
        cleanup_errors.append(error)
    if not state.transaction_context_cleared:
        try:
            if _ACTIVE_TRANSACTION.get() is state.capability:
                try:
                    _ACTIVE_TRANSACTION.reset(state.context_token)
                except BaseException as error:
                    cleanup_errors.append(error)
                    if _ACTIVE_TRANSACTION.get() is state.capability:
                        try:
                            _ACTIVE_TRANSACTION.set(None)
                        except BaseException as fallback_error:
                            cleanup_errors.append(fallback_error)
        finally:
            state.transaction_context_cleared = (
                _ACTIVE_TRANSACTION.get() is not state.capability
            )
    try:
        if (
            _thread_owner() is _OPENING_TRANSACTION
            or _thread_owner() is state.capability
        ):
            _clear_thread_owner()
    except BaseException as error:
        cleanup_errors.append(error)
    if cleanup_errors:
        primary = cleanup_errors[0]
        _raise_primary_with_cleanup(primary, primary.__traceback__, cleanup_errors[1:])


def _session_deactivation_complete(state: _SessionState) -> bool:
    with _CAPABILITY_STATES_LOCK:
        capability_state = _CAPABILITY_STATES.get(state.capability)
    capability_inactive = (
        capability_state is None
        or (
            not capability_state.active
            and capability_state.connection is None
        )
    )
    authorizer_inactive = True
    if state.authorizer_handle is not None:
        with _AUTHORIZER_STATES_LOCK:
            authorizer_state = _AUTHORIZER_STATES.get(state.authorizer_handle)
        authorizer_inactive = (
            authorizer_state is None or not authorizer_state.active
        )
    return (
        capability_inactive
        and authorizer_inactive
        and state.transaction_context_cleared
        and _ACTIVE_TRANSACTION.get() is not state.capability
        and _thread_owner() is not state.capability
        and _thread_owner() is not _OPENING_TRANSACTION
    )


def _session_resources_closed(
    session: _CoordinatedTransactionSession,
    state: _SessionState,
) -> bool:
    return (
        _session_deactivation_complete(state)
        and state.connection is None
        and state.sqlite_handle is None
        and state.opened_main_fd == -1
        and state.session_context_cleared
        and _ACTIVE_COORDINATED_SESSION.get() is not session
        and _thread_session_owner() is not session
    )


def _close_coordinated_transaction(
    session: _CoordinatedTransactionSession,
    authority: CampaignDatabaseAuthority,
) -> None:
    state = _require_session_authority(session, authority)
    capability_state = _lookup_capability_state(state.capability)
    if capability_state.thread_id != threading.get_ident():
        raise _ForeignLifecycleContextError(
            "coordinated session cannot cross its issuing thread"
        )
    if state.phase not in {_SessionPhase.DEACTIVATED, _SessionPhase.CLOSED}:
        raise InvalidImmediateTransactionError(
            "close requires a deactivated coordinated session"
        )
    cleanup_errors: list[BaseException] = []
    if not _session_deactivation_complete(state):
        try:
            _deactivate_coordinated_transaction(session, authority)
        except BaseException as error:
            cleanup_errors.append(error)
    connection = state.connection
    if connection is None:
        state.sqlite_handle = None
    if connection is not None and _sqlite_connection_is_closed(connection):
        state.connection = None
        state.sqlite_handle = None
        connection = None
    if connection is not None:
        try:
            connection.close()
        except BaseException as error:
            cleanup_errors.append(error)
            if _sqlite_connection_is_closed(connection):
                state.connection = None
                state.sqlite_handle = None
        else:
            state.connection = None
            state.sqlite_handle = None
    descriptor = state.opened_main_fd
    if descriptor >= 0:
        try:
            os.close(descriptor)
        except BaseException as error:
            cleanup_errors.append(error)
            try:
                os.fstat(descriptor)
            except OSError as status_error:
                if status_error.errno == errno.EBADF:
                    state.opened_main_fd = -1
        else:
            state.opened_main_fd = -1
    if not state.session_context_cleared:
        try:
            if _ACTIVE_COORDINATED_SESSION.get() is session:
                try:
                    _ACTIVE_COORDINATED_SESSION.reset(
                        state.session_context_token
                    )
                except BaseException as error:
                    cleanup_errors.append(error)
                    if _ACTIVE_COORDINATED_SESSION.get() is session:
                        try:
                            _ACTIVE_COORDINATED_SESSION.set(None)
                        except BaseException as fallback_error:
                            cleanup_errors.append(fallback_error)
        finally:
            state.session_context_cleared = (
                _ACTIVE_COORDINATED_SESSION.get() is not session
            )
    try:
        if _thread_session_owner() is session:
            _clear_thread_session_owner()
    except BaseException as error:
        cleanup_errors.append(error)
    if _session_resources_closed(session, state):
        state.phase = _SessionPhase.CLOSED
    if cleanup_errors:
        primary = cleanup_errors[0]
        _raise_primary_with_cleanup(primary, primary.__traceback__, cleanup_errors[1:])


def _settle_deactivated_original_connection(
    session: _CoordinatedTransactionSession,
    authority: CampaignDatabaseAuthority,
) -> _OriginalConnectionSettlement:
    """Rollback-if-active and close only after capability deactivation.

    The returned enum is lifecycle evidence only.  ``NO_ACTIVE_TRANSACTION``
    never proves commit or rollback; a commit-latched owner must classify
    durable receipts through a new independent authority-verified snapshot.
    """

    state = _require_session_authority(session, authority)
    if state.phase not in {_SessionPhase.DEACTIVATED, _SessionPhase.CLOSED}:
        raise InvalidImmediateTransactionError(
            "original-connection settlement requires a deactivated session"
        )
    connection = state.connection

    settlement = _OriginalConnectionSettlement.NO_ACTIVE_TRANSACTION
    primary: BaseException | None = None
    traceback: TracebackType | None = None
    cleanup_errors: list[BaseException] = []
    try:
        if connection is not None and connection.in_transaction:
            connection.rollback()
            settlement = _OriginalConnectionSettlement.ROLLED_BACK
    except BaseException as error:
        primary = error
        traceback = error.__traceback__
    finally:
        try:
            _close_coordinated_transaction(session, authority)
        except BaseException as cleanup_error:
            cleanup_errors.append(cleanup_error)
    if primary is not None:
        primary.__context__ = None
        if cleanup_errors:
            cause = cleanup_errors[0]
            for following in cleanup_errors[1:]:
                cause.__cause__ = following
                cause = following
            primary.__cause__ = cleanup_errors[0]
        raise primary.with_traceback(traceback)
    if cleanup_errors:
        first = cleanup_errors[0]
        _raise_primary_with_cleanup(first, first.__traceback__, cleanup_errors[1:])
    return settlement


def _finalize_context_session(
    session: _CoordinatedTransactionSession,
    authority: CampaignDatabaseAuthority,
    *,
    rollback_if_active: bool,
) -> None:
    """Drive one context-owned session to CLOSED from any live phase."""

    cleanup_errors: list[BaseException] = []
    state = _require_session_authority(session, authority)
    if _session_resources_closed(session, state):
        state.phase = _SessionPhase.CLOSED
        return
    if not _session_deactivation_complete(state):
        try:
            _deactivate_coordinated_transaction(session, authority)
        except BaseException as error:
            cleanup_errors.append(error)
    state = _require_session_authority(session, authority)
    if _session_deactivation_complete(state):
        try:
            if rollback_if_active:
                _settle_deactivated_original_connection(session, authority)
            else:
                _close_coordinated_transaction(session, authority)
        except BaseException as error:
            cleanup_errors.append(error)
    if _session_resources_closed(session, state):
        state.phase = _SessionPhase.CLOSED
    if cleanup_errors:
        primary = cleanup_errors[0]
        _raise_primary_with_cleanup(primary, primary.__traceback__, cleanup_errors[1:])


def _install_transaction_authorizer(
    session: _CoordinatedTransactionSession,
    authority: CampaignDatabaseAuthority,
    authorizer: _SQLiteAuthorizer,
) -> _TransactionAuthorizerHandle:
    """Install one generic policy hook without exposing the raw connection."""

    if not callable(authorizer):
        raise TypeError("authorizer must be callable")
    state = _require_session_authority(session, authority)
    if state.phase is not _SessionPhase.ACTIVE:
        raise InactiveImmediateTransactionError("authorizer requires an active session")
    _require_active_state(state.capability, authority, session=session)
    if state.participant_statement_count != 0:
        raise InvalidImmediateTransactionError(
            "authorizer must be installed before participant execution"
        )
    if state.authorizer_handle is not None:
        raise InvalidImmediateTransactionError(
            "coordinated session already has an authorizer"
        )
    connection = state.connection
    if connection is None:
        raise InactiveImmediateTransactionError("coordinated connection is unavailable")
    connection.set_authorizer(authorizer)
    handle = object.__new__(_TransactionAuthorizerHandle)
    handle_state = _AuthorizerState(
        session_ref=weakref.ref(session),
        authority=authority,
    )
    with _AUTHORIZER_STATES_LOCK:
        _AUTHORIZER_STATES[handle] = handle_state
    state.authorizer_handle = handle
    return handle


def _require_transaction_authorizer(
    handle: _TransactionAuthorizerHandle,
    session: _CoordinatedTransactionSession,
    authority: CampaignDatabaseAuthority,
) -> _TransactionAuthorizerHandle:
    session_state = _require_session_authority(session, authority)
    if session_state.phase is not _SessionPhase.ACTIVE:
        raise InactiveImmediateTransactionError(
            "transaction authorizer session is no longer active"
        )
    _require_active_state(session_state.capability, authority, session=session)
    if type(handle) is not _TransactionAuthorizerHandle:
        raise InvalidImmediateTransactionError(
            "operation requires an issued transaction authorizer handle"
        )
    with _AUTHORIZER_STATES_LOCK:
        state = _AUTHORIZER_STATES.get(handle)
    if state is None:
        raise InvalidImmediateTransactionError(
            "transaction authorizer handle was not issued by this module"
        )
    if not state.active:
        raise InactiveImmediateTransactionError(
            "transaction authorizer handle is no longer active"
        )
    if state.authority is not authority or state.session_ref() is not session:
        raise InvalidImmediateTransactionError(
            "transaction authorizer handle has a different binding"
        )
    return handle


def _first_effective_keyword(sql: str) -> str:
    if type(sql) is not str or not sql.strip():
        raise ParticipantStatementError("SQL must be a nonempty exact str")
    index = 0
    length = len(sql)
    while index < length:
        while index < length and sql[index].isspace():
            index += 1
        if index < length and sql[index] == ";":
            index += 1
            continue
        if sql.startswith("--", index):
            newline = sql.find("\n", index + 2)
            if newline < 0:
                raise ParticipantStatementError("SQL contains no executable statement")
            index = newline + 1
            continue
        if sql.startswith("/*", index):
            end = sql.find("*/", index + 2)
            if end < 0:
                raise ParticipantStatementError("SQL has an unterminated block comment")
            index = end + 2
            continue
        break
    match = _SQL_KEYWORD.match(sql, index)
    if match is None:
        raise ParticipantStatementError("SQL contains no executable statement keyword")
    return match.group(0).upper()


def _validate_participant_statement(sql: str) -> None:
    keyword = _first_effective_keyword(sql)
    if keyword in _TRANSACTION_KEYWORDS:
        raise TransactionControlError(
            f"participant cannot execute transaction control: {keyword}"
        )
    if keyword not in _ALLOWED_STATEMENT_KEYWORDS:
        raise ParticipantStatementError(
            f"participant statement class is forbidden: {keyword}"
        )


def _freeze_description(
    description: Sequence[Sequence[Any]] | None,
) -> tuple[tuple[Any, ...], ...] | None:
    if description is None:
        return None
    return tuple(tuple(column) for column in description)


def _run_participant_cursor(
    capability: ImmediateTransaction,
    authority: CampaignDatabaseAuthority,
    operation: Callable[[sqlite3.Cursor], None],
) -> ImmediateResult:
    capability_state = _require_active_state(capability, authority)
    session = capability_state.session_ref()
    if session is None:
        raise InactiveImmediateTransactionError("coordinated session ended")
    session_state = _require_session_authority(session, authority)
    session_state.participant_statement_count += 1
    connection = capability_state.connection
    if connection is None:
        raise InactiveImmediateTransactionError(
            "ImmediateTransaction connection is no longer available"
        )
    cursor = connection.cursor()
    primary: BaseException | None = None
    traceback: TracebackType | None = None
    rows: tuple[sqlite3.Row, ...] = ()
    rowcount = -1
    lastrowid: int | None = None
    description: tuple[tuple[Any, ...], ...] | None = None
    cleanup_errors: list[BaseException] = []
    try:
        operation(cursor)
        rows = tuple(cursor.fetchall())
        rowcount = cursor.rowcount
        lastrowid = cursor.lastrowid
        description = _freeze_description(cursor.description)
    except BaseException as error:
        primary = error
        traceback = error.__traceback__
    finally:
        try:
            cursor.close()
        except BaseException as cleanup_error:
            cleanup_errors.append(cleanup_error)
    if primary is not None:
        _raise_primary_with_cleanup(primary, traceback, cleanup_errors)
    if cleanup_errors:
        raise SQLiteConnectionCleanupError(
            "participant cursor cleanup failed"
        ) from cleanup_errors[0]
    return ImmediateResult._create(
        capability,
        rows=rows,
        rowcount=rowcount,
        lastrowid=lastrowid,
        description=description,
    )


def _execute_participant(
    transaction: ImmediateTransaction,
    authority: CampaignDatabaseAuthority,
    sql: str,
    parameters: _SqlParameters = (),
) -> ImmediateResult:
    """Private materializing primitive bound to an exact authority/capability."""

    require_active_immediate_transaction(transaction, authority)
    _validate_participant_statement(sql)
    return _run_participant_cursor(
        transaction,
        authority,
        lambda cursor: cursor.execute(sql, parameters),
    )


def _executemany_participant(
    transaction: ImmediateTransaction,
    authority: CampaignDatabaseAuthority,
    sql: str,
    parameter_rows: _SqlParameterRows,
) -> ImmediateResult:
    require_active_immediate_transaction(transaction, authority)
    _validate_participant_statement(sql)
    return _run_participant_cursor(
        transaction,
        authority,
        lambda cursor: cursor.executemany(sql, parameter_rows),
    )


def _lookup_read_snapshot_state(value: object) -> _ReadSnapshotState:
    if type(value) is not _IndependentReadSnapshot:
        raise InvalidImmediateTransactionError(
            "operation requires an issued independent read snapshot"
        )
    with _READ_SNAPSHOT_STATES_LOCK:
        state = _READ_SNAPSHOT_STATES.get(value)
    if state is None:
        raise InvalidImmediateTransactionError(
            "independent read snapshot was not issued by this module"
        )
    return state


def _require_read_snapshot(
    snapshot: _IndependentReadSnapshot,
    authority: CampaignDatabaseAuthority,
) -> _ReadSnapshotState:
    _lookup_authority_state(authority)
    state = _lookup_read_snapshot_state(snapshot)
    if state.authority is not authority:
        raise InvalidImmediateTransactionError(
            "independent read snapshot is bound to another authority"
        )
    _assert_read_snapshot_context_binding(snapshot, state)
    authority_state = _lookup_authority_state(authority)
    _assert_authority_live(authority_state)
    _assert_same_file(
        os.fstat(state.opened_main_fd),
        device=authority_state.device,
        inode=authority_state.inode,
        description="read-snapshot SQLite main FD",
    )
    if state.sqlite_handle is None:
        raise InactiveImmediateTransactionError(
            "independent SQLite handle is no longer available"
        )
    _assert_sqlite_main_not_moved(state.sqlite_handle)
    connection = state.connection
    if connection is None or not connection.in_transaction:
        raise InactiveImmediateTransactionError(
            "independent read snapshot no longer owns its SQLite transaction"
        )
    return state


def _assert_read_snapshot_context_binding(
    snapshot: _IndependentReadSnapshot,
    state: _ReadSnapshotState,
) -> None:
    if state.thread_id != threading.get_ident():
        raise InactiveImmediateTransactionError("read snapshot cannot cross threads")
    if not state.active or _thread_owner() is not snapshot:
        raise InactiveImmediateTransactionError("read snapshot is no longer active")
    _renew_context_binding(
        _ACTIVE_READ_SNAPSHOT,
        state.context_token,
        snapshot,
        install_token=lambda token: setattr(state, "context_token", token),
        description="independent read snapshot",
    )


def _sqlite_connection_is_closed(connection: sqlite3.Connection) -> bool:
    try:
        connection.in_transaction
    except sqlite3.ProgrammingError:
        return True
    return False


def _read_snapshot_resources_closed(
    snapshot: _IndependentReadSnapshot,
    state: _ReadSnapshotState,
) -> bool:
    return (
        not state.active
        and state.context_cleared
        and _thread_owner() is not snapshot
        and _thread_owner() is not _OPENING_READ_SNAPSHOT
        and state.connection is None
        and state.sqlite_handle is None
        and state.opened_main_fd == -1
    )


def _finalize_read_snapshot_state(
    snapshot: _IndependentReadSnapshot,
    state: _ReadSnapshotState,
) -> None:
    """Idempotently release every resource owned by one issued snapshot."""

    cleanup_errors: list[BaseException] = []
    state.active = False
    try:
        if not state.context_cleared:
            try:
                _ACTIVE_READ_SNAPSHOT.reset(state.context_token)
            except BaseException as error:
                cleanup_errors.append(error)
                if _ACTIVE_READ_SNAPSHOT.get() is snapshot:
                    try:
                        _ACTIVE_READ_SNAPSHOT.set(None)
                    except BaseException as fallback_error:
                        cleanup_errors.append(fallback_error)
            finally:
                state.context_cleared = (
                    _ACTIVE_READ_SNAPSHOT.get() is not snapshot
                )
    finally:
        try:
            if (
                _thread_owner() is _OPENING_READ_SNAPSHOT
                or _thread_owner() is snapshot
            ):
                _clear_thread_owner()
        except BaseException as error:
            cleanup_errors.append(error)

    try:
        connection = state.connection
        if connection is None:
            state.sqlite_handle = None
        if connection is not None and _sqlite_connection_is_closed(connection):
            state.connection = None
            state.sqlite_handle = None
            connection = None
        if connection is not None:
            try:
                if connection.in_transaction:
                    connection.rollback()
            except BaseException as error:
                cleanup_errors.append(error)
            finally:
                try:
                    connection.close()
                except BaseException as error:
                    cleanup_errors.append(error)
                    if _sqlite_connection_is_closed(connection):
                        state.connection = None
                        state.sqlite_handle = None
                else:
                    state.connection = None
                    state.sqlite_handle = None
    finally:
        descriptor = state.opened_main_fd
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except BaseException as error:
                cleanup_errors.append(error)
                try:
                    os.fstat(descriptor)
                except OSError as status_error:
                    if status_error.errno == errno.EBADF:
                        state.opened_main_fd = -1
            else:
                state.opened_main_fd = -1

    if cleanup_errors:
        primary = cleanup_errors[0]
        _raise_primary_with_cleanup(primary, primary.__traceback__, cleanup_errors[1:])


@contextmanager
def _independent_authority_read_snapshot_impl(
    authority: CampaignDatabaseAuthority,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
) -> Iterator[_IndependentReadSnapshot]:
    """Open one independent, authority-verified, consistent read snapshot."""

    _lookup_authority_state(authority)
    timeout_ms = _validate_busy_timeout_ms(busy_timeout_ms)
    connection: sqlite3.Connection | None = None
    opened_main_fd: int | None = None
    sqlite_handle: int | None = None
    snapshot: _IndependentReadSnapshot | None = None
    token: contextvars.Token[_IndependentReadSnapshot | None] | None = None
    primary: BaseException | None = None
    traceback: TracebackType | None = None
    cleanup_errors: list[BaseException] = []
    try:
        if (
            _thread_owner() is not None
            or _thread_session_owner() is not None
            or _ACTIVE_TRANSACTION.get() is not None
            or _ACTIVE_COORDINATED_SESSION.get() is not None
            or _ACTIVE_READ_SNAPSHOT.get() is not None
        ):
            raise NestedImmediateTransactionError(
                "independent snapshot cannot nest with another database owner"
            )
        _THREAD_OWNER.active = _OPENING_READ_SNAPSHOT
        connection, opened_main_fd, sqlite_handle = _connect_authority_sqlite(
            authority,
            busy_timeout_ms=timeout_ms,
        )
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        snapshot = object.__new__(_IndependentReadSnapshot)
        _THREAD_OWNER.active = snapshot
        token = _ACTIVE_READ_SNAPSHOT.set(snapshot)
        state = _ReadSnapshotState(
            connection=connection,
            opened_main_fd=opened_main_fd,
            sqlite_handle=sqlite_handle,
            authority=authority,
            thread_id=threading.get_ident(),
            context_token=token,
        )
        with _READ_SNAPSHOT_STATES_LOCK:
            _READ_SNAPSHOT_STATES[snapshot] = state
        # ``BEGIN`` is deferred.  Touch the schema before yielding so the
        # classifier's one read snapshot cannot be chosen after a nested or
        # concurrent durable change.
        connection.execute("SELECT rootpage FROM sqlite_schema LIMIT 1").fetchall()
        yield snapshot
        _require_read_snapshot(snapshot, authority)
    except BaseException as error:
        primary = error
        traceback = error.__traceback__
    finally:
        snapshot_state: _ReadSnapshotState | None = None
        if snapshot is not None:
            with _READ_SNAPSHOT_STATES_LOCK:
                snapshot_state = _READ_SNAPSHOT_STATES.get(snapshot)
        if snapshot is not None and snapshot_state is not None:
            try:
                _finalize_read_snapshot_state(snapshot, snapshot_state)
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
            finally:
                if not _read_snapshot_resources_closed(snapshot, snapshot_state):
                    try:
                        _finalize_read_snapshot_state(snapshot, snapshot_state)
                    except BaseException as recovery_error:
                        cleanup_errors.append(recovery_error)
        else:
            try:
                if token is not None:
                    try:
                        _ACTIVE_READ_SNAPSHOT.reset(token)
                    except BaseException as cleanup_error:
                        cleanup_errors.append(cleanup_error)
                        if _ACTIVE_READ_SNAPSHOT.get() is snapshot:
                            try:
                                _ACTIVE_READ_SNAPSHOT.set(None)
                            except BaseException as fallback_error:
                                cleanup_errors.append(fallback_error)
            finally:
                try:
                    if (
                        _thread_owner() is _OPENING_READ_SNAPSHOT
                        or _thread_owner() is snapshot
                    ):
                        _clear_thread_owner()
                finally:
                    try:
                        if connection is not None and connection.in_transaction:
                            connection.rollback()
                    except BaseException as cleanup_error:
                        cleanup_errors.append(cleanup_error)
                    finally:
                        try:
                            if connection is not None:
                                connection.close()
                        except BaseException as cleanup_error:
                            cleanup_errors.append(cleanup_error)
                        finally:
                            if opened_main_fd is not None:
                                _close_descriptor(opened_main_fd, cleanup_errors)
    if primary is not None:
        _raise_primary_with_cleanup(primary, traceback, cleanup_errors)
    if cleanup_errors:
        first = cleanup_errors[0]
        for following in cleanup_errors[1:]:
            _append_exception_context(first, following)
        raise SQLiteConnectionCleanupError("independent read cleanup failed") from first


class _IndependentReadSnapshotContext:
    """Context wrapper that cannot be consumed from a copied Context."""

    __slots__ = ("_authority", "_entered", "_manager", "_snapshot")

    def __init__(
        self,
        authority: CampaignDatabaseAuthority,
        *,
        busy_timeout_ms: int,
    ) -> None:
        self._authority = authority
        self._entered = False
        self._manager = _independent_authority_read_snapshot_impl(
            authority,
            busy_timeout_ms=busy_timeout_ms,
        )
        self._snapshot: _IndependentReadSnapshot | None = None

    def __enter__(self) -> _IndependentReadSnapshot:
        if self._entered:
            raise InvalidImmediateTransactionError(
                "independent snapshot context cannot be re-entered"
            )
        try:
            snapshot = self._manager.__enter__()
            self._snapshot = snapshot
            self._entered = True
            return snapshot
        except BaseException as primary:
            traceback = primary.__traceback__
            self._snapshot = None
            self._entered = False
            _cleanup_failed_context_entry(self._manager, primary, traceback)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        snapshot = self._snapshot
        if not self._entered or snapshot is None:
            raise InvalidImmediateTransactionError(
                "independent snapshot context is not active"
            )
        try:
            state = _lookup_read_snapshot_state(snapshot)
            _assert_read_snapshot_context_binding(snapshot, state)
        except _ForeignLifecycleContextError:
            raise
        except BaseException as preflight_error:
            preflight_traceback = preflight_error.__traceback__
            try:
                return _exit_after_local_preflight_failure(
                    self._manager,
                    preflight_error,
                    preflight_traceback,
                    exc_type,
                    exc_value,
                    traceback,
                )
            finally:
                self._entered = False
        try:
            return self._manager.__exit__(exc_type, exc_value, traceback)
        finally:
            self._entered = False


def _independent_authority_read_snapshot(
    authority: CampaignDatabaseAuthority,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
) -> _IndependentReadSnapshotContext:
    return _IndependentReadSnapshotContext(
        authority,
        busy_timeout_ms=busy_timeout_ms,
    )


def _execute_read_snapshot(
    snapshot: _IndependentReadSnapshot,
    authority: CampaignDatabaseAuthority,
    sql: str,
    parameters: _SqlParameters = (),
) -> tuple[sqlite3.Row, ...]:
    state = _require_read_snapshot(snapshot, authority)
    keyword = _first_effective_keyword(sql)
    if keyword not in _READ_STATEMENT_KEYWORDS:
        raise ParticipantStatementError(
            f"independent snapshot permits read statements only: {keyword}"
        )
    connection = state.connection
    if connection is None:
        raise InactiveImmediateTransactionError(
            "independent read connection is no longer available"
        )
    cursor = connection.cursor()
    primary: BaseException | None = None
    traceback: TracebackType | None = None
    rows: tuple[sqlite3.Row, ...] = ()
    cleanup_errors: list[BaseException] = []
    try:
        cursor.execute(sql, parameters)
        rows = tuple(cursor.fetchall())
    except BaseException as error:
        primary = error
        traceback = error.__traceback__
    finally:
        try:
            cursor.close()
        except BaseException as cleanup_error:
            cleanup_errors.append(cleanup_error)
    if primary is not None:
        _raise_primary_with_cleanup(primary, traceback, cleanup_errors)
    if cleanup_errors:
        raise SQLiteConnectionCleanupError("read cursor cleanup failed") from cleanup_errors[0]
    _require_read_snapshot(snapshot, authority)
    return rows


def _cleanup_failed_context_entry(
    manager: Any,
    primary: BaseException,
    traceback: TracebackType | None,
) -> None:
    cleanup_errors: list[BaseException] = []
    try:
        manager.__exit__(type(primary), primary, traceback)
    except BaseException as cleanup_error:
        if cleanup_error is not primary:
            cleanup_errors.append(cleanup_error)
    _raise_primary_with_cleanup(primary, traceback, cleanup_errors)


def _exit_after_local_preflight_failure(
    manager: Any,
    preflight_error: BaseException,
    preflight_traceback: TracebackType | None,
    exc_type: type[BaseException] | None,
    exc_value: BaseException | None,
    traceback: TracebackType | None,
) -> bool | None:
    forwarded_type = exc_type
    forwarded_value = exc_value
    forwarded_traceback = traceback
    if forwarded_value is None:
        forwarded_type = type(preflight_error)
        forwarded_value = preflight_error
        forwarded_traceback = preflight_traceback
    try:
        result = manager.__exit__(
            forwarded_type,
            forwarded_value,
            forwarded_traceback,
        )
    except BaseException as lifecycle_error:
        if lifecycle_error is not preflight_error:
            _append_exception_context(lifecycle_error, preflight_error)
        raise
    if exc_value is not None:
        _append_exception_context(exc_value, preflight_error)
        return result
    raise preflight_error.with_traceback(preflight_traceback)


@contextmanager
def _immediate_transaction_impl(
    authority: CampaignDatabaseAuthority,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
) -> Iterator[ImmediateTransaction]:
    """Convenience wrapper over the private coordinated-session lifecycle."""

    session: _CoordinatedTransactionSession | None = None
    primary: BaseException | None = None
    traceback: TracebackType | None = None
    primary_context: BaseException | None = None
    cleanup_errors: list[BaseException] = []
    try:
        session = _open_coordinated_transaction_session(
            authority,
            busy_timeout_ms=busy_timeout_ms,
        )
        transaction = _coordinated_transaction(session, authority)
        yield transaction
        require_active_immediate_transaction(transaction, authority)
        _commit_coordinated_transaction(session, authority)
    except BaseException as error:
        primary = error
        traceback = error.__traceback__
        primary_context = error.__context__
    finally:
        if session is not None:
            try:
                _finalize_context_session(
                    session,
                    authority,
                    rollback_if_active=primary is not None,
                )
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
            finally:
                # A trace/signal can interrupt dispatch before the first call
                # reaches its phase checks.  Reconcile only when resources are
                # still live; completed sessions are never touched twice.
                try:
                    state = _require_session_authority(session, authority)
                    if not _session_resources_closed(session, state):
                        _finalize_context_session(
                            session,
                            authority,
                            rollback_if_active=primary is not None,
                        )
                except BaseException as cleanup_error:
                    cleanup_errors.append(cleanup_error)
    if primary is not None:
        primary.__context__ = primary_context
        _raise_primary_with_cleanup(primary, traceback, cleanup_errors)
    if cleanup_errors:
        first = cleanup_errors[0]
        for following in cleanup_errors[1:]:
            _append_exception_context(first, following)
        raise SQLiteConnectionCleanupError(
            "SQLite transaction cleanup failed after successful commit"
        ) from first


class _ImmediateTransactionContext:
    """Context wrapper that preserves the entering Context on wrong exit."""

    __slots__ = ("_authority", "_entered", "_manager", "_session")

    def __init__(
        self,
        authority: CampaignDatabaseAuthority,
        *,
        busy_timeout_ms: int,
    ) -> None:
        self._authority = authority
        self._entered = False
        self._manager = _immediate_transaction_impl(
            authority,
            busy_timeout_ms=busy_timeout_ms,
        )
        self._session: _CoordinatedTransactionSession | None = None

    def __enter__(self) -> ImmediateTransaction:
        if self._entered:
            raise InvalidImmediateTransactionError(
                "immediate transaction context cannot be re-entered"
            )
        try:
            transaction = self._manager.__enter__()
            capability_state = _lookup_capability_state(transaction)
            session = capability_state.session_ref()
            if session is None:
                raise InactiveImmediateTransactionError(
                    "coordinated session disappeared during context entry"
                )
            self._session = session
            self._entered = True
            return transaction
        except BaseException as primary:
            traceback = primary.__traceback__
            self._session = None
            self._entered = False
            _cleanup_failed_context_entry(self._manager, primary, traceback)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        session = self._session
        if not self._entered or session is None:
            raise InvalidImmediateTransactionError(
                "immediate transaction context is not active"
            )
        try:
            state = _require_session_authority(session, self._authority)
            _assert_session_thread_binding(
                session,
                state,
                require_active_context=True,
            )
        except _ForeignLifecycleContextError:
            raise
        except BaseException as preflight_error:
            preflight_traceback = preflight_error.__traceback__
            try:
                return _exit_after_local_preflight_failure(
                    self._manager,
                    preflight_error,
                    preflight_traceback,
                    exc_type,
                    exc_value,
                    traceback,
                )
            finally:
                self._entered = False
        try:
            return self._manager.__exit__(exc_type, exc_value, traceback)
        finally:
            self._entered = False


def immediate_transaction(
    authority: CampaignDatabaseAuthority,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
) -> _ImmediateTransactionContext:
    return _ImmediateTransactionContext(
        authority,
        busy_timeout_ms=busy_timeout_ms,
    )
