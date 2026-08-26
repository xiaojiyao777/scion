"""Dirfd publication for the third initial-screening declaration leaf."""

from __future__ import annotations

import os
from typing import Any

from scion.core.initial_screening_study_controls_io import (
    _ControlsPublication,
    _leaf_fingerprint,
    _open_expected_root,
    _require_exact_names,
    _required_flags,
    _validate_child_name,
    _validate_leaf,
    _validate_root,
    _verify_leaf_bytes,
)


def _publish_third_control(
    publication: _ControlsPublication,
    *,
    first_filename: str,
    first_payload: bytes,
    second_filename: str,
    second_payload: bytes,
    second_fingerprint: tuple[int, int, int, int],
    filename: str,
    payload: bytes,
    max_bytes: int,
) -> tuple[int, int, int, int]:
    """Attach one held-fd third leaf without deleting either prior leaf."""

    _validate_publish_inputs(
        publication,
        first_filename=first_filename,
        first_payload=first_payload,
        second_filename=second_filename,
        second_payload=second_payload,
        second_fingerprint=second_fingerprint,
        filename=filename,
        payload=payload,
        max_bytes=max_bytes,
    )
    directory_flags = _required_flags(
        "O_RDONLY", "O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC"
    )
    leaf_flags = _required_flags(
        "O_WRONLY", "O_CREAT", "O_EXCL", "O_NOFOLLOW", "O_CLOEXEC"
    )
    parts = publication.campaign_dir.split("/")[1:]
    root_fd = _open_expected_root(
        parts, publication.directory_fingerprints, directory_flags
    )
    attached_fd: int | None = None
    try:
        root_stat = os.fstat(root_fd)
        _validate_root(root_stat)
        _verify_prior_leaves(
            root_fd,
            publication,
            first_filename=first_filename,
            first_payload=first_payload,
            second_filename=second_filename,
            second_payload=second_payload,
            second_fingerprint=second_fingerprint,
        )
        _require_exact_names(root_fd, (first_filename, second_filename))
        attached_fd = os.open(filename, leaf_flags, 0o600, dir_fd=root_fd)
        before = os.fstat(attached_fd)
        _validate_leaf(before, expected_size=0)
        _write_all(attached_fd, payload)
        os.fsync(attached_fd)
        after = os.fstat(attached_fd)
        _validate_leaf(after, expected_size=len(payload), expected=before)
        fingerprint = _leaf_fingerprint(after)
        os.fsync(root_fd)
        _validate_root(os.fstat(root_fd), expected=root_stat)
        _verify_all_three(
            root_fd,
            publication,
            first_filename=first_filename,
            first_payload=first_payload,
            second_filename=second_filename,
            second_payload=second_payload,
            second_fingerprint=second_fingerprint,
            filename=filename,
            payload=payload,
            fingerprint=fingerprint,
            max_bytes=max_bytes,
            require_exact_names=True,
        )
        _validate_third_control_publication(
            publication,
            first_filename=first_filename,
            first_payload=first_payload,
            second_filename=second_filename,
            second_payload=second_payload,
            second_fingerprint=second_fingerprint,
            filename=filename,
            payload=payload,
            fingerprint=fingerprint,
            max_bytes=max_bytes,
            require_exact_names=True,
        )
        # This is the publication commit point.  Descriptor cleanup below must
        # neither revoke the successful carrier nor replace an earlier failure.
        return fingerprint
    except BaseException:
        try:
            _rollback_exact_third_leaf(
                root_fd,
                publication,
                first_filename=first_filename,
                first_payload=first_payload,
                second_filename=second_filename,
                second_payload=second_payload,
                second_fingerprint=second_fingerprint,
                filename=filename,
                attached_fd=attached_fd,
            )
        except BaseException as ignored_cleanup_error:  # noqa: BLE001 - best effort
            del ignored_cleanup_error
        raise
    finally:
        try:
            if attached_fd is not None:
                try:
                    os.close(attached_fd)
                except BaseException as ignored_close_error:  # noqa: BLE001
                    del ignored_close_error
        except BaseException as ignored_attached_cleanup_error:  # noqa: BLE001
            del ignored_attached_cleanup_error
        try:
            os.close(root_fd)
        except BaseException as ignored_root_close_error:  # noqa: BLE001
            del ignored_root_close_error


