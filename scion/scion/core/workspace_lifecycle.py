"""Workspace and patch materialization lifecycle service."""
from __future__ import annotations

import logging
import os
import shutil
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, MutableMapping, Protocol

from scion.core.branch_hygiene import branch_requires_repair_focus
from scion.core.models import Branch, ChampionState, HypothesisProposal, PatchProposal

logger = logging.getLogger(__name__)


class WorkspaceMaterializerLike(Protocol):
    def create_branch_workspace(self, branch_id: str, source_snapshot: str) -> str:
        ...

    def apply_patch(self, workspace: str, patch: PatchProposal) -> str:
        ...

    def cleanup(self, workspace: str) -> None:
        ...


class BranchControllerLike(Protocol):
    def get_code_base(self, branch_id: str) -> str:
        ...

    def record_candidate_code(self, branch_id: str, code_hash: str) -> None:
        ...

    def record_verification_pass(self, branch_id: str, code_hash: str) -> None:
        ...


@dataclass(frozen=True)
class AppliedPatch:
    workspace: str
    code_hash: str
    patch: PatchProposal


@dataclass(frozen=True)
class BranchWorkspaceCheckpoint:
    workspace: str
    checkpoint_workspace: str
    current_code_hash: str | None
    last_clean_code_hash: str | None
    branch_code_status: str
    last_screening_feedback_tier: str | None
    last_telemetry_outcome: str | None
    branch_mechanism_ids: tuple[str, ...]
    patch: PatchProposal | None


