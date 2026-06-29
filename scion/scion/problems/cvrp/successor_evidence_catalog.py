"""CVRP-owned successor evidence catalog for prepared guidance."""

from __future__ import annotations

SUCCESSOR_OPPORTUNITY_FAMILIES = (
    "destroy_repair_selection",
    "construction_seed_portfolio",
    "bounded_local_search_variant",
)
REVIEWED_SUCCESSOR_OUTCOME_STATUS = "measured_no_positive_at_mde"
REVIEWED_SUCCESSOR_MECHANISMS = (
    {
        "mechanism_id": "bounded_2node_cross_exchange",
        "mechanism_family": "bounded_local_search_variant",
        "path_label": "cross-exchange successor path",
        "causal_path_label": "bounded-local-search",
    },
    {
        "mechanism_id": "intra_route_or_opt_reinsert",
        "mechanism_family": "bounded_local_search_variant",
        "path_label": "intra-route Or-opt reinsertion path",
        "causal_path_label": "bounded-local-search",
    },
    {
        "mechanism_id": "bounded_intra_route_3opt",
        "mechanism_family": "bounded_local_search_variant",
        "path_label": "bounded intra-route 3-opt path",
        "causal_path_label": "bounded-local-search",
        "effect_summary": {
            "median_delta": -0.75,
            "ci_high": 2.25,
            "rows_at_or_above_mde": 0,
            "protected_case_cmt2_median_delta": -6.5,
            "source_root_label": "successor6",
        },
    },
    {
        "mechanism_id": "bounded_ejection_chain_relocate",
        "mechanism_family": "bounded_local_search_variant",
        "path_label": "bounded ejection-chain relocation path",
        "causal_path_label": "bounded-local-search",
        "effect_summary": {
            "median_delta": 3.75,
            "ci_low": -6.25,
            "ci_high": 11.75,
            "rows_at_or_above_mde": 0,
            "protected_case_cmt2_median_delta": -14.0,
            "protected_case_cmt4_median_delta": -5.0,
            "source_root_label": "successor9",
        },
    },
    {
        "mechanism_id": "angular_sector_removal",
        "mechanism_family": "destroy_repair_selection",
        "path_label": "angular-sector removal path",
        "causal_path_label": "destroy/repair selection",
    },
    {
        "mechanism_id": "radial_string_removal",
        "mechanism_family": "destroy_repair_selection",
        "path_label": "radial-string removal path",
        "causal_path_label": "destroy/repair selection",
        "effect_summary": {
            "outcome_status": REVIEWED_SUCCESSOR_OUTCOME_STATUS,
            "rows_at_or_above_mde": 0,
            "source_root_label": "successor5",
        },
    },
    {
        "mechanism_id": "farthest_noise_related_removal",
        "mechanism_family": "destroy_repair_selection",
        "path_label": "farthest-noise related removal path",
        "causal_path_label": "destroy/repair selection",
        "effect_summary": {
            "median_delta": -3.0,
            "report_raw_median_delta": -1.0,
            "ci_high": 0.0,
            "rows_at_or_above_mde": 0,
            "protected_case_cmt2_median_delta": -12.0,
            "source_root_label": "successor6",
        },
    },
    {
        "mechanism_id": "polar_sweep_destroy_repair",
        "mechanism_family": "destroy_repair_selection",
        "path_label": "polar-sweep destroy/repair path",
        "causal_path_label": "destroy/repair selection",
        "effect_summary": {
            "median_delta": 0.0,
            "rows_at_or_above_mde": 0,
            "screening_wins": 11,
            "screening_losses": 15,
            "screening_ties": 6,
            "protected_case_cmt2_median_delta": -19.5,
            "protected_case_cmt4_median_delta": -12.0,
            "source_root_label": "successor10",
        },
    },
    {
        "mechanism_id": "route_fragment_recombination_repair",
        "mechanism_family": "destroy_repair_selection",
        "path_label": "route-fragment recombination repair path",
        "causal_path_label": "destroy/repair selection",
        "effect_summary": {
            "median_delta": 0.0,
            "rows_at_or_above_mde": 0,
            "screening_wins": 13,
            "screening_losses": 13,
            "screening_ties": 6,
            "protected_case_cmt2_median_delta": -4.5,
            "protected_case_cmt4_median_delta": 3.0,
            "source_root_label": "successor10",
        },
    },
    {
        "mechanism_id": "adjacency_pair_removal_repair",
        "mechanism_family": "destroy_repair_selection",
        "path_label": "adjacency-pair removal repair path",
        "causal_path_label": "destroy/repair selection",
        "effect_summary": {
            "median_delta": 0.0,
            "research_efficiency_median_delta": -0.75,
            "rows_at_or_above_mde": 0,
            "screening_wins": 15,
            "screening_losses": 11,
            "screening_ties": 6,
            "protected_case_cmt2_median_delta": -7.5,
            "protected_case_cmt4_median_delta": -6.0,
            "source_root_label": "successor11",
        },
    },
    {
        "mechanism_id": "load_compatible_ruin_recreate",
        "mechanism_family": "destroy_repair_selection",
        "path_label": "load-compatible ruin/recreate path",
        "causal_path_label": "destroy/repair selection",
        "effect_summary": {
            "median_delta": 0.5,
            "research_efficiency_median_delta": 1.5,
            "rows_at_or_above_mde": 0,
            "screening_wins": 16,
            "screening_losses": 11,
            "screening_ties": 5,
            "protected_case_cmt2_median_delta": -13.0,
            "protected_case_cmt4_median_delta": -10.0,
            "source_root_label": "successor11",
        },
    },
    {
        "mechanism_id": "load_complement_pair_removal",
        "mechanism_family": "destroy_repair_selection",
        "path_label": "load-complement pair removal path",
        "causal_path_label": "destroy/repair load-complement pair selection",
        "effect_summary": {
            "median_delta": -4.75,
            "ci_low": -8.75,
            "ci_high": 0.0,
            "rows_at_or_above_mde": 0,
            "screening_wins": 10,
            "screening_losses": 17,
            "screening_ties": 5,
            "case_win_count": 1,
            "case_loss_count": 5,
            "case_tie_count": 2,
            "protected_case_cmt2_median_delta": -0.5,
            "protected_case_cmt4_median_delta": -15.0,
            "protected_case_x_n110_median_delta": -6.0,
            "source_root_label": "successor15",
        },
    },
    {
        "mechanism_id": "route_pair_crossover_repair",
        "mechanism_family": "destroy_repair_selection",
        "path_label": "route-pair crossover repair path",
        "causal_path_label": "destroy/repair route-pair crossover",
        "effect_summary": {
            "median_delta": -0.5,
            "research_efficiency_median_delta": -3.5,
            "ci_high": 6.5,
            "rows_at_or_above_mde": 0,
            "screening_wins": 19,
            "screening_losses": 24,
            "screening_ties": 5,
            "protected_case_cmt2_median_delta": -7.5,
            "protected_case_cmt4_median_delta": -7.0,
            "protected_case_x_n110_median_delta": -6.0,
            "source_root_label": "successor14",
        },
    },
    {
        "mechanism_id": "timewarp_string_removal",
        "mechanism_family": "destroy_repair_selection",
        "path_label": "timewarp string-removal path",
        "causal_path_label": "destroy/repair string-removal",
        "effect_summary": {
            "median_delta": 0.0,
            "research_efficiency_median_delta": -5.25,
            "ci_high": 0.0,
            "rows_at_or_above_mde": 0,
            "screening_wins": 9,
            "screening_losses": 15,
            "screening_ties": 8,
            "protected_case_cmt2_status": "negative",
            "protected_case_cmt4_status": "negative",
            "protected_case_x_n110_status": "negative",
            "source_root_label": "successor14",
        },
    },
    {
        "mechanism_id": "savings_seed_selection_probe",
        "mechanism_family": "construction_seed_portfolio",
        "path_label": "savings seed-selection construction path",
        "causal_path_label": "construction seed-selection",
        "effect_summary": {
            "median_delta": 0.0,
            "ci_high": 0.0,
            "rows_at_or_above_mde": 0,
            "source_root_label": "successor8",
        },
    },
)

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
        "unchanged angular_sector_removal destroy/repair successor after "
        "cvrp_successor_summary measured_no_positive_at_mde review"
    ),
    (
        "unchanged bounded_intra_route_3opt bounded-local-search successor "
        "after cvrp_successor_summary measured_no_positive_at_mde review"
    ),
    (
        "unchanged bounded_ejection_chain_relocate bounded-local-search "
        "successor after cvrp_successor_summary measured_no_positive_at_mde "
        "review"
    ),
    (
        "unchanged radial_string_removal destroy/repair successor after "
        "cvrp_successor_summary measured_no_positive_at_mde review"
    ),
    (
        "unchanged farthest_noise_related_removal destroy/repair successor "
        "after cvrp_successor_summary measured_no_positive_at_mde review"
    ),
    (
        "unchanged polar_sweep_destroy_repair destroy/repair successor after "
        "cvrp_successor_summary measured_no_positive_at_mde review"
    ),
    (
        "unchanged route_fragment_recombination_repair destroy/repair "
        "successor after cvrp_successor_summary measured_no_positive_at_mde "
        "review"
    ),
    (
        "unchanged adjacency_pair_removal_repair destroy/repair successor after "
        "cvrp_successor_summary measured_no_positive_at_mde review"
    ),
    (
        "unchanged load_compatible_ruin_recreate destroy/repair successor after "
        "cvrp_successor_summary measured_no_positive_at_mde review"
    ),
    (
        "unchanged load_complement_pair_removal destroy/repair successor after "
        "cvrp_successor_summary measured_no_positive_at_mde review"
    ),
    (
        "unchanged route_pair_crossover_repair destroy/repair successor after "
        "cvrp_successor_summary measured_no_positive_at_mde review"
    ),
    (
        "unchanged timewarp_string_removal destroy/repair successor after "
        "cvrp_successor_summary measured_no_positive_at_mde review"
    ),
    (
        "unchanged savings_seed_selection_probe construction seed successor "
        "after cvrp_successor_summary measured_no_positive_at_mde review"
    ),
    (
        "unchanged seed_post_optimization_selector construction post-optimization "
        "successor after successor16 missing-activation/inactive screening; "
        "repair activation wiring only with explicit mechanism evidence"
    ),
    (
        "ec052599-style weak_positive continuation when declared primary "
        "mechanism telemetry is missing or not_evaluated/not_triggered"
    ),
)
