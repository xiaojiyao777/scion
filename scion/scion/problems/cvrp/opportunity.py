"""CVRP-owned solver opportunity provider."""

from __future__ import annotations

from typing import Any, Mapping

from scion.measurement import MeasurementConsumerView, measurement_consumer_view
from scion.opportunity import (
    AvoidedMechanismSummary,
    MechanismEvidenceSummary,
    OpportunityEvidenceRequirement,
    OpportunityAxis,
    OpportunityContext,
    ProblemOpportunitySummary,
    ProtectedCaseSummary,
)
from scion.problems.cvrp.research_guidance import (
    CVRP_PROBLEM_FAMILY,
    PROTECTED_CASES,
    REQUIRED_MECHANISM_ID,
)


class CvrpOpportunityProvider:
    """Build proposal-only CVRP opportunity summaries."""

    problem_family = CVRP_PROBLEM_FAMILY

    def __init__(
        self,
        *,
        problem_spec: Any | None = None,
        adapter: Any | None = None,
    ) -> None:
        self._problem_spec = problem_spec
        self._adapter = adapter

    def build_opportunity_summary(
        self,
        context: OpportunityContext | None = None,
    ) -> ProblemOpportunitySummary:
        context = context or OpportunityContext()
        source = _mapping_or_empty(context.source_payload) or _adapter_payload(
            self._adapter
        )
        measurement = context.measurement or _measurement_view(self._problem_spec)
        objective = _objective(source, measurement)
        return ProblemOpportunitySummary(
            problem_family=self.problem_family,
            objective=objective,
            residual_opportunity=_residual_opportunity(source),
            mechanism_evidence=_mechanism_evidence(source),
            evidence_requirements=_evidence_requirements(
                source,
                context.postrun_reports,
            ),
            protected_cases=_protected_cases(),
            measurement=measurement,
            default_avoid=_default_avoid(source),
        )


def _adapter_payload(adapter: Any | None) -> dict[str, Any]:
    hook = getattr(adapter, "render_problem_measurement_diagnostics", None)
    if not callable(hook):
        return {}
    try:
        payload = hook()
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _measurement_view(problem_spec: Any | None) -> MeasurementConsumerView | None:
    if problem_spec is None:
        return None
    return measurement_consumer_view(problem_spec)


def _objective(
    source: Mapping[str, Any],
    measurement: MeasurementConsumerView | None,
) -> str:
    if measurement is not None and measurement.effect_metric:
        return measurement.effect_metric
    measurement_context = _mapping_or_empty(source.get("measurement_context"))
    metric = str(measurement_context.get("metric") or "").strip()
    return metric or "total_distance"


def _residual_opportunity(source: Mapping[str, Any]) -> tuple[OpportunityAxis, ...]:
    axes: list[OpportunityAxis] = []
    headroom = _mapping_or_empty(source.get("screening_headroom"))
    if headroom:
        axes.append(
            OpportunityAxis(
                axis_id="screening_headroom",
                metric=str(headroom.get("metric") or ""),
                status=str(headroom.get("scope") or "available"),
                summary=str(headroom.get("planning_use") or ""),
                reason_codes=("CVRP_AGGREGATE_HEADROOM_REMAINS",),
            )
        )
    for item in _list_of_mappings(source.get("opportunity_diagnostics")):
        diagnostic_type = str(item.get("diagnostic_type") or "").strip()
        if diagnostic_type not in {"measurement_power", "residual_opportunity"}:
            continue
        axes.append(
            OpportunityAxis(
                axis_id=diagnostic_type,
                metric=str(item.get("metric") or ""),
                status=str(item.get("confidence") or ""),
                summary=str(item.get("summary") or ""),
                reason_codes=_string_tuple(item.get("reason_codes")),
            )
        )
    return tuple(axes)


def _mechanism_evidence(
    source: Mapping[str, Any],
) -> tuple[MechanismEvidenceSummary, ...]:
    summaries: list[MechanismEvidenceSummary] = []
    for item in _list_of_mappings(source.get("mechanism_effect_ranking")):
        family = str(item.get("mechanism_family") or "").strip()
        if not family:
            continue
        summaries.append(
            MechanismEvidenceSummary(
                mechanism_family=family,
                evidence_status=str(item.get("evidence_status") or ""),
                opportunity_status=str(item.get("opportunity_status") or ""),
                effect_status=str(item.get("effect_status") or ""),
                summary=str(item.get("summary") or ""),
                recommended_action=str(item.get("recommended_action") or ""),
                reason_codes=_string_tuple(item.get("reason_codes")),
            )
        )
    return tuple(summaries)


