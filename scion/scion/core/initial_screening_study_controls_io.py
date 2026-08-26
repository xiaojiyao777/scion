"""Private dirfd publication for initial-screening config-subset controls."""

from __future__ import annotations

import os
import stat
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, repr=False)
class _ControlsPublication:
    campaign_dir: str
    directory_fingerprints: tuple[tuple[int, int], ...]
    leaf_fingerprint: tuple[int, int, int, int]

    def __repr__(self) -> str:
        return "_ControlsPublication(<redacted>)"

    __str__ = __repr__


def _publish_controls(
    campaign_dir: str,
    payload: bytes,
    *,
    protected_roots: Sequence[str],
    filename: str,
    max_bytes: int,
) -> _ControlsPublication:
    if type(campaign_dir) is not str or type(payload) is not bytes:
        raise TypeError
    if len(payload) > max_bytes:
        raise ValueError
    root_token = os.fspath(campaign_dir)
    if (
        not os.path.isabs(root_token)
        or os.path.normpath(root_token) != root_token
        or "\x00" in root_token
    ):
        raise ValueError
    _validate_root_separation(root_token, protected_roots)
    directory_flags = _required_flags(
        "O_RDONLY",
        "O_DIRECTORY",
        "O_NOFOLLOW",
        "O_CLOEXEC",
    )
    leaf_flags = _required_flags(
        "O_WRONLY",
        "O_CREAT",
        "O_EXCL",
        "O_NOFOLLOW",
        "O_CLOEXEC",
    )
    parts = root_token.split("/")[1:]
    if not parts or len(parts) > 128 or any(part in {"", ".", ".."} for part in parts):
        raise ValueError
    final_name = parts[-1]
    open_chain = [os.open("/", directory_flags)]
    fingerprints = [_fingerprint(os.fstat(open_chain[0]))]
    try:
        for component in parts[:-1]:
            next_fd = os.open(component, directory_flags, dir_fd=open_chain[-1])
            open_chain.append(next_fd)
            fingerprints.append(_fingerprint(os.fstat(next_fd)))
        parent_fd = open_chain[-1]
        os.mkdir(final_name, mode=0o700, dir_fd=parent_fd)
        os.fsync(parent_fd)
        root_fd = os.open(final_name, directory_flags, dir_fd=parent_fd)
        open_chain.append(root_fd)
        root_stat = os.fstat(root_fd)
        fingerprints.append(_fingerprint(root_stat))
        _validate_root(root_stat)
        _validate_root_name(parent_fd, final_name, root_stat)
        _require_empty_directory(root_fd)
        leaf_stat = _write_leaf(root_fd, leaf_flags, payload, filename=filename)
        os.fsync(root_fd)
        _validate_root(os.fstat(root_fd), expected=root_stat)
        _validate_root_name(parent_fd, final_name, root_stat)
        publication = _ControlsPublication(
            campaign_dir=root_token,
            directory_fingerprints=tuple(fingerprints),
            leaf_fingerprint=_leaf_fingerprint(leaf_stat),
        )
        _validate_controls_publication(
            publication,
            payload,
            filename=filename,
            max_bytes=max_bytes,
        )
        return publication
    finally:
        for fd in reversed(open_chain):
            os.close(fd)


def _validate_controls_publication(
    publication: _ControlsPublication,
    payload: bytes,
    *,
    filename: str,
    max_bytes: int,
) -> None:
    if type(publication) is not _ControlsPublication or type(payload) is not bytes:
        raise TypeError
    if len(payload) > max_bytes:
        raise ValueError
    parts = publication.campaign_dir.split("/")[1:]
    expected = publication.directory_fingerprints
    if len(expected) != len(parts) + 1:
        raise ValueError
    directory_flags = _required_flags(
        "O_RDONLY",
        "O_DIRECTORY",
        "O_NOFOLLOW",
        "O_CLOEXEC",
    )
    current_fd = _open_expected_root(parts, expected, directory_flags)
    try:
        _validate_root(os.fstat(current_fd))
        _verify_leaf_bytes(
            current_fd,
            filename=filename,
            leaf_fingerprint=publication.leaf_fingerprint,
            payload=payload,
            max_bytes=max_bytes,
        )
    finally:
        os.close(current_fd)
    current_fd = _open_expected_root(parts, expected, directory_flags)
    try:
        _validate_root(os.fstat(current_fd))
        _verify_leaf_bytes(
            current_fd,
            filename=filename,
            leaf_fingerprint=publication.leaf_fingerprint,
            payload=payload,
            max_bytes=max_bytes,
        )
    finally:
        os.close(current_fd)


