"""Offline double-wheel evidence for Warehouse W3 candidate preparation.

The owner consumes two immutable Git-archive files for one launch commit,
extracts each into an independent disposable source tree, invokes one fixed
offline builder command through a narrow runner, and accepts only byte-identical
wheels with identical complete member inventories.  It has no network, root,
installation, manager, or launch capability.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Mapping, Protocol

from scion.problems.warehouse_delivery.w3_installation import GitSourceReceipt

ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256 = (
    "49196769c0c70f56714791a80e6c683d31d547c5f4e47cc7216ea1b5fda81eb6"
)
ACCEPTED_NATIVE_ELF_SHA256 = (
    "3d747973bc2eb3b0f6fda68f288987c7b988820eb24df2ff617aa567071803fc"
)
BUILDER_PYTHON = "/home/clawd/miniconda3/envs/claw/bin/python3.12"
BWRAP = "/usr/bin/bwrap"
BUILDER_ARGV_TEMPLATE = (
    BUILDER_PYTHON,
    "-I",
    "-m",
    "pip",
    "wheel",
    "--no-deps",
    "--no-build-isolation",
    "--wheel-dir",
    "<wheel-dir>",
    ".",
)

W3_TOOL_MEMBER = "scion/tools/scion_w3_tool.py"
W3_RUN_TEMPLATE_MEMBER = "scion/problems/warehouse_delivery/systemd/scion-w3@.service"
W3_CLOSE_TEMPLATE_MEMBER = (
    "scion/problems/warehouse_delivery/systemd/scion-w3-close@.service"
)

# This is the reviewed minimum import surface.  The builder additionally
# requires every non-test scion/*.py member present in the Git archive.
FIXED_REQUIRED_WHEEL_MEMBERS = (
    "scion/__init__.py",
    "scion/core/__init__.py",
    "scion/core/models.py",
    "scion/core/path_match.py",
    "scion/core/paths.py",
    "scion/core/research_surface_index.py",
    "scion/problems/__init__.py",
    "scion/problems/warehouse_delivery/__init__.py",
    "scion/problems/warehouse_delivery/w2_preservation.py",
    "scion/problems/warehouse_delivery/w3_analysis.py",
    "scion/problems/warehouse_delivery/w3_candidate_coordinator.py",
    "scion/problems/warehouse_delivery/w3_candidate_gate.py",
    "scion/problems/warehouse_delivery/w3_candidate_ingress.py",
    "scion/problems/warehouse_delivery/w3_composition.py",
    "scion/problems/warehouse_delivery/w3_counter_fixtures.py",
    "scion/problems/warehouse_delivery/w3_environment.py",
    "scion/problems/warehouse_delivery/w3_environment_receipts.py",
    "scion/problems/warehouse_delivery/w3_fixed_arm.py",
    "scion/problems/warehouse_delivery/w3_installation.py",
    "scion/problems/warehouse_delivery/w3_installed_replay.py",
    "scion/problems/warehouse_delivery/w3_prestart_facts.py",
    "scion/problems/warehouse_delivery/w3_root_coordinator.py",
    "scion/problems/warehouse_delivery/w3_root_installation.py",
    "scion/problems/warehouse_delivery/w3_root_selection.py",
    "scion/problems/warehouse_delivery/w3_root_staging.py",
    "scion/problems/warehouse_delivery/w3_start_authorization.py",
    "scion/problems/warehouse_delivery/w3_start_gate.py",
    "scion/problems/warehouse_delivery/w3_start_store.py",
    "scion/problems/warehouse_delivery/w3_terminal_acceptance.py",
    "scion/problems/warehouse_delivery/w3_terminal_manager.py",
    "scion/problems/warehouse_delivery/w3_validation.py",
    "scion/problems/warehouse_delivery/w3_wheel.py",
    W3_CLOSE_TEMPLATE_MEMBER,
    W3_RUN_TEMPLATE_MEMBER,
    "scion/runtime/__init__.py",
    "scion/runtime/execution/__init__.py",
    "scion/runtime/execution/cgroup_v2.py",
    "scion/runtime/execution/environment_integrity.py",
    "scion/runtime/execution/external_installation.py",
    "scion/runtime/execution/external_linux.py",
    "scion/runtime/execution/invocation_terminal.py",
    "scion/runtime/execution/launch_authority.py",
    "scion/runtime/execution/model.py",
    "scion/runtime/execution/spawn_backend.py",
    "scion/runtime/execution/systemd255.py",
    "scion/runtime/execution/systemd_acquisition.py",
    "scion/runtime/native/__init__.py",
    "scion/runtime/runner.py",
    "scion/runtime/subprocess_runner.py",
    "scion/runtime/workspace.py",
    "scion/tools/__init__.py",
    "scion/tools/scion_w3_install.py",
    W3_TOOL_MEMBER,
)

_SCHEMA = "scion.w3-offline-double-wheel.v2"
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_GIT_OID_RE = re.compile(r"[0-9a-f]{40}\Z")
_WHEEL_NAME_RE = re.compile(
    r"scion-[A-Za-z0-9][A-Za-z0-9_.!+-]*-cp312-cp312-linux_x86_64\.whl\Z"
)
_NATIVE_MEMBER_RE = re.compile(
    r"scion/runtime/native/_spawn_into_cgroup" r"\.cpython-312-[A-Za-z0-9_.-]+\.so\Z"
)
_DIST_WHEEL_RE = re.compile(r"scion-[A-Za-z0-9][A-Za-z0-9_.!+-]*\.dist-info/WHEEL\Z")
_ARCHIVE_MEMBER_LIMIT = 16_384
_ARCHIVE_TOTAL_LIMIT = 1024 * 1024 * 1024
_WHEEL_MEMBER_LIMIT = 16_384
_WHEEL_TOTAL_LIMIT = 1024 * 1024 * 1024
_WHEEL_METADATA_LIMIT = 64 * 1024
_COPY_SIZE = 1024 * 1024
_UINT32_MAX = (1 << 32) - 1
_UINT64_MAX = (1 << 64) - 1
_EPOCH_MAX = (1 << 63) - 1

_ENVIRONMENT_TEMPLATE = (
    ("AR", "/usr/bin/ar"),
    ("CC", "/usr/bin/gcc-13 -pthread"),
    ("CFLAGS", "-O2 -fPIC"),
    ("CPPFLAGS", ""),
    ("HOME", "<home>"),
    ("LANG", "C.UTF-8"),
    ("LC_ALL", "C.UTF-8"),
    ("LD", "/usr/bin/ld"),
    ("LDFLAGS", ""),
    ("LDSHARED", "/usr/bin/gcc-13 -pthread -shared"),
    ("PATH", "/usr/bin:/bin"),
    ("PIP_CONFIG_FILE", "/dev/null"),
    ("PIP_DISABLE_PIP_VERSION_CHECK", "1"),
    ("PIP_NO_INDEX", "1"),
    ("PYTHONDONTWRITEBYTECODE", "1"),
    ("PYTHONNOUSERSITE", "1"),
    ("RANLIB", "/usr/bin/ranlib"),
    ("SOURCE_DATE_EPOCH", "<source-date-epoch>"),
    ("TMPDIR", "<tmpdir>"),
    ("TZ", "UTC"),
)
_ENVIRONMENT_KEYS = frozenset(name for name, _value in _ENVIRONMENT_TEMPLATE)


class WarehouseW3WheelError(RuntimeError):
    """The offline W3 wheel evidence is invalid or incomplete."""


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
        raise WarehouseW3WheelError("wheel receipt value is not canonical") from exc


def _decode_canonical(raw: bytes) -> dict[str, object]:
    if type(raw) is not bytes:
        raise TypeError("wheel receipt must be exact bytes")

    def mapping(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate wheel receipt field")
            value[key] = item
        return value

    try:
        value = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=mapping,
            parse_float=lambda _value: (_ for _ in ()).throw(
                ValueError("wheel receipt contains a float")
            ),
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"wheel receipt contains {token}")
            ),
        )
    except (UnicodeError, ValueError, TypeError) as exc:
        raise WarehouseW3WheelError("wheel receipt is not canonical JSON") from exc
    if type(value) is not dict or _canonical_json(value) != raw:
        raise WarehouseW3WheelError("wheel receipt bytes are not canonical")
    return value


def _exact_keys(value: Mapping[str, object], expected: frozenset[str]) -> None:
    if frozenset(value) != expected:
        raise WarehouseW3WheelError("wheel receipt fields differ")


def _sha256(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise WarehouseW3WheelError(f"{field} is not one SHA-256")
    return value


def _git_oid(value: object, *, field: str) -> str:
    if type(value) is not str or _GIT_OID_RE.fullmatch(value) is None:
        raise WarehouseW3WheelError(f"{field} is not one Git object id")
    return value


def _uint(
    value: object,
    *,
    field: str,
    positive: bool = False,
    maximum: int = _UINT64_MAX,
) -> int:
    if type(value) is not int or value < (1 if positive else 0) or value > maximum:
        raise WarehouseW3WheelError(f"{field} is not an exact unsigned integer")
    return value


def _absolute_path(path: Path, *, field: str) -> str:
    if not isinstance(path, Path):
        raise TypeError(f"{field} must be Path")
    text = str(path)
    pure = PurePosixPath(text)
    if (
        not pure.is_absolute()
        or text == "/"
        or text.startswith("//")
        or str(pure) != text
        or any(part in {"", ".", ".."} for part in pure.parts[1:])
    ):
        raise WarehouseW3WheelError(f"{field} is not a canonical absolute path")
    return text


def _relative_path(value: object, *, field: str) -> str:
    if type(value) is not str or not value or "\\" in value or "\x00" in value:
        raise WarehouseW3WheelError(f"{field} is not a relative path")
    pure = PurePosixPath(value)
    if (
        pure.is_absolute()
        or str(pure) != value
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise WarehouseW3WheelError(f"{field} is not canonical")
    return value


def _stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_gid,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _hash_regular(path: Path, *, immutable: bool) -> tuple[str, os.stat_result]:
    try:
        named_before = os.lstat(path)
    except OSError as exc:
        raise WarehouseW3WheelError(f"cannot inspect regular file: {path}") from exc
    if (
        stat.S_ISLNK(named_before.st_mode)
        or not stat.S_ISREG(named_before.st_mode)
        or named_before.st_nlink != 1
        or (immutable and stat.S_IMODE(named_before.st_mode) not in {0o444, 0o555})
    ):
        raise WarehouseW3WheelError(f"regular file identity differs: {path}")
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise WarehouseW3WheelError(f"cannot open regular file: {path}") from exc
    digest = hashlib.sha256()
    try:
        opened_before = os.fstat(descriptor)
        if _stat_identity(opened_before) != _stat_identity(named_before):
            raise WarehouseW3WheelError(f"regular file changed before read: {path}")
        while True:
            chunk = os.read(descriptor, _COPY_SIZE)
            if not chunk:
                break
            digest.update(chunk)
        opened_after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        named_after = os.lstat(path)
    except OSError as exc:
        raise WarehouseW3WheelError(f"cannot reopen regular file: {path}") from exc
    if _stat_identity(named_before) != _stat_identity(opened_after) or _stat_identity(
        opened_after
    ) != _stat_identity(named_after):
        raise WarehouseW3WheelError(f"regular file changed during read: {path}")
    return digest.hexdigest(), named_after


@dataclass(frozen=True, slots=True)
class ImmutableGitArchive:
    """One immutable archive bound to an exact producer Git receipt."""

    path: Path
    sha256: str
    source_receipt: GitSourceReceipt

    def __post_init__(self) -> None:
        _absolute_path(self.path, field="archive.path")
        _sha256(self.sha256, field="archive.sha256")
        if (
            type(self.source_receipt) is not GitSourceReceipt
            or GitSourceReceipt.from_bytes(self.source_receipt.raw)
            != self.source_receipt
        ):
            raise WarehouseW3WheelError(
                "archive source receipt is not exact canonical evidence"
            )
        if self.path.suffix != ".tar":
            raise WarehouseW3WheelError("Git archive is not one .tar file")

    @property
    def source_commit(self) -> str:
        return self.source_receipt.source_commit

    @property
    def source_tree(self) -> str:
        return self.source_receipt.source_tree


class LocalGitReader(Protocol):
    """Read-only seam for the fixed local Git object queries below."""

    def read(self, argv: tuple[str, ...], *, repo_root: Path) -> bytes:
        """Return exact stdout bytes or raise."""


class SubprocessLocalGitReader:
    """Final no-shell local Git reader; it never invokes a remote."""

    __slots__ = ()

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("SubprocessLocalGitReader is final")

    def read(self, argv: tuple[str, ...], *, repo_root: Path) -> bytes:
        if (
            type(argv) is not tuple
            or not argv
            or argv[0] != "git"
            or any(type(item) is not str or not item for item in argv)
        ):
            raise TypeError("local Git command differs")
        try:
            completed = subprocess.run(
                argv,
                cwd=repo_root,
                env={
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_NO_REPLACE_OBJECTS": "1",
                    "HOME": "/nonexistent",
                    "LANG": "C",
                    "LC_ALL": "C",
                    "PATH": "/usr/bin:/bin",
                },
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                shell=False,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise WarehouseW3WheelError("local Git command could not run") from exc
        if completed.returncode != 0 or type(completed.stdout) is not bytes:
            raise WarehouseW3WheelError("local Git command failed")
        return completed.stdout


@dataclass(frozen=True, slots=True)
class _LocalGitAuthority:
    source_receipt_sha256: str
    source_commit: str
    source_tree: str
    source_date_epoch: int
    blob_bytes: Mapping[str, bytes]


def _one_git_line(raw: bytes, *, field: str) -> str:
    if (
        type(raw) is not bytes
        or len(raw) > 4096
        or raw.count(b"\n") != 1
        or not raw.endswith(b"\n")
    ):
        raise WarehouseW3WheelError(f"{field} is not one exact Git line")
    try:
        text = raw[:-1].decode("ascii", "strict")
    except UnicodeError as exc:
        raise WarehouseW3WheelError(f"{field} is not ASCII") from exc
    if not text or any(ord(item) < 0x20 or ord(item) == 0x7F for item in text):
        raise WarehouseW3WheelError(f"{field} contains invalid text")
    return text


def _git_blob_oid(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()


def _canonical_repo_descriptor(repo_root: Path) -> tuple[int, os.stat_result]:
    root_text = _absolute_path(repo_root, field="repo_root")
    try:
        named = os.lstat(repo_root)
        if (
            stat.S_ISLNK(named.st_mode)
            or not stat.S_ISDIR(named.st_mode)
            or str(repo_root.resolve(strict=True)) != root_text
        ):
            raise WarehouseW3WheelError(
                "repo_root is not one canonical no-follow directory"
            )
        flags = os.O_RDONLY | os.O_CLOEXEC
        if hasattr(os, "O_DIRECTORY"):
            flags |= os.O_DIRECTORY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(repo_root, flags)
        opened = os.fstat(descriptor)
    except WarehouseW3WheelError:
        raise
    except OSError as exc:
        raise WarehouseW3WheelError("repo_root cannot be opened") from exc
    if _stat_identity(opened) != _stat_identity(named):
        os.close(descriptor)
        raise WarehouseW3WheelError("repo_root changed before Git acquisition")
    return descriptor, opened


def _acquire_local_git_authority(
    repo_root: Path,
    source_receipt: GitSourceReceipt,
    *,
    reader: LocalGitReader | None,
) -> _LocalGitAuthority:
    if type(source_receipt) is not GitSourceReceipt:
        raise TypeError("source_receipt must be exact GitSourceReceipt")
    selected: LocalGitReader = SubprocessLocalGitReader() if reader is None else reader
    method = getattr(selected, "read", None)
    if not callable(method):
        raise TypeError("git_reader must expose read")
    descriptor, identity = _canonical_repo_descriptor(repo_root)

    def read(argv: tuple[str, ...], *, maximum: int) -> bytes:
        try:
            raw = method(argv, repo_root=repo_root)
        except WarehouseW3WheelError:
            raise
        except Exception as exc:
            raise WarehouseW3WheelError("local Git reader failed") from exc
        if type(raw) is not bytes or len(raw) > maximum:
            raise WarehouseW3WheelError("local Git output exceeds its exact bound")
        return raw

    commit = source_receipt.source_commit
    try:
        resolved_commit = _git_oid(
            _one_git_line(
                read(
                    ("git", "rev-parse", "--verify", f"{commit}^{{commit}}"),
                    maximum=4096,
                ),
                field="local Git commit",
            ),
            field="local Git commit",
        )
        resolved_tree = _git_oid(
            _one_git_line(
                read(
                    ("git", "rev-parse", "--verify", f"{commit}^{{tree}}"),
                    maximum=4096,
                ),
                field="local Git tree",
            ),
            field="local Git tree",
        )
        raw_epoch = _one_git_line(
            read(
                ("git", "show", "-s", "--format=%ct", commit),
                maximum=4096,
            ),
            field="local Git commit timestamp",
        )
        if (
            resolved_commit != commit
            or resolved_tree != source_receipt.source_tree
            or not raw_epoch.isascii()
            or not raw_epoch.isdecimal()
        ):
            raise WarehouseW3WheelError("local Git commit, tree, or timestamp differs")
        epoch = _uint(
            int(raw_epoch),
            field="source_date_epoch",
            positive=True,
            maximum=_EPOCH_MAX,
        )
        blobs: dict[str, bytes] = {}
        for item in source_receipt.blobs:
            entry_raw = read(
                (
                    "git",
                    "ls-tree",
                    "-z",
                    "--full-tree",
                    commit,
                    "--",
                    item.logical_path,
                ),
                maximum=16_384,
            )
            if not entry_raw.endswith(b"\0") or entry_raw.count(b"\0") != 1:
                raise WarehouseW3WheelError(
                    f"local Git tree path differs: {item.logical_path}"
                )
            try:
                header, encoded_path = entry_raw[:-1].split(b"\t", 1)
                mode_raw, kind_raw, oid_raw = header.split(b" ", 2)
                actual_path = encoded_path.decode("utf-8", "strict")
                mode = mode_raw.decode("ascii", "strict")
                kind = kind_raw.decode("ascii", "strict")
                oid = oid_raw.decode("ascii", "strict")
            except (ValueError, UnicodeError) as exc:
                raise WarehouseW3WheelError(
                    f"local Git tree entry is malformed: {item.logical_path}"
                ) from exc
            if (
                actual_path != item.logical_path
                or mode != item.mode
                or kind != "blob"
                or oid != item.blob_oid
            ):
                raise WarehouseW3WheelError(
                    f"local Git tree entry differs: {item.logical_path}"
                )
            raw = read(
                ("git", "cat-file", "blob", item.blob_oid),
                maximum=item.size_bytes,
            )
            if (
                len(raw) != item.size_bytes
                or hashlib.sha256(raw).hexdigest() != item.sha256
                or _git_blob_oid(raw) != item.blob_oid
            ):
                raise WarehouseW3WheelError(
                    f"local Git blob differs: {item.logical_path}"
                )
            blobs[item.logical_path] = raw
        after = os.fstat(descriptor)
        named_after = os.lstat(repo_root)
    except OSError as exc:
        raise WarehouseW3WheelError("repo_root changed during Git acquisition") from exc
    finally:
        os.close(descriptor)
    if _stat_identity(after) != _stat_identity(identity) or _stat_identity(
        named_after
    ) != _stat_identity(identity):
        raise WarehouseW3WheelError("repo_root changed during Git acquisition")
    return _LocalGitAuthority(
        source_receipt_sha256=source_receipt.raw_sha256,
        source_commit=commit,
        source_tree=resolved_tree,
        source_date_epoch=epoch,
        blob_bytes=blobs,
    )


@dataclass(frozen=True, slots=True)
class _ArchiveMember:
    path: str
    kind: str
    mode: int
    mtime: int
    size_bytes: int
    sha256: str | None

    def to_mapping(self) -> dict[str, object]:
        return {
            "path": self.path,
            "kind": self.kind,
            "mode": self.mode,
            "mtime": self.mtime,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


def _archive_inventory(
    archive: ImmutableGitArchive,
    *,
    source_date_epoch: int,
) -> tuple[tuple[_ArchiveMember, ...], str, os.stat_result]:
    actual_sha256, identity = _hash_regular(archive.path, immutable=True)
    if actual_sha256 != archive.sha256:
        raise WarehouseW3WheelError("Git archive SHA-256 differs")
    members: list[_ArchiveMember] = []
    paths: set[str] = set()
    total = 0
    try:
        with archive.path.open("rb") as stream:
            with tarfile.open(fileobj=stream, mode="r:") as tar:
                raw_members = tar.getmembers()
                if not raw_members or len(raw_members) > _ARCHIVE_MEMBER_LIMIT:
                    raise WarehouseW3WheelError("Git archive member count differs")
                for member in raw_members:
                    path = _relative_path(member.name, field="archive member path")
                    if path in paths:
                        raise WarehouseW3WheelError(
                            "Git archive contains a duplicate path"
                        )
                    paths.add(path)
                    mode = member.mode & 0o7777
                    if (
                        type(member.mtime) is not int
                        or member.mtime != source_date_epoch
                    ):
                        raise WarehouseW3WheelError(
                            "Git archive SOURCE_DATE_EPOCH differs"
                        )
                    if member.isdir():
                        if mode != 0o755 or member.size != 0:
                            raise WarehouseW3WheelError(
                                "Git archive directory facts differ"
                            )
                        members.append(
                            _ArchiveMember(
                                path=path,
                                kind="directory",
                                mode=mode,
                                mtime=member.mtime,
                                size_bytes=0,
                                sha256=None,
                            )
                        )
                        continue
                    if not member.isfile() or mode not in {0o644, 0o755}:
                        raise WarehouseW3WheelError(
                            "Git archive contains a link or special member"
                        )
                    extracted = tar.extractfile(member)
                    if extracted is None:
                        raise WarehouseW3WheelError(
                            "Git archive regular member cannot be read"
                        )
                    digest = hashlib.sha256()
                    size = 0
                    while True:
                        chunk = extracted.read(_COPY_SIZE)
                        if not chunk:
                            break
                        digest.update(chunk)
                        size += len(chunk)
                    if size != member.size:
                        raise WarehouseW3WheelError("Git archive member size differs")
                    total += size
                    if total > _ARCHIVE_TOTAL_LIMIT:
                        raise WarehouseW3WheelError("Git archive is too large")
                    members.append(
                        _ArchiveMember(
                            path=path,
                            kind="regular",
                            mode=mode,
                            mtime=member.mtime,
                            size_bytes=size,
                            sha256=digest.hexdigest(),
                        )
                    )
    except (OSError, tarfile.TarError) as exc:
        raise WarehouseW3WheelError("cannot inspect Git archive") from exc
    expected_regular = {
        item.logical_path: item for item in archive.source_receipt.blobs
    }
    actual_regular = {item.path: item for item in members if item.kind == "regular"}
    expected_directories = {"."}
    for path in expected_regular:
        parent = PurePosixPath(path).parent
        while str(parent) != ".":
            expected_directories.add(str(parent))
            parent = parent.parent
    actual_directories = {
        ".",
        *(item.path for item in members if item.kind == "directory"),
    }
    if (
        frozenset(actual_regular) != frozenset(expected_regular)
        or actual_directories != expected_directories
        or any(
            actual_regular[path].mode != (0o755 if identity.mode == "100755" else 0o644)
            or actual_regular[path].sha256 != identity.sha256
            or actual_regular[path].size_bytes != identity.size_bytes
            for path, identity in expected_regular.items()
        )
    ):
        raise WarehouseW3WheelError("Git archive exact source receipt closure differs")
    members.append(
        _ArchiveMember(
            path=".",
            kind="directory",
            mode=0o755,
            mtime=source_date_epoch,
            size_bytes=0,
            sha256=None,
        )
    )
    ordered = tuple(sorted(members, key=lambda item: item.path.encode("utf-8")))
    aggregate = hashlib.sha256(
        b"scion.w3-git-archive-inventory.v1\0"
        + _canonical_json([item.to_mapping() for item in ordered])
    ).hexdigest()
    after_sha256, after_identity = _hash_regular(archive.path, immutable=True)
    if after_sha256 != actual_sha256 or _stat_identity(
        after_identity
    ) != _stat_identity(identity):
        raise WarehouseW3WheelError("Git archive changed while inventoried")
    return ordered, aggregate, identity


def _write_all(descriptor: int, stream: object, expected_size: int) -> str:
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = stream.read(_COPY_SIZE)
        if not chunk:
            break
        digest.update(chunk)
        size += len(chunk)
        view = memoryview(chunk)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("archive extraction made no progress")
            view = view[written:]
    if size != expected_size:
        raise WarehouseW3WheelError("extracted archive member size differs")
    return digest.hexdigest()


def _extract_archive(
    archive: ImmutableGitArchive,
    inventory: tuple[_ArchiveMember, ...],
    destination: Path,
) -> None:
    destination.mkdir(mode=0o700)
    expected = {item.path: item for item in inventory if item.path != "."}
    for item in sorted(
        (
            member
            for member in inventory
            if member.kind == "directory" and member.path != "."
        ),
        key=lambda member: (len(PurePosixPath(member.path).parts), member.path),
    ):
        (destination / item.path).mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        with archive.path.open("rb") as stream:
            with tarfile.open(fileobj=stream, mode="r:") as tar:
                seen: set[str] = set()
                for member in tar.getmembers():
                    path = _relative_path(member.name, field="archive member path")
                    item = expected.get(path)
                    if item is None or path in seen:
                        raise WarehouseW3WheelError(
                            "Git archive changed before extraction"
                        )
                    seen.add(path)
                    target = destination / path
                    if item.kind == "directory":
                        target.mkdir(mode=0o700, parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    extracted = tar.extractfile(member)
                    if extracted is None:
                        raise WarehouseW3WheelError(
                            "Git archive regular member cannot be extracted"
                        )
                    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
                    if hasattr(os, "O_NOFOLLOW"):
                        flags |= os.O_NOFOLLOW
                    descriptor = os.open(
                        target, flags, 0o700 if item.mode == 0o755 else 0o600
                    )
                    try:
                        actual = _write_all(descriptor, extracted, item.size_bytes)
                        if actual != item.sha256:
                            raise WarehouseW3WheelError(
                                "extracted archive member SHA-256 differs"
                            )
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
                if seen != set(expected):
                    raise WarehouseW3WheelError(
                        "Git archive extraction inventory differs"
                    )
    except (OSError, tarfile.TarError) as exc:
        raise WarehouseW3WheelError("cannot extract Git archive") from exc


class WheelCommandRunner(Protocol):
    """One exact no-shell command seam for the offline wheel builder."""

    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        environment: Mapping[str, str],
        umask: int,
    ) -> None:
        """Run one build and raise for any failure or ambiguous result."""


def _validate_runner_inputs(
    argv: tuple[str, ...],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    umask: int,
) -> None:
    if (
        type(argv) is not tuple
        or len(argv) != len(BUILDER_ARGV_TEMPLATE)
        or argv[:8] != BUILDER_ARGV_TEMPLATE[:8]
        or argv[-1] != "."
        or not isinstance(cwd, Path)
        or type(umask) is not int
        or umask != 0o077
    ):
        raise TypeError("wheel runner command differs")
    _absolute_path(cwd, field="runner.cwd")
    wheel_dir = Path(_absolute_path(Path(argv[8]), field="runner.wheel_dir"))
    if not wheel_dir.is_dir():
        raise WarehouseW3WheelError("wheel runner output directory is absent")
    if (
        not isinstance(environment, Mapping)
        or frozenset(environment) != _ENVIRONMENT_KEYS
    ):
        raise TypeError("wheel runner environment differs")
    template = dict(_ENVIRONMENT_TEMPLATE)
    for name, expected in template.items():
        value = environment[name]
        if type(value) is not str:
            raise TypeError("wheel runner environment value differs")
        if expected == "<home>":
            _absolute_path(Path(value), field="runner.HOME")
        elif expected == "<tmpdir>":
            _absolute_path(Path(value), field="runner.TMPDIR")
        elif expected == "<source-date-epoch>":
            if (
                not value.isascii()
                or not value.isdecimal()
                or not 0 < int(value) <= _EPOCH_MAX
            ):
                raise WarehouseW3WheelError("SOURCE_DATE_EPOCH differs")
        elif value != expected:
            raise WarehouseW3WheelError(f"wheel runner {name} differs")


class SubprocessWheelRunner:
    """Narrow production runner; no shell, inherited environment, or network."""

    __slots__ = ()

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("SubprocessWheelRunner is final")

    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        environment: Mapping[str, str],
        umask: int,
    ) -> None:
        _validate_runner_inputs(
            argv,
            cwd=cwd,
            environment=environment,
            umask=umask,
        )
        try:
            bwrap_metadata = os.lstat(BWRAP)
        except OSError as exc:
            raise WarehouseW3WheelError(
                "fixed bubblewrap runner is unavailable"
            ) from exc
        if (
            stat.S_ISLNK(bwrap_metadata.st_mode)
            or not stat.S_ISREG(bwrap_metadata.st_mode)
            or bwrap_metadata.st_uid != 0
            or bwrap_metadata.st_mode & 0o111 == 0
        ):
            raise WarehouseW3WheelError("fixed bubblewrap runner identity differs")
        wrapped_argv = (
            BWRAP,
            "--unshare-net",
            "--die-with-parent",
            "--bind",
            "/",
            "/",
            "--chdir",
            str(cwd),
            "--",
            *argv,
        )
        try:
            completed = subprocess.run(
                wrapped_argv,
                cwd=cwd,
                env=dict(environment),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                check=False,
                umask=umask,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise WarehouseW3WheelError("offline wheel command could not run") from exc
        if completed.returncode != 0:
            raise WarehouseW3WheelError("offline wheel command failed")


@dataclass(frozen=True, slots=True)
class WheelMember:
    """One complete ordinary wheel ZIP member identity."""

    path: str
    mode: int
    size_bytes: int
    compressed_size_bytes: int
    crc32: int
    compression: int
    sha256: str

    @classmethod
    def from_mapping(cls, value: object) -> "WheelMember":
        if type(value) is not dict:
            raise WarehouseW3WheelError("wheel member is not a mapping")
        _exact_keys(
            value,
            frozenset(
                {
                    "path",
                    "mode",
                    "size_bytes",
                    "compressed_size_bytes",
                    "crc32",
                    "compression",
                    "sha256",
                }
            ),
        )
        path = _relative_path(value["path"], field="wheel member path")
        mode = _uint(value["mode"], field="wheel member mode")
        if mode not in {0o644, 0o755}:
            raise WarehouseW3WheelError("wheel member mode differs")
        compression = _uint(
            value["compression"],
            field="wheel compression",
            maximum=_UINT32_MAX,
        )
        if compression not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
            raise WarehouseW3WheelError("wheel member compression differs")
        return cls(
            path=path,
            mode=mode,
            size_bytes=_uint(
                value["size_bytes"],
                field="wheel member size",
                maximum=_WHEEL_TOTAL_LIMIT,
            ),
            compressed_size_bytes=_uint(
                value["compressed_size_bytes"],
                field="wheel member compressed size",
                maximum=_WHEEL_TOTAL_LIMIT,
            ),
            crc32=_uint(
                value["crc32"],
                field="wheel member CRC32",
                maximum=_UINT32_MAX,
            ),
            compression=compression,
            sha256=_sha256(value["sha256"], field="wheel member sha256"),
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "path": self.path,
            "mode": self.mode,
            "size_bytes": self.size_bytes,
            "compressed_size_bytes": self.compressed_size_bytes,
            "crc32": self.crc32,
            "compression": self.compression,
            "sha256": self.sha256,
        }


def _member_inventory_sha256(members: tuple[WheelMember, ...]) -> str:
    return hashlib.sha256(
        b"scion.w3-wheel-member-inventory.v1\0"
        + _canonical_json([item.to_mapping() for item in members])
    ).hexdigest()


def _wheel_inventory(
    wheel_stream: BinaryIO,
    *,
    wheel_filename: str,
    forbidden_paths: tuple[Path, ...],
    required_modules: tuple[str, ...],
) -> tuple[tuple[WheelMember, ...], str, str]:
    if _WHEEL_NAME_RE.fullmatch(wheel_filename) is None:
        raise WarehouseW3WheelError("wheel filename or ABI tag differs")
    forbidden = tuple(str(path).encode("utf-8", "strict") for path in forbidden_paths)
    members: list[WheelMember] = []
    seen: set[str] = set()
    native_matches: list[tuple[str, str]] = []
    wheel_metadata: list[bytes] = []
    total = 0
    try:
        with zipfile.ZipFile(wheel_stream, mode="r") as archive:
            infos = archive.infolist()
            if not infos or len(infos) > _WHEEL_MEMBER_LIMIT:
                raise WarehouseW3WheelError("wheel member count differs")
            for info in infos:
                path = _relative_path(info.filename, field="wheel member path")
                if path in seen:
                    raise WarehouseW3WheelError("wheel contains a duplicate member")
                seen.add(path)
                raw_mode = info.external_attr >> 16
                if info.is_dir() or info.flag_bits & 0x1 or not stat.S_ISREG(raw_mode):
                    raise WarehouseW3WheelError(
                        "wheel contains a directory, link, or encrypted member"
                    )
                mode = stat.S_IMODE(raw_mode)
                if mode not in {0o644, 0o755}:
                    raise WarehouseW3WheelError("wheel member mode differs")
                if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                    raise WarehouseW3WheelError("wheel member compression differs")
                digest = hashlib.sha256()
                size = 0
                selected = bytearray()
                leak_carry = b""
                longest_forbidden = max(
                    (len(needle) for needle in forbidden if needle),
                    default=0,
                )
                with archive.open(info, mode="r") as stream:
                    while True:
                        chunk = stream.read(_COPY_SIZE)
                        if not chunk:
                            break
                        digest.update(chunk)
                        size += len(chunk)
                        if total + size > _WHEEL_TOTAL_LIMIT:
                            raise WarehouseW3WheelError("wheel content is too large")
                        if _DIST_WHEEL_RE.fullmatch(path) is not None:
                            if size > _WHEEL_METADATA_LIMIT:
                                raise WarehouseW3WheelError(
                                    "WHEEL metadata is too large"
                                )
                            selected.extend(chunk)
                        leak_window = leak_carry + chunk
                        if any(
                            needle and needle in leak_window for needle in forbidden
                        ):
                            raise WarehouseW3WheelError(
                                "wheel member leaks a disposable path"
                            )
                        if longest_forbidden > 1:
                            leak_carry = leak_window[-(longest_forbidden - 1) :]
                if size != info.file_size:
                    raise WarehouseW3WheelError("wheel member size differs")
                total += size
                member_sha256 = digest.hexdigest()
                if _NATIVE_MEMBER_RE.fullmatch(path) is not None:
                    native_matches.append((path, member_sha256))
                if _DIST_WHEEL_RE.fullmatch(path) is not None:
                    wheel_metadata.append(bytes(selected))
                members.append(
                    WheelMember(
                        path=path,
                        mode=mode,
                        size_bytes=size,
                        compressed_size_bytes=info.compress_size,
                        crc32=info.CRC,
                        compression=info.compress_type,
                        sha256=member_sha256,
                    )
                )
    except WarehouseW3WheelError:
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise WarehouseW3WheelError("cannot inspect built wheel") from exc
    ordered = tuple(sorted(members, key=lambda item: item.path.encode("utf-8")))
    paths = frozenset(item.path for item in ordered)
    if not frozenset(FIXED_REQUIRED_WHEEL_MEMBERS).issubset(paths):
        raise WarehouseW3WheelError("wheel lacks a fixed W3/runtime member")
    if not frozenset(required_modules).issubset(paths):
        raise WarehouseW3WheelError("wheel lacks a launch-archive Python module")
    if len(native_matches) != 1:
        raise WarehouseW3WheelError("wheel lacks one exact native extension")
    native_path, native_sha256 = native_matches[0]
    if native_sha256 != ACCEPTED_NATIVE_ELF_SHA256:
        raise WarehouseW3WheelError("wheel native ELF SHA-256 differs")
    if len(wheel_metadata) != 1:
        raise WarehouseW3WheelError("wheel lacks one exact WHEEL metadata member")
    try:
        metadata = wheel_metadata[0].decode("utf-8", "strict").splitlines()
    except UnicodeError as exc:
        raise WarehouseW3WheelError("WHEEL metadata is not UTF-8") from exc
    if (
        metadata.count("Root-Is-Purelib: false") != 1
        or metadata.count("Tag: cp312-cp312-linux_x86_64") != 1
    ):
        raise WarehouseW3WheelError("wheel metadata ABI facts differ")
    return ordered, native_path, native_sha256


@dataclass(frozen=True, slots=True)
class WheelFileIdentity:
    """Final immutable named inode accepted as the wheel artifact."""

    device: int
    inode: int
    mode: int
    uid: int
    gid: int
    nlink: int
    size_bytes: int
    mtime_ns: int
    ctime_ns: int

    @classmethod
    def from_stat_result(cls, value: os.stat_result) -> "WheelFileIdentity":
        if (
            not stat.S_ISREG(value.st_mode)
            or stat.S_IMODE(value.st_mode) != 0o444
            or value.st_nlink != 1
            or value.st_size <= 0
        ):
            raise WarehouseW3WheelError("final wheel inode identity differs")
        return cls(
            device=value.st_dev,
            inode=value.st_ino,
            mode=stat.S_IMODE(value.st_mode),
            uid=value.st_uid,
            gid=value.st_gid,
            nlink=value.st_nlink,
            size_bytes=value.st_size,
            mtime_ns=value.st_mtime_ns,
            ctime_ns=value.st_ctime_ns,
        )

    @classmethod
    def from_mapping(cls, value: object) -> "WheelFileIdentity":
        if type(value) is not dict:
            raise WarehouseW3WheelError("wheel identity is not a mapping")
        _exact_keys(
            value,
            frozenset(
                {
                    "device",
                    "inode",
                    "mode",
                    "uid",
                    "gid",
                    "nlink",
                    "size_bytes",
                    "mtime_ns",
                    "ctime_ns",
                }
            ),
        )
        identity = cls(
            device=_uint(value["device"], field="wheel identity.device"),
            inode=_uint(
                value["inode"],
                field="wheel identity.inode",
                positive=True,
            ),
            mode=_uint(
                value["mode"],
                field="wheel identity.mode",
                maximum=0o7777,
            ),
            uid=_uint(value["uid"], field="wheel identity.uid"),
            gid=_uint(value["gid"], field="wheel identity.gid"),
            nlink=_uint(
                value["nlink"],
                field="wheel identity.nlink",
                positive=True,
            ),
            size_bytes=_uint(
                value["size_bytes"],
                field="wheel identity.size_bytes",
                positive=True,
                maximum=_WHEEL_TOTAL_LIMIT,
            ),
            mtime_ns=_uint(
                value["mtime_ns"],
                field="wheel identity.mtime_ns",
            ),
            ctime_ns=_uint(
                value["ctime_ns"],
                field="wheel identity.ctime_ns",
            ),
        )
        if identity.mode != 0o444 or identity.nlink != 1:
            raise WarehouseW3WheelError("wheel identity is not immutable")
        return identity

    def to_mapping(self) -> dict[str, int]:
        return {
            "device": self.device,
            "inode": self.inode,
            "mode": self.mode,
            "uid": self.uid,
            "gid": self.gid,
            "nlink": self.nlink,
            "size_bytes": self.size_bytes,
            "mtime_ns": self.mtime_ns,
            "ctime_ns": self.ctime_ns,
        }


def _stable_wheel_inspection(
    wheel_path: Path,
    *,
    forbidden_paths: tuple[Path, ...],
    required_modules: tuple[str, ...],
    expected_identity: WheelFileIdentity | None = None,
) -> tuple[
    str,
    WheelFileIdentity,
    tuple[WheelMember, ...],
    str,
]:
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        named_before = os.lstat(wheel_path)
        descriptor = os.open(wheel_path, flags)
    except OSError as exc:
        raise WarehouseW3WheelError("cannot open built wheel") from exc
    try:
        opened = os.fstat(descriptor)
        if _stat_identity(opened) != _stat_identity(named_before):
            raise WarehouseW3WheelError("wheel changed before stable inspection")
        if expected_identity is None:
            os.fchmod(descriptor, 0o444)
        baseline = os.fstat(descriptor)
        identity = WheelFileIdentity.from_stat_result(baseline)
        named_sealed = os.lstat(wheel_path)
        if _stat_identity(named_sealed) != _stat_identity(baseline):
            raise WarehouseW3WheelError("wheel name changed while sealed")
        if expected_identity is not None and identity != expected_identity:
            raise WarehouseW3WheelError("final wheel inode was replaced")
        digest = hashlib.sha256()
        os.lseek(descriptor, 0, os.SEEK_SET)
        while True:
            chunk = os.read(descriptor, _COPY_SIZE)
            if not chunk:
                break
            digest.update(chunk)
        os.lseek(descriptor, 0, os.SEEK_SET)
        with os.fdopen(os.dup(descriptor), "rb") as stream:
            inventory, native_path, _native_sha = _wheel_inventory(
                stream,
                wheel_filename=wheel_path.name,
                forbidden_paths=forbidden_paths,
                required_modules=required_modules,
            )
        opened_after = os.fstat(descriptor)
        named_after = os.lstat(wheel_path)
    except WarehouseW3WheelError:
        raise
    except OSError as exc:
        raise WarehouseW3WheelError("wheel changed during stable inspection") from exc
    finally:
        os.close(descriptor)
    if _stat_identity(opened_after) != _stat_identity(baseline) or _stat_identity(
        named_after
    ) != _stat_identity(baseline):
        raise WarehouseW3WheelError("wheel changed during stable inspection")
    return digest.hexdigest(), identity, inventory, native_path


def _files_equal(first: Path, second: Path) -> bool:
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    first_fd = os.open(first, flags)
    second_fd = os.open(second, flags)
    try:
        while True:
            first_chunk = os.read(first_fd, _COPY_SIZE)
            second_chunk = os.read(second_fd, _COPY_SIZE)
            if first_chunk != second_chunk:
                return False
            if not first_chunk:
                return True
    finally:
        os.close(second_fd)
        os.close(first_fd)


@dataclass(frozen=True, slots=True, init=False)
class OfflineDoubleWheelReceipt:
    """Canonical final evidence for two equal offline W3 wheel builds."""

    source_receipt_sha256: str
    source_commit: str
    source_tree: str
    source_date_epoch: int
    archive_sha256: tuple[str, str]
    archive_identities: tuple[WheelFileIdentity, WheelFileIdentity]
    archive_inventory_sha256: str
    required_module_members: tuple[str, ...]
    wheel_filename: str
    wheel_size_bytes: int
    wheel_sha256: str
    wheel_identity: WheelFileIdentity
    wheel_identities: tuple[WheelFileIdentity, WheelFileIdentity]
    member_inventory: tuple[WheelMember, ...]
    member_inventory_sha256: str
    native_member_path: str
    native_elf_sha256: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "OfflineDoubleWheelReceipt":
        del cls
        raise TypeError("OfflineDoubleWheelReceipt must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("OfflineDoubleWheelReceipt is final")

    @classmethod
    def _from_verified_build(
        cls,
        *,
        source_receipt_sha256: str,
        source_commit: str,
        source_tree: str,
        source_date_epoch: int,
        archive_sha256: tuple[str, str],
        archive_identities: tuple[WheelFileIdentity, WheelFileIdentity],
        archive_inventory_sha256: str,
        required_module_members: tuple[str, ...],
        wheel_filename: str,
        wheel_size_bytes: int,
        wheel_sha256: str,
        wheel_identity: WheelFileIdentity,
        wheel_identities: tuple[WheelFileIdentity, WheelFileIdentity],
        member_inventory: tuple[WheelMember, ...],
        native_member_path: str,
    ) -> "OfflineDoubleWheelReceipt":
        return cls._for_test(
            source_receipt_sha256=source_receipt_sha256,
            source_commit=source_commit,
            source_tree=source_tree,
            source_date_epoch=source_date_epoch,
            archive_sha256=archive_sha256,
            archive_identities=archive_identities,
            archive_inventory_sha256=archive_inventory_sha256,
            required_module_members=required_module_members,
            wheel_filename=wheel_filename,
            wheel_size_bytes=wheel_size_bytes,
            wheel_sha256=wheel_sha256,
            wheel_identity=wheel_identity,
            wheel_identities=wheel_identities,
            member_inventory=member_inventory,
            native_member_path=native_member_path,
        )

    @classmethod
    def _for_test(
        cls,
        *,
        source_commit: str,
        source_tree: str,
        source_date_epoch: int,
        archive_sha256: tuple[str, str],
        archive_inventory_sha256: str,
        required_module_members: tuple[str, ...],
        wheel_filename: str,
        wheel_size_bytes: int,
        wheel_sha256: str,
        member_inventory: tuple[WheelMember, ...],
        native_member_path: str,
        source_receipt_sha256: str | None = None,
        wheel_identity: WheelFileIdentity | None = None,
        archive_identities: tuple[WheelFileIdentity, WheelFileIdentity] | None = None,
        wheel_identities: tuple[WheelFileIdentity, WheelFileIdentity] | None = None,
    ) -> "OfflineDoubleWheelReceipt":
        if (
            type(archive_sha256) is not tuple
            or len(archive_sha256) != 2
            or type(required_module_members) is not tuple
            or type(member_inventory) is not tuple
        ):
            raise TypeError("wheel receipt tuple fields differ")
        receipt_sha = (
            hashlib.sha256(
                b"scion.w3-test-fixture-source-receipt.v1\0"
                + source_commit.encode("ascii")
                + source_tree.encode("ascii")
            ).hexdigest()
            if source_receipt_sha256 is None
            else _sha256(
                source_receipt_sha256,
                field="source_receipt_sha256",
            )
        )
        identity = (
            WheelFileIdentity(
                device=0,
                inode=1,
                mode=0o444,
                uid=0,
                gid=0,
                nlink=1,
                size_bytes=wheel_size_bytes,
                mtime_ns=0,
                ctime_ns=0,
            )
            if wheel_identity is None
            else wheel_identity
        )
        if type(identity) is not WheelFileIdentity:
            raise TypeError("wheel_identity must be exact WheelFileIdentity")
        archive_identity_pair = (
            (
                WheelFileIdentity(0, 2, 0o444, 0, 0, 1, 1, 0, 0),
                WheelFileIdentity(0, 3, 0o444, 0, 0, 1, 1, 0, 0),
            )
            if archive_identities is None
            else archive_identities
        )
        wheel_identity_pair = (
            (
                identity,
                WheelFileIdentity(
                    identity.device,
                    identity.inode + 1,
                    identity.mode,
                    identity.uid,
                    identity.gid,
                    identity.nlink,
                    identity.size_bytes,
                    identity.mtime_ns,
                    identity.ctime_ns,
                ),
            )
            if wheel_identities is None
            else wheel_identities
        )
        if (
            type(archive_identity_pair) is not tuple
            or len(archive_identity_pair) != 2
            or any(
                type(item) is not WheelFileIdentity for item in archive_identity_pair
            )
            or type(wheel_identity_pair) is not tuple
            or len(wheel_identity_pair) != 2
            or any(type(item) is not WheelFileIdentity for item in wheel_identity_pair)
            or wheel_identity_pair[0] != identity
        ):
            raise TypeError("double-build file identities differ")
        value = {
            "schema": _SCHEMA,
            "fixed_plan_sha256": ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
            "source_receipt_sha256": receipt_sha,
            "source_commit": _git_oid(source_commit, field="source_commit"),
            "source_tree": _git_oid(source_tree, field="source_tree"),
            "source_date_epoch": _uint(
                source_date_epoch,
                field="source_date_epoch",
                positive=True,
                maximum=_EPOCH_MAX,
            ),
            "archive_sha256": [
                _sha256(item, field="archive_sha256") for item in archive_sha256
            ],
            "archive_identities": [item.to_mapping() for item in archive_identity_pair],
            "archive_inventory_sha256": _sha256(
                archive_inventory_sha256,
                field="archive_inventory_sha256",
            ),
            "builder_argv_template": list(BUILDER_ARGV_TEMPLATE),
            "build_environment_template": dict(_ENVIRONMENT_TEMPLATE),
            "umask": 0o077,
            "required_module_members": list(required_module_members),
            "wheel_filename": wheel_filename,
            "wheel_size_bytes": _uint(
                wheel_size_bytes,
                field="wheel_size_bytes",
                positive=True,
            ),
            "wheel_sha256": _sha256(wheel_sha256, field="wheel_sha256"),
            "wheel_identity": identity.to_mapping(),
            "wheel_identities": [item.to_mapping() for item in wheel_identity_pair],
            "member_inventory": [item.to_mapping() for item in member_inventory],
            "member_inventory_sha256": _member_inventory_sha256(member_inventory),
            "native_member_path": native_member_path,
            "native_elf_sha256": ACCEPTED_NATIVE_ELF_SHA256,
            "retry": False,
            "resume": False,
            "reuse": False,
        }
        return cls.from_bytes(_canonical_json(value))

    @classmethod
    def from_bytes(cls, raw: bytes) -> "OfflineDoubleWheelReceipt":
        value = _decode_canonical(raw)
        _exact_keys(
            value,
            frozenset(
                {
                    "schema",
                    "fixed_plan_sha256",
                    "source_receipt_sha256",
                    "source_commit",
                    "source_tree",
                    "source_date_epoch",
                    "archive_sha256",
                    "archive_identities",
                    "archive_inventory_sha256",
                    "builder_argv_template",
                    "build_environment_template",
                    "umask",
                    "required_module_members",
                    "wheel_filename",
                    "wheel_size_bytes",
                    "wheel_sha256",
                    "wheel_identity",
                    "wheel_identities",
                    "member_inventory",
                    "member_inventory_sha256",
                    "native_member_path",
                    "native_elf_sha256",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
        )
        if (
            value["schema"] != _SCHEMA
            or value["fixed_plan_sha256"] != ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256
            or value["builder_argv_template"] != list(BUILDER_ARGV_TEMPLATE)
            or value["build_environment_template"] != dict(_ENVIRONMENT_TEMPLATE)
            or value["umask"] != 0o077
            or value["native_elf_sha256"] != ACCEPTED_NATIVE_ELF_SHA256
            or value["retry"] is not False
            or value["resume"] is not False
            or value["reuse"] is not False
        ):
            raise WarehouseW3WheelError("wheel receipt fixed authority differs")
        raw_archives = value["archive_sha256"]
        if type(raw_archives) is not list or len(raw_archives) != 2:
            raise WarehouseW3WheelError("wheel receipt archive inventory differs")
        archive_sha256 = tuple(
            _sha256(item, field="archive_sha256") for item in raw_archives
        )
        raw_archive_identities = value["archive_identities"]
        if type(raw_archive_identities) is not list or len(raw_archive_identities) != 2:
            raise WarehouseW3WheelError("archive identities differ")
        archive_identities = tuple(
            WheelFileIdentity.from_mapping(item) for item in raw_archive_identities
        )
        if archive_identities[0] == archive_identities[1]:
            raise WarehouseW3WheelError("archive identities are not independent")
        raw_required = value["required_module_members"]
        if type(raw_required) is not list:
            raise WarehouseW3WheelError("required module inventory is not an array")
        required = tuple(
            _relative_path(item, field="required module") for item in raw_required
        )
        if (
            required != tuple(sorted(required, key=lambda item: item.encode("utf-8")))
            or len(set(required)) != len(required)
            or not frozenset(
                item for item in FIXED_REQUIRED_WHEEL_MEMBERS if item.endswith(".py")
            ).issubset(required)
        ):
            raise WarehouseW3WheelError("required module inventory differs")
        raw_members = value["member_inventory"]
        if type(raw_members) is not list or not raw_members:
            raise WarehouseW3WheelError("wheel member inventory is empty")
        members = tuple(WheelMember.from_mapping(item) for item in raw_members)
        member_paths = tuple(item.path for item in members)
        if (
            member_paths
            != tuple(sorted(member_paths, key=lambda item: item.encode("utf-8")))
            or len(set(member_paths)) != len(member_paths)
            or not frozenset(FIXED_REQUIRED_WHEEL_MEMBERS).issubset(member_paths)
            or not frozenset(required).issubset(member_paths)
        ):
            raise WarehouseW3WheelError("wheel member inventory closure differs")
        allowed_source_payload = frozenset(
            {
                *required,
                W3_RUN_TEMPLATE_MEMBER,
                W3_CLOSE_TEMPLATE_MEMBER,
            }
        )
        actual_source_payload = frozenset(
            item.path
            for item in members
            if item.path.endswith(".py") or item.path.endswith(".service")
        )
        if actual_source_payload != allowed_source_payload:
            raise WarehouseW3WheelError("wheel Python/template payload closure differs")
        inventory_sha256 = _sha256(
            value["member_inventory_sha256"],
            field="member_inventory_sha256",
        )
        if inventory_sha256 != _member_inventory_sha256(members):
            raise WarehouseW3WheelError("wheel member inventory SHA-256 differs")
        filename = value["wheel_filename"]
        if type(filename) is not str or _WHEEL_NAME_RE.fullmatch(filename) is None:
            raise WarehouseW3WheelError("wheel filename differs")
        native_path = _relative_path(
            value["native_member_path"],
            field="native_member_path",
        )
        native = [item for item in members if _NATIVE_MEMBER_RE.fullmatch(item.path)]
        if (
            len(native) != 1
            or native[0].path != native_path
            or native[0].sha256 != ACCEPTED_NATIVE_ELF_SHA256
        ):
            raise WarehouseW3WheelError("wheel native member identity differs")
        wheel_size = _uint(
            value["wheel_size_bytes"],
            field="wheel_size_bytes",
            positive=True,
            maximum=_WHEEL_TOTAL_LIMIT,
        )
        wheel_identity = WheelFileIdentity.from_mapping(value["wheel_identity"])
        raw_wheel_identities = value["wheel_identities"]
        if type(raw_wheel_identities) is not list or len(raw_wheel_identities) != 2:
            raise WarehouseW3WheelError("wheel identities differ")
        wheel_identities = tuple(
            WheelFileIdentity.from_mapping(item) for item in raw_wheel_identities
        )
        if wheel_identity.size_bytes != wheel_size:
            raise WarehouseW3WheelError("wheel identity size differs")
        if (
            wheel_identities[0] != wheel_identity
            or wheel_identities[0] == wheel_identities[1]
            or any(item.size_bytes != wheel_size for item in wheel_identities)
        ):
            raise WarehouseW3WheelError("double-build wheel identities differ")
        fields = {
            "source_receipt_sha256": _sha256(
                value["source_receipt_sha256"],
                field="source_receipt_sha256",
            ),
            "source_commit": _git_oid(value["source_commit"], field="source_commit"),
            "source_tree": _git_oid(value["source_tree"], field="source_tree"),
            "source_date_epoch": _uint(
                value["source_date_epoch"],
                field="source_date_epoch",
                positive=True,
                maximum=_EPOCH_MAX,
            ),
            "archive_sha256": archive_sha256,
            "archive_identities": archive_identities,
            "archive_inventory_sha256": _sha256(
                value["archive_inventory_sha256"],
                field="archive_inventory_sha256",
            ),
            "required_module_members": required,
            "wheel_filename": filename,
            "wheel_size_bytes": wheel_size,
            "wheel_sha256": _sha256(value["wheel_sha256"], field="wheel_sha256"),
            "wheel_identity": wheel_identity,
            "wheel_identities": wheel_identities,
            "member_inventory": members,
            "member_inventory_sha256": inventory_sha256,
            "native_member_path": native_path,
            "native_elf_sha256": ACCEPTED_NATIVE_ELF_SHA256,
            "raw": raw,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
        instance = object.__new__(cls)
        for field, item in fields.items():
            object.__setattr__(instance, field, item)
        return instance


@dataclass(frozen=True, slots=True)
class _OfflineDoubleWheelBuildEvidence:
    repo_root: Path
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive]
    wheel_paths: tuple[Path, Path]
    wheel_identities: tuple[WheelFileIdentity, WheelFileIdentity]
    receipt: OfflineDoubleWheelReceipt
    build_argv: tuple[tuple[str, ...], tuple[str, ...]]


@dataclass(frozen=True, slots=True, init=False)
class _ProductionOfflineDoubleWheelBuildEvidence:
    evidence: _OfflineDoubleWheelBuildEvidence

    def __new__(cls) -> "_ProductionOfflineDoubleWheelBuildEvidence":
        del cls
        raise TypeError("production build evidence is internally acquired")


def _validate_build_evidence(evidence: _OfflineDoubleWheelBuildEvidence) -> None:
    if (
        type(evidence) is not _OfflineDoubleWheelBuildEvidence
        or not isinstance(evidence.repo_root, Path)
        or type(evidence.archives) is not tuple
        or len(evidence.archives) != 2
        or any(type(item) is not ImmutableGitArchive for item in evidence.archives)
        or type(evidence.wheel_paths) is not tuple
        or len(evidence.wheel_paths) != 2
        or any(not isinstance(path, Path) for path in evidence.wheel_paths)
        or type(evidence.wheel_identities) is not tuple
        or len(evidence.wheel_identities) != 2
        or any(
            type(item) is not WheelFileIdentity for item in evidence.wheel_identities
        )
        or type(evidence.receipt) is not OfflineDoubleWheelReceipt
        or type(evidence.build_argv) is not tuple
        or len(evidence.build_argv) != 2
        or any(
            type(argv) is not tuple
            or not argv
            or any(type(item) is not str or not item for item in argv)
            for argv in evidence.build_argv
        )
    ):
        raise TypeError("offline double-wheel build evidence fields differ")
    _absolute_path(evidence.repo_root, field="repo_root")
    _absolute_path(evidence.wheel_paths[0], field="wheel_path")
    _absolute_path(evidence.wheel_paths[1], field="second_wheel_path")
    work_root = evidence.wheel_paths[0].parents[2]
    expected_argv = (
        BUILDER_ARGV_TEMPLATE[:8] + (str(work_root / "build-1" / "wheel"), "."),
        BUILDER_ARGV_TEMPLATE[:8] + (str(work_root / "build-2" / "wheel"), "."),
    )
    if (
        evidence.wheel_paths[0].parent != work_root / "build-1" / "wheel"
        or evidence.wheel_paths[1].parent != work_root / "build-2" / "wheel"
        or evidence.wheel_paths[0].name != evidence.receipt.wheel_filename
        or evidence.wheel_paths[1].name != evidence.receipt.wheel_filename
        or evidence.wheel_identities[0] != evidence.receipt.wheel_identity
        or evidence.wheel_identities != evidence.receipt.wheel_identities
        or tuple(
            WheelFileIdentity.from_stat_result(os.lstat(item.path))
            for item in evidence.archives
        )
        != evidence.receipt.archive_identities
        or evidence.build_argv != expected_argv
    ):
        raise WarehouseW3WheelError("offline double-wheel build evidence differs")


@dataclass(frozen=True, slots=True, init=False)
class OfflineDoubleWheelArtifact:
    """Complete build provenance; verification relies on reacquired external facts.

    Private Python construction is a convention, not an in-process security
    boundary.  The public verifier proves the repository, archives, and wheels.
    """

    repo_root: Path
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive]
    wheel_path: Path
    second_wheel_path: Path
    wheel_identity: WheelFileIdentity
    second_wheel_identity: WheelFileIdentity
    receipt: OfflineDoubleWheelReceipt
    build_argv: tuple[tuple[str, ...], tuple[str, ...]]

    def __new__(
        cls,
        *_args: object,
        **_kwargs: object,
    ) -> "OfflineDoubleWheelArtifact":
        del cls, _args, _kwargs
        raise TypeError("OfflineDoubleWheelArtifact is build-owner constructed")

    @classmethod
    def _from_production_build(
        cls,
        production: _ProductionOfflineDoubleWheelBuildEvidence,
    ) -> "OfflineDoubleWheelArtifact":
        if type(production) is not _ProductionOfflineDoubleWheelBuildEvidence:
            raise TypeError("production build evidence type differs")
        evidence = production.evidence
        _validate_build_evidence(evidence)
        instance = object.__new__(cls)
        for field, value in (
            ("repo_root", evidence.repo_root),
            ("archives", evidence.archives),
            ("wheel_path", evidence.wheel_paths[0]),
            ("second_wheel_path", evidence.wheel_paths[1]),
            ("wheel_identity", evidence.wheel_identities[0]),
            ("second_wheel_identity", evidence.wheel_identities[1]),
            ("receipt", evidence.receipt),
            ("build_argv", evidence.build_argv),
        ):
            object.__setattr__(instance, field, value)
        return instance

    @classmethod
    def _for_test(
        cls,
        *,
        wheel_path: Path,
        wheel_identity: WheelFileIdentity,
        receipt: OfflineDoubleWheelReceipt,
        build_argv: tuple[tuple[str, ...], tuple[str, ...]],
    ) -> "OfflineDoubleWheelArtifact":
        """Create receipt-shape-only evidence that production verification rejects."""

        instance = object.__new__(cls)
        for field, value in (
            ("repo_root", wheel_path.parents[2]),
            ("archives", ()),
            ("wheel_path", wheel_path),
            (
                "second_wheel_path",
                wheel_path.parents[2] / "build-2" / "wheel" / wheel_path.name,
            ),
            ("wheel_identity", wheel_identity),
            ("second_wheel_identity", wheel_identity),
            ("receipt", receipt),
            ("build_argv", build_argv),
        ):
            object.__setattr__(instance, field, value)
        return instance

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("OfflineDoubleWheelArtifact is final")


@dataclass(frozen=True, slots=True)
class _TestOfflineDoubleWheelArtifact:
    """Hermetic test result that is never accepted by the public verifier."""

    repo_root: Path
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive]
    wheel_path: Path
    second_wheel_path: Path
    wheel_identity: WheelFileIdentity
    second_wheel_identity: WheelFileIdentity
    receipt: OfflineDoubleWheelReceipt
    build_argv: tuple[tuple[str, ...], tuple[str, ...]]

    @classmethod
    def from_evidence(
        cls,
        evidence: _OfflineDoubleWheelBuildEvidence,
    ) -> "_TestOfflineDoubleWheelArtifact":
        _validate_build_evidence(evidence)
        return cls(
            repo_root=evidence.repo_root,
            archives=evidence.archives,
            wheel_path=evidence.wheel_paths[0],
            second_wheel_path=evidence.wheel_paths[1],
            wheel_identity=evidence.wheel_identities[0],
            second_wheel_identity=evidence.wheel_identities[1],
            receipt=evidence.receipt,
            build_argv=evidence.build_argv,
        )


def _verify_offline_double_wheel_artifact_provenance(
    artifact: OfflineDoubleWheelArtifact | _TestOfflineDoubleWheelArtifact,
    *,
    git_reader: LocalGitReader,
) -> OfflineDoubleWheelReceipt:
    if type(artifact) not in {
        OfflineDoubleWheelArtifact,
        _TestOfflineDoubleWheelArtifact,
    }:
        raise TypeError("artifact type differs")
    _validate_build_evidence(
        _OfflineDoubleWheelBuildEvidence(
            repo_root=artifact.repo_root,
            archives=artifact.archives,
            wheel_paths=(artifact.wheel_path, artifact.second_wheel_path),
            wheel_identities=(
                artifact.wheel_identity,
                artifact.second_wheel_identity,
            ),
            receipt=artifact.receipt,
            build_argv=artifact.build_argv,
        )
    )
    try:
        parsed = OfflineDoubleWheelReceipt.from_bytes(artifact.receipt.raw)
    except Exception as exc:
        raise WarehouseW3WheelError(
            "offline double-wheel receipt cannot be reopened"
        ) from exc
    if parsed != artifact.receipt:
        raise WarehouseW3WheelError("offline double-wheel receipt object differs")
    authority = _acquire_local_git_authority(
        artifact.repo_root,
        artifact.archives[0].source_receipt,
        reader=git_reader,
    )
    archive_facts = tuple(
        _archive_inventory(item, source_date_epoch=authority.source_date_epoch)
        for item in artifact.archives
    )
    wheel_facts = (
        _stable_wheel_inspection(
            artifact.wheel_path,
            forbidden_paths=(),
            required_modules=parsed.required_module_members,
            expected_identity=artifact.wheel_identity,
        ),
        _stable_wheel_inspection(
            artifact.second_wheel_path,
            forbidden_paths=(),
            required_modules=parsed.required_module_members,
            expected_identity=artifact.second_wheel_identity,
        ),
    )
    source_members = {
        item.path: item for item in archive_facts[0][0] if item.kind == "regular"
    }
    required_payloads = (
        *parsed.required_module_members,
        W3_RUN_TEMPLATE_MEMBER,
        W3_CLOSE_TEMPLATE_MEMBER,
    )
    wheel_members = {item.path: item for item in wheel_facts[0][2]}
    if (
        artifact.archives[0].source_receipt.raw
        != artifact.archives[1].source_receipt.raw
        or authority.source_receipt_sha256 != parsed.source_receipt_sha256
        or authority.source_commit != parsed.source_commit
        or authority.source_tree != parsed.source_tree
        or authority.source_date_epoch != parsed.source_date_epoch
        or archive_facts[0][0] != archive_facts[1][0]
        or archive_facts[0][1] != parsed.archive_inventory_sha256
        or tuple(WheelFileIdentity.from_stat_result(item[2]) for item in archive_facts)
        != parsed.archive_identities
        or tuple(item.sha256 for item in artifact.archives) != parsed.archive_sha256
        or wheel_facts[0][0] != wheel_facts[1][0]
        or wheel_facts[0][0] != parsed.wheel_sha256
        or (wheel_facts[0][1], wheel_facts[1][1]) != parsed.wheel_identities
        or wheel_facts[0][2] != wheel_facts[1][2]
        or wheel_facts[0][2] != parsed.member_inventory
        or wheel_facts[0][3] != wheel_facts[1][3]
        or wheel_facts[0][3] != parsed.native_member_path
        or not _files_equal(artifact.wheel_path, artifact.second_wheel_path)
        or any(
            path not in source_members
            or path not in wheel_members
            or source_members[path].sha256 != wheel_members[path].sha256
            or source_members[path].size_bytes != wheel_members[path].size_bytes
            for path in required_payloads
        )
    ):
        raise WarehouseW3WheelError("reopened offline double-wheel artifact differs")
    final_authority = _acquire_local_git_authority(
        artifact.repo_root,
        artifact.archives[0].source_receipt,
        reader=git_reader,
    )
    final_archive_facts = tuple(
        _archive_inventory(item, source_date_epoch=final_authority.source_date_epoch)
        for item in artifact.archives
    )
    final_wheel_facts = (
        _stable_wheel_inspection(
            artifact.wheel_path,
            forbidden_paths=(),
            required_modules=parsed.required_module_members,
            expected_identity=artifact.wheel_identity,
        ),
        _stable_wheel_inspection(
            artifact.second_wheel_path,
            forbidden_paths=(),
            required_modules=parsed.required_module_members,
            expected_identity=artifact.second_wheel_identity,
        ),
    )
    if (
        final_authority != authority
        or final_archive_facts != archive_facts
        or final_wheel_facts != wheel_facts
        or final_wheel_facts[0][0] != parsed.wheel_sha256
        or final_wheel_facts[0][2] != parsed.member_inventory
        or final_wheel_facts[0][3] != parsed.native_member_path
        or final_wheel_facts[0][0] != final_wheel_facts[1][0]
        or final_wheel_facts[0][2] != final_wheel_facts[1][2]
    ):
        raise WarehouseW3WheelError("final offline double-wheel provenance changed")
    return parsed


def verify_offline_double_wheel_artifact(
    artifact: OfflineDoubleWheelArtifact,
) -> OfflineDoubleWheelReceipt:
    """Reacquire Git, both archives, and both wheel builds through fixed readers."""

    if type(artifact) is not OfflineDoubleWheelArtifact:
        raise TypeError("artifact must be exact production OfflineDoubleWheelArtifact")
    return _verify_offline_double_wheel_artifact_provenance(
        artifact,
        git_reader=SubprocessLocalGitReader(),
    )


def reopen_offline_double_wheel_artifact(
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive],
    *,
    repo_root: Path,
    work_root: Path,
    receipt: OfflineDoubleWheelReceipt,
) -> OfflineDoubleWheelArtifact:
    """Reconstruct and fully reverify one fixed-path production build."""

    if (
        type(archives) is not tuple
        or len(archives) != 2
        or any(type(item) is not ImmutableGitArchive for item in archives)
    ):
        raise TypeError("archives must be two exact ImmutableGitArchive values")
    if type(receipt) is not OfflineDoubleWheelReceipt:
        raise TypeError("receipt must be exact OfflineDoubleWheelReceipt")
    if OfflineDoubleWheelReceipt.from_bytes(receipt.raw) != receipt:
        raise WarehouseW3WheelError("offline double-wheel receipt object differs")
    _absolute_path(repo_root, field="repo_root")
    _absolute_path(work_root, field="work_root")
    wheel_paths = (
        work_root / "build-1" / "wheel" / receipt.wheel_filename,
        work_root / "build-2" / "wheel" / receipt.wheel_filename,
    )
    evidence = _OfflineDoubleWheelBuildEvidence(
        repo_root=repo_root,
        archives=archives,
        wheel_paths=wheel_paths,
        wheel_identities=receipt.wheel_identities,
        receipt=receipt,
        build_argv=(
            BUILDER_ARGV_TEMPLATE[:8] + (str(work_root / "build-1" / "wheel"), "."),
            BUILDER_ARGV_TEMPLATE[:8] + (str(work_root / "build-2" / "wheel"), "."),
        ),
    )
    production = object.__new__(_ProductionOfflineDoubleWheelBuildEvidence)
    object.__setattr__(production, "evidence", evidence)
    artifact = OfflineDoubleWheelArtifact._from_production_build(production)
    if verify_offline_double_wheel_artifact(artifact) != receipt:
        raise WarehouseW3WheelError("reopened offline double-wheel receipt differs")
    return artifact


def _verify_offline_double_wheel_artifact_for_test(
    artifact: _TestOfflineDoubleWheelArtifact,
    *,
    git_reader: LocalGitReader,
) -> OfflineDoubleWheelReceipt:
    if type(artifact) is not _TestOfflineDoubleWheelArtifact:
        raise TypeError("artifact must be exact test OfflineDoubleWheelArtifact")
    return _verify_offline_double_wheel_artifact_provenance(
        artifact,
        git_reader=git_reader,
    )


def _build_environment(
    home: Path, tmpdir: Path, source_date_epoch: int
) -> dict[str, str]:
    environment = dict(_ENVIRONMENT_TEMPLATE)
    environment["HOME"] = str(home)
    environment["TMPDIR"] = str(tmpdir)
    environment["SOURCE_DATE_EPOCH"] = str(source_date_epoch)
    return environment


def _run(
    runner: WheelCommandRunner,
    argv: tuple[str, ...],
    *,
    cwd: Path,
    environment: Mapping[str, str],
) -> None:
    method = getattr(runner, "run", None)
    if not callable(method):
        raise TypeError("runner must expose run")
    _validate_runner_inputs(
        argv,
        cwd=cwd,
        environment=environment,
        umask=0o077,
    )
    try:
        result = method(
            argv,
            cwd=cwd,
            environment=environment,
            umask=0o077,
        )
    except WarehouseW3WheelError:
        raise
    except Exception as exc:
        raise WarehouseW3WheelError("offline wheel runner failed") from exc
    if result is not None:
        raise WarehouseW3WheelError("offline wheel runner returned a result")


def _acquire_offline_double_wheel_build_evidence(
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive],
    *,
    repo_root: Path,
    work_root: Path,
    runner: WheelCommandRunner,
    git_reader: LocalGitReader,
) -> _OfflineDoubleWheelBuildEvidence:
    """Execute and validate both builds, returning unowned internal evidence."""

    if os.geteuid() == 0:
        raise WarehouseW3WheelError("offline wheel build rejects effective UID zero")
    if (
        type(archives) is not tuple
        or len(archives) != 2
        or any(type(item) is not ImmutableGitArchive for item in archives)
    ):
        raise TypeError("archives must be two exact ImmutableGitArchive values")
    root_text = _absolute_path(work_root, field="work_root")
    if os.path.lexists(work_root):
        raise WarehouseW3WheelError("work_root is already present")
    if (
        archives[0].path == archives[1].path
        or archives[0].source_receipt.raw != archives[1].source_receipt.raw
    ):
        raise WarehouseW3WheelError("Git archive source identities differ")
    authority = _acquire_local_git_authority(
        repo_root,
        archives[0].source_receipt,
        reader=git_reader,
    )
    epoch = authority.source_date_epoch
    first_inventory, first_aggregate, first_identity = _archive_inventory(
        archives[0],
        source_date_epoch=epoch,
    )
    second_inventory, second_aggregate, second_identity = _archive_inventory(
        archives[1],
        source_date_epoch=epoch,
    )
    if (
        (first_identity.st_dev, first_identity.st_ino)
        == (second_identity.st_dev, second_identity.st_ino)
        or first_inventory != second_inventory
        or first_aggregate != second_aggregate
    ):
        raise WarehouseW3WheelError("Git archive inventories are not independent/equal")
    source_paths = frozenset(
        item.path for item in first_inventory if item.kind == "regular"
    )
    if not frozenset(FIXED_REQUIRED_WHEEL_MEMBERS).issubset(source_paths):
        raise WarehouseW3WheelError("Git archive lacks fixed W3/runtime source")
    required_modules = tuple(
        sorted(
            (
                path
                for path in source_paths
                if path.startswith("scion/")
                and path.endswith(".py")
                and not path.startswith("scion/tests/")
            ),
            key=lambda item: item.encode("utf-8"),
        )
    )
    required_payloads = frozenset(
        {
            *required_modules,
            W3_RUN_TEMPLATE_MEMBER,
            W3_CLOSE_TEMPLATE_MEMBER,
        }
    )
    source_members = {
        item.path: item for item in first_inventory if item.kind == "regular"
    }
    receipt_blobs = {
        item.logical_path: item for item in archives[0].source_receipt.blobs
    }
    if frozenset(receipt_blobs) != source_paths:
        raise WarehouseW3WheelError(
            "Git archive is not the exact source receipt blob inventory"
        )
    if not required_payloads.issubset(receipt_blobs):
        raise WarehouseW3WheelError(
            "Git source receipt lacks required Python/template blobs"
        )
    for path, blob in receipt_blobs.items():
        member = source_members.get(path)
        local_raw = authority.blob_bytes.get(path)
        if (
            member is None
            or local_raw is None
            or member.sha256 != blob.sha256
            or member.size_bytes != blob.size_bytes
            or member.mode != (0o755 if blob.mode == "100755" else 0o644)
            or hashlib.sha256(local_raw).hexdigest() != member.sha256
        ):
            raise WarehouseW3WheelError(
                f"Git archive differs from source receipt: {path}"
            )
    selected_runner = runner
    try:
        work_root.mkdir(mode=0o700)
    except OSError as exc:
        raise WarehouseW3WheelError(
            f"cannot create offline wheel work root: {root_text}"
        ) from exc
    build_argv: list[tuple[str, ...]] = []
    wheel_paths: list[Path] = []
    wheel_inventories: list[tuple[WheelMember, ...]] = []
    wheel_sha256: list[str] = []
    wheel_identities: list[WheelFileIdentity] = []
    native_paths: list[str] = []
    for index, (archive, inventory) in enumerate(
        zip(archives, (first_inventory, second_inventory), strict=True),
        1,
    ):
        build_root = work_root / f"build-{index}"
        source_root = build_root / "source"
        home = build_root / "home"
        tmpdir = build_root / "tmp"
        wheel_dir = build_root / "wheel"
        build_root.mkdir(mode=0o700)
        for directory in (home, tmpdir, wheel_dir):
            directory.mkdir(mode=0o700)
        _extract_archive(archive, inventory, source_root)
        argv = BUILDER_ARGV_TEMPLATE[:8] + (str(wheel_dir), ".")
        environment = _build_environment(home, tmpdir, epoch)
        _run(
            selected_runner,
            argv,
            cwd=source_root,
            environment=environment,
        )
        try:
            children = tuple(wheel_dir.iterdir())
        except OSError as exc:
            raise WarehouseW3WheelError(
                "cannot inspect wheel output directory"
            ) from exc
        if len(children) != 1:
            raise WarehouseW3WheelError("wheel build produced a non-exact output set")
        wheel_path = children[0]
        wheel_sha, wheel_identity, member_inventory, native_path = (
            _stable_wheel_inspection(
                wheel_path,
                forbidden_paths=(
                    work_root,
                    archives[0].path,
                    archives[1].path,
                    source_root,
                ),
                required_modules=required_modules,
            )
        )
        wheel_by_path = {item.path: item for item in member_inventory}
        if any(
            wheel_by_path[path].sha256 != source_members[path].sha256
            or wheel_by_path[path].size_bytes != source_members[path].size_bytes
            for path in required_payloads
        ):
            raise WarehouseW3WheelError(
                "wheel Python/template bytes differ from Git archive"
            )
        build_argv.append(argv)
        wheel_paths.append(wheel_path)
        wheel_sha256.append(wheel_sha)
        wheel_identities.append(wheel_identity)
        wheel_inventories.append(member_inventory)
        native_paths.append(native_path)
    if (
        wheel_paths[0].name != wheel_paths[1].name
        or wheel_identities[0].size_bytes != wheel_identities[1].size_bytes
        or wheel_sha256[0] != wheel_sha256[1]
        or not _files_equal(wheel_paths[0], wheel_paths[1])
    ):
        raise WarehouseW3WheelError("offline wheel bytes are not identical")
    if (
        wheel_inventories[0] != wheel_inventories[1]
        or native_paths[0] != native_paths[1]
    ):
        raise WarehouseW3WheelError("offline wheel member inventories differ")
    final_inspections = tuple(
        _stable_wheel_inspection(
            path,
            forbidden_paths=(
                work_root,
                archives[0].path,
                archives[1].path,
                work_root / f"build-{index}" / "source",
            ),
            required_modules=required_modules,
            expected_identity=identity,
        )
        for index, (path, identity) in enumerate(
            zip(wheel_paths, wheel_identities, strict=True),
            1,
        )
    )
    if (
        final_inspections[0][0] != final_inspections[1][0]
        or final_inspections[0][2] != final_inspections[1][2]
        or final_inspections[0][3] != final_inspections[1][3]
        or final_inspections[0][0] != wheel_sha256[0]
        or final_inspections[0][2] != wheel_inventories[0]
    ):
        raise WarehouseW3WheelError("final reopened wheel evidence differs")
    for archive, expected_identity in zip(
        archives,
        (first_identity, second_identity),
        strict=True,
    ):
        actual_sha256, actual_identity = _hash_regular(archive.path, immutable=True)
        if actual_sha256 != archive.sha256 or _stat_identity(
            actual_identity
        ) != _stat_identity(expected_identity):
            raise WarehouseW3WheelError("Git archive changed during wheel build")
    receipt = OfflineDoubleWheelReceipt._from_verified_build(
        source_receipt_sha256=authority.source_receipt_sha256,
        source_commit=authority.source_commit,
        source_tree=authority.source_tree,
        source_date_epoch=epoch,
        archive_sha256=(archives[0].sha256, archives[1].sha256),
        archive_identities=(
            WheelFileIdentity.from_stat_result(first_identity),
            WheelFileIdentity.from_stat_result(second_identity),
        ),
        archive_inventory_sha256=first_aggregate,
        required_module_members=required_modules,
        wheel_filename=wheel_paths[0].name,
        wheel_size_bytes=wheel_identities[0].size_bytes,
        wheel_sha256=wheel_sha256[0],
        wheel_identity=wheel_identities[0],
        wheel_identities=(wheel_identities[0], wheel_identities[1]),
        member_inventory=wheel_inventories[0],
        native_member_path=native_paths[0],
    )
    return _OfflineDoubleWheelBuildEvidence(
        repo_root=repo_root,
        archives=archives,
        wheel_paths=(wheel_paths[0], wheel_paths[1]),
        wheel_identities=(wheel_identities[0], wheel_identities[1]),
        receipt=receipt,
        build_argv=(build_argv[0], build_argv[1]),
    )


def _build_offline_double_wheel_for_test(
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive],
    *,
    repo_root: Path,
    work_root: Path,
    runner: WheelCommandRunner,
    git_reader: LocalGitReader,
) -> _TestOfflineDoubleWheelArtifact:
    """Injected test-only build that can never mint production provenance."""

    evidence = _acquire_offline_double_wheel_build_evidence(
        archives,
        repo_root=repo_root,
        work_root=work_root,
        runner=runner,
        git_reader=git_reader,
    )
    return _TestOfflineDoubleWheelArtifact.from_evidence(evidence)


def _acquire_production_offline_double_wheel_build(
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive],
    *,
    repo_root: Path,
    work_root: Path,
) -> _ProductionOfflineDoubleWheelBuildEvidence:
    """Acquire production-only evidence through fixed final implementations."""

    runner = SubprocessWheelRunner()
    git_reader = SubprocessLocalGitReader()
    if (
        type(runner) is not SubprocessWheelRunner
        or type(git_reader) is not SubprocessLocalGitReader
    ):
        raise WarehouseW3WheelError("fixed production wheel acquisition differs")
    evidence = _acquire_offline_double_wheel_build_evidence(
        archives,
        repo_root=repo_root,
        work_root=work_root,
        runner=runner,
        git_reader=git_reader,
    )
    production = object.__new__(_ProductionOfflineDoubleWheelBuildEvidence)
    object.__setattr__(production, "evidence", evidence)
    return production


def build_offline_double_wheel(
    archives: tuple[ImmutableGitArchive, ImmutableGitArchive],
    *,
    repo_root: Path,
    work_root: Path,
) -> OfflineDoubleWheelArtifact:
    """Build through the fixed production bwrap and local-Git implementations."""

    production = _acquire_production_offline_double_wheel_build(
        archives,
        repo_root=repo_root,
        work_root=work_root,
    )
    return OfflineDoubleWheelArtifact._from_production_build(production)


__all__ = [
    "ACCEPTED_NATIVE_ELF_SHA256",
    "ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256",
    "BUILDER_ARGV_TEMPLATE",
    "BUILDER_PYTHON",
    "FIXED_REQUIRED_WHEEL_MEMBERS",
    "ImmutableGitArchive",
    "OfflineDoubleWheelArtifact",
    "OfflineDoubleWheelReceipt",
    "SubprocessWheelRunner",
    "W3_CLOSE_TEMPLATE_MEMBER",
    "W3_RUN_TEMPLATE_MEMBER",
    "W3_TOOL_MEMBER",
    "WarehouseW3WheelError",
    "WheelCommandRunner",
    "WheelMember",
    "build_offline_double_wheel",
    "reopen_offline_double_wheel_artifact",
    "verify_offline_double_wheel_artifact",
]
