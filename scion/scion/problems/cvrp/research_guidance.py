"""CVRP-owned research guidance provider for prepared campaign handoffs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from scion.research_guidance import (
    AvoidRule,
    ContinuityRequirement,
    EvidenceRequirement,
    GuidanceBlock,
    GuidanceContext,
    MeasurementGuidanceSummary,
    RequiredMechanism,
    ResearchGuidanceContract,
    validate_research_guidance_contract,
)

CVRP_PROBLEM_FAMILY = "cvrp"
LARGE_INSTANCE_TWO_OPT_SEED_REPORT = (
    "scion/docs/experiments/v0.4/"
    "v04-vrp-large-instance-two-opt-seed-evidence-20260618.md"
)
REQUIRED_MECHANISM_ID = "large_instance_intra_route_two_opt_seed"
SUCCESSOR_OPPORTUNITY_FAMILIES = (
    "bounded_local_search_variant",
    "destroy_repair_selection",
)
REVIEWED_SUCCESSOR_MECHANISM_ID = "bounded_2node_cross_exchange"
REVIEWED_SUCCESSOR_FAMILY = "bounded_local_search_variant"
REVIEWED_SUCCESSOR_OUTCOME_STATUS = "measured_no_positive_at_mde"
REVIEWED_OR_OPT_REINSERT_MECHANISM_ID = "intra_route_or_opt_reinsert"
REVIEWED_OR_OPT_REINSERT_FAMILY = "bounded_local_search_variant"
REVIEWED_OR_OPT_REINSERT_OUTCOME_STATUS = "measured_no_positive_at_mde"
REVIEWED_MECHANISM_IDS = (
    REQUIRED_MECHANISM_ID,
    REVIEWED_SUCCESSOR_MECHANISM_ID,
    REVIEWED_OR_OPT_REINSERT_MECHANISM_ID,
)
PROTECTED_CASES = ("CMT2", "CMT4")

DEFAULT_AVOID_DIRECTIONS = (
    "unchanged broad VNS removal",
    "pure ALNS/no-polish",
    "simple initial-VNS disablement",
    "unbounded large-instance two-opt fallback without deadline or wall-clock evidence",
    "raw cadence-2",
    "recent-best/stall gating",
    "fixed early-8",
    "tested share70 cap/rescue variants",
    "route-merge absorption",
    "demand-slack regret insertion",
    "cross-route 2-opt reconnect",
    "cluster-biased worst removal",
    "route-limit seed diversification",
    "rank-gap acceptance gates after current-run no-effect expansion",
    (
        "route-pressure acceptance/adaptive-weighting variants without a new "
        "non-acceptance causal path or direct objective-effect telemetry"
    ),
    "unchanged bounded_interroute_2opt_bridge local-search bridge",
    "high-asymmetric-promise bounded_interroute_2opt_bridge refinement",
    "unchanged cmt_slack_aware_segment_swap local-search segment swap",
    (
        "unchanged bounded_2node_cross_exchange bounded-local-search successor "
        "after cvrp_successor_summary measured_no_positive_at_mde review"
    ),
    (
        "unchanged intra_route_or_opt_reinsert bounded-local-search successor "
        "after cvrp_successor_summary measured_no_positive_at_mde review"
    ),
    (
        "ec052599-style weak_positive continuation when declared primary "
        "mechanism telemetry is missing or not_evaluated/not_triggered"
    ),
)

LARGE_INSTANCE_TWO_OPT_CONSTRAINTS = {
    "schema_version": "scion.cvrp_large_instance_two_opt_constraints.v1",
    "scope": "proposal_only_prepared_handoff",
    "seed_report": LARGE_INSTANCE_TWO_OPT_SEED_REPORT,
    "proposal_visibility_only": True,
    "decision_features_excluded": True,
    "implementation_constraints": [
        (
            "derive an explicit monotonic-clock deadline or remaining-time guard "
            "from the solver time_limit/start time before any large-instance "
            "two-opt work"
        ),
        (
            "check remaining wall-clock budget before each route, sweep, and "
            "accepted improvement; stop cleanly when the deadline is reached"
        ),
        (
            "bound effort with route/sweep/improvement caps and skip oversized "
            "routes when the remaining budget is too small"
        ),
        (
            "do not call unbounded two_opt_intra or VNS above the vns_threshold; "
            "use a bounded wrapper or deadline-aware operator"
        ),
        (
            "preserve feasibility, remove empty routes, and report route-count "
            "changes under max_routes constraints"
        ),
    ],
    "required_pair_evidence": [
        "total_distance delta by case and seed",
        "feasibility before and after local search",
        "route count before and after local search",
        "elapsed wall-clock plus budget-saturation or timeout status",
        (
            "same split, cases, seeds, and time-limit controls as the prepared "
            "run unless explicit replay controls are documented"
        ),
    ],
    "default_reject_directions": [
        (
            "unbounded vrp/src/solver.py fallback that calls two_opt_intra "
            "without a deadline"
        ),
        "operator activation claims without objective and wall-clock evidence",
        "route-count regressions without feasibility and objective attribution",
    ],
}

CASE_PROTECTION_REQUIREMENTS = {
    "schema_version": "scion.cvrp_case_protection_requirements.v1",
    "scope": "proposal_only_prepared_handoff",
    "proposal_visibility_only": True,
    "decision_features_excluded": True,
    "protected_cases": list(PROTECTED_CASES),
    "rules": [
        (
            "When revisiting construction, route-merge, demand-slack, VNS, or "
            "share70-derived mechanisms after prior CMT2/CMT4 losses, the "
            "target intent or hypothesis must name the CMT2/CMT4 protection "
            "plan before another branch slot is spent."
        ),
        (
            "Same-branch follow-up should keep CMT2 and CMT4 in formal "
            "coverage through priority case retention when those cases are "
            "available in the selected split."
        ),
        (
            "A materially different problem-owned solver mechanism must still "
            "explain how it avoids repeating the CMT2/CMT4 losses or record "
            "that the protected cases remain an unresolved caveat."
        ),
        (
            "Do not hardcode case ids, BKS values, seeds, split membership, "
            "or protected-case thresholds in solver code."
        ),
    ],
    "required_evidence": [
        "live target-intent or hypothesis trace mentions CMT2/CMT4 protection",
        (
            "formal screening includes CMT2 and CMT4 or records an unresolved "
            "case-selection caveat"
        ),
        "case-level total_distance deltas for CMT2 and CMT4",
    ],
}

RESUME_CONTINUITY_REQUIREMENTS = {
    "schema_version": "scion.cvrp_resume_continuity_requirements.v1",
    "scope": "proposal_only_prepared_handoff",
    "proposal_visibility_only": True,
    "decision_features_excluded": True,
    "fallback_sources": [
        "prepared_research_focus",
        "copied_agentic_session_trace_index",
        "copied_target_intent_or_hypothesis_traces",
    ],
    "rules": [
        (
            "A sparse resume with zero branch cards must not be treated as an "
            "empty campaign; use prepared research_focus plus copied "
            "target-intent or hypothesis traces as the continuity seed."
        ),
        (
            "Before the first new CVRP branch, identify whether the proposal "
            "continues bounded large-instance two-opt with CMT2/CMT4 "
            "protection or names a materially different problem-owned causal "
            "path."
        ),
        (
            "Do not spend a branch slot on default-avoid mechanism families "
            "unless the hypothesis explains why prior evidence no longer "
            "applies."
        ),
    ],
    "required_evidence": [
        (
            "live target-intent or hypothesis trace references copied "
            "target-intent, hypothesis, or agentic session trace evidence "
            "when branch cards are absent"
        ),
        (
            "first live hypothesis names bounded large-instance "
            "two-opt/CMT2/CMT4 continuity or a different causal mechanism"
        ),
        "branch-continuity caveat is recorded if copied branch cards remain absent",
    ],
}
REVIEWED_SUCCESSOR_EVIDENCE = {
    "schema_version": "scion.cvrp_reviewed_successor_evidence.v1",
    "scope": "proposal_only_prepared_handoff",
    "proposal_visibility_only": True,
    "decision_features_excluded": True,
    "source_summary": "cvrp_successor_summary",
    "mechanisms": [
        {
            "mechanism_id": REVIEWED_SUCCESSOR_MECHANISM_ID,
            "mechanism_family": REVIEWED_SUCCESSOR_FAMILY,
            "checklist_status": "proven",
            "outcome_status": REVIEWED_SUCCESSOR_OUTCOME_STATUS,
            "next_use_rule": (
                "Do not spend the next CVRP branch on the same cross-exchange "
                "successor path unless the hypothesis names a materially new "
                "bounded-local-search causal path and direct per-case "
                "objective-effect evidence."
            ),
        },
        {
            "mechanism_id": REVIEWED_OR_OPT_REINSERT_MECHANISM_ID,
            "mechanism_family": REVIEWED_OR_OPT_REINSERT_FAMILY,
            "checklist_status": "proven",
            "outcome_status": REVIEWED_OR_OPT_REINSERT_OUTCOME_STATUS,
            "next_use_rule": (
                "Do not spend the next CVRP branch on the same intra-route "
                "Or-opt reinsertion path unless the hypothesis names a "
                "materially new bounded-local-search causal path and direct "
                "per-case objective-effect evidence."
            ),
        },
    ],
}
REVIEWED_SUCCESSOR_GUIDANCE_LINE = (
    "Reviewed successor evidence: "
    f"`{REVIEWED_SUCCESSOR_MECHANISM_ID}` and "
    f"`{REVIEWED_OR_OPT_REINSERT_MECHANISM_ID}` both belong to "
    f"`{REVIEWED_SUCCESSOR_FAMILY}` and have "
    f"`{REVIEWED_SUCCESSOR_OUTCOME_STATUS}` in `cvrp_successor_summary`; "
    "prefer destroy/repair, construction, or another non-reviewed causal path next."
)

NEXT_REQUIRED_DIRECTION = (
    "The `large_instance_intra_route_two_opt_seed` checklist is now "
    "reviewed evidence, not the next hard-required mechanism: current-run "
    "postrun evidence completed the activation/objective/phase and CMT2/CMT4 "
    "checklist but measured no positive effect at or above MDE. The first "
    "bounded successor, `bounded_2node_cross_exchange`, is also reviewed by "
    "`cvrp_successor_summary` with checklist proven and "
    "measured_no_positive_at_mde. The next bounded-local-search successor, "
    "`intra_route_or_opt_reinsert`, reached formal screening with complete "
    "activation/effect telemetry but was abandoned for low win-rate and "
    "negative aggregate effect. Rotate the next CVRP solver-design attempt "
    "preferably to `destroy_repair_selection`, construction, or another "
    "materially different problem-owned causal path; revisit bounded local "
    "search only when the hypothesis names a causal path distinct from "
    "cross-exchange and intra-route Or-opt reinsertion and carries direct "
    "per-case objective-effect evidence."
)
CURRENT_QUESTION = (
    "After both the large-instance intra-route two-opt checklist and the "
    "first two bounded-local-search successors were reviewed without "
    "positive-at-MDE solver effect, can a materially different CVRP-owned "
    "destroy/repair, construction, or non-reviewed local-search mechanism "
    "improve total_distance with direct per-case objective-effect evidence "
    "and without repeating prior default-avoid families?"
)
REQUIRED_EVIDENCE = (
    (
        "live target-intent or hypothesis explicitly names a successor "
        "opportunity family or records why revisiting "
        "large_instance_intra_route_two_opt_seed is justified despite the "
        "reviewed no-positive-at-MDE postrun evidence"
    ),
    (
        "bounded or deadline-aware implementation evidence for any "
        "large-instance two-opt follow-up"
    ),
    (
        "current-run pair-level total_distance, feasibility, route-count, "
        "and wall-clock evidence before objective-effect claims"
    ),
    (
        "CMT2/CMT4 protection evidence or an explicit unresolved caveat "
        "for mechanisms related to prior protected-case losses"
    ),
    (
        "copied target-intent, hypothesis, or agentic trace continuity "
        "when branch cards are absent from the sparse resume"
    ),
    (
        "direct activation-to-objective-effect evidence for any route-merge, "
        "construction-seed, destroy/repair, or acceptance-weighting claim"
    ),
    (
        "a new non-acceptance causal path before revisiting rank-gap or "
        "route-pressure acceptance after the current-run no-effect results"
    ),
    (
        "a materially different bounded local-search or destroy/repair "
        "causal path before revisiting bounded_interroute_2opt_bridge, "
        "its high-asymmetric-promise refinement, or "
        "cmt_slack_aware_segment_swap after the forced-local negative "
        "postrun evidence"
    ),
    (
        "do not continue a resumed weak-positive sparse two-opt branch "
        "unless current-run telemetry proves the declared primary mechanism "
        "activates with the exact large_instance_intra_route_two_opt_seed id"
    ),
    (
        "for successor bounded-local-search or destroy/repair attempts, "
        "declare the causal path difference from the reviewed intra-route "
        "two-opt seed, reviewed bounded_2node_cross_exchange successor, "
        "reviewed intra_route_or_opt_reinsert successor, and prior "
        "default-avoid families before spending another branch slot"
    ),
    (
        "prefer destroy_repair_selection, construction, or another "
        "non-reviewed CVRP-owned causal path after bounded_2node_cross_exchange "
        "and intra_route_or_opt_reinsert were reviewed no-positive-at-MDE; "
        "bounded-local-search revisits must name a new causal path and direct "
        "objective-effect telemetry"
    ),
)
MEASURABLE_OPPORTUNITY_CLASSES = (
    (
        "construction_seed_portfolio: require same-run seed baseline or "
        "same-mechanism accepted objective delta"
    ),
    (
        "destroy_repair_selection: require per-case total_distance deltas "
        "tied to the changed repair/removal choice"
    ),
    (
        "bounded_local_search_variant: require feasible route-level "
        "objective deltas with bounded search effort; after the reviewed "
        "bounded_2node_cross_exchange and intra_route_or_opt_reinsert "
        "no-positive-at-MDE results, require a bounded-local-search causal "
        "path distinct from cross-exchange and same-route Or-opt reinsertion"
    ),
    (
        "large_instance_intra_route_two_opt_seed: direct WSL external-control "
        "replay showed 8/8 feasible XL wins, and current-run checklist "
        "evidence is now complete, but the measured outcome remains "
        "no-positive-at-MDE; treat it as reviewed evidence/default-avoid "
        "unless a new causal path invalidates that postrun conclusion; see "
        f"{LARGE_INSTANCE_TWO_OPT_SEED_REPORT}"
    ),
    (
        "acceptance_or_adaptive_weighting: require direct move acceptance "
        "and downstream objective-effect telemetry; after current-run "
        "rank-gap and route-pressure no-effect expansions, do not spend "
        "the next CVRP branch slot here without a new non-acceptance "
        "causal path"
    ),
)
SUCCESSOR_PORTFOLIO_RULE = (
    "Because large_instance_intra_route_two_opt_seed has complete checklist "
    "evidence but no positive-at-MDE outcome, and "
    "bounded_2node_cross_exchange plus intra_route_or_opt_reinsert have now "
    "repeated that no-positive outcome as bounded successors, the next CVRP "
    "slot should prefer a destroy/repair, construction, or otherwise "
    "non-reviewed portfolio attempt. Use problem-owned evidence requirements "
    "and keep this guidance out of DecisionFeatures."
)
ROUTE_MERGE_EXCEPTION_RULE = (
    "Only continue route_merge_repair when the proposal names a causal path "
    "beyond tested local absorption/guarded variants and defines direct "
    "activation-to-objective-effect evidence."
)
CONSTRUCTION_SEED_RULE = (
    "Treat fallback activation, seed-pool size, or merely selecting a seed "
    "as activation/design evidence only; require same-run seed baseline or "
    "same-mechanism accepted delta for objective-effect claims."
)
MISSING_PRIMARY_TELEMETRY_RULE = (
    "If a resumed branch or row is weak_positive only from pair-level noise "
    "while telemetry diagnostics say the declared primary mechanism was "
    "not_evaluated/not_triggered or activation/runtime/effect fields are "
    "missing, treat it as inactive missing-telemetry feedback rather than "
    "positive same-mechanism evidence. Do not continue ec052599-style sparse "
    "two-opt polish unless the next hypothesis materially changes the "
    "causal activation path and records large_instance_intra_route_two_opt_seed "
    "on active paths."
)
DECISION_BOUNDARY = (
    "This focus is proposal/delegated-analysis guidance only and must not "
    "enter DecisionFeatures, Protocol gates, promotion input, or scheduler "
    "state."
)


class CvrpResearchGuidanceProvider:
    """Problem-owned port for CVRP research-guidance contracts."""

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
    """Build the typed CVRP guidance contract for generic rendering."""

    problem_family = CVRP_PROBLEM_FAMILY
    if context is not None and context.problem_family:
        problem_family = context.problem_family
    if problem_family != CVRP_PROBLEM_FAMILY:
        raise ValueError(
            "CVRP research guidance requires problem_family="
            f"{CVRP_PROBLEM_FAMILY!r}, got {problem_family!r}"
        )
    metadata = context.metadata if context is not None else {}
    measurement = measurement_opportunity_diagnostics
    if measurement is None:
        candidate = metadata.get("measurement_opportunity_diagnostics")
        if isinstance(candidate, Mapping):
            measurement = candidate

    contract = ResearchGuidanceContract(
        schema_version="scion.cvrp_research_guidance_contract.v1",
        problem_family=problem_family,
        current_question=CURRENT_QUESTION,
        required_mechanisms=_required_mechanisms(),
        evidence_requirements=_evidence_requirements(),
        avoid_rules=_avoid_rules(),
        continuity_requirements=_continuity_requirements(),
        guidance_blocks=_guidance_blocks(),
        measurement_summary=_measurement_summary(measurement),
        decision_boundary=DECISION_BOUNDARY,
    )
    validate_research_guidance_contract(contract)
    return contract


def build_cvrp_legacy_research_focus(
    *,
    measurement_opportunity_diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the compatibility research_focus dict used by prepared manifests."""

    validate_research_guidance_contract(
        build_cvrp_research_guidance_contract(
            measurement_opportunity_diagnostics=measurement_opportunity_diagnostics,
        )
    )
    return {
        "schema_version": "scion.cvrp_research_focus.v1",
        "scope": "report_only_prepared_handoff",
        "next_required_direction": NEXT_REQUIRED_DIRECTION,
        "required_mechanism_ids": [],
        "reviewed_mechanism_ids": list(REVIEWED_MECHANISM_IDS),
        "successor_opportunity_families": list(SUCCESSOR_OPPORTUNITY_FAMILIES),
        "reviewed_successor_evidence": deepcopy(REVIEWED_SUCCESSOR_EVIDENCE),
        "current_question": CURRENT_QUESTION,
        "required_evidence": list(REQUIRED_EVIDENCE),
        "measurement_opportunity_diagnostics": _legacy_mapping(
            measurement_opportunity_diagnostics
        ),
        "default_avoid_directions": list(DEFAULT_AVOID_DIRECTIONS),
        "large_instance_two_opt_constraints": deepcopy(
            LARGE_INSTANCE_TWO_OPT_CONSTRAINTS
        ),
        "measurable_opportunity_classes": list(MEASURABLE_OPPORTUNITY_CLASSES),
        "route_merge_exception_rule": ROUTE_MERGE_EXCEPTION_RULE,
        "construction_seed_rule": CONSTRUCTION_SEED_RULE,
        "missing_primary_telemetry_rule": MISSING_PRIMARY_TELEMETRY_RULE,
        "case_protection_requirements": deepcopy(CASE_PROTECTION_REQUIREMENTS),
        "resume_continuity_requirements": deepcopy(
            RESUME_CONTINUITY_REQUIREMENTS
        ),
        "decision_boundary": DECISION_BOUNDARY,
    }


