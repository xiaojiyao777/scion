"""Main-thread commit service for completed weight optimization events."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Protocol

from scion.core.async_weight_opt import WeightOptCompletionEvent
from scion.core.models import Branch, ChampionState

logger = logging.getLogger(__name__)


class WeightOptEventSource(Protocol):
    latest_result: Any

    def drain_completed_events(self) -> list[WeightOptCompletionEvent]:
        ...


class WeightOptRegistry(Protocol):
    def record_weight_optimization(
        self,
        campaign_id: str,
        champion_version: int,
        result: Any,
    ) -> Any:
        ...

class WeightOptBranchController(Protocol):
    def get_active_branches(self) -> Iterable[Branch]:
        ...

    def mark_stale_for_weight_update(self, champion_version: int) -> list[str]:
        ...


@dataclass(frozen=True)
class WeightOptCommitter:
    """Apply completed weight optimization events at the campaign boundary.

    Async workers may create optimized snapshots, but they must not mutate
    champion or branch state. This service keeps those side effects explicit and
    testable outside ``CampaignManager``.
    """

    event_source: WeightOptEventSource
    champion_lock: Any
    get_champion: Callable[[], ChampionState]
    set_champion: Callable[[ChampionState], None]
    branch_controller: WeightOptBranchController
    registry: WeightOptRegistry
    campaign_id: str

    def drain(self) -> None:
        """Drain and commit all completed events from the coordinator."""
        for event in self.event_source.drain_completed_events():
            self.commit_event(event)

    def commit_event(self, event: WeightOptCompletionEvent) -> None:
        """Commit one completed event if it still matches the current champion."""
        self.event_source.latest_result = event.result
        try:
            self.registry.record_weight_optimization(
                campaign_id=self.campaign_id,
                champion_version=event.version,
                result=event.result,
            )
        except Exception as exc:
            logger.warning("Weight opt: failed to record result: %s", exc)

        if not event.improved:
            logger.info(
                "Weight opt complete for champion v%d (%.1f min) - no improvement",
                event.version,
                event.elapsed_minutes,
            )
            return

        if (
            event.new_revision is None
            or event.snapshot_path is None
            or event.operator_pool is None
        ):
            logger.warning(
                "Weight opt event for champion v%d missing optimized snapshot data",
                event.version,
            )
            return

        optimized_champion = self._build_optimized_champion(event)
        if optimized_champion is None:
            return

        logger.info(
            "Weight opt committed champion v%d_r%d (%.1f min)",
            event.version,
            event.new_revision,
            event.elapsed_minutes,
        )
        self._mark_branches_stale(event)

    def _build_optimized_champion(
        self,
        event: WeightOptCompletionEvent,
    ) -> ChampionState | None:
        with self.champion_lock:
            current = self.get_champion()
            if (
                current.version != event.version
                or current.weight_revision != event.base_weight_revision
            ):
                logger.warning(
                    "Weight opt for champion v%d_r%d discarded — current champion is v%d_r%d",
                    event.version,
                    event.new_revision,
                    current.version,
                    current.weight_revision,
                )
                return None
            optimized_champion = ChampionState(
                version=current.version,
                operator_pool=event.operator_pool,
                code_snapshot_path=event.snapshot_path,
                promoted_at=current.promoted_at,
                weight_revision=event.new_revision,
            )
            self.set_champion(optimized_champion)
            return optimized_champion

    def _mark_branches_stale(self, event: WeightOptCompletionEvent) -> None:
        # Stage-aware stale: do not interrupt in-flight frozen holdout, but
        # reconcile all other active branches before more validation/frozen budget.
        try:
            stale_weight_ids = self.branch_controller.mark_stale_for_weight_update(
                event.version
            )
            if stale_weight_ids:
                logger.info(
                    "Weight opt: marked %d branches stale for re-screening",
                    len(stale_weight_ids),
                )
        except Exception as exc:
            logger.warning("Weight opt: failed to mark branches stale: %s", exc)
