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
from scion.problems.cvrp.mechanism_novelty.destroy_repair.shared import (
    _acknowledges_existing_removal_savings_destroy,
)

def test_cvrp_shaw_gate_allows_contrast_text_for_non_shaw_repair() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add stochastic noise-biased insertion repair. Unlike Shaw related "
            "removal, this targets insertion diversity and does not add "
            "Shaw/proximity removal."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness=(
            "Repair insertion lacks noise diversity, unlike Shaw related removal."
        ),
        expected_effect="Improve total_distance through repair diversification.",
        mechanism_changes=(
            MechanismChange(id="noise_biased_insertion_repair", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_regret_gate_blocks_missing_claim_with_exact_span() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The baseline lacks regret insertion repair, so add regret-2 repair "
            "as a new insertion mechanism after destroy removal."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Regret repair is missing.",
        expected_effect="Improve total_distance through better repair insertion.",
        mechanism_changes=(
            MechanismChange(id="regret_insertion_repair", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is not None
    assert result.premise_check == "contradicted"
    assert result.failure_category == "mechanism_premise_warning"
    assert result.mechanism == "regret_insertion_repair"
    assert result.variant_allowed is None
    assert "lacks regret insertion repair" in result.contradicted_span
    assert result.matched_span == result.contradicted_span
    assert "Allowed variant" in (result.allowed_variant_guidance or "")


def test_cvrp_regret_gate_allows_new_destroy_using_existing_regret_repair() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add a costly-arc destroy operator that removes expensive route "
            "segments, then uses existing regret repair to reinsert removed "
            "customers without adding a new regret repair mechanism."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Destroy selection misses costly arcs.",
        expected_effect="Improve total_distance through better removals.",
        mechanism_changes=(
            MechanismChange(id="costly_arc_destroy", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_regret_gate_allows_cluster_destroy_acknowledging_regret_repair() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add proximity_cluster_destroy. The baseline already has greedy, "
            "regret-2, and regret-3 repair operators; this change only removes "
            "spatially nearby customers before calling the existing regret "
            "repair path. It is not a claim that regret insertion is absent."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness=(
            "Destroy selection lacks a proximity-cluster removal variant, while "
            "existing repair operators insert independently."
        ),
        expected_effect="Improve total_distance by perturbing spatial clusters.",
        mechanism_changes=(
            MechanismChange(id="proximity_cluster_destroy", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.failure_category != "premise_contradicted"


def test_cvrp_regret_gate_allows_route_pool_recombination_using_existing_regret() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The active solver already has diverse feasible construction, ALNS "
            "destroy/repair with regret insertion, and VNS relocate/swap/Or-opt "
            "moves, but it lacks a whole-route recombination mechanism that "
            "preserves high-quality route fragments from elite incumbent "
            "snapshots and rebuilds only uncovered customers. Add a bounded "
            "route-pool recombination phase, then repair uncovered customers "
            "with existing capacity-safe regret insertion."
        ),
        change_locus="solver_design",
        action="create_new",
        target_file="policies/baseline_modules/route_pool_recombination.py",
        target_weakness="Search lacks solution-level route-fragment recombination.",
        expected_effect="Improve total_distance through elite route recombination.",
        mechanism_changes=(
            MechanismChange(id="route_pool_recombination", change_type="add"),
            MechanismChange(id="elite_solution_pool", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.failure_category != "premise_contradicted"


def test_cvrp_random_gate_allows_cluster_destroy_contrast_with_random_removal() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The active solver uses all four destroy operators (random, worst, "
            "shaw, route) but lacks a cluster-based removal that removes "
            "geographically concentrated customer groups. The new cluster "
            "operator differs from random removal by being spatially contiguous "
            "and from Shaw removal by using pure Euclidean distance rank with "
            "no demand or route-membership weighting."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness=(
            "The existing destroy operators (random, worst, shaw, route) do not "
            "produce tight geographic clusters of removed customers."
        ),
        expected_effect=(
            "Adding cluster removal to the ALNS destroy portfolio gives the "
            "adaptive weight system a new spatially compact removal option."
        ),
        mechanism_changes=(
            MechanismChange(id="cluster_removal_destroy", change_type="add"),
        ),
        novelty_signature={
            "algorithm_family": "ALNS+VNS with expanded destroy portfolio",
            "improvement_strategy": (
                "add pure-distance cluster removal destroy: seed + top-q "
                "nearest customers by Euclidean distance"
            ),
        },
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.mechanism != "random_removal_destroy"
    assert result is None or result.failure_category != "premise_contradicted"


def test_cvrp_regret_gate_allows_nn_repair_variant_acknowledging_regret() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add nn_filtered_repair as a candidate-list variant of repair. "
            "The current solver already includes _regret2_insertion and "
            "_regret3_insertion; the new mechanism filters insertion positions "
            "to nearest-neighbor candidate lists before evaluating regret."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Existing regret repair lacks nearest-neighbor filtering.",
        expected_effect="Reduce repair time while preserving distance quality.",
        mechanism_changes=(
            MechanismChange(id="nn_filtered_repair", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.failure_category != "premise_contradicted"


def test_cvrp_regret_gate_allows_post_repair_merge_compaction_variant() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The current ALNS repair operators (_greedy_insertion, "
            "_regret2_insertion, _regret3_insertion) already exist and always "
            "insert unrouted customers into existing routes without considering "
            "whether merging a small route into another would reduce total "
            "distance. Add alns_merge_small_routes as a post-repair compaction "
            "step that relocates all customers from near-empty routes when "
            "capacity feasibility holds."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/scheduler.py",
        target_weakness=(
            "ALNS lacks post-repair small-route merge compaction."
        ),
        expected_effect="Improve total_distance by eliminating near-empty routes.",
        mechanism_changes=(
            MechanismChange(id="alns_merge_small_routes", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.failure_category != "premise_contradicted"


def test_cvrp_regret_gate_allows_reported_compact_repair_negation_fixture() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Recent feedback shows the active bottleneck is total_distance win "
            "rate, while the prior local-search expansion saturated runtime and "
            "the current fleet_violation dimension is stable. The full "
            "destroy_repair.py shows existing repairs choose lowest-cost "
            "feasible insertions or regret-2/3 insertions, but none explicitly "
            "preserves geographically compact route envelopes during repair; "
            "add a compactness-biased repair variant that scores each feasible "
            "insertion by insertion delta plus a small penalty for increasing "
            "the route's customer-to-customer/depot radius or angular spread, "
            "and wire it as an additional bounded ALNS repair option. This is "
            "not a missing-regret claim: it is a materially different repair "
            "objective that should avoid rebuilding elongated routes after "
            "random/worst/Shaw/route removal, producing shorter final routes "
            "with the existing SA/adaptive-weight acceptance and feasibility "
            "guards."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness=(
            "Existing repairs do not score compactness of route envelopes."
        ),
        expected_effect="Improve total_distance through compact route repair.",
        mechanism_changes=(
            MechanismChange(id="compact_repair", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.failure_category != "premise_contradicted"


def test_cvrp_regret_gate_allows_missing_regret_negation_variants() -> None:
    phrases = [
        "This is not a missing-regret claim.",
        "This is not a missing regret claim.",
        "It does not claim regret insertion is missing.",
        (
            "Existing repairs include regret-2/3 insertions, but none explicitly "
            "preserves compact route envelopes."
        ),
        (
            "This is not adding regret insertion itself; adding a "
            "compactness-biased scored bounded variant."
        ),
    ]

    for phrase in phrases:
        hypothesis = HypothesisProposal(
            hypothesis_text=(
                "The current solver already includes regret-2 and regret-3 "
                "repair insertions. "
                f"{phrase} Add compact_repair as a bounded repair-scoring "
                "variant that changes compactness preference, not the existence "
                "of regret repair."
            ),
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_modules/destroy_repair.py",
            target_weakness="Existing repair scoring ignores compactness.",
            expected_effect="Improve total_distance through compact repairs.",
            mechanism_changes=(
                MechanismChange(id="compact_repair", change_type="add"),
            ),
        )

        result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
            hypothesis,
            active_solver_snapshot=_active_capability_snapshot(),
        )

        assert result is None or result.failure_category != "premise_contradicted", phrase


def test_cvrp_regret_gate_allows_reported_route_compaction_no_new_route_fixture() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Screening shows the current distance improvements are tie-dominated "
            "and the failed local-search expansion saturated runtime, while "
            "fleet_violation is already stable because scheduler.py rejects "
            "infeasible and over-route-limit candidates. Add a bounded "
            "route-compaction intensification phase owned by scheduler.py after "
            "initial construction and again only when ALNS has not "
            "best-improved for a short segment: select at most three sparsest "
            "nonempty routes, try to absorb each route's customers into "
            "existing routes using best feasible regret-ordered insertions "
            "without creating routes, and keep the compaction only if route "
            "count is nonincreasing and total_distance strictly improves. This "
            "differs from existing route_removal plus regret repair because it "
            "is not a random destroy/repair operator that can recreate removed "
            "routes; it is a deterministic no-new-route absorption pass "
            "targeting low-load route fragmentation and avoiding the prior "
            "cross-route edge-bridge mechanism. It no-ops when all selected "
            "sparse routes cannot be fully absorbed within capacity, when it "
            "would increase route count or distance, or when remaining-time "
            "reserve is breached."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/scheduler.py",
        target_weakness="Route fragmentation leaves low-load routes unabsorbed.",
        expected_effect="Improve total_distance via route compaction.",
        mechanism_changes=(
            MechanismChange(id="route_compaction", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.failure_category != "premise_contradicted"
    assert result is None or result.mechanism != "regret_insertion_repair"


@pytest.mark.parametrize(
    "phrase",
    (
        (
            "Existing route_removal plus regret repair is available, but the "
            "new route compaction pass absorbs sparse routes with no additional "
            "routes."
        ),
        (
            "This differs from existing route_removal plus regret repair because "
            "the absorption variant avoids creating routes and only reuses "
            "existing feasible regret-ordered insertion positions."
        ),
        (
            "Unlike existing regret repair, this route-compaction variant is a "
            "no-new-route absorption pass for low-load route fragmentation."
        ),
        (
            "Use existing regret repair ordering inside a route compaction pass "
            "without creating new routes; do not add regret repair itself."
        ),
    ),
)
def test_cvrp_regret_gate_allows_route_creation_negation_variants(
    phrase: str,
) -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            f"{phrase} Keep the change bounded and accept it only when route "
            "count is nonincreasing and total_distance improves."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/scheduler.py",
        target_weakness="Sparse route fragmentation remains after repair.",
        expected_effect="Improve total_distance by absorbing sparse routes.",
        mechanism_changes=(
            MechanismChange(id="route_compaction", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.failure_category != "premise_contradicted", phrase
    assert result is None or result.mechanism != "regret_insertion_repair", phrase


def test_cvrp_regret_gate_blocks_current_no_regret_positive_premise() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The current solver has no regret repair, so add the first regret "
            "insertion repair operator after destroy removal."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Regret repair is missing from current repair.",
        expected_effect="Improve total_distance through first regret repair.",
        mechanism_changes=(
            MechanismChange(id="regret_insertion_repair", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is not None
    assert result.premise_check == "contradicted"
    assert result.failure_category == "mechanism_premise_warning"
    assert result.mechanism == "regret_insertion_repair"
    assert result.contradicted_span


def test_cvrp_regret_gate_allows_stagnation_restart_using_existing_regret() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add stagnation_restart as a large perturbation escape when ALNS "
            "plateaus, then use the existing regret-3 repair path to reinsert "
            "removed customers. This leverages existing regret repair after "
            "perturbation and does not claim regret insertion is absent."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/scheduler.py",
        target_weakness=(
            "Search can stagnate without escaping the local basin after many "
            "non-improving iterations."
        ),
        expected_effect="Improve total_distance after stagnation.",
        mechanism_changes=(
            MechanismChange(id="stagnation_restart", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.failure_category != "premise_contradicted"


def test_cvrp_mechanism_novelty_provider_blocks_removal_savings_duplicate_precisely() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add a _savings_removal destroy heuristic that ranks customers by "
            "removal savings and geometric detour cost using cost_of_remove, "
            "then registers it as an additional destroy operator alongside "
            "the current destroy pool."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Need an additional high-detour removal operator.",
        expected_effect="Reduce total_distance by removing high-detour customers.",
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is not None
    assert result.premise_check == "duplicate"
    assert result.failure_category == "duplicate_mechanism"
    assert result.result_kind == "duplicate_diagnostic"
    assert result.gate_action == "diagnostic"
    assert result.is_hard_block is False
    assert result.mechanism == "removal_savings_worst_removal"
    assert result.fact_ids == (
        "cvrp.destroy_repair.removal_savings_worst_removal",
    )
    rendered = " ".join([result.reason, *result.evidence])
    assert "_worst_removal" in rendered
    assert "cost_of_remove" in rendered
    assert "removal saving" in rendered
    assert result.mechanism != "shaw_related_removal"


def test_cvrp_removal_savings_duplicate_prefers_worst_removal_reason() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add a worst-position cost-of-remove destroy operator that selects "
            "customers by route.cost_of_remove(pos) and removal savings before "
            "repair. It is a new destroy heuristic, not a relatedness cluster."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Need another high-saving removal operator.",
        expected_effect="Improve total_distance by removing high saving positions.",
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is not None
    assert result.mechanism == "removal_savings_worst_removal"
    rendered = " ".join([result.reason, *result.evidence])
    assert "_worst_removal" in rendered
    assert "cost_of_remove" in rendered
    assert "_shaw_removal" not in result.reason


def test_cvrp_provider_allows_geographic_cluster_variant_acknowledging_worst_removal() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The current ALNS destroy portfolio lacks a pure geographic-cluster "
            "destroy operator. Existing _shaw_removal uses blended distance, "
            "demand, and route relatedness, and _worst_removal already seeds on "
            "removal savings with cost_of_remove. Add cluster_removal that picks "
            "a random seed customer and removes the nearest customers by "
            "Euclidean coordinates across routes before repair; this is an "
            "orthogonal pure geographic variant, not another removal-savings or "
            "detour-cost operator."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Destroy lacks a pure geographic cluster variant.",
        expected_effect="Improve total_distance by perturbing nearby customers.",
        mechanism_changes=(
            MechanismChange(id="cluster_removal", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_provider_allows_zone_cluster_variant_contrasting_existing_shaw() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Unlike the existing _shaw_removal, which grows from a seed using "
            "distance, demand, and route relatedness, add centroid zone "
            "cluster_removal that removes customers from a fixed geographic "
            "cell before repair. The runtime budget uses no extra polling "
            "cluster removal loop."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Destroy lacks a route-independent centroid zone variant.",
        expected_effect="Improve total_distance by perturbing spatial zones.",
        mechanism_changes=(
            MechanismChange(id="cluster_removal", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_provider_does_not_hard_block_shaw_near_field_variant() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The active solver already has _shaw_removal using distance, demand, "
            "and route relatedness. Add boundary_cluster_removal as a near-field "
            "variant that changes the seed selection and relatedness metric for "
            "border customers; this is not a claim that Shaw or related removal "
            "is missing."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Existing Shaw removal lacks a boundary-aware metric variant.",
        expected_effect="Improve total_distance by perturbing boundary clusters.",
        mechanism_changes=(
            MechanismChange(id="boundary_cluster_removal", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.is_hard_block is False
    assert result is None or result.result_kind == "duplicate_diagnostic"


def test_cvrp_provider_does_not_hard_block_regret_candidate_filter_variant() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The active solver already includes _regret2_insertion and "
            "_regret3_insertion. Add regret_candidate_filtering that keeps the "
            "existing regret repair semantics but filters candidate insertion "
            "positions by nearest-neighbor lists before scoring; this does not "
            "claim regret insertion is absent."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Existing regret repair lacks candidate filtering.",
        expected_effect="Reduce repair time without removing regret scoring.",
        mechanism_changes=(
            MechanismChange(id="regret_candidate_filtering", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.is_hard_block is False


def test_cvrp_provider_does_not_hard_block_route_removal_trigger_variant() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The active solver already has _route_removal for whole-route "
            "destroy. Add route_removal_trigger_variant that reuses the existing "
            "operator but changes when it is sampled after stagnation; this is "
            "not a claim that whole-route removal is absent."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/scheduler.py",
        target_weakness="Existing route removal has no stagnation-sensitive trigger.",
        expected_effect="Improve total_distance by scheduling whole-route removal better.",
        mechanism_changes=(
            MechanismChange(id="route_removal_trigger_variant", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.is_hard_block is False


def test_cvrp_provider_allows_negated_route_removal_missing_plus_route_reuse_absent() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The active solver already has diverse feasible seeds, route removal, "
            "Shaw/worst/random removal, regret repair, and VNS "
            "relocate/swap/Or-opt/tail exchange. This is materially different "
            "from the rejected route-removal premise because it does not claim "
            "whole-route destroy is missing; it adds cross-incumbent route reuse, "
            "a capability absent from single-solution ALNS neighborhoods."
        ),
        change_locus="solver_design",
        action="create_new",
        target_file="policies/baseline_modules/route_pool_recombination.py",
        target_weakness=(
            "Search lacks cross-incumbent route-pool recombination, not route "
            "removal."
        ),
        expected_effect="Improve total_distance via elite route reuse.",
        mechanism_changes=(
            MechanismChange(id="route_pool_recombination", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.failure_category != "premise_contradicted"


def test_cvrp_provider_allows_route_recombination_absence_referent_not_route_removal() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The active solver already has route removal and regret repair. "
            "What is absent is cross incumbent route-pool recombination that "
            "reuses elite complete routes across incumbents, so add a bounded "
            "route reuse module without claiming route removal is missing."
        ),
        change_locus="solver_design",
        action="create_new",
        target_file="policies/baseline_modules/route_pool_recombination.py",
        target_weakness="Cross-incumbent route reuse is absent.",
        expected_effect="Improve total_distance through route-pool recombination.",
        mechanism_changes=(
            MechanismChange(id="route_pool_recombination", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.failure_category != "premise_contradicted"


def test_cvrp_provider_still_blocks_true_missing_route_removal_claim() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The baseline lacks route removal, so add a whole-route destroy "
            "operator to remove entire routes."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Route removal is missing.",
        expected_effect="Improve search by adding route removal.",
        mechanism_changes=(
            MechanismChange(id="whole_route_removal_destroy", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is not None
    assert result.failure_category == "mechanism_premise_warning"
    assert result.mechanism == "route_removal"
    assert "lacks route removal" in result.contradicted_span


def test_cvrp_provider_does_not_hard_block_paired_regret_variant_report_case() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The active solver already has _regret2_insertion and "
            "_regret3_insertion. It lacks paired-regret repair that evaluates "
            "two removed customers jointly before calling the existing regret "
            "portfolio. Add paired_regret_repair as a candidate filtering and "
            "ordering variant, not as a new missing regret insertion operator."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Existing regret repair lacks paired-customer ordering.",
        expected_effect="Improve total_distance through better repair ordering.",
        mechanism_changes=(
            MechanismChange(id="paired_regret_repair", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.is_hard_block is False


def test_cvrp_provider_rejects_missing_removal_savings_claim_with_worst_reason() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The active baseline has no removal-savings destroy operator. "
            "Add a detour-cost removal capability for high-saving positions."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Removal savings destroy is missing.",
        expected_effect="Improve total_distance by removing high-saving customers.",
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is not None
    assert result.premise_check == "contradicted"
    assert result.failure_category == "mechanism_premise_warning"
    assert result.mechanism == "removal_savings_worst_removal"
    assert "removal-savings or detour-cost removal is missing" in result.reason
    rendered = " ".join([result.reason, *result.evidence])
    assert "_worst_removal" in rendered
    assert "cost_of_remove" in rendered
    assert "_shaw_removal" not in result.reason


def test_cvrp_provider_allows_reported_removal_savings_negated_claim() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add a slack-cluster removal destroy operator that chooses a "
            "high-load anchor route, estimates the load slack created by "
            "removing one or two expensive anchor customers, and then removes "
            "a bounded cluster of nearby customers from complementary routes "
            "whose demands can plausibly be exchanged into that slack before "
            "existing regret repair rebuilds the routes. It is materially "
            "different from existing random, savings-worst, Shaw related, and "
            "whole-route removal: the full destroy_repair.py shows no operator "
            "that targets route-pair load complementarity or residual-capacity "
            "exchange potential, while not claiming removal-savings ranking is "
            "missing."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness=(
            "Current destroy portfolio perturbs customers uniformly, by "
            "individual removal saving, by relatedness, or by whole route, "
            "but lacks a capacity-slack targeted route-pair destroy."
        ),
        expected_effect="Improve total_distance with a route-pair slack variant.",
        mechanism_changes=(
            MechanismChange(id="slack_cluster_removal", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.failure_category != "premise_contradicted"


@pytest.mark.parametrize(
    "disclaimer",
    [
        "not claiming removal-savings ranking is missing",
        "without claiming removal-savings ranking is missing",
        "rather than claiming removal-savings ranking is missing",
        "does not claim removal-savings ranking is missing",
        "not a missing removal-savings claim",
        "not a claim that removal-savings ranking is absent",
        "without claiming detour-cost removal is missing",
        "does not claim _worst_removal saving is missing",
    ],
)
def test_cvrp_provider_allows_removal_savings_negated_premise_variants(
    disclaimer: str,
) -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Existing savings-worst removal and _worst_removal already rank "
            "customers by removal saving with cost_of_remove. Add a route-pair "
            "slack cluster removal variant; no operator targets route-pair load "
            f"complementarity, while {disclaimer}."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness=(
            "Existing removal savings is active, but route-pair slack targeting "
            "is not represented."
        ),
        expected_effect="Improve total_distance with complementary-route removal.",
        mechanism_changes=(
            MechanismChange(id="slack_cluster_removal", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.failure_category != "premise_contradicted"


def test_cvrp_removal_savings_acknowledgement_helper_does_not_type_error() -> None:
    text = (
        "Removal savings from removal is already represented by the existing "
        "_worst_removal operator, so this proposes a route-pair slack variant "
        "rather than claiming removal-savings ranking is missing."
    )

    assert _acknowledges_existing_removal_savings_destroy(text)


def test_cvrp_provider_allows_existing_worst_removal_distinct_variant_claim() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Existing _worst_removal uses removal savings with cost_of_remove, "
            "but no operator targets route-pair load complementarity or residual "
            "capacity exchange potential. Propose a slack-cluster removal "
            "variant that uses route-pair capacity slack rather than another "
            "removal-savings ranking."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Removal savings exists; route-pair slack targeting does not.",
        expected_effect="Improve total_distance via a distinct destroy variant.",
        mechanism_changes=(
            MechanismChange(id="slack_cluster_removal", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.failure_category != "premise_contradicted"


def test_cvrp_provider_rejects_baseline_lacks_removal_savings_worst_removal() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The baseline lacks removal-savings worst removal. Add the missing "
            "detour-cost removal operator."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Removal-savings worst removal is missing.",
        expected_effect="Improve total_distance by adding removal-savings removal.",
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is not None
    assert result.failure_category == "mechanism_premise_warning"
    assert result.mechanism == "removal_savings_worst_removal"


def test_cvrp_provider_allows_position_cost_variant_acknowledging_worst_removal() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The current destroy portfolio lacks a mechanism that targets "
            "customers whose current position creates high insertion cost "
            "relative to their best alternative location. It already includes "
            "_worst_removal, which ranks customers by removal saving using "
            "cost_of_remove. "
            "However, it does not account for whether a cheaper best "
            "alternative insertion exists elsewhere. Add costly_position_removal "
            "that scores customers by insertion opportunity: best reinsertion "
            "cost in another route minus the removal saving, then repairs with "
            "existing regret insertion. This is an insertion-aware variant, not "
            "a claim that removal-savings removal is absent."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Destroy selection misses badly placed customers.",
        expected_effect="Improve total_distance by removing costly positions.",
        mechanism_changes=(
            MechanismChange(id="costly_position_removal", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.failure_category != "premise_contradicted"


def test_cvrp_provider_rejects_repeated_worst_removal_with_precise_reason() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Register a new _worst_removal clone that ranks customers by "
            "saving = -route.cost_of_remove(pos), removal savings, and detour "
            "cost before repair."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Need another worst-removal operator.",
        expected_effect="Improve total_distance by repeating worst removal.",
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is not None
    assert result.premise_check == "duplicate"
    assert result.failure_category == "duplicate_mechanism"
    assert result.result_kind == "duplicate_diagnostic"
    assert result.gate_action == "diagnostic"
    assert result.is_hard_block is False
    assert result.mechanism == "removal_savings_worst_removal"
    assert "removal-savings or detour-cost destroy operator" in result.reason
    assert "_worst_removal" in " ".join([result.reason, *result.evidence])
    assert "_shaw_removal" not in result.reason
