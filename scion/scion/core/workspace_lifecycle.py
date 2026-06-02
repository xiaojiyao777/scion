"""Workspace and patch materialization lifecycle service."""
from __future__ import annotations

import logging
import os
import shutil
import hashlib
import json
import uuid
from contextlib import nullcontext
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, MutableMapping, Protocol

from scion.core.branch_hygiene import branch_requires_repair_focus
from scion.core.models import (
    Branch,
    BranchCheckpointCounters,
    BranchCheckpointDiagnostics,
    BranchCheckpointEvidence,
    BranchCheckpointRecord,
    ChampionState,
    HypothesisProposal,
    PatchProposal,
)

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
    record: BranchCheckpointRecord
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
class BranchCheckpointRegistry:
    """Bounded in-memory checkpoint index keyed by branch lineage.

    This is intentionally generic and local to workspace lifecycle. It preserves
    the v0.4 restore path while giving later rollback/scheduler phases a stable
    checkpoint inventory to report and score.
    """

    max_records_per_lineage: int = 2
    _records_by_lineage: dict[str, list[BranchWorkspaceCheckpoint]] = field(
        default_factory=dict
    )

    def put(
        self, checkpoint: BranchWorkspaceCheckpoint
    ) -> tuple[BranchWorkspaceCheckpoint, ...]:
        lineage_id = checkpoint.record.lineage_id
        records = [
            existing
            for existing in self._records_by_lineage.get(lineage_id, [])
            if existing.record.checkpoint_id != checkpoint.record.checkpoint_id
        ]
        records.append(checkpoint)
        retained_ids = self._retained_checkpoint_ids(records)
        retained = [
            existing
            for existing in records
            if existing.record.checkpoint_id in retained_ids
        ]
        evicted = [
            existing
            for existing in records
            if existing.record.checkpoint_id not in retained_ids
        ]
        self._records_by_lineage[lineage_id] = retained
        return tuple(evicted)

    def replace_record(
        self, checkpoint: BranchWorkspaceCheckpoint
    ) -> None:
        lineage_id = checkpoint.record.lineage_id
        records = self._records_by_lineage.get(lineage_id, [])
        self._records_by_lineage[lineage_id] = [
            checkpoint
            if existing.record.checkpoint_id == checkpoint.record.checkpoint_id
            else existing
            for existing in records
        ]

    def records_for_lineage(
        self, lineage_id: str
    ) -> tuple[BranchWorkspaceCheckpoint, ...]:
        return tuple(self._records_by_lineage.get(lineage_id, ()))

    def records_for_branch(
        self, branch_id: str
    ) -> tuple[BranchWorkspaceCheckpoint, ...]:
        return tuple(
            checkpoint
            for records in self._records_by_lineage.values()
            for checkpoint in records
            if checkpoint.record.branch_id == branch_id
        )

    def best_quality_checkpoint(
        self, lineage_id: str
    ) -> BranchWorkspaceCheckpoint | None:
        records = self._records_by_lineage.get(lineage_id, [])
        if not records:
            return None
        return max(
            records,
            key=lambda checkpoint: (
                _checkpoint_tier_rank(checkpoint.record.screening_tier),
                checkpoint.record.created_at,
            ),
        )

    def last_valid_checkpoint(
        self, lineage_id: str
    ) -> BranchWorkspaceCheckpoint | None:
        records = self._records_by_lineage.get(lineage_id, [])
        if not records:
            return None
        return max(records, key=lambda checkpoint: checkpoint.record.created_at)

    def forget_branch(
        self, branch_id: str
    ) -> tuple[BranchWorkspaceCheckpoint, ...]:
        removed: list[BranchWorkspaceCheckpoint] = []
        for lineage_id, records in list(self._records_by_lineage.items()):
            retained: list[BranchWorkspaceCheckpoint] = []
            for checkpoint in records:
                if checkpoint.record.branch_id == branch_id:
                    removed.append(checkpoint)
                else:
                    retained.append(checkpoint)
            if retained:
                self._records_by_lineage[lineage_id] = retained
            else:
                self._records_by_lineage.pop(lineage_id, None)
        return tuple(removed)

    def summary(self) -> dict[str, Any]:
        return {
            lineage_id: {
                "checkpoint_count": len(records),
                "best_quality_checkpoint_id": (
                    best.record.checkpoint_id if best else None
                ),
                "last_valid_checkpoint_id": (
                    last.record.checkpoint_id if last else None
                ),
                "records": [
                    {
                        "checkpoint_id": checkpoint.record.checkpoint_id,
                        "branch_id": checkpoint.record.branch_id,
                        "branch_code_status": (
                            checkpoint.record.branch_code_status
                        ),
                        "screening_tier": checkpoint.record.screening_tier,
                        "code_hash": checkpoint.record.code_hash,
                        "patch_digest": checkpoint.record.patch_digest,
                    }
                    for checkpoint in records
                ],
            }
            for lineage_id, records in self._records_by_lineage.items()
            for best in [self.best_quality_checkpoint(lineage_id)]
            for last in [self.last_valid_checkpoint(lineage_id)]
        }

    def _retained_checkpoint_ids(
        self, records: list[BranchWorkspaceCheckpoint]
    ) -> set[str]:
        if self.max_records_per_lineage <= 0:
            return set()
        ranked = sorted(
            records,
            key=lambda checkpoint: (
                _checkpoint_tier_rank(checkpoint.record.screening_tier),
                checkpoint.record.created_at,
            ),
            reverse=True,
        )
        newest = sorted(
            records,
            key=lambda checkpoint: checkpoint.record.created_at,
            reverse=True,
        )
        retained: list[BranchWorkspaceCheckpoint] = []
        for candidate in ranked[:1] + newest[:1] + newest[1:]:
            if candidate in retained:
                continue
            retained.append(candidate)
            if len(retained) >= self.max_records_per_lineage:
                break
        return {checkpoint.record.checkpoint_id for checkpoint in retained}


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
    branch_checkpoint_registry: BranchCheckpointRegistry = field(
        default_factory=BranchCheckpointRegistry
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

    def capture_branch_checkpoint(self, branch: Branch) -> bool:
        """Capture the current retained branch workspace for prompt/rollback metadata."""
        workspace = self.branch_workspaces.get(branch.branch_id)
        if not workspace:
            return False
        return self._capture_branch_checkpoint(branch, workspace)

    def record_verification_pass(self, branch: Branch, code_hash: str) -> None:
        self.branch_controller.record_verification_pass(branch.branch_id, code_hash)

    def restore_branch_checkpoint(
        self,
        branch: Branch,
        *,
        reason: str = "regressed_followup",
        reason_codes: tuple[str, ...] = (),
    ) -> bool:
        """Restore the last protected branch workspace checkpoint.

        This is used when a same-branch follow-up passes syntax/contract/
        verification but later screening shows that the new head regressed.
        Verification updates the clean code hash before screening, so the prior
        screened checkpoint must be captured before patch application.
        """
        checkpoint = self.branch_checkpoints.pop(branch.branch_id, None)
        if checkpoint is None:
            lineage_id = _branch_lineage_id(branch)
            checkpoint = (
                self.branch_checkpoint_registry.best_quality_checkpoint(lineage_id)
                or self.branch_checkpoint_registry.last_valid_checkpoint(lineage_id)
            )
        if checkpoint is None:
            return False
        src = Path(checkpoint.checkpoint_workspace)
        dest = Path(checkpoint.workspace)
        if not src.is_dir():
            return False
        if dest.exists():
            self.materializer.cleanup(str(dest))
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest, symlinks=False)
        self.branch_workspaces[branch.branch_id] = str(dest)
        branch.current_code_hash = checkpoint.current_code_hash
        branch.last_clean_code_hash = checkpoint.last_clean_code_hash
        branch.branch_code_status = checkpoint.branch_code_status
        branch.last_screening_feedback_tier = checkpoint.last_screening_feedback_tier
        branch.last_telemetry_outcome = checkpoint.last_telemetry_outcome
        branch.branch_mechanism_ids = checkpoint.branch_mechanism_ids
        branch.rollback_count += 1
        branch.last_rollback_reason = reason
        branch.best_quality_checkpoint_id = (
            checkpoint.record.checkpoint_id
            if checkpoint.record.screening_tier == "weak_positive"
            else branch.best_quality_checkpoint_id
        )
        branch.last_valid_checkpoint_id = checkpoint.record.checkpoint_id
        if checkpoint.patch is None:
            self.branch_patches.pop(branch.branch_id, None)
        else:
            self.branch_patches[branch.branch_id] = checkpoint.patch
        updated = _checkpoint_with_rollback(
            checkpoint,
            rollback_count=branch.rollback_count,
            reason_codes=reason_codes or (reason,),
        )
        self.branch_checkpoint_registry.replace_record(updated)
        return True

    def discard_branch_workspace(self, branch_id: str) -> None:
        checkpoint = self.branch_checkpoints.pop(branch_id, None)
        checkpoints = list(self.branch_checkpoint_registry.forget_branch(branch_id))
        if checkpoint is not None:
            checkpoints.append(checkpoint)
        seen_paths: set[str] = set()
        for checkpoint in checkpoints:
            checkpoint_workspace = checkpoint.checkpoint_workspace
            if checkpoint_workspace in seen_paths:
                continue
            seen_paths.add(checkpoint_workspace)
            try:
                shutil.rmtree(checkpoint_workspace)
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

    def _capture_branch_checkpoint(self, branch: Branch, workspace: str) -> bool:
        if not _should_checkpoint_branch(branch):
            return False
        src = Path(workspace)
        if not src.is_dir():
            return False
        patch = self.branch_patches.get(branch.branch_id)
        existing = _matching_current_checkpoint(
            self.branch_checkpoint_registry,
            branch,
            patch=patch,
        )
        if existing is not None:
            self._sync_branch_checkpoint_metadata(branch)
            return True
        checkpoint_id = str(uuid.uuid4())
        dest = Path(f"{workspace}.checkpoint.{checkpoint_id[:8]}")
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
            return False
        record = _checkpoint_record(
            branch,
            checkpoint_id=checkpoint_id,
            workspace_ref=str(dest),
            patch=patch,
        )
        checkpoint = BranchWorkspaceCheckpoint(
            record=record,
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
            patch=patch,
        )
        evicted = self.branch_checkpoint_registry.put(checkpoint)
        self._sync_branch_checkpoint_metadata(branch)
        self._cleanup_evicted_checkpoints(evicted)
        return True

    def _sync_branch_checkpoint_metadata(self, branch: Branch) -> None:
        lineage_id = _branch_lineage_id(branch)
        best_quality = self.branch_checkpoint_registry.best_quality_checkpoint(
            lineage_id
        )
        last_valid = self.branch_checkpoint_registry.last_valid_checkpoint(lineage_id)
        branch.best_quality_checkpoint_id = (
            best_quality.record.checkpoint_id if best_quality else None
        )
        branch.last_valid_checkpoint_id = (
            last_valid.record.checkpoint_id if last_valid else None
        )
        selected = best_quality or last_valid
        if selected is not None:
            self.branch_checkpoints[branch.branch_id] = selected

    def _cleanup_evicted_checkpoints(
        self,
        checkpoints: tuple[BranchWorkspaceCheckpoint, ...],
    ) -> None:
        active_paths = {
            checkpoint.checkpoint_workspace
            for checkpoint in self.branch_checkpoints.values()
        }
        for checkpoint in checkpoints:
            if checkpoint.checkpoint_workspace in active_paths:
                continue
            try:
                shutil.rmtree(checkpoint.checkpoint_workspace)
            except Exception:
                pass

    def checkpoint_summary(self) -> dict[str, Any]:
        return self.branch_checkpoint_registry.summary()


