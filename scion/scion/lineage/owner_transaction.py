"""Sealed Branch/H write permits and durable owner receipt ledgers.

This module is the narrow policy layer between the generic SQLite transaction
foundation and the focused Branch/H stores.  It owns no store SQL, row
decoding, Campaign registry state, schema, lease policy, or transaction commit
lifecycle.  A coordinated transaction attaches exactly one ledger; owner-table
DML is then denied by default and can run only through a one-call store-bound
permit.  Every attempted permitted write is recorded before SQLite execution,
and every successful one-row write must issue and consume one sealed receipt
before pre-commit closure can succeed.

The module is intentionally dormant.  Future focused stores are the only
production importers of the private write/issuance functions, while the future
CampaignOwnerRegistry is the only production importer of ledger attachment,
receipt consumption, and closure.
"""

from __future__ import annotations

import enum
import sqlite3
import threading
import weakref
from dataclasses import dataclass, field
from typing import Any, Final, Mapping, Sequence

import scion.lineage.sqlite_connection as _sqlite
from scion.lineage.durable_owner import (
    RevisionedBranchRecord,
    RevisionedHypothesisRecord,
)

__all__ = (
    "InvalidOwnerReceiptError",
    "InactiveOwnerTransactionError",
    "OwnerCreationReceipt",
    "OwnerMutationReceipt",
    "OwnerReceiptClosureError",
    "OwnerTransactionError",
    "OwnerWriteProtocolError",
    "SemanticCreationOutcomeWitness",
)

_SqlParameters = Sequence[Any] | Mapping[str, Any]
_OwnerToken = RevisionedBranchRecord | RevisionedHypothesisRecord


class OwnerTransactionError(RuntimeError):
    """Base error for the dormant owner-table transaction protocol."""


class InvalidOwnerReceiptError(TypeError, OwnerTransactionError):
    """A permit, ledger, write fact, store binding, or receipt is forged."""


class InactiveOwnerTransactionError(OwnerTransactionError):
    """An owner ledger or receipt is no longer usable in this transaction."""


class OwnerWriteProtocolError(OwnerTransactionError):
    """A focused owner write violated its exact permit or receipt contract."""


class OwnerReceiptClosureError(OwnerTransactionError):
    """Issued, consumed, staged, and durable-write receipt sets differ."""


class _OwnerKind(enum.Enum):
    BRANCH = "branch"
    HYPOTHESIS = "hypothesis"


_OWNER_TABLES: Final[dict[str, _OwnerKind]] = {
    "branches": _OwnerKind.BRANCH,
    "hypotheses": _OwnerKind.HYPOTHESIS,
}


class _OwnerAction(enum.Enum):
    INSERT = sqlite3.SQLITE_INSERT
    UPDATE = sqlite3.SQLITE_UPDATE


class _LedgerPhase(enum.Enum):
    OPEN = enum.auto()
    SEALED = enum.auto()
    CLOSED = enum.auto()


class _CreationAuthorizationPhase(enum.Enum):
    ISSUED = enum.auto()
    WRITE_BOUND = enum.auto()
    COMPLETED = enum.auto()


class _OwnerStoreAuthority:
    """Sealed binding between one focused store kind and database authority."""

    __slots__ = ("__weakref__",)

    def __new__(cls, *_args: object, **_kwargs: object) -> "_OwnerStoreAuthority":
        raise InvalidOwnerReceiptError(
            "owner store authorities are issued only by owner_transaction"
        )

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("owner store authority is sealed")


class _OwnerCreationAuthorizerAuthority:
    """Sealed identity of one semantic owner-creation participant."""

    __slots__ = ("__weakref__",)

    def __new__(
        cls, *_args: object, **_kwargs: object
    ) -> "_OwnerCreationAuthorizerAuthority":
        raise InvalidOwnerReceiptError(
            "owner creation authorizers are issued only by owner_transaction"
        )

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("owner creation authorizer authority is sealed")

    def __copy__(self) -> "_OwnerCreationAuthorizerAuthority":
        raise InvalidOwnerReceiptError(
            "owner creation authorizer authority cannot be copied"
        )

    def __deepcopy__(
        self, _memo: dict[int, object]
    ) -> "_OwnerCreationAuthorizerAuthority":
        raise InvalidOwnerReceiptError(
            "owner creation authorizer authority cannot be copied"
        )

    def __reduce_ex__(self, _protocol: int) -> object:
        raise InvalidOwnerReceiptError(
            "owner creation authorizer authority cannot be pickled"
        )


class _OwnerCreationAuthorization:
    """One-shot transaction-bound authority for an exact revision-zero row."""

    __slots__ = ("__weakref__",)

    def __new__(
        cls, *_args: object, **_kwargs: object
    ) -> "_OwnerCreationAuthorization":
        raise InvalidOwnerReceiptError(
            "owner creation authorizations are issued only by owner_transaction"
        )

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("owner creation authorization is sealed")

    def __copy__(self) -> "_OwnerCreationAuthorization":
        raise InvalidOwnerReceiptError("owner creation authorization cannot be copied")

    def __deepcopy__(self, _memo: dict[int, object]) -> "_OwnerCreationAuthorization":
        raise InvalidOwnerReceiptError("owner creation authorization cannot be copied")

    def __reduce_ex__(self, _protocol: int) -> object:
        raise InvalidOwnerReceiptError("owner creation authorization cannot be pickled")


class _OwnerReceiptLedger:
    """Opaque Branch/H mutation ledger attached to one coordinated session."""

    __slots__ = ("__weakref__",)

    def __new__(cls, *_args: object, **_kwargs: object) -> "_OwnerReceiptLedger":
        raise InvalidOwnerReceiptError(
            "owner receipt ledgers are attached only by owner_transaction"
        )

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("owner receipt ledger is sealed")


class _OwnerWriteFact:
    """Opaque preallocated evidence for one exact permitted execute call."""

    __slots__ = ("__weakref__",)

    def __new__(cls, *_args: object, **_kwargs: object) -> "_OwnerWriteFact":
        raise InvalidOwnerReceiptError(
            "owner write facts are issued only by owner_transaction"
        )

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("owner write fact is sealed")


class OwnerMutationReceipt:
    """Opaque proof of one exact same-transaction Branch/H CAS."""

    __slots__ = ("__weakref__",)

    def __new__(cls, *_args: object, **_kwargs: object) -> "OwnerMutationReceipt":
        raise InvalidOwnerReceiptError(
            "OwnerMutationReceipt is issued only after a focused owner CAS"
        )

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("OwnerMutationReceipt is sealed")

    def __copy__(self) -> "OwnerMutationReceipt":
        raise InvalidOwnerReceiptError("OwnerMutationReceipt cannot be copied")

    def __deepcopy__(self, _memo: dict[int, object]) -> "OwnerMutationReceipt":
        raise InvalidOwnerReceiptError("OwnerMutationReceipt cannot be copied")

    def __reduce_ex__(self, _protocol: int) -> object:
        raise InvalidOwnerReceiptError("OwnerMutationReceipt cannot be pickled")


class OwnerCreationReceipt:
    """Opaque proof of one exact same-transaction Branch/H insert-once."""

    __slots__ = ("__weakref__",)

    def __new__(cls, *_args: object, **_kwargs: object) -> "OwnerCreationReceipt":
        raise InvalidOwnerReceiptError(
            "OwnerCreationReceipt is issued only after a focused owner insert"
        )

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("OwnerCreationReceipt is sealed")

    def __copy__(self) -> "OwnerCreationReceipt":
        raise InvalidOwnerReceiptError("OwnerCreationReceipt cannot be copied")

    def __deepcopy__(self, _memo: dict[int, object]) -> "OwnerCreationReceipt":
        raise InvalidOwnerReceiptError("OwnerCreationReceipt cannot be copied")

    def __reduce_ex__(self, _protocol: int) -> object:
        raise InvalidOwnerReceiptError("OwnerCreationReceipt cannot be pickled")


class SemanticCreationOutcomeWitness:
    """Opaque participant-signed identity for exact semantic creation facts."""

    __slots__ = ("__weakref__",)

    def __new__(
        cls, *_args: object, **_kwargs: object
    ) -> "SemanticCreationOutcomeWitness":
        raise InvalidOwnerReceiptError(
            "SemanticCreationOutcomeWitness is issued only by owner_transaction"
        )

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("SemanticCreationOutcomeWitness is sealed")

    def __copy__(self) -> "SemanticCreationOutcomeWitness":
        raise InvalidOwnerReceiptError(
            "SemanticCreationOutcomeWitness cannot be copied"
        )

    def __deepcopy__(
        self, _memo: dict[int, object]
    ) -> "SemanticCreationOutcomeWitness":
        raise InvalidOwnerReceiptError(
            "SemanticCreationOutcomeWitness cannot be copied"
        )

    def __reduce_ex__(self, _protocol: int) -> object:
        raise InvalidOwnerReceiptError(
            "SemanticCreationOutcomeWitness cannot be pickled"
        )


