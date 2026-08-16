"""Evaluation-stage orchestration boundary."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, MutableMapping, Optional, Tuple

from scion.core.canary_failure import (
    decision_reason_codes_for_canary,
    is_canary_config_error,
    public_canary_reason_codes,
)
from scion.core.decision_coordinator import DecisionCoordinator
from scion.core.evaluation_pipeline import EvaluationPipeline, EvaluationRequest
from scion.core.execution_outcome import (
    ExecutionOutcome,
    ExecutionOutcomeRecord,
)
from scion.core.features import SafeFeatureExtractor
from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    ChampionState,
    Decision,
    DecisionFeatures,
    ExperimentStage,
    HypothesisProposal,
    PatchProposal,
    ProtocolResult,
)
from scion.core.runtime_budget_diagnostics import runtime_budget_diagnostic_reason_codes

logger = logging.getLogger(__name__)


class EvaluationInfrastructureError(RuntimeError):
    """Explicit typed cause for evaluation infrastructure unavailability."""


class EvaluationProviderError(EvaluationInfrastructureError):
    """Explicit provider-side evaluation infrastructure failure."""


class EvaluationTransportError(EvaluationInfrastructureError):
    """Explicit transport failure while dispatching evaluation."""


@dataclass(frozen=True)
class EvaluationExecutionResult:
    """Typed evaluation result consumed through named fields, never tuple unpacking."""

    execution_outcome: ExecutionOutcomeRecord
    decision: Optional[Decision] = None
    protocol_result: Optional[ProtocolResult] = None
    canary_result: Optional[CanaryResult] = None
    decision_features: Optional[DecisionFeatures] = None
    decision_reason_codes: Tuple[str, ...] = ()
    decision_engine_reason_codes: Tuple[str, ...] = ()
    diagnostic_reason_codes: Tuple[str, ...] = ()
    bypass_reason_codes: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.execution_outcome, ExecutionOutcomeRecord):
            raise TypeError("execution_outcome must be an ExecutionOutcomeRecord")
        if self.execution_outcome.outcome is not ExecutionOutcome.EVALUATED:
            if self.decision is not None:
                raise ValueError(
                    "non-evaluated execution outcome cannot carry a Decision"
                )
            if self.protocol_result is not None:
                raise ValueError(
                    "non-evaluated execution outcome cannot carry a ProtocolResult"
                )
            if self.decision_features is not None:
                raise ValueError(
                    "non-evaluated execution outcome cannot carry DecisionFeatures"
                )
        if (
            self.execution_outcome.outcome is ExecutionOutcome.EVALUATED
            and self.decision is None
        ):
            raise ValueError("evaluated execution result requires a Decision")


@dataclass
class EvaluationOrchestrator:
    """Own protocol execution glue and typed decision coordination."""

    branch_controller: Any
    champion_lock: Any
    get_champion: Callable[[], ChampionState]
    branch_patches: MutableMapping[str, PatchProposal]
    branch_workspaces: MutableMapping[str, str]
    experiment_protocol_provider: Callable[[], Any]
    feature_extractor: SafeFeatureExtractor
    decision_coordinator: DecisionCoordinator
    campaign_id: str
    registry: Any
    materializer: Any
    begin_status_progress: Callable[..., None]
    end_status_progress: Callable[[], None]
    increment_experiment_count: Callable[[], None]
    def evaluate(
        self,
        branch: Branch,
        workspace: str,
        hypothesis: HypothesisProposal,
        *,
        branch_state: BranchState | None = None,
        screening_expand_count: int | None = None,
        validation_expand_count: int | None = None,
    ) -> EvaluationExecutionResult:
        bid = branch.branch_id
        effective_state = branch_state or branch.state
        stage = _stage_for_state(effective_state)

        with self.champion_lock:
            champion_for_eval = self.get_champion()
        champion_workspace = champion_for_eval.code_snapshot_path
        protocol = self.experiment_protocol_provider()

        effective_screening_expand_count = (
            branch.screening_expand_count
            if screening_expand_count is None
            else screening_expand_count
        )
        effective_validation_expand_count = (
            branch.validation_expand_count
            if validation_expand_count is None
            else validation_expand_count
        )
        expand, expand_round = self._prepare_expand(
            effective_state,
            effective_screening_expand_count,
            effective_validation_expand_count,
            protocol,
        )
        if expand and effective_state == BranchState.EXPLORE_EXPAND:
            effective_screening_expand_count = expand_round
        elif expand and effective_state == BranchState.VALIDATING_EXPAND:
            effective_validation_expand_count = expand_round
        request = EvaluationRequest(
            branch_state=effective_state,
            candidate_workspace=workspace,
            champion_workspace=champion_workspace,
            hypothesis_action=hypothesis.action,
            expand=expand,
            expand_round=expand_round,
            selected_surface=hypothesis.change_locus,
            patch=self.branch_patches.get(bid),
            screening_expand_count=effective_screening_expand_count,
            validation_expand_count=effective_validation_expand_count,
            failure_codes=tuple(branch.failure_codes),
        )
        pipeline = EvaluationPipeline(
            experiment_protocol=protocol,
            feature_extractor=self.feature_extractor,
        )

        try:
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
            if evaluation.protocol_result is not None:
                self.increment_experiment_count()
        except Exception as exc:
            logger.error("Branch %s: experiment failed: %s", bid, exc)
            outcome, reason_code = _execution_outcome_for_exception(exc)
            return EvaluationExecutionResult(
                execution_outcome=ExecutionOutcomeRecord(
                    outcome=outcome,
                    reason_code=reason_code,
                    detail=str(exc),
                    provenance={
                        "stage": stage.value,
                        "exception_type": (
                            f"{type(exc).__module__}.{type(exc).__qualname__}"
                        ),
                    },
                ),
                decision_reason_codes=(reason_code,),
                bypass_reason_codes=(reason_code,),
            )

        protocol_result = evaluation.protocol_result
        canary_result = evaluation.canary_result
        if _champion_evidence_acquisition_blocked(protocol_result):
            assert protocol_result is not None
            reason_code = "EVALUATION_CHAMPION_EVIDENCE_BLOCKED"
            stats = protocol_result.stats
            return EvaluationExecutionResult(
                execution_outcome=ExecutionOutcomeRecord(
                    outcome=ExecutionOutcome.BLOCKED_INFRA,
                    reason_code=reason_code,
                    detail=(
                        "champion/shared evidence acquisition failed; "
                        "this invocation is blocked"
                    ),
                    provenance={
                        "stage": protocol_result.stage.value,
                        "failure_scope": "champion_or_shared",
                        "raw_metrics_ref": protocol_result.raw_metrics_ref,
                        "protocol_gate_outcome": protocol_result.gate_outcome,
                        "protocol_reason_codes": list(protocol_result.reason_codes),
                        "total_pairs": stats.total_pairs,
                        "valid_pairs": stats.valid_pairs,
                        "failed_pairs": stats.failed_pairs,
                        "candidate_failed_pairs": stats.candidate_failed_pairs,
                        "champion_failed_pairs": stats.champion_failed_pairs,
                    },
                ),
                decision=None,
                protocol_result=None,
                canary_result=canary_result,
                decision_reason_codes=(reason_code,),
                bypass_reason_codes=(reason_code,),
            )
        features = evaluation.decision_features
        coordinated = self.decision_coordinator.decide(features)
        decision_reason_codes = coordinated.reason_codes
        diagnostic_reason_codes: Tuple[str, ...] = ()
        canary_reason_codes = public_canary_reason_codes(canary_result)
        if canary_reason_codes and not canary_result.passed:
            decision_reason_codes = decision_reason_codes_for_canary(
                decision_reason_codes,
                canary_result,
            )
            if is_canary_config_error(canary_result):
                diagnostic_reason_codes = _merge_reason_codes(
                    diagnostic_reason_codes,
                    canary_reason_codes,
                )
        runtime_budget_codes = runtime_budget_diagnostic_reason_codes(protocol_result)
        if runtime_budget_codes:
            diagnostic_reason_codes = _merge_reason_codes(
                diagnostic_reason_codes,
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
        return EvaluationExecutionResult(
            execution_outcome=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.EVALUATED,
                reason_code="EVALUATION_COMPLETED",
                provenance={
                    "stage": stage.value,
                },
            ),
            decision=decision,
            protocol_result=protocol_result,
            canary_result=canary_result,
            decision_features=features,
            decision_reason_codes=decision_reason_codes,
            decision_engine_reason_codes=coordinated.reason_codes,
            diagnostic_reason_codes=diagnostic_reason_codes,
        )

    @staticmethod
    def _prepare_expand(
        state: BranchState,
        screening_expand_count: int,
        validation_expand_count: int,
        protocol: Any,
    ) -> tuple[bool, int]:
        """Compute the effective round from the current branch value."""

        expand = False
        expand_round = 1
        if protocol is None:
            return expand, expand_round

        expand = state in (
            BranchState.EXPLORE_EXPAND,
            BranchState.VALIDATING_EXPAND,
        )
        if state == BranchState.EXPLORE_EXPAND:
            expand_round = screening_expand_count + 1
        elif state == BranchState.VALIDATING_EXPAND:
            expand_round = validation_expand_count + 1
        return expand, expand_round


def _merge_reason_codes(
    first: tuple[str, ...],
    second: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(dict.fromkeys([*first, *second]))


def _stage_for_state(state: BranchState) -> ExperimentStage:
    if state in (BranchState.VALIDATING, BranchState.VALIDATING_EXPAND):
        return ExperimentStage.VALIDATION
    if state is BranchState.FROZEN_TESTING:
        return ExperimentStage.FROZEN
    return ExperimentStage.SCREENING


def _champion_evidence_acquisition_blocked(
    protocol_result: ProtocolResult | None,
) -> bool:
    """Return whether later-stage evidence failed outside candidate attribution.

    Protocol remains responsible for marking the partial comparison as failed.
    This predicate only separates a champion/shared evidence-acquisition incident
    from a candidate-attributable runtime failure before Decision is invoked.
    """

    if protocol_result is None or protocol_result.stage not in (
        ExperimentStage.VALIDATION,
        ExperimentStage.FROZEN,
    ):
        return False
    stats = protocol_result.stats
    reason_codes = set(protocol_result.reason_codes)
    return (
        stats.failed_pairs > 0
        and stats.champion_failed_pairs == stats.failed_pairs
        and stats.candidate_failed_pairs == 0
        and "INCOMPLETE_EVIDENCE" in reason_codes
        and "CHAMPION_RUNTIME_FAILURE" in reason_codes
    )


def _execution_outcome_for_exception(
    exc: Exception,
) -> tuple[ExecutionOutcome, str]:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, EvaluationProviderError):
            return ExecutionOutcome.BLOCKED_INFRA, "EVALUATION_PROVIDER_BLOCKED"
        if isinstance(current, EvaluationTransportError):
            return ExecutionOutcome.BLOCKED_INFRA, "EVALUATION_TRANSPORT_BLOCKED"
        if isinstance(current, EvaluationInfrastructureError):
            return ExecutionOutcome.BLOCKED_INFRA, "EVALUATION_INFRA_BLOCKED"
        current = current.__cause__ or current.__context__
    return ExecutionOutcome.NOT_EVALUATED, "EVALUATION_EXCEPTION"
