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
from scion.problems.cvrp.successor_evidence_catalog import (
    DEFAULT_AVOID_DIRECTIONS,
    REVIEWED_SUCCESSOR_MECHANISMS,
    REVIEWED_SUCCESSOR_OUTCOME_STATUS,
    SUCCESSOR_OPPORTUNITY_FAMILIES,
    SUPPRESSED_SUCCESSOR_MECHANISMS,
)

CVRP_PROBLEM_FAMILY = "cvrp"
LARGE_INSTANCE_TWO_OPT_SEED_REPORT = (
    "scion/docs/experiments/v0.4/"
    "v04-vrp-large-instance-two-opt-seed-evidence-20260618.md"
)
REQUIRED_MECHANISM_ID = "large_instance_intra_route_two_opt_seed"
REVIEWED_MECHANISM_IDS = (
    REQUIRED_MECHANISM_ID,
    *(str(item["mechanism_id"]) for item in REVIEWED_SUCCESSOR_MECHANISMS),
)
SUPPRESSED_MECHANISM_IDS = tuple(
    str(item["mechanism_id"]) for item in SUPPRESSED_SUCCESSOR_MECHANISMS
)
REVIEWED_BOUNDED_LOCAL_SEARCH_IDS = tuple(
    str(item["mechanism_id"])
    for item in REVIEWED_SUCCESSOR_MECHANISMS
    if item.get("mechanism_family") == "bounded_local_search_variant"
)
REVIEWED_DESTROY_REPAIR_IDS = tuple(
    str(item["mechanism_id"])
    for item in REVIEWED_SUCCESSOR_MECHANISMS
    if item.get("mechanism_family") == "destroy_repair_selection"
)
REVIEWED_CONSTRUCTION_SEED_IDS = tuple(
    str(item["mechanism_id"])
    for item in REVIEWED_SUCCESSOR_MECHANISMS
    if item.get("mechanism_family") == "construction_seed_portfolio"
)
REVIEWED_SCHEDULER_DESTROY_SIZE_IDS = tuple(
    str(item["mechanism_id"])
    for item in REVIEWED_SUCCESSOR_MECHANISMS
    if item.get("mechanism_family") == "scheduler_destroy_size_policy"
)
PROTECTED_CASES = ("CMT2", "CMT4")
SUCCESSOR24_MECHANISM_ID = "lookahead_insertion_cost_repair"
SUCCESSOR24_V2_MECHANISM_ID = "lookahead_insertion_cost_repair_v2"
SUCCESSOR24_TARGET_FILE = "policies/baseline_modules/destroy_repair.py"
SUCCESSOR24_PLAN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor24-lookahead-insertion-repair-plan-20260630.md"
)
SUCCESSOR24_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor24-lookahead-insertion-repair-postrun-20260630.md"
)
SUCCESSOR25_MECHANISM_ID = "cw_sweep_seed_baseline_selector"
SUCCESSOR25_TARGET_FILE = "policies/baseline_modules/construction.py"
SUCCESSOR25_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor25-cw-sweep-seed-baseline-selector-postrun-20260630.md"
)
SUCCESSOR26_MECHANISM_ID = "short_horizon_seed_trajectory_selector"
SUCCESSOR26_V2_MECHANISM_ID = "short_horizon_seed_trajectory_selector_v2"
SUCCESSOR26_TARGET_FILE = "policies/baseline_modules/scheduler.py"
SUCCESSOR26_PLAN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor26-short-horizon-seed-trajectory-selector-plan-20260630.md"
)
SUCCESSOR26B_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor26b-short-horizon-seed-trajectory-selector-postrun-20260630.md"
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
    "mechanisms": [],
}
REVIEWED_SUCCESSOR_EVIDENCE["mechanisms"] = [
    {
        "mechanism_id": str(item["mechanism_id"]),
        "mechanism_family": str(item["mechanism_family"]),
        "checklist_status": "proven",
        "outcome_status": REVIEWED_SUCCESSOR_OUTCOME_STATUS,
        "next_use_rule": (
            "Do not spend the next CVRP branch on the same "
            f"{item['path_label']} unless the hypothesis names a materially "
            f"new {item['causal_path_label']} causal path and direct per-case "
            "objective-effect evidence."
        ),
        **(
            {"effect_summary": deepcopy(item["effect_summary"])}
            if "effect_summary" in item
            else {}
        ),
    }
    for item in REVIEWED_SUCCESSOR_MECHANISMS
]
REVIEWED_SUCCESSOR_GUIDANCE_LINE = (
    "Reviewed successor evidence: "
    f"`{', '.join(REVIEWED_BOUNDED_LOCAL_SEARCH_IDS)}` belong to "
    "`bounded_local_search_variant`; "
    f"`{', '.join(REVIEWED_DESTROY_REPAIR_IDS)}` belong to "
    "`destroy_repair_selection`; "
    f"`{', '.join(REVIEWED_CONSTRUCTION_SEED_IDS)}` belong to "
    "`construction_seed_portfolio`; "
    f"`{', '.join(REVIEWED_SCHEDULER_DESTROY_SIZE_IDS)}` belong to "
    "`scheduler_destroy_size_policy`; all have "
    f"`{REVIEWED_SUCCESSOR_OUTCOME_STATUS}` in `cvrp_successor_summary`; "
    "`scheduler_destroy_size_policy` is reviewed/default-avoid after "
    "successor23 repaired observable q deltas but stayed below-MDE; use it "
    "only for a telemetry-only q-audit repair that emits explicit "
    "baseline_q/adapted_q/q_delta fields, or for a materially different "
    f"scheduler causal path owned by `{SUCCESSOR26_TARGET_FILE}`. Successor24 "
    "then reviewed "
    f"`{SUCCESSOR24_MECHANISM_ID}` and `{SUCCESSOR24_V2_MECHANISM_ID}` as "
    "destroy/repair insertion-cost lookahead repairs with no positive-at-MDE "
    "effect; v2 also had direct-effect-zero telemetry. Successor25 then "
    f"tested `{SUCCESSOR25_MECHANISM_ID}` and is now reviewed/default-avoid: "
    "aggregate formal rows stayed at median delta 0.0, and its few direct "
    "construction seed gains were not preserved by downstream search. "
    "Successor26b then validly screened "
    f"`{SUCCESSOR26_MECHANISM_ID}` and `{SUCCESSOR26_V2_MECHANISM_ID}` after "
    "the static recognizer repair; both stayed below MDE, with v2 showing "
    "CMT2/CMT4 losses. Treat unchanged construction seed trajectory selection "
    "as reviewed/default-avoid. The next CVRP solver slot should clean-fork "
    "away from construction seed trajectory selectors and name a materially "
    "different problem-owned causal path with direct per-case objective "
    "effect evidence."
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
    "negative aggregate effect. The successor6 bounded-local-search expansion, "
    "`bounded_intra_route_3opt`, also completed direct evidence and was "
    "abandoned after negative CMT2-heavy evidence. The successor9 "
    "bounded-local-search ejection-chain path, "
    "`bounded_ejection_chain_relocate`, completed direct evidence but remained "
    "below MDE and lost on CMT2/CMT4. The first destroy/repair "
    "successor, "
    "`angular_sector_removal`, reached formal screening with complete "
    "activation/effect telemetry but produced no positive-at-MDE outcome. "
    "Later destroy/repair attempts `radial_string_removal` and "
    "`farthest_noise_related_removal` were also abandoned without "
    "positive-at-MDE effect. Successor10 destroy/repair attempts "
    "`polar_sweep_destroy_repair` and "
    "`route_fragment_recombination_repair` completed direct evidence but "
    "also measured no positive-at-MDE effect. Successor11 destroy/repair "
    "attempts `adjacency_pair_removal_repair` and "
    "`load_compatible_ruin_recreate` completed direct evidence but also "
    "stayed below MDE with negative CMT2/CMT4 protection medians. The "
    "successor15 destroy/repair clean fork `load_complement_pair_removal` was "
    "also rejected after loss-heavy evidence, including negative CMT4 and "
    "X-n110 medians. The "
    "successor14 destroy/repair follow-up `route_pair_crossover_repair` "
    "screened 48/48 pairs but remained below MDE with CMT2/CMT4/X-n110 losses; "
    "its clean fork `timewarp_string_removal` also screened 32/32 pairs and "
    "was rejected as loss-heavy no-positive-at-MDE evidence. The "
    "evidence-complete "
    "construction successor "
    "`savings_seed_selection_probe` also measured no positive-at-MDE effect. "
    "Successor15 found an active weak-positive construction branch, "
    "`granular_savings_seed_portfolio`, with CMT2/CMT4/M gains but below-MDE "
    "aggregate evidence and an X-n110 caveat. Successor16 followed that "
    "branch first and expanded it to 48/48 pairs; the mechanism activated and "
    "remained marginal positive but still below the 9.9 MDE. Successor17 "
    "then spent one diagnostic row on `seed_post_optimization_selector` from "
    "the resumed branch, which again showed missing activation, and one "
    "material granular follow-up that remained weak-positive but below MDE. "
    "Successor18b verified mechanism-granular suppression by continuing the "
    "mixed branch instead of active-slot blocking: it expanded "
    "`granular_savings_seed_portfolio` to 48/48 pairs with median delta 5.0, "
    "CI [-2.75, 12.75], effect/MDE 0.505, and no positive-at-MDE row, then "
    "tested `exact_short_route_polish`, which screened 32/32 pairs and was "
    "loss-heavy/quality-regression evidence (median delta -5.75, CI "
    "[-20.25, 0.5], CMT2 -80.0, CMT4 -33.5), parking the branch. "
    "Successor19 and successor20 then repaired and refined "
    "`bounded_route_segment_exchange`; successor20 completed on WSL with "
    "mechanism activation and phase telemetry, but both screening rows had "
    "median delta 0.0, CI [0.0, 0.0], positive_rows=0, and "
    "rows_at_or_above_mde=0. Treat that bounded route-segment branch as "
    "framework-useful but solver-negative for v0.4 closeout. Successor21 "
    "then tested `operator_pair_destroy_size_bands`, a scheduler destroy-size "
    "policy that clamped q by destroy/repair operator pair rather than by "
    "stagnation. It activated and recorded phase telemetry, but row 1 was "
    "below MDE (median delta 0.25, CI [-6.0, 6.5]) and the follow-up row was "
    "loss-heavy below MDE (median delta -5.5, CI [-8.0, 2.75], CMT4 -2.0), "
    "so do not repeat unchanged operator-pair q bands. Successor22b then "
    "correctly targeted `stagnation_adaptive_destroy_size_schedule` and "
    "recorded mechanism telemetry, but aligned formal ALNS traces showed zero "
    "q change versus champion (0/505 iterations in row 1 and 0/737 in row 2), "
    "with median delta 0.0, CI [0.0, 0.0], and no case-level wins. "
    "Successor23 repaired the observable q trajectory for that same mechanism, "
    "with changed aligned q deltas in most candidate/champion pairs, but both "
    "rows stayed below MDE (row 1 median delta 0.0, CI [-2.0, 3.5]; row 2 "
    "median delta -0.5, CI [-3.0, 3.25]), rows_at_or_above_mde=0, the branch "
    "parked as quality regression, and explicit baseline_q/adapted_q/q_delta "
    "runtime fields were missing. Treat unchanged successor23-style scheduler "
    "q scheduling as reviewed solver-negative/default-avoid evidence, not a "
    "current hard-required mechanism. Successor24 then clean-forked to "
    f"`{SUCCESSOR24_MECHANISM_ID}` in `{SUCCESSOR24_TARGET_FILE}`. It activated "
    "and recorded runtime, but row 1 stayed below MDE (median delta -0.75, "
    "CI [-5.5, 0.5]) with CMT4 and X losses. Its same-family v2 follow-up "
    f"`{SUCCESSOR24_V2_MECHANISM_ID}` also stayed below MDE (median delta -2.0, "
    "CI [-12.0, 1.5]) and recorded direct-effect-zero telemetry "
    "(candidate_present=60, candidate_positive=0, candidate_zero=60), with "
    "CMT4, P, and X regressions. Treat unchanged successor24-style "
    "destroy/repair insertion-cost lookahead as reviewed solver-negative/"
    "default-avoid evidence, not a telemetry-only win. Successor25 then "
    f"clean-forked to `{SUCCESSOR25_MECHANISM_ID}` in "
    f"`{SUCCESSOR25_TARGET_FILE}` and completed formal screening, but both "
    "rows stayed below MDE with median delta 0.0; direct construction seed "
    "deltas appeared only on a small B-n67 subset and were not preserved by "
    "downstream ALNS/VNS. Treat unchanged successor25-style raw seed-baseline "
    "selection as reviewed/default-avoid evidence. Successor26 first exposed a "
    "static-quality recognizer gap rather than solver evidence, then "
    "successor26b reran the repaired short-horizon seed trajectory selector in "
    f"`{SUCCESSOR26_TARGET_FILE}` on the server-local `claw` runner with two "
    "effective screening rows and no quality, telemetry, or model-call "
    "failure. The first row for "
    f"`{SUCCESSOR26_MECHANISM_ID}` stayed at median delta 0.0, CI [0.0, 0.0], "
    "win_rate 0.0, and rows_at_or_above_mde=0. The v2 row "
    f"`{SUCCESSOR26_V2_MECHANISM_ID}` stayed below MDE with median delta -5.0, "
    "CI [-8.0, 9.0], win_rate 0.25, CMT2 median -8.0, and CMT4 median -19.0. "
    "Treat unchanged successor26-style construction seed trajectory selection "
    "as reviewed solver-negative/default-avoid evidence. The next CVRP solver "
    "slot should clean-fork away from construction seed trajectory selectors "
    "and name a materially different CVRP-owned causal path before code work "
    "starts; `required_mechanism_ids` remains empty. "
    "Use "
    "`scheduler_destroy_size_policy` only when explicitly scoped as a "
    "telemetry-only q-audit repair for the missing explicit fields, or when "
    "the hypothesis names a materially different scheduler-policy causal "
    "path. Do not repeat unchanged granular_savings_seed_portfolio, "
    "exact_short_route_polish, bounded_route_segment_exchange, "
    "operator_pair_destroy_size_bands, successor23 "
    "stagnation_adaptive_destroy_size_schedule, or "
    f"successor24 {SUCCESSOR24_MECHANISM_ID}/"
    f"{SUCCESSOR24_V2_MECHANISM_ID}, unchanged successor25 "
    f"{SUCCESSOR25_MECHANISM_ID}, unchanged successor26 "
    f"{SUCCESSOR26_MECHANISM_ID}/{SUCCESSOR26_V2_MECHANISM_ID}, or "
    "seed_post_optimization_selector; the seed-post selector repair is "
    "deferred unless explicitly promoted as an activation diagnostic. "
    "revisit bounded local search or angular-sector "
    "removal only when the hypothesis names a causal path distinct from "
    "cross-exchange, intra-route Or-opt reinsertion, 3-opt, ejection-chain "
    "relocation, bounded route-segment exchange, angular-sector, "
    "radial-string, farthest-noise removal, polar-sweep destroy/repair, "
    "route-fragment recombination repair, "
    "adjacency-pair removal repair, load-compatible ruin/recreate, "
    "load-complement pair removal, route-pair crossover repair, timewarp "
    "string removal, insertion-cost lookahead repair, savings seed selection, "
    "and seed trajectory selection and carries direct per-case "
    "objective-effect evidence."
)
CURRENT_QUESTION = (
    "After both the large-instance intra-route two-opt checklist and the "
    "first bounded-local-search, destroy/repair, and construction seed "
    "successors, including granular seed-portfolio, exact short-route polish, "
    "bounded route-segment follow-ups, scheduler destroy-size q scheduling, "
    "successor24 insertion-cost lookahead repair, successor25 raw "
    "construction seed-baseline selection, and successor26b short-horizon seed "
    f"trajectory selectors `{SUCCESSOR26_MECHANISM_ID}` / "
    f"`{SUCCESSOR26_V2_MECHANISM_ID}`, were reviewed without positive-at-MDE solver "
    "effect, can the next CVRP solver branch clean-fork away from construction "
    "seed trajectory selectors to a materially different problem-owned causal "
    "path with direct per-case total_distance evidence and without repeating "
    "prior default-avoid families?"
)
REQUIRED_EVIDENCE = (
    (
        "for the next CVRP solver design, live target-intent or hypothesis "
        "names a materially different non-seed-trajectory causal path before "
        "code work starts, or records why the branch deliberately overrides "
        "successor26b reviewed/default-avoid evidence"
    ),
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
        f"`{SUCCESSOR26_MECHANISM_ID}` or `{SUCCESSOR26_V2_MECHANISM_ID}` "
        "telemetry is no longer enough to justify an unchanged construction "
        "seed trajectory selector; any revisit must name why successor26b "
        "median delta 0.0 / -5.0 below-MDE evidence no longer applies and "
        "must still report direct same-run objective effect, feasibility, "
        "route count, candidate count, and strict budget/reserve evidence"
    ),
    (
        "activation and q-trajectory evidence for scheduler-policy "
        "destroy-size claims, including baseline_q, adapted_q, q_delta, and "
        "nonzero aligned candidate/champion q deltas; do not claim ordinary "
        "downstream ALNS improvements as direct mechanism moves unless the "
        "implementation creates defensible direct q-decision attribution"
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
        "for successor construction, bounded-local-search, or destroy/repair attempts, "
        "declare the causal path difference from the reviewed intra-route "
        "two-opt seed, reviewed bounded_2node_cross_exchange successor, "
        "reviewed intra_route_or_opt_reinsert successor, reviewed "
        "bounded_intra_route_3opt successor, reviewed "
        "bounded_ejection_chain_relocate successor, reviewed "
        "bounded_route_segment_exchange successor20 evidence, reviewed "
        "angular_sector_removal, radial_string_removal, "
        "farthest_noise_related_removal, polar_sweep_destroy_repair, and "
        "route_fragment_recombination_repair, "
        "adjacency_pair_removal_repair, and load_compatible_ruin_recreate "
        "destroy/repair successors, reviewed load_complement_pair_removal "
        "successor15 destroy/repair evidence, reviewed "
        "route_pair_crossover_repair and timewarp_string_removal successor14 "
        "destroy/repair evidence, reviewed "
        "lookahead_insertion_cost_repair and "
        "lookahead_insertion_cost_repair_v2 successor24 destroy/repair "
        "evidence, reviewed "
        "savings_seed_selection_probe construction successor, reviewed "
        "granular_savings_seed_portfolio successor18b evidence, reviewed "
        "exact_short_route_polish successor18b evidence, reviewed "
        "cw_sweep_seed_baseline_selector successor25 evidence, reviewed "
        "short_horizon_seed_trajectory_selector successor26b evidence, and prior "
        "default-avoid families before spending another branch slot"
    ),
    (
        "do not continue unchanged granular_savings_seed_portfolio or "
        "exact_short_route_polish after successor18b parked the branch, and "
        "do not continue unchanged bounded_route_segment_exchange after "
        "successor20 active zero-effect below-MDE evidence; do not continue "
        "unchanged stagnation_adaptive_destroy_size_schedule after successor23 "
        "repaired observable q deltas but stayed below-MDE, parked as quality "
        "regression, and missed explicit baseline_q/adapted_q/q_delta fields; "
        "do not continue unchanged lookahead_insertion_cost_repair or "
        "lookahead_insertion_cost_repair_v2 after successor24 measured "
        "activation-observed/direct-effect-zero below-MDE evidence with "
        "CMT4/P/X regressions; do not continue unchanged "
        "cw_sweep_seed_baseline_selector after successor25 measured "
        "below-MDE aggregate evidence and showed that direct seed deltas were "
        "not preserved downstream; do not continue unchanged "
        "short_horizon_seed_trajectory_selector or "
        "short_horizon_seed_trajectory_selector_v2 after successor26b measured "
        "below-MDE evidence and CMT2/CMT4 losses in v2; the next solver "
        "research slot should clean-fork to another materially different "
        "CVRP-owned causal path, with "
        "scheduler_destroy_size_policy limited to telemetry-only q-audit "
        "repair or a materially different scheduler-policy causal path, "
        "destroy/repair insertion-cost lookahead parked, and "
        "seed_post_optimization_selector kept as a deferred activation "
        "diagnostic unless explicitly promoted, "
        "after "
        "bounded_2node_cross_exchange, intra_route_or_opt_reinsert, "
        "bounded_intra_route_3opt, bounded_ejection_chain_relocate, "
        "bounded_route_segment_exchange, "
        "angular_sector_removal, radial_string_removal, "
        "farthest_noise_related_removal, polar_sweep_destroy_repair, "
        "route_fragment_recombination_repair, adjacency_pair_removal_repair, "
        "load_compatible_ruin_recreate, load_complement_pair_removal, "
        "route_pair_crossover_repair, timewarp_string_removal, "
        "lookahead_insertion_cost_repair, "
        "lookahead_insertion_cost_repair_v2, and "
        "savings_seed_selection_probe plus granular_savings_seed_portfolio, "
        "exact_short_route_polish, short_horizon_seed_trajectory_selector, "
        "and short_horizon_seed_trajectory_selector_v2 were reviewed "
        "no-positive-at-MDE and "
        "unchanged seed_post_optimization_selector produced repeated "
        "missing-activation inactive evidence in successor16 and successor17; "
        "revisits must name a new causal path and direct objective-effect "
        "telemetry"
    ),
)
MEASURABLE_OPPORTUNITY_CLASSES = (
    (
        "construction_seed_portfolio: successor25 raw seed-baseline selection "
        "is reviewed/default-avoid because direct seed gains were not "
        "preserved downstream; successor26b validly screened "
        f"`{SUCCESSOR26_MECHANISM_ID}` and `{SUCCESSOR26_V2_MECHANISM_ID}` "
        "below MDE and made them reviewed/default-avoid as short-horizon "
        "seed trajectory selectors. Successor18b moved "
        "granular_savings_seed_portfolio to reviewed below-MDE evidence and "
        "exact_short_route_polish to reviewed loss-heavy evidence, so do not "
        "continue unchanged variants; do not repeat "
        "seed_post_optimization_selector after twice-missing activation unless "
        "repairing activation wiring with explicit pre-protocol and formal "
        "mechanism evidence; after reviewed savings_seed_selection_probe "
        "no-positive-at-MDE evidence, require any new construction path to be "
        "causally distinct from seed-baseline and seed-trajectory selection"
    ),
    (
        "scheduler_destroy_size_policy: successor23 repaired observable "
        "stagnation_adaptive_destroy_size_schedule q deltas but remained "
        "below-MDE, quality-regression parked, and missing explicit "
        "baseline_q/adapted_q/q_delta fields; use this family only for a "
        "telemetry-only q-audit repair that emits those fields, or for a "
        "materially different scheduler-policy causal path with paired "
        "row-level total_distance, MDE, and CMT2/CMT4 evidence"
    ),
    (
        "destroy_repair_selection: require per-case total_distance deltas "
        "tied to the changed repair/removal choice; after the reviewed "
        "angular_sector_removal, radial_string_removal, and "
        "farthest_noise_related_removal, polar_sweep_destroy_repair, and "
        "route_fragment_recombination_repair, adjacency_pair_removal_repair, "
        "load_compatible_ruin_recreate, load_complement_pair_removal, "
        "route_pair_crossover_repair, timewarp_string_removal, "
        "lookahead_insertion_cost_repair, and "
        "lookahead_insertion_cost_repair_v2 no-positive-at-MDE results, "
        "require a destroy/repair causal path distinct from those removal and "
        "repair paths"
    ),
    (
        "bounded_local_search_variant: require feasible route-level "
        "objective deltas with bounded search effort; after the reviewed "
        "bounded_2node_cross_exchange, intra_route_or_opt_reinsert, "
        "bounded_intra_route_3opt, and bounded_ejection_chain_relocate "
        "no-positive-at-MDE results, require a bounded-local-search causal "
        "path distinct from cross-exchange, same-route Or-opt reinsertion, "
        "3-opt, and ejection-chain relocation"
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
    "bounded_2node_cross_exchange, intra_route_or_opt_reinsert, and "
    "bounded_intra_route_3opt plus bounded_ejection_chain_relocate and "
    "bounded_route_segment_exchange have repeated that no-positive outcome "
    "as bounded successors, and "
    "angular_sector_removal, radial_string_removal, "
    "farthest_noise_related_removal, polar_sweep_destroy_repair, and "
    "route_fragment_recombination_repair plus adjacency_pair_removal_repair "
    "and load_compatible_ruin_recreate plus load_complement_pair_removal, "
    "route_pair_crossover_repair, timewarp_string_removal, "
    "lookahead_insertion_cost_repair, and lookahead_insertion_cost_repair_v2 "
    "have repeated it "
    "as destroy/repair successors, and savings_seed_selection_probe plus "
    "granular_savings_seed_portfolio, exact_short_route_polish, and "
    "cw_sweep_seed_baseline_selector plus short_horizon_seed_trajectory_selector "
    "and short_horizon_seed_trajectory_selector_v2 have repeated it as "
    "construction successors, and operator_pair_destroy_size_bands plus "
    "stagnation_adaptive_destroy_size_schedule have repeated it as scheduler "
    "destroy-size successors. "
    "seed_post_optimization_selector is twice-inactive missing-activation "
    "evidence and remains a deferred repair unless explicitly promoted. "
    "Successor23 repaired observable stagnation_adaptive_destroy_size_schedule "
    "q deltas but stayed below-MDE, parked as quality regression, and missed "
    "explicit baseline_q/adapted_q/q_delta fields. Successor24 activated "
    "lookahead insertion-cost repair but stayed below-MDE, then v2 recorded "
    "direct-effect-zero telemetry with worse CMT4/P/X case evidence. "
    "Successor25 raw seed-baseline selection stayed below-MDE and its direct "
    "seed deltas were not preserved downstream. Successor26b validly screened "
    "short-horizon seed trajectory selection after the static recognizer "
    "repair, but both rows stayed below-MDE and v2 lost on CMT2/CMT4. The next "
    "CVRP solver slot should clean-fork away from construction seed trajectory "
    "selectors to a materially different problem-owned causal path. The same scheduler "
    "family is allowed only as telemetry-only q-audit repair or a materially "
    "different scheduler-policy causal path, and insertion-cost lookahead "
    "repair is parked as reviewed solver-negative. Use "
    "problem-owned evidence requirements and keep this guidance out of "
    "DecisionFeatures."
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
        "suppressed_mechanism_ids": list(SUPPRESSED_MECHANISM_IDS),
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
        "resume_continuity_requirements": deepcopy(RESUME_CONTINUITY_REQUIREMENTS),
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
                "Require a materially different scheduler-policy, "
                "construction, bounded-local-search, or destroy/repair "
                "causal path after the reviewed large-twoopt and successor "
                "no-positive-at-MDE results."
            ),
            mechanism_ids=SUCCESSOR_OPPORTUNITY_FAMILIES,
            protected_items=PROTECTED_CASES,
            required_fields=(
                "successor mechanism family",
                "material causal-path difference from reviewed large-twoopt",
                "material causal-path difference from reviewed cross-exchange",
                "material causal-path difference from reviewed Or-opt reinsertion",
                "material causal-path difference from reviewed 3-opt",
                "material causal-path difference from reviewed ejection-chain relocation",
                "material causal-path difference from reviewed route-segment exchange",
                "scheduler destroy-size baseline_q/adapted_q/q_delta evidence when using scheduler_destroy_size_policy",
                "nonzero aligned candidate/champion q deltas before objective-effect interpretation",
                "material causal-path difference from reviewed angular-sector removal",
                "material causal-path difference from reviewed radial-string removal",
                "material causal-path difference from reviewed farthest-noise removal",
                "material causal-path difference from reviewed polar-sweep destroy/repair",
                (
                    "material causal-path difference from reviewed "
                    "route-fragment recombination repair"
                ),
                (
                    "material causal-path difference from reviewed "
                    "adjacency-pair removal repair"
                ),
                (
                    "material causal-path difference from reviewed "
                    "load-compatible ruin/recreate"
                ),
                "material causal-path difference from reviewed savings seed selection",
                "per-case total_distance delta tied to the changed mechanism",
                "feasibility and route-count preservation or explicit caveat",
                "runtime budget evidence under the formal policy",
            ),
        ),
        *_reviewed_successor_evidence_requirements(),
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


