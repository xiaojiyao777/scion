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
    has_diverse_construction: bool = False
    has_adaptive_weights: bool = False
    has_cross_route_or_opt_2_3: bool = False
    has_cross_route_tail_exchange: bool = False
    has_shaw_related_removal: bool = False
    has_removal_savings_worst_removal: bool = False
    starts_feasible_rejects_infeasible: bool = False
    guards_route_limit_search_state: bool = False
    construction_evidence: tuple[str, ...] = ()
    adaptive_weight_evidence: tuple[str, ...] = ()
    or_opt_evidence: tuple[str, ...] = ()
    tail_exchange_evidence: tuple[str, ...] = ()
    shaw_related_evidence: tuple[str, ...] = ()
    removal_savings_evidence: tuple[str, ...] = ()
    feasible_search_evidence: tuple[str, ...] = ()
    route_limit_evidence: tuple[str, ...] = ()
    snapshot_digest: str | None = None


def _active_solver_snapshot_from_observations(
    observations: Sequence[ProposalObservation],
) -> Mapping[str, Any] | None:
    for observation in reversed(tuple(observations)):
        if observation.is_error:
            continue
        if observation.tool_name != "context.read_active_solver_design":
            continue
        payload = observation.structured_payload
        if isinstance(payload, Mapping) and isinstance(
            payload.get("mechanism_summary"), Mapping
        ):
            return payload
    return None


def _facts_from_snapshot(snapshot: Mapping[str, Any]) -> _ActiveMechanismFacts:
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
        has_removal_savings_worst_removal=(
            _has_any(destroy_repair_combined, ("worst removal", "worst"))
            and _has_any(destroy_repair_combined, ("removal", "destroy"))
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
        removal_savings_evidence=_removal_savings_evidence(
            mechanism_summary.get("destroy_repair")
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
