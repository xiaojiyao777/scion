"""Direct champion promotion from an accepted candidate workspace."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Iterable, Mapping, Protocol

from scion.core.models import ChampionState, OperatorConfig
from scion.runtime.pool_manager import read_registry, read_weights
from scion.runtime.workspace import _make_tree_writable


class SnapshotMaterializer(Protocol):
    def freeze_snapshot(self, path: str) -> None: ...


@dataclass(frozen=True)
class PromotionResult:
    """Values produced by one completed promotion operation."""

    champion: ChampionState
    current_weights: Mapping[str, float] = field(default_factory=dict)
    stale_branch_ids: tuple[str, ...] = ()
    bookkeeping_failures: tuple["PromotionBookkeepingFailure", ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "current_weights", MappingProxyType(dict(self.current_weights))
        )


@dataclass(frozen=True)
class PromotionBookkeepingFailure:
    """Non-reversing failure observed after champion commit."""

    operation: str
    exception_type: str
    detail: str


class PromotionCommittedError(RuntimeError):
    """Promotion committed, but required post-commit recovery did not close."""

    def __init__(
        self,
        *,
        champion_version: int,
        operation: str,
        detail: str,
    ) -> None:
        super().__init__(detail)
        self.champion_version = champion_version
        self.operation = operation


ChampionHook = Callable[[ChampionState], None]
StaleHook = Callable[[int], Iterable[str]]
BranchHook = Callable[[str, ChampionState], None]


class PromotionService:
    """Promote one accepted branch in one operation."""

    def __init__(
        self,
        *,
        snapshot_root: str | os.PathLike[str] | None = None,
        materializer: SnapshotMaterializer | None = None,
        set_champion: ChampionHook | None = None,
        promote_branch: BranchHook | None = None,
        mark_stale: StaleHook | None = None,
        read_registry_fn: Callable[[str], Mapping[str, OperatorConfig]] = read_registry,
        read_weights_fn: Callable[[str], Mapping[str, float]] = read_weights,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._snapshot_root = Path(snapshot_root) if snapshot_root is not None else None
        self._materializer = materializer
        self._set_champion = set_champion
        self._promote_branch = promote_branch
        self._mark_stale = mark_stale
        self._read_registry = read_registry_fn
        self._read_weights = read_weights_fn
        self._clock = clock or (lambda: datetime.now().isoformat())

    def promote(
        self,
        *,
        branch_id: str,
        candidate_workspace: str,
        champion: ChampionState,
    ) -> PromotionResult:
        """Materialize and install one promoted champion, stopping on failure."""
        if self._snapshot_root is None:
            raise ValueError("snapshot_root is required")
        if self._materializer is None:
            raise ValueError("materializer is required")

        source = Path(candidate_workspace)
        if not source.is_dir():
            raise FileNotFoundError(
                f"candidate_workspace not found for branch {branch_id}: {source}"
            )

        new_version = champion.version + 1
        snapshot_path = self._snapshot_root / f"champion_v{new_version}"

        try:
            if snapshot_path.exists():
                raise FileExistsError(
                    f"champion snapshot already exists: {snapshot_path}"
                )
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, snapshot_path, symlinks=False)
            _make_tree_writable(snapshot_path)
        except Exception as exc:
            raise RuntimeError(f"mutable champion staging failed: {exc}") from exc

        registry_path = snapshot_path / "registry.yaml"
        current_weights: Mapping[str, float] = {}
        if registry_path.exists():
            current_weights = self._read_weights(str(registry_path))

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
            operator_pool = dict(champion.operator_pool)

        promoted_champion = ChampionState(
            version=new_version,
            operator_pool=operator_pool,
            code_snapshot_path=str(snapshot_path),
            promoted_at=self._clock(),
            weight_revision=champion.weight_revision,
        )

        if self._set_champion is not None:
            self._set_champion(promoted_champion)

        # Returning from set_champion is the commit point.  Later bookkeeping
        # failures are diagnostics on a real promotion and must never be
        # reclassified as an uncommitted PROMOTION_FAILED attempt.
        bookkeeping_failures: list[PromotionBookkeepingFailure] = []
        if self._promote_branch is not None:
            try:
                self._promote_branch(branch_id, promoted_champion)
            except Exception as exc:
                bookkeeping_failures.append(
                    PromotionBookkeepingFailure(
                        operation="promote_branch",
                        exception_type=type(exc).__name__,
                        detail=str(exc),
                    )
                )
        stale_branch_ids: tuple[str, ...] = ()
        if self._mark_stale is not None:
            try:
                stale_branch_ids = tuple(
                    self._mark_stale(promoted_champion.version)
                )
            except Exception as exc:
                bookkeeping_failures.append(
                    PromotionBookkeepingFailure(
                        operation="mark_stale",
                        exception_type=type(exc).__name__,
                        detail=str(exc),
                    )
                )
        return PromotionResult(
            champion=promoted_champion,
            current_weights=current_weights,
            stale_branch_ids=stale_branch_ids,
            bookkeeping_failures=tuple(bookkeeping_failures),
        )
