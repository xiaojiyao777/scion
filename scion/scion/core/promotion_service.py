"""Promotion service shell for champion snapshot prepare and commit."""
from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping, Optional, Protocol

from scion.core.models import ChampionState, OperatorConfig
from scion.runtime.pool_manager import read_registry, read_weights
from scion.runtime.workspace import _make_tree_writable


class SnapshotMaterializer(Protocol):
    def freeze_snapshot(self, path: str) -> None:
        ...

    def compute_snapshot_hash(self, workspace: str) -> str:
        ...


@dataclass(frozen=True)
class PromotionRequest:
    branch_id: str
    candidate_workspace: str
    champion_version: int
    champion_weight_revision: int
    solver_config_hash: str = ""
    previous_operator_pool: Mapping[str, OperatorConfig] = field(default_factory=dict)
    promoted_at: Optional[str] = None

    @classmethod
    def from_champion(
        cls,
        *,
        branch_id: str,
        candidate_workspace: str,
        champion: ChampionState,
        promoted_at: Optional[str] = None,
    ) -> "PromotionRequest":
        return cls(
            branch_id=branch_id,
            candidate_workspace=candidate_workspace,
            champion_version=champion.version,
            champion_weight_revision=champion.weight_revision,
            solver_config_hash=champion.solver_config_hash,
            previous_operator_pool=champion.operator_pool,
            promoted_at=promoted_at,
        )


