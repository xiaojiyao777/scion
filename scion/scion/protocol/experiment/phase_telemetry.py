from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from scion.core.models import RunResult
from scion.runtime.surface_telemetry import (
    declared_phase_runtime_fields,
    declared_phase_telemetry_buckets,
    find_research_surface,
    runtime_path_value,
)

from .values import _coerce_number, _round_runtime_number


def _phase_telemetry_summary_template(
    *,
    problem_spec: Any | None = None,
    selected_surface: str | None = None,
) -> dict[str, Any]:
    surface = find_research_surface(problem_spec, selected_surface)
    fields = declared_phase_runtime_fields(surface, problem_spec=problem_spec)
    buckets = declared_phase_telemetry_buckets(surface, problem_spec=problem_spec)
    if not fields and not buckets:
        return {}
    return {
        "selected_surface": selected_surface,
        "phase_runtime_fields": list(fields),
        "declared_buckets": list(buckets),
        "candidate_pairs": 0,
        "runtime_observed_pairs": 0,
        "_buckets": {},
    }


def _record_phase_telemetry_sample(
    result: RunResult,
    summary: dict[str, Any],
) -> None:
    if not summary:
        return
    summary["candidate_pairs"] += 1
    runtime = getattr(getattr(result, "output", None), "runtime", None)
    if not isinstance(runtime, Mapping):
        return
    summary["runtime_observed_pairs"] += 1
    fields = tuple(summary.get("phase_runtime_fields") or ())
    declared = set(str(item) for item in summary.get("declared_buckets") or ())
    for field in fields:
        value = runtime_path_value(runtime, str(field))
        if not isinstance(value, Mapping):
            continue
        for bucket, raw_number in value.items():
            bucket_name = str(bucket or "").strip()
            if not bucket_name:
                continue
            number = _coerce_number(raw_number)
            if number is None:
                continue
            _record_bucket(
                summary.setdefault("_buckets", {}),
                bucket_name,
                number,
                declared=bucket_name in declared if declared else None,
            )


def _finalize_phase_telemetry_summary(summary: dict[str, Any]) -> dict[str, Any]:
    if not summary:
        return {}
    buckets: dict[str, Any] = {}
    for name, stats in sorted((summary.get("_buckets") or {}).items()):
        count = int(stats.get("observed_count", 0) or 0)
        if count <= 0:
            continue
        buckets[name] = {
            "declared": stats.get("declared"),
            "observed_count": count,
            "weighted_sum_ms": _round_runtime_number(stats.get("weighted_sum", 0.0)),
            "min_ms": _round_runtime_number(stats.get("min")),
            "max_ms": _round_runtime_number(stats.get("max")),
            "zero_count": int(stats.get("zero_count", 0) or 0),
            "nonzero_count": int(stats.get("nonzero_count", 0) or 0),
        }
    return {
        "selected_surface": summary.get("selected_surface"),
        "phase_runtime_fields": list(summary.get("phase_runtime_fields") or ()),
        "declared_buckets": list(summary.get("declared_buckets") or ()),
        "candidate_pairs": int(summary.get("candidate_pairs", 0) or 0),
        "runtime_observed_pairs": int(
            summary.get("runtime_observed_pairs", 0) or 0
        ),
        "buckets": buckets,
    }


def _format_phase_telemetry_summary(summary: Mapping[str, Any]) -> str:
    if not summary:
        return ""
    buckets = summary.get("buckets")
    if not isinstance(buckets, Mapping) or not buckets:
        return ""
    bucket_text = ",".join(str(name) for name in sorted(buckets)[:8])
    return (
        " phase_telemetry="
        f"observed_pairs={summary.get('runtime_observed_pairs', 0)}"
        f" buckets={bucket_text}"
    )


def _record_bucket(
    buckets: dict[str, dict[str, Any]],
    name: str,
    number: float,
    *,
    declared: bool | None,
) -> None:
    stats = buckets.setdefault(
        name,
        {
            "declared": declared,
            "observed_count": 0,
            "weighted_sum": 0.0,
            "min": None,
            "max": None,
            "zero_count": 0,
            "nonzero_count": 0,
        },
    )
    if stats.get("declared") is None:
        stats["declared"] = declared
    stats["observed_count"] += 1
    stats["weighted_sum"] += number
    stats["min"] = number if stats["min"] is None else min(stats["min"], number)
    stats["max"] = number if stats["max"] is None else max(stats["max"], number)
    if abs(number) <= 1e-12:
        stats["zero_count"] += 1
    else:
        stats["nonzero_count"] += 1


__all__ = [
    "_finalize_phase_telemetry_summary",
    "_format_phase_telemetry_summary",
    "_phase_telemetry_summary_template",
    "_record_phase_telemetry_sample",
]
