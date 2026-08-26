"""Bounded no-follow reads anchored at the private M32 manifest directory."""

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
    MAX_RESEARCH_HISTORY_DEPTH,
    MAX_RESEARCH_HISTORY_FILE_BYTES,
    MAX_RESEARCH_HISTORY_FILES,
    MAX_RESEARCH_HISTORY_LINE_BYTES,
    MAX_RESEARCH_HISTORY_RECORDS,
    MAX_RESEARCH_HISTORY_TOTAL_BYTES,
    _render,
    normalize_research_history_record,
)

from .study_manifest_io_primitives import (
    _absolute_parts,
    _directory_fingerprint,
    _directory_flags,
    _DirectoryFingerprint,
    _file_fingerprint,
    _FileFingerprint,
    _Identity,
    _leaf_flags,
    _parts_overlap,
    _relative_parts,
    _StudyManifestIoError,
)

_MANIFEST_MAX_BYTES = 16 << 20
_STATUS_MAX_BYTES = 8 << 20
_SUMMARY_MAX_BYTES = 32 << 20
_CONTROLS_MAX_BYTES = 1 << 20
_CODE_LIMITS_MAX_BYTES = 4096
_RESOURCE_ENVELOPE_MAX_BYTES = 4096
_ROOT_TOTAL_MAX_BYTES = 256 << 20
_CURRENT_HISTORY_TOTAL_MAX_BYTES = 64 << 20
_READ_CHUNK_BYTES = 64 << 10

_STATUS_NAME = "status.json"
_SUMMARY_NAME = "campaign_summary.json"
_CURRENT_HISTORY_NAME = "research_history.jsonl"
_CONTROLS_NAME = "initial_screening_study_controls.json"
_CODE_LIMITS_NAME = "code_research_limits.json"
_RESOURCE_ENVELOPE_NAME = "resource_envelope.json"


@dataclass(frozen=True, repr=False)
class _FileSnapshot:
    name: str
    raw: bytes
    fingerprint: _FileFingerprint


@dataclass(frozen=True, repr=False)
class _RelativeFileSnapshot:
    token: str
    directory_chain: tuple[_DirectoryFingerprint, ...]
    leaf: _FileSnapshot


@dataclass(frozen=True, repr=False)
class _ManifestBundle:
    """One held manifest-parent anchor and its detached manifest value."""

    manifest_path: str
    parent_parts: tuple[str, ...]
    parent_chain: tuple[_DirectoryFingerprint, ...]
    parent_fd: int
    manifest: _FileSnapshot
    value: Any

    def __repr__(self) -> str:
        return "_ManifestBundle(<redacted>)"


@dataclass(frozen=True, repr=False)
class _HistoryBasis:
    """Detached normalized records for one ordered manifest block."""

    available: bool
    records: tuple[Mapping[str, Any], ...]
    files: tuple[_RelativeFileSnapshot, ...]

    def __repr__(self) -> str:
        return "_HistoryBasis(<redacted>)"


@dataclass(frozen=True, repr=False)
class _HistoryLoad:
    bases: tuple[_HistoryBasis, ...]
    unique_files: tuple[_RelativeFileSnapshot, ...]

    def __repr__(self) -> str:
        return "_HistoryLoad(<redacted>)"


@dataclass(frozen=True, repr=False)
class _RootSnapshot:
    """Six-leaf snapshot from one held private outcome root descriptor."""

    token: str
    directory_chain: tuple[_DirectoryFingerprint, ...]
    root_fingerprint: _DirectoryFingerprint
    status: Mapping[str, Any]
    summary: Mapping[str, Any]
    current_history: tuple[Mapping[str, Any], ...]
    controls: Mapping[str, Any]
    code_limits: Mapping[str, Any]
    resource_envelope: Mapping[str, Any]
    status_leaf: _FileSnapshot
    summary_leaf: _FileSnapshot
    history_leaf: _FileSnapshot | None
    controls_leaf: _FileSnapshot
    code_limits_leaf: _FileSnapshot
    resource_envelope_leaf: _FileSnapshot
    total_bytes: int
    history_bytes: int

    def __repr__(self) -> str:
        return "_RootSnapshot(<redacted>)"

    @property
    def leaf_identities(self) -> tuple[_Identity, ...]:
        leaves = [
            self.status_leaf,
            self.summary_leaf,
            self.controls_leaf,
            self.code_limits_leaf,
            self.resource_envelope_leaf,
        ]
        if self.history_leaf is not None:
            leaves.append(self.history_leaf)
        return tuple(leaf.fingerprint.identity for leaf in leaves)


