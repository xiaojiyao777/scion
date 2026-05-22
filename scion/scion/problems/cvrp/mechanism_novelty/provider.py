"""CVRP mechanism novelty provider exposed through the problem adapter."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from scion.core.models import HypothesisProposal
from scion.proposal.mechanism_novelty import MechanismNoveltyResult
from scion.proposal.tools import ProposalObservation

from scion.problems.cvrp.mechanism_novelty.acceptance import (
    _claims_weights_non_adaptive,
    _weights_non_adaptive_span,
)
from scion.problems.cvrp.mechanism_novelty.construction import (
    _claims_nearest_neighbor_only,
    _nearest_neighbor_only_span,
)
from scion.problems.cvrp.mechanism_novelty.destroy_repair import (
    _claims_missing_removal_savings_destroy,
    _claims_missing_random_removal_destroy,
    _claims_missing_regret_insertion_repair,
    _claims_missing_route_removal,
    _claims_missing_shaw_related_removal,
    _duplicate_regret_insertion_repair_span,
    _duplicates_removal_savings_destroy,
    _duplicates_random_removal_destroy,
    _duplicates_regret_insertion_repair,
    _duplicates_route_removal,
    _duplicates_shaw_related_removal,
    _missing_removal_savings_destroy_span,
    _missing_random_removal_destroy_span,
    _missing_regret_insertion_repair_span,
    _missing_route_removal_span,
    _missing_shaw_related_removal_span,
    _regret_insertion_allowed_variant_guidance,
)
from scion.problems.cvrp.mechanism_novelty.hypothesis import _hypothesis_text
from scion.problems.cvrp.mechanism_novelty.local_search import (
    _claims_missing_cross_route_tail_exchange,
    _claims_missing_intra_two_opt,
    _claims_missing_or_opt_1,
    _claims_missing_or_opt_2_3,
    _duplicates_cross_route_tail_exchange,
    _duplicates_intra_two_opt,
    _duplicates_or_opt_1,
    _duplicates_or_opt_2_3,
    _missing_cross_route_tail_exchange_span,
    _missing_intra_two_opt_span,
    _missing_or_opt_1_span,
    _missing_or_opt_2_3_span,
)
from scion.problems.cvrp.mechanism_novelty.route_limit import (
    _claims_unproven_route_limit_or_fleet_repair,
    _has_explicit_route_limit_runtime_evidence,
    _route_limit_or_fleet_repair_span,
)
from scion.problems.cvrp.mechanism_novelty.search_state import (
    _claims_unreachable_feasibility_crossing,
    _unreachable_feasibility_crossing_span,
)
from scion.problems.cvrp.mechanism_novelty.snapshot import (
    _active_solver_snapshot_from_observations,
    _facts_from_snapshot,
)

_CONSTRUCTION_FACT = "cvrp.construction.diverse_feasible_seed"
_ADAPTIVE_WEIGHTS_FACT = "cvrp.acceptance.adaptive_operator_weights"
_OR_OPT_FACT = "cvrp.local_search.cross_route_or_opt_2_3"
_OR_OPT_1_FACT = "cvrp.local_search.or_opt_1_relocation"
_INTRA_TWO_OPT_FACT = "cvrp.local_search.intra_two_opt_reversal"
_TAIL_EXCHANGE_FACT = "cvrp.local_search.cross_route_tail_exchange"
_SHAW_RELATED_FACT = "cvrp.destroy_repair.shaw_related_removal"
_RANDOM_REMOVAL_FACT = "cvrp.destroy_repair.random_removal_destroy"
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
            span = _nearest_neighbor_only_span(text)
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
                contradicted_span=span,
                matched_span=span,
                variant_allowed=False,
                allowed_variant_guidance=(
                    "Allowed variant: improve feasible construction seed quality "
                    "or add a new seed selection schedule without claiming the "
                    "active baseline is nearest-neighbor-only."
                ),
            )

        if facts.has_adaptive_weights and _claims_weights_non_adaptive(text):
            span = _weights_non_adaptive_span(text)
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
                contradicted_span=span,
                matched_span=span,
                variant_allowed=False,
                allowed_variant_guidance=(
                    "Allowed variant: modify the existing adaptive-weight update, "
                    "score, or schedule; do not claim ALNS operator weights are "
                    "uniform or non-adaptive throughout."
                ),
            )

        if facts.has_intra_two_opt_reversal and _claims_missing_intra_two_opt(text):
            span = _missing_intra_two_opt_span(text)
            return _result(
                facts,
                premise_check="contradicted",
                failure_category="premise_contradicted",
                mechanism="intra_two_opt_reversal",
                reason=(
                    "Hypothesis claims intra-route 2-opt / within-route segment "
                    "reversal is missing, but the active solver snapshot shows "
                    "_two_opt_intra registered in _default_vns_operators."
                ),
                evidence=facts.intra_two_opt_evidence,
                fact_ids=(_INTRA_TWO_OPT_FACT,),
                contradicted_span=span,
                matched_span=span,
                variant_allowed=False,
                allowed_variant_guidance=(
                    "Allowed variant: change candidate filtering, scoring, "
                    "ordering, or budget around the existing _two_opt_intra "
                    "operator; do not claim intra-route 2-opt is absent."
                ),
            )

        if facts.has_intra_two_opt_reversal and _duplicates_intra_two_opt(text):
            return _result(
                facts,
                premise_check="duplicate",
                failure_category="duplicate_mechanism",
                mechanism="intra_two_opt_reversal",
                reason=(
                    "Hypothesis proposes adding intra-route 2-opt / within-route "
                    "segment reversal as a new mechanism, but the active solver "
                    "already contains _two_opt_intra in local search."
                ),
                evidence=facts.intra_two_opt_evidence,
                fact_ids=(_INTRA_TWO_OPT_FACT,),
            )

        if facts.has_cross_route_or_opt_2_3 and _claims_missing_or_opt_2_3(text):
            span = _missing_or_opt_2_3_span(text)
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
                contradicted_span=span,
                matched_span=span,
                variant_allowed=False,
                allowed_variant_guidance=(
                    "Allowed variant: add candidate filtering, scoring, or "
                    "scheduling around existing cross-route Or-opt operators; "
                    "do not claim the cross-route Or-opt family is missing."
                ),
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
            span = _missing_or_opt_1_span(text)
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
                contradicted_span=span,
                matched_span=span,
                variant_allowed=False,
                allowed_variant_guidance=(
                    "Allowed variant: tune trigger, scoring, filtering, or "
                    "budget for existing _or_opt_1; do not claim single-customer "
                    "Or-opt relocation is missing."
                ),
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
            span = _missing_cross_route_tail_exchange_span(text)
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
                contradicted_span=span,
                matched_span=span,
                variant_allowed=False,
                allowed_variant_guidance=(
                    "Allowed variant: tune candidate filtering or scoring for "
                    "existing _two_opt_star tail exchange; do not claim the "
                    "cross-route tail exchange operator is absent."
                ),
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

        if (
            facts.has_removal_savings_worst_removal
            and _claims_missing_removal_savings_destroy(text)
        ):
            span = _missing_removal_savings_destroy_span(text)
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
                contradicted_span=span,
                matched_span=span,
                variant_allowed=False,
                allowed_variant_guidance=(
                    "Allowed variant: adjust scoring, sampling, or trigger "
                    "around existing _worst_removal; do not claim removal "
                    "savings are absent from the destroy portfolio."
                ),
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

        if facts.has_shaw_related_removal and _claims_missing_shaw_related_removal(text):
            span = _missing_shaw_related_removal_span(text)
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
                contradicted_span=span,
                matched_span=span,
                variant_allowed=False,
                allowed_variant_guidance=(
                    "Allowed variant: modify trigger, scoring, schedule, "
                    "relatedness weights, or candidate filtering for existing "
                    "_shaw_removal; do not claim Shaw/related removal is absent."
                ),
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

        if (
            facts.has_random_removal_destroy
            and _claims_missing_random_removal_destroy(text)
        ):
            span = _missing_random_removal_destroy_span(text)
            return _result(
                facts,
                premise_check="contradicted",
                failure_category="premise_contradicted",
                mechanism="random_removal_destroy",
                reason=(
                    "Hypothesis claims random customer-removal destroy is "
                    "missing, but the active solver snapshot shows "
                    '_random_removal wired as the scheduler "random" destroy '
                    "operator."
                ),
                evidence=facts.random_removal_evidence,
                fact_ids=(_RANDOM_REMOVAL_FACT,),
                contradicted_span=span,
                matched_span=span,
                variant_allowed=False,
                allowed_variant_guidance=_random_removal_allowed_variant_guidance(),
            )

        if facts.has_random_removal_destroy and _duplicates_random_removal_destroy(
            text
        ):
            return _result(
                facts,
                premise_check="duplicate",
                failure_category="duplicate_mechanism",
                mechanism="random_removal_destroy",
                reason=(
                    "Hypothesis proposes adding random customer-removal destroy "
                    "as a new capability, but the active solver already contains "
                    '_random_removal and scheduler destroy_ops "random".'
                ),
                evidence=facts.random_removal_evidence,
                fact_ids=(_RANDOM_REMOVAL_FACT,),
                variant_allowed=False,
                allowed_variant_guidance=_random_removal_allowed_variant_guidance(),
            )

        if facts.has_route_removal and _claims_missing_route_removal(text):
            span = _missing_route_removal_span(text)
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
                contradicted_span=span,
                matched_span=span,
                variant_allowed=False,
                allowed_variant_guidance=(
                    "Allowed variant: adjust trigger, scoring, or schedule for "
                    "existing _route_removal; do not claim whole-route removal "
                    "is absent."
                ),
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
            span = _missing_regret_insertion_repair_span(text)
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
                contradicted_span=span,
                matched_span=span,
                variant_allowed=False,
                allowed_variant_guidance=_regret_allowed_variant_guidance(),
            )

        if facts.has_regret_insertion_repair and _duplicates_regret_insertion_repair(
            text
        ):
            span = _duplicate_regret_insertion_repair_span(text)
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
                matched_span=span,
                variant_allowed=False,
                allowed_variant_guidance=_regret_allowed_variant_guidance(),
            )

        regret_variant_guidance = _regret_insertion_allowed_variant_guidance(text)
        if facts.has_regret_insertion_repair and regret_variant_guidance:
            return None

        if (
            facts.guards_route_limit_search_state
            and _claims_unproven_route_limit_or_fleet_repair(text)
            and not _has_explicit_route_limit_runtime_evidence(
                observations,
                context=context,
            )
        ):
            span = _route_limit_or_fleet_repair_span(text)
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
                contradicted_span=span,
                matched_span=span,
                variant_allowed=False,
                allowed_variant_guidance=(
                    "Allowed variant: improve feasible construction seed quality, "
                    "route merge quality, or total_distance while preserving the "
                    "route-limit guard; only claim fleet/route-limit repair when "
                    "screening or runtime feedback shows positive fleet_violation "
                    "or route-limit excess."
                ),
            )

        if (
            facts.starts_feasible_rejects_infeasible
            and _claims_unreachable_feasibility_crossing(text)
        ):
            span = _unreachable_feasibility_crossing_span(text)
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
                contradicted_span=span,
                matched_span=span,
                variant_allowed=False,
                allowed_variant_guidance=(
                    "Allowed variant: improve feasible-state quality or "
                    "acceptance among feasible candidates; do not rely on an "
                    "infeasible current search state unless runtime feedback "
                    "shows one."
                ),
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
    variant_allowed: bool | None = None,
    contradicted_span: str | None = None,
    matched_span: str | None = None,
    allowed_variant_guidance: str | None = None,
) -> MechanismNoveltyResult:
    if premise_check == "contradicted" and not (contradicted_span or matched_span):
        premise_check = "duplicate"
        if failure_category == "premise_contradicted":
            failure_category = "duplicate_mechanism"
        allowed_variant_guidance = allowed_variant_guidance or (
            "Provider did not find an exact contradicted span in the proposal; "
            "downgraded from premise_contradicted to duplicate/novelty guidance."
        )
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
        variant_allowed=variant_allowed,
        contradicted_span=contradicted_span,
        matched_span=matched_span,
        allowed_variant_guidance=allowed_variant_guidance,
    )


def _regret_allowed_variant_guidance() -> str:
    return (
        "Allowed variant: add or modify a destroy/removal operator that uses "
        "the existing _regret2_insertion/_regret3_insertion repair portfolio; "
        "do not claim the regret repair mechanism itself is missing or newly added."
    )


def _random_removal_allowed_variant_guidance() -> str:
    return (
        "Allowed variant: change the sampling distribution, adaptive "
        "randomization, noise schedule, trigger, budget, or telemetry around "
        'existing _random_removal / scheduler "random"; do not claim random '
        "customer removal is absent or a newly added destroy capability."
    )
