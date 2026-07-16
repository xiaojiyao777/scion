"""Workspace and patch materialization lifecycle service."""

from __future__ import annotations

import logging
import os
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, MutableMapping, Protocol

from scion.core.models import (
    Branch,
    ChampionState,
    HypothesisProposal,
    PatchProposal,
)

logger = logging.getLogger(__name__)


class WorkspaceMaterializerLike(Protocol):
    def create_branch_workspace(self, branch_id: str, source_snapshot: str) -> str: ...

    def apply_patch(self, workspace: str, patch: PatchProposal) -> str: ...

    def create_candidate_workspace(
        self,
        branch_id: str,
        source_workspace: str,
    ) -> str: ...

    def promote_candidate_workspace(
        self,
        candidate_workspace: str,
        branch_id: str,
        *,
        base_code_hash: str | None = None,
        hypothesis_id: str | None = None,
        terminalize_hypothesis_on_rollback: bool = True,
        promotion_kind: str = "explore",
    ) -> str: ...

    def finalize_candidate_promotion(self, branch_id: str) -> None: ...

    def cleanup_candidate_workspace(self, candidate_workspace: str) -> None: ...

    def compute_code_hash(self, workspace: str) -> str: ...

    def compute_snapshot_hash(self, workspace: str) -> str: ...

    def cleanup(self, workspace: str) -> None: ...


class BranchControllerLike(Protocol):
    def get_code_base(self, branch_id: str) -> str: ...

    def record_candidate_code(self, branch_id: str, code_hash: str) -> None: ...

    def record_verification_pass(self, branch_id: str, code_hash: str) -> None: ...


@dataclass(frozen=True)
class AppliedPatch:
    workspace: str
    code_hash: str
    patch: PatchProposal


@dataclass(frozen=True)
class PendingCandidate:
    workspace: str
    code_hash: str
    patch: PatchProposal
    remember_patch: bool


@dataclass(frozen=True)
class CandidateCleanupReport:
    workspace: str
    cleaned: bool
    cleanup_error: str | None = None


