"""Tainted candidate-vs-champion smoke micro-benchmark helpers."""

from __future__ import annotations

from typing import Any, Mapping

from .constants import _ALGORITHM_SMOKE_MAX_SCREENING_CASES
from .models import _RuntimeSmokeCase
from .utils import _float_or_none, _limit_text


def _solver_design_micro_benchmark_result(
    *,
    candidate_raw: Mapping[str, Any],
    candidate_run: Mapping[str, Any],
    champion_raw: Mapping[str, Any] | None,
    champion_run: Mapping[str, Any],
    smoke_case: _RuntimeSmokeCase,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "case": smoke_case.rel_path,
        "seed": smoke_case.seed,
        "label": smoke_case.label,
        "candidate_elapsed_ms": candidate_run.get("elapsed_ms"),
        "champion_elapsed_ms": champion_run.get("elapsed_ms"),
    }
    if champion_raw is None:
        result.update(
            {
                "comparison": "incomparable",
                "champion_failed": True,
                "champion_error_category": champion_run.get("error_category"),
                "champion_detail": _limit_text(
                    str(champion_run.get("detail") or ""),
                    320,
                ),
            }
        )
        return result

    comparison = _compare_solver_design_raw_outputs(candidate_raw, champion_raw)
    result.update(comparison)
    try:
        result["runtime_delta_ms"] = int(candidate_run.get("elapsed_ms") or 0) - int(
            champion_run.get("elapsed_ms") or 0
        )
    except (TypeError, ValueError):
        pass
    return result


def _compare_solver_design_raw_outputs(
    candidate_raw: Mapping[str, Any],
    champion_raw: Mapping[str, Any],
) -> dict[str, Any]:
    candidate_obj = candidate_raw.get("objective")
    champion_obj = champion_raw.get("objective")
    if not isinstance(candidate_obj, Mapping) or not isinstance(champion_obj, Mapping):
        return {"comparison": "incomparable"}
    candidate_fleet = _float_or_none(candidate_obj.get("fleet_violation"))
    champion_fleet = _float_or_none(champion_obj.get("fleet_violation"))
    candidate_distance = _float_or_none(candidate_obj.get("total_distance"))
    champion_distance = _float_or_none(champion_obj.get("total_distance"))
    comparison = "tie"
    delta = 0.0
    decisive_metric = "total_distance"
    if candidate_fleet is not None and champion_fleet is not None:
        fleet_delta = champion_fleet - candidate_fleet
        if abs(fleet_delta) > 1e-9:
            comparison = "win" if fleet_delta > 0 else "loss"
            delta = fleet_delta
            decisive_metric = "fleet_violation"
    if (
        comparison == "tie"
        and candidate_distance is not None
        and champion_distance is not None
    ):
        distance_delta = champion_distance - candidate_distance
        if abs(distance_delta) > 1e-9:
            comparison = "win" if distance_delta > 0 else "loss"
            delta = distance_delta
        else:
            delta = 0.0
    return {
        "comparison": comparison,
        "delta": delta,
        "decisive_metric": decisive_metric,
        "candidate_objective": {
            key: candidate_obj.get(key)
            for key in ("fleet_violation", "total_distance")
            if key in candidate_obj
        },
        "champion_objective": {
            key: champion_obj.get(key)
            for key in ("fleet_violation", "total_distance")
            if key in champion_obj
        },
    }


def _solver_design_micro_benchmark_issue(
    micro_results: list[dict[str, Any]],
) -> str | None:
    comparable = [
        result
        for result in micro_results
        if result.get("comparison") in {"win", "loss", "tie"}
    ]
    if not comparable:
        return None
    losses = sum(1 for result in comparable if result.get("comparison") == "loss")
    wins = sum(1 for result in comparable if result.get("comparison") == "win")
    ties = sum(1 for result in comparable if result.get("comparison") == "tie")
    if losses == len(comparable) and wins == 0 and ties == 0:
        return (
            "tainted micro-benchmark objective regression: candidate lost all "
            f"{len(comparable)} comparable smoke case(s) against the current champion"
        )
    return None


def _compact_solver_design_micro_benchmark(
    micro_results: list[dict[str, Any]],
) -> dict[str, Any]:
    comparable = [
        result
        for result in micro_results
        if result.get("comparison") in {"win", "loss", "tie"}
    ]
    wins = sum(1 for result in comparable if result.get("comparison") == "win")
    losses = sum(1 for result in comparable if result.get("comparison") == "loss")
    ties = sum(1 for result in comparable if result.get("comparison") == "tie")
    return {
        "non_promotional": True,
        "tainted_debug": True,
        "comparable_cases": len(comparable),
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "results": [
            {
                key: result.get(key)
                for key in (
                    "label",
                    "case",
                    "seed",
                    "comparison",
                    "delta",
                    "decisive_metric",
                    "runtime_delta_ms",
                )
                if key in result
            }
            for result in micro_results[:_ALGORITHM_SMOKE_MAX_SCREENING_CASES + 1]
        ],
    }
