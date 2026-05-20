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
    _claims_missing_removal_savings_destroy,
    _claims_missing_regret_insertion_repair,
    _claims_missing_route_removal,
    _claims_missing_shaw_related_removal,
    _duplicates_removal_savings_destroy,
    _duplicates_regret_insertion_repair,
    _duplicates_route_removal,
    _duplicates_shaw_related_removal,
)
from scion.problems.cvrp.mechanism_novelty.hypothesis import _hypothesis_text
from scion.problems.cvrp.mechanism_novelty.local_search import (
    _claims_missing_cross_route_tail_exchange,
    _claims_missing_or_opt_1,
    _claims_missing_or_opt_2_3,
    _duplicates_cross_route_tail_exchange,
    _duplicates_or_opt_1,
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

_CONSTRUCTION_FACT = "cvrp.construction.diverse_feasible_seed"
_ADAPTIVE_WEIGHTS_FACT = "cvrp.acceptance.adaptive_operator_weights"
_OR_OPT_FACT = "cvrp.local_search.cross_route_or_opt_2_3"
_OR_OPT_1_FACT = "cvrp.local_search.or_opt_1_relocation"
_TAIL_EXCHANGE_FACT = "cvrp.local_search.cross_route_tail_exchange"
_SHAW_RELATED_FACT = "cvrp.destroy_repair.shaw_related_removal"
_ROUTE_REMOVAL_FACT = "cvrp.destroy_repair.route_removal"
_REMOVAL_SAVINGS_FACT = "cvrp.destroy_repair.removal_savings_worst_removal"
_REGRET_INSERTION_FACT = "cvrp.destroy_repair.regret_insertion_repair"
_STARTS_FEASIBLE_FACT = "cvrp.search_state.starts_feasible_rejects_infeasible"
_ROUTE_LIMIT_FACT = "cvrp.search_state.guards_route_limit"


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
        if not facts.fact_packet_available:
            return None
        text = _hypothesis_text(hypothesis)

        if facts.has_diverse_construction and _claims_nearest_neighbor_only(text):
            return _result(
                facts,
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
                fact_ids=(_CONSTRUCTION_FACT,),
            )

        if facts.has_adaptive_weights and _claims_weights_non_adaptive(text):
            return _result(
                facts,
                premise_check="contradicted",
                failure_category="premise_contradicted",
                mechanism="adaptive_operator_weights",
                reason=(
                    "Hypothesis claims operator weights are uniform or "
                    "non-adaptive throughout, but the active solver snapshot "
                    "shows _AdaptiveWeights record/update behavior."
                ),
                evidence=facts.adaptive_weight_evidence,
                fact_ids=(_ADAPTIVE_WEIGHTS_FACT,),
            )

        if facts.has_cross_route_or_opt_2_3 and _claims_missing_or_opt_2_3(text):
            return _result(
                facts,
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
                fact_ids=(_OR_OPT_FACT,),
            )

        if facts.has_cross_route_or_opt_2_3 and _duplicates_or_opt_2_3(text):
            return _result(
                facts,
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
                fact_ids=(_OR_OPT_FACT,),
            )

        if facts.has_or_opt_1_relocation and _claims_missing_or_opt_1(text):
            return _result(
                facts,
                premise_check="contradicted",
                failure_category="premise_contradicted",
                mechanism="or_opt_1_relocation",
                reason=(
                    "Hypothesis claims single-customer Or-opt / Or-opt-1 "
                    "relocation is missing, but the active solver snapshot "
                    "shows _or_opt_1 registered in the VNS operator list."
                ),
                evidence=facts.or_opt_1_evidence,
                fact_ids=(_OR_OPT_1_FACT,),
            )

        if facts.has_or_opt_1_relocation and _duplicates_or_opt_1(text):
            return _result(
                facts,
                premise_check="duplicate",
                failure_category="duplicate_mechanism",
                mechanism="or_opt_1_relocation",
                reason=(
                    "Hypothesis proposes adding Or-opt-1 / single-customer "
                    "relocation as a new mechanism, but the active solver "
                    "already contains _or_opt_1 in local search."
                ),
                evidence=facts.or_opt_1_evidence,
                fact_ids=(_OR_OPT_1_FACT,),
            )

        if facts.has_cross_route_tail_exchange and _claims_missing_cross_route_tail_exchange(
            text
        ):
            return _result(
                facts,
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
                fact_ids=(_TAIL_EXCHANGE_FACT,),
            )

        if facts.has_cross_route_tail_exchange and _duplicates_cross_route_tail_exchange(
            text
        ):
            return _result(
                facts,
                premise_check="duplicate",
                failure_category="duplicate_mechanism",
                mechanism="cross_route_tail_exchange",
                reason=(
                    "Hypothesis proposes adding cross-route suffix/tail "
                    "exchange as a new mechanism, but the active solver "
                    "already contains _two_opt_star."
                ),
                evidence=facts.tail_exchange_evidence,
                fact_ids=(_TAIL_EXCHANGE_FACT,),
            )

        if facts.has_removal_savings_worst_removal and _duplicates_removal_savings_destroy(
            text
        ):
            return _result(
                facts,
                premise_check="duplicate",
                failure_category="duplicate_mechanism",
                mechanism="removal_savings_worst_removal",
                reason=(
                    "Hypothesis proposes adding a removal-savings or detour-cost "
                    "destroy operator as a new capability, but the active solver "
                    "already contains _worst_removal, which ranks candidates by "
                    "removal saving using saving = -route.cost_of_remove(pos)."
                ),
                evidence=facts.removal_savings_evidence,
                fact_ids=(_REMOVAL_SAVINGS_FACT,),
            )

        if (
            facts.has_removal_savings_worst_removal
            and _claims_missing_removal_savings_destroy(text)
        ):
            return _result(
                facts,
                premise_check="contradicted",
                failure_category="premise_contradicted",
                mechanism="removal_savings_worst_removal",
                reason=(
                    "Hypothesis claims removal-savings or detour-cost removal is "
                    "missing, or that _worst_removal does not use removal "
                    "savings, but the active solver already ranks _worst_removal "
                    "candidates by saving = -route.cost_of_remove(pos)."
                ),
                evidence=facts.removal_savings_evidence,
                fact_ids=(_REMOVAL_SAVINGS_FACT,),
            )

        if facts.has_shaw_related_removal and _claims_missing_shaw_related_removal(text):
            return _result(
                facts,
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
                fact_ids=(_SHAW_RELATED_FACT,),
            )

        if facts.has_shaw_related_removal and _duplicates_shaw_related_removal(text):
            return _result(
                facts,
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
                fact_ids=(_SHAW_RELATED_FACT,),
            )

        if facts.has_route_removal and _claims_missing_route_removal(text):
            return _result(
                facts,
                premise_check="contradicted",
                failure_category="premise_contradicted",
                mechanism="route_removal",
                reason=(
                    "Hypothesis claims route-level or whole-route destroy removal "
                    "is missing, but the active solver snapshot shows "
                    "_route_removal wired through the destroy operator portfolio."
                ),
                evidence=facts.route_removal_evidence,
                fact_ids=(_ROUTE_REMOVAL_FACT,),
            )

        if facts.has_route_removal and _duplicates_route_removal(text):
            return _result(
                facts,
                premise_check="duplicate",
                failure_category="duplicate_mechanism",
                mechanism="route_removal",
                reason=(
                    "Hypothesis proposes adding route-level / whole-route removal "
                    "as a new destroy capability, but the active solver already "
                    "contains _route_removal."
                ),
                evidence=facts.route_removal_evidence,
                fact_ids=(_ROUTE_REMOVAL_FACT,),
            )

        if facts.has_regret_insertion_repair and _claims_missing_regret_insertion_repair(
            text
        ):
            return _result(
                facts,
                premise_check="contradicted",
                failure_category="premise_contradicted",
                mechanism="regret_insertion_repair",
                reason=(
                    "Hypothesis claims regret insertion repair is missing, but "
                    "the active solver snapshot shows _regret2_insertion and "
                    "_regret3_insertion wired through the repair portfolio."
                ),
                evidence=facts.regret_insertion_evidence,
                fact_ids=(_REGRET_INSERTION_FACT,),
            )

        if facts.has_regret_insertion_repair and _duplicates_regret_insertion_repair(
            text
        ):
            return _result(
                facts,
                premise_check="duplicate",
                failure_category="duplicate_mechanism",
                mechanism="regret_insertion_repair",
                reason=(
                    "Hypothesis proposes adding regret insertion repair as a new "
                    "capability, but the active solver already contains "
                    "_regret2_insertion and _regret3_insertion."
                ),
                evidence=facts.regret_insertion_evidence,
                fact_ids=(_REGRET_INSERTION_FACT,),
            )

        if (
            facts.guards_route_limit_search_state
            and _claims_unproven_route_limit_or_fleet_repair(text)
            and not _has_explicit_route_limit_runtime_evidence(
                observations,
                context=context,
            )
        ):
            return _result(
                facts,
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
                fact_ids=(_ROUTE_LIMIT_FACT, _STARTS_FEASIBLE_FACT),
            )

        if (
            facts.starts_feasible_rejects_infeasible
            and _claims_unreachable_feasibility_crossing(text)
        ):
            return _result(
                facts,
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
                fact_ids=(_STARTS_FEASIBLE_FACT,),
            )

        return None


def _result(
    facts: Any,
    *,
    premise_check: str,
    failure_category: str,
    mechanism: str,
    reason: str,
    evidence: tuple[str, ...],
    fact_ids: tuple[str, ...],
) -> MechanismNoveltyResult:
    contradicted_fact_ids = fact_ids if premise_check == "contradicted" else ()
    return MechanismNoveltyResult(
        premise_check=premise_check,
        failure_category=failure_category,
        mechanism=mechanism,
        reason=reason,
        evidence=evidence,
        snapshot_digest=facts.snapshot_digest,
        fact_ids=fact_ids,
        contradicted_fact_ids=contradicted_fact_ids,
        fact_packet_digest=facts.fact_packet_digest,
        fact_provenance=facts.fact_provenance,
    )