@dataclass
class WorkspaceLifecycleService:
    """Perform filesystem and code-hash effects for the selected branch."""

    materializer: WorkspaceMaterializerLike
    branch_controller: BranchControllerLike
    branch_workspaces: MutableMapping[str, str]
    branch_patches: MutableMapping[str, PatchProposal]
    champion_lock: Any
    get_champion: Callable[[], ChampionState]
    pending_candidates: MutableMapping[str, PendingCandidate] = field(
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
        """Reuse a verified branch workspace or materialize from the champion."""

        bid = branch.branch_id
        if (
            not force_champion
            and self.branch_controller.get_code_base(bid) == "branch_workspace"
        ):
            existing = self.branch_workspaces.get(bid)
            if existing and os.path.isdir(existing):
                actual_hash = self.materializer.compute_code_hash(existing)
                expected_hash = branch.last_clean_code_hash
                if actual_hash != expected_hash:
                    logger.error(
                        "Branch %s: verified workspace hash mismatch "
                        "(expected=%s actual=%s); refusing reuse",
                        bid,
                        expected_hash,
                        actual_hash,
                    )
                    return None
                return existing
            logger.error(
                "Branch %s: verified branch workspace is unavailable; "
                "refusing champion fallback",
                bid,
            )
            return None
        self.discard_branch_workspace(bid)
        with self.champion_lock:
            source_snapshot = self.get_champion().code_snapshot_path
        try:
            workspace = self.materializer.create_branch_workspace(bid, source_snapshot)
        except Exception as exc:
            logger.error("Branch %s: workspace creation failed: %s", bid, exc)
            return None
        self.branch_workspaces[bid] = workspace
        return workspace

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

    def apply_candidate_patch(
        self,
        branch: Branch,
        base_workspace: str,
        patch: PatchProposal,
        *,
        hypothesis: HypothesisProposal | None = None,
        remember_patch: bool = False,
        sync_registry: bool = False,
    ) -> AppliedPatch:
        """Apply a research patch to isolated staging, never the durable base."""

        bid = branch.branch_id
        if bid in self.pending_candidates:
            raise RuntimeError(f"Branch {bid} already has a pending candidate")
        candidate = self.materializer.create_candidate_workspace(
            bid,
            base_workspace,
        )
        try:
            code_hash = self.materializer.apply_patch(candidate, patch)
            if sync_registry and hypothesis is not None:
                self.sync_pool_registry(candidate, hypothesis, patch)
        except BaseException:
            self._cleanup_candidate_best_effort(candidate, bid)
            branch.current_code_hash = branch.last_clean_code_hash
            branch.branch_code_status = "clean"
            branch.updated_at = datetime.now()
            raise
        self.pending_candidates[bid] = PendingCandidate(
            workspace=candidate,
            code_hash=code_hash,
            patch=patch,
            remember_patch=remember_patch,
        )
        try:
            self.branch_controller.record_candidate_code(bid, code_hash)
        except BaseException:
            self._rollback_pending_candidate(
                branch,
                pending=self.pending_candidates[bid],
            )
            raise
        return AppliedPatch(workspace=candidate, code_hash=code_hash, patch=patch)

    def promote_verified_candidate(
        self,
        branch: Branch,
        code_hash: str,
        candidate_workspace: str,
        hypothesis_id: str | None = None,
        *,
        terminalize_hypothesis_on_rollback: bool = True,
        promotion_kind: str = "explore",
    ) -> str:
        """Commit exactly one verified candidate as the durable branch source."""

        bid = branch.branch_id
        pending = self.pending_candidates.get(bid)
        if pending is None:
            raise RuntimeError(f"Branch {bid} has no pending candidate")
        previous_last_clean_hash = branch.last_clean_code_hash
        try:
            self._require_pending_candidate(bid, candidate_workspace)
            if pending.code_hash != code_hash:
                raise RuntimeError(
                    f"Branch {bid} candidate hash changed before promotion"
                )
            actual_hash = self.materializer.compute_code_hash(candidate_workspace)
            if actual_hash != code_hash:
                raise RuntimeError(
                    f"Branch {bid} candidate workspace hash mismatch before promotion"
                )
            # Commit the in-memory identity first.  It is not durable until the
            # caller persists the branch, and it can still be rolled back if the
            # filesystem promotion fails.
            self.branch_controller.record_verification_pass(bid, code_hash)
            durable = self.materializer.promote_candidate_workspace(
                candidate_workspace,
                bid,
                base_code_hash=previous_last_clean_hash,
                hypothesis_id=hypothesis_id,
                terminalize_hypothesis_on_rollback=(
                    terminalize_hypothesis_on_rollback
                ),
                promotion_kind=promotion_kind,
            )
        except BaseException:
            branch.last_clean_code_hash = previous_last_clean_hash
            self._rollback_pending_candidate(branch, pending=pending)
            raise
        self.pending_candidates.pop(bid, None)
        self.branch_workspaces[bid] = durable
        if pending.remember_patch:
            self.branch_patches[bid] = pending.patch
        return durable

    def finalize_candidate_promotion(self, branch: Branch) -> None:
        self.materializer.finalize_candidate_promotion(branch.branch_id)

    def reject_candidate(
        self,
        branch: Branch,
        candidate_workspace: str,
    ) -> CandidateCleanupReport:
        """Discard a rejected staging tree and restore the clean hash identity."""

        bid = branch.branch_id
        pending = self._require_pending_candidate(bid, candidate_workspace)
        return self._rollback_pending_candidate(branch, pending=pending)

    def release_rejected_candidate_binding(
        self,
        branch: Branch,
        candidate_workspace: str,
    ) -> None:
        """Drop process-local staging ownership after durable cleanup commits."""

        bid = branch.branch_id
        pending = self._require_pending_candidate(bid, candidate_workspace)
        if os.path.exists(pending.workspace):
            raise RuntimeError(
                f"Branch {bid}: rejected candidate still exists after completion"
            )
        # ResearchRejectionCompletionStore has already installed and persisted
        # the exact target Branch.  This method owns only the process-local
        # staging binding; mutating Branch here would drift it from that commit.
        self.pending_candidates.pop(bid, None)

    def _rollback_pending_candidate(
        self,
        branch: Branch,
        *,
        pending: PendingCandidate,
    ) -> CandidateCleanupReport:
        """Restore semantic clean state even when staging cleanup leaves debris."""

        bid = branch.branch_id
        self.pending_candidates.pop(bid, None)
        branch.current_code_hash = branch.last_clean_code_hash
        branch.branch_code_status = "clean"
        branch.updated_at = datetime.now()
        return self._cleanup_candidate_best_effort(pending.workspace, bid)

    def _cleanup_candidate_best_effort(
        self,
        candidate_workspace: str,
        branch_id: str,
    ) -> CandidateCleanupReport:
        try:
            self.materializer.cleanup_candidate_workspace(candidate_workspace)
        except Exception as exc:
            logger.warning(
                "Branch %s: candidate cleanup left debris at %s: %s",
                branch_id,
                candidate_workspace,
                exc,
            )
            return CandidateCleanupReport(
                workspace=candidate_workspace,
                cleaned=False,
                cleanup_error=f"{type(exc).__name__}: {exc}",
            )
        return CandidateCleanupReport(
            workspace=candidate_workspace,
            cleaned=True,
        )

    def _require_pending_candidate(
        self,
        branch_id: str,
        candidate_workspace: str,
    ) -> PendingCandidate:
        pending = self.pending_candidates.get(branch_id)
        if pending is None:
            raise RuntimeError(f"Branch {branch_id} has no pending candidate")
        if os.path.realpath(pending.workspace) != os.path.realpath(candidate_workspace):
            raise RuntimeError(f"Branch {branch_id} candidate workspace changed")
        return pending

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
        """Rebuild and export registry.yaml in the branch workspace."""

        champion = self.get_champion()
        if not champion.operator_pool:
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
            logger.debug("pool registry sync failed (non-fatal): %s", exc)