@dataclass(frozen=True)
class PromotionPlan:
    branch_id: str
    candidate_snapshot_ref: str
    new_champion_version: int
    registry_hash: Optional[str]
    weight_revision: int
    champion: ChampionState
    current_weights: Mapping[str, float] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "current_weights", MappingProxyType(dict(self.current_weights)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class PromotionCommitResult:
    branch_id: str
    champion_version: int
    stale_branch_ids: tuple[str, ...]


PrepareHook = Callable[[PromotionRequest], PromotionPlan]
PlanHook = Callable[[PromotionPlan], None]
ChampionHook = Callable[[ChampionState], None]
PoolHook = Callable[[Mapping[str, OperatorConfig]], None]
StaleHook = Callable[[int], Iterable[str]]
BranchHook = Callable[[str, ChampionState], None]


class PromotionService:
    """Prepare immutable champion snapshots separately from state mutation.

    The default prepare path mirrors the current campaign promotion snapshot
    flow using injected filesystem dependencies. Campaign-specific mutable
    effects are intentionally commit hooks so integration can preserve existing
    lineage, hypothesis, and branch-store semantics.
    """

    def __init__(
        self,
        *,
        snapshot_root: str | os.PathLike[str] | None = None,
        materializer: SnapshotMaterializer | None = None,
        prepare_snapshot: PrepareHook | None = None,
        before_commit: PlanHook | None = None,
        commit_champion: ChampionHook | None = None,
        commit_pool: PoolHook | None = None,
        persist_champion: ChampionHook | None = None,
        promote_branch: BranchHook | None = None,
        mark_stale: StaleHook | None = None,
        persist_branch_states: Callable[[], None] | None = None,
        on_promoted_branch: BranchHook | None = None,
        after_commit: PlanHook | None = None,
        read_registry_fn: Callable[[str], Mapping[str, OperatorConfig]] = read_registry,
        read_weights_fn: Callable[[str], Mapping[str, float]] = read_weights,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._snapshot_root = Path(snapshot_root) if snapshot_root is not None else None
        self._materializer = materializer
        self._prepare_snapshot = prepare_snapshot
        self._before_commit = before_commit
        self._commit_champion = commit_champion
        self._commit_pool = commit_pool
        self._persist_champion = persist_champion
        self._promote_branch = promote_branch
        self._mark_stale = mark_stale
        self._persist_branch_states = persist_branch_states
        self._on_promoted_branch = on_promoted_branch
        self._after_commit = after_commit
        self._read_registry = read_registry_fn
        self._read_weights = read_weights_fn
        self._clock = clock or (lambda: datetime.now().isoformat())

    def prepare(self, request: PromotionRequest) -> PromotionPlan:
        """Create and freeze a candidate champion snapshot.

        This method may mutate only snapshot filesystem state. It does not call
        any champion, pool, branch, stale, or lineage commit hooks.
        """
        if self._prepare_snapshot is not None:
            return self._prepare_snapshot(request)
        return self._prepare_from_workspace(request)

    def commit(self, plan: PromotionPlan) -> PromotionCommitResult:
        """Commit a prepared promotion plan through injected mutation hooks."""
        if self._persist_champion is not None:
            self._persist_champion(plan.champion)
        if self._before_commit is not None:
            self._before_commit(plan)
        if self._commit_champion is not None:
            self._commit_champion(plan.champion)
        if self._commit_pool is not None:
            self._commit_pool(plan.champion.operator_pool)
        if self._promote_branch is not None:
            self._promote_branch(plan.branch_id, plan.champion)

        stale_branch_ids: tuple[str, ...] = ()
        if self._mark_stale is not None:
            stale_branch_ids = tuple(self._mark_stale(plan.new_champion_version))
        if self._persist_branch_states is not None:
            self._persist_branch_states()
        if self._on_promoted_branch is not None:
            self._on_promoted_branch(plan.branch_id, plan.champion)

        result = PromotionCommitResult(
            branch_id=plan.branch_id,
            champion_version=plan.new_champion_version,
            stale_branch_ids=stale_branch_ids,
        )
        if self._after_commit is not None:
            self._after_commit(plan)
        return result

    def _prepare_from_workspace(self, request: PromotionRequest) -> PromotionPlan:
        if self._snapshot_root is None:
            raise ValueError("snapshot_root is required when prepare_snapshot is not injected")
        if self._materializer is None:
            raise ValueError("materializer is required when prepare_snapshot is not injected")

        source = Path(request.candidate_workspace)
        if not source.is_dir():
            raise FileNotFoundError(
                f"candidate_workspace not found for branch {request.branch_id}: {source}"
            )

        new_version = request.champion_version + 1
        snapshot_path = self._snapshot_root / f"champion_v{new_version}"

        try:
            if snapshot_path.exists():
                _make_tree_writable(snapshot_path)
                shutil.rmtree(snapshot_path)
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, snapshot_path, symlinks=False)
            _make_tree_writable(snapshot_path)
        except Exception as exc:
            raise RuntimeError(f"mutable champion staging failed: {exc}") from exc

        registry_path = snapshot_path / "registry.yaml"
        current_weights: Mapping[str, float] = {}
        if registry_path.exists():
            try:
                current_weights = self._read_weights(str(registry_path))
            except Exception:
                current_weights = {}

        try:
            self._materializer.freeze_snapshot(str(snapshot_path))
        except Exception as exc:
            raise RuntimeError(f"freeze champion snapshot failed: {exc}") from exc

        if registry_path.exists():
            try:
                operator_pool = dict(self._read_registry(str(registry_path)))
            except Exception as exc:
                raise RuntimeError(f"read champion registry failed: {exc}") from exc
        else:
            operator_pool = dict(request.previous_operator_pool)

        snapshot_hash = self._materializer.compute_snapshot_hash(str(snapshot_path))
        registry_hash = _sha256_file(registry_path) if registry_path.exists() else None
        champion = ChampionState(
            version=new_version,
            operator_pool=operator_pool,
            solver_config_hash=request.solver_config_hash,
            code_snapshot_path=str(snapshot_path),
            code_snapshot_hash=snapshot_hash,
            promoted_at=request.promoted_at or self._clock(),
            weight_revision=request.champion_weight_revision,
        )
        return PromotionPlan(
            branch_id=request.branch_id,
            candidate_snapshot_ref=str(snapshot_path),
            new_champion_version=new_version,
            registry_hash=registry_hash,
            weight_revision=request.champion_weight_revision,
            champion=champion,
            current_weights=current_weights,
        )


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()