def _reviewed_successor_evidence_requirements() -> tuple[EvidenceRequirement, ...]:
    return tuple(
        EvidenceRequirement(
            requirement_id=f"{_slug(str(item['mechanism_id']))}_reviewed_no_positive",
            category="reviewed_successor_evidence",
            description=(
                f"{item['mechanism_id']} is reviewed CVRP successor evidence "
                f"with outcome {REVIEWED_SUCCESSOR_OUTCOME_STATUS}; do not "
                "repeat it as the next CVRP attempt without a materially new "
                f"{item['causal_path_label']} causal path."
            ),
            mechanism_ids=(
                str(item["mechanism_id"]),
                str(item["mechanism_family"]),
            ),
            required_fields=(
                "cvrp_successor_summary checklist_status=proven",
                (
                    "cvrp_successor_summary "
                    f"outcome_status={REVIEWED_SUCCESSOR_OUTCOME_STATUS}"
                ),
                f"new {item['causal_path_label']} causal path if revisited",
                "direct per-case total_distance objective-effect telemetry",
            ),
        )
        for item in REVIEWED_SUCCESSOR_MECHANISMS
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
    for item in REVIEWED_SUCCESSOR_MECHANISMS:
        mechanism_id = str(item["mechanism_id"])
        if mechanism_id in text:
            applies_to.append(mechanism_id)
    return tuple(applies_to)


def _continuity_requirements() -> tuple[ContinuityRequirement, ...]:
    resume = RESUME_CONTINUITY_REQUIREMENTS
    related_ids = (
        *SUCCESSOR_OPPORTUNITY_FAMILIES,
        REQUIRED_MECHANISM_ID,
        *(str(item["mechanism_id"]) for item in REVIEWED_SUCCESSOR_MECHANISMS),
        "bounded_local_search_variant",
        "destroy_repair_selection",
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
