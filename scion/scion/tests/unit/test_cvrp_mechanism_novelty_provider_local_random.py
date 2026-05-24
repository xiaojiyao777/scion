from __future__ import annotations

import pytest

from scion.tests.unit.cvrp_mechanism_novelty_provider_helpers import (
    CvrpMechanismNoveltyProvider,
    DirectCvrpMechanismNoveltyProvider,
    HypothesisProposal,
    MechanismChange,
    ProposalObservation,
    _active_capability_snapshot,
    _hypothesis,
    render_negative_fact_block,
)

def test_cvrp_provider_rejects_false_alns_uniform_weight_claim() -> None:
    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        _hypothesis(
            "ALNS destroy/repair operator weights remain uniform and "
            "non-adaptive throughout the run; make them learn from accepted "
            "moves."
        ),
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is not None
    assert result.premise_check == "contradicted"
    assert result.failure_category == "premise_contradicted"
    assert result.mechanism == "adaptive_operator_weights"
    assert result.contradicted_fact_ids == (
        "cvrp.acceptance.adaptive_operator_weights",
    )
    assert result.contradicted_span
    assert result.matched_span == result.contradicted_span


def test_cvrp_provider_allows_vns_adaptive_neighborhood_ordering() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "VNS local search applies a fixed sequence of neighborhoods. Add a "
            "segment-based success counter and adaptive probability inside the "
            "VNS loop, analogous to ALNS adaptive weights but scoped only to "
            "VNS neighborhood ordering."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        target_weakness=(
            "The local-search phase uses fixed VNS neighborhood scheduling "
            "rather than adapting VNS neighborhood order from recent success."
        ),
        expected_effect=(
            "Improve total_distance by spending VNS effort on productive "
            "neighborhoods."
        ),
        no_op_condition=(
            "Fall back to the existing fixed VNS order when no neighborhood "
            "has success evidence."
        ),
        mechanism_changes=(
            MechanismChange(id="adaptive_vns_operator_weights", change_type="add"),
            MechanismChange(id="vns_local_search", change_type="modify"),
        ),
        novelty_signature={
            "algorithm_family": "adaptive_vns",
            "improvement_strategy": (
                "adaptive_weighted_vns_operator_selection_with_decay"
            ),
        },
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_provider_allows_adaptive_neighborhood_selection_with_existing_moves() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The current VNS loop applies existing segment reversal, Or-opt, "
            "swap, and tail-exchange neighborhoods in a fixed order. Add "
            "adaptive_neighborhood_selection so recent improvement success "
            "changes neighborhood ordering, without adding a new 2-opt or "
            "reversal operator."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        target_weakness=(
            "VNS neighborhood ordering is fixed rather than adaptive."
        ),
        expected_effect="Improve total_distance by prioritizing productive neighborhoods.",
        mechanism_changes=(
            MechanismChange(id="adaptive_neighborhood_selection", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_provider_allows_cross_route_variant_after_listing_existing_two_opt() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The current VNS already has existing _two_opt_intra segment reversal. "
            "Add a cross-route segment-reversal variant for paired routes rather "
            "than another intra-route 2-opt operator."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        target_weakness=(
            "Existing intra-route reversal does not target paired cross-route "
            "route-segment exchanges."
        ),
        expected_effect="Improve total_distance through a bounded cross-route variant.",
        mechanism_changes=(
            MechanismChange(id="cross_route_segment_reversal_variant", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_provider_allows_double_bridge_after_listing_existing_or_opt() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The current VNS operator list already contains _or_opt_1, "
            "_or_opt_2, and _or_opt_3. It still lacks a cross-route 3-opt / "
            "double-bridge exchange, so add that separate route-pair move."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        target_weakness=(
            "Existing Or-opt relocations do not perform a double-bridge "
            "route-pair exchange."
        ),
        expected_effect="Improve total_distance through a separate double-bridge move.",
        mechanism_changes=(
            MechanismChange(id="cross_route_double_bridge", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_provider_allows_or_opt_candidate_filter_after_listing_moves() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The active VNS local search uses _two_opt_intra, _relocate, "
            "_or_opt_1/_2/_3, _swap, and _two_opt_star, but it lacks "
            "distance-based nearest-neighbor candidate filtering and delta "
            "pruning inside the existing Or-opt evaluations. Add a KNN "
            "candidate filter to reduce unproductive route-pair scans without "
            "adding a new Or-opt operator."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        target_weakness=(
            "Existing Or-opt neighborhoods spend effort on low-value route pairs."
        ),
        expected_effect="Improve total_distance within the same time budget.",
        mechanism_changes=(
            MechanismChange(id="knn_candidate_filter", change_type="add"),
            MechanismChange(id="or_opt_local_search", change_type="modify"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


@pytest.mark.parametrize(
    "hypothesis_text,mechanism_id,target_weakness",
    (
        (
            "The active solver's VNS local search applies operators in a fixed "
            "round-robin sequence (_two_opt_intra, _relocate, _or_opt_1, "
            "_or_opt_2, _or_opt_3, _swap, _two_opt_star) with no inter-route "
            "node-pair distance filter. Add a neighbor-list filter for existing "
            "cross-route operators without adding any new Or-opt neighborhood.",
            "vns_neighbor_list_filter",
            "Existing VNS route-pair scans lack a node-pair distance filter.",
        ),
        (
            "The active solver's VNS local search applies its full operator "
            "portfolio (_two_opt_intra, _relocate, _or_opt_1/_2/_3, _swap, "
            "_two_opt_star) in a fixed sequential order every pass, with no "
            "route-pair candidate list or spatial filtering. Add a candidate "
            "list filter around the existing Or-opt evaluations.",
            "vns_candidate_list_filter",
            "Existing VNS scans lack route-pair candidate lists.",
        ),
        (
            "The active VNS phase applies every local-search operator "
            "(_two_opt_intra, _relocate, _or_opt_1/_2/_3, _swap, "
            "_two_opt_star) on every pass with no adaptive ordering or success "
            "feedback. Add adaptive_vns_op_order to reorder the existing "
            "operators by recent improvement evidence.",
            "adaptive_vns_op_order",
            "Existing VNS operator order is fixed rather than success-adaptive.",
        ),
    ),
)
def test_cvrp_provider_allows_existing_or_opt_list_with_variant_gap(
    hypothesis_text: str,
    mechanism_id: str,
    target_weakness: str,
) -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=hypothesis_text,
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        target_weakness=target_weakness,
        expected_effect="Improve total_distance using the existing VNS operators.",
        mechanism_changes=(
            MechanismChange(id=mechanism_id, change_type="add"),
            MechanismChange(id="or_opt_local_search", change_type="modify"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_provider_allows_contiguous_segment_destroy_after_route_removal_listing() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The current ALNS destroy phase has existing operators "
            "(shaw_removal, worst_removal, route_removal), but lacks a "
            "positional/sequential destroy mechanism that removes a contiguous "
            "block of customers within a route segment. Add segment_destroy as "
            "a subroute window removal variant, not a whole-route removal."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness=(
            "Existing whole-route removal does not target sequential arc windows."
        ),
        expected_effect="Improve total_distance by perturbing local arc structure.",
        mechanism_changes=(
            MechanismChange(id="segment_destroy", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_provider_allows_scheduler_perturbation_not_shaw_related_removal() -> None:
    cases = [
        HypothesisProposal(
            hypothesis_text=(
                "Add double_bridge_perturbation in scheduler.py after ALNS "
                "stagnation. The existing destroy operators (shaw, route_removal, "
                "worst_removal) remove and reinsert customers, but none performs "
                "topological route-segment reconnection."
            ),
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_modules/scheduler.py",
            target_weakness="VNS-exhausted basins need a large perturbation.",
            expected_effect="Improve total_distance by opening a new basin.",
            mechanism_changes=(
                MechanismChange(id="double_bridge_perturbation", change_type="add"),
            ),
        ),
        HypothesisProposal(
            hypothesis_text=(
                "Add a scheduler restart perturbation after repeated no-improve "
                "iterations using double-bridge route-pair moves. This is not "
                "Shaw related removal and not proximity removal."
            ),
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_modules/scheduler.py",
            target_weakness="The scheduler lacks restart perturbation on plateaus.",
            expected_effect="Improve total_distance after stagnation.",
            mechanism_changes=(
                MechanismChange(id="scheduler_restart_perturbation", change_type="add"),
            ),
        ),
    ]

    for hypothesis in cases:
        result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
            hypothesis,
            active_solver_snapshot=_active_capability_snapshot(),
        )

        assert result is None, hypothesis.hypothesis_text


def test_cvrp_provider_keeps_route_removal_blocks_precise() -> None:
    cases = [
        (
            "The active destroy portfolio has no whole route removal operator, "
            "so add route removal.",
            "contradicted",
        ),
        (
            "Introduce a new whole route removal destroy operator.",
            "duplicate",
        ),
    ]

    for text, premise_check in cases:
        result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
            _hypothesis(text),
            active_solver_snapshot=_active_capability_snapshot(),
        )

        assert result is not None, text
        assert result.mechanism == "route_removal"
        assert result.premise_check == premise_check


def test_cvrp_provider_keeps_shaw_related_duplicate_block() -> None:
    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        _hypothesis(
            "Add a new proximity-cluster removal operator as a new destroy "
            "capability for the active ALNS solver."
        ),
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is not None
    assert result.mechanism == "shaw_related_removal"
    assert result.premise_check == "duplicate"


def test_cvrp_provider_allows_positional_arc_destroy_variant_near_shaw_terms() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add a positional arc-cluster destroy variant that scores route "
            "edges by local detour and route position. This is not a new "
            "Shaw related-removal operator; it targets arc context rather than "
            "seed relatedness."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Destroy selection misses high-detour positional arcs.",
        expected_effect="Improve total_distance by removing expensive arc clusters.",
        mechanism_changes=(
            MechanismChange(id="positional_arc_destroy", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_provider_allows_random_greedy_repair_variant_near_regret_terms() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add random_greedy_repair as a stochastic greedy insertion repair "
            "alongside existing regret repair. It is not a regret insertion "
            "operator and should diversify insertion ordering after destroy."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Repair insertion ordering is too deterministic.",
        expected_effect="Improve total_distance by diversifying repair insertion.",
        mechanism_changes=(
            MechanismChange(id="random_greedy_repair", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_provider_allows_position_diversity_repair_near_regret_terms() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add position_diversity_repair to diversify insertion positions, "
            "rather than regret-2/regret-3 scoring. The existing regret "
            "portfolio remains available as a separate repair family."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Repair choices concentrate on the same route positions.",
        expected_effect="Improve total_distance through insertion-position diversity.",
        mechanism_changes=(
            MechanismChange(id="position_diversity_repair", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_provider_allows_acknowledged_knn_regret_variant() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The active solver already includes _regret2_insertion and "
            "_regret3_insertion. Add a bounded KNN insertion repair variant "
            "that filters candidate insertion routes to nearest-neighbor "
            "customers before applying regret scoring."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness=(
            "Existing regret repair evaluates too broad a candidate set when "
            "nearby routes should dominate insertion quality."
        ),
        expected_effect=(
            "Improve total_distance by adding a neighbor-limited regret variant."
        ),
        mechanism_changes=(
            MechanismChange(id="knn_insertion_repair", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


@pytest.mark.parametrize(
    "hypothesis",
    (
        HypothesisProposal(
            hypothesis_text=(
                "Add cluster_removal as a pure geographic customer-cluster "
                "destroy. The active destroy portfolio already uses random, "
                "worst, Shaw, and route removal; this cluster variant is "
                "distinct from existing Shaw related removal because it ignores "
                "demand and original-route relatedness."
            ),
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_modules/destroy_repair.py",
            target_weakness=(
                "Existing destroy choices lack a pure geographic cluster variant."
            ),
            expected_effect="Improve total_distance by perturbing spatial clusters.",
            mechanism_changes=(
                MechanismChange(id="cluster_removal", change_type="add"),
            ),
        ),
        HypothesisProposal(
            hypothesis_text=(
                "Add zone_clustered_removal. The current destroy scheduler uses "
                "route-removal operators, but it lacks a bounded zone-clustered "
                "removal variant that removes nearby customers across multiple "
                "routes rather than deleting an entire selected route."
            ),
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_modules/destroy_repair.py",
            target_weakness=(
                "Existing whole-route removal does not target spatial zones."
            ),
            expected_effect="Improve total_distance by perturbing cross-route zones.",
            mechanism_changes=(
                MechanismChange(id="zone_clustered_removal", change_type="add"),
            ),
        ),
        HypothesisProposal(
            hypothesis_text=(
                "Add adaptive_vns_operator_schedule for VNS operator ordering. "
                "The local-search operator weights are uniform at initialization "
                "and the current VNS ordering is fixed; this is not an ALNS "
                "destroy/repair adaptive-weight claim."
            ),
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_modules/local_search.py",
            target_weakness="VNS operator order is fixed rather than success-adaptive.",
            expected_effect="Improve total_distance by reordering VNS operators.",
            mechanism_changes=(
                MechanismChange(id="adaptive_vns_operator_schedule", change_type="add"),
            ),
        ),
        HypothesisProposal(
            hypothesis_text=(
                "Add nn_filtered_repair. The existing repair portfolio has "
                "greedy insertion and regret-2/regret-3 exist, but candidate-list "
                "filtering is absent; the new mechanism restricts insertion "
                "routes to nearest-neighbor candidates before using the existing "
                "repair scoring."
            ),
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_modules/destroy_repair.py",
            target_weakness=(
                "Existing repair evaluates too many nonlocal insertion candidates."
            ),
            expected_effect="Improve total_distance within the same repair budget.",
            mechanism_changes=(
                MechanismChange(id="nn_filtered_repair", change_type="add"),
            ),
        ),
        HypothesisProposal(
            hypothesis_text=(
                "Add adaptive_vns_selector to optimize VNS operator selection "
                "policy. It observes which existing productive operator, e.g. "
                "_or_opt_1, recently improved distance and reorders the existing "
                "operator list without adding a new Or-opt-1 relocation."
            ),
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_modules/local_search.py",
            target_weakness="Existing VNS selector uses a fixed operator order.",
            expected_effect="Improve total_distance by prioritizing productive moves.",
            mechanism_changes=(
                MechanismChange(id="adaptive_vns_selector", change_type="add"),
            ),
        ),
    ),
)
def test_cvrp_provider_allows_acknowledged_material_variants_from_sessions(
    hypothesis: HypothesisProposal,
) -> None:
    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None, hypothesis.hypothesis_text


def test_cvrp_provider_allows_three_opt_star_after_acknowledging_or_opt() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The active bottleneck identified from screening evidence is late "
            "local-search stagnation after the current VNS operator list has "
            "already applied _or_opt_1/_2/_3 segment moves and _two_opt_star "
            "tail exchange. The solver currently lacks a Lin-Kernighan-style "
            "3-opt* inter-route move; add a bounded three-route / triple-edge "
            "chain reconnection that is materially different from 2-opt* "
            "tail swap, Or-opt segment moves, or single-customer relocate."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        target_weakness=(
            "The VNS operator portfolio lacks multi-route 3-opt* chain "
            "reconnection: existing cross-route operators only do 2-opt* tail "
            "exchange and Or-opt segment relocation."
        ),
        expected_effect=(
            "Improve total_distance by escaping route-pair local minima with a "
            "bounded three-way chain exchange."
        ),
        no_op_condition=(
            "Skip the operator when fewer than three non-empty routes are "
            "available or no improving reconnection is found under the budget."
        ),
        mechanism_changes=(
            MechanismChange(id="three_opt_star", change_type="add"),
            MechanismChange(id="vns_operator_registry", change_type="modify"),
        ),
        novelty_signature={
            "algorithm_family": "vns_local_search",
            "improvement_strategy": (
                "three_opt_star_multi_route_triple_edge_reconnect"
            ),
            "runtime_budget_strategy": "bounded_route_triplets",
        },
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.failure_category != "premise_contradicted"


@pytest.mark.parametrize(
    "hypothesis",
    (
        HypothesisProposal(
            hypothesis_text=(
                "The existing local-search portfolio already contains "
                "_or_opt_1/_or_opt_2/_or_opt_3. Add nblist_or_opt1 to apply "
                "nearest-neighbor candidate filtering before the existing "
                "single-customer Or-opt move, without adding a new relocation "
                "operator."
            ),
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_modules/local_search.py",
            target_weakness="Existing Or-opt scans too many nonlocal destinations.",
            expected_effect="Improve total_distance by pruning low-value destinations.",
            mechanism_changes=(
                MechanismChange(id="nblist_or_opt1", change_type="add"),
            ),
        ),
        HypothesisProposal(
            hypothesis_text=(
                "The current VNS has _or_opt_1 cross-route relocation. Add an "
                "intra-route Or-opt sweep variant that tries same-route "
                "single-customer shifts as a bounded intensification step; this "
                "does not claim that cross-route Or-opt is missing."
            ),
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_modules/local_search.py",
            target_weakness="Existing VNS lacks a same-route Or-opt intensifier.",
            expected_effect="Improve total_distance inside each route.",
            mechanism_changes=(
                MechanismChange(id="intra_or_opt_sweep", change_type="add"),
            ),
        ),
        HypothesisProposal(
            hypothesis_text=(
                "Existing _or_opt_1/_2/_3 segment moves are available, but they "
                "operate on one segment relocation at a time. Add a three-route "
                "chain reconnection that composes a bounded 3-opt* exchange "
                "across route triples."
            ),
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_modules/local_search.py",
            target_weakness="Existing local search lacks route-triple chain moves.",
            expected_effect="Improve total_distance by escaping route-pair minima.",
            mechanism_changes=(
                MechanismChange(id="three_route_chain_reconnect", change_type="add"),
            ),
        ),
    ),
)
def test_cvrp_provider_allows_existing_or_opt_material_variants(
    hypothesis: HypothesisProposal,
) -> None:
    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.failure_category != "premise_contradicted"


def test_cvrp_provider_still_blocks_explicit_missing_or_opt_claim() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The active VNS has no Or-opt cross-route relocation operator, so "
            "add a new cross-route Or-opt-1 move."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        target_weakness="VNS lacks Or-opt relocation.",
        expected_effect="Improve total_distance with a new relocate operator.",
        mechanism_changes=(
            MechanismChange(id="or_opt1_relocation", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is not None
    assert result.failure_category == "premise_contradicted"
    assert result.mechanism in {"or_opt_1_relocation", "cross_route_or_opt_2_3"}


def test_cvrp_provider_blocks_duplicate_random_removal_near_cluster_terms() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add random_removal with a small stochastic destroy budget to "
            "diversify removed customers. This is not related removal, not "
            "Shaw removal, and not a proximity cluster destroy."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Destroy selection lacks random exploration.",
        expected_effect="Improve total_distance by diversifying destroy choices.",
        mechanism_changes=(
            MechanismChange(id="random_removal", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is not None
    assert result.premise_check == "duplicate"
    assert result.failure_category == "duplicate_mechanism"
    assert result.mechanism == "random_removal_destroy"
    assert result.fact_ids == ("cvrp.destroy_repair.random_removal_destroy",)
    assert "_random_removal" in " ".join([result.reason, *result.evidence])


def test_cvrp_provider_allows_cluster_destroy_contrasting_random_removal() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add proximity-cluster destroy from a random seed that greedily "
            "removes the nearest customers across routes. This is distinct from "
            "Shaw related removal and from random removal (uniform sampling). "
            "No-op condition: fall back to existing destroy selection when a "
            "cluster cannot be formed."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness=(
            "Destroy lacks a pure spatial cluster variant separate from uniform "
            "random removal."
        ),
        expected_effect="Improve total_distance by perturbing spatially related stops.",
        mechanism_changes=(
            MechanismChange(id="cluster_removal_destroy", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_provider_allows_geographic_cluster_variant_after_uniform_random_contrast() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add geographic_cluster_removal as a grid-based spatial patch "
            "destroy operator. The active destroy phase already uses random, "
            "Shaw, worst, and route removal. Random removal is purely uniform. "
            "No systematic spatial patch removal exists, so this mechanism "
            "targets geographic clusters rather than random sampling."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness=(
            "Existing random removal is purely uniform and does not form "
            "geographic customer clusters."
        ),
        expected_effect="Improve total_distance by removing spatially coherent patches.",
        mechanism_changes=(
            MechanismChange(id="geographic_cluster_removal", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_provider_blocks_missing_random_removal_claim_with_span() -> None:
    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        _hypothesis(
            "The active destroy portfolio lacks random customer removal, so add "
            "a random removal destroy operator."
        ),
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is not None
    assert result.premise_check == "contradicted"
    assert result.failure_category == "premise_contradicted"
    assert result.mechanism == "random_removal_destroy"
    assert result.contradicted_fact_ids == (
        "cvrp.destroy_repair.random_removal_destroy",
    )
    assert "lacks random customer removal" in result.contradicted_span
    assert result.matched_span == result.contradicted_span
    assert "scheduler" in result.reason


def test_cvrp_provider_regret_semantic_contradiction_uses_precise_reason() -> None:
    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        _hypothesis(
            "Regret insertion repair operators always insert customers at "
            "globally cheapest positions without considering regret score."
        ),
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is not None
    assert result.mechanism == "regret_insertion_repair"
    assert result.premise_check == "contradicted"
    assert "mischaracterizes" in result.reason
    assert "absent" not in result.reason
    assert "tie-break" in result.reason
    assert "without considering regret" in result.contradicted_span


def test_cvrp_provider_allows_acknowledged_random_removal_distribution_variant() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Modify existing _random_removal by adding an adaptive sampling "
            "distribution and noise schedule around the scheduler random destroy "
            "operator; this is a variant of the existing random removal, not a "
            "claim that random customer removal is missing."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Existing random removal samples uniformly.",
        expected_effect="Improve total_distance through adaptive randomization.",
        mechanism_changes=(
            MechanismChange(
                id="adaptive_random_removal_distribution",
                change_type="modify",
            ),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_provider_allows_noise_removal_near_savings_terms() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add noise_removal as a stochastic removal variant that perturbs "
            "destroy choice around existing cost-of-remove savings rather than "
            "adding a new savings-removal heuristic."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Worst-removal selection is too deterministic.",
        expected_effect="Improve total_distance by adding bounded destroy noise.",
        mechanism_changes=(
            MechanismChange(id="noise_removal", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_provider_blocks_missing_shaw_claim_with_span() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The baseline lacks related removal, so add a Shaw-style proximity "
            "cluster destroy operator."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Related removal is missing.",
        expected_effect="Improve destroy diversity.",
        mechanism_changes=(
            MechanismChange(id="shaw_related_removal", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is not None
    assert result.premise_check == "contradicted"
    assert result.failure_category == "premise_contradicted"
    assert result.mechanism == "shaw_related_removal"
    assert result.variant_allowed is False
    assert "lacks related removal" in result.contradicted_span
    assert result.matched_span == result.contradicted_span
    assert "Allowed variant" in (result.allowed_variant_guidance or "")


def test_cvrp_provider_allows_shaw_trigger_scoring_variant() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Modify existing _shaw_removal by adding adaptive trigger scoring, "
            "a schedule for relatedness weights, and candidate filtering; this "
            "is a variant of the existing Shaw removal, not a new missing "
            "related-removal operator."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Existing Shaw removal trigger/scoring is static.",
        expected_effect="Improve total_distance through better related removal variants.",
        mechanism_changes=(
            MechanismChange(id="shaw_related_removal_variant", change_type="modify"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_provider_allows_single_seed_trajectory_after_listing_construction_portfolio() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The current construction portfolio (sweep, Clarke-Wright, "
            "capacity-balanced, nearest-neighbor) generates a single seed "
            "solution per solve call, then follows one ALNS+VNS trajectory. "
            "Add perturbation_restart in scheduler.py to diversify the basin "
            "after stagnation without claiming construction is nearest-neighbor-only."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/scheduler.py",
        target_weakness="Search follows a single incumbent trajectory per solve.",
        expected_effect="Improve total_distance by exploring additional basins.",
        mechanism_changes=(
            MechanismChange(id="perturbation_restart", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_provider_premise_contradictions_always_have_exact_span() -> None:
    cases = [
        _hypothesis("The active solver uses only nearest neighbor seed construction."),
        _hypothesis(
            "ALNS destroy repair weights remain uniform throughout the run."
        ),
        _hypothesis("The baseline lacks intra route 2 opt segment reversal."),
        _hypothesis(
            "The active solver lacks cross route Or opt segment relocation."
        ),
        _hypothesis("The active solver lacks cross route tail exchange."),
        _hypothesis("The destroy pool lacks removal savings targeting."),
        _hypothesis("The baseline lacks related removal."),
        _hypothesis("The baseline lacks regret insertion repair."),
        HypothesisProposal(
            hypothesis_text=(
                "The current ALNS starts with positive fleet violation and must "
                "repair it before optimizing distance."
            ),
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_modules/scheduler.py",
            target_weakness="Positive fleet violation remains.",
            expected_effect="Reduce fleet violation.",
        ),
        HypothesisProposal(
            hypothesis_text=(
                "Add a feasibility crossing phase that triggers when the current "
                "solution moves from infeasible to feasible."
            ),
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_modules/scheduler.py",
            target_weakness="Feasibility crossing is unhandled.",
            expected_effect="Improve search phases.",
        ),
    ]

    for hypothesis in cases:
        result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
            hypothesis,
            active_solver_snapshot=_active_capability_snapshot(),
        )

        assert result is not None, hypothesis.hypothesis_text
        if result.premise_check == "contradicted":
            assert result.failure_category == "premise_contradicted"
            assert result.contradicted_span, result.mechanism
            assert result.matched_span == result.contradicted_span
            assert result.variant_allowed is False