def _required_mechanisms() -> tuple[RequiredMechanism, ...]:
    return ()


def _evidence_requirements() -> tuple[EvidenceRequirement, ...]:
    constraints = LARGE_INSTANCE_TWO_OPT_CONSTRAINTS
    return (
        EvidenceRequirement(
            requirement_id="successor_causal_path_direct_effect",
            category="successor_solver_opportunity_evidence",
            description=(
                "Require a materially different bounded-local-search or "
                "destroy/repair causal path after the reviewed large-twoopt "
                "plus bounded-local-search no-positive-at-MDE results."
            ),
            mechanism_ids=SUCCESSOR_OPPORTUNITY_FAMILIES,
            protected_items=PROTECTED_CASES,
            required_fields=(
                "successor mechanism family",
                "material causal-path difference from reviewed large-twoopt",
                "material causal-path difference from reviewed cross-exchange",
                "material causal-path difference from reviewed Or-opt reinsertion",
                "per-case total_distance delta tied to the changed mechanism",
                "feasibility and route-count preservation or explicit caveat",
                "runtime budget evidence under the formal policy",
            ),
        ),
        EvidenceRequirement(
            requirement_id="bounded_cross_exchange_reviewed_no_positive",
            category="reviewed_successor_evidence",
            description=(
                "The first bounded-local-search successor, "
                f"{REVIEWED_SUCCESSOR_MECHANISM_ID}, is reviewed evidence "
                f"with outcome {REVIEWED_SUCCESSOR_OUTCOME_STATUS}; do not "
                "repeat it as the next CVRP attempt without a materially new "
                "bounded-local-search causal path."
            ),
            mechanism_ids=(REVIEWED_SUCCESSOR_MECHANISM_ID, REVIEWED_SUCCESSOR_FAMILY),
            required_fields=(
                "cvrp_successor_summary checklist_status=proven",
                (
                    "cvrp_successor_summary "
                    f"outcome_status={REVIEWED_SUCCESSOR_OUTCOME_STATUS}"
                ),
                "new bounded-local-search causal path if revisited",
                "direct per-case total_distance objective-effect telemetry",
            ),
        ),
        EvidenceRequirement(
            requirement_id="or_opt_reinsert_reviewed_no_positive",
            category="reviewed_successor_evidence",
            description=(
                "The second bounded-local-search successor, "
                f"{REVIEWED_OR_OPT_REINSERT_MECHANISM_ID}, is reviewed "
                f"evidence with outcome {REVIEWED_OR_OPT_REINSERT_OUTCOME_STATUS}; "
                "do not repeat it as the next CVRP attempt without a "
                "materially new bounded-local-search causal path."
            ),
            mechanism_ids=(
                REVIEWED_OR_OPT_REINSERT_MECHANISM_ID,
                REVIEWED_OR_OPT_REINSERT_FAMILY,
            ),
            required_fields=(
                "cvrp_successor_summary checklist_status=proven",
                (
                    "cvrp_successor_summary "
                    f"outcome_status={REVIEWED_OR_OPT_REINSERT_OUTCOME_STATUS}"
                ),
                "new bounded-local-search causal path if revisited",
                "direct per-case total_distance objective-effect telemetry",
            ),
        ),
        EvidenceRequirement(
            requirement_id="large_instance_two_opt_reviewed_evidence",
            category="reviewed_bounded_local_search_evidence",
            description=(
                "The bounded two-opt seed checklist remains useful reviewed "
                "evidence, but no longer justifies a hard first-attempt "
                "mechanism after no positive-at-MDE outcome."
            ),
            mechanism_ids=(REQUIRED_MECHANISM_ID,),
            required_fields=tuple(
                str(item) for item in constraints["required_pair_evidence"]
            ),
        ),
        EvidenceRequirement(
            requirement_id="cmt2_cmt4_case_protection",
            category="protected_case_evidence",
            description=(
                "Protect the prior CMT2/CMT4 losses when revisiting related "
                "CVRP solver mechanisms."
            ),
            mechanism_ids=(REQUIRED_MECHANISM_ID,),
            protected_items=PROTECTED_CASES,
            required_fields=tuple(CASE_PROTECTION_REQUIREMENTS["required_evidence"]),
        ),
        EvidenceRequirement(
            requirement_id="primary_mechanism_telemetry",
            category="mechanism_activation_evidence",
            description=MISSING_PRIMARY_TELEMETRY_RULE,
            mechanism_ids=(REQUIRED_MECHANISM_ID,),
            required_fields=(
                "declared primary mechanism activation status",
                "mechanism-specific runtime or budget field",
                "mechanism-specific objective effect field",
            ),
        ),
    )


