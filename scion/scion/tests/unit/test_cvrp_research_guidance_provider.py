from __future__ import annotations

from scion.problems.cvrp.research_guidance import (
    CvrpResearchGuidanceProvider,
    build_cvrp_legacy_research_focus,
    build_cvrp_research_guidance_contract,
)
from scion.research_guidance import (
    GuidanceContext,
    ProblemResearchGuidanceProvider,
    launch_research_guidance_payload,
    render_research_guidance_contract,
    research_guidance_contract_to_dict,
    validate_research_guidance_contract,
)


def test_cvrp_research_guidance_contract_contains_required_blocks() -> None:
    provider: ProblemResearchGuidanceProvider = CvrpResearchGuidanceProvider()
    contract = provider.build_guidance_contract(
        GuidanceContext(
            problem_family="cvrp",
            metadata={
                "measurement_opportunity_diagnostics": {
                    "metric": "total_distance",
                    "screening_mde_at_power_80": 9.9,
                    "practical_screen_delta": 2.0,
                },
            },
        )
    )

    validate_research_guidance_contract(contract)
    rendered = render_research_guidance_contract(contract)

    assert contract.schema_version == "scion.cvrp_research_guidance_contract.v1"
    assert contract.problem_family == "cvrp"
    assert contract.proposal_visibility_only is True
    assert contract.decision_features_excluded is True
    assert not any(
        mechanism.hypothesis_mechanism_binding == "required"
        for mechanism in contract.required_mechanisms
    )
    assert [
        mechanism.mechanism_id
        for mechanism in contract.required_mechanisms
        if mechanism.hypothesis_mechanism_binding == "target_intent_required"
    ] == []
    assert any(
        "total_distance delta by case and seed" in field
        for requirement in contract.evidence_requirements
        for field in requirement.required_fields
    )
    assert any(
        "CMT2" in item and "CMT4" in item
        for requirement in contract.evidence_requirements
        for item in (*requirement.required_fields, *requirement.protected_items)
    )
    assert any(
        "unbounded large-instance two-opt fallback" in rule.description
        for rule in contract.avoid_rules
    )
    assert any(
        "route-pressure acceptance/adaptive-weighting" in rule.description
        for rule in contract.avoid_rules
    )
    assert any(
        "zero branch cards" in requirement.description
        for requirement in contract.continuity_requirements
    )
    assert contract.measurement_summary is not None
    assert "screening MDE 9.9" in contract.measurement_summary.summary
    assert "successor_causal_path_direct_effect" in rendered.text
    assert "stagnation_adaptive_destroy_size_schedule" in rendered.text
    assert "lookahead_insertion_cost_repair" in rendered.text
    assert "cw_sweep_seed_baseline_selector" in rendered.text
    assert "short_horizon_seed_trajectory_selector" in rendered.text
    assert "policies/baseline_modules/destroy_repair.py" in rendered.text
    assert "policies/baseline_modules/scheduler.py" in rendered.text
    assert "policies/baseline_modules/local_search.py" in rendered.text
    assert "policies/baseline_modules/construction.py" in rendered.text
    assert "baseline_q" in rendered.text
    assert "q_delta" in rendered.text
    assert "large_instance_intra_route_two_opt_seed" in rendered.text
    assert "bounded_2node_cross_exchange" in rendered.text
    assert "intra_route_or_opt_reinsert" in rendered.text
    assert "angular_sector_removal" in rendered.text
    assert "bounded_local_search_variant" in rendered.text
    assert "destroy_repair_selection" in rendered.text
    assert "measured_no_positive_at_mde" in rendered.text
    assert "no-positive-at-MDE" in rendered.text
    assert "CMT2/CMT4 case protection" in rendered.text
    assert "excluded from DecisionFeatures" in rendered.text

    launch_payload = launch_research_guidance_payload(
        manifest_path="/tmp/prepared_run_manifest.v1.json",
        manifest={
            "problem_family": contract.problem_family,
            "research_guidance_contract": research_guidance_contract_to_dict(contract),
        },
    )
    assert launch_payload["required_mechanism_ids"] == []
    assert launch_payload["target_intent_required_mechanism_ids"] == []


