"""Dormant connection-scoped owner for one hypothesis-attempt START event.

The participant appends and strictly rereads one existing
``ProposalAttemptRecorder`` v1 transition.  It deliberately owns neither the
Campaign schema nor transaction lifecycle, provider calls, hypothesis rows, or
production composition.
"""

from __future__ import annotations

import contextvars
import enum
import hashlib
import json
import threading
import uuid
import weakref
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Final, Mapping

from scion.core.proposal_pipeline.attempts import ProposalAttemptRecorder
from scion.lineage import sqlite_connection as _sqlite

__all__ = (
    "InvalidStartedHypothesisAttemptError",
    "ProposalAttemptOwner",
    "StartedHypothesisAttempt",
    "StartedHypothesisAttemptError",
    "StartedHypothesisAttemptLifecycleError",
)

_STARTED_EVENT_COLUMNS: Final[tuple[str, ...]] = (
    "event_id",
    "campaign_id",
    "branch_id",
    "hypothesis_id",
    "timestamp",
    "event_kind",
    "stage",
    "audit_payload_json",
)
_STARTED_EVENT_INSERT_SQL: Final[str] = """
INSERT INTO experiment_events (
    event_id,
    campaign_id,
    branch_id,
    hypothesis_id,
    timestamp,
    event_kind,
    stage,
    audit_payload_json
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""
_STARTED_EVENT_SELECT_SQL: Final[str] = """
SELECT event_id,
       campaign_id,
       branch_id,
       hypothesis_id,
       timestamp,
       event_kind,
       stage,
       audit_payload_json