def _open_manifest_bundle(manifest_path: object) -> _ManifestBundle:
    """Open one exact absolute manifest path and retain its parent anchor."""

    if type(manifest_path) is not str:
        raise _StudyManifestIoError
    path_value = manifest_path
    parts = _absolute_parts(path_value)
    parent_parts = parts[:-1]
    parent_fd, parent_chain = _open_absolute_directory(parent_parts)
    try:
        manifest = _read_required_leaf(
            parent_fd,
            parts[-1],
            limit=_MANIFEST_MAX_BYTES,
        )
        value = _parse_json(manifest.raw)
        if _directory_fingerprint(os.fstat(parent_fd)) != parent_chain[-1]:
            raise _StudyManifestIoError
        return _ManifestBundle(
            manifest_path=path_value,
            parent_parts=parent_parts,
            parent_chain=parent_chain,
            parent_fd=parent_fd,
            manifest=manifest,
            value=value,
        )
    except BaseException:
        os.close(parent_fd)
        raise


def _close_manifest_bundle(bundle: _ManifestBundle) -> None:
    if type(bundle) is not _ManifestBundle:
        raise _StudyManifestIoError
    os.close(bundle.parent_fd)


def _load_history_bases(
    bundle: _ManifestBundle,
    *,
    expected_problem_id: str,
    declarations: tuple[tuple[bool, tuple[str, ...]], ...],
) -> _HistoryLoad:
    """Load and normalize all five manifest-owned replay declarations."""

    if (
        type(bundle) is not _ManifestBundle
        or type(expected_problem_id) is not str
        or type(declarations) is not tuple
        or len(declarations) != 5
    ):
        raise _StudyManifestIoError
    cache: dict[str, tuple[_RelativeFileSnapshot, tuple[Mapping[str, Any], ...]]] = {}
    identities: dict[_Identity, str] = {}
    bases: list[_HistoryBasis] = []
    unique_total = 0
    for declaration in declarations:
        basis, added = _load_one_history_basis(
            bundle,
            expected_problem_id=expected_problem_id,
            declaration=declaration,
            cache=cache,
            identities=identities,
            remaining=MAX_RESEARCH_HISTORY_TOTAL_BYTES - unique_total,
        )
        bases.append(basis)
        unique_total += added
    return _HistoryLoad(tuple(bases), tuple(item[0] for item in cache.values()))


def _load_one_history_basis(
    bundle: _ManifestBundle,
    *,
    expected_problem_id: str,
    declaration: tuple[bool, tuple[str, ...]],
    cache: dict[
        str,
        tuple[_RelativeFileSnapshot, tuple[Mapping[str, Any], ...]],
    ],
    identities: dict[_Identity, str],
    remaining: int,
) -> tuple[_HistoryBasis, int]:
    available, files = declaration
    if type(available) is not bool or type(files) is not tuple:
        raise _StudyManifestIoError
    if not available:
        if files:
            raise _StudyManifestIoError
        return _HistoryBasis(False, (), ()), 0
    if len(files) > MAX_RESEARCH_HISTORY_FILES:
        raise _StudyManifestIoError
    records: list[Mapping[str, Any]] = []
    snapshots: list[_RelativeFileSnapshot] = []
    block_identities: set[_Identity] = set()
    added = 0
    for token in files:
        cached, file_bytes = _load_cached_history_file(
            bundle,
            token=token,
            expected_problem_id=expected_problem_id,
            cache=cache,
            identities=identities,
            remaining=remaining - added,
        )
        snapshot, file_records = cached
        identity = snapshot.leaf.fingerprint.identity
        if identity in block_identities:
            raise _StudyManifestIoError
        block_identities.add(identity)
        snapshots.append(snapshot)
        records.extend(file_records)
        added += file_bytes
        if len(records) > MAX_RESEARCH_HISTORY_RECORDS:
            raise _StudyManifestIoError
    return _HistoryBasis(True, tuple(records), tuple(snapshots)), added


