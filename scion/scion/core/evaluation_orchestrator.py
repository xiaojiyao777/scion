"""Evaluation-stage orchestration boundary."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from typing import Any, Callable, MutableMapping, Optional, Tuple

from scion.core.branch_lifecycle_policy import (
    decision_features_signal_signature,
    BRANCH_LIFECYCLE_ARCHIVE_LINEAGE,
    BRANCH_LIFECYCLE_PARK_LINEAGE,
    BRANCH_LIFECYCLE_RETAIN_CHECKPOINT,
    BRANCH_LIFECYCLE_ROLLBACK_TO_CHECKPOINT,
    SCREENING_TELEMETRY_DIAGNOSTIC_RETRY,
    VALIDATION_TELEMETRY_DIAGNOSTIC_RETRY,
    TELEMETRY_DIAGNOSTIC_STREAK_EXHAUSTED,
)
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
    DecisionFeatures,
    DecisionLifecycleAction,
    EvalStats,
    ExperimentStage,
    FailureEvent,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    ProtocolResult,
)
from scion.core.runtime_budget_diagnostics import runtime_budget_diagnostic_reason_codes
from scion.core.telemetry_validation import (
    TELEMETRY_EFFECT_ZERO_DIAGNOSTIC,
    formal_telemetry_guard_failed,
    screened_experiment_effective,
)

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
    require_experiment_protocol: bool = False
    branch_zero_win_streaks: MutableMapping[str, int] = field(default_factory=dict)
    branch_telemetry_diagnostic_streaks: MutableMapping[str, int] = field(
        default_factory=dict
    )
    decision_lifecycle_actions: MutableMapping[str, DecisionLifecycleAction] = field(
        default_factory=dict
    )
    decision_lifecycle_policy_evidence: MutableMapping[str, dict[str, Any]] = field(
        default_factory=dict
    )
    decision_lifecycle_bookkeeping: MutableMapping[str, dict[str, Any]] = field(
        default_factory=dict
    )
    decision_layer_sources: MutableMapping[str, str] = field(default_factory=dict)
    decision_engine_reason_codes: MutableMapping[str, Tuple[str, ...]] = field(
        default_factory=dict
    )
    diagnostic_reason_codes: MutableMapping[str, Tuple[str, ...]] = field(
        default_factory=dict
    )
    bypass_reason_codes: MutableMapping[str, Tuple[str, ...]] = field(
        default_factory=dict
    )
    lifecycle_reason_codes: MutableMapping[str, Tuple[str, ...]] = field(
        default_factory=dict
    )

    def evaluate(
        self,
        branch: Branch,
        workspace: str,
        hypothesis: HypothesisProposal,
    ) -> Tuple[Optional[Decision], Optional[ProtocolResult], CanaryResult]:
        bid = branch.branch_id
        self.decision_lifecycle_actions[bid] = ""
        self.decision_lifecycle_policy_evidence.pop(bid, None)
        self.decision_lifecycle_bookkeeping.pop(bid, None)
        self._set_reason_provenance(
            bid,
            source=None,
            decision_engine=(),
            diagnostics=(),
            bypass=(),
            lifecycle=(),
        )
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
                self._set_reason_provenance(
                    bid,
                    source="frozen_budget_bypass",
                    bypass=("FROZEN_BUDGET_EXHAUSTED",),
                )
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
            force_fresh_champion=bool(
                getattr(branch, "fresh_runtime_replay_step", False)
            ),
        )
        pipeline = EvaluationPipeline(
            experiment_protocol=protocol,
            require_experiment_protocol=self.require_experiment_protocol,
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
            if formal_telemetry_guard_failed(evaluation.protocol_result):
                self.increment_telemetry_failed_count()
        except Exception as exc:
            logger.error("Branch %s: experiment failed: %s", bid, exc)
            self.handle_failure(branch, FailureEvent(category="evaluation", detail=str(exc)))
            self.decision_reason_codes[bid] = ("EVALUATION_FAILED",)
            self._set_reason_provenance(
                bid,
                source="evaluation_bypass",
                bypass=("EVALUATION_FAILED",),
            )
            return None, _evaluation_failure_protocol_result(stage=stage), CanaryResult(
                passed=False,
                reason="evaluation failed",
            )

        protocol_result = evaluation.protocol_result
        canary_result = evaluation.canary_result
        features = _with_lifecycle_inputs(
            evaluation.decision_features,
            branch=branch,
            current_zero_win_streak=self.branch_zero_win_streaks.get(bid, 0),
            current_telemetry_diagnostic_streak=(
                self.branch_telemetry_diagnostic_streaks.get(bid, 0)
            ),
        )
        coordinated = self.decision_coordinator.decide(features)
        self.decision_reason_codes[bid] = coordinated.reason_codes
        self.decision_lifecycle_actions[bid] = getattr(
            coordinated,
            "lifecycle_action",
            "",
        )
        lifecycle_evidence = getattr(coordinated, "lifecycle_policy_evidence", None)
        if isinstance(lifecycle_evidence, dict) and lifecycle_evidence:
            self.decision_lifecycle_policy_evidence[bid] = dict(lifecycle_evidence)
        lifecycle_action = str(getattr(coordinated, "lifecycle_action", "") or "")
        if coordinated.decision == Decision.ABANDON and lifecycle_action in {
            "archive_lineage",
            "soft_abandon",
        }:
            self.decision_lifecycle_bookkeeping[bid] = _soft_lifecycle_bookkeeping(
                lifecycle_action=lifecycle_action,
                decision_reason_codes=coordinated.reason_codes,
            )
        else:
            self.decision_lifecycle_bookkeeping.pop(bid, None)
        self._set_reason_provenance(
            bid,
            source=str(getattr(coordinated, "decision_layer_source", "") or "stage_decision"),
            decision_engine=coordinated.reason_codes,
            lifecycle=tuple(getattr(coordinated, "lifecycle_reason_codes", ()) or ()),
        )
        if features.telemetry_effect_zero_diagnostic:
            self.decision_reason_codes[bid] = _merge_reason_codes(
                self.decision_reason_codes[bid],
                (TELEMETRY_EFFECT_ZERO_DIAGNOSTIC,),
            )
            self.diagnostic_reason_codes[bid] = _merge_reason_codes(
                self.diagnostic_reason_codes.get(bid, ()),
                (TELEMETRY_EFFECT_ZERO_DIAGNOSTIC,),
            )
        runtime_budget_codes = runtime_budget_diagnostic_reason_codes(protocol_result)
        if runtime_budget_codes:
            self.decision_reason_codes[bid] = _merge_reason_codes(
                self.decision_reason_codes[bid],
                runtime_budget_codes,
            )
            self.diagnostic_reason_codes[bid] = _merge_reason_codes(
                self.diagnostic_reason_codes.get(bid, ()),
                runtime_budget_codes,
            )
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
        if features.telemetry_validation_repairable and decision in (
            Decision.CONTINUE_EXPLORE,
            Decision.VALIDATION_REPAIR_REQUIRED,
        ):
            if _telemetry_lifecycle_reason_present(self.decision_reason_codes[bid]):
                self.branch_telemetry_diagnostic_streaks[bid] = (
                    features.lifecycle_telemetry_diagnostic_streak + 1
                )
        elif screened_experiment_effective(protocol_result):
            self.branch_telemetry_diagnostic_streaks.pop(bid, None)

        return decision, protocol_result, canary_result

    def _set_reason_provenance(
        self,
        branch_id: str,
        *,
        source: str | None,
        decision_engine: Tuple[str, ...] | tuple[str, ...] = (),
        diagnostics: Tuple[str, ...] | tuple[str, ...] = (),
        bypass: Tuple[str, ...] | tuple[str, ...] = (),
        lifecycle: Tuple[str, ...] | tuple[str, ...] = (),
    ) -> None:
        if source is None:
            self.decision_layer_sources.pop(branch_id, None)
        else:
            self.decision_layer_sources[branch_id] = source
        self.decision_engine_reason_codes[branch_id] = tuple(decision_engine)
        self.diagnostic_reason_codes[branch_id] = tuple(diagnostics)
        self.bypass_reason_codes[branch_id] = tuple(bypass)
        self.lifecycle_reason_codes[branch_id] = tuple(lifecycle)

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


def _merge_reason_codes(
    first: tuple[str, ...],
    second: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(dict.fromkeys([*first, *second]))


def _soft_lifecycle_bookkeeping(
    *,
    lifecycle_action: str,
    decision_reason_codes: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "schema": "scion.lifecycle_bookkeeping.v1",
        "role": "screening_result_lifecycle_annotation",
        "attached_to_attempt_kind": "screening",
        "legacy_attempt_kind": "branch_lifecycle_policy",
        "legacy_decision_layer_source": "lifecycle_policy",
        "decision_layer_source": "stage_decision",
        "lifecycle_action": lifecycle_action or "archive_lineage",
        "reason_codes": list(decision_reason_codes or ()),
    }


def _with_lifecycle_inputs(
    features: DecisionFeatures,
    *,
    branch: Branch,
    current_zero_win_streak: int,
    current_telemetry_diagnostic_streak: int,
) -> DecisionFeatures:
    return replace(
        features,
        stale=features.stale
        or bool(getattr(branch, "reconcile_rescreening", False)),
        lifecycle_zero_win_streak=max(0, int(current_zero_win_streak or 0)),
        lifecycle_telemetry_diagnostic_streak=max(
            0,
            int(current_telemetry_diagnostic_streak or 0),
        ),
        lifecycle_marginal_no_effect_streak=max(
            0,
            int(getattr(branch, "lifecycle_marginal_no_effect_streak", 0) or 0),
        ),
        lifecycle_no_effect_diagnostic_followups=max(
            0,
            int(
                getattr(branch, "lifecycle_no_effect_diagnostic_followups", 0)
                or 0
            ),
        ),
        lifecycle_previous_signal_repeat_count=max(
            0,
            int(getattr(branch, "lifecycle_signal_repeat_count", 0) or 0),
        ),
        lifecycle_signal_matches_previous=_signal_matches_previous(features, branch),
        lifecycle_rollback_count=max(
            0,
            int(getattr(branch, "rollback_count", 0) or 0),
        ),
        lifecycle_prior_evidence_tier=_prior_evidence_tier(branch),  # type: ignore[arg-type]
        lifecycle_has_checkpoint=_branch_has_checkpoint(branch),
    )


def _signal_matches_previous(features: DecisionFeatures, branch: Branch) -> bool:
    previous = str(getattr(branch, "lifecycle_last_signal_signature", "") or "")
    return bool(previous and previous == decision_features_signal_signature(features))


def _prior_evidence_tier(branch: Branch) -> str:
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    if tier in {"weak_positive", "marginal", "no_effect"}:
        return tier
    status = str(getattr(branch, "branch_code_status", "") or "")
    if status == "active_weak_positive":
        return "weak_positive"
    if status == "active_marginal":
        return "marginal"
    if status == "active_no_effect":
        return "no_effect"
    return ""


def _telemetry_lifecycle_reason_present(reason_codes: tuple[str, ...]) -> bool:
    return bool(
        {
            SCREENING_TELEMETRY_DIAGNOSTIC_RETRY,
            VALIDATION_TELEMETRY_DIAGNOSTIC_RETRY,
            TELEMETRY_DIAGNOSTIC_STREAK_EXHAUSTED,
            BRANCH_LIFECYCLE_ARCHIVE_LINEAGE,
            BRANCH_LIFECYCLE_PARK_LINEAGE,
            BRANCH_LIFECYCLE_RETAIN_CHECKPOINT,
            BRANCH_LIFECYCLE_ROLLBACK_TO_CHECKPOINT,
        }
        & set(reason_codes or ())
    )


def _branch_has_checkpoint(branch: Branch) -> bool:
    return bool(
        getattr(branch, "best_quality_checkpoint_id", None)
        or getattr(branch, "last_valid_checkpoint_id", None)
    )


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


def _evaluation_failure_protocol_result(*, stage: ExperimentStage) -> ProtocolResult:
    return ProtocolResult(
        stage=stage,
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
        reason_codes=("EVALUATION_FAILED",),
        exposed_summary="evaluation failed before decision",
        raw_metrics_ref="",
        opportunity_diagnostics=("evaluation_failed",),
    )
