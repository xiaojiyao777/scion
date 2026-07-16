"""Atomic campaign identity and candidate-ownership bootstrap.

This module is deliberately independent of ``CampaignManager`` composition.
Callers resolve and persist a stable request before constructing any registry or
runtime store, then pass that exact request to :class:`CampaignOwnershipStore`.
Production activation is a later slice; D2a only establishes the durable
ownership boundary.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Final

from scion.core.candidate_snapshot_registry import CandidateOwnershipMode

CAMPAIGN_OPEN_REQUEST_SCHEMA: Final = "campaign-open-request.v1"
_CALLER_IDENTITY_FILENAME: Final = "campaign-open-identity.v1.json"
_CAMPAIGN_ID_RE: Final[re.Pattern[str]] = re.compile(r"[^\s]+")
IdentityPublishFaultHook = Callable[[str], None]


class CampaignOpenKind(str, Enum):
    """The only two legal durable campaign-open operations."""

    NEW = "NEW"
    REOPEN = "REOPEN"


class CampaignOpenError(RuntimeError):
    """Base failure for invalid or contradictory ownership bootstrap."""


class CampaignOpenConflictError(CampaignOpenError):
    """Durable state contradicts the caller-bound open request."""


@dataclass(frozen=True)
class CampaignOpenRequest:
    """Caller-owned identity and requested open operation."""

    kind: CampaignOpenKind
    campaign_id: str
    expected_mode: CandidateOwnershipMode | None = None

    def __post_init__(self) -> None:
        try:
            kind = CampaignOpenKind(self.kind)
        except (TypeError, ValueError) as exc:
            raise ValueError("campaign open kind is invalid") from exc
        campaign_id = _campaign_id(self.campaign_id)
        expected_mode = self.expected_mode
        if expected_mode is not None:
            try:
                expected_mode = CandidateOwnershipMode(expected_mode)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "expected candidate ownership mode is invalid"
                ) from exc
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "campaign_id", campaign_id)
        object.__setattr__(self, "expected_mode", expected_mode)


@dataclass(frozen=True)
class CampaignOpenResult:
    """Exact singleton ownership selected by an atomic open."""

    campaign_id: str
    mode: CandidateOwnershipMode
    adopted_pre_d2_identity: bool


@dataclass(frozen=True)
class _BootstrapState:
    campaign_id: str | None
    mode: CandidateOwnershipMode | None
    event_campaign_ids: tuple[str, ...]
    has_durable_state: bool
    has_legacy_adoption_state: bool


class CampaignOpenRequestResolver:
    """Persist and reuse the caller's identity before database composition.

    The resolver consults database ownership rows and legacy event identities;
    it never examines artifacts, directories other than its identity file, or
    environment variables to select an ownership mode.
    """

    def __init__(
        self,
        campaign_root: str | Path,
        *,
        db_path: str | Path | None = None,
        fault_hook: IdentityPublishFaultHook | None = None,
    ) -> None:
        self.campaign_root = Path(campaign_root)
        self.db_path = (
            Path(db_path) if db_path is not None else (self.campaign_root / "scion.db")
        )
        self.identity_path = self.campaign_root / _CALLER_IDENTITY_FILENAME
        self.fault_hook = fault_hook

    def resolve(
        self,
        request: CampaignOpenRequest | None = None,
        *,
        campaign_id: str | None = None,
        expected_mode: CandidateOwnershipMode | str | None = None,
    ) -> CampaignOpenRequest:
        """Bind an explicit request or derive NEW/REOPEN from durable state."""

        if request is not None and (
            campaign_id is not None or expected_mode is not None
        ):
            raise ValueError(
                "an explicit campaign open request cannot be combined with overrides"
            )
        state = _read_bootstrap_state(self.db_path)
        if request is not None:
            self._validate_request_against_state(request, state)
            self._bind_identity(request.campaign_id)
            return request

        selected_mode = _optional_mode(expected_mode)
        bound_id = self._read_identity()
        proposed_id = _campaign_id(campaign_id) if campaign_id is not None else None
        durable_id = state.campaign_id
        legacy_id = (
            state.event_campaign_ids[0] if len(state.event_campaign_ids) == 1 else None
        )
        if len(state.event_campaign_ids) > 1:
            raise CampaignOpenConflictError("legacy campaign identity is ambiguous")
        identities = {
            value for value in (bound_id, proposed_id, durable_id, legacy_id) if value
        }
        if len(identities) > 1:
            raise CampaignOpenConflictError(
                "caller and durable campaign identities are contradictory"
            )
        selected_id = next(iter(identities), str(uuid.uuid4()))
        kind = (
            CampaignOpenKind.REOPEN if state.has_durable_state else CampaignOpenKind.NEW
        )
        resolved = CampaignOpenRequest(kind, selected_id, selected_mode)
        self._validate_request_against_state(resolved, state)
        self._bind_identity(selected_id)
        return resolved

    def _validate_request_against_state(
        self,
        request: CampaignOpenRequest,
        state: _BootstrapState,
    ) -> None:
        if len(state.event_campaign_ids) > 1:
            raise CampaignOpenConflictError("legacy campaign identity is ambiguous")
        if (
            state.event_campaign_ids
            and state.event_campaign_ids[0] != request.campaign_id
        ):
            raise CampaignOpenConflictError(
                "legacy event identity conflicts with caller-bound request"
            )
        bound_id = self._read_identity()
        if bound_id is not None and bound_id != request.campaign_id:
            raise CampaignOpenConflictError(
                "campaign open request changed its caller-bound identity"
            )
        if state.campaign_id is not None and state.campaign_id != request.campaign_id:
            raise CampaignOpenConflictError(
                "campaign open request conflicts with durable identity"
            )
        if state.mode is not None:
            if (
                request.expected_mode is not None
                and request.expected_mode is not state.mode
            ):
                raise CampaignOpenConflictError(
                    "campaign open request conflicts with durable ownership mode"
                )
        elif state.has_durable_state and request.expected_mode is (
            CandidateOwnershipMode.CANDIDATE_SNAPSHOT_V1
        ):
            raise CampaignOpenConflictError(
                "pre-D2 durable state cannot be reopened as snapshot ownership"
            )
        if (
            request.kind is CampaignOpenKind.REOPEN
            and state.campaign_id is None
            and state.mode is None
            and not state.has_legacy_adoption_state
        ):
            raise CampaignOpenConflictError(
                "REOPEN has no adoptable pre-D2 campaign state"
            )
        if request.kind is CampaignOpenKind.NEW and state.has_durable_state:
            raise CampaignOpenConflictError("NEW campaign already has durable state")

    def _read_identity(self) -> str | None:
        if not self.identity_path.exists():
            return None
        try:
            payload = json.loads(self.identity_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CampaignOpenConflictError(
                "caller-bound campaign identity is unreadable"
            ) from exc
        if not isinstance(payload, dict) or set(payload) != {
            "schema_version",
            "campaign_id",
        }:
            raise CampaignOpenConflictError("caller-bound campaign identity is invalid")
        if payload["schema_version"] != CAMPAIGN_OPEN_REQUEST_SCHEMA:
            raise CampaignOpenConflictError(
                "caller-bound campaign identity schema is invalid"
            )
        try:
            return _campaign_id(payload["campaign_id"])
        except ValueError as exc:
            raise CampaignOpenConflictError(
                "caller-bound campaign identity is invalid"
            ) from exc

    def _bind_identity(self, campaign_id: str) -> None:
        current = self._read_identity()
        if current is not None:
            if current != campaign_id:
                raise CampaignOpenConflictError(
                    "campaign open request changed its caller-bound identity"
                )
            return
        self.campaign_root.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": CAMPAIGN_OPEN_REQUEST_SCHEMA,
            "campaign_id": campaign_id,
        }
        data = (_canonical_json(payload) + "\n").encode("utf-8")
        temporary_path = self.campaign_root / (
            f".{_CALLER_IDENTITY_FILENAME}.{uuid.uuid4().hex}.tmp"
        )
        descriptor: int | None = None
        try:
            descriptor = os.open(
                temporary_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            self._fault("after_temp_create")
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = None
                stream.write(data)
                stream.flush()
                self._fault("after_temp_write")
                os.fsync(stream.fileno())
                self._fault("after_temp_fsync")
            try:
                os.link(temporary_path, self.identity_path)
            except FileExistsError:
                current = self._read_identity()
                if current != campaign_id:
                    raise CampaignOpenConflictError(
                        "concurrent campaign identity claim is incompatible"
                    )
                return
            self._fault("after_publish")
            self._fsync_campaign_directory()
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
            else:
                self._fsync_campaign_directory()

    def _fault(self, phase: str) -> None:
        if self.fault_hook is not None:
            self.fault_hook(phase)

    def _fsync_campaign_directory(self) -> None:
        descriptor = os.open(self.campaign_root, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


class CampaignOwnershipStore:
    """Claim campaign identity and candidate mode in one SQLite transaction."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._ensure_schema()

    def open(self, request: CampaignOpenRequest) -> CampaignOpenResult:
        """Atomically execute one strict NEW or REOPEN request."""

        if type(request) is not CampaignOpenRequest:
            raise TypeError("campaign open requires a typed request")
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN IMMEDIATE")
            identity_row = conn.execute(
                "SELECT campaign_id FROM campaign_identity WHERE singleton_id = 1"
            ).fetchone()
            mode_row = conn.execute(
                "SELECT campaign_id, mode FROM candidate_ownership_mode "
                "WHERE singleton = 1"
            ).fetchone()
            if request.kind is CampaignOpenKind.NEW:
                result = self._open_new(conn, request, identity_row, mode_row)
            else:
                result = self._open_existing(conn, request, identity_row, mode_row)
            conn.commit()
            return result

    def _open_new(
        self,
        conn: sqlite3.Connection,
        request: CampaignOpenRequest,
        identity_row: sqlite3.Row | None,
        mode_row: sqlite3.Row | None,
    ) -> CampaignOpenResult:
        if request.expected_mode not in {
            None,
            CandidateOwnershipMode.CANDIDATE_SNAPSHOT_V1,
        }:
            raise CampaignOpenConflictError(
                "NEW campaigns require snapshot candidate ownership"
            )
        if (
            identity_row is not None
            or mode_row is not None
            or _has_any_durable_rows(conn)
        ):
            raise CampaignOpenConflictError("NEW campaign already has durable state")
        mode = CandidateOwnershipMode.CANDIDATE_SNAPSHOT_V1
        self._insert_pair(conn, request.campaign_id, mode)
        return CampaignOpenResult(request.campaign_id, mode, False)

    def _open_existing(
        self,
        conn: sqlite3.Connection,
        request: CampaignOpenRequest,
        identity_row: sqlite3.Row | None,
        mode_row: sqlite3.Row | None,
    ) -> CampaignOpenResult:
        if mode_row is not None and identity_row is None:
            raise CampaignOpenConflictError(
                "candidate ownership mode has no campaign identity"
            )
        if identity_row is not None and mode_row is not None:
            identity = _durable_campaign_id(identity_row["campaign_id"])
            mode_identity = _durable_campaign_id(mode_row["campaign_id"])
            mode = _stored_mode(mode_row["mode"])
            if identity != mode_identity or identity != request.campaign_id:
                raise CampaignOpenConflictError(
                    "durable campaign ownership is contradictory"
                )
            _validate_event_identity(conn, identity)
            _require_expected_mode(request, mode)
            return CampaignOpenResult(identity, mode, False)

        legacy_mode = CandidateOwnershipMode.LEGACY_VERIFIED_COMMIT_V1
        _require_expected_mode(request, legacy_mode)
        if identity_row is not None:
            identity = _durable_campaign_id(identity_row["campaign_id"])
            if identity != request.campaign_id:
                raise CampaignOpenConflictError(
                    "REOPEN campaign identity does not match durable ownership"
                )
            _validate_event_identity(conn, identity)
            self._insert_mode(conn, identity, legacy_mode)
            return CampaignOpenResult(identity, legacy_mode, True)

        event_ids = _event_campaign_ids(conn)
        if len(event_ids) > 1:
            raise CampaignOpenConflictError("legacy campaign identity is ambiguous")
        if not _has_legacy_adoption_rows(conn):
            raise CampaignOpenConflictError(
                "REOPEN has no adoptable pre-D2 campaign state"
            )
        if event_ids and event_ids[0] != request.campaign_id:
            raise CampaignOpenConflictError(
                "legacy event identity conflicts with caller-bound request"
            )
        identity = request.campaign_id
        self._insert_pair(conn, identity, legacy_mode)
        return CampaignOpenResult(identity, legacy_mode, True)

    @staticmethod
    def _insert_pair(
        conn: sqlite3.Connection,
        campaign_id: str,
        mode: CandidateOwnershipMode,
    ) -> None:
        now = _now()
        conn.execute(
            "INSERT INTO campaign_identity "
            "(singleton_id, campaign_id, created_at) VALUES (1, ?, ?)",
            (campaign_id, now),
        )
        CampaignOwnershipStore._insert_mode(conn, campaign_id, mode, now=now)

    @staticmethod
    def _insert_mode(
        conn: sqlite3.Connection,
        campaign_id: str,
        mode: CandidateOwnershipMode,
        *,
        now: str | None = None,
    ) -> None:
        conn.execute(
            "INSERT INTO candidate_ownership_mode "
            "(singleton, campaign_id, mode, created_at) VALUES (1, ?, ?, ?)",
            (campaign_id, mode.value, now or _now()),
        )

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_OWNERSHIP_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn


def _read_bootstrap_state(db_path: Path) -> _BootstrapState:
    if not db_path.is_file():
        return _BootstrapState(None, None, (), False, False)
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise CampaignOpenConflictError("campaign database is unreadable") from exc
    try:
        conn.row_factory = sqlite3.Row
        identity = None
        if _table_exists(conn, "campaign_identity"):
            row = conn.execute(
                "SELECT campaign_id FROM campaign_identity WHERE singleton_id = 1"
            ).fetchone()
            if row is not None:
                identity = _durable_campaign_id(row["campaign_id"])
        mode = None
        if _table_exists(conn, "candidate_ownership_mode"):
            row = conn.execute(
                "SELECT campaign_id, mode FROM candidate_ownership_mode "
                "WHERE singleton = 1"
            ).fetchone()
            if row is not None:
                mode_identity = _durable_campaign_id(row["campaign_id"])
                if identity is None:
                    raise CampaignOpenConflictError(
                        "candidate ownership mode has no campaign identity"
                    )
                if identity is not None and mode_identity != identity:
                    raise CampaignOpenConflictError(
                        "durable campaign ownership is contradictory"
                    )
                mode = _stored_mode(row["mode"])
        event_ids = _event_campaign_ids(conn)
        has_state = (
            identity is not None or mode is not None or _has_any_durable_rows(conn)
        )
        return _BootstrapState(
            identity,
            mode,
            event_ids,
            has_state,
            _has_legacy_adoption_rows(conn),
        )
    except sqlite3.Error as exc:
        raise CampaignOpenConflictError("campaign database is invalid") from exc
    finally:
        conn.close()