@dataclass(frozen=True, slots=True)
class _OwnerReceiptWitness:
    """Internal detached facts consumed by future Registry staging."""

    owner_kind: _OwnerKind
    owner_id: str
    expected_token: _OwnerToken | None
    committed_token: _OwnerToken
    creation_authorization: _OwnerCreationAuthorization | None


@dataclass(frozen=True, slots=True)
class _StoreAuthorityState:
    database_authority: _sqlite.CampaignDatabaseAuthority
    owner_kind: _OwnerKind


@dataclass(frozen=True, slots=True)
class _CreationAuthorizerAuthorityState:
    database_authority: _sqlite.CampaignDatabaseAuthority
    owner_kind: _OwnerKind


@dataclass(slots=True)
class _CreationAuthorizationState:
    authorizer_authority: _OwnerCreationAuthorizerAuthority
    ledger_ref: weakref.ReferenceType[_OwnerReceiptLedger]
    transaction: _sqlite.ImmediateTransaction
    database_authority: _sqlite.CampaignDatabaseAuthority
    owner_kind: _OwnerKind
    owner_id: str
    target_payload_sha256: str
    phase: _CreationAuthorizationPhase = _CreationAuthorizationPhase.ISSUED
    write_fact: _OwnerWriteFact | None = None
    semantic_outcome_witness: SemanticCreationOutcomeWitness | None = None


@dataclass(frozen=True, slots=True)
class _SemanticCreationOutcomeWitnessState:
    authorizer_authority: _OwnerCreationAuthorizerAuthority
    authorization_ref: weakref.ReferenceType[_OwnerCreationAuthorization]
    ledger_ref: weakref.ReferenceType[_OwnerReceiptLedger]
    transaction: _sqlite.ImmediateTransaction
    database_authority: _sqlite.CampaignDatabaseAuthority
    owner_kind: _OwnerKind


@dataclass(slots=True)
class _PermitState:
    owner_kind: _OwnerKind
    action: _OwnerAction
    executing: bool = False
    authorizer_event_seen: bool = False


@dataclass(slots=True)
class _WriteFactState:
    owner_kind: _OwnerKind
    action: _OwnerAction
    owner_id: str
    expected_token: _OwnerToken | None
    target_payload_sha256: str | None
    creation_authorization: _OwnerCreationAuthorization | None
    completed: bool = False
    rowcount: int | None = None
    receipt: OwnerMutationReceipt | OwnerCreationReceipt | None = None


@dataclass(frozen=True, slots=True)
class _ReceiptState:
    ledger_ref: weakref.ReferenceType[_OwnerReceiptLedger]
    witness: _OwnerReceiptWitness


@dataclass(slots=True)
class _LedgerState:
    database_authority: _sqlite.CampaignDatabaseAuthority
    transaction: _sqlite.ImmediateTransaction
    thread_id: int
    phase: _LedgerPhase = _LedgerPhase.OPEN
    authorizer_handle: _sqlite._TransactionAuthorizerHandle | None = None
    active_permit: _PermitState | None = None
    pending_write: _OwnerWriteFact | None = None
    writes: dict[_OwnerWriteFact, _WriteFactState] = field(default_factory=dict)
    creation_authorizations: dict[
        _OwnerCreationAuthorization,
        _CreationAuthorizationState,
    ] = field(default_factory=dict)
    receipts: dict[
        OwnerMutationReceipt | OwnerCreationReceipt,
        _OwnerWriteFact,
    ] = field(default_factory=dict)
    consumed: set[OwnerMutationReceipt | OwnerCreationReceipt] = field(
        default_factory=set
    )


_STORE_AUTHORITY_STATES: weakref.WeakKeyDictionary[
    _OwnerStoreAuthority, _StoreAuthorityState
] = weakref.WeakKeyDictionary()
_STORE_AUTHORITY_STATES_LOCK = threading.RLock()
_CREATION_AUTHORIZER_AUTHORITY_STATES: weakref.WeakKeyDictionary[
    _OwnerCreationAuthorizerAuthority,
    _CreationAuthorizerAuthorityState,
] = weakref.WeakKeyDictionary()
_CREATION_AUTHORIZER_AUTHORITY_STATES_LOCK = threading.RLock()
_CREATION_AUTHORIZATION_STATES: weakref.WeakKeyDictionary[
    _OwnerCreationAuthorization,
    _CreationAuthorizationState,
] = weakref.WeakKeyDictionary()
_CREATION_AUTHORIZATION_STATES_LOCK = threading.RLock()
_SEMANTIC_CREATION_OUTCOME_WITNESS_STATES: weakref.WeakKeyDictionary[
    SemanticCreationOutcomeWitness,
    _SemanticCreationOutcomeWitnessState,
] = weakref.WeakKeyDictionary()
_SEMANTIC_CREATION_OUTCOME_WITNESS_STATES_LOCK = threading.RLock()
_LEDGER_STATES: weakref.WeakKeyDictionary[_OwnerReceiptLedger, _LedgerState] = (
    weakref.WeakKeyDictionary()
)
_TRANSACTION_LEDGERS: weakref.WeakKeyDictionary[
    _sqlite.ImmediateTransaction,
    weakref.ReferenceType[_OwnerReceiptLedger],
] = weakref.WeakKeyDictionary()
_LEDGER_STATES_LOCK = threading.RLock()
_RECEIPT_STATES: weakref.WeakKeyDictionary[
    OwnerMutationReceipt | OwnerCreationReceipt, _ReceiptState
] = weakref.WeakKeyDictionary()
_RECEIPT_STATES_LOCK = threading.RLock()


def _lookup_store_authority(value: object) -> _StoreAuthorityState:
    if type(value) is not _OwnerStoreAuthority:
        raise InvalidOwnerReceiptError(
            "operation requires an issued owner store authority"
        )
    with _STORE_AUTHORITY_STATES_LOCK:
        state = _STORE_AUTHORITY_STATES.get(value)
    if state is None:
        raise InvalidOwnerReceiptError("owner store authority was not issued")
    return state


def _issue_store_authority(
    database_authority: _sqlite.CampaignDatabaseAuthority,
    owner_kind: _OwnerKind,
) -> _OwnerStoreAuthority:
    _sqlite._lookup_authority_state(database_authority)
    value = object.__new__(_OwnerStoreAuthority)
    with _STORE_AUTHORITY_STATES_LOCK:
        _STORE_AUTHORITY_STATES[value] = _StoreAuthorityState(
            database_authority=database_authority,
            owner_kind=owner_kind,
        )
    return value


def _issue_branch_store_authority(
    database_authority: _sqlite.CampaignDatabaseAuthority,
) -> _OwnerStoreAuthority:
    """Private production issuer imported only by the focused Branch store."""

    return _issue_store_authority(database_authority, _OwnerKind.BRANCH)


def _issue_hypothesis_store_authority(
    database_authority: _sqlite.CampaignDatabaseAuthority,
) -> _OwnerStoreAuthority:
    """Private production issuer imported only by the focused H store."""

    return _issue_store_authority(database_authority, _OwnerKind.HYPOTHESIS)


def _lookup_creation_authorizer_authority(
    value: object,
) -> _CreationAuthorizerAuthorityState:
    if type(value) is not _OwnerCreationAuthorizerAuthority:
        raise InvalidOwnerReceiptError(
            "operation requires an issued owner creation authorizer authority"
        )
    with _CREATION_AUTHORIZER_AUTHORITY_STATES_LOCK:
        state = _CREATION_AUTHORIZER_AUTHORITY_STATES.get(value)
    if state is None:
        raise InvalidOwnerReceiptError(
            "owner creation authorizer authority was not issued"
        )
    return state


def _issue_creation_authorizer_authority(
    database_authority: _sqlite.CampaignDatabaseAuthority,
    owner_kind: _OwnerKind,
) -> _OwnerCreationAuthorizerAuthority:
    _sqlite._lookup_authority_state(database_authority)
    value = object.__new__(_OwnerCreationAuthorizerAuthority)
    with _CREATION_AUTHORIZER_AUTHORITY_STATES_LOCK:
        _CREATION_AUTHORIZER_AUTHORITY_STATES[value] = (
            _CreationAuthorizerAuthorityState(
                database_authority=database_authority,
                owner_kind=owner_kind,
            )
        )
    return value


def _issue_branch_creation_authorizer_authority(
    database_authority: _sqlite.CampaignDatabaseAuthority,
) -> _OwnerCreationAuthorizerAuthority:
    """Private issuer for the Branch-kind semantic participant."""

    return _issue_creation_authorizer_authority(
        database_authority,
        _OwnerKind.BRANCH,
    )


