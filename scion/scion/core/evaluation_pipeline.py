from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Optional, Protocol

from scion.core.features import BudgetState, SafeFeatureExtractor
from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    ContractResult,
    DecisionFeatures,
    ExperimentStage,
    PatchProposal,
    ProtocolResult,
    VerificationResult,
)


@dataclass(frozen=True)
class EvaluationRequest:
    branch_id: str
    branch_state: BranchState
    candidate_workspace: str
    champion_workspace: str
    hypothesis_action: str
    expand: bool = False
    expand_round: int = 0
    patch: Optional[PatchProposal] = None
    retry_count: int = 0
    screening_expand_count: int = 0
    validation_expand_count: int = 0
    failure_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvaluationOutcome:
    protocol_result: ProtocolResult | None
    decision_features: DecisionFeatures
    verification_detail: str | None
    raw_metrics_ref: str | None
    contract_result: ContractResult
    verification_result: VerificationResult
    canary_result: CanaryResult


class ExperimentProtocolLike(Protocol):
    def run_canary(self, candidate_ws: str, champion_ws: str) -> CanaryResult:
        ...

    def run_experiment(
        self,
        stage: ExperimentStage,
        candidate_ws: str,
        champion_ws: str,
        hypothesis_action: str,
        expand: bool = False,
        expand_round: int = 1,
    ) -> ProtocolResult:
        ...


ContractEvaluator = Callable[[EvaluationRequest], ContractResult]
VerificationEvaluator = Callable[[EvaluationRequest], VerificationResult]
BudgetProvider = Callable[[], BudgetState]


class EvaluationPipeline:
    """Service shell for evaluation-stage orchestration.

    The pipeline converts structured evaluation facts into DecisionFeatures.
    It intentionally accepts dependency-injected callables so campaign.py can be
    integrated incrementally without moving all contract/verification state at
    once.
    """

    def __init__(
        self,
        *,
        contract_evaluator: ContractEvaluator | None = None,
        verification_evaluator: VerificationEvaluator | None = None,
        experiment_protocol: ExperimentProtocolLike | None = None,
        feature_extractor: SafeFeatureExtractor | None = None,
        budget_provider: BudgetProvider | None = None,
    ) -> None:
        self._contract_evaluator = contract_evaluator or _default_contract_evaluator
        self._verification_evaluator = verification_evaluator or _default_verification_evaluator
        self._experiment_protocol = experiment_protocol
        self._feature_extractor = feature_extractor or SafeFeatureExtractor()
        self._budget_provider = budget_provider or (lambda: BudgetState(total=0, used=0))

    def evaluate(self, request: EvaluationRequest) -> EvaluationOutcome:
        branch = _request_to_branch(request)

        contract_result = self._contract_evaluator(request)
        verification_result = _passed_verification()
        canary_result = CanaryResult(passed=True, reason="not run")
        protocol_result: ProtocolResult | None = None

        if contract_result.passed:
            verification_result = self._verification_evaluator(request)

        if contract_result.passed and verification_result.passed:
            if self._experiment_protocol is not None:
                try:
                    canary_result = self._experiment_protocol.run_canary(
                        request.candidate_workspace,
                        request.champion_workspace,
                    )
                except (ValueError, NotImplementedError) as exc:
                    canary_result = CanaryResult(
                        passed=False,
                        reason=f"canary configuration error: {exc}",
                    )

                if canary_result.passed:
                    protocol_result = self._experiment_protocol.run_experiment(
                        stage=_stage_for_state(request.branch_state),
                        candidate_ws=request.candidate_workspace,
                        champion_ws=request.champion_workspace,
                        hypothesis_action=request.hypothesis_action,
                        expand=request.expand,
                        expand_round=request.expand_round,
                    )
                    protocol_result = _sanitize_protocol_exposure(protocol_result)
            else:
                canary_result = CanaryResult(passed=True, reason="no protocol - auto-pass")

        features = self._feature_extractor.extract(
            branch=branch,
            hypothesis_action=request.hypothesis_action,
            contract=contract_result,
            verification=verification_result,
            canary=canary_result,
            protocol=protocol_result,
            budget=self._budget_provider(),
        )

        return EvaluationOutcome(
            protocol_result=protocol_result,
            decision_features=features,
            verification_detail=_build_verification_detail(verification_result),
            raw_metrics_ref=protocol_result.raw_metrics_ref if protocol_result else None,
            contract_result=contract_result,
            verification_result=verification_result,
            canary_result=canary_result,
        )


def _request_to_branch(request: EvaluationRequest) -> Branch:
    branch = Branch(
        branch_id=request.branch_id,
        state=request.branch_state,
        base_champion_id=0,
        base_champion_hash="",
        retry_count=request.retry_count,
        screening_expand_count=request.screening_expand_count,
        validation_expand_count=request.validation_expand_count,
    )
    branch.failure_codes = list(request.failure_codes)
    return branch


def _stage_for_state(state: BranchState) -> ExperimentStage:
    if state in (BranchState.VALIDATING, BranchState.VALIDATING_EXPAND):
        return ExperimentStage.VALIDATION
    if state == BranchState.FROZEN_TESTING:
        return ExperimentStage.FROZEN
    return ExperimentStage.SCREENING


def _sanitize_protocol_exposure(result: ProtocolResult) -> ProtocolResult:
    if result.stage == ExperimentStage.SCREENING:
        return result

    stats = result.stats
    exposed_summary = (
        f"stage={result.stage.value} outcome={result.gate_outcome} "
        f"stat={stats.statistical_status or 'legacy'} "
        f"metric={stats.statistical_metric or 'scalar'} "
        f"n_cases={stats.n_cases} "
        f"runtime_pairs={stats.runtime_pairs} "
        f"runtime_ratio_median={_fmt_optional(stats.runtime_ratio_median)} "
        f"runtime_delta_median_ms={_fmt_optional(stats.runtime_delta_median_ms)} "
        f"runtime_regression_rate={_fmt_optional(stats.runtime_regression_rate)}"
    )
    return replace(
        result,
        exposed_summary=exposed_summary,
        pair_feedback=(),
        case_feedback=(),
        pattern_summary=None,
    )


def _default_contract_evaluator(request: EvaluationRequest) -> ContractResult:
    return ContractResult(passed=True, checks=())


def _fmt_optional(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{value:.4f}"


def _default_verification_evaluator(request: EvaluationRequest) -> VerificationResult:
    return _passed_verification()


def _passed_verification() -> VerificationResult:
    return VerificationResult(passed=True, checks=())


def _build_verification_detail(vresult: VerificationResult) -> Optional[str]:
    if not vresult or vresult.passed:
        return None
    failed = [c for c in vresult.checks if not c.passed]
    if not failed:
        return vresult.first_failure
    lines = [
        f"severity={vresult.failure_severity or 'unknown'}  "
        f"first_failure={vresult.first_failure or 'N/A'}"
    ]
    for check in failed:
        lines.append(f"  [{check.name}] ({check.severity}) {check.detail}")
    return "\n".join(lines)
