"""Problem-neutral durable invocation terminal and opaque publication owner."""

from __future__ import annotations

import base64
import ctypes
import errno
import hashlib
import json
import os
import re
import stat
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Mapping, Sequence, TypeVar

from .model import ClosedSpawnObservation
from .systemd255 import (
    InvocationLineage,
    StopPostEnvironment,
    StopPostTopology,
    UnitHandoffProperties,
)

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_ARTIFACT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_REASON_RE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_ROW_RE = re.compile(r"([0-9]{6})\.opaque\Z")
_EVIDENCE_RE = re.compile(r"([0-9]{6})\.json\Z")
_CLAIM_NAME = "invocation_claimed.v1.json"
_AT_FDCWD = -100
_AT_EMPTY_PATH = 0x1000
_AT_SYMLINK_FOLLOW = 0x400
_RENAME_NOREPLACE = 1
_ROOT_NAMES = ("artifacts", "control", "evidence", "raw")
_LIBC = ctypes.CDLL(None, use_errno=True)
_SystemdFact = TypeVar(
    "_SystemdFact",
    InvocationLineage,
    StopPostEnvironment,
    StopPostTopology,
    UnitHandoffProperties,
)


class InvocationTerminalError(RuntimeError):
    """The durable invocation state is malformed or a transition is invalid."""


