"""Successor55 solution-pool guidance for the CVRP research surface."""

from __future__ import annotations

from typing import Any

from scion.research_guidance import EvidenceRequirement, RequiredMechanism

SUCCESSOR55_MECHANISM_ID = "bounded_elite_solution_pool_search"
SUCCESSOR55_TARGET_FILE = "policies/baseline_modules/solution_pool.py"
SUCCESSOR55_WIRING_FILE = "policies/baseline_modules/scheduler.py"
SUCCESSOR55_DESIGN_PATH = (
    "scion/docs/experiments/v0.4/"
    "v04-cvrp-successor55-bounded-elite-solution-pool-design-20260712.md"
)
SUCCESSOR55_TARGET_INTENT_RULE = (
    f"Successor55 target-intent is `{SUCCESSOR55_MECHANISM_ID}`: a materially "
    "different CVRP-owned search-state clean fork after successor54 parked the "
    "protected race selector line. Keep hard `required_mechanism_ids` empty, "
    "but bind target intent to successor55. A candidate should add a bounded "
    "elite feasible solution pool in "
    f"`{SUCCESSOR55_TARGET_FILE}` with only minimal scheduler wiring in "
    f"`{SUCCESSOR55_WIRING_FILE}`. The pool owns admission, bounded size, "
    "route-diversity checks, anchor selection, feasibility/route-count "
    "guards, and mechanism telemetry. Scheduler code should only initialize "
    "the pool, offer accepted/current/best snapshots, and switch current to a "
    "pool anchor under a bounded stagnation or periodic policy. This is not a "
    "same-line protected race repair, route-pool exact-cover continuation, "
    "route-first config flip, seed selector, destroy/removal rule, local-search "
    "move, or contract/helper-only patch."
)
SUCCESSOR55_REQUIRED_OBSERVATIONS = (
    "pool_admission_attempted_accepted_rejected_counts",
    "anchor_switch_attempted_accepted_rejected_counts",
    "admission_reject_causes",
    "final_best_total_distance_delta_attribution",
    "feasibility_and_route_count_preservation",
    "bounded_runtime_or_budget_stop_status",
    "CMT2_CMT4_case_level_total_distance_deltas",
)


def solution_pool_focus() -> dict[str, Any]:
    return {
        "mechanism_id": SUCCESSOR55_MECHANISM_ID,
        "mechanism_family": "search_state_pool",
        "target_file": SUCCESSOR55_TARGET_FILE,
        "target_files": [SUCCESSOR55_TARGET_FILE, SUCCESSOR55_WIRING_FILE],
        "design_path": SUCCESSOR55_DESIGN_PATH,
        "status": "current_target_intent",
        "required_mechanism_binding": "target_intent_required",
        "blocked_actions": [
            "same_line_protected_race_selector_followup",
            "route_pool_exact_cover_continuation",
            "route_first_config_flip",
            "seed_selector_repeat",
            "destroy_removal_rule_repeat",
            "local_search_move_repeat",
            "contract_or_helper_only_patch",
        ],
        "required_observations": list(SUCCESSOR55_REQUIRED_OBSERVATIONS),
        "rule": SUCCESSOR55_TARGET_INTENT_RULE,
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
    }


def solution_pool_required_mechanism(
    protected_cases: tuple[str, ...],
) -> RequiredMechanism:
    return RequiredMechanism(
        mechanism_id=SUCCESSOR55_MECHANISM_ID,
        category="current_cvrp_target_intent",
        description=SUCCESSOR55_TARGET_INTENT_RULE,
        required_observations=SUCCESSOR55_REQUIRED_OBSERVATIONS,
        protected_items=protected_cases,
        hypothesis_mechanism_binding="target_intent_required",
    )


def solution_pool_evidence_requirement(
    protected_cases: tuple[str, ...],
) -> EvidenceRequirement:
    return EvidenceRequirement(
        requirement_id="successor55_bounded_elite_solution_pool_search",
        category="current_target_intent_evidence",
        description=SUCCESSOR55_TARGET_INTENT_RULE,
        mechanism_ids=(
            SUCCESSOR55_MECHANISM_ID,
            "search_state_pool",
            SUCCESSOR55_TARGET_FILE,
            SUCCESSOR55_WIRING_FILE,
        ),
        protected_items=protected_cases,
        required_fields=(
            "new solution_pool.py owns pool admission and anchor selection",
            "scheduler.py only wires pool lifecycle and current-anchor switch",
            "bounded pool size and route-diversity admission rule",
            "feasible route-count-safe candidate admission only",
            "global best is still selected by final total_distance",
            "pool admission attempted/accepted/rejected counts and reject causes",
            "anchor switch attempted/accepted/rejected counts",
            "post_downstream_or_final_total_distance_delta attribution",
            "bounded runtime or budget-stop status",
            "CMT2/CMT4 case-level total_distance deltas or split caveat",
        ),
    )


def solution_pool_related_ids() -> tuple[str, ...]:
    return (
        SUCCESSOR55_MECHANISM_ID,
        SUCCESSOR55_TARGET_FILE,
        SUCCESSOR55_WIRING_FILE,
        "search_state_pool",
    )
