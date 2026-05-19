"""CVRP mechanism novelty provider exposed through the problem adapter."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from scion.core.models import HypothesisProposal
from scion.proposal.mechanism_novelty import MechanismNoveltyResult
from scion.proposal.tools import ProposalObservation

from scion.problems.cvrp.mechanism_novelty.acceptance import (
    _claims_weights_non_adaptive,
)
from scion.problems.cvrp.mechanism_novelty.construction import (
    _claims_nearest_neighbor_only,
)
from scion.problems.cvrp.mechanism_novelty.destroy_repair import (
    _claims_missing_shaw_related_removal,
    _duplicates_shaw_related_removal,
)
from scion.problems.cvrp.mechanism_novelty.hypothesis import _hypothesis_text
from scion.problems.cvrp.mechanism_novelty.local_search import (
    _claims_missing_cross_route_tail_exchange,
    _claims_missing_or_opt_2_3,
    _duplicates_cross_route_tail_exchange,
    _duplicates_or_opt_2_3,
)
from scion.problems.cvrp.mechanism_novelty.route_limit import (
    _claims_unproven_route_limit_or_fleet_repair,
    _has_explicit_route_limit_runtime_evidence,
)
from scion.problems.cvrp.mechanism_novelty.search_state import (
    _claims_unreachable_feasibility_crossing,
)
from scion.problems.cvrp.mechanism_novelty.snapshot import (
    _active_solver_snapshot_from_observations,
    _facts_from_snapshot,
)


class CvrpMechanismNoveltyProvider:
    """Block only explicit duplicate or contradicted CVRP solver premises."""

    def evaluate_mechanism_novelty(
        self,
        hypothesis: HypothesisProposal,
        *,
        active_solver_snapshot: Mapping[str, Any] | None = None,
        observations: Sequence[ProposalObservation] = (),
        context: Any | None = None,
    ) -> MechanismNoveltyResult | None:
        if str(hypothesis.change_locus or "").strip() != "solver_design":
            return None
        snapshot = active_solver_snapshot or _active_solver_snapshot_from_observations(
            observations
        )
        if not isinstance(snapshot, Mapping):
            return None
        facts = _facts_from_snapshot(snapshot)
        text = _hypothesis_text(hypothesis)

        if facts.has_diverse_construction and _claims_nearest_neighbor_only(text):
            return MechanismNoveltyResult(
                premise_check="contradicted",
                failure_category="premise_contradicted",
                mechanism="construction_seed_strategy",
                reason=(
                    "Hypothesis claims the active baseline uses only a single "
                    "nearest-neighbor seed, but the active solver snapshot shows "
                    "sweep construction, Clarke-Wright savings, capacity-balanced "
                    "repair, and nearest-neighbor only as fallback."
                ),
                evidence=facts.construction_evidence,
                snapshot_digest=facts.snapshot_digest,
            )

        if facts.has_adaptive_weights and _claims_weights_non_adaptive(text):
            return MechanismNoveltyResult(
                premise_check="contradicted",
                failure_category="premise_contradicted",
                mechanism="adaptive_operator_weights",
                reason=(
                    "Hypothesis claims operator weights are uniform or "
                    "non-adaptive throughout, but the active solver snapshot "
                    "shows _AdaptiveWeights record/update behavior."
                ),
                evidence=facts.adaptive_weight_evidence,
                snapshot_digest=facts.snapshot_digest,
            )

        if facts.has_cross_route_or_opt_2_3 and _claims_missing_or_opt_2_3(text):
            return MechanismNoveltyResult(
                premise_check="contradicted",
                failure_category="premise_contradicted",
                mechanism="cross_route_or_opt_2_3",
                reason=(
                    "Hypothesis claims inter-route/cross-route Or-opt segment "
                    "relocation is missing, but the active solver snapshot "
                    "shows _or_opt_1/_or_opt_2/_or_opt_3 and _or_opt skipping "
                    "same-route destinations, so length-2/3 cross-route "
                    "segment relocation already exists."
                ),
                evidence=facts.or_opt_evidence,
                snapshot_digest=facts.snapshot_digest,
            )

        if facts.has_cross_route_or_opt_2_3 and _duplicates_or_opt_2_3(text):
            return MechanismNoveltyResult(
                premise_check="duplicate",
                failure_category="duplicate_mechanism",
                mechanism="cross_route_or_opt_2_3",
                reason=(
                    "Hypothesis proposes adding inter-route/cross-route Or-opt "
                    "segment relocation as a new mechanism, but the active "
                    "solver snapshot already contains _or_opt_1/_or_opt_2/"
                    "_or_opt_3 cross-route segment relocation."
                ),
                evidence=facts.or_opt_evidence,
                snapshot_digest=facts.snapshot_digest,
            )

        if facts.has_cross_route_tail_exchange and _claims_missing_cross_route_tail_exchange(
            text
        ):
            return MechanismNoveltyResult(
                premise_check="contradicted",
                failure_category="premise_contradicted",
                mechanism="cross_route_tail_exchange",
                reason=(
                    "Hypothesis claims cross-route suffix/tail exchange is "
                    "missing, but the active solver snapshot shows "
                    "_two_opt_star as a cross-route suffix/tail exchange "
                    "neighborhood."
                ),
                evidence=facts.tail_exchange_evidence,
                snapshot_digest=facts.snapshot_digest,
            )

        if facts.has_cross_route_tail_exchange and _duplicates_cross_route_tail_exchange(
            text
        ):
            return MechanismNoveltyResult(
                premise_check="duplicate",
                failure_category="duplicate_mechanism",
                mechanism="cross_route_tail_exchange",
                reason=(
                    "Hypothesis proposes adding cross-route suffix/tail "
                    "exchange as a new mechanism, but the active solver "
                    "already contains _two_opt_star."
                ),
                evidence=facts.tail_exchange_evidence,
                snapshot_digest=facts.snapshot_digest,
            )

        if facts.has_shaw_related_removal and _claims_missing_shaw_related_removal(text):
            return MechanismNoveltyResult(
                premise_check="contradicted",
                failure_category="premise_contradicted",
                mechanism="shaw_related_removal",
                reason=(
                    "Hypothesis claims related/proximity-cluster destroy removal "
                    "is missing, but the active solver snapshot shows "
                    "_shaw_removal: a seed-based destroy operator using "
                    "distance, demand, and original-route relatedness."
                ),
                evidence=facts.shaw_related_evidence,
                snapshot_digest=facts.snapshot_digest,
            )

        if facts.has_shaw_related_removal and _duplicates_shaw_related_removal(text):
            return MechanismNoveltyResult(
                premise_check="duplicate",
                failure_category="duplicate_mechanism",
                mechanism="shaw_related_removal",
                reason=(
                    "Hypothesis proposes adding related/proximity-cluster "
                    "removal as a new destroy capability, but the active solver "
                    "already contains _shaw_removal with distance, demand, and "
                    "route relatedness criteria."
                ),
                evidence=facts.shaw_related_evidence,
                snapshot_digest=facts.snapshot_digest,
            )

        if (
            facts.guards_route_limit_search_state
            and _claims_unproven_route_limit_or_fleet_repair(text)
            and not _has_explicit_route_limit_runtime_evidence(
                observations,
                context=context,
            )
        ):
            return MechanismNoveltyResult(
                premise_check="contradicted",
                failure_category="premise_contradicted",
                mechanism="route_limit_fleet_repair",
                reason=(
                    "Hypothesis treats route-limit excess or positive "
                    "fleet_violation as the default construction/ALNS state, "
                    "but the active solver snapshot shows route-limit guarded "
                    "construction and rejection of route-cap-violating search "
                    "candidates. Target this mechanism only when prior "
                    "screening/runtime feedback explicitly shows positive "
                    "fleet_violation or route-limit excess."
                ),
                evidence=facts.route_limit_evidence,
                snapshot_digest=facts.snapshot_digest,
            )

        if (
            facts.starts_feasible_rejects_infeasible
            and _claims_unreachable_feasibility_crossing(text)
        ):
            return MechanismNoveltyResult(
                premise_check="contradicted",
                failure_category="premise_contradicted",
                mechanism="feasibility_crossing",
                reason=(
                    "Hypothesis relies on an infeasible-to-feasible or "
                    "fleet-violation feasibility crossing, but the active "
                    "solver starts from a feasible construction and rejects "
                    "infeasible or route-cap-violating candidates before they "
                    "become current search states."
                ),
                evidence=facts.feasible_search_evidence,
                snapshot_digest=facts.snapshot_digest,
            )

        return None
