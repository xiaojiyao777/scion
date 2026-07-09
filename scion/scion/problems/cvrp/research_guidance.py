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
from scion.problems.cvrp.research_guidance_route_first import (
    ROUTE_FIRST_COMPARISON_MECHANISM_ID,
    ROUTE_FIRST_COMPARISON_TARGET_FILE,
    ROUTE_FIRST_COMPARISON_TARGET_INTENT_RULE,
    ROUTE_FIRST_COMPARISON_VARIANT_ID,
    route_first_comparison_evidence_requirement,
    route_first_comparison_focus,
    route_first_comparison_related_ids,
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
REVIEWED_ACCEPTANCE_OR_ADAPTIVE_IDS = tuple(
    str(item["mechanism_id"])
    for item in REVIEWED_SUCCESSOR_MECHANISMS
    if item.get("mechanism_family") == "acceptance_or_adaptive_weighting"
)
REVIEWED_SCHEDULER_RUNTIME_ALLOCATION_IDS = tuple(
    str(item["mechanism_id"])
    for item in REVIEWED_SUCCESSOR_MECHANISMS
    if item.get("mechanism_family") == "scheduler_runtime_allocation"
)
PROTECTED_CASES = ("CMT2", "CMT4")
CVRP_MATERIAL_DIFFERENCE_REQUIREMENT = {
    "schema_version": "material_difference_requirement.v1",
    "record_type": "material_difference_requirement",
    "record_id": "material_difference_requirement:cvrp_solver_design_causal_path",
    "required": True,
    "required_for": "cvrp_solver_design_clean_fork",
    "requirement_source": "cvrp_problem_research_guidance",
    "reason": (
        "CVRP solver-design remains solver-negative after many reviewed "
        "mechanism families; the next formal hypothesis must state a compact "
        "material_difference record before code generation."
    ),
    "reason_codes": [
        "CVRP_SOLVER_DESIGN_CAUSAL_PATH_CONTRACT",
        "CVRP_ALGORITHMIC_INTERVENTION_REQUIRED",
    ],
    "required_metadata_key": "material_difference",
    "required_output_contract": (
        "material_difference={changed_dimensions:['route_state_update'], "
        "contrast:{nearest_reviewed_mechanisms:['reviewed_mechanism_id'], "
        "difference:'specific structural contrast'}, "
        "evidence:['direct telemetry to collect']}"
    ),
}
CVRP_ALGORITHMIC_INTERVENTION_SUFFICIENCY_CONTRACT = {
    "schema_version": "cvrp_algorithmic_intervention_sufficiency.v1",
    "record_type": "cvrp_solver_design_prompt_contract",
    "requirement_id": "cvrp_algorithmic_intervention_sufficiency",
    "required_for": "solver_design_clean_fork",
    "description": (
        "A CVRP solver-design hypothesis is not sufficient if it only flips a "
        "config value, activates an existing variant, wraps telemetry, or adds "
        "a low-risk postprocess. It must describe the algorithmic intervention "
        "that changes the solve trajectory and the evidence that attributes "
        "final objective movement to that intervention."
    ),
    "required_fields": [
        "changed solve trajectory or search-state transition",
        "new candidate solution or route-state generation/selection",
        "attempted/accepted/rejected/budget-stopped observation plan",
        "post-downstream or final total_distance attribution",
        "CMT2/CMT4 protected-case outcome evidence",
    ],
    "required_output_contract": (
        "algorithmic_intervention={"
        "solve_trajectory_change:'how the solve trajectory changes', "
        "candidate_state_generation_or_selection:'how candidate route states are generated or selected', "
        "attempted_accepted_rejected_budget_evidence:'attempted/accepted/rejected/budget_stopped observations', "
        "final_total_distance_attribution:'post_downstream_or_final_total_distance_delta evidence'}"
    ),
    "insufficient_patterns": [
        "config-only activation",
        "default-off variant flip",
        "telemetry-only wrapper",
        "same mechanism threshold tune",
        "pre-VNS local delta without final trajectory attribution",
    ],
    "proposal_visibility_only": True,
    "decision_features_excluded": True,
}
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
SUCCESSOR27_MECHANISM_ID = "route_pair_overlap_removal"
SUCCESSOR28_PROTECTED_MECHANISM_ID = "route_pair_overlap_removal_protected_followup"
SUCCESSOR27_TARGET_FILE = "policies/baseline_modules/destroy_repair.py"
SUCCESSOR27_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor27-route-pair-overlap-postrun-20260701.md"
)
SUCCESSOR28_PLAN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor28-route-pair-overlap-protected-followup-plan-20260701.md"
)
SUCCESSOR29_PROTECTED_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor29-route-pair-overlap-required-followup-postrun-20260701.md"
)
SUCCESSOR30_MECHANISM_ID = "bounded_cross_route_double_bridge_polish"
SUCCESSOR30_TARGET_FILE = "policies/baseline_modules/local_search.py"
SUCCESSOR30_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor30-bounded-cross-route-double-bridge-postrun-20260701.md"
)
SUCCESSOR31_MECHANISM_ID = "adaptive_embedded_vns_runtime_allocation"
SUCCESSOR31_TARGET_FILE = "policies/baseline_modules/scheduler.py"
SUCCESSOR31_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor31-adaptive-embedded-vns-runtime-allocation-postrun-20260701.md"
)
SUCCESSOR32_MECHANISM_ID = "post_repair_effect_credit_weighting"
SUCCESSOR32_TARGET_FILE = "policies/baseline_modules/scheduler.py"
SUCCESSOR32_DESIGN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor32-post-repair-effect-credit-weighting-design-20260701.md"
)
SUCCESSOR32_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor32-post-repair-effect-credit-weighting-postrun-20260701.md"
)
SUCCESSOR33_MECHANISM_ID = "neighbor_list_vns_filter"
SUCCESSOR33_TARGET_FILE = "policies/baseline_modules/local_search.py"
SUCCESSOR33_DESIGN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor33-neighbor-list-vns-filter-design-20260701.md"
)
SUCCESSOR33_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor33-neighbor-list-vns-filter-postrun-20260701.md"
)
SUCCESSOR34_MECHANISM_ID = "frozen_safe_neighbor_list_vns_filter"
SUCCESSOR34_TARGET_FILE = SUCCESSOR33_TARGET_FILE
SUCCESSOR34_DESIGN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor34-frozen-safe-neighbor-list-vns-filter-design-20260701.md"
)
SUCCESSOR34_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor34-frozen-safe-neighbor-list-vns-filter-postrun-20260702.md"
)
SUCCESSOR35_MECHANISM_ID = "capacity_tightness_removal"
SUCCESSOR35_TARGET_FILE = "policies/baseline_modules/destroy_repair.py"
SUCCESSOR35_DESIGN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor35-capacity-tightness-removal-design-20260702.md"
)
SUCCESSOR35_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor35-capacity-tightness-removal-postrun-20260705.md"
)
SUCCESSOR36_MECHANISM_ID = "seed_post_optimization_selector"
SUCCESSOR36_TARGET_FILE = "policies/baseline_modules/seed_selector.py"
SUCCESSOR36_WIRING_FILE = "policies/baseline_modules/scheduler.py"
SUCCESSOR36_DESIGN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor36-seed-post-optimization-selector-activation-design-20260705.md"
)
SUCCESSOR36B_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor36b-seed-post-selector-static-smoke-repair-postrun-20260705.md"
)
SUCCESSOR37_ROUTE_ANGLE_MECHANISM_ID = "route_angle_aware_2opt_star"
SUCCESSOR37_EDGE_FREQUENCY_MECHANISM_ID = "edge_frequency_penalty_repair"
SUCCESSOR37_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor37-cleanfork-material-causal-path-postrun-20260705.md"
)
SUCCESSOR38_MECHANISM_ID = "radial_2opt_star_relink"
SUCCESSOR38_TARGET_FILE = "policies/baseline_modules/local_search.py"
SUCCESSOR38_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor38-proposal-quality-contract-postrun-20260706.md"
)
SUCCESSOR39_MECHANISM_ID = "bounded_dual_repair_selector"
SUCCESSOR39_TARGET_FILE = "policies/baseline_modules/scheduler.py"
SUCCESSOR39_DESIGN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor39-bounded-dual-repair-selector-design-20260706.md"
)
SUCCESSOR39_TARGET_INTENT_RULE = (
    f"Successor39 is preregistered as `{SUCCESSOR39_MECHANISM_ID}` in "
    f"`{SUCCESSOR39_TARGET_FILE}`. It is a proposal-only target-intent "
    "binding for a bounded ALNS repair-choice selector: after destroy, compare "
    "the normally selected repair against one bounded alternate repair on a "
    "copied post-destroy candidate, select the feasible lower-distance "
    "pre-VNS candidate, and leave acceptance, adaptive weight scoring, "
    "construction, destroy operators, local-search operators, and embedded-VNS "
    "runtime allocation unchanged. Record direct pre-VNS selector objective "
    "effect and CMT2/CMT4 protection evidence; see "
    f"`{SUCCESSOR39_DESIGN_PATH}`."
)
SUCCESSOR40_MECHANISM_ID = "bounded_two_for_one_exchange"
SUCCESSOR40_TARGET_FILE = "policies/baseline_modules/local_search.py"
SUCCESSOR40_DESIGN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor40-bounded-two-for-one-exchange-design-20260706.md"
)
SUCCESSOR40_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor40-bounded-two-for-one-exchange-postrun-20260706.md"
)
SUCCESSOR41_MECHANISM_ID = "route_skeleton_regret_repair"
SUCCESSOR41_TARGET_FILE = "policies/baseline_modules/scheduler.py"
SUCCESSOR41_SECONDARY_TARGET_FILE = "policies/baseline_modules/destroy_repair.py"
SUCCESSOR41_DESIGN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor41-route-skeleton-regret-repair-design-20260706.md"
)
SUCCESSOR41_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor41-route-skeleton-regret-repair-postrun-20260706.md"
)
SUCCESSOR41B_DESIGN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor41b-route-skeleton-diagnostic-design-20260706.md"
)
SUCCESSOR41B_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor41b-route-skeleton-diagnostic-postrun-20260706.md"
)
SUCCESSOR41_TARGET_INTENT_RULE = (
    f"Successor41 and successor41b `{SUCCESSOR41_MECHANISM_ID}` are now valid "
    "below-MDE diagnostic evidence, not live optimization targets. Successor41 "
    "produced one negative row (6/19/7, median -6.0, CMT2 0/4/0, CMT4 1/3/0) "
    "and one active-marginal row (13/14/5, median 0.0) with P/CMT4 losses; see "
    f"`{SUCCESSOR41_POSTRUN_PATH}`. Successor41b then implemented the same "
    "mechanism in a modular repair-boundary design and screened two valid "
    "48-pair rows, but both stayed below MDE with median 0.0, no promotion "
    "signal, persistent P/B/E-family losses, and CMT2 not forced into the "
    "measured case set despite being present in the split; see "
    f"`{SUCCESSOR41B_POSTRUN_PATH}`. Do not long-run, threshold-tune, rerun, "
    "or continue same-mechanism route-skeleton repair as an optimization "
    "candidate in v0.4. The mechanism may only inform telemetry, prompt-schema, "
    "and protected-case measurement repairs. The next CVRP optimization slot "
    "should first use the exact material_difference schema and force or caveat "
    "CMT2/CMT4 protected-case coverage, then clean-fork to a materially "
    "different CVRP-owned causal path."
)
SUCCESSOR42_MECHANISM_ID = "elite_route_memory_repair"
SUCCESSOR42_TARGET_FILE = "policies/baseline_modules/route_memory.py"
SUCCESSOR42B_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor42b-cleanfork-prompt-contract-retry-postrun-20260706.md"
)
SUCCESSOR42B_REVIEWED_RULE = (
    f"Successor42b `{SUCCESSOR42_MECHANISM_ID}` is valid framework-positive "
    "but solver-negative evidence. The prompt-contract and CMT2/CMT4 priority "
    "coverage repairs worked, and the mechanism had direct telemetry, but both "
    "rows stayed marginal below MDE and CMT2/CMT4 were case-level losses. Do "
    "not long-run or same-mechanism tune complete-route memory repair in v0.4."
)
SUCCESSOR43_MECHANISM_ID = "bounded_destroy_operator_shadow_selector"
SUCCESSOR43_TARGET_FILE = "policies/baseline_modules/destroy_operator_selector.py"
SUCCESSOR43_WIRING_FILE = "policies/baseline_modules/scheduler.py"
SUCCESSOR43_DESIGN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor43-bounded-destroy-operator-shadow-selector-design-20260706.md"
)
SUCCESSOR43_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor43-bounded-destroy-operator-shadow-selector-postrun-20260706.md"
)
SUCCESSOR43_REVIEWED_RULE = (
    f"Successor43 `{SUCCESSOR43_MECHANISM_ID}` is valid active marginal "
    "evidence, not a long-run candidate. It completed two screening rows with "
    "direct pre-VNS selector telemetry and no verification failure, but stayed "
    "below MDE, left CMT2 negative, and remained B/P-family loss-prone. Trace "
    "audit found design gaps: shadow trials reused the main RNG, selected "
    "alternate destroy operators were not returned to scheduler attribution, "
    "adaptive weights/traces still credited the default destroy operator, "
    "diagnostic metadata was insufficient, and pre-VNS selection was not "
    "post-VNS/SA trajectory-safe. Do not rerun unchanged raw shadow selection "
    "or threshold-tune it; only a narrow protected follow-up may revisit this "
    f"line. See `{SUCCESSOR43_POSTRUN_PATH}`."
)
SUCCESSOR43B_MECHANISM_ID = "bounded_destroy_operator_shadow_selector_protected_followup"
SUCCESSOR43B_TARGET_FILE = SUCCESSOR43_TARGET_FILE
SUCCESSOR43B_WIRING_FILE = SUCCESSOR43_WIRING_FILE
SUCCESSOR43B_DESIGN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor43b-destroy-shadow-protected-followup-design-20260706.md"
)
SUCCESSOR43B_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor43b-destroy-shadow-protected-followup-postrun-20260706.md"
)
SUCCESSOR43B_REVIEWED_RULE = (
    f"Successor43b `{SUCCESSOR43B_MECHANISM_ID}` completed the only allowed "
    "protected same-line follow-up to successor43. It repaired much of the "
    "CVRP-owned destroy-shadow selector contract: RNG state was isolated for "
    "the alternate shadow trial and the selected destroy index/name was wired "
    "back into scheduler attribution. The run was valid/complete/postrun-ready "
    "with local gpt-5.5 and no proposal/model/telemetry/verification failure, "
    "but both rows stayed below the 9.9 MDE, aggregate pair evidence was "
    "42/49/5 with median delta -1.0, CMT2/CMT4/B remained unsafe, and local "
    "pre-VNS selector gains did not preserve final trajectory quality. Treat "
    "this as reviewed/default-avoid optimization evidence. Do not long-run, "
    "threshold-tune, or continue unchanged destroy-shadow selection in v0.4. "
    "A future telemetry hygiene repair may reuse the lesson that pre-VNS "
    "selector deltas must not be recorded as final best-improvement proof, but "
    f"the next solver slot must clean-fork to a materially different CVRP-owned "
    f"causal path. See `{SUCCESSOR43B_POSTRUN_PATH}`."
)
SELECTOR_TELEMETRY_HYGIENE_LESSON = (
    "pre_vns_selector_delta_is_not_final_trajectory_proof"
)
SELECTOR_TELEMETRY_HYGIENE_RULE = (
    "Selector/filter telemetry hygiene: pre-VNS selector local deltas are "
    "candidate-filter diagnostics only. They must not be claimed as final "
    "trajectory or promotion-grade objective-effect proof. If a selector or "
    "shadow/filter mechanism declares effect evidence, separate "
    "`pre_vns_local_delta` from `post_downstream_or_final_total_distance_delta` "
    "and tie final objective claims to accepted/current/best trajectory "
    "evidence after downstream repair/VNS/acceptance."
)
SUCCESSOR44_MECHANISM_ID = "post_vns_best_anchor_acceptance_guard"
SUCCESSOR44_TARGET_FILE = "policies/baseline_modules/acceptance.py"
SUCCESSOR44_WIRING_FILE = "policies/baseline_modules/scheduler.py"
SUCCESSOR44_DESIGN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor44-telemetry-hygiene-and-post-vns-acceptance-guard-design-20260706.md"
)
SUCCESSOR44D_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor44d-policy-effect-warning-hygiene-postrun-20260707.md"
)
SUCCESSOR44D_REVIEWED_RULE = (
    f"Successor44d `{SUCCESSOR44_MECHANISM_ID}` is reviewed/default-avoid "
    "solver evidence, not the live target. The CVRP-owned policy-effect "
    "warning hygiene repair worked: policy outcome evidence is observed and "
    "the generated patch did not add fake direct-effect `record_move` deltas. "
    "Solver evidence remained weak-positive below MDE: the expanded 48/48 "
    "screen had median delta 3.0, CI [0.0, 7.25], CMT2 weak-positive, CMT4 "
    "neutral, and B-family regressions. Do not long-run, threshold-tune, or "
    "repeat unchanged `post_vns_best_anchor_acceptance_guard`. A future "
    "acceptance-policy revisit must use a new mechanism id with a new "
    "material-difference claim and must preserve the successor44 telemetry "
    "lesson: do not claim ordinary ALNS/VNS current-improving or new-best "
    "bookkeeping as mechanism effect telemetry. See "
    f"`{SUCCESSOR44_DESIGN_PATH}` and `{SUCCESSOR44D_POSTRUN_PATH}`."
)
SUCCESSOR45_MECHANISM_ID = "bounded_repair_placement_tournament"
SUCCESSOR45_TARGET_FILE = "policies/baseline_modules/destroy_repair.py"
SUCCESSOR45_WIRING_FILE = "policies/baseline_modules/scheduler.py"
SUCCESSOR45_DESIGN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor45-repair-placement-tournament-design-20260707.md"
)
SUCCESSOR45_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor45-repair-placement-tournament-postrun-20260707.md"
)
SUCCESSOR45_TARGET_INTENT_RULE = (
    f"Successor45 is preregistered as `{SUCCESSOR45_MECHANISM_ID}` in "
    f"`{SUCCESSOR45_TARGET_FILE}` with only minimal `{SUCCESSOR45_WIRING_FILE}` "
    "operator registration or trace wiring. It is a proposal-only "
    "target-intent binding for a materially different destroy/repair causal "
    "path: after one destroy step creates a removed-customer set, compare the "
    "normally selected repaired candidate against one bounded alternate "
    "placement candidate for that same removed-customer set, and only replace the "
    "repair result when the alternate is feasible, route-count safe, and "
    "strictly better in post-repair total distance before VNS. It is not a "
    "destroy-shadow selector, repair-operator selector, route-memory repair, "
    "route-skeleton repair, insertion-lookahead scoring rule, removal "
    "targeting rule, seed selector, local-search move, acceptance gate, or "
    "runtime-allocation variant. Record direct repair-placement effect under "
    "the mechanism id, keep pre-VNS repair delta separate from downstream "
    "final trajectory claims, and report formal per-case total_distance, "
    "feasibility, route-count, and CMT2/CMT4 evidence. See "
    f"`{SUCCESSOR45_DESIGN_PATH}`."
)
SUCCESSOR45_REVIEWED_RULE = (
    f"Successor45 `{SUCCESSOR45_MECHANISM_ID}` is reviewed/default-avoid "
    "solver evidence, not the live target. The run was valid/complete/"
    "postrun-ready and observed activation plus local pre-VNS repair-placement "
    "effect, but final objective evidence stayed quality-regression below MDE: "
    "the expanded screen had median delta -2.75, CI [-6.5, 3.25], case-gate "
    "W/L/T 5/4/3, CMT2 median -3.5, CMT4 median -7.0, and P-family/CMT3 "
    "losses. Trace audit found no target-binding or code-prompt truncation "
    "failure; the main design lesson is that same-removed-set pre-VNS repair "
    "gains did not reliably preserve final ALNS/VNS trajectory quality. Do "
    "not long-run, threshold-tune, or continue unchanged repair-placement "
    "tournament variants in v0.4. A future destroy/repair revisit must name a "
    "materially different CVRP-owned causal path and must not rely on local "
    "pre-VNS tournament deltas as promotion-grade final objective evidence. "
    f"See `{SUCCESSOR45_DESIGN_PATH}` and `{SUCCESSOR45_POSTRUN_PATH}`."
)
SUCCESSOR46_MECHANISM_ID = "best_solution_ruin_recreate_intensification"
SUCCESSOR46_TARGET_FILE = "policies/baseline_modules/best_solution_intensification.py"
SUCCESSOR46_WIRING_FILE = "policies/baseline_modules/scheduler.py"
SUCCESSOR46_DESIGN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor46-best-solution-ruin-recreate-intensification-design-20260707.md"
)
SUCCESSOR46_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor46-best-solution-ruin-recreate-intensification-postrun-20260707.md"
)
SUCCESSOR46_TARGET_INTENT_RULE = (
    f"Successor46 is preregistered as `{SUCCESSOR46_MECHANISM_ID}` in a new "
    f"CVRP-owned module `{SUCCESSOR46_TARGET_FILE}` with only minimal "
    f"`{SUCCESSOR46_WIRING_FILE}` orchestration. It is a materially different "
    "clean fork from the reviewed selector, repair-placement, removal, local "
    "search, seed, acceptance, and runtime-allocation lines: after the ALNS "
    "loop has a global-best incumbent and a bounded stagnation trigger fires, "
    "start from a copy of the current global best, run one bounded ruin/"
    "recreate intensification attempt plus downstream VNS under the remaining "
    "time budget, and accept the mechanism effect only when the post-VNS "
    "candidate strictly improves the global best total_distance while "
    "preserving feasibility and route count. Do not claim pre-VNS local "
    "repair deltas as solver evidence; required evidence is final "
    "best-solution total_distance delta, accepted/new-best attribution, "
    "attempted/accepted counts, runtime budget fields, RNG or trajectory "
    "isolation for rejected attempts, and CMT2/CMT4 case-level protection. "
    f"See `{SUCCESSOR46_DESIGN_PATH}`."
)
SUCCESSOR46_REVIEWED_RULE = (
    f"Successor46 `{SUCCESSOR46_MECHANISM_ID}` is reviewed/default-avoid as an "
    "unchanged solver candidate. The run completed valid/complete/"
    "postrun-ready with local gpt-5.5 and correct target binding, but both "
    "screening rows had median delta 0.0, CI [0.0, 0.0], no case-gate wins, "
    "and no row at or above MDE. Row 1 did not activate the mechanism; row 2 "
    "observed only sparse runtime (62 ms) and zero final best-solution effect. "
    "Trace audit found no provider, target-intent, or code-context failure; "
    "the generated implementation failed the intended contract by consuming "
    "the main RNG on rejected attempts, triggering too rarely, and not "
    "separating rejected/budget/infeasible/no-improvement outcomes. Do not "
    "long-run, threshold-tune, or repeat unchanged best-solution ruin/"
    "recreate intensification. Only one narrow successor46b contract repair "
    "may revisit this line; if that repair remains zero-effect, park the "
    f"line for v0.4. See `{SUCCESSOR46_DESIGN_PATH}` and "
    f"`{SUCCESSOR46_POSTRUN_PATH}`."
)
SUCCESSOR46B_MECHANISM_ID = (
    "best_solution_ruin_recreate_intensification_activation_repair"
)
SUCCESSOR46B_TARGET_FILE = SUCCESSOR46_TARGET_FILE
SUCCESSOR46B_WIRING_FILE = SUCCESSOR46_WIRING_FILE
SUCCESSOR46B_DESIGN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor46b-best-solution-activation-contract-repair-design-20260707.md"
)
SUCCESSOR46B_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor46b-best-solution-activation-contract-repair-postrun-20260708.md"
)
SUCCESSOR46B_TARGET_INTENT_RULE = (
    f"Successor46b is preregistered as `{SUCCESSOR46B_MECHANISM_ID}` in "
    f"`{SUCCESSOR46B_TARGET_FILE}` with only minimal "
    f"`{SUCCESSOR46B_WIRING_FILE}` orchestration. This is the only allowed "
    "same-line follow-up to successor46 and is a contract/activation repair, "
    "not a broad optimization or threshold-tuning pass. It must preserve the "
    "best-incumbent ruin/recreate causal path while repairing the design "
    "contract that successor46 failed to satisfy: rejected attempts must use a "
    "child RNG or restore the main RNG state; the bounded stagnation trigger "
    "must be observable in short screening without hardcoding cases or seeds; "
    "outcome telemetry must distinguish attempted, accepted, "
    "rejected_no_improvement, rejected_infeasible, rejected_route_count, and "
    "budget_stopped; effect evidence must be final post-VNS global-best "
    "total_distance delta with accepted/new-best attribution; and CMT2/CMT4 "
    "must show mechanism-level activation evidence or an explicit caveat. Do "
    "not claim pre-VNS repair diagnostics as final solver evidence. If this "
    "repair still shows zero final objective effect, park best-solution "
    f"ruin/recreate for v0.4. See `{SUCCESSOR46B_DESIGN_PATH}`."
)
SUCCESSOR46B_REVIEWED_RULE = (
    f"Successor46b `{SUCCESSOR46B_MECHANISM_ID}` is reviewed/default-avoid "
    "as a solver mechanism. The activation-repair run completed valid/"
    "complete/postrun-ready with local gpt-5.5, correct target binding, "
    "and no proposal/model/telemetry/postrun failure, but both screening "
    "rows stayed below MDE: row 1 pair W/L/T 8/4/36, median delta 0.0, "
    "CI [0.0, 0.5]; row 2 pair W/L/T 12/6/46, median delta 0.0, "
    "CI [0.0, 1.0]; aggregate case W/L/T 5/0/23; rows_at_or_above_mde=0. "
    "The mechanism activated in 29/48 and 41/64 candidate runs and had "
    "some positive phase best-delta events, so this is not an activation "
    "failure. It is weak-positive below-MDE final-effect evidence with CMT2 unsafe "
    "(median -3.5 in both rows), CMT4 tied without mechanism-phase "
    "activation, and incomplete reject-cause telemetry. Do not long-run, "
    "threshold-tune, or continue the best-solution ruin/recreate line in "
    f"v0.4. See `{SUCCESSOR46B_POSTRUN_PATH}`."
)
SUCCESSOR47_MECHANISM_ID = "bounded_giant_tour_split_recombination"
SUCCESSOR47_TARGET_FILE = "policies/baseline_modules/giant_tour_split.py"
SUCCESSOR47_WIRING_FILE = "policies/baseline_modules/scheduler.py"
SUCCESSOR47_DESIGN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor47-bounded-giant-tour-split-recombination-design-20260708.md"
)
SUCCESSOR47_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor47-bounded-giant-tour-split-recombination-postrun-20260708.md"
)
SUCCESSOR47_TARGET_INTENT_RULE = (
    f"Successor47 is preregistered as `{SUCCESSOR47_MECHANISM_ID}` in "
    f"`{SUCCESSOR47_TARGET_FILE}` with only minimal "
    f"`{SUCCESSOR47_WIRING_FILE}` orchestration. It is a materially different "
    "CVRP-owned route-first/split clean fork: build one or more bounded "
    "giant-tour sequences from the current global-best solution, run "
    "capacity-constrained split reconstruction under the remaining-time "
    "budget, and accept only a feasible, route-count-safe final route set "
    "with strict total_distance improvement. This is not best-solution "
    "ruin/recreate, destroy/repair selector tuning, repair-placement "
    "tournament, route-pair crossover, route-fragment recombination, route "
    "memory, route skeleton, construction seed selection, acceptance guard, "
    "runtime allocation, or reviewed bounded swap/or-opt/3-opt/ejection-chain "
    "local search. Required evidence: final split-reconstructed total_distance "
    "delta, attempted/accepted/rejected_no_improvement/rejected_infeasible/"
    "rejected_route_count/budget_stopped attribution, phase runtime, "
    "feasibility and route-count preservation, and CMT2/CMT4 priority-case "
    f"outcome evidence. See `{SUCCESSOR47_DESIGN_PATH}`."
)
SUCCESSOR47_REVIEWED_RULE = (
    f"Successor47 `{SUCCESSOR47_MECHANISM_ID}` is reviewed/default-avoid as "
    "the first bounded giant-tour split recombination solver attempt. The "
    "run completed valid/complete/postrun-ready with local gpt-5.5 and "
    "correct target binding, but the objective evidence stayed marginal and "
    "protected-case unsafe: aggregate pair W/L/T 49/50/13, official aggregate "
    "case W/L/T 12/11/5, current-head case W/L/T 7/6/3, median delta 0.5, "
    "CI [-6.0, 4.5], and no promotion. The mechanism activated and runtime "
    "was observed in all screening pairs, but row 1 had zero positive "
    "mechanism best-delta/improvement events and row 2 had only 1/64 positive "
    "mechanism best-delta pairs. CMT2 median was -20.0 and CMT4 median was "
    "-11.0 in the expanded row. The generated code stayed in a new CVRP "
    "module with minimal scheduler wiring, but it did not record separated "
    "reject causes and its route-order generation was too conservative to "
    "produce direct split-reconstruction effect. Do not long-run, threshold-"
    "tune, or repeat unchanged giant-tour split recombination. See "
    f"`{SUCCESSOR47_POSTRUN_PATH}`."
)
SUCCESSOR48_MECHANISM_ID = "bounded_route_pool_set_partition_recombination"
SUCCESSOR48_TARGET_FILE = "policies/baseline_modules/route_pool_recombination.py"
SUCCESSOR48_WIRING_FILE = "policies/baseline_modules/scheduler.py"
SUCCESSOR48_DESIGN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor48-route-pool-set-partition-recombination-design-20260708.md"
)
SUCCESSOR48_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor48-route-pool-set-partition-recombination-postrun-20260708.md"
)
SUCCESSOR49_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor49-repaired-context-route-pool-repeat-postrun-20260708.md"
)
SUCCESSOR50_POSTRUN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor50-material-difference-contract-repair-postrun-20260708.md"
)
SUCCESSOR50_MECHANISM_ID = "material_difference_contract_repair"
SUCCESSOR50_TARGET_FILE = "policies/baseline_modules/scheduler.py"
SUCCESSOR50_REVIEWED_RULE = (
    f"Successor50 `{SUCCESSOR50_MECHANISM_ID}` is reviewed/default-avoid as "
    "repair-or-infra work rather than a CVRP solver mechanism. The run "
    "completed valid/complete/postrun-ready after the repaired context blocked "
    "an under-specified depot-anchor hypothesis, but the accepted candidate "
    "modified scheduler.py only to add a metadata/hook gate, left the champion "
    "route search unchanged when no hook was present, screened with median "
    "delta 0.0 and CI [0.0, 0.0], and produced zero direct objective effect. "
    "Do not long-run, same-line repair, telemetry-tune, or spend another "
    "solver-design slot on scheduler-level material-difference contract gates, "
    "metadata preflights, or hook wrappers. See "
    f"`{SUCCESSOR50_POSTRUN_PATH}`."
)
SUCCESSOR48_REVIEWED_RULE = (
    f"Successor48 `{SUCCESSOR48_MECHANISM_ID}` is reviewed/default-avoid after "
    "valid route-pool set-partition evidence, and successor49 confirmed the "
    "repaired context/contract still let the agent return to the same weak "
    "mechanism when the route-pool line was not closed strongly enough. "
    "Successor48 completed valid/complete/postrun-ready with normal local "
    "gpt-5.5 calls and CMT2/CMT4 priority coverage, but aggregate case W/L/T "
    "was 0/1/23, pair W/L/T was 10/10/76, both row medians were 0.0, CI highs "
    "were 0.0, and no row reached MDE. Successor49 then reran after the "
    "CVRP-owned context/contract repair: the first same-mechanism hypothesis "
    "was blocked for missing clean-fork diversity and algorithmic-intervention "
    "sufficiency; the redrafted candidate passed, generated the same "
    "route-pool module plus minimal scheduler wiring, and screened weak/no-"
    "effect with case W/L/T 0/0/16, pair W/L/T 4/0/60, median delta 0.0, "
    "CI [0.0, 0.0], mechanism contract status observed_no_effect, and "
    "telemetry_effect_zero. Treat unchanged route-pool exact-cover "
    "recombination as reviewed/default-avoid: no long-run, no threshold/beam/"
    "pool tuning, no successor48/49 same-mechanism continuation, and no "
    "telemetry-hygiene-only follow-up. The next CVRP slot must name a "
    "materially different CVRP-owned causal path. See "
    f"`{SUCCESSOR48_POSTRUN_PATH}` and `{SUCCESSOR49_POSTRUN_PATH}`."
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
            "Current CVRP formal screening declares CMT2 and CMT4 as protocol "
            "priority_case_ids, so postrun analysis should expect both in "
            "effective_priority_case_ids unless the split changes."
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
        "outcome_status": str(
            item.get("outcome_status") or REVIEWED_SUCCESSOR_OUTCOME_STATUS
        ),
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
    "`scheduler_destroy_size_policy`; "
    f"`{', '.join(REVIEWED_SCHEDULER_RUNTIME_ALLOCATION_IDS)}` belong to "
    "`scheduler_runtime_allocation`; all reviewed entries have "
    f"`{REVIEWED_SUCCESSOR_OUTCOME_STATUS}` in `cvrp_successor_summary`. "
    "Successor28 tested boundary-spoke and edge-conflict endpoint removal "
    "clean forks; both were negative and not true route-pair-overlap "
    "continuations. Successor29 then forced the true "
    f"`{SUCCESSOR28_PROTECTED_MECHANISM_ID}` follow-up and both rows stayed "
    "negative, so the route-pair-overlap line is now parked for v0.4. "
    "Successor30 validly screened "
    f"`{SUCCESSOR30_MECHANISM_ID}` with exact zero-effect evidence, and "
    "successor31 validly screened "
    f"`{SUCCESSOR31_MECHANISM_ID}` with runtime movement but exact zero "
    "solver effect. Successor32 then validly screened "
    f"`{SUCCESSOR32_MECHANISM_ID}` with internal operator-credit movement but "
    "zero objective effect. Successor33 then produced validation-positive "
    f"`{SUCCESSOR33_MECHANISM_ID}` evidence but failed frozen on candidate-side "
    "timeouts. Successor34 repaired that frozen-safety blocker with "
    f"`{SUCCESSOR34_MECHANISM_ID}`, but stayed weak-positive below MDE and "
    "lost CMT2. Successor35 then validly screened "
    f"`{SUCCESSOR35_MECHANISM_ID}` with active telemetry, but both rows were "
    "loss-heavy below MDE and CMT2 stayed negative, so unchanged "
    "capacity-tight removal is parked. Successor36 then exposed a static "
    "recognizer-boundary bug for "
    f"`{SUCCESSOR36_TARGET_FILE}`, and successor36b repaired that boundary "
    f"and validly screened `{SUCCESSOR36_MECHANISM_ID}` with active direct "
    "telemetry, but both rows had zero aggregate medians, no positive row at "
    "MDE, and CMT2 regressed. Treat unchanged seed-post selector variants as "
    "reviewed/default-avoid. Successor37 then removed the temporary target "
    "binding and clean-forked twice: "
    f"`{SUCCESSOR37_ROUTE_ANGLE_MECHANISM_ID}` was negative and abandoned, "
    f"while `{SUCCESSOR37_EDGE_FREQUENCY_MECHANISM_ID}` was weak-positive below "
    "MDE but direct-effect-zero and lost all CMT2/CMT4 seeds. Treat both "
    "unchanged successor37 mechanisms as reviewed/default-avoid. Successor38 "
    "then proved the causal-path proposal-quality contract can block weak "
    "hypotheses before code generation, but the accepted "
    f"`{SUCCESSOR38_MECHANISM_ID}` candidate was active-no-effect: no accepted "
    "radial relink moves, zero direct mechanism effect, and all case gates "
    "tied. Treat unchanged successor38 as reviewed/default-avoid; the next "
    "CVRP slot should clean-fork to a materially different CVRP-owned causal "
    "path rather than continue a weak-positive branch whose mechanism contract "
    "says observed_no_effect. Successor46 is now also reviewed/default-avoid "
    "as unchanged best-solution ruin/recreate evidence after valid screening "
    "showed sparse activation and observed_no_effect; only successor46b may "
    "revisit that line as a narrow contract repair."
)

