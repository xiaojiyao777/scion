"""Private, bounded reader for one initial-screening artifact root.

Only the three ordinary public artifact names are addressable here.  The
caller owns study controls; this reader establishes only a stable, non-symlink
snapshot of those literal files.
"""

from __future__ import annotations

import errno
import json
import math
import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, NoReturn

from scion.core.research_history import (
    MAX_RESEARCH_HISTORY_FILE_BYTES,
    MAX_RESEARCH_HISTORY_LINE_BYTES,
    MAX_RESEARCH_HISTORY_RECORDS,
    MAX_RESEARCH_HISTORY_TOTAL_BYTES,
)

from .models import ResearchEffectivenessInputError

_STATUS_NAME = "status.json"
_SUMMARY_NAME = "campaign_summary.json"
_HISTORY_NAME = "research_history.jsonl"
_STATUS_MAX_BYTES = 8 * 1024 * 1024
_SUMMARY_MAX_BYTES = 32 * 1024 * 1024
_ALL_ARTIFACTS_MAX_BYTES = 256 * 1024 * 1024
_READ_CHUNK_BYTES = 64 * 1024
_LOAD_ERROR = "STUDY_ROOT_LOAD_INVALID"


class _StrictJsonFailure(ValueError):
    """An internal parse sentinel whose details never cross the boundary."""


@dataclass(frozen=True, repr=False)
class _FileIdentity:
    device: int
    inode: int


@dataclass(frozen=True, repr=False)
class _FileFingerprint:
    identity: _FileIdentity
    mode: int
    size: int
    links: int
    modified_ns: int
    changed_ns: int


@dataclass(frozen=True, repr=False)
class _RootFingerprint:
    identity: _FileIdentity
    mode: int
    modified_ns: int
    changed_ns: int


@dataclass(frozen=True, repr=False)
class _LoadedRootSnapshot:
    status: Mapping[str, Any]
    summary: Mapping[str, Any]
    current_history: tuple[Mapping[str, Any], ...]
    root_identity: _FileIdentity
    leaf_identities: tuple[_FileIdentity, ...]
    total_bytes: int
    history_bytes: int
    root_fingerprint: _RootFingerprint
    status_fingerprint: _FileFingerprint
    summary_fingerprint: _FileFingerprint
    history_fingerprint: _FileFingerprint | None


def _load_root_snapshot(
    root: object,
    *,
    history_record_cap: int,
    total_byte_limit: int = _ALL_ARTIFACTS_MAX_BYTES,
    history_byte_limit: int = MAX_RESEARCH_HISTORY_TOTAL_BYTES,
) -> _LoadedRootSnapshot:
    """Return one sanitized snapshot or one fixed, context-free error."""

    failed = False
    snapshot: _LoadedRootSnapshot | None = None
    try:
        canonical = _canonical_root(root)
        snapshot = _load_root_snapshot_from_canonical(
            canonical,
            history_record_cap=history_record_cap,
            total_byte_limit=total_byte_limit,
            history_byte_limit=history_byte_limit,
        )
    except Exception:  # noqa: BLE001 - sanitize every ordinary path/parser failure
        failed = True
    if failed or snapshot is None:
        _fail_load()
    return snapshot