def _should_checkpoint_branch(branch: Branch) -> bool:
    if not getattr(branch, "last_clean_code_hash", None):
        return False
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    checkpoint_statuses = {
        "clean",
        "active_weak_positive",
        "active_marginal",
        "active_no_effect",
    }
    checkpoint_tiers = {"weak_positive", "marginal", "no_effect", "last_valid"}
    return status in checkpoint_statuses or tier in checkpoint_tiers


def _branch_lineage_id(branch: Branch) -> str:
    return str(getattr(branch, "lineage_id", None) or branch.branch_id)


def _matching_current_checkpoint(
    registry: BranchCheckpointRegistry,
    branch: Branch,
    *,
    patch: PatchProposal | None,
) -> BranchWorkspaceCheckpoint | None:
    current_hash = getattr(branch, "current_code_hash", None)
    if not current_hash:
        return None
    patch_digest = _patch_digest(patch)
    for checkpoint in registry.records_for_lineage(_branch_lineage_id(branch)):
        if checkpoint.record.branch_id != branch.branch_id:
            continue
        if checkpoint.record.code_hash != current_hash:
            continue
        if checkpoint.record.patch_digest != patch_digest:
            continue
        return checkpoint
    return None


def _checkpoint_record(
    branch: Branch,
    *,
    checkpoint_id: str,
    workspace_ref: str,
    patch: PatchProposal | None,
) -> BranchCheckpointRecord:
    parent_checkpoint_id = (
        getattr(branch, "best_quality_checkpoint_id", None)
        or getattr(branch, "last_valid_checkpoint_id", None)
    )
    return BranchCheckpointRecord(
        checkpoint_id=checkpoint_id,
        branch_id=branch.branch_id,
        lineage_id=_branch_lineage_id(branch),
        parent_checkpoint_id=parent_checkpoint_id,
        workspace_ref=workspace_ref,
        patch_digest=_patch_digest(patch),
        code_hash=getattr(branch, "current_code_hash", None),
        branch_code_status=str(
            getattr(branch, "branch_code_status", "clean") or "clean"
        ),
        screening_tier=_screening_tier(branch),
        evidence=_checkpoint_evidence(branch),
        diagnostics=_checkpoint_diagnostics(branch),
        counters=BranchCheckpointCounters(
            rollback_count=int(getattr(branch, "rollback_count", 0) or 0),
            stale_count=_count_failure_code(branch, "STALE"),
        ),
    )


