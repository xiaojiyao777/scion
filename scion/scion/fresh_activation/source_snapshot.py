"""Linux-only dormant authority for one stably absent campaign target.

This module implements only the first fresh-activation boundary.  It pins the
configured campaign root and every relative ancestor, takes a non-blocking
exclusive lock on the exact parent directory, proves the target and its SQLite
sidecars absent twice, and issues one opaque staging capability.  The reserved
``PublicationPermit`` type has no issuer or consumer in this slice.  This module
does not open SQLite, create staging, publish a target, write receipts, or issue
``CampaignDatabaseAuthority``.  No production composition imports it.
"""

from __future__ import annotations

import enum
import errno
import fcntl
import hashlib
import os
import secrets
import stat
import sys
import threading
import weakref
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final

__all__ = (
    "FreshActivationBoundaryError",
    "FreshActivationHoldError",
    "FreshActivationLifecycleError",
    "FreshActivationRequestError",
    "InvalidFreshActivationCapabilityError",
    "PublicationPermit",
    "StagingCapability",
    "acquire_staging_capability",
)


_SIDECAR_SUFFIXES: Final[tuple[str, ...]] = ("-wal", "-shm", "-journal")


class FreshActivationBoundaryError(RuntimeError):
    """Base error for the dormant fresh-only source boundary."""


class FreshActivationRequestError(ValueError, FreshActivationBoundaryError):
    """The caller did not provide one closed, normalized fresh-create request."""


