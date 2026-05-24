from __future__ import annotations

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
    assert result.failure_category == "premise_contradicted"
    assert result.mechanism == "regret_insertion_repair"
    assert result.variant_allowed is False
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
    assert result.failure_category == "premise_contradicted"
    assert result.mechanism == "removal_savings_worst_removal"
    assert "removal-savings or detour-cost removal is missing" in result.reason
    rendered = " ".join([result.reason, *result.evidence])
    assert "_worst_removal" in rendered
    assert "cost_of_remove" in rendered
    assert "_shaw_removal" not in result.reason


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
    assert result.mechanism == "removal_savings_worst_removal"
    assert "removal-savings or detour-cost destroy operator" in result.reason
    assert "_worst_removal" in " ".join([result.reason, *result.evidence])
    assert "_shaw_removal" not in result.reason
