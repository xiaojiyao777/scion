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
    assert result.result_kind == "duplicate_diagnostic"
    assert result.gate_action == "diagnostic"
    assert result.is_hard_block is False
    assert result.mechanism == "cross_route_or_opt_2_3"
    assert result.snapshot_digest == "snapshot-test-digest"
    assert result.fact_packet_digest == "fact-packet-test-digest"
    assert result.fact_ids == ("cvrp.local_search.cross_route_or_opt_2_3",)


def test_cvrp_mechanism_novelty_rejection_keeps_distinct_source_and_packet_digests() -> None:
    hypothesis = _hypothesis(
        "Add cross-route Or-opt 2 and 3 as new neighborhoods to local search."
    )
    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is not None
    diagnostic = result.to_diagnostic(hypothesis)
    assert diagnostic["snapshot_digest"] == "snapshot-test-digest"
    assert diagnostic["fact_packet_digest"] == "fact-packet-test-digest"
    assert diagnostic["result_kind"] == "duplicate_diagnostic"
    assert diagnostic["gate_action"] == "diagnostic"
    rendered = render_negative_fact_block(structured_rejections=(diagnostic,))
    assert "snapshot_digest=snapshot-test-digest" in rendered
    assert "fact_packet_digest=fact-packet-test-digest" in rendered


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
    assert result.failure_category == "mechanism_premise_warning"
    assert result.mechanism == "route_limit_fleet_repair"
    assert "explicitly shows positive fleet_violation" in result.reason
    assert result.evidence
    assert "cvrp.search_state.guards_route_limit" in result.contradicted_fact_ids
    assert "cvrp.search_state.starts_feasible_rejects_infeasible" in (
        result.contradicted_fact_ids
    )
    assert result.variant_allowed is None
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