def _checkpoint_with_rollback(
    checkpoint: BranchWorkspaceCheckpoint,
    *,
    rollback_count: int,
    reason_codes: tuple[str, ...],
) -> BranchWorkspaceCheckpoint:
    diagnostics = checkpoint.record.diagnostics
    merged_reason_codes = tuple(
        dict.fromkeys(
            tuple(diagnostics.lifecycle_action_reason_codes or ())
            + tuple(reason_codes or ())
        )
    )
    record = replace(
        checkpoint.record,
        diagnostics=replace(
            diagnostics,
            lifecycle_action_reason_codes=merged_reason_codes,
        ),
        counters=replace(
            checkpoint.record.counters,
            rollback_count=rollback_count,
        ),
    )
    return replace(checkpoint, record=record)


def _patch_digest(patch: PatchProposal | None) -> str | None:
    if patch is None:
        return None
    payload = []
    for change in patch.iter_file_changes():
        payload.append(
            {
                "file_path": change.file_path,
                "action": change.action,
                "code_sha256": hashlib.sha256(
                    (change.code_content or "").encode("utf-8")
                ).hexdigest(),
            }
        )
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _screening_tier(branch: Branch) -> str:
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    if tier:
        return tier
    status = str(getattr(branch, "branch_code_status", "") or "")
    if status == "active_weak_positive":
        return "weak_positive"
    if status == "active_marginal":
        return "marginal"
    if status == "active_no_effect":
        return "no_effect"
    if "regress" in status:
        return "regression"
    if status == "clean":
        return "last_valid"
    return "unknown"