def _has_any_durable_rows(conn: sqlite3.Connection) -> bool:
    tables = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    for row in tables:
        table = str(row[0])
        quoted = '"' + table.replace('"', '""') + '"'
        if conn.execute(f"SELECT 1 FROM {quoted} LIMIT 1").fetchone() is not None:
            return True
    return False


def _has_legacy_adoption_rows(conn: sqlite3.Connection) -> bool:
    """Return true only for authoritative pre-D2 campaign state.

    Report/formal indexes block NEW through ``_has_any_durable_rows`` but never
    select legacy ownership positively.
    """

    for table in _LEGACY_ADOPTION_TABLES:
        if not _table_exists(conn, table):
            continue
        quoted = '"' + table.replace('"', '""') + '"'
        if conn.execute(f"SELECT 1 FROM {quoted} LIMIT 1").fetchone() is not None:
            return True
    return False


def _event_campaign_ids(conn: sqlite3.Connection) -> tuple[str, ...]:
    if not _table_exists(conn, "experiment_events"):
        return ()
    rows = conn.execute(
        "SELECT DISTINCT campaign_id FROM experiment_events "
        "WHERE campaign_id IS NOT NULL AND TRIM(campaign_id) != '' "
        "ORDER BY campaign_id"
    ).fetchall()
    return tuple(_durable_campaign_id(row[0]) for row in rows)