def _load_cached_history_file(
    bundle: _ManifestBundle,
    *,
    token: str,
    expected_problem_id: str,
    cache: dict[
        str,
        tuple[_RelativeFileSnapshot, tuple[Mapping[str, Any], ...]],
    ],
    identities: dict[_Identity, str],
    remaining: int,
) -> tuple[
    tuple[_RelativeFileSnapshot, tuple[Mapping[str, Any], ...]],
    int,
]:
    _relative_parts(token, required_suffix=".jsonl")
    cached = cache.get(token)
    if cached is not None:
        return cached, 0
    snapshot = _read_relative_file(
        bundle,
        token,
        limit=min(MAX_RESEARCH_HISTORY_FILE_BYTES, remaining),
    )
    if not snapshot.leaf.raw:
        raise _StudyManifestIoError
    records = _normalize_history_file(
        snapshot.leaf.raw,
        expected_problem_id=expected_problem_id,
    )
    identity = snapshot.leaf.fingerprint.identity
    if identity in identities:
        raise _StudyManifestIoError
    identities[identity] = token
    cached = (snapshot, records)
    cache[token] = cached
    return cached, len(snapshot.leaf.raw)


def _load_root_snapshots(
    bundle: _ManifestBundle,
    *,
    roots: tuple[tuple[str, int], ...],
) -> tuple[_RootSnapshot, ...]:
    """Load all ten six-leaf roots before any decoded-artifact validation."""

    if (
        type(bundle) is not _ManifestBundle
        or type(roots) is not tuple
        or len(roots) != 10
    ):
        raise _StudyManifestIoError
    snapshots: list[_RootSnapshot] = []
    total = 0
    history_total = 0
    for token, record_cap in roots:
        snapshot = _load_one_root(
            bundle,
            token=token,
            record_cap=record_cap,
            total_limit=_ROOT_TOTAL_MAX_BYTES - total,
            history_limit=_CURRENT_HISTORY_TOTAL_MAX_BYTES - history_total,
        )
        snapshots.append(snapshot)
        total += snapshot.total_bytes
        history_total += snapshot.history_bytes
    result = tuple(snapshots)
    _validate_root_set(result)
    return result


def _validate_bundle_paths(
    *,
    roots: tuple[str, ...],
    history_files: tuple[str, ...],
) -> None:
    if type(roots) is not tuple or len(roots) != 10 or type(history_files) is not tuple:
        raise _StudyManifestIoError
    root_parts = tuple(_relative_parts(token) for token in roots)
    history_parts = tuple(
        _relative_parts(token, required_suffix=".jsonl") for token in history_files
    )
    for index, left in enumerate(root_parts):
        for right in root_parts[index + 1 :]:
            if _parts_overlap(left, right):
                raise _StudyManifestIoError
    for root in root_parts:
        if any(_parts_overlap(root, history) for history in history_parts):
            raise _StudyManifestIoError


def _validate_identity_set(
    bundle: _ManifestBundle,
    histories: _HistoryLoad,
    roots: tuple[_RootSnapshot, ...],
) -> None:
    if (
        type(bundle) is not _ManifestBundle
        or type(histories) is not _HistoryLoad
        or type(roots) is not tuple
        or len(roots) != 10
    ):
        raise _StudyManifestIoError
    file_identities = [bundle.manifest.fingerprint.identity]
    file_identities.extend(
        item.leaf.fingerprint.identity for item in histories.unique_files
    )
    file_identities.extend(
        identity for root in roots for identity in root.leaf_identities
    )
    root_identities = [root.root_fingerprint.identity for root in roots]
    if (
        len(file_identities) != len(set(file_identities))
        or len(root_identities) != len(set(root_identities))
        or set(file_identities).intersection(root_identities)
    ):
        raise _StudyManifestIoError


