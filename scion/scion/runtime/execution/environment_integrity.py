"""Capability-free immutable environment inventory and verification.

This module acquires content facts only.  It deliberately owns no D-Bus,
mount, root-publication, nonce, or manager capability.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping

_SCHEMA = "scion.environment-content.v1"
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_DIRECTORY_MODE = 0o555
_REGULAR_MODES = frozenset({0o444, 0o555})
_READ_SIZE = 1024 * 1024


class EnvironmentIntegrityError(RuntimeError):
    """An immutable environment or external-runtime fact is invalid."""


def _reject_nonfinite(item: str) -> object:
    raise EnvironmentIntegrityError(f"nonfinite JSON value: {item}")


def _reject_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise EnvironmentIntegrityError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


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
        raise EnvironmentIntegrityError("value is not canonical JSON data") from exc


def _decode_canonical(raw: bytes) -> dict[str, object]:
    if type(raw) is not bytes:
        raise TypeError("environment receipt must be exact bytes")
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
    except EnvironmentIntegrityError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EnvironmentIntegrityError("environment receipt is invalid JSON") from exc
    if type(value) is not dict or _canonical_json(value) != raw:
        raise EnvironmentIntegrityError(
            "environment receipt is not one canonical mapping"
        )
    return value


def _exact_keys(
    value: Mapping[str, object],
    expected: frozenset[str],
    *,
    label: str,
) -> None:
    if frozenset(value) != expected:
        raise EnvironmentIntegrityError(f"{label} fields differ")


def _uint(value: object, *, field: str) -> int:
    if type(value) is not int or not 0 <= value <= (1 << 64) - 1:
        raise EnvironmentIntegrityError(f"{field} must be an integer in [0, 2^64-1]")
    return value


def _sha256(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise EnvironmentIntegrityError(
            f"{field} must be 64 lowercase hexadecimal characters"
        )
    return value


def _utf8_text(value: object, *, field: str) -> str:
    if type(value) is not str or not value or "\x00" in value:
        raise EnvironmentIntegrityError(f"{field} must be nonempty exact text")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise EnvironmentIntegrityError(f"{field} is not UTF-8") from exc
    if any(byte < 0x20 or byte == 0x7F for byte in encoded):
        raise EnvironmentIntegrityError(f"{field} contains a control character")
    return value


def _relative_path(value: object, *, field: str) -> str:
    text = _utf8_text(value, field=field)
    if text == ".":
        return text
    path = PurePosixPath(text)
    if (
        path.is_absolute()
        or path.parts in {(), (".",)}
        or any(part in {"", ".", ".."} for part in path.parts)
        or str(path) != text
    ):
        raise EnvironmentIntegrityError(f"{field} is not a canonical relative path")
    return text


def _absolute_path(value: object, *, field: str) -> str:
    text = _utf8_text(value, field=field)
    path = PurePosixPath(text)
    if (
        not path.is_absolute()
        or text.startswith("//")
        or any(part in {"", ".", ".."} for part in path.parts[1:])
        or str(path) != text
        or text == "/"
    ):
        raise EnvironmentIntegrityError(f"{field} is not a canonical absolute path")
    return text


def _path_bytes(path: Path, *, field: str) -> bytes:
    if not isinstance(path, Path):
        raise TypeError(f"{field} must be Path")
    text = _absolute_path(str(path), field=field)
    return text.encode("utf-8", "strict")


def _forbidden_needles(candidate_root: Path, selection_root: Path) -> tuple[bytes, ...]:
    candidate = _path_bytes(candidate_root, field="candidate_root")
    selection = _path_bytes(selection_root, field="selection_root")
    if candidate == selection:
        raise EnvironmentIntegrityError("candidate_root and selection_root must differ")
    return tuple(sorted({candidate, selection}))


def _stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _same_opened_regular(
    named: os.stat_result,
    opened: os.stat_result,
) -> bool:
    return (
        stat.S_ISREG(named.st_mode)
        and stat.S_ISREG(opened.st_mode)
        and _stat_identity(named) == _stat_identity(opened)
    )


def _read_regular(
    path: Path,
    named_before: os.stat_result,
    *,
    forbidden_needles: tuple[bytes, ...] = (),
) -> tuple[int, str]:
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise EnvironmentIntegrityError(f"cannot open regular file: {path}") from exc
    digest = hashlib.sha256()
    total = 0
    overlap = max((len(item) for item in forbidden_needles), default=1) - 1
    tail = b""
    try:
        opened_before = os.fstat(descriptor)
        if not _same_opened_regular(named_before, opened_before):
            raise EnvironmentIntegrityError(
                f"regular file identity changed before read: {path}"
            )
        while True:
            chunk = os.read(descriptor, _READ_SIZE)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
            if forbidden_needles:
                window = tail + chunk
                if any(needle in window for needle in forbidden_needles):
                    raise EnvironmentIntegrityError(
                        f"regular file contains a forbidden path: {path}"
                    )
                tail = window[-overlap:] if overlap else b""
        opened_after = os.fstat(descriptor)
    except OSError as exc:
        raise EnvironmentIntegrityError(f"cannot read regular file: {path}") from exc
    finally:
        os.close(descriptor)
    try:
        named_after = os.lstat(path)
    except OSError as exc:
        raise EnvironmentIntegrityError(
            f"cannot reopen regular file identity: {path}"
        ) from exc
    if (
        _stat_identity(opened_before) != _stat_identity(opened_after)
        or not _same_opened_regular(opened_after, named_after)
        or total != opened_after.st_size
    ):
        raise EnvironmentIntegrityError(f"regular file changed during read: {path}")
    return total, digest.hexdigest()


@dataclass(frozen=True, slots=True)
class EnvironmentInventoryEntry:
    """One closed relative environment-tree entry."""

    path: str
    kind: str
    mode: int
    size_bytes: int
    sha256: str | None

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("EnvironmentInventoryEntry is final")

    @classmethod
    def from_mapping(cls, value: object) -> "EnvironmentInventoryEntry":
        if type(value) is not dict:
            raise EnvironmentIntegrityError(
                "environment inventory entry is not a mapping"
            )
        _exact_keys(
            value,
            frozenset({"path", "kind", "mode", "size_bytes", "sha256"}),
            label="environment inventory entry",
        )
        path = _relative_path(value["path"], field="environment entry path")
        kind = value["kind"]
        if kind not in {"directory", "regular"}:
            raise EnvironmentIntegrityError("environment entry kind differs")
        mode = _uint(value["mode"], field="environment entry mode")
        size_bytes = _uint(
            value["size_bytes"],
            field="environment entry size_bytes",
        )
        raw_sha256 = value["sha256"]
        if kind == "directory":
            if mode != _DIRECTORY_MODE or size_bytes != 0 or raw_sha256 is not None:
                raise EnvironmentIntegrityError("environment directory facts differ")
            sha256 = None
        else:
            if mode not in _REGULAR_MODES:
                raise EnvironmentIntegrityError("environment regular-file mode differs")
            sha256 = _sha256(
                raw_sha256,
                field="environment entry sha256",
            )
        if path == "." and kind != "directory":
            raise EnvironmentIntegrityError("environment root is not a directory")
        return cls(
            path=path,
            kind=kind,
            mode=mode,
            size_bytes=size_bytes,
            sha256=sha256,
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "path": self.path,
            "kind": self.kind,
            "mode": self.mode,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class ExternalRuntimeEntry:
    """One exact absolute external-runtime regular file."""

    path: str
    device: int
    inode: int
    size_bytes: int
    sha256: str

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("ExternalRuntimeEntry is final")

    @classmethod
    def acquire(cls, path: Path) -> "ExternalRuntimeEntry":
        if not isinstance(path, Path):
            raise TypeError("external runtime path must be Path")
        absolute = _absolute_path(str(path), field="external runtime path")
        try:
            before = os.lstat(path)
        except OSError as exc:
            raise EnvironmentIntegrityError(
                f"cannot inspect external runtime file: {path}"
            ) from exc
        if stat.S_ISLNK(before.st_mode):
            raise EnvironmentIntegrityError(
                f"external runtime path is a symlink: {path}"
            )
        if not stat.S_ISREG(before.st_mode):
            raise EnvironmentIntegrityError(
                f"external runtime path is not regular: {path}"
            )
        size_bytes, sha256 = _read_regular(path, before)
        return cls(
            path=absolute,
            device=before.st_dev,
            inode=before.st_ino,
            size_bytes=size_bytes,
            sha256=sha256,
        )

    @classmethod
    def from_mapping(cls, value: object) -> "ExternalRuntimeEntry":
        if type(value) is not dict:
            raise EnvironmentIntegrityError("external runtime entry is not a mapping")
        _exact_keys(
            value,
            frozenset({"path", "device", "inode", "size_bytes", "sha256"}),
            label="external runtime entry",
        )
        return cls(
            path=_absolute_path(
                value["path"],
                field="external runtime path",
            ),
            device=_uint(
                value["device"],
                field="external runtime device",
            ),
            inode=_uint(
                value["inode"],
                field="external runtime inode",
            ),
            size_bytes=_uint(
                value["size_bytes"],
                field="external runtime size_bytes",
            ),
            sha256=_sha256(
                value["sha256"],
                field="external runtime sha256",
            ),
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "path": self.path,
            "device": self.device,
            "inode": self.inode,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


def _inventory_environment(
    root: Path,
    *,
    forbidden_needles: tuple[bytes, ...],
) -> tuple[EnvironmentInventoryEntry, ...]:
    if not isinstance(root, Path):
        raise TypeError("environment_root must be Path")
    _absolute_path(str(root), field="environment_root")

    entries: list[EnvironmentInventoryEntry] = []

    def walk(
        path: Path,
        relative: str,
        expected: os.stat_result | None = None,
    ) -> None:
        try:
            before = os.lstat(path)
        except OSError as exc:
            raise EnvironmentIntegrityError(
                f"cannot inspect environment entry: {path}"
            ) from exc
        if expected is not None and _stat_identity(before) != _stat_identity(expected):
            raise EnvironmentIntegrityError(
                f"environment entry identity changed: {path}"
            )
        mode = stat.S_IMODE(before.st_mode)
        if stat.S_ISLNK(before.st_mode):
            raise EnvironmentIntegrityError(
                f"environment contains a symlink: {relative}"
            )
        if stat.S_ISDIR(before.st_mode):
            if mode != _DIRECTORY_MODE:
                raise EnvironmentIntegrityError(
                    f"environment directory mode differs: {relative}"
                )
            entries.append(
                EnvironmentInventoryEntry(
                    path=relative,
                    kind="directory",
                    mode=mode,
                    size_bytes=0,
                    sha256=None,
                )
            )
            try:
                with os.scandir(path) as iterator:
                    children = sorted(
                        iterator,
                        key=lambda item: os.fsencode(item.name),
                    )
            except OSError as exc:
                raise EnvironmentIntegrityError(
                    f"cannot scan environment directory: {relative}"
                ) from exc
            for child in children:
                try:
                    child_stat = child.stat(follow_symlinks=False)
                except OSError as exc:
                    raise EnvironmentIntegrityError(
                        f"cannot inspect environment child: {child.name}"
                    ) from exc
                child_relative = (
                    child.name if relative == "." else f"{relative}/{child.name}"
                )
                _relative_path(
                    child_relative,
                    field="environment entry path",
                )
                walk(path / child.name, child_relative, child_stat)
            try:
                after = os.lstat(path)
            except OSError as exc:
                raise EnvironmentIntegrityError(
                    f"cannot reopen environment directory: {relative}"
                ) from exc
            if _stat_identity(before) != _stat_identity(after):
                raise EnvironmentIntegrityError(
                    f"environment directory changed during scan: {relative}"
                )
            return
        if stat.S_ISREG(before.st_mode):
            if before.st_nlink != 1:
                raise EnvironmentIntegrityError(
                    f"environment file is multiply linked: {relative}"
                )
            if mode not in _REGULAR_MODES:
                raise EnvironmentIntegrityError(
                    f"environment regular-file mode differs: {relative}"
                )
            size_bytes, sha256 = _read_regular(
                path,
                before,
                forbidden_needles=forbidden_needles,
            )
            entries.append(
                EnvironmentInventoryEntry(
                    path=relative,
                    kind="regular",
                    mode=mode,
                    size_bytes=size_bytes,
                    sha256=sha256,
                )
            )
            return
        raise EnvironmentIntegrityError(
            f"environment contains a special file: {relative}"
        )

    walk(root, ".")
    return tuple(
        sorted(
            entries,
            key=lambda item: item.path.encode("utf-8", "strict"),
        )
    )


def _external_runtime_entries(
    paths: tuple[Path, ...],
    *,
    forbidden_needles: tuple[bytes, ...],
) -> tuple[ExternalRuntimeEntry, ...]:
    if type(paths) is not tuple or not paths:
        raise TypeError("external_runtime_paths must be one nonempty exact tuple")
    entries = []
    seen: set[str] = set()
    for path in paths:
        entry = ExternalRuntimeEntry.acquire(path)
        encoded = entry.path.encode("utf-8", "strict")
        if any(needle in encoded for needle in forbidden_needles):
            raise EnvironmentIntegrityError(
                "external runtime path contains a forbidden path"
            )
        if entry.path in seen:
            raise EnvironmentIntegrityError("external runtime path is duplicated")
        seen.add(entry.path)
        entries.append(entry)
    return tuple(
        sorted(
            entries,
            key=lambda item: item.path.encode("utf-8", "strict"),
        )
    )


@dataclass(frozen=True, slots=True)
class EnvironmentContentReceipt:
    """Canonical relocatable environment and external-runtime content fact."""

    environment_inventory: tuple[EnvironmentInventoryEntry, ...]
    external_runtime: tuple[ExternalRuntimeEntry, ...]
    raw: bytes
    raw_sha256: str

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("EnvironmentContentReceipt is final")

    @classmethod
    def create(
        cls,
        environment_root: Path,
        *,
        external_runtime_paths: tuple[Path, ...],
        candidate_root: Path,
        selection_root: Path,
    ) -> "EnvironmentContentReceipt":
        forbidden = _forbidden_needles(candidate_root, selection_root)
        inventory = _inventory_environment(
            environment_root,
            forbidden_needles=forbidden,
        )
        external_runtime = _external_runtime_entries(
            external_runtime_paths,
            forbidden_needles=forbidden,
        )
        raw = _canonical_json(
            {
                "schema": _SCHEMA,
                "environment_inventory": [item.to_mapping() for item in inventory],
                "external_runtime": [item.to_mapping() for item in external_runtime],
            }
        )
        if any(needle in raw for needle in forbidden):
            raise EnvironmentIntegrityError(
                "environment receipt contains a forbidden path"
            )
        return cls.from_bytes(raw)

    @classmethod
    def from_bytes(cls, raw: bytes) -> "EnvironmentContentReceipt":
        value = _decode_canonical(raw)
        _exact_keys(
            value,
            frozenset(
                {
                    "schema",
                    "environment_inventory",
                    "external_runtime",
                }
            ),
            label="environment receipt",
        )
        if value["schema"] != _SCHEMA:
            raise EnvironmentIntegrityError("environment receipt schema differs")
        raw_inventory = value["environment_inventory"]
        raw_external = value["external_runtime"]
        if type(raw_inventory) is not list or not raw_inventory:
            raise EnvironmentIntegrityError(
                "environment inventory is not a nonempty array"
            )
        if type(raw_external) is not list or not raw_external:
            raise EnvironmentIntegrityError("external runtime is not a nonempty array")
        inventory = tuple(
            EnvironmentInventoryEntry.from_mapping(item) for item in raw_inventory
        )
        external_runtime = tuple(
            ExternalRuntimeEntry.from_mapping(item) for item in raw_external
        )
        inventory_by_path = {item.path: item for item in inventory}
        if inventory[0].path != "." or tuple(item.path for item in inventory) != tuple(
            sorted(
                inventory_by_path,
                key=lambda item: item.encode("utf-8", "strict"),
            )
        ):
            raise EnvironmentIntegrityError(
                "environment inventory order or paths differ"
            )
        for item in inventory[1:]:
            parent = str(PurePosixPath(item.path).parent)
            parent_entry = inventory_by_path.get(parent)
            if parent_entry is None or parent_entry.kind != "directory":
                raise EnvironmentIntegrityError(
                    "environment inventory parent closure differs"
                )
        if tuple(item.path for item in external_runtime) != tuple(
            sorted(
                {item.path for item in external_runtime},
                key=lambda item: item.encode("utf-8", "strict"),
            )
        ):
            raise EnvironmentIntegrityError("external runtime order or paths differ")
        return cls(
            environment_inventory=inventory,
            external_runtime=external_runtime,
            raw=raw,
            raw_sha256=hashlib.sha256(raw).hexdigest(),
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema": _SCHEMA,
            "environment_inventory": [
                item.to_mapping() for item in self.environment_inventory
            ],
            "external_runtime": [item.to_mapping() for item in self.external_runtime],
        }


def verify_environment_content(
    environment_root: Path,
    receipt: EnvironmentContentReceipt,
    *,
    external_runtime_paths: tuple[Path, ...],
    candidate_root: Path,
    selection_root: Path,
) -> None:
    """Read and rehash every receipt-bound fact without mutating it."""

    if type(receipt) is not EnvironmentContentReceipt:
        raise TypeError("receipt must be exact EnvironmentContentReceipt")
    if EnvironmentContentReceipt.from_bytes(receipt.raw) != receipt:
        raise EnvironmentIntegrityError("environment receipt object differs")
    forbidden = _forbidden_needles(candidate_root, selection_root)
    if any(needle in receipt.raw for needle in forbidden):
        raise EnvironmentIntegrityError("environment receipt contains a forbidden path")
    inventory = _inventory_environment(
        environment_root,
        forbidden_needles=forbidden,
    )
    if inventory != receipt.environment_inventory:
        raise EnvironmentIntegrityError("environment inventory differs")
    external_runtime = _external_runtime_entries(
        external_runtime_paths,
        forbidden_needles=forbidden,
    )
    if external_runtime != receipt.external_runtime:
        raise EnvironmentIntegrityError("external runtime inventory differs")


__all__ = [
    "EnvironmentContentReceipt",
    "EnvironmentIntegrityError",
    "EnvironmentInventoryEntry",
    "ExternalRuntimeEntry",
    "verify_environment_content",
]