def _evidence_requirements(
    source: Mapping[str, Any],
    postrun_reports: tuple[Mapping[str, Any], ...],
) -> tuple[OpportunityEvidenceRequirement, ...]:
    requirements: list[OpportunityEvidenceRequirement] = []
    recipe = _mapping_or_empty(source.get("top_opportunity_recipe"))
    large_twoopt_signal = _large_twoopt_postrun_signal(postrun_reports)
    if recipe:
        family = str(recipe.get("mechanism_family") or REQUIRED_MECHANISM_ID)
        requirements.append(
            OpportunityEvidenceRequirement(
                requirement_id="large_instance_two_opt_objective_runtime_requirement",
                mechanism_family=family,
                status=_large_twoopt_requirement_status(large_twoopt_signal),
                summary=(
                    "Bounded large-instance intra-route two-opt needs "
                    "current-run pair-level objective, feasibility, route-count, "
                    "and wall-clock evidence before solver-improvement claims."
                ),
                recommended_action=str(recipe.get("next_required_direction") or ""),
                required_observations=_string_tuple(
                    recipe.get("required_observations")
                ),
                protected_cases=_string_tuple(recipe.get("protected_cases")),
                reason_codes=_large_twoopt_requirement_reason_codes(
                    large_twoopt_signal
                ),
            )
        )
        protected_observations = _string_tuple(
            recipe.get("protected_case_required_evidence")
        )
        if protected_observations:
            requirements.append(
                OpportunityEvidenceRequirement(
                    requirement_id="cmt2_cmt4_case_protection",
                    mechanism_family=family,
                    status=_large_twoopt_requirement_status(large_twoopt_signal),
                    summary=(
                        "Prepared CVRP follow-up must keep CMT2/CMT4 protection "
                        "visible or record an unresolved protection caveat."
                    ),
                    required_observations=protected_observations,
                    protected_cases=_string_tuple(recipe.get("protected_cases")),
                    reason_codes=("CVRP_PROTECTED_CASE_REVIEW_REQUIRED",),
                )
            )
    for item in _list_of_mappings(source.get("measurable_opportunity_classes")):
        family = str(item.get("mechanism_family") or "").strip()
        if not family or family == REQUIRED_MECHANISM_ID:
            continue
        requirements.append(
            OpportunityEvidenceRequirement(
                requirement_id=f"{_slug(family)}_required_evidence",
                mechanism_family=family,
                status="eligible_if_required_evidence_declared",
                summary=str(item.get("required_evidence") or ""),
                required_observations=_string_tuple(item.get("required_evidence")),
                reason_codes=("DIRECT_EFFECT_EVIDENCE_REQUIRED",),
            )
        )
    return tuple(requirements)


def _large_twoopt_postrun_signal(
    postrun_reports: tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    for report in postrun_reports:
        payload = _mapping_or_empty(report)
        nested = _mapping_or_empty(payload.get("cvrp_large_twoopt_summary"))
        if nested:
            payload = nested
        if (
            payload.get("schema_version")
            == "scion.postrun_cvrp_large_twoopt_summary.v1"
        ):
            return payload
    return {}


def _large_twoopt_requirement_status(signal: Mapping[str, Any]) -> str:
    if not signal:
        return "current_run_required"
    if signal.get("current_run_evidence") is not True:
        return "current_run_required"
    if signal.get("available") is not True:
        return "postrun_summary_unavailable"
    evidence = _mapping_or_empty(signal.get("evidence"))
    mechanism = _mapping_or_empty(evidence.get("large_twoopt_mechanism"))
    if mechanism.get("direct_evidence_ready") is True:
        return "current_run_direct_evidence_ready"
    if mechanism.get("mechanism_family_available") is True:
        return "current_run_selected_but_direct_evidence_not_ready"
    return "current_run_checklist_not_ready"


def _large_twoopt_requirement_reason_codes(
    signal: Mapping[str, Any],
) -> tuple[str, ...]:
    if not signal:
        return ("CURRENT_RUN_EVIDENCE_REQUIRED",)
    gaps = _string_tuple(signal.get("evidence_gaps"))
    if gaps:
        return gaps
    interpretation = str(signal.get("interpretation") or "").strip()
    return (interpretation,) if interpretation else ()


def _protected_cases() -> tuple[ProtectedCaseSummary, ...]:
    required = (
        "paired objective delta",
        "feasibility status",
        "route-count status",
        "wall-clock budget status",
    )
    return tuple(
        ProtectedCaseSummary(
            case_id=case_id,
            reason="protected CVRP regression and transfer case",
            required_evidence=required,
        )
        for case_id in PROTECTED_CASES
    )


def _default_avoid(source: Mapping[str, Any]) -> tuple[AvoidedMechanismSummary, ...]:
    return tuple(
        AvoidedMechanismSummary(
            mechanism_family=str(item),
            reason="prior weak, negative, or insufficient direct-effect evidence",
        )
        for item in _string_tuple(source.get("default_avoid_directions"))
    )


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list_of_mappings(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _string_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        items = [value]
    else:
        try:
            items = list(value)
        except TypeError:
            return ()
    return tuple(str(item).strip() for item in items if str(item).strip())


def _slug(value: str) -> str:
    return "_".join(
        part for part in value.lower().replace("-", "_").split("_") if part
    )