def _sha256(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise InvocationTerminalError(
            f"{field} must be 64 lowercase hexadecimal characters"
        )
    return value


def _exact_int(value: object, *, field: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise InvocationTerminalError(f"{field} must be an integer >= {minimum}")
    return value


def _require_exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, fact: str
) -> None:
    if frozenset(value) != expected:
        raise InvocationTerminalError(f"{fact} fields differ")


def _exact_bytes(value: object, *, field: str, nonempty: bool = False) -> bytes:
    if type(value) is not bytes or (nonempty and not value):
        suffix = " nonempty" if nonempty else ""
        raise TypeError(f"{field} must be exact{suffix} bytes")
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
        raise InvocationTerminalError("fact is not canonical JSON data") from exc


def _digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _domain_digest(domain: str, value: object) -> str:
    return _digest_bytes(domain.encode("ascii") + b"\x00" + _canonical_json(value))


@dataclass(frozen=True, slots=True)
class TerminalPolicy:
    authority_sha256: str
    manifest_sha256: str
    invocation_nonce: str
    expected_rows: int
    artifact_names: tuple[str, ...]
    nonce_claim_sha256: str | None = None

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("TerminalPolicy is final")

    def __post_init__(self) -> None:
        _sha256(self.authority_sha256, field="authority_sha256")
        _sha256(self.manifest_sha256, field="manifest_sha256")
        _sha256(self.invocation_nonce, field="invocation_nonce")
        _exact_int(self.expected_rows, field="expected_rows", minimum=1)
        if self.expected_rows > 1_000_000:
            raise InvocationTerminalError(
                "expected_rows exceeds the fixed ordinal space"
            )
        if type(self.artifact_names) is not tuple or not self.artifact_names:
            raise TypeError("artifact_names must be a nonempty exact tuple")
        for name in self.artifact_names:
            if type(name) is not str or _ARTIFACT_RE.fullmatch(name) is None:
                raise InvocationTerminalError(f"invalid artifact name: {name!r}")
        if len(set(self.artifact_names)) != len(self.artifact_names):
            raise InvocationTerminalError("artifact_names contains a duplicate")
        if self.nonce_claim_sha256 is not None:
            _sha256(
                self.nonce_claim_sha256,
                field="nonce_claim_sha256",
            )

    def to_mapping(self) -> dict[str, object]:
        return {
            "authority_sha256": self.authority_sha256,
            "manifest_sha256": self.manifest_sha256,
            "invocation_nonce": self.invocation_nonce,
            "expected_rows": self.expected_rows,
            "artifact_names": list(self.artifact_names),
            "nonce_claim_sha256": self.nonce_claim_sha256,
            "retry": False,
            "resume": False,
            "reuse": False,
        }

    @property
    def policy_sha256(self) -> str:
        return _domain_digest("scion.generic-terminal-policy.v1", self.to_mapping())


@dataclass(frozen=True, slots=True)
class ObservationCommit:
    job_ordinal: int
    observation_sha256: str
    evidence_sha256: str
    evidence_size_bytes: int


@dataclass(frozen=True, slots=True)
class OpaqueRowCommit:
    job_ordinal: int
    observation_sha256: str
    evidence_sha256: str
    row_sha256: str
    row_size_bytes: int

    def to_mapping(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RawCompleteFact:
    policy_sha256: str
    row_count: int
    ordered_row_identity_sha256: str
    raw_complete_sha256: str


@dataclass(frozen=True, slots=True)
class IncompleteFact:
    policy_sha256: str
    reason_code: str
    evidence_count: int
    row_count: int
    incomplete_sha256: str


_ISSUED_OBSERVATION_COMMITS: dict[int, ObservationCommit] = {}
_ISSUED_OPAQUE_ROW_COMMITS: dict[int, OpaqueRowCommit] = {}
_ISSUED_INCOMPLETE_FACTS: dict[int, IncompleteFact] = {}


def _register_cleanup_authority(value: object) -> object:
    registry: dict[int, object]
    if type(value) is ObservationCommit:
        registry = _ISSUED_OBSERVATION_COMMITS
    elif type(value) is OpaqueRowCommit:
        registry = _ISSUED_OPAQUE_ROW_COMMITS
    elif type(value) is IncompleteFact:
        registry = _ISSUED_INCOMPLETE_FACTS
    else:
        raise TypeError("unknown terminal cleanup authority")
    registry[id(value)] = value
    return value


def _consume_opaque_cleanup_authority(
    value: OpaqueRowCommit,
) -> None:
    if _ISSUED_OPAQUE_ROW_COMMITS.get(id(value)) is not value:
        raise InvocationTerminalError(
            "opaque row commit was not issued by InvocationWriter"
        )
    del _ISSUED_OPAQUE_ROW_COMMITS[id(value)]


def _consume_incomplete_cleanup_authority(
    observation: ObservationCommit,
    incomplete: IncompleteFact,
) -> None:
    if (
        _ISSUED_OBSERVATION_COMMITS.get(id(observation)) is not observation
        or _ISSUED_INCOMPLETE_FACTS.get(id(incomplete)) is not incomplete
    ):
        raise InvocationTerminalError(
            "incomplete cleanup facts were not issued by InvocationWriter"
        )
    del _ISSUED_OBSERVATION_COMMITS[id(observation)]
    del _ISSUED_INCOMPLETE_FACTS[id(incomplete)]


def _issue_opaque_row_commit_for_tests(
    value: OpaqueRowCommit,
) -> OpaqueRowCommit:
    if type(value) is not OpaqueRowCommit:
        raise TypeError("value must be exact OpaqueRowCommit")
    return _register_cleanup_authority(value)  # type: ignore[return-value]


def _issue_incomplete_cleanup_for_tests(
    observation: ObservationCommit,
    incomplete: IncompleteFact,
) -> tuple[ObservationCommit, IncompleteFact]:
    if type(observation) is not ObservationCommit:
        raise TypeError("observation must be exact ObservationCommit")
    if type(incomplete) is not IncompleteFact:
        raise TypeError("incomplete must be exact IncompleteFact")
    _register_cleanup_authority(observation)
    _register_cleanup_authority(incomplete)
    return observation, incomplete


@dataclass(frozen=True, slots=True)
class UnitDrainedFact:
    policy_sha256: str
    invocation_id: str
    unit: str
    raw_complete_sha256: str
    unit_drained_sha256: str


@dataclass(frozen=True, slots=True)
class UnitFinalFact:
    policy_sha256: str
    invocation_id: str
    unit: str
    unit_drained_sha256: str
    unit_final_sha256: str


@dataclass(frozen=True, slots=True)
class CompleteFact:
    policy_sha256: str
    opaque_problem_acceptance_digest: str
    raw_complete_sha256: str
    unit_drained_sha256: str
    unit_final_sha256: str
    complete_sha256: str


@dataclass(frozen=True, slots=True)
class ClosedFact:
    policy_sha256: str
    complete_sha256: str
    artifact_bundle_sha256: str
    closed_sha256: str


@dataclass(frozen=True, slots=True)
class TerminalInspection:
    state: str
    evidence_count: int
    row_count: int
    filesystem_mutated: bool = False


def prepare_terminal_root(root: Path) -> None:
    """Create one exact empty terminal root without replacement or cleanup."""

    absolute = Path(os.path.abspath(root))
    if absolute == Path(absolute.anchor) or absolute.name in {"", ".", ".."}:
        raise InvocationTerminalError("invalid terminal root path")
    parent_fd = _open_directory(absolute.parent)
    root_fd = -1
    opened: list[int] = []
    try:
        os.mkdir(absolute.name, 0o700, dir_fd=parent_fd)
        os.fsync(parent_fd)
        root_fd = os.open(
            absolute.name,
            os.O_RDONLY
            | os.O_DIRECTORY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        for name in _ROOT_NAMES:
            os.mkdir(name, 0o700, dir_fd=root_fd)
            descriptor = _open_child_directory(root_fd, name)
            opened.append(descriptor)
            os.fsync(descriptor)
        os.fsync(root_fd)
    except OSError as exc:
        raise InvocationTerminalError(
            "terminal root preparation failed without repair"
        ) from exc
    finally:
        for descriptor in reversed(opened):
            os.close(descriptor)
        if root_fd >= 0:
            os.close(root_fd)
        os.close(parent_fd)


def _open_directory(path: Path) -> int:
    absolute = Path(os.path.abspath(path))
    if absolute == Path(absolute.anchor):
        raise InvocationTerminalError("filesystem root cannot be an invocation root")
    flags = (
        os.O_RDONLY
        | os.O_DIRECTORY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(absolute.anchor, flags)
    except OSError as exc:
        raise InvocationTerminalError(
            f"cannot open invocation path anchor {absolute.anchor}"
        ) from exc
    try:
        for component in absolute.parts[1:]:
            try:
                next_descriptor = os.open(component, flags, dir_fd=descriptor)
            except OSError as exc:
                raise InvocationTerminalError(
                    f"symlink path component or non-directory: {component}"
                ) from exc
            os.close(descriptor)
            descriptor = next_descriptor
        result = descriptor
        descriptor = -1
        return result
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _open_child_directory(parent_fd: int, name: str) -> int:
    if name not in {
        "control",
        "evidence",
        "raw",
        "artifacts",
        "final",
    } and not name.startswith(".bundle-"):
        raise InvocationTerminalError(f"unknown terminal directory name: {name}")
    flags = (
        os.O_RDONLY
        | os.O_DIRECTORY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        return os.open(name, flags, dir_fd=parent_fd)
    except OSError as exc:
        raise InvocationTerminalError(f"cannot open terminal directory {name}") from exc


def _write_all(descriptor: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError(errno.EIO, "short write")
        view = view[written:]


def _link_tmpfile(tmp_fd: int, directory_fd: int, name: str) -> None:
    linkat = _LIBC.linkat
    linkat.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
    ]
    linkat.restype = ctypes.c_int
    result = linkat(tmp_fd, b"", directory_fd, os.fsencode(name), _AT_EMPTY_PATH)
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number not in {errno.ENOENT, errno.EPERM}:
        raise OSError(error_number, os.strerror(error_number), name)
    proc_fd_path = os.fsencode(f"/proc/self/fd/{tmp_fd}")
    result = linkat(
        _AT_FDCWD,
        proc_fd_path,
        directory_fd,
        os.fsencode(name),
        _AT_SYMLINK_FOLLOW,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), name)


def _publish_no_replace(
    directory_fd: int, name: str, data: bytes, *, mode: int = 0o600
) -> tuple[str, int]:
    if type(name) is not str or "/" in name or name in {"", ".", ".."}:
        raise InvocationTerminalError(f"invalid publication name: {name!r}")
    raw = _exact_bytes(data, field="publication data")
    if not hasattr(os, "O_TMPFILE"):
        raise OSError(errno.EOPNOTSUPP, "O_TMPFILE is unavailable")
    descriptor = os.open(
        ".",
        os.O_WRONLY | os.O_TMPFILE | getattr(os, "O_CLOEXEC", 0),
        mode,
        dir_fd=directory_fd,
    )
    try:
        _write_all(descriptor, raw)
        os.fsync(descriptor)
        _link_tmpfile(descriptor, directory_fd, name)
        source_identity = os.fstat(descriptor)
        target_descriptor = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_fd,
        )
        try:
            target_identity = os.fstat(target_descriptor)
        finally:
            os.close(target_descriptor)
        if not stat.S_ISREG(target_identity.st_mode) or (
            source_identity.st_dev,
            source_identity.st_ino,
        ) != (target_identity.st_dev, target_identity.st_ino):
            raise InvocationTerminalError(f"published target identity differs: {name}")
        os.fsync(directory_fd)
    finally:
        os.close(descriptor)
    return _digest_bytes(raw), len(raw)


def _read_regular(directory_fd: int, name: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=directory_fd)
    except OSError as exc:
        raise InvocationTerminalError(f"cannot open terminal fact {name}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise InvocationTerminalError(f"terminal fact is not regular: {name}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        try:
            named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except OSError as exc:
            raise InvocationTerminalError(
                f"terminal fact name changed while read: {name}"
            ) from exc
    finally:
        os.close(descriptor)
    if (
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        )
        or (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        )
        != (
            named.st_dev,
            named.st_ino,
            named.st_size,
            named.st_mtime_ns,
        )
        or sum(len(chunk) for chunk in chunks) != after.st_size
    ):
        raise InvocationTerminalError(f"terminal fact changed while read: {name}")
    return b"".join(chunks)


def _load_canonical_mapping(
    directory_fd: int, name: str
) -> tuple[dict[str, object], bytes]:
    raw = _read_regular(directory_fd, name)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvocationTerminalError(f"terminal fact is invalid JSON: {name}") from exc
    if type(value) is not dict or _canonical_json(value) != raw:
        raise InvocationTerminalError(f"terminal fact is noncanonical: {name}")
    return value, raw


def _encoded_fact(value: object) -> object:
    if type(value) is bytes:
        return {"$bytes_base64": base64.b64encode(value).decode("ascii")}
    if type(value) is tuple:
        return [_encoded_fact(item) for item in value]
    if type(value) is dict:
        return {key: _encoded_fact(item) for key, item in value.items()}
    if value is None or type(value) in {str, int, bool}:
        return value
    raise TypeError(f"unsupported copied fact type: {type(value).__name__}")


def _decoded_fact(value: object) -> object:
    if type(value) is list:
        return tuple(_decoded_fact(item) for item in value)
    if type(value) is dict:
        if set(value) == {"$bytes_base64"}:
            encoded = value["$bytes_base64"]
            if type(encoded) is not str:
                raise InvocationTerminalError("encoded copied bytes are not text")
            try:
                return base64.b64decode(encoded.encode("ascii"), validate=True)
            except (ValueError, UnicodeError) as exc:
                raise InvocationTerminalError(
                    "copied bytes use invalid base64"
                ) from exc
        return {key: _decoded_fact(item) for key, item in value.items()}
    return value


def _evidence_bytes(job_ordinal: int, observation: ClosedSpawnObservation) -> bytes:
    value = {
        "schema": "scion.generic-closed-observation-evidence.v1",
        "job_ordinal": job_ordinal,
        "observation_sha256": observation.observation_sha256,
        "observation": _encoded_fact(observation.to_mapping()),
    }
    return _canonical_json(value)


def _decode_evidence(raw: bytes, expected_ordinal: int) -> ClosedSpawnObservation:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvocationTerminalError("observation evidence is invalid JSON") from exc
    if type(value) is not dict or _canonical_json(value) != raw:
        raise InvocationTerminalError("observation evidence is noncanonical")
    if set(value) != {"schema", "job_ordinal", "observation_sha256", "observation"}:
        raise InvocationTerminalError("observation evidence fields differ")
    if (
        value["schema"] != "scion.generic-closed-observation-evidence.v1"
        or _exact_int(value["job_ordinal"], field="observation evidence job_ordinal")
        != expected_ordinal
    ):
        raise InvocationTerminalError("observation evidence identity differs")
    decoded = _decoded_fact(value["observation"])
    if type(decoded) is not dict:
        raise InvocationTerminalError("decoded observation is not a mapping")
    try:
        observation = ClosedSpawnObservation.from_mapping(decoded)
    except (TypeError, ValueError) as exc:
        raise InvocationTerminalError("decoded observation is invalid") from exc
    if (
        _sha256(
            value["observation_sha256"],
            field="observation evidence observation_sha256",
        )
        != observation.observation_sha256
    ):
        raise InvocationTerminalError("observation evidence digest differs")
    return observation


def _ordinal_name(ordinal: int, suffix: str) -> str:
    _exact_int(ordinal, field="job_ordinal")
    return f"{ordinal:06d}.{suffix}"


def _directory_names(directory_fd: int) -> tuple[str, ...]:
    try:
        names = os.listdir(directory_fd)
    except OSError as exc:
        raise InvocationTerminalError("cannot list terminal directory") from exc
    if any(type(name) is not str for name in names):
        raise InvocationTerminalError("terminal directory contains a non-text name")
    return tuple(sorted(names, key=lambda item: item.encode("utf-8")))


def _require_control_inventory(control_fd: int, expected: frozenset[str]) -> None:
    if frozenset(_directory_names(control_fd)) != expected:
        raise InvocationTerminalError("terminal control inventory differs")


def _control_inventory(
    policy: TerminalPolicy,
    *dynamic_names: str,
) -> frozenset[str]:
    names = {"invocation_started.v1.json", *dynamic_names}
    if policy.nonce_claim_sha256 is not None:
        names.add(_CLAIM_NAME)
    return frozenset(names)


def _execution_inventory(
    policy: TerminalPolicy,
    *dynamic_names: str,
) -> frozenset[str]:
    names = set(_control_inventory(policy, *dynamic_names))
    if policy.nonce_claim_sha256 is not None:
        names.add("invocation_lineage.v1.json")
    return frozenset(names)


def _require_nonce_claim(control_fd: int, policy: TerminalPolicy) -> bytes:
    expected = policy.nonce_claim_sha256
    if expected is None:
        raise InvocationTerminalError("terminal policy is not claim-bound")
    raw = _read_regular(control_fd, _CLAIM_NAME)
    if _digest_bytes(raw) != expected:
        raise InvocationTerminalError("invocation nonce claim digest differs")
    return raw


def _expected_prefix(names: tuple[str, ...], suffix: str) -> int | None:
    pattern = _EVIDENCE_RE if suffix == "json" else _ROW_RE
    ordinals: list[int] = []
    for name in names:
        match = pattern.fullmatch(name)
        if match is None:
            return None
        ordinal = int(match.group(1), 10)
        if name != _ordinal_name(ordinal, suffix):
            return None
        ordinals.append(ordinal)
    if ordinals != list(range(len(ordinals))):
        return None
    return len(ordinals)


class InvocationWriter:
    """One-process, one-use capability for observation and opaque-row commits."""

    __slots__ = (
        "_state",
        "_creator_pid",
        "_root_fd",
        "_control_fd",
        "_evidence_fd",
        "_raw_fd",
        "_artifacts_fd",
        "_policy",
        "_lineage",
        "_pending",
        "_rows",
    )

    _OPEN = "OPEN"
    _CLOSED = "CLOSED"

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        del _args, _kwargs
        raise TypeError(
            "InvocationWriter is created only by open_fresh or open_claimed"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("InvocationWriter is final")

    @classmethod
    def open_fresh(cls, root: Path, policy: TerminalPolicy) -> "InvocationWriter":
        if type(policy) is not TerminalPolicy:
            raise TypeError("policy must be exact TerminalPolicy")
        if policy.nonce_claim_sha256 is not None:
            raise InvocationTerminalError("claim-bound policy requires open_claimed")
        return cls._open(root, policy, claimed=False)

    @classmethod
    def open_claimed(
        cls,
        root: Path,
        policy: TerminalPolicy,
    ) -> "InvocationWriter":
        if type(policy) is not TerminalPolicy:
            raise TypeError("policy must be exact TerminalPolicy")
        if policy.nonce_claim_sha256 is None:
            raise InvocationTerminalError("open_claimed requires a claim-bound policy")
        return cls._open(root, policy, claimed=True)

    @classmethod
    def _open(
        cls,
        root: Path,
        policy: TerminalPolicy,
        *,
        claimed: bool,
    ) -> "InvocationWriter":
        root_fd = _open_directory(root)
        opened: list[int] = [root_fd]
        try:
            if _directory_names(root_fd) != _ROOT_NAMES:
                raise InvocationTerminalError("fresh invocation root inventory differs")
            control_fd = _open_child_directory(root_fd, "control")
            evidence_fd = _open_child_directory(root_fd, "evidence")
            raw_fd = _open_child_directory(root_fd, "raw")
            artifacts_fd = _open_child_directory(root_fd, "artifacts")
            opened.extend((control_fd, evidence_fd, raw_fd, artifacts_fd))
            control_names = _directory_names(control_fd)
            expected_control = (_CLAIM_NAME,) if claimed else ()
            if control_names != expected_control or any(
                _directory_names(descriptor)
                for descriptor in (evidence_fd, raw_fd, artifacts_fd)
            ):
                raise InvocationTerminalError(
                    "fresh terminal directories are not empty"
                )
            if claimed:
                _require_nonce_claim(control_fd, policy)
            identity = os.fstat(root_fd)
            started = {
                "schema": "scion.generic-invocation-started.v1",
                "policy": policy.to_mapping(),
                "policy_sha256": policy.policy_sha256,
                "root_device": identity.st_dev,
                "root_inode": identity.st_ino,
                "retry": False,
                "resume": False,
                "reuse": False,
            }
            _publish_no_replace(
                control_fd, "invocation_started.v1.json", _canonical_json(started)
            )
            value = object.__new__(cls)
            value._state = cls._OPEN
            value._creator_pid = os.getpid()
            value._root_fd = root_fd
            value._control_fd = control_fd
            value._evidence_fd = evidence_fd
            value._raw_fd = raw_fd
            value._artifacts_fd = artifacts_fd
            value._policy = policy
            value._lineage = None
            value._pending = None
            value._rows = []
            opened.clear()
            return value
        finally:
            for descriptor in reversed(opened):
                os.close(descriptor)

    def _require_open(self) -> None:
        if os.getpid() != self._creator_pid:
            raise InvocationTerminalError("InvocationWriter belongs to another process")
        if self._state != self._OPEN:
            raise InvocationTerminalError("InvocationWriter is closed")

    def record_observation(
        self, job_ordinal: int, observation: ClosedSpawnObservation
    ) -> ObservationCommit:
        self._require_open()
        if (
            self._policy.nonce_claim_sha256 is not None
            and type(self._lineage) is not InvocationLineage
        ):
            raise InvocationTerminalError(
                "claim-bound invocation lacks durable lineage"
            )
        if type(observation) is not ClosedSpawnObservation:
            raise TypeError("observation must be exact ClosedSpawnObservation")
        expected = len(self._rows)
        if job_ordinal != expected or self._pending is not None:
            raise InvocationTerminalError(
                "observation ordinal/state is not the exact next job"
            )
        if job_ordinal >= self._policy.expected_rows:
            raise InvocationTerminalError("observation exceeds the policy row count")
        data = _evidence_bytes(job_ordinal, observation)
        digest, size = _publish_no_replace(
            self._evidence_fd, _ordinal_name(job_ordinal, "json"), data
        )
        fact = _register_cleanup_authority(
            ObservationCommit(
                job_ordinal=job_ordinal,
                observation_sha256=(observation.observation_sha256),
                evidence_sha256=digest,
                evidence_size_bytes=size,
            )
        )
        assert type(fact) is ObservationCommit
        self._pending = fact
        return fact

    def bind_invocation_lineage(
        self,
        lineage: InvocationLineage,
    ) -> InvocationLineage:
        self._require_open()
        if type(lineage) is not InvocationLineage:
            raise TypeError("lineage must be exact InvocationLineage")
        if self._lineage is not None or self._pending is not None or self._rows:
            raise InvocationTerminalError(
                "invocation lineage is not the first post-start fact"
            )
        _require_control_inventory(
            self._control_fd,
            _control_inventory(self._policy),
        )
        value = {
            "schema": "scion.generic-invocation-lineage.v1",
            "policy_sha256": self._policy.policy_sha256,
            "lineage": _systemd_mapping(lineage),
        }
        _publish_no_replace(
            self._control_fd,
            "invocation_lineage.v1.json",
            _canonical_json(value),
        )
        self._lineage = lineage
        return lineage

    def commit_opaque_row(
        self,
        job_ordinal: int,
        observation_digest: str,
        row_bytes: bytes,
    ) -> OpaqueRowCommit:
        self._require_open()
        raw = _exact_bytes(row_bytes, field="row_bytes", nonempty=True)
        pending = self._pending
        if type(pending) is not ObservationCommit:
            raise InvocationTerminalError("row has no pending durable observation")
        if job_ordinal != len(self._rows) or job_ordinal != pending.job_ordinal:
            raise InvocationTerminalError("row ordinal is not the exact pending job")
        if observation_digest != pending.observation_sha256:
            raise InvocationTerminalError("row observation digest differs")
        row_digest, row_size = _publish_no_replace(
            self._raw_fd, _ordinal_name(job_ordinal, "opaque"), raw
        )
        fact = _register_cleanup_authority(
            OpaqueRowCommit(
                job_ordinal=job_ordinal,
                observation_sha256=pending.observation_sha256,
                evidence_sha256=pending.evidence_sha256,
                row_sha256=row_digest,
                row_size_bytes=row_size,
            )
        )
        assert type(fact) is OpaqueRowCommit
        self._rows.append(fact)
        self._pending = None
        return fact

    def finish_raw(self) -> RawCompleteFact:
        self._require_open()
        if self._pending is not None or len(self._rows) != self._policy.expected_rows:
            raise InvocationTerminalError(
                "RAW_COMPLETE requires the exact complete row prefix"
            )
        _require_control_inventory(self._control_fd, _execution_inventory(self._policy))
        identities = [row.to_mapping() for row in self._rows]
        aggregate = _domain_digest(
            "scion.generic-ordered-row-identities.v1", identities
        )
        value = {
            "schema": "scion.generic-raw-complete.v1",
            "policy_sha256": self._policy.policy_sha256,
            "row_count": len(self._rows),
            "row_identities": identities,
            "ordered_row_identity_sha256": aggregate,
            "retry": False,
            "resume": False,
            "reuse": False,
        }
        data = _canonical_json(value)
        digest, _size = _publish_no_replace(
            self._control_fd, "raw_complete.v1.json", data
        )
        fact = RawCompleteFact(
            policy_sha256=self._policy.policy_sha256,
            row_count=len(self._rows),
            ordered_row_identity_sha256=aggregate,
            raw_complete_sha256=digest,
        )
        self._close_descriptors()
        return fact

    def mark_incomplete(self, reason_code: str) -> IncompleteFact:
        self._require_open()
        if type(reason_code) is not str or _REASON_RE.fullmatch(reason_code) is None:
            raise InvocationTerminalError("reason_code is not canonical")
        actual_control = frozenset(_directory_names(self._control_fd))
        allowed = {_control_inventory(self._policy)}
        if self._policy.nonce_claim_sha256 is not None:
            allowed.add(_execution_inventory(self._policy))
        if actual_control not in allowed:
            raise InvocationTerminalError("terminal control inventory differs")
        evidence_count = len(self._rows) + (1 if self._pending is not None else 0)
        value = {
            "schema": "scion.generic-invocation-incomplete.v1",
            "policy_sha256": self._policy.policy_sha256,
            "reason_code": reason_code,
            "evidence_count": evidence_count,
            "row_count": len(self._rows),
            "retry": False,
            "resume": False,
            "reuse": False,
        }
        digest, _size = _publish_no_replace(
            self._control_fd, "incomplete.v1.json", _canonical_json(value)
        )
        fact = _register_cleanup_authority(
            IncompleteFact(
                policy_sha256=self._policy.policy_sha256,
                reason_code=reason_code,
                evidence_count=evidence_count,
                row_count=len(self._rows),
                incomplete_sha256=digest,
            )
        )
        assert type(fact) is IncompleteFact
        self._close_descriptors()
        return fact

    def _close_descriptors(self) -> None:
        if self._state != self._OPEN:
            return
        self._state = self._CLOSED
        for name in (
            "_artifacts_fd",
            "_raw_fd",
            "_evidence_fd",
            "_control_fd",
            "_root_fd",
        ):
            descriptor = getattr(self, name, -1)
            if descriptor >= 0:
                os.close(descriptor)
                setattr(self, name, -1)

    def __copy__(self) -> object:
        raise TypeError("InvocationWriter is not copyable")

    def __deepcopy__(self, _memo: object) -> object:
        raise TypeError("InvocationWriter is not copyable")

    def __reduce__(self) -> object:
        raise TypeError("InvocationWriter is not serializable")

    def __reduce_ex__(self, _protocol: object) -> object:
        raise TypeError("InvocationWriter is not serializable")

    def __del__(self) -> None:
        try:
            self._close_descriptors()
        except BaseException:
            pass


def _open_terminal_directories(root: Path) -> tuple[int, int, int, int, int]:
    root_fd = _open_directory(root)
    opened = [root_fd]
    try:
        if _directory_names(root_fd) != _ROOT_NAMES:
            raise InvocationTerminalError("invocation root inventory differs")
        control_fd = _open_child_directory(root_fd, "control")
        evidence_fd = _open_child_directory(root_fd, "evidence")
        raw_fd = _open_child_directory(root_fd, "raw")
        artifacts_fd = _open_child_directory(root_fd, "artifacts")
        opened.extend((control_fd, evidence_fd, raw_fd, artifacts_fd))
        result = (root_fd, control_fd, evidence_fd, raw_fd, artifacts_fd)
        opened.clear()
        return result
    finally:
        for descriptor in reversed(opened):
            os.close(descriptor)


def _close_many(descriptors: Sequence[int]) -> None:
    for descriptor in reversed(descriptors):
        os.close(descriptor)


def _require_started(
    root_fd: int, control_fd: int, policy: TerminalPolicy
) -> tuple[dict[str, object], bytes]:
    if policy.nonce_claim_sha256 is not None:
        _require_nonce_claim(control_fd, policy)
    started, raw = _load_canonical_mapping(control_fd, "invocation_started.v1.json")
    _require_exact_keys(
        started,
        frozenset(
            {
                "schema",
                "policy",
                "policy_sha256",
                "root_device",
                "root_inode",
                "retry",
                "resume",
                "reuse",
            }
        ),
        fact="invocation-started",
    )
    root_identity = os.fstat(root_fd)
    root_device = _exact_int(
        started.get("root_device"), field="invocation-started root_device"
    )
    root_inode = _exact_int(
        started.get("root_inode"), field="invocation-started root_inode"
    )
    copied_policy = started.get("policy")
    if (
        started.get("schema") != "scion.generic-invocation-started.v1"
        or type(copied_policy) is not dict
        or _canonical_json(copied_policy) != _canonical_json(policy.to_mapping())
        or started.get("policy_sha256") != policy.policy_sha256
        or root_device != root_identity.st_dev
        or root_inode != root_identity.st_ino
        or any(started.get(name) is not False for name in ("retry", "resume", "reuse"))
    ):
        raise InvocationTerminalError("invocation-started fact differs from policy")
    return started, raw


def _raw_complete(
    control_fd: int,
    evidence_fd: int,
    raw_fd: int,
    policy: TerminalPolicy,
) -> tuple[RawCompleteFact, dict[str, object], bytes]:
    value, raw_complete_bytes = _load_canonical_mapping(
        control_fd, "raw_complete.v1.json"
    )
    _require_exact_keys(
        value,
        frozenset(
            {
                "schema",
                "policy_sha256",
                "row_count",
                "row_identities",
                "ordered_row_identity_sha256",
                "retry",
                "resume",
                "reuse",
            }
        ),
        fact="RAW_COMPLETE",
    )
    row_count = _exact_int(value.get("row_count"), field="RAW_COMPLETE row_count")
    ordered_digest = _sha256(
        value.get("ordered_row_identity_sha256"),
        field="RAW_COMPLETE ordered_row_identity_sha256",
    )
    if (
        value.get("schema") != "scion.generic-raw-complete.v1"
        or value.get("policy_sha256") != policy.policy_sha256
        or row_count != policy.expected_rows
        or any(value.get(name) is not False for name in ("retry", "resume", "reuse"))
    ):
        raise InvocationTerminalError("RAW_COMPLETE fact differs from policy")
    identities = value.get("row_identities")
    if type(identities) is not list or len(identities) != policy.expected_rows:
        raise InvocationTerminalError("RAW_COMPLETE row identity count differs")
    expected_evidence = tuple(
        _ordinal_name(ordinal, "json") for ordinal in range(policy.expected_rows)
    )
    expected_rows = tuple(
        _ordinal_name(ordinal, "opaque") for ordinal in range(policy.expected_rows)
    )
    if (
        _directory_names(evidence_fd) != expected_evidence
        or _directory_names(raw_fd) != expected_rows
    ):
        raise InvocationTerminalError("RAW_COMPLETE file prefix differs")
    checked: list[dict[str, object]] = []
    for ordinal, identity in enumerate(identities):
        if type(identity) is not dict or set(identity) != {
            "job_ordinal",
            "observation_sha256",
            "evidence_sha256",
            "row_sha256",
            "row_size_bytes",
        }:
            raise InvocationTerminalError("RAW_COMPLETE row identity fields differ")
        _exact_int(
            identity.get("job_ordinal"),
            field="RAW_COMPLETE row job_ordinal",
        )
        _sha256(
            identity.get("observation_sha256"),
            field="RAW_COMPLETE row observation_sha256",
        )
        _sha256(
            identity.get("evidence_sha256"),
            field="RAW_COMPLETE row evidence_sha256",
        )
        _sha256(
            identity.get("row_sha256"),
            field="RAW_COMPLETE row row_sha256",
        )
        _exact_int(
            identity.get("row_size_bytes"),
            field="RAW_COMPLETE row_size_bytes",
            minimum=1,
        )
        evidence_bytes = _read_regular(evidence_fd, expected_evidence[ordinal])
        observation = _decode_evidence(evidence_bytes, ordinal)
        row_bytes = _read_regular(raw_fd, expected_rows[ordinal])
        expected_identity = {
            "job_ordinal": ordinal,
            "observation_sha256": observation.observation_sha256,
            "evidence_sha256": _digest_bytes(evidence_bytes),
            "row_sha256": _digest_bytes(row_bytes),
            "row_size_bytes": len(row_bytes),
        }
        if _canonical_json(identity) != _canonical_json(expected_identity):
            raise InvocationTerminalError(
                "RAW_COMPLETE row identity differs from bytes"
            )
        checked.append(expected_identity)
    aggregate = _domain_digest("scion.generic-ordered-row-identities.v1", checked)
    if ordered_digest != aggregate:
        raise InvocationTerminalError("RAW_COMPLETE aggregate differs")
    fact = RawCompleteFact(
        policy_sha256=policy.policy_sha256,
        row_count=policy.expected_rows,
        ordered_row_identity_sha256=aggregate,
        raw_complete_sha256=_digest_bytes(raw_complete_bytes),
    )
    return fact, value, raw_complete_bytes


def _verify_open_prefix(
    evidence_fd: int,
    raw_fd: int,
    *,
    evidence_count: int,
    row_count: int,
) -> None:
    if row_count > evidence_count or evidence_count - row_count not in {0, 1}:
        raise InvocationTerminalError("open evidence/row prefix is incoherent")
    for ordinal in range(evidence_count):
        evidence = _read_regular(evidence_fd, _ordinal_name(ordinal, "json"))
        _decode_evidence(evidence, ordinal)
    for ordinal in range(row_count):
        row = _read_regular(raw_fd, _ordinal_name(ordinal, "opaque"))
        if not row:
            raise InvocationTerminalError("opaque row is empty")


def _incomplete(
    control_fd: int,
    evidence_fd: int,
    raw_fd: int,
    policy: TerminalPolicy,
) -> IncompleteFact:
    value, data = _load_canonical_mapping(control_fd, "incomplete.v1.json")
    _require_exact_keys(
        value,
        frozenset(
            {
                "schema",
                "policy_sha256",
                "reason_code",
                "evidence_count",
                "row_count",
                "retry",
                "resume",
                "reuse",
            }
        ),
        fact="INCOMPLETE",
    )
    reason_code = value.get("reason_code")
    evidence_count = _exact_int(
        value.get("evidence_count"), field="INCOMPLETE evidence_count"
    )
    row_count = _exact_int(value.get("row_count"), field="INCOMPLETE row_count")
    actual_evidence_count = _expected_prefix(_directory_names(evidence_fd), "json")
    actual_row_count = _expected_prefix(_directory_names(raw_fd), "opaque")
    if (
        value.get("schema") != "scion.generic-invocation-incomplete.v1"
        or value.get("policy_sha256") != policy.policy_sha256
        or type(reason_code) is not str
        or _REASON_RE.fullmatch(reason_code) is None
        or evidence_count != actual_evidence_count
        or row_count != actual_row_count
        or evidence_count > policy.expected_rows
        or any(value.get(name) is not False for name in ("retry", "resume", "reuse"))
    ):
        raise InvocationTerminalError("INCOMPLETE fact differs")
    _verify_open_prefix(
        evidence_fd,
        raw_fd,
        evidence_count=evidence_count,
        row_count=row_count,
    )
    return IncompleteFact(
        policy_sha256=policy.policy_sha256,
        reason_code=reason_code,
        evidence_count=evidence_count,
        row_count=row_count,
        incomplete_sha256=_digest_bytes(data),
    )


def _systemd_mapping(value: object) -> dict[str, object]:
    mapping = asdict(value)
    return {
        key: list(item) if type(item) is tuple else item
        for key, item in mapping.items()
    }


def _decode_systemd_fact(
    value: object,
    fact_type: type[_SystemdFact],
    *,
    tuple_fields: frozenset[str] = frozenset(),
) -> _SystemdFact:
    if type(value) is not dict:
        raise InvocationTerminalError(f"copied {fact_type.__name__} is not a mapping")
    expected = frozenset(item.name for item in fields(fact_type))
    _require_exact_keys(value, expected, fact=f"copied {fact_type.__name__}")
    decoded = dict(value)
    for name in tuple_fields:
        item = decoded[name]
        if type(item) is not list:
            raise InvocationTerminalError(
                f"copied {fact_type.__name__}.{name} is not an array"
            )
        decoded[name] = tuple(item)
    try:
        return fact_type(**decoded)
    except (TypeError, ValueError) as exc:
        raise InvocationTerminalError(
            f"copied {fact_type.__name__} is invalid"
        ) from exc


def _bound_invocation_lineage(
    control_fd: int,
    policy: TerminalPolicy,
) -> InvocationLineage:
    value, _raw = _load_canonical_mapping(
        control_fd,
        "invocation_lineage.v1.json",
    )
    _require_exact_keys(
        value,
        frozenset({"schema", "policy_sha256", "lineage"}),
        fact="invocation-lineage",
    )
    lineage = _decode_systemd_fact(
        value.get("lineage"),
        InvocationLineage,
    )
    if (
        value.get("schema") != "scion.generic-invocation-lineage.v1"
        or value.get("policy_sha256") != policy.policy_sha256
    ):
        raise InvocationTerminalError("invocation-lineage fact differs from policy")
    return lineage


def load_invocation_lineage(
    root: Path,
    policy: TerminalPolicy,
) -> InvocationLineage:
    """Read the durable pre-job invocation lineage without mutation."""

    if type(policy) is not TerminalPolicy:
        raise TypeError("policy must be exact TerminalPolicy")
    descriptors = _open_terminal_directories(root)
    root_fd, control_fd, _evidence_fd, _raw_fd, _artifacts_fd = descriptors
    try:
        _require_started(root_fd, control_fd, policy)
        if "invocation_lineage.v1.json" not in _directory_names(control_fd):
            raise InvocationTerminalError("durable invocation lineage is absent")
        return _bound_invocation_lineage(control_fd, policy)
    finally:
        _close_many(descriptors)


def _require_drained_success(
    lineage: InvocationLineage,
    stop_post: StopPostEnvironment,
    topology: StopPostTopology,
) -> None:
    if (
        lineage.invocation_id != stop_post.invocation_id
        or topology.service_control_group != lineage.control_group
        or topology.job_cgroups
        or stop_post.service_result != "success"
        or stop_post.exit_code != "exited"
        or stop_post.exit_status != "0"
    ):
        raise InvocationTerminalError("UNIT_DRAINED success facts are incoherent")


def seal_unit_drained(
    root: Path,
    policy: TerminalPolicy,
    lineage: InvocationLineage,
    stop_post: StopPostEnvironment,
    topology: StopPostTopology,
) -> UnitDrainedFact:
    if type(policy) is not TerminalPolicy:
        raise TypeError("policy must be exact TerminalPolicy")
    if type(lineage) is not InvocationLineage:
        raise TypeError("lineage must be exact InvocationLineage")
    if type(stop_post) is not StopPostEnvironment:
        raise TypeError("stop_post must be exact StopPostEnvironment")
    if type(topology) is not StopPostTopology:
        raise TypeError("topology must be exact StopPostTopology")
    descriptors = _open_terminal_directories(root)
    root_fd, control_fd, evidence_fd, raw_fd, _artifacts_fd = descriptors
    try:
        _require_started(root_fd, control_fd, policy)
        _require_control_inventory(
            control_fd,
            _execution_inventory(policy, "raw_complete.v1.json"),
        )
        raw_fact, _raw_value, _raw_bytes = _raw_complete(
            control_fd, evidence_fd, raw_fd, policy
        )
        if (
            policy.nonce_claim_sha256 is not None
            and _bound_invocation_lineage(control_fd, policy) != lineage
        ):
            raise InvocationTerminalError(
                "UNIT_DRAINED lineage differs from durable invocation lineage"
            )
        _require_drained_success(lineage, stop_post, topology)
        value = {
            "schema": "scion.generic-unit-drained.v1",
            "policy_sha256": policy.policy_sha256,
            "raw_complete_sha256": raw_fact.raw_complete_sha256,
            "lineage": _systemd_mapping(lineage),
            "stop_post": _systemd_mapping(stop_post),
            "topology": _systemd_mapping(topology),
        }
        data = _canonical_json(value)
        digest, _size = _publish_no_replace(control_fd, "unit_drained.v1.json", data)
        return UnitDrainedFact(
            policy_sha256=policy.policy_sha256,
            invocation_id=lineage.invocation_id,
            unit=lineage.unit,
            raw_complete_sha256=raw_fact.raw_complete_sha256,
            unit_drained_sha256=digest,
        )
    finally:
        _close_many(descriptors)


def _unit_drained(
    control_fd: int, policy: TerminalPolicy, raw_fact: RawCompleteFact
) -> tuple[UnitDrainedFact, dict[str, object], bytes]:
    value, data = _load_canonical_mapping(control_fd, "unit_drained.v1.json")
    _require_exact_keys(
        value,
        frozenset(
            {
                "schema",
                "policy_sha256",
                "raw_complete_sha256",
                "lineage",
                "stop_post",
                "topology",
            }
        ),
        fact="UNIT_DRAINED",
    )
    lineage = _decode_systemd_fact(value.get("lineage"), InvocationLineage)
    stop_post = _decode_systemd_fact(value.get("stop_post"), StopPostEnvironment)
    topology = _decode_systemd_fact(
        value.get("topology"),
        StopPostTopology,
        tuple_fields=frozenset(
            {"control_pids", "supervisor_pids", "job_cgroups", "job_pids"}
        ),
    )
    if (
        value.get("schema") != "scion.generic-unit-drained.v1"
        or value.get("policy_sha256") != policy.policy_sha256
        or value.get("raw_complete_sha256") != raw_fact.raw_complete_sha256
    ):
        raise InvocationTerminalError("UNIT_DRAINED fact differs")
    _require_drained_success(lineage, stop_post, topology)
    fact = UnitDrainedFact(
        policy_sha256=policy.policy_sha256,
        invocation_id=lineage.invocation_id,
        unit=lineage.unit,
        raw_complete_sha256=raw_fact.raw_complete_sha256,
        unit_drained_sha256=_digest_bytes(data),
    )
    return fact, value, data


def observe_unit_final(
    root: Path,
    policy: TerminalPolicy,
    handoff: UnitHandoffProperties,
) -> UnitFinalFact:
    if type(policy) is not TerminalPolicy:
        raise TypeError("policy must be exact TerminalPolicy")
    if type(handoff) is not UnitHandoffProperties:
        raise TypeError("handoff must be exact UnitHandoffProperties")
    descriptors = _open_terminal_directories(root)
    root_fd, control_fd, evidence_fd, raw_fd, _artifacts_fd = descriptors
    try:
        _require_started(root_fd, control_fd, policy)
        _require_control_inventory(
            control_fd,
            _execution_inventory(
                policy,
                "raw_complete.v1.json",
                "unit_drained.v1.json",
            ),
        )
        raw_fact, _raw_value, _raw_bytes = _raw_complete(
            control_fd, evidence_fd, raw_fd, policy
        )
        drained, _drained_value, _drained_bytes = _unit_drained(
            control_fd, policy, raw_fact
        )
        if (
            handoff.unit != drained.unit
            or handoff.invocation_id != drained.invocation_id
            or handoff.result != "success"
            or handoff.active_state != "inactive"
            or handoff.sub_state != "dead"
            or handoff.exec_main_code != 1
            or handoff.exec_main_status != 0
            or handoff.exec_stop_post_code != 1
            or handoff.exec_stop_post_status != 0
        ):
            raise InvocationTerminalError("UNIT_FINAL success facts are incoherent")
        value = {
            "schema": "scion.generic-unit-final.v1",
            "policy_sha256": policy.policy_sha256,
            "unit_drained_sha256": drained.unit_drained_sha256,
            "handoff": _systemd_mapping(handoff),
        }
        data = _canonical_json(value)
        digest, _size = _publish_no_replace(control_fd, "unit_final.v1.json", data)
        return UnitFinalFact(
            policy_sha256=policy.policy_sha256,
            invocation_id=drained.invocation_id,
            unit=drained.unit,
            unit_drained_sha256=drained.unit_drained_sha256,
            unit_final_sha256=digest,
        )
    finally:
        _close_many(descriptors)


def _unit_final(
    control_fd: int, policy: TerminalPolicy, drained: UnitDrainedFact
) -> tuple[UnitFinalFact, dict[str, object], bytes]:
    value, data = _load_canonical_mapping(control_fd, "unit_final.v1.json")
    _require_exact_keys(
        value,
        frozenset(
            {
                "schema",
                "policy_sha256",
                "unit_drained_sha256",
                "handoff",
            }
        ),
        fact="UNIT_FINAL",
    )
    handoff = _decode_systemd_fact(value.get("handoff"), UnitHandoffProperties)
    if (
        value.get("schema") != "scion.generic-unit-final.v1"
        or value.get("policy_sha256") != policy.policy_sha256
        or value.get("unit_drained_sha256") != drained.unit_drained_sha256
        or handoff.unit != drained.unit
        or handoff.invocation_id != drained.invocation_id
        or handoff.result != "success"
    ):
        raise InvocationTerminalError("UNIT_FINAL fact differs")
    fact = UnitFinalFact(
        policy_sha256=policy.policy_sha256,
        invocation_id=drained.invocation_id,
        unit=drained.unit,
        unit_drained_sha256=drained.unit_drained_sha256,
        unit_final_sha256=_digest_bytes(data),
    )
    return fact, value, data


def accept_invocation(
    root: Path,
    policy: TerminalPolicy,
    opaque_problem_acceptance_digest: str,
) -> CompleteFact:
    problem_digest = _sha256(
        opaque_problem_acceptance_digest,
        field="opaque_problem_acceptance_digest",
    )
    if type(policy) is not TerminalPolicy:
        raise TypeError("policy must be exact TerminalPolicy")
    descriptors = _open_terminal_directories(root)
    root_fd, control_fd, evidence_fd, raw_fd, _artifacts_fd = descriptors
    try:
        _require_started(root_fd, control_fd, policy)
        _require_control_inventory(
            control_fd,
            _execution_inventory(
                policy,
                "raw_complete.v1.json",
                "unit_drained.v1.json",
                "unit_final.v1.json",
            ),
        )
        raw_fact, _raw_value, _raw_bytes = _raw_complete(
            control_fd, evidence_fd, raw_fd, policy
        )
        drained, _drained_value, _drained_bytes = _unit_drained(
            control_fd, policy, raw_fact
        )
        final, _final_value, _final_bytes = _unit_final(control_fd, policy, drained)
        value = {
            "schema": "scion.generic-invocation-complete.v1",
            "policy_sha256": policy.policy_sha256,
            "opaque_problem_acceptance_digest": problem_digest,
            "raw_complete_sha256": raw_fact.raw_complete_sha256,
            "unit_drained_sha256": drained.unit_drained_sha256,
            "unit_final_sha256": final.unit_final_sha256,
        }
        data = _canonical_json(value)
        digest, _size = _publish_no_replace(control_fd, "complete.v1.json", data)
        return CompleteFact(
            policy_sha256=policy.policy_sha256,
            opaque_problem_acceptance_digest=problem_digest,
            raw_complete_sha256=raw_fact.raw_complete_sha256,
            unit_drained_sha256=drained.unit_drained_sha256,
            unit_final_sha256=final.unit_final_sha256,
            complete_sha256=digest,
        )
    finally:
        _close_many(descriptors)


def _complete(
    control_fd: int,
    policy: TerminalPolicy,
    raw_fact: RawCompleteFact,
    drained: UnitDrainedFact,
    final: UnitFinalFact,
) -> tuple[CompleteFact, dict[str, object], bytes]:
    value, data = _load_canonical_mapping(control_fd, "complete.v1.json")
    _require_exact_keys(
        value,
        frozenset(
            {
                "schema",
                "policy_sha256",
                "opaque_problem_acceptance_digest",
                "raw_complete_sha256",
                "unit_drained_sha256",
                "unit_final_sha256",
            }
        ),
        fact="COMPLETE",
    )
    if (
        value.get("schema") != "scion.generic-invocation-complete.v1"
        or value.get("policy_sha256") != policy.policy_sha256
        or value.get("raw_complete_sha256") != raw_fact.raw_complete_sha256
        or value.get("unit_drained_sha256") != drained.unit_drained_sha256
        or value.get("unit_final_sha256") != final.unit_final_sha256
    ):
        raise InvocationTerminalError("COMPLETE fact differs")
    problem_digest = _sha256(
        value.get("opaque_problem_acceptance_digest"),
        field="opaque_problem_acceptance_digest",
    )
    fact = CompleteFact(
        policy_sha256=policy.policy_sha256,
        opaque_problem_acceptance_digest=problem_digest,
        raw_complete_sha256=raw_fact.raw_complete_sha256,
        unit_drained_sha256=drained.unit_drained_sha256,
        unit_final_sha256=final.unit_final_sha256,
        complete_sha256=_digest_bytes(data),
    )
    return fact, value, data


def _rename_noreplace(
    old_directory_fd: int,
    old_name: str,
    new_directory_fd: int,
    new_name: str,
) -> None:
    renameat2 = getattr(_LIBC, "renameat2", None)
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
        old_directory_fd,
        os.fsencode(old_name),
        new_directory_fd,
        os.fsencode(new_name),
        _RENAME_NOREPLACE,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), new_name)


def publish_opaque_artifact_bundle(
    root: Path,
    policy: TerminalPolicy,
    complete: CompleteFact,
    named_bytes: Sequence[tuple[str, bytes]],
) -> ClosedFact:
    if type(policy) is not TerminalPolicy:
        raise TypeError("policy must be exact TerminalPolicy")
    if type(complete) is not CompleteFact:
        raise TypeError("complete must be exact CompleteFact")
    if type(named_bytes) is not tuple:
        raise TypeError("named_bytes must be an exact tuple")
    names = tuple(
        item[0] for item in named_bytes if type(item) is tuple and len(item) == 2
    )
    if len(names) != len(named_bytes) or names != policy.artifact_names:
        raise InvocationTerminalError("artifact bundle names/order differ from policy")
    for name, data in named_bytes:
        if type(name) is not str:
            raise TypeError("artifact name must be exact str")
        _exact_bytes(data, field=f"artifact {name}", nonempty=True)
    descriptors = _open_terminal_directories(root)
    root_fd, control_fd, evidence_fd, raw_fd, artifacts_fd = descriptors
    try:
        _require_started(root_fd, control_fd, policy)
        _require_control_inventory(
            control_fd,
            _execution_inventory(
                policy,
                "raw_complete.v1.json",
                "unit_drained.v1.json",
                "unit_final.v1.json",
                "complete.v1.json",
            ),
        )
        raw_fact, _raw_value, _raw_bytes = _raw_complete(
            control_fd, evidence_fd, raw_fd, policy
        )
        drained, _drained_value, _drained_bytes = _unit_drained(
            control_fd, policy, raw_fact
        )
        final, _final_value, _final_bytes = _unit_final(control_fd, policy, drained)
        actual_complete, _complete_value, _complete_bytes = _complete(
            control_fd, policy, raw_fact, drained, final
        )
        if complete != actual_complete:
            raise InvocationTerminalError("CompleteFact differs from durable COMPLETE")
        if _directory_names(artifacts_fd):
            raise InvocationTerminalError("artifact directory is not empty")
        staging_name = f".bundle-{policy.invocation_nonce[:16]}"
        os.mkdir(staging_name, 0o700, dir_fd=artifacts_fd)
        staging_fd = _open_child_directory(artifacts_fd, staging_name)
        try:
            identities: list[dict[str, object]] = []
            for name, data in named_bytes:
                digest, size = _publish_no_replace(staging_fd, name, data)
                identities.append({"name": name, "sha256": digest, "size_bytes": size})
            os.fsync(staging_fd)
        finally:
            os.close(staging_fd)
        _rename_noreplace(artifacts_fd, staging_name, artifacts_fd, "final")
        os.fsync(artifacts_fd)
        bundle_digest = _domain_digest(
            "scion.generic-opaque-artifact-bundle.v1", identities
        )
        closed_value = {
            "schema": "scion.generic-invocation-closed.v1",
            "policy_sha256": policy.policy_sha256,
            "complete_sha256": complete.complete_sha256,
            "raw_complete_sha256": complete.raw_complete_sha256,
            "unit_drained_sha256": complete.unit_drained_sha256,
            "unit_final_sha256": complete.unit_final_sha256,
            "artifact_identities": identities,
            "artifact_bundle_sha256": bundle_digest,
        }
        closed_data = _canonical_json(closed_value)
        closed_digest, _size = _publish_no_replace(
            control_fd, "closed.v1.json", closed_data
        )
        expected_closed = ClosedFact(
            policy_sha256=policy.policy_sha256,
            complete_sha256=complete.complete_sha256,
            artifact_bundle_sha256=bundle_digest,
            closed_sha256=closed_digest,
        )
        verified_closed = _verify_closed(control_fd, artifacts_fd, policy, complete)
        if verified_closed != expected_closed:
            raise InvocationTerminalError(
                "published CLOSED fact differs after verification"
            )
        return verified_closed
    finally:
        _close_many(descriptors)


def _verify_closed(
    control_fd: int,
    artifacts_fd: int,
    policy: TerminalPolicy,
    complete: CompleteFact,
) -> ClosedFact:
    value, closed_bytes = _load_canonical_mapping(control_fd, "closed.v1.json")
    _require_exact_keys(
        value,
        frozenset(
            {
                "schema",
                "policy_sha256",
                "complete_sha256",
                "raw_complete_sha256",
                "unit_drained_sha256",
                "unit_final_sha256",
                "artifact_identities",
                "artifact_bundle_sha256",
            }
        ),
        fact="CLOSED",
    )
    stored_identities = value.get("artifact_identities")
    if type(stored_identities) is not list or len(stored_identities) != len(
        policy.artifact_names
    ):
        raise InvocationTerminalError("closed artifact identity count differs")
    for expected_name, identity in zip(
        policy.artifact_names, stored_identities, strict=True
    ):
        if type(identity) is not dict:
            raise InvocationTerminalError("closed artifact identity is not a mapping")
        _require_exact_keys(
            identity,
            frozenset({"name", "sha256", "size_bytes"}),
            fact="closed artifact identity",
        )
        if identity.get("name") != expected_name:
            raise InvocationTerminalError("closed artifact identity name differs")
        _sha256(
            identity.get("sha256"),
            field="closed artifact identity sha256",
        )
        _exact_int(
            identity.get("size_bytes"),
            field="closed artifact identity size_bytes",
            minimum=1,
        )
    stored_bundle_digest = _sha256(
        value.get("artifact_bundle_sha256"),
        field="closed artifact_bundle_sha256",
    )
    if (
        value.get("schema") != "scion.generic-invocation-closed.v1"
        or value.get("policy_sha256") != policy.policy_sha256
        or value.get("complete_sha256") != complete.complete_sha256
        or value.get("raw_complete_sha256") != complete.raw_complete_sha256
        or value.get("unit_drained_sha256") != complete.unit_drained_sha256
        or value.get("unit_final_sha256") != complete.unit_final_sha256
    ):
        raise InvocationTerminalError("CLOSED fact differs")
    if _directory_names(artifacts_fd) != ("final",):
        raise InvocationTerminalError("closed artifact directory inventory differs")
    final_fd = _open_child_directory(artifacts_fd, "final")
    try:
        if _directory_names(final_fd) != tuple(
            sorted(policy.artifact_names, key=lambda item: item.encode("utf-8"))
        ):
            raise InvocationTerminalError("closed artifact names differ")
        identities = []
        for name in policy.artifact_names:
            data = _read_regular(final_fd, name)
            if not data:
                raise InvocationTerminalError("closed artifact is empty")
            identities.append(
                {"name": name, "sha256": _digest_bytes(data), "size_bytes": len(data)}
            )
    finally:
        os.close(final_fd)
    if _canonical_json(stored_identities) != _canonical_json(identities):
        raise InvocationTerminalError("closed artifact identities differ")
    bundle_digest = _domain_digest(
        "scion.generic-opaque-artifact-bundle.v1", identities
    )
    if stored_bundle_digest != bundle_digest:
        raise InvocationTerminalError("closed artifact aggregate differs")
    return ClosedFact(
        policy_sha256=policy.policy_sha256,
        complete_sha256=complete.complete_sha256,
        artifact_bundle_sha256=bundle_digest,
        closed_sha256=_digest_bytes(closed_bytes),
    )


def inspect_terminal(root: Path, policy: TerminalPolicy) -> TerminalInspection:
    """Classify and verify the durable prefix without writing any byte."""

    if type(policy) is not TerminalPolicy:
        raise TypeError("policy must be exact TerminalPolicy")
    descriptors = _open_terminal_directories(root)
    root_fd, control_fd, evidence_fd, raw_fd, artifacts_fd = descriptors
    try:
        control_names = _directory_names(control_fd)
        evidence_names = _directory_names(evidence_fd)
        row_names = _directory_names(raw_fd)
        artifact_names = _directory_names(artifacts_fd)
        evidence_count = _expected_prefix(evidence_names, "json")
        row_count = _expected_prefix(row_names, "opaque")
        if evidence_count is None or row_count is None:
            return TerminalInspection("UNKNOWN_INTEGRITY_HOLD", 0, 0)
        if not control_names:
            state = (
                (
                    "PREPARED_UNCLAIMED"
                    if policy.nonce_claim_sha256 is not None
                    else "PREPARED"
                )
                if not evidence_names and not row_names and not artifact_names
                else "UNKNOWN_INTEGRITY_HOLD"
            )
            return TerminalInspection(state, evidence_count, row_count)
        control_set = frozenset(control_names)
        started = _control_inventory(policy)
        if "invocation_started.v1.json" not in control_set:
            if (
                policy.nonce_claim_sha256 is not None
                and control_set == frozenset({_CLAIM_NAME})
                and not evidence_names
                and not row_names
                and not artifact_names
            ):
                try:
                    _require_nonce_claim(control_fd, policy)
                except (InvocationTerminalError, OSError):
                    return TerminalInspection(
                        "UNKNOWN_INTEGRITY_HOLD",
                        evidence_count,
                        row_count,
                    )
                return TerminalInspection(
                    "CLAIMED_PRESTART",
                    evidence_count,
                    row_count,
                )
            return TerminalInspection(
                "UNKNOWN_INTEGRITY_HOLD",
                evidence_count,
                row_count,
            )
        try:
            _require_started(root_fd, control_fd, policy)
            if "incomplete.v1.json" in control_set:
                allowed_incomplete = {started | {"incomplete.v1.json"}}
                if policy.nonce_claim_sha256 is not None:
                    allowed_incomplete.add(
                        _execution_inventory(policy) | {"incomplete.v1.json"}
                    )
                if control_set not in allowed_incomplete or artifact_names:
                    raise InvocationTerminalError(
                        "INCOMPLETE control inventory differs"
                    )
                _incomplete(control_fd, evidence_fd, raw_fd, policy)
                return TerminalInspection("INCOMPLETE", evidence_count, row_count)
            if (
                policy.nonce_claim_sha256 is not None
                and "invocation_lineage.v1.json" not in control_set
            ):
                if (
                    control_set != started
                    or evidence_names
                    or row_names
                    or artifact_names
                ):
                    raise InvocationTerminalError(
                        "pre-lineage control inventory differs"
                    )
                return TerminalInspection(
                    "STARTED_AWAITING_LINEAGE",
                    evidence_count,
                    row_count,
                )
            if policy.nonce_claim_sha256 is not None:
                _bound_invocation_lineage(control_fd, policy)
                started = _execution_inventory(policy)
            if "raw_complete.v1.json" not in control_set:
                if (
                    control_set != started
                    or artifact_names
                    or evidence_count > policy.expected_rows
                ):
                    raise InvocationTerminalError("active control inventory differs")
                _verify_open_prefix(
                    evidence_fd,
                    raw_fd,
                    evidence_count=evidence_count,
                    row_count=row_count,
                )
                state = (
                    f"ACTIVE_IDLE({row_count})"
                    if evidence_count == row_count
                    else f"EVIDENCE_ONLY({row_count})"
                )
                return TerminalInspection(state, evidence_count, row_count)
            raw_fact, _raw_value, _raw_bytes = _raw_complete(
                control_fd, evidence_fd, raw_fd, policy
            )
            if "unit_drained.v1.json" not in control_names:
                if control_set != started | {"raw_complete.v1.json"} or artifact_names:
                    raise InvocationTerminalError(
                        "RAW_COMPLETE control inventory differs"
                    )
                return TerminalInspection("RAW_COMPLETE", evidence_count, row_count)
            drained, _drained_value, _drained_bytes = _unit_drained(
                control_fd, policy, raw_fact
            )
            if "unit_final.v1.json" not in control_names:
                if (
                    control_set
                    != started | {"raw_complete.v1.json", "unit_drained.v1.json"}
                    or artifact_names
                ):
                    raise InvocationTerminalError(
                        "UNIT_DRAINED control inventory differs"
                    )
                return TerminalInspection("UNIT_DRAINED", evidence_count, row_count)
            final, _final_value, _final_bytes = _unit_final(control_fd, policy, drained)
            if "complete.v1.json" not in control_names:
                if (
                    control_set
                    != started
                    | {
                        "raw_complete.v1.json",
                        "unit_drained.v1.json",
                        "unit_final.v1.json",
                    }
                    or artifact_names
                ):
                    raise InvocationTerminalError(
                        "UNIT_FINAL control inventory differs"
                    )
                return TerminalInspection("UNIT_FINAL", evidence_count, row_count)
            complete, _complete_value, _complete_bytes = _complete(
                control_fd, policy, raw_fact, drained, final
            )
            if "closed.v1.json" not in control_names:
                if (
                    control_set
                    != started
                    | {
                        "raw_complete.v1.json",
                        "unit_drained.v1.json",
                        "unit_final.v1.json",
                        "complete.v1.json",
                    }
                    or artifact_names
                ):
                    raise InvocationTerminalError("COMPLETE control inventory differs")
                return TerminalInspection(
                    "COMPLETE_UNCLOSED", evidence_count, row_count
                )
            if control_set != started | {
                "raw_complete.v1.json",
                "unit_drained.v1.json",
                "unit_final.v1.json",
                "complete.v1.json",
                "closed.v1.json",
            }:
                raise InvocationTerminalError("CLOSED control inventory differs")
            _verify_closed(control_fd, artifacts_fd, policy, complete)
            return TerminalInspection("CLOSED", evidence_count, row_count)
        except (InvocationTerminalError, OSError):
            return TerminalInspection(
                "UNKNOWN_INTEGRITY_HOLD", evidence_count, row_count
            )
    finally:
        _close_many(descriptors)


__all__ = [
    "ClosedFact",
    "CompleteFact",
    "IncompleteFact",
    "InvocationTerminalError",
    "InvocationWriter",
    "ObservationCommit",
    "OpaqueRowCommit",
    "RawCompleteFact",
    "TerminalInspection",
    "TerminalPolicy",
    "UnitDrainedFact",
    "UnitFinalFact",
    "accept_invocation",
    "inspect_terminal",
    "load_invocation_lineage",
    "observe_unit_final",
    "prepare_terminal_root",
    "publish_opaque_artifact_bundle",
    "seal_unit_drained",
]
