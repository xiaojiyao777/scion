"""CVRP-owned successor evidence catalog for prepared guidance."""

from __future__ import annotations

SUCCESSOR_OPPORTUNITY_FAMILIES = (
    "acceptance_or_adaptive_weighting",
    "scheduler_destroy_size_policy",
    "destroy_repair_selection",
    "construction_seed_portfolio",
    "bounded_local_search_variant",
)
REVIEWED_SUCCESSOR_OUTCOME_STATUS = "measured_no_positive_at_mde"
SUPPRESSED_SUCCESSOR_MECHANISMS = (
    {
        "mechanism_id": "seed_post_optimization_selector",
        "mechanism_family": "construction_seed_portfolio",
        "reason": (
            "successor16 and successor17 both reached formal screening but "
            "reported missing activation/not_evaluated telemetry for the "
            "declared primary mechanism"
        ),
    },
)
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
        "mechanism_id": "bounded_route_segment_exchange",
        "mechanism_family": "bounded_local_search_variant",
        "path_label": "bounded route-segment exchange path",
        "causal_path_label": "bounded route-segment local search",
        "effect_summary": {
            "median_delta": 0.0,
            "ci_low": 0.0,
            "ci_high": 0.0,
            "rows_at_or_above_mde": 0,
            "positive_rows": 0,
            "max_median_delta": 0.0,
            "interpretation": "all_available_ci_high_below_mde",
            "source_root_label": "successor20",
        },
    },
    {
        "mechanism_id": "bounded_cross_route_double_bridge_polish",
        "mechanism_family": "bounded_local_search_variant",
        "path_label": "bounded cross-route double-bridge polish path",
        "causal_path_label": "bounded cross-route local-search polish",
        "effect_summary": {
            "median_delta": 0.0,
            "ci_low": 0.0,
            "ci_high": 0.0,
            "rows_at_or_above_mde": 0,
            "positive_rows": 0,
            "max_median_delta": 0.0,
            "max_effect_to_mde_ratio": 0.0,
            "interpretation": "valid_zero_effect_solver_negative",
            "source_root_label": "successor30",
        },
    },
    {
        "mechanism_id": "operator_pair_destroy_size_bands",
        "mechanism_family": "scheduler_destroy_size_policy",
        "path_label": "operator-pair destroy-size band scheduler path",
        "causal_path_label": "scheduler destroy-size policy",
        "effect_summary": {
            "median_delta": -5.5,
            "ci_low": -8.0,
            "ci_high": 2.75,
            "rows_at_or_above_mde": 0,
            "max_median_delta": 0.25,
            "max_effect_to_mde_ratio": 0.025253,
            "screening_wins": 17,
            "screening_losses": 29,
            "screening_ties": 2,
            "protected_case_cmt2_median_delta": 6.5,
            "protected_case_cmt4_median_delta": -2.0,
            "source_root_label": "successor21",
        },
    },
    {
        "mechanism_id": "stagnation_adaptive_destroy_size_schedule",
        "mechanism_family": "scheduler_destroy_size_policy",
        "path_label": "stagnation-adaptive destroy-size schedule path",
        "causal_path_label": "scheduler destroy-size q-delta policy",
        "effect_summary": {
            "median_delta": -0.5,
            "ci_low": -3.0,
            "ci_high": 3.25,
            "row1_median_delta": 0.0,
            "row1_ci_low": -2.0,
            "row1_ci_high": 3.5,
            "row2_median_delta": -0.5,
            "row2_ci_low": -3.0,
            "row2_ci_high": 3.25,
            "rows_at_or_above_mde": 0,
            "positive_rows": 0,
            "max_median_delta": 0.0,
            "max_effect_to_mde_ratio": 0.0,
            "interpretation": "activation_repaired_but_below_mde",
            "parked_status": "quality_regression",
            "screening_case_wins": 7,
            "screening_case_losses": 5,
            "screening_case_ties": 8,
            "screening_pair_wins": 33,
            "screening_pair_losses": 30,
            "screening_pair_ties": 17,
            "aligned_q_delta_iteration_count": 948,
            "aligned_q_delta_total_iterations": 1219,
            "aligned_q_delta_pair_count": 75,
            "aligned_q_delta_total_pairs": 80,
            "explicit_q_audit_field_count": 0,
            "missing_q_audit_fields": ("baseline_q", "adapted_q", "q_delta"),
            "q_trajectory_status": "observable_q_deltas_repaired",
            "q_audit_status": "explicit_q_delta_telemetry_missing",
            "predecessor_source_root_label": "successor22b",
            "predecessor_q_trajectory_status": "inactive_q_trajectory_noop",
            "source_root_label": "successor23",
        },
    },
    {
        "mechanism_id": "adaptive_embedded_vns_runtime_allocation",
        "mechanism_family": "scheduler_runtime_allocation",
        "path_label": "adaptive embedded-VNS runtime allocation path",
        "causal_path_label": "scheduler runtime-allocation policy",
        "effect_summary": {
            "median_delta": 0.0,
            "ci_low": 0.0,
            "ci_high": 0.0,
            "rows_at_or_above_mde": 0,
            "positive_rows": 0,
            "max_median_delta": 0.0,
            "max_effect_to_mde_ratio": 0.0,
            "weighted_runtime_movement_observed": True,
            "interpretation": "valid_zero_effect_solver_negative",
            "source_root_label": "successor31",
        },
    },
    {
        "mechanism_id": "post_repair_effect_credit_weighting",
        "mechanism_family": "acceptance_or_adaptive_weighting",
        "path_label": "post-repair effect credit weighting path",
        "causal_path_label": "post-repair operator-credit weighting",
        "effect_summary": {
            "median_delta": 0.0,
            "ci_low": 0.0,
            "ci_high": 0.0,
            "rows_at_or_above_mde": 0,
            "positive_rows": 0,
            "max_median_delta": 0.0,
            "max_effect_to_mde_ratio": 0.0,
            "internal_effect_observed": True,
            "objective_effect_status": "zero_objective_effect",
            "interpretation": "valid_zero_effect_solver_negative",
            "source_root_label": "successor32",
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
        "mechanism_id": "route_pair_overlap_removal",
        "mechanism_family": "destroy_repair_selection",
        "path_label": "route-pair overlap removal path",
        "causal_path_label": "destroy/repair route-pair overlap removal",
        "effect_summary": {
            "median_delta": 2.5,
            "ci_low": -7.75,
            "ci_high": 7.0,
            "rows_at_or_above_mde": 0,
            "max_effect_to_mde_ratio": 0.253,
            "protected_case_cmt2_median_delta": -3.0,
            "protected_case_cmt4_median_delta": -16.0,
            "protected_case_p_n101_median_delta": -14.0,
            "protected_case_p_n65_median_delta": -4.5,
            "protected_case_p_n76_median_delta": -7.5,
            "interpretation": "weak_positive_below_mde_parked_after_followup",
            "source_root_label": "successor27",
            "parked_after_source_root_label": "successor29",
        },
    },
    {
        "mechanism_id": "boundary_spoke_outlier_removal",
        "mechanism_family": "destroy_repair_selection",
        "path_label": "boundary-spoke outlier removal path",
        "causal_path_label": "destroy/repair boundary-spoke removal",
        "effect_summary": {
            "median_delta": -1.5,
            "ci_high": 0.0,
            "rows_at_or_above_mde": 0,
            "positive_rows": 0,
            "interpretation": "negative_non_route_pair_overlap_clean_fork",
            "source_root_label": "successor28",
        },
    },
    {
        "mechanism_id": "edge_conflict_endpoint_removal",
        "mechanism_family": "destroy_repair_selection",
        "path_label": "edge-conflict endpoint removal path",
        "causal_path_label": "destroy/repair edge-conflict endpoint removal",
        "effect_summary": {
            "median_delta": -2.5,
            "ci_high": 0.0,
            "rows_at_or_above_mde": 0,
            "positive_rows": 0,
            "interpretation": "negative_non_route_pair_overlap_clean_fork",
            "source_root_label": "successor28",
        },
    },
    {
        "mechanism_id": "route_pair_overlap_removal_protected_followup",
        "mechanism_family": "destroy_repair_selection",
        "path_label": "protected route-pair overlap removal follow-up path",
        "causal_path_label": "destroy/repair protected route-pair overlap removal",
        "effect_summary": {
            "row1_median_delta": -1.75,
            "row2_median_delta": -3.75,
            "max_median_delta": -1.75,
            "rows_at_or_above_mde": 0,
            "positive_rows": 0,
            "protected_case_cmt4_status": "negative",
            "protected_case_p_family_status": "negative",
            "interpretation": "protected_followup_negative_park_route_pair_overlap_line",
            "source_root_label": "successor29",
        },
    },
    {
        "mechanism_id": "lookahead_insertion_cost_repair",
        "mechanism_family": "destroy_repair_selection",
        "path_label": "lookahead insertion-cost repair path",
        "causal_path_label": "destroy/repair insertion-cost lookahead",
        "effect_summary": {
            "median_delta": -0.75,
            "ci_low": -5.5,
            "ci_high": 0.5,
            "effect_to_mde_ratio": -0.075758,
            "rows_at_or_above_mde": 0,
            "positive_rows": 0,
            "screening_pairs": 32,
            "protected_case_cmt2_median_delta": 8.5,
            "protected_case_cmt4_median_delta": -5.5,
            "protected_case_x_n110_median_delta": -6.0,
            "telemetry_status": "activation_observed_runtime_observed",
            "source_root_label": "successor24",
        },
    },
    {
        "mechanism_id": "lookahead_insertion_cost_repair_v2",
        "mechanism_family": "destroy_repair_selection",
        "path_label": "lookahead insertion-cost repair v2 path",
        "causal_path_label": "destroy/repair paired insertion-cost lookahead",
        "effect_summary": {
            "median_delta": -2.0,
            "ci_low": -12.0,
            "ci_high": 1.5,
            "effect_to_mde_ratio": -0.20202,
            "rows_at_or_above_mde": 0,
            "positive_rows": 0,
            "screening_pairs": 32,
            "protected_case_cmt2_median_delta": -4.0,
            "protected_case_cmt4_median_delta": -15.5,
            "protected_case_p_n65_median_delta": -12.0,
            "protected_case_x_n110_median_delta": -6.0,
            "telemetry_status": "activation_observed_runtime_observed_effect_zero",
            "direct_effect_candidate_present": 60,
            "direct_effect_candidate_positive": 0,
            "direct_effect_candidate_zero": 60,
            "source_root_label": "successor24",
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
    {
        "mechanism_id": "granular_savings_seed_portfolio",
        "mechanism_family": "construction_seed_portfolio",
        "path_label": "granular savings seed-portfolio construction path",
        "causal_path_label": "construction granular savings seed-portfolio",
        "effect_summary": {
            "median_delta": 5.0,
            "ci_low": -2.75,
            "ci_high": 12.75,
            "effect_to_mde_ratio": 0.505051,
            "rows_at_or_above_mde": 0,
            "screening_wins": 32,
            "screening_losses": 14,
            "screening_ties": 2,
            "protected_case_cmt2_median_delta": 20.5,
            "protected_case_cmt4_median_delta": 6.0,
            "source_root_label": "successor18b",
        },
    },
    {
        "mechanism_id": "exact_short_route_polish",
        "mechanism_family": "construction_seed_portfolio",
        "path_label": "exact short-route polish construction follow-up",
        "causal_path_label": "construction exact short-route polish",
        "effect_summary": {
            "median_delta": -5.75,
            "ci_low": -20.25,
            "ci_high": 0.5,
            "effect_to_mde_ratio": -0.580808,
            "rows_at_or_above_mde": 0,
            "screening_wins": 8,
            "screening_losses": 20,
            "screening_ties": 4,
            "protected_case_cmt2_median_delta": -80.0,
            "protected_case_cmt4_median_delta": -33.5,
            "source_root_label": "successor18b",
        },
    },
    {
        "mechanism_id": "cw_sweep_seed_baseline_selector",
        "mechanism_family": "construction_seed_portfolio",
        "path_label": "CW/sweep seed-baseline selector path",
        "causal_path_label": "construction seed-baseline selection",
        "effect_summary": {
            "median_delta": 0.0,
            "ci_low": 0.0,
            "ci_high": 0.0,
            "rows_at_or_above_mde": 0,
            "positive_rows": 0,
            "row1_median_delta": 0.0,
            "row2_median_delta": 0.0,
            "direct_seed_delta_positive_pairs": 4,
            "direct_seed_delta_total_pairs": 48,
            "direct_seed_delta_case": "B-n67-k10",
            "direct_seed_delta_best": 956.0,
            "downstream_case_b_n67_median_delta": -2.5,
            "interpretation": "seed_delta_not_preserved_downstream",
            "source_root_label": "successor25",
        },
    },
    {
        "mechanism_id": "short_horizon_seed_trajectory_selector",
        "mechanism_family": "construction_seed_portfolio",
        "path_label": "short-horizon seed trajectory selector path",
        "causal_path_label": "construction seed trajectory selection",
        "effect_summary": {
            "median_delta": 0.0,
            "ci_low": 0.0,
            "ci_high": 0.0,
            "rows_at_or_above_mde": 0,
            "positive_rows": 0,
            "win_rate": 0.0,
            "screening_pairs": 32,
            "case_median_win_count": 1,
            "case_median_loss_count": 2,
            "case_median_tie_count": 5,
            "protected_case_cmt2_median_delta": 0.0,
            "protected_case_cmt4_median_delta": 0.0,
            "interpretation": "all_available_ci_high_below_mde",
            "source_root_label": "successor26b",
        },
    },
    {
        "mechanism_id": "short_horizon_seed_trajectory_selector_v2",
        "mechanism_family": "construction_seed_portfolio",
        "path_label": "short-horizon seed trajectory selector v2 path",
        "causal_path_label": "construction seed trajectory selection",
        "effect_summary": {
            "median_delta": -5.0,
            "ci_low": -8.0,
            "ci_high": 9.0,
            "effect_to_mde_ratio": -0.505051,
            "rows_at_or_above_mde": 0,
            "positive_rows": 0,
            "win_rate": 0.25,
            "screening_pairs": 32,
            "case_median_win_count": 2,
            "case_median_loss_count": 5,
            "case_median_tie_count": 1,
            "protected_case_cmt2_median_delta": -8.0,
            "protected_case_cmt4_median_delta": -19.0,
            "protected_case_x_n110_median_delta": 9.0,
            "interpretation": "all_available_ci_high_below_mde",
            "source_root_label": "successor26b",
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
        "unchanged bounded_route_segment_exchange bounded-local-search "
        "successor after successor20 measured active zero-effect "
        "below-MDE evidence"
    ),
    (
        "unchanged operator_pair_destroy_size_bands scheduler destroy-size "
        "policy after successor21 measured active below-MDE and loss-heavy "
        "follow-up evidence"
    ),
    (
        "unchanged stagnation_adaptive_destroy_size_schedule scheduler "
        "destroy-size policy after successor23 repaired observable q deltas "
        "but stayed below-MDE, parked as quality-regression, and missed "
        "explicit baseline_q/adapted_q/q_delta runtime fields"
    ),
    (
        "unchanged post_repair_effect_credit_weighting acceptance/adaptive "
        "weighting after successor32 measured internal operator-credit "
        "movement but zero objective effect"
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
        "unchanged lookahead_insertion_cost_repair destroy/repair repair-scoring "
        "successor after successor24 activation-observed below-MDE evidence"
    ),
    (
        "unchanged lookahead_insertion_cost_repair_v2 destroy/repair repair-scoring "
        "successor after successor24 direct-effect-zero and below-MDE evidence"
    ),
    (
        "unchanged savings_seed_selection_probe construction seed successor "
        "after cvrp_successor_summary measured_no_positive_at_mde review"
    ),
    (
        "unchanged granular_savings_seed_portfolio construction seed successor "
        "after successor18b measured below-MDE and parked its branch"
    ),
    (
        "unchanged exact_short_route_polish construction follow-up after "
        "successor18b quality-regression/loss-heavy CMT2/CMT4 evidence"
    ),
    (
        "unchanged cw_sweep_seed_baseline_selector construction seed-baseline "
        "successor after successor25 below-MDE evidence and downstream-"
        "unpreserved direct seed delta"
    ),
    (
        "unchanged short_horizon_seed_trajectory_selector construction seed "
        "trajectory selector after successor26b valid screening stayed "
        "below-MDE with median delta 0.0 and no positive-at-MDE row"
    ),
    (
        "unchanged short_horizon_seed_trajectory_selector_v2 construction seed "
        "trajectory selector after successor26b valid screening stayed "
        "below-MDE with median delta -5.0 and CMT2/CMT4 losses"
    ),
    (
        "unchanged route_pair_overlap_removal destroy/repair follow-up after "
        "successor29 protected follow-up stayed negative and parked the "
        "route-pair-overlap line for v0.4"
    ),
    (
        "unchanged boundary_spoke_outlier_removal destroy/repair clean fork "
        "after successor28 negative below-MDE evidence"
    ),
    (
        "unchanged edge_conflict_endpoint_removal destroy/repair clean fork "
        "after successor28 negative below-MDE evidence"
    ),
    (
        "unchanged route_pair_overlap_removal_protected_followup after "
        "successor29 valid negative below-MDE evidence"
    ),
    (
        "unchanged bounded_cross_route_double_bridge_polish bounded-local-search "
        "follow-up after successor30 valid zero-effect below-MDE evidence"
    ),
    (
        "unchanged adaptive_embedded_vns_runtime_allocation scheduler runtime "
        "allocation after successor31 valid zero-effect below-MDE evidence"
    ),
    (
        "unchanged seed_post_optimization_selector construction post-optimization "
        "successor after successor16 and successor17 missing-activation/"
        "inactive screening; repair activation wiring only with explicit "
        "mechanism evidence"
    ),
    (
        "ec052599-style weak_positive continuation when declared primary "
        "mechanism telemetry is missing or not_evaluated/not_triggered"
    ),
)
