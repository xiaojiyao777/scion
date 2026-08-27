"""Dirfd publication for the fourth initial-screening declaration leaf."""

from __future__ import annotations

import os
from typing import Any

from scion.core.initial_screening_research_context import (
    _ERROR,
    _InitialScreeningResearchContextError,
)
from scion.core.initial_screening_study_controls_io import (
    _ControlsPublication,
    _fingerprint,
    _leaf_fingerprint,
    _open_expected_root,
    _require_exact_names,
    _required_flags,
    _validate_child_name,
    _validate_leaf,
    _validate_root,
    _verify_leaf_bytes,
)


def _fixed_failure() -> _InitialScreeningResearchContextError:
    return _InitialScreeningResearchContextError(_ERROR)


def _publish_fourth_control(
    publication: _ControlsPublication,
    *,
    first_filename: str,
    first_payload: bytes,
    second_filename: str,
    second_payload: bytes,
    second_fingerprint: tuple[int, int, int, int],
    third_filename: str,
    third_payload: bytes,
    third_fingerprint: tuple[int, int, int, int],
    filename: str,
    payload: bytes,
    max_bytes: int,
) -> tuple[int, int, int, int]:
    """Attach one fail-closed fourth-leaf reservation.

    A successful ``O_EXCL`` creation is irreversible here.  Any later failure
    leaves that literal name in place so this boundary never removes a
    concurrently replaced inode and a retry cannot silently overwrite the
    incomplete reservation.
    """

    root_fd: int | None = None
    attached_fd: int | None = None
    fingerprint: tuple[int, int, int, int] | None = None
    failed = False
    try:
        _validate_publish_inputs(
            publication,
            first_filename=first_filename,
            first_payload=first_payload,
            second_filename=second_filename,
            second_payload=second_payload,
            second_fingerprint=second_fingerprint,
            third_filename=third_filename,
            third_payload=third_payload,
            third_fingerprint=third_fingerprint,
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
            third_filename=third_filename,
            third_payload=third_payload,
            third_fingerprint=third_fingerprint,
        )
        _validate_identity_separation(
            root_stat,
            (
                publication.leaf_fingerprint,
                second_fingerprint,
                third_fingerprint,
            ),
        )
        _require_exact_names(root_fd, (first_filename, second_filename, third_filename))
        _validate_root(os.fstat(root_fd), expected=root_stat)
        attached_fd = os.open(filename, leaf_flags, 0o600, dir_fd=root_fd)
        os.fchmod(attached_fd, 0o600)
        before = os.fstat(attached_fd)
        _validate_leaf(before, expected_size=0)
        _write_all(attached_fd, payload)
        os.fsync(attached_fd)
        after = os.fstat(attached_fd)
        _validate_leaf(after, expected_size=len(payload), expected=before)
        fingerprint = _leaf_fingerprint(after)
        os.fsync(root_fd)
        _validate_root(os.fstat(root_fd), expected=root_stat)
        _verify_all_four(
            root_fd,
            root_stat,
            publication,
            first_filename=first_filename,
            first_payload=first_payload,
            second_filename=second_filename,
            second_payload=second_payload,
            second_fingerprint=second_fingerprint,
            third_filename=third_filename,
            third_payload=third_payload,
            third_fingerprint=third_fingerprint,
            filename=filename,
            payload=payload,
            fingerprint=fingerprint,
            max_bytes=max_bytes,
            require_exact_names=True,
        )
        _validate_fourth_control_publication(
            publication,
            first_filename=first_filename,
            first_payload=first_payload,
            second_filename=second_filename,
            second_payload=second_payload,
            second_fingerprint=second_fingerprint,
            third_filename=third_filename,
            third_payload=third_payload,
            third_fingerprint=third_fingerprint,
            filename=filename,
            payload=payload,
            fingerprint=fingerprint,
            max_bytes=max_bytes,
            require_exact_names=True,
        )
    except BaseException:  # noqa: BLE001 - fixed private boundary
        failed = True
    finally:
        if attached_fd is not None:
            try:
                os.close(attached_fd)
            except BaseException as ignored_attached_close_error:  # noqa: BLE001
                del ignored_attached_close_error
        if root_fd is not None:
            try:
                os.close(root_fd)
            except BaseException as ignored_root_close_error:  # noqa: BLE001
                del ignored_root_close_error
    if failed or fingerprint is None:
        raise _fixed_failure()
    return fingerprint