def _issue_hypothesis_creation_authorizer_authority(
    database_authority: _sqlite.CampaignDatabaseAuthority,
) -> _OwnerCreationAuthorizerAuthority:
    """Private issuer for the hypothesis-kind semantic participant."""

    return _issue_creation_authorizer_authority(
        database_authority,
        _OwnerKind.HYPOTHESIS,
    )


def _lookup_ledger(value: object) -> _LedgerState:
    if type(value) is not _OwnerReceiptLedger:
        raise InvalidOwnerReceiptError(
            "operation requires an attached owner receipt ledger"
        )
    with _LEDGER_STATES_LOCK:
        state = _LEDGER_STATES.get(value)
    if state is None:
        raise InvalidOwnerReceiptError("owner receipt ledger was not attached")
    return state


def _require_open_ledger(
    ledger: _OwnerReceiptLedger,
    database_authority: _sqlite.CampaignDatabaseAuthority,
) -> _LedgerState:
    state = _lookup_ledger(ledger)
    if state.database_authority is not database_authority:
        raise InvalidOwnerReceiptError(
            "owner receipt ledger is bound to another database authority"
        )
    if state.phase is not _LedgerPhase.OPEN:
        raise InactiveOwnerTransactionError("owner receipt ledger is not open")
    if state.thread_id != threading.get_ident():
        raise InactiveOwnerTransactionError(
            "owner receipt ledger cannot cross its issuing thread"
        )
    _sqlite.require_active_immediate_transaction(
        state.transaction,
        database_authority,
    )
    handle = state.authorizer_handle
    if handle is None:
        raise InvalidOwnerReceiptError("owner write authorizer was not installed")
    _sqlite._require_transaction_authorizer_for_transaction(
        handle,
        state.transaction,
        database_authority,
    )
    return state


def _require_owner_ledger_transaction_binding(
    transaction: _sqlite.ImmediateTransaction,
    ledger: _OwnerReceiptLedger,
    database_authority: _sqlite.CampaignDatabaseAuthority,
) -> _LedgerState:
    """Prove a participant's strict-read capability is this ledger's session."""

    state = _require_open_ledger(ledger, database_authority)
    if state.transaction is not transaction:
        raise InvalidOwnerReceiptError(
            "owner receipt ledger belongs to another transaction"
        )
    _sqlite.require_active_immediate_transaction(transaction, database_authority)
    return state


def _authorize_owner_table_action(
    ledger_ref: weakref.ReferenceType[_OwnerReceiptLedger],
    action: int,
    table_name: str | None,
    _column_name: str | None,
    database_name: str | None,
    trigger_name: str | None,
) -> int:
    """Deny owner DML without a permit and COMMIT without sealed closure."""

    try:
        ledger = ledger_ref()
        if action == sqlite3.SQLITE_TRANSACTION:
            transaction_action = table_name.upper() if type(table_name) is str else ""
            if transaction_action != "COMMIT":
                return sqlite3.SQLITE_OK
            if ledger is None:
                return sqlite3.SQLITE_DENY
            with _LEDGER_STATES_LOCK:
                state = _LEDGER_STATES.get(ledger)
                if (
                    state is None
                    or state.phase is not _LedgerPhase.SEALED
                    or state.thread_id != threading.get_ident()
                ):
                    return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        normalized_table = table_name.casefold() if type(table_name) is str else None
        owner_kind = _OWNER_TABLES.get(normalized_table or "")
        if owner_kind is None:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_DELETE:
            return sqlite3.SQLITE_DENY
        if action not in {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE}:
            return sqlite3.SQLITE_OK
        if ledger is None:
            return sqlite3.SQLITE_DENY
        with _LEDGER_STATES_LOCK:
            state = _LEDGER_STATES.get(ledger)
            if state is None or state.phase is not _LedgerPhase.OPEN:
                return sqlite3.SQLITE_DENY
            permit = state.active_permit
            if (
                permit is None
                or not permit.executing
                or permit.owner_kind is not owner_kind
                or permit.action.value != action
                or database_name != "main"
                or trigger_name is not None
                or state.thread_id != threading.get_ident()
            ):
                return sqlite3.SQLITE_DENY
            permit.authorizer_event_seen = True
            return sqlite3.SQLITE_OK
    except BaseException:
        return sqlite3.SQLITE_DENY


def _attach_owner_receipt_ledger(
    transaction: _sqlite.ImmediateTransaction,
    database_authority: _sqlite.CampaignDatabaseAuthority,
) -> _OwnerReceiptLedger:
    """Attach default-deny owner policy before any participant statement."""

    _sqlite.require_active_immediate_transaction(
        transaction,
        database_authority,
    )
    ledger = object.__new__(_OwnerReceiptLedger)
    state = _LedgerState(
        database_authority=database_authority,
        transaction=transaction,
        thread_id=threading.get_ident(),
    )
    with _LEDGER_STATES_LOCK:
        prior_ref = _TRANSACTION_LEDGERS.get(transaction)
        if prior_ref is not None and prior_ref() is not None:
            raise OwnerWriteProtocolError(
                "an owner receipt ledger is already attached to this transaction"
            )
        _LEDGER_STATES[ledger] = state
        _TRANSACTION_LEDGERS[transaction] = weakref.ref(ledger)
    ledger_ref = weakref.ref(ledger)
    try:
        state.authorizer_handle = (
            _sqlite._install_transaction_authorizer_for_transaction(
                transaction,
                database_authority,
                lambda action, table, column, database, trigger: (
                    _authorize_owner_table_action(
                        ledger_ref,
                        action,
                        table,
                        column,
                        database,
                        trigger,
                    )
                ),
            )
        )
    except BaseException:
        state.phase = _LedgerPhase.CLOSED
        state.active_permit = None
        with _LEDGER_STATES_LOCK:
            attached_ref = _TRANSACTION_LEDGERS.get(transaction)
            if attached_ref is not None and attached_ref() is ledger:
                _TRANSACTION_LEDGERS.pop(transaction, None)
        raise
    return ledger


def _validate_store_binding(
    store_authority: _OwnerStoreAuthority,
    ledger_state: _LedgerState,
    owner_kind: _OwnerKind,
) -> None:
    store_state = _lookup_store_authority(store_authority)
    if store_state.database_authority is not ledger_state.database_authority:
        raise InvalidOwnerReceiptError(
            "owner store and receipt ledger use different database authorities"
        )
    if store_state.owner_kind is not owner_kind:
        raise InvalidOwnerReceiptError("owner store authority has another owner kind")


def _require_store_ledger(
    transaction: _sqlite.ImmediateTransaction,
    store_authority: _OwnerStoreAuthority,
    owner_kind: _OwnerKind,
) -> _OwnerReceiptLedger:
    """Resolve the exact Registry-attached ledger for one focused store."""

    store_state = _lookup_store_authority(store_authority)
    if store_state.owner_kind is not owner_kind:
        raise InvalidOwnerReceiptError("owner store authority has another owner kind")
    _sqlite.require_active_immediate_transaction(
        transaction,
        store_state.database_authority,
    )
    with _LEDGER_STATES_LOCK:
        ledger_ref = _TRANSACTION_LEDGERS.get(transaction)
        ledger = None if ledger_ref is None else ledger_ref()
    if ledger is None:
        raise InvalidOwnerReceiptError(
            "focused owner store requires the transaction's attached ledger"
        )
    state = _require_open_ledger(ledger, store_state.database_authority)
    if state.transaction is not transaction:
        raise InvalidOwnerReceiptError(
            "owner receipt ledger belongs to another transaction"
        )
    _validate_store_binding(store_authority, state, owner_kind)
    return ledger


def _require_branch_store_ledger(
    transaction: _sqlite.ImmediateTransaction,
    store_authority: _OwnerStoreAuthority,
) -> _OwnerReceiptLedger:
    return _require_store_ledger(transaction, store_authority, _OwnerKind.BRANCH)


def _require_hypothesis_store_ledger(
    transaction: _sqlite.ImmediateTransaction,
    store_authority: _OwnerStoreAuthority,
) -> _OwnerReceiptLedger:
    return _require_store_ledger(
        transaction,
        store_authority,
        _OwnerKind.HYPOTHESIS,
    )


