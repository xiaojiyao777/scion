"""Direct workspace materialization for V3 branch steps."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, MutableMapping, Protocol

from scion.core.models import (
    AcceptedBranchChange,
    AcceptedFileBeforeSource,
    Branch,
    ChampionState,
    HypothesisProposal,
    PatchProposal,
    patch_file_changes,
)
from scion.core.paths import normalize_relative_patch_path

logger = logging.getLogger(__name__)


class WorkspaceMaterializerLike(Protocol):
    def create_branch_workspace(self, branch_id: str, source_snapshot: str) -> str: ...

    def cleanup_branch_workspace(self, branch_id: str) -> None: ...

    def apply_patch(self, workspace: str, patch: PatchProposal) -> str: ...

    def apply_ephemeral_patch(self, workspace: str, patch: PatchProposal) -> None: ...

    def create_candidate_workspace(
        self,
        source_workspace: str,
    ) -> str: ...

    def cleanup_candidate_workspace(self, candidate_workspace: str) -> None: ...

    def freeze_snapshot(self, path: str) -> None: ...

    def compute_code_hash(self, workspace: str) -> str: ...

    def cleanup(self, workspace: str) -> None: ...


class BranchControllerLike(Protocol):
    def get_code_base(self, branch_id: str) -> str: ...

    def accept_verified_code(self, branch_id: str, code_hash: str) -> None: ...


@dataclass(frozen=True)
class CandidateWorkspace:
    """One isolated candidate passed directly between V3 stages."""

    workspace: str
    source_digest: str
    before_sources: tuple[AcceptedFileBeforeSource, ...] = ()
    changed_files: tuple[str, ...] = ()


@dataclass
class WorkspaceService:
    """Perform filesystem and code-hash effects for the selected branch."""

    materializer: WorkspaceMaterializerLike
    branch_controller: BranchControllerLike
    branch_workspaces: MutableMapping[str, str]
    champion_lock: Any
    get_champion: Callable[[], ChampionState]

    def setup_workspace(
        self,
        branch: Branch,
    ) -> str | None:
        """Reuse a verified branch workspace or materialize from the champion."""

        bid = branch.branch_id
        if self.branch_controller.get_code_base(bid) == "branch_workspace":
            existing = self.branch_workspaces.get(bid)
            if existing and os.path.isdir(existing):
                return existing
            logger.error(
                "Branch %s: verified branch workspace is unavailable; "
                "refusing champion fallback",
                bid,
            )
            return None
        workspace: str | None = None
        complete = False
        try:
            self.discard_branch_workspace(bid)
            with self.champion_lock:
                source_snapshot = self.get_champion().code_snapshot_path
            workspace = self.materializer.create_branch_workspace(bid, source_snapshot)
            self.branch_workspaces[bid] = workspace
            complete = True
            return workspace
        except Exception as exc:
            logger.error("Branch %s: workspace creation failed: %s", bid, exc)
            return None
        finally:
            if not complete:
                self.branch_workspaces.pop(bid, None)
                self._cleanup_branch_workspace_best_effort(bid)

    def apply_candidate_patch(
        self,
        base_workspace: str,
        patch: PatchProposal,
        *,
        hypothesis: HypothesisProposal | None = None,
        sync_registry: bool = False,
    ) -> CandidateWorkspace:
        """Apply a research patch to isolated staging, never the durable base."""

        before_sources = self._capture_before_sources(base_workspace, patch)
        candidate: str | None = None
        complete = False
        try:
            candidate = self.materializer.create_candidate_workspace(
                base_workspace,
            )
            self.materializer.apply_ephemeral_patch(candidate, patch)
            if sync_registry and hypothesis is not None:
                self.sync_pool_registry(candidate, hypothesis, patch)
            changed_files = tuple(
                dict.fromkeys(
                    change.file_path for change in patch_file_changes(patch)
                )
            )
            if self._file_content_differs(
                base_workspace,
                candidate,
                "registry.yaml",
            ):
                changed_files = tuple(
                    dict.fromkeys((*changed_files, "registry.yaml"))
                )
            value = CandidateWorkspace(
                workspace=candidate,
                source_digest=self.materializer.compute_code_hash(candidate),
                before_sources=before_sources,
                changed_files=changed_files,
            )
            complete = True
            return value
        finally:
            if candidate is not None and not complete:
                self._cleanup_candidate_best_effort(candidate)

    def create_reconcile_workspace(self, base_workspace: str) -> str:
        """Create the sole disposable staging tree for an accepted-chain replay."""

        return self.materializer.create_candidate_workspace(base_workspace)

    def apply_reconcile_change(
        self,
        workspace: str,
        patch: PatchProposal,
        *,
        hypothesis: HypothesisProposal,
    ) -> None:
        """Apply one accepted change in place without copying or hashing."""

        self.materializer.apply_ephemeral_patch(workspace, patch)
        self.sync_pool_registry(workspace, hypothesis, patch)

    def seal_reconcile_candidate(
        self,
        workspace: str,
        *,
        base_workspace: str,
        changed_files: tuple[str, ...],
    ) -> CandidateWorkspace:
        """Compute the replayed candidate's one pre-Verification digest."""

        cumulative_changed_files = tuple(dict.fromkeys(changed_files))
        if self._file_content_differs(
            base_workspace,
            workspace,
            "registry.yaml",
        ):
            cumulative_changed_files = tuple(
                dict.fromkeys((*cumulative_changed_files, "registry.yaml"))
            )
        return CandidateWorkspace(
            workspace=workspace,
            source_digest=self.materializer.compute_code_hash(workspace),
            changed_files=cumulative_changed_files,
        )

    def discard_reconcile_workspace(self, workspace: str) -> None:
        """Discard a replay staging tree before ownership reaches Decision."""

        self.materializer.cleanup_candidate_workspace(workspace)

    def reconcile_source_conflicts(
        self,
        workspace: str,
        accepted_change: AcceptedBranchChange,
    ) -> tuple[str, ...]:
        """Return touched paths whose exact pre-change source no longer matches."""

        touched_paths = tuple(
            normalize_relative_patch_path(change.file_path)
            for change in patch_file_changes(accepted_change.patch)
        )
        expected: dict[str, str | None] = {}
        malformed: set[str] = set()
        for before_source in accepted_change.before_sources:
            file_path = normalize_relative_patch_path(before_source.file_path)
            if file_path in expected:
                malformed.add(file_path)
            expected[file_path] = before_source.source
        if set(touched_paths) != set(expected) or len(touched_paths) != len(expected):
            malformed.update(set(touched_paths).symmetric_difference(expected))
            malformed.update(
                file_path
                for file_path in touched_paths
                if touched_paths.count(file_path) > 1
            )
        conflicts = set(malformed)
        for file_path in touched_paths:
            if file_path not in expected:
                conflicts.add(file_path)
                continue
            try:
                current_source = self._read_plain_source(workspace, file_path)
            except (OSError, UnicodeError, ValueError):
                conflicts.add(file_path)
                continue
            if current_source != expected[file_path]:
                conflicts.add(file_path)
        return tuple(sorted(conflicts))

    def accept_candidate(
        self,
        branch: Branch,
        candidate: CandidateWorkspace,
    ) -> str:
        """Bind an accepted candidate as the branch's read-only source."""

        bid = branch.branch_id
        previous = self.branch_workspaces.get(bid)
        previous_code_hash = branch.current_code_hash
        previous_updated_at = branch.updated_at
        try:
            self.materializer.freeze_snapshot(candidate.workspace)
            self.branch_workspaces[bid] = candidate.workspace
            self.branch_controller.accept_verified_code(bid, candidate.source_digest)
        except Exception:
            if previous is None:
                self.branch_workspaces.pop(bid, None)
            else:
                self.branch_workspaces[bid] = previous
            branch.current_code_hash = previous_code_hash
            branch.updated_at = previous_updated_at
            if candidate.workspace != previous:
                self._cleanup_candidate_best_effort(candidate.workspace)
            raise
        if previous and previous != candidate.workspace:
            try:
                self.materializer.cleanup(previous)
            except Exception as exc:
                logger.warning(
                    "Branch %s: replaced workspace cleanup failed at %s: %s",
                    bid,
                    previous,
                    exc,
                )
        return candidate.workspace

    def reject_candidate(
        self,
        candidate: CandidateWorkspace,
    ) -> None:
        """Discard a rejected staging tree without changing the durable branch."""

        self.materializer.cleanup_candidate_workspace(candidate.workspace)

    def verify_candidate(self, candidate: CandidateWorkspace) -> CandidateWorkspace:
        """Bind Verification to the exact staging value passed to Protocol.

        This is the single post-materialization content equality check.  Later
        Decision handling binds this already-verified value directly.
        """

        actual_hash = self.materializer.compute_code_hash(candidate.workspace)
        if actual_hash != candidate.source_digest:
            raise RuntimeError("candidate changed between Verification and Protocol")
        return candidate

    def discard_branch_workspace(self, branch_id: str) -> None:
        workspace = self.branch_workspaces.get(branch_id)
        if not workspace:
            self.materializer.cleanup_branch_workspace(branch_id)
            return
        self.materializer.cleanup(workspace)
        if self.branch_workspaces.get(branch_id) == workspace:
            self.branch_workspaces.pop(branch_id, None)

    def _cleanup_branch_workspace_best_effort(
        self,
        branch_id: str,
    ) -> None:
        try:
            self.materializer.cleanup_branch_workspace(branch_id)
        except Exception:
            logger.exception(
                "Branch %s: failed to clean interrupted workspace",
                branch_id,
            )

    def _cleanup_candidate_best_effort(self, workspace: str) -> None:
        try:
            self.materializer.cleanup_candidate_workspace(workspace)
        except Exception:
            logger.exception(
                "Failed to clean interrupted candidate workspace at %s",
                workspace,
            )

    def _capture_before_sources(
        self,
        workspace: str,
        patch: PatchProposal,
    ) -> tuple[AcceptedFileBeforeSource, ...]:
        captured: list[AcceptedFileBeforeSource] = []
        seen: set[str] = set()
        for change in patch_file_changes(patch):
            file_path = normalize_relative_patch_path(change.file_path)
            if file_path in seen:
                raise ValueError(f"patch repeats file_path: {file_path}")
            seen.add(file_path)
            captured.append(
                AcceptedFileBeforeSource(
                    file_path=file_path,
                    source=self._read_plain_source(workspace, file_path),
                )
            )
        return tuple(captured)

    @staticmethod
    def _read_plain_source(workspace: str, file_path: str) -> str | None:
        root = Path(workspace).resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"workspace does not exist: {workspace}")
        target = (root / normalize_relative_patch_path(file_path)).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"patch file_path escapes workspace: {file_path}") from exc
        if not target.exists():
            return None
        if not target.is_file():
            raise ValueError(f"patch target is not a regular file: {file_path}")
        return target.read_text(encoding="utf-8")

    @staticmethod
    def _file_content_differs(
        base_workspace: str,
        candidate_workspace: str,
        file_path: str,
    ) -> bool:
        """Compare one ordinary workspace file, including absence as a value."""

        def read_optional(root_value: str) -> bytes | None:
            root = Path(root_value).resolve()
            target = (root / file_path).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:  # pragma: no cover - fixed local path
                raise ValueError(f"workspace file escapes root: {file_path}") from exc
            if not target.exists():
                return None
            if not target.is_file():
                raise ValueError(f"workspace target is not a file: {file_path}")
            return target.read_bytes()

        return read_optional(base_workspace) != read_optional(candidate_workspace)

    def sync_pool_registry(
        self,
        workspace: str,
        hypothesis: HypothesisProposal,
        patch: PatchProposal,
    ) -> None:
        """Apply one accepted proposal to the candidate's ordinary operator pool."""

        from scion.runtime.pool_manager import PoolManager, read_registry

        registry_path = Path(workspace) / "registry.yaml"
        if registry_path.is_file():
            current_pool = read_registry(str(registry_path))
        else:
            current_pool = dict(self.get_champion().operator_pool)
        if not current_pool:
            return
        pool_mgr = PoolManager(current_pool)
        candidate_pool = pool_mgr.build_candidate_pool(
            current_pool,
            hypothesis,
            patch,
            workspace=workspace,
        )
        pool_mgr.export_registry(candidate_pool, workspace)