def _verify_study_bundle(
    bundle: _ManifestBundle,
    histories: _HistoryLoad,
    roots: tuple[_RootSnapshot, ...],
) -> None:
    final_fd, final_chain = _open_absolute_directory(bundle.parent_parts)
    try:
        if final_chain != bundle.parent_chain:
            raise _StudyManifestIoError
        final_bundle = _ManifestBundle(
            manifest_path=bundle.manifest_path,
            parent_parts=bundle.parent_parts,
            parent_chain=final_chain,
            parent_fd=final_fd,
            manifest=bundle.manifest,
            value=bundle.value,
        )
        _verify_open_leaf(final_fd, bundle.manifest, compare_bytes=True)
        for history_snapshot in histories.unique_files:
            _verify_relative_file(final_bundle, history_snapshot)
        for root_snapshot in roots:
            _verify_root_snapshot(final_bundle, root_snapshot)
        _verify_open_leaf(final_fd, bundle.manifest, compare_bytes=True)
        if _directory_fingerprint(os.fstat(final_fd)) != final_chain[-1]:
            raise _StudyManifestIoError
    finally:
        os.close(final_fd)
    if _directory_fingerprint(os.fstat(bundle.parent_fd)) != bundle.parent_chain[-1]:
        raise _StudyManifestIoError
    _verify_final_manifest_rewalk(bundle)
    _validate_identity_set(bundle, histories, roots)


def _verify_final_manifest_rewalk(bundle: _ManifestBundle) -> None:
    final_fd, final_chain = _open_absolute_directory(bundle.parent_parts)
    try:
        if final_chain != bundle.parent_chain:
            raise _StudyManifestIoError
        _verify_open_leaf(final_fd, bundle.manifest, compare_bytes=True)
        if _directory_fingerprint(os.fstat(final_fd)) != final_chain[-1]:
            raise _StudyManifestIoError
    finally:
        os.close(final_fd)


def _load_one_root(
    bundle: _ManifestBundle,
    *,
    token: str,
    record_cap: int,
    total_limit: int,
    history_limit: int,
) -> _RootSnapshot:
    if (
        type(record_cap) is not int
        or record_cap <= 0
        or type(total_limit) is not int
        or total_limit < 0
        or type(history_limit) is not int
        or history_limit < 0
    ):
        raise _StudyManifestIoError
    root_fd, chain = _open_relative_directory(bundle, token)
    try:
        root_before = _directory_fingerprint(os.fstat(root_fd))
        _validate_private_root(root_before)
        remaining = total_limit
        status_leaf = _read_required_leaf(
            root_fd,
            _STATUS_NAME,
            limit=min(_STATUS_MAX_BYTES, remaining),
        )
        remaining -= len(status_leaf.raw)
        summary_leaf = _read_required_leaf(
            root_fd,
            _SUMMARY_NAME,
            limit=min(_SUMMARY_MAX_BYTES, remaining),
        )
        remaining -= len(summary_leaf.raw)
        history_leaf = _read_optional_leaf(
            root_fd,
            _CURRENT_HISTORY_NAME,
            limit=min(
                MAX_RESEARCH_HISTORY_FILE_BYTES,
                remaining,
                history_limit,
            ),
        )
        history_bytes = 0 if history_leaf is None else len(history_leaf.raw)
        remaining -= history_bytes
        controls_leaf = _read_required_leaf(
            root_fd,
            _CONTROLS_NAME,
            limit=min(_CONTROLS_MAX_BYTES, remaining),
            private=True,
        )
        remaining -= len(controls_leaf.raw)
        code_limits_leaf = _read_required_leaf(
            root_fd,
            _CODE_LIMITS_NAME,
            limit=min(_CODE_LIMITS_MAX_BYTES, remaining),
        )
        remaining -= len(code_limits_leaf.raw)
        resource_leaf = _read_required_leaf(
            root_fd,
            _RESOURCE_ENVELOPE_NAME,
            limit=min(_RESOURCE_ENVELOPE_MAX_BYTES, remaining),
        )
        status = _parse_json_object(status_leaf.raw)
        summary = _parse_json_object(summary_leaf.raw)
        controls = _parse_json_object(controls_leaf.raw)
        code_limits = _parse_json_object(code_limits_leaf.raw)
        resource = _parse_json_object(resource_leaf.raw)
        if history_leaf is None:
            if summary.get("steps") != []:
                raise _StudyManifestIoError
            current_history: tuple[Mapping[str, Any], ...] = ()
        else:
            if not history_leaf.raw:
                raise _StudyManifestIoError
            current_history = _parse_json_lines(
                history_leaf.raw,
                record_cap=min(record_cap, MAX_RESEARCH_HISTORY_RECORDS),
            )
        leaves = (
            status_leaf,
            summary_leaf,
            history_leaf,
            controls_leaf,
            code_limits_leaf,
            resource_leaf,
        )
        for leaf in leaves:
            if leaf is None:
                _verify_leaf_absent(root_fd, _CURRENT_HISTORY_NAME)
            else:
                _verify_open_leaf(root_fd, leaf)
        if _directory_fingerprint(os.fstat(root_fd)) != root_before:
            raise _StudyManifestIoError
    finally:
        os.close(root_fd)
    total_bytes = sum(len(leaf.raw) for leaf in leaves if leaf is not None)
    return _RootSnapshot(
        token=token,
        directory_chain=chain,
        root_fingerprint=root_before,
        status=status,
        summary=summary,
        current_history=current_history,
        controls=controls,
        code_limits=code_limits,
        resource_envelope=resource,
        status_leaf=status_leaf,
        summary_leaf=summary_leaf,
        history_leaf=history_leaf,
        controls_leaf=controls_leaf,
        code_limits_leaf=code_limits_leaf,
        resource_envelope_leaf=resource_leaf,
        total_bytes=total_bytes,
        history_bytes=history_bytes,
    )


