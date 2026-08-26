"""Direct workspace materialization for V3 branch steps."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
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

    def cleanup_branch_workspace(self, branch_id: str) -> None: ...

    def claim_branch_workspace(self, branch_id: str, workspace: str) -> None: ...

    def apply_patch(self, workspace: str, patch: PatchProposal) -> str: ...

    def create_candidate_workspace(
        self,
        source_workspace: str,
    ) -> str: ...

    def cleanup_candidate_workspace(self, candidate_workspace: str) -> None: ...

    def claim_candidate_workspace(self, candidate_workspace: str) -> None: ...

    def cleanup_inflight_workspaces(self) -> None: ...

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
        self.discard_branch_workspace(bid)
        with self.champion_lock:
            source_snapshot = self.get_champion().code_snapshot_path
        workspace: str | None = None
        try:
            workspace = self.materializer.create_branch_workspace(bid, source_snapshot)
            self.branch_workspaces[bid] = workspace
            self._claim_branch_workspace(bid, workspace)
        except Exception as exc:
            self.branch_workspaces.pop(bid, None)
            try:
                self._cleanup_branch_workspace(bid, workspace)
            except Exception as cleanup_exc:
                raise RuntimeError(
                    "branch workspace cleanup failed after setup error"
                ) from cleanup_exc
            logger.error("Branch %s: workspace creation failed: %s", bid, exc)
            return None
        except BaseException:
            self.branch_workspaces.pop(bid, None)
            try:
                self._cleanup_branch_workspace(bid, workspace)
            except Exception:
                logger.exception("Branch %s: interrupted workspace cleanup failed", bid)
            raise
        return workspace

    def apply_candidate_patch(
        self,
        base_workspace: str,
        patch: PatchProposal,
        *,
        hypothesis: HypothesisProposal | None = None,
        sync_registry: bool = False,
        on_candidate_ready: Callable[[CandidateWorkspace], None] | None = None,
    ) -> CandidateWorkspace:
        """Apply a research patch to isolated staging, never the durable base."""

        candidate: str | None = None
        try:
            candidate = self.materializer.create_candidate_workspace(
                base_workspace,
            )
            code_hash = self.materializer.apply_patch(candidate, patch)
            if sync_registry and hypothesis is not None:
                self.sync_pool_registry(candidate, hypothesis, patch)
            value = CandidateWorkspace(
                workspace=candidate,
                source_digest=code_hash,
            )
            if on_candidate_ready is not None:
                on_candidate_ready(value)
        except BaseException:
            if candidate is not None:
                self.materializer.cleanup_candidate_workspace(candidate)
            else:
                self.discard_inflight_workspaces()
            raise
        return value

    def accept_candidate(
        self,
        branch: Branch,
        candidate: CandidateWorkspace,
    ) -> str:
        """Bind an accepted candidate as the branch's read-only source."""

        bid = branch.branch_id
        previous = self.branch_workspaces.get(bid)
        self.materializer.freeze_snapshot(candidate.workspace)
        self.branch_workspaces[bid] = candidate.workspace
        self.branch_controller.accept_verified_code(bid, candidate.source_digest)
        self._claim_candidate_workspace(candidate.workspace)
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
        workspace = self.branch_workspaces.pop(branch_id, None)
        if not workspace:
            cleanup = getattr(self.materializer, "cleanup_branch_workspace", None)
            if callable(cleanup):
                cleanup(branch_id)
            return
        self.materializer.cleanup(workspace)

    def discard_inflight_workspaces(self) -> None:
        """Remove unclaimed branch/candidate leases after a BaseException."""

        cleanup = getattr(self.materializer, "cleanup_inflight_workspaces", None)
        if callable(cleanup):
            cleanup()

    def _claim_branch_workspace(self, branch_id: str, workspace: str) -> None:
        claim = getattr(self.materializer, "claim_branch_workspace", None)
        if callable(claim):
            claim(branch_id, workspace)

    def _claim_candidate_workspace(self, workspace: str) -> None:
        claim = getattr(self.materializer, "claim_candidate_workspace", None)
        if callable(claim):
            claim(workspace)

    def _cleanup_branch_workspace(
        self,
        branch_id: str,
        workspace: str | None,
    ) -> None:
        cleanup = getattr(self.materializer, "cleanup_branch_workspace", None)
        if callable(cleanup):
            cleanup(branch_id)
        elif workspace is not None:
            self.materializer.cleanup(workspace)

    def sync_pool_registry(
        self,
        workspace: str,
        hypothesis: HypothesisProposal,
        patch: PatchProposal,
    ) -> None:
        """Build and export registry.yaml once in the candidate workspace."""

        champion = self.get_champion()
        if not champion.operator_pool:
            return
        from scion.runtime.pool_manager import PoolManager

        pool_mgr = PoolManager(champion.operator_pool)
        candidate_pool = pool_mgr.build_candidate_pool(
            champion.operator_pool,
            hypothesis,
            patch,
            workspace=workspace,
        )
        pool_mgr.export_registry(candidate_pool, workspace)