def _load_root_snapshot_from_canonical(
    canonical: str,
    *,
    history_record_cap: int,
    total_byte_limit: int,
    history_byte_limit: int,
) -> _LoadedRootSnapshot:
    if (
        type(history_record_cap) is not int
        or history_record_cap < 0
        or type(total_byte_limit) is not int
        or total_byte_limit < 0
        or total_byte_limit > _ALL_ARTIFACTS_MAX_BYTES
        or type(history_byte_limit) is not int
        or history_byte_limit < 0
        or history_byte_limit > MAX_RESEARCH_HISTORY_TOTAL_BYTES
    ):
        raise _StrictJsonFailure
    root_fd = _open_canonical_root(canonical)
    try:
        root_before = _root_fingerprint(os.fstat(root_fd))
        status_raw, status_fingerprint = _read_required_leaf(
            root_fd,
            _STATUS_NAME,
            limit=min(_STATUS_MAX_BYTES, total_byte_limit),
        )
        remaining_total = total_byte_limit - len(status_raw)
        summary_raw, summary_fingerprint = _read_required_leaf(
            root_fd,
            _SUMMARY_NAME,
            limit=min(_SUMMARY_MAX_BYTES, remaining_total),
        )
        remaining_total -= len(summary_raw)
        history_leaf = _read_optional_leaf(
            root_fd,
            _HISTORY_NAME,
            limit=min(
                MAX_RESEARCH_HISTORY_FILE_BYTES,
                remaining_total,
                history_byte_limit,
            ),
        )
        status = _parse_json_object(status_raw)
        summary = _parse_json_object(summary_raw)
        if history_leaf is None:
            if summary.get("steps") != []:
                raise _StrictJsonFailure
            current_history: tuple[Mapping[str, Any], ...] = ()
            history_fingerprint = None
            history_bytes = 0
        else:
            history_raw, history_fingerprint = history_leaf
            if not history_raw:
                raise _StrictJsonFailure
            current_history = _parse_json_lines(
                history_raw,
                record_cap=min(
                    history_record_cap,
                    MAX_RESEARCH_HISTORY_RECORDS,
                ),
            )
            history_bytes = len(history_raw)
        _verify_leaf(root_fd, _STATUS_NAME, status_fingerprint)
        _verify_leaf(root_fd, _SUMMARY_NAME, summary_fingerprint)
        if history_fingerprint is None:
            _verify_leaf_absent(root_fd, _HISTORY_NAME)
        else:
            _verify_leaf(root_fd, _HISTORY_NAME, history_fingerprint)
        root_after = _root_fingerprint(os.fstat(root_fd))
        if root_after != root_before:
            raise _StrictJsonFailure
    finally:
        os.close(root_fd)
    rewalk_fd = _open_canonical_root(canonical)
    try:
        if _root_fingerprint(os.fstat(rewalk_fd)) != root_before:
            raise _StrictJsonFailure
    finally:
        os.close(rewalk_fd)
    fingerprints = [status_fingerprint, summary_fingerprint]
    if history_fingerprint is not None:
        fingerprints.append(history_fingerprint)
    return _LoadedRootSnapshot(
        status=status,
        summary=summary,
        current_history=current_history,
        root_identity=root_before.identity,
        leaf_identities=tuple(item.identity for item in fingerprints),
        total_bytes=len(status_raw) + len(summary_raw) + history_bytes,
        history_bytes=history_bytes,
        root_fingerprint=root_before,
        status_fingerprint=status_fingerprint,
        summary_fingerprint=summary_fingerprint,
        history_fingerprint=history_fingerprint,
    )


def _verify_root_snapshot(
    canonical: str,
    snapshot: _LoadedRootSnapshot,
) -> None:
    root_fd = _open_canonical_root(canonical)
    try:
        if _root_fingerprint(os.fstat(root_fd)) != snapshot.root_fingerprint:
            raise _StrictJsonFailure
        _verify_leaf(root_fd, _STATUS_NAME, snapshot.status_fingerprint)
        _verify_leaf(root_fd, _SUMMARY_NAME, snapshot.summary_fingerprint)
        if snapshot.history_fingerprint is None:
            _verify_leaf_absent(root_fd, _HISTORY_NAME)
        else:
            _verify_leaf(root_fd, _HISTORY_NAME, snapshot.history_fingerprint)
        if _root_fingerprint(os.fstat(root_fd)) != snapshot.root_fingerprint:
            raise _StrictJsonFailure
    finally:
        os.close(root_fd)


def _canonical_root(root: object) -> str:
    value = os.fspath(root)  # type: ignore[call-overload]
    if (
        type(value) is not str
        or not value
        or "\x00" in value
        or not value.startswith("/")
        or value.startswith("//")
        or value == "/"
        or os.path.normpath(value) != value
    ):
        raise _StrictJsonFailure
    parts = value.split("/")[1:]
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise _StrictJsonFailure
    return value


def _open_canonical_root(canonical: str) -> int:
    flags = _directory_flags()
    current = os.open("/", flags)
    try:
        for component in canonical.split("/")[1:]:
            child = os.open(component, flags, dir_fd=current)
            os.close(current)
            current = child
        if not stat.S_ISDIR(os.fstat(current).st_mode):
            raise _StrictJsonFailure
        return current
    except BaseException:
        os.close(current)
        raise


def _directory_flags() -> int:
    required = ("O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC")
    if any(not hasattr(os, name) for name in required):
        raise _StrictJsonFailure
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _leaf_flags() -> int:
    required = ("O_NOFOLLOW", "O_NONBLOCK", "O_CLOEXEC")
    if any(not hasattr(os, name) for name in required):
        raise _StrictJsonFailure
    return os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


def _read_required_leaf(
    root_fd: int,
    name: str,
    *,
    limit: int,
) -> tuple[bytes, _FileFingerprint]:
    fd = os.open(name, _leaf_flags(), dir_fd=root_fd)
    try:
        return _read_open_leaf(fd, limit=limit)
    finally:
        os.close(fd)