def _validate_root_set(snapshots: tuple[_RootSnapshot, ...]) -> None:
    if len(snapshots) != 10:
        raise _StudyManifestIoError
    roots = [snapshot.root_fingerprint.identity for snapshot in snapshots]
    leaves = [
        identity for snapshot in snapshots for identity in snapshot.leaf_identities
    ]
    if len(roots) != len(set(roots)) or len(leaves) != len(set(leaves)):
        raise _StudyManifestIoError
    if sum(item.total_bytes for item in snapshots) > _ROOT_TOTAL_MAX_BYTES:
        raise _StudyManifestIoError
    if sum(item.history_bytes for item in snapshots) > _CURRENT_HISTORY_TOTAL_MAX_BYTES:
        raise _StudyManifestIoError


def _read_relative_file(
    bundle: _ManifestBundle,
    token: str,
    *,
    limit: int,
) -> _RelativeFileSnapshot:
    parts = _relative_parts(token)
    directory_fd, chain = _open_relative_parts(bundle, parts[:-1])
    try:
        leaf = _read_required_leaf(directory_fd, parts[-1], limit=limit)
        if _directory_fingerprint(os.fstat(directory_fd)) != chain[-1]:
            raise _StudyManifestIoError
        return _RelativeFileSnapshot(token, chain, leaf)
    finally:
        os.close(directory_fd)


def _verify_relative_file(
    bundle: _ManifestBundle,
    snapshot: _RelativeFileSnapshot,
) -> None:
    parts = _relative_parts(snapshot.token)
    directory_fd, chain = _open_relative_parts(bundle, parts[:-1])
    try:
        if chain != snapshot.directory_chain:
            raise _StudyManifestIoError
        _verify_open_leaf(directory_fd, snapshot.leaf, compare_bytes=True)
        if _directory_fingerprint(os.fstat(directory_fd)) != chain[-1]:
            raise _StudyManifestIoError
    finally:
        os.close(directory_fd)


