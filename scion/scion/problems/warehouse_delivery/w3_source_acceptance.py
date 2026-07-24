"""Root-owned fixed-source acceptance for one Warehouse W3 source closure.

Candidate preparation is deliberately downstream of this authority.  The
root owner verifies a local, root-owned bare Git mirror without network
access, consumes exactly two independent zero-P0/zero-P1 review closures, and
publishes one immutable acceptance receipt.  Later non-root and root phases
only reopen that receipt; none may infer source acceptance from candidate
bytes.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
from dataclasses import dataclass
from typing import Mapping, Protocol

from .w3_installation import (
    ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
    GitBlobFact,
    GitBlobIdentity,
    GitSourceReceipt,
    GitSourceSnapshot,
)

SOURCE_ACCEPTANCE_ROOT = Path("/var/lib/scion/source-acceptances/w3")
W3_SOURCE_ACCEPTANCE_LOGICAL_PATH = "external/root-fixed-source-acceptance.v1.json"
W3_SOURCE_ACCEPTANCE_SEALED_PATH = (
    "sealed/external/root-fixed-source-acceptance.v1.json"
)
FIXED_GIT = "/usr/bin/git"

_REVIEW_SCHEMA = "scion.w3-fixed-source-review-closure.v1"
_GIT_VERIFICATION_SCHEMA = "scion.w3-root-git-verification.v2"
_ACCEPTANCE_SCHEMA = "scion.w3-root-fixed-source-acceptance.v1"
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_GIT_OID_RE = re.compile(r"[0-9a-f]{40}\Z")
_REF_RE = re.compile(r"refs/heads/[A-Za-z0-9][A-Za-z0-9._/-]{0,511}\Z")
_IDENTITY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}\Z")
_TIME_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
_REVIEW_SCOPES = frozenset({"root_installation", "launch_readiness"})
_READ_LIMIT = 32 * 1024 * 1024
_MAX_REPOSITORY_ENTRIES = 1_000_000
_FORBIDDEN_REPOSITORY_PATHS = frozenset(
    {
        "commondir",
        "gitdir",
        "info/grafts",
        "objects/info/alternates",
        "objects/info/http-alternates",
        "shallow",
    }
)


class WarehouseW3SourceAcceptanceError(RuntimeError):
    """The fixed-source authority is absent, mutable, or does not close."""


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
        raise WarehouseW3SourceAcceptanceError(
            "source acceptance is not canonical JSON data"
        ) from exc


def _decode(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw or len(raw) > _READ_LIMIT:
        raise TypeError(f"{label} must be bounded nonempty bytes")

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
        raise WarehouseW3SourceAcceptanceError(
            f"{label} is not canonical JSON"
        ) from exc
    if type(value) is not dict or _canonical_json(value) != raw:
        raise WarehouseW3SourceAcceptanceError(f"{label} bytes are not canonical")
    return value


def _fields(
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
        raise WarehouseW3SourceAcceptanceError(f"{label} fields differ")
    return value


def _sha256(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise WarehouseW3SourceAcceptanceError(f"{field} is not SHA-256")
    return value


def _git_oid(value: object, *, field: str) -> str:
    if type(value) is not str or _GIT_OID_RE.fullmatch(value) is None:
        raise WarehouseW3SourceAcceptanceError(f"{field} is not a Git OID")
    return value


def _identity(value: object, *, field: str) -> str:
    if type(value) is not str or _IDENTITY_RE.fullmatch(value) is None:
        raise WarehouseW3SourceAcceptanceError(f"{field} is not canonical")
    return value


def _timestamp(value: object, *, field: str) -> str:
    if type(value) is not str or _TIME_RE.fullmatch(value) is None:
        raise WarehouseW3SourceAcceptanceError(f"{field} is not canonical UTC")
    return value


def _false_controls(value: Mapping[str, object], *, label: str) -> None:
    if any(value.get(name) is not False for name in ("retry", "resume", "reuse")):
        raise WarehouseW3SourceAcceptanceError(
            f"{label} enables retry, resume, or reuse"
        )


def source_inventory_sha256(receipt: GitSourceReceipt) -> str:
    """Hash the complete ordered Git blob identity inventory."""

    if type(receipt) is not GitSourceReceipt:
        raise TypeError("receipt must be exact GitSourceReceipt")
    parsed = GitSourceReceipt.from_bytes(receipt.raw)
    if parsed != receipt:
        raise WarehouseW3SourceAcceptanceError("Git source receipt object differs")
    return hashlib.sha256(
        b"scion.w3-fixed-source-inventory.v1\0"
        + _canonical_json({"blobs": [item.to_mapping() for item in receipt.blobs]})
    ).hexdigest()


@dataclass(frozen=True, slots=True, init=False)
class FixedSourceReviewClosure:
    review_scope: str
    reviewer_identity: str
    task_identity: str
    source_commit: str
    source_tree: str
    plan_sha256: str
    source_inventory_sha256: str
    report_sha256: str
    p0_open: int
    p1_open: int
    completed_at_utc: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "FixedSourceReviewClosure":
        del cls
        raise TypeError("FixedSourceReviewClosure must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("FixedSourceReviewClosure is final")

    @classmethod
    def create(
        cls,
        *,
        review_scope: str,
        reviewer_identity: str,
        task_identity: str,
        source_commit: str,
        source_tree: str,
        source_inventory_sha256: str,
        report_sha256: str,
        p0_open: int,
        p1_open: int,
        completed_at_utc: str,
    ) -> "FixedSourceReviewClosure":
        return cls.from_bytes(
            _canonical_json(
                {
                    "schema": _REVIEW_SCHEMA,
                    "review_scope": review_scope,
                    "reviewer_identity": reviewer_identity,
                    "task_identity": task_identity,
                    "source_commit": source_commit,
                    "source_tree": source_tree,
                    "plan_sha256": ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
                    "source_inventory_sha256": source_inventory_sha256,
                    "report_sha256": report_sha256,
                    "p0_open": p0_open,
                    "p1_open": p1_open,
                    "completed_at_utc": completed_at_utc,
                    "retry": False,
                    "resume": False,
                    "reuse": False,
                }
            )
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> "FixedSourceReviewClosure":
        value = _fields(
            _decode(raw, label="fixed-source review closure"),
            frozenset(
                {
                    "schema",
                    "review_scope",
                    "reviewer_identity",
                    "task_identity",
                    "source_commit",
                    "source_tree",
                    "plan_sha256",
                    "source_inventory_sha256",
                    "report_sha256",
                    "p0_open",
                    "p1_open",
                    "completed_at_utc",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            label="fixed-source review closure",
        )
        _false_controls(value, label="fixed-source review closure")
        scope = value["review_scope"]
        p0_open = value["p0_open"]
        p1_open = value["p1_open"]
        if (
            value["schema"] != _REVIEW_SCHEMA
            or scope not in _REVIEW_SCOPES
            or value["plan_sha256"] != ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256
            or type(p0_open) is not int
            or type(p1_open) is not int
            or p0_open != 0
            or p1_open != 0
        ):
            raise WarehouseW3SourceAcceptanceError(
                "fixed-source review is not a zero-P0/zero-P1 closure"
            )
        instance = object.__new__(cls)
        for field, item in (
            ("review_scope", scope),
            (
                "reviewer_identity",
                _identity(value["reviewer_identity"], field="reviewer identity"),
            ),
            ("task_identity", _identity(value["task_identity"], field="task identity")),
            ("source_commit", _git_oid(value["source_commit"], field="source commit")),
            ("source_tree", _git_oid(value["source_tree"], field="source tree")),
            (
                "plan_sha256",
                _sha256(value["plan_sha256"], field="review plan sha256"),
            ),
            (
                "source_inventory_sha256",
                _sha256(
                    value["source_inventory_sha256"],
                    field="review source inventory sha256",
                ),
            ),
            (
                "report_sha256",
                _sha256(value["report_sha256"], field="review report sha256"),
            ),
            ("p0_open", 0),
            ("p1_open", 0),
            (
                "completed_at_utc",
                _timestamp(value["completed_at_utc"], field="review completion time"),
            ),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


@dataclass(frozen=True, slots=True, init=False)
class RootGitVerificationReceipt:
    trusted_git_root: str
    trusted_git_device: int
    trusted_git_inode: int
    trusted_git_content_sha256: str
    git_binary_sha256: str
    remote_name: str
    remote_ref: str
    source_receipt_sha256: str
    source_inventory_sha256: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "RootGitVerificationReceipt":
        del cls
        raise TypeError("RootGitVerificationReceipt must be parsed from exact bytes")

    @classmethod
    def create(
        cls,
        *,
        trusted_git_root: Path,
        trusted_git_device: int,
        trusted_git_inode: int,
        trusted_git_content_sha256: str,
        git_binary_sha256: str,
        remote_name: str,
        remote_ref: str,
        source: GitSourceSnapshot,
    ) -> "RootGitVerificationReceipt":
        return cls.from_bytes(
            _canonical_json(
                {
                    "schema": _GIT_VERIFICATION_SCHEMA,
                    "plan_sha256": ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
                    "trusted_git_root": str(trusted_git_root),
                    "trusted_git_device": trusted_git_device,
                    "trusted_git_inode": trusted_git_inode,
                    "trusted_git_content_sha256": trusted_git_content_sha256,
                    "git_binary_path": FIXED_GIT,
                    "git_binary_sha256": git_binary_sha256,
                    "remote_name": remote_name,
                    "remote_ref": remote_ref,
                    "source_receipt_sha256": source.receipt.raw_sha256,
                    "source_inventory_sha256": source_inventory_sha256(source.receipt),
                    "network_used": False,
                    "retry": False,
                    "resume": False,
                    "reuse": False,
                }
            )
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> "RootGitVerificationReceipt":
        value = _fields(
            _decode(raw, label="root Git verification receipt"),
            frozenset(
                {
                    "schema",
                    "plan_sha256",
                    "trusted_git_root",
                    "trusted_git_device",
                    "trusted_git_inode",
                    "trusted_git_content_sha256",
                    "git_binary_path",
                    "git_binary_sha256",
                    "remote_name",
                    "remote_ref",
                    "source_receipt_sha256",
                    "source_inventory_sha256",
                    "network_used",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            label="root Git verification receipt",
        )
        _false_controls(value, label="root Git verification receipt")
        root = (
            Path(value["trusted_git_root"])
            if type(value["trusted_git_root"]) is str
            else Path()
        )
        remote_ref = value["remote_ref"]
        if (
            value["schema"] != _GIT_VERIFICATION_SCHEMA
            or value["plan_sha256"] != ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256
            or value["git_binary_path"] != FIXED_GIT
            or value["network_used"] is not False
            or not root.is_absolute()
            or str(PurePosixPath(str(root))) != str(root)
            or type(remote_ref) is not str
            or _REF_RE.fullmatch(remote_ref) is None
        ):
            raise WarehouseW3SourceAcceptanceError(
                "root Git verification fixed authority differs"
            )
        instance = object.__new__(cls)
        for field, item in (
            ("trusted_git_root", str(root)),
            (
                "trusted_git_device",
                _nonnegative(value["trusted_git_device"], field="Git root device"),
            ),
            (
                "trusted_git_inode",
                _nonnegative(value["trusted_git_inode"], field="Git root inode"),
            ),
            (
                "trusted_git_content_sha256",
                _sha256(
                    value["trusted_git_content_sha256"],
                    field="Git repository content sha256",
                ),
            ),
            (
                "git_binary_sha256",
                _sha256(value["git_binary_sha256"], field="Git binary sha256"),
            ),
            ("remote_name", _identity(value["remote_name"], field="remote name")),
            ("remote_ref", remote_ref),
            (
                "source_receipt_sha256",
                _sha256(
                    value["source_receipt_sha256"],
                    field="root Git source receipt sha256",
                ),
            ),
            (
                "source_inventory_sha256",
                _sha256(
                    value["source_inventory_sha256"],
                    field="root Git inventory sha256",
                ),
            ),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


def _nonnegative(value: object, *, field: str) -> int:
    if type(value) is not int or value < 0:
        raise WarehouseW3SourceAcceptanceError(f"{field} is not nonnegative")
    return value


@dataclass(frozen=True, slots=True, init=False)
class RootFixedSourceAcceptanceReceipt:
    source_commit: str
    source_tree: str
    source_receipt: GitSourceReceipt
    source_receipt_sha256: str
    source_inventory_sha256: str
    root_git_verification: RootGitVerificationReceipt
    root_git_verification_sha256: str
    reviews: tuple[FixedSourceReviewClosure, ...]
    review_closure_sha256: tuple[str, ...]
    accepted_at_utc: str
    state: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "RootFixedSourceAcceptanceReceipt":
        del cls
        raise TypeError(
            "RootFixedSourceAcceptanceReceipt must be parsed from exact bytes"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("RootFixedSourceAcceptanceReceipt is final")

    @classmethod
    def create(
        cls,
        *,
        source: GitSourceSnapshot,
        root_git_verification: RootGitVerificationReceipt,
        reviews: tuple[FixedSourceReviewClosure, FixedSourceReviewClosure],
        accepted_at_utc: str,
    ) -> "RootFixedSourceAcceptanceReceipt":
        if type(source) is not GitSourceSnapshot:
            raise TypeError("source must be exact GitSourceSnapshot")
        if type(root_git_verification) is not RootGitVerificationReceipt:
            raise TypeError(
                "root_git_verification must be exact RootGitVerificationReceipt"
            )
        if (
            type(reviews) is not tuple
            or len(reviews) != 2
            or any(type(item) is not FixedSourceReviewClosure for item in reviews)
        ):
            raise TypeError("reviews must be exactly two fixed review closures")
        ordered = tuple(
            sorted(reviews, key=lambda item: item.review_scope.encode("utf-8"))
        )
        return cls.from_bytes(
            _canonical_json(
                {
                    "schema": _ACCEPTANCE_SCHEMA,
                    "plan_sha256": ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
                    "source_commit": source.receipt.source_commit,
                    "source_tree": source.receipt.source_tree,
                    "source_receipt": source.receipt.raw.decode("utf-8", "strict"),
                    "source_receipt_sha256": source.receipt.raw_sha256,
                    "source_inventory_sha256": source_inventory_sha256(source.receipt),
                    "root_git_verification": (
                        root_git_verification.raw.decode("utf-8", "strict")
                    ),
                    "root_git_verification_sha256": (root_git_verification.raw_sha256),
                    "reviews": [item.raw.decode("utf-8", "strict") for item in ordered],
                    "review_closure_sha256": [item.raw_sha256 for item in ordered],
                    "accepted_at_utc": accepted_at_utc,
                    "state": "FIXED_SOURCE_ACCEPTED",
                    "retry": False,
                    "resume": False,
                    "reuse": False,
                }
            )
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> "RootFixedSourceAcceptanceReceipt":
        value = _fields(
            _decode(raw, label="root fixed-source acceptance"),
            frozenset(
                {
                    "schema",
                    "plan_sha256",
                    "source_commit",
                    "source_tree",
                    "source_receipt",
                    "source_receipt_sha256",
                    "source_inventory_sha256",
                    "root_git_verification",
                    "root_git_verification_sha256",
                    "reviews",
                    "review_closure_sha256",
                    "accepted_at_utc",
                    "state",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            label="root fixed-source acceptance",
        )
        _false_controls(value, label="root fixed-source acceptance")

        def nested(name: str) -> bytes:
            item = value[name]
            if type(item) is not str:
                raise WarehouseW3SourceAcceptanceError(
                    f"root source acceptance {name} is not text"
                )
            return item.encode("utf-8", "strict")

        source = GitSourceReceipt.from_bytes(nested("source_receipt"))
        git_verification = RootGitVerificationReceipt.from_bytes(
            nested("root_git_verification")
        )
        raw_reviews = value["reviews"]
        raw_review_sha = value["review_closure_sha256"]
        if (
            type(raw_reviews) is not list
            or len(raw_reviews) != 2
            or any(type(item) is not str for item in raw_reviews)
            or type(raw_review_sha) is not list
            or len(raw_review_sha) != 2
        ):
            raise WarehouseW3SourceAcceptanceError(
                "root source acceptance review inventory differs"
            )
        reviews = tuple(
            FixedSourceReviewClosure.from_bytes(item.encode("utf-8", "strict"))
            for item in raw_reviews
        )
        review_sha = tuple(
            _sha256(item, field="review closure sha256") for item in raw_review_sha
        )
        commit = _git_oid(value["source_commit"], field="accepted source commit")
        tree = _git_oid(value["source_tree"], field="accepted source tree")
        inventory = source_inventory_sha256(source)
        reviewer_identities = {item.reviewer_identity for item in reviews}
        task_identities = {item.task_identity for item in reviews}
        if (
            value["schema"] != _ACCEPTANCE_SCHEMA
            or value["plan_sha256"] != ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256
            or value["state"] != "FIXED_SOURCE_ACCEPTED"
            or tuple(item.review_scope for item in reviews)
            != tuple(sorted(_REVIEW_SCOPES))
            or len(reviewer_identities) != 2
            or len(task_identities) != 2
            or any(
                item.source_commit != commit
                or item.source_tree != tree
                or item.plan_sha256 != ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256
                or item.source_inventory_sha256 != inventory
                for item in reviews
            )
            or source.source_commit != commit
            or source.source_tree != tree
            or value["source_receipt_sha256"] != source.raw_sha256
            or value["source_inventory_sha256"] != inventory
            or git_verification.source_receipt_sha256 != source.raw_sha256
            or git_verification.source_inventory_sha256 != inventory
            or value["root_git_verification_sha256"] != git_verification.raw_sha256
            or review_sha != tuple(item.raw_sha256 for item in reviews)
        ):
            raise WarehouseW3SourceAcceptanceError(
                "root fixed-source acceptance dependency binding differs"
            )
        instance = object.__new__(cls)
        for field, item in (
            ("source_commit", commit),
            ("source_tree", tree),
            ("source_receipt", source),
            ("source_receipt_sha256", source.raw_sha256),
            ("source_inventory_sha256", inventory),
            ("root_git_verification", git_verification),
            ("root_git_verification_sha256", git_verification.raw_sha256),
            ("reviews", reviews),
            ("review_closure_sha256", review_sha),
            (
                "accepted_at_utc",
                _timestamp(value["accepted_at_utc"], field="source accepted time"),
            ),
            ("state", "FIXED_SOURCE_ACCEPTED"),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


class RootGitRunner(Protocol):
    def run(self, argv: tuple[str, ...], *, git_root: Path) -> bytes: ...


@dataclass(frozen=True, slots=True)
class SubprocessRootGitRunner:
    """No-network fixed-binary runner for one root-owned bare mirror."""

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("SubprocessRootGitRunner is final")

    def run(self, argv: tuple[str, ...], *, git_root: Path) -> bytes:
        if not argv or argv[0] != FIXED_GIT:
            raise WarehouseW3SourceAcceptanceError("root Git argv differs")
        environment = {
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "HOME": "/nonexistent",
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/usr/bin:/bin",
        }
        try:
            completed = subprocess.run(
                argv,
                cwd=git_root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                shell=False,
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise WarehouseW3SourceAcceptanceError(
                "fixed root Git command could not run"
            ) from exc
        if completed.returncode != 0 or completed.stderr:
            raise WarehouseW3SourceAcceptanceError(
                "fixed root Git command did not return cleanly"
            )
        if len(completed.stdout) > _READ_LIMIT:
            raise WarehouseW3SourceAcceptanceError(
                "fixed root Git output exceeds its bound"
            )
        return bytes(completed.stdout)


def _hash_stable_regular(
    path: Path, *, expected_uid: int
) -> tuple[str, os.stat_result]:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as exc:
        raise WarehouseW3SourceAcceptanceError(
            f"cannot open trusted regular file: {path}"
        ) from exc
    digest = hashlib.sha256()
    try:
        before = os.fstat(descriptor)
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    named = os.stat(path, follow_symlinks=False)
    signature = lambda item: (
        item.st_dev,
        item.st_ino,
        item.st_mode,
        item.st_nlink,
        item.st_uid,
        item.st_gid,
        item.st_size,
        item.st_mtime_ns,
        item.st_ctime_ns,
    )
    if (
        signature(before) != signature(after)
        or signature(after) != signature(named)
        or not stat.S_ISREG(named.st_mode)
        or named.st_uid != expected_uid
        or named.st_gid != 0
        or named.st_nlink != 1
        or stat.S_IMODE(named.st_mode) != 0o755
    ):
        raise WarehouseW3SourceAcceptanceError(
            f"trusted regular file identity differs: {path}"
        )
    return digest.hexdigest(), named


def _open_root_owned_directory(path: Path, *, expected_uid: int) -> int:
    if not path.is_absolute() or str(PurePosixPath(str(path))) != str(path):
        raise WarehouseW3SourceAcceptanceError(
            "trusted Git root is not canonical absolute"
        )
    descriptor = os.open(
        "/",
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        for component in path.parts[1:]:
            named = os.stat(
                component,
                dir_fd=descriptor,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISDIR(named.st_mode)
                or named.st_uid != expected_uid
                or named.st_gid != 0
                or stat.S_IMODE(named.st_mode) & 0o022
            ):
                raise WarehouseW3SourceAcceptanceError(
                    "trusted Git parent-chain ownership or mode differs"
                )
            child = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=descriptor,
            )
            opened = os.fstat(child)
            signature = lambda item: (
                item.st_dev,
                item.st_ino,
                item.st_mode,
                item.st_uid,
                item.st_gid,
                item.st_nlink,
                item.st_size,
                item.st_mtime_ns,
                item.st_ctime_ns,
            )
            if signature(opened) != signature(named):
                os.close(child)
                raise WarehouseW3SourceAcceptanceError(
                    "trusted Git parent chain drifted"
                )
            os.close(descriptor)
            descriptor = child
        return descriptor
    except OSError as exc:
        os.close(descriptor)
        raise WarehouseW3SourceAcceptanceError(
            "trusted Git root cannot be opened"
        ) from exc
    except Exception:
        os.close(descriptor)
        raise


def _validate_root_owned_directory(path: Path, *, expected_uid: int) -> os.stat_result:
    descriptor = _open_root_owned_directory(path, expected_uid=expected_uid)
    try:
        return os.fstat(descriptor)
    finally:
        os.close(descriptor)


def _root_owned_repository_content(
    path: Path,
    *,
    expected_uid: int,
    expected_gid: int = 0,
) -> tuple[str, os.stat_result]:
    """Hash one pinned, root-authoritative bare-repository filesystem tree."""

    root = _open_root_owned_directory(path, expected_uid=expected_uid)
    digest = hashlib.sha256(b"scion.w3-root-owned-git-content.v1\0")
    entry_count = 0

    def record(value: Mapping[str, object]) -> None:
        digest.update(_canonical_json(value))

    def walk(directory: int, prefix: str) -> None:
        nonlocal entry_count
        try:
            names = os.listdir(directory)
        except OSError as exc:
            raise WarehouseW3SourceAcceptanceError(
                "trusted Git repository cannot be listed"
            ) from exc
        try:
            ordered = sorted(
                names,
                key=lambda item: item.encode("utf-8", "strict"),
            )
        except UnicodeError as exc:
            raise WarehouseW3SourceAcceptanceError(
                "trusted Git repository path is not UTF-8"
            ) from exc
        for name in ordered:
            if not name or name in {".", ".."} or "/" in name or "\x00" in name:
                raise WarehouseW3SourceAcceptanceError(
                    "trusted Git repository contains an unsafe path"
                )
            logical = f"{prefix}/{name}" if prefix else name
            entry_count += 1
            if entry_count > _MAX_REPOSITORY_ENTRIES:
                raise WarehouseW3SourceAcceptanceError(
                    "trusted Git repository entry bound exceeded"
                )
            if logical in _FORBIDDEN_REPOSITORY_PATHS or (
                logical.startswith("objects/pack/") and logical.endswith(".promisor")
            ):
                raise WarehouseW3SourceAcceptanceError(
                    "trusted Git repository contains external object authority"
                )
            try:
                named = os.stat(
                    name,
                    dir_fd=directory,
                    follow_symlinks=False,
                )
            except OSError as exc:
                raise WarehouseW3SourceAcceptanceError(
                    "trusted Git repository entry cannot be stated"
                ) from exc
            if not (stat.S_ISDIR(named.st_mode) or stat.S_ISREG(named.st_mode)):
                raise WarehouseW3SourceAcceptanceError(
                    "trusted Git repository contains non-regular authority"
                )
            if (
                named.st_uid != expected_uid
                or named.st_gid != expected_gid
                or stat.S_IMODE(named.st_mode) & 0o022
            ):
                raise WarehouseW3SourceAcceptanceError(
                    "trusted Git repository content authority differs"
                )
            if stat.S_ISDIR(named.st_mode):
                try:
                    child = os.open(
                        name,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                        dir_fd=directory,
                    )
                except OSError as exc:
                    raise WarehouseW3SourceAcceptanceError(
                        "trusted Git repository directory cannot be pinned"
                    ) from exc
                try:
                    opened = os.fstat(child)
                    if _stat_signature(opened) != _stat_signature(named):
                        raise WarehouseW3SourceAcceptanceError(
                            "trusted Git repository directory drifted"
                        )
                    record(
                        {
                            "path": logical,
                            "kind": "directory",
                            "device": opened.st_dev,
                            "inode": opened.st_ino,
                            "mode": opened.st_mode,
                            "uid": opened.st_uid,
                            "gid": opened.st_gid,
                            "nlink": opened.st_nlink,
                            "size": opened.st_size,
                            "mtime_ns": opened.st_mtime_ns,
                            "ctime_ns": opened.st_ctime_ns,
                        }
                    )
                    walk(child, logical)
                    reopened = os.stat(
                        name,
                        dir_fd=directory,
                        follow_symlinks=False,
                    )
                    if _stat_signature(os.fstat(child)) != _stat_signature(
                        opened
                    ) or _stat_signature(reopened) != _stat_signature(opened):
                        raise WarehouseW3SourceAcceptanceError(
                            "trusted Git repository directory changed"
                        )
                finally:
                    os.close(child)
                continue
            if named.st_nlink != 1:
                raise WarehouseW3SourceAcceptanceError(
                    "trusted Git repository contains non-regular authority"
                )
            try:
                descriptor = os.open(
                    name,
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=directory,
                )
            except OSError as exc:
                raise WarehouseW3SourceAcceptanceError(
                    "trusted Git repository file cannot be pinned"
                ) from exc
            file_digest = hashlib.sha256()
            size = 0
            try:
                opened = os.fstat(descriptor)
                if _stat_signature(opened) != _stat_signature(named):
                    raise WarehouseW3SourceAcceptanceError(
                        "trusted Git repository file drifted"
                    )
                while True:
                    chunk = os.read(descriptor, 1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    file_digest.update(chunk)
                after = os.fstat(descriptor)
                reopened = os.stat(
                    name,
                    dir_fd=directory,
                    follow_symlinks=False,
                )
                if (
                    size != opened.st_size
                    or _stat_signature(after) != _stat_signature(opened)
                    or _stat_signature(reopened) != _stat_signature(opened)
                ):
                    raise WarehouseW3SourceAcceptanceError(
                        "trusted Git repository file changed"
                    )
                record(
                    {
                        "path": logical,
                        "kind": "regular",
                        "device": opened.st_dev,
                        "inode": opened.st_ino,
                        "mode": opened.st_mode,
                        "uid": opened.st_uid,
                        "gid": opened.st_gid,
                        "nlink": opened.st_nlink,
                        "size": size,
                        "mtime_ns": opened.st_mtime_ns,
                        "ctime_ns": opened.st_ctime_ns,
                        "sha256": file_digest.hexdigest(),
                    }
                )
            finally:
                os.close(descriptor)

    try:
        root_before = os.fstat(root)
        if (
            not stat.S_ISDIR(root_before.st_mode)
            or root_before.st_uid != expected_uid
            or root_before.st_gid != expected_gid
            or stat.S_IMODE(root_before.st_mode) & 0o022
        ):
            raise WarehouseW3SourceAcceptanceError(
                "trusted Git repository root authority differs"
            )
        record(
            {
                "path": ".",
                "kind": "directory",
                "device": root_before.st_dev,
                "inode": root_before.st_ino,
                "mode": root_before.st_mode,
                "uid": root_before.st_uid,
                "gid": root_before.st_gid,
                "nlink": root_before.st_nlink,
                "size": root_before.st_size,
                "mtime_ns": root_before.st_mtime_ns,
                "ctime_ns": root_before.st_ctime_ns,
            }
        )
        walk(root, "")
        root_after = os.fstat(root)
        if _stat_signature(root_after) != _stat_signature(root_before):
            raise WarehouseW3SourceAcceptanceError(
                "trusted Git repository root changed"
            )
        return digest.hexdigest(), root_after
    finally:
        os.close(root)


def _one_line(raw: bytes, *, label: str) -> str:
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise WarehouseW3SourceAcceptanceError(f"{label} is not one line")
    try:
        value = raw[:-1].decode("utf-8", "strict")
    except UnicodeError as exc:
        raise WarehouseW3SourceAcceptanceError(f"{label} is not UTF-8") from exc
    if not value:
        raise WarehouseW3SourceAcceptanceError(f"{label} is empty")
    return value


def _reject_external_git_configuration(raw: bytes) -> None:
    if not raw or not raw.endswith(b"\0"):
        raise WarehouseW3SourceAcceptanceError(
            "trusted Git local configuration is absent or malformed"
        )
    for encoded in raw[:-1].split(b"\0"):
        try:
            key_raw, _value = encoded.split(b"\n", 1)
            key = key_raw.decode("ascii", "strict").lower()
        except (ValueError, UnicodeError) as exc:
            raise WarehouseW3SourceAcceptanceError(
                "trusted Git local configuration is malformed"
            ) from exc
        if (
            key
            in {
                "core.alternaterefscommand",
                "core.hookspath",
                "core.worktree",
                "extensions.partialclone",
                "extensions.worktreeconfig",
                "include.path",
            }
            or key.startswith("includeif.")
            or (key.startswith("remote.") and key.endswith(".promisor"))
        ):
            raise WarehouseW3SourceAcceptanceError(
                "trusted Git configuration delegates external authority"
            )


@dataclass(frozen=True, slots=True)
class RootOwnedGitSourceVerifier:
    runner: RootGitRunner
    expected_uid: int = 0

    def __post_init__(self) -> None:
        if not callable(getattr(self.runner, "run", None)):
            raise TypeError("root Git runner lacks run")
        _nonnegative(self.expected_uid, field="expected Git owner uid")

    def verify(
        self,
        trusted_git_root: Path,
        *,
        source_commit: str,
        remote_name: str,
        remote_ref: str,
    ) -> tuple[GitSourceSnapshot, RootGitVerificationReceipt]:
        repository_content_sha256, root_identity = _root_owned_repository_content(
            trusted_git_root,
            expected_uid=self.expected_uid,
        )
        git_parent_identity = _validate_root_owned_directory(
            Path(FIXED_GIT).parent,
            expected_uid=0,
        )
        git_sha256, git_identity = _hash_stable_regular(
            Path(FIXED_GIT),
            expected_uid=0,
        )
        commit = _git_oid(source_commit, field="source commit")
        if _REF_RE.fullmatch(remote_ref) is None:
            raise WarehouseW3SourceAcceptanceError("remote ref is not full branch ref")
        remote = _identity(remote_name, field="remote name")
        run = self.runner.run
        prefix = (FIXED_GIT, f"--git-dir={trusted_git_root}")
        if (
            _one_line(
                run(
                    (*prefix, "rev-parse", "--is-bare-repository"),
                    git_root=trusted_git_root,
                ),
                label="trusted Git bare state",
            )
            != "true"
            or _one_line(
                run(
                    (*prefix, "rev-parse", "--is-shallow-repository"),
                    git_root=trusted_git_root,
                ),
                label="trusted Git shallow state",
            )
            != "false"
        ):
            raise WarehouseW3SourceAcceptanceError(
                "trusted Git repository is not one complete bare mirror"
            )
        _reject_external_git_configuration(
            run(
                (*prefix, "config", "--local", "--null", "--list"),
                git_root=trusted_git_root,
            )
        )
        if run(
            (*prefix, "for-each-ref", "--format=%(refname)", "refs/replace"),
            git_root=trusted_git_root,
        ):
            raise WarehouseW3SourceAcceptanceError(
                "trusted Git repository contains replacement refs"
            )
        ref_commit = _git_oid(
            _one_line(
                run(
                    (*prefix, "rev-parse", "--verify", f"{remote_ref}^{{commit}}"),
                    git_root=trusted_git_root,
                ),
                label="trusted Git ref",
            ),
            field="trusted Git ref",
        )
        resolved = _git_oid(
            _one_line(
                run(
                    (*prefix, "rev-parse", "--verify", f"{commit}^{{commit}}"),
                    git_root=trusted_git_root,
                ),
                label="trusted Git commit",
            ),
            field="trusted Git commit",
        )
        tree = _git_oid(
            _one_line(
                run(
                    (*prefix, "rev-parse", "--verify", f"{commit}^{{tree}}"),
                    git_root=trusted_git_root,
                ),
                label="trusted Git tree",
            ),
            field="trusted Git tree",
        )
        if ref_commit != commit or resolved != commit:
            raise WarehouseW3SourceAcceptanceError(
                "trusted Git full ref differs from reviewed commit"
            )
        inventory_raw = run(
            (
                *prefix,
                "ls-tree",
                "-rz",
                "--full-tree",
                commit,
                "--",
                "pyproject.toml",
                "scion",
            ),
            git_root=trusted_git_root,
        )
        if not inventory_raw or not inventory_raw.endswith(b"\0"):
            raise WarehouseW3SourceAcceptanceError(
                "trusted Git source inventory is absent"
            )
        identities: list[GitBlobIdentity] = []
        facts: list[GitBlobFact] = []
        for encoded in inventory_raw[:-1].split(b"\0"):
            try:
                header, path_raw = encoded.split(b"\t", 1)
                mode_raw, kind_raw, oid_raw = header.split(b" ", 2)
                mode = mode_raw.decode("ascii", "strict")
                kind = kind_raw.decode("ascii", "strict")
                oid = oid_raw.decode("ascii", "strict")
                logical_path = path_raw.decode("utf-8", "strict")
            except (ValueError, UnicodeError) as exc:
                raise WarehouseW3SourceAcceptanceError(
                    "trusted Git inventory entry is malformed"
                ) from exc
            pure = PurePosixPath(logical_path)
            if (
                logical_path.startswith("scion/tests/")
                or kind != "blob"
                or mode not in {"100644", "100755"}
                or pure.is_absolute()
                or pure.as_posix() != logical_path
                or any(part in {"", ".", ".."} for part in pure.parts)
            ):
                if logical_path.startswith("scion/tests/"):
                    continue
                raise WarehouseW3SourceAcceptanceError(
                    "trusted Git inventory contains a non-regular entry"
                )
            blob_oid = _git_oid(oid, field="trusted Git blob OID")
            raw = run(
                (*prefix, "cat-file", "blob", blob_oid),
                git_root=trusted_git_root,
            )
            identity = GitBlobIdentity(
                logical_path=logical_path,
                mode=mode,
                blob_oid=blob_oid,
                sha256=hashlib.sha256(raw).hexdigest(),
                size_bytes=len(raw),
            )
            identities.append(identity)
            facts.append(
                GitBlobFact(
                    source_commit=commit,
                    source_tree=tree,
                    identity=identity,
                    raw=raw,
                )
            )
        ordered = tuple(
            sorted(
                zip(identities, facts, strict=True),
                key=lambda item: item[0].logical_path.encode("utf-8"),
            )
        )
        if (
            not ordered
            or len({item[0].logical_path for item in ordered}) != len(ordered)
            or "pyproject.toml" not in {item[0].logical_path for item in ordered}
            or "scion/tools/scion_w3_install.py"
            not in {item[0].logical_path for item in ordered}
        ):
            raise WarehouseW3SourceAcceptanceError(
                "trusted Git fixed source closure differs"
            )
        remote_url = _one_line(
            run(
                (*prefix, "config", "--get", f"remote.{remote}.url"),
                git_root=trusted_git_root,
            ),
            label="trusted Git remote URL",
        )
        receipt = GitSourceReceipt.create(
            source_commit=commit,
            source_tree=tree,
            remote_name=remote,
            remote_url=remote_url,
            remote_ref=remote_ref,
            remote_tracking_ref=(
                f"refs/remotes/{remote}/" f"{remote_ref.removeprefix('refs/heads/')}"
            ),
            blobs=tuple(item[0] for item in ordered),
        )
        snapshot = GitSourceSnapshot(
            receipt=receipt,
            blobs=tuple(item[1] for item in ordered),
        )
        repository_content_sha256_after, after = _root_owned_repository_content(
            trusted_git_root,
            expected_uid=self.expected_uid,
        )
        git_sha256_after, git_identity_after = _hash_stable_regular(
            Path(FIXED_GIT),
            expected_uid=0,
        )
        git_parent_after = _validate_root_owned_directory(
            Path(FIXED_GIT).parent,
            expected_uid=0,
        )
        if repository_content_sha256 != repository_content_sha256_after or (
            root_identity.st_dev,
            root_identity.st_ino,
            root_identity.st_mode,
            root_identity.st_uid,
            root_identity.st_gid,
            root_identity.st_mtime_ns,
            root_identity.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_uid,
            after.st_gid,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise WarehouseW3SourceAcceptanceError(
                "trusted Git repository changed during verification"
            )
        if (
            git_sha256_after != git_sha256
            or _stat_signature(git_identity_after) != _stat_signature(git_identity)
            or _stat_signature(git_parent_after) != _stat_signature(git_parent_identity)
        ):
            raise WarehouseW3SourceAcceptanceError(
                "fixed Git binary authority changed during verification"
            )
        verification = RootGitVerificationReceipt.create(
            trusted_git_root=trusted_git_root,
            trusted_git_device=after.st_dev,
            trusted_git_inode=after.st_ino,
            trusted_git_content_sha256=repository_content_sha256,
            git_binary_sha256=git_sha256,
            remote_name=remote,
            remote_ref=remote_ref,
            source=snapshot,
        )
        return snapshot, verification


def source_acceptance_path(source_commit: str) -> Path:
    return (
        SOURCE_ACCEPTANCE_ROOT
        / f"{_git_oid(source_commit, field='source commit')}.v1.json"
    )


def _stat_signature(value: os.stat_result) -> tuple[int, ...]:
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


def _directory_authority_signature(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_gid,
        value.st_nlink,
    )


def _open_root_owned_parent(
    path: Path,
    *,
    expected_uid: int,
) -> tuple[int, tuple[int, ...]]:
    if not path.is_absolute() or path == Path("/"):
        raise WarehouseW3SourceAcceptanceError("source acceptance parent path differs")
    descriptor = os.open(
        "/",
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        for component in path.parts[1:]:
            named = os.stat(
                component,
                dir_fd=descriptor,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISDIR(named.st_mode)
                or named.st_uid != expected_uid
                or named.st_gid != 0
                or stat.S_IMODE(named.st_mode) & 0o022
            ):
                raise WarehouseW3SourceAcceptanceError(
                    "source acceptance parent chain authority differs"
                )
            child = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=descriptor,
            )
            opened = os.fstat(child)
            if _stat_signature(opened) != _stat_signature(named):
                os.close(child)
                raise WarehouseW3SourceAcceptanceError(
                    "source acceptance parent chain drifted"
                )
            os.close(descriptor)
            descriptor = child
        identity = os.fstat(descriptor)
        return descriptor, _stat_signature(identity)
    except Exception:
        os.close(descriptor)
        raise


def _read_stable_acceptance(
    path: Path,
    *,
    expected_uid: int,
) -> tuple[bytes, os.stat_result]:
    parent, parent_identity = _open_root_owned_parent(
        path.parent,
        expected_uid=expected_uid,
    )
    try:
        descriptor = os.open(
            path.name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent,
        )
    except OSError as exc:
        os.close(parent)
        raise WarehouseW3SourceAcceptanceError(
            "cannot open root fixed-source acceptance"
        ) from exc
    chunks: list[bytes] = []
    total = 0
    try:
        before = os.fstat(descriptor)
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, _READ_LIMIT + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > _READ_LIMIT:
                raise WarehouseW3SourceAcceptanceError(
                    "root fixed-source acceptance exceeds its bound"
                )
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        named = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        if (
            _stat_signature(before) != _stat_signature(after)
            or _stat_signature(after) != _stat_signature(named)
            or _stat_signature(os.fstat(parent)) != parent_identity
            or not stat.S_ISREG(named.st_mode)
            or stat.S_IMODE(named.st_mode) != 0o444
            or named.st_uid != expected_uid
            or named.st_gid != 0
            or named.st_nlink != 1
        ):
            raise WarehouseW3SourceAcceptanceError(
                "root fixed-source acceptance identity differs"
            )
        return b"".join(chunks), named
    finally:
        os.close(parent)


@dataclass(slots=True)
class RootFixedSourceAcceptanceAuthority:
    """Retained immutable authority over one root-owned acceptance file."""

    path: Path
    receipt: RootFixedSourceAcceptanceReceipt
    identity: os.stat_result
    expected_uid: int = 0

    @classmethod
    def open(
        cls,
        path: Path,
        *,
        expected_uid: int = 0,
    ) -> "RootFixedSourceAcceptanceAuthority":
        if not isinstance(path, Path) or not path.is_absolute():
            raise TypeError("source acceptance path must be absolute Path")
        raw, identity = _read_stable_acceptance(path, expected_uid=expected_uid)
        receipt = RootFixedSourceAcceptanceReceipt.from_bytes(raw)
        if path.name != f"{receipt.source_commit}.v1.json":
            raise WarehouseW3SourceAcceptanceError(
                "root fixed-source acceptance path differs"
            )
        return cls(
            path=path,
            receipt=receipt,
            identity=identity,
            expected_uid=expected_uid,
        )

    def revalidate(self) -> RootFixedSourceAcceptanceReceipt:
        raw, identity = _read_stable_acceptance(
            self.path,
            expected_uid=self.expected_uid,
        )
        signature = lambda item: (
            item.st_dev,
            item.st_ino,
            item.st_mode,
            item.st_nlink,
            item.st_uid,
            item.st_gid,
            item.st_size,
            item.st_mtime_ns,
            item.st_ctime_ns,
        )
        receipt = RootFixedSourceAcceptanceReceipt.from_bytes(raw)
        if signature(identity) != signature(self.identity) or receipt != self.receipt:
            raise WarehouseW3SourceAcceptanceError(
                "root fixed-source acceptance drifted"
            )
        return receipt

    def __enter__(self) -> "RootFixedSourceAcceptanceAuthority":
        self.revalidate()
        return self

    def __exit__(self, *_args: object) -> None:
        self.revalidate()


def _publish_acceptance(
    path: Path,
    raw: bytes,
    *,
    expected_uid: int,
) -> None:
    parent, _parent_signature = _open_root_owned_parent(
        path.parent,
        expected_uid=expected_uid,
    )
    parent_identity = os.fstat(parent)
    if (
        not stat.S_ISDIR(parent_identity.st_mode)
        or parent_identity.st_uid != expected_uid
        or parent_identity.st_gid != 0
        or stat.S_IMODE(parent_identity.st_mode) != 0o755
    ):
        raise WarehouseW3SourceAcceptanceError(
            "source acceptance parent authority differs"
        )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        descriptor = os.open(path.name, flags, 0o444, dir_fd=parent)
    except OSError as exc:
        os.close(parent)
        raise WarehouseW3SourceAcceptanceError(
            "source acceptance exists or cannot be published"
        ) from exc
    try:
        os.fchmod(descriptor, 0o444)
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short source acceptance write")
            view = view[written:]
        os.fsync(descriptor)
    except OSError as exc:
        raise WarehouseW3SourceAcceptanceError(
            "source acceptance publication is a partial hold"
        ) from exc
    finally:
        os.close(descriptor)
    try:
        if _directory_authority_signature(
            os.fstat(parent)
        ) != _directory_authority_signature(parent_identity):
            raise WarehouseW3SourceAcceptanceError("source acceptance parent drifted")
        os.fsync(parent)
    finally:
        os.close(parent)


def accept_fixed_source(
    trusted_git_root: Path,
    *,
    source_commit: str,
    remote_name: str,
    remote_ref: str,
    review_one_raw: bytes,
    review_two_raw: bytes,
    accepted_at_utc: str,
) -> RootFixedSourceAcceptanceReceipt:
    """Root-only production owner for one fixed-source acceptance."""

    if os.geteuid() != 0:
        raise PermissionError("fixed-source acceptance requires effective UID zero")
    reviews = (
        FixedSourceReviewClosure.from_bytes(review_one_raw),
        FixedSourceReviewClosure.from_bytes(review_two_raw),
    )
    verifier = RootOwnedGitSourceVerifier(
        runner=SubprocessRootGitRunner(),
        expected_uid=0,
    )
    source, git_verification = verifier.verify(
        trusted_git_root,
        source_commit=source_commit,
        remote_name=remote_name,
        remote_ref=remote_ref,
    )
    receipt = RootFixedSourceAcceptanceReceipt.create(
        source=source,
        root_git_verification=git_verification,
        reviews=reviews,
        accepted_at_utc=accepted_at_utc,
    )
    path = source_acceptance_path(receipt.source_commit)
    _publish_acceptance(path, receipt.raw, expected_uid=0)
    with RootFixedSourceAcceptanceAuthority.open(path) as authority:
        if authority.receipt != receipt:
            raise WarehouseW3SourceAcceptanceError(
                "published source acceptance differs"
            )
    return receipt


__all__ = [
    "FIXED_GIT",
    "FixedSourceReviewClosure",
    "RootFixedSourceAcceptanceAuthority",
    "RootFixedSourceAcceptanceReceipt",
    "RootGitVerificationReceipt",
    "RootOwnedGitSourceVerifier",
    "SOURCE_ACCEPTANCE_ROOT",
    "SubprocessRootGitRunner",
    "WarehouseW3SourceAcceptanceError",
    "W3_SOURCE_ACCEPTANCE_LOGICAL_PATH",
    "W3_SOURCE_ACCEPTANCE_SEALED_PATH",
    "accept_fixed_source",
    "source_acceptance_path",
    "source_inventory_sha256",
]
