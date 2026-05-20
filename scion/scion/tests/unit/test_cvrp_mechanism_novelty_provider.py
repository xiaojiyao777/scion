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
                "_two_opt_star cross-route suffix tail exchange",
            ],
            "destroy_repair": [
                "_worst_removal ranks removal saving with "
                "saving = -route.cost_of_remove(pos)",
                "_shaw_removal related proximity destroy removal distance demand route",
            ],
            "alns_loop": [
                "starts from a feasible construction",
                "rejects infeasible route-cap-violating candidates",
            ],
        },
        "source_digest": {"snapshot_digest": "snapshot-test-digest"},
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
    assert result.snapshot_digest == "snapshot-test-digest"


def test_cvrp_mechanism_novelty_provider_allows_when_capability_not_in_snapshot() -> None:
    result = CvrpMechanismNoveltyProvider().evaluate_mechanism_novelty(
        _hypothesis(
            "Add cross-route Or-opt 2 and 3 as new neighborhoods to local search."
        ),
        active_solver_snapshot={"mechanism_summary": {"local_search": []}},
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
    rendered = " ".join([result.reason, *result.evidence])
    assert "_worst_removal" in rendered
    assert "cost_of_remove" in rendered
    assert "removal saving" in rendered
    assert result.mechanism != "shaw_related_removal"


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
