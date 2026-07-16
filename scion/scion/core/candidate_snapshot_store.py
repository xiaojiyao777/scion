"""Durable registry and artifact owner for immutable candidate snapshots.

D1 deliberately leaves this store unwired.  It neither reads legacy formal
candidate artifacts nor emits events; a later slice will select the ownership
mode and call :meth:`CandidateSnapshotStore.record` after Verification.
"""

from __future__ import annotations

import hashlib
import os
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterator, Mapping

from scion.core.candidate_snapshot import (
    CandidateAncestorArtifact,
    CandidateOriginKind,
    CandidateSnapshotClosure,
    CandidateSnapshotError,
    CandidateSnapshotRequest,
    CandidateSnapshotTamperError,
    _build_candidate_snapshot_closure,
    candidate_snapshot_closure_bytes,
    decode_candidate_snapshot_closure,
    execution_manifest_from_workspace,
    validate_candidate_snapshot_closure,
)
from scion.core.candidate_snapshot_registry import (
    CandidateOwnershipMode,
    CandidateSnapshotConflictError,
    CandidateSnapshotModeError,
    CandidateSnapshotRecord,
    CandidateSnapshotRegistry,
)


@dataclass(frozen=True)
class CandidateSnapshotRecoveryReport:
    """Pending rows recovered from durable bytes or held fail-closed."""

    recovered_candidate_ids: tuple[str, ...]
    held_candidate_ids: tuple[str, ...]


FaultHook = Callable[[str, CandidateSnapshotRecord], None]
IdentityManifestProvider = Callable[[str], Mapping[str, Any]]


