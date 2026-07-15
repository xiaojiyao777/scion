"""Evaluation-stage orchestration boundary."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Callable, MutableMapping, Optional, Tuple

from scion.core.canary_failure import (
    decision_reason_codes_for_canary,
    is_canary_config_error,
    public_canary_reason_codes,
)
from scion.core.decision_coordinator import DecisionCoordinator
from scion.core.evaluation_pipeline import EvaluationPipeline, EvaluationRequest
from scion.core.features import SafeFeatureExtractor
from scion.core.execution_outcome import (
    ExecutionOutcome,
    ExecutionOutcomeRecord,
    validate_execution_outcome_projection,
)
from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    ChampionState,
    Decision,
    DecisionFeatures,
    ExperimentStage,
    HypothesisProposal,
    HypothesisRecord,
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

    def __post_init__(self) -> None:
        validate_execution_outcome_projection(
            execution_outcome=self.execution_outcome.outcome,
            reason_code=self.execution_outcome.reason_code,
            detail=self.execution_outcome.detail,
            provenance=self.execution_outcome.provenance,
            decision=self.decision,
            protocol_result=self.protocol_result,
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
    branch_hypotheses: MutableMapping[str, HypothesisProposal]
    branch_current_hypothesis: MutableMapping[str, HypothesisRecord]
    experiment_protocol_provider: Callable[[], Any]
    feature_extractor: SafeFeatureExtractor
    decision_coordinator: DecisionCoordinator
    decision_reason_codes: MutableMapping[str, Tuple[str, ...]]
    campaign_id: str
    registry: Any
    materializer: Any
    hypothesis_store: Any
    persist_branch_state: Callable[[str], None]
    begin_status_progress: Callable[..., None]
    end_status_progress: Callable[[], None]
    increment_experiment_count: Callable[[], None]
    require_experiment_protocol: bool = False
    decision_engine_reason_codes: MutableMapping[str, Tuple[str, ...]] = field(
        default_factory=dict
    )
    diagnostic_reason_codes: MutableMapping[str, Tuple[str, ...]] = field(
        default_factory=dict
    )
    bypass_reason_codes: MutableMapping[str, Tuple[str, ...]] = field(
        default_factory=dict
    )
    decision_feature_snapshots: MutableMapping[str, DecisionFeatures] = field(
        default_factory=dict
    )

    def evaluate(
        self,
        branch: Branch,
        workspace: str,
        hypothesis: HypothesisProposal,
    ) -> EvaluationExecutionResult:
        bid = branch.branch_id
        self.decision_feature_snapshots.pop(bid, None)
        self._set_reason_provenance(
            bid,
            decision_engine=(),
            diagnostics=(),
            bypass=(),
        )
        stage = self.branch_controller.next_stage(bid)

        with self.champion_lock:
            champion_for_eval = self.get_champion()
        champion_workspace = champion_for_eval.code_snapshot_path
        branch.weight_revision = getattr(champion_for_eval, "weight_revision", 0)
        self.persist_branch_state(bid)

        protocol = self.experiment_protocol_provider()

        expand, expand_round = self._prepare_expand(branch, protocol)
        priority_case_ids = _branch_followup_priority_cases(branch) if expand else ()
        request = EvaluationRequest(
            branch_id=bid,
            branch_state=branch.state,
            candidate_workspace=workspace,
            champion_workspace=champion_workspace,
            hypothesis_action=hypothesis.action,
            expand=expand,
            expand_round=expand_round,
            selected_surface=hypothesis.change_locus,
            priority_case_ids=priority_case_ids,
            patch=self.branch_patches.get(bid),
            screening_expand_count=branch.screening_expand_count,
            validation_expand_count=branch.validation_expand_count,
            failure_codes=tuple(branch.failure_codes),
            force_fresh_champion=False,
        )
        pipeline = EvaluationPipeline(
            experiment_protocol=protocol,
            require_experiment_protocol=self.require_experiment_protocol,
            feature_extractor=self.feature_extractor,
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
            if evaluation.protocol_result is not None:
                self.increment_experiment_count()
        except Exception as exc:
            logger.error("Branch %s: experiment failed: %s", bid, exc)
            outcome, reason_code = _execution_outcome_for_exception(exc)
            self.decision_reason_codes[bid] = (reason_code,)
            self._set_reason_provenance(
                bid,
                bypass=(reason_code,),
            )
            return EvaluationExecutionResult(
                execution_outcome=ExecutionOutcomeRecord(
                    outcome=outcome,
                    reason_code=reason_code,
                    detail=str(exc),
                    provenance={
                        "owner": "evaluation_orchestrator",
                        "stage": stage.value,
                        "exception_type": (
                            f"{type(exc).__module__}.{type(exc).__qualname__}"
                        ),
                    },
                )
            )

        protocol_result = evaluation.protocol_result
        canary_result = evaluation.canary_result
        if _champion_evidence_acquisition_blocked(protocol_result):
            assert protocol_result is not None
            reason_code = "EVALUATION_CHAMPION_EVIDENCE_BLOCKED"
            stats = protocol_result.stats
            self.decision_reason_codes[bid] = (reason_code,)
            self._set_reason_provenance(
                bid,
                bypass=(reason_code,),
            )
            return EvaluationExecutionResult(
                execution_outcome=ExecutionOutcomeRecord(
                    outcome=ExecutionOutcome.BLOCKED_INFRA,
                    reason_code=reason_code,
                    detail=(
                        "champion/shared evidence acquisition failed; "
                        "explicit operator review is required"
                    ),
                    provenance={
                        "owner": "evaluation_orchestrator",
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
                        "operator_resume_required": True,
                    },
                ),
                decision=None,
                protocol_result=None,
                canary_result=canary_result,
            )
        features = evaluation.decision_features
        coordinated = self.decision_coordinator.decide(features)
        self.decision_feature_snapshots[bid] = coordinated.features_snapshot
        self.decision_reason_codes[bid] = coordinated.reason_codes
        self._set_reason_provenance(
            bid,
            decision_engine=coordinated.reason_codes,
        )
        canary_reason_codes = public_canary_reason_codes(canary_result)
        if canary_reason_codes and not canary_result.passed:
            self.decision_reason_codes[bid] = decision_reason_codes_for_canary(
                self.decision_reason_codes.get(bid, ()),
                canary_result,
            )
            if is_canary_config_error(canary_result):
                self.diagnostic_reason_codes[bid] = _merge_reason_codes(
                    self.diagnostic_reason_codes.get(bid, ()),
                    canary_reason_codes,
                )
        runtime_budget_codes = runtime_budget_diagnostic_reason_codes(protocol_result)
        if runtime_budget_codes:
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
        return EvaluationExecutionResult(
            execution_outcome=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.EVALUATED,
                reason_code="EVALUATION_COMPLETED",
                provenance={
                    "owner": "evaluation_orchestrator",
                    "stage": stage.value,
                },
            ),
            decision=decision,
            protocol_result=protocol_result,
            canary_result=canary_result,
        )

    def _set_reason_provenance(
        self,
        branch_id: str,
        *,
        decision_engine: Tuple[str, ...] | tuple[str, ...] = (),
        diagnostics: Tuple[str, ...] | tuple[str, ...] = (),
        bypass: Tuple[str, ...] | tuple[str, ...] = (),
    ) -> None:
        self.decision_engine_reason_codes[branch_id] = tuple(decision_engine)
        self.diagnostic_reason_codes[branch_id] = tuple(diagnostics)
        self.bypass_reason_codes[branch_id] = tuple(bypass)

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


def _branch_followup_priority_cases(branch: Branch) -> tuple[str, ...]:
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    if not isinstance(summary, Mapping):
        return ()
    case_ids: list[str] = []
    for key in (
        "case_level_negative_cases",
        "case_level_losses",
        "case_level_positive_cases",
        "case_level_winners",
    ):
        case_ids.extend(_case_ids_from_evidence(summary.get(key)))
    return tuple(dict.fromkeys(case_id for case_id in case_ids if case_id))


def _case_ids_from_evidence(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped,) if stripped else ()
    if isinstance(value, Mapping):
        for key in ("case_id", "case", "id", "instance", "path"):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                return (raw.strip(),)
        return ()
    if isinstance(value, (list, tuple, set)):
        case_ids: list[str] = []
        for item in value:
            case_ids.extend(_case_ids_from_evidence(item))
        return tuple(case_ids)
    return ()


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