def _verify_root_snapshot(
    bundle: _ManifestBundle,
    snapshot: _RootSnapshot,
) -> None:
    root_fd, chain = _open_relative_directory(bundle, snapshot.token)
    try:
        if chain != snapshot.directory_chain:
            raise _StudyManifestIoError
        current = _directory_fingerprint(os.fstat(root_fd))
        _validate_private_root(current)
        if current != snapshot.root_fingerprint:
            raise _StudyManifestIoError
        for leaf in (
            snapshot.status_leaf,
            snapshot.summary_leaf,
            snapshot.controls_leaf,
            snapshot.code_limits_leaf,
            snapshot.resource_envelope_leaf,
        ):
            _verify_open_leaf(root_fd, leaf, compare_bytes=True)
        if snapshot.history_leaf is None:
            _verify_leaf_absent(root_fd, _CURRENT_HISTORY_NAME)
        else:
            _verify_open_leaf(root_fd, snapshot.history_leaf, compare_bytes=True)
        if _directory_fingerprint(os.fstat(root_fd)) != snapshot.root_fingerprint:
            raise _StudyManifestIoError
    finally:
        os.close(root_fd)


def _open_absolute_directory(
    parts: tuple[str, ...],
) -> tuple[int, tuple[_DirectoryFingerprint, ...]]:
    current = os.open("/", _directory_flags())
    fingerprints = [_directory_fingerprint(os.fstat(current))]
    try:
        for component in parts:
            child = os.open(component, _directory_flags(), dir_fd=current)
            os.close(current)
            current = child
            fingerprints.append(_directory_fingerprint(os.fstat(current)))
        return current, tuple(fingerprints)
    except BaseException:
        os.close(current)
        raise


def _open_relative_directory(
    bundle: _ManifestBundle,
    token: str,
) -> tuple[int, tuple[_DirectoryFingerprint, ...]]:
    return _open_relative_parts(bundle, _relative_parts(token))


def _open_relative_parts(
    bundle: _ManifestBundle,
    parts: tuple[str, ...],
) -> tuple[int, tuple[_DirectoryFingerprint, ...]]:
    current = os.dup(bundle.parent_fd)
    fingerprints = [_directory_fingerprint(os.fstat(current))]
    if fingerprints[0] != bundle.parent_chain[-1]:
        os.close(current)
        raise _StudyManifestIoError
    try:
        for component in parts:
            child = os.open(component, _directory_flags(), dir_fd=current)
            os.close(current)
            current = child
            fingerprints.append(_directory_fingerprint(os.fstat(current)))
        return current, tuple(fingerprints)
    except BaseException:
        os.close(current)
        raise


def _read_required_leaf(
    directory_fd: int,
    name: str,
    *,
    limit: int,
    private: bool = False,
) -> _FileSnapshot:
    if type(limit) is not int or limit < 0:
        raise _StudyManifestIoError
    fd = os.open(name, _leaf_flags(), dir_fd=directory_fd)
    try:
        raw, fingerprint = _read_open_fd(fd, limit=limit, private=private)
        return _FileSnapshot(name, raw, fingerprint)
    finally:
        os.close(fd)


def _read_optional_leaf(
    directory_fd: int,
    name: str,
    *,
    limit: int,
) -> _FileSnapshot | None:
    if type(limit) is not int or limit < 0:
        raise _StudyManifestIoError
    try:
        fd = os.open(name, _leaf_flags(), dir_fd=directory_fd)
    except OSError as error:
        if error.errno == errno.ENOENT:
            return None
        raise
    try:
        raw, fingerprint = _read_open_fd(fd, limit=limit)
        return _FileSnapshot(name, raw, fingerprint)
    finally:
        os.close(fd)


def _read_open_fd(
    fd: int,
    *,
    limit: int,
    private: bool = False,
) -> tuple[bytes, _FileFingerprint]:
    before = _file_fingerprint(os.fstat(fd))
    if not stat.S_ISREG(before.mode) or before.links != 1 or before.size > limit:
        raise _StudyManifestIoError
    if private and (before.owner != os.geteuid() or stat.S_IMODE(before.mode) != 0o600):
        raise _StudyManifestIoError
    chunks: list[bytes] = []
    total = 0
    while True:
        amount = min(_READ_CHUNK_BYTES, limit + 1 - total)
        if amount <= 0:
            raise _StudyManifestIoError
        chunk = os.read(fd, amount)
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > limit:
            raise _StudyManifestIoError
    after = _file_fingerprint(os.fstat(fd))
    if after != before or total != before.size:
        raise _StudyManifestIoError
    return b"".join(chunks), before


