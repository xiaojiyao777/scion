"""Generic runtime budget saturation diagnostics."""
from __future__ import annotations

import statistics
from collections.abc import Sequence
from typing import Any, Mapping

RUNTIME_BUDGET_DIAGNOSTIC_SCHEMA = "scion.runtime_budget_diagnostic.v1"
TINY_RUNTIME_BUDGET_SATURATION = "TINY_RUNTIME_BUDGET_SATURATION"
SCREENING_RUNTIME_BUDGET_SATURATION = "SCREENING_RUNTIME_BUDGET_SATURATION"

_TINY_PAIR_LIMIT = 4
_TINY_SATURATION_RATIO = 0.75
_SCREENING_SATURATION_RATIO = 0.90


def runtime_budget_diagnostic(
    *,
    stage: Any,
    time_limit_sec: float | int | None,
    candidate_elapsed_ms: Sequence[Any] = (),
    champion_elapsed_ms: Sequence[Any] = (),
    total_pairs: int | None = None,
) -> dict[str, Any] | None:
    """Return a repairable diagnostic when tiny/screening runs saturate budget."""
    stage_value = str(getattr(stage, "value", stage) or "").strip().lower()
    if stage_value not in {"screening", "smoke", "proposal_smoke"}:
        return None
    limit_ms = _positive_float(time_limit_sec)
    if limit_ms is None:
        return None
    limit_ms *= 1000.0
    if limit_ms <= 0:
        return None

    candidate_samples = _elapsed_samples(candidate_elapsed_ms)
    champion_samples = _elapsed_samples(champion_elapsed_ms)
    if not candidate_samples and not champion_samples:
        return None

    observed_pairs = int(total_pairs or 0)
    if observed_pairs <= 0:
        observed_pairs = max(len(candidate_samples), len(champion_samples))
    candidate_summary = _sample_summary(candidate_samples, limit_ms)
    champion_summary = _sample_summary(champion_samples, limit_ms)
    saturation_ratio = max(
        candidate_summary.get("max_budget_ratio") or 0.0,
        champion_summary.get("max_budget_ratio") or 0.0,
    )
    median_ratio = max(
        candidate_summary.get("median_budget_ratio") or 0.0,
        champion_summary.get("median_budget_ratio") or 0.0,
    )

    tiny = observed_pairs <= _TINY_PAIR_LIMIT
    threshold = _TINY_SATURATION_RATIO if tiny else _SCREENING_SATURATION_RATIO
    if saturation_ratio < threshold and median_ratio < threshold:
        return None

    code = (
        TINY_RUNTIME_BUDGET_SATURATION
        if tiny
        else SCREENING_RUNTIME_BUDGET_SATURATION
    )
    scope = "Tiny runtime" if tiny else "Screening runtime"
    return {
        "schema": RUNTIME_BUDGET_DIAGNOSTIC_SCHEMA,
        "code": code,
        "stage": stage_value,
        "severity": "warn",
        "repairable": True,
        "total_pairs": observed_pairs,
        "time_limit_ms": round(limit_ms, 3),
        "threshold_ratio": threshold,
        "saturation_ratio": round(saturation_ratio, 4),
        "candidate": candidate_summary,
        "champion": champion_summary,
        "guidance": (
            f"{scope} is close to the per-run time limit. Reduce the "
            "candidate's per-case work before formal screening by adding time "
            "polling, smaller bounded candidate sets, earlier exits, or a "
            "cheaper schedule."
        ),
    }


def format_runtime_budget_diagnostic(summary: Mapping[str, Any] | None) -> str:
    """Return a compact prompt-facing runtime budget diagnostic suffix."""
    if not isinstance(summary, Mapping) or not summary:
        return ""
    code = str(summary.get("code") or "").strip()
    if not code:
        return ""
    candidate = summary.get("candidate")
    champion = summary.get("champion")
    candidate_ratio = (
        candidate.get("max_budget_ratio")
        if isinstance(candidate, Mapping)
        else None
    )
    champion_ratio = (
        champion.get("max_budget_ratio")
        if isinstance(champion, Mapping)
        else None
    )
    parts = [f"runtime_budget_diagnostic={code}"]
    if candidate_ratio is not None:
        parts.append(f"candidate_budget_ratio={candidate_ratio}")
    if champion_ratio is not None:
        parts.append(f"champion_budget_ratio={champion_ratio}")
    if summary.get("total_pairs") is not None:
        parts.append(f"total_pairs={summary.get('total_pairs')}")
    return " " + " ".join(parts)


def protocol_runtime_budget_diagnostic(
    protocol_result: Any,
) -> dict[str, Any] | None:
    surface_summary = getattr(
        protocol_result,
        "candidate_surface_runtime_summary",
        None,
    )
    if not isinstance(surface_summary, Mapping):
        return None
    diagnostic = surface_summary.get("runtime_budget_diagnostic")
    return dict(diagnostic) if isinstance(diagnostic, Mapping) else None


def runtime_budget_diagnostic_code(protocol_result: Any) -> str:
    diagnostic = protocol_runtime_budget_diagnostic(protocol_result)
    if not diagnostic:
        return ""
    code = str(diagnostic.get("code") or "").strip()
    if code in {TINY_RUNTIME_BUDGET_SATURATION, SCREENING_RUNTIME_BUDGET_SATURATION}:
        return code
    return ""


def runtime_budget_diagnostic_detected(protocol_result: Any) -> bool:
    return bool(runtime_budget_diagnostic_code(protocol_result))


def _elapsed_samples(values: Sequence[Any]) -> list[float]:
    samples: list[float] = []
    for value in values:
        number = _positive_float(value)
        if number is not None:
            samples.append(number)
    return samples


def _positive_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return number


def _sample_summary(samples: Sequence[float], limit_ms: float) -> dict[str, Any]:
    if not samples:
        return {"count": 0}
    median_ms = statistics.median(samples)
    max_ms = max(samples)
    return {
        "count": len(samples),
        "median_elapsed_ms": round(median_ms, 3),
        "max_elapsed_ms": round(max_ms, 3),
        "median_budget_ratio": round(median_ms / limit_ms, 4),
        "max_budget_ratio": round(max_ms / limit_ms, 4),
    }


__all__ = [
    "RUNTIME_BUDGET_DIAGNOSTIC_SCHEMA",
    "SCREENING_RUNTIME_BUDGET_SATURATION",
    "TINY_RUNTIME_BUDGET_SATURATION",
    "format_runtime_budget_diagnostic",
    "protocol_runtime_budget_diagnostic",
    "runtime_budget_diagnostic",
    "runtime_budget_diagnostic_code",
    "runtime_budget_diagnostic_detected",
]