def _avoid_rules() -> tuple[AvoidRule, ...]:
    return tuple(
        AvoidRule(
            rule_id=f"default_avoid_{index:02d}_{_slug(text)}",
            category="default_avoid_direction",
            description=text,
            applies_to=_avoid_applies_to(text),
        )
        for index, text in enumerate(DEFAULT_AVOID_DIRECTIONS, start=1)
    )


def _avoid_applies_to(text: str) -> tuple[str, ...]:
    applies_to: list[str] = []
    if "two-opt" in text or "2-opt" in text:
        applies_to.append(REQUIRED_MECHANISM_ID)
    if REVIEWED_SUCCESSOR_MECHANISM_ID in text:
        applies_to.append(REVIEWED_SUCCESSOR_MECHANISM_ID)
    if REVIEWED_OR_OPT_REINSERT_MECHANISM_ID in text:
        applies_to.append(REVIEWED_OR_OPT_REINSERT_MECHANISM_ID)
    return tuple(applies_to)


def _continuity_requirements() -> tuple[ContinuityRequirement, ...]:
    resume = RESUME_CONTINUITY_REQUIREMENTS
    related_ids = (
        *SUCCESSOR_OPPORTUNITY_FAMILIES,
        REQUIRED_MECHANISM_ID,
        REVIEWED_SUCCESSOR_MECHANISM_ID,
        REVIEWED_OR_OPT_REINSERT_MECHANISM_ID,
        REVIEWED_SUCCESSOR_FAMILY,
        *PROTECTED_CASES,
    )
    return (
        ContinuityRequirement(
            requirement_id="successor_after_large_twoopt_review",
            category="prepared_focus_continuity",
            description=NEXT_REQUIRED_DIRECTION,
            related_ids=related_ids,
        ),
        ContinuityRequirement(
            requirement_id="sparse_resume_trace_continuity",
            category="resume_continuity",
            description=" ".join(str(item) for item in resume["rules"]),
            related_ids=tuple(str(item) for item in resume["fallback_sources"]),
        ),
    )


