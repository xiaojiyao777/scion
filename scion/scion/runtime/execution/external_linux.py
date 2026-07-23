"""Descriptor-bound Linux primitives for the external installation owner.

The production adapter is intentionally narrow and is not wired into the
normal runtime.  It exposes only no-replace publication, detached mount-tree
clone/attach, mount flag changes, namespace identity, mount-ID acquisition,
and descriptor closure.  It has no rollback, deletion, overwrite, or unmount
surface.
"""

from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Callable, Protocol

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_RELATIVE_PATH_RE = re.compile(r"[^/\x00]+(?:/[^/\x00]+)*\Z")
_RENAME_NOREPLACE = 1
_AT_EMPTY_PATH = 0x1000
_OPEN_TREE_CLONE = 1
_OPEN_TREE_CLOEXEC = os.O_CLOEXEC
_MOVE_MOUNT_F_EMPTY_PATH = 0x00000004
_MS_RDONLY = 1
_MS_REMOUNT = 32
_MS_BIND = 4096
_MS_REC = 16384
_MS_PRIVATE = 1 << 18
_SYS_OPEN_TREE = 428
_SYS_MOVE_MOUNT = 429
_COPY_CHUNK = 1024 * 1024
_FDINFO_LIMIT = 64 * 1024


class ExternalLinuxError(RuntimeError):
    """A Linux primitive or retained identity is invalid."""


class CanonicalImportReceiptError(ExternalLinuxError):
    """Immutable import receipt bytes are not canonical."""


class TreeImportHold(ExternalLinuxError):
    """Import failed after reserving, or while observing, a staging leaf."""

    def __init__(self, staging_leaf: str) -> None:
        self.staging_leaf = staging_leaf
        super().__init__(f"immutable tree import is held at {staging_leaf}")


class LinuxMutationHold(ExternalLinuxError):
    """An external mutation may have happened and must not be retried."""


def _canonical_json(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise CanonicalImportReceiptError("receipt is not canonical JSON data") from exc


def _decode_canonical_json(raw: bytes, *, label: str) -> object:
    if type(raw) is not bytes:
        raise TypeError(f"{label} must be exact bytes")

    def mapping(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{label} contains a duplicate field")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=mapping,
            parse_float=lambda _value: (_ for _ in ()).throw(
                ValueError(f"{label} contains a float")
            ),
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"{label} contains {token}")
            ),
        )
    except (UnicodeError, ValueError, TypeError) as exc:
        raise CanonicalImportReceiptError(f"{label} is not canonical JSON") from exc
    if _canonical_json(value) != raw:
        raise CanonicalImportReceiptError(f"{label} bytes are not canonical")
    return value


def _exact_fields(
    value: object,
    expected: frozenset[str],
    *,
    label: str,
) -> dict[str, object]:
    if (
        type(value) is not dict
        or frozenset(value) != expected
        or any(type(key) is not str for key in value)
    ):
        raise CanonicalImportReceiptError(f"{label} fields differ")
    return value


def _text(value: object, *, field: str) -> str:
    if type(value) is not str or not value:
        raise ExternalLinuxError(f"{field} must be nonempty exact text")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise ExternalLinuxError(f"{field} is not UTF-8") from exc
    if any(byte < 0x20 or byte == 0x7F for byte in encoded):
        raise ExternalLinuxError(f"{field} contains a control character")
    return value


