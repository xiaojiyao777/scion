"""CVRP-owned active solver map provider for generic APS tools."""

from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from scion.proposal.active_solver_snapshot import (
    build_active_solver_snapshot,
    list_algorithm_files_payload,
    read_algorithm_file_payload,
    read_algorithm_symbol_payload,
)

_SURFACE = "solver_design"
_SUBJECT_ID = "cvrp.solver_design.active_baseline"
_MAX_BODY_CHARS = 24_000
_DEFAULT_BODY_CHARS = 12_000
_MAX_TOTAL_TOKENS = 9_000
_MAX_BODY_TOKENS = 3_000


@dataclass(frozen=True)
class _SliceSpec:
    slice_id: str
    file_path: str
    symbols: tuple[str, ...]
    purpose: str
    exposure_level: str
    slice_kind: str
    symbol: str | None = None
    block_name: str | None = None


class CvrpActiveSolverMapProvider:
    """Expose the active CVRP solver-design subject through generic schema."""

    def read_active_solver_map(
        self,
        context: Any,
        *,
        surface: str | None = None,
        subject_id: str | None = None,
    ) -> Mapping[str, Any] | None:
        if not _surface_supported(surface):
            return None
        snapshot = _safe_snapshot(context)
        files = _safe_algorithm_files(context)
        file_digests = _file_digests(snapshot, files)
        snapshot_digest = _snapshot_digest(snapshot) or _digest_mapping(file_digests)
        return {
            "surface": _SURFACE,
            "subject_id": _subject_id(subject_id),
            "snapshot_digest": snapshot_digest,
            "entrypoints": _entrypoints(),
            "editable_files": _editable_files(files, file_digests),
            "operator_registries": _operator_registries(),
            "scheduler_integrations": _scheduler_integrations(),
            "algorithm_slices": _algorithm_slice_refs(file_digests),
            "telemetry_fields": _telemetry_fields(context),
            "known_mechanism_facts": _known_mechanism_facts(snapshot),
            "research_lever_digest": _research_lever_digest(),
            "source_policy": {
                "max_total_tokens": _MAX_TOTAL_TOKENS,
                "max_body_tokens_per_tool_call": _MAX_BODY_TOKENS,
                "allowed_files_digest": _digest_mapping(file_digests),
                "redaction_policy": "provider_declared_summary_then_slice",
            },
        }

    def read_operator_registry(
        self,
        context: Any,
        *,
        registry_id: str,
        surface: str | None = None,
        subject_id: str | None = None,
    ) -> Mapping[str, Any] | None:
        if not _surface_supported(surface):
            return None
        registry_id = str(registry_id or "").strip()
        map_payload = self.read_active_solver_map(
            context,
            surface=surface,
            subject_id=subject_id,
        )
        if not isinstance(map_payload, Mapping):
            return None
        for registry in map_payload.get("operator_registries", ()):
            if not isinstance(registry, Mapping):
                continue
            if registry.get("registry_id") != registry_id:
                continue
            return {
                "registry_id": registry_id,
                "surface": _SURFACE,
                "subject_id": _subject_id(subject_id),
                "snapshot_digest": str(map_payload.get("snapshot_digest") or ""),
                "owner_file": str(registry.get("owner_file") or ""),
                "owner_symbol": str(registry.get("owner_symbol") or ""),
                "registry_kind": str(registry.get("registry_kind") or "custom"),
                "operators": tuple(registry.get("operators") or ()),
                "integration_points": _integration_points(registry_id),
            }
        return None

    def read_algorithm_slice(
        self,
        context: Any,
        *,
        slice_id: str,
        surface: str | None = None,
        subject_id: str | None = None,
        max_chars: int | None = None,
    ) -> Mapping[str, Any] | None:
        if not _surface_supported(surface):
            return None
        spec = _slice_spec(str(slice_id or "").strip())
        if spec is None:
            return None
        source_max_chars = _source_max_chars(max_chars)
        if spec.symbol:
            content = _symbol_slice(context, spec, source_max_chars)
        elif spec.block_name:
            content = _assignment_block_slice(context, spec, source_max_chars)
        else:
            content = None
        if content is None:
            return None
        snapshot = _safe_snapshot(context)
        snapshot_digest = _snapshot_digest(snapshot)
        token_estimate = _token_estimate(content["content"])
        return {
            "slice_id": spec.slice_id,
            "surface": _SURFACE,
            "subject_id": _subject_id(subject_id),
            "snapshot_digest": snapshot_digest,
            "file_path": spec.file_path,
            "symbols": spec.symbols,
            "slice_kind": spec.slice_kind,
            "content": content["content"],
            "content_digest": _sha256(content["content"]),
            "line_start": content["line_start"],
            "line_end": content["line_end"],
            "token_estimate": token_estimate,
            "why_visible": spec.purpose,
            "source_policy_receipt": {
                "allowed": True,
                "reason": "provider_allowlisted_cvrp_solver_design_slice",
                "remaining_budget": max(0, _MAX_BODY_TOKENS - token_estimate),
            },
            "truncated": bool(content.get("truncated")),
            "max_chars": max_chars,
        }