def _guidance_blocks() -> tuple[GuidanceBlock, ...]:
    constraints = LARGE_INSTANCE_TWO_OPT_CONSTRAINTS
    return (
        GuidanceBlock(
            block_id="successor_portfolio_direction",
            category="proposal_focus",
            title="Successor portfolio direction",
            lines=(
                NEXT_REQUIRED_DIRECTION,
                CURRENT_QUESTION,
                SUCCESSOR_PORTFOLIO_RULE,
                REVIEWED_SUCCESSOR_GUIDANCE_LINE,
            ),
        ),
        GuidanceBlock(
            block_id="large_instance_two_opt_constraints",
            category="bounded_local_search_constraints",
            title="Large-instance two-opt constraints",
            lines=(
                *tuple(str(item) for item in constraints["implementation_constraints"]),
                *tuple(str(item) for item in constraints["default_reject_directions"]),
                f"Seed evidence report: {constraints['seed_report']}",
            ),
        ),
        GuidanceBlock(
            block_id="case_protection_requirements",
            category="protected_case_requirements",
            title="CMT2/CMT4 case protection",
            lines=(
                *tuple(str(item) for item in CASE_PROTECTION_REQUIREMENTS["rules"]),
                *tuple(
                    str(item)
                    for item in CASE_PROTECTION_REQUIREMENTS["required_evidence"]
                ),
            ),
        ),
        GuidanceBlock(
            block_id="mechanism_exception_rules",
            category="default_avoid_exceptions",
            title="Mechanism exception rules",
            lines=(
                ROUTE_MERGE_EXCEPTION_RULE,
                CONSTRUCTION_SEED_RULE,
                MISSING_PRIMARY_TELEMETRY_RULE,
            ),
        ),
    )