def _validate_third_control_publication(
    publication: _ControlsPublication,
    *,
    first_filename: str,
    first_payload: bytes,
    second_filename: str,
    second_payload: bytes,
    second_fingerprint: tuple[int, int, int, int],
    filename: str,
    payload: bytes,
    fingerprint: tuple[int, int, int, int],
    max_bytes: int,
    require_exact_names: bool,
) -> None:
    _validate_publish_inputs(
        publication,
        first_filename=first_filename,
        first_payload=first_payload,
        second_filename=second_filename,
        second_payload=second_payload,
        second_fingerprint=second_fingerprint,
        filename=filename,
        payload=payload,
        max_bytes=max_bytes,
    )
    _validate_fingerprint(fingerprint)
    if type(require_exact_names) is not bool:
        raise TypeError
    flags = _required_flags("O_RDONLY", "O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC")
    parts = publication.campaign_dir.split("/")[1:]
    for _ in range(2):
        root_fd = _open_expected_root(parts, publication.directory_fingerprints, flags)
        try:
            _validate_root(os.fstat(root_fd))
            _verify_all_three(
                root_fd,
                publication,
                first_filename=first_filename,
                first_payload=first_payload,
                second_filename=second_filename,
                second_payload=second_payload,
                second_fingerprint=second_fingerprint,
                filename=filename,
                payload=payload,
                fingerprint=fingerprint,
                max_bytes=max_bytes,
                require_exact_names=require_exact_names,
            )
        finally:
            os.close(root_fd)


def _verify_all_three(
    root_fd: int,
    publication: _ControlsPublication,
    *,
    first_filename: str,
    first_payload: bytes,
    second_filename: str,
    second_payload: bytes,
    second_fingerprint: tuple[int, int, int, int],
    filename: str,
    payload: bytes,
    fingerprint: tuple[int, int, int, int],
    max_bytes: int,
    require_exact_names: bool,
) -> None:
    _verify_prior_leaves(
        root_fd,
        publication,
        first_filename=first_filename,
        first_payload=first_payload,
        second_filename=second_filename,
        second_payload=second_payload,
        second_fingerprint=second_fingerprint,
    )
    _verify_leaf_bytes(
        root_fd,
        filename=filename,
        leaf_fingerprint=fingerprint,
        payload=payload,
        max_bytes=max_bytes,
    )
    identities = {
        publication.leaf_fingerprint[:2],
        second_fingerprint[:2],
        fingerprint[:2],
    }
    if len(identities) != 3:
        raise ValueError
    if require_exact_names:
        _require_exact_names(root_fd, (first_filename, second_filename, filename))


def _verify_prior_leaves(
    root_fd: int,
    publication: _ControlsPublication,
    *,
    first_filename: str,
    first_payload: bytes,
    second_filename: str,
    second_payload: bytes,
    second_fingerprint: tuple[int, int, int, int],
) -> None:
    _verify_leaf_bytes(
        root_fd,
        filename=first_filename,
        leaf_fingerprint=publication.leaf_fingerprint,
        payload=first_payload,
        max_bytes=len(first_payload),
    )
    _verify_leaf_bytes(
        root_fd,
        filename=second_filename,
        leaf_fingerprint=second_fingerprint,
        payload=second_payload,
        max_bytes=len(second_payload),
    )


def _rollback_exact_third_leaf(
    root_fd: int,
    publication: _ControlsPublication,
    *,
    first_filename: str,
    first_payload: bytes,
    second_filename: str,
    second_payload: bytes,
    second_fingerprint: tuple[int, int, int, int],
    filename: str,
    attached_fd: int | None,
) -> None:
    if attached_fd is None:
        return
    _validate_root(os.fstat(root_fd))
    _require_exact_names(root_fd, (first_filename, second_filename, filename))
    _verify_prior_leaves(
        root_fd,
        publication,
        first_filename=first_filename,
        first_payload=first_payload,
        second_filename=second_filename,
        second_payload=second_payload,
        second_fingerprint=second_fingerprint,
    )
    held = os.fstat(attached_fd)
    _validate_leaf(held, expected_size=held.st_size)
    current = os.stat(filename, dir_fd=root_fd, follow_symlinks=False)
    _validate_leaf(current, expected_size=current.st_size, expected=held)
    os.unlink(filename, dir_fd=root_fd)
    os.fsync(root_fd)
    _require_exact_names(root_fd, (first_filename, second_filename))


def _validate_publish_inputs(
    publication: Any,
    *,
    first_filename: Any,
    first_payload: Any,
    second_filename: Any,
    second_payload: Any,
    second_fingerprint: Any,
    filename: Any,
    payload: Any,
    max_bytes: Any,
) -> None:
    if type(publication) is not _ControlsPublication:
        raise TypeError
    for name in (first_filename, second_filename, filename):
        _validate_child_name(name)
    if len({first_filename, second_filename, filename}) != 3:
        raise ValueError
    if (
        type(first_payload) is not bytes
        or type(second_payload) is not bytes
        or type(payload) is not bytes
        or type(max_bytes) is not int
        or max_bytes <= 0
        or len(payload) > max_bytes
    ):
        raise TypeError
    _validate_fingerprint(publication.leaf_fingerprint)
    _validate_fingerprint(second_fingerprint)


def _validate_fingerprint(value: Any) -> None:
    if (
        type(value) is not tuple
        or len(value) != 4
        or any(type(item) is not int for item in value)
    ):
        raise TypeError


def _write_all(fd: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(fd, payload[offset:])
        if written <= 0:
            raise OSError
        offset += written