def _sha256(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if _SHA256_RE.fullmatch(text) is None:
        raise ExternalLinuxError(f"{field} is not canonical SHA-256")
    return text


def _uint(value: object, *, field: str, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if type(value) is not int or value < minimum:
        raise ExternalLinuxError(f"{field} is not an integer >= {minimum}")
    return value


def _mode(value: object, *, field: str) -> int:
    if type(value) is not int or not 0 <= value <= 0o7777:
        raise ExternalLinuxError(f"{field} is not a canonical permission mode")
    return value


def _leaf(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if text in {".", ".."} or "/" in text or "\x00" in text:
        raise ExternalLinuxError(f"{field} is not one canonical leaf")
    return text


def _relative_path(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    path = PurePosixPath(text)
    if (
        _RELATIVE_PATH_RE.fullmatch(text) is None
        or path.is_absolute()
        or str(path) != text
        or any(part in {".", ".."} for part in path.parts)
    ):
        raise ExternalLinuxError(f"{field} is not a canonical relative path")
    return text


def _absolute_path(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    path = PurePosixPath(text)
    if (
        not path.is_absolute()
        or str(path) != text
        or text.startswith("//")
        or ".." in path.parts
    ):
        raise ExternalLinuxError(f"{field} is not a canonical absolute path")
    return text


def _require_root() -> None:
    euid = os.geteuid()
    if type(euid) is not int or euid != 0:
        raise PermissionError("external Linux mutation requires effective UID 0")


@dataclass(frozen=True, slots=True)
class FileIdentity:
    device: int
    inode: int
    mode: int
    uid: int
    gid: int
    link_count: int
    size: int

    def __post_init__(self) -> None:
        _uint(self.device, field="identity.device")
        _uint(self.inode, field="identity.inode", positive=True)
        if type(self.mode) is not int or self.mode < 0:
            raise ExternalLinuxError("identity.mode is not a nonnegative integer")
        _uint(self.uid, field="identity.uid")
        _uint(self.gid, field="identity.gid")
        _uint(self.link_count, field="identity.link_count", positive=True)
        _uint(self.size, field="identity.size")

    @classmethod
    def from_stat(cls, metadata: os.stat_result) -> "FileIdentity":
        return cls(
            device=metadata.st_dev,
            inode=metadata.st_ino,
            mode=metadata.st_mode,
            uid=metadata.st_uid,
            gid=metadata.st_gid,
            link_count=metadata.st_nlink,
            size=metadata.st_size,
        )

    def to_mapping(self) -> dict[str, int]:
        return {
            "device": self.device,
            "inode": self.inode,
            "mode": self.mode,
            "uid": self.uid,
            "gid": self.gid,
            "link_count": self.link_count,
            "size": self.size,
        }

    @classmethod
    def from_mapping(cls, value: object, *, label: str) -> "FileIdentity":
        copied = _exact_fields(
            value,
            frozenset(
                {
                    "device",
                    "inode",
                    "mode",
                    "uid",
                    "gid",
                    "link_count",
                    "size",
                }
            ),
            label=label,
        )
        return cls(
            device=copied["device"],
            inode=copied["inode"],
            mode=copied["mode"],
            uid=copied["uid"],
            gid=copied["gid"],
            link_count=copied["link_count"],
            size=copied["size"],
        )


@dataclass(frozen=True, slots=True)
class _StableStat:
    identity: FileIdentity
    mtime_ns: int
    ctime_ns: int

    @classmethod
    def from_stat(cls, metadata: os.stat_result) -> "_StableStat":
        return cls(
            identity=FileIdentity.from_stat(metadata),
            mtime_ns=metadata.st_mtime_ns,
            ctime_ns=metadata.st_ctime_ns,
        )


def _require_directory(metadata: os.stat_result, *, field: str) -> None:
    if not stat.S_ISDIR(metadata.st_mode):
        raise ExternalLinuxError(f"{field} is not a directory")


def _same_directory_identity(expected: FileIdentity, current: FileIdentity) -> bool:
    return (
        expected.device == current.device
        and expected.inode == current.inode
        and expected.mode == current.mode
        and expected.uid == current.uid
        and expected.gid == current.gid
        and expected.link_count == current.link_count
        and expected.size == current.size
    )


def _open_directory_at(parent_fd: int, leaf: str) -> int:
    return os.open(
        leaf,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        dir_fd=parent_fd,
    )


@dataclass(frozen=True, slots=True)
class PinnedComponent:
    name: str
    identity: FileIdentity

    def __post_init__(self) -> None:
        if type(self.name) is not str:
            raise TypeError("pinned component name must be exact text")
        if self.name != "/" and (
            not self.name or self.name in {".", ".."} or "/" in self.name
        ):
            raise ExternalLinuxError("pinned component name differs")
        if type(self.identity) is not FileIdentity:
            raise TypeError("pinned component identity must be exact FileIdentity")
        if not stat.S_ISDIR(self.identity.mode):
            raise ExternalLinuxError("pinned component is not a directory")


class PinnedDirectory:
    """Retain every no-follow descriptor in one absolute directory chain."""

    __slots__ = ("_path", "_fds", "_components", "_closed")

    def __init__(
        self,
        *,
        path: str,
        fds: tuple[int, ...],
        components: tuple[PinnedComponent, ...],
    ) -> None:
        if (
            type(fds) is not tuple
            or type(components) is not tuple
            or len(fds) != len(components)
            or not fds
        ):
            raise TypeError("pinned directory chain shape differs")
        self._path = _absolute_path(path, field="pinned path")
        self._fds = fds
        self._components = components
        self._closed = False

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("PinnedDirectory is final")

    @property
    def path(self) -> str:
        return self._path

    @property
    def fd(self) -> int:
        if self._closed:
            raise ExternalLinuxError("pinned directory is closed")
        return self._fds[-1]

    @property
    def components(self) -> tuple[PinnedComponent, ...]:
        return self._components

    def revalidate(self) -> None:
        if self._closed:
            raise ExternalLinuxError("pinned directory is closed")
        for index, (descriptor, component) in enumerate(
            zip(self._fds, self._components, strict=True)
        ):
            current = FileIdentity.from_stat(os.fstat(descriptor))
            if not _same_directory_identity(component.identity, current):
                raise ExternalLinuxError("retained directory identity drifted")
            if index:
                parent_fd = self._fds[index - 1]
                entry = FileIdentity.from_stat(
                    os.stat(
                        component.name,
                        dir_fd=parent_fd,
                        follow_symlinks=False,
                    )
                )
                if not _same_directory_identity(component.identity, entry):
                    raise ExternalLinuxError("current directory chain drifted")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        first_error: OSError | None = None
        for descriptor in reversed(self._fds):
            try:
                os.close(descriptor)
            except OSError as exc:
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error

    def __enter__(self) -> "PinnedDirectory":
        self.revalidate()
        return self

    def __exit__(self, *args: object) -> None:
        del args
        self.close()


def pin_absolute_directory(path: str) -> PinnedDirectory:
    """Open every absolute path component with O_DIRECTORY|O_NOFOLLOW."""

    canonical = _absolute_path(path, field="directory path")
    opened: list[int] = []
    components: list[PinnedComponent] = []
    try:
        root_fd = os.open(
            "/",
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        opened.append(root_fd)
        root_metadata = os.fstat(root_fd)
        _require_directory(root_metadata, field="filesystem root")
        components.append(
            PinnedComponent(name="/", identity=FileIdentity.from_stat(root_metadata))
        )
        current_fd = root_fd
        for part in PurePosixPath(canonical).parts[1:]:
            descriptor = _open_directory_at(
                current_fd, _leaf(part, field="path component")
            )
            opened.append(descriptor)
            metadata = os.fstat(descriptor)
            _require_directory(metadata, field="path component")
            identity = FileIdentity.from_stat(metadata)
            current_entry = FileIdentity.from_stat(
                os.stat(part, dir_fd=current_fd, follow_symlinks=False)
            )
            if current_entry != identity:
                raise ExternalLinuxError("directory component identity drifted")
            components.append(PinnedComponent(name=part, identity=identity))
            current_fd = descriptor
        result = PinnedDirectory(
            path=canonical,
            fds=tuple(opened),
            components=tuple(components),
        )
        result.revalidate()
        return result
    except Exception:
        for descriptor in reversed(opened):
            try:
                os.close(descriptor)
            except OSError:
                pass
        raise


@dataclass(frozen=True, slots=True)
class ImportEntry:
    path: str
    kind: str
    mode: int
    size: int
    sha256: str | None
    source_identity: FileIdentity
    destination_identity: FileIdentity

    def __post_init__(self) -> None:
        _relative_path(self.path, field="import entry path")
        if self.kind not in {"directory", "file"}:
            raise ExternalLinuxError("import entry kind differs")
        _mode(self.mode, field="import entry mode")
        _uint(self.size, field="import entry size")
        if self.kind == "file":
            _sha256(self.sha256, field="import entry sha256")
        elif self.sha256 is not None or self.size != 0:
            raise ExternalLinuxError("directory import entry payload differs")
        if (
            type(self.source_identity) is not FileIdentity
            or type(self.destination_identity) is not FileIdentity
        ):
            raise TypeError("import entry identities must be exact FileIdentity")

    def to_mapping(self) -> dict[str, object]:
        return {
            "path": self.path,
            "kind": self.kind,
            "mode": self.mode,
            "size": self.size,
            "sha256": self.sha256,
            "source_identity": self.source_identity.to_mapping(),
            "destination_identity": self.destination_identity.to_mapping(),
        }

    @classmethod
    def from_mapping(cls, value: object) -> "ImportEntry":
        copied = _exact_fields(
            value,
            frozenset(
                {
                    "path",
                    "kind",
                    "mode",
                    "size",
                    "sha256",
                    "source_identity",
                    "destination_identity",
                }
            ),
            label="import entry",
        )
        return cls(
            path=copied["path"],
            kind=copied["kind"],
            mode=copied["mode"],
            size=copied["size"],
            sha256=copied["sha256"],
            source_identity=FileIdentity.from_mapping(
                copied["source_identity"],
                label="import source identity",
            ),
            destination_identity=FileIdentity.from_mapping(
                copied["destination_identity"],
                label="import destination identity",
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class ImmutableTreeImportReceipt:
    staging_leaf: str
    target_uid: int
    target_gid: int
    source_root: FileIdentity
    staging_root: FileIdentity
    entries: tuple[ImportEntry, ...]
    tree_sha256: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "ImmutableTreeImportReceipt":
        del cls
        raise TypeError("ImmutableTreeImportReceipt must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("ImmutableTreeImportReceipt is final")

    @classmethod
    def create(
        cls,
        *,
        staging_leaf: str,
        target_uid: int,
        target_gid: int,
        source_root: FileIdentity,
        staging_root: FileIdentity,
        entries: tuple[ImportEntry, ...],
    ) -> "ImmutableTreeImportReceipt":
        if (
            type(source_root) is not FileIdentity
            or type(staging_root) is not FileIdentity
            or type(entries) is not tuple
            or any(type(entry) is not ImportEntry for entry in entries)
        ):
            raise TypeError("immutable import receipt inputs differ")
        ordered = tuple(sorted(entries, key=lambda item: item.path.encode("utf-8")))
        if ordered != entries or len({entry.path for entry in entries}) != len(entries):
            raise ExternalLinuxError("import entries are not unique and byte-sorted")
        inventory = {
            "schema": "scion.immutable-tree-inventory.v1",
            "entries": [entry.to_mapping() for entry in entries],
        }
        tree_sha256 = hashlib.sha256(_canonical_json(inventory)).hexdigest()
        value = {
            "schema": "scion.immutable-tree-import.v1",
            "staging_leaf": _leaf(staging_leaf, field="staging_leaf"),
            "target_uid": _uint(target_uid, field="target_uid"),
            "target_gid": _uint(target_gid, field="target_gid"),
            "source_root": source_root.to_mapping(),
            "staging_root": staging_root.to_mapping(),
            "entries": [entry.to_mapping() for entry in entries],
            "tree_sha256": tree_sha256,
        }
        return cls.from_bytes(_canonical_json(value))

    @classmethod
    def from_bytes(cls, raw: bytes) -> "ImmutableTreeImportReceipt":
        value = _exact_fields(
            _decode_canonical_json(raw, label="immutable tree import receipt"),
            frozenset(
                {
                    "schema",
                    "staging_leaf",
                    "target_uid",
                    "target_gid",
                    "source_root",
                    "staging_root",
                    "entries",
                    "tree_sha256",
                }
            ),
            label="immutable tree import receipt",
        )
        if value["schema"] != "scion.immutable-tree-import.v1":
            raise CanonicalImportReceiptError("immutable tree import schema differs")
        raw_entries = value["entries"]
        if type(raw_entries) is not list:
            raise CanonicalImportReceiptError("immutable tree entries are not an array")
        entries = tuple(ImportEntry.from_mapping(item) for item in raw_entries)
        if entries != tuple(
            sorted(entries, key=lambda item: item.path.encode("utf-8"))
        ) or len({entry.path for entry in entries}) != len(entries):
            raise CanonicalImportReceiptError(
                "immutable tree entries are not unique and byte-sorted"
            )
        inventory = {
            "schema": "scion.immutable-tree-inventory.v1",
            "entries": [entry.to_mapping() for entry in entries],
        }
        tree_sha256 = hashlib.sha256(_canonical_json(inventory)).hexdigest()
        if value["tree_sha256"] != tree_sha256:
            raise CanonicalImportReceiptError("immutable tree aggregate differs")
        source_root = FileIdentity.from_mapping(
            value["source_root"],
            label="import source root",
        )
        staging_root = FileIdentity.from_mapping(
            value["staging_root"],
            label="import staging root",
        )
        target_uid = _uint(value["target_uid"], field="target_uid")
        target_gid = _uint(value["target_gid"], field="target_gid")
        if (
            not stat.S_ISDIR(source_root.mode)
            or not stat.S_ISDIR(staging_root.mode)
            or stat.S_IMODE(source_root.mode) != 0o555
        ):
            raise CanonicalImportReceiptError(
                "immutable tree source root is not an immutable directory"
            )
        if (
            stat.S_IMODE(staging_root.mode) != 0o555
            or staging_root.uid != target_uid
            or staging_root.gid != target_gid
        ):
            raise CanonicalImportReceiptError("immutable staging root differs")
        for entry in entries:
            source_is_directory = stat.S_ISDIR(entry.source_identity.mode)
            destination_is_directory = stat.S_ISDIR(entry.destination_identity.mode)
            if (
                source_is_directory != (entry.kind == "directory")
                or destination_is_directory != (entry.kind == "directory")
                or entry.destination_identity.device != staging_root.device
                or entry.source_identity.device != source_root.device
                or entry.destination_identity.uid != target_uid
                or entry.destination_identity.gid != target_gid
                or stat.S_IMODE(entry.destination_identity.mode) != entry.mode
                or entry.mode
                != _target_mode(
                    entry.source_identity.mode,
                    directory=entry.kind == "directory",
                )
            ):
                raise CanonicalImportReceiptError(
                    "immutable import entry binding differs"
                )
            if entry.kind == "file" and (
                not stat.S_ISREG(entry.source_identity.mode)
                or not stat.S_ISREG(entry.destination_identity.mode)
                or entry.source_identity.link_count != 1
                or entry.destination_identity.link_count != 1
                or entry.source_identity.size != entry.size
                or entry.destination_identity.size != entry.size
            ):
                raise CanonicalImportReceiptError(
                    "immutable file entry binding differs"
                )
        instance = object.__new__(cls)
        for field, item in (
            ("staging_leaf", _leaf(value["staging_leaf"], field="staging_leaf")),
            ("target_uid", target_uid),
            ("target_gid", target_gid),
            ("source_root", source_root),
            ("staging_root", staging_root),
            ("entries", entries),
            ("tree_sha256", _sha256(tree_sha256, field="tree_sha256")),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


def _same_snapshot(
    expected: _StableStat,
    metadata: os.stat_result,
    *,
    field: str,
) -> None:
    if _StableStat.from_stat(metadata) != expected:
        raise ExternalLinuxError(f"{field} identity drifted")


def _write_all(descriptor: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        written = os.write(descriptor, data[offset:])
        if written <= 0:
            raise OSError(errno.EIO, "short immutable tree write")
        offset += written


def _target_mode(source_mode: int, *, directory: bool) -> int:
    mode = stat.S_IMODE(source_mode)
    expected = frozenset({0o555}) if directory else frozenset({0o444, 0o555})
    if mode not in expected:
        kind = "directory" if directory else "regular file"
        raise ExternalLinuxError(f"source {kind} mode is not immutable")
    return mode


def _copy_tree(
    source_fd: int,
    destination_fd: int,
    *,
    prefix: str,
    target_uid: int,
    target_gid: int,
    source_device: int,
    entries: list[ImportEntry],
    observer: Callable[[str, str], None] | None,
) -> None:
    source_before = _StableStat.from_stat(os.fstat(source_fd))
    _require_directory(
        os.fstat(source_fd),
        field=f"source directory {prefix or '.'}",
    )
    _target_mode(os.fstat(source_fd).st_mode, directory=True)
    names = os.listdir(source_fd)
    if any(type(name) is not str for name in names) or len(set(names)) != len(names):
        raise ExternalLinuxError("source directory entries differ")
    for name in sorted(names, key=lambda item: item.encode("utf-8")):
        leaf = _leaf(name, field="source entry")
        relative = leaf if not prefix else f"{prefix}/{leaf}"
        _relative_path(relative, field="source relative path")
        before_metadata = os.stat(leaf, dir_fd=source_fd, follow_symlinks=False)
        before = _StableStat.from_stat(before_metadata)
        if before_metadata.st_dev != source_device:
            raise ExternalLinuxError(f"source entry {relative} crosses a filesystem")
        if stat.S_ISLNK(before_metadata.st_mode):
            raise ExternalLinuxError(f"source entry {relative} is a symlink")
        if stat.S_ISDIR(before_metadata.st_mode):
            os.mkdir(leaf, 0o700, dir_fd=destination_fd)
            child_source_fd = _open_directory_at(source_fd, leaf)
            child_destination_fd = _open_directory_at(destination_fd, leaf)
            try:
                _same_snapshot(
                    before,
                    os.fstat(child_source_fd),
                    field=f"source directory {relative}",
                )
                _copy_tree(
                    child_source_fd,
                    child_destination_fd,
                    prefix=relative,
                    target_uid=target_uid,
                    target_gid=target_gid,
                    source_device=source_device,
                    entries=entries,
                    observer=observer,
                )
                target_mode = _target_mode(before_metadata.st_mode, directory=True)
                os.fchmod(child_destination_fd, target_mode)
                os.fchown(child_destination_fd, target_uid, target_gid)
                os.fsync(child_destination_fd)
                destination_identity = FileIdentity.from_stat(
                    os.fstat(child_destination_fd)
                )
            finally:
                os.close(child_destination_fd)
                os.close(child_source_fd)
            _same_snapshot(
                before,
                os.stat(leaf, dir_fd=source_fd, follow_symlinks=False),
                field=f"source directory entry {relative}",
            )
            entries.append(
                ImportEntry(
                    path=relative,
                    kind="directory",
                    mode=target_mode,
                    size=0,
                    sha256=None,
                    source_identity=before.identity,
                    destination_identity=destination_identity,
                )
            )
            os.fsync(destination_fd)
            continue
        if not stat.S_ISREG(before_metadata.st_mode):
            raise ExternalLinuxError(f"source entry {relative} is special")
        if before_metadata.st_nlink != 1:
            raise ExternalLinuxError(f"source entry {relative} is hard-linked")
        source_file_fd = os.open(
            leaf,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=source_fd,
        )
        destination_file_fd = -1
        try:
            _same_snapshot(
                before,
                os.fstat(source_file_fd),
                field=f"source file {relative}",
            )
            destination_file_fd = os.open(
                leaf,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600,
                dir_fd=destination_fd,
            )
            digest = hashlib.sha256()
            byte_count = 0
            while True:
                chunk = os.read(source_file_fd, _COPY_CHUNK)
                if not chunk:
                    break
                digest.update(chunk)
                byte_count += len(chunk)
                _write_all(destination_file_fd, chunk)
            if byte_count != before.identity.size:
                raise ExternalLinuxError(f"source file {relative} size drifted")
            target_mode = _target_mode(before_metadata.st_mode, directory=False)
            os.fchmod(destination_file_fd, target_mode)
            os.fchown(destination_file_fd, target_uid, target_gid)
            os.fsync(destination_file_fd)
            destination_identity = FileIdentity.from_stat(os.fstat(destination_file_fd))
            if observer is not None:
                observer("after-file-copy", relative)
            _same_snapshot(
                before,
                os.fstat(source_file_fd),
                field=f"source file {relative}",
            )
            _same_snapshot(
                before,
                os.stat(leaf, dir_fd=source_fd, follow_symlinks=False),
                field=f"source file entry {relative}",
            )
            entries.append(
                ImportEntry(
                    path=relative,
                    kind="file",
                    mode=target_mode,
                    size=byte_count,
                    sha256=digest.hexdigest(),
                    source_identity=before.identity,
                    destination_identity=destination_identity,
                )
            )
            os.fsync(destination_fd)
        finally:
            if destination_file_fd >= 0:
                os.close(destination_file_fd)
            os.close(source_file_fd)
    _same_snapshot(
        source_before,
        os.fstat(source_fd),
        field=f"source directory {prefix or '.'}",
    )


def _import_immutable_tree(
    source_fd: int,
    staging_parent_fd: int,
    staging_leaf: str,
    *,
    target_uid: int,
    target_gid: int,
    observer: Callable[[str, str], None] | None = None,
) -> ImmutableTreeImportReceipt:
    """Private non-privileged seam; production uses import_root_owned_tree."""

    leaf = _leaf(staging_leaf, field="staging_leaf")
    target_uid = _uint(target_uid, field="target_uid")
    target_gid = _uint(target_gid, field="target_gid")
    source_before = _StableStat.from_stat(os.fstat(source_fd))
    source_metadata = os.fstat(source_fd)
    staging_parent_metadata = os.fstat(staging_parent_fd)
    _require_directory(source_metadata, field="source root")
    _require_directory(staging_parent_metadata, field="staging parent")
    staging_fd = -1
    try:
        os.mkdir(leaf, 0o700, dir_fd=staging_parent_fd)
        os.fsync(staging_parent_fd)
        staging_fd = _open_directory_at(staging_parent_fd, leaf)
        if os.fstat(staging_fd).st_dev != staging_parent_metadata.st_dev:
            raise ExternalLinuxError("staging root is not on the parent filesystem")
        entries: list[ImportEntry] = []
        _copy_tree(
            source_fd,
            staging_fd,
            prefix="",
            target_uid=target_uid,
            target_gid=target_gid,
            source_device=source_metadata.st_dev,
            entries=entries,
            observer=observer,
        )
        _same_snapshot(
            source_before,
            os.fstat(source_fd),
            field="source root",
        )
        os.fchmod(staging_fd, 0o555)
        os.fchown(staging_fd, target_uid, target_gid)
        os.fsync(staging_fd)
        os.fsync(staging_parent_fd)
        staging_identity = FileIdentity.from_stat(os.fstat(staging_fd))
        ordered = tuple(sorted(entries, key=lambda item: item.path.encode("utf-8")))
        return ImmutableTreeImportReceipt.create(
            staging_leaf=leaf,
            target_uid=target_uid,
            target_gid=target_gid,
            source_root=source_before.identity,
            staging_root=staging_identity,
            entries=ordered,
        )
    except Exception as exc:
        raise TreeImportHold(leaf) from exc
    finally:
        if staging_fd >= 0:
            os.close(staging_fd)


def import_root_owned_tree(
    source: PinnedDirectory,
    staging_parent: PinnedDirectory,
    staging_leaf: str,
) -> ImmutableTreeImportReceipt:
    """Copy one pinned tree to fresh immutable root-owned staging."""

    _require_root()
    if (
        type(source) is not PinnedDirectory
        or type(staging_parent) is not PinnedDirectory
    ):
        raise TypeError("source and staging_parent must be exact PinnedDirectory")
    source.revalidate()
    staging_parent.revalidate()
    staging_identity = FileIdentity.from_stat(os.fstat(staging_parent.fd))
    if staging_identity.uid != 0 or staging_identity.gid != 0:
        raise ExternalLinuxError("staging parent is not root-owned")
    try:
        receipt = _import_immutable_tree(
            source.fd,
            staging_parent.fd,
            staging_leaf,
            target_uid=0,
            target_gid=0,
        )
        source.revalidate()
        staging_parent.revalidate()
        return receipt
    except TreeImportHold:
        raise
    except Exception as exc:
        raise TreeImportHold(_leaf(staging_leaf, field="staging_leaf")) from exc


@dataclass(frozen=True, slots=True)
class NamespaceIdentity:
    device: int
    inode: int

    def __post_init__(self) -> None:
        _uint(self.device, field="namespace device")
        _uint(self.inode, field="namespace inode", positive=True)


@dataclass(frozen=True, slots=True)
class MountNamespacePair:
    self_namespace: NamespaceIdentity
    pid1_namespace: NamespaceIdentity

    def __post_init__(self) -> None:
        if (
            type(self.self_namespace) is not NamespaceIdentity
            or type(self.pid1_namespace) is not NamespaceIdentity
        ):
            raise TypeError("mount namespaces must be exact NamespaceIdentity")

    @property
    def matches(self) -> bool:
        return self.self_namespace == self.pid1_namespace


@dataclass(frozen=True, slots=True)
class AttachedMount:
    source_mount_id: int
    destination_parent_mount_id: int
    destination_pre_mount_id: int
    destination_mount_id: int
    destination_leaf: str
    read_only: bool

    def __post_init__(self) -> None:
        _uint(self.source_mount_id, field="source mount ID", positive=True)
        _uint(
            self.destination_parent_mount_id,
            field="destination parent mount ID",
            positive=True,
        )
        _uint(
            self.destination_pre_mount_id,
            field="destination pre-attach mount ID",
            positive=True,
        )
        _uint(self.destination_mount_id, field="destination mount ID", positive=True)
        _leaf(self.destination_leaf, field="destination leaf")
        if self.destination_pre_mount_id != self.destination_parent_mount_id:
            raise ExternalLinuxError("destination leaf is already a mount")
        if self.destination_mount_id in {
            self.source_mount_id,
            self.destination_parent_mount_id,
        }:
            raise ExternalLinuxError("attached mount ID is not distinct")
        if type(self.read_only) is not bool:
            raise TypeError("read_only must be exact bool")


class LinuxMountAdapter(Protocol):
    """Exact syscall surface consumed by the root mutation orchestration."""

    def rename_noreplace(
        self,
        source_parent_fd: int,
        source_leaf: str,
        destination_parent_fd: int,
        destination_leaf: str,
    ) -> None: ...

    def fsync(self, descriptor: int) -> None: ...

    def open_tree_clone(self, source_fd: int) -> int: ...

    def move_mount_attach(
        self,
        tree_fd: int,
        destination_parent_fd: int,
        destination_leaf: str,
    ) -> None: ...

    def open_directory_at(self, parent_fd: int, leaf: str) -> int: ...

    def directory_is_empty(self, descriptor: int) -> bool: ...

    def make_private_recursive(self, descriptor: int) -> None: ...

    def remount_read_only(self, descriptor: int) -> None: ...

    def mount_id_for_fd(self, descriptor: int) -> int: ...

    def namespace_identity(self, subject: str) -> NamespaceIdentity: ...

    def close_fd(self, descriptor: int) -> None: ...


def _raise_errno(operation: str, *, path: str | None = None) -> None:
    error_number = ctypes.get_errno()
    if error_number == 0:
        error_number = errno.EIO
    raise OSError(error_number, os.strerror(error_number), path or operation)


def parse_fdinfo_mount_id(raw: bytes) -> int:
    if type(raw) is not bytes:
        raise TypeError("fdinfo must be exact bytes")
    try:
        text = raw.decode("ascii", "strict")
    except UnicodeError as exc:
        raise ExternalLinuxError("fdinfo is not ASCII") from exc
    if not text.endswith("\n"):
        raise ExternalLinuxError("fdinfo is not newline terminated")
    values: list[int] = []
    for line in text.splitlines():
        if line.startswith("mnt_id:"):
            parts = line.split()
            if len(parts) != 2 or parts[0] != "mnt_id:":
                raise ExternalLinuxError("fdinfo mount ID row differs")
            try:
                values.append(int(parts[1], 10))
            except ValueError as exc:
                raise ExternalLinuxError("fdinfo mount ID is not decimal") from exc
    if len(values) != 1:
        raise ExternalLinuxError("fdinfo does not contain one mount ID")
    return _uint(values[0], field="fdinfo mount ID", positive=True)


class LinuxRootAdapter:
    """Final production adapter for the fixed Linux syscall subset."""

    __slots__ = ("_libc",)

    def __init__(self) -> None:
        self._libc = ctypes.CDLL(None, use_errno=True)
        self._libc.syscall.restype = ctypes.c_long

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("LinuxRootAdapter is final")

    def rename_noreplace(
        self,
        source_parent_fd: int,
        source_leaf: str,
        destination_parent_fd: int,
        destination_leaf: str,
    ) -> None:
        _require_root()
        source_name = _leaf(source_leaf, field="source leaf")
        destination_name = _leaf(destination_leaf, field="destination leaf")
        renameat2 = getattr(self._libc, "renameat2", None)
        if renameat2 is None:
            raise OSError(errno.EOPNOTSUPP, "renameat2 is unavailable")
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        result = renameat2(
            source_parent_fd,
            os.fsencode(source_name),
            destination_parent_fd,
            os.fsencode(destination_name),
            _RENAME_NOREPLACE,
        )
        if result != 0:
            _raise_errno("renameat2", path=destination_name)

    def fsync(self, descriptor: int) -> None:
        os.fsync(descriptor)

    def open_tree_clone(self, source_fd: int) -> int:
        _require_root()
        result = self._libc.syscall(
            ctypes.c_long(_SYS_OPEN_TREE),
            ctypes.c_int(source_fd),
            ctypes.c_char_p(b""),
            ctypes.c_uint(_AT_EMPTY_PATH | _OPEN_TREE_CLONE | _OPEN_TREE_CLOEXEC),
        )
        if result < 0:
            _raise_errno("open_tree")
        return int(result)

    def move_mount_attach(
        self,
        tree_fd: int,
        destination_parent_fd: int,
        destination_leaf: str,
    ) -> None:
        _require_root()
        leaf = _leaf(destination_leaf, field="destination leaf")
        result = self._libc.syscall(
            ctypes.c_long(_SYS_MOVE_MOUNT),
            ctypes.c_int(tree_fd),
            ctypes.c_char_p(b""),
            ctypes.c_int(destination_parent_fd),
            ctypes.c_char_p(os.fsencode(leaf)),
            ctypes.c_uint(_MOVE_MOUNT_F_EMPTY_PATH),
        )
        if result != 0:
            _raise_errno("move_mount", path=leaf)

    def open_directory_at(self, parent_fd: int, leaf: str) -> int:
        return _open_directory_at(parent_fd, _leaf(leaf, field="directory leaf"))

    def directory_is_empty(self, descriptor: int) -> bool:
        return os.listdir(descriptor) == []

    def _mount_flags(self, descriptor: int, flags: int) -> None:
        _require_root()
        target = f"/proc/self/fd/{_uint(descriptor, field='mount descriptor')}"
        mount = self._libc.mount
        mount.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_ulong,
            ctypes.c_void_p,
        ]
        mount.restype = ctypes.c_int
        result = mount(
            None,
            ctypes.c_char_p(os.fsencode(target)),
            None,
            ctypes.c_ulong(flags),
            None,
        )
        if result != 0:
            _raise_errno("mount", path=target)

    def make_private_recursive(self, descriptor: int) -> None:
        self._mount_flags(descriptor, _MS_PRIVATE | _MS_REC)

    def remount_read_only(self, descriptor: int) -> None:
        self._mount_flags(
            descriptor,
            _MS_BIND | _MS_REMOUNT | _MS_RDONLY,
        )

    def mount_id_for_fd(self, descriptor: int) -> int:
        descriptor = _uint(descriptor, field="mount descriptor")
        fdinfo_fd = os.open(
            f"/proc/self/fdinfo/{descriptor}",
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        try:
            chunks: list[bytes] = []
            byte_count = 0
            while True:
                chunk = os.read(fdinfo_fd, min(4096, _FDINFO_LIMIT + 1 - byte_count))
                if not chunk:
                    break
                chunks.append(chunk)
                byte_count += len(chunk)
                if byte_count > _FDINFO_LIMIT:
                    raise ExternalLinuxError("fdinfo exceeds bounded size")
            return parse_fdinfo_mount_id(b"".join(chunks))
        finally:
            os.close(fdinfo_fd)

    def namespace_identity(self, subject: str) -> NamespaceIdentity:
        if subject == "self":
            path = "/proc/self/ns/mnt"
        elif subject == "pid1":
            path = "/proc/1/ns/mnt"
        else:
            raise ExternalLinuxError("namespace subject differs")
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
        try:
            metadata = os.fstat(descriptor)
            return NamespaceIdentity(
                device=metadata.st_dev,
                inode=metadata.st_ino,
            )
        finally:
            os.close(descriptor)

    def close_fd(self, descriptor: int) -> None:
        os.close(descriptor)


def publish_noreplace(
    adapter: LinuxMountAdapter,
    *,
    source_parent_fd: int,
    source_leaf: str,
    destination_parent_fd: int,
    destination_leaf: str,
) -> None:
    """Publish one leaf exactly once and durably; never overwrite or repair."""

    _require_root()
    source_name = _leaf(source_leaf, field="source leaf")
    destination_name = _leaf(destination_leaf, field="destination leaf")
    moved = False
    try:
        adapter.rename_noreplace(
            source_parent_fd,
            source_name,
            destination_parent_fd,
            destination_name,
        )
        moved = True
        adapter.fsync(destination_parent_fd)
        if source_parent_fd != destination_parent_fd:
            adapter.fsync(source_parent_fd)
    except Exception as exc:
        if moved:
            raise LinuxMutationHold(
                f"no-replace publication is held at {destination_name}"
            ) from exc
        raise


def attach_cloned_mount(
    adapter: LinuxMountAdapter,
    *,
    source_fd: int,
    destination_parent_fd: int,
    destination_leaf: str,
    read_only: bool,
) -> AttachedMount:
    """Clone by source FD, attach no-replace, privatize, and optionally remount RO."""

    _require_root()
    leaf = _leaf(destination_leaf, field="destination leaf")
    if type(read_only) is not bool:
        raise TypeError("read_only must be exact bool")
    source_mount_id = adapter.mount_id_for_fd(source_fd)
    destination_parent_mount_id = adapter.mount_id_for_fd(destination_parent_fd)
    pre_attach_fd = adapter.open_directory_at(destination_parent_fd, leaf)
    try:
        if not adapter.directory_is_empty(pre_attach_fd):
            raise ExternalLinuxError("destination mount leaf is not empty")
        destination_pre_mount_id = adapter.mount_id_for_fd(pre_attach_fd)
        if destination_pre_mount_id != destination_parent_mount_id:
            raise ExternalLinuxError("destination leaf is already a mount")
    finally:
        adapter.close_fd(pre_attach_fd)
    tree_fd = adapter.open_tree_clone(source_fd)
    destination_fd = -1
    attached = False
    try:
        adapter.move_mount_attach(tree_fd, destination_parent_fd, leaf)
        attached = True
        destination_fd = adapter.open_directory_at(destination_parent_fd, leaf)
        adapter.make_private_recursive(destination_fd)
        if read_only:
            adapter.remount_read_only(destination_fd)
        destination_mount_id = adapter.mount_id_for_fd(destination_fd)
        return AttachedMount(
            source_mount_id=source_mount_id,
            destination_parent_mount_id=destination_parent_mount_id,
            destination_pre_mount_id=destination_pre_mount_id,
            destination_mount_id=destination_mount_id,
            destination_leaf=leaf,
            read_only=read_only,
        )
    except Exception as exc:
        if attached:
            raise LinuxMutationHold(f"attached mount is held at {leaf}") from exc
        raise
    finally:
        if destination_fd >= 0:
            adapter.close_fd(destination_fd)
        adapter.close_fd(tree_fd)


def acquire_mount_namespace_pair(
    adapter: LinuxMountAdapter,
    *,
    require_same: bool = True,
) -> MountNamespacePair:
    if type(require_same) is not bool:
        raise TypeError("require_same must be exact bool")
    pair = MountNamespacePair(
        self_namespace=adapter.namespace_identity("self"),
        pid1_namespace=adapter.namespace_identity("pid1"),
    )
    if require_same and not pair.matches:
        raise ExternalLinuxError("self and PID 1 mount namespaces differ")
    return pair


__all__ = [
    "AttachedMount",
    "CanonicalImportReceiptError",
    "ExternalLinuxError",
    "FileIdentity",
    "ImmutableTreeImportReceipt",
    "ImportEntry",
    "LinuxMountAdapter",
    "LinuxMutationHold",
    "LinuxRootAdapter",
    "MountNamespacePair",
    "NamespaceIdentity",
    "PinnedComponent",
    "PinnedDirectory",
    "TreeImportHold",
    "acquire_mount_namespace_pair",
    "attach_cloned_mount",
    "import_root_owned_tree",
    "parse_fdinfo_mount_id",
    "pin_absolute_directory",
    "publish_noreplace",
]
