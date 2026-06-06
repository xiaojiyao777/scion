"""Tainted candidate-vs-champion smoke micro-benchmark helpers."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from .constants import _ALGORITHM_SMOKE_MAX_SCREENING_CASES
from .models import _RuntimeSmokeCase
from .utils import _limit_text


class _SolverDesignSmokeComparisonProvider(Protocol):
    def solver_design_smoke_comparison(
        self,
        *,
        candidate_raw: Mapping[str, Any],
        champion_raw: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        """Return a problem-owned candidate-vs-champion smoke comparison."""


def _solver_design_micro_benchmark_result(
    *,
    candidate_raw: Mapping[str, Any],
    candidate_run: Mapping[str, Any],
    champion_raw: Mapping[str, Any] | None,
    champion_run: Mapping[str, Any],
    smoke_case: _RuntimeSmokeCase,
    provider: _SolverDesignSmokeComparisonProvider | None = None,
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

    comparison = _compare_solver_design_raw_outputs(
        candidate_raw,
        champion_raw,
        provider=provider,
    )
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
    *,
    provider: _SolverDesignSmokeComparisonProvider | None = None,
) -> dict[str, Any]:
    if provider is None:
        return {"comparison": "incomparable"}
    hook = getattr(provider, "solver_design_smoke_comparison", None)
    if hook is None:
        return {"comparison": "incomparable"}
    try:
        raw_comparison = hook(
            candidate_raw=candidate_raw,
            champion_raw=champion_raw,
        )
    except Exception as exc:
        return {
            "comparison": "incomparable",
            "comparison_error_category": "provider_exception",
            "comparison_detail": _limit_text(str(exc), 320),
        }
    if not isinstance(raw_comparison, Mapping):
        return {
            "comparison": "incomparable",
            "comparison_error_category": "provider_invalid_result",
        }
    comparison = str(raw_comparison.get("comparison") or "")
    if comparison not in {"win", "loss", "tie", "incomparable"}:
        return {
            "comparison": "incomparable",
            "comparison_error_category": "provider_invalid_comparison",
            "comparison_detail": _limit_text(comparison, 120),
        }
    return dict(raw_comparison)


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