def _entrypoints() -> tuple[dict[str, Any], ...]:
    return (
        {
            "id": "cvrp.entrypoint.solve",
            "file_path": "policies/baseline_algorithm.py",
            "symbol": "solve",
            "summary": (
                "solve constructs the baseline module scheduler, delegates the "
                "active search, records the stop reason, and returns the "
                "adapter-owned solution object."
            ),
            "calls": (
                {
                    "target_id": "cvrp.scheduler.alns_vns_loop",
                    "evidence": (
                        "imports _ALNSVNSSolver",
                        "calls solver.solve(instance, rng)",
                    ),
                },
            ),
        },
    )


def _editable_files(
    files: Sequence[Mapping[str, Any]],
    file_digests: Mapping[str, str],
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for item in files:
        path = str(item.get("file_path") or "").strip()
        if not path or not item.get("active", True):
            continue
        rows.append(
            {
                "file_path": path,
                "role": str(item.get("role") or "active_algorithm_file"),
                "digest": file_digests.get(path, str(item.get("digest") or "")),
                "read_budget_hint": min(
                    _DEFAULT_BODY_CHARS,
                    max(0, int(item.get("size_chars") or 0)),
                ),
            }
        )
    return tuple(rows)


def _operator_registries() -> tuple[dict[str, Any], ...]:
    return (
        {
            "registry_id": "cvrp.registry.construction",
            "owner_file": "policies/baseline_modules/scheduler.py",
            "owner_symbol": "_ALNSVNSSolver._initial_solution",
            "registry_kind": "construction",
            "operators": (
                _operator(
                    "cvrp.construction.sweep",
                    "_sweep_construction",
                    "policies/baseline_modules/construction.py",
                    0,
                    "construction_seed",
                    "Large-instance angular sweep seed construction.",
                    ("construction", "large_instance_seed"),
                    ("solver_algorithm_phase_runtime_ms.construction",),
                ),
                _operator(
                    "cvrp.construction.clarke_wright",
                    "_clarke_wright_savings",
                    "policies/baseline_modules/construction.py",
                    1,
                    "construction_seed",
                    "Small/medium-instance savings merge seed construction.",
                    ("construction", "savings_seed"),
                    ("solver_algorithm_phase_runtime_ms.construction",),
                ),
                _operator(
                    "cvrp.construction.capacity_balanced",
                    "_capacity_balanced_construction",
                    "policies/baseline_modules/construction.py",
                    2,
                    "construction_repair",
                    "Route-limit guarded fallback construction.",
                    ("construction", "route_limit_guard"),
                    ("solver_algorithm_phase_runtime_ms.construction",),
                ),
                _operator(
                    "cvrp.construction.nearest_neighbor",
                    "_nearest_neighbor",
                    "policies/baseline_modules/construction.py",
                    3,
                    "construction_fallback",
                    "Feasibility fallback construction.",
                    ("construction", "fallback_seed"),
                    ("solver_algorithm_phase_runtime_ms.construction",),
                ),
            ),
        },
        {
            "registry_id": "cvrp.registry.destroy",
            "owner_file": "policies/baseline_modules/scheduler.py",
            "owner_symbol": "_ALNSVNSSolver.solve::destroy_ops",
            "registry_kind": "destroy",
            "operators": (
                _operator(
                    "cvrp.destroy.random",
                    "_random_removal",
                    "policies/baseline_modules/destroy_repair.py",
                    0,
                    "destroy",
                    "Uniform random removal destroy operator.",
                    ("destroy", "random_removal"),
                    ("solver_algorithm_context_records.alns_iterations",),
                ),
                _operator(
                    "cvrp.destroy.worst",
                    "_worst_removal",
                    "policies/baseline_modules/destroy_repair.py",
                    1,
                    "destroy",
                    "Removal-savings ranked destroy operator.",
                    ("destroy", "worst_removal"),
                    ("solver_algorithm_context_records.alns_iterations",),
                ),
                _operator(
                    "cvrp.destroy.shaw",
                    "_shaw_removal",
                    "policies/baseline_modules/destroy_repair.py",
                    2,
                    "destroy",
                    "Seed-based related/proximity removal destroy operator.",
                    ("destroy", "related_removal"),
                    ("solver_algorithm_context_records.alns_iterations",),
                ),
                _operator(
                    "cvrp.destroy.route",
                    "_route_removal",
                    "policies/baseline_modules/destroy_repair.py",
                    3,
                    "destroy",
                    "Whole-route removal destroy operator.",
                    ("destroy", "route_removal"),
                    ("solver_algorithm_context_records.alns_iterations",),
                ),
            ),
        },
        {
            "registry_id": "cvrp.registry.repair",
            "owner_file": "policies/baseline_modules/scheduler.py",
            "owner_symbol": "_ALNSVNSSolver.solve::repair_ops",
            "registry_kind": "repair",
            "operators": (
                _operator(
                    "cvrp.repair.greedy",
                    "_greedy_insertion",
                    "policies/baseline_modules/destroy_repair.py",
                    0,
                    "repair",
                    "Greedy best insertion repair operator.",
                    ("repair", "greedy_insertion"),
                    ("solver_algorithm_context_records.alns_iterations",),
                ),
                _operator(
                    "cvrp.repair.regret2",
                    "_regret2_insertion",
                    "policies/baseline_modules/destroy_repair.py",
                    1,
                    "repair",
                    "Regret-2 insertion repair operator.",
                    ("repair", "regret_insertion"),
                    ("solver_algorithm_context_records.alns_iterations",),
                ),
                _operator(
                    "cvrp.repair.regret3",
                    "_regret3_insertion",
                    "policies/baseline_modules/destroy_repair.py",
                    2,
                    "repair",
                    "Regret-3 insertion repair operator.",
                    ("repair", "regret_insertion"),
                    ("solver_algorithm_context_records.alns_iterations",),
                ),
            ),
        },
        {
            "registry_id": "cvrp.registry.local_search_vns",
            "owner_file": "policies/baseline_modules/local_search.py",
            "owner_symbol": "_default_vns_operators",
            "registry_kind": "local_search",
            "operators": (
                _operator(
                    "cvrp.local_search.two_opt_intra",
                    "_two_opt_intra",
                    "policies/baseline_modules/local_search.py",
                    0,
                    "local_search",
                    (
                        "Intra-route 2-opt reversal neighborhood; the scheduler "
                        "also invokes the paired _two_opt_intra_polish helper as "
                        "a size70 fallback when full VNS is skipped."
                    ),
                    ("vns", "local_search", "two_opt", "size70_fallback"),
                    (
                        "solver_algorithm_phase_runtime_ms.vns_embedded",
                        "solver_algorithm_phase_runtime_ms.size70_two_opt_initial",
                        "solver_algorithm_phase_runtime_ms.size70_two_opt_embedded",
                    ),
                ),
                _operator(
                    "cvrp.local_search.relocate",
                    "_relocate",
                    "policies/baseline_modules/local_search.py",
                    1,
                    "local_search",
                    "Cross-route single-customer relocation neighborhood.",
                    ("vns", "local_search", "relocate"),
                    ("solver_algorithm_phase_runtime_ms.vns_embedded",),
                ),
                _operator(
                    "cvrp.local_search.or_opt_1",
                    "_or_opt_1",
                    "policies/baseline_modules/local_search.py",
                    2,
                    "local_search",
                    "Length-1 Or-opt relocation wrapper.",
                    ("vns", "local_search", "or_opt"),
                    ("solver_algorithm_phase_runtime_ms.vns_embedded",),
                ),
                _operator(
                    "cvrp.local_search.or_opt_2",
                    "_or_opt_2",
                    "policies/baseline_modules/local_search.py",
                    3,
                    "local_search",
                    "Length-2 Or-opt relocation wrapper.",
                    ("vns", "local_search", "or_opt"),
                    ("solver_algorithm_phase_runtime_ms.vns_embedded",),
                ),
                _operator(
                    "cvrp.local_search.or_opt_3",
                    "_or_opt_3",
                    "policies/baseline_modules/local_search.py",
                    4,
                    "local_search",
                    "Length-3 Or-opt relocation wrapper.",
                    ("vns", "local_search", "or_opt"),
                    ("solver_algorithm_phase_runtime_ms.vns_embedded",),
                ),
                _operator(
                    "cvrp.local_search.swap",
                    "_swap",
                    "policies/baseline_modules/local_search.py",
                    5,
                    "local_search",
                    "Cross-route pair swap neighborhood.",
                    ("vns", "local_search", "swap"),
                    ("solver_algorithm_phase_runtime_ms.vns_embedded",),
                ),
                _operator(
                    "cvrp.local_search.two_opt_star",
                    "_two_opt_star",
                    "policies/baseline_modules/local_search.py",
                    6,
                    "local_search",
                    "Cross-route suffix exchange neighborhood.",
                    ("vns", "local_search", "tail_exchange"),
                    ("solver_algorithm_phase_runtime_ms.vns_embedded",),
                ),
            ),
        },
        {
            "registry_id": "cvrp.registry.acceptance",
            "owner_file": "policies/baseline_modules/scheduler.py",
            "owner_symbol": "_ALNSVNSSolver.solve::acceptance",
            "registry_kind": "acceptance",
            "operators": (
                _operator(
                    "cvrp.acceptance.adaptive_choose",
                    "_AdaptiveWeights.choose",
                    "policies/baseline_modules/acceptance.py",
                    0,
                    "operator_selection",
                    "Adaptive weighted operator selection.",
                    ("adaptive_weights", "operator_selection"),
                    ("solver_algorithm_context_records.alns_iterations",),
                ),
                _operator(
                    "cvrp.acceptance.adaptive_update",
                    "_AdaptiveWeights.update",
                    "policies/baseline_modules/acceptance.py",
                    1,
                    "operator_weight_update",
                    "Segment-level adaptive score update.",
                    ("adaptive_weights", "segment_update"),
                    ("solver_algorithm_context_records.alns_iterations",),
                ),
                _operator(
                    "cvrp.acceptance.simulated_annealing",
                    "_SimulatedAnnealing.accept",
                    "policies/baseline_modules/acceptance.py",
                    2,
                    "acceptance",
                    "Temperature-cooled acceptance for non-improving moves.",
                    ("acceptance", "simulated_annealing"),
                    ("solver_algorithm_accepted_moves",),
                ),
            ),
        },
    )


def _operator(
    operator_id: str,
    symbol: str,
    file_path: str,
    order: int,
    role: str,
    summary: str,
    mechanism_tags: Sequence[str],
    telemetry_ids: Sequence[str],
) -> dict[str, Any]:
    return {
        "id": operator_id,
        "symbol": symbol,
        "file_path": file_path,
        "order": order,
        "role": role,
        "summary": summary,
        "mechanism_tags": tuple(mechanism_tags),
        "telemetry_ids": tuple(telemetry_ids),
    }


def _scheduler_integrations() -> tuple[dict[str, Any], ...]:
    return (
        {
            "integration_id": "cvrp.scheduler.alns_vns_loop",
            "file_path": "policies/baseline_modules/scheduler.py",
            "symbol": "_ALNSVNSSolver.solve",
            "phase": "search",
            "summary": (
                "Initializes construction, destroy/repair registries, adaptive "
                "weights, acceptance, and the bounded ALNS loop with optional "
                "embedded VNS after repair or size70 two-opt fallback polish "
                "when full VNS is skipped."
            ),
            "calls": (
                "cvrp.registry.construction",
                "cvrp.registry.destroy",
                "cvrp.registry.repair",
                "cvrp.registry.local_search_vns",
                "cvrp.registry.acceptance",
                "_run_size70_two_opt_polish",
            ),
            "guard_conditions": (
                "_within_budget(start_ms, reserve)",
                "candidate.is_feasible()",
                "max_routes route-count guard",
                "instance.customer_count <= vns_threshold",
                "_should_run_size70_two_opt(instance)",
            ),
            "state_variables": (
                "current",
                "best",
                "destroy_weights",
                "repair_weights",
                "annealing",
                "iteration",
            ),
            "telemetry_events": (
                "solver_algorithm_search_iterations",
                "solver_algorithm_move_attempts",
                "solver_algorithm_accepted_moves",
                "solver_algorithm_phase_runtime_ms.vns_embedded",
                "solver_algorithm_phase_runtime_ms.size70_two_opt_embedded",
                "solver_algorithm_phase_best_delta.alns",
            ),
        },
        {
            "integration_id": "cvrp.scheduler.initial_solution",
            "file_path": "policies/baseline_modules/scheduler.py",
            "symbol": "_ALNSVNSSolver._initial_solution",
            "phase": "construction",
            "summary": (
                "Selects the seed construction path, applies route-limit "
                "guarding, and optionally runs initial VNS or size70 two-opt "
                "fallback polish before search."
            ),
            "calls": (
                "_sweep_construction",
                "_clarke_wright_savings",
                "_capacity_balanced_construction",
                "_nearest_neighbor",
                "_vns",
                "_run_size70_two_opt_polish",
            ),
            "guard_conditions": (
                "customer_count > cw_threshold",
                "max_routes route-count guard",
                "solution.is_feasible()",
                "customer_count <= vns_threshold",
                "_should_run_size70_two_opt(instance)",
            ),
            "state_variables": ("solution", "max_routes", "reserve"),
            "telemetry_events": (
                "solver_algorithm_phase_runtime_ms.construction",
                "solver_algorithm_phase_runtime_ms.vns_initial",
                "solver_algorithm_phase_runtime_ms.size70_two_opt_initial",
            ),
        },
    )


def _algorithm_slice_refs(
    file_digests: Mapping[str, str],
) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "slice_id": spec.slice_id,
            "file_path": spec.file_path,
            "symbols": spec.symbols,
            "purpose": spec.purpose,
            "exposure_level": spec.exposure_level,
            "source_digest": file_digests.get(spec.file_path, ""),
            "token_estimate": _slice_token_hint(spec),
            "redaction_reason": None,
        }
        for spec in _SLICE_SPECS
    )


