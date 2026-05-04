"""Workspace and patch materialization lifecycle service."""
from __future__ import annotations

import logging
import os
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any, Callable, MutableMapping, Protocol

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
        if not force_champion and self.branch_controller.get_code_base(bid) == "branch_workspace":
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
        code_hash = self.materializer.apply_patch(workspace, patch)
        if remember_patch:
            self.branch_patches[branch.branch_id] = patch
        if sync_registry and hypothesis is not None:
            self.sync_pool_registry(workspace, hypothesis, patch)
        self.branch_controller.record_candidate_code(branch.branch_id, code_hash)
        return AppliedPatch(workspace=workspace, code_hash=code_hash, patch=patch)

    def record_verification_pass(self, branch: Branch, code_hash: str) -> None:
        self.branch_controller.record_verification_pass(branch.branch_id, code_hash)

    def discard_branch_workspace(self, branch_id: str) -> None:
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
