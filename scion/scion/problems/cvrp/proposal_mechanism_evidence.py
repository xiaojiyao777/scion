"""Problem-owned compact CVRP mechanism evidence for the next proposal turn."""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any


_TRACE_FIELD = "solver_algorithm_alns_iteration_trace"


class CvrpProposalMechanismEvidenceProvider:
    """Summarize measured ALNS events without exposing raw iteration traces."""

    def summarize_proposal_mechanism_evidence(
        self,
        *,
        stage: str,
        selected_surface: str | None,
        runtime_pairs: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        if stage != "screening" or selected_surface != "solver_design":
            return {}

        candidate = _side_summary(runtime_pairs, side="candidate_runtime")
        champion = _side_summary(runtime_pairs, side="champion_runtime")
        if not candidate["trace_pairs"] and not champion["trace_pairs"]:
            return {}

        sources = Counter(
            str(pair.get("champion_result_source") or "unknown")
            for pair in runtime_pairs
        )
        return {
            "schema_version": "scion.cvrp.alns_proposal_mechanism_evidence.v1",
            "source_runtime_field": _TRACE_FIELD,
            "trace_coverage": {
                "valid_pairs": len(runtime_pairs),
                "candidate_trace_pairs": candidate.pop("trace_pairs"),
                "champion_trace_pairs": champion.pop("trace_pairs"),
                "champion_result_sources": dict(sorted(sources.items())),
            },
            "candidate": candidate,
            "champion": champion,
            "comparison": {
                key: {
                    "candidate": candidate[key],
                    "champion": champion[key],
                    "candidate_minus_champion": candidate[key] - champion[key],
                }
                for key in ("route_limit", "repair_error")
            },
        }


def _side_summary(
    runtime_pairs: Sequence[Mapping[str, Any]],
    *,
    side: str,
) -> dict[str, Any]:
    repairs: dict[str, dict[str, Any]] = {}
    trace_pairs = 0
    iterations = 0
    route_limit = 0
    repair_error = 0
    for pair in runtime_pairs:
        runtime = pair.get(side)
        if not isinstance(runtime, Mapping):
            continue
        trace = runtime.get(_TRACE_FIELD)
        if not isinstance(trace, list) or not trace:
            continue
        trace_pairs += 1
        for event in trace:
            if not isinstance(event, Mapping):
                continue
            repair = str(event.get("repair_operator") or "unknown").strip() or "unknown"
            record = repairs.setdefault(
                repair,
                {
                    "attempts": 0,
                    "accepted": 0,
                    "best_updates": 0,
                    "route_limit": 0,
                    "repair_error": 0,
                    "elapsed_ms_observed": 0,
                    "elapsed_ms_total": 0,
                },
            )
            iterations += 1
            record["attempts"] += 1
            if event.get("accepted") is True:
                record["accepted"] += 1
            if event.get("best_improved") is True:
                record["best_updates"] += 1
            reason = str(event.get("acceptance_reason") or "").strip()
            if reason == "route_limit":
                route_limit += 1
                record["route_limit"] += 1
            elif reason == "repair_error":
                repair_error += 1
                record["repair_error"] += 1
            elapsed = _event_elapsed_ms(event)
            if elapsed is not None:
                record["elapsed_ms_observed"] += 1
                record["elapsed_ms_total"] += elapsed

    rendered_repairs: dict[str, Any] = {}
    for repair in sorted(repairs):
        record = repairs[repair]
        observed = record.pop("elapsed_ms_observed")
        total = record.pop("elapsed_ms_total")
        rendered_repairs[repair] = {
            **record,
            "elapsed_ms": {
                "observed": observed,
                "total": total,
                "mean": round(total / observed, 2) if observed else None,
            },
        }
    return {
        "trace_pairs": trace_pairs,
        "iterations": iterations,
        "repairs": rendered_repairs,
        "route_limit": route_limit,
        "repair_error": repair_error,
    }


def _event_elapsed_ms(event: Mapping[str, Any]) -> int | None:
    before = _nonnegative_int(event.get("elapsed_ms_before"))
    after = _nonnegative_int(event.get("elapsed_ms_after"))
    if before is None or after is None or after < before:
        return None
    return after - before


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


__all__ = ["CvrpProposalMechanismEvidenceProvider"]