def _measurement_summary(
    measurement: Mapping[str, Any] | None,
) -> MeasurementGuidanceSummary:
    if not measurement:
        return MeasurementGuidanceSummary(
            summary_id="cvrp_measurement_summary",
            summary=(
                "Use CVRP measurement diagnostics as proposal-only guidance; "
                "do not treat them as promotion evidence."
            ),
            metric_names=("total_distance",),
            limitations=("proposal-only summary", "excluded from DecisionFeatures"),
        )
    metric = str(measurement.get("metric") or "total_distance")
    mde = measurement.get("screening_mde_at_power_80")
    practical = measurement.get("practical_screen_delta")
    return MeasurementGuidanceSummary(
        summary_id="cvrp_measurement_summary",
        summary=(
            f"Use proposal-only {metric} diagnostics with screening MDE {mde} "
            f"against practical screen delta {practical}."
        ),
        metric_names=(metric,),
        limitations=(
            "proposal-only summary",
            "excluded from DecisionFeatures",
            "not promotion or protocol-gate evidence",
        ),
    )


def _legacy_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    return deepcopy(dict(value))


def _slug(value: str) -> str:
    chars = [char.lower() if char.isalnum() else "_" for char in value]
    collapsed = "_".join(part for part in "".join(chars).split("_") if part)
    return collapsed[:48] or "rule"
