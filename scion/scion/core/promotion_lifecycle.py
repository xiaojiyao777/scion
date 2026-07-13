"""Campaign promotion lifecycle boundary."""
from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping, MutableMapping, Sequence

from scion.core.branch import BranchController, StateTransitionError
from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    Decision,
    HypothesisRecord,
)
from scion.core.promotion_service import PromotionPlan, PromotionRequest, PromotionService

logger = logging.getLogger(__name__)


@dataclass
class PromotionLifecycleService:
    """Own promotion lifecycle side effects outside ``CampaignManager``."""

    promotion_service: PromotionService
    branch_controller: BranchController
    branch_workspaces: Mapping[str, str]
    branch_current_hypothesis: MutableMapping[str, HypothesisRecord]
    champion_lock: Any
    get_champion: Callable[[], ChampionState]
    set_champion: Callable[[ChampionState], None]
    get_champion_store: Callable[[], Any]
    hypothesis_store: Any
    get_weight_opt_coord: Callable[[], Any]
    get_weight_opt_committer: Callable[[], Any]
    get_parameter_search_execution: Callable[[], str]
    promotion_dossier_ref_for: Callable[[int], str | None]

    def on_promote(self, branch: Branch) -> None:
        """Compatibility entry for callers that already hold a frozen branch."""
        try:
            self.require_promotable_branch(branch)
        except StateTransitionError as exc:
            logger.error(
                "Branch %s: promote precondition failed: %s",
                branch.branch_id,
                exc,
            )
            return
        try:
            plan = self.prepare_promoted_champion(branch)
        except Exception as exc:
            logger.error("Branch %s: promote prepare failed: %s", branch.branch_id, exc)
            return
        try:
            self.commit_promote_plan(plan)
        except Exception as exc:
            logger.error("Branch %s: promote commit failed: %s", branch.branch_id, exc)

    def prepare_promoted_champion(self, branch: Branch) -> PromotionPlan:
        """Build and freeze the champion snapshot before semantic side effects."""
        bid = branch.branch_id
        workspace = self.branch_workspaces.get(bid)
        if workspace is None:
            raise FileNotFoundError(f"no workspace found for promoted branch {bid}")

        with self.champion_lock:
            champion_for_prepare = self.get_champion()
        plan = self.promotion_service.prepare(
            PromotionRequest.from_champion(
                branch_id=bid,
                candidate_workspace=workspace,
                champion=champion_for_prepare,
            )
        )
        dossier_ref = self.promotion_dossier_ref_for(plan.new_champion_version)
        if dossier_ref:
            plan = replace(
                plan,
                champion=replace(plan.champion, promotion_dossier_ref=dossier_ref),
            )
        return plan

    def require_promotable_branch(self, branch: Branch) -> None:
        current = self.branch_controller.get_branch(branch.branch_id)
        if current.state != BranchState.FROZEN_TESTING:
            raise StateTransitionError(
                f"promotion requires frozen branch state, got {current.state.value}"
            )

    def commit_promote_plan(self, plan: PromotionPlan) -> None:
        """Commit a prepared champion snapshot and launch follow-up work."""
        result = self.promotion_service.commit(plan)
        logger.info(
            "Promoted branch %s to champion v%d; marked %d branches stale",
            result.branch_id,
            result.champion_version,
            len(result.stale_branch_ids),
        )
        self.start_weight_optimization(plan)


    def commit_promoted_champion_state(self, new_champion: ChampionState) -> None:
        """Install the promoted champion in campaign memory."""
        with self.champion_lock:
            self.set_champion(new_champion)

    def transition_promoted_branch(
        self,
        branch_id: str,
        new_champion: ChampionState,
    ) -> None:
        """Transition the promoted branch after champion persistence succeeds."""
        branch = self.branch_controller.get_branch(branch_id)
        if branch.state != BranchState.PROMOTED:
            self.branch_controller.apply_decision(branch_id, Decision.PROMOTE)
        h_record = self.branch_current_hypothesis.get(branch_id)
        if h_record is not None:
            self.hypothesis_store.mark_status(h_record.hypothesis_id, "promoted")
            self.branch_current_hypothesis.pop(branch_id, None)

    def persist_promoted_champion(self, new_champion: ChampionState) -> None:
        """Persist the promoted champion before mutable side effects."""
        self.get_champion_store().promote(new_champion)

    def start_weight_optimization(self, plan: PromotionPlan) -> None:
        """Launch or run weight optimization for an already committed champion."""
        new_champion = plan.champion
        new_version = new_champion.version
        weight_opt_coord = self.get_weight_opt_coord()
        try:
            if self.get_parameter_search_execution() == "sync":
                logger.info(
                    "Champion v%d: running weight optimization synchronously",
                    new_version,
                )
                weight_opt_coord.run_for_promoted_champion_sync(
                    plan.candidate_snapshot_ref,
                    new_version,
                    dict(plan.current_weights),
                    base_weight_revision=new_champion.weight_revision,
                )
                self.drain_weight_opt_events()
            else:
                weight_opt_coord.spawn_for_promoted_champion(
                    plan.candidate_snapshot_ref,
                    new_version,
                    dict(plan.current_weights),
                    base_weight_revision=new_champion.weight_revision,
                )
        except Exception as exc:
            logger.warning(
                "Failed to run weight optimization for champion v%d: %s",
                new_version,
                exc,
            )

    def drain_weight_opt_events(self) -> None:
        """Apply completed weight-optimization events on the campaign thread."""
        self.get_weight_opt_committer().drain()
