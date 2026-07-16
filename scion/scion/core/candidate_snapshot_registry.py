"""Internal append-only SQLite registry for candidate snapshot storage."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Final

from scion.core.candidate_snapshot import (
    CandidateOriginKind,
    CandidateSnapshotError,
    CandidateSnapshotTamperError,
)

_SHA256_RE: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{64}")


class CandidateOwnershipMode(str, Enum):
    LEGACY_VERIFIED_COMMIT_V1 = "legacy_verified_commit_v1"
    CANDIDATE_SNAPSHOT_V1 = "candidate_snapshot_v1"


class CandidateSnapshotModeError(CandidateSnapshotError):
    pass


class CandidateSnapshotConflictError(CandidateSnapshotError):
    pass


@dataclass(frozen=True)
class CandidateSnapshotRecord:
    candidate_id: str
    campaign_id: str
    origin_kind: CandidateOriginKind
    origin_id: str
    identity_sha256: str
    artifact_sha256: str
    artifact_ref: str
    parent_workspace_ref: str
    candidate_workspace_ref: str
    status: str


class CandidateSnapshotRegistry:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._ensure_tables()

    def claim_mode(
        self, campaign_id: str, mode: CandidateOwnershipMode | str
    ) -> CandidateOwnershipMode:
        campaign_id = _text(campaign_id, "campaign identity")
        try:
            selected = CandidateOwnershipMode(mode)
        except ValueError as exc:
            raise ValueError("candidate ownership mode is invalid") from exc
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT campaign_id, mode FROM candidate_ownership_mode "
                "WHERE singleton = 1"
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO candidate_ownership_mode "
                    "(singleton, campaign_id, mode, created_at) VALUES (1, ?, ?, ?)",
                    (campaign_id, selected.value, _now()),
                )
            elif row["campaign_id"] != campaign_id or row["mode"] != selected.value:
                raise CandidateSnapshotModeError(
                    "candidate ownership mode is already claimed by an incompatible owner"
                )
            conn.commit()
        return selected

    def verify_mode(
        self,
        campaign_id: str,
        expected: CandidateOwnershipMode | str = (
            CandidateOwnershipMode.CANDIDATE_SNAPSHOT_V1
        ),
    ) -> CandidateOwnershipMode:
        campaign_id = _text(campaign_id, "campaign identity")
        try:
            selected = CandidateOwnershipMode(expected)
        except ValueError as exc:
            raise ValueError("candidate ownership mode is invalid") from exc
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT campaign_id, mode FROM candidate_ownership_mode "
                "WHERE singleton = 1"
            ).fetchone()
        if row is None:
            raise CandidateSnapshotModeError(
                "candidate ownership mode must be claimed before snapshot prepare"
            )
        if row["campaign_id"] != campaign_id or row["mode"] != selected.value:
            raise CandidateSnapshotModeError(
                "candidate ownership mode does not match the requested owner"
            )
        return selected

    def load(self, candidate_id: str) -> CandidateSnapshotRecord | None:
        candidate_id = _sha(candidate_id, "candidate snapshot ID")
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM candidate_snapshots WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
        return _record(row) if row is not None else None

    def load_for_origin(
        self,
        campaign_id: str,
        origin_kind: CandidateOriginKind | str,
        origin_id: str,
    ) -> CandidateSnapshotRecord | None:
        try:
            origin = CandidateOriginKind(origin_kind)
        except ValueError as exc:
            raise ValueError("candidate snapshot origin kind is invalid") from exc
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM candidate_snapshots "
                "WHERE campaign_id = ? AND origin_kind = ? AND origin_id = ?",
                (
                    _text(campaign_id, "campaign identity"),
                    origin.value,
                    _text(origin_id, "candidate origin identity"),
                ),
            ).fetchone()
        return _record(row) if row is not None else None

    def pending(self) -> tuple[CandidateSnapshotRecord, ...]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM candidate_snapshots WHERE status = 'prepared' "
                "ORDER BY created_at, candidate_id"
            ).fetchall()
        return tuple(_record(row) for row in rows)

    def prepare(self, desired: CandidateSnapshotRecord) -> CandidateSnapshotRecord:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN IMMEDIATE")
            self._verify_mode_row(conn, desired.campaign_id)
            row = conn.execute(
                "SELECT * FROM candidate_snapshots "
                "WHERE campaign_id = ? AND origin_kind = ? AND origin_id = ?",
                (desired.campaign_id, desired.origin_kind.value, desired.origin_id),
            ).fetchone()
            if row is not None:
                current = _record(row)
                if _identity(current) != _identity(desired):
                    raise CandidateSnapshotConflictError(
                        "candidate snapshot origin already owns a different payload"
                    )
                conn.commit()
                return current
            if (
                conn.execute(
                    "SELECT 1 FROM candidate_snapshots WHERE candidate_id = ?",
                    (desired.candidate_id,),
                ).fetchone()
                is not None
            ):
                raise CandidateSnapshotConflictError(
                    "candidate snapshot ID is already owned by another origin"
                )
            now = _now()
            conn.execute(
                """
                INSERT INTO candidate_snapshots
                (candidate_id, campaign_id, origin_kind, origin_id,
                 identity_sha256, artifact_sha256, artifact_ref,
                 parent_workspace_ref, candidate_workspace_ref, status,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'prepared', ?, ?)
                """,
                (
                    *_identity(desired),
                    desired.parent_workspace_ref,
                    desired.candidate_workspace_ref,
                    now,
                    now,
                ),
            )
            conn.commit()
        prepared = self.load(desired.candidate_id)
        if prepared is None:
            raise CandidateSnapshotError("prepared candidate snapshot disappeared")
        return prepared

    def mark_committed(
        self, record: CandidateSnapshotRecord
    ) -> CandidateSnapshotRecord:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM candidate_snapshots WHERE candidate_id = ?",
                (record.candidate_id,),
            ).fetchone()
            if row is None:
                raise CandidateSnapshotError(
                    "candidate snapshot registry row is missing"
                )
            current = _record(row)
            if _identity(current) != _identity(record):
                raise CandidateSnapshotConflictError(
                    "candidate snapshot registry identity changed"
                )
            if current.status == "prepared":
                conn.execute(
                    "UPDATE candidate_snapshots SET status = 'committed', "
                    "updated_at = ? WHERE candidate_id = ?",
                    (_now(), current.candidate_id),
                )
            conn.commit()
        committed = self.load(record.candidate_id)
        if committed is None or committed.status != "committed":
            raise CandidateSnapshotError("candidate snapshot registry did not commit")
        return committed

    def _verify_mode_row(self, conn: sqlite3.Connection, campaign_id: str) -> None:
        row = conn.execute(
            "SELECT campaign_id, mode FROM candidate_ownership_mode WHERE singleton = 1"
        ).fetchone()
        if (
            row is None
            or row["campaign_id"] != campaign_id
            or row["mode"] != CandidateOwnershipMode.CANDIDATE_SNAPSHOT_V1.value
        ):
            raise CandidateSnapshotModeError(
                "candidate snapshot prepare requires its exclusive ownership mode"
            )

    def _ensure_tables(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn


def _record(row: sqlite3.Row) -> CandidateSnapshotRecord:
    try:
        origin = CandidateOriginKind(str(row["origin_kind"]))
    except ValueError as exc:
        raise CandidateSnapshotTamperError(
            "snapshot registry origin is invalid"
        ) from exc
    candidate_id = _sha(row["candidate_id"], "candidate snapshot ID")
    identity = _sha(row["identity_sha256"], "snapshot identity digest")
    if identity != candidate_id or row["status"] not in {"prepared", "committed"}:
        raise CandidateSnapshotTamperError("snapshot registry identity is invalid")
    return CandidateSnapshotRecord(
        candidate_id,
        _text(row["campaign_id"], "campaign identity"),
        origin,
        _text(row["origin_id"], "candidate origin identity"),
        identity,
        _sha(row["artifact_sha256"], "snapshot artifact digest"),
        str(row["artifact_ref"]),
        _text(row["parent_workspace_ref"], "parent workspace ref"),
        _text(row["candidate_workspace_ref"], "candidate workspace ref"),
        str(row["status"]),
    )


def _identity(record: CandidateSnapshotRecord) -> tuple[str, ...]:
    return (
        record.candidate_id,
        record.campaign_id,
        record.origin_kind.value,
        record.origin_id,
        record.identity_sha256,
        record.artifact_sha256,
        record.artifact_ref,
    )


def _text(value: object, label: str) -> str:
    text = str(value or "")
    if not text or text != text.strip():
        raise ValueError(f"{label} is invalid")
    return text


def _sha(value: object, label: str) -> str:
    text = str(value or "")
    if _SHA256_RE.fullmatch(text) is None:
        raise CandidateSnapshotTamperError(f"{label} is invalid")
    return text


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS candidate_ownership_mode (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), campaign_id TEXT NOT NULL UNIQUE,
 mode TEXT NOT NULL CHECK(mode IN ('legacy_verified_commit_v1','candidate_snapshot_v1')),
 created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS candidate_ownership_mode_no_update BEFORE UPDATE ON
 candidate_ownership_mode BEGIN SELECT RAISE(ABORT,'candidate ownership mode is immutable'); END;
CREATE TRIGGER IF NOT EXISTS candidate_ownership_mode_no_delete BEFORE DELETE ON
 candidate_ownership_mode BEGIN SELECT RAISE(ABORT,'candidate ownership mode is append-only'); END;
CREATE TABLE IF NOT EXISTS candidate_snapshots (
 candidate_id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL, origin_kind TEXT NOT NULL
 CHECK(origin_kind IN ('direct_code_attempt','reconcile_transition')), origin_id TEXT NOT NULL,
 identity_sha256 TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, artifact_ref TEXT NOT NULL UNIQUE,
 parent_workspace_ref TEXT NOT NULL, candidate_workspace_ref TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('prepared','committed')), created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL, UNIQUE(campaign_id,origin_kind,origin_id));
CREATE INDEX IF NOT EXISTS idx_candidate_snapshots_pending ON
 candidate_snapshots(status,created_at,candidate_id);
CREATE TRIGGER IF NOT EXISTS candidate_snapshots_no_delete BEFORE DELETE ON candidate_snapshots
 BEGIN SELECT RAISE(ABORT,'candidate snapshot registry is append-only'); END;
CREATE TRIGGER IF NOT EXISTS candidate_snapshots_immutable_update BEFORE UPDATE ON candidate_snapshots
 WHEN OLD.candidate_id!=NEW.candidate_id OR OLD.campaign_id!=NEW.campaign_id
 OR OLD.origin_kind!=NEW.origin_kind OR OLD.origin_id!=NEW.origin_id
 OR OLD.identity_sha256!=NEW.identity_sha256 OR OLD.artifact_sha256!=NEW.artifact_sha256
 OR OLD.artifact_ref!=NEW.artifact_ref OR OLD.parent_workspace_ref!=NEW.parent_workspace_ref
 OR OLD.candidate_workspace_ref!=NEW.candidate_workspace_ref OR OLD.created_at!=NEW.created_at
 OR OLD.status!='prepared' OR NEW.status!='committed'
 BEGIN SELECT RAISE(ABORT,'candidate snapshot registry is immutable'); END;
"""