def _validate_event_identity(conn: sqlite3.Connection, campaign_id: str) -> None:
    event_ids = _event_campaign_ids(conn)
    if len(event_ids) > 1:
        raise CampaignOpenConflictError("legacy campaign identity is ambiguous")
    if event_ids and event_ids[0] != campaign_id:
        raise CampaignOpenConflictError(
            "event history conflicts with durable campaign identity"
        )


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        is not None
    )


def _require_expected_mode(
    request: CampaignOpenRequest,
    actual: CandidateOwnershipMode,
) -> None:
    if request.expected_mode is not None and request.expected_mode is not actual:
        raise CampaignOpenConflictError(
            "REOPEN candidate ownership mode does not match durable ownership"
        )


def _campaign_id(value: object) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise ValueError("campaign identity is invalid")
    if _CAMPAIGN_ID_RE.fullmatch(value) is None:
        raise ValueError("campaign identity is invalid")
    return value


def _durable_campaign_id(value: object) -> str:
    try:
        return _campaign_id(value)
    except ValueError as exc:
        raise CampaignOpenConflictError("durable campaign identity is invalid") from exc


def _optional_mode(
    value: CandidateOwnershipMode | str | None,
) -> CandidateOwnershipMode | None:
    if value is None:
        return None
    try:
        return CandidateOwnershipMode(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("expected candidate ownership mode is invalid") from exc


def _stored_mode(value: object) -> CandidateOwnershipMode:
    try:
        return CandidateOwnershipMode(str(value))
    except ValueError as exc:
        raise CampaignOpenConflictError(
            "durable candidate ownership mode is invalid"
        ) from exc


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_LEGACY_ADOPTION_TABLES: Final = (
    "experiment_events",
    "branches",
    "hypotheses",
    "champions",
    "weight_optimizations",
    "research_rejection_completion_intents",
    "decision_completion_intents",
)


_OWNERSHIP_SCHEMA = """
CREATE TABLE IF NOT EXISTS campaign_identity (
 singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1),
 campaign_id TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS campaign_identity_no_update BEFORE UPDATE ON
 campaign_identity BEGIN SELECT RAISE(ABORT,'campaign identity is immutable'); END;
CREATE TRIGGER IF NOT EXISTS campaign_identity_no_delete BEFORE DELETE ON
 campaign_identity BEGIN SELECT RAISE(ABORT,'campaign identity is append-only'); END;
CREATE TABLE IF NOT EXISTS candidate_ownership_mode (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), campaign_id TEXT NOT NULL UNIQUE,
 mode TEXT NOT NULL CHECK(mode IN ('legacy_verified_commit_v1','candidate_snapshot_v1')),
 created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS candidate_ownership_mode_no_update BEFORE UPDATE ON
 candidate_ownership_mode BEGIN SELECT RAISE(ABORT,'candidate ownership mode is immutable'); END;
CREATE TRIGGER IF NOT EXISTS candidate_ownership_mode_no_delete BEFORE DELETE ON
 candidate_ownership_mode BEGIN SELECT RAISE(ABORT,'candidate ownership mode is append-only'); END;
"""
