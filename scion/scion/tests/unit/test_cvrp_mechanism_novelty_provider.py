from __future__ import annotations

from scion.core.models import HypothesisProposal, MechanismChange
from scion.problems.cvrp.mechanism_novelty import CvrpMechanismNoveltyProvider
from scion.problems.cvrp.mechanism_novelty.provider import (
    CvrpMechanismNoveltyProvider as DirectCvrpMechanismNoveltyProvider,
)
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


def test_cvrp_mechanism_novelty_provider_import_facade_matches_implementation() -> None:
    assert CvrpMechanismNoveltyProvider is DirectCvrpMechanismNoveltyProvider


def test_cvrp_mechanism_novelty_provider_blocks_duplicate_baseline_capability() -> None:
    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        _hypothesis(
            "Add cross-route Or-opt 2 and 3 as new neighborhoods to local search."
        ),
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is not None
    assert result.premise_check == "duplicate"
    assert result.failure_category == "duplicate_mechanism"
    assert result.mechanism == "cross_route_or_opt_2_3"
    assert result.snapshot_digest == "fact-packet-test-digest"
    assert result.fact_packet_digest == "fact-packet-test-digest"
    assert result.fact_ids == ("cvrp.local_search.cross_route_or_opt_2_3",)


def test_cvrp_mechanism_novelty_provider_allows_when_capability_not_in_snapshot() -> None:
    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        _hypothesis(
            "Add cross-route Or-opt 2 and 3 as new neighborhoods to local search."
        ),
        active_solver_snapshot={"mechanism_summary": {"local_search": []}},
    )

    assert result is None


def test_cvrp_mechanism_novelty_provider_does_not_use_private_summary_without_fact_packet() -> None:
    snapshot = dict(_active_capability_snapshot())
    snapshot.pop("active_algorithm_facts")

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        _hypothesis(
            "The active solver lacks cross-route Or-opt segment relocation."
        ),
        active_solver_snapshot=snapshot,
    )

    assert result is None


