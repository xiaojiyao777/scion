"""Public immutable values and facade for candidate snapshot closures.

The implementation is storage-agnostic: no campaign registry is written and
no production ownership path is switched by this module.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, fields
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping

from scion.core.models import PatchProposal, VerificationResult

SNAPSHOT_SCHEMA = "scion.candidate_snapshot.v1"
CLOSURE_SCHEMA = "scion.candidate_snapshot_closure.v1"
EXECUTION_MANIFEST_SCHEMA = "scion.candidate_execution_manifest.v1"
EDITABLE_MANIFEST_SCHEMA = "scion.editable_identity_manifest.v1"
VERIFICATION_IDENTITY_SCHEMA = "scion.verification_identity.v1"
ACTIVATION_IDENTITY_PATHS = frozenset({"registry.yaml"})
_SHA256_RE = re.compile(r"[0-9a-f]{64}")


class CandidateSnapshotError(RuntimeError):
    """Base class for fail-closed candidate snapshot errors."""


class CandidateSnapshotTamperError(CandidateSnapshotError):
    """The closure, its parent, or a materialized identity has drifted."""


class CandidateOriginKind(str, Enum):
    DIRECT_CODE_ATTEMPT = "direct_code_attempt"
    RECONCILE_TRANSITION = "reconcile_transition"
    FIXED_REPLAY = "fixed_replay"


class CandidateCodeParentKind(str, Enum):
    CHAMPION = "champion"
    CANDIDATE = "candidate"


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{label} must be a full SHA-256")
    return value


def _relative(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("identity path must be an exact string")
    text = value
    if not text or "\\" in text or "\x00" in text:
        raise ValueError("identity path is invalid")
    path = PurePosixPath(text)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("identity path must be a canonical relative path")
    if path.as_posix() != text:
        raise ValueError("identity path is not canonical")
    return text


@dataclass(frozen=True)
class CandidateCodeParent:
    kind: CandidateCodeParentKind
    candidate_id: str | None
    code_hash: str
    executable_snapshot_hash: str
    ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, CandidateCodeParentKind):
            raise ValueError("code parent kind must be typed")
        _sha(self.code_hash, "code parent code hash")
        _sha(self.executable_snapshot_hash, "code parent executable snapshot hash")
        if "#" in self.ref:
            raise ValueError("code parent ref cannot contain a fragment")
        _relative(self.ref)
        if self.kind is CandidateCodeParentKind.CHAMPION:
            if self.candidate_id is not None:
                raise ValueError("champion code parent cannot have a candidate ID")
        elif self.kind is CandidateCodeParentKind.CANDIDATE:
            _sha(self.candidate_id, "code parent candidate ID")
        else:  # pragma: no cover
            raise ValueError("unsupported candidate code parent kind")


@dataclass(frozen=True)
class ExecutionFile:
    file_path: str
    sha256: str
    role: str

    def __post_init__(self) -> None:
        if _relative(self.file_path) != self.file_path:
            raise ValueError("execution file path is not canonical")
        _sha(self.sha256, "execution file hash")
        if self.role not in {"code_identity", "activation"}:
            raise ValueError("execution file role is invalid")


@dataclass(frozen=True)
class ExecutionManifest:
    schema_version: str
    files: tuple[ExecutionFile, ...]
    code_hash: str
    executable_snapshot_hash: str

    def __post_init__(self) -> None:
        if self.schema_version != EXECUTION_MANIFEST_SCHEMA:
            raise ValueError("execution manifest schema is invalid")
        _sha(self.code_hash, "execution manifest code hash")
        _sha(self.executable_snapshot_hash, "execution manifest snapshot hash")
        paths = tuple(item.file_path for item in self.files)
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError("execution manifest paths must be unique and sorted")


@dataclass(frozen=True)
class CandidateDeltaEntry:
    file_path: str
    action: str
    base_sha256: str | None
    result_sha256: str | None
    content: bytes | None

    def __post_init__(self) -> None:
        _relative(self.file_path)
        if self.action not in {"create", "modify", "delete"}:
            raise ValueError("delta action is invalid")
        if self.action == "create":
            if self.base_sha256 is not None or self.content is None:
                raise ValueError("create delta identity is invalid")
        elif self.action == "modify":
            _sha(self.base_sha256, "modify base hash")
            if self.content is None:
                raise ValueError("modify delta requires content")
        else:
            _sha(self.base_sha256, "delete base hash")
            if self.result_sha256 is not None or self.content is not None:
                raise ValueError("delete delta must be a content-free tombstone")
        if self.action != "delete":
            _sha(self.result_sha256, "delta result hash")
            if hashlib.sha256(self.content or b"").hexdigest() != self.result_sha256:
                raise ValueError("delta content hash is invalid")


@dataclass(frozen=True)
class NormalizedPatchChange:
    file_path: str
    action: str
    code_sha256: str
    test_hint: str | None
    content_source: str

    def __post_init__(self) -> None:
        _relative(self.file_path)
        if self.action not in {"create", "modify", "delete"}:
            raise ValueError("patch action is invalid")
        if self.test_hint is not None and not isinstance(self.test_hint, str):
            raise ValueError("patch test hint must be string or null")
        _sha(self.code_sha256, "patch content hash")
        allowed = {
            f"delta:{self.file_path}",
            f"parent:{self.file_path}",
            f"tombstone:{self.file_path}",
        }
        if self.content_source not in allowed:
            raise ValueError("patch content source is invalid")


@dataclass(frozen=True)
class CandidateSnapshot:
    schema_version: str
    candidate_id: str
    campaign_id: str
    origin_kind: CandidateOriginKind
    origin_id: str
    branch_id: str
    lineage_id: str
    candidate_code_hash: str
    executable_snapshot_hash: str
    parent_execution_manifest_digest: str
    candidate_execution_manifest_digest: str
    code_parent: CandidateCodeParent
    base_champion_id: str
    base_champion_hash: str
    evidence_parent_hypothesis_id: str | None
    hypothesis_id: str
    mechanism_owner_id: str
    verified_touched_files: tuple[str, ...]
    proposal_patch_digest: str
    verification_identity_digest: str
    candidate_snapshot_ref: str
    proposal_patch_ref: str
    verification_result_ref: str

    def __post_init__(self) -> None:
        if self.schema_version != SNAPSHOT_SCHEMA:
            raise ValueError("candidate snapshot schema is invalid")
        required = (
            self.campaign_id,
            self.origin_id,
            self.branch_id,
            self.lineage_id,
            self.base_champion_id,
            self.hypothesis_id,
            self.mechanism_owner_id,
        )
        if any(
            not isinstance(value, str) or not value.strip() or value != value.strip()
            for value in required
        ):
            raise ValueError("candidate snapshot identity must be canonical strings")
        if not isinstance(self.origin_kind, CandidateOriginKind):
            raise ValueError("candidate snapshot origin kind must be typed")
        optional = self.evidence_parent_hypothesis_id
        if optional is not None and (
            not isinstance(optional, str)
            or not optional.strip()
            or optional != optional.strip()
        ):
            raise ValueError("optional candidate identity must be string or null")
        for value, label in (
            (self.candidate_id, "candidate ID"),
            (self.candidate_code_hash, "candidate code hash"),
            (self.executable_snapshot_hash, "candidate snapshot hash"),
            (self.parent_execution_manifest_digest, "parent manifest digest"),
            (self.candidate_execution_manifest_digest, "candidate manifest digest"),
            (self.base_champion_hash, "base champion hash"),
            (self.proposal_patch_digest, "proposal Patch digest"),
            (self.verification_identity_digest, "Verification identity digest"),
        ):
            _sha(value, label)
        if self.origin_kind is CandidateOriginKind.FIXED_REPLAY:
            raise ValueError("fixed replay candidate snapshots are reserved for D4")
        if self.verified_touched_files != tuple(
            sorted(set(self.verified_touched_files))
        ):
            raise ValueError("verified touched files must be unique and sorted")
        for path in self.verified_touched_files:
            _relative(path)
        ref = f"candidate_snapshots/{self.candidate_id}.json"
        if (
            self.candidate_snapshot_ref,
            self.proposal_patch_ref,
            self.verification_result_ref,
        ) != (ref, f"{ref}#/proposal_patch", f"{ref}#/verification_result"):
            raise ValueError("candidate snapshot refs are not canonical")


@dataclass(frozen=True)
class CandidateSnapshotClosure:
    schema_version: str
    snapshot: CandidateSnapshot
    parent_execution_manifest: ExecutionManifest
    candidate_execution_manifest: ExecutionManifest
    delta: tuple[CandidateDeltaEntry, ...]
    proposal_patch: tuple[NormalizedPatchChange, ...]
    repair_attribution_json: tuple[str, ...]
    verification_result_json: str

    def __post_init__(self) -> None:
        if self.schema_version != CLOSURE_SCHEMA:
            raise ValueError("candidate snapshot closure schema is invalid")
        paths = tuple(item.file_path for item in self.delta)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("delta paths must be unique and sorted")
        patch_paths = tuple(item.file_path for item in self.proposal_patch)
        if len(patch_paths) != len(set(patch_paths)):
            raise ValueError("proposal Patch paths must be unique")

    @property
    def verification_result(self) -> Mapping[str, Any]:
        return json.loads(self.verification_result_json)

    @property
    def repair_attribution(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(json.loads(value) for value in self.repair_attribution_json)


@dataclass(frozen=True)
class CandidateAncestorArtifact:
    candidate_id: str
    ref: str
    artifact_sha256: str
    artifact_bytes: bytes

    def __post_init__(self) -> None:
        _sha(self.candidate_id, "ancestor candidate ID")
        _relative(self.ref)
        if "#" in self.ref:
            raise ValueError("ancestor artifact ref cannot contain a fragment")
        _sha(self.artifact_sha256, "ancestor artifact hash")
        if type(self.artifact_bytes) is not bytes:
            raise ValueError("ancestor artifact bytes must be exact bytes")


CandidateAncestorResolver = Callable[[str, str], CandidateAncestorArtifact]


def _decode_pinned_ancestor(
    parent: CandidateCodeParent,
    resolver: CandidateAncestorResolver | None,
) -> CandidateSnapshotClosure:
    if resolver is None:
        raise CandidateSnapshotTamperError("candidate parent requires pinned resolver")
    artifact = resolver(parent.candidate_id or "", parent.ref)
    if type(artifact) is not CandidateAncestorArtifact:
        raise CandidateSnapshotTamperError("ancestor resolver result is invalid")
    if artifact.candidate_id != parent.candidate_id or artifact.ref != parent.ref:
        raise CandidateSnapshotTamperError("ancestor artifact identity mismatch")
    closure = decode_candidate_snapshot_closure(
        artifact.artifact_bytes, expected_sha256=artifact.artifact_sha256
    )
    if (
        closure.snapshot.candidate_id != parent.candidate_id
        or closure.snapshot.candidate_snapshot_ref != parent.ref
    ):
        raise CandidateSnapshotTamperError("ancestor decoded identity mismatch")
    return closure


@dataclass(frozen=True)
class CandidateSnapshotRequest:
    campaign_id: str
    origin_kind: CandidateOriginKind
    origin_id: str
    branch_id: str
    lineage_id: str
    parent_workspace: str
    candidate_workspace: str
    code_parent: CandidateCodeParent
    base_champion_id: str
    base_champion_hash: str
    evidence_parent_hypothesis_id: str | None
    hypothesis_id: str
    mechanism_owner_id: str
    patch: PatchProposal
    verification_result: VerificationResult

    def __post_init__(self) -> None:
        required = (
            self.campaign_id,
            self.origin_id,
            self.branch_id,
            self.lineage_id,
            self.parent_workspace,
            self.candidate_workspace,
            self.base_champion_id,
            self.hypothesis_id,
            self.mechanism_owner_id,
        )
        if any(
            not isinstance(value, str) or not value.strip() or value != value.strip()
            for value in required
        ):
            raise ValueError("candidate snapshot request strings must be canonical")
        if not isinstance(self.origin_kind, CandidateOriginKind):
            raise ValueError("candidate snapshot request origin must be typed")
        if type(self.code_parent) is not CandidateCodeParent:
            raise ValueError("candidate snapshot request code parent must be typed")
        _sha(self.base_champion_hash, "base champion hash")
        optional = self.evidence_parent_hypothesis_id
        if optional is not None and (
            not isinstance(optional, str)
            or not optional.strip()
            or optional != optional.strip()
        ):
            raise ValueError("request optional identity must be string or null")
        if (
            type(self.patch) is not PatchProposal
            or type(self.verification_result) is not VerificationResult
        ):
            raise ValueError("candidate snapshot request evidence must be typed")


def verification_identity_digest(value: Mapping[str, Any]) -> str:
    """Digest typed outcomes; exclude elapsed, detail, metadata, and paths."""

    payload = {
        "schema_version": VERIFICATION_IDENTITY_SCHEMA,
        "passed": value["passed"],
        "checks": [
            {
                "name": item["name"],
                "passed": item["passed"],
                "severity": item["severity"],
            }
            for item in value["checks"]
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _validate_verification_result_payload(value: Any) -> None:
    expected = {"passed", "failure_severity", "first_failure", "checks"}
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ValueError("Verification fields are invalid")
    if (
        value["passed"] is not True
        or value["failure_severity"] is not None
        or value["first_failure"] is not None
        or not isinstance(value["checks"], list)
    ):
        raise ValueError("Verification types are invalid")
    names: set[str] = set()
    check_fields = {"name", "passed", "severity", "detail", "elapsed_ms", "metadata"}
    for check in value["checks"]:
        if not isinstance(check, Mapping) or set(check) != check_fields:
            raise ValueError("Verification check fields are invalid")
        name, elapsed = check["name"], check["elapsed_ms"]
        token = (
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", name)
            if isinstance(name, str)
            else None
        )
        if (
            not isinstance(name, str)
            or token is None
            or name in names
            or check["passed"] is not True
            or check["severity"] not in {"light", "heavy"}
            or not isinstance(check["detail"], str)
            or isinstance(elapsed, bool)
            or not isinstance(elapsed, int)
            or elapsed < 0
            or not isinstance(check["metadata"], dict)
        ):
            raise ValueError("Verification check types are invalid")
        names.add(name)


def execution_manifest_digest(value: ExecutionManifest) -> str:
    """Frame the legacy tree hashes with canonical per-file identities."""

    canonical = json.dumps(
        execution_manifest_payload(value), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def execution_manifest_payload(value: ExecutionManifest) -> dict[str, Any]:
    return {
        "schema_version": value.schema_version,
        "files": [
            {"file_path": item.file_path, "sha256": item.sha256, "role": item.role}
            for item in value.files
        ],
        "code_hash": value.code_hash,
        "executable_snapshot_hash": value.executable_snapshot_hash,
    }


def _execution_manifest_from_json(value: Mapping[str, Any]) -> ExecutionManifest:
    expected = {"schema_version", "files", "code_hash", "executable_snapshot_hash"}
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("execution manifest fields are invalid")
    files = _json_array(value["files"], "execution files")
    for item in files:
        if not isinstance(item, dict) or set(item) != {"file_path", "sha256", "role"}:
            raise ValueError("execution file fields are invalid")
    return ExecutionManifest(
        value["schema_version"],
        tuple(
            ExecutionFile(item["file_path"], item["sha256"], item["role"])
            for item in files
        ),
        value["code_hash"],
        value["executable_snapshot_hash"],
    )


def _validate_delta_claims(value: CandidateSnapshotClosure) -> None:
    claimed = {item.file_path for item in value.proposal_patch}
    before = {
        item.file_path: item.role for item in value.parent_execution_manifest.files
    }
    after = {
        item.file_path: item.role for item in value.candidate_execution_manifest.files
    }
    for item in value.delta:
        if item.file_path in claimed:
            continue
        roles = {
            role
            for role in (before.get(item.file_path), after.get(item.file_path))
            if role is not None
        }
        if item.file_path not in ACTIVATION_IDENTITY_PATHS or roles != {"activation"}:
            raise CandidateSnapshotTamperError(
                f"unclaimed code identity delta: {item.file_path}"
            )


def _json_array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a JSON array")
    return value


def _json_object_fields(value: Any, expected: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{label} fields are invalid")


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, sort_keys=True, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValueError("structured value is not JSON-safe") from exc


def _verification_payload(value: VerificationResult) -> dict[str, Any]:
    return {
        "passed": value.passed,
        "failure_severity": value.failure_severity,
        "first_failure": value.first_failure,
        "checks": [
            {
                "name": item.name,
                "passed": item.passed,
                "severity": item.severity,
                "detail": item.detail,
                "elapsed_ms": item.elapsed_ms,
                "metadata": _json_safe(item.metadata),
            }
            for item in value.checks
        ],
    }


def _parent_identity_payload(value: CandidateCodeParent) -> dict[str, Any]:
    return {
        "kind": value.kind.value,
        "candidate_id": value.candidate_id,
        "code_hash": value.code_hash,
        "executable_snapshot_hash": value.executable_snapshot_hash,
    }


def execution_manifest_from_workspace(
    *,
    campaign_root: str | Path,
    workspace: str | Path,
    editable_identity_manifest: Mapping[str, Any],
) -> ExecutionManifest:
    from scion.core.candidate_snapshot_materialization import manifest_from_workspace

    return manifest_from_workspace(
        campaign_root=campaign_root,
        workspace=workspace,
        editable_identity_manifest=editable_identity_manifest,
    )


def _build_candidate_snapshot_closure(
    *,
    request: CandidateSnapshotRequest,
    campaign_root: str | Path,
    parent_editable_identity_manifest: Mapping[str, Any],
    candidate_editable_identity_manifest: Mapping[str, Any],
    ancestor_resolver: CandidateAncestorResolver | None = None,
) -> CandidateSnapshotClosure:
    from scion.core.candidate_snapshot_materialization import build_closure

    return build_closure(
        campaign_root=campaign_root,
        parent_editable_identity_manifest=parent_editable_identity_manifest,
        candidate_editable_identity_manifest=candidate_editable_identity_manifest,
        ancestor_resolver=ancestor_resolver,
        **{field.name: getattr(request, field.name) for field in fields(request)},
    )


def candidate_snapshot_identity_payload(snapshot: CandidateSnapshot) -> dict[str, Any]:
    from scion.core.candidate_snapshot_codec import identity_payload

    return identity_payload(snapshot)


def candidate_snapshot_closure_bytes(closure: CandidateSnapshotClosure) -> bytes:
    from scion.core.candidate_snapshot_codec import encode_closure

    return encode_closure(closure)


def decode_candidate_snapshot_closure(
    data: bytes,
    *,
    expected_sha256: str | None = None,
) -> CandidateSnapshotClosure:
    from scion.core.candidate_snapshot_codec import decode_closure

    return decode_closure(data, expected_sha256=expected_sha256)


def load_candidate_snapshot_closure(
    campaign_root: str | Path,
    ref: str,
    *,
    expected_sha256: str | None = None,
) -> CandidateSnapshotClosure:
    from scion.core.candidate_snapshot_codec import load_closure

    return load_closure(campaign_root, ref, expected_sha256=expected_sha256)


def validate_candidate_snapshot_closure(
    closure: CandidateSnapshotClosure,
    *,
    campaign_root: str | Path,
    ancestor_resolver: CandidateAncestorResolver | None = None,
) -> None:
    from scion.core.candidate_snapshot_materialization import validate_closure

    validate_closure(
        closure, campaign_root=campaign_root, ancestor_resolver=ancestor_resolver
    )


def materialize_candidate_snapshot_closure(
    closure: CandidateSnapshotClosure,
    *,
    campaign_root: str | Path,
    destination: str | Path,
    ancestor_resolver: CandidateAncestorResolver | None = None,
) -> Path:
    from scion.core.candidate_snapshot_materialization import materialize_closure

    return materialize_closure(
        closure,
        campaign_root=campaign_root,
        destination=destination,
        ancestor_resolver=ancestor_resolver,
    )