NEXT_REQUIRED_DIRECTION = (
    "Current direction after successor52: do not long-run or threshold-tune "
    "unchanged `bounded_multi_candidate_alns_race`. Successor52 completed valid "
    "active-positive below-MDE screening, but CMT2/CMT4 were loss-heavy and "
    "local race telemetry did not preserve final trajectory quality. The next "
    "CVRP solver slot must either design a protected, budgeted candidate-"
    "trajectory selector repair with RNG isolation, one-shot downstream VNS or "
    "final-acceptance attribution, canonical baseline/winner telemetry, and "
    "substantive CMT2/CMT4 protection, or clean-fork to a materially different "
    "CVRP-owned causal path. Historical reviewed context follows. "
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
    "as reviewed solver-negative/default-avoid evidence. Successor27 then "
    f"clean-forked to `{SUCCESSOR27_MECHANISM_ID}` in `{SUCCESSOR27_TARGET_FILE}` "
    "and completed two valid server-local screening rows with local `gpt-5.5`, "
    "no quality/model/telemetry/postrun failure, and activation plus objective "
    "effect observed. Row 1 had median delta 0.75, CI [-4.5, 12.5], "
    "effect/MDE 0.076, CMT2 median -3.0, CMT4 median -10.0, and P-n65 "
    "median -4.5. Row 2 expanded the same mechanism to median delta 2.5, "
    "CI [-7.75, 7.0], effect/MDE 0.253, with A-n64 14.5, A-n80 10.0, "
    "B-n63 4.0, CMT3 6.0, X-n110 12.5, but B-n67 -8.0, CMT4 -16.0, "
    "P-n101 -14.0, P-n65 -4.5, and P-n76 -7.5. Successor28 then tested "
    "`boundary_spoke_outlier_removal` and `edge_conflict_endpoint_removal`, "
    "both negative and not true route-pair-overlap continuations. Successor29 "
    "forced `route_pair_overlap_removal_protected_followup` in both legacy and "
    "typed launch focus; both rows completed without quality, telemetry, "
    "model-call, or postrun failures, but row 1 median delta was -1.75 and "
    "row 2 median delta was -3.75 with CMT4/P-family losses, so the "
    "route-pair-overlap line is parked for v0.4. Successor30 clean-forked to "
    f"`{SUCCESSOR30_MECHANISM_ID}` and completed valid screening, but both "
    "rows had median delta 0.0, CI [0.0, 0.0], rows_at_or_above_mde=0, and "
    "direct mechanism telemetry with no best delta. Successor31 clean-forked "
    f"to `{SUCCESSOR31_MECHANISM_ID}` and recorded weighted runtime allocation "
    "movement in both rows, but both rows remained exact zero-effect with "
    "median delta 0.0, CI [0.0, 0.0], and rows_at_or_above_mde=0. Treat "
    "unchanged route-pair-overlap, bounded cross-route double-bridge polish, "
    "and adaptive embedded-VNS runtime allocation as reviewed/default-avoid "
    "for v0.4. Successor32 then clean-forked to "
    f"`{SUCCESSOR32_MECHANISM_ID}` and completed valid screening with "
    "internal operator-credit movement but zero objective effect; treat "
    "unchanged post-repair effect credit weighting as reviewed/default-avoid. "
    "Successor33 then clean-forked to "
    f"`{SUCCESSOR33_MECHANISM_ID}` in `{SUCCESSOR33_TARGET_FILE}`. The first "
    "candidate was negative, but the second customer-adjacency filter passed "
    "screening and validation with active direct telemetry before frozen "
    "abandoned it for candidate-side timeouts. Treat unchanged successor33 as "
    "frozen-unsafe, not zero-effect. Successor34 repaired the timeout blocker "
    f"as `{SUCCESSOR34_MECHANISM_ID}`, but stayed weak-positive below MDE with "
    "a CMT2 regression. Successor35 then clean-forked to "
    f"`{SUCCESSOR35_MECHANISM_ID}` in `{SUCCESSOR35_TARGET_FILE}` and "
    "completed valid screening with active telemetry but loss-heavy aggregate "
    "evidence and negative CMT2. Successor36 was a recognizer-boundary "
    "quality block, and successor36b then completed a valid active "
    f"`{SUCCESSOR36_MECHANISM_ID}` screening in `{SUCCESSOR36_TARGET_FILE}` "
    "with zero aggregate medians, no positive row at MDE, and CMT2 "
    "regression. Successor37 then clean-forked without a hard target binding: "
    f"`{SUCCESSOR37_ROUTE_ANGLE_MECHANISM_ID}` in local_search.py activated "
    "but screened negative (median -4.25, CI [-8.0, 0.0]), and "
    f"`{SUCCESSOR37_EDGE_FREQUENCY_MECHANISM_ID}` in destroy_repair.py screened "
    "weak-positive (median 2.5, CI [-7.5, 19.5]) but direct mechanism effect "
    "was zero and CMT2/CMT4 lost all seeds. Successor38 then exercised the "
    "causal-path proposal-quality contract: the first weak hypothesis was "
    "blocked, but the accepted "
    f"`{SUCCESSOR38_MECHANISM_ID}` in `{SUCCESSOR38_TARGET_FILE}` screened as "
    "active-no-effect with zero accepted mechanism moves, zero direct radial "
    "best delta, all case gates tied, and observed_no_effect mechanism "
    "contract status. This is proposal-control evidence plus solver-negative "
    "candidate-quality evidence, not a long-round signal. The next CVRP solver "
    "slot should not repeat unchanged seed-post selector, successor37 variants, "
    "or successor38 radial relink; first require a materially different "
    "CVRP-owned causal path with direct mechanism-effect and CMT2/CMT4 "
    "protection commitments. Successor39 then target-intent-bound "
    f"`{SUCCESSOR39_MECHANISM_ID}` in `{SUCCESSOR39_TARGET_FILE}` and "
    "completed valid screening with normal gpt-5.5 calls, active local selector "
    "telemetry, and no proposal/telemetry/postrun failure, but the best row "
    "had median delta 0.75, CI [-6.25, 6.5], effect/MDE 0.075758, both CI "
    "highs were below the 9.9 MDE, CMT4 was negative, and B/P-family losses "
    "remained. Treat unchanged bounded dual repair selection as reviewed "
    "below-MDE evidence, not a long-run candidate. Successor40 then "
    "target-intent-bound "
    f"`{SUCCESSOR40_MECHANISM_ID}` in `{SUCCESSOR40_TARGET_FILE}` and "
    "completed two valid server-local screening rows with normal gpt-5.5 "
    "calls and active local-search telemetry, but row 1 stayed below MDE "
    "(median delta 0.0, CI [-6.0, 1.0]) with B/CMT2/X losses and row 2 "
    "also stayed below MDE (median delta 0.0, CI [-2.0, 0.0]) while the "
    "guarded refinement mostly reduced losses by becoming no-op. Treat "
    "unchanged bounded two-for-one route-set exchange and same-mechanism "
    "threshold/gating variants as reviewed/default-avoid, not long-run "
    "candidates; see "
    f"`{SUCCESSOR40_POSTRUN_PATH}`. Successor41 then target-intent-bound "
    f"`{SUCCESSOR41_MECHANISM_ID}` in `{SUCCESSOR41_TARGET_FILE}` and "
    "completed valid screening with one negative row (pair W/L/T 6/19/7, "
    "median -6.0, CMT2 0/4/0, CMT4 1/3/0) and one active-marginal guarded "
    "row (13/14/5, median 0.0, A/B case wins, P/CMT4 losses). Treat "
    "successor41 as valid active marginal evidence, not a long-run candidate; "
    f"see `{SUCCESSOR41_POSTRUN_PATH}`. "
    "Successor41b completed the only allowed same-mechanism diagnostic follow-up "
    "and did not repair the objective-effect problem. Successor43 then "
    f"target-intent-bound `{SUCCESSOR43_MECHANISM_ID}` and produced active "
    "marginal evidence, but stayed below MDE with CMT2/B/P losses and exposed "
    "RNG/attribution/post-VNS trajectory-safety gaps. Successor43b then "
    "completed the only protected same-line follow-up and repaired much of the "
    "RNG/selected-operator attribution contract, but still stayed below MDE "
    "with aggregate pair W/L/T 42/49/5, CMT2/CMT4/B losses, and only local "
    "pre-VNS selector gains. Hard `required_mechanism_ids` remains empty. "
    "Successor44d then repaired policy-effect warning hygiene for "
    f"`{SUCCESSOR44_MECHANISM_ID}`, but its expanded evidence stayed "
    "weak-positive below MDE with B-family regressions, so unchanged "
    "successor44 is reviewed/default-avoid. Successor45 then target-intent-"
    f"bound `{SUCCESSOR45_MECHANISM_ID}` and observed local repair-placement "
    "effect, but final objective evidence regressed below MDE and failed "
    "CMT2/CMT4 protection; unchanged repair-placement tournaments are now "
    "reviewed/default-avoid too. Successor46 then target-intent-bound "
    f"`{SUCCESSOR46_MECHANISM_ID}` as a global-best ruin/recreate "
    "intensification clean fork, but completed valid screening with sparse "
    "activation and zero final best-solution effect. Successor46b "
    f"`{SUCCESSOR46B_MECHANISM_ID}` then repaired activation but still stayed "
    "below MDE with CMT2 unsafe. The next prepared slot keeps hard "
    "`required_mechanism_ids` empty. It must not bind another destroy-shadow "
    "selector follow-up, unchanged acceptance guard, unchanged repair-placement "
    "tournament, unchanged successor46 rerun, or pre-VNS selector/repair "
    "diagnostic as final solver evidence. "
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
    f"{SUCCESSOR26_MECHANISM_ID}/{SUCCESSOR26_V2_MECHANISM_ID}, unchanged "
    f"{SUCCESSOR27_MECHANISM_ID}, "
    f"{SUCCESSOR28_PROTECTED_MECHANISM_ID}, successor28 endpoint/spoke "
    "removal forks, "
    f"{SUCCESSOR30_MECHANISM_ID}, unchanged successor31 "
    f"{SUCCESSOR31_MECHANISM_ID}, unchanged successor32 "
    f"{SUCCESSOR32_MECHANISM_ID}, unchanged "
    f"{SUCCESSOR35_MECHANISM_ID}, or unchanged "
    f"{SUCCESSOR36_MECHANISM_ID}, unchanged "
    f"{SUCCESSOR37_ROUTE_ANGLE_MECHANISM_ID}, or unchanged "
    f"{SUCCESSOR37_EDGE_FREQUENCY_MECHANISM_ID}, or unchanged "
    f"{SUCCESSOR38_MECHANISM_ID}, unchanged "
    f"{SUCCESSOR39_MECHANISM_ID}, or unchanged "
    f"{SUCCESSOR40_MECHANISM_ID}, or unchanged "
    f"{SUCCESSOR41_MECHANISM_ID}, or unchanged "
    f"{SUCCESSOR43_MECHANISM_ID}, or unchanged "
    f"{SUCCESSOR43B_MECHANISM_ID}, or unchanged "
    f"{SUCCESSOR44_MECHANISM_ID}, or unchanged "
    f"{SUCCESSOR46_MECHANISM_ID}, or unchanged "
    f"{SUCCESSOR46B_MECHANISM_ID}, or unchanged "
    f"{SUCCESSOR47_MECHANISM_ID}, or unchanged "
    f"{SUCCESSOR48_MECHANISM_ID}, or unchanged "
    f"{SUCCESSOR50_MECHANISM_ID}. Future construction-seed revisits must be "
    "materially distinct from raw baseline, short-horizon trajectory, and "
    "post-construction micro-polish selector paths, with direct pre-ALNS/VNS "
    "objective telemetry. "
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
    "objective-effect evidence. Before launching the next optimization "
    "candidate, keep the causal-path gate but make the exact "
    "material_difference schema prominent, and ensure CMT2/CMT4 protected "
    "cases are either forced into formal screening or recorded as an explicit "
    "measurement caveat. The route-first comparison by enabling "
    f"`{ROUTE_FIRST_COMPARISON_VARIANT_ID}` through "
    f"`{ROUTE_FIRST_COMPARISON_TARGET_FILE}` is now reviewed negative "
    "evidence, not the next target-intent slot. The CVRP-owned context/contract "
    "repair is already active; do not propose another scheduler-level "
    "material_difference_contract_repair, metadata preflight, telemetry-only "
    "wrapper, or hook gate as a solver-design experiment. The next hypothesis "
    "must describe a materially different algorithmic intervention rather than "
    "an unchanged scheduler helper rerun, route-skeleton threshold/gating "
    "variant, route-memory repair, route-fragment repair, route-pair crossover, "
    "giant-tour contiguous split, route-pool successor48/successor49 "
    "continuation, route-arc LNS rebuild, unchanged multi-candidate ALNS race, "
    "two-for-one route-set exchange, repair-operator selector, repair-placement "
    "tournament, removal targeting rule, seed selector, local-search move, "
    "acceptance-weight, runtime-allocation change, unchanged best-solution "
    "ruin/recreate rerun, unchanged route-first config flip, successor46b/47 "
    "continuation, or contract repair."
)
CURRENT_QUESTION = (
    "After both the large-instance intra-route two-opt checklist and the "
    "first bounded-local-search, destroy/repair, and construction seed "
    "successors, including granular seed-portfolio, exact short-route polish, "
    "bounded route-segment follow-ups, scheduler destroy-size q scheduling, "
    "successor24 insertion-cost lookahead repair, successor25 raw "
    "construction seed-baseline selection, and successor26b short-horizon seed "
    f"trajectory selectors `{SUCCESSOR26_MECHANISM_ID}` / "
    f"`{SUCCESSOR26_V2_MECHANISM_ID}`, successor27/29 route-pair-overlap "
    "follow-ups, successor30 double-bridge polish, and successor31 adaptive "
    "embedded-VNS runtime allocation plus successor32 post-repair effect "
    "credit weighting were reviewed without positive-at-MDE solver effect, "
    "and successor33 produced validation-positive but frozen-unsafe "
    f"`{SUCCESSOR33_MECHANISM_ID}` evidence while successor34 "
    f"`{SUCCESSOR34_MECHANISM_ID}` repaired the timeout blocker but stayed "
    "weak-positive below MDE, and successor35 "
    f"`{SUCCESSOR35_MECHANISM_ID}` activated but was loss-heavy below MDE, "
    f"and successor36b validly activated `{SUCCESSOR36_MECHANISM_ID}` but "
    "remained zero-effect at aggregate level with CMT2 regression, successor37 "
    "clean forks either went negative or stayed weak-positive below MDE with "
    "direct-effect-zero/CMT losses, and successor38 "
    f"`{SUCCESSOR38_MECHANISM_ID}` was active-no-effect despite passing the "
    "new causal-path quality contract, and successor39 "
    f"`{SUCCESSOR39_MECHANISM_ID}` activated but stayed below MDE with CMT4 "
    "and B/P losses, and successor40 "
    f"`{SUCCESSOR40_MECHANISM_ID}` activated but stayed below MDE while the "
    "guarded follow-up mostly became no-op, and successor41/41b "
    f"`{SUCCESSOR41_MECHANISM_ID}` activated but stayed below MDE with "
    "persistent P/B/E-family losses and a CMT2 measurement-coverage caveat, "
    "and successor42b "
    f"`{SUCCESSOR42_MECHANISM_ID}` activated with direct telemetry but stayed "
    "marginal below MDE and failed CMT2/CMT4 protection, "
    f"and successor43 `{SUCCESSOR43_MECHANISM_ID}` activated as a pre-VNS "
    "destroy-choice shadow selector but stayed marginal below MDE with CMT2 "
    "and B/P losses plus RNG/attribution/trajectory-safety gaps, "
    f"and successor43b `{SUCCESSOR43B_MECHANISM_ID}` repaired much of that "
    "contract but still stayed below MDE with CMT2/CMT4/B losses and local "
    "selector gains that did not preserve final trajectory quality, "
    f"and successor44d `{SUCCESSOR44_MECHANISM_ID}` repaired policy-effect "
    "warning hygiene but remained weak-positive below MDE with B-family "
    "regressions, "
    f"and successor45 `{SUCCESSOR45_MECHANISM_ID}` observed local pre-VNS "
    "repair-placement effect but regressed at the final objective gate and "
    "failed CMT2/CMT4 protection, "
    f"and successor46 `{SUCCESSOR46_MECHANISM_ID}` target-bound correctly but "
    "activated sparsely and produced zero final best-solution objective effect, "
    f"and successor46b `{SUCCESSOR46B_MECHANISM_ID}` improved activation but "
    "remained weak-positive below MDE with CMT2 unsafe and incomplete reject-"
    "cause telemetry, and successor47 "
    f"`{SUCCESSOR47_MECHANISM_ID}` activated as a modular giant-tour split "
    "attempt but stayed marginal below MDE with CMT2/CMT4 losses and almost no "
    "direct split effect, and the independent route-first comparison "
    f"`{ROUTE_FIRST_COMPARISON_MECHANISM_ID}` ran with confirmed runtime "
    "activation but lost heavily to ALNS+VNS, and successor51 "
    "`bounded_route_arc_lns_rebuild` was active-marginal below MDE with "
    "CMT2/CMT4 unsafe, and successor52 `bounded_multi_candidate_alns_race` was "
    "active-positive locally but below MDE with CMT2/CMT4 loss-heavy final "
    "evidence, can the next CVRP branch either repair the race as a protected, "
    "budgeted candidate-trajectory selector with final attribution, or state a "
    "materially different algorithmic intervention with solve-trajectory change, "
    "candidate-state generation/selection, accepted/rejected/budget telemetry, "
    "final total_distance attribution, feasibility, route count, bounded runtime, "
    "and CMT2/CMT4 priority-case evidence, while leaving generic Scion core and "
    "DecisionFeatures unchanged?"
)
REQUIRED_EVIDENCE = (
    (
        f"`{SUCCESSOR41_MECHANISM_ID}` is reviewed/default-avoid after "
        "successor41 and successor41b valid below-MDE evidence; do not long-run, "
        "threshold-tune, or continue same-mechanism route-skeleton repair as an "
        "optimization candidate"
    ),
    (
        f"`{SUCCESSOR42_MECHANISM_ID}` is reviewed/default-avoid after "
        "successor42b valid marginal below-MDE evidence with CMT2/CMT4 "
        "case-level losses; do not long-run or same-mechanism tune complete "
        "route-memory repair"
    ),
    (
        f"`{SUCCESSOR43_MECHANISM_ID}` is reviewed/default-avoid after "
        "successor43 valid active marginal evidence stayed below MDE with "
        "CMT2/B/P losses and trace-audited RNG/attribution/diagnostic gaps; "
        "do not long-run, threshold-tune, or rerun raw destroy shadow selection"
    ),
    (
        f"`{SUCCESSOR43B_MECHANISM_ID}` is reviewed/default-avoid after "
        "successor43b valid protected follow-up evidence stayed below MDE, "
        "remained unsafe on CMT2/CMT4/B, and showed local pre-VNS selector "
        "effect did not preserve final trajectory quality; do not long-run, "
        "threshold-tune, or continue the destroy-shadow selector line"
    ),
    (
        f"{SELECTOR_TELEMETRY_HYGIENE_LESSON}: selector/filter and destroy/"
        "repair-choice mechanisms may use pre_vns_local_delta as diagnostic "
        "evidence only; final trajectory claims require "
        "post_downstream_or_final_total_distance_delta, feasibility, route-count, "
        "and accepted/current/best attribution after downstream repair/VNS/"
        "acceptance"
    ),
    (
        f"successor44d `{SUCCESSOR44_MECHANISM_ID}` is reviewed/default-avoid "
        "after weak-positive below-MDE policy outcome evidence; do not "
        "long-run, threshold-tune, or repeat unchanged acceptance guard logic"
    ),
    (
        f"successor45 `{SUCCESSOR45_MECHANISM_ID}` is reviewed/default-avoid "
        "after valid screening observed local repair-placement effect but "
        "failed final objective and CMT2/CMT4 protection; do not long-run, "
        "threshold-tune, or continue unchanged repair-placement tournament "
        "variants"
    ),
    (
        f"successor46 `{SUCCESSOR46_MECHANISM_ID}` is reviewed/default-avoid "
        "after valid screening showed sparse activation, zero final "
        "best-solution effect, and rejected-attempt RNG leakage; do not "
        "long-run or repeat unchanged best-solution ruin/recreate"
    ),
    (
        f"successor46b `{SUCCESSOR46B_MECHANISM_ID}` is reviewed/default-avoid "
        "as a solver mechanism after valid weak-positive below-MDE evidence, "
        "CMT2 negative protected-case evidence, CMT4 tie without mechanism "
        "phase activation, and incomplete reject-cause telemetry; do not "
        "long-run, threshold-tune, or continue the best-solution ruin/recreate "
        "line"
    ),
    (
        f"successor47 `{SUCCESSOR47_MECHANISM_ID}` is reviewed/default-avoid "
        "after valid marginal below-MDE evidence, CMT2/CMT4 losses, almost no "
        "direct split-reconstruction effect, and missing separated reject-"
        "cause telemetry; do not long-run, threshold-tune, or continue "
        "unchanged giant-tour split recombination"
    ),
    (
        f"`{ROUTE_FIRST_COMPARISON_MECHANISM_ID}` is reviewed/default-avoid "
        "after the route-first comparison activated normally but lost to the "
        "current ALNS+VNS champion; do not spend the next slot on unchanged "
        "SOLVER_VARIANT config flips or route-first baseline repeats"
    ),
    (
        "before the next CVRP hypothesis, use exact material_difference schema "
        "keys: changed_dimensions, contrast, and evidence; do not rely on "
        "aliases such as new_dimensions, old_signature, selection_gate, "
        "module_boundary, or protected_loss_plan"
    ),
    (
        "next formal screening must include CMT2/CMT4 protected-case evidence "
        "or record an explicit measurement caveat; successor41b had CMT4 but "
        "did not force CMT2 despite CMT2 being present in the split manifest"
    ),
    (
        "for the next clean fork, live target-intent and hypothesis must name a "
        "materially different CVRP-owned causal path before code work starts "
        "and explain why it is distinct from reviewed route-skeleton repair, "
        "two-for-one exchange, bounded dual repair selection, construction seed "
        "selectors, local-search variants, reviewed destroy/repair removals, "
        "unchanged acceptance-policy guard variants, and the reviewed negative "
        "route-first config-flip comparison"
    ),
    (
        "for the next clean fork, the hypothesis must describe a sufficient "
        "algorithmic intervention: changed solve trajectory or search-state "
        "transition, new candidate route-state generation or selection, "
        "attempted/accepted/rejected/budget observation, and post-downstream or "
        "final total_distance attribution"
    ),
    (
        f"successor40 `{SUCCESSOR40_MECHANISM_ID}` is reviewed/default-avoid "
        "after valid below-MDE evidence; do not rerun unchanged two-for-one "
        "route-set exchange or same-mechanism threshold/gating follow-up"
    ),
    (
        "for the next clean fork, live target-intent or hypothesis names a "
        "materially different CVRP-owned causal path before code work starts "
        "and explains why it is distinct from reviewed raw seed-baseline, "
        "short-horizon seed-trajectory, and post-construction seed micro-polish "
        "selector paths"
    ),
    (
        "for the next CVRP solver design, live target-intent or hypothesis "
        "records why the route-pair-overlap, bounded double-bridge, adaptive "
        "embedded-VNS runtime-allocation, frozen-safe neighbor-list filter, "
        "capacity-tight removal, seed-post selector, route-angle 2-opt-star, "
        "radial 2-opt-star relink, edge-frequency repair-scoring, and "
        "bounded two-for-one route-set exchange lines are parked, then targets the "
        "new causal path rather than another unchanged reviewed mechanism"
    ),
    (
        "live target-intent and hypothesis must commit to direct mechanism "
        "objective-effect evidence and CMT2/CMT4 protection before code work; "
        "do not rely on downstream ALNS/VNS absorption to justify a weak "
        "successor37/successor38-style mechanism"
    ),
    (
        "any construction-seed revisit includes activation, phase runtime, "
        "same-run baseline comparison or same-mechanism accepted delta before "
        "downstream ALNS/VNS, accepted flag, best-improved status, and per-case "
        "total_distance/feasibility/route-count evidence"
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
        "construction-seed, destroy/repair, route-pair overlap, or "
        "acceptance/adaptive-weighting claim"
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
        "do not revisit rank-gap or route-pressure acceptance gates; "
        "successor32 post-repair operator-credit weighting is now reviewed "
        f"zero-effect evidence; successor44d `{SUCCESSOR44_MECHANISM_ID}` is "
        "now reviewed weak-positive below-MDE policy outcome evidence, so any "
        "future simulated-annealing acceptance revisit needs a new mechanism "
        "id and explicit contrast against those reviewed acceptance/adaptive-"
        "weighting paths"
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
        "radial_2opt_star_relink successor38 active-no-effect evidence, reviewed "
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
        "below-MDE evidence and CMT2/CMT4 losses in v2; do not continue "
        "unchanged route_pair_overlap_removal or "
        "route_pair_overlap_removal_protected_followup after successor29 "
        "parked the route-pair-overlap line; do not continue unchanged "
        "bounded_cross_route_double_bridge_polish after successor30 zero-effect "
        "evidence; do not continue unchanged "
        "radial_2opt_star_relink after successor38 active-no-effect evidence "
        "with zero accepted mechanism moves; do not continue unchanged "
        "adaptive_embedded_vns_runtime_allocation after successor31 zero-effect "
        "evidence; do not continue unchanged neighbor_list_vns_filter after "
        "successor33 passed validation but failed frozen on candidate-side "
        "timeouts, and do not continue unchanged "
        "frozen_safe_neighbor_list_vns_filter after successor34 stayed "
        "weak-positive below MDE with a CMT2 regression; do not continue "
        "unchanged capacity_tightness_removal after successor35 valid active "
        "loss-heavy evidence; do not continue unchanged "
        "seed_post_optimization_selector after successor36b valid active "
        "zero-aggregate evidence and CMT2 regression. The next solver research "
        "slot should clean-fork to a materially different CVRP-owned causal "
        "path, with "
        "scheduler_destroy_size_policy limited to telemetry-only q-audit "
        "repair or a materially different scheduler-policy causal path, "
        "post_repair_effect_credit_weighting parked as reviewed zero-effect, "
        "destroy/repair insertion-cost lookahead parked, and construction-seed "
        "revisits required to avoid raw baseline, short-horizon trajectory, and "
        "post-construction micro-polish selector repeats, "
        "after "
        "bounded_2node_cross_exchange, intra_route_or_opt_reinsert, "
        "bounded_intra_route_3opt, bounded_ejection_chain_relocate, "
        "bounded_route_segment_exchange, bounded_cross_route_double_bridge_polish, "
        "radial_2opt_star_relink, "
        "angular_sector_removal, radial_string_removal, "
        "farthest_noise_related_removal, polar_sweep_destroy_repair, "
        "route_fragment_recombination_repair, adjacency_pair_removal_repair, "
        "load_compatible_ruin_recreate, load_complement_pair_removal, "
        "route_pair_crossover_repair, timewarp_string_removal, "
        "lookahead_insertion_cost_repair, "
        "lookahead_insertion_cost_repair_v2, and "
        "savings_seed_selection_probe plus granular_savings_seed_portfolio, "
        "exact_short_route_polish, short_horizon_seed_trajectory_selector, "
        "short_horizon_seed_trajectory_selector_v2, and "
        "seed_post_optimization_selector were reviewed no-positive-at-MDE; "
        "adaptive_embedded_vns_runtime_allocation and "
        "post_repair_effect_credit_weighting were reviewed zero-effect; revisits "
        "must name a new causal path and direct objective-effect telemetry"
    ),
)
MEASURABLE_OPPORTUNITY_CLASSES = (
    (
        "acceptance_or_adaptive_weighting: successor32 "
        f"`{SUCCESSOR32_MECHANISM_ID}` in `{SUCCESSOR32_TARGET_FILE}` is "
        "reviewed/default-avoid after valid screening showed internal "
        "operator-credit movement but zero objective effect. Do not repeat "
        "unchanged post-repair credit weighting or rank-gap/route-pressure "
        f"acceptance gates. Successor44d `{SUCCESSOR44_MECHANISM_ID}` is now "
        "reviewed/default-avoid after weak-positive below-MDE policy outcome "
        "evidence; future acceptance-policy revisits need a new mechanism id "
        "and a new material-difference claim."
    ),
    (
        "construction_seed_portfolio: successor25 raw seed-baseline selection "
        "is reviewed/default-avoid because direct seed gains were not "
        "preserved downstream; successor26b validly screened "
        f"`{SUCCESSOR26_MECHANISM_ID}` and `{SUCCESSOR26_V2_MECHANISM_ID}` "
        "below MDE and made them reviewed/default-avoid as short-horizon "
        "seed trajectory selectors. Successor18b moved "
        "granular_savings_seed_portfolio to reviewed below-MDE evidence and "
        "exact_short_route_polish to reviewed loss-heavy evidence, so do not "
        "continue unchanged variants. Successor36b validly activated "
        "seed_post_optimization_selector in a new module boundary with direct "
        "pre-ALNS/VNS selected-seed-versus-baseline telemetry, but aggregate "
        "medians stayed zero and CMT2 regressed. After reviewed "
        "savings_seed_selection_probe no-positive-at-MDE evidence, require any "
        "new construction path to be causally distinct from seed-baseline, "
        "seed-trajectory selection, and post-construction seed micro-polish "
        "selection"
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
        "tied to the changed repair/removal choice. Successor39 "
        f"`{SUCCESSOR39_MECHANISM_ID}` validly targeted bounded dual repair "
        "choice before VNS, activated, and stayed below MDE with CMT4/B/P "
        "losses; treat unchanged bounded dual repair choice as reviewed/"
        "default-avoid rather than the current prepared slot. Successor41 "
        f"`{SUCCESSOR41_MECHANISM_ID}` validly tested route-skeleton-biased "
        "regret repair at the scheduler repair boundary, and successor41b "
        "modularized that diagnostic, but both stayed below MDE and left "
        "P/B/E-family losses plus a CMT2 measurement-coverage caveat. Treat "
        "unchanged route-skeleton repair, threshold tuning, and further "
        "same-mechanism route-skeleton optimization follow-ups as "
        "reviewed/default-avoid. Successor43 "
        f"`{SUCCESSOR43_MECHANISM_ID}` validly targeted a pre-VNS destroy "
        "choice shadow selector, activated in all screened pairs, and stayed "
        "marginal below MDE with CMT2/B/P losses plus RNG/selected-operator "
        "attribution gaps. Successor43b "
        f"`{SUCCESSOR43B_MECHANISM_ID}` completed the protected follow-up and "
        "repaired much of the RNG isolation and scheduler attribution problem, "
        "but stayed below MDE with CMT2/CMT4/B losses and local selector gains "
        "that did not survive downstream search; park the destroy-shadow line "
        "instead of repeating another same-mechanism follow-up. Successor29 validly "
        "screened route_pair_overlap_removal_protected_followup and stayed "
        "negative, so the route-pair-overlap line is parked for v0.4. After "
        "the reviewed "
        "angular_sector_removal, radial_string_removal, and "
        "farthest_noise_related_removal, polar_sweep_destroy_repair, and "
        "route_fragment_recombination_repair, adjacency_pair_removal_repair, "
        "load_compatible_ruin_recreate, load_complement_pair_removal, "
        "route_pair_crossover_repair, timewarp_string_removal, "
        "lookahead_insertion_cost_repair, and "
        "lookahead_insertion_cost_repair_v2, boundary_spoke_outlier_removal, "
        "edge_conflict_endpoint_removal, route_pair_overlap_removal, "
        "route_pair_overlap_removal_protected_followup, and "
        "capacity_tightness_removal no-positive-at-MDE or loss-heavy results, "
        "do not continue unchanged destroy/repair removal in the next slot. "
        f"Successor45 `{SUCCESSOR45_MECHANISM_ID}` is now reviewed/default-avoid "
        "after local same-removed-set repair-placement gains failed to preserve "
        "final objective quality and failed CMT2/CMT4 protection. Require a "
        "destroy/repair causal path distinct from the reviewed removal, repair, "
        "selector, shadow, memory, skeleton, and repair-placement tournament "
        "paths before revisiting this family. Successor46 "
        f"`{SUCCESSOR46_MECHANISM_ID}` is now reviewed/default-avoid as an "
        "unchanged best-incumbent ruin/recreate candidate: it target-bound "
        "correctly but activated sparsely and had zero final best-solution "
        "effect. Successor46b "
        f"`{SUCCESSOR46B_MECHANISM_ID}` is now reviewed/default-avoid after "
        "activation improved but final evidence stayed weak-positive below MDE "
        "with CMT2 unsafe. Successor51 bounded route-arc LNS rebuild and "
        "successor52 bounded multi-candidate ALNS race are also reviewed/"
        "default-avoid unchanged after active below-MDE evidence with CMT2/CMT4 "
        "unsafe final outcomes. Do not continue best-solution ruin/recreate, "
        "unchanged route-arc LNS rebuild, or unchanged multi-candidate race in "
        "the next slot."
    ),
    (
        "bounded_local_search_variant: require feasible route-level "
        "objective deltas with bounded search effort. Successor34 "
        f"`{SUCCESSOR34_MECHANISM_ID}` is now reviewed weak-positive below "
        "MDE after repairing successor33's frozen timeout blocker. Do not "
        "continue unchanged neighbor-list filtering unless a future proposal "
        "names a materially new local-search causal path and direct effect. "
        "Successor38 "
        f"`{SUCCESSOR38_MECHANISM_ID}` is reviewed active-no-effect after "
        "zero accepted mechanism moves and observed_no_effect contract status. "
        "Successor40 "
        f"`{SUCCESSOR40_MECHANISM_ID}` is reviewed below-MDE after the active "
        "2-for-1 / 1-for-2 route-set exchange stayed loss-prone and the "
        "guarded refinement mostly became no-op. Do not continue unchanged "
        "two-for-one exchange or threshold/gating variants. Future "
        "bounded-local-search attempts require attempted/accepted counts, "
        "direct record_move delta, best-improved status, phase runtime, "
        "iteration count, budget-stop/fallback/skipped counters, and per-case "
        "total_distance/feasibility/route-count evidence; after the reviewed "
        "bounded_2node_cross_exchange, intra_route_or_opt_reinsert, "
        "bounded_intra_route_3opt, bounded_ejection_chain_relocate, and "
        "bounded_cross_route_double_bridge_polish, radial 2-opt-star relink, "
        "plus frozen-unsafe "
        "neighbor_list_vns_filter and weak-positive-below-MDE "
        "frozen_safe_neighbor_list_vns_filter evidence, require a bounded-local-search causal "
        "path distinct from cross-exchange, same-route Or-opt reinsertion, "
        "3-opt, ejection-chain relocation, double-bridge polish, radial "
        "2-opt-star relink, two-for-one route-set exchange, and the unchanged "
        "frozen-unsafe successor33 implementation. Require explicit contrast "
        "against existing _swap, _or_opt_1/_or_opt_2/_or_opt_3, "
        "_two_opt_star, and successor40-style two-route set exchange."
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
        "scheduler_runtime_allocation: successor31 "
        f"`{SUCCESSOR31_MECHANISM_ID}` recorded weighted runtime movement but "
        "stayed exact zero-effect; do not revisit unchanged embedded-VNS "
        "runtime allocation unless a future proposal names a materially new "
        "runtime causal path and direct objective-effect evidence"
    ),
)
SUCCESSOR_PORTFOLIO_RULE = (
    "Because large_instance_intra_route_two_opt_seed has complete checklist "
    "evidence but no positive-at-MDE outcome, and "
    "bounded_2node_cross_exchange, intra_route_or_opt_reinsert, and "
    "bounded_intra_route_3opt plus bounded_ejection_chain_relocate, "
    "bounded_route_segment_exchange, and "
    "bounded_cross_route_double_bridge_polish plus radial_2opt_star_relink "
    "have repeated that no-positive outcome "
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
    "construction successors, seed_post_optimization_selector has now "
    "repeated it as a post-construction seed selector, and "
    "operator_pair_destroy_size_bands plus "
    "stagnation_adaptive_destroy_size_schedule have repeated it as scheduler "
    "destroy-size successors. "
    "seed_post_optimization_selector moved from prior missing-activation "
    "evidence to successor36b valid active no-positive-at-MDE evidence and is "
    "now reviewed/default-avoid as unchanged repetition. "
    "Successor23 repaired observable stagnation_adaptive_destroy_size_schedule "
    "q deltas but stayed below-MDE, parked as quality regression, and missed "
    "explicit baseline_q/adapted_q/q_delta fields. Successor24 activated "
    "lookahead insertion-cost repair but stayed below-MDE, then v2 recorded "
    "direct-effect-zero telemetry with worse CMT4/P/X case evidence. "
    "Successor25 raw seed-baseline selection stayed below-MDE and its direct "
    "seed deltas were not preserved downstream. Successor26b validly screened "
    "short-horizon seed trajectory selection after the static recognizer "
    "repair, but both rows stayed below-MDE and v2 lost on CMT2/CMT4. "
    "Successor29 forced the protected route-pair-overlap follow-up and stayed "
    "negative, so that line is parked. Successor30 double-bridge polish and "
    "successor31 adaptive embedded-VNS runtime allocation both completed valid "
    "zero-effect screening. Successor32 post-repair effect credit weighting "
    "also completed valid zero-objective-effect screening. Successor33 "
    "neighbor-list VNS filtering produced positive screening and validation "
    "evidence, then failed frozen on candidate-side timeouts. Successor34 "
    "repaired the timeout blocker, but both screened rows stayed below MDE "
    "(best median delta 0.25, CI high 3.25) and CMT2 remained negative. Treat "
    "unchanged successor34 as reviewed weak-positive below MDE, not "
    "promotion-grade evidence. Successor35 capacity-tight removal then "
    "completed valid active screening but was loss-heavy below MDE with CMT2 "
    "negative, so unchanged capacity_tightness_removal is parked. Successor36b "
    f"then completed valid active `{SUCCESSOR36_MECHANISM_ID}` screening in "
    f"`{SUCCESSOR36_TARGET_FILE}`, but aggregate medians stayed zero and CMT2 "
    "regressed, so unchanged seed-post selector variants are parked. Successor37 "
    "then showed the remaining blocker is proposal-control/candidate-quality: "
    f"`{SUCCESSOR37_ROUTE_ANGLE_MECHANISM_ID}` was a negative local-search "
    "order-bias candidate, and "
    f"`{SUCCESSOR37_EDGE_FREQUENCY_MECHANISM_ID}` was weak-positive below MDE "
    "but direct-effect-zero with CMT2/CMT4 all-seed losses. Successor38 "
    "confirmed the target-intent/hypothesis quality contract can block weak "
    "premises, but "
    f"`{SUCCESSOR38_MECHANISM_ID}` was active-no-effect with zero accepted "
    "mechanism moves and observed_no_effect status. Successor39 "
    f"`{SUCCESSOR39_MECHANISM_ID}` activated as bounded dual repair choice "
    "before VNS but remained below MDE and left CMT4/B/P losses, so unchanged "
    "bounded dual repair choice is now reviewed/default-avoid. Successor40 "
    f"`{SUCCESSOR40_MECHANISM_ID}` also stayed below MDE after an active "
    "two-route set exchange and a guarded no-op-heavy follow-up, so unchanged "
    "two-for-one exchange variants are reviewed/default-avoid. Successor41/41b "
    f"`{SUCCESSOR41_MECHANISM_ID}` is also reviewed/default-avoid after valid "
    "below-MDE route-skeleton evidence with persistent P/B/E-family losses and "
    "a CMT2 measurement-coverage caveat. Successor42b "
    f"`{SUCCESSOR42_MECHANISM_ID}` is reviewed/default-avoid after active "
    "marginal below-MDE evidence with CMT2/CMT4 losses. Successor43 "
    f"`{SUCCESSOR43_MECHANISM_ID}` and successor43b "
    f"`{SUCCESSOR43B_MECHANISM_ID}` are both reviewed/default-avoid after "
    "the protected follow-up failed to produce positive-at-MDE or protected-"
    "case-safe final objective evidence. Successor45 "
    f"`{SUCCESSOR45_MECHANISM_ID}` is reviewed/default-avoid after local "
    "repair-placement gains failed to preserve final objective quality and "
    "CMT2/CMT4 protection. Successor46 "
    f"`{SUCCESSOR46_MECHANISM_ID}` is reviewed/default-avoid as an unchanged "
    "best-solution ruin/recreate candidate after valid screening showed sparse "
    "activation and zero final best-solution effect. Successor46b "
    f"`{SUCCESSOR46B_MECHANISM_ID}`, successor47 "
    f"`{SUCCESSOR47_MECHANISM_ID}`, and successor48/49 route-pool "
    f"`{SUCCESSOR48_MECHANISM_ID}` are now also reviewed/default-avoid after "
    "valid below-MDE or no-effect evidence. Successor50 "
    f"`{SUCCESSOR50_MECHANISM_ID}` is reviewed/default-avoid as "
    "repair-or-infra work, not a solver mechanism. Successor51 "
    "`bounded_route_arc_lns_rebuild` is reviewed/default-avoid after active-"
    "marginal below-MDE evidence with CMT2/CMT4 unsafe. Successor52 "
    "`bounded_multi_candidate_alns_race` is reviewed/default-avoid unchanged "
    "after active-positive below-MDE evidence with local race signal but "
    "loss-heavy CMT2/CMT4 final outcomes. The next CVRP solver slot must either "
    "design a protected, budgeted candidate-trajectory selector repair for the "
    "race's RNG/VNS/final-attribution failure modes or clean-fork to a materially "
    "different CVRP-owned causal path after the exact material_difference schema "
    "and CMT2/CMT4 case-coverage requirements are satisfied. Scheduler destroy-size "
    "policy remains allowed only as "
    "telemetry-only q-audit repair or a materially different scheduler-policy "
    "causal path; insertion-cost lookahead repair and post-repair effect "
    "credit weighting are parked as reviewed solver-negative. Use "
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
        "target_intent_required_mechanism_ids": [],
        "reviewed_mechanism_ids": [
            *list(REVIEWED_MECHANISM_IDS),
            SUCCESSOR41_MECHANISM_ID,
            SUCCESSOR48_MECHANISM_ID,
            SUCCESSOR50_MECHANISM_ID,
            ROUTE_FIRST_COMPARISON_MECHANISM_ID,
        ],
        "suppressed_mechanism_ids": list(SUPPRESSED_MECHANISM_IDS),
        "material_difference_requirement": deepcopy(
            CVRP_MATERIAL_DIFFERENCE_REQUIREMENT
        ),
        "evidence_requirements": [
            deepcopy(CVRP_ALGORITHMIC_INTERVENTION_SUFFICIENCY_CONTRACT),
        ],
        "successor41_target_intent": {
            "mechanism_id": SUCCESSOR41_MECHANISM_ID,
            "mechanism_family": "destroy_repair_selection",
            "target_file": SUCCESSOR41_TARGET_FILE,
            "target_files": [
                SUCCESSOR41_TARGET_FILE,
                SUCCESSOR41_SECONDARY_TARGET_FILE,
            ],
            "design_path": SUCCESSOR41_DESIGN_PATH,
            "postrun_path": SUCCESSOR41_POSTRUN_PATH,
            "followup_design_path": SUCCESSOR41B_DESIGN_PATH,
            "followup_postrun_path": SUCCESSOR41B_POSTRUN_PATH,
            "status": "diagnostic_exhausted_below_mde",
            "blocked_actions": [
                "long_run",
                "unchanged_scheduler_helper_rerun",
                "same_mechanism_threshold_tuning",
                "same_mechanism_optimization_followup",
            ],
            "rule": SUCCESSOR41_TARGET_INTENT_RULE,
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
        },
        "successor40_reviewed_evidence": {
            "mechanism_id": SUCCESSOR40_MECHANISM_ID,
            "mechanism_family": "bounded_local_search_variant",
            "target_file": SUCCESSOR40_TARGET_FILE,
            "design_path": SUCCESSOR40_DESIGN_PATH,
            "postrun_path": SUCCESSOR40_POSTRUN_PATH,
            "reviewed_rule": (
                "Do not continue unchanged bounded two-for-one exchange or "
                "same-mechanism threshold/gating variants after successor40 "
                "valid below-MDE evidence."
            ),
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
        },
        "successor42b_reviewed_evidence": {
            "mechanism_id": SUCCESSOR42_MECHANISM_ID,
            "mechanism_family": "destroy_repair_selection",
            "target_file": SUCCESSOR42_TARGET_FILE,
            "postrun_path": SUCCESSOR42B_POSTRUN_PATH,
            "reviewed_rule": SUCCESSOR42B_REVIEWED_RULE,
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
        },
        "successor43_reviewed_evidence": {
            "mechanism_id": SUCCESSOR43_MECHANISM_ID,
            "mechanism_family": "destroy_repair_selection",
            "target_file": SUCCESSOR43_TARGET_FILE,
            "target_files": [
                SUCCESSOR43_TARGET_FILE,
                SUCCESSOR43_WIRING_FILE,
            ],
            "design_path": SUCCESSOR43_DESIGN_PATH,
            "postrun_path": SUCCESSOR43_POSTRUN_PATH,
            "status": "reviewed_marginal_below_mde_protected_case_unsafe",
            "blocked_actions": [
                "long_run",
                "unchanged_raw_shadow_selector_rerun",
                "same_mechanism_threshold_tuning",
                "same_mechanism_without_rng_isolation",
                "same_mechanism_without_selected_operator_attribution",
            ],
            "reviewed_rule": SUCCESSOR43_REVIEWED_RULE,
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
        },
        "successor43b_reviewed_evidence": {
            "mechanism_id": SUCCESSOR43B_MECHANISM_ID,
            "mechanism_family": "destroy_repair_selection",
            "target_file": SUCCESSOR43B_TARGET_FILE,
            "target_files": [
                SUCCESSOR43B_TARGET_FILE,
                SUCCESSOR43B_WIRING_FILE,
            ],
            "design_path": SUCCESSOR43B_DESIGN_PATH,
            "postrun_path": SUCCESSOR43B_POSTRUN_PATH,
            "status": "reviewed_below_mde_protected_case_unsafe",
            "blocked_actions": [
                "long_run",
                "same_mechanism_threshold_tuning",
                "same_mechanism_optimization_followup",
                "another_destroy_shadow_selector_followup",
            ],
            "carried_lessons": [
                SELECTOR_TELEMETRY_HYGIENE_LESSON,
                "default_alternate_diagnostics_should_be_explicit",
                "selected_operator_attribution_must_match_scheduler_trace",
            ],
            "reviewed_rule": SUCCESSOR43B_REVIEWED_RULE,
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
        },
        "successor44d_reviewed_evidence": {
            "mechanism_id": SUCCESSOR44_MECHANISM_ID,
            "mechanism_family": "acceptance_or_adaptive_weighting",
            "target_file": SUCCESSOR44_TARGET_FILE,
            "target_files": [
                SUCCESSOR44_TARGET_FILE,
                SUCCESSOR44_WIRING_FILE,
            ],
            "design_path": SUCCESSOR44_DESIGN_PATH,
            "postrun_path": SUCCESSOR44D_POSTRUN_PATH,
            "status": "reviewed_weak_positive_below_mde_policy_hygiene_repaired",
            "required_mechanism_binding": "none",
            "blocked_actions": [
                "long_run",
                "same_mechanism_threshold_tuning",
                "unchanged_acceptance_guard_repeat",
                "rank_gap_acceptance_gate_repeat",
                "route_pressure_acceptance_gate_repeat",
                "operator_credit_weighting_repeat",
                "pre_vns_selector_local_delta_as_final_effect",
            ],
            "carried_lessons": [
                SELECTOR_TELEMETRY_HYGIENE_LESSON,
                "final_effect_must_be_post_downstream_or_accepted_trajectory",
                "do_not_record_positive_delta_for_rejected_worse_candidates",
            ],
            "reviewed_rule": SUCCESSOR44D_REVIEWED_RULE,
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
        },
        "successor45_reviewed_evidence": {
            "mechanism_id": SUCCESSOR45_MECHANISM_ID,
            "mechanism_family": "destroy_repair_selection",
            "target_file": SUCCESSOR45_TARGET_FILE,
            "target_files": [
                SUCCESSOR45_TARGET_FILE,
                SUCCESSOR45_WIRING_FILE,
            ],
            "design_path": SUCCESSOR45_DESIGN_PATH,
            "postrun_path": SUCCESSOR45_POSTRUN_PATH,
            "status": "reviewed_quality_regression_local_effect_not_preserved",
            "required_mechanism_binding": "none",
            "blocked_actions": [
                "long_run",
                "same_mechanism_threshold_tuning",
                "same_mechanism_optimization_followup",
                "unchanged_repair_placement_tournament_repeat",
                "repair_operator_selector_repeat",
                "destroy_shadow_selector_followup",
                "lookahead_insertion_repeat",
                "route_memory_repair_repeat",
                "route_skeleton_repair_repeat",
                "pre_vns_local_delta_as_final_effect",
            ],
            "carried_lessons": [
                SELECTOR_TELEMETRY_HYGIENE_LESSON,
                "pre_vns_repair_delta_is_not_final_protocol_outcome",
                "same_removed_customer_set_baseline_vs_alternate_repair",
                "alternate_repair_should_not_consume_main_rng_when_rejected",
            ],
            "reviewed_rule": SUCCESSOR45_REVIEWED_RULE,
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
        },
        "successor46_reviewed_evidence": {
            "mechanism_id": SUCCESSOR46_MECHANISM_ID,
            "mechanism_family": "destroy_repair_selection",
            "target_file": SUCCESSOR46_TARGET_FILE,
            "target_files": [
                SUCCESSOR46_TARGET_FILE,
                SUCCESSOR46_WIRING_FILE,
            ],
            "design_path": SUCCESSOR46_DESIGN_PATH,
            "postrun_path": SUCCESSOR46_POSTRUN_PATH,
            "status": "reviewed_activation_sparse_observed_no_effect",
            "required_mechanism_binding": "none",
            "blocked_actions": [
                "long_run",
                "same_mechanism_threshold_tuning",
                "unchanged_best_solution_ruin_recreate_repeat",
                "same_mechanism_without_rng_isolation",
                "same_mechanism_without_outcome_cause_telemetry",
            ],
            "carried_lessons": [
                "rejected_attempt_rng_must_be_isolated_or_restored",
                "stagnation_trigger_must_be_observable_in_short_screening",
                "outcome_telemetry_must_separate_reject_causes",
                "protected_cases_need_mechanism_level_activation_or_caveat",
            ],
            "reviewed_rule": SUCCESSOR46_REVIEWED_RULE,
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
        },
        "successor46b_reviewed_evidence": {
            "mechanism_id": SUCCESSOR46B_MECHANISM_ID,
            "mechanism_family": "destroy_repair_selection",
            "target_file": SUCCESSOR46B_TARGET_FILE,
            "target_files": [
                SUCCESSOR46B_TARGET_FILE,
                SUCCESSOR46B_WIRING_FILE,
            ],
            "design_path": SUCCESSOR46B_DESIGN_PATH,
            "postrun_path": SUCCESSOR46B_POSTRUN_PATH,
            "status": "reviewed_weak_positive_below_mde_protected_case_unsafe",
            "required_mechanism_binding": "none",
            "blocked_actions": [
                "long_run",
                "same_mechanism_threshold_tuning",
                "same_mechanism_optimization_followup",
                "best_solution_ruin_recreate_continuation",
                "telemetry_hygiene_as_solver_experiment",
            ],
            "carried_lessons": [
                "activation_repair_is_not_sufficient_without_final_effect",
                "reject_cause_telemetry_must_not_collapse_to_accepted_zero",
                "cmt4_case_tie_without_mechanism_activation_is_not_protection",
                "cmt2_negative_blocks_long_run",
            ],
            "reviewed_rule": SUCCESSOR46B_REVIEWED_RULE,
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
        },
        "successor47_reviewed_evidence": {
            "mechanism_id": SUCCESSOR47_MECHANISM_ID,
            "mechanism_family": "bounded_local_search_variant",
            "target_file": SUCCESSOR47_TARGET_FILE,
            "target_files": [
                SUCCESSOR47_TARGET_FILE,
                SUCCESSOR47_WIRING_FILE,
            ],
            "design_path": SUCCESSOR47_DESIGN_PATH,
            "postrun_path": SUCCESSOR47_POSTRUN_PATH,
            "status": "reviewed_marginal_below_mde_protected_case_unsafe",
            "required_mechanism_binding": "none",
            "blocked_actions": [
                "long_run",
                "same_mechanism_threshold_tuning",
                "unchanged_giant_tour_split_repeat",
                "contiguous_split_dp_followup",
                "telemetry_hygiene_as_solver_experiment",
            ],
            "carried_lessons": [
                "activation_without_direct_split_effect_is_not_enough",
                "route_order_generation_must_not_be_too_conservative",
                "reject_cause_telemetry_must_be_explicit",
                "cmt2_cmt4_negative_blocks_long_run",
            ],
            "reviewed_rule": SUCCESSOR47_REVIEWED_RULE,
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
        },
        "successor48_reviewed_evidence": {
            "mechanism_id": SUCCESSOR48_MECHANISM_ID,
            "mechanism_family": "bounded_local_search_variant",
            "target_file": SUCCESSOR48_TARGET_FILE,
            "target_files": [
                SUCCESSOR48_TARGET_FILE,
                SUCCESSOR48_WIRING_FILE,
            ],
            "design_path": SUCCESSOR48_DESIGN_PATH,
            "postrun_path": SUCCESSOR48_POSTRUN_PATH,
            "postrun_paths": [
                SUCCESSOR48_POSTRUN_PATH,
                SUCCESSOR49_POSTRUN_PATH,
            ],
            "status": "reviewed_no_positive_at_mde_same_line_repeated",
            "required_mechanism_binding": "none",
            "blocked_actions": [
                "long_run",
                "same_mechanism_threshold_tuning",
                "same_mechanism_beam_or_pool_tuning",
                "unchanged_route_pool_exact_cover_repeat",
                "successor48_or_successor49_same_line_followup",
                "telemetry_hygiene_as_solver_experiment",
            ],
            "carried_lessons": [
                "whole-route pool exact cover was too conservative",
                "route-pool activation without accepted final effect is insufficient",
                "same-run incumbent/current/best route pools are not diverse enough",
                "route-pool source counts and reject causes are diagnostic only",
            ],
            "reviewed_rule": SUCCESSOR48_REVIEWED_RULE,
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
        },
        "successor50_reviewed_evidence": {
            "mechanism_id": SUCCESSOR50_MECHANISM_ID,
            "mechanism_family": "repair_or_infra_candidate",
            "target_file": SUCCESSOR50_TARGET_FILE,
            "target_files": [
                SUCCESSOR50_TARGET_FILE,
            ],
            "postrun_path": SUCCESSOR50_POSTRUN_PATH,
            "status": "reviewed_repair_or_infra_not_solver_mechanism",
            "required_mechanism_binding": "none",
            "blocked_actions": [
                "long_run",
                "same_mechanism_followup",
                "telemetry_tuning",
                "scheduler_contract_gate_as_solver_experiment",
                "metadata_preflight_as_solver_experiment",
                "hook_wrapper_as_solver_experiment",
            ],
            "carried_lessons": [
                "contract repair must not consume solver-design optimization slots",
                "metadata gates do not generate candidate route states",
                "telemetry-only wrappers do not prove final objective effect",
                "context/contract repair is already active before successor50",
            ],
            "reviewed_rule": SUCCESSOR50_REVIEWED_RULE,
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
        },
        "route_first_comparison_target_intent": route_first_comparison_focus(),
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
                "material causal-path difference from reviewed double-bridge polish",
                "material causal-path difference from reviewed route-angle 2-opt-star",
                "material causal-path difference from reviewed bounded two-for-one exchange",
                "neighbor-list candidate filtering/order evidence when using bounded_local_search_variant",
                "local-search attempted/accepted counts and record_move delta when revisiting bounded_local_search_variant",
                "material causal-path difference from reviewed seed-post selector micro-polish",
                "same-run baseline or same-mechanism direct objective delta before downstream ALNS/VNS when revisiting construction seeds",
                "scheduler destroy-size baseline_q/adapted_q/q_delta evidence when using scheduler_destroy_size_policy",
                "nonzero aligned candidate/champion q deltas before objective-effect interpretation",
                "post-repair operator-credit old score and new credit when using acceptance_or_adaptive_weighting",
                "operator weights before and after segment update when using acceptance_or_adaptive_weighting",
                (
                    "same removed-customer set baseline repair distance, "
                    "alternate repair distance, and pre-VNS repair delta "
                    "when using a future repair-placement mechanism distinct "
                    f"from reviewed {SUCCESSOR45_MECHANISM_ID}"
                ),
                (
                    "selector/filter mechanisms separate pre_vns_local_delta "
                    "from post_downstream_or_final_total_distance_delta"
                ),
                (
                    "best-solution intensification mechanisms report final "
                    "post-VNS global-best total_distance delta, not pre-VNS "
                    "local repair diagnostics"
                ),
                (
                    "RNG or trajectory isolation evidence for rejected "
                    f"{SUCCESSOR46B_MECHANISM_ID} attempts"
                ),
                (
                    "mechanism-level CMT2/CMT4 activation evidence or explicit "
                    "caveat for best-solution intensification repairs"
                ),
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
                "material causal-path difference from reviewed route-pair-overlap follow-ups",
                "material causal-path difference from reviewed edge-frequency repair scoring",
                "material causal-path difference from reviewed bounded dual repair selector",
                "material causal-path difference from reviewed adaptive embedded-VNS runtime allocation",
                "material causal-path difference from reviewed successor44 acceptance guard",
                "material causal-path difference from reviewed savings seed selection",
                "per-case total_distance delta tied to the changed mechanism",
                "feasibility and route-count preservation or explicit caveat",
                "runtime budget evidence under the formal policy",
            ),
        ),
        EvidenceRequirement(
            requirement_id="selector_telemetry_hygiene",
            category="telemetry_hygiene",
            description=SELECTOR_TELEMETRY_HYGIENE_RULE,
            mechanism_ids=(
                SUCCESSOR39_MECHANISM_ID,
                SUCCESSOR43_MECHANISM_ID,
                SUCCESSOR43B_MECHANISM_ID,
                SUCCESSOR45_MECHANISM_ID,
                "destroy_repair_selection",
                "selector",
                "filter",
                "shadow_selector",
                "repair_placement_tournament",
            ),
            protected_items=PROTECTED_CASES,
            required_fields=(
                SELECTOR_TELEMETRY_HYGIENE_LESSON,
                "pre_vns_local_delta labelled as diagnostic evidence only",
                "post_downstream_or_final_total_distance_delta for final claims",
                "accepted/current/best trajectory attribution for effect claims",
                "CMT2/CMT4 case-level total_distance deltas or split caveat",
            ),
        ),
        EvidenceRequirement(
            requirement_id="successor44d_reviewed_policy_evidence",
            category="reviewed_acceptance_policy_evidence",
            description=SUCCESSOR44D_REVIEWED_RULE,
            mechanism_ids=(
                SUCCESSOR44_MECHANISM_ID,
                "acceptance_or_adaptive_weighting",
                SUCCESSOR44_TARGET_FILE,
                SUCCESSOR44_WIRING_FILE,
            ),
            protected_items=PROTECTED_CASES,
            required_fields=(
                "successor44d postrun cited before any acceptance-policy revisit",
                "no unchanged post_vns_best_anchor_acceptance_guard long-run",
                "new mechanism id required for future acceptance-policy revisit",
                "no fake direct-effect record_move delta for policy outcome evidence",
                "formal per-case total_distance remains the solver evidence source",
            ),
        ),
        EvidenceRequirement(
            requirement_id="successor45_bounded_repair_placement_tournament",
            category="reviewed_destroy_repair_selection_evidence",
            description=SUCCESSOR45_REVIEWED_RULE,
            mechanism_ids=(
                SUCCESSOR45_MECHANISM_ID,
                "destroy_repair_selection",
                SUCCESSOR45_TARGET_FILE,
                SUCCESSOR45_WIRING_FILE,
            ),
            protected_items=PROTECTED_CASES,
            required_fields=(
                "successor45 postrun cited before any repair-placement revisit",
                "no unchanged bounded_repair_placement_tournament long-run",
                "no same-mechanism threshold or gating follow-up",
                "material contrast against successor24 lookahead insertion",
                "material contrast against successor39 repair selector",
                "material contrast against successor43/43b destroy shadow selectors",
                "material contrast against route-memory and route-skeleton repair",
                "same removed-customer set for baseline and alternate repair",
                "baseline repaired candidate total_distance before VNS",
                "alternate repaired candidate total_distance before VNS",
                "strict feasible route-count-safe replacement condition",
                "future repair-placement variants must isolate alternate RNG or caveat stochastic trajectory drift",
                "pre-VNS repair delta labelled separately from final trajectory claims",
                "final per-case total_distance deltas",
                "feasibility and route-count preservation or explicit caveat",
                "CMT2/CMT4 case-level total_distance deltas or split caveat",
            ),
        ),
        EvidenceRequirement(
            requirement_id=(
                "successor46_best_solution_ruin_recreate_intensification"
            ),
            category="reviewed_destroy_repair_selection_evidence",
            description=SUCCESSOR46_REVIEWED_RULE,
            mechanism_ids=(
                SUCCESSOR46_MECHANISM_ID,
                "destroy_repair_selection",
                SUCCESSOR46_TARGET_FILE,
                SUCCESSOR46_WIRING_FILE,
            ),
            protected_items=PROTECTED_CASES,
            required_fields=(
                "successor46 postrun cited before any same-line follow-up",
                "no unchanged best_solution_ruin_recreate_intensification long-run",
                "no same-mechanism threshold tuning without contract repair",
                "main RNG consumed by rejected attempts is carried as a design gap",
                "sparse activation is carried as a design gap",
                "outcome reject causes must be separated before another run",
                "mechanism-level CMT2/CMT4 activation or caveat required",
            ),
        ),
        EvidenceRequirement(
            requirement_id=(
                "successor46b_best_solution_activation_contract_repair"
            ),
            category="reviewed_destroy_repair_selection_evidence",
            description=SUCCESSOR46B_REVIEWED_RULE,
            mechanism_ids=(
                SUCCESSOR46B_MECHANISM_ID,
                "destroy_repair_selection",
                SUCCESSOR46B_TARGET_FILE,
                SUCCESSOR46B_WIRING_FILE,
            ),
            protected_items=PROTECTED_CASES,
            required_fields=(
                "successor46b postrun cited before any related proposal",
                "no best-solution ruin/recreate activation-repair long-run",
                "no same-mechanism threshold tuning or successor46c solver slot",
                "weak-positive below-MDE evidence carried as reviewed",
                "CMT2 negative protected-case evidence carried as blocker",
                "CMT4 tie without mechanism phase activation carried as caveat",
                "reject-cause telemetry gap treated as hygiene, not solver follow-up",
            ),
        ),
        EvidenceRequirement(
            requirement_id="successor47_bounded_giant_tour_split_recombination",
            category="reviewed_bounded_local_search_evidence",
            description=SUCCESSOR47_REVIEWED_RULE,
            mechanism_ids=(
                SUCCESSOR47_MECHANISM_ID,
                "bounded_local_search_variant",
                SUCCESSOR47_TARGET_FILE,
                SUCCESSOR47_WIRING_FILE,
            ),
            protected_items=PROTECTED_CASES,
            required_fields=(
                "successor47 postrun cited before any related proposal",
                "no unchanged bounded giant-tour split recombination long-run",
                "no same-mechanism threshold or route-order tuning follow-up",
                "marginal below-MDE evidence carried as reviewed",
                "CMT2/CMT4 negative protected-case evidence carried as blocker",
                "missing reject-cause telemetry treated as hygiene not solver follow-up",
            ),
        ),
        route_first_comparison_evidence_requirement(PROTECTED_CASES),
        EvidenceRequirement(
            requirement_id="cvrp_algorithmic_intervention_sufficiency",
            category="solver_design_prompt_contract",
            description=CVRP_ALGORITHMIC_INTERVENTION_SUFFICIENCY_CONTRACT[
                "description"
            ],
            mechanism_ids=(
                "cvrp_solver_design_clean_fork",
                "route_pool_recombination",
                "future_clean_fork_mechanism",
            ),
            protected_items=PROTECTED_CASES,
            required_fields=tuple(
                str(item)
                for item in CVRP_ALGORITHMIC_INTERVENTION_SUFFICIENCY_CONTRACT[
                    "required_fields"
                ]
            ),
        ),
        EvidenceRequirement(
            requirement_id=(
                "successor48_bounded_route_pool_set_partition_recombination"
            ),
            category="reviewed_bounded_local_search_evidence",
            description=SUCCESSOR48_REVIEWED_RULE,
            mechanism_ids=(
                SUCCESSOR48_MECHANISM_ID,
                "bounded_local_search_variant",
                SUCCESSOR48_TARGET_FILE,
                SUCCESSOR48_WIRING_FILE,
            ),
            protected_items=PROTECTED_CASES,
            required_fields=(
                "successor48 postrun cited before any route-pool proposal",
                "successor49 trace audit cited before any route-pool proposal",
                "no unchanged bounded_route_pool_set_partition_recombination long-run",
                "no same-mechanism beam width or pool-limit tuning follow-up",
                "no route-pool telemetry-hygiene-only solver experiment",
                "whole-route route-pool exact cover carried as reviewed no-effect evidence",
                "direct mechanism effect was zero or below MDE",
                "same-run route-pool diversity was insufficient",
                "new CVRP-owned causal path required if revisiting recombination",
                "CMT2/CMT4 priority-case outcome evidence remains required",
            ),
        ),
        EvidenceRequirement(
            requirement_id="successor41_route_skeleton_regret_repair",
            category="reviewed_destroy_repair_selection_evidence",
            description=SUCCESSOR41_TARGET_INTENT_RULE,
            mechanism_ids=(
                SUCCESSOR41_MECHANISM_ID,
                "destroy_repair_selection",
                SUCCESSOR41_TARGET_FILE,
                SUCCESSOR41_SECONDARY_TARGET_FILE,
            ),
            protected_items=PROTECTED_CASES,
            required_fields=(
                "successor41 and successor41b postrun evidence cited before any related proposal",
                "no route_skeleton_regret_repair long-run or same-mechanism tuning",
                "no unchanged scheduler helper rerun",
                "no repeated route-skeleton threshold or margin gate variant",
                "CMT2 measurement-coverage caveat carried forward",
                "P/B/E-family losses carried forward as route-skeleton risk",
                "next proposal names a distinct CVRP-owned causal path",
            ),
        ),
        EvidenceRequirement(
            requirement_id="successor40_reviewed_two_for_one_default_avoid",
            category="reviewed_bounded_local_search_evidence",
            description=(
                f"Successor40 `{SUCCESSOR40_MECHANISM_ID}` completed valid "
                "screening below MDE; future bounded-local-search proposals "
                "must not repeat unchanged two-for-one route-set exchange or "
                "same-mechanism threshold/gating variants."
            ),
            mechanism_ids=(
                SUCCESSOR40_MECHANISM_ID,
                "bounded_local_search_variant",
                SUCCESSOR40_TARGET_FILE,
            ),
            protected_items=PROTECTED_CASES,
            required_fields=(
                "material causal-path difference from reviewed bounded_two_for_one_exchange",
                "direct mechanism objective-effect evidence for the new local-search path",
                "CMT2/CMT4 case-level total_distance deltas or split caveat",
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
            requirement_id=(
                f"{_slug(str(item['mechanism_id']))}_reviewed_"
                f"{'no_positive' if outcome_status == REVIEWED_SUCCESSOR_OUTCOME_STATUS else _slug(outcome_status)}"
            ),
            category="reviewed_successor_evidence",
            description=(
                f"{item['mechanism_id']} is reviewed CVRP successor evidence "
                f"with outcome {outcome_status}; do not "
                "repeat it as the next CVRP attempt without a materially new "
                f"{item['causal_path_label']} causal path."
            ),
            mechanism_ids=(
                str(item["mechanism_id"]),
                str(item["mechanism_family"]),
            ),
            required_fields=(
                "cvrp_successor_summary checklist_status=proven",
                f"cvrp_successor_summary outcome_status={outcome_status}",
                f"new {item['causal_path_label']} causal path if revisited",
                "direct per-case total_distance objective-effect telemetry",
            ),
        )
        for item in REVIEWED_SUCCESSOR_MECHANISMS
        for outcome_status in (
            str(item.get("outcome_status") or REVIEWED_SUCCESSOR_OUTCOME_STATUS),
        )
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
        SUCCESSOR41_MECHANISM_ID,
        SUCCESSOR41_TARGET_FILE,
        SUCCESSOR41_SECONDARY_TARGET_FILE,
        SUCCESSOR40_MECHANISM_ID,
        SUCCESSOR40_TARGET_FILE,
        SUCCESSOR43B_MECHANISM_ID,
        SUCCESSOR43B_TARGET_FILE,
        SUCCESSOR44_MECHANISM_ID,
        SUCCESSOR44_TARGET_FILE,
        SUCCESSOR44_WIRING_FILE,
        SUCCESSOR45_MECHANISM_ID,
        SUCCESSOR45_TARGET_FILE,
        SUCCESSOR45_WIRING_FILE,
        SUCCESSOR46_MECHANISM_ID,
        SUCCESSOR46_TARGET_FILE,
        SUCCESSOR46_WIRING_FILE,
        SUCCESSOR46B_MECHANISM_ID,
        SUCCESSOR46B_TARGET_FILE,
        SUCCESSOR46B_WIRING_FILE,
        SUCCESSOR47_MECHANISM_ID,
        SUCCESSOR47_TARGET_FILE,
        SUCCESSOR47_WIRING_FILE,
        SUCCESSOR48_MECHANISM_ID,
        SUCCESSOR48_TARGET_FILE,
        SUCCESSOR48_WIRING_FILE,
        *route_first_comparison_related_ids(),
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
                ROUTE_FIRST_COMPARISON_TARGET_INTENT_RULE,
                SUCCESSOR50_REVIEWED_RULE,
                SUCCESSOR48_REVIEWED_RULE,
                SUCCESSOR47_REVIEWED_RULE,
                SUCCESSOR46B_REVIEWED_RULE,
                SUCCESSOR46_REVIEWED_RULE,
                SUCCESSOR45_REVIEWED_RULE,
                SUCCESSOR44D_REVIEWED_RULE,
                SUCCESSOR43B_REVIEWED_RULE,
                SUCCESSOR43_REVIEWED_RULE,
                SUCCESSOR41_TARGET_INTENT_RULE,
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
                SELECTOR_TELEMETRY_HYGIENE_RULE,
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