def _telemetry_fields(context: Any) -> tuple[dict[str, Any], ...]:
    surface = _solver_design_surface(context)
    evidence = getattr(surface, "evidence", None)
    if evidence is None:
        return ()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(field: Any, role: str, declared_by: str) -> None:
        value = str(field or "").strip()
        if not value or value in seen:
            return
        seen.add(value)
        rows.append(
            {
                "field": value,
                "role": role,
                "mechanism_id_template": (
                    "{mechanism}" if "{mechanism}" in value else None
                ),
                "declared_by": declared_by,
            }
        )

    role_map = {
        "mechanism_activation": "activation",
        "activation": "activation",
        "activity": "activity",
        "aggregate_effect": "effect",
        "effect": "effect",
        "budget": "budget",
        "safety": "safety",
        "debug": "debug",
    }
    runtime_roles = getattr(evidence, "runtime_field_roles", {}) or {}
    if isinstance(runtime_roles, Mapping):
        for raw_role, fields in runtime_roles.items():
            role = role_map.get(str(raw_role or "").strip(), "debug")
            for field in fields or ():
                add(field, role, "adapter:evidence.runtime_field_roles")
    activation = getattr(evidence, "activation_runtime_fields", {}) or {}
    if isinstance(activation, Mapping):
        for fields in activation.values():
            for field in fields or ():
                add(field, "activation", "adapter:evidence.activation_runtime_fields")
    for field in getattr(evidence, "effect_probe_runtime_fields", ()) or ():
        add(field, "effect", "adapter:evidence.effect_probe_runtime_fields")
    for field in getattr(evidence, "required_runtime_fields", ()) or ():
        add(
            field,
            _fallback_telemetry_role(str(field or "")),
            "adapter:evidence.required_runtime_fields",
        )
    for field in getattr(evidence, "optional_runtime_fields", ()) or ():
        add(field, "debug", "adapter:evidence.optional_runtime_fields")
    return tuple(rows)


