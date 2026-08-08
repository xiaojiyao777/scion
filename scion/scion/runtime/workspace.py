"""WorkspaceMaterializer: create and manage branch workspaces."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import stat
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Iterable, Optional

from scion.core.models import (
    ChampionState,
    PatchFileChange,
    PatchProposal,
    patch_file_changes,
)
from scion.core.path_match import segment_glob_match
from scion.core.paths import normalize_relative_patch_path
from scion.core.research_surface_index import normalize_editable_identity_patterns

# Generic runtime has no problem-specific frozen files by default.
_DEFAULT_FROZEN_PATTERNS = frozenset()
logger = logging.getLogger(__name__)


class FrozenFileError(Exception):
    """Raised when apply_patch attempts to modify a frozen file."""


class WorkspaceIdentityCaptureError(RuntimeError):
    """One exact editable-identity byte capture could not be proven."""


class WorkspaceIdentityDriftError(WorkspaceIdentityCaptureError):
    """The selected workspace identity changed while it was being captured."""


@dataclass(frozen=True, slots=True)
class EditableIdentityBytesEntry:
    """One immutable file fact read exactly once during an identity capture."""

    file_path: str
    content: bytes
    sha256: str
    code_identity: bool
    snapshot_identity: bool


@dataclass(frozen=True, slots=True)
class EditableIdentityBytesCapture:
    """One complete immutable code/snapshot identity derived from the same bytes."""

    schema_version: ClassVar[str] = "scion.editable_identity_bytes_capture.v1"
    entries: tuple[EditableIdentityBytesEntry, ...]
    code_hash: str
    snapshot_hash: str
    manifest_digest: str


class WorkspaceMaterializer:
    """Manages filesystem workspaces for Scion branch experiments.

    Directory layout under campaign_dir::

        campaign_dir/
            workspaces/
                <branch_id>/   ← created by create_branch_workspace
            champions/
                v<N>/          ← created by create_champion_snapshot
    """

    def __init__(
        self,
        campaign_dir: str,
        frozen_patterns: Optional[frozenset[str]] = None,
        editable_patterns: Optional[Iterable[str]] = None,
    ) -> None:
        self._campaign_dir = Path(campaign_dir)
        self._workspaces_dir = self._campaign_dir / "workspaces"
        self._candidate_workspaces_dir = self._campaign_dir / "candidate_workspaces"
        self._champions_dir = self._campaign_dir / "champions"
        self._frozen_patterns = (
            _DEFAULT_FROZEN_PATTERNS if frozen_patterns is None else frozen_patterns
        )
        self._editable_patterns = (
            None
            if editable_patterns is None
            else normalize_editable_identity_patterns(editable_patterns)
        )

        self._workspaces_dir.mkdir(parents=True, exist_ok=True)
        self._candidate_workspaces_dir.mkdir(parents=True, exist_ok=True)
        self._champions_dir.mkdir(parents=True, exist_ok=True)
        self._archive_dir = self._campaign_dir / "archive"
        self._archive_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_branch_workspace(self, branch_id: str, code_base: str) -> str:
        """Copy code_base into a fresh branch workspace.

        Args:
            branch_id: Unique identifier for the branch.
            code_base: Path to the source code directory to copy.

        Returns:
            Absolute path to the new workspace directory.

        Raises:
            FileNotFoundError: If code_base does not exist.
        """
        src = Path(code_base)
        if not src.exists():
            raise FileNotFoundError(f"code_base does not exist: {code_base}")

        dest = self._workspaces_dir / branch_id
        if dest.exists():
            shutil.rmtree(dest)

        shutil.copytree(src, dest, symlinks=False)
        # Ensure workspace is writable even if copied from a read-only champion snapshot
        _make_tree_writable(dest)
        return str(dest)

    def create_candidate_workspace(
        self,
        branch_id: str,
        source_workspace: str,
    ) -> str:
        """Copy a clean branch base into an isolated candidate workspace."""

        src = Path(source_workspace).resolve()
        if not src.is_dir():
            raise FileNotFoundError(
                f"candidate source workspace does not exist: {source_workspace}"
            )
        branch_dir = self._candidate_workspaces_dir / branch_id
        branch_dir.mkdir(parents=True, exist_ok=True)
        candidate = branch_dir / uuid.uuid4().hex
        shutil.copytree(src, candidate, symlinks=False)
        _make_tree_writable(candidate)
        return str(candidate)

    def adopt_candidate_workspace(
        self,
        candidate_workspace: str,
        branch_id: str,
    ) -> str:
        """Move verified staging to the ordinary durable branch path.

        This is a local filesystem handoff, not a promotion or authority
        protocol.  A temporary backup only protects the preceding branch tree
        while the two renames occur and is removed before return.
        """

        candidate = Path(candidate_workspace).resolve()
        expected_parent = (self._candidate_workspaces_dir / branch_id).resolve()
        if candidate.parent != expected_parent or not candidate.is_dir():
            raise ValueError("candidate workspace is not owned by the branch")

        durable = self._workspaces_dir / branch_id
        backup = self._workspaces_dir / f".{branch_id}.adopt-backup-{uuid.uuid4().hex}"
        try:
            if durable.exists():
                durable.rename(backup)
            candidate.rename(durable)
        except BaseException:
            if durable.exists() and not candidate.exists():
                durable.rename(candidate)
            if backup.exists() and not durable.exists():
                backup.rename(durable)
            raise
        if backup.exists():
            try:
                _make_tree_writable(backup)
                shutil.rmtree(backup)
            except OSError as exc:
                # The candidate rename is already committed.  Old-tree debris
                # cannot turn a successful local handoff into a false rollback.
                logger.warning(
                    "Could not remove replaced branch workspace %s: %s",
                    backup,
                    exc,
                )
        _prune_empty_candidate_parent(expected_parent, self._candidate_workspaces_dir)
        return str(durable)

    def cleanup_candidate_workspace(self, candidate_workspace: str) -> None:
        """Delete an isolated candidate without touching its durable base."""

        candidate = Path(candidate_workspace).resolve()
        candidate_root = self._candidate_workspaces_dir.resolve()
        if (
            not _is_relative_to(candidate, candidate_root)
            or candidate == candidate_root
        ):
            raise ValueError("refusing to clean a non-candidate workspace")
        if candidate.exists():
            _make_tree_writable(candidate)
            shutil.rmtree(candidate)
        _prune_empty_candidate_parent(candidate.parent, candidate_root)

    def apply_patch(self, workspace: str, patch: PatchProposal) -> str:
        """Atomically materialize every declared file change.

        The file_path in patch is treated as relative to workspace root.

        Args:
            workspace: Absolute path to the branch workspace.
            patch: PatchProposal to apply.

        Returns:
            SHA-256 hex string of declared editable identity files after patch.

        Raises:
            FrozenFileError: If the patch targets a frozen file.
            ValueError: If patch.action is 'delete' (not yet supported here).
        """
        ws = Path(workspace).resolve()
        if not ws.is_dir():
            raise FileNotFoundError(f"workspace does not exist: {workspace}")
        changes = patch_file_changes(patch)
        self._preflight_file_changes(ws, changes)

        transaction_id = uuid.uuid4().hex
        staged = ws.parent / f".{ws.name}.patch-stage-{transaction_id}"
        backup = ws.parent / f".{ws.name}.patch-backup-{transaction_id}"
        try:
            shutil.copytree(ws, staged, symlinks=False)
            _make_tree_writable(staged)
            for change in changes:
                self._apply_file_change(staged, change)
            code_hash = self.compute_code_hash(str(staged))

            ws.rename(backup)
            try:
                staged.rename(ws)
            except BaseException:
                backup.rename(ws)
                raise
            try:
                shutil.rmtree(backup)
            except OSError:
                # The committed workspace is authoritative. A stale backup is
                # cleanup debris, not a reason to report a failed materialization.
                pass
            return code_hash
        finally:
            if staged.exists():
                shutil.rmtree(staged, ignore_errors=True)

    def _preflight_file_changes(
        self,
        ws: Path,
        changes: Iterable[PatchFileChange],
    ) -> None:
        seen: set[str] = set()
        for change in changes:
            file_rel = normalize_relative_patch_path(change.file_path)
            if file_rel in seen:
                raise ValueError(f"patch repeats file_path: {file_rel}")
            seen.add(file_rel)
            if self._is_frozen(file_rel):
                raise FrozenFileError(
                    f"apply_patch refused: '{change.file_path}' matches frozen patterns"
                )
            target = (ws / file_rel).resolve()
            if not _is_relative_to(target, ws):
                raise ValueError(
                    f"patch file_path escapes workspace: {change.file_path}"
                )
            if change.action not in {"modify", "create", "delete"}:
                raise ValueError(f"unsupported patch action: {change.action}")
            if change.action != "delete" and not isinstance(
                change.code_content,
                str,
            ):
                raise TypeError(
                    f"patch code_content must be a string: {change.file_path}"
                )

    def _apply_file_change(self, ws: Path, change: PatchFileChange) -> None:
        # Second-level frozen-file check (Contract Gate is the first)
        file_rel = normalize_relative_patch_path(change.file_path)
        if self._is_frozen(file_rel):
            raise FrozenFileError(
                f"apply_patch refused: '{change.file_path}' matches frozen patterns"
            )

        target = (ws / file_rel).resolve()
        if not _is_relative_to(target, ws):
            raise ValueError(f"patch file_path escapes workspace: {change.file_path}")

        if change.action == "delete":
            if target.exists():
                target.unlink()
        else:
            # "modify" or "create"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(change.code_content, encoding="utf-8")

    def create_champion_snapshot(
        self,
        champion: ChampionState,
        target_dir: str,
    ) -> str:
        """Create a read-only snapshot of the champion workspace.

        Args:
            champion: Champion state containing code_snapshot_path.
            target_dir: Parent directory under which the snapshot is placed.

        Returns:
            Absolute path to the snapshot directory.
        """
        src = Path(champion.code_snapshot_path)
        dest = Path(target_dir) / f"champion_v{champion.version}"

        if dest.exists():
            # Make writable first so we can remove it
            _make_tree_writable(dest)
            shutil.rmtree(dest)

        shutil.copytree(src, dest, symlinks=False)

        # Make the whole tree read-only
        _make_tree_readonly(dest)

        return str(dest)

    def cleanup(self, workspace: str) -> None:
        """Remove the workspace directory (best-effort).

        Args:
            workspace: Absolute path to the branch workspace to delete.
        """
        ws = Path(workspace)
        if ws.exists():
            # Ensure writable before removal
            _make_tree_writable(ws)
            shutil.rmtree(ws)

    def archive_workspace(self, workspace: str, branch_id: str) -> str | None:
        """Copy editable identity files into archive/<branch_id_short>/.

        Called before cleanup on ABANDON so generated research-surface files are
        preserved for post-campaign analysis.

        Args:
            workspace: Absolute path to the branch workspace.
            branch_id: Branch ID used to name the archive sub-directory.

        Returns:
            Absolute path to the archive directory, or None if no editable
            research-surface directories are present.
        """
        ws = Path(workspace)
        files = self._identity_files(ws)
        if not files:
            return None

        # Use first 8 chars of branch_id for readability
        short_id = str(branch_id)[:8]
        archive_dest = self._archive_dir / short_id
        # If a prior archive exists for the same short id, append suffix
        if archive_dest.exists():
            suffix = 1
            while (self._archive_dir / f"{short_id}_{suffix}").exists():
                suffix += 1
            archive_dest = self._archive_dir / f"{short_id}_{suffix}"

        archive_dest.mkdir(parents=True)
        for source in files:
            rel = source.relative_to(ws)
            dest = archive_dest / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest, follow_symlinks=False)
        import logging as _logging

        _logging.getLogger(__name__).info(
            "Archived research surfaces from branch %s → %s", branch_id, archive_dest
        )
        return str(archive_dest)

    def compute_code_hash(self, workspace: str) -> str:
        """Compute SHA-256 of editable identity files.

        Args:
            workspace: Absolute path to the workspace.

        Returns:
            Hex-encoded SHA-256 string.
        """
        ws = Path(workspace)
        return _hash_files(ws, self._identity_files(ws))

    def editable_identity_manifest(self, workspace: str) -> dict[str, object]:
        """Return the exact editable-file identity used by ``compute_code_hash``.

        Formal replay artifacts use this manifest to describe a cumulative
        candidate without reimplementing research-surface path selection.
        File contents remain in the replay materialization artifact; this
        manifest carries only canonical paths, per-file hashes, and the tree
        hash used by branch verification.
        """

        ws = Path(workspace).resolve()
        if not ws.is_dir():
            raise FileNotFoundError(f"workspace does not exist: {workspace}")
        files = _dedupe_sorted_paths(self._identity_files(ws), ws)
        return {
            "schema_version": "scion.editable_identity_manifest.v1",
            "files": [
                {
                    "file_path": path.relative_to(ws).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
                for path in files
            ],
            "code_hash": _hash_files(ws, files),
        }

    def capture_editable_identity_bytes(
        self,
        workspace: str,
    ) -> EditableIdentityBytesCapture:
        """Capture one exact editable identity without accepting a manifest.

        Every selected file is read once.  Per-file digests, the legacy
        ``compute_code_hash`` identity, the legacy ``compute_snapshot_hash``
        identity, and the canonical manifest digest are then derived from those
        same immutable bytes.  The stricter capture boundary rejects relative or
        aliased roots, symlinks, non-canonical relative paths, and any path,
        metadata, or membership drift observed during the capture.
        """

        ws = _strict_capture_workspace(workspace)
        code_files = _strict_capture_identity_files(
            ws,
            patterns=self._editable_patterns,
            is_frozen=self._is_frozen,
        )
        code_paths = tuple(
            _canonical_capture_relative_path(ws, path) for path in code_files
        )
        snapshot_paths = list(code_paths)
        registry_path = ws / "registry.yaml"
        if registry_path.exists() or registry_path.is_symlink():
            _validate_capture_file(ws, registry_path)
            if "registry.yaml" not in snapshot_paths:
                snapshot_paths.append("registry.yaml")
        snapshot_paths.sort()
        all_paths = tuple(sorted(set(snapshot_paths)))
        expected_signatures = {
            relative: _capture_file_signature(ws, relative) for relative in all_paths
        }

        captured: dict[str, bytes] = {}
        for relative in all_paths:
            captured[relative] = _read_stable_identity_file_once(
                ws,
                relative,
                expected_signatures[relative],
            )

        after_code_files = _strict_capture_identity_files(
            ws,
            patterns=self._editable_patterns,
            is_frozen=self._is_frozen,
        )
        after_code_paths = tuple(
            _canonical_capture_relative_path(ws, path) for path in after_code_files
        )
        after_snapshot_paths = list(after_code_paths)
        if registry_path.exists() or registry_path.is_symlink():
            _validate_capture_file(ws, registry_path)
            if "registry.yaml" not in after_snapshot_paths:
                after_snapshot_paths.append("registry.yaml")
        after_snapshot_paths.sort()
        if code_paths != after_code_paths or tuple(snapshot_paths) != tuple(
            after_snapshot_paths
        ):
            raise WorkspaceIdentityDriftError(
                "workspace identity membership changed during capture"
            )
        for relative, expected in expected_signatures.items():
            if _capture_file_signature(ws, relative) != expected:
                raise WorkspaceIdentityDriftError(
                    f"workspace identity file changed during capture: {relative}"
                )

        code_path_set = frozenset(code_paths)
        entries = tuple(
            EditableIdentityBytesEntry(
                file_path=relative,
                content=captured[relative],
                sha256=hashlib.sha256(captured[relative]).hexdigest(),
                code_identity=relative in code_path_set,
                snapshot_identity=True,
            )
            for relative in all_paths
        )
        code_hash = _hash_captured_identity(entries, code_only=True)
        snapshot_hash = _hash_captured_identity(entries, code_only=False)
        manifest_payload = {
            "schema_version": EditableIdentityBytesCapture.schema_version,
            "entries": [
                {
                    "file_path": entry.file_path,
                    "sha256": entry.sha256,
                    "code_identity": entry.code_identity,
                    "snapshot_identity": entry.snapshot_identity,
                }
                for entry in entries
            ],
            "code_hash": code_hash,
            "snapshot_hash": snapshot_hash,
        }
        manifest_bytes = json.dumps(
            manifest_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
        return EditableIdentityBytesCapture(
            entries=entries,
            code_hash=code_hash,
            snapshot_hash=snapshot_hash,
            manifest_digest=hashlib.sha256(manifest_bytes).hexdigest(),
        )

    def compute_snapshot_hash(self, workspace: str) -> str:
        """Compute SHA-256 of editable identity files + registry.yaml.

        Includes registry.yaml so weight changes affect the champion hash.

        Args:
            workspace: Absolute path to the workspace.

        Returns:
            Hex-encoded SHA-256 string.
        """
        ws = Path(workspace)
        return compute_snapshot_hash_for_files(ws, self._identity_files(ws))

    def create_mutable_staging(self, source_workspace: str) -> str:
        """Create a writable staging copy of source_workspace.

        Used in the promote + weight-optimization flow so that weight writes
        land on a mutable copy before the snapshot is frozen.

        Args:
            source_workspace: Path to copy from (may be read-only).

        Returns:
            Absolute path to the new writable staging directory.
        """
        import time as _time

        src = Path(source_workspace)
        staging_dir = self._campaign_dir / "staging"
        staging_dir.mkdir(parents=True, exist_ok=True)

        staging = staging_dir / f"staging_{int(_time.time() * 1000)}"
        if staging.exists():
            _make_tree_writable(staging)
            shutil.rmtree(staging)

        shutil.copytree(src, staging, symlinks=False)
        _make_tree_writable(staging)
        return str(staging)

    def freeze_snapshot(self, path: str) -> None:
        """Recursively make path and its contents read-only.

        Args:
            path: Absolute path to the directory to freeze.
        """
        _make_tree_readonly(Path(path))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _is_frozen(self, file_rel: str) -> bool:
        """Return True if file_rel matches any frozen pattern."""
        import fnmatch

        for pattern in self._frozen_patterns:
            if fnmatch.fnmatch(file_rel, pattern):
                return True
            # Also check basename match for flat patterns without '/'
            if "/" not in pattern and fnmatch.fnmatch(Path(file_rel).name, pattern):
                return True
        return False

    def _identity_files(self, ws: Path) -> list[Path]:
        if self._editable_patterns is None:
            return []
        return _explicit_identity_files(
            ws,
            patterns=self._editable_patterns,
            is_frozen=self._is_frozen,
        )


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _prune_empty_candidate_parent(path: Path, candidate_root: Path) -> None:
    """Remove empty per-branch candidate directories, never the shared root."""

    if path == candidate_root or not _is_relative_to(path, candidate_root):
        return
    try:
        path.rmdir()
    except OSError:
        pass


def _hash_files(ws: Path, files: Iterable[Path]) -> str:
    h = hashlib.sha256()
    for file_path in _dedupe_sorted_paths(files, ws):
        rel = file_path.relative_to(ws)
        h.update(rel.as_posix().encode())
        h.update(file_path.read_bytes())
    return h.hexdigest()


def _strict_capture_workspace(workspace: str) -> Path:
    if type(workspace) is not str or not workspace:
        raise WorkspaceIdentityCaptureError(
            "workspace identity capture requires an exact absolute path"
        )
    raw = Path(workspace)
    if not raw.is_absolute():
        raise WorkspaceIdentityCaptureError(
            "workspace identity capture requires an absolute path"
        )
    if raw.is_symlink():
        raise WorkspaceIdentityCaptureError(
            "workspace identity capture root cannot be a symlink"
        )
    try:
        resolved = raw.resolve(strict=True)
    except OSError as exc:
        raise WorkspaceIdentityCaptureError(
            "workspace identity capture root is unavailable"
        ) from exc
    if raw != resolved:
        raise WorkspaceIdentityCaptureError(
            "workspace identity capture root is not canonical"
        )
    if not resolved.is_dir():
        raise WorkspaceIdentityCaptureError(
            "workspace identity capture root is not a directory"
        )
    return resolved


def _strict_capture_identity_files(
    ws: Path,
    *,
    patterns: tuple[str, ...] | None,
    is_frozen: Callable[[str], bool],
) -> list[Path]:
    if patterns is None:
        return []
    _reject_capture_pattern_symlinks(ws, patterns)
    files = _explicit_identity_files(
        ws,
        patterns=patterns,
        is_frozen=is_frozen,
    )
    for path in files:
        _validate_capture_file(ws, path)
    return files


def _reject_capture_pattern_symlinks(
    ws: Path,
    patterns: Iterable[str],
) -> None:
    """Reject symlinks in paths selected by one editable identity pattern."""

    for pattern in patterns:
        target = ws / pattern
        matches = list(ws.glob(pattern)) if _contains_glob(pattern) else [target]
        for match in matches:
            if not (match.exists() or match.is_symlink()):
                continue
            _validate_capture_path(ws, match)
            if match.is_dir():
                try:
                    descendants = tuple(match.rglob("*"))
                except OSError as exc:
                    raise WorkspaceIdentityCaptureError(
                        "workspace identity pattern cannot be enumerated"
                    ) from exc
                for descendant in descendants:
                    _validate_capture_path(ws, descendant)


def _validate_capture_path(ws: Path, path: Path) -> None:
    try:
        relative_parts = path.absolute().relative_to(ws.absolute()).parts
    except ValueError as exc:
        raise WorkspaceIdentityCaptureError(
            "workspace identity path escapes the capture root"
        ) from exc
    cursor = ws
    for part in relative_parts:
        cursor /= part
        if cursor.is_symlink():
            raise WorkspaceIdentityCaptureError(
                "workspace identity path contains a symlink"
            )
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(ws)
    except (OSError, ValueError) as exc:
        raise WorkspaceIdentityCaptureError(
            "workspace identity path escapes the capture root"
        ) from exc
    if resolved != path.absolute():
        raise WorkspaceIdentityCaptureError("workspace identity path is not canonical")


def _validate_capture_file(ws: Path, path: Path) -> None:
    _validate_capture_path(ws, path)
    try:
        metadata = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise WorkspaceIdentityCaptureError(
            "workspace identity file is unavailable"
        ) from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise WorkspaceIdentityCaptureError(
            "workspace identity path is not a regular file"
        )
    _canonical_capture_relative_path(ws, path)


def _canonical_capture_relative_path(ws: Path, path: Path) -> str:
    try:
        relative = path.relative_to(ws).as_posix()
    except ValueError as exc:
        raise WorkspaceIdentityCaptureError(
            "workspace identity path escapes the capture root"
        ) from exc
    if (
        not relative
        or relative.startswith("/")
        or "\\" in relative
        or any(part in {"", ".", ".."} for part in relative.split("/"))
    ):
        raise WorkspaceIdentityCaptureError(
            "workspace identity relative path is not canonical"
        )
    return relative


def _capture_stat_signature(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        int(metadata.st_dev),
        int(metadata.st_ino),
        int(stat.S_IFMT(metadata.st_mode)),
        int(metadata.st_size),
        int(metadata.st_mtime_ns),
        int(metadata.st_ctime_ns),
    )


def _capture_file_signature(ws: Path, relative: str) -> tuple[int, ...]:
    path = ws / relative
    _validate_capture_file(ws, path)
    try:
        return _capture_stat_signature(os.stat(path, follow_symlinks=False))
    except OSError as exc:
        raise WorkspaceIdentityDriftError(
            f"workspace identity file disappeared during capture: {relative}"
        ) from exc


def _read_stable_identity_file_once(
    ws: Path,
    relative: str,
    expected_signature: tuple[int, ...],
) -> bytes:
    path = ws / relative
    _validate_capture_file(ws, path)
    before = _capture_stat_signature(os.stat(path, follow_symlinks=False))
    if before != expected_signature:
        raise WorkspaceIdentityDriftError(
            f"workspace identity file changed before read: {relative}"
        )
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise WorkspaceIdentityCaptureError(
            f"workspace identity file cannot be opened safely: {relative}"
        ) from exc
    try:
        opened = _capture_stat_signature(os.fstat(descriptor))
        if opened != expected_signature:
            raise WorkspaceIdentityDriftError(
                f"workspace identity file changed while opening: {relative}"
            )
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            descriptor = -1
            content = handle.read()
            after_read = _capture_stat_signature(os.fstat(handle.fileno()))
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if after_read != expected_signature or len(content) != expected_signature[3]:
        raise WorkspaceIdentityDriftError(
            f"workspace identity file changed while reading: {relative}"
        )
    after = _capture_stat_signature(os.stat(path, follow_symlinks=False))
    if after != expected_signature:
        raise WorkspaceIdentityDriftError(
            f"workspace identity file changed after read: {relative}"
        )
    _validate_capture_file(ws, path)
    return content


def _hash_captured_identity(
    entries: tuple[EditableIdentityBytesEntry, ...],
    *,
    code_only: bool,
) -> str:
    digest = hashlib.sha256()
    for entry in entries:
        if code_only and not entry.code_identity:
            continue
        if not entry.snapshot_identity:
            continue
        digest.update(entry.file_path.encode())
        digest.update(entry.content)
    return digest.hexdigest()


def compute_snapshot_hash_for_files(
    workspace: str | Path,
    identity_files: Iterable[Path],
) -> str:
    """Hash one canonical editable identity plus optional ``registry.yaml``."""

    ws = Path(workspace)
    files = list(identity_files)
    registry_path = ws / "registry.yaml"
    if registry_path.exists():
        files.append(registry_path)
    return _hash_files(ws, files)


def _explicit_identity_files(
    ws: Path,
    *,
    patterns: Iterable[str],
    is_frozen: Callable[[str], bool],
) -> list[Path]:
    files: list[Path] = []
    resolved_ws = ws.resolve()
    for pattern in patterns:
        files.extend(
            _files_for_editable_pattern(
                ws=ws,
                resolved_ws=resolved_ws,
                pattern=pattern,
                is_frozen=is_frozen,
            )
        )
    return _dedupe_sorted_paths(files, ws)


def _files_for_editable_pattern(
    *,
    ws: Path,
    resolved_ws: Path,
    pattern: str,
    is_frozen: Callable[[str], bool],
) -> list[Path]:
    target = ws / pattern
    if not _contains_glob(pattern):
        if target.is_file():
            return _allowed_identity_files(
                (target,),
                ws=ws,
                resolved_ws=resolved_ws,
                is_frozen=is_frozen,
            )
        if target.is_dir():
            return _allowed_identity_files(
                target.rglob("*"),
                ws=ws,
                resolved_ws=resolved_ws,
                is_frozen=is_frozen,
            )
        return []

    files: list[Path] = []
    for match in ws.glob(pattern):
        if match.is_dir():
            files.extend(
                _allowed_identity_files(
                    match.rglob("*"),
                    ws=ws,
                    resolved_ws=resolved_ws,
                    is_frozen=is_frozen,
                )
            )
        else:
            files.extend(
                _allowed_identity_files(
                    (match,),
                    ws=ws,
                    resolved_ws=resolved_ws,
                    is_frozen=is_frozen,
                    pattern=pattern,
                )
            )
    return files


def _allowed_identity_files(
    candidates: Iterable[Path],
    *,
    ws: Path,
    resolved_ws: Path,
    is_frozen: Callable[[str], bool],
    pattern: str | None = None,
) -> list[Path]:
    files: list[Path] = []
    for candidate in candidates:
        if not candidate.is_file():
            continue
        if not _is_relative_to(candidate.resolve(), resolved_ws):
            continue
        rel = candidate.relative_to(ws).as_posix()
        if pattern is not None and not segment_glob_match(rel, pattern):
            continue
        if is_frozen(rel):
            continue
        files.append(candidate)
    return files


def _dedupe_sorted_paths(paths: Iterable[Path], ws: Path) -> list[Path]:
    by_rel: dict[str, Path] = {}
    for path in paths:
        if not path.is_file():
            continue
        rel = path.relative_to(ws).as_posix()
        by_rel.setdefault(rel, path)
    return [by_rel[rel] for rel in sorted(by_rel)]


def _contains_glob(path: str) -> bool:
    return any(char in path for char in "*?[")


def _make_tree_readonly(path: Path) -> None:
    """Recursively remove write permissions from path."""
    for root, dirs, files in os.walk(path):
        for name in files + dirs:
            fp = Path(root) / name
            try:
                current = fp.stat().st_mode
                fp.chmod(current & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
            except OSError:
                pass
    # Also the root itself
    try:
        current = path.stat().st_mode
        path.chmod(current & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    except OSError:
        pass


def _make_tree_writable(path: Path) -> None:
    """Recursively restore write permissions so the tree can be deleted."""
    for root, dirs, files in os.walk(path):
        for name in files + dirs:
            fp = Path(root) / name
            try:
                current = fp.stat().st_mode
                fp.chmod(current | stat.S_IWUSR)
            except OSError:
                pass
    try:
        current = path.stat().st_mode
        path.chmod(current | stat.S_IWUSR)
    except OSError:
        pass