@dataclass
class WorkspaceLifecycleService:
    """Own workspace setup, patch materialization, and registry sync.

    CampaignManager decides when a branch should run; this service only performs
    the filesystem/code-hash side effects for the chosen branch.
    """

    materializer: WorkspaceMaterializerLike
    branch_controller: BranchControllerLike
    branch_workspaces: MutableMapping[str, str]
    branch_patches: MutableMapping[str, PatchProposal]
    champion_lock: Any
    get_champion: Callable[[], ChampionState]
    branch_checkpoints: MutableMapping[str, BranchWorkspaceCheckpoint] = field(
        default_factory=dict
    )

    @classmethod
    def from_owner(cls, owner: Any) -> "WorkspaceLifecycleService":
        return cls(
            materializer=owner._materializer,
            branch_controller=owner._branch_ctrl,
            branch_workspaces=owner._branch_workspaces,
            branch_patches=owner._branch_patches,
            champion_lock=getattr(owner, "_champion_lock", nullcontext()),
            get_champion=lambda: owner._champion,
        )

    def setup_workspace(
        self,
        branch: Branch,
        *,
        force_champion: bool = False,
    ) -> str | None:
        """Return a workspace for the branch, creating one from champion if needed."""
        bid = branch.branch_id
        if branch_requires_repair_focus(branch):
            self.discard_branch_workspace(bid)
            force_champion = True
        if (
            not force_champion
            and self.branch_controller.get_code_base(bid) == "branch_workspace"
        ):
            existing = self.branch_workspaces.get(bid)
            if existing and os.path.isdir(existing):
                return existing

        self.discard_branch_workspace(bid)

        with self.champion_lock:
            source_snapshot = self.get_champion().code_snapshot_path
        try:
            workspace = self.materializer.create_branch_workspace(bid, source_snapshot)
            self.branch_workspaces[bid] = workspace
            return workspace
        except Exception as exc:
            logger.error("Branch %s: workspace creation failed: %s", bid, exc)
            return None

    def apply_patch(
        self,
        branch: Branch,
        workspace: str,
        patch: PatchProposal,
        *,
        hypothesis: HypothesisProposal | None = None,
        remember_patch: bool = False,
        sync_registry: bool = False,
    ) -> AppliedPatch:
        """Apply a patch and record the candidate code hash before verification."""
        if remember_patch:
            self._capture_branch_checkpoint(branch, workspace)
        code_hash = self.materializer.apply_patch(workspace, patch)
        if remember_patch:
            self.branch_patches[branch.branch_id] = patch
        if sync_registry and hypothesis is not None:
            self.sync_pool_registry(workspace, hypothesis, patch)
        self.branch_controller.record_candidate_code(branch.branch_id, code_hash)
        return AppliedPatch(workspace=workspace, code_hash=code_hash, patch=patch)

    def record_verification_pass(self, branch: Branch, code_hash: str) -> None:
        self.branch_controller.record_verification_pass(branch.branch_id, code_hash)

    def restore_branch_checkpoint(self, branch: Branch) -> bool:
        """Restore the last protected branch workspace checkpoint.

        This is used when a same-branch follow-up passes syntax/contract/
        verification but later screening shows that the new head regressed.
        Verification updates the clean code hash before screening, so the prior
        screened checkpoint must be captured before patch application.
        """
        checkpoint = self.branch_checkpoints.pop(branch.branch_id, None)
        if checkpoint is None:
            return False
        src = Path(checkpoint.checkpoint_workspace)
        dest = Path(checkpoint.workspace)
        if not src.is_dir():
            return False
        try:
            if dest.exists():
                self.materializer.cleanup(str(dest))
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest, symlinks=False)
            self.branch_workspaces[branch.branch_id] = str(dest)
            branch.current_code_hash = checkpoint.current_code_hash
            branch.last_clean_code_hash = checkpoint.last_clean_code_hash
            branch.branch_code_status = checkpoint.branch_code_status
            branch.last_screening_feedback_tier = (
                checkpoint.last_screening_feedback_tier
            )
            branch.last_telemetry_outcome = checkpoint.last_telemetry_outcome
            branch.branch_mechanism_ids = checkpoint.branch_mechanism_ids
            if checkpoint.patch is None:
                self.branch_patches.pop(branch.branch_id, None)
            else:
                self.branch_patches[branch.branch_id] = checkpoint.patch
            return True
        finally:
            try:
                if src.exists():
                    shutil.rmtree(src)
            except Exception:
                pass

    def discard_branch_workspace(self, branch_id: str) -> None:
        checkpoint = self.branch_checkpoints.pop(branch_id, None)
        if checkpoint is not None:
            try:
                shutil.rmtree(checkpoint.checkpoint_workspace)
            except Exception:
                pass
        workspace = self.branch_workspaces.pop(branch_id, None)
        if not workspace:
            return
        try:
            self.materializer.cleanup(workspace)
        except Exception:
            pass

    def sync_pool_registry(
        self,
        workspace: str,
        hypothesis: HypothesisProposal,
        patch: PatchProposal,
    ) -> None:
        """Rebuild and export registry.yaml in workspace via PoolManager."""
        champion = self.get_champion()
        if not champion.operator_pool:
            logger.debug("_sync_pool_registry skipped: champion pool is empty")
            return
        try:
            from scion.runtime.pool_manager import PoolManager

            pool_mgr = PoolManager(champion.operator_pool)
            candidate_pool = pool_mgr.build_candidate_pool(
                champion.operator_pool,
                hypothesis,
                patch,
                workspace=workspace,
            )
            pool_mgr.export_registry(candidate_pool, workspace)
        except Exception as exc:
            logger.debug("_sync_pool_registry failed (non-fatal): %s", exc)

    def _capture_branch_checkpoint(self, branch: Branch, workspace: str) -> None:
        if not _should_checkpoint_branch(branch):
            return
        src = Path(workspace)
        if not src.is_dir():
            return
        dest = Path(f"{workspace}.checkpoint")
        try:
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest, symlinks=False)
        except Exception as exc:
            logger.debug(
                "Branch %s: checkpoint capture failed: %s",
                branch.branch_id,
                exc,
            )
            return
        self.branch_checkpoints[branch.branch_id] = BranchWorkspaceCheckpoint(
            workspace=str(src),
            checkpoint_workspace=str(dest),
            current_code_hash=getattr(branch, "current_code_hash", None),
            last_clean_code_hash=getattr(branch, "last_clean_code_hash", None),
            branch_code_status=str(
                getattr(branch, "branch_code_status", "clean") or "clean"
            ),
            last_screening_feedback_tier=getattr(
                branch,
                "last_screening_feedback_tier",
                None,
            ),
            last_telemetry_outcome=getattr(branch, "last_telemetry_outcome", None),
            branch_mechanism_ids=tuple(
                getattr(branch, "branch_mechanism_ids", ()) or ()
            ),
            patch=self.branch_patches.get(branch.branch_id),
        )


def _should_checkpoint_branch(branch: Branch) -> bool:
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    return status == "active_weak_positive" or tier == "weak_positive"