def _verify_open_leaf(
    directory_fd: int,
    snapshot: _FileSnapshot,
    *,
    compare_bytes: bool = False,
) -> None:
    fd = os.open(snapshot.name, _leaf_flags(), dir_fd=directory_fd)
    try:
        current = _file_fingerprint(os.fstat(fd))
        if current != snapshot.fingerprint:
            raise _StudyManifestIoError
        if compare_bytes:
            raw, fingerprint = _read_open_fd(
                fd,
                limit=len(snapshot.raw),
                private=(snapshot.name == _CONTROLS_NAME),
            )
            if fingerprint != snapshot.fingerprint or raw != snapshot.raw:
                raise _StudyManifestIoError
    finally:
        os.close(fd)


def _verify_leaf_absent(directory_fd: int, name: str) -> None:
    try:
        fd = os.open(name, _leaf_flags(), dir_fd=directory_fd)
    except OSError as error:
        if error.errno == errno.ENOENT:
            return
        raise
    os.close(fd)
    raise _StudyManifestIoError


def _normalize_history_file(
    raw: bytes,
    *,
    expected_problem_id: str,
) -> tuple[Mapping[str, Any], ...]:
    parsed = _parse_json_lines(raw, record_cap=MAX_RESEARCH_HISTORY_RECORDS)
    records: list[Mapping[str, Any]] = []
    lines = raw[:-1].split(b"\n")
    for line, value in zip(lines, parsed, strict=True):
        normalized = normalize_research_history_record(
            value,
            expected_problem_id=expected_problem_id,
        )
        if _render(normalized) != line + b"\n":
            raise _StudyManifestIoError
        records.append(normalized)
    return tuple(records)


def _parse_json_lines(
    raw: bytes,
    *,
    record_cap: int,
) -> tuple[Mapping[str, Any], ...]:
    if not raw or not raw.endswith(b"\n") or b"\r" in raw:
        raise _StudyManifestIoError
    lines = raw[:-1].split(b"\n")
    if not lines or len(lines) > record_cap:
        raise _StudyManifestIoError
    records: list[Mapping[str, Any]] = []
    for line in lines:
        if not line or len(line) + 1 > MAX_RESEARCH_HISTORY_LINE_BYTES:
            raise _StudyManifestIoError
        value = _parse_json(line)
        if type(value) is not dict:
            raise _StudyManifestIoError
        records.append(value)
    return tuple(records)


def _parse_json_object(raw: bytes) -> Mapping[str, Any]:
    value = _parse_json(raw)
    if type(value) is not dict:
        raise _StudyManifestIoError
    return value


def _parse_json(raw: bytes) -> Any:
    if not raw:
        raise _StudyManifestIoError
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_mapping_without_duplicates,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
        )
        _validate_json_depth(value, depth=0)
        return value
    except _StudyManifestIoError:
        raise
    except Exception as error:
        raise _StudyManifestIoError from error


def _validate_json_depth(value: Any, *, depth: int) -> None:
    if depth > MAX_RESEARCH_HISTORY_DEPTH:
        raise _StudyManifestIoError
    if value is None or type(value) in {str, bool, int}:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise _StudyManifestIoError
        return
    if type(value) is list:
        for item in value:
            _validate_json_depth(item, depth=depth + 1)
        return
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise _StudyManifestIoError
        for item in value.values():
            _validate_json_depth(item, depth=depth + 1)
        return
    raise _StudyManifestIoError


def _mapping_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _StudyManifestIoError
        result[key] = value
    return result


def _reject_constant(_token: str) -> NoReturn:
    raise _StudyManifestIoError


def _finite_float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise _StudyManifestIoError
    return value


def _validate_private_root(value: _DirectoryFingerprint) -> None:
    if value.owner != os.geteuid() or stat.S_IMODE(value.mode) != 0o700:
        raise _StudyManifestIoError


__all__: tuple[str, ...] = ()
