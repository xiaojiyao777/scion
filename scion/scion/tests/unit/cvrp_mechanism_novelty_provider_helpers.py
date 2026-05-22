from __future__ import annotations

from scion.core.models import HypothesisProposal, MechanismChange
from scion.problems.cvrp.mechanism_novelty import CvrpMechanismNoveltyProvider
from scion.problems.cvrp.mechanism_novelty.provider import (
    CvrpMechanismNoveltyProvider as DirectCvrpMechanismNoveltyProvider,
)
from scion.proposal.negative_facts import render_negative_fact_block
from scion.proposal.tools import ProposalObservation


def _hypothesis(text: str) -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=text,
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        target_weakness=text,
        expected_effect="Improve solver behavior.",
    )


def _active_capability_snapshot() -> dict[str, object]:
    return {
        "provenance": {
            "source": "unit_test_snapshot",
            "branch_id": "branch-test",
        },
        "source_digest": {"snapshot_digest": "snapshot-test-digest"},
        "active_algorithm_facts": {
            "packet_id": "cvrp_active_algorithm_facts_v1",
            "snapshot_digest": "snapshot-test-digest",
            "fact_packet_digest": "fact-packet-test-digest",
            "facts": [
                _fact(
                    "cvrp.construction.diverse_feasible_seed",
                    "Initial construction uses diverse feasible seeding.",
                    [
                        "_sweep_construction",
                        "_clarke_wright_savings",
                        "_capacity_balanced_construction",
                        "_nearest_neighbor fallback",
                    ],
                ),
                _fact(
                    "cvrp.acceptance.adaptive_operator_weights",
                    "Operator choice uses adaptive weights.",
                    [
                        "_AdaptiveWeights.choose",
                        "_AdaptiveWeights.record score usage",
                        "_AdaptiveWeights.update",
                    ],
                ),
                _fact(
                    "cvrp.local_search.intra_two_opt_reversal",
                    "Intra-route 2-opt reversal already exists.",
                    ["_two_opt_intra registered by _default_vns_operators"],
                ),
                _fact(
                    "cvrp.local_search.relocate_and_swap",
                    "Relocate and swap already exist.",
                    ["_relocate", "_swap"],
                ),
                _fact(
                    "cvrp.local_search.vns_operator_registry",
                    "VNS operator registry contains the full local-search portfolio.",
                    [
                        "_default_vns_operators",
                        "_two_opt_intra",
                        "_relocate",
                        "_or_opt_1",
                        "_or_opt_2",
                        "_or_opt_3",
                        "_swap",
                        "_two_opt_star",
                    ],
                ),
                _fact(
                    "cvrp.local_search.cross_route_or_opt_2_3",
                    "Cross-route Or-opt length 2 and 3 already exist.",
                    [
                        "_or_opt_2",
                        "_or_opt_3",
                        "_or_opt skips same-route destinations for cross-route moves",
                    ],
                ),
                _fact(
                    "cvrp.local_search.cross_route_tail_exchange",
                    "Cross-route suffix/tail exchange already exists.",
                    ["_two_opt_star cross-route suffix tail exchange"],
                ),
                _fact(
                    "cvrp.destroy_repair.removal_savings_worst_removal",
                    "_worst_removal ranks removal saving.",
                    [
                        "_worst_removal ranks removal saving with "
                        "saving = -route.cost_of_remove(pos)"
                    ],
                ),
                _fact(
                    "cvrp.destroy_repair.shaw_related_removal",
                    "_shaw_removal related removal already exists.",
                    [
                        "_shaw_removal related proximity destroy removal distance demand route"
                    ],
                ),
                _fact(
                    "cvrp.destroy_repair.random_removal_destroy",
                    "_random_removal random customer-removal destroy already exists.",
                    [
                        "_random_removal uniformly samples customers with rng.sample",
                        'scheduler destroy_ops registers "random" removal',
                    ],
                ),
                _fact(
                    "cvrp.destroy_repair.route_removal",
                    "_route_removal removes a whole selected route.",
                    [
                        "_route_removal removes customers from an entire selected route",
                        "scheduler destroy_ops registers route removal",
                    ],
                ),
                _fact(
                    "cvrp.destroy_repair.regret_insertion_repair",
                    "Repair portfolio already includes regret-2 and regret-3 insertion.",
                    [
                        "_regret2_insertion",
                        "_regret3_insertion",
                        "repair_ops registry includes regret repair operators",
                    ],
                ),
                _fact(
                    "cvrp.search_state.starts_feasible_rejects_infeasible",
                    "Search starts feasible and rejects infeasible candidates.",
                    [
                        "starts from a feasible construction",
                        "rejects infeasible route-cap-violating candidates",
                    ],
                ),
                _fact(
                    "cvrp.search_state.guards_route_limit",
                    "Search guards route limit.",
                    [
                        "_capacity_balanced_construction when route cap is exceeded",
                        "rejects route-cap-violating candidates",
                    ],
                ),
            ],
        },
        "mechanism_summary": {
            "construction": [
                "_sweep_construction",
                "_clarke_wright_savings",
                "_capacity_balanced_construction",
                "_nearest_neighbor fallback",
            ],
            "acceptance": [
                "_AdaptiveWeights.choose",
                "_AdaptiveWeights.record score usage",
                "_AdaptiveWeights.update",
            ],
            "local_search": [
                "_or_opt_2",
                "_or_opt_3",
                "_or_opt skips same-route destinations for cross-route moves",
                "_two_opt_intra registered by _default_vns_operators",
                "_default_vns_operators",
                "_two_opt_star cross-route suffix tail exchange",
            ],
            "destroy_repair": [
                "_worst_removal ranks removal saving with "
                "saving = -route.cost_of_remove(pos)",
                "_shaw_removal related proximity destroy removal distance demand route",
                "_random_removal uniformly samples customers with rng.sample",
                'scheduler destroy_ops registers "random" removal',
                "_route_removal removes customers from an entire selected route",
                "_regret2_insertion",
                "_regret3_insertion",
            ],
            "alns_loop": [
                "starts from a feasible construction",
                "rejects infeasible route-cap-violating candidates",
            ],
        },
    }


def _fact(fact_id: str, claim: str, evidence: list[str]) -> dict[str, object]:
    return {
        "fact_id": fact_id,
        "claim": claim,
        "evidence": evidence,
        "source_paths_or_symbols": [f"test::{fact_id}"],
        "importance": "high",
        "used_by_prompt": True,
        "used_by_gate": True,
    }