def _checkpoint_tier_rank(tier: str | None) -> int:
    return {
        "promotable": 7,
        "weak_positive": 6,
        "marginal": 5,
        "last_valid": 4,
        "no_effect": 4,
        "diagnostic": 3,
        "regression": 2,
        "invalid": 1,
    }.get(str(tier or ""), 0)


def _checkpoint_evidence(branch: Branch) -> BranchCheckpointEvidence:
    source = _checkpoint_metadata_source(branch)
    return BranchCheckpointEvidence(
        wins=_int_value(source, "wins", "case_wins", "pair_wins"),
        losses=_int_value(source, "losses", "case_losses", "pair_losses"),
        ties=_int_value(source, "ties", "case_ties", "pair_ties"),
        median_delta=_float_value(source, "median_delta", "screening_median_delta"),
        ci_low=_float_value(source, "ci_low", "screening_ci_low"),
        ci_high=_float_value(source, "ci_high", "screening_ci_high"),
        runtime_ratio_median=_float_value(source, "runtime_ratio_median"),
        runtime_regression_rate=_float_value(source, "runtime_regression_rate"),
    )


def _checkpoint_diagnostics(branch: Branch) -> BranchCheckpointDiagnostics:
    source = _checkpoint_metadata_source(branch)
    gate_codes = _string_tuple(
        source.get("gate_observation_reason_codes")
        or source.get("decision_reason_codes")
        or source.get("reason_codes")
    )
    lifecycle_codes = _string_tuple(
        source.get("lifecycle_action_reason_codes")
        or source.get("decision_reason_codes")
        or source.get("reason_codes")
    )
    return BranchCheckpointDiagnostics(
        gate_observation_reason_codes=gate_codes,
        lifecycle_action_reason_codes=lifecycle_codes,
        telemetry_outcome=getattr(branch, "last_telemetry_outcome", None),
    )


def _checkpoint_metadata_source(branch: Branch) -> dict[str, Any]:
    evidence = getattr(branch, "branch_evidence_summary", {}) or {}
    if isinstance(evidence, dict) and evidence:
        return dict(evidence)
    block = getattr(branch, "last_branch_lifecycle_policy_block", {}) or {}
    return dict(block) if isinstance(block, dict) else {}


def _int_value(source: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = source.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _float_value(source: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = source.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value if str(item))
    return (str(value),)


def _count_failure_code(branch: Branch, code: str) -> int:
    return sum(1 for item in getattr(branch, "failure_codes", []) if item == code)
