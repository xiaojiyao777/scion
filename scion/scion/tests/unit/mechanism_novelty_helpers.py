from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scion.proposal.active_solver_snapshot import build_active_solver_snapshot
from scion.proposal.engine import _split_hypothesis_context
from scion.proposal.agentic_models import (
    AgenticProposalRequest,
    AgenticProposalStatus,
    AgenticTerminationReason,
)
from scion.proposal.agentic_session import AgenticProposalSession
from scion.proposal.mechanism_novelty import MechanismNoveltyGate
from scion.proposal.tools import ProposalToolRegistry
from scion.tests.unit.test_agentic_proposal_tools_helpers import (
    FakeCreative,
    FileAgenticSessionArtifactStore,
    HypothesisProposal,
    PatchProposal,
    _cvrp_context_with_champion,
    _valid_hypothesis_payload,
)


FALSE_PREMISES = (
    (
        "nearest_neighbor_only",
        (
            "The current baseline only builds a single nearest-neighbor seed "
            "before search; replace it with sweep and Clarke-Wright seeding."
        ),
        "construction_seed_strategy",
    ),
    (
        "uniform_adaptive_weights",
        (
            "Adaptive operator weights remain uniform and non-adaptive "
            "throughout the run; make them learn from accepted moves."
        ),
        "adaptive_operator_weights",
    ),
    (
        "missing_cross_route_or_opt",
        (
            "The active solver is missing cross-route Or-opt 2/3, so add "
            "those cross-route route relocation neighborhoods."
        ),
        "cross_route_or_opt_2_3",
    ),
    (
        "missing_or_opt_1",
        (
            "The active solver lacks Or-opt-1 single customer relocation; "
            "add that VNS neighborhood."
        ),
        "or_opt_1_relocation",
    ),
    (
        "missing_inter_route_or_opt_segment_relocation",
        (
            "The active solver lacks inter-route Or-opt segment relocation; "
            "add an NN-filtered cross-route segment relocation neighborhood."
        ),
        "cross_route_or_opt_2_3",
    ),
    (
        "missing_intra_two_opt",
        (
            "The current VNS has cross-route Or-opt, but it lacks intra-route "
            "2-opt segment reversal; add intra_two_opt."
        ),
        "intra_two_opt_reversal",
    ),
    (
        "missing_shaw_related_removal",
        (
            "The active solver has no proximity-cluster destroy removal, so add "
            "a seed-based related removal operator using distance and demand."
        ),
        "shaw_related_removal",
    ),
    (
        "missing_random_removal_destroy",
        (
            "The active destroy portfolio lacks random customer removal, so add "
            "a random removal destroy operator."
        ),
        "random_removal_destroy",
    ),
    (
        "missing_route_removal",
        (
            "The active destroy portfolio has no whole route removal operator, "
            "so add route removal."
        ),
        "route_removal",
    ),
    (
        "missing_regret_repair",
        (
            "The active repair portfolio lacks regret-2/regret-3 insertion "
            "repair, so add regret insertion."
        ),
        "regret_insertion_repair",
    ),
    (
        "missing_cross_route_tail_exchange",
        (
            "The active solver lacks cross-route tail swap / suffix exchange, "
            "so add that neighborhood to local search."
        ),
        "cross_route_tail_exchange",
    ),
    (
        "unreachable_feasibility_crossing",
        (
            "Reset adaptive weights on the first infeasible-to-feasible "
            "feasibility crossing in the current search state."
        ),
        "feasibility_crossing",
    ),
    (
        "unproven_construction_route_merge",
        (
            "The current construction can produce more routes than route_limit, "
            "leaving ALNS with fleet_violation to repair. Add "
            "construction_route_merge while len(routes) > route_limit."
        ),
        "route_limit_fleet_repair",
    ),
)

MECHANISM_FACT_IDS = {
    "construction_seed_strategy": ("cvrp.construction.diverse_feasible_seed",),
    "adaptive_operator_weights": ("cvrp.acceptance.adaptive_operator_weights",),
    "cross_route_or_opt_2_3": ("cvrp.local_search.cross_route_or_opt_2_3",),
    "or_opt_1_relocation": ("cvrp.local_search.or_opt_1_relocation",),
    "intra_two_opt_reversal": ("cvrp.local_search.intra_two_opt_reversal",),
    "shaw_related_removal": ("cvrp.destroy_repair.shaw_related_removal",),
    "random_removal_destroy": ("cvrp.destroy_repair.random_removal_destroy",),
    "route_removal": ("cvrp.destroy_repair.route_removal",),
    "regret_insertion_repair": (
        "cvrp.destroy_repair.regret_insertion_repair",
    ),
    "cross_route_tail_exchange": ("cvrp.local_search.cross_route_tail_exchange",),
    "feasibility_crossing": ("cvrp.search_state.starts_feasible_rejects_infeasible",),
    "route_limit_fleet_repair": (
        "cvrp.search_state.guards_route_limit",
        "cvrp.search_state.starts_feasible_rejects_infeasible",
    ),
}


def _solver_design_hypothesis(text: str) -> HypothesisProposal:
    return HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_modules/local_search.py",
            hypothesis_text=text,
            target_weakness=text,
            expected_effect="Improve the active solver design.",
        )
    )


class SequentialHypothesisCreative(FakeCreative):
    def __init__(self, hypotheses: list[HypothesisProposal]) -> None:
        super().__init__(hypothesis=hypotheses[-1])
        self.hypotheses = list(hypotheses)

    def generate_hypothesis(self, context):
        self.hypothesis_contexts.append(dict(context))
        if not self.hypotheses:
            return self.hypothesis
        return self.hypotheses.pop(0)
