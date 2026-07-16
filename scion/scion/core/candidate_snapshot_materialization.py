"""Workspace identity, delta building, and exact materialization."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

from scion.core import candidate_snapshot as cs
from scion.core.evidence_recording.replay_identity import stable_patch_digest
from scion.core.models import PatchProposal, VerificationResult, patch_file_changes


def build_closure(
    *,
    campaign_root: str | Path,
    parent_workspace: str | Path,
    candidate_workspace: str | Path,
    parent_editable_identity_manifest: Mapping[str, Any],
    candidate_editable_identity_manifest: Mapping[str, Any],
    campaign_id: str,
    origin_kind: cs.CandidateOriginKind | str,
    origin_id: str,
    branch_id: str,
    lineage_id: str,
    code_parent: cs.CandidateCodeParent,
    base_champion_id: str,
    base_champion_hash: str,
    evidence_parent_hypothesis_id: str | None,
    hypothesis_id: str,
    mechanism_owner_id: str,
    patch: PatchProposal,
    verification_result: VerificationResult,
    ancestor_resolver: cs.CandidateAncestorResolver | None = None,
) -> cs.CandidateSnapshotClosure:
    root = _root(campaign_root)
    parent_path = _workspace(root, parent_workspace, "parent workspace")
    candidate_path = _workspace(root, candidate_workspace, "candidate workspace")
    try:
        origin = cs.CandidateOriginKind(origin_kind)
    except ValueError as exc:
        raise ValueError("candidate origin kind is invalid") from exc
    if origin is cs.CandidateOriginKind.FIXED_REPLAY:
        raise ValueError("fixed replay candidate snapshots are reserved for D4")
    if not verification_result.passed:
        raise ValueError("candidate snapshot requires passed Verification")
    parent_manifest = _manifest(parent_path, parent_editable_identity_manifest)
    candidate_manifest = _manifest(candidate_path, candidate_editable_identity_manifest)
    if (
        parent_manifest.code_hash != code_parent.code_hash
        or parent_manifest.executable_snapshot_hash
        != code_parent.executable_snapshot_hash
    ):
        raise cs.CandidateSnapshotTamperError("code parent identity mismatch")
    champion_id = _text(base_champion_id, "base_champion_id")
    champion_hash = cs._sha(base_champion_hash, "base champion hash")
    _validate_build_parent(
        root,
        parent_path,
        code_parent,
        parent_manifest,
        champion_id,
        champion_hash,
        ancestor_resolver,
    )
    delta = _delta(parent_path, candidate_path, parent_manifest, candidate_manifest)
    if not delta:
        raise ValueError(
            "exact executable reuse must reference an existing candidate ID"
        )
    normalized_patch = _patch(
        patch, parent_path, candidate_path, parent_manifest, candidate_manifest, delta
    )
    patch_digest = stable_patch_digest(patch_file_changes(patch))
    verification_json = _json(cs._verification_payload(verification_result))
    verification_digest = cs.verification_identity_digest(json.loads(verification_json))
    if any(not isinstance(item, Mapping) for item in (patch.repair_attribution or ())):
        raise ValueError("repair attribution entries must be mappings")
    values = {
        "campaign_id": _text(campaign_id, "campaign_id"),
        "origin_id": _text(origin_id, "origin_id"),
        "branch_id": _text(branch_id, "branch_id"),
        "lineage_id": _text(lineage_id, "lineage_id"),
        "base_champion_id": champion_id,
        "hypothesis_id": _text(hypothesis_id, "hypothesis_id"),
        "mechanism_owner_id": _text(mechanism_owner_id, "mechanism_owner_id"),
    }
    provisional = {
        "schema_version": cs.SNAPSHOT_SCHEMA,
        "campaign_id": values["campaign_id"],
        "origin": {"kind": origin.value, "id": values["origin_id"]},
        "branch_id": values["branch_id"],
        "lineage_id": values["lineage_id"],
        "candidate_code_hash": candidate_manifest.code_hash,
        "executable_snapshot_hash": candidate_manifest.executable_snapshot_hash,
        "parent_execution_manifest_digest": cs.execution_manifest_digest(
            parent_manifest
        ),
        "candidate_execution_manifest_digest": cs.execution_manifest_digest(
            candidate_manifest
        ),
        "code_parent": cs._parent_identity_payload(code_parent),
        "champion_anchor": {"id": values["base_champion_id"], "hash": champion_hash},
        "evidence_parent_hypothesis_id": _optional(evidence_parent_hypothesis_id),
        "hypothesis_id": values["hypothesis_id"],
        "mechanism_owner_id": values["mechanism_owner_id"],
        "verified_touched_files": [item.file_path for item in delta],
        "proposal_patch_digest": patch_digest,
        "verification_identity_digest": verification_digest,
    }
    candidate_id = _digest_text(_json(provisional))
    ref = f"candidate_snapshots/{candidate_id}.json"
    snapshot = cs.CandidateSnapshot(
        schema_version=cs.SNAPSHOT_SCHEMA,
        candidate_id=candidate_id,
        campaign_id=values["campaign_id"],
        origin_kind=origin,
        origin_id=values["origin_id"],
        branch_id=values["branch_id"],
        lineage_id=values["lineage_id"],
        candidate_code_hash=candidate_manifest.code_hash,
        executable_snapshot_hash=candidate_manifest.executable_snapshot_hash,
        parent_execution_manifest_digest=provisional[
            "parent_execution_manifest_digest"
        ],
        candidate_execution_manifest_digest=provisional[
            "candidate_execution_manifest_digest"
        ],
        code_parent=code_parent,
        base_champion_id=values["base_champion_id"],
        base_champion_hash=provisional["champion_anchor"]["hash"],
        evidence_parent_hypothesis_id=provisional["evidence_parent_hypothesis_id"],
        hypothesis_id=values["hypothesis_id"],
        mechanism_owner_id=values["mechanism_owner_id"],
        verified_touched_files=tuple(item.file_path for item in delta),
        proposal_patch_digest=patch_digest,
        verification_identity_digest=verification_digest,
        candidate_snapshot_ref=ref,
        proposal_patch_ref=f"{ref}#/proposal_patch",
        verification_result_ref=f"{ref}#/verification_result",
    )
    closure = cs.CandidateSnapshotClosure(
        schema_version=cs.CLOSURE_SCHEMA,
        snapshot=snapshot,
        parent_execution_manifest=parent_manifest,
        candidate_execution_manifest=candidate_manifest,
        delta=delta,
        proposal_patch=normalized_patch,
        repair_attribution_json=tuple(
            _json(cs._json_safe(item)) for item in (patch.repair_attribution or ())
        ),
        verification_result_json=verification_json,
    )
    validate_internal(closure)
    return closure


def validate_closure(
    closure: cs.CandidateSnapshotClosure,
    *,
    campaign_root: str | Path,
    ancestor_resolver: cs.CandidateAncestorResolver | None = None,
) -> None:
    with tempfile.TemporaryDirectory(prefix="scion-candidate-snapshot-") as temp:
        _materialize(
            closure,
            _root(campaign_root),
            Path(temp) / "identity",
            set(),
            ancestor_resolver,
        )


def materialize_closure(
    closure: cs.CandidateSnapshotClosure,
    *,
    campaign_root: str | Path,
    destination: str | Path,
    ancestor_resolver: cs.CandidateAncestorResolver | None = None,
) -> Path:
    destination = Path(destination)
    if destination.exists() and (
        not destination.is_dir() or any(destination.iterdir())
    ):
        raise FileExistsError("candidate snapshot destination must be empty")
    destination.mkdir(parents=True, exist_ok=True)
    try:
        _materialize(
            closure, _root(campaign_root), destination, set(), ancestor_resolver
        )
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return destination


def manifest_from_workspace(
    *,
    campaign_root: str | Path,
    workspace: str | Path,
    editable_identity_manifest: Mapping[str, Any],
) -> cs.ExecutionManifest:
    root = _root(campaign_root)
    return _manifest(
        _workspace(root, workspace, "identity workspace"),
        editable_identity_manifest,
    )


def _manifest(workspace: Path, editable: Mapping[str, Any]) -> cs.ExecutionManifest:
    if editable.get("schema_version") != cs.EDITABLE_MANIFEST_SCHEMA:
        raise ValueError("editable identity manifest schema is invalid")
    raw_files = editable.get("files")
    if not isinstance(raw_files, list):
        raise ValueError("editable identity manifest files are invalid")
    declared: dict[str, str] = {}
    for item in raw_files:
        if not isinstance(item, Mapping):
            raise ValueError("editable identity manifest file is invalid")
        path = cs._relative(str(item.get("file_path") or ""))
        if path in declared:
            raise ValueError("editable identity manifest has duplicate paths")
        declared[path] = cs._sha(item.get("sha256"), "editable file hash")
    files: list[cs.ExecutionFile] = []
    for path in sorted(declared):
        digest = hashlib.sha256(_read(workspace, path)).hexdigest()
        if digest != declared[path]:
            raise cs.CandidateSnapshotTamperError(f"editable hash mismatch: {path}")
        files.append(cs.ExecutionFile(path, digest, "code_identity"))
    code_hash = _tree_hash(workspace, declared)
    if code_hash != editable.get("code_hash"):
        raise cs.CandidateSnapshotTamperError("editable code hash mismatch")
    if "registry.yaml" not in declared:
        registry = workspace / "registry.yaml"
        if registry.exists() or registry.is_symlink():
            data = _read(workspace, "registry.yaml")
            files.append(
                cs.ExecutionFile(
                    "registry.yaml", hashlib.sha256(data).hexdigest(), "activation"
                )
            )
    files.sort(key=lambda item: item.file_path)
    return cs.ExecutionManifest(
        cs.EXECUTION_MANIFEST_SCHEMA,
        tuple(files),
        code_hash,
        _tree_hash(workspace, (item.file_path for item in files)),
    )


def _delta(
    parent: Path,
    candidate: Path,
    before_manifest: cs.ExecutionManifest,
    after_manifest: cs.ExecutionManifest,
) -> tuple[cs.CandidateDeltaEntry, ...]:
    before = {item.file_path: item.sha256 for item in before_manifest.files}
    after = {item.file_path: item.sha256 for item in after_manifest.files}
    result = []
    for path in sorted(set(before) | set(after)):
        if before.get(path) == after.get(path):
            continue
        if path not in before:
            result.append(
                cs.CandidateDeltaEntry(
                    path, "create", None, after[path], _read(candidate, path)
                )
            )
        elif path not in after:
            result.append(
                cs.CandidateDeltaEntry(path, "delete", before[path], None, None)
            )
        else:
            result.append(
                cs.CandidateDeltaEntry(
                    path, "modify", before[path], after[path], _read(candidate, path)
                )
            )
    return tuple(result)


def _patch(
    patch: PatchProposal,
    parent: Path,
    candidate: Path,
    before_manifest: cs.ExecutionManifest,
    after_manifest: cs.ExecutionManifest,
    delta: tuple[cs.CandidateDeltaEntry, ...],
) -> tuple[cs.NormalizedPatchChange, ...]:
    before = {item.file_path for item in before_manifest.files}
    after = {item.file_path for item in after_manifest.files}
    delta_paths = {item.file_path for item in delta}
    result, seen = [], set()
    for change in patch_file_changes(patch):
        path, action = cs._relative(change.file_path), str(change.action)
        if path in seen:
            raise ValueError("Patch has duplicate file paths")
        seen.add(path)
        code = str(change.code_content or "").encode()
        if action == "create":
            valid = (
                path not in before and path in after and _read(candidate, path) == code
            )
            source = f"delta:{path}"
        elif action == "modify":
            valid = path in before and path in after and _read(candidate, path) == code
            source = f"delta:{path}" if path in delta_paths else f"parent:{path}"
        elif action == "delete":
            valid, source = path in before and path not in after, f"tombstone:{path}"
        else:
            raise ValueError("Patch action is invalid")
        if not valid:
            raise cs.CandidateSnapshotTamperError(f"Patch {action} identity mismatch")
        result.append(
            cs.NormalizedPatchChange(
                path,
                action,
                hashlib.sha256(code).hexdigest(),
                None if change.test_hint is None else str(change.test_hint),
                source,
            )
        )
    return tuple(result)


def _validate_build_parent(
    root: Path,
    workspace: Path,
    parent: cs.CandidateCodeParent,
    manifest: cs.ExecutionManifest,
    champion_id: str,
    champion_hash: str,
    ancestor_resolver: cs.CandidateAncestorResolver | None,
) -> None:
    if parent.kind is cs.CandidateCodeParentKind.CHAMPION:
        if _resolve(root, parent.ref, file=False) != workspace:
            raise cs.CandidateSnapshotTamperError("champion parent ref mismatch")
        if champion_hash != parent.executable_snapshot_hash:
            raise cs.CandidateSnapshotTamperError("champion parent anchor mismatch")
        return
    closure = cs._decode_pinned_ancestor(parent, ancestor_resolver)
    validate_closure(closure, campaign_root=root, ancestor_resolver=ancestor_resolver)
    if (
        closure.snapshot.candidate_id != parent.candidate_id
        or closure.candidate_execution_manifest != manifest
    ):
        raise cs.CandidateSnapshotTamperError("candidate parent identity mismatch")
    if (champion_id, champion_hash) != (
        closure.snapshot.base_champion_id,
        closure.snapshot.base_champion_hash,
    ):
        raise cs.CandidateSnapshotTamperError(
            "candidate parent champion anchor mismatch"
        )


def validate_internal(closure: cs.CandidateSnapshotClosure) -> None:
    snapshot, before, after = (
        closure.snapshot,
        closure.parent_execution_manifest,
        closure.candidate_execution_manifest,
    )
    if (before.code_hash, before.executable_snapshot_hash) != (
        snapshot.code_parent.code_hash,
        snapshot.code_parent.executable_snapshot_hash,
    ):
        raise cs.CandidateSnapshotTamperError("closure parent identity mismatch")
    if (after.code_hash, after.executable_snapshot_hash) != (
        snapshot.candidate_code_hash,
        snapshot.executable_snapshot_hash,
    ):
        raise cs.CandidateSnapshotTamperError("closure candidate identity mismatch")
    if (
        cs.execution_manifest_digest(before)
        != snapshot.parent_execution_manifest_digest
        or cs.execution_manifest_digest(after)
        != snapshot.candidate_execution_manifest_digest
    ):
        raise cs.CandidateSnapshotTamperError("execution manifest digest mismatch")
    if (
        tuple(item.file_path for item in closure.delta)
        != snapshot.verified_touched_files
    ):
        raise cs.CandidateSnapshotTamperError("verified touched files mismatch")
    patch_identity = [
        {
            "file_path": item.file_path,
            "action": item.action,
            "code_sha256": item.code_sha256,
        }
        for item in closure.proposal_patch
    ]
    if _digest_text(_json(patch_identity)) != snapshot.proposal_patch_digest:
        raise cs.CandidateSnapshotTamperError("proposal Patch digest mismatch")
    verification = json.loads(closure.verification_result_json)
    cs._validate_verification_result_payload(verification)
    if (
        cs.verification_identity_digest(verification)
        != snapshot.verification_identity_digest
        or verification.get("passed") is not True
    ):
        raise cs.CandidateSnapshotTamperError("Verification identity mismatch")
    if (
        _digest_text(_json(cs.candidate_snapshot_identity_payload(snapshot)))
        != snapshot.candidate_id
    ):
        raise cs.CandidateSnapshotTamperError("candidate ownership identity mismatch")
    old = {item.file_path: item.sha256 for item in before.files}
    new = {item.file_path: item.sha256 for item in after.files}
    changed = sorted(
        path for path in set(old) | set(new) if old.get(path) != new.get(path)
    )
    if changed != [item.file_path for item in closure.delta]:
        raise cs.CandidateSnapshotTamperError("delta manifest mismatch")
    for item in closure.delta:
        if (item.base_sha256, item.result_sha256) != (
            old.get(item.file_path),
            new.get(item.file_path),
        ):
            raise cs.CandidateSnapshotTamperError("delta identity mismatch")
    cs._validate_delta_claims(closure)
    delta_by_path = {item.file_path: item for item in closure.delta}
    empty_sha256 = hashlib.sha256(b"").hexdigest()
    for item in closure.proposal_patch:
        prefix, _, path = item.content_source.partition(":")
        delta_item = delta_by_path.get(path)
        if path != item.file_path:
            raise cs.CandidateSnapshotTamperError("Patch content source mismatch")
        if prefix == "delta":
            if (
                delta_item is None
                or delta_item.action not in {"create", "modify"}
                or item.action != delta_item.action
                or item.code_sha256 != delta_item.result_sha256
            ):
                raise cs.CandidateSnapshotTamperError("Patch delta content mismatch")
        elif prefix == "parent":
            if (
                item.action != "modify"
                or path not in old
                or old[path] != new.get(path)
                or item.code_sha256 != old[path]
            ):
                raise cs.CandidateSnapshotTamperError("Patch parent content mismatch")
        elif prefix == "tombstone":
            if (
                item.action != "delete"
                or delta_item is None
                or delta_item.action != "delete"
                or item.code_sha256 != empty_sha256
            ):
                raise cs.CandidateSnapshotTamperError("Patch tombstone mismatch")
        else:  # NormalizedPatchChange rejects this before reaching the codec.
            raise cs.CandidateSnapshotTamperError("Patch content source mismatch")


def _materialize(
    closure: cs.CandidateSnapshotClosure,
    root: Path,
    destination: Path,
    seen: set[str],
    ancestor_resolver: cs.CandidateAncestorResolver | None,
) -> None:
    validate_internal(closure)
    candidate_id = closure.snapshot.candidate_id
    if candidate_id in seen:
        raise cs.CandidateSnapshotTamperError("candidate snapshot parent cycle")
    seen.add(candidate_id)
    destination.mkdir(parents=True, exist_ok=True)
    parent = closure.snapshot.code_parent
    if parent.kind is cs.CandidateCodeParentKind.CHAMPION:
        source = _resolve(root, parent.ref, file=False)
        if not source.is_dir():
            raise cs.CandidateSnapshotTamperError("champion parent is missing")
        _copy_manifest(source, destination, closure.parent_execution_manifest)
    else:
        ancestor = cs._decode_pinned_ancestor(parent, ancestor_resolver)
        _materialize(ancestor, root, destination, seen, ancestor_resolver)
        if ancestor.candidate_execution_manifest != closure.parent_execution_manifest:
            raise cs.CandidateSnapshotTamperError("candidate parent manifest mismatch")
    _verify_manifest(destination, closure.parent_execution_manifest)
    for item in closure.delta:
        target = _target(destination, item.file_path)
        if item.action == "delete":
            if not target.is_file() or target.is_symlink():
                raise cs.CandidateSnapshotTamperError(
                    "delete tombstone base is missing"
                )
            target.unlink()
        else:
            if item.action == "modify" and (
                not target.is_file() or target.is_symlink()
            ):
                raise cs.CandidateSnapshotTamperError("modify delta base is missing")
            if item.action == "create" and (target.exists() or target.is_symlink()):
                raise cs.CandidateSnapshotTamperError("create delta target exists")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(item.content or b"")
    _verify_manifest(destination, closure.candidate_execution_manifest)
    seen.remove(candidate_id)


def _copy_manifest(
    source: Path, destination: Path, manifest: cs.ExecutionManifest
) -> None:
    for item in manifest.files:
        data = _read(source, item.file_path)
        if hashlib.sha256(data).hexdigest() != item.sha256:
            raise cs.CandidateSnapshotTamperError(f"parent drift: {item.file_path}")
        target = _target(destination, item.file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def _verify_manifest(path: Path, manifest: cs.ExecutionManifest) -> None:
    for item in manifest.files:
        if hashlib.sha256(_read(path, item.file_path)).hexdigest() != item.sha256:
            raise cs.CandidateSnapshotTamperError(
                f"materialization drift: {item.file_path}"
            )
    code = (item.file_path for item in manifest.files if item.role == "code_identity")
    if (
        _tree_hash(path, code) != manifest.code_hash
        or _tree_hash(path, (item.file_path for item in manifest.files))
        != manifest.executable_snapshot_hash
    ):
        raise cs.CandidateSnapshotTamperError("materialized identity hash mismatch")


def _root(value: str | Path) -> Path:
    path = Path(value)
    if path.is_symlink() or not path.is_dir():
        raise cs.CandidateSnapshotError("campaign root is unavailable or a symlink")
    return path.resolve()


def _workspace(root: Path, value: str | Path, label: str) -> Path:
    path = Path(value)
    path = path if path.is_absolute() else root / path
    _contained(root, path, label)
    _no_symlinks(root, path)
    if path.is_symlink() or not path.is_dir():
        raise cs.CandidateSnapshotError(f"{label} is unavailable or a symlink")
    return path.resolve()


def _resolve(root: Path, ref: str, *, file: bool) -> Path:
    if "#" in str(ref or ""):
        raise ValueError("physical candidate snapshot ref cannot contain a fragment")
    physical = cs._relative(str(ref or "").partition("#")[0])
    path = root.joinpath(*PurePosixPath(physical).parts)
    _contained(root, path, "snapshot ref")
    _no_symlinks(root, path)
    if not path.exists() or (file and (not path.is_file() or path.is_symlink())):
        raise cs.CandidateSnapshotTamperError("candidate snapshot ref is missing")
    return path.resolve()


def _contained(root: Path, path: Path, label: str) -> None:
    try:
        path.absolute().relative_to(root.absolute())
    except ValueError as exc:
        raise cs.CandidateSnapshotError(f"{label} escapes campaign root") from exc


def _no_symlinks(root: Path, path: Path) -> None:
    cursor = root
    for part in path.absolute().relative_to(root.absolute()).parts:
        cursor /= part
        if cursor.is_symlink():
            raise cs.CandidateSnapshotTamperError("symlink traversal is forbidden")


def _read(root: Path, relative: str) -> bytes:
    path = root.joinpath(*PurePosixPath(cs._relative(relative)).parts)
    _contained(root.resolve(), path, "identity file")
    _no_symlinks(root.resolve(), path)
    if path.is_symlink() or not path.is_file():
        raise cs.CandidateSnapshotTamperError(f"identity file is missing: {relative}")
    return path.read_bytes()


def _target(root: Path, relative: str) -> Path:
    path = root.joinpath(*PurePosixPath(cs._relative(relative)).parts)
    _contained(root.resolve(), path, "materialization path")
    return path


def _tree_hash(root: Path, paths: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        digest.update(path.encode())
        digest.update(_read(root, path))
    return digest.hexdigest()


def _json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an exact string")
    result = value.strip()
    if not result:
        raise ValueError(f"{label} is required")
    return result


def _optional(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("optional identity must be string or null")
    return value.strip()


def read_snapshot_ref_bytes(campaign_root: str | Path, ref: str) -> bytes:
    """Read one root-contained immutable closure ref without following symlinks."""

    return _resolve(_root(campaign_root), ref, file=True).read_bytes()