def _create_private_child_directory(
    publication: _ControlsPublication,
    name: str,
) -> tuple[int, int]:
    if type(publication) is not _ControlsPublication:
        raise TypeError
    _validate_child_name(name)
    flags = _required_flags(
        "O_RDONLY",
        "O_DIRECTORY",
        "O_NOFOLLOW",
        "O_CLOEXEC",
    )
    parts = publication.campaign_dir.split("/")[1:]
    root_fd = _open_expected_root(parts, publication.directory_fingerprints, flags)
    try:
        _validate_root(os.fstat(root_fd))
        os.mkdir(name, mode=0o700, dir_fd=root_fd)
        os.fsync(root_fd)
        child_fd = os.open(name, flags, dir_fd=root_fd)
        try:
            child = os.fstat(child_fd)
            _validate_private_directory(child)
            _require_empty_directory(child_fd)
            current = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
            _validate_private_directory(current, expected=child)
            return _fingerprint(child)
        finally:
            os.close(child_fd)
    finally:
        os.close(root_fd)


def _validate_private_child_directory(
    publication: _ControlsPublication,
    name: str,
    expected: tuple[int, int],
) -> None:
    if type(publication) is not _ControlsPublication:
        raise TypeError
    _validate_child_name(name)
    flags = _required_flags(
        "O_RDONLY",
        "O_DIRECTORY",
        "O_NOFOLLOW",
        "O_CLOEXEC",
    )
    parts = publication.campaign_dir.split("/")[1:]
    for _ in range(2):
        root_fd = _open_expected_root(
            parts,
            publication.directory_fingerprints,
            flags,
        )
        try:
            _validate_root(os.fstat(root_fd))
            child_fd = os.open(name, flags, dir_fd=root_fd)
            try:
                child = os.fstat(child_fd)
                _validate_private_directory(child)
                if _fingerprint(child) != expected:
                    raise ValueError
                _require_empty_directory(child_fd)
                current = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
                _validate_private_directory(current, expected=child)
            finally:
                os.close(child_fd)
        finally:
            os.close(root_fd)


def _validate_child_name(name: str) -> None:
    if type(name) is not str or not name or name in {".", ".."} or "/" in name:
        raise ValueError


def _require_empty_directory(fd: int) -> None:
    sentinel = object()
    with os.scandir(fd) as entries:
        if next(entries, sentinel) is not sentinel:
            raise ValueError


def _validate_private_directory(
    current: os.stat_result,
    *,
    expected: os.stat_result | None = None,
) -> None:
    if not stat.S_ISDIR(current.st_mode):
        raise ValueError
    if stat.S_IMODE(current.st_mode) != 0o700 or current.st_uid != os.geteuid():
        raise ValueError
    if expected is not None and _fingerprint(current) != _fingerprint(expected):
        raise ValueError


