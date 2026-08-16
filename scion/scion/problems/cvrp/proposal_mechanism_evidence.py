"""Problem-owned compact CVRP search-allocation evidence for proposals."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from scion.problems.cvrp.evidence.search_allocation import (
    build_search_allocation_evidence,
    has_search_allocation_observations,
)


_PROPOSAL_SCHEMA_VERSION = "scion.cvrp.proposal_mechanism_evidence.v1"
_COMPARISON_COLUMNS = (
    "candidate",
    "champion",
    "candidate_minus_champion",
)


class CvrpProposalMechanismEvidenceProvider:
    """Project screening runtime into compact, proposal-only CVRP diagnostics."""

    def summarize_proposal_mechanism_evidence(
        self,
        *,
        stage: str,
        selected_surface: str | None,
        runtime_pairs: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        if stage != "screening" or selected_surface != "solver_design":
            return {}
        packet = build_search_allocation_evidence(runtime_pairs)
        if not has_search_allocation_observations(packet):
            return {}
        return _project_for_proposal(packet)


def _project_for_proposal(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Keep fixed, actionable semantics while raw evidence remains in lineage.

    The search-allocation builder deliberately emits a lossless diagnostic packet.
    A proposal does not need its candidate and champion side summaries repeated
    beside the paired comparison.  This projection is schema-driven (never sized
    or token-triggered) and cannot influence a protocol decision.
    """

    comparison = _mapping(packet.get("comparison"))
    coverage = _mapping(packet.get("coverage"))
    candidate_coverage = _mapping(coverage.get("candidate"))
    champion_coverage = _mapping(coverage.get("champion"))
    paired_coverage = _mapping(coverage.get("paired"))

    return {
        "schema_version": _PROPOSAL_SCHEMA_VERSION,
        "evidence_scope": packet.get("evidence_scope"),
        "hypothesis_attribution": packet.get("hypothesis_attribution"),
        "interpretation_constraint": packet.get("interpretation_constraint"),
        "comparison_columns": list(_COMPARISON_COLUMNS),
        "coverage_columns": ["candidate", "champion", "paired"],
        "coverage": {
            "provider_inputs": coverage.get("provider_inputs"),
            "runtime_pairs": coverage.get("runtime_pairs"),
            "missing_semantics": coverage.get("missing_semantics"),
            "runtime_mapping_pairs": [
                candidate_coverage.get("runtime_mapping_pairs"),
                champion_coverage.get("runtime_mapping_pairs"),
                None,
            ],
            "observed_runtime_fields": [
                candidate_coverage.get("observed_runtime_fields"),
                champion_coverage.get("observed_runtime_fields"),
                None,
            ],
            "trace_pairs": [
                candidate_coverage.get("trace_pairs"),
                champion_coverage.get("trace_pairs"),
                paired_coverage.get("trace_pairs"),
            ],
            "phase_accounting_pairs": [
                candidate_coverage.get("phase_accounting_pairs"),
                champion_coverage.get("phase_accounting_pairs"),
                paired_coverage.get("phase_accounting_pairs"),
            ],
            "malformed_trace_events": [
                candidate_coverage.get("malformed_trace_events"),
                champion_coverage.get("malformed_trace_events"),
                None,
            ],
        },
        "paired_comparison": {
            "solver_algorithm_elapsed_ms": _comparison_value(
                comparison.get("solver_algorithm_elapsed_ms")
            ),
            "runtime_residual_ms": _comparison_value(
                comparison.get("runtime_residual_ms")
            ),
            "phase_runtime_share": _comparison_map(
                comparison.get("phase_runtime_share")
            ),
            "alns": _comparison_map(comparison.get("alns")),
            "post_repair_polish": _comparison_map(
                comparison.get("post_repair_polish")
            ),
            "move_phases": _nested_comparison_map(
                comparison.get("move_phases")
            ),
        },
        "operator_comparison": {
            "pair_key_encoding": coverage.get(
                "destroy_repair_pair_key_encoding"
            ),
            "destroy": _operator_table(
                comparison.get("destroy_operators"),
                fields=("selected",),
            ),
            "repair": _operator_table(
                comparison.get("repair_operators"),
                fields=(
                    "selected",
                    "invoked",
                    "completed",
                    "accepted",
                    "best_updates",
                ),
            ),
            "destroy_repair_pair": _operator_table(
                comparison.get("destroy_repair_pairs"),
                fields=(
                    "selected",
                    "invoked",
                    "completed",
                    "accepted",
                    "best_updates",
                ),
            ),
        },
        "instance_feasibility": packet.get("instance_feasibility", {}),
    }


def _operator_table(value: Any, *, fields: tuple[str, ...]) -> dict[str, Any]:
    table = _mapping(value)
    projected: dict[str, Any] = {}
    for name in sorted(table):
        record = _mapping(table[name])
        compact = {
            field: metric
            for field in fields
            if (metric := _comparison_value(record.get(field))) is not None
        }
        timing = _mapping(record.get("selected_iteration_elapsed_ms"))
        mean = _comparison_value(timing.get("mean"))
        if mean is not None:
            compact["mean_selected_iteration_elapsed_ms"] = mean
        if compact:
            projected[str(name)] = compact
    return projected


def _nested_comparison_map(value: Any) -> dict[str, Any]:
    return {
        str(name): compact
        for name, metrics in sorted(_mapping(value).items())
        if (compact := _comparison_map(metrics))
    }


def _comparison_map(value: Any) -> dict[str, Any]:
    return {
        str(name): metric
        for name, raw_metric in sorted(_mapping(value).items())
        if (metric := _comparison_value(raw_metric)) is not None
    }


def _comparison_value(value: Any) -> list[Any] | None:
    metric = _mapping(value)
    values = [metric.get(column) for column in _COMPARISON_COLUMNS]
    return None if all(item is None for item in values) else values


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


__all__ = ["CvrpProposalMechanismEvidenceProvider"]