FROM experiment_events
WHERE event_id = ?
"""
_EVENT_KIND: Final[str] = "proposal_attempt_transition"
_EVENT_STAGE: Final[str] = "proposal_hypothesis"
_PROVIDER_ATTEMPT_AUDIT_SCHEMA: Final[str] = "provider-call-attempt-audit.v1"


class StartedHypothesisAttemptError(RuntimeError):
    """Base error for the dormant START owner and its sealed capability."""


class InvalidStartedHypothesisAttemptError(
    TypeError,
    StartedHypothesisAttemptError,
):
    """A START payload or capability is forged, malformed, or mismatched."""


class StartedHypothesisAttemptLifecycleError(StartedHypothesisAttemptError):
    """A genuine START capability crossed its context or was reused."""


class StartedHypothesisAttempt:
    """Sealed, context-bound authority for one strictly reread START event."""

    __slots__ = ("__weakref__",)

    def __new__(
        cls,
        *_args: object,
        **_kwargs: object,
    ) -> "StartedHypothesisAttempt":
        raise InvalidStartedHypothesisAttemptError(
            "StartedHypothesisAttempt is issued only by ProposalAttemptOwner"
        )

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("StartedHypothesisAttempt is sealed")

    def __copy__(self) -> "StartedHypothesisAttempt":
        raise InvalidStartedHypothesisAttemptError(
            "StartedHypothesisAttempt cannot be copied"
        )

    def __deepcopy__(
        self,
        _memo: dict[int, object],
    ) -> "StartedHypothesisAttempt":
        raise InvalidStartedHypothesisAttemptError(
            "StartedHypothesisAttempt cannot be copied"
        )

    def __reduce__(self) -> object:
        raise InvalidStartedHypothesisAttemptError(
            "StartedHypothesisAttempt cannot be pickled"
        )

    def __reduce_ex__(self, _protocol: int) -> object:
        raise InvalidStartedHypothesisAttemptError(
            "StartedHypothesisAttempt cannot be pickled"
        )


class _StartedAttemptPhase(enum.Enum):
    ISSUED = enum.auto()
    PROVIDER_BOUND = enum.auto()


@dataclass(frozen=True, slots=True)
class _StartedHypothesisAttemptFacts:
    event_id: str
    attempt_id: str
    campaign_id: str
    branch_id: str
    timestamp: str
    event_kind: str
    stage: str
    context_digest: str
    prompt_hash: str
    canonical_payload_json: bytes
    payload_sha256: str


@dataclass(slots=True)
class _StartedHypothesisAttemptState:
    facts: _StartedHypothesisAttemptFacts
    owner: ProposalAttemptOwner
    thread_id: int
    context_probe: contextvars.ContextVar[object | None]
    context_marker: object
    context_token: contextvars.Token[object | None]
    phase: _StartedAttemptPhase = _StartedAttemptPhase.ISSUED


@dataclass(frozen=True, slots=True)
class _StartedHypothesisProviderBinding:
    """Frozen non-authority facts accepted by the dormant provider seam."""

    attempt_id: str
    started_event_id: str
    campaign_id: str
    branch_id: str
    context_digest: str
    prompt_hash: str
    canonical_payload_json: bytes
    payload_sha256: str
    attempt_audit: Mapping[str, object]


_STARTED_ATTEMPT_STATES: weakref.WeakKeyDictionary[
    StartedHypothesisAttempt,
    _StartedHypothesisAttemptState,
] = weakref.WeakKeyDictionary()
_STARTED_ATTEMPT_STATES_LOCK = threading.RLock()


def _required_exact_string(value: object, *, field: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise InvalidStartedHypothesisAttemptError(
            f"started hypothesis attempt requires exact {field}"
        )
    return value


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidStartedHypothesisAttemptError(
                "started hypothesis attempt JSON contains a duplicate object key"
            )
        result[key] = value
    return result


def _canonical_started_payload(
    payload: Mapping[str, Any],
    *,
    authority_campaign_id: str,
) -> tuple[dict[str, Any], bytes]:
    if type(payload) is not dict:
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis transition must be an exact dict"
        )
    normalized = dict(payload)
    if normalized.get("phase") != "hypothesis":
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis transition requires hypothesis phase"
        )
    if normalized.get("status") != "started":
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis transition requires started status"
        )
    if normalized.get("attempt_kind") != "initial":
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis transition requires initial attempt kind"
        )
    if normalized.get("continuation_of_attempt_id") is not None:
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis transition cannot be a continuation"
        )
    try:
        ProposalAttemptRecorder.validate_transition(normalized)
    except (TypeError, ValueError) as exc:
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis transition failed ProposalAttemptRecorder validation"
        ) from exc

    attempt_id = _required_exact_string(
        normalized.get("attempt_id"),
        field="attempt_id",
    )
    campaign_id = _required_exact_string(
        normalized.get("campaign_id"),
        field="campaign_id",
    )
    _required_exact_string(normalized.get("branch_id"), field="branch_id")
    if campaign_id != authority_campaign_id:
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis transition belongs to another campaign"
        )
    if (
        normalized.get("hypothesis_id") is not None
        or normalized.get("hypothesis_digest") is not None
    ):
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis transition cannot contain hypothesis identity"
        )

    prompt_call = normalized.get("prompt_call")
    if type(prompt_call) is not dict:
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis prompt_call must be an exact dict"
        )
    _required_exact_string(
        prompt_call.get("context_digest"),
        field="prompt context_digest",
    )
    _required_exact_string(
        prompt_call.get("prompt_hash"),
        field="prompt_hash",
    )
    if type(normalized.get("anchors")) is not dict:
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis anchors must be an exact dict"
        )
    if type(normalized.get("tainted_artifact_refs")) is not list:
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis artifact refs must be an exact list"
        )

    try:
        encoded = json.dumps(
            normalized,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis transition cannot be canonically encoded"
        ) from exc
    try:
        decoded = json.loads(
            encoded.decode("utf-8"),
            object_pairs_hook=_json_object,
            parse_constant=lambda value: (_raise_nonfinite_json(value)),
        )
    except InvalidStartedHypothesisAttemptError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis canonical JSON is malformed"
        ) from exc
    if type(decoded) is not dict or decoded != normalized:
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis canonical JSON changed the transition"
        )
    # Keep the exact variables alive for type-checking and make accidental
    # replacement during future edits visible to static readers.
    if decoded["attempt_id"] != attempt_id or decoded["campaign_id"] != campaign_id:
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis canonical identity changed"
        )
    return decoded, encoded


def _raise_nonfinite_json(value: str) -> None:
    raise InvalidStartedHypothesisAttemptError(
        f"started hypothesis JSON contains non-finite value {value}"
    )


def _result_columns(result: _sqlite.ImmediateResult) -> tuple[str, ...]:
    description = result.description
    if description is None:
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis SELECT has no row description"
        )
    try:
        return tuple(column[0] for column in description)
    except (IndexError, TypeError) as exc:
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis SELECT description is malformed"
        ) from exc


def _strict_reread_started_event(
    transaction: _sqlite.ImmediateTransaction,
    database_authority: _sqlite.CampaignDatabaseAuthority,
    expected_values: tuple[object, ...],
) -> _StartedHypothesisAttemptFacts:
    event_id = _required_exact_string(expected_values[0], field="event_id")
    result = _sqlite._execute_participant(
        transaction,
        database_authority,
        _STARTED_EVENT_SELECT_SQL,
        (event_id,),
    )
    if _result_columns(result) != _STARTED_EVENT_COLUMNS:
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis SELECT did not return the frozen columns"
        )
    rows = result.fetchall()
    if len(rows) != 1:
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis INSERT did not reread one exact event"
        )
    values = tuple(rows[0])
    if len(values) != len(_STARTED_EVENT_COLUMNS):
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis event row is incomplete"
        )
    for column, stored, expected in zip(
        _STARTED_EVENT_COLUMNS,
        values,
        expected_values,
        strict=True,
    ):
        if type(stored) is not type(expected) or stored != expected:
            raise InvalidStartedHypothesisAttemptError(
                f"started hypothesis post-write storage differs: {column}"
            )

    stored_payload = values[7]
    if type(stored_payload) is not str:
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis payload is not exact JSON text"
        )
    try:
        decoded = json.loads(
            stored_payload,
            object_pairs_hook=_json_object,
            parse_constant=lambda value: (_raise_nonfinite_json(value)),
        )
    except InvalidStartedHypothesisAttemptError:
        raise
    except (TypeError, json.JSONDecodeError, RecursionError) as exc:
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis stored payload is malformed"
        ) from exc
    authority_state = _sqlite._lookup_authority_state(database_authority)
    normalized, canonical_payload = _canonical_started_payload(
        decoded,
        authority_campaign_id=authority_state.campaign_id,
    )
    if canonical_payload.decode("utf-8") != stored_payload:
        raise InvalidStartedHypothesisAttemptError(
            "started hypothesis stored payload is not canonical"
        )
    prompt_call = normalized["prompt_call"]
    return _StartedHypothesisAttemptFacts(
        event_id=event_id,
        attempt_id=normalized["attempt_id"],
        campaign_id=normalized["campaign_id"],
        branch_id=normalized["branch_id"],
        timestamp=values[4],
        event_kind=values[5],
        stage=values[6],
        context_digest=prompt_call["context_digest"],
        prompt_hash=prompt_call["prompt_hash"],
        canonical_payload_json=canonical_payload,
        payload_sha256=hashlib.sha256(canonical_payload).hexdigest(),
    )


def _issue_started_hypothesis_attempt(
    facts: _StartedHypothesisAttemptFacts,
    *,
    owner: ProposalAttemptOwner,
) -> StartedHypothesisAttempt:
    context_probe: contextvars.ContextVar[object | None] = contextvars.ContextVar(
        f"scion_started_hypothesis_attempt_{facts.event_id}",
        default=None,
    )
    context_marker = object()
    context_token = context_probe.set(context_marker)
    value = object.__new__(StartedHypothesisAttempt)
    state = _StartedHypothesisAttemptState(
        facts=facts,
        owner=owner,
        thread_id=threading.get_ident(),
        context_probe=context_probe,
        context_marker=context_marker,
        context_token=context_token,
    )
    with _STARTED_ATTEMPT_STATES_LOCK:
        _STARTED_ATTEMPT_STATES[value] = state
    return value


def _prove_started_attempt_context(
    state: _StartedHypothesisAttemptState,
) -> None:
    if state.context_probe.get() is not state.context_marker:
        raise StartedHypothesisAttemptLifecycleError(
            "StartedHypothesisAttempt cannot cross Contexts"
        )
    try:
        state.context_probe.reset(state.context_token)
    except (RuntimeError, ValueError) as exc:
        raise StartedHypothesisAttemptLifecycleError(
            "StartedHypothesisAttempt cannot cross Contexts"
        ) from exc
    state.context_token = state.context_probe.set(state.context_marker)


def _bind_started_hypothesis_attempt_to_provider(
    value: StartedHypothesisAttempt,
    committed_snapshot: _sqlite._IndependentReadSnapshot,
) -> _StartedHypothesisProviderBinding:
    """Claim one START only after its exact event is durably visible."""

    if type(value) is not StartedHypothesisAttempt:
        raise InvalidStartedHypothesisAttemptError(
            "provider binding requires an exact StartedHypothesisAttempt"
        )
    with _STARTED_ATTEMPT_STATES_LOCK:
        state = _STARTED_ATTEMPT_STATES.get(value)
        if state is None:
            raise InvalidStartedHypothesisAttemptError(
                "StartedHypothesisAttempt was not issued"
            )
        if state.phase is not _StartedAttemptPhase.ISSUED:
            raise StartedHypothesisAttemptLifecycleError(
                "StartedHypothesisAttempt is already provider-bound"
            )
        if state.thread_id != threading.get_ident():
            raise StartedHypothesisAttemptLifecycleError(
                "StartedHypothesisAttempt cannot cross threads"
            )
        _prove_started_attempt_context(state)
        # Claim before the durable classification read.  A wrong/rolled-back
        # event, foreign snapshot, or later failure can never make this START
        # reusable.
        state.phase = _StartedAttemptPhase.PROVIDER_BOUND
        facts = state.facts
        owner = state.owner

    owner._require_committed_started_in(committed_snapshot, facts)
    attempt_audit = MappingProxyType(
        {
            "schema_version": _PROVIDER_ATTEMPT_AUDIT_SCHEMA,
            "attempt_id": facts.attempt_id,
            "phase": "hypothesis",
            "attempt_kind": "initial",
            "continuation_of_attempt_id": None,
            "hypothesis_attempt_id": facts.attempt_id,
            "started_lineage_event_id": facts.event_id,
        }
    )
    return _StartedHypothesisProviderBinding(
        attempt_id=facts.attempt_id,
        started_event_id=facts.event_id,
        campaign_id=facts.campaign_id,
        branch_id=facts.branch_id,
        context_digest=facts.context_digest,
        prompt_hash=facts.prompt_hash,
        canonical_payload_json=bytes(facts.canonical_payload_json),
        payload_sha256=facts.payload_sha256,
        attempt_audit=attempt_audit,
    )


class ProposalAttemptOwner:
    """Connection-scoped participant for a single hypothesis START append."""

    __slots__ = ("__authority_campaign_id", "__database_authority")

    def __init__(
        self,
        database_authority: _sqlite.CampaignDatabaseAuthority,
    ) -> None:
        authority_state = _sqlite._lookup_authority_state(database_authority)
        self.__database_authority = database_authority
        self.__authority_campaign_id = authority_state.campaign_id

    def _require_committed_started_in(
        self,
        snapshot: _sqlite._IndependentReadSnapshot,
        facts: _StartedHypothesisAttemptFacts,
    ) -> None:
        rows = _sqlite._execute_read_snapshot(
            snapshot,
            self.__database_authority,
            _STARTED_EVENT_SELECT_SQL,
            (facts.event_id,),
        )
        if len(rows) != 1:
            raise InvalidStartedHypothesisAttemptError(
                "started hypothesis event is not durably committed"
            )
        values = tuple(rows[0])
        expected_values: tuple[object, ...] = (
            facts.event_id,
            facts.campaign_id,
            facts.branch_id,
            None,
            facts.timestamp,
            facts.event_kind,
            facts.stage,
            facts.canonical_payload_json.decode("utf-8"),
        )
        if len(values) != len(_STARTED_EVENT_COLUMNS):
            raise InvalidStartedHypothesisAttemptError(
                "committed started hypothesis event is incomplete"
            )
        for column, stored, expected in zip(
            _STARTED_EVENT_COLUMNS,
            values,
            expected_values,
            strict=True,
        ):
            if type(stored) is not type(expected) or stored != expected:
                raise InvalidStartedHypothesisAttemptError(
                    f"committed started hypothesis event differs: {column}"
                )

    def append_started_hypothesis_attempt_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        transition_payload: Mapping[str, Any],
    ) -> StartedHypothesisAttempt:
        """Append, exact-reread, and issue one START capability in ``transaction``."""

        normalized, canonical_payload = _canonical_started_payload(
            transition_payload,
            authority_campaign_id=self.__authority_campaign_id,
        )
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        expected_values: tuple[object, ...] = (
            event_id,
            normalized["campaign_id"],
            normalized["branch_id"],
            None,
            timestamp,
            _EVENT_KIND,
            _EVENT_STAGE,
            canonical_payload.decode("utf-8"),
        )
        result = _sqlite._execute_participant(
            transaction,
            self.__database_authority,
            _STARTED_EVENT_INSERT_SQL,
            expected_values,
        )
        if result.rowcount != 1:
            raise InvalidStartedHypothesisAttemptError(
                "started hypothesis INSERT did not change exactly one row"
            )
        facts = _strict_reread_started_event(
            transaction,
            self.__database_authority,
            expected_values,
        )
        if facts.canonical_payload_json != canonical_payload:
            raise InvalidStartedHypothesisAttemptError(
                "started hypothesis reread changed canonical payload bytes"
            )
        return _issue_started_hypothesis_attempt(facts, owner=self)
