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
                "_shaw_removal related proximity destroy removal distance demand route"
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
