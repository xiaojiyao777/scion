"""CVRP mechanism-family aliases used by problem-owned evidence reviews."""

from __future__ import annotations

CONSTRUCTION_SEED_PORTFOLIO_ALIASES = (
    "construction_seed_portfolio",
    "construction_seed",
    "seed_portfolio",
    "initial_solution",
    "rotated_sweep_seed_tournament",
    "sweep_seed_tournament",
    "rotated_sweep_seed",
    "sweep_seed",
    "sweep_construction",
    "savings_seed_selection_probe",
    "savings_seed_selection",
    "same_route_count_savings_variant_selection",
    "savings_variant_selection",
    "savings_seed_portfolio",
    "savings_seed",
    "savings_construction",
    "clarke_wright_savings",
    "clarke_wright",
    "cw_savings",
    "construction",
)

BOUNDED_LOCAL_SEARCH_VARIANT_ALIASES = (
    "bounded_local_search_variant",
    "bounded_local_search",
    "local_search",
    "deadline_aware_local_search",
    "bounded_2node_cross_exchange",
    "two_node_cross_exchange",
    "2node_cross_exchange",
    "cross_exchange",
    "intra_route_or_opt_reinsert",
    "or_opt_reinsert",
    "same_route_or_opt_reinsertion",
    "intra_route_block_reinsert",
    "bounded_same_route_or_opt_reinsertion",
    "alns_vns_intra_route_block_reinsert",
    "bounded_intra_route_3opt",
    "bounded_intra_route_three_opt",
    "intra_route_3opt",
    "intra_route_three_opt",
    "bounded_ejection_chain_relocate",
    "ejection_chain_relocate",
    "two_step_ejection_chain_relocation",
    "ejection_chain",
    "3opt",
    "three_opt",
    "segment_swap",
    "route_pair_exchange",
    "two_opt_intra_bounded",
)

DESTROY_REPAIR_SELECTION_ALIASES = (
    "destroy_repair_selection",
    "destroy_repair",
    "angular_sector_removal",
    "angular_sector",
    "radial_string_removal",
    "farthest_noise_related_removal",
    "removal",
    "repair",
    "regret_insertion",
    "insertion",
    "shaw_removal",
    "worst_removal",
)

CVRP_SUCCESSOR_FAMILY_ALIASES = {
    "construction_seed_portfolio": CONSTRUCTION_SEED_PORTFOLIO_ALIASES,
    "bounded_local_search_variant": BOUNDED_LOCAL_SEARCH_VARIANT_ALIASES,
    "destroy_repair_selection": DESTROY_REPAIR_SELECTION_ALIASES,
}
