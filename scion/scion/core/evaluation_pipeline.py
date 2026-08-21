from __future__ import annotations

import inspect
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, Optional, Protocol

from scion.core.canary_failure import (
    canary_configuration_error,
    normalize_canary_result,
)
from scion.core.features import SafeFeatureExtractor
from scion.core.models import (
    BranchState,
    CanaryResult,
    DecisionFeatures,
    ExperimentStage,
    PatchProposal,
    ProtocolResult,
)
from scion.core.runtime_budget_diagnostics import (
    format_runtime_budget_diagnostic,
    protocol_runtime_budget_diagnostic,
)


@dataclass(frozen=True)
class EvaluationRequest:
    branch_state: BranchState
    candidate_workspace: str
    champion_workspace: str
    hypothesis_action: str
    # Source against which the current patch was authored.  This can be a
    # branch's accepted workspace rather than the global champion.
    proposal_base_workspace: str | None = None
    expand: bool = False
    expand_round: int = 0
    selected_surface: str | None = None
    patch: Optional[PatchProposal] = None
    screening_expand_count: int = 0
    validation_expand_count: int = 0
    failure_codes: tuple[str, ...] = ()
    contract_passed: bool = True
    verification_passed: bool = True


@dataclass(frozen=True)
class EvaluationOutcome:
    protocol_result: ProtocolResult | None
    decision_features: DecisionFeatures
    raw_metrics_ref: str | None
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
        proposal_subject: Mapping[str, Any] | None = None,
    ) -> ProtocolResult:
        ...


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
        experiment_protocol: ExperimentProtocolLike,
        feature_extractor: SafeFeatureExtractor | None = None,
    ) -> None:
        self._experiment_protocol = experiment_protocol
        self._feature_extractor = feature_extractor or SafeFeatureExtractor()

    def evaluate(self, request: EvaluationRequest) -> EvaluationOutcome:
        canary_result = CanaryResult(passed=True, reason="not run")
        protocol_result: ProtocolResult | None = None

        if request.contract_passed and request.verification_passed:
            try:
                canary_result = _run_protocol_canary(
                    self._experiment_protocol,
                    request.candidate_workspace,
                    request.champion_workspace,
                    selected_surface=request.selected_surface,
                )
            except (ValueError, NotImplementedError) as exc:
                canary_result = canary_configuration_error(exc)
            canary_result = normalize_canary_result(canary_result)

            if canary_result.passed:
                from scion.protocol.experiment.proposal_evidence import (
                    build_problem_proposal_subject,
                )

                protocol_result = _run_protocol_experiment(
                    self._experiment_protocol,
                    stage=_stage_for_state(request.branch_state),
                    candidate_ws=request.candidate_workspace,
                    champion_ws=request.champion_workspace,
                    hypothesis_action=request.hypothesis_action,
                    expand=request.expand,
                    expand_round=request.expand_round,
                    selected_surface=request.selected_surface,
                    proposal_subject=build_problem_proposal_subject(
                        patch=request.patch,
                        base_workspace=request.proposal_base_workspace,
                    ),
                )
                protocol_result = _sanitize_protocol_exposure(protocol_result)

        features = self._feature_extractor.extract(
            branch_state=request.branch_state,
            screening_expand_count=request.screening_expand_count,
            validation_expand_count=request.validation_expand_count,
            failure_codes=request.failure_codes,
            hypothesis_action=request.hypothesis_action,
            contract=request.contract_passed,
            verification=request.verification_passed,
            canary=canary_result,
            protocol=protocol_result,
        )

        return EvaluationOutcome(
            protocol_result=protocol_result,
            decision_features=features,
            raw_metrics_ref=protocol_result.raw_metrics_ref if protocol_result else None,
            canary_result=canary_result,
        )

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
    runtime_budget_suffix = format_runtime_budget_diagnostic(
        protocol_runtime_budget_diagnostic(result)
    )
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
        f" runtime_confidence={result.runtime_confidence}"
        f"{runtime_budget_suffix}"
    )
    return replace(
        result,
        exposed_summary=exposed_summary,
        pair_feedback=(),
        case_feedback=(),
        pattern_summary=None,
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
    if _should_forward_selected_surface(
        protocol,
        "run_experiment",
        selected_surface,
    ):
        kwargs["selected_surface"] = selected_surface
    proposal_subject = kwargs.pop("proposal_subject", None)
    if isinstance(proposal_subject, Mapping) and proposal_subject:
        kwargs["proposal_subject"] = dict(proposal_subject)
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
