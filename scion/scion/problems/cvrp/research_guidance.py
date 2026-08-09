"""Direct, problem-owned CVRP research guidance.

This module describes the optimization objective, the CVRP-owned source and
interface boundary, measurement interpretation, causal attribution, and a
compact cross-campaign research prior.  The prior is proposal context only; it
does not select a mechanism, module, or file for the next proposal.
"""

from __future__ import annotations

from typing import Any, Mapping

from scion.research_guidance import (
    EvidenceRequirement,
    GuidanceBlock,
    GuidanceContext,
    MeasurementGuidanceSummary,
    ResearchGuidanceContract,
    validate_research_guidance_contract,
)


CVRP_PROBLEM_FAMILY = "cvrp"
CURRENT_QUESTION = (
    "What CVRP-owned algorithmic change can improve final total_distance on "
    "the declared evaluation surface while preserving feasibility and route "
    "validity, and what observations support attribution of the final result "
    "to that change?"
)
DECISION_BOUNDARY = (
    "This problem guidance is proposal context only. Protocol results and "
    "DecisionFeatures remain the authority for evaluation and promotion."
)
SOLVER_DESIGN_SOURCE_GUIDANCE = (
    "Work within the CVRP-owned algorithm package: "
    "`policies/baseline_algorithm.py` and cohesive modules under "
    "`policies/baseline_modules/`. Preserve the stable "
    "`solve(instance, rng, time_limit_sec, context)` interface. Use the "
    "complete visible source map and operator interface supplied with the "
    "proposal context to understand visible symbols and editable files. Keep "
    "generic Scion core, Protocol, DecisionFeatures, and `solver.py` unchanged. "
    "Prefer the smallest complete causal implementation that can test the hypothesis. "
    "Preserve unrelated code, imports, scheduling, telemetry, and terminal "
    "return behavior; use multiple owner files only when the same mechanism "
    "genuinely requires them."
)
CROSS_CAMPAIGN_RESEARCH_PRIOR = (
    (
        "Previously evaluated route-segment and cross-route exchanges, "
        "destroy-size schedules, insertion-cost lookahead, construction-seed "
        "selection, route-pair overlap targeting, double-bridge moves, and "
        "adaptive embedded-VNS allocation were neutral or negative on final "
        "total_distance. Broad removal of VNS was also negative. These are "
        "observations, not proposal prohibitions."
    ),
    (
        "Historical screening-level evidence around SWAP* and initial-VNS "
        "budget allocation was mixed and cumulative; it did not isolate a "
        "causal mechanism. This is a neutral lead, not a required direction."
    ),
    (
        "Recent ejection evidence is mixed and implementation-sensitive. An "
        "older deeper route-preserving chain was 0W/4L/4T cases with median "
        "-11.5 and only about 74 ALNS iterations versus 1,631 for B0. In the "
        "open-research R1 partial run, a bounded completion-aware depth-one "
        "repair reproduced a sparse positive direction after expansion at "
        "6W/1L/5T cases, median +3.75 with CI [0,11], but recorded 186 "
        "aggregate repair errors (8.7% of all ALNS iterations) without an "
        "exposed operator-local denominator and did not advance; a cumulative "
        "depth-two "
        "variant was negative. These observations neither require nor forbid "
        "ejection research, depth-one refinement, or a different direction."
    ),
    (
        "Corrected R2's strongest result was elapsed-budget simulated "
        "annealing: its exact 12-case quality screen was 6W/1L/5T cases, "
        "49W/20L/27T pairs, and median final total_distance improvement +2.75 "
        "with CI [0,11]. It did not pass the fixed R2 wins/all-cases rule and "
        "is not a hidden promotion. The implementation removed nearly all "
        "late worsening acceptances and increased best updates, but its "
        "progress denominator omitted construction, initial VNS, and the "
        "tighter outer deadline, while its temperature update lagged one "
        "iteration. These are neutral source-grounded leads, not a required "
        "mechanism or host-mandated fix."
    ),
)
FEASIBILITY_GUIDANCE = (
    "A candidate result is interpretable only when capacity, customer "
    "coverage, depot, route structure, and reported objective consistency "
    "remain valid. Report route-count changes alongside feasibility and final "
    "total_distance."
)
ATTRIBUTION_GUIDANCE = (
    "Keep attempted changes, accepted route-state transitions, direct "
    "objective changes, downstream search effects, and final total_distance "
    "distinct. Attribute improvement only to observations available on the "
    "changed execution path."
)
MEASUREMENT_GUIDANCE = (
    "Interpret paired total_distance with case-level variation, the declared "
    "measurement scale, and uncertainty. Activation or an intermediate local "
    "delta alone does not establish improvement of the final solver result."
)


