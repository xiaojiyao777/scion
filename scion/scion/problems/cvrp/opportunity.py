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
    SUCCESSOR_OPPORTUNITY_FAMILIES,
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
    successor_signal = _successor_postrun_signal(postrun_reports)
    large_twoopt_reviewed = _large_twoopt_reviewed_no_positive_at_mde(
        large_twoopt_signal
    )
    if not large_twoopt_signal:
        large_twoopt_reviewed = _recipe_large_twoopt_reviewed_no_positive_at_mde(
            recipe
        )
    if large_twoopt_reviewed:
        requirements.extend(_successor_evidence_requirements(successor_signal))
    if recipe:
        family = str(recipe.get("mechanism_family") or REQUIRED_MECHANISM_ID)
        requirements.append(
            OpportunityEvidenceRequirement(
                requirement_id="large_instance_two_opt_objective_runtime_requirement",
                mechanism_family=family,
                status=_large_twoopt_requirement_status(
                    large_twoopt_signal,
                    "large_instance_two_opt_objective_runtime_requirement",
                ),
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
                    large_twoopt_signal,
                    "large_instance_two_opt_objective_runtime_requirement",
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
                    status=_large_twoopt_requirement_status(
                        large_twoopt_signal,
                        "cmt2_cmt4_case_protection",
                    ),
                    summary=(
                        "Prepared CVRP follow-up must produce case-level "
                        "total_distance deltas for CMT2/CMT4, or record a "
                        "formal case-selection caveat; mentioning protection "
                        "without case deltas is not enough."
                    ),
                    required_observations=_large_twoopt_requirement_observations(
                        protected_observations,
                        large_twoopt_signal,
                        "cmt2_cmt4_case_protection",
                    ),
                    protected_cases=_string_tuple(recipe.get("protected_cases")),
                    reason_codes=_large_twoopt_requirement_reason_codes(
                        large_twoopt_signal,
                        "cmt2_cmt4_case_protection",
                    )
                    or ("CVRP_PROTECTED_CASE_REVIEW_REQUIRED",),
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


_SUCCESSOR_COMMON_OBSERVATIONS = (
    "material causal-path difference from reviewed large_instance_intra_route_two_opt_seed",
    "per-case total_distance delta tied to the changed mechanism",
    "feasibility and route-count preservation or explicit caveat",
    "runtime budget evidence under the formal policy",
    "CMT2/CMT4 protection plan or unresolved protected-case caveat",
)

_SUCCESSOR_REQUIREMENT_SPECS = {
    "acceptance_or_adaptive_weighting": {
        "requirement_id": "successor_acceptance_adaptive_weighting_direct_effect",
        "summary": (
            "An acceptance/adaptive-weighting successor is eligible only if it "
            "directly changes the acceptance or operator-credit causal path "
            "and separates its objective effect from downstream local-search "
            "and annealing noise."
        ),
        "recommended_action": (
            "For post_repair_effect_credit_weighting, record operator pair, q, "
            "current/best objective before repair, post-repair and post-polish "
            "candidate objective, old coarse score, new credit, weights before/"
            "after update, accepted/new-best counts, and per-case formal "
            "total_distance evidence."
        ),
        "required_observations": (
            "material causal-path difference from reviewed rank-gap, route-pressure, and runtime-allocation variants",
            "operator pair and q for each credited ALNS iteration",
            "current and best objective before repair",
            "candidate total_distance after repair and after polish",
            "old coarse score and new post-repair credit",
            "destroy and repair weights before and after segment update",
            "accepted and new-best counts under the declared mechanism id",
            "per-case total_distance delta tied to adaptive credit changes",
            "feasibility and route-count preservation or explicit caveat",
            "runtime budget evidence under the formal policy",
            "CMT2/CMT4 protection plan or unresolved protected-case caveat",
        ),
        "reason_codes": (
            "ADAPTIVE_WEIGHTING_DIRECT_EFFECT_REQUIRED",
            "POST_REPAIR_CREDIT_ATTRIBUTION_REQUIRED",
        ),
    },
    "bounded_local_search_variant": {
        "requirement_id": "successor_bounded_local_search_direct_effect",
        "summary": (
            "The large-instance intra-route two-opt checklist is proven "
            "but measured no positive-at-MDE effect; a bounded local-search "
            "successor must change a different causal path before another "
            "branch slot is spent."
        ),
        "recommended_action": (
            "Prefer a bounded local-search mechanism outside the reviewed "
            "seed path, with direct route-level objective deltas and "
            "formal-budget evidence."
        ),
        "required_observations": _SUCCESSOR_COMMON_OBSERVATIONS,
        "reason_codes": (
            "CVRP_LARGE_TWOOPT_REVIEWED_NO_POSITIVE_AT_MDE",
            "SUCCESSOR_CAUSAL_PATH_REQUIRED",
        ),
    },
    "destroy_repair_selection": {
        "requirement_id": "successor_destroy_repair_direct_effect",
        "summary": (
            "A destroy/repair successor is eligible only if it materially "
            "changes removal or repair selection and reports direct "
            "per-case objective attribution."
        ),
        "recommended_action": (
            "Do not repeat unchanged demand-slack, route-merge, or "
            "cluster-biased variants; name the new selection rule and "
            "objective-effect telemetry before screening."
        ),
        "required_observations": _SUCCESSOR_COMMON_OBSERVATIONS,
        "reason_codes": (
            "MATERIAL_DIFFERENCE_REQUIRED",
            "DIRECT_OBJECTIVE_EFFECT_REQUIRED",
        ),
    },
    "construction_seed_portfolio": {
        "requirement_id": "successor_construction_seed_direct_effect",
        "summary": (
            "A construction seed/portfolio successor is eligible only if it "
            "isolates seed quality with a same-run baseline or accepted "
            "candidate-vs-baseline objective delta before downstream ALNS/VNS "
            "attribution becomes ambiguous."
        ),
        "recommended_action": (
            "Record activation for the construction path, then report a direct "
            "seed-selection comparison or accepted delta under the declared "
            "mechanism id before claiming solver improvement."
        ),
        "required_observations": (
            "same-run seed baseline or accepted candidate-vs-baseline delta",
            "per-case total_distance delta tied to the selected construction seed",
            "feasibility and route-count preservation or explicit caveat",
            "runtime budget evidence under the formal policy",
            "CMT2/CMT4 protection plan or unresolved protected-case caveat",
        ),
        "reason_codes": (
            "CONSTRUCTION_SEED_NEEDS_DIRECT_EFFECT",
            "SAME_RUN_SEED_BASELINE_REQUIRED",
        ),
    },
}


def _successor_evidence_requirements(
    successor_signal: Mapping[str, Any] | None = None,
) -> tuple[OpportunityEvidenceRequirement, ...]:
    requirements: list[OpportunityEvidenceRequirement] = []
    for family in SUCCESSOR_OPPORTUNITY_FAMILIES:
        spec = _SUCCESSOR_REQUIREMENT_SPECS.get(family)
        if not spec:
            continue
        requirements.append(
            OpportunityEvidenceRequirement(
                requirement_id=str(spec["requirement_id"]),
                mechanism_family=family,
                status=_successor_requirement_status(
                    successor_signal,
                    family,
                ),
                summary=str(spec["summary"]),
                recommended_action=str(spec["recommended_action"]),
                required_observations=tuple(spec["required_observations"]),
                protected_cases=PROTECTED_CASES,
                reason_codes=_successor_requirement_reason_codes(
                    successor_signal,
                    family,
                )
                or tuple(spec["reason_codes"]),
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


def _successor_postrun_signal(
    postrun_reports: tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    for report in postrun_reports:
        payload = _mapping_or_empty(report)
        nested = _mapping_or_empty(payload.get("cvrp_successor_summary"))
        if nested:
            payload = nested
        if payload.get("schema_version") == "scion.postrun_cvrp_successor_summary.v1":
            return payload
    return {}


def _successor_requirement_status(
    signal: Mapping[str, Any] | None,
    family: str,
) -> str:
    signal = _mapping_or_empty(signal)
    if not signal:
        return "successor_required_after_large_twoopt_no_positive_at_mde"
    if signal.get("current_run_evidence") is not True:
        return "current_run_required"
    proof = _successor_family_proof(signal, family)
    if not proof:
        return "current_run_no_matching_successor_evidence"
    if proof.get("checklist_status") == "proven":
        outcome = str(proof.get("outcome_status") or "").strip()
        if outcome == "positive_effect_observed":
            return "current_run_direct_evidence_positive"
        if outcome == "measured_no_positive_at_mde":
            return "reviewed_no_positive_at_mde"
        return "current_run_required_evidence_observed"
    if proof.get("mechanism_family_available") is True:
        return "current_run_selected_but_required_evidence_missing"
    return "current_run_checklist_not_ready"


def _successor_requirement_reason_codes(
    signal: Mapping[str, Any] | None,
    family: str,
) -> tuple[str, ...]:
    signal = _mapping_or_empty(signal)
    if not signal:
        return ()
    proof = _successor_family_proof(signal, family)
    if not proof:
        return ("NO_MATCHING_SUCCESSOR_EVIDENCE",)
    missing = _string_tuple(proof.get("missing"))
    if missing:
        return missing
    outcome = str(proof.get("outcome_status") or "").strip()
    return (outcome,) if outcome else ()


def _successor_family_proof(
    signal: Mapping[str, Any],
    family: str,
) -> dict[str, Any]:
    by_family = _mapping_or_empty(signal.get("by_family"))
    return _mapping_or_empty(by_family.get(family))


def _large_twoopt_requirement_status(
    signal: Mapping[str, Any],
    requirement_id: str,
) -> str:
    if not signal:
        return "current_run_required"
    if signal.get("current_run_evidence") is not True:
        return "current_run_required"
    evidence = _mapping_or_empty(signal.get("evidence"))
    requirement = _large_twoopt_requirement_payload(evidence, requirement_id)
    if requirement:
        if requirement.get("status") == "observed":
            if (
                requirement_id
                == "large_instance_two_opt_objective_runtime_requirement"
                and _mapping_or_empty(
                    evidence.get("evidence_requirement_statuses")
                ).get("complete")
                is True
                and str(requirement.get("outcome_status") or "").strip()
                == "measured_no_positive_at_mde"
            ):
                return "reviewed_no_positive_at_mde"
            return "current_run_required_evidence_observed"
        return "current_run_selected_but_required_evidence_missing"
    if signal.get("available") is not True:
        return "postrun_summary_unavailable"
    mechanism = _mapping_or_empty(evidence.get("large_twoopt_mechanism"))
    if mechanism.get("direct_evidence_ready") is True:
        return "current_run_direct_evidence_ready"
    if mechanism.get("mechanism_family_available") is True:
        return "current_run_selected_but_direct_evidence_not_ready"
    return "current_run_checklist_not_ready"


def _large_twoopt_requirement_reason_codes(
    signal: Mapping[str, Any],
    requirement_id: str | None = None,
) -> tuple[str, ...]:
    if not signal:
        return ("CURRENT_RUN_EVIDENCE_REQUIRED",)
    if requirement_id:
        evidence = _mapping_or_empty(signal.get("evidence"))
        requirement = _large_twoopt_requirement_payload(evidence, requirement_id)
        if requirement:
            missing = _string_tuple(requirement.get("missing_fields"))
            if missing:
                return missing
            outcome = str(requirement.get("outcome_status") or "").strip()
            if outcome and outcome != "not_outcome_requirement":
                return (outcome,)
            return ()
    gaps = _string_tuple(signal.get("evidence_gaps"))
    if gaps:
        return gaps
    interpretation = str(signal.get("interpretation") or "").strip()
    return (interpretation,) if interpretation else ()


def _large_twoopt_reviewed_no_positive_at_mde(
    signal: Mapping[str, Any],
) -> bool:
    if not signal:
        return False
    if signal.get("current_run_evidence") is not True:
        return False
    evidence = _mapping_or_empty(signal.get("evidence"))
    statuses = _mapping_or_empty(evidence.get("evidence_requirement_statuses"))
    if statuses.get("complete") is not True:
        return False
    requirement = _large_twoopt_requirement_payload(
        evidence,
        "large_instance_two_opt_objective_runtime_requirement",
    )
    return (
        requirement.get("status") == "observed"
        and str(requirement.get("outcome_status") or "").strip()
        == "measured_no_positive_at_mde"
    )


def _recipe_large_twoopt_reviewed_no_positive_at_mde(
    recipe: Mapping[str, Any],
) -> bool:
    return (
        str(recipe.get("mechanism_family") or "").strip() == REQUIRED_MECHANISM_ID
        and str(recipe.get("review_status") or "").strip()
        == "reviewed_no_positive_at_mde"
    )


def _large_twoopt_requirement_observations(
    base_observations: tuple[str, ...],
    signal: Mapping[str, Any],
    requirement_id: str,
) -> tuple[str, ...]:
    evidence = _mapping_or_empty(signal.get("evidence"))
    requirement = _large_twoopt_requirement_payload(evidence, requirement_id)
    observations = list(base_observations)
    missing = _string_tuple(requirement.get("missing_fields"))
    for item in missing:
        observations.append(f"current postrun missing: {item}")
    required_cases = _string_tuple(requirement.get("required_protected_cases"))
    observed_cases = set(_string_tuple(requirement.get("protected_cases_observed")))
    missing_cases = [case for case in required_cases if case not in observed_cases]
    if missing_cases:
        observations.append(
            "case-level total_distance deltas still required for protected "
            f"cases: {', '.join(missing_cases)}"
        )
    return tuple(dict.fromkeys(observations))


def _large_twoopt_requirement_payload(
    evidence: Mapping[str, Any],
    requirement_id: str,
) -> dict[str, Any]:
    statuses = _mapping_or_empty(evidence.get("evidence_requirement_statuses"))
    requirements = _mapping_or_empty(statuses.get("requirements"))
    return _mapping_or_empty(requirements.get(requirement_id))


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