def test_near_field_angle_sector_destroy_is_guidance_not_hard_premise_block() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add angle_sector_removal as a depot-centered geographic wedge "
            "destroy variant. It differs from existing random, worst, Shaw, "
            "and whole-route removal because it removes customers by polar "
            "sector without relying on current-route relatedness or removal "
            "savings."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
        target_weakness="Destroy portfolio lacks sector-shaped spatial pressure.",
        expected_effect="Improve total_distance on clustered routes.",
        mechanism_changes=(
            MechanismChange(id="angle_sector_removal", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.failure_category != "premise_contradicted"


def test_explicit_missing_removal_savings_claim_still_hard_blocks() -> None:
    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        _hypothesis(
            "The active destroy portfolio lacks removal savings / detour-cost "
            "removal. Add a removal-savings destroy operator."
        ),
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is not None
    assert result.premise_check == "contradicted"
    assert result.failure_category == "mechanism_premise_warning"
    assert result.mechanism == "removal_savings_worst_removal"
    assert result.gate_action == "diagnostic"


def test_near_field_route_merge_compaction_is_not_route_removal_missing_claim() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Create route_merge as a route-pair merge/compaction pass for "
            "capacity-compatible routes. The current portfolio already has "
            "whole-route removal; this proposal targets pair compaction and "
            "reinsertion quality, not a claim that whole-route removal is "
            "missing."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/route_merge.py",
        target_weakness="Route-pair compaction may improve total_distance.",
        expected_effect="Reduce total_distance while preserving route caps.",
        mechanism_changes=(MechanismChange(id="route_merge", change_type="add"),),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.failure_category != "premise_contradicted"


def test_giant_split_decoder_feasible_seed_variant_is_not_route_limit_repair_block() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add giant_split_decoder as a construction seed variant: build a "
            "giant customer tour, split it into capacity-feasible routes under "
            "the existing route limit, and keep the incumbent when no feasible "
            "split improves total_distance. This is a feasible seed-quality "
            "change, not repair of an absent route-limit guard."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/construction.py",
        target_weakness="Construction seed ordering leaves avoidable distance.",
        expected_effect="Improve total_distance without increasing fleet_violation.",
        mechanism_changes=(
            MechanismChange(id="giant_split_decoder", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.failure_category != "premise_contradicted"


def test_cvrp_route_limit_gate_allows_feasibility_filter_variant_text() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add a route-limit-aware feasibility filter for candidate merges: "
            "reject route-cap violating candidates and skip moves that would "
            "produce more routes than route_limit. This targets total_distance "
            "quality while preserving the existing feasibility guard."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/construction.py",
        target_weakness="Seed quality leaves avoidable distance.",
        expected_effect="Improve total_distance without changing route-limit guards.",
        mechanism_changes=(
            MechanismChange(id="route_limit_feasibility_filter", change_type="add"),
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


def test_cvrp_route_limit_gate_allows_rejected_route_limit_excess_clause() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Add a giant-tour split construction seed that remains capacity "
            "feasible and route-limit aware; it starts and remains feasible "
            "rather than accepting route-limit excess."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/construction.py",
        target_weakness=(
            "Seed construction leaves avoidable total_distance while already "
            "guarding route count feasibility."
        ),
        expected_effect=(
            "Reduce total_distance by changing construction ordering without "
            "changing route-limit guards."
        ),
        mechanism_changes=(
            MechanismChange(id="giant_tour_split_seed", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None


def test_cvrp_route_limit_gate_allows_route_limit_rejection_variants() -> None:
    variants = [
        "instead of accepting route-limit excess",
        "avoids accepting route-limit excess",
        "avoid route-limit excess",
        "prevent route-limit excess",
        "reject route-limit excess",
        "skip route-limit excess",
        "disallow route-limit excess",
    ]

    for phrase in variants:
        hypothesis = HypothesisProposal(
            hypothesis_text=(
                "Add a feasible construction ordering variant that targets "
                f"total_distance and will {phrase} while preserving the "
                "route-limit guard."
            ),
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_modules/construction.py",
            target_weakness="Feasible seed quality leaves avoidable distance.",
            expected_effect="Improve total_distance without allowing fleet excess.",
            mechanism_changes=(
                MechanismChange(id="feasible_route_ordering", change_type="add"),
            ),
        )

        result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
            hypothesis,
            active_solver_snapshot=_active_capability_snapshot(),
        )

        assert result is None, phrase


def test_cvrp_route_limit_gate_allows_exact_protective_premise_fixtures() -> None:
    phrases = [
        "rather than accepting route-limit excess",
        "instead of accepting route-limit excess",
        "avoid accepting fleet violation",
        "instead of allowing infeasible states",
        "candidate routes exceed route_limit should fail before promotion",
    ]

    for phrase in phrases:
        hypothesis = HypothesisProposal(
            hypothesis_text=(
                "Add a capacity-compatible construction ordering variant that "
                f"{phrase}; it only targets total_distance and preserves the "
                "existing route-limit guard."
            ),
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_modules/construction.py",
            target_weakness="Feasible seed ordering leaves avoidable distance.",
            expected_effect="Improve total_distance while preserving feasibility.",
            mechanism_changes=(
                MechanismChange(id="distance_ordering_fixture", change_type="add"),
            ),
        )

        result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
            hypothesis,
            active_solver_snapshot=_active_capability_snapshot(),
        )

        assert result is None, phrase


def test_cvrp_route_limit_gate_allows_noop_more_routes_than_incumbent_guard() -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Recent screening shows late-stage local-search, destroy, "
            "compaction, and tabu variants either saturated the full runtime "
            "or produced no decisive wins, while fleet_violation is already "
            "stable under the active route-limit guards; the missing capability "
            "is a stronger but bounded feasible starting basin rather than "
            "another expensive post-construction neighborhood. Modify "
            "construction.py to add multi_start_insertion_seed: build up to "
            "four deterministic/randomized sector starts from the existing "
            "customer set, then complete each route set with capacity-feasible "
            "cheapest insertion scored by insertion delta plus a mild "
            "load-balance penalty, and select the lexicographically best seed "
            "before the existing VNS/ALNS pipeline. It no-ops to the current "
            "construction result when route-limit-feasible insertion cannot "
            "place every customer, the constructed seed has more routes than "
            "the incumbent seed, remaining construction budget is below "
            "reserve, or no candidate seed has a better objective key, "
            "preserving hard capacity feasibility and fleet_violation."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/construction.py",
        target_weakness="Feasible seed construction quality leaves avoidable distance.",
        expected_effect="Improve total_distance without changing route-limit guards.",
        no_op_condition=(
            "No-op when the candidate cannot place every customer or has more "
            "routes than the incumbent seed."
        ),
        mechanism_changes=(
            MechanismChange(id="multi_start_insertion_seed", change_type="add"),
        ),
    )

    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        hypothesis,
        active_solver_snapshot=_active_capability_snapshot(),
    )

    assert result is None or result.mechanism != "route_limit_fleet_repair"
    assert result is None or result.failure_category != "premise_contradicted"


def test_cvrp_route_limit_gate_blocks_exact_positive_state_premises() -> None:
    phrases = [
        "The baseline accepts route-limit excess as the construction state.",
        "The current solver uses positive fleet_violation as a search state.",
        "The default path permits infeasible current states before repair.",
    ]

    for phrase in phrases:
        hypothesis = HypothesisProposal(
            hypothesis_text=(
                f"{phrase} Add a route repair phase that converts that state "
                "into a feasible incumbent."
            ),
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_modules/scheduler.py",
            target_weakness="Route feasibility is assumed to be repaired later.",
            expected_effect="Repair route feasibility before distance search.",
            mechanism_changes=(
                MechanismChange(id="positive_route_state_fixture", change_type="add"),
            ),
        )

        result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
            hypothesis,
            active_solver_snapshot=_active_capability_snapshot(),
        )

        assert result is not None, phrase
        assert result.failure_category == "mechanism_premise_warning"
        assert result.mechanism == "route_limit_fleet_repair"
        assert result.gate_action == "diagnostic"


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
    assert result.variant_allowed is None
    assert "positive fleet violation" in result.contradicted_span
