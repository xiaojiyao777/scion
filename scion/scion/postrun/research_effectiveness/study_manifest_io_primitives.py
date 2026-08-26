"""Private path tokens and filesystem fingerprints for the M32 bundle."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass

_MAX_PATH_BYTES = 4096
_MAX_PATH_COMPONENTS = 128
_MAX_COMPONENT_BYTES = 255


class _StudyManifestIoError(ValueError):
    """Internal sentinel whose details never cross the loader boundary."""


@dataclass(frozen=True, repr=False)
class _Identity:
    device: int
    inode: int


@dataclass(frozen=True, repr=False)
class _FileFingerprint:
    identity: _Identity
    mode: int
    owner: int
    size: int
    links: int
    modified_ns: int
    changed_ns: int


@dataclass(frozen=True, repr=False)
class _DirectoryFingerprint:
    identity: _Identity
    mode: int
    owner: int
    size: int
    links: int
    modified_ns: int
    changed_ns: int


def _absolute_parts(path: object) -> tuple[str, ...]:
    if type(path) is not str:
        raise _StudyManifestIoError
    value = path
    if (
        not value
        or not value.startswith("/")
        or value.startswith("//")
        or value == "/"
        or "\x00" in value
        or "\\" in value
        or os.path.normpath(value) != value
    ):
        raise _StudyManifestIoError
    encoded = value.encode("utf-8")
    parts = tuple(value.split("/")[1:])
    if (
        len(encoded) > _MAX_PATH_BYTES
        or not parts
        or len(parts) > _MAX_PATH_COMPONENTS
        or any(
            part in {"", ".", ".."} or len(part.encode("utf-8")) > _MAX_COMPONENT_BYTES
            for part in parts
        )
    ):
        raise _StudyManifestIoError
    return parts


def _relative_parts(
    token: object,
    *,
    required_suffix: str | None = None,
) -> tuple[str, ...]:
    if type(token) is not str:
        raise _StudyManifestIoError
    value = token
    if (
        not value
        or value.startswith("/")
        or "\x00" in value
        or "\\" in value
        or required_suffix is not None
        and not value.endswith(required_suffix)
    ):
        raise _StudyManifestIoError
    encoded = value.encode("utf-8")
    parts = tuple(value.split("/"))
    if (
        len(encoded) > _MAX_PATH_BYTES
        or len(parts) > _MAX_PATH_COMPONENTS
        or any(
            part in {"", ".", ".."} or len(part.encode("utf-8")) > _MAX_COMPONENT_BYTES
            for part in parts
        )
    ):
        raise _StudyManifestIoError
    return parts


def _parts_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    common = min(len(left), len(right))
    return left[:common] == right[:common]


def _directory_flags() -> int:
    required = ("O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC")
    if any(not hasattr(os, name) for name in required):
        raise _StudyManifestIoError
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _leaf_flags() -> int:
    required = ("O_NOFOLLOW", "O_NONBLOCK", "O_CLOEXEC")
    if any(not hasattr(os, name) for name in required):
        raise _StudyManifestIoError
    return os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


def _file_fingerprint(value: os.stat_result) -> _FileFingerprint:
    return _FileFingerprint(
        identity=_Identity(value.st_dev, value.st_ino),
        mode=value.st_mode,
        owner=value.st_uid,
        size=value.st_size,
        links=value.st_nlink,
        modified_ns=value.st_mtime_ns,
        changed_ns=value.st_ctime_ns,
    )


def _directory_fingerprint(value: os.stat_result) -> _DirectoryFingerprint:
    if not stat.S_ISDIR(value.st_mode):
        raise _StudyManifestIoError
    return _DirectoryFingerprint(
        identity=_Identity(value.st_dev, value.st_ino),
        mode=value.st_mode,
        owner=value.st_uid,
        size=value.st_size,
        links=value.st_nlink,
        modified_ns=value.st_mtime_ns,
        changed_ns=value.st_ctime_ns,
    )


__all__: tuple[str, ...] = ()