class FreshActivationHoldError(FreshActivationBoundaryError):
    """No fresh-create authority exists for the observed filesystem state."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class InvalidFreshActivationCapabilityError(
    TypeError,
    FreshActivationBoundaryError,
):
    """A capability is forged, malformed, or belongs to another lifecycle."""


class FreshActivationLifecycleError(FreshActivationBoundaryError):
    """A genuine fresh-activation capability was reused or already settled."""


class _OpaqueCapability:
    __slots__ = ("__issuing_pid", "__weakref__")

    def __new__(cls, *_args: object, **_kwargs: object) -> "_OpaqueCapability":
        raise InvalidFreshActivationCapabilityError(
            f"{cls.__name__} is issued only by the fresh activation boundary"
        )

    def __copy__(self) -> "_OpaqueCapability":
        raise InvalidFreshActivationCapabilityError(
            f"{type(self).__name__} cannot be copied"
        )

    def __deepcopy__(self, _memo: dict[int, object]) -> "_OpaqueCapability":
        raise InvalidFreshActivationCapabilityError(
            f"{type(self).__name__} cannot be copied"
        )

    def __reduce__(self) -> object:
        raise InvalidFreshActivationCapabilityError(
            f"{type(self).__name__} cannot be pickled"
        )

    def __reduce_ex__(self, _protocol: int) -> object:
        raise InvalidFreshActivationCapabilityError(
            f"{type(self).__name__} cannot be pickled"
        )


class StagingCapability(_OpaqueCapability):
    """One-shot permission to begin offline staging for one absent target."""

    __slots__ = ()

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("StagingCapability is sealed")


class PublicationPermit(_OpaqueCapability):
    """Reserved sealed type; this dormant slice has no issuer or consumer."""

    __slots__ = ()

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("PublicationPermit is sealed")


class _ConsumedStagingAuthority(_OpaqueCapability):
    __slots__ = ()

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("_ConsumedStagingAuthority is sealed")


class _Phase(enum.Enum):
    ISSUED = enum.auto()
    SPENT = enum.auto()


@dataclass(frozen=True, slots=True)
class _DirectoryIdentity:
    device: int
    inode: int
    mount_id: int


@dataclass(slots=True)
class _PinnedAuthority:
    issuing_pid: int
    root_path: str
    parent_parts: tuple[str, ...]
    chain_identities: tuple[_DirectoryIdentity, ...]
    descriptors: tuple[int, ...]
    target_basename: str
    staging_basename: str
    cutover_id: str
    policy_generation: str
    schema_generation: str
    writer_generation: str
    absence_observation: object
    closed: bool = False

    @property
    def parent_fd(self) -> int:
        return self.descriptors[-1]

    @property
    def parent_identity(self) -> _DirectoryIdentity:
        return self.chain_identities[-1]


@dataclass(slots=True)
class _HandleState:
    authority: _PinnedAuthority
    phase: _Phase = _Phase.ISSUED
    finalizer: weakref.finalize | None = None


_STAGING_CAPABILITY_STATES: Final[
    weakref.WeakKeyDictionary[StagingCapability, _HandleState]
] = weakref.WeakKeyDictionary()
_STAGING_AUTHORITY_STATES: Final[
    weakref.WeakKeyDictionary[_ConsumedStagingAuthority, _HandleState]
] = weakref.WeakKeyDictionary()
_STATE_LOCK: Final[threading.RLock] = threading.RLock()


def _bind_handle_process(handle: _OpaqueCapability, issuing_pid: int) -> None:
    object.__setattr__(
        handle,
        "_OpaqueCapability__issuing_pid",
        issuing_pid,
    )


def _assert_handle_process(handle: object) -> None:
    try:
        issuing_pid = object.__getattribute__(
            handle,
            "_OpaqueCapability__issuing_pid",
        )
    except (AttributeError, TypeError) as exc:
        raise InvalidFreshActivationCapabilityError(
            "fresh activation handle has no issuing-process binding"
        ) from exc
    if issuing_pid != os.getpid():
        raise FreshActivationLifecycleError(
            "fresh activation authority cannot cross a process boundary"
        )


def _require_linux_primitives() -> None:
    missing = tuple(
        name
        for name in ("O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC")
        if not hasattr(os, name)
    )
    descriptor_relative = (
        os.open in os.supports_dir_fd
        and os.stat in os.supports_dir_fd
        and os.stat in os.supports_follow_symlinks
    )
    if (
        not sys.platform.startswith("linux")
        or missing
        or not descriptor_relative
        or not hasattr(fcntl, "flock")
        or not hasattr(fcntl, "LOCK_EX")
        or not hasattr(fcntl, "LOCK_NB")
    ):
        detail = "" if not missing else f"; missing {', '.join(missing)}"
        raise FreshActivationHoldError(
            "required_linux_primitive_unavailable",
            "fresh activation requires Linux descriptor-relative/no-follow and flock "
            f"primitives with no fallback{detail}",
        )


def _normalized_root(value: str | os.PathLike[str]) -> str:
    raw = os.fspath(value)
    if not isinstance(raw, str):
        raise FreshActivationRequestError("campaign_root must be a text path")
    if not raw or "\x00" in raw or not os.path.isabs(raw):
        raise FreshActivationRequestError(
            "campaign_root must be one nonempty absolute text path"
        )
    normalized = os.path.normpath(raw)
    if normalized != raw:
        raise FreshActivationRequestError(
            "campaign_root must already be lexically normalized"
        )
    return normalized


def _normalized_target(value: str) -> tuple[tuple[str, ...], str]:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise FreshActivationRequestError(
            "target_relative_path must be one normalized POSIX text path"
        )
    path = PurePosixPath(value)
    parts = path.parts
    if (
        path.is_absolute()
        or path.as_posix() != value
        or not parts
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise FreshActivationRequestError(
            "target_relative_path must be normalized and contained by campaign_root"
        )
    return tuple(parts[:-1]), parts[-1]


def _exact_text(value: str, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or "\x00" in value
    ):
        raise FreshActivationRequestError(f"{field} must be one exact nonempty string")
    return value


def _new_staging_basename(cutover_id: str) -> str:
    cutover_tag = hashlib.sha256(cutover_id.encode("utf-8")).hexdigest()[:20]
    return f".scion-{cutover_tag}-{secrets.token_hex(16)}.staging"


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _mount_id(descriptor: int) -> int:
    fdinfo = f"/proc/self/fdinfo/{descriptor}"
    fd: int | None = None
    try:
        fd = os.open(fdinfo, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        payload = os.read(fd, 16_385)
    except OSError as exc:
        raise FreshActivationHoldError(
            "mount_identity_unavailable",
            "Linux mount identity cannot be read from the pinned descriptor",
        ) from exc
    finally:
        if fd is not None:
            os.close(fd)
    if len(payload) > 16_384:
        raise FreshActivationHoldError(
            "mount_identity_unavailable",
            "Linux descriptor metadata exceeds the closed mount-identity format",
        )
    try:
        lines = payload.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise FreshActivationHoldError(
            "mount_identity_unavailable",
            "Linux descriptor metadata is not ASCII",
        ) from exc
    values = [
        line.removeprefix("mnt_id:\t")
        for line in lines
        if line.startswith("mnt_id:\t")
    ]
    if len(values) != 1 or not values[0].isdigit() or int(values[0]) <= 0:
        raise FreshActivationHoldError(
            "mount_identity_unavailable",
            "Linux descriptor metadata has no exact positive mount identity",
        )
    return int(values[0])


def _identity(descriptor: int) -> _DirectoryIdentity:
    try:
        metadata = os.fstat(descriptor)
    except OSError as exc:
        raise FreshActivationHoldError(
            "descriptor_identity_unavailable",
            "pinned directory descriptor is no longer observable",
        ) from exc
    if not stat.S_ISDIR(metadata.st_mode):
        raise FreshActivationHoldError(
            "non_directory_ancestor",
            "fresh target ancestry contains a non-directory",
        )
    return _DirectoryIdentity(
        int(metadata.st_dev),
        int(metadata.st_ino),
        _mount_id(descriptor),
    )


def _open_chain(root_path: str, parent_parts: tuple[str, ...]) -> tuple[int, ...]:
    descriptors: list[int] = []
    try:
        descriptors.append(os.open(root_path, _directory_flags()))
        for part in parent_parts:
            descriptors.append(
                os.open(part, _directory_flags(), dir_fd=descriptors[-1])
            )
        for descriptor in descriptors:
            os.set_inheritable(descriptor, False)
            _identity(descriptor)
        return tuple(descriptors)
    except FreshActivationBoundaryError:
        _close_descriptors(descriptors)
        raise
    except OSError as exc:
        _close_descriptors(descriptors)
        raise FreshActivationHoldError(
            "ancestor_unavailable_or_unsafe",
            "campaign root or target ancestor is unavailable, changed, or a symlink",
        ) from exc


def _close_descriptors(descriptors: object) -> None:
    if not isinstance(descriptors, (list, tuple)):
        return
    for descriptor in reversed(descriptors):
        try:
            os.close(descriptor)
        except OSError:
            pass


def _cleanup_authority(authority: _PinnedAuthority) -> None:
    if os.getpid() != authority.issuing_pid:
        # ``flock`` is attached to the inherited open-file description.  An
        # explicit LOCK_UN in a fork child would silently unlock the parent's
        # authority.  Closing only the child's descriptor copies is safe.
        if not authority.closed:
            authority.closed = True
            _close_descriptors(authority.descriptors)
        return
    with _STATE_LOCK:
        if authority.closed:
            return
        authority.closed = True
    try:
        fcntl.flock(authority.parent_fd, fcntl.LOCK_UN)
    except OSError:
        pass
    _close_descriptors(authority.descriptors)


def _assert_chain_stable(authority: _PinnedAuthority) -> None:
    if authority.closed:
        raise FreshActivationLifecycleError("pinned directory authority is closed")
    reopened = _open_chain(authority.root_path, authority.parent_parts)
    try:
        current = tuple(_identity(descriptor) for descriptor in reopened)
        pinned = tuple(_identity(descriptor) for descriptor in authority.descriptors)
        if current != authority.chain_identities or pinned != authority.chain_identities:
            raise FreshActivationHoldError(
                "directory_identity_drift",
                "campaign root, target ancestor, or pinned parent identity changed",
            )
    finally:
        _close_descriptors(reopened)


def _assert_names_fit(parent_fd: int, names: tuple[str, ...]) -> None:
    try:
        name_max = int(os.fpathconf(parent_fd, "PC_NAME_MAX"))
    except (OSError, ValueError) as exc:
        raise FreshActivationHoldError(
            "directory_limits_unavailable",
            "pinned parent name limits cannot be observed",
        ) from exc
    if any(len(os.fsencode(name)) > name_max for name in names):
        raise FreshActivationRequestError(
            "target or activation staging basename exceeds the pinned directory limit"
        )


def _assert_absent(parent_fd: int, name: str, *, reason_code: str) -> None:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise FreshActivationHoldError(
            "source_observation_failed",
            f"cannot prove {name!r} absent under the pinned parent",
        ) from exc
    raise FreshActivationHoldError(
        reason_code,
        f"fresh activation requires absent path; observed {name!r}",
    )


def _assert_target_bundle_absent(authority: _PinnedAuthority) -> None:
    _assert_absent(
        authority.parent_fd,
        authority.target_basename,
        reason_code="existing_target_hold",
    )
    for suffix in _SIDECAR_SUFFIXES:
        _assert_absent(
            authority.parent_fd,
            f"{authority.target_basename}{suffix}",
            reason_code="existing_sidecar_hold",
        )


def _assert_fresh_source_stable(authority: _PinnedAuthority) -> None:
    _assert_chain_stable(authority)
    _assert_target_bundle_absent(authority)
    _assert_absent(
        authority.parent_fd,
        authority.staging_basename,
        reason_code="staging_collision_hold",
    )
    _assert_chain_stable(authority)
    _assert_target_bundle_absent(authority)
    _assert_absent(
        authority.parent_fd,
        authority.staging_basename,
        reason_code="staging_collision_hold",
    )


def acquire_staging_capability(
    *,
    campaign_root: str | os.PathLike[str],
    target_relative_path: str,
    cutover_id: str,
    policy_generation: str,
    schema_generation: str,
    writer_generation: str,
) -> StagingCapability:
    """Pin and lock one absent target, returning a dormant one-shot capability.

    Every non-positive filesystem observation raises ``FreshActivationHoldError``.
    The function never creates or opens the final target and performs no retry.
    """

    _require_linux_primitives()
    root_path = _normalized_root(campaign_root)
    parent_parts, target_basename = _normalized_target(target_relative_path)
    cutover = _exact_text(cutover_id, field="cutover_id")
    policy = _exact_text(policy_generation, field="policy_generation")
    schema = _exact_text(schema_generation, field="schema_generation")
    writer = _exact_text(writer_generation, field="writer_generation")
    staging_basename = _new_staging_basename(cutover)

    descriptors = _open_chain(root_path, parent_parts)
    locked = False
    authority: _PinnedAuthority | None = None
    try:
        parent_fd = descriptors[-1]
        _assert_names_fit(
            parent_fd,
            (
                target_basename,
                *(f"{target_basename}{suffix}" for suffix in _SIDECAR_SUFFIXES),
                staging_basename,
            ),
        )
        try:
            fcntl.flock(parent_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as exc:
            if exc.errno not in {errno.EACCES, errno.EAGAIN}:
                raise FreshActivationHoldError(
                    "initializer_lock_failed",
                    "exclusive initializer lock could not be established",
                ) from exc
            raise FreshActivationHoldError(
                "initializer_lock_unavailable",
                "another initializer owns the pinned parent directory",
            ) from exc

        authority = _PinnedAuthority(
            issuing_pid=os.getpid(),
            root_path=root_path,
            parent_parts=parent_parts,
            chain_identities=tuple(_identity(fd) for fd in descriptors),
            descriptors=descriptors,
            target_basename=target_basename,
            staging_basename=staging_basename,
            cutover_id=cutover,
            policy_generation=policy,
            schema_generation=schema,
            writer_generation=writer,
            absence_observation=object(),
        )
        _assert_fresh_source_stable(authority)
        capability = object.__new__(StagingCapability)
        _bind_handle_process(capability, authority.issuing_pid)
        state = _HandleState(authority=authority)
        with _STATE_LOCK:
            _STAGING_CAPABILITY_STATES[capability] = state
        state.finalizer = weakref.finalize(
            capability,
            _cleanup_authority,
            authority,
        )
        return capability
    except BaseException:
        if authority is not None:
            _cleanup_authority(authority)
        else:
            if locked:
                try:
                    fcntl.flock(descriptors[-1], fcntl.LOCK_UN)
                except OSError:
                    pass
            _close_descriptors(descriptors)
        raise


def _lookup_staging_capability(value: object) -> _HandleState:
    if type(value) is not StagingCapability:
        raise InvalidFreshActivationCapabilityError(
            "operation requires an issued StagingCapability"
        )
    _assert_handle_process(value)
    with _STATE_LOCK:
        state = _STAGING_CAPABILITY_STATES.get(value)
    if state is None:
        raise InvalidFreshActivationCapabilityError(
            "StagingCapability was not issued by this module"
        )
    return state


def _consume_staging_capability(
    capability: StagingCapability,
) -> _ConsumedStagingAuthority:
    """Spend before returning the private authority used by future bootstrap."""

    state = _lookup_staging_capability(capability)
    with _STATE_LOCK:
        if state.phase is not _Phase.ISSUED:
            raise FreshActivationLifecycleError("StagingCapability is already spent")
        state.phase = _Phase.SPENT
        if state.finalizer is not None:
            state.finalizer.detach()
    try:
        _assert_fresh_source_stable(state.authority)
    except BaseException:
        _cleanup_authority(state.authority)
        raise
    authority = object.__new__(_ConsumedStagingAuthority)
    _bind_handle_process(authority, state.authority.issuing_pid)
    authority_state = _HandleState(authority=state.authority)
    with _STATE_LOCK:
        _STAGING_AUTHORITY_STATES[authority] = authority_state
    authority_state.finalizer = weakref.finalize(
        authority,
        _cleanup_authority,
        state.authority,
    )
    return authority


def _lookup_staging_authority(value: object) -> _HandleState:
    if type(value) is not _ConsumedStagingAuthority:
        raise InvalidFreshActivationCapabilityError(
            "operation requires the consumed staging authority"
        )
    _assert_handle_process(value)
    with _STATE_LOCK:
        state = _STAGING_AUTHORITY_STATES.get(value)
    if state is None:
        raise InvalidFreshActivationCapabilityError(
            "staging authority was not issued by this module"
        )
    return state


def _abort_staging_authority(authority: _ConsumedStagingAuthority) -> None:
    state = _lookup_staging_authority(authority)
    with _STATE_LOCK:
        if state.phase is not _Phase.ISSUED:
            raise FreshActivationLifecycleError("staging authority is already spent")
        state.phase = _Phase.SPENT
    _cleanup_authority(state.authority)