class CandidateSnapshotStore:
    """Append-only SQLite registry plus atomic content-addressed artifacts."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        campaign_root: str | Path,
        identity_manifest_for: IdentityManifestProvider,
        fault_hook: FaultHook | None = None,
    ) -> None:
        root = Path(campaign_root)
        if root.is_symlink() or not root.is_dir():
            raise CandidateSnapshotError(
                "candidate snapshot campaign root is unavailable or a symlink"
            )
        self.db_path = str(db_path)
        self.campaign_root = root.resolve()
        root_stat = self.campaign_root.stat()
        self._root_identity = (root_stat.st_dev, root_stat.st_ino)
        self.identity_manifest_for = identity_manifest_for
        self.fault_hook = fault_hook
        self._registry = CandidateSnapshotRegistry(db_path)

    def claim_ownership_mode(
        self,
        campaign_id: str,
        mode: CandidateOwnershipMode | str,
    ) -> CandidateOwnershipMode:
        """Claim the DB singleton once; the selected mode is immutable."""

        return self._registry.claim_mode(campaign_id, mode)

    def verify_ownership_mode(
        self,
        campaign_id: str,
        expected: CandidateOwnershipMode | str = (
            CandidateOwnershipMode.CANDIDATE_SNAPSHOT_V1
        ),
    ) -> CandidateOwnershipMode:
        """Verify an explicit durable claim without examining artifacts."""

        return self._registry.verify_mode(campaign_id, expected)

    def record(self, request: CandidateSnapshotRequest) -> CandidateSnapshotRecord:
        """Build from authoritative workspace manifests, publish, and commit."""

        if type(request) is not CandidateSnapshotRequest:
            raise TypeError("candidate snapshot record requires a typed request")
        parent_ref = self._workspace_ref(request.parent_workspace, "parent workspace")
        candidate_ref = self._workspace_ref(
            request.candidate_workspace,
            "candidate workspace",
        )
        closure = _build_candidate_snapshot_closure(
            request=request,
            campaign_root=self.campaign_root,
            parent_editable_identity_manifest=self.identity_manifest_for(
                str(self._workspace_path(parent_ref))
            ),
            candidate_editable_identity_manifest=self.identity_manifest_for(
                str(self._workspace_path(candidate_ref))
            ),
            ancestor_resolver=self.resolve_ancestor_artifact,
        )
        return self._record_closure(closure, parent_ref, candidate_ref)

    def _record_closure(
        self,
        closure: CandidateSnapshotClosure,
        parent_workspace_ref: str,
        candidate_workspace_ref: str,
    ) -> CandidateSnapshotRecord:
        snapshot = closure.snapshot
        self.verify_ownership_mode(snapshot.campaign_id)
        validate_candidate_snapshot_closure(
            closure,
            campaign_root=self.campaign_root,
            ancestor_resolver=self.resolve_ancestor_artifact,
        )
        artifact = candidate_snapshot_closure_bytes(closure)
        artifact_sha256 = hashlib.sha256(artifact).hexdigest()
        desired = CandidateSnapshotRecord(
            candidate_id=snapshot.candidate_id,
            campaign_id=snapshot.campaign_id,
            origin_kind=snapshot.origin_kind,
            origin_id=snapshot.origin_id,
            identity_sha256=snapshot.candidate_id,
            artifact_sha256=artifact_sha256,
            artifact_ref=snapshot.candidate_snapshot_ref,
            parent_workspace_ref=parent_workspace_ref,
            candidate_workspace_ref=candidate_workspace_ref,
            status="prepared",
        )
        self._revalidate_workspaces(desired, closure)
        record = self._prepare(desired)
        if record.status == "committed":
            with self._artifact_dirfd() as (root_fd, directory_fd):
                final, _ = self._artifact_names(record)
                self._verify_artifact(record, directory_fd, final)
                self._assert_canonical_artifact_dir(root_fd, directory_fd)
            return record
        self._fault("after_prepare", record)
        return self._publish_and_commit(
            record,
            artifact,
            workspace_owner=desired,
        )

    def load(self, candidate_id: str) -> CandidateSnapshotRecord | None:
        return self._registry.load(candidate_id)

    def load_for_origin(
        self,
        campaign_id: str,
        origin_kind: CandidateOriginKind | str,
        origin_id: str,
    ) -> CandidateSnapshotRecord | None:
        return self._registry.load_for_origin(campaign_id, origin_kind, origin_id)

    def verify(self, candidate_id: str) -> CandidateSnapshotClosure:
        """Load and physically verify one committed closure and exact parent."""

        record = self.load(candidate_id)
        if record is None or record.status != "committed":
            raise CandidateSnapshotError(
                "candidate snapshot does not have a committed registry owner"
            )
        self.verify_ownership_mode(record.campaign_id)
        with self._artifact_dirfd() as (root_fd, directory_fd):
            final, _ = self._artifact_names(record)
            closure = self._verify_artifact(record, directory_fd, final)
            self._assert_canonical_artifact_dir(root_fd, directory_fd)
            return closure

    def resolve_ancestor_artifact(
        self,
        candidate_id: str,
        ref: str,
    ) -> CandidateAncestorArtifact:
        """Resolve exact committed bytes pinned by the registry artifact digest."""

        record = self.load(candidate_id)
        if record is None or record.status != "committed":
            raise CandidateSnapshotTamperError(
                "candidate ancestor has no committed registry owner"
            )
        self.verify_ownership_mode(record.campaign_id)
        if ref != record.artifact_ref:
            raise CandidateSnapshotTamperError(
                "candidate ancestor ref conflicts with its registry owner"
            )
        with self._artifact_dirfd() as (root_fd, directory_fd):
            final, _ = self._artifact_names(record)
            data = _read_pinned_at(directory_fd, final)
            assert data is not None
            self._assert_canonical_artifact_dir(root_fd, directory_fd)
            return CandidateAncestorArtifact(
                record.candidate_id,
                record.artifact_ref,
                record.artifact_sha256,
                data,
            )

    def pending(self) -> tuple[CandidateSnapshotRecord, ...]:
        return self._registry.pending()

    def recover_pending(self) -> CandidateSnapshotRecoveryReport:
        """Converge only rows with an intact final or fsynced temp artifact."""

        recovered: list[str] = []
        held: list[str] = []
        for record in self.pending():
            try:
                self.verify_ownership_mode(record.campaign_id)
                committed = self._publish_and_commit(record, artifact=None)
            except (CandidateSnapshotError, OSError):
                held.append(record.candidate_id)
                continue
            recovered.append(committed.candidate_id)
        return CandidateSnapshotRecoveryReport(tuple(recovered), tuple(held))

    def _prepare(self, desired: CandidateSnapshotRecord) -> CandidateSnapshotRecord:
        return self._registry.prepare(desired)

    def _publish_and_commit(
        self,
        record: CandidateSnapshotRecord,
        artifact: bytes | None,
        *,
        workspace_owner: CandidateSnapshotRecord | None = None,
    ) -> CandidateSnapshotRecord:
        with self._artifact_dirfd() as (root_fd, directory_fd):
            final, temp = self._artifact_names(record)
            final_data = _read_pinned_at(directory_fd, final, missing_ok=True)
            if final_data is not None:
                closure = self._decode_artifact(record, final_data)
                self._discard_temp(directory_fd, temp)
            else:
                temp_data = _read_pinned_at(directory_fd, temp, missing_ok=True)
                if temp_data is not None:
                    self._decode_artifact(record, temp_data)
                elif artifact is None:
                    raise CandidateSnapshotTamperError(
                        "prepared candidate snapshot has no durable artifact bytes"
                    )
                else:
                    self._write_temp(directory_fd, temp, artifact)
                self._fault("after_temp_fsync", record)
                final_data = _read_pinned_at(directory_fd, final, missing_ok=True)
                if final_data is not None:
                    closure = self._decode_artifact(record, final_data)
                    self._discard_temp(directory_fd, temp)
                else:
                    os.rename(
                        temp,
                        final,
                        src_dir_fd=directory_fd,
                        dst_dir_fd=directory_fd,
                    )
                    os.fsync(directory_fd)
                    self._fault("after_artifact_rename", record)
                    closure = self._verify_artifact(record, directory_fd, final)
            self._revalidate_workspaces(workspace_owner or record, closure)
            self._fault("before_registry_commit", record)
            self._assert_canonical_artifact_dir(root_fd, directory_fd)
            committed = self._mark_committed(record)
            self._fault("after_registry_commit", committed)
            return committed

    def _mark_committed(
        self,
        record: CandidateSnapshotRecord,
    ) -> CandidateSnapshotRecord:
        return self._registry.mark_committed(record)

    def _verify_artifact(
        self,
        record: CandidateSnapshotRecord,
        directory_fd: int,
        name: str,
    ) -> CandidateSnapshotClosure:
        data = _read_pinned_at(directory_fd, name)
        assert data is not None
        return self._decode_artifact(record, data)

    def _decode_artifact(
        self,
        record: CandidateSnapshotRecord,
        data: bytes,
    ) -> CandidateSnapshotClosure:
        closure = decode_candidate_snapshot_closure(
            data,
            expected_sha256=record.artifact_sha256,
        )
        snapshot = closure.snapshot
        if (
            snapshot.candidate_id != record.candidate_id
            or snapshot.campaign_id != record.campaign_id
            or snapshot.origin_kind is not record.origin_kind
            or snapshot.origin_id != record.origin_id
            or snapshot.candidate_snapshot_ref != record.artifact_ref
            or snapshot.candidate_id != record.identity_sha256
        ):
            raise CandidateSnapshotTamperError(
                "candidate snapshot artifact conflicts with its registry owner"
            )
        validate_candidate_snapshot_closure(
            closure,
            campaign_root=self.campaign_root,
            ancestor_resolver=self.resolve_ancestor_artifact,
        )
        return closure

    def _revalidate_workspaces(
        self,
        record: CandidateSnapshotRecord,
        closure: CandidateSnapshotClosure,
    ) -> None:
        parent = self._workspace_path(record.parent_workspace_ref)
        candidate = self._workspace_path(record.candidate_workspace_ref)
        parent_manifest = execution_manifest_from_workspace(
            campaign_root=self.campaign_root,
            workspace=parent,
            editable_identity_manifest=self.identity_manifest_for(str(parent)),
        )
        candidate_manifest = execution_manifest_from_workspace(
            campaign_root=self.campaign_root,
            workspace=candidate,
            editable_identity_manifest=self.identity_manifest_for(str(candidate)),
        )
        if (
            parent_manifest != closure.parent_execution_manifest
            or candidate_manifest != closure.candidate_execution_manifest
        ):
            raise CandidateSnapshotTamperError(
                "candidate snapshot workspace identity drifted before commit"
            )

    def _write_temp(self, directory_fd: int, name: str, data: bytes) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(name, flags, 0o600, dir_fd=directory_fd)
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            os.close(descriptor)

    @contextmanager
    def _artifact_dirfd(self) -> Iterator[tuple[int, int]]:
        with self._root_dirfd() as root_fd:
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            try:
                try:
                    descriptor = os.open("candidate_snapshots", flags, dir_fd=root_fd)
                except FileNotFoundError:
                    os.mkdir("candidate_snapshots", 0o700, dir_fd=root_fd)
                    os.fsync(root_fd)
                    descriptor = os.open("candidate_snapshots", flags, dir_fd=root_fd)
            except OSError as exc:
                raise CandidateSnapshotTamperError(
                    "candidate snapshot artifact directory is unavailable or a symlink"
                ) from exc
            try:
                yield root_fd, descriptor
            finally:
                os.close(descriptor)

    def _assert_canonical_artifact_dir(
        self,
        root_fd: int,
        pinned_fd: int,
    ) -> None:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        parent_fd: int | None = None
        canonical_root_fd: int | None = None
        canonical_child_fd: int | None = None
        try:
            try:
                parent_fd = os.open(self.campaign_root.parent, flags)
                canonical_root_fd = os.open(
                    self.campaign_root.name,
                    flags,
                    dir_fd=parent_fd,
                )
                canonical_child_fd = os.open(
                    "candidate_snapshots",
                    flags,
                    dir_fd=canonical_root_fd,
                )
            except OSError as exc:
                raise CandidateSnapshotTamperError(
                    "candidate snapshot canonical root or artifact directory "
                    "is unreachable"
                ) from exc
            assert canonical_root_fd is not None
            assert canonical_child_fd is not None
            canonical_root = os.fstat(canonical_root_fd)
            pinned_root = os.fstat(root_fd)
            root_identity = (canonical_root.st_dev, canonical_root.st_ino)
            if root_identity != self._root_identity or root_identity != (
                pinned_root.st_dev,
                pinned_root.st_ino,
            ):
                raise CandidateSnapshotTamperError(
                    "candidate snapshot canonical campaign root changed"
                )
            canonical = os.fstat(canonical_child_fd)
            pinned = os.fstat(pinned_fd)
            if (canonical.st_dev, canonical.st_ino) != (
                pinned.st_dev,
                pinned.st_ino,
            ):
                raise CandidateSnapshotTamperError(
                    "candidate snapshot canonical artifact directory changed"
                )
        finally:
            for descriptor in (
                canonical_child_fd,
                canonical_root_fd,
                parent_fd,
            ):
                if descriptor is not None:
                    os.close(descriptor)

    @contextmanager
    def _root_dirfd(self) -> Iterator[int]:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(self.campaign_root, flags)
        except OSError as exc:
            raise CandidateSnapshotTamperError(
                "candidate snapshot campaign root changed"
            ) from exc
        try:
            current = os.fstat(descriptor)
            if (current.st_dev, current.st_ino) != self._root_identity:
                raise CandidateSnapshotTamperError(
                    "candidate snapshot campaign root identity changed"
                )
            yield descriptor
        finally:
            os.close(descriptor)

    @staticmethod
    def _artifact_names(record: CandidateSnapshotRecord) -> tuple[str, str]:
        expected = f"candidate_snapshots/{record.candidate_id}.json"
        if record.artifact_ref != expected:
            raise CandidateSnapshotTamperError(
                "candidate snapshot registry ref is not canonical"
            )
        return (
            f"{record.candidate_id}.json",
            f".{record.candidate_id}.{record.artifact_sha256}.tmp",
        )

    def _workspace_ref(self, value: str, label: str) -> str:
        path = Path(value)
        path = path if path.is_absolute() else self.campaign_root / path
        try:
            relative = path.absolute().relative_to(self.campaign_root)
        except ValueError as exc:
            raise CandidateSnapshotError(f"{label} escapes campaign root") from exc
        ref = relative.as_posix()
        self._workspace_path(ref)
        return ref

    def _workspace_path(self, ref: str) -> Path:
        pure = PurePosixPath(ref)
        if (
            pure.is_absolute()
            or pure.as_posix() != ref
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            raise CandidateSnapshotTamperError("candidate workspace ref is invalid")
        path = self.campaign_root
        for part in pure.parts:
            path /= part
            if path.is_symlink():
                raise CandidateSnapshotTamperError(
                    "candidate workspace symlink traversal is forbidden"
                )
        if not path.is_dir():
            raise CandidateSnapshotTamperError("candidate workspace is unavailable")
        return path

    @staticmethod
    def _discard_temp(directory_fd: int, name: str) -> None:
        if _read_pinned_at(directory_fd, name, missing_ok=True) is not None:
            os.unlink(name, dir_fd=directory_fd)
            os.fsync(directory_fd)

    def _fault(self, phase: str, record: CandidateSnapshotRecord) -> None:
        if self.fault_hook is not None:
            self.fault_hook(phase, record)


def _read_pinned_at(
    directory_fd: int,
    name: str,
    *,
    missing_ok: bool = False,
) -> bytes | None:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(name, flags, dir_fd=directory_fd)
    except FileNotFoundError:
        if missing_ok:
            return None
        raise CandidateSnapshotTamperError("candidate snapshot artifact is missing")
    except OSError as exc:
        raise CandidateSnapshotTamperError(
            "candidate snapshot artifact is missing or a symlink"
        ) from exc
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise CandidateSnapshotTamperError(
                "candidate snapshot artifact is not a regular file"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read()
    finally:
        os.close(descriptor)