class CvrpResearchGuidanceProvider:
    """Problem-owned port for direct CVRP research guidance."""

    def build_guidance_contract(
        self,
        context: GuidanceContext,
    ) -> ResearchGuidanceContract:
        return build_cvrp_research_guidance_contract(context)


def build_cvrp_research_guidance_contract(
    context: GuidanceContext | None = None,
    *,
    measurement_opportunity_diagnostics: Mapping[str, Any] | None = None,
) -> ResearchGuidanceContract:
    """Build open CVRP guidance with factual prior but no target steering."""

    problem_family = CVRP_PROBLEM_FAMILY
    if context is not None and context.problem_family:
        problem_family = context.problem_family
    if problem_family != CVRP_PROBLEM_FAMILY:
        raise ValueError(
            "CVRP research guidance requires problem_family="
            f"{CVRP_PROBLEM_FAMILY!r}, got {problem_family!r}"
        )

    measurement = measurement_opportunity_diagnostics
    if measurement is None and context is not None:
        candidate = context.metadata.get("measurement_opportunity_diagnostics")
        if isinstance(candidate, Mapping):
            measurement = candidate

    contract = ResearchGuidanceContract(
        schema_version="scion.cvrp_research_guidance_contract.v3",
        problem_family=problem_family,
        current_question=CURRENT_QUESTION,
        required_mechanisms=(),
        evidence_requirements=(
            EvidenceRequirement(
                requirement_id="cvrp_objective_feasibility_attribution",
                category="typed_attribution_guidance",
                description=(
                    "Relate the changed CVRP execution path to accepted route "
                    "state, final total_distance, feasibility, and route validity."
                ),
                required_fields=(
                    "attempted change",
                    "accepted route-state transition",
                    "direct objective change when observable",
                    "downstream and final total_distance",
                    "feasibility and route validity",
                ),
            ),
            EvidenceRequirement(
                requirement_id="cvrp_measurement_interpretation",
                category="measurement_guidance",
                description=MEASUREMENT_GUIDANCE,
            ),
        ),
        avoid_rules=(),
        continuity_requirements=(),
        guidance_blocks=(
            GuidanceBlock(
                block_id="cvrp_source_interface",
                category="source_interface",
                title="CVRP source and interface",
                lines=(SOLVER_DESIGN_SOURCE_GUIDANCE,),
            ),
            GuidanceBlock(
                block_id="cvrp_objective_feasibility",
                category="objective_feasibility",
                title="Objective and feasibility",
                lines=(CURRENT_QUESTION, FEASIBILITY_GUIDANCE),
            ),
            GuidanceBlock(
                block_id="cvrp_typed_attribution",
                category="typed_attribution_guidance",
                title="Causal attribution",
                lines=(ATTRIBUTION_GUIDANCE,),
            ),
            GuidanceBlock(
                block_id="cvrp_measurement",
                category="measurement_guidance",
                title="Measurement interpretation",
                lines=(MEASUREMENT_GUIDANCE,),
            ),
            GuidanceBlock(
                block_id="cvrp_cross_campaign_prior",
                category="research_prior",
                title="Cross-campaign research prior",
                lines=CROSS_CAMPAIGN_RESEARCH_PRIOR,
            ),
        ),
        measurement_summary=_measurement_summary(measurement),
        decision_boundary=DECISION_BOUNDARY,
    )
    validate_research_guidance_contract(contract)
    return contract


def build_cvrp_research_focus(
    *,
    measurement_opportunity_diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the minimal report-only focus used by prepared-run tooling."""

    contract = build_cvrp_research_guidance_contract(
        measurement_opportunity_diagnostics=measurement_opportunity_diagnostics,
    )
    return {
        "schema_version": "scion.cvrp_research_focus.v3",
        "scope": "report_only",
        "current_question": contract.current_question,
        "decision_boundary": contract.decision_boundary,
    }


def _measurement_summary(
    measurement: Mapping[str, Any] | None,
) -> MeasurementGuidanceSummary:
    payload = measurement if isinstance(measurement, Mapping) else {}
    context = payload.get("measurement_context")
    if not isinstance(context, Mapping):
        context = payload
    metric = str(context.get("metric") or "total_distance")
    mde = context.get("screening_mde_at_power_80")
    practical = context.get("practical_screen_delta")
    summary = f"Interpret {metric} using paired and case-level evidence"
    if mde not in (None, ""):
        summary += f"; formal screening MDE={mde}"
    if practical not in (None, ""):
        summary += f"; practical screening delta={practical}"
    return MeasurementGuidanceSummary(
        summary_id="cvrp_measurement_guidance",
        summary=summary,
        metric_names=(metric, "feasibility", "route_count"),
        limitations=(
            "activation and intermediate deltas do not establish final effect",
            "aggregate results can hide case-level variation",
        ),
    )