def test_cvrp_legacy_research_focus_keeps_prepared_manifest_keys() -> None:
    measurement = {
        "metric": "total_distance",
        "screening_mde_at_power_80": 9.9,
        "practical_screen_delta": 2.0,
        "reason_codes": ["CVRP_MDE_EXCEEDS_PRACTICAL_DELTA"],
    }

    focus = build_cvrp_legacy_research_focus(
        measurement_opportunity_diagnostics=measurement
    )

    assert focus["schema_version"] == "scion.cvrp_research_focus.v1"
    assert focus["scope"] == "report_only_prepared_handoff"
    assert focus["required_mechanism_ids"] == []
    assert focus["target_intent_required_mechanism_ids"] == []
    assert focus["reviewed_mechanism_ids"] == [
        "large_instance_intra_route_two_opt_seed",
        "bounded_2node_cross_exchange",
        "intra_route_or_opt_reinsert",
        "bounded_intra_route_3opt",
        "bounded_ejection_chain_relocate",
        "bounded_route_segment_exchange",
        "bounded_cross_route_double_bridge_polish",
        "neighbor_list_vns_filter",
        "frozen_safe_neighbor_list_vns_filter",
        "route_angle_aware_2opt_star",
        "operator_pair_destroy_size_bands",
        "stagnation_adaptive_destroy_size_schedule",
        "adaptive_embedded_vns_runtime_allocation",
        "post_repair_effect_credit_weighting",
        "angular_sector_removal",
        "radial_string_removal",
        "farthest_noise_related_removal",
        "polar_sweep_destroy_repair",
        "route_fragment_recombination_repair",
        "adjacency_pair_removal_repair",
        "load_compatible_ruin_recreate",
        "load_complement_pair_removal",
        "route_pair_crossover_repair",
        "timewarp_string_removal",
        "route_pair_overlap_removal",
        "boundary_spoke_outlier_removal",
        "edge_conflict_endpoint_removal",
        "route_pair_overlap_removal_protected_followup",
        "capacity_tightness_removal",
        "edge_frequency_penalty_repair",
        "lookahead_insertion_cost_repair",
        "lookahead_insertion_cost_repair_v2",
        "savings_seed_selection_probe",
        "granular_savings_seed_portfolio",
        "exact_short_route_polish",
        "cw_sweep_seed_baseline_selector",
        "short_horizon_seed_trajectory_selector",
        "short_horizon_seed_trajectory_selector_v2",
        "seed_post_optimization_selector",
    ]
    assert focus["suppressed_mechanism_ids"] == []
    assert focus["successor_opportunity_families"] == [
        "acceptance_or_adaptive_weighting",
        "scheduler_destroy_size_policy",
        "destroy_repair_selection",
        "construction_seed_portfolio",
        "bounded_local_search_variant",
    ]
    assert "positive-at-MDE" in focus["current_question"]
    assert "short_horizon_seed_trajectory_selector" in focus["current_question"]
    assert "short-horizon seed trajectory selector" in focus["current_question"]
    assert "successor27/29 route-pair-overlap follow-ups" in focus[
        "current_question"
    ]
    assert "neighbor_list_vns_filter" in focus["current_question"]
    assert "frozen_safe_neighbor_list_vns_filter" in focus["current_question"]
    assert "capacity_tightness_removal" in focus["current_question"]
    assert "seed_post_optimization_selector" in focus["current_question"]
    assert "successor37" in focus["current_question"]
    assert "bounded_2node_cross_exchange" in focus["next_required_direction"]
    assert "intra_route_or_opt_reinsert" in focus["next_required_direction"]
    assert "bounded_intra_route_3opt" in focus["next_required_direction"]
    assert "bounded_ejection_chain_relocate" in focus["next_required_direction"]
    assert "bounded_route_segment_exchange" in focus["next_required_direction"]
    assert "Successor19 and successor20" in focus["next_required_direction"]
    assert "stagnation_adaptive_destroy_size_schedule" in (
        focus["next_required_direction"]
    )
    assert "angular_sector_removal" in focus["next_required_direction"]
    assert "radial_string_removal" in focus["next_required_direction"]
    assert "farthest_noise_related_removal" in focus["next_required_direction"]
    assert "polar_sweep_destroy_repair" in focus["next_required_direction"]
    assert "route_fragment_recombination_repair" in focus["next_required_direction"]
    assert "adjacency_pair_removal_repair" in focus["next_required_direction"]
    assert "load_compatible_ruin_recreate" in focus["next_required_direction"]
    assert "load_complement_pair_removal" in focus["next_required_direction"]
    assert "route_pair_crossover_repair" in focus["next_required_direction"]
    assert "timewarp_string_removal" in focus["next_required_direction"]
    assert "granular_savings_seed_portfolio" in focus["next_required_direction"]
    assert "seed_post_optimization_selector" in focus["next_required_direction"]
    assert "savings_seed_selection_probe" in focus["next_required_direction"]
    assert "Do not repeat unchanged granular_savings_seed_portfolio" in (
        focus["next_required_direction"]
    )
    assert "bounded_route_segment_exchange" in focus["next_required_direction"]
    assert "operator_pair_destroy_size_bands" in focus["next_required_direction"]
    assert "Successor23 repaired the observable q trajectory" in (
        focus["next_required_direction"]
    )
    assert "below MDE" in focus["next_required_direction"]
    assert "quality regression" in focus["next_required_direction"]
    assert "explicit baseline_q/adapted_q/q_delta runtime fields were missing" in (
        focus["next_required_direction"]
    )
    assert "baseline_q" in focus["next_required_direction"]
    assert "q_delta" in focus["next_required_direction"]
    assert "exact_short_route_polish" in focus["next_required_direction"]
    assert "Successor25 then clean-forked" in focus["next_required_direction"]
    assert "cw_sweep_seed_baseline_selector" in focus["next_required_direction"]
    assert "not preserved by downstream ALNS/VNS" in focus["next_required_direction"]
    assert "successor26b reran" in focus["next_required_direction"]
    assert "short_horizon_seed_trajectory_selector" in focus[
        "next_required_direction"
    ]
    assert "short_horizon_seed_trajectory_selector_v2" in focus[
        "next_required_direction"
    ]
    assert "CMT4 median -19.0" in focus["next_required_direction"]
    assert "policies/baseline_modules/destroy_repair.py" in (
        focus["next_required_direction"]
    )
    assert "`required_mechanism_ids` remains empty" in (
        focus["next_required_direction"]
    )
    assert "Successor27 then clean-forked" in focus["next_required_direction"]
    assert "route_pair_overlap_removal" in focus["next_required_direction"]
    assert "Successor29 forced" in focus["next_required_direction"]
    assert "route-pair-overlap line is parked" in focus["next_required_direction"]
    assert "neighbor_list_vns_filter" in focus["next_required_direction"]
    assert "frozen_safe_neighbor_list_vns_filter" in focus[
        "next_required_direction"
    ]
    assert "capacity_tightness_removal" in focus["next_required_direction"]
    assert "telemetry-only q-audit repair" in focus["next_required_direction"]
    assert "successor36b" in focus["next_required_direction"]
    assert "proposal-control and candidate-quality evidence" in focus[
        "next_required_direction"
    ]
    assert "materially different CVRP-owned causal path" in focus[
        "next_required_direction"
    ]
    assert "Successor18b" in focus["next_required_direction"]
    assert "distinct from cross-exchange, intra-route Or-opt reinsertion" in (
        focus["next_required_direction"]
    )
    assert focus["measurement_opportunity_diagnostics"] == measurement
    assert focus["measurement_opportunity_diagnostics"] is not measurement
    assert any(
        "current-run pair-level total_distance" in item
        for item in focus["required_evidence"]
    )
    assert any(
        "seed_post_optimization_selector" in item
        and "micro-polish" in item
        for item in focus["required_evidence"]
    )
    assert any(
        "construction-seed revisit" in item
        and "same-mechanism accepted delta" in item
        for item in focus["required_evidence"]
    )
    assert any(
        "route-merge absorption" in item for item in focus["default_avoid_directions"]
    )
    assert any("ec052599-style" in item for item in focus["default_avoid_directions"])
    assert any(
        "bounded_2node_cross_exchange" in item and "measured_no_positive_at_mde" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "intra_route_or_opt_reinsert" in item and "measured_no_positive_at_mde" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "angular_sector_removal" in item and "measured_no_positive_at_mde" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "bounded_intra_route_3opt" in item and "measured_no_positive_at_mde" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "bounded_ejection_chain_relocate" in item
        and "measured_no_positive_at_mde" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "bounded_route_segment_exchange" in item and "below-MDE" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "operator_pair_destroy_size_bands" in item and "below-MDE" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "stagnation_adaptive_destroy_size_schedule" in item
        and "successor23 repaired observable q deltas" in item
        and "below-MDE" in item
        and "quality-regression" in item
        and "baseline_q/adapted_q/q_delta" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "radial_string_removal" in item and "measured_no_positive_at_mde" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "farthest_noise_related_removal" in item
        and "measured_no_positive_at_mde" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "polar_sweep_destroy_repair" in item
        and "measured_no_positive_at_mde" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "route_fragment_recombination_repair" in item
        and "measured_no_positive_at_mde" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "adjacency_pair_removal_repair" in item
        and "measured_no_positive_at_mde" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "load_compatible_ruin_recreate" in item
        and "measured_no_positive_at_mde" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "load_complement_pair_removal" in item
        and "measured_no_positive_at_mde" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "route_pair_crossover_repair" in item
        and "measured_no_positive_at_mde" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "timewarp_string_removal" in item
        and "measured_no_positive_at_mde" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "lookahead_insertion_cost_repair" in item and "successor24" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "lookahead_insertion_cost_repair_v2" in item
        and "direct-effect-zero" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "savings_seed_selection_probe" in item
        and "measured_no_positive_at_mde" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "granular_savings_seed_portfolio" in item
        and "successor18b measured below-MDE" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "exact_short_route_polish" in item
        and "quality-regression/loss-heavy" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "cw_sweep_seed_baseline_selector" in item
        and "successor25 below-MDE evidence" in item
        and "downstream-unpreserved direct seed delta" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "short_horizon_seed_trajectory_selector" in item
        and "successor26b valid screening" in item
        and "below-MDE" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "short_horizon_seed_trajectory_selector_v2" in item
        and "CMT2/CMT4 losses" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "route_pair_overlap_removal" in item
        and "successor29 protected follow-up" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "route_pair_overlap_removal_protected_followup" in item
        and "successor29 valid negative" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "capacity_tightness_removal" in item
        and "successor35 valid active loss-heavy evidence" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "bounded_cross_route_double_bridge_polish" in item
        and "successor30 valid zero-effect" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "adaptive_embedded_vns_runtime_allocation" in item
        and "successor31 valid zero-effect" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "seed_post_optimization_selector" in item
        and "successor36b valid active no-positive-at-MDE" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "route_angle_aware_2opt_star" in item and "successor37 valid negative" in item
        for item in focus["default_avoid_directions"]
    )
    assert any(
        "edge_frequency_penalty_repair" in item
        and "direct mechanism effect zero" in item
        for item in focus["default_avoid_directions"]
    )
    assert not any(
        item.strip().lower() == "avoid bounded_local_search_variant"
        for item in focus["default_avoid_directions"]
    )

    successor_evidence = focus["reviewed_successor_evidence"]
    assert successor_evidence["source_summary"] == "cvrp_successor_summary"
    assert successor_evidence["decision_features_excluded"] is True
    mechanisms_by_id = {
        item["mechanism_id"]: item for item in successor_evidence["mechanisms"]
    }
    assert set(mechanisms_by_id) == {
        "bounded_2node_cross_exchange",
        "intra_route_or_opt_reinsert",
        "bounded_intra_route_3opt",
        "bounded_ejection_chain_relocate",
        "bounded_route_segment_exchange",
        "bounded_cross_route_double_bridge_polish",
        "neighbor_list_vns_filter",
        "frozen_safe_neighbor_list_vns_filter",
        "route_angle_aware_2opt_star",
        "operator_pair_destroy_size_bands",
        "stagnation_adaptive_destroy_size_schedule",
        "adaptive_embedded_vns_runtime_allocation",
        "post_repair_effect_credit_weighting",
        "angular_sector_removal",
        "radial_string_removal",
        "farthest_noise_related_removal",
        "polar_sweep_destroy_repair",
        "route_fragment_recombination_repair",
        "adjacency_pair_removal_repair",
        "load_compatible_ruin_recreate",
        "load_complement_pair_removal",
        "route_pair_crossover_repair",
        "timewarp_string_removal",
        "route_pair_overlap_removal",
        "boundary_spoke_outlier_removal",
        "edge_conflict_endpoint_removal",
        "route_pair_overlap_removal_protected_followup",
        "capacity_tightness_removal",
        "edge_frequency_penalty_repair",
        "lookahead_insertion_cost_repair",
        "lookahead_insertion_cost_repair_v2",
        "savings_seed_selection_probe",
        "granular_savings_seed_portfolio",
        "exact_short_route_polish",
        "cw_sweep_seed_baseline_selector",
        "short_horizon_seed_trajectory_selector",
        "short_horizon_seed_trajectory_selector_v2",
        "seed_post_optimization_selector",
        "route_angle_aware_2opt_star",
        "edge_frequency_penalty_repair",
    }
    assert "seed_post_optimization_selector" in mechanisms_by_id
    assert mechanisms_by_id["capacity_tightness_removal"][
        "mechanism_family"
    ] == "destroy_repair_selection"
    assert mechanisms_by_id["bounded_intra_route_3opt"][
        "mechanism_family"
    ] == "bounded_local_search_variant"
    assert mechanisms_by_id["bounded_ejection_chain_relocate"][
        "mechanism_family"
    ] == "bounded_local_search_variant"
    assert mechanisms_by_id["bounded_cross_route_double_bridge_polish"][
        "mechanism_family"
    ] == "bounded_local_search_variant"
    assert mechanisms_by_id["frozen_safe_neighbor_list_vns_filter"][
        "mechanism_family"
    ] == "bounded_local_search_variant"
    assert mechanisms_by_id["route_angle_aware_2opt_star"][
        "mechanism_family"
    ] == "bounded_local_search_variant"
    assert mechanisms_by_id["operator_pair_destroy_size_bands"][
        "mechanism_family"
    ] == "scheduler_destroy_size_policy"
    assert mechanisms_by_id["stagnation_adaptive_destroy_size_schedule"][
        "mechanism_family"
    ] == "scheduler_destroy_size_policy"
    assert mechanisms_by_id["adaptive_embedded_vns_runtime_allocation"][
        "mechanism_family"
    ] == "scheduler_runtime_allocation"
    assert mechanisms_by_id["farthest_noise_related_removal"][
        "mechanism_family"
    ] == "destroy_repair_selection"
    assert mechanisms_by_id["polar_sweep_destroy_repair"][
        "mechanism_family"
    ] == "destroy_repair_selection"
    assert mechanisms_by_id["route_fragment_recombination_repair"][
        "mechanism_family"
    ] == "destroy_repair_selection"
    assert mechanisms_by_id["adjacency_pair_removal_repair"][
        "mechanism_family"
    ] == "destroy_repair_selection"
    assert mechanisms_by_id["load_compatible_ruin_recreate"][
        "mechanism_family"
    ] == "destroy_repair_selection"
    assert mechanisms_by_id["load_complement_pair_removal"][
        "mechanism_family"
    ] == "destroy_repair_selection"
    assert mechanisms_by_id["route_pair_crossover_repair"][
        "mechanism_family"
    ] == "destroy_repair_selection"
    assert mechanisms_by_id["timewarp_string_removal"][
        "mechanism_family"
    ] == "destroy_repair_selection"
    assert mechanisms_by_id["route_pair_overlap_removal"][
        "mechanism_family"
    ] == "destroy_repair_selection"
    assert mechanisms_by_id["boundary_spoke_outlier_removal"][
        "mechanism_family"
    ] == "destroy_repair_selection"
    assert mechanisms_by_id["edge_conflict_endpoint_removal"][
        "mechanism_family"
    ] == "destroy_repair_selection"
    assert mechanisms_by_id["route_pair_overlap_removal_protected_followup"][
        "mechanism_family"
    ] == "destroy_repair_selection"
    assert mechanisms_by_id["edge_frequency_penalty_repair"][
        "mechanism_family"
    ] == "destroy_repair_selection"
    assert mechanisms_by_id["lookahead_insertion_cost_repair"][
        "mechanism_family"
    ] == "destroy_repair_selection"
    assert mechanisms_by_id["lookahead_insertion_cost_repair_v2"][
        "mechanism_family"
    ] == "destroy_repair_selection"
    assert mechanisms_by_id["savings_seed_selection_probe"][
        "mechanism_family"
    ] == "construction_seed_portfolio"
    assert mechanisms_by_id["granular_savings_seed_portfolio"][
        "mechanism_family"
    ] == "construction_seed_portfolio"
    assert mechanisms_by_id["exact_short_route_polish"][
        "mechanism_family"
    ] == "construction_seed_portfolio"
    assert mechanisms_by_id["cw_sweep_seed_baseline_selector"][
        "mechanism_family"
    ] == "construction_seed_portfolio"
    assert mechanisms_by_id["short_horizon_seed_trajectory_selector"][
        "mechanism_family"
    ] == "construction_seed_portfolio"
    assert mechanisms_by_id["short_horizon_seed_trajectory_selector_v2"][
        "mechanism_family"
    ] == "construction_seed_portfolio"
    no_positive_mechanisms = {
        mechanism_id: item
        for mechanism_id, item in mechanisms_by_id.items()
        if mechanism_id
        not in {
            "neighbor_list_vns_filter",
            "frozen_safe_neighbor_list_vns_filter",
            "edge_frequency_penalty_repair",
        }
    }
    assert all(
        item["checklist_status"] == "proven"
        and item["outcome_status"] == "measured_no_positive_at_mde"
        and "direct per-case objective-effect evidence" in item["next_use_rule"]
        for item in no_positive_mechanisms.values()
    )
    assert mechanisms_by_id["neighbor_list_vns_filter"]["outcome_status"] == (
        "frozen_unsafe_validation_positive"
    )
    assert mechanisms_by_id["neighbor_list_vns_filter"]["effect_summary"][
        "recommended_followup"
    ] == "frozen_safe_neighbor_list_vns_filter"
    assert mechanisms_by_id["frozen_safe_neighbor_list_vns_filter"][
        "outcome_status"
    ] == "weak_positive_below_mde"
    assert mechanisms_by_id["edge_frequency_penalty_repair"]["outcome_status"] == (
        "weak_positive_below_mde_direct_no_effect"
    )
    assert mechanisms_by_id["frozen_safe_neighbor_list_vns_filter"][
        "effect_summary"
    ]["recommended_followup"] == "capacity_tightness_removal"
    assert mechanisms_by_id["bounded_intra_route_3opt"]["effect_summary"][
        "protected_case_cmt2_median_delta"
    ] == -6.5
    assert mechanisms_by_id["farthest_noise_related_removal"]["effect_summary"][
        "protected_case_cmt2_median_delta"
    ] == -12.0
    assert mechanisms_by_id["polar_sweep_destroy_repair"]["effect_summary"][
        "protected_case_cmt2_median_delta"
    ] == -19.5
    assert mechanisms_by_id["route_fragment_recombination_repair"]["effect_summary"][
        "screening_wins"
    ] == 13
    assert mechanisms_by_id["adjacency_pair_removal_repair"]["effect_summary"][
        "screening_wins"
    ] == 15
    assert mechanisms_by_id["load_compatible_ruin_recreate"]["effect_summary"][
        "protected_case_cmt2_median_delta"
    ] == -13.0
    assert mechanisms_by_id["load_complement_pair_removal"]["effect_summary"][
        "protected_case_cmt4_median_delta"
    ] == -15.0
    assert mechanisms_by_id["route_pair_crossover_repair"]["effect_summary"][
        "protected_case_x_n110_median_delta"
    ] == -6.0
    assert mechanisms_by_id["timewarp_string_removal"]["effect_summary"][
        "research_efficiency_median_delta"
    ] == -5.25
    double_bridge_effect = mechanisms_by_id["bounded_cross_route_double_bridge_polish"][
        "effect_summary"
    ]
    assert double_bridge_effect["median_delta"] == 0.0
    assert double_bridge_effect["source_root_label"] == "successor30"
    runtime_effect = mechanisms_by_id["adaptive_embedded_vns_runtime_allocation"][
        "effect_summary"
    ]
    assert runtime_effect["median_delta"] == 0.0
    assert runtime_effect["source_root_label"] == "successor31"
    route_pair_effect = mechanisms_by_id["route_pair_overlap_removal"][
        "effect_summary"
    ]
    assert route_pair_effect["max_effect_to_mde_ratio"] == 0.253
    protected_route_pair_effect = mechanisms_by_id[
        "route_pair_overlap_removal_protected_followup"
    ]["effect_summary"]
    assert protected_route_pair_effect["row2_median_delta"] == -3.75
    assert protected_route_pair_effect["source_root_label"] == "successor29"
    lookahead_effect = mechanisms_by_id["lookahead_insertion_cost_repair"][
        "effect_summary"
    ]
    assert lookahead_effect["median_delta"] == -0.75
    assert lookahead_effect["protected_case_cmt4_median_delta"] == -5.5
    assert lookahead_effect["source_root_label"] == "successor24"
    lookahead_v2_effect = mechanisms_by_id["lookahead_insertion_cost_repair_v2"][
        "effect_summary"
    ]
    assert lookahead_v2_effect["median_delta"] == -2.0
    assert lookahead_v2_effect["direct_effect_candidate_positive"] == 0
    assert lookahead_v2_effect["source_root_label"] == "successor24"
    granular_effect = mechanisms_by_id["granular_savings_seed_portfolio"][
        "effect_summary"
    ]
    assert granular_effect["median_delta"] == 5.0
    assert granular_effect["effect_to_mde_ratio"] == 0.505051
    assert granular_effect["rows_at_or_above_mde"] == 0
    assert granular_effect["protected_case_cmt2_median_delta"] == 20.5
    assert granular_effect["source_root_label"] == "successor18b"
    exact_effect = mechanisms_by_id["exact_short_route_polish"]["effect_summary"]
    assert exact_effect["median_delta"] == -5.75
    assert exact_effect["ci_high"] == 0.5
    assert exact_effect["protected_case_cmt2_median_delta"] == -80.0
    assert exact_effect["protected_case_cmt4_median_delta"] == -33.5
    assert exact_effect["source_root_label"] == "successor18b"
    seed_baseline_effect = mechanisms_by_id["cw_sweep_seed_baseline_selector"][
        "effect_summary"
    ]
    assert seed_baseline_effect["median_delta"] == 0.0
    assert seed_baseline_effect["direct_seed_delta_positive_pairs"] == 4
    assert seed_baseline_effect["direct_seed_delta_total_pairs"] == 48
    assert seed_baseline_effect["interpretation"] == "seed_delta_not_preserved_downstream"
    assert seed_baseline_effect["source_root_label"] == "successor25"
    stagnation_effect = mechanisms_by_id["stagnation_adaptive_destroy_size_schedule"][
        "effect_summary"
    ]
    assert stagnation_effect["row1_median_delta"] == 0.0
    assert stagnation_effect["row2_median_delta"] == -0.5
    assert stagnation_effect["rows_at_or_above_mde"] == 0
    assert stagnation_effect["aligned_q_delta_iteration_count"] == 948
    assert stagnation_effect["aligned_q_delta_total_iterations"] == 1219
    assert stagnation_effect["aligned_q_delta_pair_count"] == 75
    assert stagnation_effect["explicit_q_audit_field_count"] == 0
    assert stagnation_effect["missing_q_audit_fields"] == (
        "baseline_q",
        "adapted_q",
        "q_delta",
    )
    assert stagnation_effect["q_trajectory_status"] == "observable_q_deltas_repaired"
    assert stagnation_effect["q_audit_status"] == "explicit_q_delta_telemetry_missing"
    assert stagnation_effect["parked_status"] == "quality_regression"
    assert stagnation_effect["predecessor_source_root_label"] == "successor22b"
    assert stagnation_effect["source_root_label"] == "successor23"

    large_twoopt = focus["large_instance_two_opt_constraints"]
    assert large_twoopt["schema_version"] == (
        "scion.cvrp_large_instance_two_opt_constraints.v1"
    )
    assert large_twoopt["proposal_visibility_only"] is True
    assert large_twoopt["decision_features_excluded"] is True
    assert "v04-vrp-large-instance-two-opt-seed-evidence-20260618.md" in (
        large_twoopt["seed_report"]
    )
    assert any(
        "two_opt_intra" in item and "unbounded" in item
        for item in large_twoopt["implementation_constraints"]
    )

    case_protection = focus["case_protection_requirements"]
    assert case_protection["protected_cases"] == ["CMT2", "CMT4"]
    assert any("CMT2/CMT4" in item for item in case_protection["rules"])

    resume_continuity = focus["resume_continuity_requirements"]
    assert "prepared_research_focus" in resume_continuity["fallback_sources"]
    assert any("zero branch cards" in item for item in resume_continuity["rules"])
    assert "DecisionFeatures" in focus["decision_boundary"]

    launch_payload = launch_research_guidance_payload(
        manifest_path="/tmp/prepared_run_manifest.v1.json",
        manifest={
            "problem_family": "cvrp",
            "research_guidance_contract": research_guidance_contract_to_dict(
                build_cvrp_research_guidance_contract(
                    measurement_opportunity_diagnostics=measurement
                )
            ),
            "research_focus": focus,
        },
    )
    assert launch_payload["reviewed_mechanism_ids"] == [
        "large_instance_intra_route_two_opt_seed",
        "bounded_2node_cross_exchange",
        "intra_route_or_opt_reinsert",
        "bounded_intra_route_3opt",
        "bounded_ejection_chain_relocate",
        "bounded_route_segment_exchange",
        "bounded_cross_route_double_bridge_polish",
        "neighbor_list_vns_filter",
        "frozen_safe_neighbor_list_vns_filter",
        "route_angle_aware_2opt_star",
        "operator_pair_destroy_size_bands",
        "stagnation_adaptive_destroy_size_schedule",
        "adaptive_embedded_vns_runtime_allocation",
        "post_repair_effect_credit_weighting",
        "angular_sector_removal",
        "radial_string_removal",
        "farthest_noise_related_removal",
        "polar_sweep_destroy_repair",
        "route_fragment_recombination_repair",
        "adjacency_pair_removal_repair",
        "load_compatible_ruin_recreate",
        "load_complement_pair_removal",
        "route_pair_crossover_repair",
        "timewarp_string_removal",
        "route_pair_overlap_removal",
        "boundary_spoke_outlier_removal",
        "edge_conflict_endpoint_removal",
        "route_pair_overlap_removal_protected_followup",
        "capacity_tightness_removal",
        "edge_frequency_penalty_repair",
        "lookahead_insertion_cost_repair",
        "lookahead_insertion_cost_repair_v2",
        "savings_seed_selection_probe",
        "granular_savings_seed_portfolio",
        "exact_short_route_polish",
        "cw_sweep_seed_baseline_selector",
        "short_horizon_seed_trajectory_selector",
        "short_horizon_seed_trajectory_selector_v2",
        "seed_post_optimization_selector",
    ]
    assert launch_payload["required_mechanism_ids"] == []
    assert launch_payload["target_intent_required_mechanism_ids"] == []
    assert launch_payload["suppressed_mechanism_ids"] == []
    assert launch_payload["successor_opportunity_families"] == [
        "acceptance_or_adaptive_weighting",
        "scheduler_destroy_size_policy",
        "destroy_repair_selection",
        "construction_seed_portfolio",
        "bounded_local_search_variant",
    ]
    assert launch_payload["legacy_research_focus_schema_version"] == (
        "scion.cvrp_research_focus.v1"
    )


def test_cvrp_contract_rejects_non_cvrp_context() -> None:
    try:
        build_cvrp_research_guidance_contract(
            GuidanceContext(problem_family="warehouse")
        )
    except ValueError as exc:
        assert "cvrp" in str(exc)
    else:
        raise AssertionError("CVRP contract accepted a non-CVRP context")


def test_cvrp_contract_function_accepts_explicit_measurement() -> None:
    contract = build_cvrp_research_guidance_contract(
        measurement_opportunity_diagnostics={
            "metric": "total_distance",
            "screening_mde_at_power_80": 9.9,
            "practical_screen_delta": 2.0,
        }
    )

    assert contract.measurement_summary is not None
    assert contract.measurement_summary.metric_names == ("total_distance",)
    assert "not promotion" in " ".join(contract.measurement_summary.limitations)