def _read_optional_leaf(
    root_fd: int,
    name: str,
    *,
    limit: int,
) -> tuple[bytes, _FileFingerprint] | None:
    try:
        fd = os.open(name, _leaf_flags(), dir_fd=root_fd)
    except OSError as error:
        if error.errno == errno.ENOENT:
            return None
        raise
    try:
        return _read_open_leaf(fd, limit=limit)
    finally:
        os.close(fd)


def _read_open_leaf(fd: int, *, limit: int) -> tuple[bytes, _FileFingerprint]:
    before = _file_fingerprint(os.fstat(fd))
    if not stat.S_ISREG(before.mode) or before.links != 1 or before.size > limit:
        raise _StrictJsonFailure
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(fd, min(_READ_CHUNK_BYTES, limit + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > limit:
            raise _StrictJsonFailure
    after = _file_fingerprint(os.fstat(fd))
    if after != before or total != before.size:
        raise _StrictJsonFailure
    return b"".join(chunks), before


def _verify_leaf(
    root_fd: int,
    name: str,
    expected: _FileFingerprint,
) -> None:
    fd = os.open(name, _leaf_flags(), dir_fd=root_fd)
    try:
        if _file_fingerprint(os.fstat(fd)) != expected:
            raise _StrictJsonFailure
    finally:
        os.close(fd)


def _verify_leaf_absent(root_fd: int, name: str) -> None:
    try:
        fd = os.open(name, _leaf_flags(), dir_fd=root_fd)
    except OSError as error:
        if error.errno == errno.ENOENT:
            return
        raise
    os.close(fd)
    raise _StrictJsonFailure


def _file_fingerprint(value: os.stat_result) -> _FileFingerprint:
    return _FileFingerprint(
        identity=_FileIdentity(value.st_dev, value.st_ino),
        mode=value.st_mode,
        size=value.st_size,
        links=value.st_nlink,
        modified_ns=value.st_mtime_ns,
        changed_ns=value.st_ctime_ns,
    )


def _root_fingerprint(value: os.stat_result) -> _RootFingerprint:
    if not stat.S_ISDIR(value.st_mode):
        raise _StrictJsonFailure
    return _RootFingerprint(
        identity=_FileIdentity(value.st_dev, value.st_ino),
        mode=value.st_mode,
        modified_ns=value.st_mtime_ns,
        changed_ns=value.st_ctime_ns,
    )


def _parse_json_object(raw: bytes) -> Mapping[str, Any]:
    value = _parse_json(raw)
    if type(value) is not dict:
        raise _StrictJsonFailure
    return value


def _parse_json_lines(
    raw: bytes,
    *,
    record_cap: int,
) -> tuple[Mapping[str, Any], ...]:
    if not raw.endswith(b"\n") or b"\r" in raw:
        raise _StrictJsonFailure
    lines = raw[:-1].split(b"\n")
    if not lines or len(lines) > record_cap:
        raise _StrictJsonFailure
    records: list[Mapping[str, Any]] = []
    for line in lines:
        if not line or len(line) + 1 > MAX_RESEARCH_HISTORY_LINE_BYTES:
            raise _StrictJsonFailure
        value = _parse_json(line)
        if type(value) is not dict:
            raise _StrictJsonFailure
        records.append(value)
    return tuple(records)


def _parse_json(raw: bytes) -> Any:
    text = raw.decode("utf-8")
    return json.loads(
        text,
        object_pairs_hook=_mapping_without_duplicates,
        parse_constant=_reject_json_constant,
        parse_float=_finite_json_float,
    )


def _mapping_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _StrictJsonFailure
        result[key] = value
    return result


def _reject_json_constant(_token: str) -> NoReturn:
    raise _StrictJsonFailure


def _finite_json_float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise _StrictJsonFailure
    return value


def _validate_snapshot_set(
    snapshots: tuple[_LoadedRootSnapshot, ...],
) -> None:
    if len(snapshots) != 10:
        raise _StrictJsonFailure
    root_identities = [snapshot.root_identity for snapshot in snapshots]
    if len(set(root_identities)) != len(root_identities):
        raise _StrictJsonFailure
    leaf_identities = [
        identity for snapshot in snapshots for identity in snapshot.leaf_identities
    ]
    if len(set(leaf_identities)) != len(leaf_identities):
        raise _StrictJsonFailure
    if sum(snapshot.total_bytes for snapshot in snapshots) > _ALL_ARTIFACTS_MAX_BYTES:
        raise _StrictJsonFailure
    if (
        sum(snapshot.history_bytes for snapshot in snapshots)
        > MAX_RESEARCH_HISTORY_TOTAL_BYTES
    ):
        raise _StrictJsonFailure


def _fail_load() -> NoReturn:
    raise ResearchEffectivenessInputError(_LOAD_ERROR)
