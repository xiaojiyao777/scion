"""Evaluation-stage orchestration boundary."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, MutableMapping, Optional, Tuple

from scion.core.branch import StateTransitionError
from scion.core.branch_lifecycle_policy import BranchLifecyclePolicy
from scion.core.decision_coordinator import DecisionCoordinator
from scion.core.evaluation_pipeline import EvaluationPipeline, EvaluationRequest
from scion.core.features import BudgetState, SafeFeatureExtractor
from scion.core.frozen_budget import FROZEN_BUDGET_EXHAUSTED
from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    ChampionState,
    Decision,
    EvalStats,
    ExperimentStage,
    FailureEvent,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    ProtocolResult,
)
from scion.core.telemetry_validation import screened_experiment_effective

logger = logging.getLogger(__name__)


@dataclass
class EvaluationOrchestrator:
    """Own protocol execution glue, decision coordination, and soft-abandon."""

    branch_controller: Any
    champion_lock: Any
    get_champion: Callable[[], ChampionState]
    branch_patches: MutableMapping[str, PatchProposal]
    branch_workspaces: MutableMapping[str, str]
    branch_hypotheses: MutableMapping[str, HypothesisProposal]
    branch_current_hypothesis: MutableMapping[str, HypothesisRecord]
    experiment_protocol_provider: Callable[[], Any]
    feature_extractor: SafeFeatureExtractor
    get_budget: Callable[[], BudgetState]
    decision_coordinator: DecisionCoordinator
    decision_reason_codes: MutableMapping[str, Tuple[str, ...]]
    campaign_id: str
    registry: Any
    materializer: Any
    hypothesis_store: Any
    persist_branch_state: Callable[[str], None]
    begin_status_progress: Callable[..., None]
    end_status_progress: Callable[[], None]
    handle_failure: Callable[[Branch, FailureEvent], None]
    increment_experiment_count: Callable[[], None]
    increment_budget_used: Callable[[], None]
    increment_soft_abandon_streak: Callable[[], None]
    increment_telemetry_failed_count: Callable[[], None] = lambda: None
    frozen_budget_ledger: Any | None = None
    branch_zero_win_streaks: MutableMapping[str, int] = field(default_factory=dict)
    branch_lifecycle_policy: BranchLifecyclePolicy = field(
        default_factory=BranchLifecyclePolicy
    )

    def evaluate(
        self,
        branch: Branch,
        workspace: str,
        hypothesis: HypothesisProposal,
    ) -> Tuple[Decision, Optional[ProtocolResult], CanaryResult]:
        bid = branch.branch_id
        stage = self.branch_controller.next_stage(bid)

        with self.champion_lock:
            champion_for_eval = self.get_champion()
        champion_workspace = champion_for_eval.code_snapshot_path
        branch.weight_revision = getattr(champion_for_eval, "weight_revision", 0)
        self.persist_branch_state(bid)

        protocol = self.experiment_protocol_provider()
        if stage == ExperimentStage.FROZEN and self.frozen_budget_ledger is not None:
            budget_decision = self.frozen_budget_ledger.try_consume(branch_id=bid)
            if not budget_decision.allowed:
                self.decision_reason_codes[bid] = ("FROZEN_BUDGET_EXHAUSTED",)
                return Decision.ABANDON, _frozen_budget_protocol_result(
                    used=budget_decision.used,
                    limit=budget_decision.limit,
                ), CanaryResult(passed=True, reason=FROZEN_BUDGET_EXHAUSTED)

        expand, expand_round = self._prepare_expand(branch, protocol)
        request = EvaluationRequest(
            branch_id=bid,
            branch_state=branch.state,
            candidate_workspace=workspace,
            champion_workspace=champion_workspace,
            hypothesis_action=hypothesis.action,
            expand=expand,
            expand_round=expand_round,
            selected_surface=hypothesis.change_locus,
            expected_telemetry=dict(getattr(hypothesis, "expected_telemetry", {}) or {}),
            mechanism_changes=tuple(getattr(hypothesis, "mechanism_changes", ()) or ()),
            protected_objectives=tuple(
                getattr(hypothesis, "protected_objectives", ()) or ()
            ),
            patch=self.branch_patches.get(bid),
            retry_count=branch.retry_count,
            screening_expand_count=branch.screening_expand_count,
            validation_expand_count=branch.validation_expand_count,
            failure_codes=tuple(branch.failure_codes),
        )
        pipeline = EvaluationPipeline(
            experiment_protocol=protocol,
            feature_extractor=self.feature_extractor,
            budget_provider=self.get_budget,
        )

        try:
            if protocol is not None:
                self.begin_status_progress(
                    branch=branch,
                    stage=stage,
                    hypothesis=hypothesis,
                    expand=expand,
                    expand_round=expand_round,
                )
                try:
                    evaluation = pipeline.evaluate(request)
                finally:
                    self.end_status_progress()
            else:
                evaluation = pipeline.evaluate(request)
            if screened_experiment_effective(evaluation.protocol_result):
                self.increment_experiment_count()
                self.increment_budget_used()
            elif evaluation.protocol_result is not None:
                self.increment_telemetry_failed_count()
        except Exception as exc:
            logger.error("Branch %s: experiment failed: %s", bid, exc)
            self.handle_failure(branch, FailureEvent(category="evaluation", detail=str(exc)))
            self.decision_reason_codes[bid] = ("EVALUATION_FAILED",)
            return Decision.ABANDON, None, CanaryResult(
                passed=True,
                reason="evaluation failed",
            )

        protocol_result = evaluation.protocol_result
        canary_result = evaluation.canary_result
        features = evaluation.decision_features
        coordinated = self.decision_coordinator.decide(features)
        self.decision_reason_codes[bid] = coordinated.reason_codes
        logger.info(
            "Branch %s: features wr=%s md=%s stage=%s -> decision=%s rule=%s reasons=%s",
            bid,
            features.win_rate,
            features.median_delta,
            features.stage,
            coordinated.decision.value,
            coordinated.rule,
            coordinated.reason_codes,
        )

        decision = coordinated.decision
        if (
            decision == Decision.CONTINUE_EXPLORE
            and features.win_rate is not None
            and not features.telemetry_validation_repairable
        ):
            lifecycle = self.branch_lifecycle_policy.decide(
                features,
                current_zero_win_streak=self.branch_zero_win_streaks.get(bid, 0),
            )
            if lifecycle.reason_codes:
                self.decision_reason_codes[bid] = _merge_reason_codes(
                    coordinated.reason_codes,
                    lifecycle.reason_codes,
                )
            if lifecycle.soft_abandon:
                logger.info(
                    "Branch %s: win_rate=%.2f lifecycle=%s -> soft_abandon",
                    bid,
                    features.win_rate,
                    lifecycle.reason_codes,
                )
                self.branch_zero_win_streaks[bid] = lifecycle.next_zero_win_streak
                self._record_soft_abandon_event(
                    bid,
                    features.win_rate,
                    lifecycle.reason_codes,
                )
                self.increment_soft_abandon_streak()
                self.apply_soft_abandon(
                    bid,
                    branch,
                    self.branch_current_hypothesis.get(bid),
                )
                return Decision.ABANDON, protocol_result, canary_result
            elif features.win_rate > 0.6:
                logger.info(
                    "Branch %s: win_rate=%.2f > 0.6 -> high_potential (continue_explore)",
                    bid,
                    features.win_rate,
                )

        return decision, protocol_result, canary_result

    def apply_soft_abandon(
        self,
        branch_id: str,
        branch: Branch,
        h_record: Optional[HypothesisRecord],
    ) -> None:
        """Discard a no-signal branch without incrementing hard stagnation."""
        workspace = self.branch_workspaces.pop(branch_id, None)
        if workspace:
            try:
                self.materializer.archive_workspace(workspace, branch_id)
            except Exception as exc:
                logger.debug("Branch %s: soft_abandon archive failed: %s", branch_id, exc)
            try:
                self.materializer.cleanup(workspace)
            except Exception:
                pass

        self.branch_hypotheses.pop(branch_id, None)
        if h_record is not None:
            self.hypothesis_store.mark_status(h_record.hypothesis_id, "rejected")
            self.branch_current_hypothesis.pop(branch_id, None)

        try:
            self.branch_controller.apply_decision(branch_id, Decision.ABANDON)
        except StateTransitionError as exc:
            logger.debug("Branch %s: soft_abandon apply_decision failed: %s", branch_id, exc)
        self.persist_branch_state(branch_id)

    @staticmethod
    def _prepare_expand(branch: Branch, protocol: Any) -> tuple[bool, int]:
        expand = False
        expand_round = 1
        if protocol is None:
            return expand, expand_round

        expand = branch.state in (
            BranchState.EXPLORE_EXPAND,
            BranchState.VALIDATING_EXPAND,
        )
        if branch.state == BranchState.EXPLORE_EXPAND:
            branch.screening_expand_count += 1
            expand_round = branch.screening_expand_count
        elif branch.state == BranchState.VALIDATING_EXPAND:
            branch.validation_expand_count += 1
            expand_round = branch.validation_expand_count
        return expand, expand_round

    def _record_soft_abandon_event(
        self,
        branch_id: str,
        win_rate: float,
        reason_codes: tuple[str, ...],
    ) -> None:
        try:
            self.registry.record_event(
                {
                    "campaign_id": self.campaign_id,
                    "branch_id": branch_id,
                    "timestamp": datetime.now().isoformat(),
                    "event_kind": "abandon_fast",
                    "reason": reason_codes[0] if reason_codes else "low_signal",
                    "reason_codes": list(reason_codes),
                    "win_rate": win_rate,
                    "abandon_type": "soft_lifecycle",
                }
            )
        except Exception:
            pass


def _merge_reason_codes(
    first: tuple[str, ...],
    second: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(dict.fromkeys([*first, *second]))


def _frozen_budget_protocol_result(*, used: int, limit: int) -> ProtocolResult:
    return ProtocolResult(
        stage=ExperimentStage.FROZEN,
        stats=EvalStats(
            n_cases=0,
            wins=0,
            losses=0,
            ties=0,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
        ),
        gate_outcome="fail",
        reason_codes=(FROZEN_BUDGET_EXHAUSTED,),
        exposed_summary=(
            "stage=frozen blocked=true "
            f"reason={FROZEN_BUDGET_EXHAUSTED} used={used} limit={limit}"
        ),
        raw_metrics_ref="",
    )