def _validate_fourth_control_publication(
    publication: _ControlsPublication,
    *,
    first_filename: str,
    first_payload: bytes,
    second_filename: str,
    second_payload: bytes,
    second_fingerprint: tuple[int, int, int, int],
    third_filename: str,
    third_payload: bytes,
    third_fingerprint: tuple[int, int, int, int],
    filename: str,
    payload: bytes,
    fingerprint: tuple[int, int, int, int],
    max_bytes: int,
    require_exact_names: bool,
) -> None:
    """Validate all four leaves through two independent absolute rewalks."""

    _validate_publish_inputs(
        publication,
        first_filename=first_filename,
        first_payload=first_payload,
        second_filename=second_filename,
        second_payload=second_payload,
        second_fingerprint=second_fingerprint,
        third_filename=third_filename,
        third_payload=third_payload,
        third_fingerprint=third_fingerprint,
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
            root_stat = os.fstat(root_fd)
            _validate_root(root_stat)
            _verify_all_four(
                root_fd,
                root_stat,
                publication,
                first_filename=first_filename,
                first_payload=first_payload,
                second_filename=second_filename,
                second_payload=second_payload,
                second_fingerprint=second_fingerprint,
                third_filename=third_filename,
                third_payload=third_payload,
                third_fingerprint=third_fingerprint,
                filename=filename,
                payload=payload,
                fingerprint=fingerprint,
                max_bytes=max_bytes,
                require_exact_names=require_exact_names,
            )
        finally:
            try:
                os.close(root_fd)
            except BaseException as ignored_close_error:  # noqa: BLE001
                del ignored_close_error


def _verify_all_four(
    root_fd: int,
    root_stat: os.stat_result,
    publication: _ControlsPublication,
    *,
    first_filename: str,
    first_payload: bytes,
    second_filename: str,
    second_payload: bytes,
    second_fingerprint: tuple[int, int, int, int],
    third_filename: str,
    third_payload: bytes,
    third_fingerprint: tuple[int, int, int, int],
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
        third_filename=third_filename,
        third_payload=third_payload,
        third_fingerprint=third_fingerprint,
    )
    _verify_leaf_bytes(
        root_fd,
        filename=filename,
        leaf_fingerprint=fingerprint,
        payload=payload,
        max_bytes=max_bytes,
    )
    _validate_identity_separation(
        root_stat,
        (
            publication.leaf_fingerprint,
            second_fingerprint,
            third_fingerprint,
            fingerprint,
        ),
    )
    if require_exact_names:
        _require_exact_names(
            root_fd,
            (first_filename, second_filename, third_filename, filename),
        )
    _validate_root(os.fstat(root_fd), expected=root_stat)


def _verify_prior_leaves(
    root_fd: int,
    publication: _ControlsPublication,
    *,
    first_filename: str,
    first_payload: bytes,
    second_filename: str,
    second_payload: bytes,
    second_fingerprint: tuple[int, int, int, int],
    third_filename: str,
    third_payload: bytes,
    third_fingerprint: tuple[int, int, int, int],
) -> None:
    for filename, fingerprint, payload in (
        (first_filename, publication.leaf_fingerprint, first_payload),
        (second_filename, second_fingerprint, second_payload),
        (third_filename, third_fingerprint, third_payload),
    ):
        _verify_leaf_bytes(
            root_fd,
            filename=filename,
            leaf_fingerprint=fingerprint,
            payload=payload,
            max_bytes=len(payload),
        )


def _validate_identity_separation(
    root_stat: os.stat_result,
    leaf_fingerprints: tuple[tuple[int, int, int, int], ...],
) -> None:
    identities = {_fingerprint(root_stat)}
    identities.update(fingerprint[:2] for fingerprint in leaf_fingerprints)
    if len(identities) != len(leaf_fingerprints) + 1:
        raise ValueError


def _validate_publish_inputs(
    publication: Any,
    *,
    first_filename: Any,
    first_payload: Any,
    second_filename: Any,
    second_payload: Any,
    second_fingerprint: Any,
    third_filename: Any,
    third_payload: Any,
    third_fingerprint: Any,
    filename: Any,
    payload: Any,
    max_bytes: Any,
) -> None:
    if type(publication) is not _ControlsPublication:
        raise TypeError
    names = (first_filename, second_filename, third_filename, filename)
    for name in names:
        _validate_child_name(name)
    if len(set(names)) != 4:
        raise ValueError
    if (
        type(first_payload) is not bytes
        or type(second_payload) is not bytes
        or type(third_payload) is not bytes
        or type(payload) is not bytes
        or type(max_bytes) is not int
    ):
        raise TypeError
    if max_bytes != 64 << 20 or len(payload) > max_bytes:
        raise ValueError
    _validate_fingerprint(publication.leaf_fingerprint)
    _validate_fingerprint(second_fingerprint)
    _validate_fingerprint(third_fingerprint)


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
