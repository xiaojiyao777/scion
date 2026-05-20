from __future__ import annotations

import inspect
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, Callable, Optional, Protocol

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
from scion.core.telemetry_validation import (
    telemetry_validation_failure_codes,
    telemetry_validation_feedback,
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
    selected_surface: str | None = None
    expected_telemetry: Mapping[str, Any] | None = None
    mechanism_changes: tuple[Any, ...] = ()
    protected_objectives: tuple[str, ...] = ()
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
    def run_canary(
        self,
        candidate_ws: str,
        champion_ws: str,
        *,
        selected_surface: str | None = None,
    ) -> CanaryResult:
        ...

    def run_experiment(
        self,
        stage: ExperimentStage,
        candidate_ws: str,
        champion_ws: str,
        hypothesis_action: str,
        expand: bool = False,
        expand_round: int = 1,
        selected_surface: str | None = None,
        expected_telemetry: Mapping[str, Any] | None = None,
        mechanism_changes: tuple[Any, ...] = (),
        protected_objectives: tuple[str, ...] = (),
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
                    canary_result = _run_protocol_canary(
                        self._experiment_protocol,
                        request.candidate_workspace,
                        request.champion_workspace,
                        selected_surface=request.selected_surface,
                    )
                except (ValueError, NotImplementedError) as exc:
                    canary_result = CanaryResult(
                        passed=False,
                        reason=f"canary configuration error: {exc}",
                    )

                if canary_result.passed:
                    protocol_result = _run_protocol_experiment(
                        self._experiment_protocol,
                        stage=_stage_for_state(request.branch_state),
                        candidate_ws=request.candidate_workspace,
                        champion_ws=request.champion_workspace,
                        hypothesis_action=request.hypothesis_action,
                        expand=request.expand,
                        expand_round=request.expand_round,
                        selected_surface=request.selected_surface,
                        expected_telemetry=request.expected_telemetry,
                        mechanism_changes=request.mechanism_changes,
                        protected_objectives=request.protected_objectives,
                    )
                    protocol_result = _annotate_telemetry_validation_failure(
                        protocol_result
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
    telemetry_guard = ""
    surface_summary = result.candidate_surface_runtime_summary or {}
    if isinstance(surface_summary, Mapping):
        guard = surface_summary.get("telemetry_guard")
        if isinstance(guard, Mapping):
            failures = guard.get("failures")
            warnings = guard.get("warnings")
            failure_count = len(failures) if isinstance(failures, list) else 0
            warning_count = len(warnings) if isinstance(warnings, list) else 0
            telemetry_guard = (
                f" telemetry_guard_passed={bool(guard.get('passed'))}"
                f" telemetry_guard_failures={failure_count}"
                f" telemetry_guard_warnings={warning_count}"
            )
    telemetry_feedback = telemetry_validation_feedback(result)
    telemetry_feedback_suffix = f" {telemetry_feedback}" if telemetry_feedback else ""
    exposed_summary = (
        f"stage={result.stage.value} outcome={result.gate_outcome} "
        f"stat={stats.statistical_status or 'legacy'} "
        f"metric={stats.statistical_metric or 'scalar'} "
        f"n_cases={stats.n_cases} "
        f"runtime_pairs={stats.runtime_pairs} "
        f"runtime_ratio_median={_fmt_optional(stats.runtime_ratio_median)} "
        f"runtime_delta_median_ms={_fmt_optional(stats.runtime_delta_median_ms)} "
        f"runtime_regression_rate={_fmt_optional(stats.runtime_regression_rate)} "
        f"candidate_runtime_categories="
        f"{_fmt_category_counts(result.candidate_runtime_failure_categories)} "
        f"candidate_operator_attempts={result.candidate_operator_attempts} "
        f"candidate_operator_accepted={result.candidate_operator_accepted}"
        f"{telemetry_guard}"
        f"{telemetry_feedback_suffix}"
    )
    return replace(
        result,
        exposed_summary=exposed_summary,
        pair_feedback=(),
        case_feedback=(),
        pattern_summary=None,
    )


def _annotate_telemetry_validation_failure(
    result: ProtocolResult,
) -> ProtocolResult:
    codes = telemetry_validation_failure_codes(result)
    if not codes:
        return result
    reason_codes = tuple(dict.fromkeys([*codes, *result.reason_codes]))
    feedback = telemetry_validation_feedback(result)
    exposed_summary = result.exposed_summary or ""
    if feedback and feedback not in exposed_summary:
        exposed_summary = (exposed_summary + " " + feedback).strip()
    return replace(
        result,
        reason_codes=reason_codes,
        exposed_summary=exposed_summary,
    )


def _run_protocol_canary(
    protocol: ExperimentProtocolLike,
    candidate_ws: str,
    champion_ws: str,
    *,
    selected_surface: str | None,
) -> CanaryResult:
    if _should_forward_selected_surface(protocol, "run_canary", selected_surface):
        return protocol.run_canary(
            candidate_ws,
            champion_ws,
            selected_surface=selected_surface,
        )
    return protocol.run_canary(candidate_ws, champion_ws)


def _run_protocol_experiment(
    protocol: ExperimentProtocolLike,
    **kwargs: object,
) -> ProtocolResult:
    selected_surface = kwargs.pop("selected_surface", None)
    expected_telemetry = kwargs.pop("expected_telemetry", None)
    mechanism_changes = kwargs.pop("mechanism_changes", None)
    protected_objectives = kwargs.pop("protected_objectives", None)
    if _should_forward_selected_surface(
        protocol,
        "run_experiment",
        selected_surface,
    ):
        kwargs["selected_surface"] = selected_surface
    if expected_telemetry and _method_accepts_keyword(
        protocol,
        "run_experiment",
        "expected_telemetry",
    ):
        kwargs["expected_telemetry"] = expected_telemetry
    if mechanism_changes and _method_accepts_keyword(
        protocol,
        "run_experiment",
        "mechanism_changes",
    ):
        kwargs["mechanism_changes"] = mechanism_changes
    if protected_objectives and _method_accepts_keyword(
        protocol,
        "run_experiment",
        "protected_objectives",
    ):
        kwargs["protected_objectives"] = protected_objectives
    return protocol.run_experiment(**kwargs)


def _should_forward_selected_surface(
    protocol: ExperimentProtocolLike,
    method_name: str,
    selected_surface: object,
) -> bool:
    if not isinstance(selected_surface, str) or not selected_surface.strip():
        return False
    if not _method_accepts_keyword(protocol, method_name, "selected_surface"):
        return False
    return _protocol_has_research_surfaces(protocol)


def _method_accepts_keyword(
    protocol: ExperimentProtocolLike,
    method_name: str,
    keyword: str,
) -> bool:
    method = getattr(protocol, method_name, None)
    if method is None:
        return False
    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):
        return False
    return any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    ) or keyword in signature.parameters


def _protocol_has_research_surfaces(protocol: ExperimentProtocolLike) -> bool:
    problem_spec: Any = getattr(protocol, "problem_spec", None)
    if problem_spec is None:
        problem_spec = getattr(protocol, "_problem_spec", None)
    surfaces = _get_field(problem_spec, "research_surfaces")
    return isinstance(surfaces, (list, tuple)) and bool(surfaces)


def _get_field(obj: Any, name: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def _default_contract_evaluator(request: EvaluationRequest) -> ContractResult:
    return ContractResult(passed=True, checks=())


def _fmt_optional(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{value:.4f}"


def _fmt_category_counts(categories: dict[str, int]) -> str:
    if not categories:
        return "none"
    return ";".join(
        f"{key}:{value}"
        for key, value in sorted(categories.items())
        if value > 0
    ) or "none"


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
