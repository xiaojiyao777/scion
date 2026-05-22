"""CVRP-owned active solver-design facts exposed through the adapter."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

_ALGORITHM_FILE_ROLES: tuple[tuple[str, str, bool], ...] = (
    ("policies/baseline_algorithm.py", "active_entrypoint", True),
    ("policies/baseline_modules/scheduler.py", "active_scheduler_alns_vns", True),
    ("policies/baseline_modules/construction.py", "active_construction", True),
    ("policies/baseline_modules/destroy_repair.py", "active_destroy_repair", True),
    ("policies/baseline_modules/local_search.py", "active_local_search_vns", True),
    ("policies/baseline_modules/acceptance.py", "active_acceptance_weights", True),
    ("policies/baseline_modules/config.py", "active_runtime_config", True),
    ("policies/baseline_modules/state.py", "active_solution_state", True),
)

_FACT_IMPORTANCE = "high"


class CvrpActiveSolverDesignProvider:
    """Problem-owned active algorithm manifest, summaries, and fact packet."""

    def active_solver_algorithm_file_manifest(self, context: Any) -> Sequence[Mapping[str, Any]]:
        del context
        return tuple(
            {
                "file_path": file_path,
                "role": role,
                "active": active,
            }
            for file_path, role, active in _ALGORITHM_FILE_ROLES
        )

    def active_solver_entrypoint_summary(
        self,
        context: Any,
        snapshot_context: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        del context
        text = _file_text(snapshot_context, "policies/baseline_algorithm.py")
        return {
            "file_path": "policies/baseline_algorithm.py",
            "symbol": "solve",
            "call_target": (
                "policies/baseline_modules/scheduler.py::_ALNSVNSSolver.solve"
            ),
            "source": snapshot_context.get("source_kind"),
            "readable": bool(text),
            "digest": _digest_for(snapshot_context, "policies/baseline_algorithm.py"),
            "summary": (
                "solve(instance, rng, time_limit_sec, context) constructs "
                "_ALNSVNSSolver, delegates to solver.solve(instance, rng), records "
                "stop_reason, and returns context.make_solution(routes_as_tuples())."
            ),
        }

    def active_solver_call_graph_edges(
        self,
        context: Any,
        snapshot_context: Mapping[str, Any],
    ) -> Sequence[Mapping[str, Any]]:
        del context, snapshot_context
        return (
            {
                "from": "policies/baseline_algorithm.py::solve",
                "to": "policies/baseline_modules/scheduler.py::_ALNSVNSSolver.__init__",
                "mechanism": "entrypoint wires config and context into scheduler",
                "evidence": ["baseline_algorithm.py imports _ALNSVNSSolver"],
            },
            {
                "from": "policies/baseline_algorithm.py::solve",
                "to": "policies/baseline_modules/scheduler.py::_ALNSVNSSolver.solve",
                "mechanism": "entrypoint delegates the active search and adapts output",
                "evidence": ["solver.solve(instance, rng)", "context.make_solution(...)"],
            },
            {
                "from": "scheduler._ALNSVNSSolver.solve",
                "to": "scheduler._ALNSVNSSolver._initial_solution",
                "mechanism": "seed construction before ALNS loop",
                "evidence": ["current = self._initial_solution(instance, reserve)"],
            },
            {
                "from": "scheduler._ALNSVNSSolver._initial_solution",
                "to": "construction",
                "mechanism": (
                    "uses sweep for large instances, Clarke-Wright otherwise, "
                    "capacity-balanced repair for route cap, nearest-neighbor fallback"
                ),
                "evidence": [
                    "_sweep_construction",
                    "_clarke_wright_savings",
                    "_capacity_balanced_construction",
                    "_nearest_neighbor",
                ],
            },
            {
                "from": "scheduler._ALNSVNSSolver.solve",
                "to": "acceptance._AdaptiveWeights",
                "mechanism": "adaptive destroy/repair operator choice, score, and update",
                "evidence": ["choose", "record", "update", "segment_length"],
            },
            {
                "from": "scheduler._ALNSVNSSolver.solve",
                "to": "destroy_repair",
                "mechanism": (
                    "ALNS destroy/repair loop includes Shaw related removal: "
                    "seed-based removal with distance, demand, and route relatedness"
                ),
                "evidence": [
                    "_random_removal",
                    "_worst_removal",
                    "_shaw_removal",
                    "seed-based related removal",
                    "distance + demand + original-route relatedness",
                    "_route_removal",
                    "_greedy_insertion",
                    "_regret2_insertion",
                    "_regret3_insertion",
                ],
            },
            {
                "from": "scheduler._ALNSVNSSolver.solve",
                "to": "local_search._vns",
                "mechanism": "embedded local search when VNS is enabled and bounded",
                "evidence": ["_vns", "_default_vns_operators", "vns_embedded"],
            },
            {
                "from": "local_search._default_vns_operators",
                "to": "local_search operators",
                "mechanism": "VNS neighborhoods include intra and cross-route moves",
                "evidence": [
                    "_two_opt_intra",
                    "_relocate",
                    "_or_opt_1",
                    "_or_opt_2",
                    "_or_opt_3",
                    "_swap",
                    "_two_opt_star",
                ],
            },
            {
                "from": "scheduler._ALNSVNSSolver.solve",
                "to": "acceptance._SimulatedAnnealing.accept",
                "mechanism": "accepts best, better, and bounded worse candidates",
                "evidence": ["SIGMA_BEST", "SIGMA_BETTER", "SIGMA_ACCEPTED", "accept"],
            },
        )

    def active_solver_mechanism_summary(
        self,
        context: Any,
        snapshot_context: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        del context
        scheduler = _file_text(snapshot_context, "policies/baseline_modules/scheduler.py")
        local_search = _file_text(
            snapshot_context,
            "policies/baseline_modules/local_search.py",
        )
        acceptance = _file_text(
            snapshot_context,
            "policies/baseline_modules/acceptance.py",
        )
        destroy_repair = _file_text(
            snapshot_context,
            "policies/baseline_modules/destroy_repair.py",
        )
        return {
            "construction": {
                "active": "_initial_solution" in scheduler,
                "summary": (
                    "_initial_solution chooses sweep construction above cw_threshold, "
                    "Clarke-Wright otherwise, capacity-balanced construction if the "
                    "route cap is exceeded, nearest-neighbor only as feasibility "
                    "fallback, then optional vns_initial."
                ),
                "evidence_symbols": [
                    "_initial_solution",
                    "_sweep_construction",
                    "_clarke_wright_savings",
                    "_capacity_balanced_construction",
                    "_nearest_neighbor",
                    "vns_initial",
                ],
            },
            "alns_loop": {
                "active": "while self._within_budget" in scheduler,
                "summary": (
                    "The main ALNS loop starts from a feasible construction, "
                    "records iterations, samples destroy/repair operators through "
                    "adaptive weights, applies destroy/repair, optionally embeds "
                    "VNS, rejects infeasible or route-cap-violating candidates, "
                    "scores best/better/accepted moves, and updates weights per "
                    "segment. Capacity infeasibility is not a normal accepted "
                    "search state."
                ),
                "evidence_symbols": [
                    "record_iteration('alns')",
                    "_AdaptiveWeights.choose",
                    "destroy_op",
                    "repair_op",
                    "record_move('alns')",
                    "segment_length",
                ],
            },
            "destroy_repair": {
                "active": (
                    "_random_removal" in destroy_repair
                    and '"random", _random_removal' in scheduler
                    and "_worst_removal" in destroy_repair
                    and '"worst", _worst_removal' in scheduler
                    and "_route_removal" in destroy_repair
                    and '"route", _route_removal' in scheduler
                    and "_shaw_removal" in destroy_repair
                    and '"shaw", _shaw_removal' in scheduler
                ),
                "summary": (
                    "The destroy operator portfolio contains random, worst, Shaw "
                    "related removal, and whole-route removal, wired through "
                    "scheduler destroy_ops. _random_removal uniformly samples "
                    "customers from the active solution and removes them as the "
                    'scheduler "random" destroy operator. '
                    "_shaw_removal is a seed-based "
                    "related/proximity-cluster destroy operator: it picks a seed "
                    "customer, then removes customers ranked by distance, demand, "
                    "and original-route relatedness, with stochastic p sampling."
                ),
                "evidence_symbols": [
                    "_random_removal",
                    '"random", _random_removal',
                    "rng.sample(customers, q)",
                    "_shaw_removal",
                    '"shaw", _shaw_removal',
                    "seed customer",
                    "phi_dist",
                    "phi_demand",
                    "phi_route",
                    "original_route",
                    "distance(customer, ref)",
                    "rng.random() ** p",
                ],
            },
            "local_search": {
                "active": "_default_vns_operators" in local_search,
                "summary": (
                    "VNS uses _two_opt_intra, _relocate, _or_opt_1/_2/_3, _swap, "
                    "and _two_opt_star. _or_opt skips same-route destinations, so "
                    "single-customer, length-2, and length-3 cross-route Or-opt "
                    "already exist. "
                    "_two_opt_star exchanges cross-route suffix/tail segments."
                ),
                "evidence_symbols": [
                    "_vns",
                    "_default_vns_operators",
                    "_two_opt_intra",
                    "_relocate",
                    "_or_opt_1",
                    "_or_opt_2",
                    "_or_opt_3",
                    "_swap",
                    "_two_opt_star",
                ],
            },
            "acceptance": {
                "active": (
                    "_SimulatedAnnealing" in acceptance
                    and "_AdaptiveWeights" in acceptance
                ),
                "summary": (
                    "_AdaptiveWeights starts uniform but records scores/usages and "
                    "updates weights with the reaction factor. _SimulatedAnnealing "
                    "accepts worsening moves with a cooling probability."
                ),
                "evidence_symbols": [
                    "_AdaptiveWeights.choose",
                    "_AdaptiveWeights.record",
                    "_AdaptiveWeights.update",
                    "_SimulatedAnnealing.accept",
                ],
            },
        }

    def active_algorithm_facts(
        self,
        context: Any,
        snapshot_context: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        del context
        mechanism_summary = snapshot_context.get("mechanism_summary")
        mechanism_summary = (
            mechanism_summary if isinstance(mechanism_summary, Mapping) else {}
        )
        snapshot_digest = _snapshot_digest(snapshot_context)
        scheduler_text = _file_text(
            snapshot_context,
            "policies/baseline_modules/scheduler.py",
        )
        destroy_repair_text = _file_text(
            snapshot_context,
            "policies/baseline_modules/destroy_repair.py",
        )
        facts = [
            _fact(
                "cvrp.construction.diverse_feasible_seed",
                (
                    "Initial construction uses sweep, Clarke-Wright savings, "
                    "capacity-balanced construction, and nearest-neighbor fallback."
                ),
                mechanism_summary.get("construction"),
                [
                    "policies/baseline_modules/scheduler.py::_initial_solution",
                    "policies/baseline_modules/construction.py::_sweep_construction",
                    "policies/baseline_modules/construction.py::_clarke_wright_savings",
                    (
                        "policies/baseline_modules/construction.py::"
                        "_capacity_balanced_construction"
                    ),
                    "policies/baseline_modules/construction.py::_nearest_neighbor",
                ],
            ),
            _fact(
                "cvrp.search_state.starts_feasible_rejects_infeasible",
                (
                    "The active search starts from feasible construction and "
                    "rejects infeasible or route-cap-violating candidates before "
                    "they become current search state."
                ),
                mechanism_summary.get("alns_loop"),
                [
                    "policies/baseline_modules/scheduler.py::_ALNSVNSSolver.solve",
                    "policies/baseline_modules/state.py::_Solution.is_feasible",
                ],
            ),
            _fact(
                "cvrp.search_state.guards_route_limit",
                (
                    "Construction and search guard the route limit; route-count "
                    "excess is not an accepted default search state."
                ),
                [
                    mechanism_summary.get("construction"),
                    mechanism_summary.get("alns_loop"),
                ],
                [
                    "policies/baseline_modules/scheduler.py::_initial_solution",
                    "policies/baseline_modules/scheduler.py::_ALNSVNSSolver.solve",
                    (
                        "policies/baseline_modules/construction.py::"
                        "_capacity_balanced_construction"
                    ),
                ],
            ),
            _fact(
                "cvrp.acceptance.adaptive_operator_weights",
                (
                    "Destroy/repair operator selection uses adaptive weights with "
                    "choose, record, and update behavior."
                ),
                mechanism_summary.get("acceptance"),
                [
                    "policies/baseline_modules/acceptance.py::_AdaptiveWeights.choose",
                    "policies/baseline_modules/acceptance.py::_AdaptiveWeights.record",
                    "policies/baseline_modules/acceptance.py::_AdaptiveWeights.update",
                ],
            ),
            _fact(
                "cvrp.destroy_repair.shaw_related_removal",
                (
                    "_shaw_removal is already a seed-based related/proximity "
                    "destroy operator using distance, demand, and original-route "
                    "relatedness."
                ),
                mechanism_summary.get("destroy_repair"),
                [
                    "policies/baseline_modules/destroy_repair.py::_shaw_removal",
                    "policies/baseline_modules/scheduler.py::destroy_ops",
                ],
            ),
            *(
                [
                    _fact(
                        "cvrp.destroy_repair.random_removal_destroy",
                        (
                            "_random_removal is already a random customer-removal "
                            "destroy operator: it uniformly samples customers "
                            "with rng.sample(customers, q), removes them from the "
                            "solution, and is wired as scheduler destroy_ops "
                            '"random".'
                        ),
                        mechanism_summary.get("destroy_repair"),
                        [
                            (
                                "policies/baseline_modules/destroy_repair.py::"
                                "_random_removal"
                            ),
                            "policies/baseline_modules/scheduler.py::destroy_ops",
                            'policies/baseline_modules/scheduler.py::"random"',
                        ],
                        mechanism="random_removal_destroy",
                        allowed_variant_guidance=(
                            "Allowed variant: modify the existing _random_removal "
                            "sampling distribution, adaptive randomization, noise "
                            "schedule, trigger, or budget while explicitly "
                            "acknowledging _random_removal / scheduler \"random\" "
                            "already exists; do not claim random customer removal "
                            "is missing or newly added."
                        ),
                    )
                ]
                if (
                    "_random_removal" in destroy_repair_text
                    and '"random", _random_removal' in scheduler_text
                )
                else []
            ),
            _fact(
                "cvrp.destroy_repair.route_removal",
                (
                    "_route_removal is already a destroy operator that removes "
                    "customers from an entire selected non-empty route and is wired "
                    "through scheduler destroy_ops."
                ),
                mechanism_summary.get("destroy_repair"),
                [
                    "policies/baseline_modules/destroy_repair.py::_route_removal",
                    "policies/baseline_modules/scheduler.py::destroy_ops",
                ],
            ),
            _fact(
                "cvrp.destroy_repair.removal_savings_worst_removal",
                (
                    "_worst_removal already ranks candidates by removal saving "
                    "using saving = -route.cost_of_remove(pos)."
                ),
                mechanism_summary.get("destroy_repair"),
                [
                    "policies/baseline_modules/destroy_repair.py::_worst_removal",
                    "policies/baseline_modules/state.py::_Route.cost_of_remove",
                ],
            ),
            _fact(
                "cvrp.destroy_repair.regret_insertion_repair",
                (
                    "Repair portfolio already includes regret-2 and regret-3 "
                    "insertion heuristics wired through scheduler repair_ops."
                ),
                mechanism_summary.get("destroy_repair"),
                [
                    "policies/baseline_modules/destroy_repair.py::_regret2_insertion",
                    "policies/baseline_modules/destroy_repair.py::_regret3_insertion",
                    "policies/baseline_modules/scheduler.py::repair_ops",
                ],
            ),
            _fact(
                "cvrp.local_search.intra_two_opt_reversal",
                (
                    "Local search already includes _two_opt_intra, an intra-route "
                    "2-opt segment reversal neighborhood registered in the VNS "
                    "operator list."
                ),
                mechanism_summary.get("local_search"),
                [
                    "policies/baseline_modules/local_search.py::_two_opt_intra",
                    "policies/baseline_modules/local_search.py::_default_vns_operators",
                ],
            ),
            _fact(
                "cvrp.local_search.relocate_and_swap",
                (
                    "Local search already includes _relocate and _swap in the VNS "
                    "operator list."
                ),
                mechanism_summary.get("local_search"),
                [
                    "policies/baseline_modules/local_search.py::_relocate",
                    "policies/baseline_modules/local_search.py::_swap",
                    "policies/baseline_modules/local_search.py::_default_vns_operators",
                ],
            ),
            _fact(
                "cvrp.local_search.vns_operator_registry",
                (
                    "_default_vns_operators registers the active VNS neighborhood "
                    "portfolio: _two_opt_intra, _relocate, _or_opt_1/_2/_3, "
                    "_swap, and _two_opt_star."
                ),
                mechanism_summary.get("local_search"),
                [
                    "policies/baseline_modules/local_search.py::_default_vns_operators",
                    "policies/baseline_modules/local_search.py::_two_opt_intra",
                    "policies/baseline_modules/local_search.py::_relocate",
                    "policies/baseline_modules/local_search.py::_or_opt_1",
                    "policies/baseline_modules/local_search.py::_or_opt_2",
                    "policies/baseline_modules/local_search.py::_or_opt_3",
                    "policies/baseline_modules/local_search.py::_swap",
                    "policies/baseline_modules/local_search.py::_two_opt_star",
                ],
            ),
            _fact(
                "cvrp.local_search.or_opt_1_relocation",
                (
                    "Local search already includes _or_opt_1 single-customer "
                    "relocation through the VNS operator list."
                ),
                mechanism_summary.get("local_search"),
                [
                    "policies/baseline_modules/local_search.py::_or_opt_1",
                    "policies/baseline_modules/local_search.py::_default_vns_operators",
                ],
            ),
            _fact(
                "cvrp.local_search.cross_route_or_opt_2_3",
                (
                    "Local search already includes length-2 and length-3 "
                    "cross-route Or-opt segment relocation."
                ),
                mechanism_summary.get("local_search"),
                [
                    "policies/baseline_modules/local_search.py::_or_opt_2",
                    "policies/baseline_modules/local_search.py::_or_opt_3",
                ],
            ),
            _fact(
                "cvrp.local_search.cross_route_tail_exchange",
                (
                    "Local search already includes cross-route suffix/tail "
                    "exchange through _two_opt_star."
                ),
                mechanism_summary.get("local_search"),
                ["policies/baseline_modules/local_search.py::_two_opt_star"],
            ),
        ]
        packet: dict[str, Any] = {
            "packet_id": "cvrp_active_algorithm_facts_v1",
            "snapshot_digest": snapshot_digest,
            "provenance": _packet_provenance(snapshot_context),
            "fact_ids": [fact["fact_id"] for fact in facts],
            "facts": facts,
        }
        packet["fact_packet_digest"] = _packet_digest(packet)
        return packet

    def legacy_inactive_surface_exclusion(
        self,
        context: Any,
        snapshot_context: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        del context
        active_files = [
            str(item.get("file_path"))
            for item in snapshot_context.get("files", ())
            if isinstance(item, Mapping) and item.get("active") and item.get("file_path")
        ]
        return {
            "rule": (
                "The active solver_design object is the CVRP provider-declared "
                "algorithm package listed in active_files. Deleted legacy "
                "component surfaces are not part of the active research object "
                "and must not be used as optimization directions or as active "
                "evidence that a mechanism is present or absent."
            ),
            "active_files": active_files,
            "excluded_surface_policy": (
                "All deleted legacy component surfaces are omitted from active "
                "solver_design context instead of being exposed by name."
            ),
            "excluded_files_or_hooks": [
                {
                    "path": "vrp/",
                    "reason": (
                        "legacy package implementation; active solver_design does "
                        "not import it"
                    ),
                },
                {
                    "path": "compact context.read_surface component defaults",
                    "reason": "surface metadata is not active branch/champion code",
                },
            ],
        }


def _file_text(snapshot_context: Mapping[str, Any], rel_path: str) -> str:
    file_texts = snapshot_context.get("file_texts")
    if not isinstance(file_texts, Mapping):
        return ""
    return str(file_texts.get(rel_path) or "")


def _digest_for(snapshot_context: Mapping[str, Any], rel_path: str) -> str | None:
    file_digests = snapshot_context.get("file_digests")
    if not isinstance(file_digests, Mapping):
        return None
    digest = file_digests.get(rel_path)
    return str(digest)[:16] if digest else None


def _snapshot_digest(snapshot_context: Mapping[str, Any]) -> str:
    source_digest = snapshot_context.get("source_digest")
    if isinstance(source_digest, Mapping):
        digest = source_digest.get("snapshot_digest")
        if digest:
            return str(digest)
    return ""


def _fact(
    fact_id: str,
    claim: str,
    evidence_source: Any,
    source_paths_or_symbols: Sequence[str],
    *,
    mechanism: str | None = None,
    allowed_variant_guidance: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "fact_id": fact_id,
        "claim": claim,
        "evidence": _evidence(evidence_source),
        "source_paths_or_symbols": list(source_paths_or_symbols),
        "importance": _FACT_IMPORTANCE,
        "used_by_prompt": True,
        "used_by_gate": True,
        "provenance": {
            "source": "active_algorithm_facts_provider",
            "provider": (
                "scion.problems.cvrp.active_solver_facts."
                "CvrpActiveSolverDesignProvider"
            ),
        },
    }
    if mechanism:
        payload["mechanism"] = mechanism
    if allowed_variant_guidance:
        payload["allowed_variant_guidance"] = allowed_variant_guidance
    payload["fact_digest"] = _digest_mapping(payload, exclude_keys=("fact_digest",))
    return payload


def _evidence(value: Any) -> list[str]:
    strings = [
        item
        for item in _flatten_strings(value)
        if item and len(item) <= 220 and item.lower() not in {"true", "false"}
    ]
    return list(dict.fromkeys(strings[:10]))


def _flatten_strings(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        strings: list[str] = []
        for key, child in value.items():
            strings.append(str(key))
            strings.extend(_flatten_strings(child))
        return strings
    if isinstance(value, (list, tuple, set)):
        strings = []
        for child in value:
            strings.extend(_flatten_strings(child))
        return strings
    if value is None:
        return []
    return [str(value)]


def _packet_digest(packet: Mapping[str, Any]) -> str:
    return _digest_mapping(packet, exclude_keys=("fact_packet_digest",))


def _digest_mapping(
    value: Mapping[str, Any],
    *,
    exclude_keys: Sequence[str],
) -> str:
    excluded = set(exclude_keys)
    digest_payload = {
        key: item
        for key, item in value.items()
        if key not in excluded
    }
    encoded = json.dumps(
        digest_payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _packet_provenance(snapshot_context: Mapping[str, Any]) -> dict[str, Any]:
    provenance: dict[str, Any] = {"source": "active_algorithm_facts_provider"}
    source_provenance = snapshot_context.get("provenance")
    if isinstance(source_provenance, Mapping):
        provenance["source_snapshot"] = dict(source_provenance)
    source_digest = snapshot_context.get("source_digest")
    if isinstance(source_digest, Mapping):
        provenance["source_digest"] = {
            key: value
            for key, value in source_digest.items()
            if key in {"algorithm", "snapshot_digest"}
        }
    return provenance


__all__ = ["CvrpActiveSolverDesignProvider"]
