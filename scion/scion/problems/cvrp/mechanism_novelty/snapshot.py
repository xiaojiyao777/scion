"""Active-solver capability facts for CVRP mechanism novelty checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from scion.proposal.tools import ProposalObservation

from scion.problems.cvrp.mechanism_novelty.text import (
    _evidence,
    _flatten_strings,
    _has_any,
    _normalized_join,
    _snapshot_digest,
)


@dataclass(frozen=True)
class _ActiveMechanismFacts:
    fact_packet_available: bool = False
    has_diverse_construction: bool = False
    has_adaptive_weights: bool = False
    has_cross_route_or_opt_2_3: bool = False
    has_or_opt_1_relocation: bool = False
    has_intra_two_opt_reversal: bool = False
    has_relocate_and_swap: bool = False
    has_vns_operator_registry: bool = False
    has_cross_route_tail_exchange: bool = False
    has_shaw_related_removal: bool = False
    has_random_removal_destroy: bool = False
    has_route_removal: bool = False
    has_removal_savings_worst_removal: bool = False
    has_regret_insertion_repair: bool = False
    starts_feasible_rejects_infeasible: bool = False
    guards_route_limit_search_state: bool = False
    construction_evidence: tuple[str, ...] = ()
    adaptive_weight_evidence: tuple[str, ...] = ()
    or_opt_evidence: tuple[str, ...] = ()
    or_opt_1_evidence: tuple[str, ...] = ()
    intra_two_opt_evidence: tuple[str, ...] = ()
    relocate_swap_evidence: tuple[str, ...] = ()
    vns_registry_evidence: tuple[str, ...] = ()
    tail_exchange_evidence: tuple[str, ...] = ()
    shaw_related_evidence: tuple[str, ...] = ()
    random_removal_evidence: tuple[str, ...] = ()
    route_removal_evidence: tuple[str, ...] = ()
    removal_savings_evidence: tuple[str, ...] = ()
    regret_insertion_evidence: tuple[str, ...] = ()
    feasible_search_evidence: tuple[str, ...] = ()
    route_limit_evidence: tuple[str, ...] = ()
    snapshot_digest: str | None = None
    fact_packet_digest: str | None = None
    fact_provenance: Mapping[str, Any] | None = None


def _active_solver_snapshot_from_observations(
    observations: Sequence[ProposalObservation],
) -> Mapping[str, Any] | None:
    for observation in reversed(tuple(observations)):
        if observation.is_error:
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        if isinstance(payload.get("active_algorithm_facts"), Mapping):
            return payload
        if isinstance(payload.get("mechanism_summary"), Mapping):
            return payload
    return None


def _facts_from_snapshot(snapshot: Mapping[str, Any]) -> _ActiveMechanismFacts:
    fact_packet = _fact_packet(snapshot)
    if fact_packet:
        return _facts_from_fact_packet(fact_packet, snapshot)

    mechanism_summary = snapshot.get("mechanism_summary")
    mechanism_summary = mechanism_summary if isinstance(mechanism_summary, Mapping) else {}
    construction_text = _normalized_join(
        _flatten_strings(mechanism_summary.get("construction"))
    )
    acceptance_text = _normalized_join(_flatten_strings(mechanism_summary.get("acceptance")))
    local_search_text = _normalized_join(
        _flatten_strings(mechanism_summary.get("local_search"))
    )
    destroy_repair_text = _normalized_join(
        _flatten_strings(mechanism_summary.get("destroy_repair"))
    )
    alns_text = _normalized_join(_flatten_strings(mechanism_summary.get("alns_loop")))
    call_graph_text = _normalized_join(_flatten_strings(snapshot.get("call_graph")))

    construction_combined = f"{construction_text} {call_graph_text}"
    acceptance_combined = f"{acceptance_text} {call_graph_text}"
    local_search_combined = f"{local_search_text} {call_graph_text}"
    destroy_repair_combined = f"{destroy_repair_text} {call_graph_text}"
    alns_combined = f"{alns_text} {call_graph_text}"

    return _ActiveMechanismFacts(
        has_diverse_construction=(
            _has_any(construction_combined, ("sweep", "_sweep_construction"))
            and _has_any(construction_combined, ("clarke wright", "clarke-wright"))
            and "capacity balanced" in construction_combined
            and _has_any(construction_combined, ("nearest neighbor", "_nearest_neighbor"))
        ),
        has_adaptive_weights=(
            "adaptiveweights" in acceptance_combined.replace(" ", "")
            and "update" in acceptance_combined
            and _has_any(acceptance_combined, ("record", "score", "usage"))
        ),
        has_cross_route_or_opt_2_3=(
            _has_or_opt_token(local_search_combined, "2")
            and _has_or_opt_token(local_search_combined, "3")
            and _has_any(
                local_search_combined,
                (
                    "cross route",
                    "cross-route",
                    "skips same route",
                    "same-route destinations",
                    "intra and cross route moves",
                ),
            )
        ),
        has_or_opt_1_relocation=_has_or_opt_token(local_search_combined, "1"),
        has_intra_two_opt_reversal=_has_any(
            local_search_combined,
            ("_two_opt_intra", "intra route 2 opt", "intra-route 2-opt"),
        ),
        has_relocate_and_swap=(
            "_relocate" in local_search_combined and "_swap" in local_search_combined
        ),
        has_vns_operator_registry="_default_vns_operators" in local_search_combined,
        has_cross_route_tail_exchange=(
            "two opt star" in local_search_combined
            and _has_any(
                local_search_combined,
                (
                    "cross route",
                    "cross-route",
                    "suffix",
                    "tail",
                ),
            )
        ),
        has_shaw_related_removal=(
            "shaw removal" in destroy_repair_combined
            and _has_any(
                destroy_repair_combined,
                ("related", "relatedness", "proximity", "cluster"),
            )
            and _has_any(
                destroy_repair_combined,
                ("destroy", "removal", "remove"),
            )
            and "distance" in destroy_repair_combined
            and "demand" in destroy_repair_combined
            and "route" in destroy_repair_combined
        ),
        has_random_removal_destroy=(
            _has_any(
                destroy_repair_combined,
                (
                    "_random_removal",
                    "random removal",
                    "random destroy",
                    "random customer removal",
                    "rng sample",
                ),
            )
            and _has_any(destroy_repair_combined, ("customer", "customers"))
            and _has_any(destroy_repair_combined, ("destroy", "removal", "remove"))
        ),
        has_route_removal=_has_any(
            destroy_repair_combined,
            ("_route_removal", "route removal", "whole-route removal"),
        ),
        has_removal_savings_worst_removal=(
            _has_any(destroy_repair_combined, ("worst removal", "worst"))
            and _has_any(destroy_repair_combined, ("removal", "destroy"))
        ),
        has_regret_insertion_repair=(
            _has_any(destroy_repair_combined, ("_regret2_insertion", "regret 2"))
            and _has_any(destroy_repair_combined, ("_regret3_insertion", "regret 3"))
        ),
        starts_feasible_rejects_infeasible=(
            _has_any(alns_combined, ("starts from a feasible", "feasible construction"))
            and _has_any(
                alns_combined,
                (
                    "rejects infeasible",
                    "reject infeasible",
                    "route cap violating",
                    "route-cap-violating",
                ),
            )
        ),
        guards_route_limit_search_state=(
            _has_any(
                construction_combined,
                (
                    "capacity balanced",
                    "capacity-balanced",
                    "route cap is exceeded",
                    "route cap",
                    "max routes",
                ),
            )
            and _has_any(
                alns_combined,
                (
                    "route cap violating",
                    "route-cap-violating",
                    "route cap",
                    "max routes",
                ),
            )
        ),
        construction_evidence=_evidence(
            mechanism_summary.get("construction"),
            fallback=(
                "_sweep_construction",
                "_clarke_wright_savings",
                "_capacity_balanced_construction",
                "_nearest_neighbor",
            ),
        ),
        adaptive_weight_evidence=_evidence(
            mechanism_summary.get("acceptance"),
            fallback=(
                "_AdaptiveWeights.choose",
                "_AdaptiveWeights.record",
                "_AdaptiveWeights.update",
            ),
        ),
        or_opt_evidence=_evidence(
            mechanism_summary.get("local_search"),
            fallback=(
                "_or_opt",
                "_or_opt_1",
                "_or_opt_2",
                "_or_opt_3",
                "cross-route Or-opt segment relocation",
            ),
        ),
        or_opt_1_evidence=_evidence(
            mechanism_summary.get("local_search"),
            fallback=(
                "_or_opt_1",
                "single-customer Or-opt relocation",
            ),
        ),
        intra_two_opt_evidence=_evidence(
            mechanism_summary.get("local_search"),
            fallback=(
                "_two_opt_intra",
                "intra-route 2-opt segment reversal",
            ),
        ),
        relocate_swap_evidence=_evidence(
            mechanism_summary.get("local_search"),
            fallback=(
                "_relocate",
                "_swap",
                "relocate and swap VNS neighborhoods",
            ),
        ),
        vns_registry_evidence=_evidence(
            mechanism_summary.get("local_search"),
            fallback=(
                "_default_vns_operators",
                "_two_opt_intra",
                "_relocate",
                "_or_opt_1",
                "_or_opt_2",
                "_or_opt_3",
                "_swap",
                "_two_opt_star",
            ),
        ),
        tail_exchange_evidence=_evidence(
            mechanism_summary.get("local_search"),
            fallback=(
                "_two_opt_star",
                "cross-route suffix/tail exchange",
            ),
        ),
        shaw_related_evidence=_evidence(
            mechanism_summary.get("destroy_repair"),
            fallback=(
                "_shaw_removal",
                "seed-based related removal",
                "distance + demand + original-route relatedness",
            ),
        ),
        random_removal_evidence=_evidence(
            mechanism_summary.get("destroy_repair"),
            fallback=(
                "_random_removal",
                '"random" destroy operator',
                "rng.sample(customers, q)",
            ),
        ),
        route_removal_evidence=_evidence(
            mechanism_summary.get("destroy_repair"),
            fallback=(
                "_route_removal",
                "whole-route removal destroy operator",
            ),
        ),
        removal_savings_evidence=_removal_savings_evidence(
            mechanism_summary.get("destroy_repair")
        ),
        regret_insertion_evidence=_evidence(
            mechanism_summary.get("destroy_repair"),
            fallback=(
                "_regret2_insertion",
                "_regret3_insertion",
                "regret repair insertion portfolio",
            ),
        ),
        feasible_search_evidence=_evidence(
            mechanism_summary.get("alns_loop"),
            fallback=(
                "starts from feasible construction",
                "rejects infeasible or route-cap-violating candidates",
            ),
        ),
        route_limit_evidence=tuple(
            dict.fromkeys(
                [
                    *_evidence(
                        mechanism_summary.get("construction"),
                        fallback=(
                            "_capacity_balanced_construction when route cap is exceeded",
                            "_initial_solution rejects route-limit excess",
                        ),
                    ),
                    *_evidence(
                        mechanism_summary.get("alns_loop"),
                        fallback=(
                            "rejects route-cap-violating candidates",
                            "route-count excess is not accepted as current state",
                        ),
                    ),
                ]
            )
        ),
        snapshot_digest=_snapshot_digest(snapshot),
    )


def _facts_from_fact_packet(
    fact_packet: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> _ActiveMechanismFacts:
    by_id = _facts_by_id(fact_packet)
    return _ActiveMechanismFacts(
        fact_packet_available=True,
        has_diverse_construction=_has_fact(
            by_id,
            "cvrp.construction.diverse_feasible_seed",
        ),
        has_adaptive_weights=_has_fact(
            by_id,
            "cvrp.acceptance.adaptive_operator_weights",
        ),
        has_cross_route_or_opt_2_3=_has_fact(
            by_id,
            "cvrp.local_search.cross_route_or_opt_2_3",
        ),
        has_or_opt_1_relocation=_has_fact(
            by_id,
            "cvrp.local_search.or_opt_1_relocation",
        ),
        has_intra_two_opt_reversal=_has_fact(
            by_id,
            "cvrp.local_search.intra_two_opt_reversal",
        ),
        has_relocate_and_swap=_has_fact(
            by_id,
            "cvrp.local_search.relocate_and_swap",
        ),
        has_vns_operator_registry=_has_fact(
            by_id,
            "cvrp.local_search.vns_operator_registry",
        ),
        has_cross_route_tail_exchange=_has_fact(
            by_id,
            "cvrp.local_search.cross_route_tail_exchange",
        ),
        has_shaw_related_removal=_has_fact(
            by_id,
            "cvrp.destroy_repair.shaw_related_removal",
        ),
        has_random_removal_destroy=_has_fact(
            by_id,
            "cvrp.destroy_repair.random_removal_destroy",
        ),
        has_route_removal=_has_fact(
            by_id,
            "cvrp.destroy_repair.route_removal",
        ),
        has_removal_savings_worst_removal=_has_fact(
            by_id,
            "cvrp.destroy_repair.removal_savings_worst_removal",
        ),
        has_regret_insertion_repair=_has_fact(
            by_id,
            "cvrp.destroy_repair.regret_insertion_repair",
        ),
        starts_feasible_rejects_infeasible=_has_fact(
            by_id,
            "cvrp.search_state.starts_feasible_rejects_infeasible",
        ),
        guards_route_limit_search_state=_has_fact(
            by_id,
            "cvrp.search_state.guards_route_limit",
        ),
        construction_evidence=_fact_evidence(
            by_id,
            "cvrp.construction.diverse_feasible_seed",
            fallback=(
                "_sweep_construction",
                "_clarke_wright_savings",
                "_capacity_balanced_construction",
                "_nearest_neighbor",
            ),
        ),
        adaptive_weight_evidence=_fact_evidence(
            by_id,
            "cvrp.acceptance.adaptive_operator_weights",
            fallback=(
                "_AdaptiveWeights.choose",
                "_AdaptiveWeights.record",
                "_AdaptiveWeights.update",
            ),
        ),
        or_opt_evidence=_fact_evidence(
            by_id,
            "cvrp.local_search.cross_route_or_opt_2_3",
            fallback=(
                "_or_opt",
                "_or_opt_1",
                "_or_opt_2",
                "_or_opt_3",
                "cross-route Or-opt segment relocation",
            ),
        ),
        or_opt_1_evidence=_fact_evidence(
            by_id,
            "cvrp.local_search.or_opt_1_relocation",
            fallback=(
                "_or_opt_1",
                "single-customer Or-opt relocation",
            ),
        ),
        intra_two_opt_evidence=_fact_evidence(
            by_id,
            "cvrp.local_search.intra_two_opt_reversal",
            fallback=(
                "_two_opt_intra",
                "intra-route 2-opt segment reversal",
            ),
        ),
        relocate_swap_evidence=_fact_evidence(
            by_id,
            "cvrp.local_search.relocate_and_swap",
            fallback=(
                "_relocate",
                "_swap",
                "relocate and swap VNS neighborhoods",
            ),
        ),
        vns_registry_evidence=_fact_evidence(
            by_id,
            "cvrp.local_search.vns_operator_registry",
            fallback=(
                "_default_vns_operators",
                "_two_opt_intra",
                "_relocate",
                "_or_opt_1",
                "_or_opt_2",
                "_or_opt_3",
                "_swap",
                "_two_opt_star",
            ),
        ),
        tail_exchange_evidence=_fact_evidence(
            by_id,
            "cvrp.local_search.cross_route_tail_exchange",
            fallback=(
                "_two_opt_star",
                "cross-route suffix/tail exchange",
            ),
        ),
        shaw_related_evidence=_fact_evidence(
            by_id,
            "cvrp.destroy_repair.shaw_related_removal",
            fallback=(
                "_shaw_removal",
                "seed-based related removal",
                "distance + demand + original-route relatedness",
            ),
        ),
        random_removal_evidence=_fact_evidence(
            by_id,
            "cvrp.destroy_repair.random_removal_destroy",
            fallback=(
                "_random_removal",
                '"random" destroy operator',
                "rng.sample(customers, q)",
            ),
        ),
        route_removal_evidence=_fact_evidence(
            by_id,
            "cvrp.destroy_repair.route_removal",
            fallback=(
                "_route_removal",
                "whole-route removal destroy operator",
            ),
        ),
        removal_savings_evidence=_fact_evidence(
            by_id,
            "cvrp.destroy_repair.removal_savings_worst_removal",
            fallback=(
                "_worst_removal",
                "saving = -route.cost_of_remove(pos)",
                "removal saving / detour eliminated",
            ),
        ),
        regret_insertion_evidence=_fact_evidence(
            by_id,
            "cvrp.destroy_repair.regret_insertion_repair",
            fallback=(
                "_regret2_insertion",
                "_regret3_insertion",
                "regret repair insertion portfolio",
            ),
        ),
        feasible_search_evidence=_fact_evidence(
            by_id,
            "cvrp.search_state.starts_feasible_rejects_infeasible",
            fallback=(
                "starts from feasible construction",
                "rejects infeasible or route-cap-violating candidates",
            ),
        ),
        route_limit_evidence=tuple(
            dict.fromkeys(
                [
                    *_fact_evidence(
                        by_id,
                        "cvrp.search_state.guards_route_limit",
                        fallback=(
                            "_capacity_balanced_construction when route cap is exceeded",
                            "_initial_solution rejects route-limit excess",
                        ),
                    ),
                    *_fact_evidence(
                        by_id,
                        "cvrp.search_state.starts_feasible_rejects_infeasible",
                        fallback=(
                            "rejects route-cap-violating candidates",
                            "route-count excess is not accepted as current state",
                        ),
                    ),
                ]
            )
        ),
        snapshot_digest=_source_snapshot_digest(fact_packet, snapshot),
        fact_packet_digest=_fact_packet_digest(fact_packet, snapshot),
        fact_provenance=_fact_provenance(snapshot),
    )


def _has_or_opt_token(text: str, length: str) -> bool:
    compact = text.replace(" ", "").replace("-", "_")
    return f"_or_opt_{length}" in compact or f"oropt{length}" in compact


def _removal_savings_evidence(value: Any) -> tuple[str, ...]:
    relevant = []
    for item in _evidence(value, fallback=()):
        normalized = _normalized_join((item,))
        if _has_any(
            normalized,
            (
                "worst removal",
                "cost of remove",
                "removal saving",
                "savings from removal",
                "detour",
            ),
        ):
            relevant.append(item)
    return tuple(
        dict.fromkeys(
            [
                *relevant,
                "_worst_removal",
                "saving = -route.cost_of_remove(pos)",
                "removal saving / detour eliminated",
            ]
        )
    )


def _fact_packet(snapshot: Mapping[str, Any]) -> Mapping[str, Any]:
    packet = snapshot.get("active_algorithm_facts")
    return packet if isinstance(packet, Mapping) else {}


def _facts_by_id(fact_packet: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    facts = fact_packet.get("facts")
    if not isinstance(facts, Sequence) or isinstance(facts, (str, bytes)):
        return {}
    by_id: dict[str, Mapping[str, Any]] = {}
    for item in facts:
        if not isinstance(item, Mapping):
            continue
        fact_id = str(item.get("fact_id") or "").strip()
        if fact_id:
            by_id[fact_id] = item
    return by_id


def _has_fact(facts_by_id: Mapping[str, Mapping[str, Any]], fact_id: str) -> bool:
    fact = facts_by_id.get(fact_id)
    if not isinstance(fact, Mapping):
        return False
    active = fact.get("active", True)
    used_by_gate = fact.get("used_by_gate", True)
    return bool(active) and bool(used_by_gate)


def _fact_evidence(
    facts_by_id: Mapping[str, Mapping[str, Any]],
    fact_id: str,
    *,
    fallback: tuple[str, ...],
) -> tuple[str, ...]:
    fact = facts_by_id.get(fact_id)
    if not isinstance(fact, Mapping):
        return fallback
    evidence = [
        f"fact_id:{fact_id}",
        *[
            str(item)
            for item in _flatten_strings(fact.get("evidence"))
            if str(item or "").strip()
        ],
        *[
            str(item)
            for item in _flatten_strings(fact.get("source_paths_or_symbols"))
            if str(item or "").strip()
        ],
    ]
    result = tuple(dict.fromkeys(item for item in evidence if len(item) <= 240))
    return result or fallback


def _fact_packet_digest(
    fact_packet: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> str | None:
    digest = fact_packet.get("fact_packet_digest")
    if digest:
        return str(digest)
    return _snapshot_digest(snapshot)


def _source_snapshot_digest(
    fact_packet: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> str | None:
    digest = fact_packet.get("snapshot_digest")
    if digest:
        return str(digest)
    return _snapshot_digest(snapshot)


def _fact_provenance(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    provenance = snapshot.get("provenance")
    source_digest = snapshot.get("source_digest")
    result: dict[str, Any] = {}
    if isinstance(provenance, Mapping):
        result["provenance"] = dict(provenance)
    if isinstance(source_digest, Mapping):
        result["source_digest"] = dict(source_digest)
    return result