def _known_mechanism_facts(snapshot: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    packet = snapshot.get("active_algorithm_facts")
    if not isinstance(packet, Mapping):
        return ()
    facts = packet.get("facts")
    if not isinstance(facts, Sequence) or isinstance(facts, (str, bytes)):
        return ()
    rows: list[dict[str, Any]] = []
    for fact in facts:
        if not isinstance(fact, Mapping):
            continue
        fact_id = str(fact.get("fact_id") or "").strip()
        claim = str(fact.get("claim") or "").strip()
        if not fact_id or not claim:
            continue
        rows.append(
            {
                "fact_id": fact_id,
                "claim": claim,
                "evidence": tuple(_compact_strings(fact.get("evidence"), limit=8)),
                "provenance": "provider",
            }
        )
    return tuple(rows)


def _research_lever_digest() -> dict[str, Any]:
    """Return bounded CVRP-owned proposal guidance for mechanism diversity."""

    return {
        "digest_id": "cvrp_solver_design_research_lever_digest_v1",
        "scope": "CVRP solver_design proposal context",
        "visibility": "proposal-only advisory",
        "proposal_visibility_only": True,
        "excluded_from": (
            "DecisionFeatures",
            "promotion_gates",
            "scheduler_decisions",
        ),
        "summary": (
            "The active solver has several distinct CVRP causal levers. Use this "
            "digest to choose a mechanism family deliberately before reading the "
            "owner file; do not treat it as evidence that a proposal will pass."
        ),
        "active_lever_families": (
            {
                "family": "construction",
                "owner_files": ("policies/baseline_modules/construction.py",),
                "causal_lever": (
                    "seed route geometry, savings merges, route-cap guarded "
                    "fallbacks, and initial route load distribution"
                ),
            },
            {
                "family": "destroy",
                "owner_files": ("policies/baseline_modules/destroy_repair.py",),
                "causal_lever": (
                    "which customers or route fragments are removed before repair"
                ),
            },
            {
                "family": "repair",
                "owner_files": ("policies/baseline_modules/destroy_repair.py",),
                "causal_lever": (
                    "customer reinsertion order, regret scoring, capacity slack, "
                    "and insertion tie-breaks"
                ),
            },
            {
                "family": "local_search",
                "owner_files": ("policies/baseline_modules/local_search.py",),
                "causal_lever": (
                    "intra-route cleanup, cross-route relocation, segment moves, "
                    "swaps, and tail exchanges after repair"
                ),
            },
            {
                "family": "acceptance_and_weights",
                "owner_files": ("policies/baseline_modules/acceptance.py",),
                "causal_lever": (
                    "operator choice, score update, exploration temperature, and "
                    "whether bounded worse moves remain useful"
                ),
            },
            {
                "family": "scheduler_orchestration",
                "owner_files": ("policies/baseline_modules/scheduler.py",),
                "causal_lever": (
                    "phase ordering, budget allocation, trigger policy, and narrow "
                    "integration wiring for module-owned mechanisms, including "
                    "thresholded size70 two-opt fallback when full VNS is skipped"
                ),
            },
        ),
        "diversity_guidance": (
            "Avoid concentrating every proposal in one local route absorption, "
            "route compaction, or slack-preservation family.",
            (
                "Prefer a different causal lever when recent branch context is "
                "already dominated by variants of the same route-local mechanism."
            ),
            (
                "Concrete alternatives include construction seed diversity, "
                "destroy selection, repair scoring, acceptance/weight adaptation, "
                "local-search neighborhood design, or scheduler budget/trigger "
                "policy."
            ),
            (
                "Scheduler edits should usually be narrow orchestration or wiring; "
                "put construction, destroy, repair, local-search, and acceptance "
                "semantics in their owner modules."
            ),
        ),
    }


def _integration_points(registry_id: str) -> tuple[dict[str, Any], ...]:
    if registry_id == "cvrp.registry.construction":
        return (
            {
                "file_path": "policies/baseline_modules/scheduler.py",
                "symbol": "_ALNSVNSSolver._initial_solution",
                "insert_policy": (
                    "Wire construction changes inside _initial_solution or import "
                    "a helper from construction.py and select it there."
                ),
                "required_telemetry_pattern": (
                    "context.record_phase('construction', elapsed_ms)"
                ),
            },
        )
    if registry_id == "cvrp.registry.destroy":
        return (
            {
                "file_path": "policies/baseline_modules/scheduler.py",
                "symbol": "_ALNSVNSSolver.solve::destroy_ops",
                "insert_policy": (
                    "Import the destroy helper from destroy_repair.py and add one "
                    "(name, function) tuple to destroy_ops."
                ),
                "required_telemetry_pattern": (
                    "context.record_iteration('<mechanism>', count)"
                ),
            },
        )
    if registry_id == "cvrp.registry.repair":
        return (
            {
                "file_path": "policies/baseline_modules/scheduler.py",
                "symbol": "_ALNSVNSSolver.solve::repair_ops",
                "insert_policy": (
                    "Import the repair helper from destroy_repair.py and add one "
                    "(name, function) tuple to repair_ops."
                ),
                "required_telemetry_pattern": (
                    "context.record_iteration('<mechanism>', count)"
                ),
            },
        )
    if registry_id == "cvrp.registry.local_search_vns":
        return (
            {
                "file_path": "policies/baseline_modules/local_search.py",
                "symbol": "_default_vns_operators",
                "insert_policy": (
                    "Define the local-search helper in local_search.py and add it "
                    "to the _default_vns_operators returned list."
                ),
                "required_telemetry_pattern": (
                    "context.record_move('<mechanism>', attempted=1, accepted=...)"
                ),
            },
        )
    if registry_id == "cvrp.registry.acceptance":
        return (
            {
                "file_path": "policies/baseline_modules/acceptance.py",
                "symbol": "_AdaptiveWeights or _SimulatedAnnealing",
                "insert_policy": (
                    "Keep acceptance logic in acceptance.py and wire scheduler "
                    "changes with narrow imports or constructor arguments."
                ),
                "required_telemetry_pattern": (
                    "Use activation/budget telemetry for policy changes unless "
                    "the mechanism records a direct accepted/improving decision."
                ),
            },
        )
    return ()


def _symbol_slice(
    context: Any,
    spec: _SliceSpec,
    max_chars: int,
) -> dict[str, Any] | None:
    artifact = read_algorithm_symbol_payload(
        context,
        spec.file_path,
        str(spec.symbol),
        max_chars=_MAX_BODY_CHARS,
    )
    if not artifact.get("readable"):
        return None
    content = str(artifact.get("content_preview") or "")
    truncated = bool(artifact.get("truncated")) or len(content) > max_chars
    if len(content) > max_chars:
        content = content[:max_chars]
    return {
        "content": content,
        "line_start": artifact.get("line_start"),
        "line_end": artifact.get("line_end"),
        "truncated": truncated,
    }


def _assignment_block_slice(
    context: Any,
    spec: _SliceSpec,
    max_chars: int,
) -> dict[str, Any] | None:
    file_payload = read_algorithm_file_payload(
        context,
        spec.file_path,
        max_chars=_MAX_BODY_CHARS,
    )
    if not file_payload.get("readable"):
        return None
    source = str(file_payload.get("content_preview") or "")
    line_span = _assignment_line_span(
        source,
        block_name=str(spec.block_name or ""),
        class_name="_ALNSVNSSolver",
        function_name="solve",
    )
    if line_span is None:
        return None
    start, end = line_span
    lines = source.splitlines()
    content = "\n".join(lines[start - 1 : end])
    truncated = len(content) > max_chars
    if truncated:
        content = content[:max_chars]
    return {
        "content": content,
        "line_start": start,
        "line_end": end,
        "truncated": truncated,
    }


def _assignment_line_span(
    source: str,
    *,
    block_name: str,
    class_name: str,
    function_name: str,
) -> tuple[int, int] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for child in node.body:
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if child.name != function_name:
                continue
            for descendant in ast.walk(child):
                if not isinstance(descendant, ast.Assign):
                    continue
                if not any(
                    _target_name(target) == block_name
                    for target in descendant.targets
                ):
                    continue
                start = int(getattr(descendant, "lineno", 1))
                end = int(getattr(descendant, "end_lineno", start))
                return start, end
    return None


def _target_name(target: ast.AST) -> str | None:
    if isinstance(target, ast.Name):
        return target.id
    return None


def _slice_spec(slice_id: str) -> _SliceSpec | None:
    for spec in _SLICE_SPECS:
        if spec.slice_id == slice_id:
            return spec
    return None


def _surface_supported(surface: str | None) -> bool:
    requested = str(surface or "").strip()
    return requested in {"", _SURFACE}


def _subject_id(subject_id: str | None) -> str:
    return str(subject_id or "").strip() or _SUBJECT_ID


def _safe_snapshot(context: Any) -> dict[str, Any]:
    try:
        payload = build_active_solver_snapshot(context, include_file_previews=False)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_algorithm_files(context: Any) -> tuple[dict[str, Any], ...]:
    try:
        files = list_algorithm_files_payload(context, include_inactive=False)
    except Exception:
        return ()
    return tuple(item for item in files if isinstance(item, dict))


def _file_digests(
    snapshot: Mapping[str, Any],
    files: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    source_digest = snapshot.get("source_digest")
    if isinstance(source_digest, Mapping):
        raw_files = source_digest.get("files")
        if isinstance(raw_files, Mapping):
            normalized = {
                str(path): str(digest)
                for path, digest in raw_files.items()
                if str(path).strip() and str(digest).strip()
            }
            if normalized:
                return normalized
    return {
        str(item.get("file_path")): str(item.get("sha256") or item.get("digest") or "")
        for item in files
        if str(item.get("file_path") or "").strip()
    }


def _snapshot_digest(snapshot: Mapping[str, Any]) -> str:
    source_digest = snapshot.get("source_digest")
    if isinstance(source_digest, Mapping):
        digest = str(source_digest.get("snapshot_digest") or "").strip()
        if digest:
            return digest
    return ""


def _solver_design_surface(context: Any) -> Any:
    problem_spec = getattr(context, "problem_spec", None)
    for surface in getattr(problem_spec, "research_surfaces", ()) or ():
        if str(getattr(surface, "name", "") or "").strip() == _SURFACE:
            return surface
    return None


def _fallback_telemetry_role(field: str) -> str:
    lowered = field.lower()
    if "elapsed_ms" in lowered or "phase_runtime" in lowered:
        return "budget"
    if "error" in lowered or "valid" in lowered:
        return "safety"
    if "iterations" in lowered or "moves" in lowered or "active" in lowered:
        return "activity"
    if "delta" in lowered or "improving" in lowered or "objective" in lowered:
        return "effect"
    return "debug"


def _source_max_chars(max_chars: int | None) -> int:
    requested = _DEFAULT_BODY_CHARS if max_chars is None else int(max_chars)
    return max(_DEFAULT_BODY_CHARS, min(_MAX_BODY_CHARS, requested))


def _token_estimate(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _slice_token_hint(spec: _SliceSpec) -> int:
    if spec.slice_kind == "registry_block":
        return 80
    if spec.symbol in {"_ALNSVNSSolver.solve", "_ALNSVNSSolver._initial_solution"}:
        return 700
    if spec.file_path.endswith("local_search.py"):
        return 450
    return 300


def _compact_strings(value: Any, *, limit: int) -> list[str]:
    strings: list[str] = []
    if isinstance(value, Mapping):
        iterable = value.values()
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        iterable = value
    else:
        iterable = (value,)
    for item in iterable:
        text = str(item or "").strip()
        if text and text not in strings:
            strings.append(text)
        if len(strings) >= limit:
            break
    return strings


def _digest_mapping(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return _sha256(encoded)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_SLICE_SPECS: tuple[_SliceSpec, ...] = (
    _SliceSpec(
        "cvrp.slice.entrypoint.solve",
        "policies/baseline_algorithm.py",
        ("solve",),
        "Show the active solver-design entrypoint and scheduler handoff.",
        "body",
        "symbol_body",
        symbol="solve",
    ),
    _SliceSpec(
        "cvrp.slice.scheduler.solve",
        "policies/baseline_modules/scheduler.py",
        ("_ALNSVNSSolver.solve",),
        "Show the bounded ALNS/VNS scheduler integration loop.",
        "body",
        "integration_block",
        symbol="_ALNSVNSSolver.solve",
    ),
    _SliceSpec(
        "cvrp.slice.scheduler.initial_solution",
        "policies/baseline_modules/scheduler.py",
        ("_ALNSVNSSolver._initial_solution",),
        "Show the construction selection, initial VNS, and size70 fallback integration.",
        "body",
        "integration_block",
        symbol="_ALNSVNSSolver._initial_solution",
    ),
    _SliceSpec(
        "cvrp.slice.scheduler.size70_two_opt_polish",
        "policies/baseline_modules/scheduler.py",
        ("_ALNSVNSSolver._run_size70_two_opt_polish",),
        "Show the scheduler-owned size70 two-opt fallback polish integration.",
        "body",
        "integration_block",
        symbol="_ALNSVNSSolver._run_size70_two_opt_polish",
    ),
    _SliceSpec(
        "cvrp.slice.scheduler.destroy_ops",
        "policies/baseline_modules/scheduler.py",
        ("destroy_ops",),
        "Show the active destroy operator registry block.",
        "excerpt",
        "registry_block",
        block_name="destroy_ops",
    ),
    _SliceSpec(
        "cvrp.slice.scheduler.repair_ops",
        "policies/baseline_modules/scheduler.py",
        ("repair_ops",),
        "Show the active repair operator registry block.",
        "excerpt",
        "registry_block",
        block_name="repair_ops",
    ),
    _SliceSpec(
        "cvrp.slice.local_search.default_vns_operators",
        "policies/baseline_modules/local_search.py",
        ("_default_vns_operators",),
        "Show the active VNS/local-search operator registry.",
        "body",
        "symbol_body",
        symbol="_default_vns_operators",
    ),
    _SliceSpec(
        "cvrp.slice.local_search.vns",
        "policies/baseline_modules/local_search.py",
        ("_vns",),
        "Show the VNS loop that consumes local-search operators.",
        "body",
        "symbol_body",
        symbol="_vns",
    ),
    _SliceSpec(
        "cvrp.slice.local_search.or_opt",
        "policies/baseline_modules/local_search.py",
        ("_or_opt",),
        "Show the shared Or-opt helper used by length-1/2/3 wrappers.",
        "body",
        "symbol_body",
        symbol="_or_opt",
    ),
    _SliceSpec(
        "cvrp.slice.local_search.two_opt_star",
        "policies/baseline_modules/local_search.py",
        ("_two_opt_star",),
        "Show the cross-route tail-exchange local-search helper.",
        "body",
        "symbol_body",
        symbol="_two_opt_star",
    ),
    _SliceSpec(
        "cvrp.slice.destroy_repair.shaw_removal",
        "policies/baseline_modules/destroy_repair.py",
        ("_shaw_removal",),
        "Show the related-removal destroy helper body.",
        "body",
        "symbol_body",
        symbol="_shaw_removal",
    ),
    _SliceSpec(
        "cvrp.slice.destroy_repair.regret_insertion",
        "policies/baseline_modules/destroy_repair.py",
        ("_regret_insertion",),
        "Show the shared regret insertion repair helper body.",
        "body",
        "symbol_body",
        symbol="_regret_insertion",
    ),
    _SliceSpec(
        "cvrp.slice.construction.capacity_balanced",
        "policies/baseline_modules/construction.py",
        ("_capacity_balanced_construction",),
        "Show the route-limit guarded construction helper.",
        "body",
        "symbol_body",
        symbol="_capacity_balanced_construction",
    ),
    _SliceSpec(
        "cvrp.slice.acceptance.adaptive_weights",
        "policies/baseline_modules/acceptance.py",
        ("_AdaptiveWeights",),
        "Show adaptive operator weighting behavior.",
        "body",
        "symbol_body",
        symbol="_AdaptiveWeights",
    ),
    _SliceSpec(
        "cvrp.slice.acceptance.simulated_annealing",
        "policies/baseline_modules/acceptance.py",
        ("_SimulatedAnnealing",),
        "Show non-improving move acceptance behavior.",
        "body",
        "symbol_body",
        symbol="_SimulatedAnnealing",
    ),
)


__all__ = ["CvrpActiveSolverMapProvider"]