def _validate_payload_sha256(value: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise OwnerWriteProtocolError(
            "target payload SHA-256 must be 64 lowercase hexadecimal characters"
        )
    return value


def _lookup_creation_authorization(
    value: object,
) -> _CreationAuthorizationState:
    if type(value) is not _OwnerCreationAuthorization:
        raise InvalidOwnerReceiptError(
            "operation requires an issued owner creation authorization"
        )
    with _CREATION_AUTHORIZATION_STATES_LOCK:
        state = _CREATION_AUTHORIZATION_STATES.get(value)
    if state is None:
        raise InvalidOwnerReceiptError("owner creation authorization was not issued")
    return state


def _require_registered_creation_authorization(
    ledger: _OwnerReceiptLedger,
    authorization: _OwnerCreationAuthorization,
    *,
    owner_kind: _OwnerKind,
    authorizer_authority: _OwnerCreationAuthorizerAuthority | None = None,
) -> tuple[_LedgerState, _CreationAuthorizationState]:
    authorization_state = _lookup_creation_authorization(authorization)
    ledger_state = _require_open_ledger(
        ledger,
        authorization_state.database_authority,
    )
    if authorization_state.ledger_ref() is not ledger:
        raise InvalidOwnerReceiptError(
            "owner creation authorization belongs to another receipt ledger"
        )
    if authorization_state.transaction is not ledger_state.transaction:
        raise InvalidOwnerReceiptError(
            "owner creation authorization belongs to another transaction"
        )
    if authorization_state.owner_kind is not owner_kind:
        raise InvalidOwnerReceiptError(
            "owner creation authorization has another owner kind"
        )
    registered_state = ledger_state.creation_authorizations.get(authorization)
    if registered_state is not authorization_state:
        raise InvalidOwnerReceiptError(
            "owner creation authorization is not registered in this ledger"
        )
    issued_authorizer_state = _lookup_creation_authorizer_authority(
        authorization_state.authorizer_authority
    )
    if (
        issued_authorizer_state.database_authority
        is not authorization_state.database_authority
        or issued_authorizer_state.owner_kind is not owner_kind
    ):
        raise InvalidOwnerReceiptError(
            "owner creation authorization has a malformed authorizer binding"
        )
    if authorizer_authority is not None:
        provided_authorizer_state = _lookup_creation_authorizer_authority(
            authorizer_authority
        )
        if (
            authorization_state.authorizer_authority is not authorizer_authority
            or provided_authorizer_state.database_authority
            is not authorization_state.database_authority
            or provided_authorizer_state.owner_kind is not owner_kind
        ):
            raise InvalidOwnerReceiptError(
                "another semantic authorizer issued this creation authorization"
            )
    return ledger_state, authorization_state


def _register_creation_authorization(
    authorizer_authority: _OwnerCreationAuthorizerAuthority,
    transaction: _sqlite.ImmediateTransaction,
    ledger: _OwnerReceiptLedger,
    owner_id: str,
    target_payload_sha256: str,
    *,
    owner_kind: _OwnerKind,
) -> _OwnerCreationAuthorization:
    authorizer_state = _lookup_creation_authorizer_authority(authorizer_authority)
    if authorizer_state.owner_kind is not owner_kind:
        raise InvalidOwnerReceiptError(
            "owner creation authorizer has another owner kind"
        )
    ledger_state = _require_owner_ledger_transaction_binding(
        transaction,
        ledger,
        authorizer_state.database_authority,
    )
    owner = _validate_exact_owner_id(owner_id)
    target_digest = _validate_payload_sha256(target_payload_sha256)
    if any(
        prior.owner_kind is owner_kind and prior.owner_id == owner
        for prior in ledger_state.creation_authorizations.values()
    ):
        raise OwnerWriteProtocolError(
            "one owner ID cannot receive two creation authorizations"
        )

    authorization = object.__new__(_OwnerCreationAuthorization)
    authorization_state = _CreationAuthorizationState(
        authorizer_authority=authorizer_authority,
        ledger_ref=weakref.ref(ledger),
        transaction=ledger_state.transaction,
        database_authority=ledger_state.database_authority,
        owner_kind=owner_kind,
        owner_id=owner,
        target_payload_sha256=target_digest,
    )
    # Registration is deliberately one-way.  Once the ledger owns the
    # capability, interruption or participant failure leaves an extra ISSUED
    # authorization and therefore prevents pre-commit closure.
    with _CREATION_AUTHORIZATION_STATES_LOCK:
        _CREATION_AUTHORIZATION_STATES[authorization] = authorization_state
    ledger_state.creation_authorizations[authorization] = authorization_state
    return authorization


def _register_branch_creation_authorization(
    authorizer_authority: _OwnerCreationAuthorizerAuthority,
    transaction: _sqlite.ImmediateTransaction,
    ledger: _OwnerReceiptLedger,
    owner_id: str,
    target_payload_sha256: str,
) -> _OwnerCreationAuthorization:
    return _register_creation_authorization(
        authorizer_authority,
        transaction,
        ledger,
        owner_id,
        target_payload_sha256,
        owner_kind=_OwnerKind.BRANCH,
    )


def _register_hypothesis_creation_authorization(
    authorizer_authority: _OwnerCreationAuthorizerAuthority,
    transaction: _sqlite.ImmediateTransaction,
    ledger: _OwnerReceiptLedger,
    owner_id: str,
    target_payload_sha256: str,
) -> _OwnerCreationAuthorization:
    return _register_creation_authorization(
        authorizer_authority,
        transaction,
        ledger,
        owner_id,
        target_payload_sha256,
        owner_kind=_OwnerKind.HYPOTHESIS,
    )


def _token_kind(value: object) -> _OwnerKind:
    if type(value) is RevisionedBranchRecord:
        return _OwnerKind.BRANCH
    if type(value) is RevisionedHypothesisRecord:
        return _OwnerKind.HYPOTHESIS
    raise OwnerWriteProtocolError("owner token has an unsupported exact type")


def _token_owner_id(value: _OwnerToken) -> str:
    if type(value) is RevisionedBranchRecord:
        return value.branch_id
    if type(value) is RevisionedHypothesisRecord:
        return value.hypothesis_id
    raise OwnerWriteProtocolError("owner token has an unsupported exact type")


def _validate_exact_owner_id(value: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise OwnerWriteProtocolError("owner ID must be a nonempty exact str")
    return value


def _execute_owner_statement(
    store_authority: _OwnerStoreAuthority,
    ledger: _OwnerReceiptLedger,
    *,
    owner_kind: _OwnerKind,
    action: _OwnerAction,
    owner_id: str,
    expected_token: _OwnerToken | None,
    creation_authorization: _OwnerCreationAuthorization | None,
    sql: str,
    parameters: _SqlParameters,
) -> tuple[_sqlite.ImmediateResult, _OwnerWriteFact]:
    store_state = _lookup_store_authority(store_authority)
    state = _require_open_ledger(ledger, store_state.database_authority)
    _validate_store_binding(store_authority, state, owner_kind)
    owner = _validate_exact_owner_id(owner_id)
    if type(sql) is not str or not sql.strip():
        raise OwnerWriteProtocolError("focused owner SQL must be a nonempty exact str")
    authorization_state: _CreationAuthorizationState | None = None
    if action is _OwnerAction.UPDATE:
        if creation_authorization is not None:
            raise OwnerWriteProtocolError(
                "owner UPDATE cannot carry a creation authorization"
            )
        if expected_token is None or _token_kind(expected_token) is not owner_kind:
            raise OwnerWriteProtocolError(
                "owner UPDATE requires an exact expected token of the store kind"
            )
        if _token_owner_id(expected_token) != owner:
            raise OwnerWriteProtocolError(
                "owner UPDATE ID does not match its expected token"
            )
    else:
        if expected_token is not None:
            raise OwnerWriteProtocolError("owner INSERT cannot carry an expected token")
        if type(creation_authorization) is not _OwnerCreationAuthorization:
            raise InvalidOwnerReceiptError(
                "owner INSERT requires an issued creation authorization"
            )
        authorization_ledger_state, authorization_state = (
            _require_registered_creation_authorization(
                ledger,
                creation_authorization,
                owner_kind=owner_kind,
            )
        )
        if authorization_ledger_state is not state:
            raise InvalidOwnerReceiptError(
                "owner INSERT authorization resolved another receipt ledger"
            )
        if authorization_state.owner_id != owner:
            raise OwnerWriteProtocolError(
                "owner INSERT ID differs from its creation authorization"
            )
        if authorization_state.phase is not _CreationAuthorizationPhase.ISSUED:
            raise OwnerWriteProtocolError(
                "owner creation authorization is not in ISSUED phase"
            )
        if authorization_state.write_fact is not None:
            raise InvalidOwnerReceiptError(
                "issued owner creation authorization already has a write fact"
            )
    if state.active_permit is not None:
        raise OwnerWriteProtocolError("another owner-table permit is already active")
    if state.pending_write is not None:
        raise OwnerWriteProtocolError(
            "the prior owner write has not issued its exact receipt"
        )
    if any(
        prior.owner_kind is owner_kind and prior.owner_id == owner
        for prior in state.writes.values()
    ):
        raise OwnerWriteProtocolError(
            "one owner ID cannot be written twice in the same transaction"
        )
    fact = object.__new__(_OwnerWriteFact)
    fact_state = _WriteFactState(
        owner_kind=owner_kind,
        action=action,
        owner_id=owner,
        expected_token=expected_token,
        target_payload_sha256=(
            None
            if authorization_state is None
            else authorization_state.target_payload_sha256
        ),
        creation_authorization=creation_authorization,
    )
    # The pending latch is installed before SQLite execution.  Any interruption
    # from here through receipt issuance prevents a second owner permit and
    # makes pre-commit closure fail closed.
    state.pending_write = fact
    state.writes[fact] = fact_state
    if authorization_state is not None:
        authorization_state.write_fact = fact
        authorization_state.phase = _CreationAuthorizationPhase.WRITE_BOUND
    permit = _PermitState(owner_kind=owner_kind, action=action)
    result: _sqlite.ImmediateResult | None = None
    try:
        try:
            state.active_permit = permit
            permit.executing = True
            result = _sqlite._execute_participant(
                state.transaction,
                state.database_authority,
                sql,
                parameters,
            )
            rowcount = result.rowcount
            if not permit.authorizer_event_seen:
                raise OwnerWriteProtocolError(
                    "owner permit statement did not write its exact owner table"
                )
            fact_state.rowcount = rowcount
            fact_state.completed = True
        finally:
            # Phase first: any interruption after this assignment makes the
            # authorizer deny replay even if later cleanup is interrupted.
            permit.executing = False
            if state.active_permit is permit:
                state.active_permit = None
        assert result is not None
        return result, fact
    finally:
        # A one-shot asynchronous failure at the first cleanup boundary still
        # reaches this idempotent outer reconciliation.
        permit.executing = False
        if state.active_permit is permit:
            state.active_permit = None


def _execute_branch_owner_update(
    store_authority: _OwnerStoreAuthority,
    ledger: _OwnerReceiptLedger,
    expected_token: RevisionedBranchRecord,
    sql: str,
    parameters: _SqlParameters = (),
) -> tuple[_sqlite.ImmediateResult, _OwnerWriteFact]:
    return _execute_owner_statement(
        store_authority,
        ledger,
        owner_kind=_OwnerKind.BRANCH,
        action=_OwnerAction.UPDATE,
        owner_id=expected_token.branch_id,
        expected_token=expected_token,
        creation_authorization=None,
        sql=sql,
        parameters=parameters,
    )


def _execute_hypothesis_owner_update(
    store_authority: _OwnerStoreAuthority,
    ledger: _OwnerReceiptLedger,
    expected_token: RevisionedHypothesisRecord,
    sql: str,
    parameters: _SqlParameters = (),
) -> tuple[_sqlite.ImmediateResult, _OwnerWriteFact]:
    return _execute_owner_statement(
        store_authority,
        ledger,
        owner_kind=_OwnerKind.HYPOTHESIS,
        action=_OwnerAction.UPDATE,
        owner_id=expected_token.hypothesis_id,
        expected_token=expected_token,
        creation_authorization=None,
        sql=sql,
        parameters=parameters,
    )


def _execute_branch_owner_insert(
    store_authority: _OwnerStoreAuthority,
    ledger: _OwnerReceiptLedger,
    creation_authorization: _OwnerCreationAuthorization,
    owner_id: str,
    sql: str,
    parameters: _SqlParameters = (),
) -> tuple[_sqlite.ImmediateResult, _OwnerWriteFact]:
    return _execute_owner_statement(
        store_authority,
        ledger,
        owner_kind=_OwnerKind.BRANCH,
        action=_OwnerAction.INSERT,
        owner_id=owner_id,
        expected_token=None,
        creation_authorization=creation_authorization,
        sql=sql,
        parameters=parameters,
    )


def _execute_hypothesis_owner_insert(
    store_authority: _OwnerStoreAuthority,
    ledger: _OwnerReceiptLedger,
    creation_authorization: _OwnerCreationAuthorization,
    owner_id: str,
    sql: str,
    parameters: _SqlParameters = (),
) -> tuple[_sqlite.ImmediateResult, _OwnerWriteFact]:
    return _execute_owner_statement(
        store_authority,
        ledger,
        owner_kind=_OwnerKind.HYPOTHESIS,
        action=_OwnerAction.INSERT,
        owner_id=owner_id,
        expected_token=None,
        creation_authorization=creation_authorization,
        sql=sql,
        parameters=parameters,
    )


def _lookup_write_fact(
    state: _LedgerState,
    value: object,
) -> _WriteFactState:
    if type(value) is not _OwnerWriteFact:
        raise InvalidOwnerReceiptError("operation requires an issued owner write fact")
    fact_state = state.writes.get(value)
    if fact_state is None:
        raise InvalidOwnerReceiptError(
            "owner write fact belongs to another receipt ledger"
        )
    return fact_state


def _validate_mutation_successor(
    owner_kind: _OwnerKind,
    expected: _OwnerToken,
    committed: _OwnerToken,
) -> None:
    if (
        _token_kind(expected) is not owner_kind
        or _token_kind(committed) is not owner_kind
    ):
        raise OwnerWriteProtocolError("mutation tokens have the wrong owner kind")
    if _token_owner_id(expected) != _token_owner_id(committed):
        raise OwnerWriteProtocolError("owner identity changed during mutation")
    if committed.owner_revision != expected.owner_revision + 1:
        raise OwnerWriteProtocolError(
            "owner mutation must advance exactly one durable revision"
        )
    if committed.payload_sha256 == expected.payload_sha256:
        raise OwnerWriteProtocolError("owner mutation must change semantic payload")
    if owner_kind is _OwnerKind.HYPOTHESIS:
        expected_h = expected
        committed_h = committed
        assert type(expected_h) is RevisionedHypothesisRecord
        assert type(committed_h) is RevisionedHypothesisRecord
        if expected_h.value().branch_id != committed_h.value().branch_id:
            raise OwnerWriteProtocolError(
                "a hypothesis owner cannot move between Branches"
            )


def _issue_receipt(
    store_authority: _OwnerStoreAuthority,
    ledger: _OwnerReceiptLedger,
    write_fact: _OwnerWriteFact,
    committed_token: _OwnerToken,
    *,
    owner_kind: _OwnerKind,
    action: _OwnerAction,
) -> OwnerMutationReceipt | OwnerCreationReceipt:
    state = _require_open_ledger(
        ledger,
        _lookup_store_authority(store_authority).database_authority,
    )
    _validate_store_binding(store_authority, state, owner_kind)
    fact_state = _lookup_write_fact(state, write_fact)
    if fact_state.owner_kind is not owner_kind or fact_state.action is not action:
        raise OwnerWriteProtocolError("owner write fact has another kind or action")
    if state.pending_write is not write_fact:
        raise OwnerWriteProtocolError(
            "receipt issuance requires the exact pending owner write"
        )
    if not fact_state.completed or fact_state.rowcount != 1:
        raise OwnerWriteProtocolError(
            "receipt issuance requires one completed single-row owner write"
        )
    if fact_state.receipt is not None:
        raise OwnerWriteProtocolError("owner write fact already issued a receipt")
    if _token_kind(committed_token) is not owner_kind:
        raise OwnerWriteProtocolError("committed token has another owner kind")
    if _token_owner_id(committed_token) != fact_state.owner_id:
        raise OwnerWriteProtocolError(
            "committed token ID differs from the permitted owner ID"
        )
    creation_authorization = fact_state.creation_authorization
    if action is _OwnerAction.UPDATE:
        if (
            fact_state.target_payload_sha256 is not None
            or creation_authorization is not None
        ):
            raise InvalidOwnerReceiptError(
                "owner mutation write fact carries creation authorization state"
            )
        expected = fact_state.expected_token
        assert expected is not None
        _validate_mutation_successor(owner_kind, expected, committed_token)
        receipt = object.__new__(OwnerMutationReceipt)
    else:
        expected = None
        if type(creation_authorization) is not _OwnerCreationAuthorization:
            raise InvalidOwnerReceiptError(
                "owner creation write fact lacks its exact authorization"
            )
        _, authorization_state = _require_registered_creation_authorization(
            ledger,
            creation_authorization,
            owner_kind=owner_kind,
        )
        if (
            authorization_state.phase is not _CreationAuthorizationPhase.WRITE_BOUND
            or authorization_state.write_fact is not write_fact
            or authorization_state.owner_id != fact_state.owner_id
            or authorization_state.target_payload_sha256
            != fact_state.target_payload_sha256
        ):
            raise InvalidOwnerReceiptError(
                "owner creation authorization and write fact identities differ"
            )
        if committed_token.owner_revision != 0:
            raise OwnerWriteProtocolError(
                "owner creation receipt requires committed revision zero"
            )
        if committed_token.payload_sha256 != fact_state.target_payload_sha256:
            raise OwnerWriteProtocolError(
                "owner creation token digest differs from its authorization"
            )
        receipt = object.__new__(OwnerCreationReceipt)

    witness = _OwnerReceiptWitness(
        owner_kind=owner_kind,
        owner_id=fact_state.owner_id,
        expected_token=expected,
        committed_token=committed_token,
        creation_authorization=creation_authorization,
    )
    receipt_state = _ReceiptState(ledger_ref=weakref.ref(ledger), witness=witness)
    # Register the receipt before publishing it to the focused store.  An
    # interruption after registration leaves an extra unconsumed receipt and
    # therefore makes closure fail rather than losing a durable write fact.
    state.receipts[receipt] = write_fact
    with _RECEIPT_STATES_LOCK:
        _RECEIPT_STATES[receipt] = receipt_state
    fact_state.receipt = receipt
    state.pending_write = None
    return receipt


def _issue_branch_mutation_receipt(
    store_authority: _OwnerStoreAuthority,
    ledger: _OwnerReceiptLedger,
    write_fact: _OwnerWriteFact,
    committed_token: RevisionedBranchRecord,
) -> OwnerMutationReceipt:
    receipt = _issue_receipt(
        store_authority,
        ledger,
        write_fact,
        committed_token,
        owner_kind=_OwnerKind.BRANCH,
        action=_OwnerAction.UPDATE,
    )
    assert type(receipt) is OwnerMutationReceipt
    return receipt


def _issue_hypothesis_mutation_receipt(
    store_authority: _OwnerStoreAuthority,
    ledger: _OwnerReceiptLedger,
    write_fact: _OwnerWriteFact,
    committed_token: RevisionedHypothesisRecord,
) -> OwnerMutationReceipt:
    receipt = _issue_receipt(
        store_authority,
        ledger,
        write_fact,
        committed_token,
        owner_kind=_OwnerKind.HYPOTHESIS,
        action=_OwnerAction.UPDATE,
    )
    assert type(receipt) is OwnerMutationReceipt
    return receipt


def _issue_branch_creation_receipt(
    store_authority: _OwnerStoreAuthority,
    ledger: _OwnerReceiptLedger,
    write_fact: _OwnerWriteFact,
    committed_token: RevisionedBranchRecord,
) -> OwnerCreationReceipt:
    receipt = _issue_receipt(
        store_authority,
        ledger,
        write_fact,
        committed_token,
        owner_kind=_OwnerKind.BRANCH,
        action=_OwnerAction.INSERT,
    )
    assert type(receipt) is OwnerCreationReceipt
    return receipt


def _issue_hypothesis_creation_receipt(
    store_authority: _OwnerStoreAuthority,
    ledger: _OwnerReceiptLedger,
    write_fact: _OwnerWriteFact,
    committed_token: RevisionedHypothesisRecord,
) -> OwnerCreationReceipt:
    receipt = _issue_receipt(
        store_authority,
        ledger,
        write_fact,
        committed_token,
        owner_kind=_OwnerKind.HYPOTHESIS,
        action=_OwnerAction.INSERT,
    )
    assert type(receipt) is OwnerCreationReceipt
    return receipt


def _lookup_receipt(
    value: object,
) -> _ReceiptState:
    if type(value) not in {OwnerMutationReceipt, OwnerCreationReceipt}:
        raise InvalidOwnerReceiptError("operation requires an issued owner receipt")
    with _RECEIPT_STATES_LOCK:
        state = _RECEIPT_STATES.get(value)  # type: ignore[arg-type]
    if state is None:
        raise InvalidOwnerReceiptError("owner receipt was not issued")
    return state


def _lookup_semantic_creation_outcome_witness(
    value: object,
) -> _SemanticCreationOutcomeWitnessState:
    if type(value) is not SemanticCreationOutcomeWitness:
        raise InvalidOwnerReceiptError(
            "operation requires an issued semantic creation outcome witness"
        )
    with _SEMANTIC_CREATION_OUTCOME_WITNESS_STATES_LOCK:
        state = _SEMANTIC_CREATION_OUTCOME_WITNESS_STATES.get(value)
    if state is None:
        raise InvalidOwnerReceiptError(
            "semantic creation outcome witness was not issued"
        )
    return state


def _require_semantic_creation_outcome_witness(
    authorizer_authority: _OwnerCreationAuthorizerAuthority,
    transaction: _sqlite.ImmediateTransaction,
    ledger: _OwnerReceiptLedger,
    authorization: _OwnerCreationAuthorization,
    witness: SemanticCreationOutcomeWitness,
    *,
    owner_kind: _OwnerKind,
) -> tuple[_LedgerState, _CreationAuthorizationState]:
    ledger_state, authorization_state = _require_registered_creation_authorization(
        ledger,
        authorization,
        owner_kind=owner_kind,
        authorizer_authority=authorizer_authority,
    )
    if ledger_state.transaction is not transaction:
        raise InvalidOwnerReceiptError(
            "semantic creation outcome witness uses another transaction"
        )
    _require_owner_ledger_transaction_binding(
        transaction,
        ledger,
        authorization_state.database_authority,
    )
    witness_state = _lookup_semantic_creation_outcome_witness(witness)
    if (
        witness_state.authorizer_authority is not authorizer_authority
        or witness_state.authorization_ref() is not authorization
        or witness_state.ledger_ref() is not ledger
        or witness_state.transaction is not transaction
        or witness_state.database_authority
        is not authorization_state.database_authority
        or witness_state.owner_kind is not owner_kind
        or authorization_state.semantic_outcome_witness is not witness
    ):
        raise InvalidOwnerReceiptError(
            "semantic creation outcome witness has another exact binding"
        )
    return ledger_state, authorization_state


def _issue_semantic_creation_outcome_witness(
    authorizer_authority: _OwnerCreationAuthorizerAuthority,
    transaction: _sqlite.ImmediateTransaction,
    ledger: _OwnerReceiptLedger,
    authorization: _OwnerCreationAuthorization,
    *,
    owner_kind: _OwnerKind,
) -> SemanticCreationOutcomeWitness:
    ledger_state, authorization_state = _require_registered_creation_authorization(
        ledger,
        authorization,
        owner_kind=owner_kind,
        authorizer_authority=authorizer_authority,
    )
    if ledger_state.transaction is not transaction:
        raise InvalidOwnerReceiptError(
            "semantic creation outcome witness uses another transaction"
        )
    _require_owner_ledger_transaction_binding(
        transaction,
        ledger,
        authorization_state.database_authority,
    )
    if authorization_state.phase is not _CreationAuthorizationPhase.WRITE_BOUND:
        raise OwnerWriteProtocolError(
            "semantic creation outcome requires WRITE_BOUND authorization"
        )
    if authorization_state.semantic_outcome_witness is not None:
        raise OwnerWriteProtocolError(
            "semantic creation outcome witness can be issued only once"
        )
    write_fact = authorization_state.write_fact
    if type(write_fact) is not _OwnerWriteFact:
        raise InvalidOwnerReceiptError(
            "semantic creation outcome lacks its authorization write fact"
        )
    fact_state = _lookup_write_fact(ledger_state, write_fact)
    receipt = fact_state.receipt
    if (
        fact_state.action is not _OwnerAction.INSERT
        or fact_state.creation_authorization is not authorization
        or not fact_state.completed
        or fact_state.rowcount != 1
        or type(receipt) is not OwnerCreationReceipt
        or ledger_state.receipts.get(receipt) is not write_fact
        or ledger_state.pending_write is not None
        or ledger_state.active_permit is not None
    ):
        raise OwnerWriteProtocolError(
            "semantic creation outcome requires one exact issued creation receipt"
        )

    witness = object.__new__(SemanticCreationOutcomeWitness)
    witness_state = _SemanticCreationOutcomeWitnessState(
        authorizer_authority=authorizer_authority,
        authorization_ref=weakref.ref(authorization),
        ledger_ref=weakref.ref(ledger),
        transaction=transaction,
        database_authority=authorization_state.database_authority,
        owner_kind=owner_kind,
    )
    with _SEMANTIC_CREATION_OUTCOME_WITNESS_STATES_LOCK:
        _SEMANTIC_CREATION_OUTCOME_WITNESS_STATES[witness] = witness_state
    authorization_state.semantic_outcome_witness = witness
    return witness


def _issue_branch_semantic_creation_outcome_witness(
    authorizer_authority: _OwnerCreationAuthorizerAuthority,
    transaction: _sqlite.ImmediateTransaction,
    ledger: _OwnerReceiptLedger,
    authorization: _OwnerCreationAuthorization,
) -> SemanticCreationOutcomeWitness:
    return _issue_semantic_creation_outcome_witness(
        authorizer_authority,
        transaction,
        ledger,
        authorization,
        owner_kind=_OwnerKind.BRANCH,
    )


def _issue_hypothesis_semantic_creation_outcome_witness(
    authorizer_authority: _OwnerCreationAuthorizerAuthority,
    transaction: _sqlite.ImmediateTransaction,
    ledger: _OwnerReceiptLedger,
    authorization: _OwnerCreationAuthorization,
) -> SemanticCreationOutcomeWitness:
    return _issue_semantic_creation_outcome_witness(
        authorizer_authority,
        transaction,
        ledger,
        authorization,
        owner_kind=_OwnerKind.HYPOTHESIS,
    )


def _require_branch_semantic_creation_outcome_witness(
    authorizer_authority: _OwnerCreationAuthorizerAuthority,
    transaction: _sqlite.ImmediateTransaction,
    ledger: _OwnerReceiptLedger,
    authorization: _OwnerCreationAuthorization,
    witness: SemanticCreationOutcomeWitness,
) -> None:
    _require_semantic_creation_outcome_witness(
        authorizer_authority,
        transaction,
        ledger,
        authorization,
        witness,
        owner_kind=_OwnerKind.BRANCH,
    )


def _require_hypothesis_semantic_creation_outcome_witness(
    authorizer_authority: _OwnerCreationAuthorizerAuthority,
    transaction: _sqlite.ImmediateTransaction,
    ledger: _OwnerReceiptLedger,
    authorization: _OwnerCreationAuthorization,
    witness: SemanticCreationOutcomeWitness,
) -> None:
    _require_semantic_creation_outcome_witness(
        authorizer_authority,
        transaction,
        ledger,
        authorization,
        witness,
        owner_kind=_OwnerKind.HYPOTHESIS,
    )


def _complete_creation_authorization(
    authorizer_authority: _OwnerCreationAuthorizerAuthority,
    transaction: _sqlite.ImmediateTransaction,
    ledger: _OwnerReceiptLedger,
    authorization: _OwnerCreationAuthorization,
    receipt: OwnerCreationReceipt,
    semantic_outcome_witness: SemanticCreationOutcomeWitness,
    *,
    owner_kind: _OwnerKind,
) -> None:
    ledger_state, authorization_state = _require_semantic_creation_outcome_witness(
        authorizer_authority,
        transaction,
        ledger,
        authorization,
        semantic_outcome_witness,
        owner_kind=owner_kind,
    )
    if authorization_state.phase is not _CreationAuthorizationPhase.WRITE_BOUND:
        raise OwnerWriteProtocolError(
            "owner creation authorization is not in WRITE_BOUND phase"
        )
    write_fact = authorization_state.write_fact
    if type(write_fact) is not _OwnerWriteFact:
        raise InvalidOwnerReceiptError(
            "owner creation authorization lacks its exact write fact"
        )
    fact_state = _lookup_write_fact(ledger_state, write_fact)
    if (
        fact_state.owner_kind is not owner_kind
        or fact_state.action is not _OwnerAction.INSERT
        or fact_state.owner_id != authorization_state.owner_id
        or fact_state.expected_token is not None
        or fact_state.target_payload_sha256 != authorization_state.target_payload_sha256
        or fact_state.creation_authorization is not authorization
        or not fact_state.completed
        or fact_state.rowcount != 1
        or fact_state.receipt is not receipt
    ):
        raise InvalidOwnerReceiptError(
            "owner creation completion facts do not match the authorization"
        )
    if type(receipt) is not OwnerCreationReceipt:
        raise InvalidOwnerReceiptError(
            "owner creation completion requires an exact creation receipt"
        )
    if ledger_state.pending_write is not None:
        raise OwnerWriteProtocolError(
            "owner creation authorization cannot complete with a pending write"
        )
    if ledger_state.active_permit is not None:
        raise OwnerWriteProtocolError(
            "owner creation authorization cannot complete with an active permit"
        )
    if ledger_state.receipts.get(receipt) is not write_fact:
        raise InvalidOwnerReceiptError(
            "owner creation receipt is not registered for its exact write fact"
        )
    receipt_state = _lookup_receipt(receipt)
    witness = receipt_state.witness
    committed = witness.committed_token
    if (
        receipt_state.ledger_ref() is not ledger
        or witness.owner_kind is not owner_kind
        or witness.owner_id != authorization_state.owner_id
        or witness.expected_token is not None
        or witness.creation_authorization is not authorization
        or _token_kind(committed) is not owner_kind
        or _token_owner_id(committed) != authorization_state.owner_id
        or committed.owner_revision != 0
        or committed.payload_sha256 != authorization_state.target_payload_sha256
    ):
        raise InvalidOwnerReceiptError(
            "owner creation receipt witness does not match the authorization"
        )
    # This is the final, one-way semantic participant latch.  There is no
    # reset, replay, cancellation, or idempotent second completion path.
    authorization_state.phase = _CreationAuthorizationPhase.COMPLETED


def _complete_branch_creation_authorization(
    authorizer_authority: _OwnerCreationAuthorizerAuthority,
    transaction: _sqlite.ImmediateTransaction,
    ledger: _OwnerReceiptLedger,
    authorization: _OwnerCreationAuthorization,
    receipt: OwnerCreationReceipt,
    semantic_outcome_witness: SemanticCreationOutcomeWitness,
) -> None:
    _complete_creation_authorization(
        authorizer_authority,
        transaction,
        ledger,
        authorization,
        receipt,
        semantic_outcome_witness,
        owner_kind=_OwnerKind.BRANCH,
    )


def _complete_hypothesis_creation_authorization(
    authorizer_authority: _OwnerCreationAuthorizerAuthority,
    transaction: _sqlite.ImmediateTransaction,
    ledger: _OwnerReceiptLedger,
    authorization: _OwnerCreationAuthorization,
    receipt: OwnerCreationReceipt,
    semantic_outcome_witness: SemanticCreationOutcomeWitness,
) -> None:
    _complete_creation_authorization(
        authorizer_authority,
        transaction,
        ledger,
        authorization,
        receipt,
        semantic_outcome_witness,
        owner_kind=_OwnerKind.HYPOTHESIS,
    )


def _consume_receipt_as(
    ledger: _OwnerReceiptLedger,
    receipt: OwnerMutationReceipt | OwnerCreationReceipt,
    *,
    owner_kind: _OwnerKind,
    creation: bool,
) -> _OwnerReceiptWitness:
    state = _lookup_ledger(ledger)
    state = _require_open_ledger(ledger, state.database_authority)
    receipt_state = _lookup_receipt(receipt)
    if receipt_state.ledger_ref() is not ledger:
        raise InvalidOwnerReceiptError("owner receipt belongs to another transaction")
    witness = receipt_state.witness
    if witness.owner_kind is not owner_kind:
        raise OwnerWriteProtocolError("owner receipt has another owner kind")
    if creation != (type(receipt) is OwnerCreationReceipt):
        raise OwnerWriteProtocolError(
            "owner mutation and creation receipts cannot be interchanged"
        )
    if creation != (witness.expected_token is None):
        raise InvalidOwnerReceiptError("owner receipt action state is malformed")
    write_fact = state.receipts.get(receipt)
    if write_fact is None:
        raise InvalidOwnerReceiptError("owner receipt is absent from this ledger")
    fact_state = _lookup_write_fact(state, write_fact)
    if creation:
        authorization = witness.creation_authorization
        if type(authorization) is not _OwnerCreationAuthorization:
            raise InvalidOwnerReceiptError(
                "owner creation receipt lacks its exact authorization"
            )
        _, authorization_state = _require_registered_creation_authorization(
            ledger,
            authorization,
            owner_kind=owner_kind,
        )
        if (
            authorization_state.phase is not _CreationAuthorizationPhase.COMPLETED
            or authorization_state.write_fact is not write_fact
            or fact_state.creation_authorization is not authorization
            or fact_state.receipt is not receipt
            or fact_state.target_payload_sha256
            != authorization_state.target_payload_sha256
        ):
            raise OwnerWriteProtocolError(
                "owner creation receipt authorization is not completed exactly"
            )
    elif (
        witness.creation_authorization is not None
        or fact_state.creation_authorization is not None
        or fact_state.target_payload_sha256 is not None
    ):
        raise InvalidOwnerReceiptError(
            "owner mutation receipt carries creation authorization state"
        )
    if receipt in state.consumed:
        raise OwnerWriteProtocolError("owner receipt can be consumed only once")
    state.consumed.add(receipt)
    return witness


def _consume_branch_mutation_receipt(
    ledger: _OwnerReceiptLedger,
    receipt: OwnerMutationReceipt,
) -> _OwnerReceiptWitness:
    return _consume_receipt_as(
        ledger,
        receipt,
        owner_kind=_OwnerKind.BRANCH,
        creation=False,
    )


def _consume_hypothesis_mutation_receipt(
    ledger: _OwnerReceiptLedger,
    receipt: OwnerMutationReceipt,
) -> _OwnerReceiptWitness:
    return _consume_receipt_as(
        ledger,
        receipt,
        owner_kind=_OwnerKind.HYPOTHESIS,
        creation=False,
    )


def _consume_branch_creation_receipt(
    ledger: _OwnerReceiptLedger,
    receipt: OwnerCreationReceipt,
) -> _OwnerReceiptWitness:
    return _consume_receipt_as(
        ledger,
        receipt,
        owner_kind=_OwnerKind.BRANCH,
        creation=True,
    )


def _consume_hypothesis_creation_receipt(
    ledger: _OwnerReceiptLedger,
    receipt: OwnerCreationReceipt,
) -> _OwnerReceiptWitness:
    return _consume_receipt_as(
        ledger,
        receipt,
        owner_kind=_OwnerKind.HYPOTHESIS,
        creation=True,
    )


def _seal_owner_receipt_ledger(
    ledger: _OwnerReceiptLedger,
    staged_receipts: tuple[OwnerMutationReceipt | OwnerCreationReceipt, ...],
) -> tuple[_OwnerReceiptWitness, ...]:
    """Prove exact write/issued/consumed/staged identity equality pre-commit."""

    state = _lookup_ledger(ledger)
    state = _require_open_ledger(ledger, state.database_authority)
    if type(staged_receipts) is not tuple:
        raise TypeError("staged_receipts must be an exact tuple")
    if not staged_receipts:
        raise OwnerReceiptClosureError("owner receipt closure cannot be empty")
    if state.active_permit is not None:
        raise OwnerReceiptClosureError("an owner write permit is still active")
    if state.pending_write is not None:
        raise OwnerReceiptClosureError(
            "an owner write has not completed receipt issuance"
        )
    if any(
        type(receipt) not in {OwnerMutationReceipt, OwnerCreationReceipt}
        for receipt in staged_receipts
    ):
        raise InvalidOwnerReceiptError("staged receipt has a forged type")
    if len(set(staged_receipts)) != len(staged_receipts):
        raise OwnerReceiptClosureError("staged owner receipts contain duplicates")

    issued = set(state.receipts)
    staged = set(staged_receipts)
    if staged != issued or state.consumed != issued:
        raise OwnerReceiptClosureError(
            "issued, consumed, and staged owner receipt identities differ"
        )
    if len(state.writes) != len(issued):
        raise OwnerReceiptClosureError(
            "owner write facts and issued receipt counts differ"
        )
    bound_creation_authorizations: set[_OwnerCreationAuthorization] = set()
    for write_fact, fact_state in state.writes.items():
        if (
            not fact_state.completed
            or fact_state.rowcount != 1
            or fact_state.receipt is None
            or state.receipts.get(fact_state.receipt) is not write_fact
        ):
            raise OwnerReceiptClosureError(
                "an owner write lacks one exact completed receipt"
            )
        if fact_state.action is _OwnerAction.INSERT:
            authorization = fact_state.creation_authorization
            if (
                type(authorization) is not _OwnerCreationAuthorization
                or fact_state.expected_token is not None
                or fact_state.target_payload_sha256 is None
            ):
                raise OwnerReceiptClosureError(
                    "an owner creation write lacks exact authorization state"
                )
            authorization_state = state.creation_authorizations.get(authorization)
            if (
                authorization_state is None
                or authorization_state.write_fact is not write_fact
                or authorization_state.owner_kind is not fact_state.owner_kind
                or authorization_state.owner_id != fact_state.owner_id
                or authorization_state.target_payload_sha256
                != fact_state.target_payload_sha256
            ):
                raise OwnerReceiptClosureError(
                    "an owner creation write is bound to another authorization"
                )
            bound_creation_authorizations.add(authorization)
        elif (
            fact_state.expected_token is None
            or fact_state.target_payload_sha256 is not None
            or fact_state.creation_authorization is not None
        ):
            raise OwnerReceiptClosureError(
                "an owner mutation write carries creation authorization state"
            )

    registered_creation_authorizations = set(state.creation_authorizations)
    completed_creation_authorizations = {
        authorization
        for authorization, authorization_state in (
            state.creation_authorizations.items()
        )
        if authorization_state.phase is _CreationAuthorizationPhase.COMPLETED
    }
    witnessed_creation_authorizations: set[_OwnerCreationAuthorization] = set()
    for authorization, authorization_state in state.creation_authorizations.items():
        outcome_witness = authorization_state.semantic_outcome_witness
        if outcome_witness is None:
            continue
        try:
            outcome_state = _lookup_semantic_creation_outcome_witness(outcome_witness)
        except InvalidOwnerReceiptError as exc:
            raise OwnerReceiptClosureError(
                "a semantic creation outcome witness is not issued exactly"
            ) from exc
        if (
            outcome_state.authorizer_authority
            is not authorization_state.authorizer_authority
            or outcome_state.authorization_ref() is not authorization
            or outcome_state.ledger_ref() is not ledger
            or outcome_state.transaction is not state.transaction
            or outcome_state.database_authority is not state.database_authority
            or outcome_state.owner_kind is not authorization_state.owner_kind
        ):
            raise OwnerReceiptClosureError(
                "a semantic creation outcome witness has another exact binding"
            )
        witnessed_creation_authorizations.add(authorization)

    def _receipt_creation_authorization(
        receipt: OwnerMutationReceipt | OwnerCreationReceipt,
    ) -> _OwnerCreationAuthorization | None:
        receipt_state = _lookup_receipt(receipt)
        if receipt_state.ledger_ref() is not ledger:
            raise OwnerReceiptClosureError(
                "an owner receipt witness belongs to another ledger"
            )
        authorization = receipt_state.witness.creation_authorization
        if type(receipt) is OwnerCreationReceipt:
            if type(authorization) is not _OwnerCreationAuthorization:
                raise OwnerReceiptClosureError(
                    "an owner creation receipt lacks its authorization identity"
                )
            return authorization
        if authorization is not None:
            raise OwnerReceiptClosureError(
                "an owner mutation receipt carries a creation authorization"
            )
        return None

    issued_creation_sequence = tuple(
        authorization
        for receipt in state.receipts
        if (authorization := _receipt_creation_authorization(receipt)) is not None
    )
    consumed_creation_sequence = tuple(
        authorization
        for receipt in state.consumed
        if (authorization := _receipt_creation_authorization(receipt)) is not None
    )
    staged_creation_sequence = tuple(
        authorization
        for receipt in staged_receipts
        if (authorization := _receipt_creation_authorization(receipt)) is not None
    )
    authorization_sets = (
        registered_creation_authorizations,
        bound_creation_authorizations,
        witnessed_creation_authorizations,
        completed_creation_authorizations,
        set(issued_creation_sequence),
        set(consumed_creation_sequence),
        set(staged_creation_sequence),
    )
    if any(
        values != registered_creation_authorizations for values in authorization_sets
    ) or any(
        len(values) != len(registered_creation_authorizations)
        for values in (
            issued_creation_sequence,
            consumed_creation_sequence,
            staged_creation_sequence,
        )
    ):
        raise OwnerReceiptClosureError(
            "registered, bound, witnessed, completed, issued, consumed, and staged "
            "creation authorization identities differ"
        )

    witnesses = tuple(_lookup_receipt(receipt).witness for receipt in staged_receipts)
    # Phase is the final pre-commit latch for this module.  No permit or new
    # receipt can be issued after it, including if an asynchronous exception
    # interrupts the caller immediately after this assignment.
    state.phase = _LedgerPhase.SEALED
    return witnesses


def _close_owner_receipt_ledger(
    ledger: _OwnerReceiptLedger,
    database_authority: _sqlite.CampaignDatabaseAuthority,
) -> None:
    """Irreversibly deny further owner writes during transaction cleanup."""

    state = _lookup_ledger(ledger)
    if state.database_authority is not database_authority:
        raise InvalidOwnerReceiptError(
            "owner receipt ledger is bound to another database authority"
        )
    if state.thread_id != threading.get_ident():
        raise InactiveOwnerTransactionError(
            "owner receipt ledger cannot be closed from another thread"
        )
    if state.phase is _LedgerPhase.CLOSED:
        return
    try:
        _sqlite.require_active_immediate_transaction(
            state.transaction,
            database_authority,
        )
    except _sqlite._ForeignLifecycleContextError as exc:
        raise InactiveOwnerTransactionError(
            "owner receipt ledger cannot be closed from another Context"
        ) from exc
    except _sqlite.InactiveImmediateTransactionError as exc:
        if state.phase is _LedgerPhase.OPEN:
            raise InactiveOwnerTransactionError(
                "an unsealed owner ledger can close only in its active transaction"
            ) from exc
    # Phase first: SQLite authorizer callback denies all owner DML from here.
    state.phase = _LedgerPhase.CLOSED
    permit = state.active_permit
    if permit is not None:
        permit.executing = False
    state.active_permit = None