def test_cvrp_mechanism_novelty_provider_uses_latest_snapshot_observation() -> None:
    observations = (
        ProposalObservation(
            observation_id="obs-old",
            session_id="session",
            tool_name="context.read_active_solver_design",
            tool_call_id="call-old",
            observation_type="tool_result",
            summary="old",
            structured_payload={"mechanism_summary": {"local_search": []}},
        ),
        ProposalObservation(
            observation_id="obs-new",
            session_id="session",
            tool_name="context.read_active_solver_design",
            tool_call_id="call-new",
            observation_type="tool_result",
            summary="new",
            structured_payload=_active_capability_snapshot(),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        _hypothesis(
            "The active solver lacks cross-route tail swap / suffix exchange."
        ),
        observations=observations,
    )

    assert result is not None
    assert result.premise_check == "contradicted"
    assert result.mechanism == "cross_route_tail_exchange"
    assert result.contradicted_fact_ids == (
        "cvrp.local_search.cross_route_tail_exchange",
    )
    assert result.fact_packet_digest == "fact-packet-test-digest"
    assert result.contradicted_span
    assert result.matched_span == result.contradicted_span


def test_cvrp_mechanism_novelty_provider_blocks_unproven_construction_route_merge() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The current construction can produce more routes than the route_limit, "
            "leaving ALNS with a fleet_violation deficit to repair. Add a "
            "post-construction greedy route merge that runs while "
            "len(routes) > route_limit."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/construction.py",
        target_weakness=(
            "Initial construction frequently produces route_limit excess and "
            "positive fleet_violation."
        ),
        expected_effect="Reduce solver_algorithm_fleet_violation before ALNS.",
        no_op_condition="Skip if len(routes) <= route_limit.",
        mechanism_changes=(
            MechanismChange(id="construction_route_merge", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is not None
    assert result.premise_check == "contradicted"
    assert result.failure_category == "premise_contradicted"
    assert result.mechanism == "route_limit_fleet_repair"
    assert "explicitly shows positive fleet_violation" in result.reason
    assert result.evidence
    assert "cvrp.search_state.guards_route_limit" in result.contradicted_fact_ids
    assert "cvrp.search_state.starts_feasible_rejects_infeasible" in (
        result.contradicted_fact_ids
    )
    assert result.variant_allowed is False
    assert result.contradicted_span
    assert result.matched_span == result.contradicted_span
    assert "Allowed variant" in (result.allowed_variant_guidance or "")


def test_cvrp_mechanism_novelty_provider_allows_route_limit_repair_with_runtime_evidence() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add construction_route_merge because prior runtime feedback shows "
            "len(routes) > route_limit after construction."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/construction.py",
        target_weakness="Observed positive fleet_violation after construction.",
        expected_effect="Reduce route-limit excess.",
        mechanism_changes=(
            MechanismChange(id="construction_route_merge", change_type="add"),
        ),
    )
    observations = (
        ProposalObservation(
            observation_id="runtime-1",
            session_id="session",
            tool_name="feedback.query_runtime",
            tool_call_id="call-runtime",
            observation_type="runtime_feedback",
            summary="Returned runtime feedback.",
            structured_payload={
                "runtime_feedback": (
                    "screening evidence: solver_algorithm_fleet_violation=2 "
                    "on candidate construction smoke"
                )
            },
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
        observations=observations,
    )

    assert result is None


def test_cvrp_mechanism_novelty_provider_allows_distance_stagnation_escalation() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The current ALNS destroy/repair loop uses a fixed destroy ratio "
            "regardless of solution quality plateau length. When the search "
            "stagnates, small perturbations are insufficient to escape local "
            "optima. Add perturbation intensity escalation in scheduler.py: "
            "after several ALNS iterations without best-solution improvement, "
            "temporarily double the destroy ratio and removed customer count "
            "ceiling, then reset on any best improvement. The expected effect "
            "is escaping plateau regions and discovering shorter total_distance "
            "solutions while fleet_violation remains zero."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/scheduler.py",
        target_weakness=(
            "Fixed destroy ratio causes total-distance stagnation on plateau "
            "regions while preserving fleet feasibility."
        ),
        expected_effect=(
            "Increase solver_algorithm_best_improving_moves and reduce "
            "solver_algorithm_total_distance without increasing fleet_violation."
        ),
        novelty_signature={
            "predicted_direction": "distance_stagnation_escalation",
            "target_objectives": ["total_distance"],
        },
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_route_limit_gate_allows_distance_and_repair_ordering_targets() -> None:
    cases = [
        (
            "Adaptive destroy size should increase after total_distance stagnation "
            "while preserving fleet_violation and route count as a protected constraint."
        ),
        (
            "Cluster regret repair should improve insertion ordering for "
            "total_distance; keep the capacity feasibility guard and route "
            "feasibility guard unchanged."
        ),
        (
            "Or-opt chain repair should reorder segment repair ordering for "
            "shorter total_distance without increasing fleet_violation."
        ),
        (
            "Large-neighborhood segment repair should target total_distance and "
            "leave route feasibility guard behavior intact."
        ),
        (
            "Nearest-neighbor-biased repair should reduce total_distance while "
            "fleet_violation remains zero."
        ),
    ]

    for text in cases:
        hypothesis = HypothesisProposal(
            hypothesis_text=text,
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_modules/destroy_repair.py",
            target_weakness=text,
            expected_effect="Improve total_distance while preserving constraints.",
        )

        result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
            hypothesis,
            active_solver_snapshot=_active_capability_snapshot(),
        )

        assert result is None, text


def test_cvrp_route_limit_gate_allows_feasible_route_merge_quality_variant() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add a feasible construction route merge seed pass that merges only "
            "capacity-compatible routes to reduce total_distance while preserving "
            "fleet_violation at zero and skipping any route-limit violating merge."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/construction.py",
        target_weakness="Construction seed quality leaves avoidable distance.",
        expected_effect="Reduce total_distance without changing route-limit guards.",
        mechanism_changes=(
            MechanismChange(id="feasible_route_merge_seed", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_route_limit_gate_ignores_risk_mitigation_text() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add randomized savings construction for shorter total_distance "
            "while preserving feasible seed construction."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/construction.py",
        target_weakness="Seed quality leaves avoidable distance.",
        expected_effect="Improve total_distance.",
        risk_to_higher_priority=(
            "Risk: randomized savings could produce more routes than "
            "route_limit, so keep the route-limit guard and reject route-cap "
            "violating candidates."
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_mechanism_novelty_provider_blocks_positive_fleet_violation_repair() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "The current ALNS starts with positive fleet_violation after "
            "construction and must repair fleet_violation to zero before "
            "distance can improve."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/scheduler.py",
        target_weakness="Positive fleet_violation remains in the current search state.",
        expected_effect="Reduce fleet_violation before optimizing distance.",
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is not None
    assert result.premise_check == "contradicted"
    assert result.mechanism == "route_limit_fleet_repair"
    assert "cvrp.search_state.guards_route_limit" in result.contradicted_fact_ids
    assert result.variant_allowed is False
    assert "positive fleet violation" in result.contradicted_span


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


def test_cvrp_mechanism_novelty_provider_blocks_removal_savings_duplicate_precisely() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add a _savings_removal destroy heuristic that ranks customers by "
            "removal savings and geometric detour cost using cost_of_remove, "
            "then registers it as a new destroy operator. This capability is "
            "absent because _shaw_removal uses proximity and _worst_removal "
            "does not target savings from removal."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="The destroy pool lacks removal-savings targeting.",
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
        target_weakness="Removal savings destroy is missing.",
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


def test_cvrp_provider_allows_random_removal_near_cluster_terms() -> None:
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