def _open_expected_root(
    parts: list[str],
    expected: tuple[tuple[int, int], ...],
    directory_flags: int,
) -> int:
    current_fd = os.open("/", directory_flags)
    try:
        if _fingerprint(os.fstat(current_fd)) != expected[0]:
            raise ValueError
        for index, component in enumerate(parts, start=1):
            next_fd = os.open(component, directory_flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
            if _fingerprint(os.fstat(current_fd)) != expected[index]:
                raise ValueError
        return current_fd
    except BaseException:
        os.close(current_fd)
        raise


def _validate_root_separation(
    campaign_root: str,
    protected_roots: Sequence[str],
) -> None:
    if not isinstance(protected_roots, (tuple, list)):
        raise TypeError
    campaign_real = os.path.realpath(campaign_root)
    for raw_root in protected_roots:
        if type(raw_root) is not str or not raw_root or "\x00" in raw_root:
            raise TypeError
        if not os.path.isabs(raw_root) or os.path.normpath(raw_root) != raw_root:
            raise ValueError
        if _paths_overlap(campaign_root, raw_root) or _paths_overlap(
            campaign_real,
            os.path.realpath(raw_root),
        ):
            raise ValueError


def _paths_overlap(left: str, right: str) -> bool:
    try:
        common = os.path.commonpath((left, right))
    except ValueError:
        raise ValueError from None
    return common in {left, right}


def _verify_leaf_bytes(
    root_fd: int,
    *,
    filename: str,
    leaf_fingerprint: tuple[int, int, int, int],
    payload: bytes,
    max_bytes: int,
) -> None:
    flags = _required_flags("O_RDONLY", "O_NOFOLLOW", "O_CLOEXEC", "O_NONBLOCK")
    fd = os.open(filename, flags, dir_fd=root_fd)
    try:
        before = os.fstat(fd)
        _validate_leaf(before, expected_size=len(payload))
        if _leaf_fingerprint(before) != leaf_fingerprint:
            raise ValueError
        body = bytearray()
        while len(body) <= max_bytes:
            chunk = os.read(fd, min(65536, max_bytes + 1 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
        if bytes(body) != payload:
            raise ValueError
        after = os.fstat(fd)
        _validate_leaf(after, expected_size=len(payload), expected=before)
        current = os.stat(filename, dir_fd=root_fd, follow_symlinks=False)
        _validate_leaf(current, expected_size=len(payload), expected=before)
    finally:
        os.close(fd)


def _required_flags(*names: str) -> int:
    flags = 0
    for name in names:
        value = getattr(os, name, None)
        if type(value) is not int:
            raise RuntimeError
        flags |= value
    return flags


def _validate_root(
    current: os.stat_result, expected: os.stat_result | None = None
) -> None:
    if not stat.S_ISDIR(current.st_mode):
        raise ValueError
    if stat.S_IMODE(current.st_mode) != 0o700 or current.st_uid != os.geteuid():
        raise ValueError
    if expected is not None and _fingerprint(current) != _fingerprint(expected):
        raise ValueError


def _validate_root_name(
    parent_fd: int,
    name: str,
    expected: os.stat_result,
) -> None:
    current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    _validate_root(current, expected=expected)


def _write_leaf(
    root_fd: int,
    flags: int,
    payload: bytes,
    *,
    filename: str,
) -> os.stat_result:
    fd = os.open(filename, flags, 0o600, dir_fd=root_fd)
    try:
        before = os.fstat(fd)
        _validate_leaf(before, expected_size=0)
        offset = 0
        while offset < len(payload):
            written = os.write(fd, payload[offset:])
            if written <= 0:
                raise OSError
            offset += written
        os.fsync(fd)
        after = os.fstat(fd)
        _validate_leaf(after, expected_size=len(payload), expected=before)
        current = os.stat(filename, dir_fd=root_fd, follow_symlinks=False)
        _validate_leaf(current, expected_size=len(payload), expected=before)
        return after
    finally:
        os.close(fd)


def _validate_leaf(
    current: os.stat_result,
    *,
    expected_size: int,
    expected: os.stat_result | None = None,
) -> None:
    if not stat.S_ISREG(current.st_mode) or current.st_nlink != 1:
        raise ValueError
    if stat.S_IMODE(current.st_mode) != 0o600 or current.st_uid != os.geteuid():
        raise ValueError
    if current.st_size != expected_size:
        raise ValueError
    if expected is not None and _fingerprint(current) != _fingerprint(expected):
        raise ValueError


def _fingerprint(value: os.stat_result) -> tuple[int, int]:
    return (value.st_dev, value.st_ino)


def _leaf_fingerprint(value: os.stat_result) -> tuple[int, int, int, int]:
    return (value.st_dev, value.st_ino, value.st_ctime_ns, value.st_mtime_ns)
